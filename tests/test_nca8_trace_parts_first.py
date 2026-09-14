#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parts-first trace contracts: named components, real routes, no invented hardware.

The schematic is diagnostic instrumentation. It must distinguish CCA8 parts from
representations and simulation services without changing a recorded computation.
Assertions use actual Gate-A events and deliberate partial/unknown inputs. A
source-code wiring description must not turn into a fictional runtime measurement
or a promise that an absent component ran.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product
import re

import pytest

from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1, render_flow_trace_lines_v1


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Provide immutable records from the current implementation, not a hand-drawn success path."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _text(events: tuple[Nca8TraceEventV1, ...], **kwargs) -> str:
    """Render through the public interface; tests never call private layout helpers."""
    return "\n".join(render_flow_trace_lines_v1(events, **kwargs))


def _diagrams(text: str) -> str:
    """Extract main diagrams only, excluding the implementation explanations beneath each cycle."""
    return "\n".join(section.split("EXPLANATIONS -", 1)[0] for section in text.split("RECORDED FLOW -")[1:])


def _node(diagrams: str, sequence: int) -> str:
    """Return one diagram node, without its predecessor's fields or successor's title."""
    following = diagrams.split(f"[#{sequence}] ", 1)[1]
    return re.split(r"(?m)^  (?:\+[- ]+\+|\[-+\])$", following, maxsplit=1)[0]


def _words(text: str) -> str:
    """Ignore wrapping and box edges, not identifiers or the direction of an arrow."""
    return " ".join(re.sub(r"(?m)^  [|:] | [|:]$", "", text).split())


@pytest.mark.parametrize("sequence, category, component", (
    (1, "SERVICE", "Session setup"),
    (4, "SERVICE", "Scheduler"),
    (6, "SERVICE", "Scheduler"),
    (7, "SERVICE", "Cognitive-cycle driver"),
    (8, "SERVICE", "A0 body-sensory scaffold"),
    (9, "REPRESENTATION", "POSTURE-SUPPORT current configuration"),
    (10, "PART", "BodyMap"),
    (11, "PART", "BodyMap"),
    (12, "PART", "Attention"),
    (13, "PART", "Attention"),
    (14, "REPRESENTATION", "Working Navigation Map (WNM)"),
    (15, "PART", "StandUp Instinctive Primitive (IP)"),
    (16, "PART", "Navigation Module"),
    (18, "REPRESENTATION", "Projected NavMap (PNM)"),
    (19, "PART", "BodyMap"),
    (20, "SERVICE", "Cognitive-cycle driver"),
    (21, "SERVICE", "Internal lower-action handoff"),
))
def test_main_nodes_name_architectural_status_before_software(gate_events, sequence, category, component) -> None:
    """Python class/file names must not masquerade as the system's physical parts catalog."""
    node = _words(_node(_diagrams(_text(gate_events)), sequence))
    assert node.startswith(f"{category}: {component}")
    assert "INPUT:" in node and "DO:" in node and "OUTPUT:" in node
    assert ".py" not in node
    assert "Nca8" not in node
    assert "_current_state" not in node


def test_all_main_diagrams_keep_code_details_below_the_diagram(gate_events) -> None:
    """Architecture comes first, while every implementation detail remains inspectable below it."""
    text = _text(gate_events)
    diagrams = _diagrams(text)
    assert ".py" not in diagrams
    assert "PredictionRuntime" not in diagrams
    assert "_current_states" not in diagrams
    assert "Implementation: nca8_sensory.py" in text
    assert "Nca8MapLibraryV1._current_states['posture_support']" in text
    assert "Nca8BodyRuntimeV1._current_state" in text
    assert "Nca8PredictionRuntimeV1._outcome_history" in text


def test_parts_catalog_has_no_invented_sensory_prediction_or_learning_module(gate_events) -> None:
    """Only actually used canonical functional parts get PART boxes, not every Python service."""
    diagrams = _diagrams(_text(gate_events))
    parts = set(re.findall(r"\[#\d+\] PART: ([^|\n]+)", diagrams))
    assert {part.strip() for part in parts} == {
        "Attention", "BodyMap", "Navigation Module", "StandUp Instinctive Primitive (IP)",
    }
    for forbidden in ("PART: SEC", "PART: WorldIndex", "PART: WNM", "PART: PNM", "PART: A0", "PART: Prediction"):
        assert forbidden not in diagrams


