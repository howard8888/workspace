#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrated-flow regression tests: fidelity, chronology, retention, and read-only display.

The production renderer may read only the immutable trace snapshot. These tests
exercise the actual Gate-A runtime and its ablations as well as intentionally
partial/extended traces. Rendering must not infer missing events, mislabel a
blocked action as failed movement, or turn diagnostic prose into a new policy.
"""

from __future__ import annotations

import builtins
from dataclasses import replace
from itertools import product
import re

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
from nca8_contracts import CircuitResultV1, CircuitTimingV1
import nca8_menu
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1, render_explanatory_trace_lines_v1, render_flow_trace_lines_v1


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Share only an immutable six-cycle trace, not a mutable session, between tests."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _text(events: tuple[Nca8TraceEventV1, ...], **kwargs) -> str:
    """Join display lines; retain newlines so order and record coverage stay testable."""
    return "\n".join(render_flow_trace_lines_v1(events, **kwargs))


def _flat(text: str) -> str:
    """Ignore display wrapping only, not words, when checking explanatory sentences."""
    return " ".join(text.split())


def _record_numbers(text: str) -> list[int]:
    """Read each narrative's provenance heading, excluding chart and cross-reference labels."""
    return [int(value) for value in re.findall(r"^  Record #(\d+) -", text, re.MULTILINE)]


def test_flow_covers_every_retained_event_once_in_original_order(gate_events) -> None:
    """Grouping must neither duplicate, drop, sort, nor manufacture execution records."""
    text = _text(gate_events)
    assert _record_numbers(text) == [event.sequence for event in gate_events]
    assert "Untranslated event" not in text
    assert "PARTIAL VIEW" not in text
    assert "GAP:" not in text
    assert "       |  retained order (not a signal wire)\n       v" in text
    assert "PHASE A - COLLECT" in text
    assert "PHASE F - FINISH" in text
    for cycle in range(1, 7):
        assert f"COGNITIVE CYCLE {cycle}\n" in text
    assert "COGNITIVE CYCLE 7\n" not in text


def test_flow_explains_input_counts_without_inventing_packet_contents(gate_events) -> None:
    """No display-time peek into the observation may turn a count into unrecorded contents."""
    text = _flat(_text(gate_events[:3]))
    assert "2 ordinary raw-channel entries" in text
    assert "4 predicate tokens" in text
    assert "0 cue tokens" in text
    assert "NavPatches, not cognitive NavMaps" in text
    assert "not another whitelist pass" in text
    assert "world advances since reset" in text
    assert "posture:fallen" not in text
    assert "kid_temperature" not in text
    assert "distance_to_mom" not in text
    assert "p_scene" not in text


def test_flow_preserves_source_configuration_and_operation_distinctions(gate_events) -> None:
    """Readable source terminology must not claim Attention chooses a primitive or desired reality."""
    text = _flat(_text(tuple(event for event in gate_events if event.cycle_id == 1)))
    assert "Source NavMap posture_support@r1" in text
    assert "through current configuration posture_support:current" in text
    assert "source, not its desired configuration" in text
    assert "Current POSTURE-SUPPORT configuration -> BodyMap" in text
    assert "BodyMap" in text and "never becomes the WNM" in text
    assert "Navigation selects and applies" in text
    assert "Selected primitive: ip:stand_up" in text
    assert "recorded above, not a second operation" in text
    assert "complete geometric or motor implementation" in text


def test_failure_quotes_only_its_actual_earlier_pnm_and_current_evidence(gate_events) -> None:
    """Cycle 2's failure should identify application 1 and the evidence that tested it."""
    text = _flat(_text(tuple(event for event in gate_events if event.cycle_id is None or event.cycle_id <= 2)))
    assert "application application:stand_up:1" in text
    assert "Earlier expectation [record #18]: posture = standing; support = stable" in text
    assert "evidence cycle 2]: posture = fallen; physical support = inadequate" in text
    assert "Recorded prediction outcome: failure" in text
    assert "not a separate outcome-only focal cycle" in text
    assert "does not establish durable learning or select Attention's next source" in text


