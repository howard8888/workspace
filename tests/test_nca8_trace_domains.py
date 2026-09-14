#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1R-A: truthful domains and bridge timing without changing A0 behavior.

The tests read immutable trace events through public renderers. Domain is a
presentation dimension, not a new cognitive field or a revised scheduler phase.
The frozen fixture was captured from clean HEAD 7dae1dc before this patch; it
checks complete cycle results, canonical events, and next input independently
of wording. Do not regenerate it to conceal a change to cognitive behavior.
"""

from __future__ import annotations

import builtins
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
import nca8_menu
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1, render_explanatory_trace_lines_v1, render_flow_trace_lines_v1


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Retain one immutable successful trace with the historical record numbering."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _text(events: tuple[Nca8TraceEventV1, ...], *, include_details: bool = True, width: int = 96) -> str:
    """Use the public renderer; never call a private domain/classification helper."""
    return "\n".join(render_flow_trace_lines_v1(events, include_details=include_details, width=width))


def _words(text: str) -> str:
    """Remove box edges and wrapping, without removing words or inventing data."""
    return " ".join(re.sub(r"(?m)^  [|:] | [|:]$", "", text).split())


def _node(text: str, sequence: int) -> str:
    """Extract one main diagram node, not the prose or planned target schematic."""
    following = text.split(f"[#{sequence}] ", 1)[1]
    return _words(re.split(r"(?m)^  (?:\+[- ]+\+|\[-+\])$", following, maxsplit=1)[0])


def _note(text: str, sequence: int) -> str:
    """Extract only the requested numbered explanation from a possibly partial trace."""
    return _words(text.split(f"  Record #{sequence} -", 1)[1].split("\n  Record #", 1)[0])


@pytest.mark.parametrize("sequence, category, domain", (
    (1, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
    (2, "SERVICE", "CCA8 INPUT BOUNDARY"),
    (4, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
    (7, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
    (8, "SERVICE", "CCA8 COGNITION"),
    (9, "REPRESENTATION", "CCA8 COGNITION"),
    (10, "PART", "CCA8 COGNITION"),
    (17, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
    (20, "SERVICE", "CCA8 COGNITION"),
    (21, "SERVICE", "MIXED BOUNDARY REPORT"),
    (22, "SERVICE", "CCA8 COGNITION"),
    (23, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
    (24, "SERVICE", "CCA8 INPUT BOUNDARY"),
    (25, "SERVICE", "CCA8 RUNTIME INFRASTRUCTURE"),
))
def test_domain_is_independent_of_part_service_category(
    gate_events: tuple[Nca8TraceEventV1, ...], sequence: int, category: str, domain: str,
) -> None:
    """A sensory service is cognitive work; a scheduler service is infrastructure."""
    node = _node(_text(gate_events[:25]), sequence)
    assert node.startswith(f"{category}:")
    assert f"DOMAIN: {domain}" in node
    assert "INPUT:" in node and "DO:" in node and "OUTPUT:" in node
    assert ".py" not in node


def test_dispatch_describes_world_step_and_adaptation_before_its_report(gate_events: tuple[Nca8TraceEventV1, ...]) -> None:
    """The historical callback spans three domains, not just internal handoff."""
    text = _text(gate_events[:25])
    node = _node(text, 21)
    note = _note(text, 21)
    assert "CCA8 LOWER-ACTION / EMBODIMENT BOUNDARY -> EXTERNAL BODY + WORLD -> CCA8 INPUT BOUNDARY" in node
    assert "Report the completed combined boundary call" in node
    assert "returned an already-adapted next observation" in node
    assert "Nca8EnvironmentBridgeV1.apply_task_action" in note
    assert "adapt_env_observation_v1" in note
    assert "Only after that call returns" in note
    assert "no separate observed sub-records or substep timestamps" in note
    assert "does not establish task success" in note


@pytest.mark.parametrize("sequence", (2, 24))
def test_buffering_is_not_another_whitelist_or_world_step(gate_events: tuple[Nca8TraceEventV1, ...], sequence: int) -> None:
    """Both reset and post-action packets have already crossed the adapter."""
    text = _text(gate_events[:25])
    node = _node(text, sequence)
    note = _note(text, sequence)
    assert "DO: Buffer already-adapted Observation_" in node
    assert "INPUT: [Already-adapted Observation_" in node
    assert "Filter and buffer" not in node
    assert "This is not another filtering pass" in note
    assert "an additional world step" in note
    expanded = gate_events[sequence - 1].render_explanatory()
    assert "already-adapted" in expanded
    assert "passed the NCA8 observation whitelist and was buffered" not in expanded


def test_planned_target_and_stored_cycle_grouping_cannot_masquerade_as_new_order(
    gate_events: tuple[Nca8TraceEventV1, ...],
) -> None:
    """F and close remain after the old combined callback; the target is separate."""
    text = _text(gate_events[:25])
    assert "PLANNED TARGET ORDER - NOT EXECUTED (P16-1R-B)" in text
    assert text.index("PLANNED TARGET ORDER") < text.index("RECORDED FLOW -")
    assert "TRACE GROUP: stored cycle_id" in _words(text)
    assert "NOT cognitive-system walls" in _words(text)
    assert re.findall(r"(?m)^  Record #(\d+) -", text) == [str(event.sequence) for event in gate_events[:25]]
    assert [text.index(f"[#{number}] ") for number in range(20, 26)] == sorted(
        text.index(f"[#{number}] ") for number in range(20, 26)
    )
    assert "[#21a]" not in text and "[#21b]" not in text
    assert "another focal WNM operation" in _note(text, 22)
    assert "runtime accounting, not another cognitive operation or world step" in _note(text, 25)


def test_buffer_only_tail_does_not_reconstruct_missing_dispatch(gate_events: tuple[Nca8TraceEventV1, ...]) -> None:
    """A source-contract explanation may survive truncation; an observed step may not be invented."""
    text = _text(gate_events[23:25], include_details=False)
    assert "EARLIER RECORDS NOT RETAINED" in text
    assert "PARTIAL VIEW" in text
    assert "[#21]" not in text
    assert re.findall(r"(?m)^  Record #(\d+) -", text) == ["24", "25"]
    assert "SOURCE CONTRACT:" in _note(text, 24)
    assert "does not reconstruct any missing earlier event or timestamp" in _note(text, 24)
    assert "DOMAIN: CCA8 INPUT BOUNDARY" in _node(text, 24)


def test_gap_in_tail_preserves_order_and_domains(gate_events: tuple[Nca8TraceEventV1, ...]) -> None:
    """Missing F is a gap in retained evidence, not permission to reorder the bridge."""
    events = tuple(event for event in gate_events[:25] if event.sequence != 22)
    text = _text(events)
    assert "GAP: records #22-#22" in text
    assert "[#22]" not in text
    assert "MIXED BOUNDARY REPORT" in _node(text, 21)
    assert "CCA8 INPUT BOUNDARY" in _node(text, 24)


@pytest.mark.parametrize("channel", ("dispatch", "firewall", "scheduler", "runtime", "body"))
def test_unknown_message_does_not_inherit_a_domain_from_channel_or_phase(channel: str) -> None:
    """A familiar channel and phase are insufficient to classify a future operation."""
    trace = Nca8TraceBufferV1()
    trace.append(channel, "future operation with unspecified ownership", cycle_id=1, phase="PROJECT_DISPATCH", details={"x": 7})
    text = _text(trace.snapshot(), include_details=False)
    assert "DOMAIN: UNCLASSIFIED - no domain inferred from channel or phase" in _node(text, 1)
    assert "Original message: future operation with unspecified ownership" in _words(text)
    assert "x=7" in text
    assert "Implementation:" not in text


def test_missing_dispatch_details_do_not_produce_fictional_measurements(gate_events: tuple[Nca8TraceEventV1, ...]) -> None:
    """Known source wiring is not an observed action token, step number, or clock time."""
    event = replace(gate_events[20], details=())
    text = _text((event,))
    assert "world step not recorded" in _node(text, event.sequence)
    assert "no emission is inferred" in _note(text, event.sequence)
    assert "policy:stand_up" not in text
    assert "world step 1" not in text


@pytest.mark.parametrize("width", (60, 96, 140))
def test_domain_rows_and_target_note_fit_the_existing_ascii_layout(gate_events: tuple[Nca8TraceEventV1, ...], width: int) -> None:
    """Long mixed-domain names wrap inside the existing boxes rather than overflow."""
    lines = render_flow_trace_lines_v1(gate_events[:25], width=width)
    assert all(line.isascii() and len(line) <= width for line in lines)
    assert "MIXED BOUNDARY REPORT" in _words("\n".join(lines))
    assert sum("PLANNED TARGET ORDER" in line for line in lines) == 1


def test_original_message_and_detail_values_remain_available(gate_events: tuple[Nca8TraceEventV1, ...]) -> None:
    """Expanded wording must not replace or hide the underlying canonical message."""
    events = gate_events[:25]
    before = tuple(event.as_dict() for event in events)
    text = _text(events)
    for event in events:
        note = _note(text, event.sequence)
        assert f"Original message: {event.message}" in note
        for key, value in event.details:
            assert f"{key}={value!r}" in note
    assert tuple(event.as_dict() for event in events) == before
    assert "Technical record" not in _text(events, include_details=False)


def _json_digest(value: object) -> str:
    """Hash deterministic JSON exactly as in the pre-patch reference capture."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