def test_phase_headers_are_not_drawn_as_functional_parts(gate_events) -> None:
    """A scheduling subdivision is a heading, not a fifth type of cognitive hardware."""
    diagrams = _diagrams(_text(gate_events))
    assert re.search(r"(?m)^PHASE C1 - APPLY", diagrams)
    assert re.search(r"(?m)^PHASE D - CHOOSE", diagrams)
    assert "PART: PHASE" not in diagrams
    assert "PART: Scheduler" not in diagrams
    assert "Repeated part names show repeated operations of the same session component" in _words(_text(gate_events))


def test_sensory_node_names_existing_source_and_actual_profile_check(gate_events) -> None:
    """C1 applies an already selected profile; it does not invent raw-sensor recognition or an anatomical host."""
    text = _text(gate_events)
    node = _words(_node(_diagrams(text), 8))
    assert "body_sensory:1" in node and "Observation_1" in node
    assert "innate POSTURE-SUPPORT source posture_support@r1" in node
    assert "Check staged lateral_ground_profile_v1" in node
    assert "require agreement with posture:fallen" in node
    assert "POSTURE-SUPPORT map service" in node
    assert "No fully modeled sensory/association circuit" in _words(text)
    assert "This is not posture recognition from raw sensors" in _words(text)
    assert "body-ground angle = 0" not in text


def test_sensory_node_does_not_invent_a_source_id_when_setup_is_missing(gate_events) -> None:
    """The fixed representation name is a code contract; its concrete instance ID needs retained evidence."""
    node = _words(_node(_diagrams(_text(gate_events[2:25])), 8))
    assert "innate POSTURE-SUPPORT source not recorded" in node
    assert "posture_support@r1" not in node


def test_sensory_source_setup_reference_is_not_carried_across_a_gap(gate_events) -> None:
    """Do not fill a missing sequence with old initialization context just to finish a schematic."""
    events = tuple(event for event in gate_events[:25] if event.sequence != 5)
    text = _text(events)
    assert "GAP: records #5-#5" in text
    assert "source not recorded" in _words(_node(_diagrams(text), 8))


def test_bodymap_not_sensory_or_prediction_supplies_the_attention_nomination(gate_events) -> None:
    """Wiring must identify the actual candidate producer even after intervening outcome records."""
    diagrams = _diagrams(_text(gate_events))
    candidate = _words(_node(diagrams, 11))
    bid = _words(_node(diagrams, 12))
    assert candidate.startswith("PART: BodyMap")
    assert "BodyMap creates this nomination, not the sensory service" in candidate
    assert "INPUT: BodyMap -> [source nomination" in bid
    for event in gate_events:
        if event.channel == "attention" and "submitted as an Attention bid" in event.message:
            assert "INPUT: BodyMap -> [source nomination" in _words(_node(diagrams, event.sequence))


def test_c2_displays_two_distinct_evidence_routes(gate_events) -> None:
    """Envelope status reads BodyMap; PNM evaluation reads POSTURE-SUPPORT, not the copied body register."""
    diagrams = _diagrams(_text(gate_events))
    envelope = next(event for event in gate_events if event.channel == "bodymap" and event.phase == "UPDATE_OUTCOMES")
    outcome = next(event for event in gate_events if event.channel == "outcome")
    envelope_node = _words(_node(diagrams, envelope.sequence))
    outcome_node = _words(_node(diagrams, outcome.sequence))
    assert envelope_node.startswith("PART: BodyMap")
    assert "INPUT: [BodyMap current-body register] + [previous authorized action envelope]" in envelope_node
    assert outcome_node.startswith("SERVICE: A0 prediction evaluation")
    assert "[current POSTURE-SUPPORT configuration] from C1; not the BodyMap copy" in outcome_node
    assert "no source nomination or new focal operation" in outcome_node


