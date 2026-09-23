"""Live same-hierarchy maternal correspondence, consumer controls and menu paths."""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_followmom_demo import (
    FOLLOW_MOM_CASES_V1, MATERNAL_OUTCOME_CASES_V1, create_follow_mom_trial_v1, run_follow_mom_v1, render_follow_mom_v1,
)
import nca8_followmom_demo as demo
from nca8_hierarchy import IntegratedRightingCoreV1, IntegratedRightingTrialV1
from nca8_maternal_outcomes import MaternalIntervalEvidenceV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: run_follow_mom_v1(case, outcomes_enabled=True) for case in MATERNAL_OUTCOME_CASES_V1}


def outcomes(result):
    return tuple(outcome for cycle in result.cycles for outcome in cycle.maternal_correspondence.outcomes)


@pytest.mark.parametrize("case", MATERNAL_OUTCOME_CASES_V1)
def test_every_live_profile_has_actual_bounds_unchanged_durable_state_and_finite_time(case, results):
    result = results[case]
    assert len(result.local_steps) == len(result.physical_samples) == 80
    assert result.as_dict()["elapsed_seconds"] == 4.0
    assert result.bound_violations == () and result.durable_unchanged
    assert result.as_dict()["durable_updates"] == 0
    assert all(c.maternal_correspondence.cutoff_tick == c.calculation.cutoff_tick for c in result.cycles)
    assert all(c.maternal_correspondence.as_dict()["attention_route"] == "not_implemented_for_maternal" for c in result.cycles)
    numbers = [o.number for o in outcomes(result)]
    assert numbers == sorted(set(numbers))
    assert all(not o.as_dict()["establishes_task_completion"] for o in outcomes(result))


@pytest.mark.parametrize("case", ["nominal", "brief_gap", "support_interruption", "narrowed", "mapping_reversed", "assisted", "competing_off"])
def test_consumer_enablement_changes_no_task_decision_command_or_physical_trajectory(case, results):
    off, on = run_follow_mom_v1(case), results[case]
    assert off.local_steps == on.local_steps and off.physical_samples == on.physical_samples
    assert [c.commitment for c in off.cycles] == [c.commitment for c in on.cycles]
    assert [c.maternal_source for c in off.cycles] == [c.maternal_source for c in on.cycles]
    assert [c.maternal_task.task for c in off.cycles] == [c.maternal_task.task for c in on.cycles]
    assert all(c.maternal_correspondence is None for c in off.cycles)


def test_nominal_old_endpoint_survives_new_application_and_does_not_complete_task(results):
    result = results["nominal"]
    first, at8, at12 = result.cycles[0], result.cycles[2], result.cycles[3]
    claim = first.maternal_correspondence.registration
    assert len(at8.maternal_correspondence.pending) == 2
    assert at8.maternal_correspondence.registration is not claim
    outcome = at12.maternal_correspondence.outcomes[0]
    assert outcome.claim is claim and outcome.status == "matched"
    assert outcome.evidence.event_tick == 8 and at12.maternal_source.event_tick == 11
    assert at12.maternal_task.task.status == "active"
    final_task = result.cycles[-1].maternal_task
    assert final_task.task.status == "completed"
    assert [x.event_tick for x in final_task.supported_samples] == [55, 59, 63]


def test_local_achievement_can_precede_a_real_task_forecast_mismatch(results):
    result = results["post_achievement_drift"]
    assert result.local_steps[6].reports[0].disposition.value == "achieved"
    outcome = outcomes(result)[0]
    assert outcome.status == "mismatch" and outcome.command_intervals == 5
    assert outcome.evidence.event_tick == 8 and outcome.evaluated_tick == 12
    assert dict(outcome.relations) == {"self_position": "mismatch", "maternal_anchor": "matched", "separation": "mismatch"}
    assert dict(outcome.residuals)["self_position"] == pytest.approx(0.06708203932499372)
    # This discrepancy actually moved the body closer; mismatch is not an aversive verdict.
    assert result.physical_samples[7].position[0] > outcome.claim.preview.predicted_self.x
    assert result.cycles[-1].maternal_task.task.status == "completed"


