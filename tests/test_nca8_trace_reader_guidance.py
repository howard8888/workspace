#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Option-4 reader guidance: comprehensible wording without changed execution.

The opt-in view shares record recognition, provenance, layout and raw technical
rendering with the retained flow renderer. Tests cover actual menu routing,
continued execution after inspection, prior-baseline digests, partial/unknown
records, current versus predicted state, and the A0 approximation boundary.
"""

from __future__ import annotations

import builtins
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import re

import pytest

import nca8_menu
from nca8_adapters import Nca8EnvironmentBridgeV1
from nca8_maps import Nca8MapLibraryV1
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import Nca8TraceEventV1, render_flow_trace_lines_v1


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Use actual immutable output from the six-cycle Gate-A demonstration."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _text(events: tuple[Nca8TraceEventV1, ...], **kwargs) -> str:
    """Join only the opt-in public presentation; no private builder invocation."""
    return "\n".join(render_flow_trace_lines_v1(events, reader_guidance=True, **kwargs))


def _words(text: str) -> str:
    """Remove wrapping and outer box sides, but preserve the words and punctuation."""
    return " ".join(re.sub(r"(?m)^  [|:] | [|:]$", "", text).split())


def _note(text: str, number: int) -> str:
    """Select the numbered explanation rather than a diagram or the next record."""
    return _words(text.split(f"  Record #{number} -", 1)[1].split("\n  Record #", 1)[0])


def _with_fields(event: Nca8TraceEventV1, *, remove: tuple[str, ...] = (), **fields) -> Nca8TraceEventV1:
    """Make explicit synthetic missing/conflicting fields without changing a fixture."""
    values = dict(event.details)
    for key in remove:
        values.pop(key, None)
    values.update(fields)
    return replace(event, details=tuple(sorted(values.items())))


# Captured from exact clean T2 HEAD 5dfeb7749c689c0b53533e1e7e21e7b5a42c5b5c
# during approved Step 1. They are independent expected values, not regenerated
# from the candidate. SHA256 hashes UTF-8 newline-joined default flow text.
_DEFAULT_FLOW_BASELINE = (
    ({}, "e480ebb3687002d2373856c9d3826c2aa62c5c6d94b4d605fd188be7cf3199f6"),
    ({"attention_enabled": False}, "77da75c2aa65d911efd0a5282ddb997de40827722659d732079921f15a79abcd"),
    ({"navigation_enabled": False}, "6cc5dc14df006c5d1379be02788e2a01848b77ab20494c8b3dd385a1301bd3fe"),
    ({"body_action_handoff_enabled": False}, "20d80736c4f5a55a14c460a2c76225925ee17f36ea7bb6cc408c17c3f3b97cf8"),
    ({"support_observation_enabled": True, "support_dynamics_enabled": True},
     "f2a0960d7bd9cf7bab555f04273e93ff914590018df9cd876f3b623ce8f86ca7"),
    ({"trace_capacity": 5}, "73414b1ca55eb4fec0984ef1c633953fc2db116ca7f21cf47af64b5d0a8d562c"),
)


@pytest.mark.parametrize("settings,digest", _DEFAULT_FLOW_BASELINE)
def test_other_callers_keep_the_exact_t2_default_flow(settings, digest) -> None:
    """Scripts and other callers must not silently acquire the new option-4 output."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**settings))
    for _ in range(6):
        session.run_cognitive_cycle()
    events = session.trace_snapshot()
    original = render_flow_trace_lines_v1(events)
    assert hashlib.sha256("\n".join(original).encode("utf-8")).hexdigest() == digest
    assert render_flow_trace_lines_v1(events, reader_guidance=False) == original
    assert render_flow_trace_lines_v1(events, reader_guidance=True) != original
    assert render_flow_trace_lines_v1(events) == original


@pytest.mark.parametrize("value", (None, 0, 1, "yes", [], {}))
def test_reader_switch_requires_a_real_boolean(value) -> None:
    """Reject ambiguous options even with no events; do not silently enable a view."""
    with pytest.raises(TypeError, match="reader_guidance must be Boolean"):
        render_flow_trace_lines_v1((), reader_guidance=value)


