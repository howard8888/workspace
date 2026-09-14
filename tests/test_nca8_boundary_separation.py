#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1R-B: actual internal/world/input order and fail-closed execution.

These tests exercise the running code, not only renderer text. Injected faults
are software/transport experiments, not animal behavior. A world return, action
permission and later task success remain distinct. No test skips a dependency
or replaces a failed world step with legacy cognition.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import FrozenInstanceError, replace
import inspect
import json
from pathlib import Path
import re

import pytest

from cca8_env import EnvObservation
import nca8_adapters
from nca8_adapters import Nca8EnvironmentBridgeV1, adapt_env_observation_v1
from nca8_handoff import Nca8InternalHandoffV1, Nca8PhaseEDispatchV1
import nca8_menu
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8EpisodeRunnerV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1, render_explanatory_trace_lines_v1, render_flow_trace_lines_v1


def _components(*, enabled: bool = True, generation: int = 1):
    """Create an isolated real bridge/core/driver with a controllable acceptance boundary."""
    bridge = Nca8EnvironmentBridgeV1(scenario_name="newborn_goat_first_hour_benchmark_hard")
    initial = bridge.reset(seed=19).observation
    trace = Nca8TraceBufferV1(256)
    runtime = Nca8CognitiveRuntimeV1(
        trace=trace, scheduler=Nca8DeterministicSchedulerV1(),
        handoff=Nca8InternalHandoffV1(enabled=enabled, generation=generation),
    )
    runner = Nca8EpisodeRunnerV1(
        environment_bridge=bridge, cognitive_runtime=runtime, trace=trace, initial_observation=initial,
    )
    return runtime, runner, bridge, trace


def _core_result():
    """Return a real closed core's ready receipt without executing a world step."""
    runtime, runner, _, trace = _components()
    result = runtime.run_cycle(runner.pending_observation, observation_number=1)
    return runtime, result, trace


def _details(trace, channel: str):
    """Return the last matching actual event's details, preserving its stored values."""
    return dict([event for event in trace.snapshot() if event.channel == channel][-1].details)


def _text(trace) -> str:
    """Render only immutable events; no additional cognitive or world operation."""
    return "\n".join(render_flow_trace_lines_v1(trace.snapshot()))


def _assert_stopped(runtime, runner, *, status: str) -> None:
    """Check safe retry/permission/input behavior without assuming the task failed."""
    assert runner.reset_required and runtime.reset_required
    assert runner.execution_status == status
    assert not runner.has_pending_observation
    with pytest.raises(RuntimeError, match="pending observation"):
        _ = runner.pending_observation
    with pytest.raises(RuntimeError, match="reset"):
        runner.run_cycle()
    with pytest.raises(RuntimeError, match="reset"):
        runtime.run_cycle(adapt_env_observation_v1(EnvObservation()), observation_number=runtime.cognitive_cycles + 1)
    assert runtime.body_runtime.current_lower_request is None
    assert runtime.body_runtime.current_envelope.status.value == "cancelled"


def test_real_core_closes_before_world_and_admission_with_no_callback(monkeypatch) -> None:
    """Observe actual method entry, core counters and source content at each boundary."""
    runtime, runner, bridge, trace = _components()
    observations = []
    advance = bridge.advance_task_action
    admit = bridge.admit_observation

    def watch_advance(action):
        assert runtime.cognitive_cycles == 1
        assert trace.snapshot()[-1].message == "CognitiveCycle_1 closed"
        assert runtime.handoff.receipt.disposition == "consumed"
        assert runtime.last_applied_observation_number == 1
        observations.append("world")
        return advance(action)

    def watch_admit(receipt):
        assert trace.snapshot()[-1].channel == "dispatch"
        assert runtime.last_applied_observation_number == 1
        observations.append("input")
        return admit(receipt)

    monkeypatch.setattr(bridge, "advance_task_action", watch_advance)
    monkeypatch.setattr(bridge, "admit_observation", watch_admit)
    result = runner.run_cycle()
    assert observations == ["world", "input"]
    assert result.environment_step == 1
    assert runner.pending_observation_number == 2
    assert runtime.last_applied_observation_number == 1
    tail = [(e.channel, e.phase) for e in trace.snapshot()[-7:]]
    assert tail == [
        ("handoff", "PROJECT_DISPATCH"), ("learning", "LEARNING_SCHEDULE"),
        ("scheduler", "LEARNING_SCHEDULE"), ("cycle", None),
        ("dispatch", None), ("input", None), ("firewall", None),
    ]
    assert "phase_e_hook" not in inspect.signature(runtime.run_cycle).parameters


