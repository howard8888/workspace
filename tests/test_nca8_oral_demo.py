"""Oral foundation controls reuse the real lower driver and read-only menu."""

from dataclasses import replace
import ast
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import cca8_run
import nca8_feeding_demo
import nca8_menu
import nca8_oral_demo as demo
from nca8_runtime import Nca8SessionV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1
from nca8_sensorimotor_demo import SensorimotorTrialV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_oral_contact_v1(case) for case in demo.ORAL_CONTACT_CASES_V1}


@pytest.mark.parametrize("case", demo.ORAL_CONTACT_CASES_V1)
def test_every_declared_case_has_full_bounded_causal_evidence(results, case):
    result = results[case]
    assert result.review_status == "PASS", result.checks()
    assert len(result.checks()) == 9 and result.elapsed_ticks == 12
    assert result.metrics()["focal_calls"] == 0
    assert result.metrics()["source_update_fixture_opportunities"] == 1
    assert result.source_before == result.source_after and result.durable_before == result.durable_after
    exported = json.loads(json.dumps(result.as_dict(), allow_nan=False))
    assert exported["task_pnm"] == "not_supplied" and exported["feeding_learning"] == "unimplemented_no_participation"
    assert exported["latch"] == exported["milk"] == "not_modeled"
    assert exported["B99"] == "open" and exported["restores_motor_permission"] is False


def test_actual_contact_precedes_delivery_and_is_not_in_original_source(results):
    result = results["nominal"]
    assert result.metrics()["first_physical_touch_tick"] == result.metrics()["first_sensed_touch_event"] == 4
    assert result.metrics()["first_touch_available_tick"] == result.metrics()["local_achievement_reported_tick"] == 5
    assert result.metrics()["nonneutral_commands"] == 4
    assert result.sensed[4].oral.contact is False and result.sensed[5].oral.contact is True
    assert result.steps[4].feedback.event_tick == 3 and result.steps[5].feedback.event_tick == 4
    assert result.proposal.oral_preview.source.cutoff_tick == 0
    assert result.targets[0].initial.target.basis.oral.contact is False


def test_absent_tactile_surface_keeps_target_and_commands_but_removes_touch(results):
    present, absent = results["nominal"], results["no_surface"]
    assert present.commands == absent.commands
    assert present.proposal == absent.proposal
    assert tuple(row.extension_metres for row in present.physical) == tuple(row.extension_metres for row in absent.physical)
    assert absent.metrics()["observed_local_coordinate_achieved"] is True
    assert absent.metrics()["first_sensed_touch_event"] is None
    assert absent.sensed[-1].oral.contact is False


def test_unknown_contact_blocks_authority_instead_of_claiming_absent_contact(results):
    absent, unknown = results["no_surface"], results["missing_contact"]
    assert absent.targets and not unknown.targets
    assert unknown.sensed[0].oral.contact is None and unknown.metrics()["nonneutral_commands"] == 0
    assert unknown.proposal.withheld[0][1] == "required_contact_evidence_missing"


def test_geometry_only_preview_has_real_mapping_without_installation_or_motion(results):
    result = results["geometry_only"]
    assert result.proposal.bindings[0].target.endpoint == 0.1
    assert result.installations == 0 and not result.targets
    assert all(item.extension_metres == 0.0 for item in result.physical)


def test_body_rotation_alone_refuses_but_equivalent_scene_reexpression_moves(results):
    assert not results["heading_90"].targets
    assert results["rotated_scene"].commands == results["nominal"].commands
    assert results["rotated_scene"].physical == results["nominal"].physical


def test_partial_local_target_and_shorter_lease_never_imply_contact(results):
    for case, endpoint, count in [("intermediate_target", 0.15, 6), ("short_lease", 0.05, 2)]:
        result = results[case]
        assert result.targets[0].initial.target.endpoint == endpoint
        assert result.metrics()["observed_local_coordinate_achieved"] is True
        assert result.metrics()["first_sensed_touch_event"] is None
        assert result.metrics()["nonneutral_commands"] == count
    short = results["short_lease"]
    assert short.reports[0].feedback.event_tick == 2
    assert short.reports[0].reported_tick == 3
    assert short.targets[0].current.expires_at_tick == 2