@pytest.mark.parametrize("left,right", [("nominal", "comparison_off"), ("post_achievement_drift", "drift_comparison_off")])
def test_comparison_off_preserves_registration_and_entire_motor_and_task_paths(left, right, results):
    on, off = results[left], results[right]
    assert on.local_steps == off.local_steps and on.physical_samples == off.physical_samples
    assert [x.commitment for x in on.cycles] == [x.commitment for x in off.cycles]
    assert [x.maternal_task for x in on.cycles] == [x.maternal_task for x in off.cycles]
    assert [x.maternal_source for x in on.cycles] == [x.maternal_source for x in off.cycles]
    assert [x.maternal_correspondence.registration for x in on.cycles] == [x.maternal_correspondence.registration for x in off.cycles]
    assert all(x.status == "comparison_disabled" for x in outcomes(off))


def test_narrowing_and_reversal_do_not_rewrite_original_projection(results):
    for case in ("narrowed_k8", "mapping_reversed"):
        result = results[case]
        first = result.cycles[0]
        claim = first.maternal_correspondence.registration
        target = first.reservations[0].current.target
        assert target.endpoint != (claim.preview.predicted_self.x, claim.preview.predicted_self.y)
        assert claim.unevaluable_relations == ("self_position", "separation")
        outcome = outcomes(result)[0]
        assert outcome.status == "partly_matched"
        assert dict(outcome.relations)["self_position"] == "unevaluable_authorization"
        assert dict(outcome.residuals)["self_position"] > 0.1
        assert not outcome.as_dict()["establishes_task_completion"]
    assert len(results["narrowed_k8"].cycles) == 11  # Disclosed K8 observation/control fixture, not the ordinary K4 run.


def test_replacing_narrowed_achieved_target_before_original_horizon_is_interruption(results):
    result = results["narrowed"]
    assert outcomes(result)[0].status == "interrupted"
    assert result.cycles[-1].maternal_task.task.status == "budget_exhausted"
    assert result.cycles[-1].maternal_source.separation == pytest.approx(0.48)


@pytest.mark.parametrize("case", ["support_interruption", "obstacle_contact", "motor_blocked", "cancelled", "delayed_feedback"])
def test_lower_or_task_interruption_is_not_scored_as_a_fully_executed_forecast(case, results):
    assert any(o.status == "interrupted" for o in outcomes(results[case]))
    assert all(o.status != "matched" for o in outcomes(results[case]) if o.evidence is None)


def test_gap_withholds_both_current_and_historical_visual_admission(results):
    result = results["brief_gap"]
    at12 = result.cycles[3]
    assert not at12.maternal_source.action_localized
    original = result.cycles[0].maternal_correspondence.registration
    original_outcome = next(o for o in outcomes(result) if o.claim is original)
    assert original_outcome.status == "expired_unresolved"
    assert original_outcome.evidence is None
    assert result.cycles[-1].maternal_task.task.status == "completed"


def test_final_unavailable_endpoint_remains_pending_at_physical_horizon(results):
    final = results["mapping_reversed"].cycles[-1].maternal_correspondence
    assert len(final.pending) == 1 and final.pending[0].due_tick == 80
    assert final.pending[0].expires_at_tick == 88
    assert final.cutoff_tick == 80


def test_veto_and_external_proximity_do_not_earn_execution_or_task_credit(results):
    veto = outcomes(results["veto"])
    assert len(veto) == 20 and all(x.status == "not_applied" and x.command_intervals == 0 for x in veto)
    assert not outcomes(results["assisted_no_task"])
    assert results["assisted_no_task"].cycles[-1].maternal_task.task is None
    assert results["assisted"].cycles[-1].maternal_task.task.status == "completed"
    assert all(x.as_dict()["causal_credit"] == "not_established" for x in outcomes(results["assisted"]))


def test_default_core_constructs_no_maternal_consumer_or_side_effect():
    trial = create_follow_mom_trial_v1("nominal")
    assert trial.core.maternal_outcomes is None
    first = trial.focal_step()
    assert first.maternal_correspondence is None
    assert "maternal_pending_claims" not in trial.retained_counts()
    assert "maternal_correspondence" not in first.as_dict()


def test_disabled_core_rejects_maternal_ingress_instead_of_silently_dropping_it():
    core = IntegratedRightingCoreV1(MotorStreamRefV1("test", 1))
    with pytest.raises(ValueError):
        core.run_cycle(None, cutoff_tick=0, maternal_intervals=(MaternalIntervalEvidenceV1(0, None, (), (), ()),))
    assert core.last_result is None