def test_standalone_core_never_advances_environment_and_requires_receipt_disposition(monkeypatch) -> None:
    """A closed core cannot silently overwrite an unconsumed action on its next pass."""
    runtime, runner, bridge, trace = _components()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("world access inside cognitive call")

    monkeypatch.setattr(bridge, "advance_task_action", forbidden)
    monkeypatch.setattr(Nca8EnvironmentBridgeV1, "apply_task_action", forbidden)
    observation = runner.pending_observation
    result = runtime.run_cycle(observation, observation_number=1)
    assert result.handoff_receipt.disposition == "ready"
    assert trace.snapshot()[-1].message == "CognitiveCycle_1 closed"
    assert not any(e.channel in {"dispatch", "input"} for e in trace.snapshot())
    with pytest.raises(RuntimeError, match="consumption or cancellation"):
        runtime.run_cycle(observation, observation_number=2)
    assert runtime.cognitive_cycles == 1
    runtime.handoff.consume(result.handoff_receipt)
    second = runtime.run_cycle(observation, observation_number=2)
    assert second.cycle_id == 2


def test_core_has_no_world_evolution_attributes_or_action_callback_signature() -> None:
    """Guard the functional split structurally as well as through dynamic method spies."""
    tree = ast.parse(inspect.getsource(Nca8CognitiveRuntimeV1))
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not attributes & {"apply_task_action", "advance_task_action", "admit_observation", "apply_action", "_environment_bridge"}
    assert "phase_e_hook" not in inspect.signature(Nca8CognitiveRuntimeV1.run_cycle).parameters