def test_local_prediction_protection_changes_rate_not_the_task_or_a_faster_claim(results):
    intact, reactive, opened = (results[key] for key in ("disturbed", "prediction_off", "open_loop"))
    assert intact.proposal == reactive.proposal == opened.proposal
    assert intact.source_before == reactive.source_before == opened.source_before
    assert intact.steps[3].command.oral_drive == pytest.approx(0.5)
    assert reactive.steps[3].command.oral_drive == pytest.approx(1.0)
    assert any(abs(event.residual or 0.0) >= 0.019 for event in intact.events)
    assert not reactive.events and not opened.events and not opened.reports
    assert intact.metrics()["first_touch_available_tick"] == 7
    assert reactive.metrics()["first_touch_available_tick"] == 6
    assert opened.commands == results["nominal"].commands
    assert opened.metrics()["final_measured_reach"] == pytest.approx(0.08)
    assert opened.metrics()["first_sensed_touch_event"] is None


@pytest.mark.parametrize("case,reason", [("early_contact", "oral_contact_before_target"),
                                       ("body_shift", "oral_body_anchor_changed"), ("body_turn", "oral_body_anchor_changed")])
def test_new_contact_or_changed_body_stops_at_first_eligible_notice(results, case, reason):
    result = results[case]
    assert result.reports[0].reason == reason
    assert result.reports[0].reported_tick == 3
    assert result.steps[3].command is None and all(step.command is None for step in result.steps[3:])
    assert result.metrics()["observed_local_coordinate_achieved"] is False
    assert result.targets[0].current == result.targets[0].initial


def test_early_contact_does_not_claim_instant_stop_or_a_latch(results):
    result = results["early_contact"]
    assert result.physical[2].contact is True
    assert result.steps[2].command is not None
    assert result.physical[3].extension_metres == pytest.approx(0.075)
    assert result.physical[3].contact is False
    assert result.sensed[3].event_tick == 2 and result.sensed[3].oral.contact is True


def test_support_loss_preserves_physical_and_sensed_timing_without_unobserved_credit(results):
    result = results["support_loss"]
    assert result.physical[-1].extension_metres == pytest.approx(0.025)
    assert result.steps[3].command is None
    assert all(step.command is None for step in result.steps[3:])
    assert result.metrics()["observed_local_coordinate_achieved"] is False


def test_dropout_can_have_physical_touch_without_observed_confirmation(results):
    result = results["dropout"]
    assert result.metrics()["first_physical_touch_tick"] == 4
    assert result.metrics()["first_sensed_touch_event"] is None
    assert result.metrics()["observed_local_coordinate_achieved"] is False
    assert result.reports[0].reason == "current_feedback_timeout"
    assert result.sensed[-1].event_tick == 1
    assert result.physical[-1].extension_metres == pytest.approx(0.1)


def test_fixed_external_cancellation_does_not_renew_or_undo_effects(results):
    result = results["cancelled"]
    assert result.steps[0].command is not None
    assert all(step.command is None for step in result.steps[1:])
    assert result.reports[0].disposition is LocalTargetDispositionV1.CANCELLED
    assert result.physical[-1].extension_metres == pytest.approx(0.025)


@pytest.mark.parametrize("case", ["nominal", "disturbed", "dropout", "early_contact", "body_shift", "open_loop"])
@pytest.mark.parametrize("capacity", [1, 8])
def test_diagnostic_capacity_does_not_change_sources_authority_or_physics(results, case, capacity):
    smaller = demo.run_oral_contact_v1(case, trace_capacity=capacity)
    full = results[case]
    assert smaller.review_status == "PASS"
    assert smaller.commands == full.commands and smaller.physical == full.physical and smaller.sensed == full.sensed
    assert smaller.reports == full.reports and smaller.events == full.events
    assert smaller.targets == full.targets and smaller.source_after == full.source_after
    assert smaller.durable_after == full.durable_after


