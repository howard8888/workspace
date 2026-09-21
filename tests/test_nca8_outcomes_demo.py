"""P16-1G-A live controls and read-only menu/script comparisons, not biomechanical claims."""

from __future__ import annotations

import builtins
import json
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import cca8_run
import nca8_hierarchy_demo as hierarchy_demo
import nca8_menu
import nca8_outcomes as outcomes
import nca8_outcomes_demo as demo
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def experiments():
    return {case: demo.run_righting_outcome_v1(case) for case in demo.RIGHTING_OUTCOME_CASES_V1}


def cycle_rows(result):
    return tuple(focal for focal, _ in result.intervals) + (result.final_cycle,)


def motor_rows(result):
    return tuple(step.command for _, lower in result.intervals for step in lower)


@pytest.mark.parametrize("case", demo.RIGHTING_OUTCOME_CASES_V1)
def test_all_declared_cases_use_one_finite_physical_horizon_with_real_owner_bounds(experiments, case):
    result = experiments[case]
    assert len(result.intervals) == 20
    assert sum(len(lower) for _, lower in result.intervals) == 80
    assert result.final_cycle.calculation.cutoff_tick == 80
    assert result.metrics()["simulation_seconds"] == 4.0
    assert result.metrics()["focal_reads"] == 21
    assert not result.bound_violations
    assert all(focal.task_outcome is not None for focal in cycle_rows(result))
    assert result.as_dict()["restores_motor_permission"] is False
    assert result.metrics()["durable_learning_updates"] == 0
    assert result.metrics()["causal_action_credit"] == "uncertain"


def test_nominal_partial_progress_and_later_stall_do_not_manufacture_task_success(experiments):
    result = experiments["nominal"]
    counts = result.metrics()["task_evidence_counts"]
    assert counts["progress"] > 0 and counts["stall"] > 0
    assert result.final_cycle.calculation.task.status == "budget_exhausted"
    assert result.final_cycle.task_outcome.feedback.body_tilt_degrees == pytest.approx(12.014584888933006)
    assert result.metrics()["task_completed"] is False
    assert not any(row.status == "failed" for row in result.outcomes)
    assert any(row.status == "mismatch" for row in result.outcomes)
    assert any(report.disposition.value == "achieved" for _, lower in result.intervals for step in lower for report in step.reports)


def test_final_endpoint_remains_pending_when_sensing_would_arrive_after_physical_horizon(experiments):
    result = experiments["nominal"]
    assert len(result.pending) == 1 and result.pending[0].due_tick == 80
    assert all(row.evidence is None or row.evidence.available_tick <= 80 for row in result.outcomes)
    assert result.final_cycle.task_outcome.feedback.event_tick == 79
    assert result.pending[0].expires_at_tick == 88


def test_assistance_closes_only_after_three_distinct_focal_acquisitions_and_revokes_pursuit(experiments):
    result = experiments["assisted"]
    task = result.final_cycle.calculation.task
    assert task.status == "completed"
    assert result.metrics()["first_supported_completion_cutoff"] == 32
    assert [item.event_tick for item in task.completion_samples] == [23, 27, 31]
    assert len({item.sample_id for item in task.completion_samples}) == 3
    assert all(step.command is None for focal, lower in result.intervals if focal.calculation.cutoff_tick >= 32 for step in lower)
    assert all(item.as_dict()["action_causation"] == "uncertain" for item in result.outcomes)
    assert any(row.task_outcome.status == "adequate_pending_dwell" for row in cycle_rows(result))


def test_external_adequacy_without_a_selected_task_is_not_task_completion(experiments):
    result = experiments["assisted_no_task"]
    assert all(item is None for item in motor_rows(result))
    assert result.final_cycle.calculation.task is None
    assert abs(result.final_cycle.task_outcome.feedback.body_tilt_degrees) < 12
    assert result.final_cycle.task_outcome.feedback.useful_loading >= 0.75
    assert result.metrics()["task_completed"] is False and not result.outcomes
    assert all(focal.task_outcome.status == "no_task" for focal in cycle_rows(result))


def test_prediction_comparison_ablation_preserves_task_dwell_and_every_motor_command(experiments):
    intact, disabled = experiments["assisted"], experiments["assisted_comparison_off"]
    assert motor_rows(intact) == motor_rows(disabled)
    assert intact.final_body == disabled.final_body
    assert intact.final_cycle.calculation.task == disabled.final_cycle.calculation.task
    assert [item.task_outcome for item in cycle_rows(intact)] == [item.task_outcome for item in cycle_rows(disabled)]
    assert {item.status for item in disabled.outcomes} == {"comparison_disabled"}
    assert "comparison_disabled" not in {item.status for item in intact.outcomes}


