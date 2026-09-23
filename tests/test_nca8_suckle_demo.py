"""Selected-latch causal experiments, reset/fault boundaries and menu/CLI preservation."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

import nca8_suckle_demo as demo
from nca8_suckle import SuckleApplicationV1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_suckle_v1(case) for case in demo.SUCKLE_LATCH_CASES_V1}


def commands(result):
    return tuple(step.command for step in result.run.local_steps)


@pytest.mark.parametrize("case", demo.SUCKLE_LATCH_CASES_V1)
def test_each_predeclared_case_has_complete_actual_evidence(case, runs):
    result = runs[case]
    assert result.review_status == "PASS", [(key, value) for key, value in result.checks() if not value]
    assert len(result.checks()) == 17
    assert result.run.durable_before == result.run.durable_after
    assert result.metrics()["full_suckle_complete"] is False
    assert result.metrics()["milk"] == "not_supplied"
    assert len(result.run.physical_samples) == result.profile.run.horizon_ticks + 1


def test_nominal_timeline_keeps_physical_seal_and_sampled_task_result_separate(runs):
    result = runs["nominal"]
    metrics = result.metrics()
    assert metrics["first_suckle_tick"] == 0 and metrics["closure_commands"] == 6
    assert metrics["first_physical_seal_tick"] == 5
    assert (metrics["first_source_seal_event"], metrics["first_source_seal_cutoff"], metrics["latch_established_tick"]) == (7, 8, 12)
    cycles = {cycle.calculation.cutoff_tick: cycle for cycle in result.run.cycles}
    assert cycles[8].suckle_task.task.status == "active"
    assert [item.maternal.visual.event_tick for item in cycles[12].suckle_task.latch_samples] == [7, 11]
    assert cycles[0].receipt.dispatch.motor.as_dict()["physical_execution_established"] is False
    assert cycles[12].suckle_task.task.as_dict()["full_suckle_complete"] is False


def test_nonsealable_surface_preserves_every_command_and_closure_but_never_latches(runs):
    nominal, other = runs["nominal"], runs["nonsealable"]
    assert commands(nominal) == commands(other)
    assert tuple(x.seal.closure for x in nominal.run.physical_samples) == tuple(x.seal.closure for x in other.run.physical_samples)
    assert tuple(x.oral for x in nominal.run.physical_samples) == tuple(x.oral for x in other.run.physical_samples)
    assert nominal.run.cycles[0].calculation.navigation.application.projection == other.run.cycles[0].calculation.navigation.application.projection
    assert other.metrics()["final_closure"] == 0.6 and other.metrics()["latch_established_tick"] is None
    assert other.metrics()["final_task_status"] == "budget_exhausted"


def test_seal_sensor_loss_preserves_every_physical_sample_not_confirmation(runs):
    nominal, other = runs["nominal"], runs["missing_seal"]
    assert commands(nominal) == commands(other) and nominal.run.physical_samples == other.run.physical_samples
    assert other.metrics()["final_physical_seal"] and other.metrics()["latch_established_tick"] is None
    assert other.metrics()["first_source_seal_cutoff"] is None
    assert all(c.feeding_detail_source.oral_sealed is None for c in other.run.cycles)


@pytest.mark.parametrize("case", ["suckle_off", "attention_off", "source_off", "no_need", "wrong_category", "missing_detail",
                                  "no_touch", "touch_elsewhere", "missing_touch", "missing_closure"])
def test_missing_preconditions_cannot_be_replaced_by_a_command_or_milestone(case, runs):
    result = runs[case]
    assert result.metrics()["suckle_applications"] == result.metrics()["closure_commands"] == 0
    assert result.metrics()["first_physical_seal_tick"] is None
    assert not any(isinstance(c.calculation.navigation.application, SuckleApplicationV1) for c in result.run.cycles)


@pytest.mark.parametrize("case", ["already_sealed", "closed_without_seal"])
def test_initial_fixture_is_not_a_newly_selected_task_or_earned_latch(case, runs):
    result = runs[case]
    assert result.metrics()["final_closure"] == 0.6
    assert result.metrics()["first_suckle_tick"] is None and result.metrics()["latch_established_tick"] is None
    assert result.metrics()["final_physical_seal"] is (case == "already_sealed")


def test_narrowing_keeps_one_task_and_original_forecast_without_renewing_budget(runs):
    result = runs["narrowed"]
    selected = [c for c in result.run.cycles if isinstance(c.calculation.navigation.application, SuckleApplicationV1)]
    first, second = selected
    assert [c.calculation.cutoff_tick for c in selected] == [0, 8]
    assert first.reservations[0].current.target.endpoint == pytest.approx(0.3)
    assert first.calculation.navigation.application.projection.predicted_closure == 0.6
    assert second.reservations[0].current.target.endpoint == pytest.approx(0.6)
    assert second.suckle_task.task.task_id == first.suckle_task.task.task_id
    assert first.suckle_task.task.started_tick == second.suckle_task.task.started_tick == 0
    assert second.suckle_task.task.applications == 2 and result.metrics()["latch_established_tick"] == 16
    assert first.receipt.dispatch.motor.as_dict()["task_pnm_correspondence"] == "deferred_suckle_correspondence"


def test_absent_capability_and_blocked_execution_are_not_the_same_failure(runs):
    absent, blocked = runs["no_capability"], runs["blocked_motor"]
    assert absent.metrics()["suckle_applications"] == 12 and absent.metrics()["target_installations"] == 0
    assert absent.metrics()["closure_commands"] == 0 and absent.metrics()["final_task_status"] == "budget_exhausted"
    assert blocked.metrics()["target_installations"] == 1 and blocked.metrics()["closure_commands"] > 0
    assert blocked.metrics()["final_closure"] == 0 and blocked.metrics()["final_task_status"] == "execution_exhausted"
    assert len({c.suckle_task.task.task_id for c in absent.run.cycles if c.suckle_task.task}) == 1


def test_influence_pair_changes_actual_focus_without_changing_movement_or_evidence(runs):
    enabled, disabled = runs["competing_on"], runs["influence_off"]
    assert enabled.profile.run == disabled.profile.run or replace(enabled.profile.run, case="influence_off") == disabled.profile.run
    assert enabled.run.physical_samples == disabled.run.physical_samples and commands(enabled) == commands(disabled)
    assert tuple(c.feeding_detail_source for c in enabled.run.cycles) == tuple(c.feeding_detail_source for c in disabled.run.cycles)
    assert enabled.run.cycles[1].calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
    assert disabled.run.cycles[1].calculation.attention.selected_source_state.source_map_ref.map_id == "visual_scene"
    assert enabled.metrics()["latch_established_tick"] == disabled.metrics()["latch_established_tick"] == 12


def test_registration_control_keeps_original_handoff_preview_not_prediction_information_ablation(runs):
    nominal, off = runs["nominal"], runs["pnm_registration_off"]
    assert commands(nominal) == commands(off) and nominal.run.physical_samples == off.run.physical_samples
    assert nominal.run.registered_suckle_pnm_cycles == (1,) and off.run.registered_suckle_pnm_cycles == ()
    assert off.run.cycles[0].receipt.dispatch.motor.projection is not None
    assert off.metrics()["latch_established_tick"] == nominal.metrics()["latch_established_tick"]


@pytest.mark.parametrize("case,opportunities,latch", [("cadence_1", 65, 10), ("nominal", 17, 12), ("cadence_8", 9, 16)])
def test_cadence_holds_physical_horizon_not_number_of_focal_calls(case, opportunities, latch, runs):
    result = runs[case]
    assert result.metrics()["physical_ticks"] == 64 and result.metrics()["focal_opportunities"] == opportunities
    assert result.metrics()["latch_established_tick"] == latch
    assert commands(result) == commands(runs["nominal"])
    assert result.run.physical_samples == runs["nominal"].run.physical_samples


@pytest.mark.parametrize("case,selected,reach,latch", [("seek_then_latch", 8, 12, 20), ("stand_follow", 108, 112, 120)])
def test_latch_selection_does_not_wait_for_seeking_completion_milestone(case, selected, reach, latch, runs):
    result = runs[case]
    assert result.metrics()["first_suckle_tick"] == selected < reach == result.metrics()["first_geometric_reach_tick"]
    assert result.metrics()["latch_established_tick"] == latch
    entry = next(c for c in result.run.cycles if c.calculation.cutoff_tick == selected)
    assert entry.seeking_task.task.status == "active" and entry.feeding_detail_source.contact_correspondence_status == "compatible"
    assert entry.suckle_task.task.applications == 1
    assert all(r.current.target.kind is SensorimotorTargetKindV1.ORAL_CLOSURE for r in entry.reservations)


@pytest.mark.parametrize("enabled,disabled", [("seek_then_latch", "seek_then_suckle_off"), ("stand_follow", "stand_follow_suckle_off")])
def test_suckle_off_preserves_prior_seeking_then_removes_new_closure(enabled, disabled, runs):
    on, off = runs[enabled], runs[disabled]
    onset = on.metrics()["first_suckle_tick"]
    assert on.run.physical_samples[:onset + 1] == off.run.physical_samples[:onset + 1]
    assert commands(on)[:onset] == commands(off)[:onset]
    assert on.metrics()["first_seeking_tick"] == off.metrics()["first_seeking_tick"]
    assert on.metrics()["first_geometric_reach_tick"] == off.metrics()["first_geometric_reach_tick"]
    assert off.metrics()["closure_commands"] == 0 and off.metrics()["latch_established_tick"] is None


def test_later_seal_loss_keeps_historical_latch_not_current_success(runs):
    result = runs["seal_loss_after"]
    assert result.metrics()["latch_established_tick"] == 12
    assert result.run.physical_samples[12].seal.sealed and not result.run.physical_samples[13].seal.sealed
    assert result.metrics()["final_task_status"] == "latch_established"
    cycles = {cycle.calculation.cutoff_tick: cycle for cycle in result.run.cycles}
    assert cycles[16].suckle_task.current_seal_status == "no_seal"
    assert cycles[16].commitment.selected_primitive_id == "ip:seek_nipple"
    assert cycles[20].suckle_task.current_seal_status == "compatible"
    assert cycles[16].suckle_task.latch_samples == cycles[20].suckle_task.latch_samples == cycles[12].suckle_task.latch_samples
    assert result.run.physical_samples[17].seal.sealed
    assert result.metrics()["suckle_applications"] == 1


def test_missing_visual_gap_stops_and_resumes_only_a_new_current_contribution(runs):
    brief, long = runs["brief_gap"], runs["prolonged_gap"]
    assert brief.metrics()["suckle_applications"] == 2 and brief.metrics()["latch_established_tick"] == 16
    assert all(step.command is None for step in brief.run.local_steps[4:8])
    assert long.metrics()["final_task_status"] == "evidence_unavailable" and long.metrics()["suckle_applications"] == 1
    assert long.metrics()["latch_established_tick"] is None


@pytest.mark.parametrize("case,status", [("support_loss", "support_interrupted"), ("body_shift", "contact_lost"),
                                         ("cancelled", "cancelled"), ("dropout", "evidence_unavailable"), ("delayed", "evidence_unavailable")])
def test_interrupted_or_unknown_execution_ends_boundedly_without_latch(case, status, runs):
    result = runs[case]
    assert result.metrics()["final_task_status"] == status and result.metrics()["latch_established_tick"] is None
    assert all(step.command is None or step.command.oral_closure_drive in (None, 0.0) for step in result.run.local_steps[8:])


@pytest.mark.parametrize("case", ["nominal", "narrowed", "missing_seal", "stand_follow"])
def test_retained_rendering_and_small_trace_do_not_change_any_source_or_motion(case, runs):
    full, small = runs[case], demo.run_suckle_v1(case, trace_capacity=1)
    assert commands(full) == commands(small) and full.run.physical_samples == small.run.physical_samples
    assert tuple(c.feeding_detail_source for c in full.run.cycles) == tuple(c.feeding_detail_source for c in small.run.cycles)
    assert full.metrics() == small.metrics()
    before = json.dumps(full.as_dict(), sort_keys=True)
    assert "P16-2C-H" in demo.render_suckle_v1(full) and "Original projections" in demo.render_suckle_v1(full, detail=True)
    exported = full.as_dict()
    exported["cycles"].clear()
    assert json.dumps(full.as_dict(), sort_keys=True) == before


def test_review_detects_wrong_schedule_missing_commands_or_mutated_durable_evidence(runs):
    result = runs["nominal"]
    for changed in (replace(result.run, local_steps=result.run.local_steps[:-1]),
                    replace(result.run, durable_after="changed"), replace(result.run, handoff_consumptions=0),
                    replace(result.run, registered_suckle_pnm_cycles=())):
        assert replace(result, run=changed).review_status == "FAIL"


def test_focal_handoff_installs_once_without_physically_advancing():
    trial = demo.create_suckle_trial_v1()
    before = trial.observer_oral_seal_body
    cycle = trial.focal_step()
    assert trial.tick == 0 and trial.observer_oral_seal_body == before and trial.controller.installation_count == 1
    assert cycle.calculation.navigation.application.primitive_id == "ip:suckle"
    step = trial.advance_lower()
    assert step.tick == 0 and trial.tick == 1 and trial.observer_oral_seal_body.closure == pytest.approx(0.1)
    with pytest.raises((RuntimeError, ValueError)):
        trial.core.handoff.consume(cycle.receipt)
    assert trial.tick == 1 and trial.controller.installation_count == 1


def test_reset_replaces_suckle_owner_and_revokes_old_generation():
    trial = demo.create_suckle_trial_v1()
    cycle = trial.focal_step()
    old_owner, old_controller = trial.core.suckle, trial.controller
    trial.advance_lower()
    trial.reset()
    assert trial.tick == 0 and trial.core.suckle is not old_owner and trial.controller is not old_controller
    assert old_owner.task.status == "cancelled" and trial.core.suckle.task is None and not trial.core.suckle.history()
    assert trial.observer_oral_seal_body.closure == 0
    current = trial.focal_step()
    assert current.feeding_detail_source.stream.generation == cycle.feeding_detail_source.stream.generation + 1
    with pytest.raises((RuntimeError, ValueError)):
        trial.core.handoff.consume(cycle.receipt)


def test_fault_after_possible_effect_stops_without_command_replay(monkeypatch):
    trial = demo.create_suckle_trial_v1()
    trial.focal_step()
    original = trial._world.step
    def fail_after_effect(command=None):
        original(command)
        raise RuntimeError("injected post-effect failure")
    monkeypatch.setattr(trial._world, "step", fail_after_effect)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1 and trial.observer_oral_seal_body.closure == pytest.approx(0.1)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1


@pytest.mark.parametrize("bad", [None, 1, "bad"])
def test_unknown_case_is_not_silently_repaired(bad):
    with pytest.raises(ValueError):
        demo.run_suckle_v1(bad)


def test_wrong_renderer_arguments_are_rejected(runs):
    with pytest.raises(TypeError):
        demo.render_suckle_v1(None)
    with pytest.raises(TypeError):
        demo.render_suckle_v1(runs["nominal"], detail=1)


def test_menu_retained_detail_does_not_reexecute(monkeypatch, capsys):
    answers = iter(("6", "bogus", "1", "6", ""))
    calls = []
    original = demo.run_suckle_v1
    def counted(case="nominal", **kwargs):
        calls.append(case)
        return original(case, **kwargs)
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(demo, "run_suckle_v1", counted)
    demo.run_suckle_menu_v1()
    output = capsys.readouterr().out
    assert calls == ["nominal", "nonsealable", "missing_seal", "already_sealed", "closed_without_seal"]
    assert "No completed results" in output and "Unknown choice" in output
    assert "Original projections" in output and "SELECTED INITIAL LATCH REVIEW: PASS" in output


def test_feeding_menu_routes_new_option_without_running_old_demo(monkeypatch):
    import nca8_feeding_demo as feeding
    answers, calls = iter(("24", "")), []
    monkeypatch.setattr(feeding.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(feeding, "run_suckle_menu_v1", lambda: calls.append("H"))
    feeding.run_feeding_detail_menu_v1()
    assert calls == ["H"]


def test_cli_json_matches_complete_export_and_rejects_wrong_selector(tmp_path, runs):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    completed = subprocess.run([sys.executable, str(script), "--suckle", "--case", "nominal", "--json"],
                               cwd=tmp_path, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)[0] == json.loads(json.dumps(runs["nominal"].as_dict()))
    for args in (("--suckle", "--case", "bad"), ("--suckle", "--oral-seal")):
        failed = subprocess.run([sys.executable, str(script), *args], cwd=tmp_path, capture_output=True, text=True, check=False)
        assert failed.returncode != 0


def test_cli_failed_review_produces_nonzero_exit(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/review_nca8_feeding.py"
    spec = importlib.util.spec_from_file_location("suckle_review_cli_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Failure:
        review_status = "FAIL"
    monkeypatch.setattr(module, "run_suckle_v1", lambda case: Failure())
    monkeypatch.setattr(module, "render_suckle_v1", lambda *args, **kwargs: "FAIL")
    assert module.main(["--suckle", "--case", "nominal"]) == 1


def test_registry_reports_new_production_modules_not_full_suckle():
    import cca8_run
    assert cca8_run.__version__ == "0.30.36"
    assert len(cca8_run._cca8_component_rows()) == 106 and len(cca8_run.PRIMITIVES) == 8
    rows = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert rows["nca8_suckle"] == "nca8_suckle" and rows["nca8_suckle_demo"] == "nca8_suckle_demo"
