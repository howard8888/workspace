"""L-A shared direct-drive review, observer integrity, and unchanged menu/CLI authority."""
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_oral_extraction_demo as demo
from cca8_motor_contracts import MotorCommandV1, MotorStreamRefV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_oral_extraction_v1(case) for case in demo.ORAL_EXTRACTION_CASES_V1}


@pytest.mark.parametrize("case", demo.ORAL_EXTRACTION_CASES_V1)
def test_all_shared_physical_cases_are_truthful_and_finite(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", result.checks()
    assert 0 < len(result.commands) <= 80
    assert len(result.physical) == len(result.commands) + 1
    data = result.as_dict()
    assert data["scope"] == "P16_2C_L_A_physical_extraction_only"
    assert data["command_authority"] == "external_direct_drive_fixture"
    assert data["autonomous_suckle"] is False and data["BodyMap_extraction_target"] == "not_implemented"
    assert data["durable_learning_updates"] == 0 and data["nourishment"] == "not_modeled"
    assert data["B99"] == "open"
    assert json.loads(json.dumps(data, allow_nan=False)) == data
    assert result.initial_feedback.event_tick == 0
    assert result.initial_feedback.oral_extraction is None or result.initial_feedback.oral_extraction.interval_start_tick is None


@pytest.mark.parametrize("control", ["dry_surface", "displaced_supplier", "missing_milk", "missing_stroke", "dropout", "delayed"])
def test_controls_change_only_declared_conditions_not_nonextraction_physics(control, runs):
    nominal, variant = runs["wet_stroke"], runs[control]
    assert nominal.commands == variant.commands
    for a, b in zip(nominal.physical, variant.physical):
        assert (a.body, a.planar, a.oral, a.seal) == (b.body, b.planar, b.oral, b.seal)
        assert a.extraction.stroke == b.extraction.stroke
    if control in {"dry_surface", "displaced_supplier"}:
        assert variant.metrics()["physical_transfer_units"] == 0
        assert nominal.metrics()["physical_transfer_units"] == pytest.approx(0.8)
    else:
        assert nominal.physical == variant.physical


def test_seal_or_command_alone_cannot_produce_transfer(runs):
    for name in ("neutral_seal", "motor_blocked", "saturated"):
        result = runs[name]
        assert all(p.seal.sealed for p in result.physical)
        assert result.metrics()["physical_transfer_units"] == 0
    assert runs["wet_stroke"].commands == runs["motor_blocked"].commands == runs["saturated"].commands
    assert runs["wet_stroke"].metrics()["physical_transfer_units"] > 0


def test_repeated_motion_not_held_drive_or_call_count_explains_transfer(runs):
    held, repeated = runs["held_drive"], runs["repeated_strokes"]
    assert len(held.commands) == len(repeated.commands) == 30
    assert held.profile.physical == repeated.profile.physical
    assert held.metrics()["physical_transfer_units"] == pytest.approx(1)
    assert repeated.metrics()["physical_transfer_units"] == pytest.approx(2)
    assert all(p.extraction.interval_milk_units == 0 for p in repeated.physical[11:21])
    assert runs["supply_exhausted"].metrics()["physical_transfer_units"] == pytest.approx(0.25)
    assert runs["supply_exhausted"].physical[-1].extraction.remaining_supply_units == 0


def test_equal_time_resolution_controls_do_not_reward_more_calls(runs):
    results = [runs[name] for name in ("resolution_base", "resolution_half", "resolution_fine")]
    assert [len(r.commands) for r in results] == [12, 24, 60]
    for result in results:
        assert result.metrics()["duration_seconds"] == pytest.approx(0.6)
        assert result.metrics()["physical_transfer_units"] == pytest.approx(0.8)
        dt = result.profile.physical.dt_seconds
        switches = [c.issued_tick * dt for old, c in zip(result.commands, result.commands[1:])
                    if c.oral_extraction_drive != old.oral_extraction_drive]
        assert switches == pytest.approx([0.2, 0.4])


def test_loss_and_endpoint_acquisition_do_not_retroactively_credit_contact(runs):
    for name in ("support_loss", "contact_loss", "seal_loss"):
        r = runs[name]
        assert r.physical[2].extraction.transferred_milk_units == pytest.approx(0.2)
        assert r.metrics()["physical_transfer_units"] == pytest.approx(0.2)
    r = runs["closure_at_endpoint"]
    assert not r.physical[0].seal.sealed and r.physical[1].seal.sealed
    assert r.physical[1].extraction.interval_milk_units == 0
    assert r.physical[2].extraction.interval_milk_units == pytest.approx(0.1)


def test_curved_case_independently_has_contact_only_at_the_two_endpoints(runs):
    r = runs["curved_path"]
    assert r.physical[0].seal.sealed and r.physical[-1].seal.sealed
    disk = r.profile.extraction.supplying_surface
    assert math.hypot(r.profile.oral.initial_extension_metres - disk.position[0], disk.position[1]) > disk.radius + 1e-12
    assert r.metrics()["physical_transfer_units"] == 0
    assert r.physical[-1].extraction.stroke > r.physical[0].extraction.stroke


def test_missing_zero_and_delayed_evidence_are_not_private_physical_totals(runs):
    missing, zero, delayed, dropout = [runs[n] for n in ("missing_milk", "dry_surface", "delayed", "dropout")]
    assert all(f.oral_extraction.milk_transferred_units is None for f in missing.feedback())
    assert all(f.oral_extraction.milk_transferred_units == 0 for f in zero.feedback()[1:])
    assert missing.metrics()["physical_transfer_units"] == pytest.approx(0.8)
    assert missing.metrics()["known_interval_measurements"] == 0
    assert zero.metrics()["known_interval_measurements"] == 8
    assert delayed.metrics()["physical_transfer_units"] == pytest.approx(0.8)
    assert delayed.metrics()["measured_delivered_units"] == pytest.approx(0.5)
    assert delayed.pending_counts[-1] == 3 and delayed.feedback()[-1].event_tick == 5
    assert dropout.metrics()["measured_delivered_units"] == pytest.approx(0.6)
    assert [f.event_tick for f in dropout.feedback()] == [0, 1, 4, 5, 6, 7, 8]


def test_feature_off_is_the_original_v4_feedback_and_no_new_drive(runs):
    result = runs["feature_off"]
    assert all(c is None for c in result.commands)
    assert all(p.extraction is None for p in result.physical)
    assert all(f.oral_extraction is None for f in result.feedback())
    assert all("oral_extraction" not in f.as_dict() for f in result.feedback())


@pytest.mark.parametrize("capacity", [1, 2, 32, 256])
def test_diagnostic_capacity_and_rendering_change_no_world_or_rng(capacity, runs, monkeypatch):
    before = random.getstate()
    result = demo.run_oral_extraction_v1("repeated_strokes", diagnostic_capacity=capacity)
    base = runs["repeated_strokes"]
    assert result.physical == base.physical and result.commands == base.commands
    assert result.feedback() == base.feedback() and result.pending_counts == base.pending_counts
    assert len(result.diagnostics) <= capacity
    def forbidden(*args, **kwargs):
        raise AssertionError("read-only review attempted physical execution")
    monkeypatch.setattr(demo.MotorWorldV1, "step", forbidden)
    monkeypatch.setattr(demo.MotorWorldV1, "reset", forbidden)
    data = result.as_dict()
    for _ in range(3):
        assert result.review_status == "PASS"
        assert result.as_dict() == data
        assert "PHYSICAL" in demo.render_oral_extraction_v1(result, detail=True)
        assert "SENSED" in demo.render_oral_extraction_v1(result, detail=True)
    assert random.getstate() == before


@pytest.mark.parametrize("bad", [None, True, False, 0, -1, 257, "32", 1.5])
def test_invalid_capacity_fails_before_constructing_world(bad, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid request touched physical provider")
    monkeypatch.setattr(demo, "_world_from_profile", forbidden)
    with pytest.raises(ValueError):
        demo.run_oral_extraction_v1(diagnostic_capacity=bad)


@pytest.mark.parametrize("bad", [None, True, 0, "", "unknown", "nominal", "wet_stroke "])
def test_unknown_case_cannot_silently_select_another_experiment(bad):
    with pytest.raises(ValueError):
        demo.oral_extraction_review_profile_v1(bad)
    with pytest.raises(ValueError):
        demo.create_oral_extraction_world_v1(bad)


def test_factory_is_independent_and_reset_is_not_new_feeding():
    a, b = demo.create_oral_extraction_world_v1(), demo.create_oral_extraction_world_v1()
    initial = a.observe()
    a.step(MotorCommandV1(a.stream, 1, 0, oral_extraction_drive=1))
    assert b.tick == 0 and b.oral_extraction_body.transferred_milk_units == 0
    saved = a.oral_extraction_body
    for _ in range(5):
        assert a.observe().event_tick == 1 and a.oral_extraction_body == saved
    reset = a.reset()
    assert reset.stream.generation == initial.stream.generation + 1
    assert reset.oral_extraction.interval_start_tick is None and reset.oral_extraction.milk_transferred_units is None
    assert a.oral_extraction_body.transferred_milk_units == 0 and a.tick == 0


@pytest.mark.parametrize("mutation", ["quantity", "profile", "command", "missing_step", "missing_delivery", "duplicate", "timing",
                                    "sample", "stream", "wrong_interval", "private_quantity", "pending", "diagnostics"])
def test_corrupt_evidence_is_not_certified(mutation, runs):
    r = runs["wet_stroke"]
    if mutation == "quantity":
        ps = list(r.physical)
        ps[-1] = replace(ps[-1], extraction=replace(ps[-1].extraction, transferred_milk_units=0.5, remaining_supply_units=1.5))
        r = replace(r, physical=tuple(ps))
    elif mutation == "profile":
        r = replace(r, profile=replace(r.profile, expected_transfer_units=99))
    elif mutation == "command":
        r = replace(r, commands=(None,) + r.commands[1:])
    elif mutation == "missing_step":
        r = replace(r, physical=r.physical[:-1])
    elif mutation == "pending":
        r = replace(r, pending_counts=(1,) + r.pending_counts[1:])
    elif mutation == "diagnostics":
        r = replace(r, diagnostic_capacity=1)
    else:
        batches = list(r.deliveries)
        f = batches[0][0]
        if mutation == "missing_delivery":
            batches[0] = ()
        elif mutation == "duplicate":
            batches[0] = (f, f)
        elif mutation == "timing":
            batches[0] = (replace(f, available_tick=3),)
        elif mutation == "sample":
            batches[0] = (replace(f, sample_id=25),)
        elif mutation == "stream":
            batches[0] = (replace(f, stream=MotorStreamRefV1("foreign", 1)),)
        elif mutation == "wrong_interval":
            batches[0] = batches[1]
        elif mutation == "private_quantity":
            batches[0] = (replace(f, oral_extraction=replace(f.oral_extraction, milk_transferred_units=0.7)),)
        r = replace(r, deliveries=tuple(batches))
    assert r.review_status == "FAIL"


def load_cli():
    spec = importlib.util.spec_from_file_location("review_la_cli", ROOT / "scripts/review_nca8_feeding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_uses_same_json_renderer_and_reports_failed_check(capsys, monkeypatch, runs):
    cli = load_cli()
    assert cli.main(["--oral-extraction", "--case", "wet_stroke", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [runs["wet_stroke"].as_dict()]
    corrupt = replace(runs["wet_stroke"], physical=())
    monkeypatch.setattr(cli, "run_oral_extraction_v1", lambda case: corrupt)
    assert cli.main(["--oral-extraction", "--case", "wet_stroke"]) == 1
    assert "FAIL" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--oral-extraction", "--oral-seal"], ["--oral-extraction", "--suckle-learning"],
                                  ["--oral-extraction", "--case", "unknown"]])
def test_cli_refuses_ambiguous_or_unknown_routes(args):
    with pytest.raises(SystemExit) as error:
        load_cli().main(args)
    assert error.value.code == 2


def test_cli_runs_from_outside_repository_with_complete_json(tmp_path, runs):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"),
                             "--oral-extraction", "--case", "delayed", "--json"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=40, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [runs["delayed"].as_dict()]


def test_feeding_menu_preserves_J_K_and_delegates_new_28(monkeypatch):
    import nca8_feeding_demo as feeding
    choices = iter(("26", "27", "28", ""))
    calls = []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(feeding, "run_suckle_attention_menu_v1", lambda: calls.append("J26"))
    monkeypatch.setattr(feeding, "run_suckle_learning_menu_v1", lambda: calls.append("K27"))
    monkeypatch.setattr(feeding, "run_oral_extraction_menu_v1", lambda: calls.append("LA28"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["J26", "K27", "LA28"]


def test_extraction_menu_retained_read_and_invalid_choice_never_rerun(monkeypatch, capsys, runs):
    choices = iter(("6", "unknown", "1", "6", "6", ""))
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    def run(case):
        calls.append(case)
        return runs[case]
    monkeypatch.setattr(demo, "run_oral_extraction_v1", run)
    demo.run_oral_extraction_menu_v1()
    output = capsys.readouterr().out
    assert len(calls) == 6 and len(set(calls)) == 6
    assert "No retained results." in output and "Unknown choice" in output
    assert "SENSED" in output and "not Navigation/Suckle" in output


def test_registry_versions_and_preserved_task_factory():
    import cca8_run
    import cca8_motor_contracts
    import cca8_support_world
    from nca8_suckle_demo import create_suckle_trial_v1
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.45" and len(rows) == 123
    assert cca8_motor_contracts.__version__ == "0.7.0"
    assert cca8_support_world.__version__ == "0.8.0"
    assert ("nca8_oral_extraction_demo", "nca8_oral_extraction_demo") in cca8_run._CCA8_COMPONENT_REGISTRY
    assert len(cca8_run.PRIMITIVES) == 8
    trial = create_suckle_trial_v1(outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True)
    assert trial._world.oral_extraction_body is None  # Test-only inspection; no new provider is wired to the IP.
    assert trial.latest_feedback.oral_extraction is None
