#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H2 physical response and isolation; fixed commands are test inputs, not goat decisions."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
import inspect
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from cca8_env import EnvConfig, FsmBackend, HybridEnvironment, PerceptionAdapter
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1, MotorWorldV1

ROOT = Path(__file__).resolve().parents[1]


def _world(**settings) -> MotorWorldV1:
    return MotorWorldV1(MotorStreamRefV1("test-body", 1), MotorWorldProfileV1(**settings))


def _command(world: MotorWorldV1, orientation: float = 0.0, extension: float = 0.0) -> MotorCommandV1:
    return MotorCommandV1(world.stream, world.tick + 1, world.tick, orientation, extension)


def _snapshot(world: MotorWorldV1):
    return world.stream, world.body, world.tick, world.elapsed_seconds, world.observe(), world.pending_feedback_count


def _run(world: MotorWorldV1, orientation=0.0, extension=0.0, steps=8):
    reports = [world.observe().as_dict()]
    for _ in range(steps):
        reports.extend(item.as_dict() for item in world.step(_command(world, orientation, extension)))
    return asdict(world.body), reports


def test_reset_reading_is_actual_geometry_and_has_no_task_answers() -> None:
    world = _world()
    first = world.observe()
    assert first.body_tilt_degrees == 30.0 and first.support_extension == 0.4
    assert first.useful_loading == pytest.approx(0.12854688201836736)
    assert first.support_contact is True
    assert first.sample_id == 1 and first.event_tick == first.available_tick == 0
    assert world.tick == 0 and world.pending_feedback_count == 0
    assert not {"success", "standing", "target", "task", "profile", "perturbations", "scenario_stage"} & first.as_dict().keys()
    assert MotorFeedbackV1.from_dict(first.as_dict()) == first


def test_first_step_matches_frozen_h1_equations_and_nominal_sensor_delay() -> None:
    world = _world()
    first = world.observe()
    assert world.step(_command(world, -0.5, 0.5)) == ()
    assert world.body.body_tilt_degrees == pytest.approx(28.01143593539449)
    assert world.body.support_extension == pytest.approx(0.425)
    assert world.observe() is first  # Not the future event just acquired.
    assert world.pending_feedback_count == 1
    due = world.step(None)
    assert len(due) == 1
    assert due[0].event_tick == 1 and due[0].available_tick == 2 and due[0].sample_id == 2
    assert due[0].body_tilt_degrees == pytest.approx(28.01143593539449)
    assert due[0].useful_loading == pytest.approx(0.16695052702710544)
    assert due[0].destabilization == pytest.approx(0.6121914026076246)
    assert world.elapsed_seconds == pytest.approx(0.1)
    assert world.observe() is due[0]


@pytest.mark.parametrize("drive", (-1.0, -0.5, 0.0, 0.5, 1.0))
def test_orientation_drive_sign_and_magnitude_have_independent_physical_effect(drive) -> None:
    neutral, driven = _world(), _world()
    neutral.step(None)
    driven.step(_command(driven, drive, 0.0))
    assert driven.body.body_tilt_degrees - neutral.body.body_tilt_degrees == pytest.approx(90 * drive * 0.05)
    assert driven.body.support_extension == neutral.body.support_extension == 0.4


@pytest.mark.parametrize("drive", (-1.0, -0.5, 0.0, 0.5, 1.0))
def test_extension_is_not_a_hidden_orientation_or_loading_command(drive) -> None:
    neutral, driven = _world(), _world()
    neutral.step(None)
    driven.step(_command(driven, 0.0, drive))
    assert driven.body.support_extension - neutral.body.support_extension == pytest.approx(drive * 0.05)
    assert driven.body.body_tilt_degrees == neutral.body.body_tilt_degrees
    assert driven.body.support_extension != driven.observe().useful_loading


def test_neutral_advances_time_and_gravity_without_reusing_the_last_drive() -> None:
    world = _world()
    world.step(_command(world, -1.0, 1.0))
    previous = world.body
    world.step(None)
    assert world.body.body_tilt_degrees > previous.body_tilt_degrees
    assert world.body.support_extension == previous.support_extension
    assert world.tick == 2
    other = _world()
    _run(other, steps=80)
    assert other.body.body_tilt_degrees > 30.0 and other.body.support_extension == 0.4


