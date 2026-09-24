"""Full selected seeking: causal controls, authority timing and read-only review."""

import ast
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import cca8_run
import nca8_feeding_demo
import nca8_seek_nipple_demo as demo
from cca8_support_world import MotorWorldV1, PlanarDetailObjectV1
from nca8_handoff import Nca8MotorEnvelopeV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_runtime import Nca8SessionV1
from nca8_seek_nipple import SeekNippleApplicationV1, SeekNippleProfileV1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1

ROOT = Path(__file__).resolve().parents[1]
ORAL = SensorimotorTargetKindV1.ORAL_REACH


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_seek_nipple_v1(case) for case in demo.SEEK_NIPPLE_CASES_V1}


def selected(result):
    return tuple(c for c in result.cycles if isinstance(c.calculation.navigation.application, SeekNippleApplicationV1))


def commands(result):
    return tuple(s.command for s in result.local_steps)


def focal(result, tick):
    return next(c for c in result.cycles if c.calculation.cutoff_tick == tick)


@pytest.mark.parametrize("case", demo.SEEK_NIPPLE_CASES_V1)
def test_every_frozen_case_has_real_finite_evidence(results, case):
    result = results[case]
    assert result.review_status == "PASS", result.checks()
    assert len(result.checks()) == 14 and not result.bound_violations
    assert len(result.local_steps) == result.profile.horizon_ticks
    assert len(result.physical_samples) == result.profile.horizon_ticks + 1
    assert len(result.cycles) == result.profile.horizon_ticks // result.profile.cadence + 1
    export = json.loads(json.dumps(result.as_dict(), allow_nan=False))
    assert export["B99"] == "open" and export["feeding_learning"] == "unimplemented_no_participation"
    assert export["seeking_pnm_comparison"] == "deferred" and result.durable_before == result.durable_after


def test_actual_selection_precedes_installation_motion_contact_and_reach_proof(results):
    result = results["nominal"]
    first = result.cycles[0]
    app = first.calculation.navigation.application
    assert first.commitment.selected_primitive_id == "ip:seek_nipple"
    assert first.commitment.task_action == "SEEK_NIPPLE"
    assert app.projection is first.receipt.dispatch.motor.projection
    assert app.projection.basis is first.feeding_detail_source
    assert first.reservations[0].current.target.basis is first.feeding_detail_source.oral_feedback
    assert result.physical_samples[0].oral.extension_metres == 0
    assert result.metrics()["first_physical_touch_tick"] == 4
    assert result.metrics()["first_touch_consumption_tick"] == 5
    assert result.metrics()["first_reached_detail_tick"] == 12
    assert result.metrics()["seeking_applications"] == 1


def test_coordinate_reach_without_surface_does_not_imply_touch_latch_or_milk(results):
    present, absent = results["nominal"], results["no_surface"]
    assert commands(present) == commands(absent)
    assert [p.oral.extension_metres for p in present.physical_samples] == [p.oral.extension_metres for p in absent.physical_samples]
    assert absent.metrics()["final_task_status"] == "reached_detail" and absent.metrics()["first_physical_touch_tick"] is None
    assert absent.final_feedback.oral.contact is False and absent.metrics()["latch"] == "not_implemented"


@pytest.mark.parametrize("case", ["seek_off", "attention_off", "source_off", "no_need", "missing_detail", "wrong_category",
                                  "missing_touch", "missing_reach"])
def test_no_eligible_selected_operation_never_emits_oral_drives(results, case):
    result = results[case]
    assert not selected(result) and not result.installations
    assert all(s.command is None or s.command.oral_drive in (None, 0.0) for s in result.local_steps)
    assert result.metrics()["final_task_status"] == "no_task"


def test_task_off_preserves_source_and_focal_choice_while_attention_off_preserves_only_sensing(results):
    nominal, task_off, attention_off = (focal(results[c], 0) for c in ("nominal", "seek_off", "attention_off"))
    assert nominal.feeding_detail_source == task_off.feeding_detail_source == attention_off.feeding_detail_source
    assert task_off.calculation.attention.selected_source_state is task_off.feeding_detail_source
    assert attention_off.calculation.attention.selected_source_state is not attention_off.feeding_detail_source


