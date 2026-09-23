"""Physical, focal-allocation, lifecycle and neutral-UI tests for P16-2C-E."""
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
from nca8_executive import NavigationRuntimeV1
import nca8_feeding_demo
import nca8_menu
from nca8_runtime import Nca8SessionV1
import nca8_seek_attention_demo as demo
import nca8_seek_nipple_demo as collector

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_seeking_attention_v1(case) for case in demo.SEEKING_ATTENTION_CASES_V1}


def advance_to_next_focal(trial):
    for _ in range(4):
        trial.advance_lower()


@pytest.mark.parametrize("case", demo.SEEKING_ATTENTION_CASES_V1)
def test_each_declared_case_has_complete_finite_measured_evidence(results, case):
    result = results[case]
    assert result.review_status == "PASS", result.checks()
    assert len(result.checks()) == 21 and not result.bound_violations
    assert result.evidence.profile.horizon_ticks in (64, 160)
    assert result.evidence.durable_before == result.evidence.durable_after
    assert result.as_dict()["feeding_learning"] == "unimplemented_no_participation"
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("prefix", ["competing", "maintain"])
def test_only_outcome_route_changes_allocation_with_all_nonoutcome_input_fixed(results, prefix):
    on, off = results[prefix + "_on"], results[prefix + "_off"]
    assert on.evidence.local_steps == off.evidence.local_steps
    assert on.evidence.physical_samples == off.evidence.physical_samples
    assert tuple(c.feeding_detail_source for c in on.evidence.cycles) == tuple(c.feeding_detail_source for c in off.evidence.cycles)
    assert tuple(c.seeking_task for c in on.evidence.cycles) == tuple(c.seeking_task for c in off.evidence.cycles)
    assert on.outcomes() == off.outcomes()
    a = next(c for c in on.evidence.cycles if c.calculation.cutoff_tick == 12)
    b = next(c for c in off.evidence.cycles if c.calculation.cutoff_tick == 12)
    assert a.calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
    assert b.calculation.attention.selected_source_state.source_map_ref.map_id == "visual_scene"
    assert a.seeking_attention.allocation.kind == "interpretation" and b.seeking_attention is None
    assert a.calculation.attention.disposition.value == ("switch" if prefix == "competing" else "maintain")
    assert on.metrics()["first_reached_detail_tick"] == off.metrics()["first_reached_detail_tick"] == 24
    assert on.metrics()["oral_commands"] == off.metrics()["oral_commands"]


def test_interpretation_has_no_simultaneous_primitive_target_or_new_projection(results):
    result = results["competing_on"]
    interpreted = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == 12)
    response = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == 16)
    assert interpreted.status == "seeking_interpretation"
    assert interpreted.calculation.navigation.application is None and interpreted.calculation.proposal is None
    assert interpreted.seeking_correspondence.registration is None and interpreted.reservations == ()
    assert response.seeking_attention.allocation.kind == "response_reconsideration"
    assert response.calculation.navigation.application is not None and response.reservations
    assert response.seeking_attention.allocation.interpretation is interpreted.seeking_attention.allocation.interpretation
    assert response.reservations[0].current.committed_tick == 16


def test_prediction_comparison_off_prevents_mismatch_request_not_motor_execution(results):
    on, off = results["competing_on"], results["comparison_off"]
    assert on.evidence.local_steps == off.evidence.local_steps
    assert on.evidence.physical_samples == off.evidence.physical_samples
    assert tuple(item.status for item in off.outcomes()) == ("comparison_disabled", "interrupted")
    assert on.outcomes()[-1].status == off.outcomes()[-1].status == "interrupted"
    assert not off.requests() and not off.interpretations()
    assert off.metrics()["cutoff12_source"] == "visual_scene"


def test_geometric_match_and_touch_remain_different(results):
    nominal, absent = results["nominal_on"], results["no_surface"]
    assert nominal.metrics()["first_reached_detail_tick"] == absent.metrics()["first_reached_detail_tick"] == 12
    assert nominal.metrics()["first_physical_touch_tick"] == 4
    assert absent.metrics()["first_physical_touch_tick"] is None
    assert nominal.outcomes()[0].status == absent.outcomes()[0].status == "matched"
    assert not nominal.requests() and not absent.requests()