def test_zero_command_and_none_have_identical_physics_and_sensing() -> None:
    first, second = _world(), _world()
    for _ in range(30):
        assert first.step(None) == second.step(_command(second))
        assert _snapshot(first) == _snapshot(second)


@pytest.mark.parametrize("tilt", (15.0, 30.0, 75.0))
def test_mirrored_bodies_with_mirrored_drives_have_mirrored_motion(tilt) -> None:
    positive = _world(initial_body=MotorBodyStateV1(tilt, 0.4), sensor_delay_ticks=0)
    negative = _world(initial_body=MotorBodyStateV1(-tilt, 0.4), sensor_delay_ticks=0)
    for _ in range(8):
        plus = positive.step(_command(positive, -0.5, 0.5))[0]
        minus = negative.step(_command(negative, 0.5, 0.5))[0]
        assert plus.body_tilt_degrees == pytest.approx(-minus.body_tilt_degrees)
        assert plus.support_extension == minus.support_extension
        assert plus.useful_loading == pytest.approx(minus.useful_loading)
        assert plus.destabilization == pytest.approx(minus.destabilization)


@pytest.mark.parametrize("extension, contact, loading", ((0.20, False, 0.0), (0.25, True, 0.0), (0.625, True, 0.5), (1.0, True, 1.0)))
def test_contact_and_loading_follow_reach_not_the_extension_label(extension, contact, loading) -> None:
    feedback = _world(initial_body=MotorBodyStateV1(0, extension)).observe()
    assert feedback.support_contact is contact
    assert feedback.useful_loading == pytest.approx(loading)


def test_extension_can_reach_point_six_with_no_surface_or_useful_loading() -> None:
    world = _world(surface_present=False, sensor_delay_ticks=0)
    for _ in range(4):
        report = world.step(_command(world, 0.0, 1.0))[0]
        assert report.support_contact is False and report.useful_loading == 0.0
    assert report.support_extension == pytest.approx(0.6)
    assert "achieved" not in report.as_dict() and "success" not in report.as_dict()


@pytest.mark.parametrize("orientation_enabled,extension_enabled", ((False, True), (True, False), (False, False)))
def test_blocked_motors_remove_only_their_drive_not_passive_physics(orientation_enabled, extension_enabled) -> None:
    blocked = _world(orientation_motor_enabled=orientation_enabled, extension_motor_enabled=extension_enabled)
    matched = _world()
    for _ in range(8):
        result = blocked.step(_command(blocked, -0.5, 0.5))
        control = matched.step(_command(matched, -0.5 if orientation_enabled else 0.0, 0.5 if extension_enabled else 0.0))
        assert result == control and blocked.body == matched.body


@pytest.mark.parametrize("tilt,extension,drive", ((89.9, 0.99, 1.0), (-89.9, 0.01, -1.0)))
def test_physical_limits_saturate_without_an_instant_success_answer(tilt, extension, drive) -> None:
    world = _world(initial_body=MotorBodyStateV1(tilt, extension), sensor_delay_ticks=0)
    for _ in range(20):
        report = world.step(_command(world, drive, drive))[0]
        assert -90 <= report.body_tilt_degrees <= 90
        assert 0 <= report.support_extension <= 1
        assert 0 <= report.useful_loading <= 1 and 0 <= report.destabilization <= 1
        json.dumps(report.as_dict(), allow_nan=False)
    assert world.body.body_tilt_degrees == 90 * drive
    assert world.body.support_extension == (1.0 if drive > 0 else 0.0)


def test_time_fixed_angular_disturbance_is_not_indexed_by_command_number() -> None:
    forcing = (MotorWorldPerturbationV1(2, 3, angular_rate_degrees_s=120.0),)
    normal, disturbed, renumbered = _world(), _world(perturbations=forcing), _world(perturbations=forcing)
    for index in range(3):
        normal.step(_command(normal, -0.5, 0.5))
        disturbed.step(_command(disturbed, -0.5, 0.5))
        renumbered.step(MotorCommandV1(renumbered.stream, 100 + index * 7, index, -0.5, 0.5))
        assert disturbed.body == renumbered.body
        assert disturbed.observe() == renumbered.observe()
        if index < 2:
            assert normal.body == disturbed.body
    assert disturbed.body.body_tilt_degrees - normal.body.body_tilt_degrees == pytest.approx(6.0)
    assert disturbed.body.support_extension == normal.body.support_extension


