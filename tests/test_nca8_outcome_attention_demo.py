"""Live 1G-B causal controls, single-focus timing, local continuation and neutral UI."""

from __future__ import annotations

import ast
import builtins
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_menu
import nca8_outcome_attention_demo as demo
from cca8_support_world import MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_hierarchy_demo import run_hierarchy_review_menu_v1
from nca8_outcomes_demo import run_righting_outcome_v1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_outcome_attention_v1(case) for case in demo.OUTCOME_ATTENTION_CASES_V1}


@pytest.mark.parametrize("case", demo.OUTCOME_ATTENTION_CASES_V1)
def test_every_live_case_has_the_same_finite_timebase_and_real_owner_bounds(results, case):
    result = results[case]
    metrics = result.metrics()
    assert metrics["physical_ticks"] == 80 and metrics["focal_reads"] == 21
    assert len(result.physical_samples) == 81
    assert not result.bound_violations
    assert result.final_cycle.calculation.cutoff_tick == 80
    assert metrics["durable_learning_updates"] == 0
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("case", demo.OUTCOME_ATTENTION_CASES_V1)
def test_each_interpretation_excludes_new_task_pnm_and_motor_installation(results, case):
    result = results[case]
    task_ids = set()
    for focal, _ in (*result.intervals, (result.final_cycle, ())):
        calc = focal.calculation
        if calc.task is not None:
            task_ids.add(calc.task.task_id)
        allocation = calc.outcome_allocation
        if allocation is None or allocation.kind != "interpretation":
            continue
        assert calc.cutoff_tick < 80
        assert calc.navigation.application is None and not calc.navigation.applicability_records
        assert focal.commitment.selected_primitive_id is None
        assert focal.commitment.pnm_id is None and focal.commitment.task_action is None
        assert not focal.reservations and focal.claim_registration is None
        assert calc.proposal is None
        interpretation = allocation.interpretation
        assert interpretation.cycle_id == calc.cycle_id
        assert interpretation.working_id == calc.navigation.wnm.working_id
        assert interpretation.request.outcome.registration.preview.pnm.created_cycle < calc.cycle_id
        assert interpretation.request.outcome.evidence.available_tick <= calc.cutoff_tick
        assert interpretation.as_dict()["action_causation"] == "uncertain"
    assert len(task_ids) == 1


@pytest.mark.parametrize("prefix", ["competing", "maintain"])
def test_task_outcome_route_changes_real_focal_choice_with_body_and_claim_exactly_fixed(results, prefix):
    on, off = results[prefix + "_on"], results[prefix + "_off"]
    left, right = on.intervals[4][0], off.intervals[4][0]
    assert on.physical_samples[:17] == off.physical_samples[:17]
    assert [step for _, lower in on.intervals[:4] for step in lower] == [step for _, lower in off.intervals[:4] for step in lower]
    assert left.calculation.source == right.calculation.source
    assert left.calculation.task == right.calculation.task
    assert left.calculation.persistence_rank == right.calculation.persistence_rank
    assert left.local_reports == right.local_reports and left.local_events == right.local_events
    assert left.claim_outcomes == right.claim_outcomes and left.claim_outcomes
    assert left.task_outcome == right.task_outcome
    assert left.calculation.attention.selected_bid.candidate_id == "source:posture_support"
    assert right.calculation.attention.selected_bid.candidate_id == "fixture:competing_source"
    assert left.calculation.outcome_source_bid.priority_components[:2] == (0, 20)
    assert left.calculation.outcome_source_bid.prediction_or_envelope_failure_rank == 40
    assert left.calculation.outcome_allocation.kind == "interpretation"
    assert left.calculation.attention.disposition.value == ("maintain" if prefix == "maintain" else "switch")


def test_corrected_historical_contact_is_not_misreported_as_current_danger(results):
    focal = results["competing_on"].intervals[4][0]
    interpretation = focal.calculation.outcome_allocation.interpretation
    old = interpretation.request.outcome
    assert old.evidence.event_tick == 12 and old.evidence.available_tick == 13
    assert old.evidence.support_contact is False
    assert interpretation.current_evidence.event_tick == 15 and interpretation.current_evidence.support_contact is True
    assert interpretation.status == "corrected_historical_discrepancy"
    assert interpretation.current_evidence.body_tilt_degrees > 12
    assert not focal.task_outcome.completion_supported
    assert focal.calculation.outcome_source_bid.protected_safety_rank == 0