def test_historical_endpoint_is_not_substituted_with_latest_sensed_geometry(results):
    recovered = results["historical_resolved"]
    interpretation, = recovered.interpretations()
    original = interpretation.request.outcome
    assert original.evidence.feedback.event_tick == original.claim.due_tick == 8
    assert original.evidence.feedback.available_tick == 9
    assert interpretation.current_source.maternal.visual.event_tick == 11
    assert original.status == "mismatch" and interpretation.status == "historical_resolved"
    assert recovered.metrics()["first_reached_detail_tick"] == 12
    after = results["after_endpoint_drift"]
    assert after.outcomes()[0].status == "matched" and not after.requests()
    assert after.metrics()["first_reached_detail_tick"] == 20


def test_one_partial_residual_is_routine_two_consecutive_residuals_can_escalate(results):
    once, repeated = results["routine_once"], results["persistent"]
    assert once.outcomes()[0].status == repeated.outcomes()[0].status == "mismatch"
    assert once.requests() == ()
    request, = repeated.requests()
    assert request.admitted_tick == 20 and request.outcome.evidence.feedback.event_tick == 16
    assert request.significance == "persistent_executed_seeking_discrepancy"
    assert request.outcome.claim.preview.predicted_separation > .005
    assert repeated.interpretations()[0].status == "historical_resolved"


def test_one_tick_availability_difference_cannot_retroactively_block_a_focal_decision(results):
    before, after = results["support_before_cutoff"], results["support_priority"]
    assert before.metrics()["request_ticks"] == after.metrics()["request_ticks"] == [12]
    assert before.interpretations() == () and after.metrics()["interpretation_ticks"] == [12]
    assert before.metrics()["cutoff12_source"] == "posture_support"
    assert after.metrics()["cutoff12_source"] == "feeding_detail"
    assert (before.requests()[0].request_id, "expired_uninterpreted", 20) in before.dispositions
    for result in (before, after):
        at16 = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == 16)
        assert at16.calculation.attention.selected_source_state.source_map_ref.map_id == "posture_support"
        assert result.metrics()["final_task_status"] == "support_interrupted"
        assert not any(s.command is not None and s.command.oral_drive not in (None, 0) for s in result.evidence.local_steps if s.tick >= 12)


@pytest.mark.parametrize("case", ["dropout", "delayed", "no_capability", "narrowed", "cancelled"])
def test_unknown_interrupted_and_unevaluable_outcomes_do_not_invent_relevance(results, case):
    result = results[case]
    assert not result.requests() and not result.interpretations()
    if case == "narrowed":
        outcome = result.outcomes()[0]
        assert outcome.status == "partly_matched"
        assert dict(outcome.relations)["separation"] == "unevaluable_authorization"
    if case == "no_capability":
        assert all(o.status == "not_applied" and o.command_intervals == 0 for o in result.outcomes())


def test_three_domain_routes_share_the_same_focal_slot_in_continuous_run(results):
    result = results["stand_follow_drift"]
    assert result.metrics()["first_seeking_tick"] == 92
    assert result.metrics()["interpretation_ticks"] == [112]
    for cycle in result.evidence.cycles:
        allocations = (cycle.calculation.outcome_allocation, cycle.calculation.maternal_outcome_allocation,
                       cycle.calculation.seeking_outcome_allocation)
        assert all(item is not None for item in allocations)
        count = sum(item.kind == "interpretation" for item in allocations)
        assert count + int(cycle.calculation.navigation.application is not None) <= 1
    assert result.metrics()["first_reached_detail_tick"] == 124
    assert results["stand_follow"].metrics()["first_reached_detail_tick"] == 112
    # These are different physical conditions, not an isolated performance effect of Attention.


@pytest.mark.parametrize("case", ["cadence_1", "cadence_8"])
def test_cadence_retains_physical_duration_and_original_task_bounds(results, case):
    result = results[case]
    assert result.metrics()["physical_ticks"] == 64
    assert result.evidence.profile.seeking.as_dict()["maximum_focal_opportunities"] == 12
    assert result.evidence.profile.seeking.as_dict()["maximum_physical_ticks"] == 48
    for item in result.interpretations():
        cycle = next(c for c in result.evidence.cycles if c.commitment.cycle_id == item.cycle_id)
        assert item.cycle_id - cycle.seeking_task.task.started_cycle < 12


@pytest.mark.parametrize("capacity", [1, 8])
@pytest.mark.parametrize("case", ["competing_on", "historical_resolved", "support_before_cutoff", "stand_follow_drift"])
def test_trace_retention_cannot_change_full_functional_evidence(results, capacity, case):
    actual = demo.run_seeking_attention_v1(case, trace_capacity=capacity).as_dict()
    expected = results[case].as_dict()
    # Only the observed diagnostic queue size changes. All other exported fields must agree.
    differences = {key for key, value in actual["peak_owner_counts"].items() if expected["peak_owner_counts"].get(key) != value}
    assert differences == {"focal_trace"}
    assert actual["peak_owner_counts"].pop("focal_trace") == capacity
    expected["peak_owner_counts"].pop("focal_trace")
    assert actual == expected


