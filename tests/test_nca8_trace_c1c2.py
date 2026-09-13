#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1/C2 manual-style trace tests: source fidelity, storage, absence, and chronology.

C1/C2 subdivide the display of the existing Phase C. No test grants a renderer
permission to invent a missing event, execute geometry, alter the scheduler, or
turn a returned envelope status into proof that a new comparison took place.
"""

from __future__ import annotations

from dataclasses import replace
import re

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
from nca8_body import Nca8BodyRuntimeV1
from nca8_contracts import CyclePhase
from nca8_maps import Nca8MapLibraryV1, create_posture_support_map_library_v1
from nca8_prediction import Nca8PredictionRuntimeV1
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionConfigV1, Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_sensory import Nca8BodySensoryModuleV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1, render_flow_trace_lines_v1
import nca8_maps


@pytest.fixture(scope="module")
def gate_events() -> tuple[Nca8TraceEventV1, ...]:
    """Share immutable default-session trace records, never mutable cognitive state."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    return session.trace_snapshot()


def _text(events: tuple[Nca8TraceEventV1, ...]) -> str:
    """Join the public renderer's output for narrative and chart assertions."""
    return "\n".join(render_flow_trace_lines_v1(events))


def _flat(text: str) -> str:
    """Remove line wrapping, but retain all words and punctuation."""
    return " ".join(text.split())


def _cycle(text: str, number: int) -> str:
    """Return only one cycle's diagram and prose, excluding later cycles."""
    section = re.split(rf"(?m)^COGNITIVE CYCLE {number}$", text, maxsplit=1)[1]
    return re.split(rf"(?m)^COGNITIVE CYCLE {number + 1}$", section, maxsplit=1)[0]


def _note(text: str, sequence: int) -> str:
    """Return a numbered explanation, not an earlier diagram node or a later event."""
    return text.split(f"  Record #{sequence} -", 1)[1].split("\n  Record #", 1)[0]


def test_c1_c2_are_display_subsections_without_new_scheduler_phases(gate_events) -> None:
    """Preserve the six-phase execution contract and original event phase metadata."""
    assert tuple(phase.name for phase in CyclePhase) == (
        "POLL_STAGE", "FREEZE_ELIGIBLE", "UPDATE_OUTCOMES",
        "FOCAL_COMMITMENT", "PROJECT_DISPATCH", "LEARNING_SCHEDULE",
    )
    before = tuple(event.as_dict() for event in gate_events)
    text = _text(gate_events)
    assert "display subsections of the existing Phase C" in _flat(text)
    assert all(event.phase == "UPDATE_OUTCOMES" for event in gate_events if event.channel == "outcome")
    assert tuple(event.as_dict() for event in gate_events) == before
    assert "stored phase=UPDATE_OUTCOMES" in text
    assert "stored phase=C1" not in text and "stored phase=C2" not in text


def test_first_cycle_has_an_unnumbered_empty_c2_note(gate_events) -> None:
    """Initial absence is explained without manufacturing a 147th trace record."""
    text = _text(gate_events)
    first = _cycle(text, 1)
    assert "BEFORE COGNITIVE CYCLE 1\nSession setup and pending input" in text
    assert "SESSION / BETWEEN-CYCLE RECORDS" not in text
    assert "no earlier NCA8 action exists" in _flat(first)
    assert "CONTEXT NOTE (not a trace event)" in _flat(first)
    assert first.index("PHASE C1 -") < first.index("PHASE C2 -") < first.index("PHASE D -")
    assert "Record #12 - PART: Attention" in first
    records = [int(number) for number in re.findall(r"^  Record #(\d+) -", text, re.MULTILINE)]
    assert records == [event.sequence for event in gate_events]
    assert len(records) == 146
    assert "Recorded prediction outcome:" not in first


@pytest.mark.parametrize("missing", ((1,), (2,), (3,), (9,), (1, 2)))
def test_no_first_cycle_absence_claim_without_contiguous_reset_context(gate_events, missing) -> None:
    """A retained Cycle-1 tail must not pretend that its setup and whole input path were seen."""
    events = tuple(event for event in gate_events[:25] if event.sequence not in missing)
    text = _text(events)
    assert "no earlier NCA8 action exists" not in _flat(text)
    assert "Recorded prediction outcome:" not in text
    assert len(re.findall(r"^  Record #", text, re.MULTILINE)) == len(events)