def test_dependent_response_is_later_and_uses_new_current_source_not_the_old_endpoint(results):
    result = results["competing_on"]
    interpreted, later = result.intervals[4][0], result.intervals[5][0]
    allocation = later.calculation.outcome_allocation
    assert allocation.kind == "response_reconsideration"
    assert allocation.interpretation is interpreted.calculation.outcome_allocation.interpretation
    assert later.calculation.cutoff_tick == 20 and allocation.interpretation.cutoff_tick == 16
    assert later.calculation.source.motor_support.feedback.event_tick == 19
    assert later.calculation.navigation.selected_primitive_id == "ip:righting"
    assert all(binding.target.basis.event_tick == 19 for binding in later.calculation.proposal.bindings)


def test_protected_candidate_prevents_capture_and_old_request_expires_uninterpreted(results):
    result = results["protected_competitor"]
    focal = result.intervals[4][0]
    assert focal.calculation.attention.selected_bid.protected_safety_rank == 1
    assert focal.calculation.outcome_allocation.kind == "other_source"
    request, = focal.outcome_requests_created
    assert (request.request_id, "expired_uninterpreted", 24) in result.dispositions
    for item, _ in result.intervals:
        allocation = item.calculation.outcome_allocation
        if allocation.interpretation is not None:
            assert allocation.interpretation.request.request_id != request.request_id


def test_existing_lower_target_can_continue_during_focal_interpretation_without_lease_renewal(results):
    result = results["nominal_on"]
    focal, lower = result.intervals[5]
    previous = result.intervals[4][0]
    assert focal.calculation.cutoff_tick == 20 and focal.calculation.outcome_allocation.kind == "interpretation"
    assert focal.receipt.dispatch.motor.directive == "no_new_task_output"
    assert any(step.command is not None for step in lower)
    allowed = tuple(reservation.current for reservation in previous.reservations)
    assert allowed and all(target.expires_at_tick == 24 for target in allowed)
    for step in lower:
        assert all(report.committed_target in allowed for report in step.reports)
        assert all(report.committed_target.expires_at_tick == 24 for report in step.reports)
    assert not focal.reservations


def test_missing_sensing_alone_does_not_create_any_task_mismatch_request(results):
    result = results["feedback_missing"]
    assert result.metrics()["interpretation_ticks"] == []
    assert not any(focal.outcome_requests_created for focal, _ in result.intervals)
    assert result.final_cycle.task_outcome.status == "unknown"
    assert result.metrics()["task_status"] == "budget_exhausted"


def test_valid_old_endpoint_can_be_interpreted_as_currently_unresolved_without_inventing_failure(results):
    result = results["unresolved_current"]
    focal = result.intervals[4][0]
    interpretation = focal.calculation.outcome_allocation.interpretation
    assert interpretation.status == "unresolved_current_relevance"
    assert interpretation.request.outcome.evidence.support_contact is False
    assert interpretation.current_evidence is None
    assert focal.task_outcome.status == "unknown"
    assert all(step.command is None for _, lower in result.intervals[4:] for step in lower)
    assert any(kind == "dependent_response_expired_or_invalidated" for _, kind, _ in result.dispositions)


def test_nominal_boundary_is_not_redefined_as_prediction_failure_or_task_success(results):
    result = results["nominal_on"]
    assert result.metrics()["task_status"] == "budget_exhausted"
    assert not result.metrics()["task_completed"]
    assert not any(focal.outcome_requests_created for focal, _ in result.intervals if focal.calculation.cutoff_tick >= 40)
    for focal, _ in result.intervals:
        for request in focal.outcome_requests_created:
            assert request.outcome.status == "mismatch" and request.outcome.command_intervals > 0


def test_assisted_on_off_can_have_identical_motion_without_proving_prediction_useless(results):
    on, off = results["assisted_on"], results["assisted_off"]
    assert on.metrics()["task_completed"] and off.metrics()["task_completed"]
    assert on.physical_samples == off.physical_samples
    assert [step.command for _, lower in on.intervals for step in lower] == [step.command for _, lower in off.intervals for step in lower]
    assert on.metrics()["interpretation_ticks"] and not off.metrics()["interpretation_ticks"]
    assert on.metrics()["causal_action_credit"] == off.metrics()["causal_action_credit"] == "uncertain"