def test_surface_removal_is_sensed_and_does_not_fabricate_a_motor_failure_flag() -> None:
    world = _world(sensor_delay_ticks=0, perturbations=(MotorWorldPerturbationV1(1, 3, remove_support=True),))
    assert world.step(None)[0].support_contact is True
    for _ in range(2):
        report = world.step(_command(world, 0.0, 0.5))[0]
        assert report.support_contact is False and report.useful_loading == 0.0
        assert report.support_extension > 0.4
    assert world.step(None)[0].support_contact is True


def test_same_geometry_and_command_not_attempt_count_determines_response() -> None:
    original = _world(initial_body=MotorBodyStateV1(0.0, 0.5), sensor_delay_ticks=0)
    for _ in range(7):
        original.step(None)  # Upright neutral model remains at exactly the same coordinates.
    fresh = _world(initial_body=original.body, sensor_delay_ticks=0)
    a = original.step(_command(original, 0.25, -0.25))[0]
    b = fresh.step(_command(fresh, 0.25, -0.25))[0]
    assert original.body == fresh.body
    assert a.body_tilt_degrees == b.body_tilt_degrees and a.useful_loading == b.useful_loading
    assert a.event_tick != b.event_tick


@pytest.mark.parametrize("dt", (0.01, 0.025, 0.05))
def test_explicit_interval_controls_rate_without_changing_legacy_dt(dt) -> None:
    world = _world(dt_seconds=dt, initial_body=MotorBodyStateV1(0.0, 0.5), sensor_delay_ticks=0)
    report = world.step(_command(world, 0.25, 0.5))[0]
    assert report.body_tilt_degrees == pytest.approx(90 * 0.25 * dt)
    assert report.support_extension == pytest.approx(0.5 + 0.5 * dt)
    assert world.elapsed_seconds == dt


@pytest.mark.parametrize("delay", (0, 1, 3, 16))
def test_delayed_reports_keep_acquisition_identity_and_never_arrive_early(delay) -> None:
    world = _world(sensor_delay_ticks=delay)
    seen = []
    for _ in range(35):
        reports = world.step(None)
        assert world.pending_feedback_count <= min(delay, 16)
        for report in reports:
            assert report.available_tick == world.tick
            assert report.event_tick + delay == report.available_tick
            assert report.sample_id == report.event_tick + 1
            seen.append(report.event_tick)
    assert seen == list(range(1, 36 - delay))


def test_dropout_creates_no_new_report_but_does_not_erase_earlier_transit() -> None:
    world = _world(perturbations=(MotorWorldPerturbationV1(1, 3, drop_feedback=True),))
    initial = world.observe()
    assert world.step(None) == ()  # event 1 acquired, due at tick 2
    earlier = world.step(None)  # event 2 dropped, event 1 legitimately arrives
    assert len(earlier) == 1 and earlier[0].event_tick == 1
    assert world.step(None) == ()  # event 3 dropped
    assert world.observe() is earlier[0] and world.observe() is not initial
    assert world.step(None) == ()  # event 4 acquired, still delayed
    resumed = world.step(None)
    assert resumed[0].sample_id == 5 and resumed[0].event_tick == 4


@pytest.mark.parametrize("channel", ("body_tilt_degrees", "support_extension", "support_contact", "useful_loading", "destabilization"))
def test_missing_channel_does_not_change_physics_or_replace_missing_with_zero(channel) -> None:
    masked = _world(unavailable_channels=(channel,), sensor_delay_ticks=0)
    intact = _world(sensor_delay_ticks=0)
    for _ in range(4):
        report = masked.step(_command(masked, -0.5, 0.5))[0]
        reference = intact.step(_command(intact, -0.5, 0.5))[0]
        assert masked.body == intact.body and getattr(report, channel) is None
        assert replace(report, **{channel: getattr(reference, channel)}) == reference
        assert MotorFeedbackV1.from_dict(report.as_dict()) == report