@pytest.mark.parametrize("config", ({}, {"attention_enabled": False}, {"navigation_enabled": False}, {"body_action_handoff_enabled": False}))
def test_each_successful_runner_step_advances_once_including_null(monkeypatch, config) -> None:
    """Null output is one physical-time advance, not zero or a fabricated task token."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**config))
    bridge = session._environment_bridge
    original = bridge._environment.apply_action
    calls = []

    def apply(action, *, ctx):
        calls.append(action)
        return original(action, ctx=ctx)

    monkeypatch.setattr(bridge._environment, "apply_action", apply)
    for cycle in range(1, 4):
        result = session.run_cognitive_cycle()
        assert result.environment_step == cycle
        assert len(calls) == cycle
        assert calls[-1] == result.environment_action
        assert session._cognitive_runtime.last_applied_observation_number == cycle
        assert session.status().handoff_disposition == "consumed"
    if config:
        assert all(token is None for token in calls)
    else:
        assert all(token == "policy:stand_up" for token in calls)


def test_acceptance_refusal_is_not_execution_or_body_veto() -> None:
    """A boundary refusal preserves the committed request but prevents the world step."""
    runtime, runner, _, trace = _components(enabled=False)
    with pytest.raises(RuntimeError, match="refused"):
        runner.run_cycle()
    assert runtime.handoff.receipt.disposition == "refused"
    assert runtime.last_commitment.task_action == "STAND_UP"
    assert runtime.last_prediction_outcomes[-1].status.value == "not_applied"
    assert runtime.cognitive_cycles == 0
    assert not any(e.channel in {"dispatch", "input", "handoff"} for e in trace.snapshot())
    _assert_stopped(runtime, runner, status="not_attempted")
    assert _details(trace, "boundary_failure")["handoff_disposition"] == "refused"


@pytest.mark.parametrize("failure", ("learning_report", "scheduler_finish", "closure_report"))
def test_f_or_report_failure_cancels_accepted_request_before_world(monkeypatch, failure) -> None:
    """An exception after E retains the immutable commitment, not fictitious execution."""
    runtime, runner, bridge, trace = _components()
    advance_count = []
    original_append = trace.append

    def fail(*_args, **_kwargs):
        assert runtime.handoff.receipt.disposition == "accepted"
        raise RuntimeError("injected internal failure")

    def append(channel, message, **kwargs):
        if (failure == "learning_report" and channel == "learning") or (
            failure == "closure_report" and channel == "cycle" and message.endswith(" closed")
        ):
            return fail()
        return original_append(channel, message, **kwargs)

    monkeypatch.setattr(trace, "append", append)
    if failure == "scheduler_finish":
        monkeypatch.setattr(runtime.scheduler, "phase_f_finish", fail)
    monkeypatch.setattr(bridge, "advance_task_action", lambda _action: advance_count.append("unexpected"))
    with pytest.raises(RuntimeError, match="injected internal failure"):
        runner.run_cycle()
    assert not advance_count
    receipt = runtime.handoff.receipt
    assert receipt.disposition == "cancelled"
    assert receipt.dispatch.commitment is runtime.last_commitment
    assert runtime.last_commitment.task_action == "STAND_UP"
    with pytest.raises(FrozenInstanceError):
        runtime.last_commitment.task_action = None
    assert runtime.prediction.outcome_history()[-1].status.value == "not_applied"
    _assert_stopped(runtime, runner, status="not_attempted")


def test_failure_before_current_e_does_not_mark_previous_executed_request_not_applied(monkeypatch) -> None:
    """The next cycle's failure cannot erase the preceding action's unresolved evidence claim."""
    runtime, runner, _, _ = _components()
    first = runner.run_cycle()
    pending = runtime.prediction.pending_snapshot()

    def fail(*_args, **_kwargs):
        raise RuntimeError("input processing failed")

    monkeypatch.setattr(runtime, "_apply_phase_c_results", fail)
    with pytest.raises(RuntimeError, match="input processing"):
        runner.run_cycle()
    assert runtime.last_commitment == first.commitment
    assert runtime.prediction.pending_snapshot() == pending
    assert not runtime.prediction.outcome_history()


@pytest.mark.parametrize("side_effect_before_error", (False, True))
def test_external_exception_is_unknown_and_never_retried(monkeypatch, side_effect_before_error) -> None:
    """Both pre-effect and post-effect exceptions are conservatively unknown at this interface."""
    runtime, runner, bridge, trace = _components()
    original = bridge._environment.apply_action
    calls = []

    def fail(action, *, ctx):
        calls.append(action)
        if side_effect_before_error:
            original(action, ctx=ctx)
        raise OSError("injected external failure")

    monkeypatch.setattr(bridge._environment, "apply_action", fail)
    with pytest.raises(OSError, match="injected external"):
        runner.run_cycle()
    assert len(calls) == 1
    assert runtime.cognitive_cycles == 1
    assert runtime.handoff.receipt.disposition == "consumed"
    assert runtime.prediction.current_trace.status.value == "pending"
    assert not runtime.prediction.outcome_history()
    _assert_stopped(runtime, runner, status="unknown")
    assert len(calls) == 1
    assert _details(trace, "boundary_failure")["execution_status"] == "unknown"
    assert not any(e.channel in {"input", "firewall", "dispatch"} for e in trace.snapshot())
    with pytest.raises(RuntimeError, match="reset"):
        bridge.apply_task_action(None)
    text = _text(trace)
    assert "unknown" in text and "no automatic retry" in " ".join(text.replace(" :", "").split())
    assert "Untranslated event" not in text


@pytest.mark.parametrize("packet", (None, object()))
def test_missing_or_malformed_next_packet_is_not_a_fresh_old_observation(monkeypatch, packet) -> None:
    """The world call returned; input failed. Neither fact proves prediction success/failure."""
    runtime, runner, bridge, trace = _components()
    original = bridge._environment.apply_action
    old = runner.pending_observation
    calls = []

    def missing(action, *, ctx):
        calls.append(action)
        _, reward, done, info = original(action, ctx=ctx)
        return packet, reward, done, info

    monkeypatch.setattr(bridge._environment, "apply_action", missing)
    with pytest.raises(TypeError, match="missing or malformed"):
        runner.run_cycle()
    assert len(calls) == 1
    assert old.step_index == 0
    assert runtime.last_applied_observation_number == 1
    assert runtime.prediction.current_trace.status.value == "pending"
    assert _details(trace, "boundary_failure")["stage"] == "input_admission"
    assert any(e.channel == "dispatch" for e in trace.snapshot())
    assert not any(e.channel in {"input", "firewall"} for e in trace.snapshot())
    _assert_stopped(runtime, runner, status="returned")
    assert len(calls) == 1


def test_whitelist_exception_after_world_return_requires_reset(monkeypatch) -> None:
    """A transport decoder fault is not a second world attempt or invented body failure."""
    runtime, runner, bridge, trace = _components()

    def fail(_raw):
        raise ValueError("decoder failure")

    monkeypatch.setattr(nca8_adapters, "adapt_env_observation_v1", fail)
    with pytest.raises(ValueError, match="decoder failure"):
        runner.run_cycle()
    assert runtime.handoff.receipt.disposition == "consumed"
    _assert_stopped(runtime, runner, status="returned")
    with pytest.raises(RuntimeError, match="reset"):
        bridge.advance_task_action(None)
    assert _details(trace, "boundary_failure")["stage"] == "input_admission"


def test_logger_failure_does_not_restore_permission_or_mask_original_fault(monkeypatch) -> None:
    """Even when the failure report cannot be written, unsafe retry remains impossible."""
    runtime, runner, _, trace = _components()
    original = trace.append

    def fail(channel, message, **kwargs):
        if channel in {"dispatch", "boundary_failure"}:
            raise RuntimeError("logger unavailable")
        return original(channel, message, **kwargs)

    monkeypatch.setattr(trace, "append", fail)
    with pytest.raises(RuntimeError, match="logger unavailable"):
        runner.run_cycle()
    _assert_stopped(runtime, runner, status="returned")
    assert runtime.last_commitment.task_action == "STAND_UP"


def test_duplicate_consumption_and_copied_receipt_are_rejected() -> None:
    """A ready receipt is an owner-held token, not reusable serialized permission."""
    runtime, result, _ = _core_result()
    slot = runtime.handoff
    ready = result.handoff_receipt
    with pytest.raises(RuntimeError, match="copied"):
        slot.consume(replace(ready))
    action = slot.consume(ready)
    assert action == result.phase_e_dispatch.authorized_task_action
    with pytest.raises(RuntimeError, match="stale"):
        slot.consume(ready)
    with pytest.raises(RuntimeError, match="consumed"):
        slot.consume(slot.receipt)
    assert ready.disposition == "ready" and slot.receipt.disposition == "consumed"


@pytest.mark.parametrize("generation", (1, 2))
def test_foreign_and_cross_generation_receipts_cannot_cross_sessions(generation) -> None:
    """Same action numbers are insufficient, even when diagnostic generation numbers match."""
    first, first_result, _ = _core_result()
    second, runner, _, _ = _components(generation=generation)
    second_result = second.run_cycle(runner.pending_observation, observation_number=1)
    with pytest.raises(RuntimeError, match="foreign"):
        second.handoff.consume(first_result.handoff_receipt)
    assert second.handoff.receipt is second_result.handoff_receipt
    assert first.handoff.receipt is first_result.handoff_receipt


def test_slot_does_not_overwrite_pending_or_reaccept_old_action() -> None:
    """Single-slot bounds and monotonic action identity do not depend on trace capacity."""
    _, result, _ = _core_result()
    slot = Nca8InternalHandoffV1()
    accepted = slot.accept(result.phase_e_dispatch)
    with pytest.raises(RuntimeError, match="previous handoff"):
        slot.accept(result.phase_e_dispatch)
    with pytest.raises(RuntimeError, match="accepted"):
        slot.consume(accepted)
    ready = slot.release_after_close(accepted)
    slot.consume(ready)
    with pytest.raises(RuntimeError, match="next unaccepted"):
        slot.accept(result.phase_e_dispatch)


def test_cancelled_receipt_cannot_execute() -> None:
    """Cancellation before consumption differs from uncertain execution after consumption."""
    runtime, result, _ = _core_result()
    cancelled = runtime.handoff.cancel(result.handoff_receipt, reason="controlled_unconsumed_cancel")
    assert cancelled.disposition == "cancelled"
    with pytest.raises(RuntimeError, match="cancelled"):
        runtime.handoff.consume(cancelled)


@pytest.mark.parametrize("case", ("missing_pnm", "missing_body", "missing_action", "wrong_action", "wrong_pnm", "wrong_envelope"))
def test_inconsistent_handoff_is_rejected_before_acceptance(case) -> None:
    """The receipt cannot authorize a body request unrelated to its committed action/PNM."""
    _, result, _ = _core_result()
    dispatch = result.phase_e_dispatch
    if case == "missing_pnm":
        bad = replace(dispatch, pnm=None)
    elif case == "missing_body":
        bad = replace(dispatch, body_handoff=None)
    elif case == "missing_action":
        bad = replace(dispatch, task_action=None)
    elif case == "wrong_action":
        bad = replace(dispatch, task_action=replace(dispatch.task_action, task_action_id="foreign:action"))
    elif case == "wrong_pnm":
        bad = replace(dispatch, pnm=replace(dispatch.pnm, pnm_id="foreign:pnm"))
    else:
        bad = replace(dispatch, body_handoff=replace(
            dispatch.body_handoff, envelope=replace(dispatch.body_handoff.envelope, envelope_id="foreign:envelope"),
        ))
    slot = Nca8InternalHandoffV1()
    with pytest.raises((TypeError, ValueError)):
        slot.accept(bad)
    assert slot.receipt is None


def test_bridge_separates_world_and_input_and_detaches_once(monkeypatch) -> None:
    """Raw packets stay private until the single admission; later mutations cannot affect CCA8."""
    _, _, bridge, _ = _components()
    raw = EnvObservation(predicates=["posture:standing", "oracle:answer"], raw_sensors={"distance_to_mom": 3.0})
    monkeypatch.setattr(bridge._environment, "apply_action", lambda _action, ctx: (raw, 0.0, False, {"step_index": 1}))
    original = nca8_adapters.adapt_env_observation_v1
    decoded = []

    def adapt(packet):
        decoded.append(packet)
        return original(packet)

    monkeypatch.setattr(nca8_adapters, "adapt_env_observation_v1", adapt)
    advance = bridge.advance_task_action(None)
    assert not hasattr(advance, "observation")
    assert not decoded
    with pytest.raises(RuntimeError, match="previous world result"):
        bridge.advance_task_action(None)
    with pytest.raises(RuntimeError, match="copied"):
        bridge.admit_observation(replace(advance))
    step = bridge.admit_observation(advance)
    assert len(decoded) == 1
    assert step.observation.predicates == ("posture:standing",)
    raw.predicates.clear()
    raw.raw_sensors["distance_to_mom"] = 999.0
    assert step.observation.predicates == ("posture:standing",)
    assert step.observation.raw_sensors["distance_to_mom"] == 3.0
    with pytest.raises(RuntimeError, match="stale"):
        bridge.admit_observation(advance)
    assert len(decoded) == 1


def test_future_body_evidence_cannot_influence_earlier_commitment(monkeypatch) -> None:
    """A world that immediately returns standing must still be interpreted only next cycle."""
    runtime, runner, bridge, _ = _components()
    raw = EnvObservation(predicates=["posture:standing"], env_meta={"step_index": 1})
    monkeypatch.setattr(bridge._environment, "apply_action", lambda _action, ctx: (raw, 0.0, False, {"step_index": 1}))
    first = runner.run_cycle()
    assert first.commitment.task_action == "STAND_UP"
    assert first.posture_support_state.posture.value == "fallen"
    assert runtime.last_applied_observation_number == 1
    assert runner.pending_observation.predicates == ("posture:standing",)
    second = runner.run_cycle()
    assert second.posture_support_state.posture.value == "standing"
    assert second.prediction_outcomes[0].status.value == "success"
    assert second.commitment.task_action is None
    assert first.commitment.task_action == "STAND_UP"


def test_invalid_optional_support_packet_keeps_existing_read_only_contract(monkeypatch) -> None:
    """Transport failure of the whole observation and rejection of optional support differ."""
    session = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    raw = EnvObservation(predicates=["posture:fallen"], raw_sensors={"posture_support_v1": {"unknown": "not evidence"}})
    monkeypatch.setattr(session._environment_bridge._environment, "apply_action", lambda _action, ctx: (raw, 0.0, False, {}))
    session.run_cognitive_cycle()
    assert session.pending_observation.support_observation is None
    assert session.pending_observation.support_observation_error == "unknown_support_fields"
    result = session.run_cognitive_cycle()
    assert result.commitment.task_action == "STAND_UP"
    assert session.support_configuration.behavioral_authority is False
    assert session.status().reset_required is False


def test_protected_stop_between_close_and_world_withholds_request(monkeypatch) -> None:
    """A lower protected event can revoke permission without revising the frozen task."""
    runtime, runner, bridge, trace = _components()
    original = runtime.run_cycle
    attempted = []

    def close_then_stop(*args, **kwargs):
        result = original(*args, **kwargs)
        runner.stop_for_protection(reason="controlled_new_protected_danger")
        return result

    monkeypatch.setattr(runtime, "run_cycle", close_then_stop)
    monkeypatch.setattr(bridge, "advance_task_action", lambda action: attempted.append(action))
    with pytest.raises(RuntimeError, match="protected stop"):
        runner.run_cycle()
    assert not attempted
    assert runtime.last_commitment.task_action == "STAND_UP"
    assert runtime.cognitive_cycles == 1
    assert runtime.handoff.receipt.disposition == "cancelled"
    assert runtime.prediction.outcome_history()[-1].status.value == "not_applied"
    assert _details(trace, "protection")["physical_stop_confirmed"] is False
    _assert_stopped(runtime, runner, status="not_attempted")


def test_protected_stop_after_world_return_does_not_claim_motion_rollback() -> None:
    """The minimal stop seam cancels further permission, not the earlier physical effect."""
    runtime, runner, _, trace = _components()
    first = runner.run_cycle()
    pending = runtime.prediction.pending_snapshot()
    runner.stop_for_protection(reason="controlled_postexecution_hazard")
    assert runtime.last_commitment == first.commitment
    assert runtime.prediction.pending_snapshot() == pending
    assert not runtime.prediction.outcome_history()
    assert _details(trace, "protection")["execution_status"] == "returned"
    assert _details(trace, "protection")["physical_stop_confirmed"] is False
    _assert_stopped(runtime, runner, status="returned")


def test_explicit_session_reset_discards_stopped_receipts_and_stale_input() -> None:
    """Reset starts a new generation; an old receipt cannot authorize the new session."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    old = session._cognitive_runtime.handoff.receipt
    session.stop_for_protection(reason="reset_test")
    assert session.status().reset_required
    status = session.reset()
    assert status.lifecycle_generation == 2
    assert not status.reset_required
    assert status.pending_input_available and status.pending_observation_number == 1
    with pytest.raises(RuntimeError, match="foreign"):
        session._cognitive_runtime.handoff.consume(old)
    session.run_cognitive_cycle()
    assert session.status().handoff_receipt_id == "handoff:g2:a1"


