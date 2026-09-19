#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1E-B: physical support measurements through the retained read-only seam.

Test the provider independently, then shared-world integration, the real
handoff/world/admission/Phase-C path, and explicit noninterference. Physical
state access below belongs to external evaluators and controlled tests only.
No test supplies a future trajectory to cognition as a success answer.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from cca8_env import EnvConfig, EnvObservation, FsmBackend, HybridEnvironment
import cca8_env
from cca8_support_world import (
    SupportWorldProfileV1,
    SupportWorldStateV1,
    advance_support_world_v1,
    support_observation_packet_v1,
    support_profile_for_scenario_v1,
)
from nca8_adapters import Nca8EnvironmentBridgeV1, adapt_env_observation_v1
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import Nca8TraceEventV1, render_flow_trace_lines_v1
from scripts.run_nca8_support_evidence import main, run_support_case_v1
import nca8_menu

ROOT = Path(__file__).resolve().parents[1]
_BASELINE = json.loads((ROOT / "tests/fixtures/nca8_support_provider_baseline.json").read_text(encoding="utf-8"))
RECOVERY = "posture_support_recovery_v1"
DISTURBED = "posture_support_disturbed_v1"


def _world(scenario=RECOVERY, **config):
    """Construct/reset a real world; config belongs to the external experiment."""
    world = HybridEnvironment(EnvConfig(scenario_name=scenario, **config))
    observation, _ = world.reset(seed=13)
    return world, observation


def _session(scenario=RECOVERY, *, enabled=True, **flags):
    """Use the normal public session/bridge path, not a scripted observation runner."""
    return Nca8SessionV1(Nca8SessionConfigV1(scenario_name=scenario, support_observation_enabled=enabled, **flags))


def _sample(observation):
    """Admit a world packet through the production whitelist and return its typed sample."""
    sample = adapt_env_observation_v1(observation).support_observation
    assert sample is not None
    return sample