@pytest.mark.parametrize("case,reason", [("no_capability", "capability_unavailable"), ("heading_90", "oral_target_off_axis"),
                                        ("out_of_reach", "oral_target_out_of_reach")])
def test_bodymap_refusal_preserves_selected_task_prediction_but_no_movement(results, case, reason):
    result = results[case]
    assert len(selected(result)) == 12 and result.metrics()["final_task_status"] == "budget_exhausted"
    assert all(c.calculation.proposal.withheld == ((ORAL, reason),) for c in selected(result))
    assert result.installations == 0 and result.metrics()["oral_commands"] == 0


def test_rotating_scene_with_body_is_different_from_rotating_body_alone(results):
    assert commands(results["nominal"]) == commands(results["rotated_scene"])
    assert results["rotated_scene"].metrics()["first_reached_detail_tick"] == 12
    assert results["heading_90"].metrics()["first_reached_detail_tick"] is None


def test_two_contributions_keep_one_task_and_do_not_rebase_old_targets(results):
    result = results["intermediate_target"]
    first, second = selected(result)
    a, b = first.reservations[0].current, second.reservations[0].current
    assert a.target.origin.task_id == b.target.origin.task_id
    assert a.target.origin.application_id != b.target.origin.application_id
    assert a.target.endpoint == pytest.approx(0.15) and b.target.endpoint == pytest.approx(0.3)
    assert a.target.basis.oral.extension_metres == 0 and b.target.basis.oral.extension_metres == pytest.approx(0.15)
    assert second.calculation.navigation.application.projection.scene_target == first.calculation.navigation.application.projection.scene_target
    assert result.metrics()["first_reached_detail_tick"] == 20


def test_brief_gap_revokes_old_exact_pursuit_and_resumes_same_task_from_new_sensing(results):
    result = results["brief_gap"]
    gap = focal(result, 4)
    assert gap.receipt.dispatch.motor.cancel_previous and gap.feeding_detail_source.mouth_position is None
    assert all(s.command is None for s in result.local_steps[4:8])
    a, b, c = selected(result)
    assert len({x.calculation.navigation.application.task.task_id for x in (a, b, c)}) == 1
    assert b.calculation.navigation.application.projection.basis.maternal.visual.event_tick == 7
    assert b.reservations[0].current.target.basis.oral.extension_metres == pytest.approx(0.1)
    assert result.metrics()["first_reached_detail_tick"] == 24


def test_long_gap_terminates_without_restarting_when_detail_returns(results):
    result = results["prolonged_gap"]
    assert len(selected(result)) == 1 and result.metrics()["final_task_status"] == "target_unavailable"
    assert focal(result, 20).feeding_detail_source.focal_accessible
    assert all(s.command is None for s in result.local_steps[4:])
    assert focal(result, 20).seeking_task.task.task_id == focal(result, 0).seeking_task.task.task_id


def test_local_anchor_protection_precedes_new_selected_remapping(results):
    result = results["body_shift"]
    assert result.local_steps[3].command is None
    assert result.local_steps[3].reports[0].reason == "oral_body_anchor_changed"
    a, b = selected(result)
    assert b.calculation.cutoff_tick == 4 and b.reservations[0].current.target.endpoint == pytest.approx(0.09)
    assert a.reservations[0].current.target.endpoint == pytest.approx(0.1)
    assert b.reservations[0].current.target.basis.planar.position == pytest.approx((0.01, 0.0))
    assert result.metrics()["first_reached_detail_tick"] == 12


def test_new_body_turn_cannot_be_repaired_with_a_hidden_head_or_translation_action(results):
    result = results["body_turn"]
    assert result.local_steps[3].command is None
    assert all(s.command is None for s in result.local_steps[3:])
    assert result.metrics()["final_task_status"] == "budget_exhausted"
    assert all(c.calculation.proposal.withheld == ((ORAL, "oral_target_off_axis"),) for c in selected(result)[1:])


def test_missing_feedback_can_hide_actual_touch_but_not_create_a_task_success(results):
    result = results["dropout"]
    assert result.metrics()["first_physical_touch_tick"] == 4
    assert result.metrics()["first_delivered_touch_event"] is None
    assert result.metrics()["first_reached_detail_tick"] is None
    assert all(c.seeking_task.task is None or c.seeking_task.task.status != "reached_detail" for c in result.cycles)


