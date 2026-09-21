"""Combined P16-2B proofs without changing the qualified core, physics or task limits."""

from __future__ import annotations

import ast
import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import cca8_cli
import cca8_run
import nca8_followmom_qualification as qualification
import nca8_menu
from nca8_runtime import Nca8SessionV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1
from nca8_stand_follow_demo import run_stand_follow_v1, stand_follow_profile_v1
from scripts import review_nca8_followmom as script

ROOT = Path(__file__).resolve().parents[1]
CASES = qualification.FOLLOW_MOM_QUALIFICATION_CASES_V1


@pytest.fixture(scope="module")
def report():
    """Run each finite live profile once; assertions and renderings reuse these records."""
    return qualification.run_follow_mom_qualification_v1()


@pytest.fixture(scope="module")
def runs(report):
    return {run.profile.case: run for run in report.runs}


def at(run, tick):
    return next(c for c in run.cycles if c.calculation.cutoff_tick == tick)


def translation(step):
    return step.command is not None and step.command.translation is not None and (
        step.command.translation.forward != 0 or step.command.translation.left != 0)


def without_hook(cycle):
    """Ignore precisely the report and two configuration labels, no behavior/evidence fields."""
    value = cycle.as_dict()
    value.pop("maternal_learning_reconciliation", None)
    for name in ("maternal_correspondence", "maternal_attention"):
        if name in value:
            value[name].pop("learning_route", None)
    return value


def test_complete_report_is_not_acceptance_of_2b_or_b99(report):
    assert report.status == "PASS" and not report.missing_evidence
    assert len(report.runs) == 16 and len(report.source_replays) == 4 and len(report.routing_fixtures) == 2
    assert all(check.passed for check in report.checks())
    exported = report.as_dict()
    assert exported["scope"] == "P16-2B_only_not_B99"
    assert exported["acceptance"] == "requires_local_validation_and_Howard_review"
    assert "P16-2C" in exported["next_after_acceptance"]
    assert "legacy remains default" in exported["limits"]


@pytest.mark.parametrize("case", CASES)
def test_all_live_runs_have_exact_shared_clock_and_real_owner_bounds(runs, case):
    run = runs[case]
    assert tuple(s.tick for s in run.local_steps) == tuple(range(160))
    assert tuple(s.tick for s in run.physical_samples) == tuple(range(161))
    assert tuple(c.calculation.cutoff_tick for c in run.cycles) == tuple(range(0, 161, 4))
    assert tuple(c.commitment.cycle_id for c in run.cycles) == tuple(range(1, 42))
    assert run.handoff_consumptions == 41
    assert run.target_installations == sum(bool(c.reservations) for c in run.cycles)
    assert not run.bound_violations
    assert run.durable_before == run.durable_after and run.fixed_before == run.fixed_after
    assert all(c.learning_report is not None for c in run.cycles)
    assert all((c.maternal_learning_report is None) == (case == "drift_hook_off") for c in run.cycles)
    assert run.metrics()["durable_learning_updates"] == 0
    assert qualification.FollowMomQualificationReportV1((run,)).status == "PARTIAL"


@pytest.mark.parametrize("case,tick", [
    ("nominal", 104), ("brief_gap", 108), ("heading_90", 104), ("different_target", 104), ("already_supported", 64),
    ("drift_attention_on", 108), ("drift_attention_off", 108), ("drift_hook_off", 108),
])
def test_supported_success_uses_actual_distinct_evidence_and_unchanged_budgets(runs, case, tick):
    run = runs[case]
    assert run.metrics()["proximity_completed_at_tick"] == tick
    frame = at(run, tick).maternal_task
    assert frame.task.status == "completed" and len(frame.supported_samples) == 3
    assert len({s.sample_id for s in frame.supported_samples}) == 3
    assert frame.supported_samples[-1].event_tick - frame.supported_samples[0].event_tick >= 8
    assert all(s.separation <= 0.5 and s.identity_status == "supported" for s in frame.supported_samples)
    assert frame.task.as_dict()["maximum_focal_opportunities"] == 20
    assert frame.task.as_dict()["maximum_physical_ticks"] == 80
    assert tick - frame.task.started_tick <= 80
    assert all(not translation(step) for step in run.local_steps if step.tick >= tick)