def test_render_and_export_are_read_only_and_do_not_run_a_trial(monkeypatch, results):
    def forbidden(*args, **kwargs):
        raise AssertionError("inspection attempted a physical trial")
    monkeypatch.setattr(demo, "run_oral_contact_v1", forbidden)
    result = results["nominal"]
    before, rng = result.as_dict(), random.getstate()
    for detail in (False, True):
        text = demo.render_oral_contact_v1(result, detail=detail)
        assert "supplied" in text.lower() and "B99 remains open" in text
    export = result.as_dict()
    export["sensed"][0]["oral"]["contact"] = True
    assert result.as_dict() == before and random.getstate() == rng


@pytest.mark.parametrize("change", [{"steps": ()}, {"sensed": ()}, {"physical": ()}, {"targets": ()}, {"installations": 0},
                                    {"elapsed_ticks": 11}, {"peak_counts": ()}, {"peak_counts": (("unknown", 1),)},
                                    {"source_before": "", "source_after": ""}, {"source_after": "changed"},
                                    {"durable_before": "", "durable_after": ""}, {"durable_after": "changed"}])
def test_missing_or_changed_qualification_evidence_cannot_pass(results, change):
    assert replace(results["nominal"], **change).review_status == "FAIL"


def test_duplicate_or_excessive_owner_counts_cannot_hide_growth(results):
    result = results["nominal"]
    duplicate = replace(result, peak_counts=result.peak_counts + (result.peak_counts[0],))
    assert duplicate.review_status == "FAIL"
    counts = dict(result.peak_counts)
    counts["body_reserved_records"] = 2
    assert replace(result, peak_counts=tuple(counts.items())).review_status == "FAIL"


def test_driver_methods_are_the_existing_h4_boundary_not_a_copied_oral_loop():
    for name in ("advance", "advance_open_loop", "_admit", "reset"):
        assert getattr(demo.OralContactTrialV1, name) is getattr(SensorimotorTrialV1, name)


def test_exception_after_possible_effect_stops_instead_of_replaying(monkeypatch):
    trial = demo.OralContactTrialV1()
    original = trial.world.step
    def fail_after_step(command):
        original(command)
        raise RuntimeError("ambiguous external effect")
    monkeypatch.setattr(trial.world, "step", fail_after_step)
    with pytest.raises(RuntimeError, match="ambiguous"):
        trial.advance()
    assert trial.stopped and trial.world.tick == 1
    assert trial.world.oral_body.extension_metres == pytest.approx(0.025)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        trial.advance()
    assert trial.world.tick == 1
    trial.reset()
    assert not trial.stopped and trial.world.stream.generation == 2
    assert trial.world.tick == 0 and trial.world.oral_body.extension_metres == 0.0


def test_reset_invalidates_old_targets_source_and_pending_deliveries():
    trial = demo.OralContactTrialV1()
    old_targets, old_source = trial.targets, trial.source
    trial.advance()
    trial.reset()
    assert trial.source.stream.generation == old_source.stream.generation + 1
    assert trial.world.pending_feedback_count == 0
    with pytest.raises(ValueError):
        trial.body.motor_targets.validate_reservation(old_targets[0], at_tick=0)
    assert trial.controller.installation_count == 1
    assert trial.advance().command.stream.generation == 2


@pytest.mark.parametrize("bad", [None, True, 0, [], "typo", ""])
def test_unknown_cases_fail_before_world_construction(bad):
    with pytest.raises(ValueError):
        demo.OralContactTrialV1(bad)


@pytest.mark.parametrize("bad", [0, 257, True, 1.5, "8"])
def test_invalid_retention_is_not_coerced(bad):
    with pytest.raises((TypeError, ValueError)):
        demo.OralContactTrialV1(trace_capacity=bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "true"])
def test_render_requires_explicit_boolean_option(results, bad):
    with pytest.raises(TypeError):
        demo.render_oral_contact_v1(results["nominal"], detail=bad)