def test_local_early_contact_stops_before_task_reads_it_and_is_not_a_latch(results):
    result = results["early_contact"]
    assert result.local_steps[3].command is None and result.local_steps[3].reports[0].reason == "oral_contact_before_target"
    assert focal(result, 4).seeking_task.task.status == "unexpected_contact"
    assert result.physical_samples[2].oral.contact is True and result.physical_samples[3].oral.contact is False
    assert all(s.command is None for s in result.local_steps[3:])


def test_support_loss_stops_local_execution_then_terminates_the_task(results):
    result = results["support_loss"]
    assert result.local_steps[3].command is None
    assert focal(result, 4).seeking_task.task.status == "support_interrupted"
    assert result.metrics()["first_reached_detail_tick"] is None


def test_prediction_registration_control_does_not_claim_unique_predictive_benefit(results):
    intact, off = results["nominal"], results["pnm_registration_off"]
    assert commands(intact) == commands(off) and intact.physical_samples == off.physical_samples
    assert intact.registered_pnm_cycles == (1,) and off.registered_pnm_cycles == ()
    assert selected(off)[0].receipt.dispatch.motor.projection is not None
    assert intact.metrics()["first_reached_detail_tick"] == off.metrics()["first_reached_detail_tick"]


def test_relevance_route_changes_allocation_without_changing_measurements_or_motor_lease(results):
    intact, off = results["competing_on"], results["influence_off"]
    for tick in (4, 12):
        a, b = focal(intact, tick), focal(off, tick)
        assert a.feeding_detail_source == b.feeding_detail_source
        assert a.calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
        assert b.calculation.attention.selected_source_state.source_map_ref.map_id == "visual_scene"
        assert not a.reservations and not b.reservations
    assert commands(intact) == commands(off) and intact.physical_samples == off.physical_samples


def test_cadence_controls_keep_physical_horizon_and_original_task_budget(results):
    fast, nominal, slow = (results[c] for c in ("cadence_1", "intermediate_target", "cadence_8"))
    assert all(len(r.local_steps) == 64 for r in (fast, nominal, slow))
    assert [len(r.cycles) for r in (fast, nominal, slow)] == [65, 17, 9]
    assert fast.metrics()["final_task_status"] == "budget_exhausted"
    assert fast.physical_samples[-1].oral.extension_metres == pytest.approx(0.25)
    assert nominal.metrics()["first_reached_detail_tick"] == 20 and slow.metrics()["first_reached_detail_tick"] == 24
    assert all(s.command is None for s in fast.local_steps[12:])


def test_continuous_run_has_no_reset_or_reached_mom_instruction(results):
    result = results["stand_follow"]
    assert result.metrics()["first_seeking_tick"] == 92 and result.metrics()["first_reached_detail_tick"] == 112
    assert {s.command.stream.generation for s in result.local_steps if s.command is not None} == {1}
    for cycle in selected(result):
        assert len(cycle.reservations) == 1 and cycle.reservations[0].current.target.kind is ORAL
        assert not cycle.seeking_task.movement_blocked
    assert all(not (s.command.oral_drive and (s.command.orientation_drive or s.command.extension_drive or s.command.translation))
               for s in result.local_steps if s.command is not None)
    assert any(c.commitment.selected_primitive_id == "ip:righting" for c in result.cycles)
    assert any(c.commitment.selected_primitive_id == "ip:follow_mom" for c in result.cycles)
    assert len({c.seeking_task.task.task_id for c in result.cycles if c.seeking_task.task is not None}) == 1
    assert all(c.learning_report is not None and c.maternal_learning_report is not None for c in result.cycles)


def test_continuous_controls_preserve_the_old_body_trajectory_without_invented_touch(results):
    full, off, dry = (results[c] for c in ("stand_follow", "stand_follow_seek_off", "stand_follow_no_surface"))
    assert [p.support for p in full.physical_samples] == [p.support for p in off.physical_samples]
    assert [p.planar for p in full.physical_samples] == [p.planar for p in off.physical_samples]
    assert commands(full) == commands(dry)
    assert dry.metrics()["final_task_status"] == "reached_detail" and dry.metrics()["first_physical_touch_tick"] is None
    assert off.metrics()["final_task_status"] == "no_task" and not off.metrics()["oral_commands"]