@pytest.mark.parametrize("case,status", [
    ("prolonged_gap", "target_unavailable"), ("support_loss", "budget_exhausted"), ("righting_off", "no_task"),
    ("following_off", "no_task"), ("association_off", "no_task"), ("translation_unavailable", "budget_exhausted"),
    ("motor_blocked", "execution_exhausted"), ("boundary_aim", "no_task"),
])
def test_adverse_conditions_are_finite_outcomes_not_hidden_success(runs, case, status):
    assert runs[case].metrics()["maternal_final_status"] == status
    assert runs[case].metrics()["proximity_completed_at_tick"] is None
    assert len(runs[case].local_steps) == 160


def test_brief_gap_cancels_precision_then_same_task_returns_from_fresh_evidence(runs):
    run = runs["brief_gap"]
    gap, after = at(run, 60), at(run, 64)
    assert gap.maternal_source.target_position is None
    assert gap.maternal_source.identity_status == "retained" and gap.maternal_source.uncertainty_radius > 0
    assert gap.maternal_source.last_supported_tick < 60 and not gap.reservations
    assert not any(translation(s) for s in run.local_steps if 60 <= s.tick < 64)
    assert after.maternal_source.target_position is not None and after.maternal_source.last_supported_tick > gap.maternal_source.last_supported_tick
    assert after.reservations and gap.maternal_task.task.task_id == after.maternal_task.task.task_id
    assert len({c.maternal_task.task.task_id for c in run.cycles if c.maternal_task.task is not None}) == 1


def test_prolonged_gap_ends_task_without_reviving_old_permissions(runs):
    run = runs["prolonged_gap"]
    assert at(run, 80).maternal_source.target_position is not None
    assert run.cycles[-1].maternal_task.task.status == "target_unavailable"
    assert not any(c.reservations for c in run.cycles if c.calculation.cutoff_tick >= 76)
    assert not any(translation(s) for s in run.local_steps if s.tick >= 60)


def test_support_protection_remains_local_with_both_hooks_enabled(runs):
    run = runs["support_loss"]
    assert any(translation(s) for s in run.local_steps if s.tick < 57)
    assert any(s.significant_events_added for s in run.local_steps if 57 <= s.tick < 60)
    assert not any(translation(s) for s in run.local_steps if s.tick >= 60)
    assert at(run, 60).maternal_source.identity_status == "supported"
    assert at(run, 60).maternal_source.target_position is not None


def test_supported_start_proves_there_is_no_forced_task_order(runs):
    run = runs["already_supported"]
    assert all(c.calculation.task is None for c in run.cycles)
    assert run.cycles[0].commitment.selected_primitive_id == "ip:follow_mom"
    assert run.metrics()["first_follow_at_tick"] == 0
    assert runs["nominal"].metrics()["righting_completed_at_tick"] == 36
    assert runs["nominal"].metrics()["first_follow_at_tick"] == 40


def test_same_inputs_and_previous_commands_isolate_outcome_attention(runs):
    on, off = runs["drift_attention_on"], runs["drift_attention_off"]
    assert replace(on.profile, case=off.profile.case,
                   maternal=replace(on.profile.maternal, outcome_attention_enabled=False)) == off.profile
    assert on.physical_samples[:61] == off.physical_samples[:61] and on.local_steps[:60] == off.local_steps[:60]
    a, b = at(on, 60), at(off, 60)
    assert a.maternal_source == b.maternal_source and a.visual_source == b.visual_source
    assert a.calculation.source == b.calculation.source
    assert a.maternal_correspondence.outcomes == b.maternal_correspondence.outcomes
    assert a.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "maternal_target"
    assert b.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "visual_scene"
    assert a.maternal_attention.allocation.kind == "interpretation"
    assert a.commitment.selected_primitive_id is None and a.commitment.pnm_id is None and not a.reservations
    assert on.metrics()["interpretation_ticks"] == [60] and on.metrics()["response_ticks"] == [64]
    assert on.metrics()["proximity_completed_at_tick"] == off.metrics()["proximity_completed_at_tick"] == 108


