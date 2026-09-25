"""L-E live review/access tests; no supplied-target fixture is relabelled cognition."""
from dataclasses import replace
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import nca8_feeding_demo as feeding_menu
import nca8_suckle_extraction_attention_demo as demo
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def experiment(case):
    return demo.run_extraction_attention_v1(case)


@pytest.mark.parametrize("case", demo.EXTRACTION_ATTENTION_CASES_V1)
def test_all_live_reviews_pass(case):
    result = experiment(case)
    assert result.review_status == "PASS", result.checks()
    assert all(ok for _, ok in result.checks())
    assert result.profile.latch.suckle.extraction_outcomes_enabled
    assert result.as_dict()["limits"] == "no_remedy_retry_new_batch_learning_nourishment_or_causal_credit"


@pytest.mark.parametrize("case", demo.EXTRACTION_ATTENTION_CASES_V1)
def test_exports_and_rendering_are_pure_and_json_detached(case):
    result = experiment(case)
    original = result.as_dict()
    compact = demo.render_extraction_attention_v1(result)
    detailed = demo.render_extraction_attention_v1(result, detail=True)
    assert result.as_dict() == json.loads(json.dumps(original))
    assert compact in detailed
    original["cycles"].clear()
    assert result.as_dict()["cycles"] and result.review_status == "PASS"
    assert "Outcome questions are not IPs" in compact


@pytest.mark.parametrize("case", ["competing_source", "maintain_source"])
def test_causal_pair_has_same_current_source_but_different_focal_choice(case):
    result = experiment(case)
    request, = result.requests()
    left = next(c for c in result.run.cycles if c.calculation.cutoff_tick == request.admitted_tick)
    right = next(c for c in result.control.cycles if c.calculation.cutoff_tick == request.admitted_tick)
    assert left.feeding_detail_source == right.feeding_detail_source
    assert left.calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
    assert right.calculation.attention.selected_source_state.source_map_ref.map_id != "feeding_detail"
    assert left.calculation.navigation.application is None and left.receipt.dispatch.pnm is None and not left.reservations
    assert len(result.interpretations()) == 1


def test_inaccessible_source_expires_without_late_reconstruction():
    result = experiment("source_unavailable")
    q, = result.requests()
    assert not result.interpretations()
    assert (q.request_id, "expired_uninterpreted", q.expires_at_tick) in result.dispositions
    assert any(c.feeding_detail_source.focal_accessible for c in result.run.cycles if c.calculation.cutoff_tick > q.expires_at_tick)
    assert all(not c.extraction_attention.pending for c in result.run.cycles if c.calculation.cutoff_tick >= q.expires_at_tick)


def test_independent_old_I_J_K_disabled_case():
    r = experiment("without_latch_route")
    assert len(r.requests()) == len(r.interpretations()) == 1
    assert all(c.suckle_correspondence is None and c.suckle_attention is None and c.suckle_learning_report is None for c in r.run.cycles)
    assert all(c.suckle_task.task is None for c in r.run.cycles)


@pytest.mark.parametrize("capacity", [1, 4, 16])
def test_trace_retention_changes_no_allocation_evidence_or_physics(capacity):
    actual = demo.run_extraction_attention_v1("competing_source", trace_capacity=capacity)
    full = experiment("competing_source")
    assert actual.requests() == full.requests() and actual.interpretations() == full.interpretations()
    assert actual.run.local_steps == full.run.local_steps and actual.run.physical_samples == full.run.physical_samples
    assert actual.dispositions == full.dispositions and actual.review_status == "PASS"


