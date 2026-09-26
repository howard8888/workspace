"""L-C shared real-cycle review, causal controls and observer/access preservation."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_suckle_extraction_demo as demo
from nca8_suckle import SuckleApplicationV1, SuckleExtractionApplicationV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_extraction_v1(case) for case in demo.SUCKLE_EXTRACTION_CASES_V1}


@pytest.mark.parametrize("case", demo.SUCKLE_EXTRACTION_CASES_V1)
def test_each_finite_shared_case_has_real_selected_authority_and_honest_nonclaims(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", result.checks()
    assert len(result.run.local_steps) == result.profile.latch.run.horizon_ticks
    assert json.loads(json.dumps(result.as_dict(), allow_nan=False)) == result.as_dict()
    assert result.metrics()["full_suckle_complete"] is False
    assert result.metrics()["task_pnm_fulfilment"] == "unimplemented_unscored"
    assert result.run.durable_before == result.run.durable_after
    for cycle in result.run.cycles:
        app = cycle.calculation.navigation.application
        if isinstance(app, SuckleExtractionApplicationV1):
            assert cycle.commitment.selected_primitive_id == "ip:suckle"
            assert app.contribution.origin_status == "selected_suckle_extraction"
            assert cycle.receipt.dispatch.motor.projection is app.projection
            assert cycle.receipt.dispatch.pnm is app.projection.pnm
            assert app.primitive_id == app.projection.pnm.primitive_id == "ip:suckle"
            assert not isinstance(app, SuckleApplicationV1)


@pytest.mark.parametrize("case, expected", [
    ("nominal", .2), ("dry", 0), ("depleted", .05), ("milk_sensor_off", .2),
    ("one_cycle", .1), ("blocked_motor", 0), ("no_capability", 0),
])
def test_task_choice_motor_completion_and_milk_are_separate(case, expected, runs):
    result = runs[case]
    assert result.metrics()["physical_milk_units"] == pytest.approx(expected)
    if case == "blocked_motor":
        assert result.metrics()["extraction_commands"] > 0
        assert result.metrics()["local_status"] != "local_achieved"
    elif case != "no_capability":
        assert result.metrics()["local_status"] == "local_achieved"
    assert result.metrics()["selected_extraction_applications"] == 1


def test_hidden_supply_and_milk_sensor_do_not_choose_or_drive_the_task(runs):
    base = runs["nominal"]
    for case in ("dry", "depleted", "milk_sensor_off"):
        result = runs[case]
        assert [s.command for s in result.run.local_steps] == [s.command for s in base.run.local_steps]
        assert [c.commitment for c in result.run.cycles] == [c.commitment for c in base.run.cycles]
        assert result.metrics()["extraction_installations"] == 1
    assert runs["milk_sensor_off"].run.final_feedback.oral_extraction.milk_transferred_units is None


@pytest.mark.parametrize("case", ["extraction_off", "suckle_off", "no_need", "source_off", "attention_off",
                                   "missing_stroke", "missing_seal", "nonsealable", "competing_initial"])
def test_no_selected_contribution_means_no_hidden_extraction(case, runs):
    result = runs[case]
    assert result.metrics()["selected_extraction_applications"] == 0
    assert result.metrics()["physical_milk_units"] == 0
    assert all(step.command is None or step.command.oral_extraction_drive in (None, 0)
               for step in result.run.local_steps)


@pytest.mark.parametrize("case", ["latch_then_extract", "seek_then_latch", "stand_follow"])
def test_continuation_is_one_world_not_a_reset_or_second_task_timer(case, runs):
    result = runs[case]
    closure = [c.calculation.navigation.application for c in result.run.cycles
               if isinstance(c.calculation.navigation.application, SuckleApplicationV1)]
    extract = [c.calculation.navigation.application for c in result.run.cycles
               if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)]
    assert len(extract) == 1 and closure
    app = extract[0]
    assert app.task.task_id == closure[0].task.task_id
    assert app.task.started_tick == closure[0].task.started_tick
    assert app.task.started_cycle == closure[0].task.started_cycle
    assert app.task.latch.status == "latch_established"
    assert {s.feedback.stream.generation for s in result.run.local_steps if s.feedback} == {1}
    assert all(not c.suckle_learning_report or c.suckle_learning_report.new_participation is None
               for c in result.run.cycles if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1))


@pytest.mark.parametrize("capacity", [1, 8, 64, 4096])
def test_diagnostic_reads_and_capacity_do_not_change_behavior(capacity, runs, monkeypatch):
    rng = random.getstate()
    result = demo.run_suckle_extraction_v1("nominal", trace_capacity=capacity)
    base = runs["nominal"]
    assert result.run.local_steps == base.run.local_steps
    assert result.run.physical_samples == base.run.physical_samples
    assert [c.commitment for c in result.run.cycles] == [c.commitment for c in base.run.cycles]
    assert result.metrics() == base.metrics()
    def forbidden(*args, **kwargs):
        raise AssertionError("observer attempted to execute a live task")
    monkeypatch.setattr(demo.IntegratedRightingTrialV1, "advance_lower", forbidden)
    for _ in range(2):
        assert "not milk, nourishment" in demo.render_suckle_extraction_v1(result, detail=True)
        detached = result.as_dict()
        detached["cycles"].clear()
        assert result.run.cycles
    assert random.getstate() == rng


@pytest.mark.parametrize("case", ["nominal", "latch_then_extract", "competing_after"])
def test_fresh_generations_produce_identical_evidence(case, runs):
    assert demo.run_suckle_extraction_v1(case).as_dict() == runs[case].as_dict()


@pytest.mark.parametrize("bad", [None, True, 1, "", "unknown", "nominal "])
def test_bad_case_cannot_silently_select_another(bad):
    with pytest.raises(ValueError):
        demo.suckle_extraction_profile_v1(bad)


@pytest.mark.parametrize("mutation", ["duplicate_application", "installations", "steps", "durable"])
def test_observer_rejects_corrupted_completed_evidence(mutation, runs):
    result = runs["nominal"]
    run = result.run
    if mutation == "duplicate_application":
        run = replace(run, cycles=(run.cycles[0], *run.cycles))
    elif mutation == "installations":
        run = replace(run, installations=99)
    elif mutation == "steps":
        run = replace(run, local_steps=run.local_steps[:-1])
    else:
        run = replace(run, durable_after="unreported change")
    assert replace(result, run=run).review_status == "FAIL"


def load_cli():
    spec = importlib.util.spec_from_file_location("lc_review_cli", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_json_and_failed_review_use_shared_results(capsys, monkeypatch, runs):
    cli = load_cli()
    assert cli.main(["--suckle-extraction", "--case", "nominal", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [runs["nominal"].as_dict()]
    bad = replace(runs["nominal"], run=replace(runs["nominal"].run, installations=99))
    monkeypatch.setattr(cli, "run_suckle_extraction_v1", lambda case: bad)
    assert cli.main(["--suckle-extraction", "--case", "nominal"]) == 1
    assert "FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--suckle-extraction", "--oral-extraction-control"],
                                   ["--suckle-extraction", "--suckle"], ["--suckle-extraction", "--case", "unknown"]])
def test_invalid_cli_choices_fail_before_execution(args):
    with pytest.raises(SystemExit) as error:
        load_cli().main(args)
    assert error.value.code == 2


def test_cli_outside_repository(tmp_path, runs):
    r = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                        "--suckle-extraction", "--case", "delayed", "--json"], cwd=tmp_path, text=True,
                       encoding="utf-8", capture_output=True, timeout=30, check=False)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [runs["delayed"].as_dict()]


def test_parent_menu_preserves_previous_routes_and_never_falls_through(monkeypatch, capsys):
    import nca8_feeding_demo as feeding
    calls = []
    choices = iter(("26", "27", "28", "29", "30", ""))
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda *a: next(choices))
    names = ("run_suckle_attention_menu_v1", "run_suckle_learning_menu_v1", "run_oral_extraction_menu_v1",
             "run_oral_extraction_control_menu_v1", "run_suckle_extraction_menu_v1")
    for name in names:
        monkeypatch.setattr(feeding, name, lambda name=name: calls.append(name))
    feeding.run_feeding_detail_menu_v1()
    assert calls == list(names)
    assert "Choose a displayed number" not in capsys.readouterr().out


def test_retained_menu_detail_does_not_reexecute(monkeypatch, capsys, runs):
    choices = iter(("6", "bad", "1", "6", "6", ""))
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda *a: next(choices))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_suckle_extraction_v1", run)
    demo.run_suckle_extraction_menu_v1()
    assert calls == ["nominal", "extraction_off", "latch_then_extract"]
    text = capsys.readouterr().out
    assert "No completed results" in text and "Invalid selection" in text and "Cycle" in text


def test_default_H_factory_has_no_extraction_route_and_registry_has_one_new_service():
    import cca8_run
    from nca8_suckle_demo import create_suckle_trial_v1
    trial = create_suckle_trial_v1(outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True)
    assert trial.core.suckle.profile.extraction_enabled is False
    assert trial.latest_feedback.oral_extraction is None
    assert cca8_run.__version__ == "0.30.46"
    assert len(cca8_run._cca8_component_rows()) == 126
    assert ("nca8_suckle_extraction_demo", "nca8_suckle_extraction_demo") in cca8_run._CCA8_COMPONENT_REGISTRY
    assert len(cca8_run.PRIMITIVES) == 8