@pytest.mark.parametrize("enabled", (False, True))
def test_empty_snapshot_stays_empty(enabled: bool) -> None:
    """A rendering choice must not manufacture setup records for an empty history."""
    assert render_flow_trace_lines_v1((), reader_guidance=enabled) == ()


@pytest.mark.parametrize("width", (60, 72, 80, 96, 120, 140))
@pytest.mark.parametrize("include_details", (False, True))
def test_reader_view_preserves_every_record_and_ascii_width(gate_events, width, include_details) -> None:
    """All retained events stay in order at supported widths, without terminal control codes."""
    before = tuple(event.as_dict() for event in gate_events)
    lines = render_flow_trace_lines_v1(gate_events, width=width, include_details=include_details, reader_guidance=True)
    assert all(line.isascii() and (not line or line.isprintable()) and len(line) <= width for line in lines)
    text = "\n".join(lines)
    expected = [event.sequence for event in gate_events]
    assert [int(x) for x in re.findall(r"\[#(\d+)\]", text)] == expected
    assert [int(x) for x in re.findall(r"(?m)^  Record #(\d+) -", text)] == expected
    assert len(re.findall(r"Technical record #", text)) == (len(expected) if include_details else 0)
    assert tuple(event.as_dict() for event in gate_events) == before


def test_header_defines_notation_phase_and_local_examples(gate_events) -> None:
    """Definitions precede records and distinguish representation, Part and service."""
    intro = _words(_text(gate_events[:27]).split("BEFORE COGNITIVE CYCLE 1", 1)[0])
    for phrase in (
        "BOX KEY - these are notation examples, not execution records",
        "PART: BodyMap Module", "REPRESENTATION: a NavMap Configuration", "SERVICE: session setup",
        "BodyMap Module is a Part; the body state it maintains is a representation",
        "Not every service is a temporary scaffold", "a supplied posture label and predefined geometry",
        "For the actual signal paths, follow the named INPUT source and OUTPUT destination",
        "six scheduled groups of work, A through F", "Phase C, for example",
        "not extra scheduler phases", "not everything below that heading is cognition",
        "Gate A is the retained early StandUp demonstration", "later integrated Righting review is separate",
        "A prediction is not an observation", "not recorded", "explicit null value",
    ):
        assert phrase in intro


def test_setup_has_correct_seed_navmap_and_already_admitted_input(gate_events) -> None:
    """Reset has already filtered/supplied the packet; prose must not invent another admission."""
    text = _text(gate_events[:27])
    setup = _note(text, 1)
    assert "Session setup and preparation of the first input" in text
    assert "generation 1 (session creation/reset number)" in setup
    assert "seed 0 (randomization starting value)" in setup
    assert "pseudo-random-number generator" in setup
    assert "this record does not show a random choice" in setup
    assert "innate POSTURE-SUPPORT NavMap posture_support@r1" in setup
    assert "the first cognitive cycle does not learn it" in setup
    assert "before these setup/buffering records are appended" in setup
    assert "No new input signal is being awaited here" in setup
    assert "awaits the input path" not in text
    buffer_note = _note(text, 2)
    assert "already-admitted observation" in buffer_note
    assert "not another filtering pass" in buffer_note


def test_setup_values_are_not_copied_from_the_teaching_example() -> None:
    """Generation/seed descriptions must report this session, not hard-code 1/0."""
    session = Nca8SessionV1(Nca8SessionConfigV1(seed=37))
    session.reset()
    note = _note(_text(session.trace_snapshot()), 1)
    assert "generation 2 (session creation/reset number)" in note
    assert "Randomization seed: 37" in note
    assert "Session generation: 2" in note
    assert "seed 0" not in note and "Session generation: 1" not in note