def test_other_outside_cycle_events_are_not_mislabeled_as_initial_setup() -> None:
    """Only a recognized retained reset can justify the initial-session heading."""
    trace = Nca8TraceBufferV1()
    trace.append("future", "outside-cycle diagnostic")
    text = _text(trace.snapshot())
    assert "RECORDS OUTSIDE A NUMBERED COGNITIVE CYCLE" in text
    assert "BEFORE COGNITIVE CYCLE 1" not in text


def test_cycle_two_routes_body_envelope_and_prediction_records_to_c2(gate_events) -> None:
    """C2 reports two different checks after representation writes and before Attention."""
    second = _cycle(_text(gate_events), 2)
    chart = second.split("EXPLANATIONS -", 1)[0]
    c1 = chart.split("PHASE C1 -", 1)[1].split("PHASE C2 -", 1)[0]
    c2 = chart.split("PHASE C2 -", 1)[1].split("PHASE D -", 1)[0]
    assert "REPRESENTATION: POSTURE-SUPPORT" in c1 and "posture_support:current" in c1
    assert "PART: BodyMap" in c2 and "earlier envelope" in c2
    assert "SERVICE: A0 prediction evaluation" in c2 and "PNM pnm:application:stand_up:1" in c2
    assert "CONTEXT NOTE" not in second
    assert "_last_applied_observation_number = 2" in second
    assert "Nca8BodyRuntimeV1._current_envelope" in second
    assert "Nca8PredictionRuntimeV1._outcome_history" in second


def test_no_c2_outcome_record_does_not_prove_no_pending_predictions() -> None:
    """Later cycles with no selected task get an honest absence note, not invented comparisons."""
    session = Nca8SessionV1(Nca8SessionConfigV1(navigation_enabled=False))
    session.run_cognitive_cycle()
    session.run_cognitive_cycle()
    second = _flat(_cycle(_text(session.trace_snapshot()), 2))
    assert "no earlier-outcome record is present" in second
    assert "does not establish that no prediction is pending" in second
    assert "no earlier NCA8 action exists" not in second
    assert "Recorded prediction outcome:" not in second


def test_missing_c2_records_are_not_reconstructed_across_a_gap(gate_events) -> None:
    """Removing real Cycle-2 outcome events must leave a gap, not a fabricated empty C2."""
    events = tuple(
        event for event in gate_events
        if not (event.cycle_id == 2 and event.channel in ("bodymap", "outcome") and event.phase == "UPDATE_OUTCOMES")
    )
    second = _cycle(_text(events), 2)
    assert "GAP:" in second
    assert "PHASE C2 -" not in second
    assert "CONTEXT NOTE" not in second
    assert "Recorded prediction outcome:" not in second


@pytest.mark.parametrize("channel", ("scheduler", "body", "outcome", "support_observation"))
def test_unknown_phase_c_messages_are_not_assigned_an_invented_subphase(channel) -> None:
    """A familiar channel is insufficient to identify a new event's processing responsibility."""
    trace = Nca8TraceBufferV1()
    trace.append(channel, "future Phase-C event", cycle_id=3, phase="UPDATE_OUTCOMES", details={"new_value": 4, "behavioral_authority": False})
    text = _text(trace.snapshot())
    assert "PHASE C - UNCLASSIFIED RECORD; C1/C2 NOT INFERRED" in text
    assert "Untranslated event - original message" in text
    assert "new_value=4" in text
    assert "PHASE C1 -" not in text and "PHASE C2 -" not in text


def test_reversed_subphase_records_stay_in_recorded_order(gate_events) -> None:
    """The renderer is not allowed to repair an unexpected execution sequence by sorting it."""
    outcome = next(event for event in gate_events if event.channel == "outcome")
    maps = next(event for event in gate_events if event.channel == "maps")
    events = (replace(outcome, sequence=1), replace(maps, sequence=2, cycle_id=outcome.cycle_id))
    text = _text(events)
    assert text.index("PHASE C2 -") < text.index("PHASE C1 -")
    assert re.findall(r"^  Record #(\d+) -", text, re.MULTILINE) == ["1", "2"]


