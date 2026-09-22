"""Live maternal F integration, causal neutrality, boundedness and menu/CLI proof."""
from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_menu
import nca8_maternal_learning_demo as demo
from nca8_contracts import CyclePhase
from nca8_learning_registry import learning_capabilities_v1
from nca8_maternal_learning import MaternalLearningHookV1
from nca8_runtime import Nca8SessionV1
from scripts import review_nca8_followmom as script

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_maternal_learning_v1(case) for case in demo.MATERNAL_LEARNING_CASES_V1}


def without_learning_metadata(focal):
    """Remove only the new no-learning report/label, preserving every cognitive datum."""
    value = focal.as_dict()
    value.pop("maternal_learning_reconciliation", None)
    for name in ("maternal_correspondence", "maternal_attention"):
        if name in value and value[name] is not None:
            value[name].pop("learning_route", None)
    return value


@pytest.mark.parametrize("case", demo.MATERNAL_LEARNING_CASES_V1)
def test_all_profiles_have_actual_finite_owner_bounds_and_no_durable_change(results, case):
    result = results[case]
    ticks = 160 if case.startswith("stand_") else 80
    stride = 1 if case == "fast_cadence" else 8 if case == "narrowed" else 4
    assert len(result.local_steps) == len(result.physical_samples) == ticks
    assert len(result.cycles) == ticks // stride + 1
    assert result.cycles[-1].calculation.cutoff_tick == ticks
    assert not result.bound_violations and result.durable_unchanged and result.fixed_configuration_unchanged
    assert result.metrics()["maternal_F_calls"] == (0 if case.endswith("_off") and case in {"nominal_off", "competing_off"} else len(result.cycles))
    assert result.metrics()["durable_learning_updates"] == 0
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("prefix", ["nominal", "competing"])
def test_only_the_hook_changes_with_identical_cognition_commands_sources_and_physics(results, prefix):
    on, off = results[prefix + "_on"], results[prefix + "_off"]
    assert on.physical_samples == off.physical_samples and on.local_steps == off.local_steps
    assert on.final_feedback == off.final_feedback and on.durable_after == off.durable_after
    assert [without_learning_metadata(item) for item in on.cycles] == [without_learning_metadata(item) for item in off.cycles]
    assert on.metrics()["proximity_completed_at_tick"] == off.metrics()["proximity_completed_at_tick"]
    assert any(item.maternal_learning_report.new_participation is not None for item in on.cycles)
    assert all(item.maternal_learning_report is None for item in off.cycles)


@pytest.mark.parametrize("case", demo.MATERNAL_LEARNING_CASES_V1)
def test_interpretation_is_existing_focal_work_not_a_new_ip_pnm_or_target(results, case):
    for focal in results[case].cycles:
        frame = focal.maternal_attention
        if frame is not None and frame.allocation.kind == "interpretation":
            assert focal.commitment.selected_primitive_id is None
            assert focal.commitment.pnm_id is None and not focal.reservations
            assert focal.maternal_correspondence.registration is None
            assert focal.calculation.navigation.application is None
            if focal.maternal_learning_report is not None:
                assert focal.maternal_learning_report.new_participation is None
                for item in focal.maternal_learning_report.dispositions:
                    if item.interpretation is not None:
                        assert item.interpretation is frame.allocation.interpretation
                        assert item.interpretation.cycle_id == focal.commitment.cycle_id


def test_competing_outcome_admission_follows_actual_interpretation_before_later_response(results):
    result = results["competing_on"]
    focal = result.cycles[5]
    assert focal.calculation.cutoff_tick == 20
    interpreted = focal.maternal_attention.allocation.interpretation
    accepted = [item for item in focal.maternal_learning_report.dispositions if item.status == "accepted_no_update"]
    assert len(accepted) == 1 and accepted[0].interpretation is interpreted
    assert result.metrics()["interpretation_ticks"] == [20] and result.metrics()["response_ticks"] == [24]
    assert result.metrics()["proximity_completed_at_tick"] == 68


