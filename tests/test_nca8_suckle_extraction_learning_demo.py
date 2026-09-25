"""Shared L-F review, selective controls, read-only exports and menu/CLI access."""
from dataclasses import replace
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_feeding_demo as feeding_menu
import nca8_suckle_extraction_learning_demo as demo
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def experiment(case):
    return demo.run_extraction_learning_v1(case)


@pytest.mark.parametrize("case", demo.EXTRACTION_LEARNING_CASES_V1)
def test_every_review_uses_live_hook_and_identical_behavioral_control(case):
    result = experiment(case)
    assert result.review_status == "PASS", result.checks()
    assert result.profile.latch.suckle.extraction_learning_hook_enabled
    assert len(result.checks()) >= 16
    assert all(c.extraction_learning_report is not None for c in result.run.cycles)
    assert all(c.extraction_learning_report is None for c in result.control.cycles)
    assert result.run.physical_samples == result.control.physical_samples
    assert result.run.local_steps == result.control.local_steps


@pytest.mark.parametrize("case", demo.EXTRACTION_LEARNING_CASES_V1)
def test_export_is_detached_and_rendering_cannot_run_or_learn(case):
    result = experiment(case)
    before, rng = result.as_dict(), random.getstate()
    compact = demo.render_extraction_learning_v1(result)
    detail = demo.render_extraction_learning_v1(result, detail=True)
    assert compact in detail and "No durable learning" in compact
    assert result.as_dict() == before and random.getstate() == rng
    copied = result.as_dict()
    copied["cycles"].clear()
    copied["dispositions"].clear()
    assert result.as_dict() == before
    assert json.loads(json.dumps(before, allow_nan=False)) == before


@pytest.mark.parametrize("capacity", [1, 4, 16])
def test_trace_retention_cannot_change_participation_or_physics(capacity):
    small = demo.run_extraction_learning_v1("mismatch", trace_capacity=capacity)
    full = experiment("mismatch")
    assert small.registrations() == full.registrations()
    assert small.dispositions == full.dispositions
    assert small.run.local_steps == full.run.local_steps and small.run.physical_samples == full.run.physical_samples
    assert small.review_status == "PASS"


def test_report_cannot_pass_when_participation_or_behavior_is_removed():
    result = experiment("matched")
    first = result.run.cycles[0]
    missing = replace(first, extraction_learning_report=replace(first.extraction_learning_report, new_participation=None))
    bad = replace(result, run=replace(result.run, cycles=(missing, *result.run.cycles[1:])))
    assert bad.review_status == "FAIL"
    bad = replace(result, run=replace(result.run, local_steps=result.run.local_steps[:-1]))
    assert bad.review_status == "FAIL"


def test_read_only_owner_views_and_generation_reset():
    profile = demo.extraction_learning_profile_v1("route_off")
    trial = create_suckle_extraction_trial_v1(profile)
    collect_seek_nipple_evidence_v1(trial, profile.latch.run)
    owner = trial.core.feeding_detail.extraction_learning_hook
    before = owner.retained_counts(), owner.pending(), owner.history(), trial.tick
    for _ in range(5):
        owner.pending(); owner.history(); owner.retained_counts(); trial.snapshot()
    assert before == (owner.retained_counts(), owner.pending(), owner.history(), trial.tick)
    trial.reset()
    current = trial.core.feeding_detail.extraction_learning_hook
    assert current is not owner and current.stream != owner.stream
    assert current.pending() == current.history() == ()


@pytest.mark.parametrize("case", ["dry", "milk_sensor_off", "depleted"])
def test_milk_information_is_observed_context_not_a_forecast_or_reward(case):
    result = experiment(case)
    accepted = [d for d in result.dispositions if d.status == "accepted_no_update"]
    assert len(accepted) == 1
    data = accepted[0].as_dict()
    assert "milk" not in data["accepted_relations"] and data["durable_learning_updates"] == 0
    assert data["milk_evidence"]["milk_yield_predicted"] is False
    assert data["milk_evidence"]["nourishment"] == "not_established"
    if case == "dry":
        assert data["milk_evidence"]["exact_observed_total"] == 0
        assert all(status == "matched" for status in data["accepted_relations"].values())
    elif case == "milk_sensor_off":
        assert data["milk_evidence"]["exact_observed_total"] is None
        assert data["milk_evidence"]["coverage"] == "unavailable"