def test_success_and_cycle_six_null_dispatch_are_not_a_rejected_action(gate_events) -> None:
    """Standing is confirmed by later evidence; Cycle 6 then selects no new body task."""
    text = _text(gate_events)
    cycle_six = _flat(text.split("COGNITIVE CYCLE 6\n", 1)[1])
    assert "Recorded prediction outcome: success" in cycle_six
    assert "evidence cycle 6]: posture = standing; physical support = stable" in cycle_six
    assert "No task was selected by Navigation" in cycle_six
    assert "Action_6:NO_ACTION" in cycle_six
    assert "Environment step after dispatch: 6" in cycle_six
    assert "Observation_7" in cycle_six
    assert "BodyMap blocks the proposed task" not in cycle_six
    assert "handoff was blocked" not in cycle_six
    assert "does not prove that this particular command alone caused" in cycle_six


def test_blocked_handoff_remains_at_its_recorded_position_and_is_not_sensory_failure() -> None:
    """An existing Phase-C metadata error must be visible, not silently sorted before Phase E."""
    session = Nca8SessionV1(Nca8SessionConfigV1(body_action_handoff_enabled=False))
    session.run_cognitive_cycle()
    before = session.trace_canonical_bytes()
    events = session.trace_snapshot()
    outcome = next(event for event in events if event.channel == "outcome")
    assert outcome.phase == "UPDATE_OUTCOMES"
    assert dict(outcome.details)["status"] == "not_applied"
    text = _text(events)
    flattened = _flat(text)
    assert _record_numbers(text) == [event.sequence for event in events]
    assert "TRACE LABEL WARNING" in text
    assert "This is not a second Phase C" in flattened
    assert "NOT APPLIED, not as a failed movement" in flattened
    assert "does not compare later sensory evidence" in flattened
    assert "body-to-environment handoff mechanism is disabled" in flattened
    assert text.index("BodyMap blocks") < text.index("OUTCOME AT THIS POINT") < text.index("Commit Action_1:NO_ACTION")
    assert "Earlier expectation [record" not in text
    assert "Recorded prediction outcome: failure" not in text
    assert "body_target=None" in text
    assert "envelope=None" in text
    chart = text.split("\nCOGNITIVE CYCLE 1\n", 1)[1].split("EXPLANATIONS -", 1)[0]
    assert chart.count("PHASE C1 - APPLY") == 1
    assert chart.count("PHASE C2 - RESOLVE") == 1
    assert "CONTEXT NOTE (not a trace event)" in flattened
    assert session.trace_canonical_bytes() == before


