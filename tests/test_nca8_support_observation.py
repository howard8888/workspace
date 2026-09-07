#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P15-1E-A support-packet admission, owning consumption, and noninterference.

The measurements below are explicit synthetic agent-visible fixtures. They are
not produced by the physical environment and do not demonstrate Righting,
trajectory estimation, supported dwell, or learning. Existing A0 tests remain
unchanged and are run alongside these tests.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from cca8_env import EnvObservation
from nca8_adapters import Nca8EnvironmentBridgeV1, Nca8ObservationV1, adapt_env_observation_v1
from nca8_contracts import CyclePhase
from nca8_executive import AttentionRuntimeV1
from nca8_maps import SupportObservationV1, create_posture_support_map_library_v1
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_sensory import Nca8BodySensoryModuleV1
from nca8_trace import Nca8TraceBufferV1, render_explanatory_trace_lines_v1

_ABSENT = object()


def _packet(sample_id: int = 1, event_cycle: int = 1, **changes: Any) -> dict[str, Any]:
    """Build a declared synthetic packet, never reading hidden environment state."""
    packet = {
        "schema": "posture_support_v1",
        "sample_id": sample_id,
        "event_cycle": event_cycle,
        "frame_id": "body_ground_v1",
        "body_ground_angle_degrees": 0.0,
        "useful_loading": 0.2,
        "destabilization": 0.8,
        "lateral_contact": True,
    }
    packet.update(changes)
    return packet


def _observation(packet: object = _ABSENT, *, predicates: tuple[str, ...] = ("posture:fallen",)) -> Nca8ObservationV1:
    """Use the real firewall, including the distinction between absent and None."""
    raw = {} if packet is _ABSENT else {"posture_support_v1": packet}
    return adapt_env_observation_v1(EnvObservation(raw_sensors=raw, predicates=list(predicates)))


def _module(*, enabled: bool = True) -> Nca8BodySensoryModuleV1:
    """Construct one independent owning circuit with its unchanged innate map."""
    return Nca8BodySensoryModuleV1(create_posture_support_map_library_v1(), support_observation_enabled=enabled)


def _apply(module: Nca8BodySensoryModuleV1, cycle: int, packet: object = _ABSENT):
    """Exercise the existing staged-result and owning application contract."""
    result = module.poll_observation(_observation(packet), cycle_id=cycle, observation_number=cycle)
    return module.apply_result(result.mark_applied(cycle), cycle_id=cycle)


def _runtime(*, enabled: bool = True, attention: bool = True, capacity: int = 256):
    """Wire the real runtime and trace around a separately owned sensory module."""
    trace = Nca8TraceBufferV1(capacity=capacity)
    module = _module(enabled=enabled)
    runtime = Nca8CognitiveRuntimeV1(
        trace=trace,
        scheduler=Nca8DeterministicSchedulerV1(),
        body_sensory=module,
        attention=AttentionRuntimeV1(enabled=attention),
    )
    return runtime, trace


def test_packet_is_typed_detached_immutable_and_json_safe() -> None:
    """Firewall output must retain no mutable alias to the supplied packet."""
    packet = _packet()
    observation = _observation(packet)
    sample = observation.support_observation
    assert sample is not None
    assert isinstance(sample, SupportObservationV1)
    assert observation.raw_sensors == {}
    assert observation.support_observation_error is None
    packet["useful_loading"] = 0.99
    assert sample.useful_loading == 0.2
    exported = observation.as_dict()
    exported["support_observation"]["useful_loading"] = 0.75
    assert sample.useful_loading == 0.2
    with pytest.raises(FrozenInstanceError):
        setattr(sample, "useful_loading", 0.5)
    json.dumps(observation.as_dict(), allow_nan=False)


def test_absent_null_and_all_missing_packets_are_distinct() -> None:
    """No input is not malformed input, and a valid empty sample is not zero load."""
    absent = _observation()
    null = _observation(None)
    empty = _observation({"schema": "posture_support_v1", "sample_id": 1, "event_cycle": 1, "frame_id": "body_ground_v1"})
    assert absent.support_observation is None and absent.support_observation_error is None
    assert "support_observation" not in absent.as_dict()
    assert null.support_observation is None and null.support_observation_error == "invalid_support_packet"
    assert empty.support_observation is not None
    assert empty.support_observation.has_measurements is False
    assert empty.support_observation.useful_loading is None


