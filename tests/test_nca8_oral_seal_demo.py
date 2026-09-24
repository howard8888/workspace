"""Measured positive/adverse closure contrasts and read-only menu/CLI integration."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

import nca8_oral_seal_demo as demo
from nca8_sensorimotor_contracts import LocalTargetDispositionV1


@pytest.mark.parametrize("case", demo.ORAL_SEAL_CASES_V1)
def test_all_declared_cases_have_real_complete_evidence(case):
    result = demo.run_oral_seal_v1(case)
    assert result.review_status == "PASS", [(name, value) for name, value in result.checks() if not value]
    assert len(result.checks()) == 19
    assert result.durable_before == result.durable_after
    assert result.metrics()["navigation_selections"] == 0 and not result.metrics()["latch_task_implemented"]
    assert result.metrics()["milk_evidence"] == "not_supplied"
    assert len(result.physical) == len(result.sources) == 13


def test_nominal_timeline_separates_touch_seal_delivery_and_target_completion():
    result = demo.run_oral_seal_v1()
    metrics = result.metrics()
    assert result.physical[0].oral.contact and not result.physical[0].seal.sealed
    assert metrics["physical_seal_first_tick"] == 5 and metrics["compatible_seal_first_cutoff"] == 6
    report = result.reports[0]
    assert report.disposition is LocalTargetDispositionV1.ACHIEVED and report.reported_tick == 7
    assert report.feedback.event_tick == 6 and metrics["final_closure"] == 0.6
    assert metrics["command_count"] == 6


def test_nonsealable_surface_preserves_every_command_and_closure_sample():
    nominal, nonsealable = demo.run_oral_seal_v1(), demo.run_oral_seal_v1("nonsealable")
    assert nominal.commands == nonsealable.commands
    assert tuple(item.seal.closure for item in nominal.physical) == tuple(item.seal.closure for item in nonsealable.physical)
    assert tuple(item.oral for item in nominal.physical) == tuple(item.oral for item in nonsealable.physical)
    assert nominal.metrics()["physical_seal_final"] and not nonsealable.metrics()["physical_seal_final"]
    assert nonsealable.metrics()["local_coordinate_achieved"]


def test_seal_sensor_loss_preserves_complete_physics_and_commands_but_not_knowledge():
    nominal, missing = demo.run_oral_seal_v1(), demo.run_oral_seal_v1("missing_seal")
    assert nominal.physical == missing.physical and nominal.commands == missing.commands
    assert all(source.oral_sealed is None for source in missing.sources)
    assert missing.metrics()["compatible_seal_first_cutoff"] is None


def test_fixed_disturbance_reactive_and_prediction_paths_are_not_open_loop():
    nominal = demo.run_oral_seal_v1()
    protected = demo.run_oral_seal_v1("disturbed")
    reactive = demo.run_oral_seal_v1("prediction_off")
    replay = demo.run_oral_seal_v1("open_loop")
    assert protected.settings.seal == reactive.settings.seal == replay.settings.seal
    assert protected.settings.physical == reactive.settings.physical == replay.settings.physical
    assert replay.commands == nominal.commands
    assert protected.commands != reactive.commands and reactive.commands != replay.commands
    assert protected.metrics()["final_closure"] == reactive.metrics()["final_closure"] == 0.6
    assert replay.metrics()["final_closure"] == 0.5 and replay.metrics()["physical_seal_final"]
    assert protected.metrics()["physical_seal_first_tick"] == 7 and reactive.metrics()["physical_seal_first_tick"] == 6
    assert any(comparison.unexpected for step in protected.steps for comparison in step.comparisons)
    assert any(comparison.unexpected for step in reactive.steps for comparison in step.comparisons)
    assert replay.reports == ()


def test_late_seal_loss_does_not_erase_historical_local_achievement():
    result = demo.run_oral_seal_v1("contact_loss_after")
    assert result.physical[8].seal.sealed and not result.physical[9].seal.sealed
    assert result.sources[9].oral_sealed is True and result.sources[10].oral_sealed is False
    assert result.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert result.metrics()["final_correspondence"] == "no_seal"


def test_short_lease_is_intermediate_attainment_not_full_request():
    result = demo.run_oral_seal_v1("short_lease")
    assert result.proposal.request.desired_closure == 0.6
    assert result.proposal.bindings[0].target.endpoint == pytest.approx(0.2)
    assert result.metrics()["local_coordinate_achieved"] and not result.metrics()["requested_coordinate_met"]
    assert all(command is None for command in result.commands[2:])


@pytest.mark.parametrize("case", ["nominal", "disturbed", "dropout", "contact_loss_after"])
def test_trace_capacity_and_rendering_do_not_change_movement_or_sources(case):
    full, small = demo.run_oral_seal_v1(case), demo.run_oral_seal_v1(case, trace_capacity=1)
    assert full.commands == small.commands and full.physical == small.physical and full.sources == small.sources
    assert dict(small.peaks)["lower_trace"] <= 1
    before = json.dumps(full.as_dict(), sort_keys=True)
    assert "P16-2C-G" in demo.render_oral_seal_v1(full)
    assert "Coordinate achievement" in demo.render_oral_seal_v1(full, detail=True)
    exported = full.as_dict()
    exported["physical"].clear()
    assert json.dumps(full.as_dict(), sort_keys=True) == before


def test_review_rejects_obvious_mutated_evidence():
    result = demo.run_oral_seal_v1()
    assert replace(result, installation_count=2).review_status == "FAIL"
    assert replace(result, durable_after="changed").review_status == "FAIL"
    assert replace(result, peaks=tuple((key, 5 if key == "lower_predictions_per_axis" else value)
                                      for key, value in result.peaks)).review_status == "FAIL"


def test_unknown_case_or_wrong_render_arguments_rejected():
    with pytest.raises(ValueError):
        demo.run_oral_seal_v1("not_a_case")
    with pytest.raises(TypeError):
        demo.render_oral_seal_v1(None)
    with pytest.raises(TypeError):
        demo.render_oral_seal_v1(demo.run_oral_seal_v1(), detail=1)


def test_menu_retained_detail_does_not_execute_again(monkeypatch, capsys):
    answers = iter(("5", "bogus", "1", "5", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    original = demo.run_oral_seal_v1
    calls = []
    def counted(case="nominal", **kwargs):
        calls.append(case)
        return original(case, **kwargs)
    monkeypatch.setattr(demo, "run_oral_seal_v1", counted)
    demo.run_oral_seal_menu_v1()
    output = capsys.readouterr().out
    assert calls == ["nominal", "nonsealable", "missing_seal", "partial_closure"]
    assert "No results retained" in output and "Choose 1-5" in output and "ORAL CLOSURE AND SEAL REVIEW: PASS" in output


def test_feeding_menu_routes_new_option_without_changing_old_choices(monkeypatch):
    import nca8_feeding_demo as feeding
    answers = iter(("23", ""))
    calls = []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(feeding, "run_oral_seal_menu_v1", lambda: calls.append("G"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["G"]


def test_cli_json_and_unknown_selector(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    completed = subprocess.run([sys.executable, str(script), "--oral-seal", "--case", "nominal", "--json"],
                               cwd=tmp_path, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)[0] == json.loads(json.dumps(demo.run_oral_seal_v1().as_dict()))
    invalid = subprocess.run([sys.executable, str(script), "--oral-seal", "--case", "bad"],
                             cwd=tmp_path, capture_output=True, text=True, check=False)
    assert invalid.returncode != 0 and "case is not available" in invalid.stderr


def test_registry_and_task_repertoire_keep_honest_scope():
    import cca8_run
    assert cca8_run.__version__ == "0.30.41"
    assert len(cca8_run._cca8_component_rows()) == 115
    assert len(cca8_run.PRIMITIVES) == 8
    rows = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert rows["nca8_oral_seal_demo"] == "nca8_oral_seal_demo"


def test_faulted_provider_stops_trial_without_automatic_retry(monkeypatch):
    trial = demo.OralSealTrialV1()
    original = trial.world.step
    def fail_after_effect(command=None):
        original(command)
        raise RuntimeError("injected post-effect boundary failure")
    monkeypatch.setattr(trial.world, "step", fail_after_effect)
    with pytest.raises(RuntimeError):
        trial.advance()
    assert trial.stopped and trial.world.tick == 1 and trial.world.oral_seal_body.closure == pytest.approx(0.1)
    with pytest.raises(RuntimeError):
        trial.advance()
    assert trial.world.tick == 1
