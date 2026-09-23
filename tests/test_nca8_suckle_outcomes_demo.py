"""I live causal controls, exact accepted-H preservation and menu/read-only evidence."""

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

import nca8_suckle_outcomes_demo as demo
from nca8_suckle_demo import create_suckle_trial_v1, run_suckle_v1, SUCKLE_LATCH_CASES_V1


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_outcome_v1(case) for case in demo.SUCKLE_OUTCOME_CASES_V1}


@pytest.mark.parametrize("case", demo.SUCKLE_OUTCOME_CASES_V1)
def test_complete_live_cases_pass_and_have_no_new_learning_or_feeding_claim(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", [(key, value) for key, value in result.checks() if not value]
    assert len(result.checks()) == 25
    exported = result.as_dict()
    assert exported["B99"] == "open" and exported["durable_before"] == exported["durable_after"]
    assert exported["profile"]["suckle"]["task_pnm_correspondence"] == "suckle_correspondence_v1"
    assert exported["control_behavior_sha256"] == exported["observed_behavior_sha256"]
    assert exported["metrics"]["milk"] == "not_supplied" and exported["metrics"]["full_suckle_complete"] is False


def _portable_H_export_value(value):
    """Return a cross-platform canonical form for accepted-H export hashing.

    CPython delegates trigonometric functions to the platform math library.  The
    retained stand/follow controls therefore differ by sub-femtoscale floating
    noise across Linux and Windows even when every represented relation, event,
    command and discrete outcome is identical.  Quantizing floats to 12 decimal
    places removes that non-semantic libm variation while preserving the full
    exported structure and substantially more precision than any H decision
    threshold uses.  Integers, booleans, text, collection order and identities
    are left unchanged.
    """
    if isinstance(value, float):
        canonical = round(value, 12)
        return 0.0 if canonical == 0.0 else canonical
    if isinstance(value, list):
        return [_portable_H_export_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_portable_H_export_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _portable_H_export_value(item) for key, item in value.items()}
    return value


def _portable_H_export_sha256(exported):
    """Hash the complete accepted-H export after bounded float canonicalization."""
    canonical = _portable_H_export_value(exported)
    payload = json.dumps(canonical, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("case", SUCKLE_LATCH_CASES_V1)
def test_default_H_full_export_matches_hash_captured_from_accepted_commit_before_I_changes(case):
    baseline = json.loads((Path(__file__).parent / "fixtures/nca8_suckle_h_baseline.json").read_text(encoding="utf-8"))
    result = run_suckle_v1(case)
    actual = _portable_H_export_sha256(result.as_dict())
    assert baseline["baseline_commit"] == "6112280fba17146ff7a9600547bbfe4431d770bd"
    assert baseline["encoding"] == "SHA256(canonical-H-export-v2: floats rounded to 12 decimal places; compact sorted UTF-8 JSON)"
    assert actual == baseline["cases"][case]


def test_nonsealable_surface_changes_correspondence_not_commands_or_closure(runs):
    nominal, adverse = runs["nominal"], runs["nonsealable"]
    assert tuple(x.command for x in nominal.evidence.run.local_steps) == tuple(x.command for x in adverse.evidence.run.local_steps)
    assert tuple(x.seal.closure for x in nominal.evidence.run.physical_samples) == tuple(x.seal.closure for x in adverse.evidence.run.physical_samples)
    assert nominal.claims()[0].preview == adverse.claims()[0].preview
    assert nominal.outcomes()[0].status == "matched" and adverse.outcomes()[0].status == "mismatch"
    assert dict(adverse.outcomes()[0].relations) == {"mouth_position": "matched", "detail_anchor": "matched", "closure": "matched", "seal": "mismatch"}
    assert adverse.evidence.metrics()["latch_established_tick"] is None


def test_missing_seal_sensor_preserves_physics_but_outcome_is_unknown(runs):
    nominal, missing = runs["nominal"], runs["missing_seal"]
    assert nominal.evidence.run.physical_samples == missing.evidence.run.physical_samples
    assert missing.evidence.metrics()["final_physical_seal"] is True
    outcome = missing.outcomes()[0]
    assert outcome.status == "unknown" and outcome.evidence.feedback.oral_seal.sealed is None
    assert dict(outcome.relations)["closure"] == "matched" and dict(outcome.relations)["seal"] == "unknown"


@pytest.mark.parametrize("intact,disabled", [("nominal", "comparison_off"), ("nonsealable", "nonsealable_comparison_off")])
def test_comparison_off_retains_claim_exposure_evidence_and_whole_H_behavior(intact, disabled, runs):
    on, off = runs[intact], runs[disabled]
    left, right = on.outcomes()[0], off.outcomes()[0]
    assert on.control_signature == off.control_signature
    assert on.claims() == off.claims() and left.evidence == right.evidence and left.command_intervals == right.command_intervals
    assert right.status == "comparison_disabled" and right.relations == right.residuals == ()
    assert right.installed


def test_narrowed_early_claim_is_not_rewritten_by_later_full_latch(runs):
    result = runs["narrowed"]
    first, later = result.outcomes()
    assert first.status == "partly_matched" and later.status == "matched"
    assert first.claim.preview.predicted_closure == 0.6 and first.claim.targets[0].target.endpoint == pytest.approx(0.3)
    assert first.evidence.feedback.oral_seal.closure == pytest.approx(0.3)
    assert result.evidence.metrics()["latch_established_tick"] is not None
    assert first.claim.preview.pnm.pnm_id != later.claim.preview.pnm.pnm_id


def test_later_loss_in_current_source_does_not_erase_original_event_match(runs):
    result = runs["seal_loss_after"]
    outcome = result.outcomes()[0]
    assert outcome.status == "matched" and outcome.evidence.feedback.event_tick == 8
    assert outcome.evidence.feedback.oral_seal.sealed is True
    later = next(c for c in result.evidence.run.cycles if c.calculation.cutoff_tick == 16)
    assert later.feeding_detail_source.oral_sealed is False
    assert any(p.tick > 12 and p.seal.sealed is False for p in result.evidence.run.physical_samples)
    assert outcome.claim.preview.basis is not result.evidence.run.cycles[-1].feeding_detail_source


@pytest.mark.parametrize("case", ["nominal", "cadence_1", "cadence_8"])
def test_same_event_claim_survives_different_focal_read_times(case, runs):
    outcome = runs[case].outcomes()[0]
    assert outcome.claim.due_tick == outcome.evidence.feedback.event_tick == 8
    assert outcome.evidence.feedback.available_tick == 9 and outcome.evaluated_tick >= 9
    assert outcome.command_intervals == 6 and outcome.status == "matched"


def test_existing_pnm_registration_switch_is_not_a_behavioral_dependency(runs):
    result = runs["pnm_registration_off"]
    assert result.evidence.run.registered_suckle_pnm_cycles == () and result.outcomes()[0].status == "matched"
    assert result.claims()[0].preview.pnm is not None
    assert result.evidence.metrics()["latch_established_tick"] == runs["nominal"].evidence.metrics()["latch_established_tick"]


@pytest.mark.parametrize("case", ["seek_then_latch", "stand_follow"])
def test_continuous_runs_keep_independent_seeking_following_and_suckle_claims(case, runs):
    result = runs[case]
    assert result.outcomes()[0].claim.request.origin.application_id.startswith("suckle_application:")
    assert result.outcomes()[0].status == "matched"
    assert result.evidence.metrics()["first_suckle_tick"] < result.evidence.metrics()["first_geometric_reach_tick"]


def test_fault_after_possible_effect_is_unresolved_and_cannot_replay(monkeypatch):
    trial = create_suckle_trial_v1(outcomes_enabled=True)
    trial.focal_step()
    original = trial._world.step
    def fail_after_effect(command=None):
        original(command)
        raise RuntimeError("injected post-effect failure")
    monkeypatch.setattr(trial._world, "step", fail_after_effect)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1 and trial.observer_oral_seal_body.closure == pytest.approx(0.1)
    owner = trial.core.suckle_outcomes
    assert owner.history()[0].status == "unresolved_stopped" and owner.pending() == ()
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1


def test_generation_reset_replaces_owner_queue_and_permission_without_erasing_old_diagnostic():
    trial = create_suckle_trial_v1(outcomes_enabled=True)
    first = trial.focal_step()
    owner = trial.core.suckle_outcomes
    trial.advance_lower()
    trial.reset()
    assert trial.tick == 0 and trial._suckle_intervals == [] and trial.core.suckle_outcomes is not owner
    assert owner.history()[0].status == "unresolved_stopped" and not owner.pending()
    current = trial.focal_step()
    assert current.feeding_detail_source.stream.generation == first.feeding_detail_source.stream.generation + 1
    with pytest.raises(ValueError):
        trial.core.suckle_outcomes.installed(first.suckle_correspondence.registration, at_tick=0)


def test_suckle_ingress_overflow_stops_before_another_physical_effect():
    trial = create_suckle_trial_v1(outcomes_enabled=True)
    trial.focal_step()
    for _ in range(16):
        trial.advance_lower()
    assert len(trial._suckle_intervals) == 16
    before = trial.observer_oral_seal_body
    with pytest.raises(OverflowError):
        trial.advance_lower()
    assert trial.tick == 16 and trial.observer_oral_seal_body == before and trial.stopped


def test_renderer_and_detached_exports_do_not_change_retained_results(runs):
    result = runs["narrowed"]
    before = json.dumps(result.as_dict(), sort_keys=True, allow_nan=False)
    for _ in range(3):
        assert "SUCKLE CORRESPONDENCE REVIEW: PASS" in demo.render_suckle_outcome_v1(result, detail=True)
        exported = result.as_dict()
        exported["original_claims"].clear()
        exported["cycles"].clear()
    assert json.dumps(result.as_dict(), sort_keys=True, allow_nan=False) == before


@pytest.mark.parametrize("mutation", ["control", "commands", "schedule", "durable", "counts"])
def test_review_detects_tampered_evidence_instead_of_assuming_success(mutation, runs):
    result = runs["nominal"]
    if mutation == "control":
        changed = replace(result, control_signature="not_the_control")
    else:
        raw = result.evidence.run
        if mutation == "commands":
            raw = replace(raw, local_steps=tuple(replace(item, command=None) for item in raw.local_steps))
        elif mutation == "schedule":
            raw = replace(raw, local_steps=raw.local_steps[:-1])
        elif mutation == "durable":
            raw = replace(raw, durable_after="unexpected_update")
        else:
            raw = replace(raw, peak_counts=raw.peak_counts + (("unbounded_owner", 1000),))
        changed = replace(result, evidence=replace(result.evidence, run=raw))
    assert changed.review_status == "FAIL"


def test_menu_reuses_experiments_and_inspects_without_rerunning(monkeypatch, capsys, runs):
    answers, calls = iter(("6", "bad", "1", "6", "")), []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_suckle_outcome_v1", run)
    demo.run_suckle_outcome_menu_v1()
    assert calls == ["nominal", "nonsealable", "missing_seal", "comparison_off", "nonsealable_comparison_off"]
    output = capsys.readouterr().out
    assert "No retained results" in output and "Unknown choice" in output and "original endpoint=" in output


def test_feeding_menu_routes_I_without_old_review_execution(monkeypatch):
    import nca8_feeding_demo as feeding
    answers, calls = iter(("25", "")), []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(feeding, "run_suckle_outcome_menu_v1", lambda: calls.append("I"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["I"]


def test_cli_exports_real_evidence_from_any_directory_and_rejects_wrong_selector(tmp_path, runs):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    completed = subprocess.run([sys.executable, str(script), "--suckle-outcomes", "--case", "nominal", "--json"],
                               cwd=tmp_path, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)[0] == json.loads(json.dumps(runs["nominal"].as_dict()))
    for args in (("--suckle-outcomes", "--case", "bad"), ("--suckle-outcomes", "--suckle")):
        failed = subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, capture_output=True, text=True, check=False)
        assert failed.returncode != 0


def test_cli_failed_check_returns_nonzero(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    spec = importlib.util.spec_from_file_location("suckle_outcome_review_cli_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Failure:
        review_status = "FAIL"
    monkeypatch.setattr(module, "run_suckle_outcome_v1", lambda case: Failure())
    monkeypatch.setattr(module, "render_suckle_outcome_v1", lambda *args, **kwargs: "FAIL")
    assert module.main(["--suckle-outcomes", "--case", "nominal"]) == 1


@pytest.mark.parametrize("bad", [None, 1, "bad"])
def test_unknown_case_not_repaired(bad):
    with pytest.raises(ValueError):
        demo.run_suckle_outcome_v1(bad)


def test_registry_keeps_eight_host_primitives_and_adds_only_two_I_components():
    import cca8_run
    rows = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert len(cca8_run._cca8_component_rows()) == 110 and len(cca8_run.PRIMITIVES) == 8
    assert rows["nca8_suckle_outcomes"] == "nca8_suckle_outcomes"
    assert rows["nca8_suckle_outcomes_demo"] == "nca8_suckle_outcomes_demo"


@pytest.mark.parametrize("capacity", [1, 4, 4096])
def test_diagnostic_capacity_does_not_change_scoring_or_behavior(capacity, runs):
    result = demo.run_suckle_outcome_v1("nominal", trace_capacity=capacity)
    assert result.review_status == "PASS"
    assert result.outcomes() == runs["nominal"].outcomes()
    assert result.control_signature == runs["nominal"].control_signature
    assert dict(result.evidence.run.peak_counts)["focal_trace"] <= capacity
    if capacity == 4096:
        control = run_suckle_v1("nominal", trace_capacity=capacity)
        difference = dict(result.evidence.run.peak_counts)["focal_trace"] - dict(control.run.peak_counts)["focal_trace"]
        assert difference == len(result.claims()) + len(result.outcomes())