@pytest.mark.parametrize("field", ["schema", "sample_id", "event_cycle", "frame_id"])
def test_headers_are_mandatory(field: str) -> None:
    """No identity, event time, or frame may be invented by the adapter."""
    packet = _packet()
    del packet[field]
    observation = _observation(packet)
    assert observation.support_observation is None
    assert observation.support_observation_error == "invalid_support_header"


@pytest.mark.parametrize("field", ["body_ground_angle_degrees", "useful_loading", "destabilization"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, True, "0.2", {}, 10**400])
def test_invalid_measurements_reject_the_entire_packet(field: str, value: object) -> None:
    """NaN, infinity, overflow, coercions, and nested content must fail closed."""
    observation = _observation(_packet(**{field: value}))
    assert observation.support_observation is None
    assert observation.support_observation_error == "invalid_support_values"
    json.dumps(observation.as_dict(), allow_nan=False)


@pytest.mark.parametrize("field,value", [
    ("body_ground_angle_degrees", 90.01), ("useful_loading", 1.01), ("destabilization", 1.01),
    ("lateral_contact", 1), ("lateral_contact", "true"), ("frame_id", "another_body_frame"),
])
def test_measurement_ranges_contact_type_and_frame_are_explicit(field: str, value: object) -> None:
    """Unsupported units/frames and ambiguous Boolean coercions are not admitted."""
    assert _observation(_packet(**{field: value})).support_observation_error == "invalid_support_values"


@pytest.mark.parametrize("field", ["sample_id", "event_cycle"])
@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", 2**63])
def test_identity_and_event_cycle_require_bounded_positive_integers(field: str, value: object) -> None:
    """Sender sample identity is not a string, Boolean, or unbounded numeric blob."""
    packet = _packet()
    packet[field] = value
    assert _observation(packet).support_observation_error == "invalid_support_values"


@pytest.mark.parametrize("field", ["oracle_policy", "owner_circuit", "source_map_ref", "progress"])
def test_unknown_packet_keys_reject_without_leaking_payload(field: str) -> None:
    """Even plausible owner/source fields are local authority, not sender input."""
    observation = _observation(_packet(**{field: "DO_NOT_LEAK_THIS_VALUE"}))
    assert observation.support_observation is None
    assert observation.support_observation_error == "unknown_support_fields"
    assert "DO_NOT_LEAK_THIS_VALUE" not in json.dumps(observation.as_dict())


def test_canonical_location_and_version_are_not_guessed() -> None:
    """An alias/metadata packet or another schema cannot silently enter the seam."""
    observation = adapt_env_observation_v1(EnvObservation(
        raw_sensors={"support": _packet()}, env_meta={"posture_support_v1": _packet()},
    ))
    assert observation.support_observation is None and observation.support_observation_error is None
    assert _observation(_packet(schema="posture_support_v2")).support_observation_error == "invalid_support_header"


def test_zero_and_false_are_observed_not_missing() -> None:
    """Zero useful loading is negative measurement evidence, not missing input."""
    module = _module()
    _apply(module, 1, _packet(useful_loading=0, destabilization=0, lateral_contact=False))
    config = module.support_configuration
    assert config is not None and config.evidence_current
    assert config.observation is not None and config.observation.has_measurements
    assert config.observation.useful_loading == 0.0
    assert config.observation.lateral_contact is False
    assert config.behavioral_authority is False