def test_disabling_endpoint_comparison_preserves_the_independent_source_and_lower_paths():
    profile = MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),))
    trial = IntegratedRightingTrialV1(profile, task_outcomes_enabled=True, task_outcome_attention_enabled=True,
                                    task_prediction_comparison_enabled=False)
    for _ in range(20):
        focal, _ = trial.step()
        assert not focal.outcome_requests_created
        assert focal.calculation.outcome_allocation.kind != "interpretation"
    assert trial.tick == 80 and not trial.stopped


def test_navigation_is_not_called_to_apply_a_task_after_interpretation(monkeypatch):
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_outcome_attention_enabled=True)
    for _ in range(5):
        trial.step()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("a second demanding task was attempted")
    monkeypatch.setattr(trial.core.cognition.navigation, "commit", forbidden)
    focal = trial.focal_step()
    assert focal.calculation.outcome_allocation.kind == "interpretation"
    assert trial.core.cognition.navigation.last_decision.reason == "interpretation"


def test_interpretation_failure_stops_the_core_and_lower_without_an_unearned_retry(monkeypatch):
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_outcome_attention_enabled=True)
    for _ in range(5):
        trial.step()
    body, tick = trial.observer_body, trial.tick
    def fail(*_args, **_kwargs):
        raise OverflowError("deliberately tested outcome relevance overflow")
    monkeypatch.setattr(trial.core.cognition.sensory.outcome_attention, "admit", fail)
    with pytest.raises(OverflowError):
        trial.focal_step()
    assert trial.stopped and trial.observer_body == body and trial.tick == tick
    with pytest.raises(RuntimeError):
        trial.advance_lower()


def test_reset_clears_requests_dependencies_and_does_not_reuse_old_generation():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_outcome_attention_enabled=True)
    for _ in range(6):
        trial.step()
    old = trial.core.cognition.sensory.outcome_attention
    assert old.retained_counts()["attention_dependency"] == 1
    trial.reset()
    new = trial.core.cognition.sensory.outcome_attention
    assert new is not old and new.stream.generation == old.stream.generation + 1
    assert new.retained_counts() == {"attention_pending_requests": 0, "attention_previous_endpoint": 0,
                                     "attention_dependency": 0, "attention_dispositions": 0}
    assert trial.tick == 0 and not trial.controller.reports


@pytest.mark.parametrize("case", ["competing_on", "unresolved_current", "nominal_on"])
def test_trace_capacity_rendering_and_json_export_have_no_functional_effect(results, case):
    original = results[case]
    before, rng = original.as_dict(), random.getstate()
    tiny = demo.run_outcome_attention_v1(case, trace_capacity=1)
    assert tiny.intervals == original.intervals and tiny.final_cycle == original.final_cycle
    assert tiny.physical_samples == original.physical_samples and tiny.dispositions == original.dispositions
    demo.render_outcome_attention_v1(original)
    demo.render_outcome_attention_v1(original, detail=True)
    demo.render_outcome_attention_summary_v1((original,))
    exported = original.as_dict()
    exported["metrics"]["task_completed"] = True
    assert original.as_dict() == before and random.getstate() == rng


def test_old_1ga_nominal_and_assisted_profiles_remain_distinct_disabled_controls(results):
    for case in ("nominal", "assisted"):
        old = run_righting_outcome_v1(case)
        disabled = results[case + "_off"]
        assert old.intervals == disabled.intervals
        assert old.final_cycle == disabled.final_cycle


@pytest.mark.parametrize("case", [None, True, "bad", "COMPETING_ON", 3])
def test_unknown_case_is_rejected_before_constructing_a_trial(monkeypatch, case):
    monkeypatch.setattr(demo, "IntegratedRightingTrialV1", lambda *_a, **_kw: pytest.fail("constructed a trial"))
    with pytest.raises(ValueError):
        demo.run_outcome_attention_v1(case)


def test_menu_open_and_return_do_not_construct_or_reset_any_trial(monkeypatch):
    monkeypatch.setattr(demo, "run_outcome_attention_v1", lambda *_a, **_kw: pytest.fail("ran a trial"))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    demo.run_outcome_attention_menu_v1()


@pytest.mark.parametrize("choice,cases", [("2", ("competing_on", "competing_off")), ("3", ("maintain_on", "maintain_off")),
                                         ("4", ("protected_competitor",)), ("5", ("feedback_missing", "unresolved_current")),
                                         ("7", ("assisted_on", "assisted_off")), ("8", ("competing_on",))])
