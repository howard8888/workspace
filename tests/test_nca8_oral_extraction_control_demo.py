"""Shared L-B review/access checks; supplied requirements are never task IPs."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_oral_extraction_control_demo as demo
from nca8_sensorimotor_contracts import LocalTargetDispositionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_oral_extraction_control_v1(case) for case in demo.ORAL_EXTRACTION_CONTROL_CASES_V1}


@pytest.mark.parametrize("case", demo.ORAL_EXTRACTION_CONTROL_CASES_V1)
def test_each_declared_case_has_finite_truthful_review(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", result.checks
    assert len(result.steps) == 12 and len(result.physical) == 13
    assert result.as_dict()["is_navigation_selected_suckle"] is False
    assert result.as_dict()["focal_calls"] == 0 and result.as_dict()["durable_learning_updates"] == 0
    assert result.source_before == result.source_after
    assert json.loads(json.dumps(result.as_dict())) == result.as_dict()
    assert all(tick == step.tick for tick, step in enumerate(result.steps))


@pytest.mark.parametrize("case, expected", [("nominal", 0.1), ("twice", 0.2), ("shifted_stroke", 0.1),
                                             ("dry_surface", 0.0), ("exhausted_supply", 0.05), ("missing_milk", 0.1)])
def test_observed_pattern_is_not_milk_or_task_completion(case, expected, runs):
    result = runs[case]
    report = result.steps[-1].reports[0]
    assert report.disposition is LocalTargetDispositionV1.ACHIEVED
    assert len(report.extraction_confirmations) == 2 * result.settings.repetitions
    assert result.physical[-1].transferred_milk_units == pytest.approx(expected)
    assert all(step.command is None for step in result.steps if step.tick >= result.target.lease_ticks)
    assert result.installation_count == 1


def test_wet_dry_and_missing_milk_decisions_are_identical(runs):
    keys = ("nominal", "dry_surface", "exhausted_supply", "missing_milk")
    commands = [[step.command for step in runs[key].steps] for key in keys]
    assert all(value == commands[0] for value in commands[1:])
    missing = runs["missing_milk"]
    assert all(step.feedback.oral_extraction.milk_transferred_units is None for step in missing.steps if step.feedback)
    assert missing.physical[-1].transferred_milk_units > 0


@pytest.mark.parametrize("case", ["preview_only", "no_capability", "source_off", "no_touch", "no_seal",
                                  "missing_stroke", "missing_seal"])
def test_no_reservation_means_no_hidden_default_drive(case, runs):
    result = runs[case]
    assert result.target is None and result.installation_count == 0
    assert all(step.command is None and not step.reports for step in result.steps)
    assert result.physical[-1].transferred_milk_units == 0.0


@pytest.mark.parametrize("bad", [None, True, 1, "", "unknown", "nominal "])
def test_invalid_case_never_selects_another_profile(bad):
    with pytest.raises(ValueError):
        demo.oral_extraction_control_profile_v1(bad)


@pytest.mark.parametrize("capacity", [1, 2, 12, 256])
def test_trace_capacity_and_rendering_cannot_change_control(capacity, runs, monkeypatch):
    state = random.getstate()
    result = demo.run_oral_extraction_control_v1("twice", trace_capacity=capacity)
    assert result.steps == runs["twice"].steps and result.physical == runs["twice"].physical
    assert result.trace_retained <= min(capacity, 12)
    def forbidden(*args, **kwargs):
        raise AssertionError("inspection attempted a control/world step")
    monkeypatch.setattr(demo.SensorimotorTrialV1, "advance", forbidden)
    for _ in range(3):
        text = demo.render_oral_extraction_control_v1(result, detail=True)
        assert "NOT Navigation-selected Suckle" in text and "sensed=" in text and "endpoints=" in text
        detached = result.as_dict()
        detached["physical"].clear()
        assert len(result.physical) == 13 and result.review_status == "PASS"
    assert random.getstate() == state


@pytest.mark.parametrize("mutation", ["steps", "installations", "source", "trace", "transfer", "late_command"])
def test_observer_detects_corrupt_completed_evidence(mutation, runs):
    result = runs["nominal"]
    if mutation == "steps":
        result = replace(result, steps=result.steps[:-1])
    elif mutation == "installations":
        result = replace(result, installation_count=2)
    elif mutation == "source":
        result = replace(result, source_after="unreported learning")
    elif mutation == "trace":
        result = replace(result, trace_retained=100)
    elif mutation == "transfer":
        final = result.physical[-1]
        result = replace(result, physical=(*result.physical[:-1], replace(final, transferred_milk_units=0.2, remaining_supply_units=0.8)))
    else:
        # Corrupt the completed observation fixture, not a live motor command.
        import copy
        late = copy.copy(result.steps[-1])
        object.__setattr__(late, "command", result.steps[0].command)
        result = replace(result, steps=(*result.steps[:-1], late))
    assert result.review_status == "FAIL"


def load_cli():
    spec = importlib.util.spec_from_file_location("lb_review_cli", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_json_matches_same_shared_result_and_failure_is_nonzero(capsys, monkeypatch, runs):
    cli = load_cli()
    assert cli.main(["--oral-extraction-control", "--case", "twice", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [runs["twice"].as_dict()]
    monkeypatch.setattr(cli, "run_oral_extraction_control_v1", lambda case: replace(runs[case], installation_count=99))
    assert cli.main(["--oral-extraction-control", "--case", "nominal"]) == 1
    assert "FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--oral-extraction-control", "--oral-extraction"],
                                   ["--oral-extraction-control", "--suckle"],
                                   ["--oral-extraction-control", "--case", "unknown"]])
def test_cli_invalid_or_mixed_routes_are_not_silently_repaired(args):
    with pytest.raises(SystemExit) as error:
        load_cli().main(args)
    assert error.value.code == 2


def test_cli_outside_checkout_preserves_json(tmp_path, runs):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                             "--oral-extraction-control", "--case", "delayed", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [runs["delayed"].as_dict()]


def test_menu_preserves_J_K_LA_and_adds_LB(monkeypatch):
    import nca8_feeding_demo as feeding
    choices = iter(("26", "27", "28", "29", ""))
    calls = []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda *args: next(choices))
    for name, tag in (("run_suckle_attention_menu_v1", "J"), ("run_suckle_learning_menu_v1", "K"),
                      ("run_oral_extraction_menu_v1", "LA"), ("run_oral_extraction_control_menu_v1", "LB")):
        monkeypatch.setattr(feeding, name, lambda tag=tag: calls.append(tag))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["J", "K", "LA", "LB"]


def test_retained_detail_and_invalid_menu_choice_do_not_repeat_execution(monkeypatch, capsys, runs):
    choices = iter(("6", "unknown", "1", "6", "6", ""))
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda *args: next(choices))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_oral_extraction_control_v1", run)
    demo.run_oral_extraction_control_menu_v1()
    assert calls == ["nominal", "twice", "shifted_stroke", "preview_only"]
    text = capsys.readouterr().out
    assert "No retained review." in text and "Choose 0-6." in text and "sensed=" in text


def test_registry_versions_and_real_suckle_remains_unextended():
    import cca8_run
    import nca8_sensorimotor_contracts as contracts
    import nca8_body_targets as targets
    import nca8_sensorimotor as motor
    from nca8_suckle_demo import create_suckle_trial_v1
    assert cca8_run.__version__ == "0.30.40" and len(cca8_run._cca8_component_rows()) == 114
    assert contracts.__version__ == "0.6.0" and targets.__version__ == "0.12.0" and motor.__version__ == "0.6.0"
    assert ("nca8_oral_extraction_control_demo", "nca8_oral_extraction_control_demo") in cca8_run._CCA8_COMPONENT_REGISTRY
    assert len(cca8_run.PRIMITIVES) == 8
    trial = create_suckle_trial_v1(outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True)
    assert trial.latest_feedback.oral_extraction is None