def test_every_recognized_box_names_a_part_representation_or_service(gate_events) -> None:
    """The chart identifies function first; Python filenames remain under the explanation."""
    text = _text(gate_events)
    categories = re.findall(r"^  [|:] \[#\d+\] (PART|REPRESENTATION|SERVICE):", text, re.MULTILINE)
    assert len(categories) == len(gate_events)
    assert set(categories) == {"PART", "REPRESENTATION", "SERVICE"}
    implementations = re.findall(r"^    Implementation: (nca8_[a-z_]+\.py)", text, re.MULTILINE)
    assert len(implementations) == len(gate_events)
    assert {"nca8_runtime.py", "nca8_sensory.py", "nca8_maps.py", "nca8_body.py", "nca8_prediction.py"} <= set(implementations)


def test_c1_explains_identity_checks_and_specific_storage_locations(gate_events) -> None:
    """No vague confirmation or unnamed destination may substitute for the implementation path."""
    first = _flat(_cycle(_text(gate_events), 1))
    for required in (
        "Nca8CognitiveRuntimeV1._apply_phase_c_results",
        "exactly one observation_ingress result",
        "_last_applied_observation_number = 1",
        "Nca8BodySensoryModuleV1._pending_samples",
        "Nca8MapLibraryV1.evaluate_profile('lateral_ground_profile_v1')",
        "cca8_navmap_kernel.py.body_state_evidence",
        "Nca8MapLibraryV1._current_states['posture_support']",
        "Nca8BodyRuntimeV1._current_state",
        "Nca8BodyRuntimeV1._posture_support_candidate",
        "not independently measured loading",
        "Numeric geometry values are not recorded",
    ):
        assert required in first
    assert "already happened" in first
    assert "source-code description" in first
    assert "body-ground angle = 0" not in first


@pytest.mark.parametrize("posture, profile", (("fallen", "lateral_ground_profile_v1"), ("standing", "upright_support_profile_v1")))
def test_staged_result_really_defers_geometry_and_storage_until_application(monkeypatch, posture, profile) -> None:
    """Check the actual source contract described in A, B and C1, not just strings in a fixture."""
    library = create_posture_support_map_library_v1()
    sensory = Nca8BodySensoryModuleV1(library)
    calls = []
    original = nca8_maps.body_state_evidence

    def counted_geometry(*args, **kwargs):
        """Record actual map-kernel calls without changing their results."""
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(nca8_maps, "body_state_evidence", counted_geometry)
    observation = adapt_env_observation_v1(EnvObservation(predicates=[f"posture:{posture}"]))
    result = sensory.poll_observation(observation, cycle_id=1, observation_number=1)
    assert result.payload_dict()["geometry_profile_id"] == profile
    assert "support" not in result.payload_dict()
    assert sensory.current_state is None and sensory.pending_sample_count == 1
    assert calls == []
    application = sensory.apply_result(result.mark_applied(1), cycle_id=1)
    assert len(calls) == 1
    assert application.map_state.posture.value == posture
    assert library.current_state() is application.map_state
    assert sensory.pending_sample_count == 0


@pytest.mark.parametrize("predicates, word", (([], "unknown"), (["posture:fallen", "posture:standing"], "ambiguous")))
def test_open_world_path_is_not_displayed_as_a_canonical_geometry_evaluation(predicates, word) -> None:
    """Missing/conflicting observations take the explicit no-profile path, not a magic recognizer."""
    trace = Nca8TraceBufferV1(256)
    runtime = Nca8CognitiveRuntimeV1(trace=trace, scheduler=Nca8DeterministicSchedulerV1())
    runtime.run_cycle(adapt_env_observation_v1(EnvObservation(predicates=predicates)), observation_number=1)
    sensory = next(event for event in trace.snapshot() if event.channel == "sensory")
    note = _flat(_note(_text(trace.snapshot()), sensory.sequence))
    assert "open_world_evidence" in note
    assert "not evaluate_profile/body_state_evidence" in note
    assert f"posture = {word}" in note
    assert "GEOMETRY:" not in note
    assert "CLASSIFICATION RULES" not in note


