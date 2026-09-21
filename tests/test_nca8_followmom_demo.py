"""Integrated maternal experiments, selective controls and read-only menu/CLI access."""

import ast
import importlib.util
import json
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import nca8_followmom_demo as demo
import nca8_menu
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_runtime import Nca8SessionV1
from nca8_translation import TranslationFixtureV1
from cca8_support_world import PlanarWorldProfileV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", demo.FOLLOW_MOM_CASES_V1)
def test_all_profiles_have_measured_bounded_owners_fixed_physical_time_and_no_learning(case):
    rng = random.getstate()
    result = demo.run_follow_mom_v1(case)
    assert len(result.local_steps) == len(result.physical_samples) == 80
    assert len(result.cycles) == (81 if case == "fast_cadence" else 21)
    assert result.durable_unchanged and not result.bound_violations
    assert dict(result.peak_counts)["maternal_durable_maps"] == 1
    assert dict(result.peak_counts)["current_pnm"] <= 1
    assert all(cycle.scheduler.cycle_id == i + 1 for i, cycle in enumerate(result.cycles))
    assert random.getstate() == rng
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("case", ["association_off", "wrong_seed", "recognition_off", "spatial_off", "following_off", "already_near"])
def test_selective_disabled_inputs_or_adequate_proximity_do_not_create_hidden_following(case):
    result = demo.run_follow_mom_v1(case)
    assert result.cycles[-1].maternal_task.task is None
    assert not any(cycle.reservations for cycle in result.cycles)
    assert all(body.position == (0.0, 0.0) for body in result.physical_samples)


def test_turned_body_changes_motor_drives_while_task_scene_destination_agrees():
    straight, turned, other = (demo.run_follow_mom_v1(case) for case in ("nominal", "heading_90", "different_target"))
    first = straight.local_steps[0].command.translation
    second = turned.local_steps[0].command.translation
    assert first.forward == pytest.approx(-second.left)
    assert first.left == pytest.approx(second.forward)
    assert straight.physical_samples[-1].position == pytest.approx(turned.physical_samples[-1].position)
    assert other.physical_samples[-1].position[1] == pytest.approx(-straight.physical_samples[-1].position[1])


def test_operation_influence_changes_actual_focus_without_changing_body_or_other_priority_inputs():
    enabled, disabled = demo.run_follow_mom_v1("competing_on"), demo.run_follow_mom_v1("competing_off")
    on, off = enabled.cycles[1], disabled.cycles[1]
    assert on.calculation.cutoff_tick == off.calculation.cutoff_tick == 4
    assert on.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "maternal_target"
    assert off.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "visual_scene"
    assert on.maternal_source.as_dict() == off.maternal_source.as_dict()
    assert on.visual_source.as_dict() == off.visual_source.as_dict()
    assert on.commitment.selected_primitive_id is off.commitment.selected_primitive_id is None
    assert [item.as_dict() for item in enabled.local_steps] == [item.as_dict() for item in disabled.local_steps]
    assert enabled.physical_samples == disabled.physical_samples
    assert enabled.cycles[-1].maternal_task == disabled.cycles[-1].maternal_task


@pytest.mark.parametrize("case", ["nominal", "brief_gap", "support_interruption", "competing_on"])
def test_renderer_and_history_capacity_do_not_change_function_or_rng(case):
    full = demo.run_follow_mom_v1(case)
    short = demo.run_follow_mom_v1(case, trace_capacity=1)
    assert full.physical_samples == short.physical_samples
    assert [item.command for item in full.local_steps] == [item.command for item in short.local_steps]
    assert full.cycles[-1].maternal_task == short.cycles[-1].maternal_task
    before, rng = json.dumps(full.as_dict(), sort_keys=True), random.getstate()
    for detail in (False, True):
        text = demo.render_follow_mom_v1(full, detail=detail)
        assert "Full P16-2B remains open" in text and "no learned identity" in text
    exported = full.as_dict()
    exported["cycles"].clear()
    assert json.dumps(full.as_dict(), sort_keys=True) == before and random.getstate() == rng


@pytest.mark.parametrize("case", demo.MATERNAL_REPLAY_CASES_V1)
def test_source_replays_are_explicitly_nonphysical_and_start_no_selected_operation(case):
    result = demo.run_maternal_source_replay_v1(case)
    assert len(result.sources) == 2
    assert "NO PHYSICS / NO SELECTED APPLICATION" in demo.render_maternal_replay_v1(result)
    assert result.as_dict()["physical_steps"] == 0