def test_export_and_render_are_detached_readonly_and_do_not_touch_rng(results, monkeypatch):
    result = results["competing_on"]
    original, state = result.as_dict(), random.getstate()
    monkeypatch.setattr(demo, "run_seeking_attention_v1", lambda *a, **k: pytest.fail("inspection reran movement"))
    assert "still_relevant" in demo.render_seeking_attention_v1(result, detail=True)
    detached = result.as_dict()
    detached["cycles"].clear()
    assert result.as_dict() == original and random.getstate() == state


@pytest.mark.parametrize("tamper", ["cycles", "steps", "physics", "counts", "duplicate", "coerced", "durable", "consumptions", "installations", "profile"])
def test_missing_or_tampered_evidence_cannot_pass(results, tamper):
    raw = results["competing_on"].evidence
    changes = {"cycles": {"cycles": ()}, "steps": {"local_steps": ()}, "physics": {"physical_samples": ()},
               "counts": {"peak_counts": ()}, "duplicate": {"peak_counts": raw.peak_counts + raw.peak_counts[:1]},
               "coerced": {"peak_counts": ((raw.peak_counts[0][0], True),) + raw.peak_counts[1:]},
               "durable": {"durable_after": "changed"}, "consumptions": {"handoff_consumptions": 0},
               "installations": {"installations": 0}, "profile": {"profile": replace(raw.profile, competitor_cutoffs=())}}
    result = replace(results["competing_on"], evidence=replace(raw, **changes[tamper]))
    assert result.review_status == "FAIL"


@pytest.mark.parametrize("bad", [None, True, 0, [], "", "COMPETING_ON", "unknown"])
def test_unknown_selector_is_rejected_before_trial_creation(bad, monkeypatch):
    monkeypatch.setattr(demo, "IntegratedRightingTrialV1", lambda *a, **k: pytest.fail("unexpected trial"))
    with pytest.raises(ValueError):
        demo.create_seeking_attention_trial_v1(bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes"])
def test_render_flag_is_not_coerced(results, bad):
    with pytest.raises(TypeError):
        demo.render_seeking_attention_v1(results["competing_on"], detail=bad)


@pytest.mark.parametrize("bad", [True, 0, 4097, 1.5, "8"])
def test_trace_capacity_is_bounded_and_typed(bad):
    with pytest.raises(ValueError):
        demo.create_seeking_attention_trial_v1(trace_capacity=bad)


@pytest.mark.parametrize("case", ["competing_on", "historical_resolved", "support_before_cutoff", "stand_follow_drift"])
def test_cli_outside_repo_exports_identical_complete_shared_result(results, tmp_path, case):
    run = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"), "--seek-attention", "--case", case, "--json"],
                         cwd=tmp_path, capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == json.loads(json.dumps([results[case].as_dict()]))


@pytest.mark.parametrize("arguments", [["--oral"], ["--seek"], ["--seek-outcomes"], ["--case", "unknown"]])
def test_cli_rejects_cross_family_and_unknown_selectors(arguments):
    run = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"), "--seek-attention", *arguments],
                         cwd=ROOT, capture_output=True, text=True, check=False)
    assert run.returncode != 0 and "error" in run.stderr.lower()


def test_menu_retains_completed_results_and_detail_does_not_rerun(results, monkeypatch, capsys):
    choices = iter(("7", "bad", "1", "7", "7", ""))
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    def run(case):
        calls.append(case)
        return results[case]
    monkeypatch.setattr(demo, "run_seeking_attention_v1", run)
    demo.run_seeking_attention_menu_v1()
    assert calls == ["competing_on", "competing_off", "maintain_on", "maintain_off"]
    text = capsys.readouterr().out
    assert "No completed results" in text and "Choose 1-7" in text