def _digest(value):
    """Match the prepatch fixture's exact deterministic JSON encoding."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def test_named_profiles_share_initial_body_and_differ_only_in_disturbance() -> None:
    """The control is a physical intervention, not a different prelearned recovery route."""
    normal = support_profile_for_scenario_v1(RECOVERY)
    adverse = support_profile_for_scenario_v1(DISTURBED)
    assert normal.initial_body == adverse.initial_body
    assert normal.profile_id == adverse.profile_id == "support_dynamics_v1"
    assert normal.surface_disturbance == 0.0 and adverse.surface_disturbance == 0.85
    assert support_profile_for_scenario_v1("newborn_goat_first_hour") is None
    with pytest.raises(FrozenInstanceError):
        normal.surface_disturbance = 1.0
    with pytest.raises(FrozenInstanceError):
        normal.initial_body.useful_loading = 1.0


@pytest.mark.parametrize("field, upper", (("body_ground_angle_degrees", 90.0), ("useful_loading", 1.0), ("destabilization", 1.0)))
@pytest.mark.parametrize("bad", (float("nan"), float("inf"), -0.1, True, "0.5"))
def test_physical_state_rejects_invalid_measurements(field, upper, bad) -> None:
    """Invalid initial physical quantities are not silently saturated into valid observations."""
    with pytest.raises((TypeError, ValueError)):
        SupportWorldStateV1(**{field: bad})
    with pytest.raises(ValueError):
        SupportWorldStateV1(**{field: upper + 0.1})


@pytest.mark.parametrize("bad", (-0.1, 1.1, float("nan"), float("inf"), True, "bad"))
def test_profile_rejects_invalid_disturbance(bad) -> None:
    """Forcing has a bounded declared range rather than a hidden arbitrary score."""
    with pytest.raises((TypeError, ValueError)):
        SupportWorldProfileV1(surface_disturbance=bad)
    with pytest.raises(TypeError):
        SupportWorldProfileV1(initial_body={})


def test_first_physical_step_matches_the_declared_equations() -> None:
    """Pin the test-profile numbers independently of posture, attempts and clock labels."""
    profile = SupportWorldProfileV1()
    initial = profile.initial_body
    updated = advance_support_world_v1(initial, action="policy:stand_up", profile=profile, dt=1.0)
    assert updated.useful_loading == pytest.approx(0.735)
    assert updated.destabilization == pytest.approx(0.259625)
    assert updated.body_ground_angle_degrees == pytest.approx(34.48658875)
    assert initial == SupportWorldStateV1(10.0, 0.45, 0.40)
    assert updated is not initial


@pytest.mark.parametrize("dt", (0.25, 0.5, 1.0))
def test_action_and_null_differ_with_same_physical_initial_conditions(dt) -> None:
    """An actual lifting request changes the next measurement; elapsed time alone does not lift."""
    profile = SupportWorldProfileV1()
    acted = advance_support_world_v1(profile.initial_body, action="policy:stand_up", profile=profile, dt=dt)
    null = advance_support_world_v1(profile.initial_body, action=None, profile=profile, dt=dt)
    assert acted.useful_loading > profile.initial_body.useful_loading > null.useful_loading
    assert acted.body_ground_angle_degrees > profile.initial_body.body_ground_angle_degrees >= null.body_ground_angle_degrees
    assert acted.destabilization < null.destabilization


def test_disturbance_defeats_the_same_command_not_just_a_success_flag() -> None:
    """Changing external forcing reverses first-step loading/sliding while both coarse poses remain fallen."""
    normal = SupportWorldProfileV1()
    adverse = replace(normal, surface_disturbance=0.85)
    initial = normal.initial_body
    improved = advance_support_world_v1(initial, action="policy:stand_up", profile=normal, dt=1.0)
    impaired = advance_support_world_v1(initial, action="policy:stand_up", profile=adverse, dt=1.0)
    assert improved.posture_label == impaired.posture_label == "fallen"
    assert improved.useful_loading > initial.useful_loading > impaired.useful_loading
    assert improved.destabilization < initial.destabilization < impaired.destabilization
    for _ in range(7):
        improved = advance_support_world_v1(improved, action="policy:stand_up", profile=normal, dt=1.0)
        impaired = advance_support_world_v1(impaired, action="policy:stand_up", profile=adverse, dt=1.0)
    assert improved.body_ground_angle_degrees == 90.0
    assert impaired.body_ground_angle_degrees == 0.0
    assert impaired.useful_loading < 0.5 and impaired.destabilization > 0.9


def test_null_time_steps_never_supply_automatic_lifting_or_learning() -> None:
    """No request means passive settling, even after far more than the old storyboard's birth steps."""
    profile = SupportWorldProfileV1()
    body = profile.initial_body
    for _ in range(40):
        updated = advance_support_world_v1(body, action=None, profile=profile, dt=1.0)
        assert updated.body_ground_angle_degrees <= body.body_ground_angle_degrees
        assert updated.useful_loading <= body.useful_loading
        body = updated
    assert body.posture_label == "fallen"


def test_initial_body_matters_at_the_same_command_and_step() -> None:
    """This is a state-dependent surrogate, not a sequence indexed by attempt number."""
    profile = SupportWorldProfileV1()
    low = SupportWorldStateV1(10.0, 0.1, 0.8)
    high = SupportWorldStateV1(10.0, 0.8, 0.1)
    first = advance_support_world_v1(low, action="policy:stand_up", profile=profile, dt=1.0)
    second = advance_support_world_v1(high, action="policy:stand_up", profile=profile, dt=1.0)
    assert first != second
    assert second.body_ground_angle_degrees > first.body_ground_angle_degrees
    assert second.useful_loading > first.useful_loading


@pytest.mark.parametrize("body", (SupportWorldStateV1(0, 0, 0), SupportWorldStateV1(90, 1, 1), SupportWorldStateV1()))
@pytest.mark.parametrize("disturbance", (0.0, 0.5, 1.0))
def test_extreme_valid_states_remain_finite_and_bounded(body, disturbance) -> None:
    """Declared physical saturation holds under a mixed fixed intervention sequence."""
    profile = SupportWorldProfileV1(surface_disturbance=disturbance)
    for action in [None, "policy:stand_up"] * 20:
        body = advance_support_world_v1(body, action=action, profile=profile, dt=1.0)
        assert 0 <= body.body_ground_angle_degrees <= 90
        assert 0 <= body.useful_loading <= 1 and 0 <= body.destabilization <= 1
        json.dumps(asdict(body), allow_nan=False)