def test_recursive_runner_call_is_rejected_without_second_world_step(monkeypatch) -> None:
    """Accidental reentrancy inside a provider cannot create another cognitive decision."""
    _, runner, bridge, _ = _components()
    original = bridge.advance_task_action
    calls = []

    def advance(action):
        calls.append(action)
        with pytest.raises(RuntimeError, match="already running"):
            runner.run_cycle()
        return original(action)

    monkeypatch.setattr(bridge, "advance_task_action", advance)
    assert runner.run_cycle().environment_step == 1
    assert len(calls) == 1


@pytest.mark.parametrize("width", (60, 96, 140))
def test_current_trace_has_real_separate_domains_and_preserves_ascii_layout(width) -> None:
    """The new boundary records, unlike the historical callback, are not mixed-domain boxes."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    before = session.status(), session.trace_canonical_bytes(), session.pending_observation
    lines = render_flow_trace_lines_v1(session.trace_snapshot(), width=width)
    text = "\n".join(lines)
    flat = " ".join(text.split())
    assert all(line.isascii() and len(line) <= width for line in lines)
    assert "P16-1R-B REFERENCE ORDER" in text
    assert "PLANNED TARGET ORDER - NOT EXECUTED" not in text
    assert "DOMAIN: MIXED BOUNDARY REPORT" not in text
    assert "OUTSIDE THE INTERNAL COGNITIVE CYCLE" in flat
    assert "CCA8 INPUT BOUNDARY - ADMIT LATER INPUT" in flat
    assert "Untranslated event" not in text
    assert [int(n) for n in re.findall(r"(?m)^  Record #(\d+) -", text)] == list(range(1, 159))
    assert (session.status(), session.trace_canonical_bytes(), session.pending_observation) == before


def test_partial_new_boundary_trace_does_not_invent_evicted_handoff_or_close() -> None:
    """A protocol marker supplies a source explanation, not missing historical records."""
    session = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=2))
    session.run_cognitive_cycle()
    events = session.trace_snapshot()
    assert [event.channel for event in events] == ["input", "firewall"]
    text = "\n".join(render_flow_trace_lines_v1(events))
    assert "EARLIER RECORDS NOT RETAINED" in text
    assert "PARTIAL VIEW" in text
    assert [int(n) for n in re.findall(r"(?m)^  Record #(\d+) -", text)] == [26, 27]
    assert "[#21]" not in text and "[#24]" not in text


def test_historical_gate_trace_keeps_its_original_mixed_boundary_meaning() -> None:
    """Retain actual pre-refactor events; new code must not reinterpret old record #21."""
    from nca8_trace import Nca8TraceEventV1
    source = json.loads((Path(__file__).parent / "fixtures" / "nca8_gate_a_pre_1r_b.json").read_text())
    events = tuple(Nca8TraceEventV1(**{**raw, "details": tuple(sorted(raw["details"].items()))}) for raw in source["events"])
    text = "\n".join(render_flow_trace_lines_v1(events))
    assert "DOMAIN: MIXED BOUNDARY REPORT" in text
    assert "PLANNED TARGET ORDER - NOT EXECUTED" in text
    assert "[#21] SERVICE: Lower-action / environment adapter" in text
    assert len(events) == 146


