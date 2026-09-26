"""Fixed-horizon integrated experiments, adverse outcomes and menu/CLI neutrality."""

from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import nca8_followmom_demo as maternal_demo
import nca8_menu
import nca8_stand_follow_demo as demo
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def runs():
    return {case: demo.run_stand_follow_v1(case) for case in demo.STAND_FOLLOW_CASES_V1}


@pytest.mark.parametrize("case", demo.STAND_FOLLOW_CASES_V1)
def test_every_profile_uses_one_finite_physical_horizon_actual_owner_bounds_and_no_durable_change(case, runs):
    result = runs[case]
    assert len(result.local_steps) == 160 and len(result.physical_samples) == 161
    assert [sample.tick for sample in result.physical_samples] == list(range(161))
    assert [cycle.calculation.cutoff_tick for cycle in result.cycles] == list(range(0, 161, 4))
    assert [cycle.scheduler.cycle_id for cycle in result.cycles] == list(range(1, 42))
    assert result.metrics()["elapsed_seconds"] == 8.0
    assert result.handoff_consumptions == 41
    assert result.target_installations == sum(bool(cycle.reservations) for cycle in result.cycles)
    assert result.bound_violations == () and result.durable_unchanged
    peaks = dict(result.peak_counts)
    assert peaks["maternal_durable_maps"] == peaks["visual_durable_maps"] == 1
    assert peaks["current_pnm"] <= 1 and peaks["outcome_pending_claims"] <= 8
    assert all(cycle.learning_report is None for cycle in result.cycles)
    assert all(cycle.maternal_correspondence.as_dict()["attention_route"] == "not_implemented_for_maternal" for cycle in result.cycles)
    payload = result.as_dict()
    assert payload["full_P16_2B"].startswith("open_") and payload["B99"].startswith("open_")
    assert not payload["restores_motor_permission"]
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("case,expected", [
    ("nominal", "completed"), ("brief_gap", "completed"), ("prolonged_gap", "target_unavailable"),
    ("support_loss", "budget_exhausted"), ("boundary_aim", "no_task"), ("righting_off", "no_task"),
    ("following_off", "no_task"), ("association_off", "no_task"), ("translation_unavailable", "budget_exhausted"),
    ("heading_90", "completed"), ("different_target", "completed"), ("already_supported", "completed"),
    ("motor_blocked", "execution_exhausted"), ("maternal_comparison_off", "completed"),
])
def test_adverse_profiles_report_their_actual_finite_result_not_forced_success(case, expected, runs):
    result = runs[case]
    assert result.metrics()["maternal_final_status"] == expected
    task = result.cycles[-1].maternal_task.task
    if task is not None:
        assert task.applications <= 20
        terminal = next(c for c in result.cycles if c.maternal_task.task is not None and c.maternal_task.task.status != "active")
        assert terminal.calculation.cutoff_tick - task.started_tick <= 80