@pytest.mark.parametrize("dt", (0, -0.1, 1.1, float("nan"), float("inf"), True, "1"))
def test_bad_dt_rejected_before_shared_world_mutation(dt) -> None:
    """An invalid interval cannot increment counters or partially replace the physical body."""
    world, _ = _world()
    before = world.state.copy()
    world.config.dt = dt
    with pytest.raises((TypeError, ValueError)):
        world.apply_action("policy:stand_up", ctx=None)
    assert world.state == before and world.episode_steps == 0
    with pytest.raises((TypeError, ValueError)):
        world.reset()
    assert world.state == before and world.episode_index == 1


@pytest.mark.parametrize("action", ("policy:follow_mom", "NO_ACTION", "", False, 1))
def test_unsupported_action_has_no_world_effect(action) -> None:
    """Unknown control is rejected, not reinterpreted as a legitimate null step or recovery."""
    world, _ = _world()
    before = world.state.copy()
    with pytest.raises(ValueError):
        world.apply_action(action, ctx=None)
    assert world.state == before and world.episode_steps == 0


@pytest.mark.parametrize("step", (-1, True, 0.5, 2**63 - 1))
def test_sensor_identity_rejects_invalid_world_clock(step) -> None:
    """Clock-domain conversion must fit the retained signed-64-bit positive packet header."""
    with pytest.raises(ValueError):
        support_observation_packet_v1(SupportWorldStateV1(), step_index=step)


def test_packet_reuses_exact_schema_and_clock_labels_do_not_determine_values() -> None:
    """Step numbering identifies measurements; it never generates their physical contents."""
    body = SupportWorldStateV1()
    first = support_observation_packet_v1(body, step_index=0)
    later = support_observation_packet_v1(body, step_index=99)
    assert set(first) == {
        "schema", "sample_id", "event_cycle", "frame_id", "body_ground_angle_degrees", "useful_loading",
        "destabilization", "lateral_contact",
    }
    assert first["sample_id"] == first["event_cycle"] == 1
    assert later["sample_id"] == later["event_cycle"] == 100
    assert {key: value for key, value in first.items() if key not in {"sample_id", "event_cycle"}} == {
        key: value for key, value in later.items() if key not in {"sample_id", "event_cycle"}
    }
    assert type(first["lateral_contact"]) is bool
    assert _sample(EnvObservation(raw_sensors={"posture_support_v1": first})).as_dict() == first


def test_repeated_observe_is_identical_and_copies_do_not_mutate_world() -> None:
    """Repeated reads are not new samples; old frozen body snapshots survive later motion."""
    world, first = _world(dt=0.5)
    before = world.state.copy()
    assert asdict(world.observe()) == asdict(first)
    assert world.state == before and world.episode_steps == 0
    first.raw_sensors["posture_support_v1"]["useful_loading"] = 0.999
    assert _sample(world.observe()).useful_loading == 0.45
    advanced, _, _, _ = world.apply_action("policy:stand_up", ctx=None)
    assert _sample(advanced).sample_id == _sample(advanced).event_cycle == 2
    assert world.state.time_since_birth == 0.5
    assert before.support_world == SupportWorldStateV1()
    assert before.support_world is not world.state.support_world


def test_mutating_posture_or_hidden_story_does_not_manufacture_support_measurements() -> None:
    """World support values are independent of old labels, milestones, attempt counters and context."""
    world, _ = _world()
    control, _ = _world()
    world.state.kid_posture = "standing"
    world.state.scenario_stage = "first_latch"
    world.state.milestones = ["stood_up", "rested"]
    world.state.newborn_stand_attempts = 999
    world.state.newborn_benchmark_hard = True
    assert _sample(world.observe()) == _sample(control.observe())
    context = SimpleNamespace(pnm="standing/stable", desired_configuration="upright", policy="policy:rest", percept_focus="mom")
    altered, _, _, _ = world.apply_action("policy:stand_up", ctx=context)
    expected, _, _, _ = control.apply_action("policy:stand_up", ctx=None)
    assert _sample(altered) == _sample(expected)
    assert world.state.kid_posture == world.state.support_world.posture_label
    assert world.state.newborn_stand_attempts == 999  # No storyboard update occurred.


