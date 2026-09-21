"""Integration/inspection tests for the explicitly non-actuating visual preview."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_menu
import nca8_visual_demo as demo
from cca8_navmap_kernel import NavPointV1
from nca8_runtime import Nca8SessionV1
from nca8_visual import VisualNavMapStateV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", demo.VISUAL_PREVIEW_CASES_V1)
def test_all_declared_profiles_are_finite_repeatable_nonactuating_and_bounded(case):
    before = random.getstate()
    first, second = demo.run_visual_preview_v1(case), demo.run_visual_preview_v1(case)
    assert first.as_dict() == second.as_dict()
    assert random.getstate() == before
    assert 1 <= len(first.records) <= 4
    assert first.durable_unchanged and not first.bound_violations
    assert all(first.as_dict()[name] == 0 for name in ("physical_steps", "motor_commands", "target_installations", "durable_learning_updates"))
    for record in first.records:
        selected = record.calculation.attention.selected_source_state
        working = record.calculation.navigation.wnm
        if working is not None:
            assert working.primary_source_state is selected
        if isinstance(selected, VisualNavMapStateV1):
            assert selected is record.visual
            assert record.calculation.navigation.application is None
            assert record.calculation.proposal is None
            assert record.mapping is not None and not record.mapping.as_dict()["motor_authority"]
        else:
            assert record.mapping is None


def test_real_body_rotation_and_equivalent_coordinate_reexpression_are_different():
    nominal, rotated, expressed, shifted = (demo.run_visual_preview_v1(case).records[0].mapping for case in
        ("heading_0", "heading_90", "rotated_coordinates", "translated_coordinates"))
    assert nominal.scene_target == rotated.scene_target == NavPointV1(2, 1)
    assert nominal.body_relative_target == NavPointV1(2, 1)
    assert (rotated.body_relative_target.x, rotated.body_relative_target.y) == pytest.approx((1, -2))
    assert nominal.hypothetical_self == rotated.hypothetical_self
    assert (expressed.body_relative_target.x, expressed.body_relative_target.y) == pytest.approx((2, 1))
    assert (expressed.body_step.x, expressed.body_step.y) == pytest.approx((nominal.body_step.x, nominal.body_step.y))
    assert shifted.body_relative_target == nominal.body_relative_target
    assert (shifted.hypothetical_self.x - 10, shifted.hypothetical_self.y + 3) == pytest.approx(
        (nominal.hypothetical_self.x, nominal.hypothetical_self.y))


def test_recognition_and_action_stream_ablations_have_independent_consumers():
    nominal = demo.run_visual_preview_v1("heading_0").records[0]
    recognition_off = demo.run_visual_preview_v1("recognition_off").records[0]
    spatial_off = demo.run_visual_preview_v1("spatial_off").records[0]
    both_off = demo.run_visual_preview_v1("both_off").records[0]
    assert not recognition_off.visual.recognition
    assert recognition_off.visual.guidance == nominal.visual.guidance
    assert recognition_off.mapping.body_relative_target == nominal.mapping.body_relative_target
    assert recognition_off.mapping.body_step == nominal.mapping.body_step
    assert spatial_off.visual.recognition == nominal.visual.recognition
    assert spatial_off.visual.guidance == () and spatial_off.visual.self_position is None
    assert spatial_off.mapping.status == "spatial_stream_disabled"
    assert spatial_off.mapping.body_step is None
    assert both_off.calculation.navigation.wnm is None and both_off.mapping is None


@pytest.mark.parametrize("case,status", [("missing_heading", "body_geometry_unknown"), ("missing_body_position", "body_geometry_unknown"),
                                        ("frame_mismatch", "frame_incompatible"), ("target_unlocalized", "target_unlocalized"),
                                        ("mapping_off", "mapping_disabled"), ("stale_body", "body_pose_unavailable")])
def test_missing_stale_and_disabled_geometry_are_not_fabricated_targets(case, status):
    result = demo.run_visual_preview_v1(case).records[-1]
    assert result.mapping.status == status and result.mapping.body_step is None
    assert result.calculation.navigation.application is None


def test_visual_source_does_not_override_the_real_support_candidate():
    record = demo.run_visual_preview_v1("support_priority").records[0]
    assert record.calculation.attention.selected_source_state.source_map_ref.map_id == "posture_support"
    assert record.calculation.navigation.selected_primitive_id == "ip:righting"
    assert record.visual.evidence_current and record.mapping is None
    assert record.calculation.proposal is not None


def test_nonfocal_updates_return_the_new_visual_source_not_cached_working_content():
    records = demo.run_visual_preview_v1("nonfocal_refresh").records
    assert [r.visual.guidance[0].position for r in records] == [NavPointV1(2, 1), NavPointV1(3, 1), NavPointV1(4, 1)]
    assert [r.calculation.attention.selected_source_state.source_map_ref.map_id for r in records] == [
        "posture_support", "posture_support", "visual_scene"]
    assert len({r.visual.source_map_ref for r in records}) == 1
    assert records[-1].mapping.scene_target == NavPointV1(4, 1)
    assert records[0].visual.guidance[0].position == NavPointV1(2, 1)


def test_gap_does_not_restore_current_access_from_an_old_duplicate():
    records = demo.run_visual_preview_v1("gap_recovery").records
    assert [r.visual.input_status for r in records] == ["current", "missing", "unavailable_after_gap", "current"]
    assert records[1].calculation.navigation.wnm is None and records[2].calculation.navigation.wnm is None
    assert records[0].visual.event_tick == records[2].visual.event_tick == 0
    assert records[-1].visual.event_tick == 11 and records[-1].mapping is not None


def test_preview_never_constructs_physics_or_installs_any_lower_executor(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("preview must not construct a physical world or install targets")
    monkeypatch.setattr("cca8_support_world.MotorWorldV1.__init__", forbidden)
    monkeypatch.setattr("nca8_sensorimotor.SensorimotorExecutorV1.install", forbidden)
    for case in demo.VISUAL_PREVIEW_CASES_V1:
        demo.run_visual_preview_v1(case)


@pytest.mark.parametrize("case", demo.VISUAL_PREVIEW_CASES_V1)
def test_rendering_and_detached_export_cannot_change_retained_records(case):
    result = demo.run_visual_preview_v1(case)
    before = json.dumps(result.as_dict(), sort_keys=True, allow_nan=False)
    for detail in (False, True, False):
        text = demo.render_visual_preview_v1(result, detail=detail)
        assert "P16-2A remains open" in text and "physical steps=0" in text
    exported = result.as_dict()
    exported["records"].clear()
    assert json.dumps(result.as_dict(), sort_keys=True, allow_nan=False) == before


def test_summary_reports_actual_bound_or_durable_failures():
    result = replace(demo.run_visual_preview_v1(), durable_unchanged=False, bound_violations=("test_violation",))
    text = demo.render_visual_preview_v1(result)
    assert "durable unchanged=False" in text and "test_violation" in text


@pytest.mark.parametrize("case", [None, True, 1, "bad", "HEADING_0"])
def test_unknown_case_does_not_silently_run_the_nominal_fixture(case):
    with pytest.raises(ValueError):
        demo.run_visual_preview_v1(case)


def test_menu_open_and_return_construct_no_trial(monkeypatch):
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: "")
    monkeypatch.setattr(demo, "run_visual_preview_v1", lambda *_args: pytest.fail("opening menu ran a trial"))
    demo.run_visual_preview_menu_v1()


@pytest.mark.parametrize("choice,cases", [("2", ("heading_0", "heading_90", "rotated_coordinates", "translated_coordinates")),
                                        ("3", ("heading_0", "recognition_off", "spatial_off", "both_off")),
                                        ("5", ("support_priority", "nonfocal_refresh")), ("6", ("gap_recovery",)),
                                        ("7", ("heading_0",))])
def test_menu_runs_the_same_case_functions_and_keeps_return_semantics(monkeypatch, choice, cases):
    replies, called = iter(("bad", choice, "")), []
    original = demo.run_visual_preview_v1
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(replies))
    def record(case):
        called.append(case)
        return original(case)
    monkeypatch.setattr(demo, "run_visual_preview_v1", record)
    demo.run_visual_preview_menu_v1()
    assert tuple(called) == cases


def test_parent_menu_route_preserves_the_existing_a0_session(monkeypatch):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    replies = iter(("9", "2", "", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


@pytest.mark.parametrize("case", ["heading_90", "spatial_off", "nonfocal_refresh", "gap_recovery"])
def test_cli_outside_repo_json_matches_the_shared_experiment(tmp_path, case):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_visual.py"), "--case", case, "--json"],
                            cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [demo.run_visual_preview_v1(case).as_dict()]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("args", [["--case", "unknown"], ["--outcomes"], ["--case"], ["--case", "heading_0", "extra"]])
def test_cli_unknown_selectors_are_explicit_errors(tmp_path, args):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "review_nca8_visual.py"), *args],
                            cwd=tmp_path, capture_output=True, check=False)
    assert result.returncode == 2


def test_cli_rejects_failed_inspection_instead_of_printing_a_success_exit(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("review_nca8_visual_test", ROOT / "scripts" / "review_nca8_visual.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failed = replace(demo.run_visual_preview_v1(), durable_unchanged=False)
    monkeypatch.setattr(module, "run_visual_preview_v1", lambda _case: failed)
    assert module.main(["--case", "heading_0"]) == 1
    assert "durable unchanged=False" in capsys.readouterr().out