@pytest.mark.parametrize("bad", [None, True, 1, "", "unknown"])
def test_invalid_case_is_not_normalized_into_another_experiment(bad):
    with pytest.raises(ValueError):
        demo.extraction_learning_profile_v1(bad)


@pytest.mark.parametrize("bad", [None, 1, "yes"])
def test_renderer_requires_boolean_detail(bad):
    with pytest.raises(TypeError):
        demo.render_extraction_learning_v1(experiment("matched"), detail=bad)


def load_script():
    spec = importlib.util.spec_from_file_location("lf_review_script", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_CLI_delegates_to_shared_run_and_returns_failed_review(monkeypatch, capsys):
    script, result = load_script(), experiment("matched")
    calls = []
    monkeypatch.setattr(script, "run_extraction_learning_v1", lambda case: calls.append(case) or result)
    assert script.main(["--suckle-extraction-learning", "--case", "matched", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [result.as_dict()] and calls == ["matched"]
    monkeypatch.setattr(demo.ExtractionLearningExperimentV1, "review_status", property(lambda self: "FAIL"))
    assert script.main(["--suckle-extraction-learning", "--case", "matched"]) == 1


@pytest.mark.parametrize("args", [
    ["--suckle-extraction-learning", "--suckle-extraction-attention"],
    ["--suckle-extraction-learning", "--suckle-learning"],
    ["--suckle-extraction-learning", "--case", "unknown"],
])
def test_CLI_rejects_conflicting_or_unknown_selectors(args):
    with pytest.raises(SystemExit) as exc:
        load_script().main(args)
    assert exc.value.code != 0


def test_CLI_works_outside_repository(tmp_path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OAI_IS_JUPYTER_KERNEL="0", PYTHONIOENCODING="utf-8")
    run = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                          "--suckle-extraction-learning", "--case", "matched", "--json"],
                         cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45, check=False)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == [experiment("matched").as_dict()]


def test_menu33_and_old_feeding_routes_have_no_fallthrough(monkeypatch, capsys):
    calls = []
    targets = {"27": "run_suckle_learning_menu_v1", "28": "run_oral_extraction_menu_v1",
               "29": "run_oral_extraction_control_menu_v1", "30": "run_suckle_extraction_menu_v1",
               "31": "run_suckle_extraction_outcome_menu_v1", "32": "run_extraction_attention_menu_v1",
               "33": "run_extraction_learning_menu_v1"}
    for key, name in targets.items():
        monkeypatch.setattr(feeding_menu, name, lambda k=key: calls.append(k))
    choices = iter([*targets, ""])
    monkeypatch.setattr(feeding_menu.cca8_cli, "read_menu_input_v1", lambda *a, **kw: next(choices))
    feeding_menu.run_feeding_detail_menu_v1()
    assert calls == list(targets)
    assert "33) Extraction participation" in capsys.readouterr().out


def test_retained_menu_detail_does_not_execute_again(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(demo, "run_extraction_learning_v1", lambda case: calls.append(case) or experiment(case))
    choices = iter(["6", "1", "6", "6", "bad", "0"])
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda *a: next(choices))
    demo.run_extraction_learning_menu_v1()
    assert calls == ["matched", "mismatch", "route_off", "without_latch_route"]
    text = capsys.readouterr().out
    assert "No retained result." in text and "Invalid selection." in text


def test_host_registers_two_services_not_new_behavioral_primitives():
    import cca8_run
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.45" and len(rows) == 123
    assert len(cca8_run.PRIMITIVES) == 8
    assert {"nca8_suckle_extraction_learning", "nca8_suckle_extraction_learning_demo"} <= {r[0] for r in rows}


def test_route_status_is_reported_at_composite_boundary_not_in_old_PNM_evidence():
    result = experiment("matched")
    for cycle in result.run.cycles:
        data = cycle.as_dict()
        assert data["extraction_correspondence"]["learning_route"] == "suckle_extraction_no_learning_v1"
        assert data["suckle_extraction"]["participation"] == "separate_source_owned_F_hook"
        assert data["extraction_attention"]["learning_route"] == "separate_source_owned_F_hook"
    assert result.run.cycles[0].extraction_learning_report.new_participation.claim is result.run.cycles[0].extraction_correspondence.registration
