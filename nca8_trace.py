#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent bounded trace support for the new CCA8 runtime.

Purpose
-------
The ``nca8_*`` modules implement the retained A0 runtime on the migration path
toward Architecture v09.9, governed by Planning v16. They run
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
writes information back into cognition. The guided flow renderer groups retained
events into parts-first ASCII boxes: components, representations and software
services stay distinct. Input/operation/output ports expose the implemented
routes, with visible gaps and exact technical details below each diagram.
C1 (current-input updates) and C2 (earlier-operation outcomes) are display
subsections of the existing UPDATE_OUTCOMES phase, not new scheduler phases.
Source-code mechanism descriptions are labeled separately from event data;
the renderer never executes the described geometry or outcome computations.

P16-1R-A adds a separate DOMAIN label to each recognized flow step. A software
service may implement cognitive work, runtime bookkeeping, or a boundary call;
its category alone does not identify its architectural domain. Historical event
order and canonical bytes are unchanged. The target-order note is unnumbered
and explicitly planned: no handoff/world/input refactor is performed here.
"""

from __future__ import annotations

import json
import math
import textwrap
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import groupby
from typing import TypeAlias

# pylint: disable=unnecessary-comprehension

__version__ = "0.8.0"
__all__ = [
    "Nca8TraceBufferV1",
    "Nca8TraceEventV1",
    "TraceScalarV1",
    "render_explanatory_trace_lines_v1",
    "render_flow_trace_lines_v1",
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
            "The already-adapted Observation_1 was buffered as the external input for CognitiveCycle_1. "
            "In the A0 source path, the reset bridge applied the observation whitelist before this record. "
            "Buffering does not repeat filtering or interpret sensory content."
        )
    if "buffered for CognitiveCycle_" not in event.message:
        return None
    details = _details_v1(event)
    observation_number = _detail_int_v1(details, "observation_number")
    next_cycle_id = _detail_int_v1(details, "next_cycle_id")
    if observation_number is None or next_cycle_id is None:
        return None
    prior_action = f"Action_{event.cycle_id}" if event.cycle_id is not None else "the preceding action"
    if details.get("boundary_protocol") == "p16_1r_b_v1":
        return (
            f"The already-adapted Observation_{observation_number} was buffered for CognitiveCycle_{next_cycle_id}. "
            "The separately recorded input-admission operation applied the whitelist after internal closure and the "
            f"external world step. Buffering does not filter again and cannot influence {prior_action}."
        )
    return (
        f"The already-adapted Observation_{observation_number} was buffered for CognitiveCycle_{next_cycle_id}. "
        "In the A0 source path, the synchronous bridge applied the whitelist before the dispatch record; "
        "this record reports pending-input assignment, not another filtering pass. "
        f"It cannot influence {prior_action}, which was already committed."
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
    if details.get("boundary_protocol") == "p16_1r_b_v1":
        return (
            f"{event.message} after committing {output or 'the recorded output'} and completing F/housekeeping. "
            "The internal request is ready for outer consumption; the world has not yet advanced for this action "
            "and no next observation has been admitted. Closure is not physical success."
        )
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
            "Phase F completed scheduler housekeeping. The pending, latched, and retired counts describe "
            "scheduler results and events, not learned changes. The separate learning record reports the A0 slot."
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
    separated = dict(event.details).get("boundary_protocol") == "p16_1r_b_v1"
    if not event.message.startswith("Action_") or not (
        "physical environment boundary" in event.message
        or (separated and event.message.endswith("completed the external world step"))
    ):
        return None
    details = _details_v1(event)
    environment_action = _detail_str_v1(details, "environment_action")
    boundary_note = (
        " Source contract: the current synchronous bridge advances the external world and adapts its returned "
        "observation before this dispatch record is emitted. The later buffering record does not filter again. "
        "No separate internal handoff receipt or world-step timestamp is recorded here."
    )
    if separated:
        boundary_note = (
            " The outer runner consumed the internal receipt once after F and internal closure. "
            "The world call has returned, but its observation has not yet been admitted. "
            "Input admission and buffering are separate later operations. This receipt is not proof of task success."
        )
    if ":NO_ACTION" in event.message:
        action_label = event.message.split(" crossed", maxsplit=1)[0].split(" completed", maxsplit=1)[0]
        body_authorized = details.get("body_authorized") is True
        pnm_id = _detail_str_v1(details, "pnm_id")
        if pnm_id is not None and not body_authorized:
            return (
                f"{action_label} completed the environment boundary without emitting a task action because BodyMap "
                "rejected the selected task's action envelope. This was a blocked handoff, not the absence of a "
                "proposed task."
            ) + boundary_note
        return (
            f"{action_label} completed the environment boundary with no task action emitted. No BodyMap authorization "
            "was required because there was no task to authorize."
        ) + boundary_note
    body_authorized = details.get("body_authorized") is True
    if not body_authorized:
        return (
            f"{event.message}, but no authorized body task was available for the adapter to emit. Later evidence will "
            "still belong to the next cognitive cycle."
        ) + boundary_note
    environment_text = f" as environment token '{environment_action}'" if environment_action is not None else ""
    action_label = event.message.split(" crossed", maxsplit=1)[0].split(" completed", maxsplit=1)[0]
    return (
        f"{action_label} crossed the physical environment boundary only after BodyMap authorized its action envelope. "
        f"The adapter emitted it{environment_text}; any resulting observation belongs to the next cognitive cycle."
    ) + boundary_note


def _explain_boundary_v1(event: Nca8TraceEventV1) -> str | None:
    """Explain the new protocol's actual handoff, admission and stop records."""
    details = _details_v1(event)
    if details.get("boundary_protocol") != "p16_1r_b_v1":
        return None
    if event.channel == "handoff" and event.message == "committed output accepted by internal lower-action boundary":
        return (
            "The lower-action boundary accepted the immutable committed output, without executing it. "
            "F, scheduler housekeeping and internal closure must finish before the outer runner consumes it once."
        )
    if event.channel == "input" and event.message.endswith("admitted and detached at the input boundary"):
        return (
            f"{event.message}. The existing positive whitelist made an NCA8-owned packet after external execution. "
            "This is input admission, not sensory interpretation or another world step. Buffering follows separately."
        )
    if (event.channel, event.message) in {
        ("boundary_failure", "runner stopped after boundary failure"),
        ("protection", "protected stop revoked further execution permission"),
    }:
        return (
            f"{event.message}. Execution status: {details.get('execution_status', 'not recorded')}; "
            f"stage: {details.get('stage', 'not recorded')}. No stale input or automatic retry is supplied. "
            "The original commitment remains historical; revoked permission does not roll back physical effects. "
            "Explicit reset is required."
        )
    return None


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
    "handoff": _explain_boundary_v1,
    "input": _explain_boundary_v1,
    "boundary_failure": _explain_boundary_v1,
    "protection": _explain_boundary_v1,
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


# ---- Guided flow trace: presentation only -----------------------------------

@dataclass(frozen=True, slots=True)
class FlowStepV1:
    """Describe one retained event without promoting its software into a brain part.

    The input and output strings identify the implemented information routes.
    The title states the operation; explanations give the mechanism and storage
    contract. Values must come from this event or earlier retained references.
    These descriptions neither execute the operation nor synthesize new events.
    """

    title: str
    explanations: tuple[str, ...]
    incoming: str
    outgoing: str

_FLOW_PHASE_TITLES_V1 = {
    "POLL_STAGE": "PHASE A - COLLECT COMPLETED PROCESSING RESULTS",
    "FREEZE_ELIGIBLE": "PHASE B - FIX WHICH RESULTS MAY COUNT THIS CYCLE",
    "UPDATE_OUTCOMES": "PHASE C - INPUT UPDATES AND EARLIER OUTCOMES",
    "FOCAL_COMMITMENT": "PHASE D - CHOOSE THE FOCAL SOURCE AND OPERATION",
    "PROJECT_DISPATCH": "PHASE E - PREDICT, CHECK THE BODY, COMMIT AND DISPATCH",
    "LEARNING_SCHEDULE": "PHASE F - FINISH THE A0 LEARNING SLOT AND SCHEDULER BOOKKEEPING",
}
_FLOW_SUPPORT_MESSAGE_V1 = (
    "The body-sensory owner inspected the support packet in Phase C. "
    "This configuration is read-only; A0 authority is unchanged."
)
_FLOW_C1_V1 = "C1_INPUT_UPDATE"
_FLOW_C2_V1 = "C2_EARLIER_OUTCOMES"
_FLOW_C_TITLES_V1 = {
    _FLOW_C1_V1: "PHASE C1 - APPLY CURRENT INPUT AND UPDATE CURRENT REPRESENTATIONS",
    _FLOW_C2_V1: "PHASE C2 - RESOLVE EARLIER OPERATION OUTCOMES USING UPDATED EVIDENCE",
}
_FLOW_MODULES_V1 = {
    "session": "nca8_runtime.py",
    "firewall": "nca8_adapters.py / nca8_runtime.py",
    "cycle": "nca8_runtime.py",
    "scheduler": "nca8_scheduler.py",
    "runtime": "nca8_runtime.py",
    "sensory": "nca8_sensory.py",
    "maps": "nca8_maps.py",
    "body": "nca8_body.py",
    "bodymap": "nca8_body.py",
    "attention": "nca8_executive.py",
    "wnm": "nca8_executive.py",
    "navigation": "nca8_executive.py",
    "pnm": "nca8_prediction.py",
    "outcome": "nca8_prediction.py",
    "dispatch": "nca8_runtime.py / nca8_adapters.py",
    "handoff": "nca8_handoff.py / nca8_runtime.py",
    "input": "nca8_adapters.py / nca8_runtime.py",
    "boundary_failure": "nca8_runtime.py / nca8_handoff.py",
    "protection": "nca8_runtime.py / nca8_body.py",
    "learning": "nca8_runtime.py",
    "support_observation": "nca8_sensory.py",
}
_FLOW_REASON_TEXT_V1 = {
    "bodymap_action_handoff_ablation_disabled": "The body-to-environment handoff mechanism is disabled for this experiment.",
    "bodymap_current_state_missing": "BodyMap has no current body representation to check.",
    "bodymap_current_evidence_not_supported": "The available body evidence cannot support a current action permission.",
    "bodymap_gate_a_supports_only_stand_up": "This Gate-A handoff supports StandUp, not the requested task.",
    "bodymap_current_posture_is_not_fallen": "The current body posture does not meet the fallen-posture requirement.",
    "bodymap_current_support_is_not_inadequate": "The current physical support does not meet the inadequate-support requirement.",
    "primitive_application_has_no_envelope_request": "The selected operation supplied no action-permission request.",
    "authorized_current_fallen_body_recovery": "Current fallen-posture and inadequate-support evidence permits this recovery request.",
    "navigation_ablation_disabled": "Navigation is disabled for this experiment.",
    "no_wnm": "There is no Working Navigation Map on which to operate.",
    "no_eligible_primitive": "No available primitive met the requirements for selection.",
    "selected_by_visible_navigation_components": "Navigation selected the operation after evaluating its applicability.",
}


@dataclass(slots=True)
class _FlowContextV1:
    """Hold only earlier retained trace evidence during one rendering call.

    These local references are not runtime state. They let an outcome quote its
    own earlier PNM rather than inventing an expectation, and let Attention's
    configuration reference resolve to the source-map ID actually recorded.
    A session-reset event clears the context. Map evidence is cleared at every
    new cycle and every gap; missing retained evidence stays explicitly missing.
    """

    settings: dict[str, TraceScalarV1] = field(default_factory=dict)
    source_maps: dict[str, str] = field(default_factory=dict)
    predictions: dict[str, Nca8TraceEventV1] = field(default_factory=dict)
    map_evidence: Nca8TraceEventV1 | None = None
    initial_cycle_pending: bool = False

    def remember(self, event: Nca8TraceEventV1) -> None:
        """Remember recognized records only after their own explanation is drawn."""
        details = _details_v1(event)
        if event.channel == "session" and event.message == "isolated Phase-1D Gate-A session reset":
            self.settings = details
            self.source_maps.clear()
            self.predictions.clear()
            self.map_evidence = None
            self.initial_cycle_pending = details.get("pending_observation_number") == 1
        elif event.channel == "maps" and event.message == "POSTURE-SUPPORT NavMapState updated without durable map revision":
            self.map_evidence = event
            state_id = _detail_str_v1(details, "state_id")
            source_map = _detail_str_v1(details, "durable_map")
            if state_id is not None and source_map is not None:
                self.source_maps[state_id] = source_map
        elif event.channel == "pnm" and event.message == "current PNM created before task-action dispatch":
            pnm_id = _detail_str_v1(details, "pnm_id")
            if pnm_id is not None:
                self.predictions[pnm_id] = event