def test_protected_delay_and_unresolved_current_expire_without_free_teaching(results):
    for case in ("protected_competitor", "unresolved_current"):
        result = results[case]
        focal = result.cycles[5]
        request, = focal.maternal_attention.created
        statuses = [item.status for later in result.cycles for item in later.maternal_learning_report.dispositions
                    if item.pnm_id == request.outcome.claim.preview.pnm.pnm_id]
        assert "pending_interpretation" in statuses and "eligibility_expired" in statuses
        assert "accepted_no_update" not in statuses
        assert result.cycles[6].calculation.cutoff_tick == 24 < request.expires_at_tick == 28
        if case == "unresolved_current":
            assert "pending_unresolved_interpretation" in statuses
            assert result.metrics()["response_ticks"] == []
        else:
            assert result.metrics()["interpretation_ticks"] == []


def test_disabled_attention_conservatively_holds_discrepancies_not_matches(results):
    result = results["attention_off"]
    assert not result.metrics()["interpretation_ticks"]
    accepted = [item for focal in result.cycles for item in focal.maternal_learning_report.dispositions if item.status == "accepted_no_update"]
    assert accepted and all(item.outcome.status != "mismatch" for item in accepted)
    assert result.metrics()["dispositions"]["eligibility_expired"] == 2


def test_comparison_off_never_creates_executed_teaching_but_keeps_movement(results):
    off, nominal = results["comparison_off"], results["nominal_on"]
    assert off.physical_samples == nominal.physical_samples
    assert off.local_steps == nominal.local_steps
    assert off.metrics()["new_participants"] == 0
    assert "accepted_no_update" not in off.metrics()["dispositions"]


def test_veto_and_assistance_are_not_false_executed_learning_success(results):
    veto = results["veto"]
    assert veto.metrics()["new_participants"] == veto.metrics()["command_intervals"] == 0
    assert set(veto.metrics()["dispositions"]) == {"not_applied"}
    no_task = results["assisted_no_task"]
    assert no_task.metrics()["new_participants"] == 0 and no_task.metrics()["maternal_final_status"] == "no_task"
    assert no_task.physical_samples[-1].position != no_task.physical_samples[0].position
    assisted = results["assisted"]
    assert assisted.metrics()["maternal_final_status"] == "completed"
    assert assisted.metrics()["causal_credit"] == "not_established_by_completion"


def test_faster_cadence_expires_four_cycle_eligibility_without_shortening_physical_claim(results):
    result = results["fast_cadence"]
    first = result.cycles[0].maternal_learning_report.new_participation
    expiry = result.cycles[4].maternal_learning_report
    assert first.expires_before_cycle == 5 and first.claim.due_tick == 8
    assert expiry.cycle_id == 5 and expiry.cutoff_tick == 4
    assert expiry.dispositions[0].status == "eligibility_expired"
    assert result.metrics()["dispositions"]["rejected_expired_eligibility"] > 0
    assert "accepted_no_update" not in result.metrics()["dispositions"]


def test_final_pending_is_not_cleared_by_fake_extra_physical_time(results):
    result = results["narrowed"]
    last = result.cycles[-1]
    assert last.calculation.cutoff_tick == len(result.local_steps) == 80
    assert len(last.maternal_learning_report.pending) == 1
    assert last.maternal_learning_report.pending[0].claim.due_tick == 80
    assert last.maternal_learning_report.pending[0].expires_before_cycle > last.commitment.cycle_id
    assert last.maternal_correspondence.pending


def test_local_support_protection_stops_before_next_focal_response(results):
    result = results["support_loss"]
    assert result.local_steps[20].command is not None
    assert result.local_steps[21].reports[0].disposition.value == "partial"
    assert result.local_steps[22].command is None
    assert result.local_steps[22].reports[0].reason == "unexpected_contact_loss"
    assert result.cycles[6].calculation.cutoff_tick == 24
    assert result.metrics()["maternal_final_status"] != "completed"