def test_support_scenarios_never_call_the_storyboard(monkeypatch) -> None:
    """There is one physical body owner, even with EnvConfig's backward-compatible use_fsm=True default."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("support scenario called the storyboard")
    monkeypatch.setattr(FsmBackend, "reset", forbidden)
    monkeypatch.setattr(FsmBackend, "step", forbidden)
    world, _ = _world()
    world.apply_action("policy:stand_up", ctx=None)
    assert world.state.newborn_stand_attempts == 0
    assert world.state.milestones == []


def test_profile_override_is_explicit_and_applied_only_on_reset() -> None:
    """An experiment may vary initial conditions without silently changing ordinary scenarios."""
    profile = SupportWorldProfileV1(initial_body=SupportWorldStateV1(25, 0.3, 0.6), surface_disturbance=0.2)
    world, observation = _world(support_profile=profile)
    assert _sample(observation).body_ground_angle_degrees == 25
    world.config.support_profile = replace(profile, surface_disturbance=1.0)
    observation, _, _, _ = world.apply_action("policy:stand_up", ctx=None)
    expected = advance_support_world_v1(profile.initial_body, action="policy:stand_up", profile=profile, dt=1.0)
    assert _sample(observation).useful_loading == expected.useful_loading
    world.reset()
    world.apply_action("policy:stand_up", ctx=None)
    assert world.state.support_world != expected
    with pytest.raises(ValueError, match="named"):
        HybridEnvironment(EnvConfig(support_profile=profile)).reset()
    with pytest.raises(ValueError, match="unknown support scenario"):
        _world("posture_support_typo_v1")
    with pytest.raises(TypeError, match="support_profile"):
        _world(support_profile={})


def test_support_scenario_requires_explicit_reset_before_observing_or_acting() -> None:
    """No accidental pre-reset storyboard can masquerade as a support-provider sample."""
    world = HybridEnvironment(EnvConfig(scenario_name=RECOVERY))
    with pytest.raises(RuntimeError, match="reset"):
        world.observe()
    with pytest.raises(RuntimeError, match="reset"):
        world.apply_action(None, ctx=None)
    assert world.episode_steps == 0


def test_stream_bound_exhaustion_stops_before_another_step() -> None:
    """The largest valid current sample cannot roll over to a reused or invalid identity."""
    world, _ = _world()
    world._episode_steps = world.state.step_index = 2**63 - 2
    assert _sample(world.observe()).sample_id == 2**63 - 1
    before = world.state.copy()
    with pytest.raises(OverflowError):
        world.apply_action(None, ctx=None)
    assert world.state == before


def test_reset_and_independent_worlds_do_not_share_mutable_physical_state() -> None:
    """Reset restarts the sensor stream; moving one body cannot alter the other world."""
    first, initial = _world()
    second, _ = _world()
    first.apply_action("policy:stand_up", ctx=None)
    assert _sample(first.observe()) != _sample(second.observe())
    reset, _ = first.reset(seed=99)
    assert asdict(reset) == asdict(initial)
    assert first.episode_index == 2 and second.episode_index == 1
    first.reset(config=EnvConfig())
    assert first.state.support_world is None
    assert "posture_support_v1" not in first.observe().raw_sensors


@pytest.mark.parametrize("scenario", (RECOVERY, DISTURBED))
def test_real_packet_reaches_owning_phase_c_but_not_behavioral_authority(scenario) -> None:
    """Each cycle uses its already-admitted sample, not its own later world result."""
    session = _session(scenario)
    durable = session.durable_posture_support_map
    for cycle in range(1, 7):
        current_input = session.pending_observation.support_observation
        result = session.run_cognitive_cycle()
        companion = session.support_configuration
        assert companion.observation == current_input
        assert companion.observation.event_cycle == companion.applied_cycle == cycle
        assert companion.disposition == "current" and companion.behavioral_authority is False
        assert session.pending_observation.support_observation.event_cycle == cycle + 1
        assert result.environment_step == cycle
        assert session.durable_posture_support_map is durable
        if result.wnm is not None:
            assert {relation.partition(":")[0] for relation in result.wnm.working_relations} == {"contact", "posture", "support"}
    assert all(dict(event.details)["durable_updates"] == 0 for event in session.trace_snapshot() if event.channel == "learning")
    assert session.status().posture_support_map_revision == 1


@pytest.mark.parametrize("scenario", (RECOVERY, DISTURBED))
def test_disabling_readonly_consumer_preserves_all_actions_and_later_packets(scenario) -> None:
    """Measured support is available in transport but does not secretly teach or guide A0."""
    enabled = _session(scenario)
    disabled = _session(scenario, enabled=False)
    for _ in range(6):
        assert enabled.run_cognitive_cycle().as_dict() == disabled.run_cognitive_cycle().as_dict()
        assert enabled.pending_observation.as_dict() == disabled.pending_observation.as_dict()
        assert disabled.support_configuration is None
    measured_events = [event for event in enabled.trace_snapshot() if event.channel == "support_observation"]
    assert len(measured_events) == 6
    assert not any(event.channel == "support_observation" for event in disabled.trace_snapshot())


def test_provider_step_runs_after_internal_close_and_admission_is_later(monkeypatch) -> None:
    """The new physical producer cannot reopen the removed Phase-E environment callback."""
    session = _session()
    original = cca8_env.advance_support_world_v1
    calls = []
    def inspected(*args, **kwargs):
        events = session.trace_snapshot()
        assert events[-1].message == f"CognitiveCycle_{len(calls) + 1} closed"
        assert dict(events[-1].details)["next_input_available"] is False
        assert session.support_configuration.observation.event_cycle == len(calls) + 1
        calls.append(kwargs["action"])
        return original(*args, **kwargs)
    monkeypatch.setattr(cca8_env, "advance_support_world_v1", inspected)
    for cycle in range(1, 4):
        session.run_cognitive_cycle()
        events = [event for event in session.trace_snapshot() if event.cycle_id == cycle]
        channels = [event.channel for event in events]
        assert channels[-4:] == ["cycle", "dispatch", "input", "firewall"]
        assert len(calls) == cycle
        assert dict(events[-1].details)["observation_number"] == cycle + 1


def test_boundary_failure_after_physical_change_does_not_retry_provider(monkeypatch) -> None:
    """A moved body plus lost execution report is unknown, not an excuse to issue another lift."""
    session = _session()
    environment = session._environment_bridge._environment
    original = environment.apply_action
    calls = []
    def lose_result(*args, **kwargs):
        calls.append(args)
        original(*args, **kwargs)
        raise OSError("controlled loss after support world changed")
    monkeypatch.setattr(environment, "apply_action", lose_result)
    with pytest.raises(OSError):
        session.run_cognitive_cycle()
    assert environment.episode_steps == 1 and environment.state.support_world.useful_loading > 0.45
    assert session.status().execution_status == "unknown"
    assert session.status().reset_required and not session.status().pending_input_available
    with pytest.raises(RuntimeError, match="reset"):
        session.run_cognitive_cycle()
    assert len(calls) == 1 and environment.episode_steps == 1


def test_world_receipt_can_be_admitted_only_once_with_real_support_packet() -> None:
    """The retained input boundary never duplicates a physical step to obtain another sample."""
    bridge = Nca8EnvironmentBridgeV1(scenario_name=RECOVERY)
    initial = bridge.reset().observation.support_observation
    receipt = bridge.advance_task_action(None)
    with pytest.raises(RuntimeError, match="admission"):
        bridge.advance_task_action(None)
    step = bridge.admit_observation(receipt)
    assert step.observation.support_observation.sample_id == initial.sample_id + 1
    with pytest.raises(RuntimeError, match="receipt"):
        bridge.admit_observation(receipt)


@pytest.mark.parametrize("mode, expected", (
    ("absent", "missing"), ("invalid", "invalid"), ("future", "future"), ("partial", "current"),
    ("duplicate", "duplicate"), ("out_of_order", "out_of_order"), ("conflict", "conflict"),
))
def test_produced_packet_transport_variants_preserve_existing_rejection_semantics(monkeypatch, mode, expected) -> None:
    """Fault injection at the output seam remains explicit; nothing fabricates progress or new authority."""
    session = _session()
    initial = session.pending_observation.support_observation.as_dict()
    environment = session._environment_bridge._environment
    original = environment.apply_action
    def altered(*args, **kwargs):
        observation, reward, done, info = original(*args, **kwargs)
        packet = observation.raw_sensors["posture_support_v1"]
        if mode == "absent":
            del observation.raw_sensors["posture_support_v1"]
        elif mode == "invalid":
            packet["useful_loading"] = float("nan")
        elif mode == "future":
            packet["event_cycle"] = 999
        elif mode == "partial":
            del packet["useful_loading"]
            del packet["destabilization"]
        elif mode == "duplicate":
            observation.raw_sensors["posture_support_v1"] = dict(initial)
        elif mode == "out_of_order":
            packet["event_cycle"] = 1
        elif mode == "conflict":
            packet["body_ground_angle_degrees"] = 90.0
        return observation, reward, done, info
    monkeypatch.setattr(environment, "apply_action", altered)
    session.run_cognitive_cycle()
    session.run_cognitive_cycle()
    companion = session.support_configuration
    assert companion.disposition == expected
    assert companion.behavioral_authority is False
    assert companion.last_supported_event_cycle == (2 if mode == "partial" else 1)
    if mode == "partial":
        assert companion.observation.useful_loading is None and companion.observation.destabilization is None
    assert session.status().posture_support_map_revision == 1


def test_support_packet_and_world_profile_never_import_cognitive_answers() -> None:
    """Only the neutral motor-message module is added; no task/source/current-map input."""
    tree = ast.parse((ROOT / "cca8_support_world.py").read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports <= {"__future__", "dataclasses", "math", "cca8_motor_contracts"}
    assert set(inspect.signature(advance_support_world_v1).parameters) == {"body", "action", "profile", "dt"}
    assert set(inspect.signature(support_observation_packet_v1).parameters) == {"body", "step_index"}
    world, _ = _world()
    admitted = adapt_env_observation_v1(world.observe()).as_dict()
    assert "support_profile" not in admitted["env_meta"]
    assert "scenario_stage" not in admitted["env_meta"]
    assert not {"owner", "source_map", "pnm", "success", "task_action"} & admitted["support_observation"].keys()


@pytest.mark.parametrize("name", tuple(_BASELINE["nca8"]))
def test_prepatch_nca8_semantics_packets_and_canonical_bytes_remain_identical(name) -> None:
    """Frozen pre-edit evidence, not a comparison of two equally modified runs."""
    case = _BASELINE["nca8"][name]
    session = Nca8SessionV1(Nca8SessionConfigV1(**case["config"]))
    results = [session.run_cognitive_cycle().as_dict() for _ in range(6)]
    assert _digest(results) == case["cycle_results_sha256"]
    assert _digest(session.pending_observation.as_dict()) == case["next_input_sha256"]
    assert hashlib.sha256(session.trace_canonical_bytes()).hexdigest() == case["trace_sha256"]
    assert len(session.trace_snapshot()) == case["trace_count"]


@pytest.mark.parametrize("scenario", tuple(_BASELINE["legacy_world"]))
def test_prepatch_legacy_world_observations_remain_identical(scenario) -> None:
    """No support field, dynamics or default-scenario promotion leaks into existing world paths."""
    case = _BASELINE["legacy_world"][scenario]
    world, first = _world(scenario)
    observations = [asdict(first)]
    for action in case["actions"]:
        observation, _, _, _ = world.apply_action(action, ctx=None)
        assert "posture_support_v1" not in observation.raw_sensors
        observations.append(asdict(observation))
    assert _digest(observations) == case["observation_sha256"]


def test_deferred_text_edits_match_current_order_without_rewriting_historical_trace() -> None:
    """HAND OFF names new Phase E; saved pre-1R-B traces keep their real dispatch timing."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    text = "\n".join(render_flow_trace_lines_v1(session.trace_snapshot()))
    assert text.count("PHASE E - PREDICT, CHECK THE BODY, COMMIT AND HAND OFF") == 2
    fixture = json.loads((ROOT / "tests/fixtures/nca8_gate_a_pre_1r_b.json").read_text(encoding="utf-8"))
    events = tuple(Nca8TraceEventV1(
        sequence=item["sequence"], channel=item["channel"], message=item["message"], cycle_id=item["cycle_id"],
        phase=item["phase"], details=tuple(sorted(item["details"].items())),
    ) for item in fixture["events"])
    historical = "\n".join(render_flow_trace_lines_v1(events))
    assert "PHASE E - PREDICT, CHECK THE BODY, COMMIT AND DISPATCH" in historical
    assert "PHASE E - PREDICT, CHECK THE BODY, COMMIT AND HAND OFF" not in historical
    intro = " ".join(nca8_menu._INTRODUCTION_V1.split())
    assert "After the internal cognitive cycle closes, the outer runner sends the accepted request" in intro
    assert "separate handoff receipt controls one-time consumption" in intro