@pytest.mark.parametrize("case", ["nominal", "brief_gap", "dropout", "competing_on", "stand_follow"])
@pytest.mark.parametrize("capacity", [1, 8])
def test_trace_retention_changes_no_complete_causal_export(results, case, capacity):
    smaller = demo.run_seek_nipple_v1(case, trace_capacity=capacity)
    original = results[case]
    assert smaller.cycles == original.cycles and smaller.local_steps == original.local_steps
    assert smaller.physical_samples == original.physical_samples and smaller.durable_after == original.durable_after
    assert smaller.metrics() == original.metrics() and smaller.review_status == "PASS"


@pytest.mark.parametrize("change", [{"cycles": ()}, {"local_steps": ()}, {"physical_samples": ()}, {"peak_counts": ()},
                                    {"peak_counts": (("wnm", 2),)}, {"handoff_consumptions": 0}, {"installations": 0},
                                    {"registered_pnm_cycles": ()}, {"durable_before": ""}, {"durable_after": "changed"}])
def test_missing_or_tampered_review_cannot_pass(results, change):
    assert replace(results["nominal"], **change).review_status == "FAIL"


def test_duplicate_or_coerced_owner_counts_are_not_accepted(results):
    original = results["nominal"]
    assert replace(original, peak_counts=original.peak_counts + original.peak_counts).review_status == "FAIL"
    for value in (True, 1.0, "1", -1):
        counts = tuple((k, value if k == "wnm" else n) for k, n in original.peak_counts)
        assert replace(original, peak_counts=counts).review_status == "FAIL"


