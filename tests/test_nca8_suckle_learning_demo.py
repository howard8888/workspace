"""K's shared observer, neutral controls, real menu/CLI routes and truthful failure.

Simultaneous-question and late-J fixtures remain in the unchanged Stage C tests.
These tests exercise the shipping physical reviews and keep diagnostics separate
from mechanism authority. No existing expectation is weakened to admit K.
"""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_suckle_learning_demo as demo
from nca8_suckle_demo import create_suckle_trial_v1
from nca8_suckle_attention_demo import run_suckle_attention_v1


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_learning_v1(case) for case in demo.SUCKLE_LEARNING_CASES_V1}


@pytest.mark.parametrize("case", demo.SUCKLE_LEARNING_CASES_V1)
def test_complete_fixed_reviews_and_no_behavioral_learning_gain(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", [name for name, passed in result.checks() if not passed]
    data = result.as_dict()
    assert data["scope"] == "P16_2C_K_suckle_participation" and data["maturity"] == "eligibility_only"
    assert data["durable_learning_updates"] == 0 and data["B99"] == "open"
    assert data["observed_behavior_sha256"] == data["control_behavior_sha256"]
    assert data["metrics"]["milk"] == "not_supplied" and data["metrics"]["full_suckle_complete"] is False
    assert data["evidence"]["cycles"] and data["control_evidence"]["cycles"]
    assert json.loads(json.dumps(data, allow_nan=False))["checks"] == dict(result.checks())


@pytest.mark.parametrize("pair", [("nominal_on", "nominal_off"), ("competing_on", "competing_off"), ("stand_follow", "stand_follow_off")])
def test_hook_pairs_share_physics_sources_J_and_schedule(pair, runs):
    on, off = [runs[name] for name in pair]
    a, b = on.evidence, off.evidence
    assert a.profile.run == replace(b.profile.run, case=a.profile.run.case)
    assert a.profile.suckle == replace(b.profile.suckle, learning_hook_enabled=True)
    assert a.profile.seal == b.profile.seal and a.profile.capability == b.profile.capability
    assert a.run.local_steps == b.run.local_steps and a.run.physical_samples == b.run.physical_samples
    assert demo.suckle_learning_behavior_signature_v1(a) == demo.suckle_learning_behavior_signature_v1(b)
    assert on.reports() and not off.reports()


def test_nonfocal_matched_evidence_reaches_original_Suckle_participant(runs):
    result = runs["nonfocal"]
    cycle = next(c for c in result.evidence.run.cycles if c.calculation.cutoff_tick == 12)
    assert cycle.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "visual_scene"
    assert any(d.status == "accepted_no_update" for d in cycle.suckle_learning_report.dispositions)
    assert cycle.suckle_learning_report.recipient_id.endswith(":suckle_consequence")


def test_attention_off_and_fast_cadence_expire_without_reviving_participation(runs):
    assert runs["attention_off"].metrics()["accepted_ticks"] == []
    assert {"pending_interpretation", "eligibility_expired"} <= runs["attention_off"].metrics()["disposition_counts"].keys()
    assert {"eligibility_expired", "rejected_expired_eligibility"} <= runs["cadence_1"].metrics()["disposition_counts"].keys()
    assert runs["cadence_1"].metrics()["accepted_ticks"] == []
    assert runs["cadence_8"].metrics()["accepted_ticks"] == [16]


def test_real_H_factory_K_flag_is_opt_in_and_J_default_is_unchanged():
    old = create_suckle_trial_v1(outcomes_enabled=True)
    assert old.core.feeding_detail.suckle_learning_hook is None
    assert old.core.feeding_detail.suckle_outcome_attention is None
    new = create_suckle_trial_v1(outcomes_enabled=True, learning_hook_enabled=True)
    assert new.core.feeding_detail.suckle_learning_hook is not None
    assert new.core.feeding_detail.suckle_outcome_attention is None
    first = new.focal_step()
    assert first.suckle_learning_report.new_participation.claim is first.suckle_correspondence.registration
    assert first.suckle_learning_report.new_participation.outcome is None


@pytest.mark.parametrize("bad", [None, True, 0, -1, 33, 1.5, "4"])
def test_factory_preserves_original_diagnostic_capacity_validation(bad):
    with pytest.raises((TypeError, ValueError)):
        demo.create_suckle_learning_trial_v1(diagnostic_capacity=bad)


@pytest.mark.parametrize("trace,history", [(1, 1), (4, 2), (4096, 32)])
def test_diagnostic_capacity_changes_no_mechanism_or_random_state(trace, history, runs):
    state = random.getstate()
    actual = demo.run_suckle_learning_v1("competing_on", trace_capacity=trace, diagnostic_capacity=history)
    control = runs["competing_on"]
    assert actual.review_status == "PASS"
    assert actual.evidence.run.local_steps == control.evidence.run.local_steps
    assert actual.evidence.run.physical_samples == control.evidence.run.physical_samples
    assert actual.reports() == control.reports()
    assert len(actual.retained_dispositions) <= history
    if trace == 4096:
        assert (dict(actual.evidence.run.peak_counts)["focal_trace"] - dict(actual.control.run.peak_counts)["focal_trace"]
                == len(actual.reports()))
    assert random.getstate() == state


@pytest.mark.parametrize("mutation", ["durable", "schedule", "bounds", "missing_F", "copied_claim", "copied_outcome",
                                     "copied_J", "late_acceptance", "relations", "double_allocation", "control_profile", "control_behavior"])
def test_corrupt_observer_evidence_is_not_certified(mutation, runs):
    result = runs["competing_on"]
    raw = result.evidence.run
    cycles = list(raw.cycles)
    i = next(i for i, c in enumerate(cycles) if c.suckle_learning_report and c.suckle_learning_report.dispositions)
    c = cycles[i]
    r = c.suckle_learning_report
    if mutation == "durable":
        raw = replace(raw, durable_after="unapproved learned change")
    elif mutation == "schedule":
        raw = replace(raw, local_steps=raw.local_steps[:-1])
    elif mutation == "bounds":
        raw = replace(raw, peak_counts=raw.peak_counts + (("unknown_owner", 1),))
    elif mutation == "missing_F":
        cycles[i] = replace(c, suckle_learning_report=None)
    elif mutation == "copied_claim":
        first = cycles[0]
        p = first.suckle_learning_report.new_participation
        cycles[0] = replace(first, suckle_learning_report=replace(first.suckle_learning_report,
                            new_participation=replace(p, claim=replace(p.claim))))
    elif mutation in {"copied_outcome", "copied_J", "late_acceptance", "relations"}:
        ds = list(r.dispositions)
        k = next(k for k, d in enumerate(ds) if d.status == "accepted_no_update")
        d = ds[k]
        if mutation == "copied_outcome":
            ds[k] = replace(d, outcome=replace(d.outcome))
        elif mutation == "copied_J":
            ds[k] = replace(d, interpretation=replace(d.interpretation))
        elif mutation == "late_acceptance":
            ds[k] = replace(d, cycle_id=5)
        else:
            ds[k] = replace(d, accepted_relations=(("fabricated", "matched"),))
        cycles[i] = replace(c, suckle_learning_report=replace(r, dispositions=tuple(ds)))
    elif mutation == "double_allocation":
        # Deliberately corrupt only a completed observer allocation record.
        cycles[i] = replace(c, calculation=replace(c.calculation, seeking_outcome_allocation=c.calculation.suckle_outcome_allocation))
    elif mutation == "control_profile":
        result = replace(result, control=replace(result.control, profile=result.evidence.profile))
    elif mutation == "control_behavior":
        result = replace(result, control=replace(result.control, run=replace(result.control.run, local_steps=())))
    if mutation not in {"durable", "schedule", "bounds"}:
        raw = replace(raw, cycles=tuple(cycles))
    assert replace(result, evidence=replace(result.evidence, run=raw)).review_status == "FAIL"


def test_retained_detail_and_exports_do_not_reexecute(monkeypatch, runs):
    result = runs["competing_on"]
    before = json.dumps(result.as_dict(), sort_keys=True)
    monkeypatch.setattr(demo, "run_suckle_learning_v1", lambda *a, **k: pytest.fail("renderer ran cognition"))
    text = demo.render_suckle_learning_v1(result, detail=True)
    assert "recipient=feeding_detail_association:feeding_detail:suckle_consequence" in text
    assert "expires_before_cycle=5" in text and "pending_interpretation" in text and "accepted_no_update" in text
    assert json.dumps(result.as_dict(), sort_keys=True) == before


def test_menu_uses_shared_runs_and_retained_read_only_detail(monkeypatch, capsys, runs):
    answers, calls = iter(("6", "bad", "1", "6", "")), []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_suckle_learning_v1", run)
    demo.run_suckle_learning_menu_v1()
    assert calls == ["nominal_on", "nominal_off", "competing_on", "competing_off"]
    output = capsys.readouterr().out
    assert "No retained results" in output and "Unknown choice" in output and "expires_before_cycle=" in output


def test_feeding_menu_preserves_J26_and_adds_K27(monkeypatch):
    import nca8_feeding_demo as feeding
    answers, calls = iter(("26", "27", "")), []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(feeding, "run_suckle_attention_menu_v1", lambda: calls.append("J"))
    monkeypatch.setattr(feeding, "run_suckle_learning_menu_v1", lambda: calls.append("K"))
    monkeypatch.setattr(feeding, "run_suckle_outcome_menu_v1", lambda: pytest.fail("wrong route"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["J", "K"]


def test_CLI_json_from_external_directory_equals_shared_result(tmp_path, runs):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    result = subprocess.run([sys.executable, str(script), "--suckle-learning", "--case", "competing_on", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [json.loads(json.dumps(runs["competing_on"].as_dict()))]
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("args", [("--suckle-learning", "--case", "bad"), ("--suckle-learning", "--suckle-attention"),
                                  ("--suckle-learning", "--seek-learning")])
def test_CLI_rejects_invalid_or_ambiguous_selection(args, tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    result = subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, capture_output=True,
                            text=True, encoding="utf-8", check=False)
    assert result.returncode == 2


def test_CLI_returns_failure_when_a_review_check_fails(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    spec = importlib.util.spec_from_file_location("K_review_CLI", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Failure:
        review_status = "FAIL"
    monkeypatch.setattr(module, "run_suckle_learning_v1", lambda case: Failure())
    monkeypatch.setattr(module, "render_suckle_learning_v1", lambda *a, **k: "FAIL")
    assert module.main(["--suckle-learning", "--case", "nominal_on"]) == 1


@pytest.mark.parametrize("bad", [None, 1, "bad", True])
def test_unknown_case_does_not_default_to_success(bad):
    with pytest.raises(ValueError):
        demo.run_suckle_learning_v1(bad)


def test_host_components_are_services_not_additional_IPs():
    import cca8_run
    rows = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert cca8_run.__version__ == "0.30.45" and len(cca8_run._cca8_component_rows()) == 123
    assert len(cca8_run.PRIMITIVES) == 8
    assert rows["nca8_suckle_learning"] == "nca8_suckle_learning"
    assert rows["nca8_suckle_learning_demo"] == "nca8_suckle_learning_demo"


def test_existing_J_review_stays_K_disabled_and_valid():
    result = run_suckle_attention_v1("competing_on")
    assert result.review_status == "PASS"
    assert all(c.suckle_learning_report is None for c in result.evidence.run.cycles)