def test_overflow_stops_before_another_physical_interval():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    trial.focal_step()
    for _ in range(16):
        trial.advance_lower()
    position = trial.observer_planar_body
    with pytest.raises(OverflowError):
        trial.advance_lower()
    assert trial.stopped and trial.tick == 16 and trial.observer_planar_body == position
    assert trial.core.maternal_outcomes.history()[0].status == "unresolved_stopped"


def test_reset_closes_old_owner_and_clears_staged_evidence_and_permissions():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    trial.focal_step()
    for _ in range(3):
        trial.advance_lower()
    owner = trial.core.maternal_outcomes
    old_intervals = tuple(trial._maternal_intervals)
    trial.reset()
    assert trial.core.maternal_outcomes is not owner
    assert trial.retained_counts()["maternal_staged_intervals"] == 0
    assert trial.tick == 0 and not trial.core.maternal_outcomes.pending()
    assert not owner.pending()
    with pytest.raises(ValueError):
        owner.consume_intervals(old_intervals, cutoff_tick=3)
    with pytest.raises(ValueError):
        trial.core.maternal_outcomes.consume_intervals(old_intervals, cutoff_tick=3)


def test_frozen_endpoint_is_consumed_in_c2_before_new_selection():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True, trace_capacity=4096)
    for tick in range(12):
        if tick % 4 == 0:
            trial.focal_step()
        trial.advance_lower()
    at12 = trial.focal_step()
    assert at12.maternal_correspondence.outcomes[0].evaluated_tick == 12
    events = trial.core.trace.snapshot()
    related = [event for event in events if event.cycle_id == 4]
    names = [event.channel for event in related]
    assert names.index("hierarchy_maternal_outcome") < names.index("hierarchy_selection") < names.index("hierarchy_close")


@pytest.mark.parametrize("capacity", [1, 8, 256])
def test_rendering_and_trace_retention_do_not_drive_correspondence_or_movement(capacity, results):
    rng = random.getstate()
    result = run_follow_mom_v1("post_achievement_drift", outcomes_enabled=True, trace_capacity=capacity)
    baseline = results["post_achievement_drift"]
    assert result.local_steps == baseline.local_steps and result.physical_samples == baseline.physical_samples
    assert [c.maternal_correspondence for c in result.cycles] == [c.maternal_correspondence for c in baseline.cycles]
    before = result.as_dict()
    for detail in (False, True, False):
        assert "P16-2B-B" in render_follow_mom_v1(result, detail=detail)
    assert result.as_dict() == before and random.getstate() == rng


@pytest.mark.parametrize("args", [["--outcomes", "nominal"], ["--outcomes", "drift_comparison_off"], ["--outcomes", "veto"]])
def test_cli_json_is_the_same_complete_experiment_from_outside_repository(args, tmp_path):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), *args, "--json"],
                             cwd=tmp_path, capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    expected = [run_follow_mom_v1(args[1], outcomes_enabled=True).as_dict()]
    assert json.loads(process.stdout) == json.loads(json.dumps(expected))


@pytest.mark.parametrize("args", [["--outcomes", "bad"], ["--outcomes", "--case", "nominal"], ["--outcomes", "--replay"],
                                   ["--case", "comparison_off"]])
def test_cli_unknown_or_conflicting_families_are_not_silently_repaired(args):
    process = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), *args],
                             capture_output=True, text=True, check=False)
    assert process.returncode == 2


@pytest.mark.parametrize("choice,expected", [("2", ("nominal", "comparison_off", "post_achievement_drift", "drift_comparison_off")),
                                             ("7", ("nominal",))])
def test_menu_calls_shared_experiments_only_after_choice(monkeypatch, choice, expected):
    choices = iter([choice, ""])
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(demo, "run_follow_mom_v1", lambda case, **kw: calls.append((case, kw)) or case)
    monkeypatch.setattr(demo, "render_follow_mom_v1", lambda *_args, **_kw: "review")
    demo.run_maternal_outcome_menu_v1()
    assert [c for c, _ in calls] == list(expected)
    assert all(kw == {"outcomes_enabled": True} for _, kw in calls)


def test_open_and_return_performs_no_physics_or_source_mutation(monkeypatch):
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: "")
    monkeypatch.setattr(demo, "run_follow_mom_v1", lambda *_args, **_kw: pytest.fail("unexpected experiment"))
    demo.run_maternal_outcome_menu_v1()


