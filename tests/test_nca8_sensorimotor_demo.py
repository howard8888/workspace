"""External H4 driver, matched controls, menu/CLI equivalence and fault handling."""

from __future__ import annotations

import builtins
import json
import random
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

import pytest

import cca8_cli
import nca8_menu
import nca8_sensorimotor_demo as demo
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorWorldProfileV1
from nca8_runtime import Nca8SessionV1
from nca8_sensorimotor import SensorimotorProfileV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1
from scripts.review_nca8_sensorimotor import main

ROOT = Path(__file__).resolve().parents[1]


def test_every_local_update_advances_physics_once_and_installation_does_not(monkeypatch):
    trial = demo.SensorimotorTrialV1()
    assert trial.world.tick == 0 and trial.controller.next_tick == 0
    assert trial.body.current_state is None and trial.body.current_envelope is None
    actual_step = trial.world.step
    calls = []

    def measured_step(command):
        calls.append((trial.world.tick, command))
        return actual_step(command)

    monkeypatch.setattr(trial.world, "step", measured_step)
    for tick in range(12):
        result = trial.advance()
        assert result.tick == tick
        assert trial.world.tick == tick + 1 == trial.controller.next_tick
    assert len(calls) == 12
    assert trial.controller.installation_count == 1
    assert trial.body.current_state is None and trial.body.current_envelope is None


def test_poststep_feedback_is_staged_not_used_by_the_preceding_command():
    trial = demo.SensorimotorTrialV1()
    zero = trial.advance()
    assert zero.feedback.event_tick == 0
    assert trial.latest_feedback.event_tick == 0  # Event 1 is still in transit.
    one = trial.advance()
    assert one.feedback.event_tick == 0
    assert trial.latest_feedback.event_tick == 1
    two = trial.advance()
    assert two.feedback.event_tick == 1
    assert two.feedback.available_tick == 2
    assert trial.latest_feedback.event_tick == 2


def test_partial_progress_is_observed_not_inferred_from_a_command():
    result = demo.run_sensorimotor_experiment_v1()
    partials = [report for step in result.steps for report in step.reports if report.disposition is LocalTargetDispositionV1.PARTIAL]
    assert partials
    for report in partials:
        assert report.feedback is not None
        assert report.feedback.event_tick > report.committed_target.target.basis.event_tick
        assert not report.as_dict()["establishes_task_success"]


@pytest.mark.parametrize("after_effect", [False, True])
def test_physical_exception_stops_without_retry_or_undoing_real_effect(after_effect, monkeypatch):
    trial = demo.SensorimotorTrialV1()
    original = trial.world.step
    calls = []
    before = trial.world.body

    def fail(command):
        calls.append(command)
        if after_effect:
            original(command)
        raise RuntimeError("injected physical failure")

    monkeypatch.setattr(trial.world, "step", fail)
    with pytest.raises(RuntimeError, match="injected physical failure"):
        trial.advance()
    assert trial.stopped and trial.controller.fault
    assert trial.world.tick == int(after_effect)
    assert (trial.world.body != before) is after_effect
    with pytest.raises(RuntimeError, match="no automatic retry"):
        trial.advance()
    assert len(calls) == 1
    assert all(item.disposition is LocalTargetDispositionV1.INTERRUPTED for item in trial.controller.reports)


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_base_exception_after_possible_motion_is_stopped_before_propagation(error, monkeypatch):
    trial = demo.SensorimotorTrialV1()
    original = trial.world.step

    def fail(command):
        original(command)
        raise error()

    monkeypatch.setattr(trial.world, "step", fail)
    with pytest.raises(error):
        trial.advance()
    assert trial.stopped and trial.controller.fault
    assert trial.world.tick == 1


@pytest.mark.parametrize("mode", ["none", "dict", "oversized", "future", "changed_id", "wrong_stream", "bad_order"])
def test_invalid_return_after_world_effect_never_becomes_fresh_feedback(mode, monkeypatch):
    trial = demo.SensorimotorTrialV1()
    original = trial.world.step
    old = trial.latest_feedback

    def corrupt(command):
        original(command)
        if mode == "none":
            return None
        if mode == "dict":
            return (old.as_dict(),)
        if mode == "oversized":
            return (old,) * 17
        if mode == "future":
            return (replace(old, sample_id=2, event_tick=1, available_tick=2),)
        if mode == "changed_id":
            return (replace(old, support_extension=0.8),)
        if mode == "wrong_stream":
            return (replace(old, stream=MotorStreamRefV1("different", 1)),)
        return (replace(old, sample_id=2),)

    monkeypatch.setattr(trial.world, "step", corrupt)
    with pytest.raises((TypeError, ValueError)):
        trial.advance()
    assert trial.world.tick == 1 and trial.stopped
    assert trial.latest_feedback is old
    with pytest.raises(RuntimeError):
        trial.advance()