def test_reading_and_exporting_never_advance_or_retimestamp_a_sensor_event() -> None:
    world = _world(sensor_delay_ticks=3)
    world.step(_command(world, -0.5, 0.5))
    before = _snapshot(world)
    for _ in range(10):
        packet = world.observe().as_dict()
        packet["body_tilt_degrees"] = 0.0
    assert _snapshot(world) == before
    assert world.observe().body_tilt_degrees == 30.0
    with pytest.raises(FrozenInstanceError):
        world.body.body_tilt_degrees = 0.0


def test_exact_replay_and_interleaved_instances_do_not_share_state_or_rng() -> None:
    before_rng = random.getstate()
    profile = MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(3, 4, remove_support=True),))
    left, right = MotorWorldV1(MotorStreamRefV1("left", 1), profile), MotorWorldV1(MotorStreamRefV1("right", 1), profile)
    right_before = _snapshot(right)
    _run(left, -0.5, 0.5)
    assert _snapshot(right) == right_before
    first = _run(MotorWorldV1(MotorStreamRefV1("replay", 1), profile), -0.5, 0.5)
    second = _run(MotorWorldV1(MotorStreamRefV1("replay", 1), profile), -0.5, 0.5)
    assert json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(second, sort_keys=True, allow_nan=False)
    assert random.getstate() == before_rng


@pytest.mark.parametrize("bad", ("policy:stand_up", {}, True, 1, 0.5))
def test_unsupported_commands_have_no_body_time_or_delivery_effect(bad) -> None:
    world = _world()
    before = _snapshot(world)
    with pytest.raises(TypeError):
        world.step(bad)
    assert _snapshot(world) == before
    world.step(_command(world))  # An invalid input did not consume a valid command number.


@pytest.mark.parametrize("variant", ("stream", "generation", "old_tick", "future_tick", "duplicate", "reversed"))
def test_command_ownership_and_order_fail_before_any_effect(variant) -> None:
    world = _world()
    world.step(MotorCommandV1(world.stream, 5, 0))
    command = MotorCommandV1(world.stream, 6, 1)
    if variant == "stream":
        command = replace(command, stream=MotorStreamRefV1("other", 1))
    elif variant == "generation":
        command = replace(command, stream=MotorStreamRefV1("test-body", 2))
    elif variant == "old_tick":
        command = replace(command, issued_tick=0)
    elif variant == "future_tick":
        command = replace(command, issued_tick=2)
    elif variant == "duplicate":
        command = replace(command, command_id=5)
    else:
        command = replace(command, command_id=4)
    before = _snapshot(world)
    with pytest.raises(ValueError):
        world.step(command)
    assert _snapshot(world) == before
    world.step(MotorCommandV1(world.stream, 6, 1))


def test_reset_discards_pending_deliveries_and_rejects_old_generation() -> None:
    world = _world(sensor_delay_ticks=3)
    old_command = _command(world, -0.5, 0.5)
    world.step(old_command)
    assert world.pending_feedback_count == 1
    initial = world.reset()
    assert initial.stream.generation == 2 and initial.sample_id == 1 and initial.event_tick == 0
    assert world.tick == world.pending_feedback_count == 0 and world.body == MotorBodyStateV1()
    with pytest.raises(ValueError):
        world.step(old_command)
    assert world.step(_command(world)) == ()


def test_generation_overflow_and_counter_exhaustion_leave_state_unchanged() -> None:
    world = MotorWorldV1(MotorStreamRefV1("last", 2**63 - 1))
    before = _snapshot(world)
    with pytest.raises(ValueError):
        world.reset()
    assert _snapshot(world) == before
    world._tick = 2**63 - 2  # Test-only fault injection; no public clock writer.
    before = _snapshot(world)
    with pytest.raises(OverflowError):
        world.step(None)
    assert _snapshot(world) == before


@pytest.mark.parametrize("bad", (True, "0.05", 0.0, -0.01, 0.050001, float("nan"), float("inf"), 10**1000))
def test_invalid_interval_is_rejected_not_repaired(bad) -> None:
    with pytest.raises((TypeError, ValueError)):
        MotorWorldProfileV1(dt_seconds=bad)