def test_missing_packets_stay_unknown_and_do_not_create_stall_or_failed_forecasts(experiments):
    result = experiments["feedback_missing"]
    late = [item.task_outcome for item in cycle_rows(result) if item.calculation.cutoff_tick >= 12]
    assert all(item.status == "unknown" and not item.supported_samples for item in late)
    assert any(item.status == "expired_unresolved" for item in result.outcomes)
    assert all(step.command is None for focal, lower in result.intervals if focal.calculation.cutoff_tick >= 12 for step in lower)
    assert result.final_cycle.calculation.task.status == "budget_exhausted"


def test_blocked_motor_can_show_stall_despite_executed_command_opportunities(experiments):
    result = experiments["blocked_orientation"]
    assert result.metrics()["nonnull_commands"] > 0
    assert result.metrics()["task_evidence_counts"]["stall"] > 0
    assert result.metrics()["prediction_outcome_counts"]["mismatch"] > 0
    assert result.metrics()["task_completed"] is False


def test_material_mapping_narrowing_reconciles_before_handoff_without_rewriting_forecast(experiments):
    result = experiments["narrowed"]
    registrations = [focal.claim_registration for focal in cycle_rows(result) if focal.claim_registration is not None]
    narrowed = [row for row in registrations if "tilt" in row.unevaluable_relations]
    assert narrowed and any(row.status == "partly_matched" for row in result.outcomes)
    assert any(row.request.desired_tilt_degrees != target.target.endpoint for row in narrowed for target in row.targets
               if target.target.kind.value == "orientation_adjust")
    assert all("loading" in row.unevaluable_relations for row in narrowed)
    for row in result.outcomes:
        assert row.registration in registrations
        assert row.registration.preview.basis.cutoff_tick <= row.evaluated_tick


def test_veto_is_not_applied_even_while_passive_body_deteriorates(experiments):
    result = experiments["veto"]
    assert not any(motor_rows(result))
    assert len(result.outcomes) == 20
    assert {item.status for item in result.outcomes} == {"not_applied"}
    assert all(item.command_intervals == 0 and not item.registration.targets for item in result.outcomes)
    assert result.metrics()["task_evidence_counts"]["regression"] > 0


def test_context_change_does_not_relabel_the_old_mobility_task_successful(experiments):
    result = experiments["context_change"]
    old = [row.calculation.task for row in cycle_rows(result) if row.calculation.cutoff_tick < 16]
    assert any(task is not None for task in old)
    assert all(task is None or task.context.activity.value == "mobility" for task in old)
    assert all(row.calculation.task is None for row in cycle_rows(result) if row.calculation.cutoff_tick >= 16)
    assert result.metrics()["task_completed"] is False


@pytest.mark.parametrize("case", ("nominal", "assisted", "feedback_missing", "narrowed"))
def test_trace_capacity_does_not_change_outcome_owner_or_motor_behavior(experiments, case):
    reduced = demo.run_righting_outcome_v1(case, trace_capacity=1)
    reduced_export, original_export = reduced.as_dict(), experiments[case].as_dict()
    assert reduced_export["peak_owner_counts"].pop("focal_trace") == 1
    assert original_export["peak_owner_counts"].pop("focal_trace") == 256
    assert reduced_export == original_export


@pytest.mark.parametrize("case", ("nominal", "assisted", "support_loss"))
def test_repeated_runs_and_all_renderers_are_neutral(experiments, case):
    result = experiments[case]
    before, rng = result.as_dict(), random.getstate()
    assert demo.run_righting_outcome_v1(case).as_dict() == before
    compact = demo.render_righting_outcome_v1(result)
    detail = demo.render_righting_outcome_v1(result, detail=True)
    summary = demo.render_righting_outcome_summary_v1((result,))
    assert "P16-1G-A" in summary and "PNM" in compact and len(detail) > len(compact)
    assert result.as_dict() == before and random.getstate() == rng
    json.dumps(before, allow_nan=False)


@pytest.mark.parametrize("case", (None, 1, True, "unknown", "", "Nominal"))
def test_invalid_case_is_rejected_without_constructing_a_trial(monkeypatch, case):
    monkeypatch.setattr(demo, "IntegratedRightingTrialV1", lambda *args, **kwargs: pytest.fail("constructed invalid trial"))
    with pytest.raises(ValueError):
        demo.run_righting_outcome_v1(case)


