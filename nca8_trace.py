#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent bounded trace support for the new CCA8 runtime.

Purpose
-------
The ``nca8_*`` modules implement the experimental Architecture-v09.3 runtime
beside the established ``cca8_*`` runtime. This module provides deterministic,
bounded, immutable trace events that can be rendered for a human or exported in
canonical JSON form.

Authority boundary
------------------
Trace records are observations about execution. They are never read back as
cognitive evidence, never select an action, and never mutate the environment.
Logical sequence numbers, optional cognitive-cycle numbers, and optional phase
labels replace wall-clock timestamps so identical runs can be compared byte for
byte.

The compact renderer remains the stable developer-facing representation used by
existing tests and canonical trace inspection. The explanatory renderer is a
read-only presentation layer for line-by-line human review. It derives clearer
sentences only from fields already present in each immutable event and never
writes information back into cognition.
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

# pylint: disable=unnecessary-comprehension

__version__ = "0.3.0"
__all__ = [
    "Nca8TraceBufferV1",
    "Nca8TraceEventV1",
    "TraceScalarV1",
    "render_explanatory_trace_lines_v1",
    "__version__",
]

TraceScalarV1: TypeAlias = str | int | float | bool | None
ExplanationBuilderV1: TypeAlias = Callable[["Nca8TraceEventV1"], str | None]

_MAX_CHANNEL_LENGTH = 40
_MAX_MESSAGE_LENGTH = 240
_MAX_PHASE_LENGTH = 40
_MAX_DETAIL_COUNT = 16
_MAX_DETAIL_KEY_LENGTH = 60
_MAX_DETAIL_STRING_LENGTH = 200


