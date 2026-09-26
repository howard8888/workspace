"""Shared M menu/script, detached evidence, repeatability and failed-review tests."""
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

import nca8_feeding_demo as menu
import nca8_sustained_feeding_demo as demo
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def result(case="nominal"):
    return demo.run_sustained_feeding_v1(case)


def script():
    spec = importlib.util.spec_from_file_location("m_review_cli", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case", demo.SUSTAINED_FEEDING_CASES_V1)
def test_export_roundtrip_is_detached_and_rendering_performs_no_work(case, monkeypatch):
    r = result(case)
    state, rng = r.as_dict(), random.getstate()
    def forbidden(*args, **kwargs):
        raise AssertionError("render/export cannot run an experiment")
    monkeypatch.setattr(demo, "run_sustained_feeding_v1", forbidden)
    compact = demo.render_sustained_feeding_v1(r)
    detailed = demo.render_sustained_feeding_v1(r, detail=True)
    assert compact in detailed and "not biological nutrition" in compact
    assert r.as_dict() == state and random.getstate() == rng
    assert json.loads(json.dumps(state, allow_nan=False)) == state
    copy = r.as_dict()
    copy["cycles"].clear()
    copy["profile"]["downstream_competence"]["unavailable_ticks"].append(999)
    assert r.as_dict() == state


@pytest.mark.parametrize("capacity", [1, 4, 16])
def test_diagnostic_capacity_cannot_change_decisions_body_or_satisfaction(capacity):
    small = demo.run_sustained_feeding_v1("nominal", trace_capacity=capacity)
    large = result()
    assert small.applications() == large.applications() and small.outcomes() == large.outcomes()
    assert small.run.physical_samples == large.run.physical_samples and small.run.local_steps == large.run.local_steps
    assert tuple(c.sustained_feeding for c in small.run.cycles) == tuple(c.sustained_feeding for c in large.run.cycles)
    assert small.review_status == "PASS"


@pytest.mark.parametrize("corruption", ["no_cycles", "no_F", "no_participant", "no_storage_count", "no_body_sample", "missing_assessment"])
def test_missing_review_evidence_fails_instead_of_vacuous_success(corruption):
    r = result("already_sealed")
    first = r.run.cycles[0]
    if corruption == "no_cycles":
        changed = replace(r.run, cycles=())
    elif corruption == "no_storage_count":
        changed = replace(r.run, peak_counts=tuple(row for row in r.run.peak_counts if row[0] != "extraction_original_claims"))
    elif corruption == "no_body_sample":
        changed = replace(r.run, physical_samples=r.run.physical_samples[1:])
    else:
        if corruption == "no_F":
            first = replace(first, extraction_learning_report=None)
        elif corruption == "no_participant":
            first = replace(first, extraction_learning_report=replace(first.extraction_learning_report, new_participation=None))
        else:
            first = replace(first, sustained_feeding=None)
        changed = replace(r.run, cycles=(first, *r.run.cycles[1:]))
    assert replace(r, run=changed).review_status == "FAIL"


def test_no_cycles_is_not_a_pass_in_a_no_extraction_control():
    r = result("internal_sensor_off")
    assert replace(r, run=replace(r.run, cycles=())).review_status == "FAIL"


@pytest.mark.parametrize("bad", [None, 1, "", "unknown", True])
def test_unknown_case_is_not_silently_normalized(bad):
    with pytest.raises(ValueError):
        demo.sustained_feeding_profile_v1(bad)


@pytest.mark.parametrize("bad", [None, 1, "yes"])
def test_renderer_requires_explicit_boolean_detail(bad):
    with pytest.raises(TypeError):
        demo.render_sustained_feeding_v1(result(), detail=bad)


def test_menu34_delegates_without_fallthrough_or_replacing_K_LE_LF(monkeypatch, capsys):
    calls = []
    choices = {"27": "run_suckle_learning_menu_v1", "32": "run_extraction_attention_menu_v1",
               "33": "run_extraction_learning_menu_v1", "34": "run_sustained_feeding_menu_v1"}
    for key, name in choices.items():
        monkeypatch.setattr(menu, name, lambda k=key: calls.append(k))
    inputs = iter([*choices, ""])
    monkeypatch.setattr(menu.cca8_cli, "read_menu_input_v1", lambda: next(inputs))
    menu.run_feeding_detail_menu_v1()
    assert calls == list(choices) and "34) Sustained feeding" in capsys.readouterr().out


def test_retained_menu_detail_does_not_rerun_physics(monkeypatch, capsys):
    calls = []
    inputs = iter(["6", "bad", "1", "6", "0"])
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(inputs))
    monkeypatch.setattr(demo, "run_sustained_feeding_v1", lambda case: calls.append(case) or result(case))
    demo.run_sustained_feeding_menu_v1()
    out = capsys.readouterr().out
    assert calls == ["nominal", "already_sealed", "latch_then_extract"]
    assert "No retained result." in out and "Invalid selection." in out and "Tick 56" in out