def test_brief_gap_cancels_precise_pursuit_without_resetting_task_or_refreshing_evidence(runs):
    result = runs["brief_gap"]
    before, gap, resumed = (result.cycles[tick // 4] for tick in (56, 60, 64))
    assert gap.maternal_source.identity_status == "retained"
    assert gap.maternal_source.target_position is None and not gap.maternal_source.action_localized
    assert gap.maternal_source.last_supported_tick == before.maternal_source.last_supported_tick == 55
    assert gap.maternal_source.uncertainty_radius == pytest.approx(0.125)
    assert gap.maternal_task.task.task_id == before.maternal_task.task.task_id == resumed.maternal_task.task.task_id
    assert gap.receipt.dispatch.motor.directive == "cancel" and not gap.reservations and gap.commitment.pnm_id is None
    assert all(step.command is None for step in result.local_steps[60:64])
    assert resumed.maternal_source.action_localized and resumed.reservations
    assert result.metrics()["maternal_proximity_completed_at_tick"] == 108
    assert result.metrics()["maternal_applications"] == 8
    outcomes = [o for c in result.cycles for o in c.maternal_correspondence.outcomes]
    assert any(o.status == "interrupted" for o in outcomes)
    assert any(o.status == "expired_unresolved" and o.evidence is None for o in outcomes)


def test_prolonged_gap_stops_task_and_does_not_restart_when_target_reappears(runs):
    result = runs["prolonged_gap"]
    terminal = next(c for c in result.cycles if c.maternal_task.task is not None and c.maternal_task.task.status == "target_unavailable")
    assert terminal.calculation.cutoff_tick == 64
    assert result.cycles[-1].maternal_source.action_localized
    assert all(not c.reservations for c in result.cycles if c.calculation.cutoff_tick >= 60)
    assert all(step.command is None for step in result.local_steps[60:])
    assert result.physical_samples[-1].planar.position == result.physical_samples[60].planar.position
    assert result.metrics()["righting_final_status"] == "completed"
    assert result.metrics()["maternal_proximity_completed_at_tick"] is None


def test_support_loss_interrupts_lower_pursuit_before_next_focal_read_without_hidden_recovery(runs):
    result = runs["support_loss"]
    assert result.profile.physical.perturbations[0].start_tick == 57
    assert result.local_steps[58].command is not None
    stopped = result.local_steps[59]
    assert stopped.feedback.event_tick == 58 and stopped.feedback.available_tick == 59
    assert stopped.feedback.support_contact is False and stopped.command is None
    assert stopped.reports[0].disposition.value == "interrupted"
    assert stopped.reports[0].reason == "unexpected_contact_loss"
    assert result.cycles[15].calculation.cutoff_tick == 60
    assert result.cycles[15].maternal_task.reason == "body_support_unavailable"
    assert all(step.command is None for step in result.local_steps[59:])
    assert result.metrics()["righting_final_status"] == "completed"  # Historical, not current safety.
    assert result.final_feedback.support_contact is False
    assert not any(c.commitment.selected_primitive_id == "ip:righting" for c in result.cycles[10:])
    assert result.metrics()["maternal_final_status"] == "budget_exhausted"


@pytest.mark.parametrize("case", ["righting_off", "following_off", "association_off", "translation_unavailable", "motor_blocked"])
def test_selective_mechanism_removal_has_real_movement_consequence(case, runs):
    result = runs[case]
    assert all(sample.planar.position == (0, 0) for sample in result.physical_samples)
    assert not result.metrics()["stood_and_reached"]
    if case != "righting_off":
        assert result.metrics()["righting_final_status"] == "completed"
    if case == "motor_blocked":
        assert result.metrics()["first_translation_install_at_tick"] == 40
        assert result.metrics()["support_to_follow_authority_transition"]  # Installation is not movement.
    if case == "translation_unavailable":
        assert result.metrics()["maternal_applications"] == 20
        assert result.metrics()["first_translation_install_at_tick"] is None


def test_heading_transform_and_maternal_destination_act_through_actual_motor_commands(runs):
    normal, turned, other = (runs[case] for case in ("nominal", "heading_90", "different_target"))
    first, second = normal.local_steps[40].command.translation, turned.local_steps[40].command.translation
    assert first.forward == pytest.approx(-second.left)
    assert first.left == pytest.approx(second.forward)
    assert normal.physical_samples[-1].planar.position == pytest.approx(turned.physical_samples[-1].planar.position)
    assert other.physical_samples[-1].planar.position[1] == pytest.approx(-normal.physical_samples[-1].planar.position[1])
    assert normal.cycles[10].maternal_correspondence.registration.preview.scene_target.y == 1
    assert other.cycles[10].maternal_correspondence.registration.preview.scene_target.y == -1
    left_task, right_task = normal.cycles[9].calculation.task, turned.cycles[9].calculation.task
    assert replace(left_task, completion_samples=right_task.completion_samples) == right_task
    assert [replace(sample, planar=None) for sample in left_task.completion_samples] == [
        replace(sample, planar=None) for sample in right_task.completion_samples]
    assert all(sample.planar.heading_degrees == 90 for sample in right_task.completion_samples)


def test_maternal_comparison_control_preserves_commitments_commands_tasks_and_physics(runs):
    enabled, disabled = runs["nominal"], runs["maternal_comparison_off"]
    assert enabled.physical_samples == disabled.physical_samples
    assert enabled.local_steps == disabled.local_steps
    assert [c.commitment for c in enabled.cycles] == [c.commitment for c in disabled.cycles]
    assert [c.maternal_task for c in enabled.cycles] == [c.maternal_task for c in disabled.cycles]
    assert [c.claim_outcomes for c in enabled.cycles] == [c.claim_outcomes for c in disabled.cycles]
    assert all(o.status == "comparison_disabled" for c in disabled.cycles for o in c.maternal_correspondence.outcomes)
    assert len([o for c in disabled.cycles for o in c.maternal_correspondence.outcomes]) == 7


@pytest.mark.parametrize("capacity", [1, 8, 256, 4096])
def test_render_export_rng_and_retention_are_diagnostic_only(capacity, runs):
    state = random.getstate()
    actual = demo.run_stand_follow_v1("brief_gap", trace_capacity=capacity)
    expected = runs["brief_gap"]
    before = actual.as_dict()
    assert actual.local_steps == expected.local_steps and actual.physical_samples == expected.physical_samples
    assert actual.cycles == expected.cycles
    for detail in (False, True):
        rendered = demo.render_stand_follow_v1(actual, detail=detail)
        assert "Full P16-2B remains open" in rendered and "no runner stage list" in rendered
    assert actual.as_dict() == before and random.getstate() == state


def test_profile_and_owner_limit_exports_are_detached_from_cognitive_configuration():
    first = maternal_demo.follow_mom_owner_limits_v1()
    second = maternal_demo.follow_mom_owner_limits_v1()
    first["current_pnm"] = 999
    assert second["current_pnm"] == 1
    profile = demo.stand_follow_profile_v1()
    payload = profile.as_dict()
    payload["righting_target_inset_degrees"] = 99
    assert profile.target_inset_degrees == 2
    assert profile.as_dict()["physical_horizon_ticks"] == 160
    assert profile.as_dict()["each_task_maximum_ticks"] == 80


@pytest.mark.parametrize("bad", [None, True, 1, "typo", "", []])
def test_unknown_profiles_fail_before_a_trial_is_created(bad):
    with pytest.raises(ValueError):
        demo.create_stand_follow_trial_v1(bad)


@pytest.mark.parametrize("detail", [None, 0, 1, "yes"])
def test_renderer_rejects_truthy_nonboolean_detail(detail, runs):
    with pytest.raises(TypeError):
        demo.render_stand_follow_v1(runs["nominal"], detail=detail)


def test_replay_is_exact_including_both_original_correspondence_paths(runs):
    assert demo.run_stand_follow_v1("nominal").as_dict() == runs["nominal"].as_dict()


def test_menu_path_reuses_same_experiments_and_preserves_existing_a0_session(monkeypatch, capsys):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    choices = iter(("11", "1", "", ""))
    monkeypatch.setattr(nca8_menu.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert "P16-2B-C CONTINUOUS STAND -> FOLLOW-MOM | nominal" in output
    assert "'maternal_proximity_completed_at_tick': 104" in output
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


@pytest.mark.parametrize("choice,expected,detail", [("1", ("nominal",), False),
                                                   ("2", ("brief_gap", "prolonged_gap", "support_loss"), False),
                                                   ("6", ("nominal",), True), ("7", ("brief_gap",), True)])
def test_submenu_delegates_without_duplicating_a_cognitive_loop(choice, expected, detail, monkeypatch, capsys):
    calls = []
    choices = iter(("invalid", choice, ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(demo, "run_stand_follow_v1", lambda case: calls.append(case) or case)
    monkeypatch.setattr(demo, "render_stand_follow_v1", lambda result, **options: f"{result} detail={options['detail']}")
    demo.run_stand_follow_menu_v1()
    assert tuple(calls) == expected
    output = capsys.readouterr().out
    assert "Choose 1-7" in output and f"detail={detail}" in output


@pytest.mark.parametrize("case", ["nominal", "prolonged_gap", "support_loss"])
def test_cli_runs_outside_repo_and_exports_exact_shared_results(case, runs, tmp_path):
    command = [sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), "--stand-follow", case, "--json"]
    process = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == json.loads(json.dumps([runs[case].as_dict()], allow_nan=False))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [["--stand-follow", "typo"], ["--stand-follow", "--case", "nominal"],
                                  ["--stand-follow", "--outcomes"], ["--stand-follow", "--replay"]])
def test_cli_rejects_unknown_or_combined_experiment_selectors(args, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), *args], cwd=tmp_path,
                             capture_output=True, text=True, check=False)
    assert process.returncode == 2


def load_review():
    spec = importlib.util.spec_from_file_location("stand_follow_review_test", ROOT / "scripts/review_nca8_followmom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("change", [{"durable_after": "changed"}, {"peak_counts": (("unknown_owner", 1),)},
                                    {"peak_counts": (("current_pnm", 2),)}, {"peak_counts": (("current_pnm", -1),)}])