def _flow_value_v1(details: Mapping[str, TraceScalarV1], key: str) -> str:
    """Distinguish a missing field from an explicitly recorded null or false value."""
    if key not in details:
        return "not recorded"
    value = details[key]
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _flow_relations_v1(value: str) -> str:
    """Make a recorded relation list readable without adding or changing relations."""
    return "; ".join(part.replace(":", " = ", 1) for part in value.split(","))


def _flow_reason_v1(details: Mapping[str, TraceScalarV1], key: str = "reason") -> str:
    """Translate only known reasons; preserve unknown reasons instead of guessing."""
    reason = _detail_str_v1(details, key)
    if reason is None:
        return f"Reason: {_flow_value_v1(details, key)}."
    return _FLOW_REASON_TEXT_V1.get(reason, f"Recorded reason: {reason}.")


def _flow_observation_counts_v1(details: Mapping[str, TraceScalarV1]) -> str:
    """Explain packet counts, not unrecorded channel identities or map contents."""
    return (
        f"Already admitted packet: {_flow_value_v1(details, 'raw_sensor_count')} ordinary raw-channel entries; "
        f"{_flow_value_v1(details, 'predicate_count')} predicate tokens; "
        f"{_flow_value_v1(details, 'cue_count')} cue tokens; "
        f"{_flow_value_v1(details, 'nav_patch_count')} local geometry patches (NavPatches, not cognitive NavMaps). "
        "These counts do not identify the contents or say that the contents have been used."
    )


def _flow_input_step_v1(event: Nca8TraceEventV1, _context: _FlowContextV1) -> FlowStepV1 | None:
    """Explain setup, already-filtered input, and cycle boundaries from their records."""
    details = _details_v1(event)
    if event.channel == "session" and event.message == "isolated Phase-1D Gate-A session reset":
        return FlowStepV1(
            title="Create the isolated NCA8 session",
            explanations=(
                f"Session generation {_flow_value_v1(details, 'generation')} initialized. The session's mutable machinery "
                f"was replaced and the innate POSTURE-SUPPORT source {_flow_value_v1(details, 'durable_posture_support_map')} "
                "was instantiated. This is not a learned result of the demonstration.",
                f"Environment run: {_flow_value_v1(details, 'episode_index')}; seed: {_flow_value_v1(details, 'seed')}; "
                f"next observation number: {_flow_value_v1(details, 'pending_observation_number')}. "
                "The stored episode_index is the environment-run counter, not a cognitive-episode counter.",
                f"Attention available: {_flow_value_v1(details, 'attention_enabled')}. "
                f"Navigation available: {_flow_value_v1(details, 'navigation_enabled')}. "
                f"Body-to-environment handoff available: {_flow_value_v1(details, 'body_action_handoff_enabled')}. "
                "These switches permit mechanisms; they do not authorize a particular action.",
            ),
            incoming=f"Session settings: generation {_flow_value_v1(details, 'generation')}; seed {_flow_value_v1(details, 'seed')}",
            outgoing=(
                f"[Innate POSTURE-SUPPORT source {_flow_value_v1(details, 'durable_posture_support_map')}] instantiated; "
                f"Observation_{_flow_value_v1(details, 'pending_observation_number')} awaits the input path"
            ),
        )
    if event.channel == "firewall":
        first = event.message == "Observation_1 buffered as the first cognitive-cycle input"
        number = _detail_int_v1(details, "observation_number")
        next_cycle = _detail_int_v1(details, "next_cycle_id")
        later = number is not None and next_cycle is not None and event.message == (
            f"Observation_{number} buffered for CognitiveCycle_{next_cycle} without same-cycle processing"
        )
        if not first and not later:
            return None
        target = "1" if first else str(next_cycle)
        observation_label = f"Observation_{number}" if number is not None else "the observation"
        return FlowStepV1(
            title=f"Buffer already-adapted {observation_label} for CognitiveCycle_{target}",
            explanations=(
                f"Already-adapted NCA8-owned packet -> pending input for CognitiveCycle_{target}.",
                (
                    "SOURCE CONTRACT: Nca8EnvironmentBridgeV1.reset calls adapt_env_observation_v1 before "
                    "the initial buffering record. This record reports the already-adapted reset packet."
                    if first else
                    "SOURCE CONTRACT: the outer runner called Nca8EnvironmentBridgeV1.admit_observation after "
                    "the separate world-step report. That input operation called adapt_env_observation_v1 once. "
                    "This record stores the already-adapted packet after internal cognitive-cycle closure."
                    if details.get("boundary_protocol") == "p16_1r_b_v1" else
                    "SOURCE CONTRACT: Nca8EnvironmentBridgeV1.apply_task_action advances the environment and calls "
                    "adapt_env_observation_v1 before the dispatch record is emitted. After the core returns, the runner "
                    "assigns that already-adapted packet to its pending-input buffer and emits this record."
                ),
                "This is not another filtering pass. Buffering is input-boundary work, not sensory interpretation, "
                "a current-map update, or an additional world step. The source contract does not reconstruct any "
                "missing earlier event or timestamp.",
                _flow_observation_counts_v1(details),
                f"Environment step: {_flow_value_v1(details, 'environment_step')} (world advances since reset, not a cycle "
                "or environment-run number). " + (
                    "The first observation is supplied by reset, before the first action."
                    if first else "This input cannot change the already committed action of its originating cycle."
                ),
            ),
            incoming=f"[Already-adapted {observation_label}] from the bridge -> pending-input assignment",
            outgoing=f"[NCA8-owned {observation_label}] -> pending-input buffer for CognitiveCycle_{target}",
        )
    if event.channel == "cycle" and event.cycle_id is not None:
        cycle = event.cycle_id
        number = _detail_int_v1(details, "observation_number")
        if number is not None and event.message == f"CognitiveCycle_{cycle} opened with Observation_{number}":
            return FlowStepV1(
                title=f"Open CognitiveCycle_{cycle} with Observation_{number}",
                explanations=(
                    "The cycle opens with the same already-filtered pending input; this is not another whitelist pass. "
                    "A collects results, B fixes their eligibility, C1 applies input and updates representations, "
                    "and C2 checks earlier operation outcomes against the updated evidence. "
                    "Scheduler bookkeeping can change before those cognitive updates.",
                    _flow_observation_counts_v1(details),
                    f"Environment step at input: {_flow_value_v1(details, 'environment_step')}. "
                    "Step 0 is the reset observation; a world step can also occur with NO_ACTION.",
                ),
                incoming=f"Pending-input buffer -> [Observation_{number}]",
                outgoing="The same admitted packet -> scheduler collection; no second filtering pass",
            )
        if event.message == f"CognitiveCycle_{cycle} closed":
            return FlowStepV1(
                title=f"Close CognitiveCycle_{cycle}",
                explanations=(
                    f"Input: {_flow_value_v1(details, 'input')} -> committed output: {_flow_value_v1(details, 'output')} "
                    f"-> next input waiting: {_flow_value_v1(details, 'next_input')}.",
                    "This is runtime accounting, not another cognitive operation or world step. In the current A0 "
                    "source path, this closure record follows F, scheduler housekeeping and next-input buffering. "
                    "The planned target moves internal closure before the outer world/input work; that refactor has not occurred.",
                    "Closing this cycle does not process the next observation. Displaying this chart does not advance the session.",
                ),
                incoming=f"Committed output {_flow_value_v1(details, 'output')}; pending input {_flow_value_v1(details, 'next_input')}",
                outgoing="Cycle closed; pending observation remains for the next cycle, not this decision",
            )
    return None


def _flow_scheduler_step_v1(event: Nca8TraceEventV1, _context: _FlowContextV1) -> FlowStepV1 | None:
    """Name result storage and destination modules, keeping scheduler marks separate from application.

    phase_c_apply_frozen marks records applied and returns them. The runtime then
    routes the returned records to the actual consumers. The summary event is
    therefore not evidence that the scheduler has itself updated two NavMaps.
    """
    details = _details_v1(event)
    if event.message == "Phase_A POLL_STAGE completed":
        result_ids = _detail_str_v1(details, "result_ids")
        results = f"Completed result references: {result_ids}." if result_ids else "Result references: not recorded or empty."
        return FlowStepV1(
            title=f"Collect {_flow_value_v1(details, 'staged_result_count')} completed results; do not apply them",
            explanations=(
                f"Scheduler polled {_flow_value_v1(details, 'poll_source_count')} due processing sources and staged "
                f"{_flow_value_v1(details, 'staged_result_count')} completed results. "
                "Arrival does not yet permit a result to update current cognition.",
                "Due processing sources -> completed results -> waiting for the eligibility cutoff.",
                results,
                "A0 mechanism: observation_ingress contains input-identity bookkeeping. body_sensory identifies a staged "
                "posture sample and selected geometry profile in nca8_sensory.py._pending_samples. The geometry check and "
                "current-map write occur during C1, not during collection. These are not two finished NavMaps.",
            ),
            incoming=f"Due processing services -> {_flow_value_v1(details, 'result_ids')}",
            outgoing=(
                "[Staged result set] -> scheduler eligibility check. A body result identifies a sample/profile, "
                "not a current NavMap"
            ),
        )
    if event.message == "Phase_B FREEZE_ELIGIBLE froze the eligible set":
        return FlowStepV1(
            title=f"Freeze {_flow_value_v1(details, 'eligible_result_count')} results for this cycle",
            explanations=(
                f"Scheduler fixed {_flow_value_v1(details, 'eligible_result_count')} results that may influence this cycle. "
                "Results not yet eligible at this boundary must wait. Existing represented state is not erased by this cutoff.",
                "Staged results -> eligibility and timing checks -> fixed result set for this decision.",
                f"Eligible result references: {_flow_value_v1(details, 'result_ids')}.",
            ),
            incoming=f"Scheduler staged set -> {_flow_value_v1(details, 'result_ids')}",
            outgoing="[Frozen eligible result set] -> C1 application; not-yet-eligible results wait",
        )
    if event.message == "Phase_C UPDATE_OUTCOMES applied frozen results":
        result_ids = _detail_str_v1(details, "result_ids") or ""
        routes: list[str] = []
        for result_id in result_ids.split(","):
            if result_id.startswith("observation_ingress:"):
                routes.append(f"{result_id} -> cycle-driver input-identity service")
            elif result_id.startswith("body_sensory:"):
                routes.append(f"{result_id} -> A0 body-sensory service")
            elif result_id:
                routes.append(f"{result_id} -> destination not identified by this renderer")
        route_text = "; ".join(routes) or "No result references recorded."
        return FlowStepV1(
            title=f"Mark {_flow_value_v1(details, 'applied_result_count')} frozen results applied; return them to the cycle driver",
            explanations=(
                "Mechanism: Nca8DeterministicSchedulerV1.phase_c_apply_frozen stamps each eligible result with its "
                "applied cycle and returns the result tuple. Nca8CognitiveRuntimeV1._apply_phase_c_results then routes it. "
                "The scheduler's applied mark does not itself write sensory representations.",
                f"Routes for the recorded result references: {route_text}.",
                "The subsequent records report the input check and representation updates. A result count is not a "
                "count of updated NavMaps. C1 is the input/update subsection of the existing stored Phase C.",
            ),
            incoming=f"Scheduler frozen set -> {_flow_value_v1(details, 'result_ids')}",
            outgoing=route_text,
        )
    if event.message == "Phase_F LEARNING_SCHEDULE completed":
        return FlowStepV1(
            title="Retain waiting results and retire expired records",
            explanations=(
                f"Results still pending: {_flow_value_v1(details, 'pending_result_count')}; "
                f"latched: {_flow_value_v1(details, 'latched_result_count')}; "
                f"retired: {_flow_value_v1(details, 'retired_result_count')}.",
                "Pending results wait for later eligibility; latched events are held for later consumption; "
                "retired results are no longer available through that scheduler record. These are not episodic-memory counts.",
            ),
            incoming="Scheduler pending results, latched events and expiry times",
            outgoing=(
                f"Scheduler records: pending {_flow_value_v1(details, 'pending_result_count')}; "
                f"latched {_flow_value_v1(details, 'latched_result_count')}; retired {_flow_value_v1(details, 'retired_result_count')}"
            ),
        )
    return None