@pytest.mark.parametrize("name,bad", (
    ("initial_body", {}), ("surface_reach", 1.0), ("surface_reach", -0.1), ("surface_reach", True),
    ("surface_present", 1), ("orientation_motor_enabled", 0), ("extension_motor_enabled", None),
    ("sensor_delay_ticks", True), ("sensor_delay_ticks", -1), ("sensor_delay_ticks", 17), ("sensor_delay_ticks", 0.5),
    ("unavailable_channels", []), ("unavailable_channels", ("success",)),
    ("unavailable_channels", ("support_contact", "support_contact")), ("unavailable_channels", ([],)),
    ("perturbations", []), ("perturbations", ({},)),
    ("perturbations", (MotorWorldPerturbationV1(2, 4), MotorWorldPerturbationV1(3, 5))),
    ("perturbations", tuple(MotorWorldPerturbationV1(i, i + 1) for i in range(17))),
))
def test_invalid_profile_parameters_cannot_start_a_world(name, bad) -> None:
    with pytest.raises((TypeError, ValueError)):
        MotorWorldProfileV1(**{name: bad})


@pytest.mark.parametrize("name,bad", (
    ("start_tick", True), ("start_tick", -1), ("stop_tick", 0), ("stop_tick", 0.5),
    ("angular_rate_degrees_s", float("nan")), ("angular_rate_degrees_s", 180.1),
    ("angular_rate_degrees_s", True), ("remove_support", 1), ("drop_feedback", 0),
))
def test_invalid_external_intervention_is_rejected(name, bad) -> None:
    settings = {"start_tick": 0, "stop_tick": 1, name: bad}
    with pytest.raises((TypeError, ValueError)):
        MotorWorldPerturbationV1(**settings)


@pytest.mark.parametrize("name,bad", (
    ("body_tilt_degrees", True), ("body_tilt_degrees", -90.1), ("body_tilt_degrees", 90.1),
    ("body_tilt_degrees", float("nan")), ("support_extension", -0.1), ("support_extension", 1.1),
    ("support_extension", False), ("support_extension", "0.4"),
))
def test_invalid_physical_initial_coordinates_are_not_clipped(name, bad) -> None:
    with pytest.raises((TypeError, ValueError)):
        MotorBodyStateV1(**{name: bad})


class _ForbiddenFsm(FsmBackend):
    def reset(self, *args, **kwargs):
        raise AssertionError("motor mode must not call FSM reset")

    def step(self, *args, **kwargs):
        raise AssertionError("motor mode must not call FSM step")


class _ForbiddenPerception(PerceptionAdapter):
    def observe(self, *args, **kwargs):
        raise AssertionError("motor mode must not create legacy predicate observations")


def test_shared_environment_motor_entry_bypasses_storyboard_and_legacy_perception() -> None:
    world = HybridEnvironment(fsm_backend=_ForbiddenFsm(), perception=_ForbiddenPerception())
    initial = world.reset_motor(stream_id="shared")
    assert initial.sample_id == 1
    assert world.step_motor(MotorCommandV1(initial.stream, 1, 0, -0.5, 0.5)) == ()
    assert world.motor_body.body_tilt_degrees == pytest.approx(28.01143593539449)
    assert world.episode_steps == 1 and world.motor_elapsed_seconds == 0.05
    assert world.observe_motor() is initial
    assert world.config.dt == 1.0  # Old scenario interval is not silently repurposed.


@pytest.mark.parametrize("method", ("observe", "step", "apply_action", "state"))
def test_motor_mode_refuses_legacy_observation_and_policy_paths_before_effect(method) -> None:
    world = HybridEnvironment()
    initial = world.reset_motor(stream_id="shared")
    before = world.motor_body, world.episode_steps, world.episode_index, world.observe_motor()
    with pytest.raises(RuntimeError):
        if method == "observe":
            world.observe()
        elif method == "state":
            _ = world.state
        else:
            getattr(world, method)("policy:stand_up", None)
    assert (world.motor_body, world.episode_steps, world.episode_index, world.observe_motor()) == before
    assert world.step_motor(MotorCommandV1(initial.stream, 1, 0)) == ()