def test_provider_without_exact_one_tick_advance_is_an_explicit_fault(monkeypatch):
    trial = demo.SensorimotorTrialV1()
    monkeypatch.setattr(trial.world, "step", lambda _command: ())
    with pytest.raises(ValueError, match="exactly one interval"):
        trial.advance()
    assert trial.stopped and trial.world.tick == 0


def test_reentrant_advance_is_rejected_without_second_world_effect(monkeypatch):
    trial = demo.SensorimotorTrialV1()

    def recursive(_command):
        trial.advance()
        raise AssertionError("unreachable")

    monkeypatch.setattr(trial.world, "step", recursive)
    with pytest.raises(RuntimeError, match="already advancing"):
        trial.advance()
    assert trial.world.tick == 0 and trial.stopped


def test_reset_during_world_advance_is_rejected(monkeypatch):
    trial = demo.SensorimotorTrialV1()
    monkeypatch.setattr(trial.world, "step", lambda _command: trial.reset())
    with pytest.raises(RuntimeError, match="during"):
        trial.advance()
    assert trial.stopped and trial.world.stream.generation == 1


def test_explicit_reset_replaces_all_target_execution_and_sensor_ownership():
    trial = demo.SensorimotorTrialV1()
    old_controller = trial.controller
    old_mapper = trial.body.motor_targets
    old_targets = trial.targets
    first_steps = [trial.advance() for _ in range(3)]
    trial.reset()
    assert trial.world.stream.generation == 2
    assert trial.world.tick == trial.controller.next_tick == 0
    assert trial.controller is not old_controller
    assert trial.body.motor_targets is not old_mapper
    assert not trial.controller.events
    assert trial.controller.installation_count == 1
    with pytest.raises(ValueError):
        trial.body.motor_targets.validate_reservation(old_targets[0], at_tick=0)
    repeated = trial.advance()
    assert repeated.command.orientation_drive == first_steps[0].command.orientation_drive
    assert repeated.command.extension_drive == first_steps[0].command.extension_drive
    assert repeated.command.stream.generation == 2


@pytest.mark.parametrize("open_loop", [False, True])
def test_uncoordinated_world_reset_cannot_advance_under_the_old_execution(open_loop):
    trial = demo.SensorimotorTrialV1()
    trial.world.reset()
    with pytest.raises(ValueError):
        trial.advance_open_loop(None) if open_loop else trial.advance()
    assert trial.stopped and trial.world.tick == 0


def test_open_loop_replay_keeps_the_original_lease_and_exception_policy(monkeypatch):
    trial = demo.SensorimotorTrialV1()
    for _ in range(8):
        trial.advance_open_loop(None)
    command = MotorCommandV1(trial.world.stream, 9, 8, -0.1, 0.1)
    with pytest.raises(ValueError, match="lease"):
        trial.advance_open_loop(command)
    assert trial.stopped and trial.world.tick == 8


@pytest.mark.parametrize("stride", [1, 4, 8])
def test_reference_markers_change_neither_physical_horizon_nor_control(stride):
    reference = demo.run_sensorimotor_experiment_v1("perturbed")
    result = demo.run_sensorimotor_experiment_v1("perturbed", marker_stride=stride)
    assert reference.commands == result.commands
    assert reference.final_body == result.final_body
    assert reference.reports == result.reports
    assert reference.events == result.events
    assert result.elapsed_ticks == 12
    assert result.as_dict()["focal_calls"] == 0


def test_detailed_rendering_is_readonly_and_discloses_reference_markers():
    result = demo.run_sensorimotor_experiment_v1("perturbed", trace_capacity=1)
    before = result.as_dict()
    rng = random.getstate()
    compact = demo.render_sensorimotor_experiment_v1(result)
    detail = demo.render_sensorimotor_experiment_v1(result, detailed=True)
    assert len(detail) > len(compact)
    assert "NO focal call" in "\n".join(detail)
    assert "Passive tilt may drift afterward" in "\n".join(detail)
    assert result.as_dict() == before and random.getstate() == rng
    json.dumps(before, allow_nan=False)


def test_independent_instances_and_repeated_runs_have_identical_behavior():
    left, right = demo.SensorimotorTrialV1(), demo.SensorimotorTrialV1()
    for _ in range(12):
        a = left.advance()
        b = right.advance()
        assert a.as_dict() == b.as_dict()
        assert left.world.body == right.world.body
    assert demo.run_sensorimotor_experiment_v1().as_dict() == demo.run_sensorimotor_experiment_v1().as_dict()


@pytest.mark.parametrize("dt", [0.01, 0.025, 0.05])
def test_actual_declared_interval_is_shared_with_mapper_without_a_second_clock(dt):
    trial = demo.SensorimotorTrialV1(MotorWorldProfileV1(dt_seconds=dt), desired_tilt_degrees=None)
    for _ in range(12):
        trial.advance()
    assert trial.body.motor_targets.tick_seconds == dt
    assert trial.world.elapsed_seconds == pytest.approx(12 * dt)
    assert all(step.command is None for step in trial.controller.trace_snapshot()[8:])


