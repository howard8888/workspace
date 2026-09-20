"""H6-B menu/script routing and inspection without hidden live-session changes."""

from __future__ import annotations

import builtins
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

import cca8_run
import nca8_hierarchy_demo as integrated
import nca8_hierarchy_qualification as qualification
import nca8_menu
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


def test_opening_and_returning_from_qualification_does_not_construct_a_trial(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("menu inspection created an unrequested physical trial")
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_group_v1", prohibited)
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_v1", prohibited)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    before = random.getstate()
    qualification.run_hierarchy_qualification_menu_v1()
    assert random.getstate() == before


@pytest.mark.parametrize("choice,group", [("1", "all"), ("2", "mapping"), ("3", "feedback"), ("4", "prediction"),
                                         ("5", "cadence"), ("6", "assistance"), ("7", "righting")])
def test_menu_group_choices_call_the_same_shared_runner(monkeypatch, choice, group):
    calls = []
    records = (object(),)
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_group_v1", lambda selected: calls.append(selected) or records)
    monkeypatch.setattr(qualification, "render_hierarchy_qualification_summary_v1", lambda value: calls.append(value) or "summary")
    answers = iter(("invalid", choice, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    qualification.run_hierarchy_qualification_menu_v1()
    assert calls == [group, records]


@pytest.mark.parametrize("choice,detail", [("8", False), ("9", True)])
def test_single_case_menu_changes_only_requested_presentation(monkeypatch, choice, detail):
    calls = []
    record = object()
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_v1", lambda case: calls.append(case) or record)
    monkeypatch.setattr(qualification, "render_hierarchy_qualification_v1",
                        lambda value, **options: calls.append((value, options)) or "timeline")
    answers = iter((choice, "7", ""))  # fast_feedback_off is profile 7, independent of menu choice.
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    qualification.run_hierarchy_qualification_menu_v1()
    assert calls == ["fast_feedback_off", (record, {"detail": detail})]


@pytest.mark.parametrize("answer", ("", "x", "0", "18", "Ⅳ", "９"))
def test_invalid_or_cancelled_case_selection_runs_no_trial(monkeypatch, answer):
    def prohibited(*args, **kwargs):
        raise AssertionError("invalid selection started a trial")
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_v1", prohibited)
    answers = iter(("9", answer, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    qualification.run_hierarchy_qualification_menu_v1()


def test_h4_control_menu_reuses_the_original_lower_experiments(monkeypatch):
    calls = []
    monkeypatch.setattr(qualification, "run_sensorimotor_experiment_v1", lambda case: calls.append(case) or case)
    monkeypatch.setattr(qualification, "render_sensorimotor_experiment_v1", lambda record: (record,))
    answers = iter(("10", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    qualification.run_hierarchy_qualification_menu_v1()
    assert calls == ["perturbed", "feedback_off", "prediction_off", "support_loss", "support_loss_prediction_off"]


def test_h6a_submenu_opens_h6b_without_changing_its_existing_routes(monkeypatch):
    calls = []
    monkeypatch.setattr(qualification, "run_hierarchy_qualification_menu_v1", lambda: calls.append("H6-B"))
    answers = iter(("5", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    integrated.run_hierarchy_review_menu_v1(qualification_menu=qualification.run_hierarchy_qualification_menu_v1)
    assert calls == ["H6-B"]


def test_real_nested_menu_review_leaves_retained_a0_session_and_rng_unchanged(monkeypatch, capsys):
    retained = Nca8SessionV1()
    before, trace, rng = retained.status(), retained.trace_snapshot(), random.getstate()
    answers = iter(("8", "5", "2", "", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(retained) is retained
    assert retained.status() == before and retained.trace_snapshot() == trace
    assert random.getstate() == rng
    text = capsys.readouterr().out
    assert "mapping_reversed" in text and "orientation_unavailable" in text
    assert "HIERARCHY QUALIFICATION SUMMARY" in text


@pytest.mark.parametrize("options", [
    ("--qualify", "mapping"), ("--qualify",), ("--profile", "fast_feedback_off", "--detail"),
    ("--qualify", "prediction", "--json"), ("--profile", "task_pnm_consumer_off", "--json"),
])
def test_permanent_script_works_outside_repository_without_writing_files(tmp_path, options):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_hierarchy.py"), *options],
                             cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert process.returncode == 0, process.stderr
    assert list(tmp_path.iterdir()) == []
    if "--json" in options:
        records = json.loads(process.stdout)
        assert all(record["metrics"]["physical_ticks"] == 80 for record in records)
        assert all(not record["bound_violations"] for record in records)
        assert all(record["metrics"]["task_success_established"] is False for record in records)
    else:
        assert "P18-H6-B" in process.stdout and "INTERPRETATION LIMITS" in process.stdout
        if "--detail" in options:
            assert process.stdout.count("    LOWER tick=") == 80


@pytest.mark.parametrize("options", [("--case", "nominal", "--qualify"), ("--profile", "nominal", "--qualify"),
                                    ("--qualify", "unknown"), ("--profile", "success")])
def test_cli_rejects_ambiguous_or_unknown_experiments(tmp_path, options):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_hierarchy.py"), *options],
                             cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert process.returncode == 2
    assert "P18-H6-B HIERARCHY QUALIFICATION" not in process.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad", (None, [], (), (object(),)))
def test_summary_rejects_nonresults_or_empty_payloads(bad):
    with pytest.raises((ValueError, TypeError)):
        qualification.render_hierarchy_qualification_summary_v1(bad)


def test_summary_rejects_duplicate_case_identity_and_detects_a_bound_violation():
    from dataclasses import replace
    record = qualification.run_hierarchy_qualification_v1("nominal")
    with pytest.raises(ValueError):
        qualification.render_hierarchy_qualification_summary_v1((record, record))
    changed = replace(record, peak_counts=tuple((name, 2 if name == "wnm" else value) for name, value in record.peak_counts))
    assert changed.bound_violations == ("wnm",)
    assert "bounds=['wnm']" in qualification.render_hierarchy_qualification_summary_v1((changed,))


def test_registry_includes_one_cohesive_qualification_component():
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_hierarchy_qualification"] == "nca8_hierarchy_qualification"
    assert qualification.__version__ == "0.1.0"
    assert cca8_run.__version__ == "0.30.19"
    assert len(cca8_run._cca8_component_rows()) == 75
    assert len(cca8_run.PRIMITIVES) == 8


def test_standalone_h6a_menu_has_no_unprovided_qualification_route(monkeypatch, capsys):
    answers = iter(("5", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    integrated.run_hierarchy_review_menu_v1()
    text = capsys.readouterr().out
    assert "Choose 1-4" in text
    assert "  5)" not in text


@pytest.mark.parametrize("callback", (False, "qualification", 42))
def test_menu_rejects_invalid_callback_before_input_or_execution(monkeypatch, callback):
    def prohibited(*args, **kwargs):
        raise AssertionError("invalid callback prompted for input")
    monkeypatch.setattr(builtins, "input", prohibited)
    with pytest.raises(TypeError):
        integrated.run_hierarchy_review_menu_v1(qualification_menu=callback)