@pytest.mark.parametrize("disabled", ("attention_enabled", "navigation_enabled"))
def test_other_ablations_explain_no_operation_without_inventing_body_rejection(disabled) -> None:
    """A missing focal source or disabled Navigation is distinct from a denied body handoff."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**{disabled: False}))
    session.run_cognitive_cycle()
    text = _flat(_text(session.trace_snapshot()))
    assert "No task was selected by Navigation" in text
    assert "Commit Action_1:NO_ACTION" in text
    assert "BodyMap blocks" not in text
    assert "NOT APPLIED" not in text
    if disabled == "attention_enabled":
        assert "session-start record has Attention disabled" in text
        assert "No Working Navigation Map is available" in text
    else:
        assert "Navigation is disabled for this experiment" in text
        assert "Working relations:" in text


@pytest.mark.parametrize("predicates, expected", (([], "unknown"), (["posture:fallen", "posture:standing"], "ambiguous")))
def test_missing_and_conflicting_posture_evidence_never_becomes_fabricated_standing(predicates, expected) -> None:
    """The old no-candidate message is not sufficient evidence for a standing/stable explanation."""
    trace = Nca8TraceBufferV1(256)
    runtime = Nca8CognitiveRuntimeV1(trace=trace, scheduler=Nca8DeterministicSchedulerV1())
    observation = adapt_env_observation_v1(EnvObservation(predicates=predicates))
    result = runtime.run_cycle(observation, observation_number=1)
    assert result.output == "NO_ACTION"
    text = _flat(_text(trace.snapshot()))
    assert f"posture = {expected}" in text
    assert "Absence of a candidate alone does not prove standing" in text
    assert "posture:unknown" not in text
    assert "posture:ambiguous" not in text
    assert "posture = standing" not in text
    assert "Cross the environment boundary and advance the world" not in text
    assert "closing record not retained" in text


def test_optional_support_companion_is_visible_without_behavioral_authority() -> None:
    """A support-enabled session may report missing measurements; no invented loads or learning."""
    session = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    session.run_cognitive_cycle()
    text = _flat(_text(session.trace_snapshot()))
    assert "Inspect optional support measurements without controlling behavior" in text
    assert "Behavioral authority is explicitly false" in text
    assert "A missing measurement is not zero" in text
    assert "Useful loading: none" in text
    assert "behavioral_authority=False" in text
    assert "Commit Action_1:STAND_UP" in text


@pytest.mark.parametrize("attention, navigation, handoff, support", tuple(product((False, True), repeat=4)))
def test_rendering_between_cycles_cannot_change_behavior_or_any_existing_trace_format(
    attention, navigation, handoff, support,
) -> None:
    """Exercise every switch combination, proving noninterference on future as well as current state."""
    config = Nca8SessionConfigV1(
        seed=19, attention_enabled=attention, navigation_enabled=navigation,
        body_action_handoff_enabled=handoff, support_observation_enabled=support,
    )
    viewed = Nca8SessionV1(config)
    control = Nca8SessionV1(config)
    for _ in range(6):
        assert viewed.run_cognitive_cycle().as_dict() == control.run_cognitive_cycle().as_dict()
        before = viewed.status()
        pending = viewed.pending_observation
        events = viewed.trace_snapshot()
        compact = viewed.trace_lines()
        canonical = viewed.trace_canonical_bytes()
        old_explanatory = render_explanatory_trace_lines_v1(events)
        assert render_flow_trace_lines_v1(events) == render_flow_trace_lines_v1(events)
        assert render_flow_trace_lines_v1(events, include_details=False)
        assert viewed.status() == before == control.status()
        assert viewed.pending_observation is pending
        assert viewed.trace_snapshot() == events
        assert viewed.trace_lines() == compact == control.trace_lines()
        assert viewed.trace_canonical_bytes() == canonical == control.trace_canonical_bytes()
        assert render_explanatory_trace_lines_v1(events) == old_explanatory


@pytest.mark.parametrize("capacity", (1, 5, 12, 20, 40))
def test_actual_retention_eviction_is_explicit_and_preserves_every_remaining_event(capacity) -> None:
    """A retained tail is not displayed as a complete session or reconstructed full cycle."""
    session = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=capacity))
    session.run_gate_a(reset_first=False)
    events = session.trace_snapshot()
    text = _text(events)
    assert "EARLIER RECORDS NOT RETAINED" in text
    assert _record_numbers(text) == [event.sequence for event in events]
    assert "SESSION INITIALIZATION" not in text
    assert "COGNITIVE CYCLE 1\n" not in text
    if capacity <= 20:
        assert "PARTIAL VIEW" in text
    if not any(event.phase == "POLL_STAGE" for event in events):
        assert "| PHASE A - COLLECT" not in text


def test_every_prefix_and_suffix_of_gate_a_renders_without_losing_records(gate_events) -> None:
    """Traces can end or begin at any event, including inside a phase or a prediction chain."""
    for index in range(len(gate_events) + 1):
        for subset in (gate_events[:index], gate_events[index:]):
            lines = render_flow_trace_lines_v1(subset, include_details=False)
            assert _record_numbers("\n".join(lines)) == [event.sequence for event in subset]
            assert all(len(line) <= 96 and line.isascii() for line in lines)


def test_internal_missing_record_breaks_the_flow_arrow(gate_events) -> None:
    """Even when opening and closing markers survive, a missing middle event stays visible."""
    events = tuple(event for event in gate_events[:25] if event.sequence != 9)
    text = _text(events)
    assert "GAP: records #9-#9 are absent" in text
    assert "No flow arrow is drawn across that gap" in _flat(text)
    assert _record_numbers(text) == [event.sequence for event in events]
    assert "[Record #9]" not in text
    assert "| [#9]" not in text
    assert "enduring source-map ID is not available" in _flat(text)


def test_outcome_does_not_reconstruct_an_evicted_expectation(gate_events) -> None:
    """The matched PNM ID remains visible even when its original relation list is unavailable."""
    events = tuple(event for event in gate_events if event.cycle_id == 2)
    text = _flat(_text(events))
    assert "matching earlier PNM contents are not retained" in text
    assert "Earlier expectation [record" not in text
    assert "PNM pnm:application:stand_up:1" in text
    assert "evidence cycle 2" in text


def test_outcome_lookup_never_reads_a_later_event(gate_events) -> None:
    """A reference table must be filled incrementally rather than allowing hindsight lookup."""
    prior = next(event for event in gate_events if event.channel == "pnm")
    outcome = next(event for event in gate_events if event.channel == "outcome")
    events = (replace(outcome, sequence=1), replace(prior, sequence=2, cycle_id=outcome.cycle_id))
    text = _flat(_text(events))
    assert "matching earlier PNM contents are not retained" in text
    assert "Earlier expectation [record" not in text


def test_outcome_does_not_match_a_pnm_with_a_different_application(gate_events) -> None:
    """An equal PNM ID is not enough when the originating application references conflict."""
    events = list(gate_events[:50])
    index = next(index for index, event in enumerate(events) if event.channel == "pnm")
    details = dict(events[index].details)
    details["application_id"] = "application:other"
    events[index] = replace(events[index], details=tuple(sorted(details.items())))
    text = _flat(_text(tuple(events)))
    assert "matching earlier PNM contents are not retained" in text
    assert "Earlier expectation [record #18]" not in text


@pytest.mark.parametrize("width", (60, 80, 96, 140))
def test_rendered_lines_fit_terminal_width_and_are_ascii(gate_events, width) -> None:
    """ASCII boxes and wrapped identifiers should work in ordinary Windows command terminals."""
    lines = render_flow_trace_lines_v1(gate_events, width=width)
    assert lines
    assert all(line.isascii() and len(line) <= width for line in lines)
    assert all(len(line) == width for line in lines if line.startswith(("  +", "  [", "  | ", "  : ")))


@pytest.mark.parametrize("include_details", (False, True))
def test_unknown_event_keeps_its_message_and_every_detail_even_with_details_hidden(include_details) -> None:
    """Unrecognized events must not disappear or acquire a made-up cognitive explanation."""
    trace = Nca8TraceBufferV1()
    trace.append("future", "a new processing event", cycle_id=7, phase="FUTURE_PHASE", details={"novel_value": 37})
    events = trace.snapshot()
    text = _text(events, include_details=include_details)
    assert "Untranslated event - original message" in text
    assert "a new processing event" in text
    assert "novel_value=37" in text
    assert "UNRECOGNIZED STORED PHASE: FUTURE_PHASE" in text
    assert "| PHASE A - COLLECT" not in text
    assert _record_numbers(text) == [1]


def test_controls_unicode_and_long_tokens_are_escaped_and_wrapped_without_mutation() -> None:
    """An unexpected trace message must not execute ANSI escapes or break chart alignment."""
    trace = Nca8TraceBufferV1()
    message = "future\nmessage\t\x1b[2J caf\u00e9"
    token = "x" * 200
    event = trace.append("future", message, details={"long_token": token, "value": "\x1b[31m\u03bb"})
    before = event.as_dict()
    lines = render_flow_trace_lines_v1(trace.snapshot(), width=60, include_details=False)
    text = "\n".join(lines)
    assert all(line.isascii() and len(line) <= 60 for line in lines)
    assert "\x1b" not in text and "\t" not in text
    assert r"\x1b" in text and r"\xe9" in text and r"\u03bb" in text
    assert token in "".join(text.split())
    assert event.as_dict() == before


def test_hiding_technical_details_does_not_hide_the_narrative(gate_events) -> None:
    """The optional API compactness control changes presentation only, never record coverage."""
    text = _text(gate_events[:25], include_details=False)
    assert "Technical record" not in text
    assert _record_numbers(text) == [event.sequence for event in gate_events[:25]]
    assert "Commit Action_1:STAND_UP" in text


def test_renderer_is_quiet_and_empty_trace_is_empty(capsys) -> None:
    """The renderer returns lines instead of printing or creating a runtime to obtain input."""
    assert render_flow_trace_lines_v1(()) == ()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("width", (True, False, 0, 59, 141, 96.5, "96", None))
def test_invalid_width_is_rejected(width) -> None:
    """Bad terminal-width settings must fail predictably before rendering partial output."""
    with pytest.raises(ValueError, match="60 to 140"):
        render_flow_trace_lines_v1((), width=width)


def test_invalid_detail_switch_and_event_type_are_rejected() -> None:
    """A typed display interface should not silently coerce arbitrary settings or mutable inputs."""
    with pytest.raises(TypeError, match="Boolean"):
        render_flow_trace_lines_v1((), include_details="yes")
    with pytest.raises(TypeError, match="Nca8TraceEventV1"):
        render_flow_trace_lines_v1((object(),))


@pytest.mark.parametrize("indices", ((1, 0), (0, 0)))
def test_reversed_or_duplicate_records_are_not_silently_sorted(gate_events, indices) -> None:
    """Sorting would manufacture an apparently valid execution history from invalid input order."""
    with pytest.raises(ValueError, match="strictly increasing"):
        render_flow_trace_lines_v1(tuple(gate_events[index] for index in indices))


def test_menu_four_repeated_rendering_is_read_only_and_matches_public_flow_renderer(monkeypatch, capsys) -> None:
    """The actual menu uses the guided renderer and does not advance cognition to fill its chart."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    before = session.status()
    canonical = session.trace_canonical_bytes()
    pending = session.pending_observation
    expected = _text(session.trace_snapshot())
    responses = iter(("4", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert output.count(expected) == 2
    assert "Trace entries retained: 146 / 256" in output
    assert "(text + flowchart)" in output
    assert "COGNITIVE CYCLE 7\n" not in output
    assert session.status() == before
    assert session.trace_canonical_bytes() == canonical
    assert session.pending_observation is pending


def test_arrival_is_not_eligibility_when_an_extra_result_is_for_a_later_cycle() -> None:
    """A third completed result can be staged in A while only two are eligible in B."""
    def poll_delayed(cycle_id: int) -> tuple[CircuitResultV1, ...]:
        return (CircuitResultV1.from_mapping(
            result_id="delayed:1", source_circuit="delayed", source_sequence=1,
            timing=CircuitTimingV1(sampled_event_cycle=cycle_id, available_cycle=cycle_id + 1),
            payload={"token": "delayed_input"},
        ),)

    trace = Nca8TraceBufferV1(256)
    runtime = Nca8CognitiveRuntimeV1(
        trace=trace, scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(CircuitPollSourceV1("delayed", poll_delayed),),
    )
    runtime.run_cycle(adapt_env_observation_v1(EnvObservation(predicates=["posture:fallen"])), observation_number=1)
    text = _flat(_text(trace.snapshot()))
    assert "polled 3 due processing sources and staged 3 completed results" in text
    assert "Scheduler fixed 2 results" in text
    assert "Results still pending: 1" in text
    assert "delayed:1" in text


def test_gap_at_a_cycle_boundary_is_reported(gate_events) -> None:
    """A missing opening event between otherwise retained cycles must not disappear in grouping."""
    events = tuple(event for event in gate_events if event.sequence != 26)
    text = _flat(_text(events))
    assert "GAP: records #26-#26 are absent between these groups" in text
    assert "PARTIAL VIEW: opening record not retained" in text
    assert "Open CognitiveCycle_2" not in text


def test_future_message_in_a_known_channel_uses_the_original_record() -> None:
    """Recognizing the channel alone is not permission to invent a known operation."""
    trace = Nca8TraceBufferV1()
    trace.append("navigation", "new future navigation event", cycle_id=2, phase="FOCAL_COMMITMENT", details={"new_key": 4})
    text = _text(trace.snapshot(), include_details=False)
    assert "Untranslated event" in text
    assert "new future navigation event" in text
    assert "new_key=4" in text
    assert "Navigation selects and applies" not in text


def test_missing_authorization_field_is_not_treated_as_permission_or_rejection() -> None:
    """Missing fields remain missing, rather than becoming an implicit false or true."""
    trace = Nca8TraceBufferV1()
    trace.append(
        "bodymap", "BodyMap mapped the selected task to a body-relative target and envelope", cycle_id=1,
        phase="PROJECT_DISPATCH", details={"task_action": "STAND_UP"},
    )
    text = _flat(_text(trace.snapshot()))
    assert "authorization not recorded" in text
    assert "No permission or rejection is inferred" in text
    assert "BodyMap blocks" not in text
    assert "BodyMap permits" not in text