def test_only_owning_phase_c_application_creates_the_configuration() -> None:
    """Polling/inspection cannot update the register, and foreign results are rejected."""
    module = _module()
    source = module.map_library.durable_map()
    signature = module.map_library.durable_record_signature()
    result = module.poll_observation(_observation(_packet()), cycle_id=1, observation_number=1)
    assert module.support_configuration is None
    assert module.current_state is None
    with pytest.raises(ValueError, match="marked applied"):
        module.apply_result(result, cycle_id=1)
    with pytest.raises(ValueError, match="own circuit"):
        module.apply_result(replace(result, source_circuit="foreign").mark_applied(1), cycle_id=1)
    assert module.support_configuration is None
    module.apply_result(result.mark_applied(1), cycle_id=1)
    config = module.support_configuration
    assert config is not None and config.evidence_current
    assert config.owner_circuit == "body_sensory"
    assert config.source_map_ref == module.map_library.posture_support_ref
    assert (config.available_cycle, config.applied_cycle, config.last_supported_event_cycle) == (1, 1, 1)
    assert module.map_library.durable_map() is source
    assert module.map_library.durable_map_count == 1
    assert module.map_library.durable_record_signature() == signature
    with pytest.raises(KeyError):
        module.apply_result(result.mark_applied(1), cycle_id=1)
    assert module.support_configuration is config
    with pytest.raises(FrozenInstanceError):
        setattr(config, "disposition", "current")
    json.dumps(config.as_dict(), allow_nan=False)


def test_replays_and_changed_reused_ids_do_not_refresh_support() -> None:
    """A watermark survives missing input; re-delivery never supplies new support."""
    module = _module()
    packet = _packet()
    _apply(module, 1, packet)
    _apply(module, 2, packet)
    assert module.support_configuration.disposition == "duplicate"
    assert module.support_configuration.last_supported_event_cycle == 1
    _apply(module, 3)
    assert module.support_configuration.disposition == "missing"
    _apply(module, 4, packet)
    assert module.support_configuration.disposition == "duplicate"
    _apply(module, 5, _packet(useful_loading=0.9))
    assert module.support_configuration.disposition == "invalid"
    assert module.support_configuration.reason == "sample_identity_reused_with_changed_content"
    assert module.support_configuration.last_supported_event_cycle == 1


@pytest.mark.parametrize("sample_id,event_cycle,disposition", [
    (1, 3, "out_of_order"), (3, 2, "out_of_order"), (3, 1, "out_of_order"), (3, 4, "future"),
])
def test_out_of_order_and_future_events_are_not_current(sample_id: int, event_cycle: int, disposition: str) -> None:
    """Neither identity ordering nor genuine event ordering may run backwards."""
    module = _module()
    _apply(module, 1, _packet())
    _apply(module, 2, _packet(2, 2))
    _apply(module, 3, _packet(sample_id, event_cycle))
    assert module.support_configuration.disposition == disposition
    assert module.support_configuration.evidence_current is False
    assert module.support_configuration.last_supported_event_cycle == 2
    _apply(module, 4, _packet(4, 4))
    assert module.support_configuration.disposition == "current"
    assert module.support_configuration.last_supported_event_cycle == 4


def test_delayed_packet_is_historical_and_cannot_become_fresh_on_replay() -> None:
    """Arrival time must not replace the event time carried by an old measurement."""
    module = _module()
    _apply(module, 1)
    _apply(module, 2, _packet())
    config = module.support_configuration
    assert config.disposition == "delayed"
    assert config.observation.event_cycle == 1 and config.available_cycle == 2
    assert config.last_supported_event_cycle is None
    _apply(module, 3, _packet())
    assert module.support_configuration.disposition == "duplicate"
    assert module.support_configuration.last_supported_event_cycle is None


def test_delayed_application_does_not_launder_a_future_at_receipt_packet() -> None:
    """Even later application cannot make pre-receipt future evidence legitimate."""
    module = _module()
    result = module.poll_observation(_observation(_packet(1, 2)), cycle_id=1, observation_number=1)
    result = replace(result, timing=replace(result.timing, available_cycle=2, expires_after_cycle=2))
    module.apply_result(result.mark_applied(2), cycle_id=2)
    assert module.support_configuration.disposition == "future"
    assert module.support_configuration.last_supported_event_cycle is None