def _flow_sensory_step_v1(details: Mapping[str, TraceScalarV1], context: _FlowContextV1) -> FlowStepV1:
    """Explain the known A0 sample-to-geometry path without recalculating geometry.

    Profile and posture values come from the event. Function names and decision
    rules describe the source contract, not extra recorded measurements. An
    absent, unknown, or inconsistent profile never selects a fictional path.
    """
    posture = _detail_str_v1(details, "posture")
    profile = _detail_str_v1(details, "geometry_profile")
    number = _flow_value_v1(details, "observation_number")
    result_id = _flow_value_v1(details, "result_id")
    source_id = _flow_value_v1(context.settings, "durable_posture_support_map")
    expected_profiles = {"fallen": "lateral_ground_profile_v1", "standing": "upright_support_profile_v1"}
    if posture is not None and posture in expected_profiles and profile == expected_profiles[posture]:
        return FlowStepV1(
            title=f"Check staged {profile} with the map/geometry services; require agreement with posture:{posture}",
            explanations=(
                "ROLE: A0 substitutes a software service for the unfinished body-related sensory pathway. "
                "The class name below does not establish a canonical Body-Sensory Module. Its geometry/map helpers "
                "are services too, not extra brain parts.",
                f"INPUT: result {result_id} retrieves its pending sample in Nca8BodySensoryModuleV1._pending_samples. "
                f"The sample came from Observation_{number}'s admitted posture:{posture} scaffold. "
                "Profile selection was computed during Phase A; C1 applies that staged sample rather than filtering the input again.",
                f"MECHANISM: apply_result checks the result's circuit, applied cycle and observation number. "
                f"It calls Nca8MapLibraryV1.evaluate_profile({profile!r}) in nca8_maps.py. The profile selects "
                "SELF body-axis, head, foot and ground elements from the existing durable POSTURE-SUPPORT map.",
                "GEOMETRY: evaluate_profile calls cca8_navmap_kernel.py.body_state_evidence. Its support_evidence helper "
                "computes body-ground angle, foot-ground contact, head-ground distance and the fraction of the body axis "
                "near ground, then compares these with the configured thresholds.",
                "CLASSIFICATION RULES (source-code description): parallel body + low head + high lateral contact gives a "
                "lateral-ground pattern; foot contact + upright body + elevated head + low lateral contact gives an upright "
                "pattern. Only the first pattern gives FALLEN_LIKE; only the second gives STANDING_LIKE. "
                "Mixed patterns remain ambiguous. NCA8 translates these into posture/support/contact labels.",
                "OUTPUT: apply_result requires the geometry classification to agree with the staged posture, then calls "
                "update_current_state. The next map record reports that write. These are reports from one application call, "
                "not separate independent sensory computations.",
                "SCAFFOLD LIMIT: the environment already supplied a posture label, which selected a predefined geometry profile. "
                "This is not posture recognition from raw sensors. In A0 the support label is derived from the profile, "
                "not independently measured loading. Numeric geometry values are not recorded in this event and are not reconstructed.",
            ),
            incoming=(
                f"[Result {result_id}] -> staged sample for Observation_{number}; "
                f"profile geometry from [innate POSTURE-SUPPORT source {source_id}]"
            ),
            outgoing=(
                f"[Posture-support evidence: posture={posture}] -> POSTURE-SUPPORT map service for current-configuration storage; "
                "the next map record reports the stored support/contact labels"
            ),
        )
    if posture in ("unknown", "ambiguous") and profile is None:
        condition = "no usable posture token" if posture == "unknown" else "conflicting fallen and standing posture tokens"
        return FlowStepV1(
            title=f"Apply {result_id}: {condition}; preserve {posture} evidence without a geometry profile",
            explanations=(
                f"INPUT: pending body-sensory sample for Observation_{number}; {condition}.",
                "MECHANISM: nca8_sensory.py.apply_result calls Nca8MapLibraryV1.open_world_evidence, "
                "not evaluate_profile/body_state_evidence. It then calls update_current_state with that open-world result.",
                f"OUTPUT: posture = {posture}. No canonical profile is selected and no standing or fallen "
                "geometry is invented. The following map record supplies the actual stored labels.",
                _flow_reason_v1(details),
            ),
            incoming=f"[Staged body-sensory sample] from Observation_{number}",
            outgoing=f"[{posture} posture evidence] -> POSTURE-SUPPORT map service; no canonical geometry evaluation",
        )
    return FlowStepV1(
        title="Recorded posture/profile combination: mechanism not identified",
        explanations=(
            f"Recorded posture: {_flow_value_v1(details, 'posture')}; geometry profile: "
            f"{_flow_value_v1(details, 'geometry_profile')}; source: {_flow_value_v1(details, 'scaffold_source')}.",
            "The recorded combination does not identify a recognized A0 path. No token, geometry calculation or "
            "profile contents are inferred. Consult the original details before extending this explanation.",
            _flow_reason_v1(details),
        ),
        incoming=f"[Body result {result_id}] for Observation_{number}; profile {_flow_value_v1(details, 'geometry_profile')}",
        outgoing="Mechanism/output path not identified by this renderer; inspect the original details",
    )


def _flow_representation_step_v1(event: Nca8TraceEventV1, _context: _FlowContextV1) -> FlowStepV1 | None:
    """Name C1 inputs, operations and storage locations without inventing observation contents."""
    details = _details_v1(event)
    if event.channel == "runtime":
        number = _detail_int_v1(details, "observation_number")
        if number is not None and event.message == f"Observation_{number} became the applied Phase-C cycle input":
            return FlowStepV1(
                title=f"Verify ingress identifies Observation_{number} -> record it as this cycle's applied input",
                explanations=(
                    f"INPUT: {_flow_value_v1(details, 'result_id')} from the frozen result set; "
                    f"current cycle input is Observation_{number}.",
                    "CHECK: Nca8CognitiveRuntimeV1._apply_phase_c_results requires exactly one observation_ingress "
                    "result and checks its payload observation_number against the expected input number. Missing, duplicate "
                    "or mismatched ingress raises an error instead of silently admitting another observation.",
                    f"WRITE: Nca8CognitiveRuntimeV1._last_applied_observation_number = {number}.",
                    "This verifies identity and records application; the whitelist filtering has already happened. "
                    "No sensory content is interpreted and no NavMap or BodyMap is written by this check.",
                ),
                incoming=f"Frozen {_flow_value_v1(details, 'result_id')} + expected Observation_{number}",
                outgoing=f"[Applied observation number = {number}] -> cycle-driver register; no sensory map write",
            )
    if event.channel == "sensory" and event.message == "posture predicate scaffold interpreted as current SELF-ground evidence":
        return _flow_sensory_step_v1(details, _context)
    if event.channel == "maps" and event.message == "POSTURE-SUPPORT NavMapState updated without durable map revision":
        return FlowStepV1(
            title=f"Map service writes current configuration (update: {_flow_value_v1(details, 'update_kind')}); durable source unchanged",
            explanations=(
                "HOST: the POSTURE-SUPPORT map service holds this representation in A0. No fully modeled "
                "sensory/association circuit is being claimed as its physical host. This is a representation write, "
                "not an autonomous NavMap processor calling another part.",
                "INPUT: PostureSupportEvidenceV1 returned by the map service during nca8_sensory.py.apply_result.",
                "MECHANISM: Nca8MapLibraryV1.update_current_state checks the source-map reference and active element IDs, "
                "constructs a NavMapStateV1 with posture/support/contact and timing, and replaces or refreshes the current entry.",
                f"WRITE: Nca8MapLibraryV1._current_states['posture_support'] holds state_id "
                f"{_flow_value_v1(details, 'state_id')}. Recorded update: {_flow_value_v1(details, 'update_kind')}.",
                f"Current interpretation: posture = {_flow_value_v1(details, 'posture')}; "
                f"physical support = {_flow_value_v1(details, 'support')}; contact = {_flow_value_v1(details, 'contact')}.",
                f"The durable source {_flow_value_v1(details, 'durable_map')} is stored separately and is not revised. "
                "NavMapState is the compatibility name for this transient current configuration, not a newly learned map.",
                "NEXT: the runtime passes this current configuration to nca8_body.py.update_from_map_state. "
                "Storing a map configuration does not itself select Attention, create a WNM or authorize movement.",
            ),
            incoming="[Posture-support evidence] from A0 sensory/geometry services",
            outgoing=(
                f"[POSTURE-SUPPORT {_flow_value_v1(details, 'state_id')}] held by map service: "
                f"posture={_flow_value_v1(details, 'posture')}; support={_flow_value_v1(details, 'support')}; "
                f"contact={_flow_value_v1(details, 'contact')}. Source {_flow_value_v1(details, 'durable_map')}; copied next to BodyMap"
            ),
        )
    if event.channel == "body" and event.message == "BodyMapState updated from current POSTURE-SUPPORT evidence":
        return FlowStepV1(
            title="Copy current posture, support, contact and evidence timing into the body register",
            explanations=(
                "INPUT: the current NavMapStateV1 returned by the body-sensory application. "
                "Current POSTURE-SUPPORT configuration -> BodyMap's current body register.",
                "MECHANISM: Nca8BodyRuntimeV1.update_from_map_state copies posture, support, contact, source references "
                "and timing into BodyMapStateV1; it is not another sensory recognition step.",
                f"WRITE: Nca8BodyRuntimeV1._current_state holds {_flow_value_v1(details, 'state_id')}. "
                f"Recorded posture = {_flow_value_v1(details, 'posture')}; physical support = "
                f"{_flow_value_v1(details, 'support')}; contact = {_flow_value_v1(details, 'contact')}.",
                "BodyMap uses this representation to check proposed body actions; it never becomes the WNM. "
                "Protected means a selected task or desired result cannot overwrite this sensory-derived body evidence.",
            ),
            incoming="[Current POSTURE-SUPPORT configuration] from map service via cycle driver",
            outgoing=(
                f"[BodyMap {_flow_value_v1(details, 'state_id')}] stores posture={_flow_value_v1(details, 'posture')}, "
                f"support={_flow_value_v1(details, 'support')}, contact={_flow_value_v1(details, 'contact')}; "
                "used for candidacy and later action checks, never as WNM"
            ),
        )
    if event.channel == "body" and event.message == "POSTURE-SUPPORT map-state candidate published for Attention":
        return FlowStepV1(
            title="Nominate the POSTURE-SUPPORT source under the current-body evidence rule",
            explanations=(
                f"INPUT: source configuration {_flow_value_v1(details, 'source_state_id')}; "
                f"posture = {_flow_value_v1(details, 'posture')}; support = {_flow_value_v1(details, 'support')}.",
                "CHECK: update_from_map_state requires fallen posture, inadequate support and current evidence. "
                "WRITE: Nca8BodyRuntimeV1._posture_support_candidate references that current source configuration.",
                "NEXT: nca8_executive.py can submit this candidate to Attention during Phase D. Nomination is not "
                "source selection or action permission. The present A0 candidacy rule is based on body evidence, "
                "not on the outcome comparisons that follow in C2.",
            ),
            incoming=(
                f"[Current source configuration {_flow_value_v1(details, 'source_state_id')}] with "
                f"posture={_flow_value_v1(details, 'posture')}; support={_flow_value_v1(details, 'support')}"
            ),
            outgoing=(
                f"[Source nomination {_flow_value_v1(details, 'candidate_id')}] -> Attention in D; "
                "BodyMap creates this nomination, not the sensory service"
            ),
        )
    if event.channel == "body" and event.message == "no POSTURE-SUPPORT candidate published":
        return FlowStepV1(
            title="The current-body rule produces no posture-recovery nomination",
            explanations=(
                f"BodyMap reports candidate event {_flow_value_v1(details, 'candidate_event')}; posture = "
                f"{_flow_value_v1(details, 'posture')}; physical support = {_flow_value_v1(details, 'support')}.",
                "The current-evidence/fallen/inadequate-support rule did not produce a candidate. "
                "No candidate is supplied. Absence of a candidate alone does not prove standing: "
                "unknown or ambiguous body evidence can also prevent nomination.",
            ),
            incoming=f"[Current body] posture={_flow_value_v1(details, 'posture')}; support={_flow_value_v1(details, 'support')}",
            outgoing="No POSTURE-SUPPORT candidate -> Attention; this alone does not establish standing",
        )
    return None