_BASELINE = json.loads((Path(__file__).parent / "fixtures" / "nca8_trace_domains_baseline.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _BASELINE["cases"], ids=lambda case: case["name"])
def test_cycle_and_canonical_results_match_the_unmodified_source(case: dict[str, Any]) -> None:
    """Compare against clean 7dae1dc, not just two runs of the newly patched code."""
    session = Nca8SessionV1(Nca8SessionConfigV1(**case["config"]))
    results = []
    for _ in range(case["cycles"]):
        results.append(session.run_cognitive_cycle().as_dict())
        render_flow_trace_lines_v1(session.trace_snapshot(), include_details=False)
        render_explanatory_trace_lines_v1(session.trace_snapshot())
    assert hashlib.sha256(session.trace_canonical_bytes()).hexdigest() == case["canonical_trace_sha256"]
    assert _json_digest(results) == case["cycle_results_sha256"]
    assert _json_digest(session.pending_observation.as_dict()) == case["pending_observation_sha256"]
    assert session.status().as_dict() == case["status"]


def test_pending_outcomes_and_source_owners_are_unchanged_by_display() -> None:
    """Observe the public owner snapshots while a PNM is still pending, then after comparison."""
    trace = Nca8TraceBufferV1(256)
    runtime = Nca8CognitiveRuntimeV1(trace=trace, scheduler=Nca8DeterministicSchedulerV1())
    observation = adapt_env_observation_v1(EnvObservation(predicates=["posture:fallen"]))
    for cycle in (1, 2):
        result = runtime.run_cycle(observation, observation_number=cycle)
        before = (
            runtime.prediction.pending_snapshot(), runtime.prediction.outcome_history(), runtime.prediction.current_trace,
            runtime.map_library.current_map_view(), runtime.map_library.durable_record_signature(), runtime.body_map_state,
            runtime.last_commitment, trace.as_canonical_json_bytes(), result.as_dict(),
        )
        assert runtime.prediction.pending_snapshot()
        render_flow_trace_lines_v1(trace.snapshot())
        render_explanatory_trace_lines_v1(trace.snapshot())
        assert (
            runtime.prediction.pending_snapshot(), runtime.prediction.outcome_history(), runtime.prediction.current_trace,
            runtime.map_library.current_map_view(), runtime.map_library.durable_record_signature(), runtime.body_map_state,
            runtime.last_commitment, trace.as_canonical_json_bytes(), result.as_dict(),
        ) == before


def test_menu_trace_displays_domains_without_advancing_the_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Option 4 uses the new presentation without introducing another cycle or reset."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    before = session.status(), session.trace_canonical_bytes(), session.pending_observation
    responses = iter(("4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out
    assert "Architecture v09.9 is the target" in output
    assert "Planning v16 P16-1R-A improves the explanation only" in output
    assert "DOMAIN: MIXED BOUNDARY REPORT" in _words(output)
    assert "PLANNED TARGET ORDER - NOT EXECUTED" in output
    assert (session.status(), session.trace_canonical_bytes(), session.pending_observation) == before