def test_main_records_explain_their_distinct_authorities(gate_events) -> None:
    """Current evidence, focal selection, permission and later world work are not synonyms."""
    text = _text(gate_events[:27])
    for number, phrase in (
        (4, "Neither result is a completed NavMap"),
        (5, "not stop the body or freeze every component's state"),
        (6, "scheduler bookkeeping mark"),
        (7, "exactly one observation_ingress result"),
        (8, "This is not recognition from raw sensors"),
        (9, "not acquisition of the innate NavMap"),
        (10, "not a second posture-recognition step"),
        (11, "A candidate is a proposal, not a selection"),
        (12, "not percentages or probabilities"),
        (13, "including the first selection from no previous source"),
        (14, "not another enduring NavMap"),
        (15, "eligibility alone neither selects the Procedure nor authorizes the body"),
        (16, "A Procedure Application is one use of a Procedure"),
        (17, "committed later, after Phase E"),
        (18, "predicted relations, not observations"),
        (19, "Authorized Action Envelope records whether that attempt is permitted"),
        (20, "Committed is not executed"),
        (21, "A receipt identifies the accepted request for later one-time use"),
        (22, "placeholder"),
        (23, "not learned memories or completed tasks"),
        (24, "closes before the world call"),
        (25, "not that the goat stood up"),
        (26, "explicit list of allowed input fields"),
        (27, "not another filtering pass"),
    ):
        assert phrase in _note(text, number), f"record {number}"


def test_every_original_message_and_field_remains_in_the_technical_record(gate_events) -> None:
    """User-friendly descriptions never rename protocol keys or hide inconvenient values."""
    text = _text(gate_events)
    for event in gate_events:
        note = _note(text, event.sequence)
        assert f"Original message: {event.message}" in note
        for key, value in event.details:
            assert f"{key}={value!r}" in note