@pytest.mark.parametrize("profile", (None, "unrecognized_profile", "upright_support_profile_v1"))
def test_unrecognized_sensory_profile_does_not_get_a_fabricated_geometry_path(gate_events, profile) -> None:
    """A recorded fallen label is not permission to invent the canonical fallen-profile linkage."""
    event = next(event for event in gate_events if event.channel == "sensory")
    details = dict(event.details)
    details["geometry_profile"] = profile
    text = _flat(_text((replace(event, details=tuple(sorted(details.items()))),)))
    assert "mechanism not identified" in text
    assert "No token, geometry calculation or profile contents are inferred" in text
    assert "GEOMETRY:" not in text


def test_rendering_does_not_execute_the_functions_it_describes(gate_events, monkeypatch) -> None:
    """Source-contract prose is not permission to recompute facts or touch cognitive services."""
    def forbidden(*_args, **_kwargs):
        """Fail immediately if presentation tries to execute cognition or geometry."""
        raise AssertionError("a trace renderer must not execute the described mechanism")

    monkeypatch.setattr(Nca8MapLibraryV1, "evaluate_profile", forbidden)
    monkeypatch.setattr(nca8_maps, "body_state_evidence", forbidden)
    monkeypatch.setattr(Nca8BodyRuntimeV1, "update_from_map_state", forbidden)
    monkeypatch.setattr(Nca8PredictionRuntimeV1, "evaluate_ready", forbidden)
    assert "PHASE C1 -" in _text(gate_events)
    assert "PHASE C2 -" in _text(gate_events)


def test_prediction_quote_uses_map_evidence_not_a_different_bodymap_copy(gate_events) -> None:
    """The real prediction evaluator's argument is the current map, unlike envelope reconciliation."""
    events = list(gate_events)
    index = next(index for index, event in enumerate(events) if event.cycle_id == 2 and event.channel == "body")
    details = dict(events[index].details)
    details.update(posture="standing", support="stable")
    events[index] = replace(events[index], details=tuple(sorted(details.items())))
    outcome = next(event for event in events if event.channel == "outcome")
    note = _flat(_note(_text(tuple(events)), outcome.sequence))
    assert "Later POSTURE-SUPPORT interpretation" in note
    assert "evidence cycle 2]: posture = fallen; physical support = inadequate" in note
    assert "not BodyMap as its argument" in note
    assert "evidence cycle 2]: posture = standing" not in note


def test_prediction_does_not_substitute_bodymap_when_map_evidence_is_missing(gate_events) -> None:
    """A retained BodyMap update cannot silently replace missing evidence from the actual argument."""
    events = tuple(event for event in gate_events if not (event.cycle_id == 2 and event.channel == "maps"))
    outcome = next(event for event in events if event.channel == "outcome")
    note = _flat(_note(_text(events), outcome.sequence))
    assert "Matching POSTURE-SUPPORT contents are not available" in note
    assert "Later POSTURE-SUPPORT interpretation [record" not in note


def test_envelope_prose_does_not_claim_every_returned_status_is_a_new_transition(gate_events) -> None:
    """The reconciliation function also returns already-closed or currently unresolvable envelopes."""
    event = next(event for event in gate_events if event.channel == "bodymap" and event.phase == "UPDATE_OUTCOMES")
    note = _flat(_note(_text(gate_events), event.sequence))
    assert "returns the existing status unchanged" in note
    assert "does not by itself prove a new transition" in note


def test_optional_measurement_companion_remains_in_c1_and_behavior_disabled() -> None:
    """Splitting Phase C must not promote the read-only support-observation experiment."""
    session = Nca8SessionV1(Nca8SessionConfigV1(support_observation_enabled=True))
    session.run_cognitive_cycle()
    first = _cycle(_text(session.trace_snapshot()), 1)
    chart = first.split("EXPLANATIONS -", 1)[0]
    assert chart.index("PHASE C1 -") < chart.index("Inspect optional support") < chart.index("PHASE C2 -")
    assert "behavioral_authority=False" in first
    assert "Behavioral authority is explicitly false" in _flat(first)
