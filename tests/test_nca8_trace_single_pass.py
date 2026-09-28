#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Keep each option-4 explanation and original evidence with its one record box.

These tests exercise the public renderer and actual menu. They check layout as
well as content: an explanation appended at the end of a cycle must not pass
merely because all its words remain somewhere in the output. The existing
reader-guidance suite retains its wording, raw-evidence, default-output digest,
source-provenance and read-only/continued-execution controls.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path
import re

import pytest

import nca8_menu
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import Nca8TraceEventV1, render_flow_trace_lines_v1


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Retain real reset and six-cycle events, including later outcomes and NO_ACTION."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _blocks(text: str) -> dict[int, str]:
    """Read the single occurrence of each numbered box through the next box.

    Unnumbered context notes and gap warnings may occur between boxes; they are
    not new events. Repeated numbered headings are rejected rather than hidden
    by a dictionary overwrite.
    """
    matches = list(re.finditer(r"\[#(\d+)\]", text))
    result: dict[int, str] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        assert number not in result, f"duplicate record box #{number}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[number] = text[match.start():end]
    return result


def _words(text: str) -> str:
    """Normalize wrapping and box sides for semantic assertions, not layout checks."""
    return " ".join(re.sub(r"(?m)^  [|:] | [|:]$", "", text).split())


def _assert_single_pass(
    events: tuple[Nca8TraceEventV1, ...], *, width: int = 96, include_details: bool = True,
) -> tuple[str, dict[int, str]]:
    """Assert one box, one set of ports and adjacent explanation/evidence per event."""
    before = tuple(event.as_dict() for event in events)
    lines = render_flow_trace_lines_v1(events, width=width, include_details=include_details, reader_guidance=True)
    text = "\n".join(lines)
    assert all(len(line) <= width and line.isascii() and (not line or line.isprintable()) for line in lines)
    blocks = _blocks(text)
    assert list(blocks) == [event.sequence for event in events]
    assert not re.search(r"(?m)^\s*Record #\d+ -", text)
    assert "Technical record #" not in text
    assert "EXPLANATIONS - same record order" not in text
    for event in events:
        block = blocks[event.sequence]
        explanation = "What this means / how the software does it / limits:"
        assert block.count(explanation) == 1
        # Ports stay in the box, not a repeated narrative beneath it. The first
        # box line was sliced at its number; subsequent lines retain their sides.
        for port in ("DOMAIN", "INPUT", "DO", "OUTPUT"):
            assert len(re.findall(rf"(?m)^  [|:] {port}:", block)) == 1
            assert not re.search(rf"(?m)^    {port}:", block)
        assert block.index("OUTPUT:") < block.index(explanation)
        raw_required = include_details or "UNCLASSIFIED:" in block.splitlines()[0]
        if raw_required:
            assert block.count("Original technical evidence:") == 1
            assert block.count("Original message:") == 1
            assert block.index(explanation) < block.index("Original technical evidence:") < block.index("Original message:")
            assert f"channel={event.channel}" in _words(block)
            assert f"stored phase={event.phase or '(outside phases)'}" in _words(block)
        else:
            assert "Original technical evidence:" not in block and "Original message:" not in block
        if "UNCLASSIFIED:" not in block.splitlines()[0]:
            assert block.count("Implementation:") == 1
            assert block.index(explanation) < block.index("Implementation:")
            if raw_required:
                assert block.index("Implementation:") < block.index("Original technical evidence:")
    assert tuple(event.as_dict() for event in events) == before
    return text, blocks


@pytest.mark.parametrize("cycles", (1, 6))
@pytest.mark.parametrize("width", (60, 96, 140))
@pytest.mark.parametrize("include_details", (False, True))
def test_every_explanation_and_evidence_precedes_the_next_record(gate_events, cycles, width, include_details) -> None:
    """Cover setup, all phases, multiple cycles and the later world/input records."""
    events = tuple(e for e in gate_events if e.cycle_id is None or e.cycle_id <= cycles)
    _assert_single_pass(events, width=width, include_details=include_details)