def test_full_nested_menu_preserves_existing_a0_session_and_rng(monkeypatch, capsys):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    answers = iter(("15", "18", "1", "8", "", "", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert output.count("P16-2C-B / nominal / ORAL FOUNDATION REVIEW: PASS") == 2
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


def test_oral_menu_all_routes_and_retained_view_use_shared_results(monkeypatch, capsys, results):
    calls = []
    answers = iter(("8", "²", "unknown", "7", "8", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(demo, "run_oral_contact_v1", lambda case: calls.append(case) or results[case])
    demo.run_oral_contact_menu_v1()
    assert calls == list(demo.ORAL_CONTACT_CASES_V1)
    text = capsys.readouterr().out
    assert "No oral results retained" in text and "Choose 1-8" in text
    assert text.count("ORAL FOUNDATION REVIEW: PASS") == 2 * len(results)


@pytest.mark.parametrize("choice,expected", [("1", 1), ("2", 3), ("3", 5), ("4", 6), ("5", 3), ("6", 6)])
def test_each_menu_group_runs_only_its_declared_cases(monkeypatch, capsys, results, choice, expected):
    calls = []
    answers = iter((choice, ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(demo, "run_oral_contact_v1", lambda case: calls.append(case) or results[case])
    demo.run_oral_contact_menu_v1()
    assert len(calls) == expected
    assert capsys.readouterr().out.count("ORAL FOUNDATION REVIEW: PASS") == expected


@pytest.mark.parametrize("case", ["nominal", "no_surface", "dropout", "open_loop"])
def test_script_json_outside_repo_matches_common_full_evidence(results, case):
    script = ROOT / "scripts" / "review_nca8_feeding.py"
    response = subprocess.run([sys.executable, str(script), "--oral", "--case", case, "--json"],
                              cwd=ROOT.parent, capture_output=True, text=True, check=False)
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout) == [json.loads(json.dumps(results[case].as_dict()))]


@pytest.mark.parametrize("args", [("--oral", "--case", "attention_off"), ("--case", "early_contact"),
                                  ("--oral", "--case", "typo"), ("--oral", "--unknown")])
def test_script_rejects_cross_domain_or_unknown_selectors(args):
    response = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_feeding.py"), *args],
                              cwd=ROOT.parent, capture_output=True, text=True, check=False)
    assert response.returncode != 0 and response.stdout == ""


def test_script_propagates_a_failed_review_without_claiming_success(monkeypatch, capsys, results):
    from scripts import review_nca8_feeding as script
    bad = replace(results["nominal"], physical=())
    monkeypatch.setattr(script, "run_oral_contact_v1", lambda _case: bad)
    assert script.main(["--oral", "--case", "nominal"]) == 1
    assert "REVIEW: FAIL" in capsys.readouterr().out


def test_default_feeding_source_menu_still_routes_all_without_oral_runs(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("the default source review entered oral control")
    monkeypatch.setattr(nca8_feeding_demo, "run_oral_contact_menu_v1", forbidden)
    answers = iter(("",))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    nca8_feeding_demo.run_feeding_detail_menu_v1()
    assert "18) Oral target/contact foundation" in capsys.readouterr().out


def test_registry_reports_one_added_observer_not_new_host_task_primitives():
    assert cca8_run.__version__ == "0.30.37"
    assert len(cca8_run._cca8_component_rows()) == 110 and len(cca8_run.PRIMITIVES) == 8
    assert dict(cca8_run._CCA8_COMPONENT_REGISTRY)["nca8_oral_demo"] == "nca8_oral_demo"


def test_neutral_world_and_oral_mapper_do_not_consult_task_stage_or_predictions():
    tree = ast.parse((ROOT / "cca8_support_world.py").read_text())
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_advance_oral")
    words = {node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute)}
    assert not {"state", "_state", "task", "target", "pnm", "stage", "milestones", "success", "detail_position"} & words
    tree = ast.parse((ROOT / "nca8_body_targets.py").read_text())
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "propose_oral_reach")
    calls = {node.func.attr for node in ast.walk(method) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {"step", "advance", "commit", "choose", "install", "reserve", "focal_step"} & calls


def test_full_export_retains_original_physical_and_control_profile(results):
    result = results["disturbed"]
    profile = result.as_dict()["supplied_fixture_profile"]
    assert profile["physical"]["dt_seconds"] == 0.05
    assert profile["oral"]["perturbations"][0]["rate_metres_s"] == -0.4
    assert profile["oral"]["surfaces"][0]["position"] == (0.1, 0.0)
    assert profile["prediction_protection"] is True
    altered = replace(result.settings, prediction_protection=False)
    assert replace(result, settings=altered).review_status == "FAIL"
