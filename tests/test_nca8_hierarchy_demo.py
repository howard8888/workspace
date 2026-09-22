"""H6-A permanent review, truthful finite results, menu and presentation isolation."""

from __future__ import annotations

import builtins
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

import nca8_hierarchy_demo as demo
import nca8_menu
from nca8_runtime import Nca8SessionV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case,installations", [("nominal", 20), ("disturbed", 19)])
def test_review_contains_real_finite_loop_and_honest_uncompleted_task(case, installations):
    result = demo.run_integrated_righting_v1(case)
    assert len(result.intervals) == 20 and all(len(lower) == 4 for _, lower in result.intervals)
    assert result.installation_count == installations
    assert result.final_cycle.calculation.cutoff_tick == 80
    assert result.final_cycle.status == "budget_exhausted"
    assert result.final_cycle.receipt.dispatch.motor.directive == "cancel"
    assert result.final_feedback.event_tick == 79 and result.final_feedback.available_tick == 80
    tasks = {focal.calculation.task.task_id for focal, _ in result.intervals}
    assert tasks == {result.final_cycle.calculation.task.task_id}
    first, steps = result.intervals[0]
    assert first.calculation.task.status == "active"
    assert steps[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert result.final_feedback.body_tilt_degrees > 12.0  # Local tolerance is not task adequacy.
    assert not result.as_dict()["task_success_established"]


def test_matched_disturbance_changes_local_drive_before_next_focal_decision():
    nominal = demo.run_integrated_righting_v1("nominal")
    disturbed = demo.run_integrated_righting_v1("disturbed")
    first_nominal = nominal.intervals[0][0].calculation.source.motor_support.feedback
    first_disturbed = disturbed.intervals[0][0].calculation.source.motor_support.feedback
    assert first_nominal == first_disturbed
    step = disturbed.intervals[2][1][2]
    assert step.tick == 10 and disturbed.intervals[3][0].calculation.cutoff_tick == 12
    assert step.command != nominal.intervals[2][1][2].command
    assert any(item.reason == "bounded_anomalous_correction" for item in step.reports)
    assert any(item.unexpected and item.feedback.event_tick == 9 for item in step.comparisons)
    events = disturbed.intervals[3][0].local_events
    assert events[0].event_tick == 9 and events[0].noticed_tick == 10


@pytest.mark.parametrize("case", ["nominal", "disturbed"])
def test_readonly_render_export_and_trace_retention_do_not_change_computation(case):
    before_rng = random.getstate()
    result = demo.run_integrated_righting_v1(case, trace_capacity=1)
    before = json.dumps(result.as_dict(), sort_keys=True)
    compact = demo.render_integrated_righting_v1(result)
    detailed = demo.render_integrated_righting_v1(result, detail=True)
    assert "task completion NOT established" in compact
    assert "durable learning updates=0" in compact
    assert "H6-B controls are available separately; P16-1G outcomes remain pending" in compact
    assert "CORE CLOSED" in compact and "consumed ONCE" in compact
    assert detailed.count("    LOWER tick=") == 80
    assert json.dumps(result.as_dict(), sort_keys=True) == before
    assert demo.run_integrated_righting_v1(case, trace_capacity=4096).as_dict() == result.as_dict()
    assert random.getstate() == before_rng
    assert len(result.trace) == 1


@pytest.mark.parametrize("case", ["a0", "all", "success", "", None])
def test_review_does_not_silently_fallback_from_unknown_profile(case):
    with pytest.raises(ValueError):
        demo.run_integrated_righting_v1(case)


@pytest.mark.parametrize("bad", [None, "text", {}, 1])
def test_renderer_requires_a_real_retained_experiment(bad):
    with pytest.raises(TypeError):
        demo.render_integrated_righting_v1(bad)


def test_opening_review_menu_does_not_run_a_trial(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("opening a menu must not start physical execution")
    monkeypatch.setattr(demo, "run_integrated_righting_v1", prohibited)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    demo.run_hierarchy_review_menu_v1()


@pytest.mark.parametrize("choice,case,detail", [("1", "nominal", False), ("2", "disturbed", False),
                                              ("3", "nominal", True), ("4", "disturbed", True)])
def test_submenu_uses_shared_experiment_and_only_changes_presentation(monkeypatch, choice, case, detail):
    result = demo.run_integrated_righting_v1(case)
    calls = []
    monkeypatch.setattr(demo, "run_integrated_righting_v1", lambda selected: calls.append(selected) or result)
    monkeypatch.setattr(demo, "render_integrated_righting_v1", lambda record, **options: calls.append((record, options)) or "review")
    answers = iter(("invalid", choice, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    demo.run_hierarchy_review_menu_v1()
    assert calls == [case, (result, {"detail": detail})]


def test_nca8_route_eight_preserves_retained_a0_session(monkeypatch):
    retained = Nca8SessionV1()
    before, trace = retained.status(), retained.trace_snapshot()
    calls = []
    monkeypatch.setattr(nca8_menu, "run_hierarchy_review_menu_v1", lambda **options: calls.append(options))
    answers = iter(("8", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(retained) is retained
    assert calls == [{"qualification_menu": nca8_menu.run_hierarchy_qualification_menu_v1,
                      "outcome_menu": nca8_menu.run_righting_outcome_menu_v1,
                      "outcome_attention_menu": nca8_menu.run_outcome_attention_menu_v1,
                      "learning_menu": nca8_menu.run_learning_review_menu_v1}]
    assert retained.status() == before and retained.trace_snapshot() == trace


@pytest.mark.parametrize("options", [("--case", "nominal"), ("--case", "disturbed", "--detail"),
                                    ("--case", "both", "--json")])
def test_permanent_script_runs_outside_repo_without_writes(tmp_path, options):
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_hierarchy.py"), *options],
                               cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []
    if "--json" in options:
        records = json.loads(completed.stdout)
        assert [item["case"] for item in records] == ["nominal", "disturbed"]
        assert all(item["local_ticks"] == 80 for item in records)
        assert not any(item["task_success_established"] for item in records)
    else:
        assert "P18-H6-A INTEGRATED RIGHTING" in completed.stdout
        assert "task completion NOT established" in completed.stdout


def test_registry_versions_include_real_modules_and_preserve_legacy_count():
    import cca8_run
    import cca8_motor_contracts
    import nca8_hierarchy
    import nca8_handoff
    import nca8_sensorimotor_contracts
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_hierarchy"] == "nca8_hierarchy"
    assert registry["nca8_hierarchy_demo"] == "nca8_hierarchy_demo"
    assert cca8_run.__version__ == "0.30.35"
    assert nca8_hierarchy.__version__ == "0.16.0" and demo.__version__ == "0.5.1"
    assert cca8_motor_contracts.__version__ == nca8_sensorimotor_contracts.__version__ == "0.5.0"
    assert nca8_handoff.__version__ == "0.6.0"
    assert len(cca8_run._cca8_component_rows()) == 104
    assert len(cca8_run.PRIMITIVES) == 8