def test_actual_interpretation_releases_F_without_granting_durable_learning(runs):
    on, off = runs["drift_attention_on"], runs["drift_attention_off"]
    cycle = at(on, 60)
    interpretation = cycle.maternal_attention.allocation.interpretation
    accepted = [d for d in cycle.maternal_learning_report.dispositions if d.status == "accepted_no_update"]
    assert len(accepted) == 1 and accepted[0].interpretation is interpretation
    assert accepted[0].outcome is interpretation.request.outcome
    original_pnm = accepted[0].pnm_id
    off_dispositions = [d for c in off.cycles for d in c.maternal_learning_report.dispositions if d.pnm_id == original_pnm]
    assert any(d.status == "eligibility_expired" for d in off_dispositions)
    assert not any(d.status == "accepted_no_update" for d in off_dispositions)
    assert cycle.maternal_learning_report.new_participation is None
    assert on.durable_before == off.durable_after


def test_hook_ablation_preserves_entire_behavior_not_just_completion(runs):
    on, off = runs["drift_attention_on"], runs["drift_hook_off"]
    assert [without_hook(c) for c in on.cycles] == [without_hook(c) for c in off.cycles]
    assert on.local_steps == off.local_steps and on.physical_samples == off.physical_samples
    assert on.final_feedback == off.final_feedback and on.durable_after == off.durable_after
    assert any(c.maternal_learning_report.new_participation is not None for c in on.cycles)
    assert all(c.maternal_learning_report is None for c in off.cycles)
    assert all(c.learning_report is not None for c in off.cycles)


def test_heading_and_destination_are_actual_body_and_source_relations(runs):
    def first_target(run):
        return next(r.current.target for c in run.cycles for r in c.reservations if isinstance(r.current.target, BodyTranslationTargetV1))
    nominal, heading, other = (runs[c] for c in ("nominal", "heading_90", "different_target"))
    a, b, c = first_target(nominal), first_target(heading), first_target(other)
    assert b.offset == pytest.approx((a.offset[1], -a.offset[0]))
    assert c.offset == pytest.approx((a.offset[0], -a.offset[1]))
    assert nominal.physical_samples[-1].planar.position == pytest.approx(heading.physical_samples[-1].planar.position)
    assert other.physical_samples[-1].planar.position[1] < 0 < nominal.physical_samples[-1].planar.position[1]


@pytest.mark.parametrize("case", ["nominal", "brief_gap", "heading_90"])
def test_combined_routes_preserve_accepted_C_behavior(runs, case):
    retained = run_stand_follow_v1(case)
    current = runs[case]
    def canonical(value):
        # Change only the explicitly different stream label, preserving all other
        # source, command, target, report, commitment and timing fields.
        return json.dumps(value, sort_keys=True).replace("stand_follow_reference_body", "follow_mom_qualification_body")
    assert canonical([s.as_dict() for s in current.local_steps]) == canonical([s.as_dict() for s in retained.local_steps])
    assert canonical([c.commitment.as_dict() for c in current.cycles]) == canonical([c.commitment.as_dict() for c in retained.cycles])
    # The deliberately different stream id is provenance, not a behavioral change.
    assert current.physical_samples == retained.physical_samples
    assert [c.commitment.selected_primitive_id for c in current.cycles] == [c.commitment.selected_primitive_id for c in retained.cycles]
    assert current.metrics()["proximity_completed_at_tick"] == retained.metrics()["maternal_proximity_completed_at_tick"]