@pytest.mark.parametrize("case, commands", (("recovery", ["STAND_UP"] * 3 + ["NO_ACTION"] * 3),
                                           ("disturbed", ["STAND_UP"] * 6), ("no-action", ["NO_ACTION"] * 6)))
def test_small_demo_drives_real_sessions_without_selecting_commands(case, commands, capsys) -> None:
    """The harness executes six cycles; its expected command pattern is tested, never supplied to the runtime."""
    session = run_support_case_v1(case)
    text = capsys.readouterr().out
    assert [line.split("output=", 1)[1].split(";", 1)[0] for line in text.splitlines() if line.startswith("Cycle ")] == commands
    assert text.count("input   (processed)") == text.count("pending (not used)") == 6
    assert session.support_configuration.observation.event_cycle == 6
    assert session.pending_observation.support_observation.event_cycle == 7
    assert "no A99 gate" in text


def test_demo_trace_is_readonly_and_cli_rejects_invalid_bounds(capsys) -> None:
    """Diagnostics do not add cycles and invalid requests fail before constructing a case."""
    plain = run_support_case_v1("recovery", cycles=2)
    verbose = run_support_case_v1("recovery", cycles=2, show_trace=True)
    assert plain.trace_canonical_bytes() == verbose.trace_canonical_bytes()
    assert plain.pending_observation == verbose.pending_observation
    assert "NCA8 GUIDED FLOW TRACE" in capsys.readouterr().out
    with pytest.raises(SystemExit) as raised:
        main(["--cycles", "0"])
    assert raised.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    with pytest.raises(ValueError):
        run_support_case_v1("unknown")
    with pytest.raises(ValueError):
        run_support_case_v1("recovery", cycles=True)