def test_readonly_rendering_and_detached_exports_never_rerun_or_change_rng(results, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("render attempted execution")
    monkeypatch.setattr(demo, "run_seek_nipple_v1", forbidden)
    result, rng = results["nominal"], random.getstate()
    before = result.as_dict()
    assert "SELECTED SEEKING" in demo.render_seek_nipple_v1(result)
    assert "lower tick" in demo.render_seek_nipple_v1(result, detail=True)
    exported = result.as_dict()
    exported["profile"]["horizon_ticks"] = 999
    assert result.as_dict() == before and random.getstate() == rng


@pytest.mark.parametrize("case", [None, True, 1, [], "", "NOMINAL", "typo"])
def test_unknown_selector_refused_before_trial(case, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("constructed world for invalid selector")
    monkeypatch.setattr(demo, "IntegratedRightingTrialV1", forbidden)
    with pytest.raises(ValueError):
        demo.run_seek_nipple_v1(case)


@pytest.mark.parametrize("value", [None, 0, 1, "yes"])
def test_detail_flag_requires_boolean(results, value):
    with pytest.raises(TypeError):
        demo.render_seek_nipple_v1(results["nominal"], detail=value)


@pytest.mark.parametrize("case", ["nominal", "no_surface", "dropout", "stand_follow"])
def test_cli_full_json_matches_shared_menu_result_outside_repository(results, case, tmp_path):
    output = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"), "--seek", "--case", case, "--json"],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert output.returncode == 0, output.stderr
    assert json.loads(output.stdout) == [json.loads(json.dumps(results[case].as_dict(), allow_nan=False))]


@pytest.mark.parametrize("args", [["--oral", "--seek"], ["--seek", "--case", "wrong_parent_seed"], ["--seek", "--case", "typo"]])
def test_cli_rejects_cross_family_or_unknown_choices(args):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_feeding.py"), *args], capture_output=True, text=True, check=False)
    assert result.returncode != 0


def test_menu_retains_results_and_detail_performs_no_new_movement(results, monkeypatch, capsys):
    choices = iter(("8", "bad", "1", "8", ""))
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    def run(case):
        calls.append(case)
        return results[case]
    monkeypatch.setattr(demo, "run_seek_nipple_v1", run)
    demo.run_seek_nipple_menu_v1()
    assert calls == ["nominal", "no_surface", "missing_touch"]
    assert "No completed results" in capsys.readouterr().out


def test_existing_feeding_menu_delegates_to_new_route_without_a_second_loop(monkeypatch):
    choices, calls = iter(("19", "")), []
    monkeypatch.setattr(nca8_feeding_demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(nca8_feeding_demo, "run_seek_nipple_menu_v1", lambda: calls.append("seek"))
    nca8_feeding_demo.run_feeding_detail_menu_v1()
    assert calls == ["seek"]


def test_registry_adds_task_and_observer_without_changing_host_primitive_count():
    assert cca8_run.__version__ == "0.30.40" and len(cca8_run._cca8_component_rows()) == 114
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_seek_nipple"] == "nca8_seek_nipple" and registry["nca8_seek_nipple_demo"] == "nca8_seek_nipple_demo"
    assert len(cca8_run.PRIMITIVES) == 8


def test_task_has_no_private_world_lower_driver_or_legacy_cognitive_import():
    tree = ast.parse((ROOT / "nca8_seek_nipple.py").read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not modules & {"cca8_support_world", "cca8_env", "nca8_hierarchy", "nca8_sensorimotor", "cca8_feeding"}
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"_world", "milestones", "reward", "observer_body", "observer_planar_body", "observer_oral_body"}


def test_receipt_cannot_be_replayed_to_install_or_move_twice():
    trial = demo.create_seek_nipple_trial_v1()
    cycle = trial.focal_step()
    before = trial.tick, trial.controller.installation_count, trial.observer_oral_body
    with pytest.raises((RuntimeError, ValueError)):
        trial.controller.install_authorized(cycle.receipt, at_tick=0)
    assert (trial.tick, trial.controller.installation_count, trial.observer_oral_body) == before


def test_reset_invalidates_old_task_body_feedback_and_permissions():
    trial = demo.create_seek_nipple_trial_v1()
    old = trial.focal_step()
    trial.advance_lower()
    task, source = trial.core.seek_nipple, trial.core.feeding_detail
    trial.reset()
    assert trial.tick == 0 and trial.observer_oral_body.extension_metres == 0
    assert trial.core.seek_nipple is not task and trial.core.feeding_detail is not source
    assert trial.core.seek_nipple.task is None and trial.core.cognition.stream.generation == 2
    assert trial.controller.installation_count == 0
    with pytest.raises((ValueError, RuntimeError)):
        trial.controller.install_authorized(old.receipt, at_tick=0)


def test_exception_after_possible_effect_stops_without_blind_retry(monkeypatch):
    trial = demo.create_seek_nipple_trial_v1()
    trial.focal_step()
    original, calls = MotorWorldV1.step, []
    def failing(world, command):
        calls.append(command)
        original(world, command)
        raise RuntimeError("after possible effect")
    monkeypatch.setattr(MotorWorldV1, "step", failing)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1 and trial.observer_oral_body.extension_metres == pytest.approx(0.025)
    assert trial.stopped
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert len(calls) == 1


def test_nested_menu_preserves_unrelated_a0_session_and_rng(monkeypatch, capsys):
    import nca8_menu
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    answers = iter(("15", "19", "1", "8", "", "", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert capsys.readouterr().out.count("P16-2C-C / nominal / SELECTED SEEKING REVIEW: PASS") == 2
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


@pytest.mark.parametrize("capacity", [0, 4097, True, 1.5, "8"])
def test_retention_is_bounded_not_coerced(capacity):
    with pytest.raises((TypeError, ValueError)):
        demo.create_seek_nipple_trial_v1(trace_capacity=capacity)


def test_current_mouth_already_at_detail_does_not_start_a_task(monkeypatch):
    original = demo.seek_nipple_profile_v1("nominal")
    objects = tuple(PlanarDetailObjectV1("region_2", (0.0, 0.0)) if obj.region_id == "region_2" else obj
                    for obj in original.planar.objects)
    changed = replace(original, planar=replace(original.planar, objects=objects))
    monkeypatch.setattr(demo, "seek_nipple_profile_v1", lambda case="nominal": changed)
    trial = demo.create_seek_nipple_trial_v1()
    cycle = trial.focal_step()
    assert cycle.seeking_task.reason == "already_at_detail_no_task"
    assert cycle.seeking_task.task is None and not cycle.reservations
    assert trial.advance_lower().command is None


def test_pnm_basis_does_not_change_after_actual_body_movement(results):
    result = results["intermediate_target"]
    a, b = selected(result)
    first, second = (c.calculation.navigation.application.projection for c in (a, b))
    assert first.basis.oral_feedback.oral.extension_metres == 0
    assert second.basis.oral_feedback.oral.extension_metres == pytest.approx(0.15)
    assert first.predicted_mouth.x == pytest.approx(0.15)
    assert first.basis.detail_position == second.basis.detail_position
    assert first.pnm.application_id != second.pnm.application_id


def test_envelope_refuses_targets_without_prediction_or_beyond_its_horizon(results):
    envelope = selected(results["nominal"])[0].receipt.dispatch.motor
    with pytest.raises(ValueError):
        replace(envelope, projection=None)
    with pytest.raises(ValueError):
        replace(envelope, projection=replace(envelope.projection, horizon_ticks=4))
    assert envelope.targets[0].expires_at_tick == 8


@pytest.mark.parametrize("wrong", ["foreign_task", "fixture_origin", "no_replace"])
def test_oral_replacement_cannot_erase_foreign_or_unreviewed_rights(wrong):
    trial = demo.create_seek_nipple_trial_v1()
    first = trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    current = trial.focal_step()
    request = first.calculation.navigation.application.contribution
    origin = replace(request.origin, task_id="foreign_task" if wrong == "foreign_task" else request.origin.task_id,
                     application_id="new_application", envelope_id="new_envelope")
    request = replace(request, origin=origin, origin_status="supplied_requirement_fixture" if wrong == "fixture_origin" else "selected_seek_nipple")
    mapper = trial.core.cognition.mapper
    before = mapper.reservations(at_tick=4)
    proposal = mapper.propose_oral_reach(request, current.feeding_detail_source, at_tick=4, replace_existing=wrong != "no_replace")
    assert not proposal.bindings and not proposal.replaces
    assert mapper.reservations(at_tick=4) == before


def test_same_task_replacement_is_explicit_and_preserves_old_immutable_target():
    trial = demo.create_seek_nipple_trial_v1()
    first = trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    current = trial.focal_step()
    request = first.calculation.navigation.application.contribution
    request = replace(request, origin=replace(request.origin, application_id="new_application", envelope_id="new_envelope"))
    mapper = trial.core.cognition.mapper
    proposal = mapper.propose_oral_reach(request, current.feeding_detail_source, at_tick=4, replace_existing=True)
    assert len(proposal.bindings) == len(proposal.replaces) == 1
    assert proposal.replaces[0].current is first.reservations[0].current
    assert proposal.bindings[0].target.basis is current.feeding_detail_source.oral_feedback
    assert first.reservations[0].current.target.basis.oral.extension_metres == 0


def test_three_available_scalar_families_are_not_three_live_targets():
    trial = demo.create_seek_nipple_trial_v1("stand_follow")
    first = trial.focal_step()
    assert len(first.reservations) <= 2
    assert all(item.current.target.kind is not ORAL for item in first.reservations)
    assert first.seeking_task.task is None


def test_old_maternal_milestone_does_not_gate_initial_seek_and_old_rights_end_first(results):
    result = results["stand_follow"]
    at88, at92, at100 = (focal(result, t) for t in (88, 92, 100))
    assert at88.seeking_task.movement_blocked and not at88.reservations
    assert at92.maternal_task.task.status == "active" and at92.commitment.selected_primitive_id == "ip:seek_nipple"
    assert at100.maternal_task.task.status == "completed"
    assert all(s.command is None or s.command.translation is None for s in result.local_steps[92:])


def test_repeated_export_is_identical_and_interleaved_trials_share_no_state(results):
    first, other = demo.create_seek_nipple_trial_v1(), demo.create_seek_nipple_trial_v1("no_surface")
    before = other.snapshot(), other.observer_oral_body
    first.focal_step()
    first.advance_lower()
    assert (other.snapshot(), other.observer_oral_body) == before
    assert demo.run_seek_nipple_v1("nominal").as_dict() == results["nominal"].as_dict()