def test_cli_hygiene_failures_are_nonzero_not_suppressed_adverse_tasks(change, runs, monkeypatch, capsys):
    module = load_review()
    failed = replace(runs["nominal"], **change)
    monkeypatch.setattr(module, "run_stand_follow_v1", lambda case: failed)
    assert module.main(["--stand-follow", "nominal"]) == 1
    assert "P16-2B-C" in capsys.readouterr().out


def test_cli_no_case_means_all_named_stand_follow_profiles(runs, monkeypatch, capsys):
    module = load_review()
    calls = []
    monkeypatch.setattr(module, "run_stand_follow_v1", lambda case: calls.append(case) or runs[case])
    monkeypatch.setattr(module, "render_stand_follow_v1", lambda result, **kwargs: result.profile.case)
    assert module.main(["--stand-follow"]) == 0
    assert tuple(calls) == demo.STAND_FOLLOW_CASES_V1
    assert "boundary_aim" in capsys.readouterr().out


def test_registry_includes_real_new_experiment_without_new_host_behavioral_primitives():
    import cca8_run
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_stand_follow_demo"] == "nca8_stand_follow_demo"
    assert cca8_run.__version__ == "0.30.46"
    assert len(cca8_run._cca8_component_rows()) == 126 and len(cca8_run.PRIMITIVES) == 8