def test_parent_menu_exposes_the_same_submenu_without_another_loop(monkeypatch):
    choices = iter(["10", ""])
    calls = []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(demo, "run_maternal_outcome_menu_v1", lambda: calls.append(True))
    demo.run_follow_mom_menu_v1()
    assert calls == [True]


def test_registry_adds_one_real_consumer_without_new_host_primitives():
    import cca8_run
    assert cca8_run.__version__ == "0.30.36"
    assert len(cca8_run._cca8_component_rows()) == 106 and len(cca8_run.PRIMITIVES) == 8
    assert dict(cca8_run._CCA8_COMPONENT_REGISTRY)["nca8_maternal_outcomes"] == "nca8_maternal_outcomes"


def test_domain_correspondence_has_no_world_or_executive_or_learning_authority():
    tree = ast.parse((ROOT / "nca8_maternal_outcomes.py").read_text())
    forbidden = {"observer_body", "observer_planar_body", "_world", "focal_step", "advance_lower", "install_authorized",
                 "commit", "select_source", "scenario_stage", "milestones", "evaluate_applicability", "apply"}
    assert not any(isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(tree))
    assert not any(isinstance(node, ast.ImportFrom) and node.module in {"cca8_support_world", "nca8_executive", "nca8_learning"}
                   for node in ast.walk(tree))


def test_original_visual_acquisition_uses_old_self_without_resampling_or_mutating_provider():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    original = trial.latest_feedback
    trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    provider = trial._world
    before = (provider.tick, provider.body, provider.planar_body, provider.observe())
    old_surface = provider.visual_surface(feedback=original)
    current_surface = provider.visual_surface()
    assert old_surface["anchor"] == {"entity": "self", "x": 0.0, "y": 0.0}
    assert current_surface["anchor"] != old_surface["anchor"]
    assert current_surface["objects"] == old_surface["objects"]
    old_surface["anchor"]["x"] = 100
    assert provider.visual_surface(feedback=original)["anchor"]["x"] == 0.0
    assert (provider.tick, provider.body, provider.planar_body, provider.observe()) == before


@pytest.mark.parametrize("kind", ["not_canonical", "foreign_stream", "foreign_generation", "future", "undelivered"])
def test_original_visual_product_rejects_foreign_or_unavailable_acquisition_without_effect(kind):
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    original = trial.latest_feedback
    provider = trial._world
    if kind == "not_canonical":
        bad = original.as_dict()
    elif kind == "foreign_stream":
        bad = replace(original, stream=MotorStreamRefV1("other", 1))
    elif kind == "foreign_generation":
        bad = replace(original, stream=MotorStreamRefV1(original.stream.stream_id, 2))
    elif kind == "future":
        bad = replace(original, sample_id=2, event_tick=1, available_tick=2)
    else:
        bad = replace(original, sample_id=2)
    before = (provider.tick, provider.body, provider.planar_body, provider.observe())
    with pytest.raises((ValueError, TypeError)):
        provider.visual_surface(feedback=bad)
    assert (provider.tick, provider.body, provider.planar_body, provider.observe()) == before


@pytest.mark.parametrize("after_effect", [False, True])
def test_physical_call_fault_never_retries_or_labels_unknown_effect_not_applied(monkeypatch, after_effect):
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    trial.focal_step()
    step = trial._world.step
    calls = []

    def fault(command):
        calls.append(command)
        if after_effect:
            step(command)
        raise RuntimeError("simulated uncertain physical call")

    monkeypatch.setattr(trial._world, "step", fault)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == int(after_effect) and trial.stopped
    assert trial.core.maternal_outcomes.history()[0].status == "unresolved_stopped"
    assert not trial.core.maternal_outcomes.pending()
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert len(calls) == 1


@pytest.mark.parametrize("after_install", [False, True])
def test_installation_fault_consumes_receipt_once_and_leaves_no_false_execution_verdict(monkeypatch, after_install):
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    install = trial.controller.install_authorized

    def fault(*args, **kwargs):
        if after_install:
            install(*args, **kwargs)
        raise RuntimeError("simulated uncertain installation")

    monkeypatch.setattr(trial.controller, "install_authorized", fault)
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert trial.handoff_consumptions == 1 and trial.stopped and trial.tick == 0
    owner = trial.core.maternal_outcomes
    assert not owner.pending() and owner.history()[0].status == "unresolved_stopped"
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert trial.handoff_consumptions == 1