@pytest.mark.parametrize("case", ["nominal", "brief_gap", "prolonged_gap", "drift_attention_on"])
def test_tiny_diagnostics_and_repeated_fresh_runs_preserve_complete_evidence(runs, case):
    tiny = qualification.run_follow_mom_qualification_case_v1(case, trace_capacity=1, diagnostic_capacity=1)
    assert tiny.cycles == runs[case].cycles and tiny.local_steps == runs[case].local_steps
    assert tiny.physical_samples == runs[case].physical_samples and tiny.metrics() == runs[case].metrics()
    assert not tiny.bound_violations
    assert dict(tiny.peak_counts)["maternal_learning_dispositions"] <= 1


def test_synthetic_evidence_cannot_be_mislabeled_as_live_newborn_work(report):
    for replay in report.as_dict()["source_replays"]:
        assert replay["physical_steps"] == replay["selected_applications"] == 0
        assert "supplied_source_replay" in replay["scope"]
    for fixture in report.as_dict()["routing_fixtures"]:
        assert fixture["physical_steps"] == 0 and fixture["evidence"] == "supplied_endpoint_core_routing_fixture"
    replay = next(r for r in report.source_replays if r.case == "contradiction")
    assert replay.sources[-1].identity_status == "contradicted"
    assert replay.sources[-1].target_position is None and replay.sources[-1].possible_center is None


@pytest.mark.parametrize("missing", ["live", "replay", "routing"])
def test_incomplete_matrix_is_partial_even_when_all_present_checks_pass(report, missing):
    fields = {"live": {"runs": report.runs[:-1]}, "replay": {"source_replays": report.source_replays[:-1]},
              "routing": {"routing_fixtures": report.routing_fixtures[:-1]}}
    partial = replace(report, **fields[missing])
    assert partial.missing_evidence and partial.status == "PARTIAL"
    assert all(c.passed for c in partial.checks())


@pytest.mark.parametrize("which", ["live", "replay", "routing"])
def test_duplicate_evidence_is_rejected_not_counted_twice(report, which):
    fields = {"live": {"runs": (*report.runs, report.runs[0])},
              "replay": {"source_replays": (*report.source_replays, report.source_replays[0])},
              "routing": {"routing_fixtures": (*report.routing_fixtures, report.routing_fixtures[0])}}
    with pytest.raises(ValueError, match="duplicate"):
        replace(report, **fields[which])


@pytest.mark.parametrize("field,value", [
    ("durable_after", "changed"), ("fixed_after", "changed"), ("handoff_consumptions", 42), ("target_installations", 999),
    ("cycles", ()), ("local_steps", ()), ("physical_samples", ()), ("peak_counts", ()),
    ("peak_counts", (("wnm", 2),)), ("peak_counts", (("undeclared_owner", 0),)),
])
def test_broken_evidence_cannot_hide_behind_the_old_success_flag(report, field, value):
    bad = replace(report.runs[0], **{field: value})
    broken = replace(report, runs=(bad, *report.runs[1:]))
    assert broken.status == "FAIL"
    assert any(not c.passed for c in broken.checks())
    assert "FAIL" in qualification.render_follow_mom_qualification_v1(broken)


def test_missing_F_or_double_work_is_detected(report):
    run = report.runs[0]
    first = replace(run.cycles[0], maternal_learning_report=None)
    bad = replace(run, cycles=(first, *run.cycles[1:]))
    assert qualification.FollowMomQualificationReportV1((bad,)).status == "FAIL"


def test_wrong_original_recipient_is_a_failing_fixture(report):
    name, records = report.routing_fixtures[0]
    last = replace(records[-1], maternal_learning_report=replace(records[-1].maternal_learning_report, recipient_id="wrong_recipient"))
    broken = replace(report, routing_fixtures=((name, (*records[:-1], last)), report.routing_fixtures[1]))
    assert broken.status == "FAIL"
    assert not next(c for c in broken.checks() if c.name == "routing_fixture/eligible").passed