def test_parent_route_delegates_without_running_old_experiments(monkeypatch):
    choices, calls = iter(("21", "")), []
    monkeypatch.setattr(nca8_feeding_demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(nca8_feeding_demo, "run_seeking_attention_menu_v1", lambda: calls.append("E"))
    monkeypatch.setattr(nca8_feeding_demo, "run_feeding_detail_v1", lambda *a: pytest.fail("wrong experiment"))
    nca8_feeding_demo.run_feeding_detail_menu_v1()
    assert calls == ["E"]


def test_nested_menu_preserves_existing_a0_session_and_rng(monkeypatch):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    choices = iter(("15", "21", "", "", ""))
    monkeypatch.setattr(nca8_menu.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert before == (session.status(), session.trace_snapshot(), random.getstate())


def test_e_uses_the_existing_collector_not_another_cognitive_loop(monkeypatch):
    calls = []
    original = collector.collect_seek_nipple_evidence_v1
    def collect(trial, profile):
        calls.append(profile.case)
        return original(trial, profile)
    monkeypatch.setattr(demo, "collect_seek_nipple_evidence_v1", collect)
    assert demo.run_seeking_attention_v1().review_status == "PASS"
    assert calls == ["competing_on"]


def test_navigation_disabled_prevents_hidden_interpretation():
    trial = demo.create_seeking_attention_trial_v1()
    for tick in range(12):
        if tick % 4 == 0:
            trial.focal_step(visual_bid_priority=(10, 70) if tick == 8 else None)
        trial.advance_lower()
    trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False)
    cycle = trial.focal_step(visual_bid_priority=(10, 70))
    assert cycle.seeking_attention.created
    assert cycle.seeking_attention.allocation.kind == "navigation_disabled"
    assert cycle.seeking_attention.allocation.interpretation is None
    assert cycle.calculation.navigation.application is None and not cycle.reservations


def test_disabled_ordinary_nomination_is_not_revived_by_outcome():
    trial = demo.create_seeking_attention_trial_v1()
    for tick in range(12):
        if tick % 4 == 0:
            trial.focal_step()
        trial.advance_lower()
    source = trial.core.feeding_detail
    source._profile = replace(source.profile, attention_enabled=False)  # Explicit consumer-lesion fixture.
    cycle = trial.focal_step()
    assert cycle.seeking_attention.created and cycle.seeking_attention.source_bid is None
    assert cycle.seeking_attention.allocation.kind == "other_source"
    assert not cycle.reservations


def test_reset_closes_old_source_route_and_replaces_all_ownership():
    trial = demo.create_seeking_attention_trial_v1()
    first = trial.focal_step()
    old = trial.core.feeding_detail.outcome_attention
    trial.advance_lower()
    trial.reset()
    assert old is not trial.core.feeding_detail.outcome_attention
    assert old._closed and old.pending() == ()
    assert trial.tick == 0 and trial.latest_feedback.stream.generation == 2
    assert trial.focal_step().seeking_attention.created == ()
    with pytest.raises((ValueError, RuntimeError)):
        old.allocate(first.calculation.navigation.wnm, cycle_id=1)


@pytest.mark.parametrize("after_effect", [False, True])
def test_physical_fault_closes_relevance_without_retrying(monkeypatch, after_effect):
    trial = demo.create_seeking_attention_trial_v1()
    trial.focal_step()
    original, calls = MotorWorldV1.step, []
    def fail(world, command):
        calls.append(command)
        if after_effect:
            original(world, command)
        raise RuntimeError("injected physical fault")
    monkeypatch.setattr(MotorWorldV1, "step", fail)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.stopped and trial.tick == int(after_effect)
    assert trial.core.feeding_detail.outcome_attention._closed
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert len(calls) == 1


def test_cognitive_relevance_overflow_stops_before_an_extra_installation(monkeypatch):
    trial = demo.create_seeking_attention_trial_v1()
    trial.focal_step()
    advance_to_next_focal(trial)
    before = trial.tick, trial.controller.installation_count, trial.observer_oral_body
    def overflow(*a, **k):
        raise OverflowError("injected full relevance queue")
    monkeypatch.setattr(trial.core.feeding_detail.outcome_attention, "admit", overflow)
    with pytest.raises(OverflowError):
        trial.focal_step()
    assert trial.stopped and before == (trial.tick, trial.controller.installation_count, trial.observer_oral_body)


def test_new_consumer_has_no_private_world_motor_or_learning_authority():
    tree = ast.parse((ROOT / "nca8_seek_attention.py").read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not modules & {"cca8_env", "cca8_support_world", "nca8_hierarchy", "nca8_sensorimotor", "nca8_learning", "cca8_feeding"}
    assert not attributes & {"_world", "milestones", "reward", "observer_body", "install_authorized", "commit", "apply", "retain_influence"}


def test_registry_contains_two_real_components_without_new_host_primitives():
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_seek_attention"] == "nca8_seek_attention"
    assert registry["nca8_seek_attention_demo"] == "nca8_seek_attention_demo"
    assert cca8_run.__version__ == "0.30.36"
    assert len(cca8_run._cca8_component_rows()) == 106 and len(cca8_run.PRIMITIVES) == 8