def _flow_source_v1(details: Mapping[str, TraceScalarV1], context: _FlowContextV1) -> str:
    """Resolve a source only from an earlier retained source/configuration link."""
    state_id = _detail_str_v1(details, "source_state_id")
    source_map = context.source_maps.get(state_id) if state_id is not None else None
    if source_map is not None:
        return f"Source NavMap {source_map}, accessed through current configuration {state_id}."
    return (
        f"Source configuration reference: {_flow_value_v1(details, 'source_state_id')}. "
        "Its enduring source-map ID is not available from earlier retained mapping records."
    )


def _flow_focal_step_v1(event: Nca8TraceEventV1, context: _FlowContextV1) -> FlowStepV1 | None:
    """Keep Attention's source choice separate from Navigation's operation choice."""
    details = _details_v1(event)
    if event.channel == "attention":
        if event.message == "POSTURE-SUPPORT map-state candidate submitted as an Attention bid":
            return FlowStepV1(
                title="Build a source-priority bid; do not choose an operation",
                explanations=(
                    _flow_source_v1(details, context),
                    f"Priority ranks: safety = {_flow_value_v1(details, 'protected_safety_rank')}; "
                    f"task need = {_flow_value_v1(details, 'new_task_need_rank')}. "
                    "These rank a source candidate, not a primitive or a probability of success.",
                ),
                incoming=f"BodyMap -> [source nomination {_flow_value_v1(details, 'candidate_id')}]",
                outgoing=(
                    f"[Bid {_flow_value_v1(details, 'bid_id')}] -> Attention selection; safety rank "
                    f"{_flow_value_v1(details, 'protected_safety_rank')}, task-need rank {_flow_value_v1(details, 'new_task_need_rank')}"
                ),
            )
        for disposition, verb in (("switch", "switched"), ("maintain", "maintained"), ("release", "released")):
            if event.message == f"Attention {verb} the primary source map state":
                if disposition == "release":
                    setting = (
                        "The retained session-start record has Attention disabled."
                        if context.settings.get("attention_enabled") is False
                        else "This selection record does not, by itself, state why no source was selected."
                    )
                    return FlowStepV1(
                        title="Attention has no selected focal source",
                        explanations=(setting, "Attention selected no primitive; that is Navigation's job."),
                        incoming="Available source bids + prior focal-source context",
                        outgoing="[No selected source] -> Navigation; no WNM source is supplied",
                    )
                state_id = _detail_str_v1(details, "source_state_id")
                source_id = context.source_maps.get(state_id) if state_id is not None else None
                heading = f"Attention: {disposition} source {source_id}" if source_id is not None else (
                    f"Attention: {disposition} the source via {_flow_value_v1(details, 'source_state_id')}"
                )
                return FlowStepV1(
                    title=heading,
                    explanations=(
                        _flow_source_v1(details, context),
                        "Attention chooses focal access to the source, not its desired configuration and not the StandUp operation. "
                        "This scaffold records that choice through a source-state reference.",
                    ),
                    incoming="[Available source bids] from candidacy + prior focal-source context",
                    outgoing=(
                        f"[Source selection {_flow_value_v1(details, 'selection_id')}] -> Navigation for WNM maintenance; "
                        "source selection is not a StandUp command"
                    ),
                )
    if event.channel == "wnm":
        if event.message == "source-linked WNM constructed or refreshed from Attention's selected state":
            return FlowStepV1(
                title=f"Navigation copies/refreshes source-linked working content in {_flow_value_v1(details, 'working_id')}",
                explanations=(
                    f"Selected source {_flow_value_v1(details, 'source_map')} -> working representation "
                    f"{_flow_value_v1(details, 'working_id')}.",
                    f"Working relations: {_flow_relations_v1(_flow_value_v1(details, 'working_relations'))}.",
                    "Navigation copies or refreshes source-linked working content in this scaffold. "
                    "The WNM is not another durable map and cannot overwrite the source's sensory evidence.",
                ),
                incoming=(
                    f"Attention source selection + [source {_flow_value_v1(details, 'source_map')} / "
                    f"configuration {_flow_value_v1(details, 'source_state_id')}]"
                ),
                outgoing=(
                    f"[WNM relations: {_flow_relations_v1(_flow_value_v1(details, 'working_relations'))}] "
                    "maintained by Navigation -> primitive applicability; no source write-back"
                ),
            )
        if event.message == "no WNM exists because Attention released or selected no source":
            return FlowStepV1(
                title="No Working Navigation Map is available",
                explanations=(
                    "Attention selected no source, so Navigation has no WNM for a focal operation. This is not a BodyMap deletion.",
                ),
                incoming="Attention -> [no selected source]",
                outgoing="Navigation holds no WNM; no working content supplied for a focal operation. BodyMap remains separate",
            )
    if event.channel == "navigation":
        if event.message == "primitive applicability evaluated from the WNM":
            return FlowStepV1(
                title=f"Evaluate applicability of {_flow_value_v1(details, 'primitive_id')}; do not execute a body action",
                explanations=(
                    f"Primitive {_flow_value_v1(details, 'primitive_id')}: eligible = {_flow_value_v1(details, 'eligible')}; "
                    f"fit rank = {_flow_value_v1(details, 'fit_rank')}; safety rank = {_flow_value_v1(details, 'safety_rank')}; "
                    f"vetoes = {_flow_value_v1(details, 'vetoes')}.",
                    "This is an applicability check, not a dispatched body action.",
                ),
                incoming="Navigation -> [current WNM relations] -> primitive applicability check",
                outgoing=(
                    f"[Applicability report: eligible={_flow_value_v1(details, 'eligible')}; "
                    f"fit={_flow_value_v1(details, 'fit_rank')}; "
                    f"safety={_flow_value_v1(details, 'safety_rank')}; vetoes={_flow_value_v1(details, 'vetoes')}] -> Navigation"
                ),
            )
        if event.message == "Navigation commitment completed":
            if details.get("selected_primitive_id") is None and "selected_primitive_id" in details:
                return FlowStepV1(
                    title="Navigation selects no focal operation",
                    explanations=(_flow_reason_v1(details), "No task was selected by Navigation."),
                    incoming="Current WNM/absence + Navigation setting + applicability reports",
                    outgoing="No primitive application -> cycle driver; no new task request or PNM",
                )
            return FlowStepV1(
                title=(
                    f"Navigation selects and applies {_flow_value_v1(details, 'selected_primitive_id')} -> "
                    f"{_flow_value_v1(details, 'application_id')}"
                ),
                explanations=(
                    f"Selected primitive: {_flow_value_v1(details, 'selected_primitive_id')}; "
                    f"application: {_flow_value_v1(details, 'application_id')}.",
                    _flow_reason_v1(details),
                    "Primitive application -> task request. Selection is not BodyMap permission or proof that the body moved.",
                ),
                incoming="[Current WNM] + primitive applicability reports",
                outgoing=(
                    f"[Application {_flow_value_v1(details, 'application_id')}] -> prediction service for PNM "
                    "and BodyMap for task handoff in E; these are two separate consumers"
                ),
            )
    if event.channel == "runtime" and event.message == "Phase_D FOCAL_COMMITMENT completed":
        return FlowStepV1(
            title="Finish this cycle's focal selection",
            explanations=(
                f"Attention decision: {_flow_value_v1(details, 'attention_disposition')}; WNM: {_flow_value_v1(details, 'wnm')}; "
                f"selected primitive: {_flow_value_v1(details, 'selected_primitive')}; "
                f"application: {_flow_value_v1(details, 'focal_operation')}.",
                "These are the focal decisions already recorded above, not a second operation. Physical dispatch has not occurred here.",
            ),
            incoming="Attention selection + Navigation working representation and decision",
            outgoing=(
                f"[Focal decision: primitive {_flow_value_v1(details, 'selected_primitive')}; "
                f"application {_flow_value_v1(details, 'focal_operation')}] -> Phase E; no second operation"
            ),
        )
    return None


def _flow_outcome_step_v1(event: Nca8TraceEventV1, context: _FlowContextV1) -> FlowStepV1 | None:
    """Explain the recorded outcome using only matching earlier trace references.

    A not-applied outcome is not a sensory comparison even though the current
    runtime gives it the same message and Phase-C label. Retention gaps never
    license reconstruction of an absent PNM, observed relation, or causal claim.
    """
    if event.message != "later body evidence evaluated an operation-linked pending prediction":
        return None
    details = _details_v1(event)
    application = _flow_value_v1(details, "application_id")
    status = _detail_str_v1(details, "status")
    if status == "not_applied":
        return FlowStepV1(
            title="Close the prediction as NOT APPLIED, not as a failed movement",
            explanations=(
                f"Application {application} was not sent through the body handoff. This outcome does not compare later "
                "sensory evidence with a movement that occurred.",
                _flow_reason_v1(details),
            ),
            incoming=f"[Blocked handoff] for application {application}; no later-sensory comparison here",
            outgoing=f"[Prediction {_flow_value_v1(details, 'pnm_id')}: not_applied] -> prediction-service outcome history",
        )
    pnm_id = _detail_str_v1(details, "pnm_id")
    prior = context.predictions.get(pnm_id) if pnm_id is not None else None
    prior_details = _details_v1(prior) if prior is not None else {}
    linked = prior is not None and prior_details.get("application_id") == details.get("application_id")
    expected = (
        f"Earlier expectation [record #{prior.sequence}]: "
        f"{_flow_relations_v1(_flow_value_v1(prior_details, 'expected_relations'))}."
        if linked and prior is not None
        else "The matching earlier PNM contents are not retained in this view; no expectation is reconstructed."
    )
    body = context.map_evidence
    evidence_cycle = _detail_int_v1(details, "evidence_sampled_cycle")
    if body is not None and evidence_cycle is not None and body.cycle_id == evidence_cycle:
        body_details = _details_v1(body)
        observed = (
            f"Later POSTURE-SUPPORT interpretation [record #{body.sequence}, evidence cycle {evidence_cycle}]: "
            f"posture = {_flow_value_v1(body_details, 'posture')}; physical support = {_flow_value_v1(body_details, 'support')}."
        )
    else:
        observed = (
            f"Evidence cycle: {_flow_value_v1(details, 'evidence_sampled_cycle')}. "
            "Matching POSTURE-SUPPORT contents are not available from this retained sequence."
        )
    return FlowStepV1(
        title=f"Compare PNM {_flow_value_v1(details, 'pnm_id')} with eligible updated POSTURE-SUPPORT evidence",
        explanations=(
            "ROLE: the A0 prediction service performs this comparison. This is not a newly adopted Prediction Module "
        "and it is not a call to SEC. The placement of consequential outcome comparison in focal processing "
        "remains an architectural question; this display preserves the current code.",
        f"PredictionRuntime evaluates PNM {_flow_value_v1(details, 'pnm_id')} for application {application}.",
            "INPUT: Nca8PredictionRuntimeV1.evaluate_ready receives the updated NavMapStateV1 from C1, not a new "
            "sensory read and not BodyMap as its argument. It requires evidence applied in this cycle; "
            "_evaluate_one requires the prediction eligibility cycle to have been reached and the evidence sample "
            "to be later than prediction creation. A0 uses one POSTURE-SUPPORT route, not general source/identity correspondence.",
            "RULE: standing/stable satisfies the upright-support expectation; fallen/inadequate contradicts it. "
            "Other evidence can leave a prediction unresolved until expiry. WRITE: terminal outcomes enter "
            "Nca8PredictionRuntimeV1._outcome_history; unresolved traces remain pending. This does not choose a new operation.",
            expected,
            observed,
            f"Recorded prediction outcome: {_flow_value_v1(details, 'status')}. "
            "This is the existing A0 comparison, not a separate outcome-only focal cycle. "
            "A0's upright/stable expectation is not the future persistent Righting policy.",
            "Later evidence tests the expectation; it does not prove that this particular command alone caused the result. "
            "This comparison does not establish durable learning or select Attention's next source.",
        ),
        incoming=(
            f"[Earlier PNM] for {application} + [current POSTURE-SUPPORT configuration] from C1; "
            "not the BodyMap copy"
        ),
        outgoing=(
            f"[Outcome {_flow_value_v1(details, 'status')}] for {application} -> prediction-service result/history; "
            "no source nomination or new focal operation produced by this comparison"
        ),
    )