@pytest.mark.parametrize("predicates,angle,reason", [
    (("posture:fallen",), 90.0, "fallen_scaffold_vs_near_upright_measurement"),
    (("posture:standing",), 0.0, "standing_scaffold_vs_near_horizontal_measurement"),
    (("posture:fallen", "posture:standing"), 0.0, "ambiguous_posture_scaffold"),
])
def test_contradictions_are_retained_without_new_authority(predicates: tuple[str, ...], angle: float, reason: str) -> None:
    """The read-only path preserves both inputs rather than picking a convenient one."""
    runtime, _trace = _runtime()
    observation = _observation(_packet(body_ground_angle_degrees=angle), predicates=predicates)
    result = runtime.run_cycle(observation, observation_number=1)
    config = runtime.body_sensory.support_configuration
    assert config.disposition == "conflict"
    assert config.discrepancy == reason
    assert config.observation.body_ground_angle_degrees == angle
    assert config.last_supported_event_cycle is None
    assert config.behavioral_authority is False
    baseline, _baseline_trace = _runtime(enabled=False)
    assert result.as_dict() == baseline.run_cycle(observation, observation_number=1).as_dict()


@pytest.mark.parametrize("angle", [15.01, 45.0, 74.99])
def test_intermediate_pose_is_not_forced_into_a_binary_posture(angle: float) -> None:
    """A changing intermediate geometry must not automatically contradict 'fallen'."""
    module = _module()
    _apply(module, 1, _packet(body_ground_angle_degrees=angle))
    assert module.support_configuration.discrepancy is None
    assert module.support_configuration.observation.body_ground_angle_degrees == angle
    assert module.current_state.posture.value == "fallen"


def test_empty_invalid_and_absent_inputs_clear_current_measurement_not_the_watermark() -> None:
    """Invalid evidence cannot leave a stale measured configuration marked current."""
    module = _module()
    _apply(module, 1, _packet())
    _apply(module, 2, _packet(2, 2, body_ground_angle_degrees=None, useful_loading=None, destabilization=None, lateral_contact=None))
    assert module.support_configuration.disposition == "empty"
    _apply(module, 3, _packet(3, 3, useful_loading=float("nan")))
    assert module.support_configuration.disposition == "invalid"
    assert module.support_configuration.observation is None
    _apply(module, 4)
    assert module.support_configuration.disposition == "missing"
    assert module.support_configuration.observation is None
    assert module.support_configuration.last_supported_event_cycle == 1
    assert module.support_configuration.evidence_current is False


def test_disabled_consumer_never_creates_or_stages_measured_state() -> None:
    """Explicitly disabled computation remains the original A0 path."""
    module = _module(enabled=False)
    application = _apply(module, 1, _packet())
    assert application.sample.support_observation is None
    assert module.support_configuration is None
    with pytest.raises(TypeError):
        Nca8BodySensoryModuleV1(module.map_library, support_observation_enabled=1)
    with pytest.raises(TypeError):
        Nca8SessionConfigV1(support_observation_enabled=1)


def test_measurements_cannot_select_a_task_without_scaffold_or_attention() -> None:
    """The measured record is not a covert replacement for A0 task authority."""
    runtime, _trace = _runtime()
    result = runtime.run_cycle(_observation(_packet(), predicates=()), observation_number=1)
    assert result.output == "NO_ACTION" and result.wnm is None and result.pnm is None
    assert runtime.body_sensory.support_configuration.evidence_current
    ablated, _ablated_trace = _runtime(attention=False)
    result = ablated.run_cycle(_observation(_packet()), observation_number=1)
    assert result.output == "NO_ACTION" and result.pnm is None


def test_read_only_trace_demonstrates_same_pose_different_measurements() -> None:
    """Show two synthetic series without claiming that a trajectory estimator exists."""
    results = []
    measured_configs = []
    for label, values in (
        ("increasing loading / decreasing destabilization", ((0.2, 0.8), (0.6, 0.2))),
        ("decreasing loading / increasing destabilization", ((0.6, 0.2), (0.2, 0.8))),
    ):
        runtime, trace = _runtime()
        signature = runtime.map_library.durable_record_signature()
        print(f"\nSynthetic read-only inputs: {label}; coarse posture remains fallen.")
        run_results = []
        for cycle, (loading, instability) in enumerate(values, start=1):
            observation = _observation(_packet(cycle, cycle, useful_loading=loading, destabilization=instability))
            run_results.append(runtime.run_cycle(observation, observation_number=cycle).as_dict())
        events = tuple(event for event in trace.snapshot() if event.channel == "support_observation")
        assert len(events) == 2
        assert all(event.phase == CyclePhase.UPDATE_OUTCOMES.name for event in events)
        print("\n".join(render_explanatory_trace_lines_v1(events)))
        assert runtime.map_library.durable_record_signature() == signature
        assert runtime.map_library.durable_map_count == 1
        assert runtime.map_library.current_state_count == 1
        results.append(run_results)
        measured_configs.append(runtime.body_sensory.support_configuration.as_dict())
    assert results[0] == results[1]
    assert measured_configs[0] != measured_configs[1]