@pytest.mark.parametrize("settings", (
    {"attention_enabled": False},
    {"navigation_enabled": False},
    {"body_action_handoff_enabled": False},
    {"support_observation_enabled": True, "support_dynamics_enabled": True},
    {"trace_capacity": 5},
    {"seed": 37},
))
def test_other_record_shapes_keep_the_same_single_pass_contract(settings) -> None:
    """Vetoes, no Procedure, support facets, eviction and non-default settings stay visible."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**settings))
    for _ in range(6):
        session.run_cognitive_cycle()
    _assert_single_pass(session.trace_snapshot())


def test_each_raw_message_and_field_is_kept_once_under_its_own_record(gate_events) -> None:
    """Raw messages/fields are not renamed or moved under another record's explanation."""
    text, blocks = _assert_single_pass(gate_events)
    assert text.count("Original message:") == len(gate_events)
    for event in gate_events:
        raw = _words(blocks[event.sequence].split("Original message:", 1)[1])
        assert raw.startswith(event.message)
        for key, value in event.details:
            assert f"{key}={value!r}" in raw


def test_first_cycle_c2_context_is_single_and_at_its_original_boundary(gate_events) -> None:
    """The unnumbered C2 explanation follows C1 and precedes the first Phase-D record."""
    events = tuple(e for e in gate_events if e.cycle_id is None or e.cycle_id == 1)
    text, _blocks_by_id = _assert_single_pass(events)
    note = "CONTEXT NOTE (not a trace event): first cycle"
    explanation = "C2 uses later evidence to assess earlier attempts."
    assert text.count(note) == 1 and text.count(explanation) == 1
    c1_last = max(e.sequence for e in events if e.phase == "UPDATE_OUTCOMES")
    d_first = next(e.sequence for e in events if e.phase == "FOCAL_COMMITMENT")
    assert text.index(f"[#{c1_last}]") < text.index(note) < text.index(explanation) < text.index(f"[#{d_first}]")
    assert text.count("PHASE C2 - RESOLVE EARLIER OPERATION OUTCOMES") == 1


def test_not_applied_warning_is_attached_once_to_the_affected_outcome() -> None:
    """The misleading stored phase stays unchanged; its warning is not detached at the end."""
    session = Nca8SessionV1(Nca8SessionConfigV1(body_action_handoff_enabled=False))
    session.run_cognitive_cycle()
    events = session.trace_snapshot()
    text, blocks = _assert_single_pass(events)
    affected = [e for e in events if e.channel == "outcome" and dict(e.details).get("status") == "not_applied"]
    assert len(affected) == 1
    outcome = affected[0]
    assert outcome.phase == "UPDATE_OUTCOMES"
    block = blocks[outcome.sequence]
    assert text.count("TRACE LABEL WARNING:") == block.count("TRACE LABEL WARNING:") == 1
    assert block.index("OUTPUT:") < block.index("TRACE LABEL WARNING:") < block.index("Original technical evidence:")
    assert "stored phase=UPDATE_OUTCOMES" in _words(block)


@pytest.mark.parametrize("missing", ((1,), (2,), (3,), (9,), (18,), (1, 2), (8, 9, 10), (24, 25, 26)))
def test_missing_records_never_reappear_as_detached_explanations(gate_events, missing) -> None:
    """Internal gaps and missing initial evidence remain missing in both boxes and prose."""
    events = tuple(e for e in gate_events[:27] if e.sequence not in missing)
    text, blocks = _assert_single_pass(events)
    assert not set(missing) & set(blocks)
    assert "GAP:" in text or "EARLIER RECORDS NOT RETAINED" in text
    if set(missing) & {1, 2, 3, 8, 9, 10}:
        assert "no earlier NCA8 action exists" not in _words(text)