def _flow_action_step_v1(event: Nca8TraceEventV1, context: _FlowContextV1) -> FlowStepV1 | None:
    """Explain expectation, permission, commitment, and dispatch as separate events."""
    details = _details_v1(event)
    if event.channel == "outcome":
        return _flow_outcome_step_v1(event, context)
    if event.channel == "pnm" and event.message == "current PNM created before task-action dispatch":
        return FlowStepV1(
            title="Prediction service records the selected operation's expectation before dispatch",
            explanations=(
                "The Projected NavMap (PNM) records the selected operation's expected result before dispatch.",
                f"Application {_flow_value_v1(details, 'application_id')} -> prediction {_flow_value_v1(details, 'pnm_id')}.",
                f"Expected relations: {_flow_relations_v1(_flow_value_v1(details, 'expected_relations'))}.",
                f"Evidence condition: {_flow_value_v1(details, 'observation_condition')}. "
                "For the Gate-A condition next_current_body_support_evidence, the next eligible current body evidence "
                "tests the expectation. "
                "An expectation is not current-world truth, and creating it does not send an action.",
            ),
            incoming=f"Navigation -> [application {_flow_value_v1(details, 'application_id')} and expectation request]",
            outgoing=(
                f"[PNM {_flow_value_v1(details, 'pnm_id')}: "
                f"{_flow_relations_v1(_flow_value_v1(details, 'expected_relations'))}] -> prediction service retained for later evidence; "
                "the task request goes separately to BodyMap"
            ),
        )
    if event.channel == "bodymap":
        if event.message == "prior authorized action envelope reconciled from later body evidence":
            return FlowStepV1(
                title=f"Check/return earlier envelope {_flow_value_v1(details, 'envelope_id')} status; not a new action choice",
                explanations=(
                    "INPUT: Nca8BodyRuntimeV1._current_state and _current_envelope. "
                    "reconcile_envelope_from_current_state checks an authorized envelope against current body evidence. "
                    "Standing/stable marks it completed; fallen/inadequate marks it failed. Without usable current "
                    "evidence, or when the envelope is already closed, it returns the existing status unchanged.",
                    "WRITE: the returned envelope status remains in Nca8BodyRuntimeV1._current_envelope. "
                    "A returned status does not by itself prove a new transition occurred in this cycle.",
                    f"BodyMap records {_flow_value_v1(details, 'status')} for earlier envelope "
                    f"{_flow_value_v1(details, 'envelope_id')} using later body evidence.",
                    f"Recorded reason: {_flow_value_v1(details, 'status_reason')}. "
                    "An envelope identifies permission for an earlier action; issuing it did not prove success.",
                ),
                incoming="[BodyMap current-body register] + [previous authorized action envelope]",
                outgoing=(
                    f"[Envelope status {_flow_value_v1(details, 'status')}] -> BodyMap envelope register and cycle-driver report; "
                    "prediction evaluation is a separate check"
                ),
            )
        if event.message == "BodyMap mapped the selected task to a body-relative target and envelope":
            authorized = details.get("authorized")
            if authorized is True:
                heading = f"BodyMap permits {_flow_value_v1(details, 'task_action')} and records its body-relative target"
                consequence = (
                    "Task request -> body-state checks -> body-relative target plus action-permission envelope. "
                    "This is the Gate-A mapping scaffold, not a complete geometric or motor implementation."
                )
            elif authorized is False:
                heading = "BodyMap blocks the proposed task"
                consequence = "Task request -> body-state/permission checks -> handoff refused. No task action is authorized here."
            else:
                heading = "BodyMap handoff decision (authorization not recorded)"
                consequence = "No permission or rejection is inferred from a missing authorization value."
            return FlowStepV1(
                title=heading,
                explanations=(
                    f"Requested task: {_flow_value_v1(details, 'task_action')}. {_flow_reason_v1(details)}",
                    consequence,
                    f"Recorded body target: {_flow_value_v1(details, 'body_target')}; "
                    f"permission envelope: {_flow_value_v1(details, 'envelope')}.",
                ),
                incoming=(
                    f"Navigation application -> [task {_flow_value_v1(details, 'task_action')}] + "
                    "[BodyMap current posture/support] + handoff setting"
                ),
                outgoing=(
                    f"[Authorization={_flow_value_v1(details, 'authorized')}; target={_flow_value_v1(details, 'body_target')}; "
                    f"envelope={_flow_value_v1(details, 'envelope')}] -> cycle driver. {_flow_reason_v1(details)}"
                ),
            )
    if event.channel == "runtime" and event.message.startswith("Phase_E PROJECT_DISPATCH committed Action_"):
        task = _flow_value_v1(details, "task_action")
        action_number = _flow_value_v1(details, "action_number")
        if "task_action" in details and details["task_action"] is None:
            proposed = _detail_str_v1(details, "selected_primitive")
            explanation = (
                "A primitive was selected, but the commitment contains no authorized task action."
                if proposed is not None else "No focal primitive was selected; the commitment contains no task action."
            )
            return FlowStepV1(
                title=f"Commit Action_{action_number}:NO_ACTION",
                explanations=(
                    explanation,
                    "The output is now fixed. NO_ACTION still permits the environment to advance; it does not stop simulated time.",
                ),
                incoming="[Navigation decision] + any BodyMap handoff disposition",
                outgoing=(
                f"[Action_{action_number}:NO_ACTION] -> internal acceptance; outer world may advance time after close"
                if details.get("boundary_protocol") == "p16_1r_b_v1" else
                f"[Action_{action_number}:NO_ACTION] -> environment adapter; simulated time still advances"
            ),
            )
        return FlowStepV1(
            title=f"Commit Action_{action_number}:{task}",
            explanations=(
                "The runtime records the chosen output after the prediction and body-handoff stages. "
                "Commitment is not the physical dispatch itself; the boundary record below reports that dispatch.",
                f"PNM reference: {_flow_value_v1(details, 'pnm')}; permission envelope: {_flow_value_v1(details, 'envelope')}.",
            ),
            incoming="[Navigation application] + [PNM reference] + [BodyMap handoff result]",
            outgoing=(
                f"[Fixed Action_{action_number}:{task}] -> internal lower-action acceptance; no world step yet"
                if details.get("boundary_protocol") == "p16_1r_b_v1" else
                f"[Fixed Action_{action_number}:{task}] -> environment adapter; dispatch is reported separately"
            ),
        )
    if event.channel == "dispatch" and event.message.startswith("Action_") and event.message.endswith("physical environment boundary"):
        token = _detail_str_v1(details, "environment_action")
        if token is not None:
            emission = (
                f"The environment adapter emitted task token {token}. "
                f"Body authorization: {_flow_value_v1(details, 'body_authorized')}."
            )
        elif details.get("pnm_id") is not None and details.get("body_authorized") is False:
            emission = "No task token was emitted: a prediction existed, but the body handoff was blocked."
        elif "environment_action" in details and details["environment_action"] is None:
            emission = "No task token was emitted. This null dispatch is not itself evidence that BodyMap rejected a proposed task."
        else:
            emission = "The environment-action token is not recorded; no emission is inferred."
        return FlowStepV1(
            title="Report the completed combined boundary call; do not step the world again",
            explanations=(
                emission,
                "SOURCE CONTRACT: Nca8EpisodeRunnerV1's Phase-E callback calls "
                "Nca8EnvironmentBridgeV1.apply_task_action. The bridge translates the permitted request, "
                "advances the external environment, and calls adapt_env_observation_v1 on the returned observation. "
                "Only after that call returns does the callback append this dispatch record.",
                "This is a combined report across the lower-action/embodiment, external body/world and input domains. "
                "The external simulation is not cognition merely because Python calls it inside Phase E. "
                "There are no separate observed sub-records or substep timestamps; internal handoff acceptance is not "
                "yet a distinct receipt. Rendering this record performs none of those operations.",
                f"Environment step after dispatch: {_flow_value_v1(details, 'environment_step')}. "
                "The resulting observation is for the next cognitive cycle, not the action already committed. "
                "The later buffering record marks when the already-adapted packet is stored as pending input. "
                "It is not the time of whitelist filtering, and this dispatch report does not establish task success.",
            ),
            incoming=(
                f"Cycle driver -> [Action_{_flow_value_v1(details, 'action_number')}] with "
                f"body authorization {_flow_value_v1(details, 'body_authorized')}"
            ),
            outgoing=(
                f"[Environment token {_flow_value_v1(details, 'environment_action')}] -> external world; "
                f"world step {_flow_value_v1(details, 'environment_step')} returned an already-adapted next observation; "
                "later buffering only, not current-cycle evidence"
            ),
        )
    return None


def _flow_finish_step_v1(event: Nca8TraceEventV1, _context: _FlowContextV1) -> FlowStepV1 | None:
    """Keep optional support measurements and actual durable updates distinguishable."""
    details = _details_v1(event)
    if event.channel == "learning" and event.message == "Phase-F durable learning made no changes for initial Gate A":
        return FlowStepV1(
            title=f"Durable learning updates recorded: {_flow_value_v1(details, 'durable_updates')}",
            explanations=(
                f"Durable updates recorded: {_flow_value_v1(details, 'durable_updates')}. "
                "In initial Gate A this slot makes no durable map, primitive, or memory-learning changes. "
                "Current-configuration updates earlier in the cycle are not durable learning.",
                "TARGET DISTINCTION: Architecture v09.9 keeps F as a regular learning-reconciliation opportunity, "
                "not the only permitted learning time or another focal WNM operation. This A0 record remains a "
                "zero-update placeholder; it does not demonstrate the planned local learners or Emotion influences.",
            ),
            incoming="End-of-cycle bookkeeping slot; no durable-learning implementation runs in A0",
            outgoing=(
                f"[Durable updates {_flow_value_v1(details, 'durable_updates')}] -> diagnostic record only; "
                "this is not a new Learning Module"
            ),
        )
    if (
        event.channel == "support_observation" and event.message == _FLOW_SUPPORT_MESSAGE_V1
        and details.get("behavioral_authority") is False
    ):
        return FlowStepV1(
            title="Inspect optional support measurements without controlling behavior",
            explanations=(
                f"Nca8BodySensoryModuleV1 records sample {_flow_value_v1(details, 'sample_id')}; "
                f"disposition: {_flow_value_v1(details, 'disposition')}; event cycle: {_flow_value_v1(details, 'event_cycle')}; "
                f"available cycle: {_flow_value_v1(details, 'available_cycle')}; "
                f"applied cycle: {_flow_value_v1(details, 'applied_cycle')}.",
                f"Useful loading: {_flow_value_v1(details, 'useful_loading')}; destabilization: "
                f"{_flow_value_v1(details, 'destabilization')}; discrepancy: {_flow_value_v1(details, 'discrepancy')}.",
                "Behavioral authority is explicitly false. These read-only measurements do not change StandUp selection "
                "or authorize a body action. A missing measurement is not zero; sample times are not interchangeable.",
            ),
            incoming=f"[Optional support sample {_flow_value_v1(details, 'sample_id')}] -> read-only sensory companion",
            outgoing=(
                f"[Support disposition {_flow_value_v1(details, 'disposition')}] -> companion/diagnostics; "
                "behavioral authority=false, no task choice or body authorization"
            ),
        )
    return None


