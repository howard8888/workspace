"""Real maternal mismatch allocation, independent protection and neutral menu/export."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import cca8_run
import nca8_menu
import nca8_maternal_attention_demo as demo
from nca8_maternal_attention import MaternalOutcomeAttentionV1
from nca8_runtime import Nca8SessionV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_maternal_attention_v1(case) for case in demo.MATERNAL_ATTENTION_CASES_V1}


@pytest.mark.parametrize("case", demo.MATERNAL_ATTENTION_CASES_V1)
def test_every_live_profile_has_fixed_physical_horizon_owner_bounds_and_no_learning(results, case):
    result = results[case]
    ticks = 160 if case.startswith("stand_") else 80
    assert result.metrics()["physical_ticks"] == ticks
    assert result.metrics()["focal_opportunities"] == ticks // 4 + 1
    assert result.cycles[-1].calculation.cutoff_tick == ticks
    assert not result.bound_violations and result.durable_unchanged
    assert result.metrics()["durable_learning_updates"] == 0
    assert result.as_dict()["restores_motor_permission"] is False
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("prefix", ["competing", "maintain"])
def test_only_outcome_route_changes_focal_winner_with_all_nonoutcome_inputs_fixed(results, prefix):
    on, off = results[prefix + "_on"], results[prefix + "_off"]
    left, right = on.cycles[5], off.cycles[5]
    assert left.calculation.cutoff_tick == right.calculation.cutoff_tick == 20
    assert on.physical_samples[:20] == off.physical_samples[:20]
    assert on.local_steps[:20] == off.local_steps[:20]
    assert left.calculation.source == right.calculation.source
    assert left.visual_source == right.visual_source and left.maternal_source == right.maternal_source
    assert left.maternal_task == right.maternal_task
    assert left.local_reports == right.local_reports and left.local_events == right.local_events
    assert left.maternal_correspondence.outcomes == right.maternal_correspondence.outcomes
    assert left.calculation.attention.selected_bid.candidate_id == "maternal:target_candidate"
    assert right.calculation.attention.selected_bid.candidate_id == "visual:scene_candidate"
    assert left.calculation.attention.disposition.value == ("maintain" if prefix == "maintain" else "switch")
    bid = left.maternal_attention.source_bid
    assert bid.priority_components[:2] == (0, 10)
    assert bid.prediction_or_envelope_failure_rank == 40
    # This contrast establishes source/focal allocation, not a fabricated survival benefit.
    assert on.physical_samples == off.physical_samples
    assert on.metrics()["first_proximity_completion_tick"] == off.metrics()["first_proximity_completion_tick"]


@pytest.mark.parametrize("case", demo.MATERNAL_ATTENTION_CASES_V1)
def test_interpretation_uses_existing_opportunity_without_new_pnm_ip_or_target(results, case):
    result = results[case]
    for focal in result.cycles:
        frame = focal.maternal_attention
        if frame is None or frame.allocation.kind != "interpretation":
            continue
        calc = focal.calculation
        assert calc.navigation.application is None and not calc.navigation.applicability_records
        assert focal.commitment.selected_primitive_id is None and focal.commitment.task_action is None
        assert focal.commitment.pnm_id is None and not focal.reservations
        assert focal.maternal_correspondence.registration is None and calc.proposal is None
        item = frame.allocation.interpretation
        assert item.current_source is focal.maternal_source
        assert item.working_id == calc.navigation.wnm.working_id
        assert item.request.outcome.claim.preview.pnm.created_cycle < calc.cycle_id
        assert item.request.outcome.evidence.available_tick <= calc.cutoff_tick
        assert item.as_dict()["demanding_allocations"] == 1
        assert item.as_dict()["causal_credit"] == "not_established"


def test_response_is_reconsidered_at_next_existing_slot_and_uses_current_geometry(results):
    focal = results["competing_on"].cycles[6]
    assert focal.calculation.cutoff_tick == 24
    assert focal.maternal_attention.allocation.kind == "response_reconsideration"
    app = focal.calculation.navigation.application
    assert app.primitive_id == "ip:follow_mom" and app.projection.basis is focal.maternal_source
    assert focal.reservations[0].current.committed_tick == 24
    assert focal.maternal_attention.allocation.interpretation.cycle_id < focal.calculation.cycle_id


def test_missing_current_relevance_is_not_replaced_by_original_endpoint(results):
    result = results["unresolved_current"]
    focal = result.cycles[5]
    item = focal.maternal_attention.allocation.interpretation
    assert item.request.outcome.status == "mismatch" and item.request.outcome.evidence.event_tick == 16
    assert not item.current_source.visual.evidence_current and not item.current_source.action_localized
    assert item.status == "unresolved_current_relevance"
    assert result.metrics()["response_reconsideration_ticks"] == []
    assert any("expired_or_invalidated" in reason for _, reason, _ in result.dispositions)
    assert result.metrics()["first_proximity_completion_tick"] is None


def test_unresolved_dependency_blocks_only_its_source_until_original_expiry(results):
    item = results["unresolved_current"].cycles[5]
    request = item.maternal_attention.created[0]
    route = MaternalOutcomeAttentionV1(item.maternal_source.stream, item.maternal_source.seed)
    earlier = results["unresolved_current"].cycles[3]
    route.admit(earlier.maternal_correspondence.outcomes, earlier.maternal_source, earlier.maternal_task.task, cutoff_tick=12)
    route.admit((request.outcome,), item.maternal_source, item.maternal_task.task, cutoff_tick=20)
    first = route.allocate(item.calculation.navigation.wnm, cycle_id=6)
    assert first.interpretation.status == "unresolved_current_relevance"
    # One later focal read with no new acquisition, still inside the eight-tick retention.
    source = replace(item.maternal_source, uncertainty_radius=(21 - item.maternal_source.last_supported_tick) * 0.025,
                     visual=replace(item.maternal_source.visual, applied_cycle=7, cutoff_tick=21))
    route.admit((), source, item.maternal_task.task, cutoff_tick=21)
    working = replace(item.calculation.navigation.wnm, refreshed_cycle=7, focus_age=7, primary_source_state=source)
    held = route.allocate(working, cycle_id=7)
    assert held.kind == "dependent_unresolved" and not held.permits_primitive_selection
    assert held.interpretation.request.expires_at_tick == 28


def test_stronger_task_need_can_win_and_request_expires_instead_of_forcing_focus(results):
    result = results["request_expiry"]
    assert result.metrics()["request_ticks"] == [20]
    assert result.metrics()["interpretation_ticks"] == []
    assert result.cycles[5].calculation.attention.selected_bid.candidate_id == "visual:scene_candidate"
    assert any(reason == "expired_uninterpreted" and tick == 28 for _, reason, tick in result.dispositions)
    assert not result.cycles[7].maternal_attention.pending


def test_local_protection_stops_movement_before_next_focal_response(results):
    result = results["support_loss"]
    assert result.cycles[5].maternal_attention.allocation.kind == "interpretation"
    interrupted = [(step.tick, report.reason) for step in result.local_steps for report in step.reports
                   if report.reason == "unexpected_contact_loss"]
    assert interrupted and min(tick for tick, _ in interrupted) == 22
    assert result.local_steps[22].command is None
    assert result.cycles[6].calculation.cutoff_tick == 24
    assert result.cycles[6].commitment.selected_primitive_id is None
    assert result.metrics()["first_proximity_completion_tick"] is None


@pytest.mark.parametrize("case", ["nominal_on", "nominal_off", "routine_once", "comparison_off"])
def test_no_false_escalation_for_matches_single_minor_or_disabled_comparison(results, case):
    assert results[case].metrics()["request_ticks"] == []
    assert results[case].metrics()["interpretation_ticks"] == []


def test_continuous_stand_follow_remains_bounded_with_independent_outcome_consumers(results):
    assert results["stand_follow"].metrics()["first_proximity_completion_tick"] == 104
    drift = results["stand_drift"]
    assert drift.metrics()["interpretation_ticks"] == [60]
    assert drift.metrics()["response_reconsideration_ticks"] == [64]
    assert drift.metrics()["first_proximity_completion_tick"] == 104
    focal = drift.cycles[15]
    assert focal.calculation.task.status == "completed"
    assert focal.maternal_attention.created[0].outcome.claim.preview.pnm.primitive_id == "ip:follow_mom"
    assert focal.claim_outcomes == ()


@pytest.mark.parametrize("case", ["competing_on", "unresolved_current", "stand_drift"])
def test_trace_truncation_does_not_change_complete_cognitive_results(results, case):
    small = demo.run_maternal_attention_v1(case, trace_capacity=1)
    left, right = small.as_dict(), results[case].as_dict()
    for data in (left, right):
        data["peak_owner_counts"].pop("focal_trace")
        data["peak_owner_counts"].pop("lower_trace")
    assert left == right


def test_diagnostic_disposition_capacity_is_not_cognitive_memory(results):
    ordinary = results["competing_on"]
    trial = demo.create_maternal_attention_trial_v1("competing_on")
    trial.core.maternal._outcome_attention = MaternalOutcomeAttentionV1(trial.latest_feedback.stream, trial.core.maternal._seed,
                                                                      diagnostic_capacity=1)
    cycles = []
    for tick in range(81):
        if tick % 4 == 0:
            cycles.append(trial.focal_step(visual_bid_priority=demo._visual_priority("competing_on", tick)))
        if tick < 80: trial.advance_lower()
    assert [item.as_dict() for item in cycles] == [item.as_dict() for item in ordinary.cycles]
    assert len(trial.core.maternal.outcome_attention.dispositions()) <= 1


def test_reset_discards_old_pending_claim_and_permissions(results):
    trial = demo.create_maternal_attention_trial_v1("request_expiry")
    for tick in range(21):
        if tick % 4 == 0: trial.focal_step(visual_bid_priority=demo._visual_priority("request_expiry", tick))
        if tick < 20: trial.advance_lower()
    old = trial.core.maternal.outcome_attention
    assert old.pending()
    trial.reset()
    new = trial.core.maternal.outcome_attention
    assert new is not old and new.stream.generation == old.stream.generation + 1
    assert not new.pending() and not new.dispositions()
    assert trial.controller.installation_count == trial.handoff_consumptions == trial.tick == 0
    assert trial.focal_step().maternal_attention.created == ()


def test_menu_and_render_are_read_only_for_existing_a0_session(monkeypatch, capsys, results):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    choices = iter(("12", "1", "", ""))
    monkeypatch.setattr(nca8_menu.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert "P16-2B-D MATERNAL OUTCOME -> ATTENTION | competing_on" in output
    assert "P16-2B-D MATERNAL OUTCOME -> ATTENTION | competing_off" in output
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before
    data = results["competing_on"].as_dict()
    demo.render_maternal_attention_v1(results["competing_on"], detail=True)
    assert results["competing_on"].as_dict() == data


@pytest.mark.parametrize("bad", [None, True, 1, "unknown", "", []])
def test_bad_case_refused(bad):
    with pytest.raises(ValueError): demo.create_maternal_attention_trial_v1(bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes"])
def test_detail_is_boolean(results, bad):
    with pytest.raises(TypeError): demo.render_maternal_attention_v1(results["competing_on"], detail=bad)


def test_review_script_matches_function_from_another_directory(tmp_path, results):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), "--outcome-attention",
                             "competing_on", "--json"], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(json.dumps([results["competing_on"].as_dict()]))


def test_new_registry_is_complete_without_extra_behavioral_primitives():
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.38" and len(rows) == 112
    assert {"nca8_maternal_attention", "nca8_maternal_attention_demo"} <= {row[0] for row in rows}
    assert len(cca8_run.PRIMITIVES) == 8


@pytest.mark.parametrize("choice,expected", [("7", ("competing_on",)), ("8", ("unresolved_current", "support_loss"))])
def test_detailed_menu_delegates_to_shared_renderer(choice, expected, monkeypatch, capsys):
    calls = []
    choices = iter(("invalid", choice, ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(demo, "run_maternal_attention_v1", lambda case: calls.append(case) or case)
    monkeypatch.setattr(demo, "render_maternal_attention_v1", lambda result, detail=False: f"{result}:detail={detail}")
    demo.run_maternal_attention_menu_v1()
    output = capsys.readouterr().out
    assert tuple(calls) == expected and "Choose 1-8" in output
    assert output.count(":detail=True") == len(expected)


def test_disabled_navigation_does_not_perform_free_interpretation():
    from nca8_executive import NavigationRuntimeV1
    trial = demo.create_maternal_attention_trial_v1("competing_on")
    for tick in range(20):
        if tick % 4 == 0: trial.focal_step(visual_bid_priority=demo._visual_priority("competing_on", tick))
        trial.advance_lower()
    trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False)
    focal = trial.focal_step(visual_bid_priority=(10, 60))
    assert focal.maternal_attention.created
    assert focal.maternal_attention.allocation.kind == "navigation_disabled"
    assert focal.maternal_attention.allocation.interpretation is None
    assert focal.commitment.selected_primitive_id is None and not focal.reservations


def test_both_domain_routes_share_one_focal_allocation_without_extra_clock():
    from nca8_body_targets import BodyTranslationCapabilityV1
    from nca8_followmom import FollowMomProfileV1
    from nca8_hierarchy import IntegratedRightingTrialV1
    from cca8_support_world import PlanarObjectV1, PlanarWorldProfileV1
    trial = IntegratedRightingTrialV1(
        planar_profile=PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2., 1.)),)),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=True, outcome_attention_enabled=True),
        translation_capability=BodyTranslationCapabilityV1(), task_outcomes_enabled=True, task_outcome_attention_enabled=True,
        stand_follow_enabled=True, righting_target_inset_degrees=2.,
    )
    for tick in range(81):
        if tick % 4 == 0:
            focal = trial.focal_step()
            allocations = (focal.calculation.outcome_allocation, focal.calculation.maternal_outcome_allocation)
            assert sum(item is not None and item.kind == "interpretation" for item in allocations) <= 1
            if any(item is not None and not item.permits_primitive_selection for item in allocations):
                assert focal.commitment.selected_primitive_id is None
        if tick < 80: trial.advance_lower()
    assert trial.tick == 80 and trial.handoff_consumptions == 21