@pytest.mark.parametrize("start,stop", ((0, 1), (0, 2), (0, 12), (0, 21), (7, 27), (24, 27), (28, 53), (150, None)))
def test_partial_prefixes_and_suffixes_remain_single_pass(gate_events, start, stop) -> None:
    """Single-record and partial-cycle windows do not manufacture missing counterparts."""
    _assert_single_pass(gate_events[start:stop], include_details=False, width=60)


@pytest.mark.parametrize("include_details", (False, True))
def test_unknown_evidence_is_adjacent_escaped_and_not_guessed(gate_events, include_details) -> None:
    """Unknown events retain raw evidence even when ordinary details are hidden."""
    unknown = Nca8TraceEventV1(
        8, "future", "unknown instruction \x1b[31m\nnot an action", 1, "UPDATE_OUTCOMES", (("value", None),),
    )
    events = gate_events[:7] + (unknown,) + gate_events[8:27]
    text, blocks = _assert_single_pass(events, include_details=include_details, width=60)
    block = blocks[8]
    assert "UNCLASSIFIED" in block and "No input route is inferred" in _words(block)
    assert "value=None" in _words(block)
    assert "\\x1b[31m\\n" in block and "\x1b" not in text
    assert "Implementation:" not in block


def test_historical_combined_boundary_keeps_its_evidence_with_its_box() -> None:
    """The historical fixture changes layout, not its combined-call mechanism or record order."""
    fixture = json.loads((Path(__file__).parent / "fixtures/nca8_gate_a_pre_1r_b.json").read_text(encoding="utf-8"))
    events = tuple(Nca8TraceEventV1(
        sequence=e["sequence"], channel=e["channel"], message=e["message"], cycle_id=e["cycle_id"], phase=e["phase"],
        details=tuple(sorted(e["details"].items())),
    ) for e in fixture["events"])
    text, blocks = _assert_single_pass(events)
    assert "MIXED BOUNDARY REPORT" in text and "PLANNED TARGET ORDER - NOT EXECUTED" in text
    assert "P16-1R-B REFERENCE ORDER" not in text
    for event in events:
        assert event.message in _words(blocks[event.sequence])


def test_actual_fault_evidence_precedes_the_next_retained_record(monkeypatch) -> None:
    """A failed outer call still has its original unknown-execution status and no retry."""
    session = Nca8SessionV1()

    def fail(_action, *, ctx):
        raise OSError("single-pass world fault")

    monkeypatch.setattr(session._environment_bridge._environment, "apply_action", fail)
    with pytest.raises(OSError, match="single-pass world fault"):
        session.run_cognitive_cycle()
    before = session.trace_canonical_bytes()
    events = session.trace_snapshot()
    _text, blocks = _assert_single_pass(events)
    event = next(e for e in events if e.channel == "boundary_failure")
    assert "execution_status='unknown'" in _words(blocks[event.sequence])
    assert "no automatic retry" in _words(blocks[event.sequence])
    assert session.trace_canonical_bytes() == before


def test_actual_menu_teaches_one_record_at_a_time(monkeypatch, capsys) -> None:
    """The option-4 header and delivered layout agree; inspection remains read-only."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    before = session.status(), session.trace_canonical_bytes(), session.pending_observation, session._rng.getstate()
    replies = iter(("4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert "Each record appears once." in output
    assert "kept directly below its box, before the next record." in output
    assert "follow each diagram" not in output and "explanations follow the diagram" not in output
    expected, _ = _assert_single_pass(session.trace_snapshot())
    assert output.count(expected) == 1
    assert before == (session.status(), session.trace_canonical_bytes(), session.pending_observation, session._rng.getstate())


def test_empty_trace_and_absent_session_do_not_invent_record_explanations(monkeypatch, capsys) -> None:
    """The explanatory introduction alone is not evidence of session setup."""
    assert render_flow_trace_lines_v1((), reader_guidance=True) == ()
    replies = iter(("4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(replies))
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    output = capsys.readouterr().out
    assert "No NCA8 session has been created" in output and not _blocks(output)
    assert "Original technical evidence:" not in output