@pytest.mark.parametrize("case", ["stand_follow", "stand_drift"])
def test_two_original_recipients_share_one_f_checkpoint_and_keep_stand_follow_behavior(results, case):
    result = results[case]
    assert result.metrics()["righting_F_calls"] == result.metrics()["maternal_F_calls"] == 41
    assert result.metrics()["proximity_completed_at_tick"] == 104
    for focal in result.cycles:
        righting, maternal = focal.learning_report, focal.maternal_learning_report
        assert righting.cycle_id == maternal.cycle_id == focal.commitment.cycle_id
        assert righting.recipient_id != maternal.recipient_id
        assert not (righting.new_participation is not None and maternal.new_participation is not None)
        assert righting.as_dict()["durable_learning_updates"] == maternal.as_dict()["durable_learning_updates"] == 0
    if case == "stand_drift":
        assert result.metrics()["interpretation_ticks"] == [60] and result.metrics()["response_ticks"] == [64]


def test_actual_f_callback_is_after_handoff_before_close_installation_or_world_step(monkeypatch):
    trial = demo.create_maternal_learning_trial_v1("nominal_on")
    hook = trial.core.maternal.learning_hook
    reconcile = hook.reconcile
    calls = []

    def inspect(**kwargs):
        assert trial.core.scheduler._last_phase_value == int(CyclePhase.LEARNING_SCHEDULE)
        assert trial.core.handoff.has_pending_request
        assert trial.controller.installation_count == 0 and trial.tick == 0
        channels = [item.channel for item in trial.core.trace.snapshot()]
        assert "hierarchy_handoff" in channels and "hierarchy_close" not in channels
        assert kwargs["outcomes"] == ()
        calls.append(kwargs["cycle_id"])
        return reconcile(**kwargs)

    monkeypatch.setattr(hook, "reconcile", inspect)
    focal = trial.focal_step()
    assert calls == [1] and focal.maternal_learning_report.new_participation is not None
    assert trial.controller.installation_count == 1 and trial.tick == 0


@pytest.mark.parametrize("case", ["nominal_on", "stand_follow"])
def test_f_failure_stops_before_installation_or_physics_and_cannot_retry(monkeypatch, case):
    trial = demo.create_maternal_learning_trial_v1(case)
    hook = trial.core.maternal.learning_hook
    calls = []

    def fail(**_kwargs):
        calls.append(True)
        raise ValueError("injected maternal F failure")

    monkeypatch.setattr(hook, "reconcile", fail)
    with pytest.raises(ValueError, match="injected"):
        trial.focal_step()
    assert trial.stopped and trial.tick == 0 and trial.controller.installation_count == 0
    assert not trial.core.handoff.has_pending_request and not hook.pending()
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert calls == [True]


def test_reset_closes_old_source_eligibility_and_replaces_generation():
    trial = demo.create_maternal_learning_trial_v1("nominal_on")
    trial.focal_step()
    old = trial.core.maternal.learning_hook
    assert old.pending()
    trial.reset()
    new = trial.core.maternal.learning_hook
    assert new is not old and new.stream.generation != old.stream.generation
    assert not old.pending() and not new.pending()
    with pytest.raises(RuntimeError):
        old.reconcile(cycle_id=2, cutoff_tick=4)
    assert trial.focal_step().maternal_learning_report.new_participation is not None


@pytest.mark.parametrize("case", ["competing_on", "unresolved_current", "stand_drift"])
def test_trace_and_diagnostic_capacity_do_not_change_any_cognitive_or_physical_result(results, case):
    tiny = demo.run_maternal_learning_v1(case, trace_capacity=1, diagnostic_capacity=1)
    original = results[case]
    assert tiny.cycles == original.cycles
    assert tiny.local_steps == original.local_steps and tiny.physical_samples == original.physical_samples
    assert tiny.metrics() == original.metrics() and tiny.durable_after == original.durable_after
    assert dict(tiny.peak_counts)["maternal_learning_dispositions"] <= 1


