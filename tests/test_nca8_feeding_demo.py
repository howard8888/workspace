"""Live source-access causal controls; same hierarchy, no oral authority or learning."""
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import cca8_run
import nca8_feeding_demo as demo
import nca8_menu
from cca8_motor_contracts import MotorStreamRefV1
from nca8_feeding import FeedingDetailProfileV1
from nca8_hierarchy import IntegratedRightingCoreV1
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_feeding_detail_v1(case) for case in demo.FEEDING_DETAIL_CASES_V1}


def selected(cycle):
    source = cycle.calculation.attention.selected_source_state
    return None if source is None else source.source_map_ref.map_id


@pytest.mark.parametrize("case", demo.FEEDING_DETAIL_CASES_V1)
def test_all_cases_have_complete_finite_real_runs_honest_bounds_and_no_learning(results, case):
    result = results[case]
    assert result.review_status == "PASS" and len(result.cycles) == 41 and len(result.local_steps) == 160
    assert len(result.physical_samples) == 161 and result.durable_unchanged and not result.bound_violations
    assert result.metrics()["elapsed_seconds"] == 8.0 and result.handoff_consumptions == 41
    assert dict(result.peak_counts)["feeding_detail_durable_maps"] == 1
    assert dict(result.peak_counts)["feeding_detail_current_configurations"] == 1
    for cycle in result.cycles:
        source = cycle.feeding_detail_source
        assert source.maternal is cycle.maternal_source and source.maternal.visual is cycle.visual_source
        assert source.applied_cycle == cycle.scheduler.cycle_id
        assert source.maternal.visual.event_tick <= cycle.calculation.cutoff_tick
        assert cycle.commitment.selected_primitive_id in {None, "ip:righting", "ip:follow_mom"}
        if selected(cycle) == "feeding_detail":
            assert cycle.calculation.navigation.wnm.primary_source_state is source
            assert cycle.calculation.navigation.application is None
            assert cycle.calculation.proposal is None and not cycle.reservations
            assert cycle.commitment.task_action is cycle.commitment.pnm_id is None
            assert cycle.receipt.dispatch.motor.projection is None
            assert cycle.status == "feeding_detail_selected_no_task_implementation"
        assert cycle.as_dict()["feeding_learning_status"] == "unimplemented_no_participation"
    exported = result.as_dict()
    assert exported["B99"] == "open" and exported["restores_motor_permission"] is False
    json.dumps(exported, allow_nan=False)


def test_nominal_transition_is_observed_before_proximity_completion_not_ordered_by_it(results):
    result = results["nominal"]
    assert result.metrics()["first_localized_detail_tick"] == result.metrics()["first_feeding_detail_focus_tick"] == 96
    assert result.metrics()["maternal_proximity_completed_tick"] == 104
    before, current = result.cycles[23:25]
    assert before.calculation.cutoff_tick == 92 and before.feeding_detail_source.detail_position is None
    assert current.visual_source.event_tick == 95 and selected(current) == "feeding_detail"
    assert current.maternal_task.task.status != "completed"
    assert current.feeding_detail_source.parent_distance == pytest.approx(.18)
    assert current.feeding_detail_source.self_distance < .4
    assert all(c.calculation.source.source_map_ref.map_id == "posture_support" for c in result.cycles)


@pytest.mark.parametrize("control", ["attention_off", "no_feeding_need"])
def test_route_and_need_ablation_changes_actual_focus_not_sensation_or_movement(results, control):
    on, off = results["nominal"], results[control]
    assert on.physical_samples == off.physical_samples and on.local_steps == off.local_steps
    assert on.target_installations == off.target_installations == 14
    for current, counterfactual in zip(on.cycles, off.cycles):
        assert current.visual_source == counterfactual.visual_source
        assert current.maternal_source == counterfactual.maternal_source
        assert current.feeding_detail_source == counterfactual.feeding_detail_source
        assert current.maternal_task == counterfactual.maternal_task
        assert current.commitment.selected_primitive_id == counterfactual.commitment.selected_primitive_id
    assert selected(on.cycles[24]) == "feeding_detail" and selected(off.cycles[24]) == "maternal_target"
    assert off.cycles[24].feeding_detail_source.focal_accessible
    assert off.metrics()["first_feeding_detail_focus_tick"] is None
    assert on.metrics()["maternal_proximity_completed_tick"] == off.metrics()["maternal_proximity_completed_tick"]


def test_disabled_source_preserves_actual_visual_and_maternal_evidence(results):
    on, off = results["nominal"], results["source_off"]
    assert on.local_steps == off.local_steps and on.physical_samples == off.physical_samples
    assert on.cycles[24].visual_source == off.cycles[24].visual_source
    assert len(off.cycles[24].visual_source.guidance) == 2
    assert off.cycles[24].feeding_detail_source.association_status == "disabled"
    assert selected(off.cycles[24]) == "maternal_target"