def test_menu_reports_missing_input_and_stopped_state_without_retry(monkeypatch, capsys) -> None:
    """A faulted session remains inspectable; the menu does not silently reset or retry it."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    session.stop_for_protection(reason="menu_stop")
    before = session.trace_canonical_bytes()
    responses = iter(("1", "3", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    text = capsys.readouterr().out
    assert "No next sensory input is available" in text
    assert "Reset required before further cycles: yes" in text
    assert "[nca8:stopped]" in text
    assert session.trace_canonical_bytes() == before
    assert session.status().cognitive_cycles == 1


@pytest.mark.parametrize("bad", (None, object()))
def test_missing_receipt_is_rejected_without_consumption(bad) -> None:
    """An empty slot is not a matching null receipt; null output still needs a real receipt."""
    slot = Nca8InternalHandoffV1()
    with pytest.raises(RuntimeError, match="foreign"):
        slot.consume(bad)
    assert slot.receipt is None


@pytest.mark.parametrize("generation", (0, -1, True, 1.5))
def test_handoff_rejects_invalid_generation(generation) -> None:
    """A bounded positive integer identifies one actual owner incarnation."""
    with pytest.raises(ValueError, match="positive integer"):
        Nca8InternalHandoffV1(generation=generation)


def test_handoff_rejects_foreign_body_target() -> None:
    """A correctly named envelope does not make a mismatched effector target valid."""
    _, result, _ = _core_result()
    dispatch = result.phase_e_dispatch
    bad = replace(dispatch, body_handoff=replace(
        dispatch.body_handoff, task_target=replace(dispatch.body_handoff.task_target, target_id="foreign:target"),
    ))
    slot = Nca8InternalHandoffV1()
    with pytest.raises(ValueError, match="body target"):
        slot.accept(bad)
    assert slot.receipt is None


@pytest.mark.parametrize("malformed", (False, True))
def test_failed_bridge_reset_discards_old_world_receipt_and_stays_stopped(monkeypatch, malformed) -> None:
    """A failed world reset cannot resurrect the previously returned raw packet."""
    _, _, bridge, _ = _components()
    old = bridge.advance_task_action(None)
    reset = bridge._environment.reset

    def fail(*, seed):
        if malformed:
            return None, {}
        raise OSError("injected reset failure")

    monkeypatch.setattr(bridge._environment, "reset", fail)
    with pytest.raises((OSError, TypeError)):
        bridge.reset(seed=19)
    with pytest.raises(RuntimeError, match="reset"):
        bridge.admit_observation(old)
    with pytest.raises(RuntimeError, match="reset"):
        bridge.advance_task_action(None)
    monkeypatch.setattr(bridge._environment, "reset", reset)
    bridge.reset(seed=19)
    with pytest.raises(RuntimeError, match="stale"):
        bridge.admit_observation(old)
    assert bridge.apply_no_action().step_index == 1


def test_no_reentrant_world_or_reset_while_admitting_input(monkeypatch) -> None:
    """Input decoding cannot interleave another world step or replace the private world."""
    _, _, bridge, _ = _components()
    advance = bridge.advance_task_action(None)
    original = nca8_adapters.adapt_env_observation_v1

    def adapt(observation):
        with pytest.raises(RuntimeError):
            bridge.advance_task_action(None)
        with pytest.raises(RuntimeError):
            bridge.reset(seed=1)
        with pytest.raises(RuntimeError):
            bridge.admit_observation(advance)
        return original(observation)

    monkeypatch.setattr(nca8_adapters, "adapt_env_observation_v1", adapt)
    assert bridge.admit_observation(advance).step_index == 1


def test_protection_after_consumption_still_prevents_unstarted_world_step(monkeypatch) -> None:
    """Claiming a receipt is not starting the effect; check the stop latch before dispatch."""
    runtime, runner, bridge, _ = _components()
    consume = runtime.handoff.consume
    calls = []

    def consume_then_stop(receipt):
        action = consume(receipt)
        runner.stop_for_protection(reason="controlled_pre_execution_stop")
        return action

    monkeypatch.setattr(runtime.handoff, "consume", consume_then_stop)
    monkeypatch.setattr(bridge, "advance_task_action", lambda action: calls.append(action))
    with pytest.raises(RuntimeError, match="protected stop"):
        runner.run_cycle()
    assert not calls
    assert runtime.handoff.receipt.disposition == "consumed"
    assert runtime.last_prediction_outcomes[-1].status.value == "not_applied"
    _assert_stopped(runtime, runner, status="not_attempted")


@pytest.mark.parametrize("channel", ("dispatch", "input", "firewall"))
def test_reporting_failure_after_world_return_never_reuses_input_or_retries(monkeypatch, channel) -> None:
    """A successful side effect followed by a failed report is not an unexecuted command."""
    runtime, runner, bridge, trace = _components()
    append = trace.append
    advance = bridge.advance_task_action
    calls = []

    def count(action):
        calls.append(action)
        return advance(action)

    def fail_report(got_channel, message, **kwargs):
        if got_channel == channel:
            raise OSError("injected report failure")
        return append(got_channel, message, **kwargs)

    monkeypatch.setattr(bridge, "advance_task_action", count)
    monkeypatch.setattr(trace, "append", fail_report)
    with pytest.raises(OSError, match="report failure"):
        runner.run_cycle()
    assert len(calls) == 1
    assert runtime.last_commitment.task_action == "STAND_UP"
    assert runtime.prediction.current_trace.status.value == "pending"
    assert not runtime.prediction.outcome_history()
    _assert_stopped(runtime, runner, status="returned")
    assert _details(trace, "boundary_failure")["execution_status"] == "returned"


def test_commit_report_failure_preserves_commitment_without_acceptance(monkeypatch) -> None:
    """Committing and reporting are separate: a failed report cannot erase the fixed command."""
    runtime, runner, _, trace = _components()
    append = trace.append

    def fail(channel, message, **kwargs):
        if message.startswith("Phase_E PROJECT_DISPATCH committed"):
            raise OSError("injected commitment report failure")
        return append(channel, message, **kwargs)

    monkeypatch.setattr(trace, "append", fail)
    with pytest.raises(OSError):
        runner.run_cycle()
    assert runtime.last_commitment.task_action == "STAND_UP"
    assert runtime.handoff.receipt is None
    assert runtime.last_prediction_outcomes[-1].status.value == "not_applied"
    _assert_stopped(runtime, runner, status="not_attempted")


@pytest.mark.parametrize("error_type", (KeyboardInterrupt, SystemExit))
def test_external_base_exception_stops_before_propagating(monkeypatch, error_type) -> None:
    """Terminal interruption also needs a fault latch, but must not be swallowed as success."""
    runtime, runner, bridge, trace = _components()

    def fail(_action, *, ctx):
        raise error_type("controlled interruption")

    monkeypatch.setattr(bridge._environment, "apply_action", fail)
    with pytest.raises(error_type):
        runner.run_cycle()
    _assert_stopped(runtime, runner, status="unknown")
    assert _details(trace, "boundary_failure")["reason"] == error_type.__name__


@pytest.mark.parametrize("capacity", (1, 2, 16))
def test_live_boundary_semantics_do_not_depend_on_trace_retention(capacity) -> None:
    """Receipt ownership, pending claims and next actions survive diagnostic event eviction."""
    bounded = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=capacity))
    control = Nca8SessionV1()
    for _ in range(6):
        assert bounded.run_cognitive_cycle().as_dict() == control.run_cognitive_cycle().as_dict()
        assert bounded.pending_observation.as_dict() == control.pending_observation.as_dict()
        assert bounded.status().handoff_disposition == control.status().handoff_disposition == "consumed"
    assert len(bounded.trace_snapshot()) == capacity


def test_latest_failed_cycle_is_not_reported_as_previous_committed_cycle(monkeypatch) -> None:
    """A Cycle-2 ingress failure may reference Action_1 but belongs to the Cycle-2 attempt."""
    runtime, runner, _, trace = _components()
    runner.run_cycle()

    def fail(*_args, **_kwargs):
        raise OSError("controlled next-cycle input failure")

    monkeypatch.setattr(runtime.scheduler, "phase_a_poll_and_stage", fail)
    with pytest.raises(OSError):
        runner.run_cycle()
    event = next(event for event in trace.snapshot() if event.channel == "boundary_failure")
    assert event.cycle_id == 2
    assert dict(event.details)["last_commitment_action_number"] == 1
    assert runtime.prediction.current_trace.status.value == "pending"