def test_menu_choices_share_the_exact_experiment_functions(monkeypatch, choice, cases):
    calls = []
    answers = iter(("bad", choice, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    monkeypatch.setattr(demo, "run_outcome_attention_v1", lambda case: calls.append(case) or case)
    monkeypatch.setattr(demo, "render_outcome_attention_summary_v1", lambda _values: "summary")
    monkeypatch.setattr(demo, "render_outcome_attention_v1", lambda _value, **_kw: "timeline")
    demo.run_outcome_attention_menu_v1()
    assert calls == list(cases)


def test_parent_menu_callback_adds_no_reverse_import_or_hidden_loop(monkeypatch):
    calls = []
    answers = iter(("7", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    run_hierarchy_review_menu_v1(outcome_attention_menu=lambda: calls.append("outcome_attention"))
    assert calls == ["outcome_attention"]
    source = (ROOT / "nca8_hierarchy_demo.py").read_text()
    assert "from nca8_outcome_attention_demo" not in source


def test_actual_nested_menu_leaves_existing_a0_session_and_rng_unchanged(monkeypatch, capsys):
    retained = Nca8SessionV1()
    before, trace, rng = retained.status(), retained.trace_snapshot(), random.getstate()
    answers = iter(("8", "7", "2", "", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(retained) is retained
    assert retained.status() == before and retained.trace_snapshot() == trace and random.getstate() == rng
    assert "TASK-OUTCOME ATTENTION REVIEW" in capsys.readouterr().out


@pytest.mark.parametrize("case", ["competing_on", "unresolved_current", "nominal_off"])
def test_script_runs_outside_repository_and_json_matches_actual_shared_result(tmp_path, results, case):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_hierarchy.py"), "--outcome-attention", case, "--json"],
                          cwd=tmp_path, capture_output=True, text=True, check=False, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == json.loads(json.dumps([results[case].as_dict()]))
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("args", [("--outcome-attention", "bad"), ("--outcome-attention", "--outcomes"),
                                 ("--outcome-attention", "--qualify"), ("--outcome-attention", "--case", "nominal")])
def test_ambiguous_or_unknown_cli_selectors_do_not_silently_run_another_profile(args, tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_hierarchy.py"), *args], cwd=tmp_path,
                          capture_output=True, text=True, check=False, timeout=30)
    assert proc.returncode == 2
    assert not tuple(tmp_path.iterdir())


def test_summary_reports_actual_bound_failure_instead_of_a_success_banner(results):
    result = results["competing_on"]
    bad = replace(result, peak_counts=(*result.peak_counts, ("unexpected_owner", 1)))
    assert "unexpected_owner" in demo.render_outcome_attention_summary_v1((bad,))
    with pytest.raises(ValueError):
        demo.render_outcome_attention_summary_v1((result, result))


def test_domain_extension_has_no_task_motor_or_private_world_call():
    tree = ast.parse((ROOT / "nca8_outcome_attention.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"step", "apply", "commit", "select", "observe", "install", "install_authorized"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"_world", "observer_body", "scenario_stage", "milestones"}


def test_component_registry_and_menu_describe_real_current_features():
    import cca8_run
    import nca8_outcome_attention
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_outcome_attention"] == "nca8_outcome_attention"
    assert registry["nca8_outcome_attention_demo"] == "nca8_outcome_attention_demo"
    assert cca8_run.__version__ == "0.30.27" and len(cca8_run._cca8_component_rows()) == 91
    assert nca8_outcome_attention.__version__ == "0.1.0" and demo.__version__ == "0.1.1"
    assert len(cca8_run.PRIMITIVES) == 8
    assert "H6-B qualification and P16-1G task outcomes remain open" not in Path(nca8_menu.__file__).read_text()


def test_navigation_disabled_cannot_run_a_hidden_interpretation():
    from nca8_executive import NavigationRuntimeV1
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_outcome_attention_enabled=True)
    for _ in range(5):
        trial.step()
    # Explicit component ablation: no interpreted task may hide in C2 or Attention.
    trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False, motor_preview_enabled=True)
    before = trial.core.cognition.righting.task.applications
    focal, _ = trial.step()
    assert focal.outcome_requests_created
    assert focal.calculation.outcome_allocation.kind == "navigation_disabled"
    assert focal.calculation.outcome_allocation.interpretation is None
    assert focal.commitment.selected_primitive_id is None
    assert trial.core.cognition.righting.task.applications == before
    assert trial.core.cognition.sensory.outcome_attention.retained_counts()["attention_dependency"] == 0
    assert trial.tick == 24 and not trial.stopped