@pytest.mark.parametrize("case,status,tick", [
    ("missing_detail", "detail_unrecognized", 96), ("wrong_category", "detail_category_contradicted", 96),
    ("wrong_detail_seed", "detail_unrecognized", 96), ("wrong_parent_seed", "parent_seed_mismatch", 96),
    ("incompatible_part", "part_geometry_contradicted", 72),
])
def test_invalid_part_conditions_withhold_access_without_repairing_source(results, case, status, tick):
    result = results[case]
    source = result.cycles[tick // 4].feeding_detail_source
    assert source.association_status == status
    assert result.metrics()["first_feeding_detail_focus_tick"] is None
    assert result.local_steps == results["nominal"].local_steps
    if case in {"wrong_category", "incompatible_part", "wrong_parent_seed"}:
        assert source.detail_position is not None  # Located does not mean accepted part association.


@pytest.mark.parametrize("case,gaps,resumption", [("brief_gap", (120,), 124), ("prolonged_gap", (120, 124, 128, 132), 136)])
def test_visual_gaps_clear_precise_detail_and_new_evidence_restores_it(results, case, gaps, resumption):
    result = results[case]
    old = result.cycles[29].feeding_detail_source
    for tick in gaps:
        cycle = result.cycles[tick // 4]
        assert cycle.feeding_detail_source.association_status == "visual_unavailable"
        assert cycle.feeding_detail_source.detail_position is None
        assert selected(cycle) != "feeding_detail"
        assert cycle.visual_source.event_tick == old.maternal.visual.event_tick
    fresh = result.cycles[resumption // 4]
    assert selected(fresh) == "feeding_detail" and fresh.visual_source.event_tick == resumption - 1
    assert old.detail_position is not None and old.cutoff_tick == 116
    assert result.local_steps == results["nominal"].local_steps  # No oral task to resume or renew.


def test_new_source_does_not_create_motor_permission_from_unsupported_body(results):
    result = results["support_loss"]
    assert result.local_steps[119].feedback.support_contact is False
    assert result.cycles[30].feeding_detail_source.focal_accessible  # Representation need not be deleted by body danger.
    assert all(step.command is None for step in result.local_steps[117:])
    assert not any(c.reservations for c in result.cycles[30:])
    assert result.metrics()["feeding_task_applications"] == 0
    # The earlier Righting episode stays terminal. This case does not claim a fresh recovery task or safe rest.
    assert result.cycles[30].task_outcome.status == "completed"


def test_real_current_righting_need_wins_over_visible_detail_without_deleting_it(results, monkeypatch):
    result = results["support_competition"]
    trial = demo.create_feeding_detail_trial_v1("support_competition")
    bids = []
    original = trial.core.cognition.attention.build_bid

    def capture(candidate, *, cycle_id):
        bid = original(candidate, cycle_id=cycle_id)
        bids.append(bid)
        return bid

    monkeypatch.setattr(trial.core.cognition.attention, "build_bid", capture)
    first = trial.focal_step()
    assert first.feeding_detail_source.focal_accessible and len(first.visual_source.guidance) == 2
    assert selected(first) == "posture_support" and first.commitment.selected_primitive_id == "ip:righting"
    feeding = next(b for b in bids if b.source_map_state.source_map_ref.map_id == "feeding_detail")
    winner = first.calculation.attention.selected_bid
    assert winner.new_task_need_rank > feeding.new_task_need_rank
    assert result.metrics()["first_feeding_detail_focus_tick"] > 0


def test_already_near_skips_unnecessary_task_history_and_focuses_detail_immediately(results):
    result = results["already_near"]
    assert result.metrics()["first_feeding_detail_focus_tick"] == 0
    assert result.target_installations == 0 and result.metrics()["maternal_proximity_completed_tick"] is None
    assert all(c.commitment.selected_primitive_id is None and c.maternal_task.task is None for c in result.cycles)
    assert all(s.command is None for s in result.local_steps)


def test_heading_changes_body_drives_not_part_scene_geometry(results):
    normal, rotated = results["nominal"], results["heading_90"]
    assert normal.metrics()["first_feeding_detail_focus_tick"] == rotated.metrics()["first_feeding_detail_focus_tick"]
    assert normal.cycles[24].feeding_detail_source.detail_position == rotated.cycles[24].feeding_detail_source.detail_position
    normal_drive = next(s.command.translation for s in normal.local_steps if s.command and s.command.translation)
    rotated_drive = next(s.command.translation for s in rotated.local_steps if s.command and s.command.translation)
    assert normal_drive != rotated_drive


@pytest.mark.parametrize("capacity", [1, 8, 256, 4096])
def test_trace_retention_rendering_export_and_rng_are_nonbehavioral(results, capacity):
    rng = random.getstate()
    current = demo.run_feeding_detail_v1("brief_gap", trace_capacity=capacity)
    expected = results["brief_gap"]
    assert current.cycles == expected.cycles and current.local_steps == expected.local_steps
    assert current.physical_samples == expected.physical_samples
    before = current.as_dict()
    for detail in (False, True):
        assert "Contact/latch/milk: NOT SUPPLIED" in demo.render_feeding_detail_v1(current, detail=detail)
    assert current.as_dict() == before and random.getstate() == rng
    before["feeding_profile"]["seed"]["detail_region_id"] = "invented"
    assert current.feeding_profile.seed.detail_region_id == "region_2"


def test_exact_replay_and_generation_reset_discard_old_current_source(results):
    assert demo.run_feeding_detail_v1().as_dict() == results["nominal"].as_dict()
    trial = demo.create_feeding_detail_trial_v1("already_near")
    initial = trial.focal_step()
    trial.reset()
    assert trial.core.feeding_detail.current is None and trial.tick == 0
    assert trial.core.feeding_detail.profile == FeedingDetailProfileV1()
    with pytest.raises(ValueError):
        trial.core.feeding_detail.update(initial.maternal_source)
    current = trial.focal_step()
    assert current.feeding_detail_source.stream.generation == initial.feeding_detail_source.stream.generation + 1
    assert selected(current) == "feeding_detail"


@pytest.mark.parametrize("change", [
    {"cycles": ()}, {"local_steps": ()}, {"physical_samples": ()}, {"durable_after": "changed"},
    {"peak_counts": (("unregistered_owner", 1),)}, {"peak_counts": (("feeding_detail_current_configurations", 2),)},
    {"handoff_consumptions": 0}, {"peak_counts": ()}, {"durable_before": "", "durable_after": ""},
])
def test_missing_or_failed_observer_evidence_cannot_pass(results, change):
    assert replace(results["nominal"], **change).review_status == "FAIL"


@pytest.mark.parametrize("bad", [None, True, 0, [], "typo", ""])
def test_invalid_case_is_rejected_before_trial_construction(bad):
    with pytest.raises(ValueError):
        demo.create_feeding_detail_trial_v1(bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes"])
def test_render_rejects_truthy_detail_switch(results, bad):
    with pytest.raises(TypeError):
        demo.render_feeding_detail_v1(results["nominal"], detail=bad)


def test_new_owner_requires_explicit_typed_profile_and_existing_maternal_seam():
    with pytest.raises(ValueError, match="maternal"):
        IntegratedRightingCoreV1(MotorStreamRefV1("missing_parent", 1), feeding_detail_profile=FeedingDetailProfileV1())
    with pytest.raises(TypeError):
        IntegratedRightingCoreV1(MotorStreamRefV1("invalid", 1), feeding_detail_profile=True)


def test_old_default_construction_has_no_feeding_owner_fields_or_source():
    from nca8_stand_follow_demo import create_stand_follow_trial_v1
    trial = create_stand_follow_trial_v1()
    first = trial.focal_step()
    assert trial.core.feeding_detail is None and first.feeding_detail_source is None
    assert not any("feeding" in key for key in first.as_dict())
    assert not any("feeding" in key for key in trial.snapshot())
    assert not any("feeding" in key for key in trial.retained_counts())


def test_menu_15_calls_shared_review_and_does_not_mutate_existing_session(monkeypatch, capsys):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    answers = iter(("15", "1", "", ""))
    monkeypatch.setattr(nca8_menu.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert "P16-2C-A / nominal / SOURCE-ACCESS REVIEW: PASS" in output
    assert "first feeding focus: 96" in output
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


def test_submenu_all_and_invalid_selection_use_common_renderer(monkeypatch, capsys, results):
    calls = []
    answers = iter(("invalid", "²", "Ⅳ", "９", "0", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(demo, "run_feeding_detail_v1", lambda case: calls.append(case) or results[case])
    demo.run_feeding_detail_menu_v1()
    assert calls == list(demo.FEEDING_DETAIL_CASES_V1)
    assert "Choose a displayed number" in capsys.readouterr().out


def test_script_json_matches_complete_common_result_and_unknown_case_fails(results):
    script = ROOT / "scripts" / "review_nca8_feeding.py"
    response = subprocess.run([sys.executable, str(script), "--case", "nominal", "--json"], cwd=ROOT.parent,
                              capture_output=True, text=True, check=False)
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout) == [json.loads(json.dumps(results["nominal"].as_dict()))]
    bad = subprocess.run([sys.executable, str(script), "--case", "typo"], cwd=ROOT.parent, capture_output=True, text=True, check=False)
    assert bad.returncode != 0


def test_source_slice_registry_is_truthful_without_changing_host_primitive_count():
    assert cca8_run.__version__ == "0.30.41" and len(cca8_run._cca8_component_rows()) == 115
    rows = str(cca8_run._cca8_component_rows())
    assert "nca8_feeding" in rows and "nca8_feeding_demo" in rows