@pytest.mark.parametrize("scenario", ("newborn_goat_first_hour", "posture_support_recovery_v1"))
def test_ordinary_modes_refuse_motor_entry_points_and_commands_without_mutation(scenario) -> None:
    world = HybridEnvironment(EnvConfig(scenario_name=scenario))
    world.reset()
    before = world.state.copy(), world.episode_steps, world.episode_index
    command = MotorCommandV1(MotorStreamRefV1("not-installed", 1), 1, 0)
    with pytest.raises(RuntimeError):
        world.step_motor(command)
    with pytest.raises(RuntimeError):
        world.observe_motor()
    with pytest.raises(ValueError):
        world.step(command, None)
    assert (world.state, world.episode_steps, world.episode_index) == before


def test_switching_modes_explicitly_keeps_generation_fresh_and_normal_reset_unchanged() -> None:
    world = HybridEnvironment()
    first = world.reset_motor(stream_id="same")
    world.step_motor(MotorCommandV1(first.stream, 1, 0))
    normal, _ = world.reset()
    control, _ = HybridEnvironment().reset()
    assert asdict(normal) == asdict(control)
    with pytest.raises(RuntimeError):
        world.step_motor(None)
    second = world.reset_motor(stream_id="same")
    assert second.stream.generation == 2
    with pytest.raises(ValueError):
        world.step_motor(MotorCommandV1(first.stream, 2, 0))
    assert world.episode_steps == 0 and world.motor_body == MotorBodyStateV1()


def test_invalid_motor_reset_and_invalid_normal_reset_preserve_existing_mode() -> None:
    world = HybridEnvironment()
    initial = world.reset_motor(stream_id="valid")
    world.step_motor(MotorCommandV1(initial.stream, 1, 0))
    before = world.motor_body, world.episode_steps, world.episode_index, world.observe_motor()
    with pytest.raises(TypeError):
        world.reset_motor(stream_id="invalid", profile={})
    with pytest.raises(ValueError):
        world.reset(config=EnvConfig(scenario_name="posture_support_recovery_v1", dt=0))
    assert (world.motor_body, world.episode_steps, world.episode_index, world.observe_motor()) == before


def test_hybrid_motor_timeline_matches_direct_provider() -> None:
    profile = MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(1, 3, remove_support=True),))
    shared = HybridEnvironment()
    initial = shared.reset_motor(stream_id="same", profile=profile)
    direct = MotorWorldV1(initial.stream, profile)
    for index in range(10):
        command = MotorCommandV1(initial.stream, index + 1, index, -0.25, 0.5)
        assert shared.step_motor(command) == direct.step(command)
        assert shared.motor_body == direct.body
        assert shared.motor_elapsed_seconds == direct.elapsed_seconds
        assert shared.observe_motor() == direct.observe()


def test_physical_provider_has_no_cognitive_imports_or_task_input() -> None:
    tree = ast.parse((ROOT / "cca8_support_world.py").read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports == {"__future__", "math", "dataclasses", "cca8_motor_contracts"}
    neutral = ast.parse((ROOT / "cca8_motor_contracts.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.ImportFrom) and (node.module or "").startswith(("cca8_", "nca8_"))
                   for node in ast.walk(neutral))
    assert set(inspect.signature(MotorWorldV1.step).parameters) == {"self", "command"}
    assert set(inspect.signature(HybridEnvironment.step_motor).parameters) == {"self", "command"}
    assert set(inspect.signature(MotorCommandV1).parameters) == {
        "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive", "translation", "oral_drive", "oral_closure_drive",
    }


def test_manual_h2_inspection_is_deterministic_and_disclaims_task_control() -> None:
    path = ROOT / "scripts/review_nca8_motor_world.py"
    runs = [subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True, text=True, check=False) for _ in range(2)]
    assert runs[0].returncode == runs[1].returncode == 0, runs[0].stderr
    assert runs[0].stdout == runs[1].stdout
    assert "P18-H2 BODY SIMULATOR" in runs[0].stdout
    assert "PHYSICAL PROVIDER CHECKS PASSED" in runs[0].stdout
    assert "Righting selection / BodyMap mapping / SMP feedback control: not run" in runs[0].stdout