def test_read_only_owner_diagnostics_and_reset():
    p = demo.extraction_attention_profile_v1()
    trial = create_suckle_extraction_trial_v1(p)
    collect_seek_nipple_evidence_v1(trial, p.latch.run)
    owner = trial.core.feeding_detail.extraction_outcome_attention
    before = owner.retained_counts(), owner.dispositions(), trial.tick
    for _ in range(8):
        owner.pending(); owner.dispositions(); owner.retained_counts(); trial.snapshot()
    assert (owner.retained_counts(), owner.dispositions(), trial.tick) == before
    old_stream = owner.stream
    trial.reset()
    current = trial.core.feeding_detail.extraction_outcome_attention
    assert current is not owner and current.stream != old_stream
    assert current.pending() == current.dispositions() == ()


def test_observer_rejects_removed_causal_question():
    r = experiment("mismatch")
    cycles = tuple(replace(c, extraction_attention=replace(c.extraction_attention, created=())) for c in r.run.cycles)
    bad = replace(r, run=replace(r.run, cycles=cycles))
    assert bad.review_status == "FAIL"


@pytest.mark.parametrize("bad", [None, True, 2, "unknown", "", "body_shift"])
def test_invalid_case_is_not_silently_repaired(bad):
    with pytest.raises(ValueError): demo.extraction_attention_profile_v1(bad)


def load_script():
    spec = importlib.util.spec_from_file_location("le_review_script", ROOT / "scripts/review_nca8_feeding.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_cli_uses_identical_shared_result_and_returns_failure(monkeypatch, capsys):
    script = load_script()
    r = experiment("mismatch")
    monkeypatch.setattr(script, "run_extraction_attention_v1", lambda case: r)
    assert script.main(["--suckle-extraction-attention", "--case", "mismatch", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [r.as_dict()]
    monkeypatch.setattr(demo.ExtractionAttentionExperimentV1, "review_status", property(lambda self: "FAIL"))
    assert script.main(["--suckle-extraction-attention", "--case", "mismatch"]) == 1


@pytest.mark.parametrize("args", [
    ["--suckle-extraction-attention", "--suckle-extraction-outcomes"],
    ["--suckle-extraction-attention", "--case", "unknown"],
])
def test_cli_invalid_or_conflicting_selector_fails(args):
    with pytest.raises(SystemExit) as exc: load_script().main(args)
    assert exc.value.code != 0


def test_cli_runs_from_outside_repository(tmp_path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OAI_IS_JUPYTER_KERNEL="0", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                             "--suckle-extraction-attention", "--case", "mismatch", "--json"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [experiment("mismatch").as_dict()]


def test_menu32_and_old_routes_delegate_without_fallthrough(monkeypatch, capsys):
    calls = []
    targets = {"26": "run_suckle_attention_menu_v1", "27": "run_suckle_learning_menu_v1",
               "28": "run_oral_extraction_menu_v1", "29": "run_oral_extraction_control_menu_v1",
               "30": "run_suckle_extraction_menu_v1", "31": "run_suckle_extraction_outcome_menu_v1",
               "32": "run_extraction_attention_menu_v1"}
    for key, name in targets.items(): monkeypatch.setattr(feeding_menu, name, lambda k=key: calls.append(k))
    choices = iter([*targets, ""])
    monkeypatch.setattr(feeding_menu.cca8_cli, "read_menu_input_v1", lambda *a, **kw: next(choices))
    feeding_menu.run_feeding_detail_menu_v1()
    assert calls == list(targets)
    assert "Invalid" not in capsys.readouterr().out


def test_retained_detail_runs_no_second_experiment(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(demo, "run_extraction_attention_v1", lambda case: calls.append(case) or experiment(case))
    choices = iter(["6", "1", "6", "6", "bad", "0"])
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda *a: next(choices))
    demo.run_extraction_attention_menu_v1()
    assert calls == ["mismatch", "route_off", "competing_source", "maintain_source"]
    text = capsys.readouterr().out
    assert "No retained result." in text and "Invalid selection." in text


def test_registry_contains_services_not_extra_IPs():
    import cca8_run
    rows = cca8_run._cca8_component_rows()
    assert len(rows) == 121
    assert {"nca8_suckle_extraction_attention", "nca8_suckle_extraction_attention_demo"} <= {r[0] for r in rows}