def _bounded_text(value: str, *, maximum: int, field_name: str) -> str:
    """Return one non-empty bounded string or raise ``ValueError``."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character trace limit")
    return normalized


def _normalize_trace_scalar(value: TraceScalarV1) -> TraceScalarV1:
    """Return a JSON-safe scalar suitable for deterministic trace details."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("trace detail floats must be finite")
        return value
    if isinstance(value, str):
        if len(value) > _MAX_DETAIL_STRING_LENGTH:
            raise ValueError(
                f"trace detail string exceeds the {_MAX_DETAIL_STRING_LENGTH}-character limit"
            )
        return value
    raise TypeError(f"trace details accept JSON-safe scalar values, not {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Nca8TraceEventV1:
    """One immutable engineering trace event from the new runtime.

    ``cycle_id`` and ``phase`` are optional because lifecycle and firewall
    events also occur outside a cognitive cycle. When present, they make the
    causal location explicit in JSON without relying on prose parsing.

    ``render()`` preserves the compact deterministic representation.
    ``render_explanatory()`` adds human-facing causal wording without changing
    the event, its compact rendering, or its canonical JSON representation.
    """

    sequence: int
    channel: str
    message: str
    cycle_id: int | None = None
    phase: str | None = None
    details: tuple[tuple[str, TraceScalarV1], ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe dictionary without exposing mutable trace state."""
        return {
            "sequence": self.sequence,
            "channel": self.channel,
            "message": self.message,
            "cycle_id": self.cycle_id,
            "phase": self.phase,
            "details": {key: value for key, value in self.details},
        }

    def render(self) -> str:
        """Return one compact deterministic terminal line."""
        prefix = f"[nca8:{self.channel}]"
        if not self.details:
            return f"{prefix} {self.message}"
        detail_text = " ".join(f"{key}={value!r}" for key, value in self.details)
        return f"{prefix} {self.message} | {detail_text}"

    def render_explanatory(self) -> str:
        """Return one deterministic, more explanatory terminal line.

        The method is a presentation-only transformation. It reads this
        immutable event, selects clearer wording for recognized Gate-A events,
        and falls back to the original message for every unknown or future
        event. It does not mutate the event or add fields to canonical JSON.
        """
        prefix = f"[nca8:{self.channel}]"
        message = _explanatory_message_v1(self)
        visible_details = _explanatory_details_v1(self)
        if not visible_details:
            return f"{prefix} {message}"
        detail_text = " ".join(f"{key}={value!r}" for key, value in visible_details)
        return f"{prefix} {message} | {detail_text}"


def _details_v1(event: Nca8TraceEventV1) -> dict[str, TraceScalarV1]:
    """Return a newly allocated detail mapping for presentation helpers."""
    return dict(event.details)


def _detail_int_v1(details: Mapping[str, TraceScalarV1], key: str) -> int | None:
    """Return one non-Boolean integer detail when present."""
    value = details.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _detail_str_v1(details: Mapping[str, TraceScalarV1], key: str) -> str | None:
    """Return one string detail when present."""
    value = details.get(key)
    return value if isinstance(value, str) else None


def _explain_session_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain session lifecycle events without changing generation semantics."""
    if event.message != "isolated Phase-1D Gate-A session reset":
        return None
    details = _details_v1(event)
    generation = _detail_int_v1(details, "generation")
    generation_text = f" generation {generation}" if generation is not None else ""
    return (
        f"Fresh isolated Gate-A session{generation_text} initialized. All mutable NCA8 state was replaced, "
        "the innate POSTURE-SUPPORT NM was instantiated, and Observation_1 is pending."
    )


def _explain_firewall_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain observation admission and next-cycle buffering boundaries."""
    if event.message == "Observation_1 buffered as the first cognitive-cycle input":
        return (
            "Observation_1 passed the NCA8 observation whitelist and was buffered as the external input for "
            "CognitiveCycle_1. No sensory interpretation or current-state update has occurred yet."
        )
    if "buffered for CognitiveCycle_" not in event.message:
        return None
    details = _details_v1(event)
    observation_number = _detail_int_v1(details, "observation_number")
    next_cycle_id = _detail_int_v1(details, "next_cycle_id")
    if observation_number is None or next_cycle_id is None:
        return None
    prior_action = f"Action_{event.cycle_id}" if event.cycle_id is not None else "the preceding action"
    return (
        f"Observation_{observation_number} passed the NCA8 observation whitelist and was buffered for "
        f"CognitiveCycle_{next_cycle_id}. It cannot influence {prior_action}, which was already committed."
    )


def _explain_cycle_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain cognitive-cycle opening and closing boundaries."""
    if " opened with Observation_" in event.message:
        return (
            f"{event.message} as its pending external input. Phases A-C must stage, freeze, and apply eligible "
            "results before current NCA8 state can change."
        )
    if not event.message.startswith("CognitiveCycle_") or not event.message.endswith(" closed"):
        return None
    details = _details_v1(event)
    output = _detail_str_v1(details, "output")
    next_input = _detail_str_v1(details, "next_input")
    if output is None or next_input is None:
        return f"{event.message}."
    return f"{event.message} after committing {output}. {next_input} remains buffered for the next cognitive cycle."


def _explain_scheduler_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain the scheduler's staged, frozen, applied, and carried-forward sets."""
    details = _details_v1(event)
    if event.message == "Phase_A POLL_STAGE completed":
        source_count = _detail_int_v1(details, "poll_source_count")
        result_count = _detail_int_v1(details, "staged_result_count")
        if source_count is None or result_count is None:
            return None
        return (
            f"Phase A polled {source_count} due circuit sources and staged {result_count} completed CircuitResults. "
            "Staged results have arrived, but they are not yet allowed to update current state."
        )
    if event.message == "Phase_B FREEZE_ELIGIBLE froze the eligible set":
        eligible_count = _detail_int_v1(details, "eligible_result_count")
        count_text = str(eligible_count) if eligible_count is not None else "the eligible"
        cycle_text = f"CognitiveCycle_{event.cycle_id}" if event.cycle_id is not None else "this cognitive cycle"
        return (
            f"Phase B fixed the {count_text} results allowed to affect {cycle_text}. Results arriving after this "
            "boundary must wait for a later cycle."
        )
    if event.message == "Phase_C UPDATE_OUTCOMES applied frozen results":
        applied_count = _detail_int_v1(details, "applied_result_count")
        result_ids = _detail_str_v1(details, "result_ids") or ""
        count_text = str(applied_count) if applied_count is not None else "frozen"
        if "observation_ingress:" in result_ids and "body_sensory:" in result_ids:
            return (
                f"Phase C applied {count_text} frozen CircuitResults to their owning consumers. This count includes "
                "one observation-ingress bookkeeping result and one body-sensory interpretation result; it does not "
                "mean that two NavMaps were updated."
            )
        return (
            f"Phase C applied {count_text} frozen CircuitResults to their owning consumers. Applied-result counts may "
            "include scheduler infrastructure as well as cognitive or sensory-processing results."
        )
    if event.message == "Phase_F LEARNING_SCHEDULE completed":
        return (
            "Phase F completed bounded learning and scheduler bookkeeping. The pending, latched, and retired counts "
            "show what, if anything, remains available after this cognitive cycle."
        )
    return None


def _explain_runtime_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain runtime-owned Phase-C input admission and Phase-D/E commitments."""
    if event.message.startswith("Observation_") and event.message.endswith("became the applied Phase-C cycle input"):
        details = _details_v1(event)
        observation_number = _detail_int_v1(details, "observation_number")
        observation_text = f"Observation_{observation_number}" if observation_number is not None else "The observation"
        return (
            f"The observation-ingress CircuitResult formally admitted {observation_text} as this cycle's external input. "
            "It did not itself interpret sensory content or update a NavMap."
        )
    if event.message == "Phase_D FOCAL_COMMITMENT completed":
        return (
            "Phase D completed the causal commitment sequence: Attention selected a current NavMapState source, the one "
            "WNM was constructed or released, and Navigation selected zero or one focal primitive."
        )
    if not event.message.startswith("Phase_E PROJECT_DISPATCH committed Action_"):
        return None
    details = _details_v1(event)
    task_action = _detail_str_v1(details, "task_action")
    if task_action is None:
        selected_primitive = _detail_str_v1(details, "selected_primitive")
        pnm_id = _detail_str_v1(details, "pnm")
        if selected_primitive is not None or pnm_id is not None:
            return (
                f"{event.message} because BodyMap did not authorize the task selected by Navigation. The selected "
                "primitive and PNM remain visible in the trace, but no task action crossed the boundary."
            )
        return (
            f"{event.message} because Phase D selected no primitive. No PNM, task action, or BodyMap action envelope "
            "was created."
        )
    return (
        f"{event.message} after Navigation's primitive application, PNM creation, and BodyMap authorization were in "
        "place. The committed task action can now cross the body/environment boundary."
    )


def _explain_sensory_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain how the temporary posture scaffold selects current map configuration."""
    if event.message != "posture predicate scaffold interpreted as current SELF-ground evidence":
        return None
    details = _details_v1(event)
    observation_number = _detail_int_v1(details, "observation_number")
    posture = _detail_str_v1(details, "posture") or "unknown"
    geometry_profile = _detail_str_v1(details, "geometry_profile") or "unknown"
    observation_text = f"Observation_{observation_number}" if observation_number is not None else "the observation"
    return (
        f"Body-sensory processing read {observation_text}'s temporary 'posture:{posture}' predicate scaffold and "
        f"interpreted it as current SELF-ground evidence matching geometry profile '{geometry_profile}' within the "
        "already-existing innate POSTURE-SUPPORT NM. No new NavMap was created."
    )


def _explain_maps_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain transient NavMapState updates versus durable innate-map content."""
    if event.message != "POSTURE-SUPPORT NavMapState updated without durable map revision":
        return None
    details = _details_v1(event)
    update_kind = _detail_str_v1(details, "update_kind") or "updated"
    durable_map = _detail_str_v1(details, "durable_map")
    durable_text = (
        f"The already-existing innate NM {durable_map} was not revised."
        if durable_map is not None
        else "The already-existing durable innate POSTURE-SUPPORT NM was not revised."
    )
    return (
        f"The body-sensory owner {update_kind} the transient current POSTURE-SUPPORT NavMapState from this evidence. "
        f"{durable_text}"
    )


def _explain_body_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain protected BodyMap state and its Attention-candidate publication."""
    if event.message == "BodyMapState updated from current POSTURE-SUPPORT evidence":
        return (
            "BodyMap copied the current POSTURE-SUPPORT state into its protected current-body register. BodyMap may "
            "gate and authorize body actions, but it is not the WNM."
        )
    if event.message == "POSTURE-SUPPORT map-state candidate published for Attention":
        return (
            "Because current SELF posture is fallen with inadequate support, BodyMap published the current "
            "POSTURE-SUPPORT NavMapState as an Attention candidate. Candidate status grants neither focal nor action "
            "authority."
        )
    if event.message == "no POSTURE-SUPPORT candidate published":
        return (
            "Because current SELF posture is standing with stable support, BodyMap cleared the POSTURE-SUPPORT "
            "Attention candidate. There is no remaining posture-recovery source for Attention to select."
        )
    return None


def _explain_bodymap_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain later envelope reconciliation and the task-to-body authorization seam."""
    details = _details_v1(event)
    if event.message == "prior authorized action envelope reconciled from later body evidence":
        envelope_id = _detail_str_v1(details, "envelope_id") or "the prior envelope"
        status = _detail_str_v1(details, "status") or "updated"
        return (
            f"Later current BodyMap evidence marked previously authorized envelope '{envelope_id}' as {status}. The "
            "earlier STAND_UP command did not establish its own outcome."
        )
    if event.message != "BodyMap mapped the selected task to a body-relative target and envelope":
        return None
    task_action = _detail_str_v1(details, "task_action") or "the selected task"
    authorized = details.get("authorized") is True
    decision = "authorized" if authorized else "rejected"
    return (
        f"BodyMap translated task action {task_action} into a body-relative target and {decision} its action envelope "
        "after checking protected current-body state. This is the BodyMap/action-envelope boundary between the "
        "task-level command and environment dispatch."
    )


def _explain_outcome_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain why later evidence, rather than the command, owns outcome truth."""
    if event.message != "later body evidence evaluated an operation-linked pending prediction":
        return None
    details = _details_v1(event)
    application_id = _detail_str_v1(details, "application_id") or "the originating primitive application"
    status = _detail_str_v1(details, "status") or "evaluated"
    return (
        f"PredictionRuntime compared later current body evidence with the pending PNM linked to '{application_id}' and "
        f"marked that prediction {status}. Outcome authority comes from later evidence, not from the earlier command."
    )


def _explain_attention_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain Attention bids and source selection without granting action authority."""
    details = _details_v1(event)
    source_state_id = _detail_str_v1(details, "source_state_id")

    if event.message == "POSTURE-SUPPORT map-state candidate submitted as an Attention bid":
        candidate_source_text = source_state_id or "the current POSTURE-SUPPORT state"
        return (
            f"Attention received a bid for current NavMapState '{candidate_source_text}'. The safety and task-need ranks score "
            "the map-state candidate only; Attention is not choosing a primitive."
        )

    source_text = (
        f"current NavMapState '{source_state_id}'"
        if source_state_id is not None
        else "the selected current NavMapState"
    )

    if event.message == "Attention switched the primary source map state":
        return (
            f"Attention switched its primary source selection to {source_text}. Attention selected a source map state; "
            "it did not choose StandUp or any other primitive."
        )

    if event.message == "Attention maintained the primary source map state":
        return (
            f"Attention maintained {source_text} as the primary source for focal processing. Attention itself still "
            "selected no primitive."
        )

    if event.message == "Attention released the primary source map state":
        return (
            "Attention released the primary source because no current posture-recovery candidate remained. It selected "
            "no replacement source and no primitive."
        )

    return None


def _explain_wnm_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain construction or absence of the one source-linked WNM."""
    if event.message == "source-linked WNM constructed or refreshed from Attention's selected state":
        return (
            "Navigation constructed or refreshed the one source-linked WNM from Attention's selected current "
            "NavMapState. The WNM is a working representation and does not overwrite sensory truth or the innate NM."
        )
    if event.message == "no WNM exists because Attention released or selected no source":
        return "No WNM was created because Attention selected no current NavMapState source."
    return None


def _explain_navigation_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain primitive applicability and Navigation's exclusive action choice."""
    details = _details_v1(event)
    if event.message == "primitive applicability evaluated from the WNM":
        primitive_id = _detail_str_v1(details, "primitive_id") or "the primitive"
        return (
            f"Navigation asked primitive '{primitive_id}' whether it applied to the current WNM. Eligibility, fit, "
            "safety, and veto fields expose the primitive's answer before Navigation arbitrates."
        )
    if event.message != "Navigation commitment completed":
        return None
    selected_primitive_id = _detail_str_v1(details, "selected_primitive_id")
    application_id = _detail_str_v1(details, "application_id")
    if selected_primitive_id is None:
        reason = _detail_str_v1(details, "reason")
        if reason == "no_wnm":
            return "Navigation selected no primitive because no WNM exists."
        return "Navigation evaluated the available primitive information and selected no focal primitive."
    application_text = f", producing application '{application_id}'" if application_id is not None else ""
    return (
        f"Navigation selected and applied primitive '{selected_primitive_id}' as this cycle's one focal primitive"
        f"{application_text}. Attention did not make this action choice."
    )


def _explain_pnm_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain PNM creation, timing, and non-current epistemic status."""
    if event.message != "current PNM created before task-action dispatch":
        return None
    details = _details_v1(event)
    pnm_id = _detail_str_v1(details, "pnm_id") or "the current PNM"
    expected = _detail_str_v1(details, "expected_relations") or "its expected relations"
    condition = _detail_str_v1(details, "observation_condition") or "later evidence"
    return (
        f"PredictionRuntime created PNM '{pnm_id}' before task-action dispatch. It projects '{expected}' and must be "
        f"tested by '{condition}'; a PNM is projected information, not accepted-current truth."
    )


def _explain_dispatch_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain the physical boundary and distinguish NO_ACTION from rejection."""
    if not event.message.startswith("Action_") or "physical environment boundary" not in event.message:
        return None
    details = _details_v1(event)
    environment_action = _detail_str_v1(details, "environment_action")
    if ":NO_ACTION" in event.message:
        action_label = event.message.split(" crossed", maxsplit=1)[0]
        body_authorized = details.get("body_authorized") is True
        pnm_id = _detail_str_v1(details, "pnm_id")
        if pnm_id is not None and not body_authorized:
            return (
                f"{action_label} completed the environment boundary without emitting a task action because BodyMap "
                "rejected the selected task's action envelope. This was a blocked handoff, not the absence of a "
                "proposed task."
            )
        return (
            f"{action_label} completed the environment boundary with no task action emitted. No BodyMap authorization "
            "was required because there was no task to authorize."
        )
    body_authorized = details.get("body_authorized") is True
    if not body_authorized:
        return (
            f"{event.message}, but no authorized body task was available for the adapter to emit. Later evidence will "
            "still belong to the next cognitive cycle."
        )
    environment_text = f" as environment token '{environment_action}'" if environment_action is not None else ""
    action_label = event.message.split(" crossed", maxsplit=1)[0]
    return (
        f"{action_label} crossed the physical environment boundary only after BodyMap authorized its action envelope. "
        f"The adapter emitted it{environment_text}; any resulting observation belongs to the next cognitive cycle."
    )


def _explain_learning_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain the deliberately inactive durable-learning slot in Gate A."""
    if event.message != "Phase-F durable learning made no changes for initial Gate A":
        return None
    return (
        "Phase F made no durable learning changes in initial Gate A. The innate NM, IP definition, and durable memory "
        "remained unchanged."
    )


_EXPLANATION_BUILDERS: Mapping[str, ExplanationBuilderV1] = {
    "attention": _explain_attention_v1,
    "body": _explain_body_v1,
    "bodymap": _explain_bodymap_v1,
    "cycle": _explain_cycle_v1,
    "dispatch": _explain_dispatch_v1,
    "firewall": _explain_firewall_v1,
    "learning": _explain_learning_v1,
    "maps": _explain_maps_v1,
    "navigation": _explain_navigation_v1,
    "outcome": _explain_outcome_v1,
    "pnm": _explain_pnm_v1,
    "runtime": _explain_runtime_v1,
    "scheduler": _explain_scheduler_v1,
    "sensory": _explain_sensory_v1,
    "session": _explain_session_v1,
    "wnm": _explain_wnm_v1,
}


def _explanatory_message_v1(event: Nca8TraceEventV1) -> str:
    """Return clearer wording for one recognized event, otherwise its original message."""
    builder = _EXPLANATION_BUILDERS.get(event.channel)
    if builder is None:
        return event.message
    explanation = builder(event)
    return explanation if explanation is not None else event.message


def _explanatory_details_v1(event: Nca8TraceEventV1) -> tuple[tuple[str, TraceScalarV1], ...]:
    """Return visible details for explanatory output without changing stored details.

    ``body_authorized=False`` is suppressed only for a true no-task NO_ACTION
    dispatch. When a primitive and PNM existed but BodyMap rejected the action
    envelope, the field remains visible because the false value is explanatory.
    The compact renderer and JSON export always retain the original field.
    """
    if event.channel == "dispatch" and ":NO_ACTION" in event.message:
        details = _details_v1(event)
        if _detail_str_v1(details, "pnm_id") is None:
            return tuple((key, value) for key, value in event.details if key != "body_authorized")
    return event.details


def render_explanatory_trace_lines_v1(events: Sequence[Nca8TraceEventV1]) -> tuple[str, ...]:
    """Return deterministic explanatory lines for immutable trace events.

    The function is intentionally separate from ``Nca8TraceBufferV1`` and the
    cognitive runtime so terminal teaching language cannot become cognitive
    state or authority. Unknown future events retain their compact message text.
    """
    lines: list[str] = []
    for event in events:
        if not isinstance(event, Nca8TraceEventV1):
            raise TypeError("explanatory trace rendering requires Nca8TraceEventV1 values")
        lines.append(event.render_explanatory())
    return tuple(lines)


class Nca8TraceBufferV1:
    """Own a bounded sequence of immutable new-runtime trace events.

    The service is mutable only in the engineering sense that it appends and
    evicts trace events. It has no cognitive authority. ``capacity`` bounds
    retained history, while ``total_appended`` records how many events were
    emitted since the last clear even when old events have been evicted.
    """

    def __init__(self, capacity: int = 64) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("trace capacity must be a positive integer")
        self._capacity = capacity
        self._events: deque[Nca8TraceEventV1] = deque(maxlen=capacity)
        self._next_sequence = 1
        self._total_appended = 0

    @property
    def capacity(self) -> int:
        """Return the maximum number of retained events."""
        return self._capacity

    @property
    def retained_count(self) -> int:
        """Return the number of events currently retained."""
        return len(self._events)

    @property
    def total_appended(self) -> int:
        """Return the number of events appended since the last clear."""
        return self._total_appended

    def clear(self) -> None:
        """Remove all events and restart logical sequence numbering at one."""
        self._events.clear()
        self._next_sequence = 1
        self._total_appended = 0

    def append(
        self,
        channel: str,
        message: str,
        *,
        cycle_id: int | None = None,
        phase: str | None = None,
        details: Mapping[str, TraceScalarV1] | None = None,
    ) -> Nca8TraceEventV1:
        """Create, retain, and return one validated immutable trace event.

        Detail keys are sorted so caller dictionary insertion order cannot alter
        rendered output or JSON export. Rich observations and mutable runtime
        objects are intentionally excluded.
        """
        normalized_channel = _bounded_text(
            channel,
            maximum=_MAX_CHANNEL_LENGTH,
            field_name="trace channel",
        )
        normalized_message = _bounded_text(
            message,
            maximum=_MAX_MESSAGE_LENGTH,
            field_name="trace message",
        )

        if cycle_id is not None:
            if isinstance(cycle_id, bool) or not isinstance(cycle_id, int) or cycle_id <= 0:
                raise ValueError("trace cycle_id must be a positive integer or None")
        normalized_phase = None
        if phase is not None:
            normalized_phase = _bounded_text(
                phase,
                maximum=_MAX_PHASE_LENGTH,
                field_name="trace phase",
            )

        raw_details = details or {}
        if len(raw_details) > _MAX_DETAIL_COUNT:
            raise ValueError(f"one trace event may contain at most {_MAX_DETAIL_COUNT} details")

        normalized_details: list[tuple[str, TraceScalarV1]] = []
        for key in sorted(raw_details):
            normalized_key = _bounded_text(
                str(key),
                maximum=_MAX_DETAIL_KEY_LENGTH,
                field_name="trace detail key",
            )
            normalized_details.append((normalized_key, _normalize_trace_scalar(raw_details[key])))

        event = Nca8TraceEventV1(
            sequence=self._next_sequence,
            channel=normalized_channel,
            message=normalized_message,
            cycle_id=cycle_id,
            phase=normalized_phase,
            details=tuple(normalized_details),
        )
        self._next_sequence += 1
        self._total_appended += 1
        self._events.append(event)
        return event

    def snapshot(self) -> tuple[Nca8TraceEventV1, ...]:
        """Return an immutable snapshot of retained events in causal order."""
        return tuple(self._events)

    def render_lines(self) -> tuple[str, ...]:
        """Return all retained events as immutable compact terminal lines."""
        return tuple(event.render() for event in self._events)

    def as_json_safe(self) -> list[dict[str, object]]:
        """Return retained events as newly allocated JSON-safe dictionaries."""
        return [event.as_dict() for event in self._events]

    def as_canonical_json_bytes(self) -> bytes:
        """Return byte-stable canonical JSON for deterministic replay checks."""
        text = json.dumps(
            self.as_json_safe(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return text.encode("utf-8")
