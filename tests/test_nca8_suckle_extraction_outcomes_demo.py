"""L-D integrated C2 evidence, route neutrality, shared review and menu/CLI access."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_suckle_extraction_outcomes_demo as demo
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1
from nca8_suckle import SuckleExtractionApplicationV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_extraction_outcome_v1(case) for case in demo.SUCKLE_EXTRACTION_OUTCOME_CASES_V1}


@pytest.mark.parametrize("case", demo.SUCKLE_EXTRACTION_OUTCOME_CASES_V1)
def test_live_review_and_disabled_control_have_same_actions_and_original_owners(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", result.checks()
    assert result.run.local_steps == result.control.local_steps
    assert result.run.physical_samples == result.control.physical_samples
    assert [c.commitment for c in result.run.cycles] == [c.commitment for c in result.control.cycles]
    assert json.loads(json.dumps(result.as_dict(), allow_nan=False)) == result.as_dict()
    for a, b in zip(result.run.cycles, result.control.cycles):
        assert a.calculation.attention == b.calculation.attention
        assert a.scheduler == b.scheduler
        app = a.calculation.navigation.application
        if isinstance(app, SuckleExtractionApplicationV1):
            assert replace(app, projection=replace(app.projection, outcomes_enabled=False)) == b.calculation.navigation.application
    for outcome in result.outcomes():
        assert outcome.claim.application.projection.pnm.expected_relations == outcome.claim.application.expected_relations
        assert not outcome.milk_evidence()["milk_yield_predicted"]


@pytest.mark.parametrize("case,total,coverage", [
    ("nominal", .2, "complete"), ("one_cycle", .1, "complete"), ("dry", 0, "complete"),
    ("depleted", .05, "complete"), ("milk_sensor_off", 0, "unavailable"), ("dropout", .1, "partial"),
    ("comparison_off", .2, "complete"), ("without_closure_owner", .2, "complete"),
    ("delayed", .1, "complete"), ("cancelled", .1, "complete"),
])
def test_real_interval_totals_and_coverage_not_provider_or_latest_sample(case, total, coverage, runs):
    outcome, = runs[case].outcomes()
    milk = outcome.milk_evidence()
    assert milk["known_interval_sum"] == pytest.approx(total)
    assert milk["coverage"] == coverage
    if coverage != "complete": assert milk["exact_observed_total"] is None
    if case == "dropout":
        assert runs[case].run.final_feedback.event_tick == 1  # held old sample is not fresh zero or a total
        assert milk["missing_event_ticks"] == [2, 3, 4]
    else:
        assert runs[case].run.final_feedback.oral_extraction.milk_transferred_units in (0, None)


def test_same_dry_and_wet_movement_predictions_do_not_invent_a_milk_expectation(runs):
    wet, dry = runs["nominal"].outcomes()[0], runs["dry"].outcomes()[0]
    assert wet.relations == dry.relations and wet.status == dry.status == "local_sequence_observed"
    assert wet.claim.application.projection.pnm == dry.claim.application.projection.pnm
    assert wet.milk_evidence()["quantity_status"] == "observed_positive"
    assert dry.milk_evidence()["quantity_status"] == "known_zero"


def test_actual_nonfocal_C2_result_retains_original_source_not_current_WNM(runs):
    result = runs["nonfocal_outcome"]
    published = [c for c in result.run.cycles if c.extraction_correspondence and c.extraction_correspondence.outcomes]
    assert len(published) == 1
    cycle = published[0]
    assert cycle.calculation.attention.selected_source_state != cycle.feeding_detail_source
    outcome, = cycle.extraction_correspondence.outcomes
    assert outcome.claim.application.projection.basis.cutoff_tick == 0
    assert outcome.evaluated_tick == 12 and dict(outcome.relations)["finite_reciprocation"] == "matched"
    assert outcome.milk_evidence()["exact_observed_total"] == pytest.approx(.2)


@pytest.mark.parametrize("case", ["latch_then_extract", "seek_then_latch", "stand_follow"])
def test_original_closure_recipients_survive_extraction_outcome(case, runs):
    result = runs[case]; outcome, = result.outcomes()
    app = outcome.claim.application
    assert app.task.latch is not None and app.task.started_tick == app.task.latch.started_tick
    for cycle in result.run.cycles:
        if cycle.suckle_correspondence:
            assert all(o.claim.preview.pnm.application_id != app.application_id for o in cycle.suckle_correspondence.outcomes)
        if isinstance(cycle.calculation.navigation.application, SuckleExtractionApplicationV1):
            assert cycle.suckle_learning_report.new_participation is None
    assert result.run.durable_before == result.run.durable_after


@pytest.mark.parametrize("capacity", [1, 8, 64, 4096])
def test_diagnostics_and_read_only_exports_do_not_change_evidence_or_control(capacity, runs, monkeypatch):
    before_rng = random.getstate()
    result = demo.run_suckle_extraction_outcome_v1("nominal", trace_capacity=capacity)
    assert result.outcomes() == runs["nominal"].outcomes()
    assert result.run.local_steps == runs["nominal"].run.local_steps
    def forbidden(*args, **kwargs): raise AssertionError("observer executed a live trial")
    monkeypatch.setattr(demo, "create_suckle_extraction_trial_v1", forbidden)
    assert "Known milk sum" in demo.render_suckle_extraction_outcome_v1(result, detail=True)
    result.as_dict()["outcomes"].clear()
    assert len(result.outcomes()) == 1 and random.getstate() == before_rng


@pytest.mark.parametrize("bad", [None, True, 1, "", "not_a_case", "nominal "])
def test_invalid_case_is_rejected(bad):
    with pytest.raises(ValueError): demo.suckle_extraction_outcome_profile_v1(bad)


@pytest.mark.parametrize("mutation", ["duplicate_result", "physical", "commitments", "durable", "quantity"])
def test_observer_does_not_print_success_for_corrupted_evidence(mutation, runs):
    result = runs["nominal"]; run = result.run
    if mutation == "duplicate_result":
        chosen = next(c for c in run.cycles if c.extraction_correspondence and c.extraction_correspondence.outcomes)
        run = replace(run, cycles=(*run.cycles, chosen))
    elif mutation == "physical": run = replace(run, physical_samples=run.physical_samples[:-1])
    elif mutation == "commitments": run = replace(run, cycles=run.cycles[:-1])
    elif mutation == "durable": run = replace(run, durable_after="unreported mutation")
    else:
        cycle = next(c for c in run.cycles if c.extraction_correspondence and c.extraction_correspondence.outcomes)
        outcome, = cycle.extraction_correspondence.outcomes
        corrupted = replace(outcome, samples=())
        new = replace(cycle, extraction_correspondence=replace(cycle.extraction_correspondence, outcomes=(corrupted,)))
        run = replace(run, cycles=tuple(new if c is cycle else c for c in run.cycles))
    assert replace(result, run=run).review_status == "FAIL"


def load_cli():
    spec = importlib.util.spec_from_file_location("ld_cli", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_CLI_and_renderer_share_live_results_and_failures(capsys, monkeypatch, runs):
    cli = load_cli()
    assert cli.main(["--suckle-extraction-outcomes", "--case", "nominal", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [runs["nominal"].as_dict()]
    bad = replace(runs["nominal"], run=replace(runs["nominal"].run, durable_after="changed"))
    monkeypatch.setattr(cli, "run_suckle_extraction_outcome_v1", lambda case: bad)
    assert cli.main(["--suckle-extraction-outcomes", "--case", "nominal"]) == 1
    assert "FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--suckle-extraction-outcomes", "--suckle-extraction"],
                                   ["--suckle-extraction-outcomes", "--suckle-outcomes"],
                                   ["--suckle-extraction-outcomes", "--case", "unknown"]])
def test_invalid_CLI_combinations_fail(args):
    with pytest.raises(SystemExit) as error: load_cli().main(args)
    assert error.value.code == 2


def test_cli_from_outside_repository(tmp_path, runs):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                              "--suckle-extraction-outcomes", "--case", "dry", "--json"], cwd=tmp_path,
                             text=True, encoding="utf-8", capture_output=True, timeout=30, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [runs["dry"].as_dict()]


def test_menu31_delegates_and_old_menu30_stays(monkeypatch, capsys):
    import nca8_feeding_demo as feeding
    responses = iter(["31", "30", ""]); calls = []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda *a, **k: next(responses))
    monkeypatch.setattr(feeding, "run_suckle_extraction_outcome_menu_v1", lambda: calls.append("LD"))
    monkeypatch.setattr(feeding, "run_suckle_extraction_menu_v1", lambda: calls.append("LC"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["LD", "LC"]
    assert "Choose a displayed number" not in capsys.readouterr().out


def test_shared_submenu_retains_results_without_another_trial(monkeypatch, capsys, runs):
    responses = iter(["6", "invalid", "1", "6", "0"]); calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda *a, **k: next(responses))
    def existing(case): calls.append(case); return runs[case]
    monkeypatch.setattr(demo, "run_suckle_extraction_outcome_v1", existing)
    demo.run_suckle_extraction_outcome_menu_v1()
    assert calls == ["nominal", "consumer_off", "comparison_off", "without_closure_owner"]
    output = capsys.readouterr().out
    assert "No completed results" in output and "Invalid selection" in output and "Original PNM" in output


def test_new_components_are_services_not_new_task_IPs():
    import cca8_run
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.45" and len(rows) == 123
    assert len(cca8_run.PRIMITIVES) == 8
    assert {r[0] for r in rows} >= {"nca8_suckle_extraction_outcomes", "nca8_suckle_extraction_outcomes_demo"}