def _flow_boundary_step_v1(event: Nca8TraceEventV1, _context: _FlowContextV1) -> FlowStepV1 | None:
    """Describe actual P16-1R-B boundaries; no historical ID is reinterpreted."""
    details = _details_v1(event)
    if details.get("boundary_protocol") != "p16_1r_b_v1":
        return None
    receipt = _flow_value_v1(details, "receipt_id")
    if event.channel == "handoff" and event.message == "committed output accepted by internal lower-action boundary":
        return FlowStepV1(
            title="Accept the committed output at the internal lower-action boundary; do not execute it",
            incoming=f"[Immutable Action_{_flow_value_v1(details, 'action_number')}] with its permitted body request or null output",
            outgoing=f"[Receipt {receipt}: accepted] -> wait for F, housekeeping and internal closure; no world step yet",
            explanations=(
                "Nca8InternalHandoffV1.accept validates action, PNM, application and BodyMap links before filling one slot. "
                "Null output also uses a receipt so the outer driver may advance time once without a movement token.",
                "Acceptance is not execution or success. release_after_close makes the exact receipt ready only after "
                "the core finishes. consume marks it used before the outer side effect; copies and duplicate use are rejected.",
                f"Recorded receipt: {receipt}; generation {_flow_value_v1(details, 'generation')}; "
                f"disposition {_flow_value_v1(details, 'disposition')}.",
            ),
        )
    if event.channel == "cycle" and event.message == f"CognitiveCycle_{event.cycle_id} closed":
        return FlowStepV1(
            title=f"Close CognitiveCycle_{event.cycle_id} before external execution",
            incoming=f"Committed output {_flow_value_v1(details, 'output')}; completed F and scheduler housekeeping",
            outgoing=f"[Receipt {receipt}] -> ready for one outer consumption; no next observation available yet",
            explanations=(
                f"Input: {_flow_value_v1(details, 'input')} -> committed output: {_flow_value_v1(details, 'output')}. "
                "The next observation is not available at this internal boundary.",
                "The core records internal closure after F and scheduler completion, then releases the accepted receipt. "
                "It has not called the environment and cannot receive the next observation through a Phase-E callback.",
                "This is runtime accounting, not another cognitive operation or world step. The next external/input "
                "events are attributed to the originating cycle but are outside its internal processing.",
                "Later execution failure does not erase this closure or rewrite the earlier commitment. "
                "A closure record alone does not establish successful external consumption or input arrival.",
            ),
        )
    if event.channel == "dispatch" and event.message.startswith("Action_") and event.message.endswith("completed the external world step"):
        token = _flow_value_v1(details, "environment_action")
        return FlowStepV1(
            title="Report the returned external world step after one outer consumption",
            incoming=f"[Ready receipt {receipt}] -> consume once -> external world token {token}",
            outgoing=f"[World step {_flow_value_v1(details, 'environment_step')} returned] -> private raw packet awaits input admission",
            explanations=(
                "Nca8EpisodeRunnerV1 consumes the exact ready receipt after the core returns. "
                "Nca8EnvironmentBridgeV1.advance_task_action translates the permitted request and advances its private world once. "
                "No raw observation, reward or done result enters the closed cognitive call.",
                f"Environment step after dispatch: {_flow_value_v1(details, 'environment_step')}. "
                "Returned means the external call returned, not that the task succeeded. "
                "A null token advances time without an additional movement command.",
                "The raw packet remains private in the bridge. admit_observation subsequently filters and detaches it; "
                "that input operation and the later buffer assignment have their own actual records.",
            ),
        )
    if event.channel == "input" and event.message == (
        f"Observation_{details.get('observation_number')} admitted and detached at the input boundary"
    ):
        number = _flow_value_v1(details, "observation_number")
        return FlowStepV1(
            title=f"Admit and detach Observation_{number} through the positive whitelist",
            incoming=f"[Private raw world packet] associated with receipt {receipt} -> input adapter",
            outgoing=f"[NCA8-owned Observation_{number}] -> pending-input assignment; not sensory interpretation",
            explanations=(
                "Nca8EnvironmentBridgeV1.admit_observation consumes the exact world receipt once and calls the existing "
                "adapt_env_observation_v1. Raw EnvObservation stays outside cognition. This operation does not advance time.",
                "A missing or malformed outer packet stops the session rather than copying the old observation. "
                "An invalid optional support packet keeps its existing bounded rejection status and no behavioral authority.",
                _flow_observation_counts_v1(details),
                "Admission occurs after the internal cycle closed. Only a later eligible cognitive cycle can interpret the packet.",
            ),
        )
    if (event.channel, event.message) in {
        ("boundary_failure", "runner stopped after boundary failure"),
        ("protection", "protected stop revoked further execution permission"),
    }:
        return FlowStepV1(
            title=event.message.capitalize(),
            incoming=f"[Receipt {receipt}] / stage {_flow_value_v1(details, 'stage')}; reason {_flow_value_v1(details, 'reason')}",
            outgoing=f"[Execution {_flow_value_v1(details, 'execution_status')}; handoff {_flow_value_v1(details, 'handoff_disposition')}] "
            "-> stopped; no pending input, no automatic retry; explicit reset required",
            explanations=(
                "A refusal or cancelled unconsumed serialized request is not execution. Once a world call may have "
                "run, an exception is recorded as unknown execution; it must not produce an automatic second attempt.",
                "A returned world call followed by failed admission is different: execution returned, but no usable next "
                "observation is available. The old packet is never reintroduced as new evidence.",
                "Outstanding BodyMap permission is revoked without changing the immutable command or current sensory facts. "
                "Only known nonexecution marks the corresponding pending claim NOT_APPLIED; unknown/returned attempts stay unresolved.",
                "This serialized simulator supplies no continuing actuator to stop. Protected stopping withholds further "
                "execution; it is not proof of physical rollback, a confirmed motor stop or selection of another task.",
            ),
        )
    return None


_FLOW_BUILDERS_V1: Mapping[str, Callable[[Nca8TraceEventV1, _FlowContextV1], FlowStepV1 | None]] = {
    "session": _flow_input_step_v1,
    "firewall": _flow_input_step_v1,
    "cycle": _flow_input_step_v1,
    "scheduler": _flow_scheduler_step_v1,
    "sensory": _flow_representation_step_v1,
    "maps": _flow_representation_step_v1,
    "body": _flow_representation_step_v1,
    "attention": _flow_focal_step_v1,
    "wnm": _flow_focal_step_v1,
    "navigation": _flow_focal_step_v1,
    "pnm": _flow_action_step_v1,
    "bodymap": _flow_action_step_v1,
    "outcome": _flow_action_step_v1,
    "dispatch": _flow_action_step_v1,
    "learning": _flow_finish_step_v1,
    "support_observation": _flow_finish_step_v1,
}


def _flow_step_v1(event: Nca8TraceEventV1, context: _FlowContextV1) -> FlowStepV1 | None:
    """Build a recognized event's parts-first account without consulting live objects.

    Unknown messages do not inherit a guessed component or mechanism from their
    channel. Software names are attached later, underneath the numbered explanation.
    """
    step = _flow_boundary_step_v1(event, context)
    if step is not None:
        return step
    if event.channel == "runtime":
        for runtime_builder in (_flow_representation_step_v1, _flow_focal_step_v1, _flow_action_step_v1):
            step = runtime_builder(event, context)
            if step is not None:
                break
    else:
        builder = _FLOW_BUILDERS_V1.get(event.channel)
        step = builder(event, context) if builder is not None else None
    if step is None:
        return None
    return step



def _flow_component_v1(event: Nca8TraceEventV1) -> tuple[str, str]:
    """Classify an already recognized step, not arbitrary channel names.

    PART names are canonical functional CCA8 components, not assertions that a
    full biological or hardware implementation exists. REPRESENTATION names
    identify maintained information. SERVICE includes runtime infrastructure and
    temporary sensory/prediction approximations; essential work done by a service
    does not establish a new architectural processor. Call only after recognition.
    """
    if event.channel == "navigation" and event.message == "primitive applicability evaluated from the WNM":
        if dict(event.details).get("primitive_id") == "ip:stand_up":
            return "PART", "StandUp Instinctive Primitive (IP)"
        return "PART", "Navigation Module - primitive query"
    components = {
        "session": ("SERVICE", "Session setup"),
        "firewall": ("SERVICE", "Observation adapter and pending-input buffer"),
        "cycle": ("SERVICE", "Cognitive-cycle driver"),
        "scheduler": ("SERVICE", "Scheduler"),
        "runtime": ("SERVICE", "Cognitive-cycle driver"),
        "sensory": ("SERVICE", "A0 body-sensory scaffold"),
        "maps": ("REPRESENTATION", "POSTURE-SUPPORT current configuration"),
        "body": ("PART", "BodyMap"),
        "bodymap": ("PART", "BodyMap"),
        "attention": ("PART", "Attention"),
        "wnm": ("REPRESENTATION", "Working Navigation Map (WNM) - maintained by Navigation"),
        "navigation": ("PART", "Navigation Module"),
        "pnm": ("REPRESENTATION", "Projected NavMap (PNM) - held by prediction service"),
        "outcome": ("SERVICE", "A0 prediction evaluation"),
        "dispatch": ("SERVICE", "Lower-action / environment adapter"),
        "handoff": ("SERVICE", "Internal lower-action handoff"),
        "input": ("SERVICE", "Observation admission adapter"),
        "boundary_failure": ("SERVICE", "Boundary failure and safe-stop accounting"),
        "protection": ("SERVICE", "Protected execution stop"),
        "learning": ("SERVICE", "A0 learning slot - no durable learning"),
        "support_observation": ("SERVICE", "Read-only support-observation companion"),
    }
    return components[event.channel]


def _flow_domain_v1(event: Nca8TraceEventV1) -> str:
    """Name the domain of an already recognized source-code operation.

    Call only after ``_flow_step_v1`` recognizes the message. Channel or phase
    alone cannot classify an unknown event. The return value is presentation
    metadata: it is neither written to the event nor used by any runtime owner.
    A SERVICE can implement cognition or infrastructure. Historical combined
    dispatch reports keep their mixed-domain meaning; the versioned new protocol
    records internal handoff, external return and input admission separately.
    """
    if dict(event.details).get("boundary_protocol") == "p16_1r_b_v1":
        if event.channel == "dispatch":
            return "EXTERNAL BODY + WORLD (after internal cognitive-cycle closure)"
        if event.channel == "input":
            return "CCA8 INPUT BOUNDARY (admission and detachment, not interpretation)"
        if event.channel in {"handoff", "protection"}:
            return "CCA8 LOWER-ACTION / EMBODIMENT BOUNDARY"
        if event.channel == "boundary_failure":
            return "CCA8 RUNTIME INFRASTRUCTURE (external/input/core failure accounting)"
    if event.channel == "dispatch":
        return (
            "MIXED BOUNDARY REPORT: CCA8 LOWER-ACTION / EMBODIMENT BOUNDARY -> "
            "EXTERNAL BODY + WORLD -> CCA8 INPUT BOUNDARY"
        )
    if event.channel == "firewall":
        return "CCA8 INPUT BOUNDARY (admitted-packet buffering)"
    if event.channel in ("session", "cycle", "scheduler"):
        return "CCA8 RUNTIME INFRASTRUCTURE (not a cognitive operation)"
    if event.channel == "runtime" and not event.message.startswith("Phase_E PROJECT_DISPATCH committed Action_"):
        return "CCA8 RUNTIME INFRASTRUCTURE (identity or summary bookkeeping)"
    return "CCA8 COGNITION (implemented function or declared A0 approximation)"


def _flow_target_note_v1(width: int) -> list[str]:
    """Draw the planned boundary order without fabricating a recorded event.

    This constant schematic describes P16-1R-B, not the call order in A0 and
    not a simulated replay. It has no sequence number, observed time, or live
    state. Keeping it outside the recorded diagrams also keeps partial traces
    from acquiring imagined opening, handoff, world-step, or closure records.
    """
    lines: list[str] = []
    for paragraph in (
        "PLANNED TARGET ORDER - NOT EXECUTED (P16-1R-B)",
        "Unnumbered architecture schematic, separate from the recorded flow:",
        "  CCA8 COGNITION: E commits the permitted action",
        "    -> LOWER-ACTION / EMBODIMENT BOUNDARY: internal handoff",
        "    -> CCA8 COGNITION: F learning reconciliation",
        "    -> RUNTIME INFRASTRUCTURE: housekeeping; internal close",
        "  EXTERNAL BODY + WORLD: outer runner consumes once",
        "    -> INPUT BOUNDARY: admit / detach / buffer observation",
        "    -> next eligible cognitive cycle",
        "This is the planned serialized simulator driver. A real body/world may begin evolving at handoff "
        "and overlap F. Future evidence cannot justify the earlier decision. The current A0 callback still "
        "steps the world and adapts input before F; its buffering and closure records remain in their original order.",
    ):
        lines.extend(_flow_wrap_v1(paragraph, width))
    lines.extend(("=" * width, ""))
    return lines