def test_mutated_pair_physics_cannot_pass_a_matching_endpoint_label(report):
    original = next(r for r in report.runs if r.profile.case == "drift_hook_off")
    changed = replace(original.physical_samples[-1], planar=replace(original.physical_samples[-1].planar, position=(1.0, 1.0)))
    bad = replace(original, physical_samples=(*original.physical_samples[:-1], changed))
    altered = replace(report, runs=tuple(bad if r.profile.case == bad.profile.case else r for r in report.runs))
    assert altered.status == "FAIL"
    assert not next(c for c in altered.checks() if c.name == "pair/hook_neutrality").passed


def test_render_export_and_check_are_read_only_with_no_new_trial(report, monkeypatch):
    before = json.dumps(report.as_dict(), sort_keys=True, allow_nan=False)
    rng = random.getstate()
    monkeypatch.setattr(qualification, "run_follow_mom_qualification_case_v1", lambda *_a, **_k: pytest.fail("unexpected rerun"))
    for detail in (False, True):
        output = qualification.render_follow_mom_qualification_v1(report, detail=detail)
        assert "RESULT: PASS" in output and "zero physical" in output
    export = report.as_dict()
    export["live_runs"][0]["cycles"].clear()
    export["live_runs"][0]["owner_limits"]["wnm"] = 50
    export["checks"].clear()
    assert json.dumps(report.as_dict(), sort_keys=True, allow_nan=False) == before
    assert random.getstate() == rng
    with pytest.raises(FrozenInstanceError):
        report.runs = ()


@pytest.mark.parametrize("bad", [None, True, 1, "", "not_a_case", []])
def test_unknown_case_is_rejected_before_constructing_a_trial(monkeypatch, bad):
    monkeypatch.setattr(qualification, "IntegratedRightingTrialV1", lambda *_a, **_k: pytest.fail("trial constructed"))
    with pytest.raises(ValueError):
        qualification.run_follow_mom_qualification_v1(bad)
    with pytest.raises(ValueError):
        qualification.follow_mom_qualification_profile_v1(bad)


@pytest.mark.parametrize("field,value", [("trace_capacity", 0), ("trace_capacity", True), ("diagnostic_capacity", 0),
                                         ("diagnostic_capacity", 33), ("diagnostic_capacity", True)])
def test_bad_diagnostic_limits_do_not_start_a_live_run(field, value):
    with pytest.raises((ValueError, TypeError)):
        qualification.run_follow_mom_qualification_case_v1("nominal", **{field: value})


@pytest.mark.parametrize("detail", [None, 0, 1, "true"])
def test_detail_flag_is_not_truthy_configuration(report, detail):
    with pytest.raises(TypeError):
        qualification.render_follow_mom_qualification_v1(report, detail=detail)


@pytest.mark.parametrize("choice,case,detail", [("1", "all", False), ("2", "nominal", True), ("3", "brief_gap", True),
                                               ("4", "prolonged_gap", True), ("5", "support_loss", True),
                                               ("6", "drift_attention_on", True)])
def test_menu_calls_the_shared_runner_exactly_once_per_choice(monkeypatch, report, choice, case, detail):
    choices = iter(["x", choice, ""])
    calls = []
    monkeypatch.setattr(cca8_cli, "read_menu_input_v1", lambda: next(choices))
    monkeypatch.setattr(qualification, "run_follow_mom_qualification_v1", lambda selected: calls.append(("run", selected)) or report)
    monkeypatch.setattr(qualification, "render_follow_mom_qualification_v1", lambda result, *, detail: calls.append(("render", detail)) or "report")
    qualification.run_follow_mom_qualification_menu_v1()
    assert calls == [("run", case), ("render", detail)]