@pytest.mark.parametrize("value", ((), [], None, (object(),)))
def test_summary_rejects_invented_or_missing_results(value):
    with pytest.raises(TypeError):
        demo.render_righting_outcome_summary_v1(value)


def test_measured_bound_failure_is_not_hidden_by_a_positive_task_label(experiments):
    record = experiments["assisted"]
    counts = dict(record.peak_counts)
    counts["outcome_pending_claims"] = 9
    invalid = replace(record, peak_counts=tuple(counts.items()))
    assert invalid.metrics()["task_completed"] is True
    assert invalid.bound_violations == ("outcome_pending_claims",)


def test_opening_menu_runs_no_physics(monkeypatch):
    monkeypatch.setattr(demo, "run_righting_outcome_v1", lambda *args, **kwargs: pytest.fail("unrequested trial"))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    rng = random.getstate()
    demo.run_righting_outcome_menu_v1()
    assert random.getstate() == rng


@pytest.mark.parametrize("choice,cases,detail", [
    ("1", demo.RIGHTING_OUTCOME_CASES_V1, False), ("2", ("nominal",), False),
    ("3", ("assisted", "assisted_no_task"), False), ("4", ("support_loss",), False),
    ("5", ("feedback_missing",), False), ("6", ("narrowed", "veto"), False),
    ("7", ("assisted", "assisted_comparison_off"), False), ("8", ("nominal",), True),
])
def test_menu_routes_use_shared_experiments_not_another_loop(monkeypatch, choice, cases, detail):
    calls, renders = [], []
    monkeypatch.setattr(demo, "run_righting_outcome_v1", lambda selected: calls.append(selected) or selected)
    monkeypatch.setattr(demo, "render_righting_outcome_summary_v1", lambda records: "summary")
    monkeypatch.setattr(demo, "render_righting_outcome_v1", lambda record, **options: renders.append(options["detail"]) or "result")
    answers = iter(("invalid", choice, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    demo.run_righting_outcome_menu_v1()
    assert tuple(calls) == cases
    assert renders == ([] if choice == "1" else [detail] * len(cases))


def test_integrated_menu_uses_an_injected_callback_not_a_reverse_consumer_import(monkeypatch):
    calls = []
    answers = iter(("6", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    hierarchy_demo.run_hierarchy_review_menu_v1(outcome_menu=lambda: calls.append("outcomes"))
    assert calls == ["outcomes"]


def test_nested_menu_leaves_retained_a0_session_and_rng_unchanged(monkeypatch, capsys):
    retained = Nca8SessionV1()
    before, trace, rng = retained.status(), retained.trace_snapshot(), random.getstate()
    answers = iter(("8", "6", "3", "", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(retained) is retained
    assert retained.status() == before and retained.trace_snapshot() == trace and random.getstate() == rng
    text = capsys.readouterr().out
    assert "assisted_no_task" in text and "completion_cutoff=32" in text


@pytest.mark.parametrize("case", ("nominal", "assisted", "narrowed"))
def test_permanent_script_json_equals_the_actual_shared_experiment(experiments, case, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_hierarchy.py"), "--outcomes", case, "--json"],
                             cwd=tmp_path, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == json.loads(json.dumps([experiments[case].as_dict()]))
    assert not tuple(tmp_path.iterdir())


def test_permanent_script_summary_does_not_report_every_case_as_task_success(tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_hierarchy.py"), "--outcomes"],
                             cwd=tmp_path, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert "task=budget_exhausted" in process.stdout and "task=completed" in process.stdout
    assert "pending=1" in process.stdout and not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("arguments", [("--outcomes", "unknown"), ("--outcomes", "nominal", "--qualify"),
                                        ("--outcomes", "--case", "nominal")])
def test_cli_ambiguous_or_unknown_selectors_are_not_silently_accepted(arguments, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_hierarchy.py"), *arguments],
                             cwd=tmp_path, text=True, capture_output=True, check=False)
    assert process.returncode == 2 and not tuple(tmp_path.iterdir())


def test_versions_register_real_components_not_new_primitives():
    assert cca8_run.__version__ == "0.30.23"
    assert outcomes.__version__ == "0.1.1" and demo.__version__ == "0.1.0"
    versions = cca8_run.versions_dict()
    assert versions["nca8_outcomes"] == "0.1.1"
    assert versions["nca8_outcomes_demo"] == "0.1.0"