def _flow_separated_note_v1(width: int) -> list[str]:
    """Show the marked protocol's reference order, not fictional missing events."""
    lines: list[str] = []
    for paragraph in (
        "P16-1R-B REFERENCE ORDER - NOT ADDITIONAL TRACE EVENTS",
        "A retained protocol marker identifies the separated driver. The numbered records below remain the execution evidence.",
        "  INTERNAL: commit -> accept handoff -> F -> scheduler -> close",
        "  EXTERNAL: consume once -> world step returns",
        "  INPUT: admit / detach -> buffer -> next eligible cycle",
        "Failures can stop this sequence; a missing record never proves completion. No elapsed times are invented. "
        "Real body/world evolution may overlap F; this is the serialized simulator's order, not a global biological clock.",
    ):
        lines.extend(_flow_wrap_v1(paragraph, width))
    lines.extend(("=" * width, ""))
    return lines


def _flow_part_box_v1(title: str, rows: Sequence[str], width: int, *, kind: str) -> list[str]:
    """Draw one event with a category-specific outline and labeled information ports.

    Solid outlines denote functional parts, bracketed outlines representations,
    and dashed outlines services. Unknown records use the service-like outline
    but an explicit UNCLASSIFIED heading, never an invented component. Phase
    headings remain outside these boxes because a scheduler phase is not a part.
    """
    span = width - 4
    if kind == "PART":
        border = "  +" + "-" * span + "+"
        side = "|"
    elif kind == "REPRESENTATION":
        border = "  [" + "-" * span + "]"
        side = "|"
    else:
        border = "  +" + ("- " * span)[:span] + "+"
        side = ":"
    inside_width = width - 6
    lines = [border]
    for paragraph in (title, *rows):
        for row in _flow_wrap_v1(paragraph, inside_width):
            lines.append(f"  {side} " + row.ljust(inside_width) + f" {side}")
    lines.append(border)
    return lines

def _flow_ascii_v1(text: str) -> str:
    """Escape controls and non-ASCII characters so traces cannot alter the terminal.

    Normal printable ASCII, including identifiers and backslashes, is preserved.
    Other characters are shown as Python-style escapes rather than executed as
    terminal controls or silently removed. Rendering does not alter raw records.
    """
    return "".join(character if " " <= character <= "~" else ascii(character)[1:-1] for character in text)


def _flow_wrap_v1(text: str, width: int, *, indent: str = "") -> list[str]:
    """Wrap text deterministically, including long identifiers, without truncation."""
    return textwrap.wrap(
        _flow_ascii_v1(text), width=width, initial_indent=indent, subsequent_indent=indent,
        break_long_words=True, break_on_hyphens=False,
    ) or [indent]


def _flow_c_section_v1(event: Nca8TraceEventV1) -> str:
    """Return a display subsection for recognized Phase-C records only.

    The scheduler retains its original UPDATE_OUTCOMES enum and event metadata.
    Unknown messages remain explicitly unclassified. NOT_APPLIED is handled
    before this helper because it belongs at the later handoff position.
    """
    if event.channel == "bodymap" and event.message == "prior authorized action envelope reconciled from later body evidence":
        return _FLOW_C2_V1
    if event.channel == "outcome" and event.message == "later body evidence evaluated an operation-linked pending prediction":
        return _FLOW_C2_V1
    known_messages = {
        "scheduler": ("Phase_C UPDATE_OUTCOMES applied frozen results",),
        "sensory": ("posture predicate scaffold interpreted as current SELF-ground evidence",),
        "maps": ("POSTURE-SUPPORT NavMapState updated without durable map revision",),
        "body": (
            "BodyMapState updated from current POSTURE-SUPPORT evidence",
            "POSTURE-SUPPORT map-state candidate published for Attention",
            "no POSTURE-SUPPORT candidate published",
        ),
    }
    if event.message in known_messages.get(event.channel, ()):
        return _FLOW_C1_V1
    details = _details_v1(event)
    number = _detail_int_v1(details, "observation_number")
    if event.channel == "runtime" and number is not None and event.message == (
        f"Observation_{number} became the applied Phase-C cycle input"
    ):
        return _FLOW_C1_V1
    if (
        event.channel == "support_observation" and event.message == _FLOW_SUPPORT_MESSAGE_V1
        and details.get("behavioral_authority") is False
    ):
        return _FLOW_C1_V1
    return "UPDATE_OUTCOMES"


def _flow_section_v1(event: Nca8TraceEventV1) -> str:
    """Group adjacent records only; never sort by the phase label or move outcomes."""
    if (
        event.channel == "outcome"
        and event.message == "later body evidence evaluated an operation-linked pending prediction"
        and dict(event.details).get("status") == "not_applied"
    ):
        return "NOT_APPLIED"
    if dict(event.details).get("boundary_protocol") == "p16_1r_b_v1":
        if event.channel == "dispatch":
            return "EXTERNAL_WORLD"
        if event.channel == "input":
            return "ADMISSION"
        if event.channel == "boundary_failure":
            return "BOUNDARY_FAILURE"
        if event.channel == "protection":
            return "PROTECTED_STOP"
    if event.phase == "UPDATE_OUTCOMES":
        return _flow_c_section_v1(event)
    if event.phase is not None:
        return event.phase
    if event.channel == "cycle" and " opened with Observation_" in event.message:
        return "INPUT"
    if event.channel == "cycle" and event.message.endswith(" closed"):
        return "CLOSE"
    if event.channel == "session":
        return "SETUP"
    if event.channel == "firewall":
        return "BUFFER"
    return "OTHER"


def _flow_group_title_v1(section: str) -> str:
    """Return a display title; unknown phase labels remain visible and untranslated."""
    titles = {
        **_FLOW_PHASE_TITLES_V1,
        **_FLOW_C_TITLES_V1,
        "UPDATE_OUTCOMES": "PHASE C - UNCLASSIFIED RECORD; C1/C2 NOT INFERRED",
        "INPUT": "OPEN THE CYCLE WITH ITS PENDING INPUT",
        "CLOSE": "CLOSE THE CYCLE",
        "SETUP": "SESSION INITIALIZATION",
        "BUFFER": "INPUT BOUNDARY AND PENDING OBSERVATION",
        "EXTERNAL_WORLD": "OUTSIDE THE INTERNAL COGNITIVE CYCLE - EXTERNAL BODY / WORLD",
        "ADMISSION": "CCA8 INPUT BOUNDARY - ADMIT LATER INPUT AFTER INTERNAL CLOSURE",
        "BOUNDARY_FAILURE": "BOUNDARY FAILURE - STOPPED; EXECUTION AND INPUT STATUS REMAIN EXPLICIT",
        "PROTECTED_STOP": "PROTECTED STOP - REVOKE PERMISSION WITHOUT REWRITING THE COMMITMENT",
        "OTHER": "OTHER RETAINED EVENTS",
        "NOT_APPLIED": "OUTCOME AT THIS POINT - THE TASK WAS NOT SENT",
    }
    return titles.get(section, f"UNRECOGNIZED STORED PHASE: {section}")


def _flow_groups_v1(events: Sequence[Nca8TraceEventV1]) -> list[tuple[Nca8TraceEventV1, ...]]:
    """Partition consecutive records at phase changes or gaps without losing any event."""
    groups: list[tuple[Nca8TraceEventV1, ...]] = []
    current: list[Nca8TraceEventV1] = []
    for event in events:
        if current and (
            _flow_section_v1(event) != _flow_section_v1(current[-1]) or event.sequence != current[-1].sequence + 1
        ):
            groups.append(tuple(current))
            current = []
        current.append(event)
    if current:
        groups.append(tuple(current))
    return groups


def _flow_technical_v1(event: Nca8TraceEventV1, width: int) -> list[str]:
    """Show every stored detail below its block, with exact names retained for debugging."""
    lines = _flow_wrap_v1(
        f"Technical record #{event.sequence}: channel={event.channel}; stored phase={event.phase or '(outside phases)'}",
        width, indent="    ",
    )
    lines.extend(_flow_wrap_v1(f"Original message: {event.message}", width, indent="      "))
    detail_text = "; ".join(f"{key}={value!r}" for key, value in event.details)
    if detail_text:
        lines.extend(_flow_wrap_v1(detail_text, width, indent="      "))
    return lines


def _flow_cycle_heading_v1(events: Sequence[Nca8TraceEventV1], width: int) -> list[str]:
    """Identify visible cycle boundaries and missing phases without reconstructing them."""
    cycle_id = events[0].cycle_id
    if cycle_id is None:
        initial = any(
            event.channel == "session" and event.message == "isolated Phase-1D Gate-A session reset"
            and dict(event.details).get("pending_observation_number") == 1
            for event in events
        )
        if initial:
            return ["", "=" * width, "BEFORE COGNITIVE CYCLE 1", "Session setup and pending input", "=" * width]
        return ["", "=" * width, "RECORDS OUTSIDE A NUMBERED COGNITIVE CYCLE", "=" * width]
    opening = any(
        event.channel == "cycle" and event.message == (
            f"CognitiveCycle_{cycle_id} opened with Observation_{dict(event.details).get('observation_number')}"
        )
        for event in events
    )
    closing = any(event.channel == "cycle" and event.message == f"CognitiveCycle_{cycle_id} closed" for event in events)
    sections = {_flow_section_v1(event) for event in events}
    if sections & {_FLOW_C1_V1, _FLOW_C2_V1}:
        sections.add("UPDATE_OUTCOMES")
    missing = [title.split(" - ", 1)[0] for key, title in _FLOW_PHASE_TITLES_V1.items() if key not in sections]
    lines = ["", "=" * width, f"COGNITIVE CYCLE {cycle_id}", "=" * width]
    lines.extend(_flow_wrap_v1(
        "TRACE GROUP: stored cycle_id associates these records; it does not put every operation inside cognition. "
        "Use DOMAIN for architectural location and the stored phase for the current software schedule.", width,
    ))
    lines.extend(_flow_wrap_v1(f"Retained records #{events[0].sequence}-#{events[-1].sequence}.", width))
    if not opening or not closing or missing:
        lines.extend(_flow_wrap_v1(
            "PARTIAL VIEW: opening record " + ("retained" if opening else "not retained") + "; closing record "
            + ("retained" if closing else "not retained") + ". Missing records are not proof that steps did not occur.", width,
        ))
    if missing:
        lines.extend(_flow_wrap_v1("Phases not represented here: " + ", ".join(missing) + ". No boxes are invented for them.", width))
    return lines


def _flow_empty_c2_note_v1(*, first_cycle: bool, width: int) -> tuple[list[str], list[str]]:
    """Describe the absence of C2 events without inventing an execution record.

    A first-cycle statement requires retained reset/input context with no gap.
    Otherwise absence says only that no outcome event is present, not whether
    there are pending predictions or whether a comparison took place.
    """
    title = _FLOW_C_TITLES_V1[_FLOW_C2_V1]
    if first_cycle:
        note = (
            "CONTEXT NOTE (not a trace event): first cycle after the retained session reset; "
            "no earlier NCA8 action exists to resolve. No C2 outcome-result record is emitted."
        )
    else:
        note = (
            "CONTEXT NOTE (not a trace event): no earlier-outcome record is present at this boundary. "
            "This does not establish that no prediction is pending or that an evaluation succeeded."
        )
    explanation = (
        "A0 call path in nca8_runtime.py: after C1, nca8_body.py.reconcile_envelope_from_current_state reads "
        "BodyMap and the previous action envelope; nca8_prediction.py.evaluate_ready reads the updated "
        "POSTURE-SUPPORT map state and pending predictions. These are separate checks before Phase D. "
        "This note describes that source-code contract; it is not a fabricated record of a comparison."
    )
    box = _flow_part_box_v1(title, (note,), width, kind="SERVICE")
    notes = _flow_wrap_v1(title, width) + _flow_wrap_v1(note, width, indent="  ")
    notes.extend(_flow_wrap_v1(explanation, width, indent="    "))
    notes.append("")
    return box, notes