def test_pnm_and_task_request_are_distinct_outputs_not_a_serial_control_funnel(gate_events) -> None:
    """Creating an expectation must not be drawn as the source of the body action request."""
    diagrams = _diagrams(_text(gate_events))
    navigation = _words(_node(diagrams, 16))
    pnm = _words(_node(diagrams, 18))
    bodymap = _words(_node(diagrams, 19))
    assert "two separate consumers" in navigation
    assert "task request goes separately to BodyMap" in pnm
    assert "INPUT: Navigation application -> [task STAND_UP]" in bodymap
    assert "INPUT: PNM" not in bodymap


@pytest.mark.parametrize("result_ids", ("future_service:9", "", None))
def test_scheduler_does_not_invent_routing_for_missing_or_unrecognized_results(result_ids) -> None:
    """A known scheduler summary is insufficient to assume it contains the usual two packets."""
    trace = Nca8TraceBufferV1()
    trace.append("scheduler", "Phase_C UPDATE_OUTCOMES applied frozen results", cycle_id=2,
                 phase="UPDATE_OUTCOMES", details={"applied_result_count": 1, "result_ids": result_ids})
    node = _words(_node(_diagrams(_text(trace.snapshot())), 1))
    assert "body_sensory:" not in node and "observation_ingress:" not in node
    if result_ids:
        assert "destination not identified" in node
    else:
        assert "No result references recorded" in node


@pytest.mark.parametrize("width", (60, 80, 96, 140))
def test_category_outlines_and_all_lines_fit_the_requested_terminal_width(gate_events, width) -> None:
    """Solid parts, bracketed representations and dashed services remain visually distinct in plain ASCII."""
    lines = render_flow_trace_lines_v1(gate_events, width=width)
    assert all(line.isascii() and len(line) <= width for line in lines)
    assert any(line.startswith("  +- - ") for line in lines)
    assert any(line.startswith("  [---") for line in lines)
    assert any(line.startswith("  +----") for line in lines)
    assert all(len(line) == width for line in lines if line.startswith(("  +", "  [", "  | ", "  : ")))
    assert "retained order (not a signal wire)" in "\n".join(lines)


@pytest.mark.parametrize("settings", tuple(product((False, True), repeat=4)))
def test_parts_first_display_is_read_only_across_all_experiment_switches(settings) -> None:
    """No diagnostic route may change current cognition, pending input or the canonical trace."""
    session = Nca8SessionV1(Nca8SessionConfigV1(
        attention_enabled=settings[0], navigation_enabled=settings[1],
        body_action_handoff_enabled=settings[2], support_observation_enabled=settings[3],
    ))
    session.run_cognitive_cycle()
    session.run_cognitive_cycle()
    before = session.status()
    canonical = session.trace_canonical_bytes()
    pending = session.pending_observation
    events = session.trace_snapshot()
    text = _text(events, include_details=False)
    assert re.findall(r"(?m)^  Record #(\d+) -", text) == [str(event.sequence) for event in events]
    assert text == _text(events, include_details=False)
    assert session.trace_canonical_bytes() == canonical
    assert session.status() == before
    assert session.pending_observation is pending


@pytest.mark.parametrize("channel", ("sensory", "navigation", "prediction", "future"))
def test_unrecognized_event_has_no_guessed_part_or_ports(channel) -> None:
    """A familiar channel cannot grant an unknown event a canonical architectural identity."""
    trace = Nca8TraceBufferV1()
    trace.append(channel, "new unrecognized operation", cycle_id=9, details={"extra": 77})
    text = _text(trace.snapshot(), include_details=False)
    node = _words(_node(_diagrams(text), 1))
    assert node.startswith("UNCLASSIFIED: Untranslated event")
    assert "No input route is inferred" in node and "No output route is inferred" in node
    assert "extra=77" in text
    assert "Implementation:" not in text


def test_other_primitive_query_does_not_get_renamed_standup(gate_events) -> None:
    """Preserve a different recorded primitive identity without inventing a canonical part for it."""
    event = next(event for event in gate_events if event.channel == "navigation")
    details = dict(event.details)
    details["primitive_id"] = "ip:unrecognized"
    changed = replace(event, details=tuple(sorted(details.items())))
    node = _words(_node(_diagrams(_text((changed,))), changed.sequence))
    assert node.startswith("PART: Navigation Module - primitive query")
    assert "ip:unrecognized" in node
    assert "StandUp Instinctive Primitive" not in node
