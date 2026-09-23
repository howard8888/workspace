"""J's shared menu/CLI observer, physical ablation pairs and truthful review failure."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

import nca8_suckle_attention_demo as demo
from nca8_suckle_demo import run_suckle_v1
from nca8_suckle_outcomes_demo import suckle_behavior_signature_v1


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_attention_v1(case) for case in demo.SUCKLE_ATTENTION_CASES_V1}


@pytest.mark.parametrize("case", demo.SUCKLE_ATTENTION_CASES_V1)
def test_live_review_reports_actual_controls_with_complete_bounded_evidence(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", [name for name, passed in result.checks() if not passed]
    exported = result.as_dict()
    assert exported["scope"] == "P16_2C_J_suckle_outcome_attention"
    assert exported["B99"] == "open" and exported["suckle_learning"] == "unimplemented_no_participation"
    assert exported["durable_before"] == exported["durable_after"]
    assert exported["metrics"]["milk"] == "not_supplied" and not exported["metrics"]["full_suckle_complete"]
    assert json.loads(json.dumps(exported, allow_nan=False))["checks"] == dict(result.checks())


@pytest.mark.parametrize("prefix", ["competing", "maintain"])
def test_physical_on_off_pairs_hold_other_inputs_fixed_at_causal_cutoff(prefix, runs):
    on, off = runs[prefix + "_on"], runs[prefix + "_off"]
    assert on.evidence.profile.run == replace(off.evidence.profile.run, case=on.evidence.profile.run.case)
    assert on.evidence.profile.seal == off.evidence.profile.seal
    assert on.evidence.profile.capability == off.evidence.profile.capability
    assert on.evidence.run.local_steps[:12] == off.evidence.run.local_steps[:12]
    assert on.evidence.run.physical_samples[:13] == off.evidence.run.physical_samples[:13]
    a = next(c for c in on.evidence.run.cycles if c.calculation.cutoff_tick == 12)
    b = next(c for c in off.evidence.run.cycles if c.calculation.cutoff_tick == 12)
    assert a.feeding_detail_source == b.feeding_detail_source and a.suckle_task == b.suckle_task
    assert a.local_reports == b.local_reports and a.local_events == b.local_events
    assert a.suckle_correspondence.outcomes == b.suckle_correspondence.outcomes
    assert on.metrics()["cutoff12_source"] == "feeding_detail"
    assert off.metrics()["cutoff12_source"] == "visual_scene"
    assert on.metrics()["interpretation_ticks"] == [12] and off.metrics()["interpretation_ticks"] == []
    assert a.calculation.navigation.application is None and not a.reservations


def test_nominal_J_disabled_factory_preserves_complete_H_behavior(runs):
    assert suckle_behavior_signature_v1(runs["nominal_off"].evidence) == suckle_behavior_signature_v1(run_suckle_v1())


@pytest.mark.parametrize("case", ["comparison_off", "missing_seal", "no_capability", "blocked_motor", "cancelled", "support_loss"])
def test_unscored_uncertain_and_unexecuted_controls_do_not_invent_interpretation(case, runs):
    assert runs[case].outcomes() and not runs[case].requests() and not runs[case].interpretations()


@pytest.mark.parametrize("mutation", ["duplicate_outcome", "durable", "bounds", "schedule", "identity", "permission"])
def test_review_fails_when_completed_evidence_is_corrupted(mutation, runs):
    result = runs["competing_on"]
    raw = result.evidence.run
    if mutation == "durable":
        raw = replace(raw, durable_after="unexpected learned change")
    elif mutation == "bounds":
        raw = replace(raw, peak_counts=raw.peak_counts + (("unknown_owner", 1),))
    elif mutation == "schedule":
        raw = replace(raw, local_steps=raw.local_steps[:-1])
    else:
        cycles = list(raw.cycles)
        index = next(i for i, c in enumerate(cycles) if c.suckle_attention is not None and c.suckle_attention.created)
        cycle = cycles[index]
        if mutation == "duplicate_outcome":
            cycle = replace(cycle, suckle_correspondence=replace(cycle.suckle_correspondence,
                            outcomes=cycle.suckle_correspondence.outcomes * 2))
        elif mutation == "identity":
            frame = cycle.suckle_attention
            request = frame.created[0]
            cycle = replace(cycle, suckle_attention=replace(frame, created=(replace(request, outcome=replace(request.outcome)),)))
        else:
            cycle = replace(cycle, commitment=replace(cycle.commitment, selected_primitive_id="ip:suckle"))
        cycles[index] = cycle
        raw = replace(raw, cycles=tuple(cycles))
    assert replace(result, evidence=replace(result.evidence, run=raw)).review_status == "FAIL"


def test_retained_detail_does_not_rerun_or_mutate_evidence(monkeypatch, runs):
    result = runs["competing_on"]
    before = json.dumps(result.as_dict(), sort_keys=True)
    monkeypatch.setattr(demo, "run_suckle_attention_v1", lambda *a, **k: pytest.fail("renderer ran cognition"))
    original_id = result.requests()[0].outcome.claim.preview.pnm.pnm_id
    assert f"original={original_id}" in demo.render_suckle_attention_v1(result, detail=True)
    assert json.dumps(result.as_dict(), sort_keys=True) == before


def test_menu_runs_shared_pairs_and_retained_detail_only(monkeypatch, capsys, runs):
    answers, calls = iter(("6", "bad", "1", "6", "")), []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_suckle_attention_v1", run)
    demo.run_suckle_attention_menu_v1()
    assert calls == ["competing_on", "competing_off", "maintain_on", "maintain_off"]
    output = capsys.readouterr().out
    assert "No retained results" in output and "Unknown choice" in output and "original=" in output


def test_feeding_menu_routes_J_without_executing_old_reviews(monkeypatch):
    import nca8_feeding_demo as feeding
    answers, calls = iter(("26", "")), []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(feeding, "run_suckle_attention_menu_v1", lambda: calls.append("J"))
    monkeypatch.setattr(feeding, "run_suckle_outcome_menu_v1", lambda: pytest.fail("wrong I route"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["J"]


def test_CLI_JSON_uses_shared_result_from_any_directory_and_rejects_bad_flags(tmp_path, runs):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    result = subprocess.run([sys.executable, str(script), "--suckle-attention", "--case", "competing_on", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0] == json.loads(json.dumps(runs["competing_on"].as_dict()))
    for args in (("--suckle-attention", "--case", "bad"), ("--suckle-attention", "--suckle-outcomes")):
        failed = subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, capture_output=True,
                                text=True, encoding="utf-8", check=False)
        assert failed.returncode != 0


def test_CLI_reports_failed_review_nonzero(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    spec = importlib.util.spec_from_file_location("J_review_CLI", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Failure:
        review_status = "FAIL"
    monkeypatch.setattr(module, "run_suckle_attention_v1", lambda case: Failure())
    monkeypatch.setattr(module, "render_suckle_attention_v1", lambda *a, **k: "FAIL")
    assert module.main(["--suckle-attention", "--case", "competing_on"]) == 1


@pytest.mark.parametrize("capacity", [1, 4, 4096])
def test_diagnostic_capacity_does_not_change_decisions_or_outcomes(capacity, runs):
    result = demo.run_suckle_attention_v1(trace_capacity=capacity)
    control = runs["competing_on"]
    assert result.review_status == "PASS"
    assert result.outcomes() == control.outcomes() and result.interpretations() == control.interpretations()
    assert tuple(c.commitment for c in result.evidence.run.cycles) == tuple(c.commitment for c in control.evidence.run.cycles)
    assert result.evidence.run.local_steps == control.evidence.run.local_steps


@pytest.mark.parametrize("bad", [None, 1, "bad", True])
def test_unknown_case_is_not_repaired(bad):
    with pytest.raises(ValueError):
        demo.run_suckle_attention_v1(bad)


def test_host_registry_adds_J_services_not_IPs():
    import cca8_run
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert cca8_run.__version__ == "0.30.37" and len(cca8_run._cca8_component_rows()) == 110
    assert len(cca8_run.PRIMITIVES) == 8
    assert registry["nca8_suckle_attention"] == "nca8_suckle_attention"
    assert registry["nca8_suckle_attention_demo"] == "nca8_suckle_attention_demo"