@pytest.mark.parametrize("expired", [False, True])
def test_source_a_receives_historical_outcome_when_b_focal_and_a_unavailable(expired):
    records = demo.run_maternal_learning_routing_fixture_v1(expired=expired)
    first, last = records[0], records[-1]
    original = first.maternal_learning_report.new_participation
    assert last.calculation.attention.selected_bid.candidate_id == "fixture:competing_source"
    assert not last.maternal_source.focal_accessible
    assert last.maternal_source.target_position is None
    outcome, = last.maternal_correspondence.outcomes
    assert outcome.claim is original.claim and outcome.status == "matched"
    status, = last.maternal_learning_report.dispositions
    assert status.status == ("rejected_expired_eligibility" if expired else "accepted_no_update")
    assert last.maternal_learning_report.recipient_id == original.recipient_id
    if expired:
        expiry = records[-2]
        assert expiry.commitment.cycle_id == original.expires_before_cycle == 5
        assert expiry.maternal_correspondence.pending and not expiry.maternal_learning_report.pending
    assert "NO PHYSICAL WORLD STEPS" in demo.render_maternal_learning_routing_fixture_v1(records)


def test_readonly_render_export_and_inventory_do_not_change_rng_or_results(results):
    result = results["competing_on"]
    before = json.dumps(result.as_dict(), sort_keys=True)
    state = random.getstate()
    for detail in (False, True):
        assert "durable updates=0" in demo.render_maternal_learning_v1(result, detail=detail)
    result.as_dict()["cycles"].clear()
    cards = learning_capabilities_v1()
    card = next(item for item in cards if item.capability_id == "L12")
    assert "MaternalLearningHookV1.reconcile" in card.live_consumer
    assert len(cards) == 25 and card.maturity == "eligibility_only_no_durable_rule"
    assert random.getstate() == state and json.dumps(result.as_dict(), sort_keys=True) == before


@pytest.mark.parametrize("bad", [None, True, 1, "unknown", "", []])
def test_bad_profile_does_not_construct_a_trial(bad):
    with pytest.raises(ValueError):
        demo.create_maternal_learning_trial_v1(bad)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes"])
def test_render_detail_is_boolean(results, bad):
    with pytest.raises(TypeError):
        demo.render_maternal_learning_v1(results["nominal_on"], detail=bad)


def test_menu_open_or_ledger_does_not_run_trial(monkeypatch, capsys):
    def fail(*_args, **_kwargs):
        pytest.fail("no trial should be constructed")
    choices = iter(["8", ""])
    monkeypatch.setattr(demo, "run_maternal_learning_v1", fail)
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    demo.run_maternal_learning_menu_v1()
    assert "L25" in capsys.readouterr().out


@pytest.mark.parametrize("choice,cases,detail", [("1", ("nominal_on", "nominal_off", "competing_on", "competing_off"), False),
                                                ("5", ("stand_follow", "stand_drift"), False),
                                                ("9", ("competing_on", "unresolved_current"), True)])
def test_menu_uses_shared_functions_without_another_cognitive_loop(monkeypatch, choice, cases, detail):
    calls = []
    choices = iter(["invalid", choice, ""])
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(demo, "run_maternal_learning_v1", lambda case: calls.append(("run", case)) or case)
    monkeypatch.setattr(demo, "render_maternal_learning_v1", lambda result, *, detail: calls.append(("render", result, detail)) or "review")
    demo.run_maternal_learning_menu_v1()
    assert calls == [item for case in cases for item in (("run", case), ("render", case, detail))]


def test_menu_thirteen_preserves_existing_a0_session(monkeypatch):
    session = Nca8SessionV1()
    before, rng = session.trace_snapshot(), random.getstate()
    choices = iter(["13", ""])
    called = []
    monkeypatch.setattr(nca8_menu.cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(nca8_menu, "run_maternal_learning_menu_v1", lambda: called.append(True))
    returned = nca8_menu.run_nca8_experimental_menu_v1(session)
    assert returned is session and called == [True]
    assert session.trace_snapshot() == before and random.getstate() == rng


@pytest.mark.parametrize("case", ["nominal_on", "competing_on", "unresolved_current"])
def test_cli_runs_outside_repo_and_exports_exact_shared_result(results, tmp_path, case):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), "--learning", case, "--json"],
                          cwd=tmp_path, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == json.loads(json.dumps([results[case].as_dict()]))
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("args", [["--learning", "unknown"], ["--learning", "nominal_on", "--outcomes"],
                                   ["--learning", "--outcome-attention"], ["--learning-routing", "--learning"]])