@pytest.mark.parametrize("settings,_digest", _DEFAULT_FLOW_BASELINE)
def test_repeated_actual_option4_and_subsequent_cycles_are_inert(settings, _digest, monkeypatch, capsys) -> None:
    """Actual menu reads leave input/RNG/state intact and cannot change future decisions."""
    config = Nca8SessionConfigV1(**settings)
    session = Nca8SessionV1(config)
    control = Nca8SessionV1(config)
    assert session.run_cognitive_cycle().as_dict() == control.run_cognitive_cycle().as_dict()
    before = session.status()
    trace_before = session.trace_canonical_bytes()
    input_before = session.pending_observation
    random_before = session._rng.getstate()
    global_random_before = random.getstate()
    representation_before = (session.posture_support_state, session.body_map_state, session.durable_posture_support_map)
    replies = iter(("4", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert output.count(_text(session.trace_snapshot())) == 2
    assert session.status() == before
    assert session.trace_canonical_bytes() == trace_before
    assert session.pending_observation is input_before
    assert session._rng.getstate() == random_before and random.getstate() == global_random_before
    assert (session.posture_support_state, session.body_map_state, session.durable_posture_support_map) == representation_before
    for _ in range(5):
        assert session.run_cognitive_cycle().as_dict() == control.run_cognitive_cycle().as_dict()
        _text(session.trace_snapshot())
    assert session.status() == control.status()
    assert session.trace_canonical_bytes() == control.trace_canonical_bytes()


def test_menu_enables_only_the_option4_rendering_switch(monkeypatch, capsys) -> None:
    """There is no default promotion and no extra renderer call while entering the submenu."""
    session = Nca8SessionV1()
    calls = []
    original = nca8_menu.render_flow_trace_lines_v1

    def record_call(events, **kwargs):
        calls.append(kwargs)
        return original(events, **kwargs)

    monkeypatch.setattr(nca8_menu, "render_flow_trace_lines_v1", record_call)
    replies = iter(("1", "3", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    capsys.readouterr()
    assert calls == [{"reader_guidance": True}]


def test_rendering_does_not_call_geometry_or_the_world(gate_events, monkeypatch) -> None:
    """Explaining the source code must never rerun the mechanism to fill in absent evidence."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("a diagnostic renderer tried to execute a modeled mechanism")

    monkeypatch.setattr(Nca8MapLibraryV1, "evaluate_profile", forbidden)
    monkeypatch.setattr(Nca8EnvironmentBridgeV1, "advance_task_action", forbidden)
    monkeypatch.setattr(Nca8EnvironmentBridgeV1, "admit_observation", forbidden)
    assert "innate POSTURE-SUPPORT NavMap" in _text(gate_events)


@pytest.mark.parametrize("channel", ("session", "sensory", "attention", "bodymap", "dispatch", "future"))
def test_unknown_records_keep_original_evidence_without_a_guessed_owner(channel) -> None:
    """Familiar channel names do not turn an unknown message into a recognized mechanism."""
    event = Nca8TraceEventV1(1, channel, "future message \x1b[31m\nnot an action", 1, "UPDATE_OUTCOMES", (("x", 0),))
    text = _text((event,), include_details=False)
    note = _note(text, 1)
    assert "UNCLASSIFIED" in note and "No input route is inferred" in note
    assert "Original message:" in note and "x=0" in note
    assert "\\x1b[31m\\n" in note and "\x1b" not in text
    assert "ENVIRONMENT ACTION" not in note


@pytest.mark.parametrize("missing", ((1,), (2,), (3,), (9,), (1, 2), (8, 9, 10)))
def test_gaps_do_not_reconstruct_first_cycle_evidence(gate_events, missing) -> None:
    """Only contiguous retained reset context justifies the first-cycle no-earlier-action note."""
    events = tuple(event for event in gate_events[:27] if event.sequence not in missing)
    text = _text(events)
    assert "no earlier NCA8 action exists" not in _words(text)
    assert [int(x) for x in re.findall(r"(?m)^  Record #(\d+) -", text)] == [event.sequence for event in events]
    assert "GAP:" in text or "EARLIER RECORDS NOT RETAINED" in text


@pytest.mark.parametrize("start", (0, 1, 8, 12, 20, 26, 28, 50, 150, 157))
def test_partial_history_and_details_off_never_hide_unknowns_or_create_records(gate_events, start) -> None:
    """Selected prefixes/suffixes exercise retention without an expensive quadratic full-render loop."""
    for events in (gate_events[:start + 1], gate_events[start:]):
        text = _text(events, include_details=False, width=60)
        assert [int(x) for x in re.findall(r"\[#(\d+)\]", text)] == [event.sequence for event in events]
        assert "Original message:" not in text


def test_later_outcome_uses_its_own_retained_prediction_and_current_evidence(gate_events) -> None:
    """The explanatory projection must reuse the shared provenance rather than make an expectation up."""
    second_outcome = next(e for e in gate_events if e.channel == "outcome" and e.cycle_id == 2)
    text = _text(gate_events)
    note = _note(text, second_outcome.sequence)
    assert "Earlier expectation [record #18]: posture = standing; support = stable" in note
    assert "Later POSTURE-SUPPORT interpretation" in note
    assert "Recorded prediction outcome: failure" in note
    assert "does not prove this command alone caused it" in note
    stripped = tuple(e for e in gate_events if e.sequence >= second_outcome.sequence)
    stripped_note = _note(_text(stripped), second_outcome.sequence)
    assert "matching earlier PNM contents are not retained" in stripped_note
    assert "Matching POSTURE-SUPPORT contents are not available" in stripped_note
    assert "Earlier expectation [record #18]" not in stripped_note


@pytest.mark.parametrize("settings,phrase", (
    ({"attention_enabled": False}, "ExecNav selected no Procedure"),
    ({"navigation_enabled": False}, "ExecNav selected no Procedure"),
    ({"body_action_handoff_enabled": False}, "ExecNav selected a Procedure, but"),
))
def test_no_action_is_not_automatically_a_body_veto(settings, phrase) -> None:
    """A missing task choice and a rejected chosen task need different explanations."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**settings))
    session.run_cognitive_cycle()
    events = session.trace_snapshot()
    action = next(e for e in events if e.channel == "runtime" and e.message.startswith("Phase_E"))
    note = _note(_text(events), action.sequence)
    assert phrase in note
    assert "may still advance simulated time" in note
    if settings.get("body_action_handoff_enabled") is False:
        assert "NOT APPLIED means the request was not sent for execution" in _words(_text(events))
        assert "TRACE LABEL WARNING" in _text(events)


@pytest.mark.parametrize("authorization", (True, False, None, "missing"))
def test_missing_authorization_never_becomes_permission(gate_events, authorization) -> None:
    """Absent, null, false and true remain visibly different in prose and exact fields."""
    event = next(e for e in gate_events if e.sequence == 19)
    if authorization == "missing":
        event = _with_fields(event, remove=("authorized",))
    else:
        event = _with_fields(event, authorized=authorization)
    note = _note(_text((event,)), event.sequence)
    if authorization is True:
        assert "BodyMap permits STAND_UP" in note and "authorized=True" in note
    elif authorization is False:
        assert "BodyMap blocks the proposed task" in note and "authorized=False" in note
    else:
        assert "authorization not recorded" in note
        assert "No permission or rejection is inferred" in note


def test_missing_procedure_fields_do_not_claim_no_selection(gate_events) -> None:
    """An omitted field is not the same observation as a recorded None."""
    event = _with_fields(gate_events[15], remove=("selected_primitive_id",))
    note = _note(_text((event,)), event.sequence)
    assert "selected Procedure is not recorded" in note
    assert "cannot determine whether a Procedure was selected" in note
    assert "ExecNav selects no focal operation" not in note
    action = _with_fields(gate_events[19], remove=("selected_primitive",), task_action=None)
    note = _note(_text((action,)), action.sequence)
    assert "whether ExecNav selected a Procedure is not recorded" in note
    assert "ExecNav selected no Procedure" not in note


@pytest.mark.parametrize("posture,profile", (
    ("unknown", None), ("ambiguous", None), ("fallen", "upright_support_profile_v1"),
    ("new-posture", "new-profile"), (None, None),
))
def test_unsupported_sensory_pairs_never_gain_a_fictional_geometry(gate_events, posture, profile) -> None:
    """The reader view retains the shared unknown/ambiguous/mismatched profile boundary."""
    event = _with_fields(gate_events[7], posture=posture, geometry_profile=profile)
    note = _note(_text((event,)), event.sequence)
    if posture in ("unknown", "ambiguous"):
        assert "No canonical profile is selected" in note
    else:
        assert "mechanism not identified" in note
    assert "Check the geometry profile selected from the supplied posture label" not in note
    assert f"posture={posture!r}" in note and f"geometry_profile={profile!r}" in note


def test_historical_combined_boundary_is_not_relabelled_as_separated() -> None:
    """Saved pre-1R-B traces keep their actual sequence and combined-call explanation."""
    fixture = json.loads((Path(__file__).parent / "fixtures/nca8_gate_a_pre_1r_b.json").read_text(encoding="utf-8"))
    events = tuple(Nca8TraceEventV1(
        sequence=e["sequence"], channel=e["channel"], message=e["message"], cycle_id=e["cycle_id"], phase=e["phase"],
        details=tuple(sorted(e["details"].items())),
    ) for e in fixture["events"])
    text = _text(events)
    assert "MIXED BOUNDARY REPORT" in text
    assert "completed combined boundary call" in text
    assert "PLANNED TARGET ORDER - NOT EXECUTED" in text
    assert "P16-1R-B REFERENCE ORDER" not in text
    assert [int(x) for x in re.findall(r"\[#(\d+)\]", text)] == [e.sequence for e in events]


def test_fault_trace_retains_unknown_execution_and_no_retry(monkeypatch) -> None:
    """A real boundary failure is not narrated as task failure, rollback, or a successful stop."""
    session = Nca8SessionV1()

    def fail(_action, *, ctx):
        raise OSError("reader-guidance world fault")

    monkeypatch.setattr(session._environment_bridge._environment, "apply_action", fail)
    with pytest.raises(OSError, match="reader-guidance world fault"):
        session.run_cognitive_cycle()
    before = session.status()
    canonical = session.trace_canonical_bytes()
    text = _text(session.trace_snapshot())
    failure = next(e for e in session.trace_snapshot() if e.channel == "boundary_failure")
    note = _note(text, failure.sequence)
    assert "execution_status='unknown'" in note
    assert "no automatic retry" in note
    assert "not proof of physical rollback" in note
    assert session.status() == before and session.trace_canonical_bytes() == canonical
    with pytest.raises(RuntimeError, match="reset"):
        session.run_cognitive_cycle()