def test_rendering_and_trace_eviction_cannot_affect_cognition_or_measured_support() -> None:
    """Capacity and repeated presentation must not become another timing/control input."""
    first, small = _runtime(capacity=1)
    second, large = _runtime(capacity=256)
    for cycle in range(1, 5):
        observation = _observation(_packet(cycle, cycle))
        assert first.run_cycle(observation, observation_number=cycle).as_dict() == second.run_cycle(
            observation, observation_number=cycle,
        ).as_dict()
        before = large.as_canonical_json_bytes()
        assert render_explanatory_trace_lines_v1(large.snapshot()) == render_explanatory_trace_lines_v1(large.snapshot())
        assert large.as_canonical_json_bytes() == before
        assert first.body_sensory.support_configuration == second.body_sensory.support_configuration
    assert small.retained_count == 1


def test_a0_gate_a_survives_opt_in_missing_measurements_and_reset_is_session_local() -> None:
    """Real Gate A stays six cycles/five actions; no packet is fabricated by the environment."""
    default = Nca8SessionV1()
    observed = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    other = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    baseline = default.run_gate_a(reset_first=False)
    summary = observed.run_gate_a(reset_first=False)
    assert baseline.as_dict() == summary.as_dict()
    assert (summary.cycles_run, summary.stand_up_actions, summary.successful_application_id) == (6, 5, "application:stand_up:5")
    assert default.support_configuration is None
    assert observed.support_configuration.disposition == "missing"
    assert observed.support_configuration.last_supported_event_cycle is None
    assert other.support_configuration is None
    source = observed.durable_posture_support_map
    observed.reset()
    assert observed.support_configuration is None
    assert other.status().cognitive_cycles == 0
    assert observed.durable_posture_support_map.record_signature() == source.record_signature()


def test_measured_path_is_byte_deterministic_and_independent_of_packet_key_order() -> None:
    """Fresh measured runs must replay exactly through the existing canonical trace."""
    first, first_trace = _runtime()
    second, second_trace = _runtime()
    for cycle in range(1, 4):
        packet = _packet(cycle, cycle, useful_loading=cycle / 4)
        reversed_packet = dict(reversed(tuple(packet.items())))
        first.run_cycle(_observation(packet), observation_number=cycle)
        second.run_cycle(_observation(reversed_packet), observation_number=cycle)
        assert first_trace.as_canonical_json_bytes() == second_trace.as_canonical_json_bytes()
        assert first.body_sensory.support_configuration == second.body_sensory.support_configuration


def test_session_reset_clears_a_used_measurement_watermark(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real session reset must accept sample 1 again, not carry an earlier replay watermark."""
    original_reset = Nca8EnvironmentBridgeV1.reset
    measured = _observation(_packet()).support_observation

    def reset_with_synthetic_packet(bridge: Nca8EnvironmentBridgeV1, *, seed: int):
        reset_result = original_reset(bridge, seed=seed)
        observation = replace(reset_result.observation, support_observation=measured)
        return replace(reset_result, observation=observation)

    # Only the test supplies this already-firewalled packet; physical stepping
    # still uses the real environment bridge and no production backend changes.
    monkeypatch.setattr(Nca8EnvironmentBridgeV1, "reset", reset_with_synthetic_packet)
    session = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    assert session.support_configuration is None
    session.run_cognitive_cycle()
    assert session.support_configuration.disposition == "current"
    assert session.support_configuration.last_supported_event_cycle == 1
    first_trace = session.trace_canonical_bytes()
    session.reset()
    assert session.support_configuration is None
    assert session.status().lifecycle_generation == 2
    session.run_cognitive_cycle()
    assert session.support_configuration.disposition == "current"
    assert session.support_configuration.last_supported_event_cycle == 1
    assert session.status().cognitive_cycles == 1
    assert session.trace_canonical_bytes() != first_trace  # explicit generation changed
