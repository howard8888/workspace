"""Regression checks for the L-F follow-up lint/type-narrowing maintenance patch.

Use actual extraction publications and existing review paths. Corrupted observer
records must fail checks rather than pass vacuously or crash on optional fields.
The manual API smoke script is exercised with a fake SDK and no network request.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

import nca8_feeding_demo as feeding
import nca8_suckle_extraction_attention_demo as attention_demo
import nca8_suckle_extraction_outcomes as outcomes_module
import nca8_suckle_extraction_outcomes_demo as outcome_demo
from nca8_suckle import SuckleIPV1
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1

ROOT = Path(__file__).resolve().parents[1]
OUTCOME_CASES = ("nominal", "dry", "depleted", "milk_sensor_off", "dropout", "cancelled", "comparison_off")


@pytest.fixture(scope="module")
def outcome_runs():
    """Keep genuine publications available before tests isolate the validator."""
    return {case: outcome_demo.run_suckle_extraction_outcome_v1(case) for case in OUTCOME_CASES}


@pytest.fixture(scope="module")
def attention_run():
    """Obtain one genuine selected-source competition and performed interpretation."""
    return attention_demo.run_extraction_attention_v1("competing_source")


def _load_script(name):
    """Import a developer entry without executing its guarded main function."""
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location("static_fix_" + path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case", OUTCOME_CASES)
def test_canonical_validation_is_read_only_and_needs_no_temporary_publisher(case, outcome_runs, monkeypatch):
    result = outcome_runs[case]
    outcome, = result.outcomes()
    before = outcome.as_dict()

    def forbidden(*args, **kwargs):
        raise AssertionError("validation constructed a mutable runtime")

    monkeypatch.setattr(outcomes_module.SuckleExtractionOutcomeRuntimeV1, "__init__", forbidden)
    for _ in range(3):
        outcomes_module.validate_suckle_extraction_outcome_v1(
            outcome, stream=outcome.claim.application.projection.basis.stream, cutoff_tick=outcome.evaluated_tick,
        )
    assert outcome.as_dict() == before
    assert result.review_status == "PASS"


def test_pure_validation_still_rejects_forged_scores(outcome_runs):
    outcome, = outcome_runs["nominal"].outcomes()
    before = outcome.as_dict()
    changed = replace(outcome, relations=tuple(
        (name, "mismatch" if name == "sealed_contact" else value) for name, value in outcome.relations
    ))
    with pytest.raises(ValueError, match="canonical evidence"):
        outcomes_module.validate_suckle_extraction_outcome_v1(
            changed, stream=outcome.claim.application.projection.basis.stream, cutoff_tick=outcome.evaluated_tick,
        )
    assert outcome.as_dict() == before


@pytest.mark.parametrize("missing", ["interpretation", "wnm", "feeding_source"])
def test_missing_grant_evidence_fails_review_instead_of_disappearing(missing, attention_run):
    original = next(c for c in attention_run.run.cycles
                    if c.extraction_attention is not None and c.extraction_attention.allocation.kind == "interpretation")
    if missing == "interpretation":
        frame = original.extraction_attention
        changed = replace(original, extraction_attention=replace(frame, allocation=replace(frame.allocation, interpretation=None)))
    elif missing == "wnm":
        calculation = original.calculation
        changed = replace(original, calculation=replace(calculation, navigation=replace(calculation.navigation, wnm=None)))
    else:
        changed = replace(original, feeding_detail_source=None)
    run = replace(attention_run.run, cycles=tuple(changed if c is original else c for c in attention_run.run.cycles))
    corrupted = replace(attention_run, run=run)
    assert dict(corrupted.checks())["grant_matches_question_and_current_WNM"] is False
    assert corrupted.review_status == "FAIL"
    assert attention_run.review_status == "PASS"


def test_missing_control_source_fails_competition_check(attention_run):
    request, = attention_run.requests()
    original = next(c for c in attention_run.control.cycles if c.calculation.cutoff_tick == request.admitted_tick)
    changed = replace(original, feeding_detail_source=None)
    control = replace(attention_run.control, cycles=tuple(changed if c is original else c for c in attention_run.control.cycles))
    corrupted = replace(attention_run, control=control)
    assert dict(corrupted.checks())["real_Attention_consequence"] is False
    assert corrupted.review_status == "FAIL"


@pytest.mark.parametrize("invalid_sum", ["0.2", None, True, float("nan"), object()])
def test_quantity_check_does_not_coerce_untyped_or_invalid_evidence(invalid_sum, outcome_runs, monkeypatch):
    original = outcomes_module.SuckleExtractionOutcomeV1.milk_evidence

    def altered(self):
        return {**original(self), "known_interval_sum": invalid_sum}

    monkeypatch.setattr(outcomes_module.SuckleExtractionOutcomeV1, "milk_evidence", altered)
    result = outcome_runs["nominal"]
    assert dict(result.checks())["declared_known_quantity"] is False
    assert result.review_status == "FAIL"


@pytest.mark.parametrize("registered", [False, True])
def test_snapshot_reads_the_optional_pending_claim_once(registered, monkeypatch):
    trial = create_suckle_extraction_trial_v1(outcome_demo.suckle_extraction_outcome_profile_v1())
    if registered:
        trial.focal_step()
    owner = trial.core.extraction_outcomes
    assert owner is not None
    original = owner.pending
    expected = original()
    calls = []

    def counted():
        calls.append(True)
        return original()

    monkeypatch.setattr(owner, "pending", counted)
    before_tick = trial.tick
    snapshot = trial.snapshot()
    assert calls == [True]
    assert snapshot["extraction_pending_claim"] == (expected.as_dict() if expected is not None else None)
    assert (expected is not None) == registered
    assert trial.tick == before_tick


def test_missing_optional_assessment_does_not_fabricate_an_application(monkeypatch):
    trial = create_suckle_extraction_trial_v1(attention_demo.extraction_attention_profile_v1("no_need"))
    monkeypatch.setattr(SuckleIPV1, "extraction_assessment", lambda self: None)
    cycle = trial.focal_step()
    assert cycle.calculation.navigation.application is None
    assert cycle.extraction_attention is not None and not cycle.extraction_attention.created
    assert cycle.extraction_correspondence is not None and cycle.extraction_correspondence.registration is None


def test_missing_review_source_raises_named_integrity_error(monkeypatch):
    original = attention_demo.collect_seek_nipple_evidence_v1

    def without_source(trial, profile):
        run = original(trial, profile)
        trial.core.feeding_detail = None
        return run

    monkeypatch.setattr(attention_demo, "collect_seek_nipple_evidence_v1", without_source)
    with pytest.raises(RuntimeError, match="feeding-detail source"):
        attention_demo.run_extraction_attention_v1("matched")


def test_menu_29_and_28_dispatch_once_then_return(monkeypatch, capsys):
    choices = iter(["29", "28", ""])
    calls = []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(feeding, "run_oral_extraction_control_menu_v1", lambda: calls.append("29"))
    monkeypatch.setattr(feeding, "run_oral_extraction_menu_v1", lambda: calls.append("28"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["29", "28"]
    assert "Choose a displayed number" not in capsys.readouterr().out


def test_retained_scalar_body_target_script_passes(capsys):
    module = _load_script("review_nca8_body_targets.py")
    assert module.main() == 0
    assert "BODYMAP TARGET CHECKS PASSED" in capsys.readouterr().out


def test_manual_smoke_script_import_and_missing_key_path_make_no_request(monkeypatch, capsys):
    calls = []
    fake_sdk = ModuleType("openai")

    def forbidden_client():
        calls.append(True)
        raise AssertionError("smoke script constructed a client without an explicit keyed invocation")

    fake_sdk.OpenAI = forbidden_client
    monkeypatch.setitem(sys.modules, "openai", fake_sdk)
    monkeypatch.setenv("OPENAI_API_KEY", "test-import-must-not-call")
    module = _load_script("openai_smoke_test.py")
    assert not calls
    monkeypatch.delenv("OPENAI_API_KEY")
    assert module.main() is None
    assert "OPENAI_API_KEY is missing" in capsys.readouterr().out
    assert not calls
    assert module.__doc__ and module.main.__doc__
    assert (ROOT / "scripts/openai_smoke_test.py").read_bytes().endswith(b"\n")