def test_cli_rejects_ambiguous_or_unknown_selector(args, capsys):
    with pytest.raises(SystemExit) as error:
        script.main(args)
    assert error.value.code == 2
    capsys.readouterr()


def test_cli_routing_identifies_synthetic_nonphysical_evidence(capsys):
    assert script.main(["--learning-routing", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 2 and all(row["physical_world_steps"] == 0 for row in rows)
    assert all(row["evidence"] == "supplied_routing_fixture" for row in rows)


@pytest.mark.parametrize("field,value", [("durable_after", "changed"), ("fixed_configuration_unchanged", False),
                                        ("peak_counts", (("unexpected_owner", 1),))])
def test_cli_bound_or_durable_violation_is_nonzero_not_hidden_by_completion(results, monkeypatch, capsys, field, value):
    bad = replace(results["nominal_on"], **{field: value})
    monkeypatch.setattr(script, "run_maternal_learning_v1", lambda _case: bad)
    assert script.main(["--learning", "nominal_on"]) == 1
    capsys.readouterr()


def test_hook_never_imports_physics_executive_or_ledger_and_creates_no_update_rule():
    tree = ast.parse((ROOT / "nca8_maternal_learning.py").read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imports & {"cca8_support_world", "nca8_hierarchy", "nca8_executive", "nca8_learning_registry", "random"}
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"allocate", "run_cycle", "focal_step", "advance_lower", "apply", "install_authorized"}
    assert "reconcile" in MaternalLearningHookV1.__dict__


def test_registry_adds_exactly_the_two_real_components_without_new_host_primitives():
    import cca8_run
    import nca8_maternal_learning
    import nca8_trace
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.32" and len(rows) == 99
    assert {"nca8_maternal_learning", "nca8_maternal_learning_demo"} <= {row[0] for row in rows}
    assert nca8_maternal_learning.__version__ == demo.__version__ == "0.1.0"
    assert nca8_trace.__version__ == "0.9.1" and len(cca8_run.PRIMITIVES) == 8


@pytest.mark.parametrize("after_install", [False, True])
def test_installation_fault_closes_original_hook_without_retry_or_false_execution(monkeypatch, after_install):
    trial = demo.create_maternal_learning_trial_v1("nominal_on")
    old_hook = trial.core.maternal.learning_hook
    original = trial.controller.install_authorized
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        if after_install:
            original(*args, **kwargs)
        raise ValueError("installation fault fixture")

    monkeypatch.setattr(trial.controller, "install_authorized", fail)
    with pytest.raises(ValueError, match="installation fault"):
        trial.focal_step()
    assert trial.stopped and trial.tick == 0 and not old_hook.pending()
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert calls == [True]
    assert not any(item.status == "accepted_no_update" for item in old_hook.history())


@pytest.mark.parametrize("after_motion", [False, True])
def test_possible_physical_effect_fault_closes_hook_without_replaying_command(monkeypatch, after_motion):
    trial = demo.create_maternal_learning_trial_v1("nominal_on")
    trial.focal_step()
    hook = trial.core.maternal.learning_hook
    original = trial._world.step
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        if after_motion:
            original(*args, **kwargs)
        raise ValueError("physical fault fixture")

    monkeypatch.setattr(trial._world, "step", fail)
    with pytest.raises(ValueError, match="physical fault"):
        trial.advance_lower()
    assert trial.stopped and not hook.pending()
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert calls == [True]
    assert not any(item.status == "accepted_no_update" for item in hook.history())


def test_old_stand_follow_export_omits_disabled_hook_without_hiding_enabled_configuration():
    from nca8_stand_follow_demo import stand_follow_profile_v1
    profile = stand_follow_profile_v1()
    assert "learning_hook_enabled" not in profile.as_dict()["maternal"]
    enabled = replace(profile, maternal=replace(profile.maternal, learning_hook_enabled=True))
    assert enabled.as_dict()["maternal"]["learning_hook_enabled"] is True