@pytest.mark.parametrize("bad", [None, True, 0, "NOMINAL", "unknown"])
def test_unknown_profile_is_not_silently_repaired(bad):
    with pytest.raises(ValueError):
        demo.run_follow_mom_v1(bad)


def test_default_and_translation_profiles_do_not_construct_maternal_owners():
    for trial in (IntegratedRightingTrialV1(), IntegratedRightingTrialV1(planar_profile=PlanarWorldProfileV1(),
                                                                       translation_fixture=TranslationFixtureV1())):
        assert trial.core.maternal is trial.core.follow_mom is None
        assert not any(name.startswith("maternal_") or name.startswith("follow_mom_") for name in trial.retained_counts())


@pytest.mark.parametrize("options", [
    {"follow_mom_profile": True},
    {"follow_mom_profile": FollowMomProfileV1()},
    {"follow_mom_profile": FollowMomProfileV1(), "translation_fixture": TranslationFixtureV1(), "planar_profile": PlanarWorldProfileV1()},
    {"follow_mom_profile": FollowMomProfileV1(), "planar_profile": PlanarWorldProfileV1(), "task_outcomes_enabled": True},
])
def test_invalid_compositions_do_not_start_a_hybrid_or_reuse_righting_outcome_scoring(options):
    with pytest.raises((TypeError, ValueError)):
        IntegratedRightingTrialV1(**options)


def test_opening_and_leaving_menu_creates_no_world(monkeypatch):
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: "")
    monkeypatch.setattr(demo, "run_follow_mom_v1", lambda *_: pytest.fail("opening menu advanced a world"))
    demo.run_follow_mom_menu_v1()


@pytest.mark.parametrize("choice,cases", [("2", ("nominal", "heading_90", "different_target", "already_near")),
                                        ("4", ("brief_gap", "prolonged_gap", "support_interruption")),
                                        ("5", ("competing_on", "competing_off")), ("9", ("nominal",))])
def test_menu_calls_shared_experiments_once_and_preserves_return(choice, cases, monkeypatch):
    replies, calls = iter(("bad", choice, "")), []
    original = demo.run_follow_mom_v1
    def record(case):
        calls.append(case)
        return original(case)
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(replies))
    monkeypatch.setattr(demo, "run_follow_mom_v1", record)
    demo.run_follow_mom_menu_v1()
    assert tuple(calls) == cases


def test_parent_menu_keeps_existing_a0_session_and_rng(monkeypatch):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    replies = iter(("10", "5", "", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


@pytest.mark.parametrize("args", [["--case", "nominal"], ["--case", "prolonged_gap"], ["--replay", "independent_approach"]])
def test_cli_works_outside_repo_and_exports_the_exact_shared_result(args, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), *args, "--json"],
                             cwd=tmp_path, capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    expected = demo.run_maternal_source_replay_v1(args[1]) if args[0] == "--replay" else demo.run_follow_mom_v1(args[1])
    assert json.loads(process.stdout) == json.loads(json.dumps([expected.as_dict()], allow_nan=False))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [["--case", "unknown"], ["--replay", "unknown"], ["--case"],
                                  ["--case", "nominal", "--replay"], ["--outcomes", "unknown"]])
def test_cli_ambiguous_or_unknown_requests_fail_explicitly(args, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), *args],
                             cwd=tmp_path, capture_output=True, check=False)
    assert process.returncode == 2


def test_cli_reports_actual_bound_or_durable_change_as_failure(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("maternal_review_test", ROOT / "scripts/review_nca8_followmom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failed = replace(demo.run_follow_mom_v1(), durable_after="changed")
    monkeypatch.setattr(module, "run_follow_mom_v1", lambda _: failed)
    assert module.main(["--case", "nominal"]) == 1
    assert "durable unchanged=False" in capsys.readouterr().out


def test_owners_never_access_physics_legacy_task_or_evaluator():
    for name in ("nca8_maternal.py", "nca8_followmom.py"):
        tree = ast.parse((ROOT / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"_world", "observer_body", "observer_planar_body", "scenario_stage", "milestones"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"advance_lower", "focal_step", "install", "step_motor", "action_center_step"}


def test_registry_reports_real_components_without_promoting_local_smp_to_task():
    import cca8_run
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    for name in ("nca8_maternal", "nca8_followmom", "nca8_followmom_demo"):
        assert registry[name] == name
    assert cca8_run.__version__ == "0.30.29" and len(cca8_run._cca8_component_rows()) == 94
    assert len(cca8_run.PRIMITIVES) == 8