def test_demo_direct_script_works_outside_repository_launch_directory(tmp_path) -> None:
    """The paste-in Windows command needs no PYTHONPATH edits or installation step."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_nca8_support_evidence.py"), "--case", "recovery", "--cycles", "1"],
        cwd=tmp_path, text=True, encoding="utf-8", capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Cycle 1: output=STAND_UP" in result.stdout
    assert "sample=2 event=2" in result.stdout


@pytest.mark.parametrize("flags", ({"body_action_handoff_enabled": False}, {"navigation_enabled": False}))
def test_current_veto_and_null_phase_e_headings_do_not_revert_to_external_dispatch(flags) -> None:
    """An intervening NOT_APPLIED record cannot make one current Phase-E segment look historical."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**flags))
    session.run_cognitive_cycle()
    text = "\n".join(render_flow_trace_lines_v1(session.trace_snapshot()))
    assert "PHASE E - PREDICT, CHECK THE BODY, COMMIT AND HAND OFF" in text
    assert "PHASE E - PREDICT, CHECK THE BODY, COMMIT AND DISPATCH" not in text


def test_demo_stops_on_runtime_failure_without_retry_or_running_another_case(monkeypatch, capsys) -> None:
    """A review harness must not silently advance another world after an unexpected boundary failure."""
    from scripts import run_nca8_support_evidence
    calls = []
    def fail(case, **_kwargs):
        calls.append(case)
        raise RuntimeError("controlled failure")
    monkeypatch.setattr(run_nca8_support_evidence, "run_support_case_v1", fail)
    assert main(["--case", "all"]) == 1
    assert calls == ["recovery"]
    assert "controlled failure" in capsys.readouterr().err