def _flow_render_cycle_v1(
    events: Sequence[Nca8TraceEventV1], context: _FlowContextV1, *, width: int, include_details: bool,
) -> list[str]:
    """Render parts, representations and services in retained order, never sort by topology.

    Every known event gets a named participant plus input, operation and output
    ports. The between-box arrows explicitly mean record order; ports describe
    data wiring. This avoids implying that, for example, a prediction evaluation
    directly created the next Attention bid just because those events are adjacent.
    Unknown events, missing records and misleading phase labels stay visible.
    DOMAIN identifies architectural location independently of the part/service
    category and stored cycle/phase grouping. Mixed boundary calls remain one
    historical event, with no artificial sub-records or chronology changes.
    """
    lines = _flow_cycle_heading_v1(events, width)
    lines.append("")
    lines.extend(_flow_wrap_v1("RECORDED FLOW - follow the boxes; explanations follow the diagram.", width))
    lines.append("")
    explanation_lines: list[str] = []
    context.map_evidence = None
    first_cycle = (
        context.initial_cycle_pending and events[0].cycle_id == 1 and events[0].channel == "cycle"
        and events[0].message == "CognitiveCycle_1 opened with Observation_1"
    )
    if events[0].cycle_id is not None:
        context.initial_cycle_pending = False
    sections = {_flow_section_v1(event) for event in events}
    previous: Nca8TraceEventV1 | None = None
    phase_e_seen = False
    for group in _flow_groups_v1(events):
        notes: list[str] = []
        section = _flow_section_v1(group[0])
        contiguous = previous is not None and group[0].sequence == previous.sequence + 1
        if (
            section == "FOCAL_COMMITMENT" and contiguous and previous is not None #pylint: disable=too-many-boolean-expressions
            and _flow_section_v1(previous) == _FLOW_C1_V1
            and _FLOW_C2_V1 not in sections and "UPDATE_OUTCOMES" not in sections
        ):
            box, c2_notes = _flow_empty_c2_note_v1(first_cycle=first_cycle, width=width)
            lines.extend(("", "       |  retained order; context note below is not an event", "       v", ""))
            lines.extend(box)
            explanation_lines.extend(c2_notes)
        lines.extend(_flow_wrap_v1(_flow_group_title_v1(section), width))
        lines.append("-" * width)
        if section == "PROJECT_DISPATCH":
            phase_e_seen = True
        if section == "NOT_APPLIED" and phase_e_seen and group[0].phase == "UPDATE_OUTCOMES":
            notes.extend(_flow_wrap_v1(
                "TRACE LABEL WARNING: this outcome carries the stored Phase-C label UPDATE_OUTCOMES, "
                "but appears after Phase-E records. It stays at its recorded position. This is not a second Phase C "
                "or evidence of a later sensory comparison.", width, indent="  ",
            ))
        for event in group:
            if previous is not None:
                if event.sequence == previous.sequence + 1:
                    lines.extend(("", "       |  retained order (not a signal wire)", "       v", ""))
                else:
                    lines.extend(_flow_wrap_v1(
                        f"GAP: records #{previous.sequence + 1}-#{event.sequence - 1} are absent. "
                        "No flow arrow is drawn across that gap.", width,
                    ))
                    context.map_evidence = None
                    context.source_maps.clear()
                    context.settings.clear()
                    first_cycle = False
                    context.initial_cycle_pending = False
            step = _flow_step_v1(event, context)
            untranslated = step is None
            if step is None:
                kind, component = "UNCLASSIFIED", "Untranslated event - original message"
                step = FlowStepV1(
                    title=event.message, explanations=(event.message,),
                    incoming="No input route is inferred for an unrecognized event.",
                    outgoing="No output route is inferred; original message and details are retained.",
                )
            else:
                kind, component = _flow_component_v1(event)
            label = f"{kind}: {component}"
            domain = "UNCLASSIFIED - no domain inferred from channel or phase" if untranslated else _flow_domain_v1(event)
            rows = (f"DOMAIN: {domain}", f"INPUT: {step.incoming}", f"DO: {step.title}", f"OUTPUT: {step.outgoing}")
            lines.extend(_flow_part_box_v1(f"[#{event.sequence}] {label}", rows, width, kind=kind))
            notes.extend(_flow_wrap_v1(f"Record #{event.sequence} - {label}", width, indent="  "))
            for paragraph in rows:
                notes.extend(_flow_wrap_v1(paragraph, width, indent="    "))
            notes.extend(_flow_wrap_v1("Mechanism / storage / limits:", width, indent="    "))
            for explanation in step.explanations:
                notes.extend(_flow_wrap_v1(explanation, width, indent="    "))
            if not untranslated:
                implementation = _FLOW_MODULES_V1[event.channel]
                if event.channel == "navigation" and event.message == "primitive applicability evaluated from the WNM":
                    implementation += " / nca8_primitives.py"
                notes.extend(_flow_wrap_v1(f"Implementation: {implementation}", width, indent="    "))
            if include_details or untranslated:
                notes.extend(_flow_technical_v1(event, width))
            notes.append("")
            context.remember(event)
            previous = event
        explanation_lines.extend(_flow_wrap_v1(_flow_group_title_v1(section), width))
        explanation_lines.extend(notes)
    lines.append("")
    lines.extend(_flow_wrap_v1("EXPLANATIONS - same record order, with data below the relevant step.", width))
    lines.append("-" * width)
    lines.extend(explanation_lines)
    return lines


def render_flow_trace_lines_v1(
    events: Sequence[Nca8TraceEventV1], *, width: int = 96, include_details: bool = True,
) -> tuple[str, ...]:
    """Return a read-only narrated ASCII flowchart of retained NCA8 trace events.

    Parameters
    ----------
    events:
        One session's immutable trace snapshot in strictly increasing sequence
        order. Consecutive events are grouped by cycle and phase without sorting.
        Gaps, absent cycle boundaries, and absent phases remain explicit. The
        renderer never constructs a missing processing step from a later result.
    width:
        Terminal width, from 60 through 140 columns. All output, including long
        identifiers and escaped control characters, is wrapped to this bound.
        Printable ASCII boxes work without ANSI colors or Unicode font support.
    include_details:
        Include the exact stored detail fields with each numbered explanation. Unknown
        events always retain their original message and details, even when this
        option is false. Compact and explanatory legacy renderers remain separate.

    Returns
    -------
    tuple[str, ...]
        Deterministic display lines, or an empty tuple for an empty snapshot.
        Record references connect explanations to the underlying trace. Main
        downward arrows indicate retained execution order, not a claim that every
        adjacent event caused the next. In particular, current A0 outcome checks
        are not redrawn as a new Attention-selection or outcome-only mechanism.

    Authority and limits
    --------------------
    No live session, environment, map, or prediction service is read. Earlier PNM
    and source-map references are resolved only from preceding retained records.
    Parts, representations and services use distinct labels and outlines. Their
    input/output ports describe implemented wiring, not causal inference from
    adjacency. Module/function/storage names below the chart describe the source
    contract; they are not additional recorded measurements. C1/C2 only subdivide the displayed
    Phase C. An unnumbered C2 absence note never asserts an unrecorded outcome.
    Rendering performs no cognitive steps and neither mutates nor caches input.
    The current not-applied outcome's misleading Phase-C metadata is displayed
    with a warning at its recorded position, not fixed in the canonical trace.
    DOMAIN is independent of the component category and stored phase. The
    historical dispatch report covers a combined boundary call. P16-1R-B records
    identify real separated handoff, external and input operations by protocol.
    Neither reference schematic invents missing execution evidence. Original messages remain
    available with the technical details. This is an implementation view, not
    certification of architectural validity.
    """
    if isinstance(width, bool) or not isinstance(width, int) or not 60 <= width <= 140:
        raise ValueError("flow trace width must be an integer from 60 to 140")
    if not isinstance(include_details, bool):
        raise TypeError("include_details must be Boolean")
    snapshot = tuple(events)
    previous_sequence = 0
    for event in snapshot:
        if not isinstance(event, Nca8TraceEventV1):
            raise TypeError("flow trace rendering requires Nca8TraceEventV1 values")
        if event.sequence <= previous_sequence:
            raise ValueError("flow trace events must have strictly increasing sequence numbers from one session")
        previous_sequence = event.sequence
    if not snapshot:
        return ()
    lines = ["NCA8 GUIDED FLOW TRACE", "=" * width]
    for paragraph in (
        "PARTS FIRST: read each named component's INPUT, DO and OUTPUT. The main diagram describes the "
        "functional machine; Python filenames, calls and storage addresses appear in the explanations below.",
        "LEGEND: solid +---+ boxes are PARTS (CCA8 functional components); bracketed [---] boxes are "
        "REPRESENTATIONS; dashed +- -+ boxes are SERVICES / SCAFFOLDS. Phase headings are timing groups, not parts.",
        "PART does not mean one chip or a fully implemented brain circuit. A0 approximates Attention, Navigation, "
        "StandUp IP and BodyMap. POSTURE-SUPPORT, WNM and PNM are representations. A0 body-sensory processing "
        "and prediction evaluation are software services, not newly invented architectural modules. "
        "Repeated part names show repeated operations of the same session component, not extra parts.",
        "DOMAIN is separate from PART/REPRESENTATION/SERVICE and from an INTEGRITY CHECK's purpose. "
        "It distinguishes CCA8 cognition, the lower-action/embodiment boundary, external body/world, input boundary "
        "and supporting runtime infrastructure. A cognitive SERVICE is not the same thing as scheduler housekeeping.",
        "Cycle and phase headings group existing records by their stored labels; they are NOT cognitive-system walls. "
        "P16-1R-B explicitly records internal handoff and closure, then separate external-world and input events. "
        "Historical combined callbacks retain their mixed-domain explanation; no missing handoff/world/input event is invented.",
        "INPUT/OUTPUT name the implemented information routes. Downward arrows BETWEEN boxes show retained "
        "execution order, not proof that every adjacent step caused the next. In particular, the outcome check "
        "does not generate BodyMap's source nomination. Follow the named input source, not just the previous box.",
        "C1 applies current input and updates representations. C2 resolves earlier-operation outcomes using that "
        "updated evidence. They are display subsections of the existing Phase C (UPDATE_OUTCOMES), not new scheduler phases.",
        "MECHANISM and storage-location descriptions explain the source-code contract. Actual values come from "
        "retained records only. Unnumbered CONTEXT NOTES are explanations, not additional execution events. "
        "A service may perform necessary cognitive work without establishing an additional architectural part. "
        "Several records can describe one completed call; record numbers are not extra processing steps.",
        "This is the current A0 implementation, not the full scientific target. SEC, WorldIndex, general sensory/ANM "
        "learning, Emotion and LP induction are not active in this Gate-A path. The chart does not invent those steps, "
        "detailed motor execution, or a separate outcome-only focal cycle.",
        "Record numbers identify the existing diagnostic events. Boxes and wrapped lines do not consume trace "
        "capacity. A missing record is not proof that an event never happened. Predictions are not observations.",
    ):
        lines.extend(_flow_wrap_v1(paragraph, width))
        lines.append("")
    separated = any(dict(event.details).get("boundary_protocol") == "p16_1r_b_v1" for event in snapshot)
    lines.extend(_flow_separated_note_v1(width) if separated else _flow_target_note_v1(width))
    if snapshot[0].sequence != 1:
        lines.extend(_flow_wrap_v1(
            f"EARLIER RECORDS NOT RETAINED: this view starts at record #{snapshot[0].sequence}. "
            "Session setup and earlier source/prediction details may be unavailable.", width,
        ))
    context = _FlowContextV1()
    previous_event: Nca8TraceEventV1 | None = None
    for _cycle_id, cycle_events in groupby(snapshot, key=lambda event: event.cycle_id):
        group = tuple(cycle_events)
        if previous_event is not None and group[0].sequence != previous_event.sequence + 1:
            lines.extend(_flow_wrap_v1(
                f"GAP: records #{previous_event.sequence + 1}-#{group[0].sequence - 1} are absent between these groups.", width,
            ))
            context.map_evidence = None
            context.source_maps.clear()
            context.settings.clear()
            context.initial_cycle_pending = False
        lines.extend(_flow_render_cycle_v1(group, context, width=width, include_details=include_details))
        previous_event = group[-1]
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