def test_opening_menu_and_returning_runs_nothing(monkeypatch):
    monkeypatch.setattr(cca8_cli, "read_menu_input_v1", lambda: "")
    monkeypatch.setattr(qualification, "run_follow_mom_qualification_v1", lambda *_: pytest.fail("unrequested trial"))
    qualification.run_follow_mom_qualification_menu_v1()


def test_menu_fourteen_retains_existing_A0_session_and_rng(monkeypatch):
    session = Nca8SessionV1()
    before = session.status().as_dict()
    state = random.getstate()
    choices = iter(["14", "2", "", ""])
    monkeypatch.setattr(cca8_cli, "read_menu_input_v1", lambda: next(choices))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert session.status().as_dict() == before and random.getstate() == state


@pytest.mark.parametrize("args", [["--qualification"], ["--qualification", "nominal"], ["--qualification", "nominal", "--json"]])
def test_cli_delegates_once_and_returns_zero_for_valid_scope(monkeypatch, capsys, report, args):
    calls = []
    monkeypatch.setattr(script, "run_follow_mom_qualification_v1", lambda case: calls.append(case) or report)
    assert script.main(args) == 0
    assert calls == [("all" if args == ["--qualification"] else "nominal")]
    if "--json" in args:
        assert json.loads(capsys.readouterr().out)["status"] == "PASS"


@pytest.mark.parametrize("incomplete", [True, False])
def test_cli_full_selection_refuses_partial_or_failed_report(monkeypatch, capsys, report, incomplete):
    partial = replace(report, runs=report.runs[:1]) if incomplete else replace(
        report, runs=(replace(report.runs[0], durable_after="changed"), *report.runs[1:]))
    monkeypatch.setattr(script, "run_follow_mom_qualification_v1", lambda _: partial)
    assert script.main(["--qualification"]) == 1
    assert ("PARTIAL" if incomplete else "FAIL") in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--qualification", "bad"], ["--qualification", "--learning"],
                                  ["--qualification", "--case", "nominal"], ["--qualification", "--outcome-attention"]])
def test_cli_refuses_ambiguous_or_unknown_selection_before_work(monkeypatch, args):
    monkeypatch.setattr(script, "run_follow_mom_qualification_v1", lambda *_: pytest.fail("unexpected trial"))
    with pytest.raises(SystemExit) as error:
        script.main(args)
    assert error.value.code == 2


def test_script_works_from_another_directory_without_creating_repository_outputs(tmp_path):
    command = [sys.executable, str(ROOT / "scripts/review_nca8_followmom.py"), "--qualification", "nominal", "--json"]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PARTIAL" and payload["missing_evidence"]
    assert payload["live_runs"][0]["metrics"]["proximity_completed_at_tick"] == 104
    assert list(tmp_path.iterdir()) == []


def test_registry_and_dependency_direction_are_truthful():
    rows = cca8_run._cca8_component_rows()
    assert cca8_run.__version__ == "0.30.30" and len(rows) == 95 and len(cca8_run.PRIMITIVES) == 8
    assert "nca8_followmom_qualification" in {r[0] for r in rows}
    assert qualification.__version__ == "0.1.0"
    for name in ("nca8_followmom.py", "nca8_hierarchy.py", "nca8_maternal.py", "nca8_maternal_outcomes.py",
                 "nca8_maternal_attention.py", "nca8_maternal_learning.py", "nca8_sensorimotor.py"):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert "nca8_followmom_qualification" not in imported


def test_profile_building_does_not_modify_accepted_C_profiles_or_global_rng():
    original = stand_follow_profile_v1("nominal")
    state = random.getstate()
    new = qualification.follow_mom_qualification_profile_v1("nominal")
    assert original.maternal.outcome_attention_enabled is False and original.maternal.learning_hook_enabled is False
    assert new.maternal.outcome_attention_enabled and new.maternal.learning_hook_enabled
    assert original.physical == new.physical and original.planar == new.planar
    assert stand_follow_profile_v1("nominal") == original and random.getstate() == state