@pytest.mark.parametrize("case", ["nominal", "perturbed", "feedback_off", "prediction_off", "dropout", "delayed",
                                  "no_surface", "no_orientation", "blocked_motor", "support_loss", "support_loss_prediction_off"])
def test_supported_cases_are_finite_json_safe_and_explicitly_not_righting(case):
    result = demo.run_sensorimotor_experiment_v1(case)
    exported = result.as_dict()
    json.dumps(exported, allow_nan=False)
    assert len(result.steps) == result.elapsed_ticks == 12
    assert exported["task_requirement_source"] == "external_fixture"
    assert exported["durable_learning_updates"] == exported["focal_calls"] == 0
    assert exported["establishes_righting_success"] is False
    assert len(result.events) <= 4


@pytest.mark.parametrize("name,value", [("ticks", 0), ("ticks", 81), ("ticks", True), ("ticks", 2.5),
                                       ("marker_stride", 0), ("marker_stride", 9), ("marker_stride", True),
                                       ("trace_capacity", 0), ("trace_capacity", 257)])
def test_invalid_review_bounds_are_rejected(name, value):
    with pytest.raises((TypeError, ValueError)):
        demo.run_sensorimotor_experiment_v1(**{name: value})


def test_unknown_case_is_not_silently_replaced_by_an_easy_nominal_run():
    with pytest.raises(ValueError):
        demo.run_sensorimotor_experiment_v1("made_up")


def test_menu_open_detail_and_return_do_not_create_any_world(monkeypatch, capsys):
    responses = iter(("6", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(demo, "run_sensorimotor_experiment_v1", lambda *_args, **_kwargs: pytest.fail("unexpected run"))
    demo.run_sensorimotor_review_menu_v1()
    assert "No H4 run is retained" in capsys.readouterr().out


def test_menu_detail_reuses_completed_results_instead_of_rerunning(monkeypatch, capsys):
    expected = demo.run_sensorimotor_experiment_v1()
    calls = []

    def run(case):
        calls.append(case)
        return expected

    monkeypatch.setattr(demo, "run_sensorimotor_experiment_v1", run)
    responses = iter(("1", "6", "6", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    demo.run_sensorimotor_review_menu_v1()
    output = capsys.readouterr().out
    assert calls == ["nominal"]
    assert "reference focal marker 4" in output
    assert "CASE: nominal" in output


@pytest.mark.parametrize("choice,cases", [
    ("2", ["perturbed", "feedback_off", "prediction_off", "support_loss", "support_loss_prediction_off"]),
    ("3", ["no_orientation"]), ("4", ["dropout", "delayed"]), ("5", ["no_surface"]),
])
def test_menu_uses_the_same_named_experiments_as_cli(choice, cases, monkeypatch):
    calls = []
    expected = demo.run_sensorimotor_experiment_v1()
    monkeypatch.setattr(demo, "run_sensorimotor_experiment_v1", lambda case: (calls.append(case), expected)[1])
    responses = iter((choice, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    demo.run_sensorimotor_review_menu_v1()
    assert calls == cases


def test_option_six_does_not_construct_reset_or_advance_the_retained_a0_session(monkeypatch):
    session = Nca8SessionV1()
    before = session.status(), session.trace_canonical_bytes(), session.pending_observation
    responses = iter(("6", "1", "6", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert before == (session.status(), session.trace_canonical_bytes(), session.pending_observation)


def test_option_six_can_run_with_no_a0_session_and_preserves_return_pause(monkeypatch):
    responses = iter(("6", "1", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(cca8_cli, "wait_for_main_menu_continue_v1", lambda: pytest.fail("unexpected main-menu pause"))
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None


def test_cli_matches_shared_review_output_and_runs_no_hidden_cognitive_session():
    first, second = StringIO(), StringIO()
    with redirect_stdout(first):
        results = demo.run_sensorimotor_review_v1()
    with redirect_stdout(second):
        assert main([]) == 0
    assert first.getvalue() == second.getvalue()
    assert len(results) == 11
    assert "H5 Righting preview remains next" in second.getvalue()


def test_permanent_cli_works_from_outside_repo_and_supports_detail(tmp_path):
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_sensorimotor.py"), "--detail"],
                               cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "reference focal marker" in completed.stdout
    assert "LOCAL TARGET EXECUTION REVIEW COMPLETE" in completed.stdout


def test_registry_reports_all_production_modules_without_registering_an_smp_as_a_task():
    import cca8_run
    import nca8_body_targets
    import nca8_sensorimotor
    assert cca8_run.__version__ == "0.30.31"
    assert nca8_body_targets.__version__ == "0.9.0"
    assert nca8_sensorimotor.__version__ == "0.4.0"
    assert demo.__version__ == "0.3.0"
    assert nca8_menu.__version__ == "0.24.0"
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_sensorimotor"] == "nca8_sensorimotor"
    assert registry["nca8_sensorimotor_demo"] == "nca8_sensorimotor_demo"
    assert len(cca8_run._cca8_component_rows()) == 97
    assert len(cca8_run.PRIMITIVES) == 8