def test_CLI_same_shared_results_and_nonzero_on_failed_review(monkeypatch, capsys):
    cli = script()
    calls = []
    monkeypatch.setattr(cli, "run_sustained_feeding_v1", lambda case: calls.append(case) or result(case))
    assert cli.main(["--sustained-feeding", "--case", "nominal", "--json"]) == 0
    assert calls == ["nominal"] and json.loads(capsys.readouterr().out) == [result().as_dict()]
    monkeypatch.setattr(demo.SustainedFeedingExperimentV1, "review_status", property(lambda self: "FAIL"))
    assert cli.main(["--sustained-feeding", "--case", "nominal"]) == 1


@pytest.mark.parametrize("args", [["--sustained-feeding", "--suckle-extraction-learning"],
                                  ["--sustained-feeding", "--case", "unknown"]])
def test_CLI_rejects_conflicting_or_unknown_selection(args):
    with pytest.raises(SystemExit) as exc:
        script().main(args)
    assert exc.value.code != 0


def test_CLI_from_external_directory_preserves_fixed_experiment(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"), "--sustained-feeding",
                           "--case", "nominal", "--json"], cwd=tmp_path, check=False, timeout=45,
                          capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [result().as_dict()]


def test_fresh_generation_repeats_are_identical_but_no_stale_owner_survives():
    p = demo.sustained_feeding_profile_v1("already_sealed")
    a, b = demo.create_sustained_feeding_trial_v1(p), demo.create_sustained_feeding_trial_v1(p)
    assert a.core is not b.core and a.core.feeding_detail is not b.core.feeding_detail
    ra = collect_seek_nipple_evidence_v1(a, p.extraction.latch.run)
    rb = collect_seek_nipple_evidence_v1(b, p.extraction.latch.run)
    assert ra == rb
    old = a.core
    a.reset()
    assert old.fault and a.core is not old and a.core.suckle.extraction_applications() == ()
    assert a.core.cognition.sensory.feeding_need is None
    assert a.core.extraction_outcomes.history() == ()
    assert a.core.feeding_detail.extraction_learning_hook.pending() == ()


def test_comparison_off_does_not_invent_relation_targets_or_learning():
    p = demo.sustained_feeding_profile_v1("already_sealed")
    p = replace(p, extraction=replace(p.extraction, latch=replace(p.extraction.latch,
                suckle=replace(p.extraction.latch.suckle, extraction_prediction_comparison_enabled=False))))
    trial = demo.create_sustained_feeding_trial_v1(p)
    r = demo.SustainedFeedingExperimentV1(p, collect_seek_nipple_evidence_v1(trial, p.extraction.latch.run))
    assert r.final.task.status == "completed"
    assert all(value == "comparison_disabled" for o in r.outcomes() for _, value in o.relations)
    assert all(c.extraction_learning_report.new_participation is None for c in r.run.cycles)
    assert r.review_status == "PASS" and r.run.durable_before == r.run.durable_after


def test_release_registry_contains_data_and_observer_not_new_task_primitives():
    """The two new modules must resolve locally in the common host registry."""
    import cca8_run
    import nca8_feeding_state
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.46" and len(rows) == 126
    assert len(cca8_run.PRIMITIVES) == 8
    for module in (nca8_feeding_state, demo):
        matches = [(version, path) for name, version, path in rows if name == module.__name__]
        assert matches == [(module.__version__, module.__file__)]
        assert Path(module.__file__).resolve().parent == ROOT
