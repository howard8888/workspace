#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First NCA8 body-sensory scaffold and current NavMap-state update path.

Phase 1C purpose
----------------
The shared environment currently supplies interpreted posture tokens rather
than realistic vestibular, proprioceptive, loading, and contact streams.  This
module treats ``posture:fallen`` and ``posture:standing`` as an explicit,
temporary perception scaffold.  It converts the scaffold into one canonical
SELF-ground geometry profile, evaluates that profile through the immutable
NavMap kernel, and updates the current :class:`nca8_maps.NavMapStateV1` owned by
this body-sensory circuit.

Missing posture evidence remains ``UNKNOWN``.  Simultaneous fallen and standing
evidence remains ``AMBIGUOUS``.  Neither case fabricates the opposite posture or
selects one canonical geometry profile.

Authority boundary
------------------
The body-sensory module owns sensory interpretation and its current NavMap
state.  It does not select Attention, form a WNM, arbitrate IPs/LPs, generate a
PNM, produce a task action, or revise durable NavMap content.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nca8_adapters import Nca8ObservationV1
from nca8_outcome_attention import RightingOutcomeAttentionV1
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1
from nca8_support_dynamics import SupportDynamicsTrackerV1, SupportDynamicsV1
from nca8_contracts import CircuitResultV1, CircuitTimingV1, LogicalAvailabilityV1
from nca8_maps import (
    Nca8MapLibraryV1,
    MotorSupportConfigurationV1,
    Nca8PostureStateV1,
    NavMapStateV1,
    PostureSupportEvidenceV1,
    SupportConfigurationV1,
    SupportObservationV1,
)

# Small validation helpers intentionally remain local to keep this vertical
# slice readable without a generic validation framework.
# pylint: disable=duplicate-code

__version__ = "0.5.0"
__all__ = [
    "NCA8_BODY_SENSORY_CIRCUIT_ID_V1",
    "Nca8BodySensoryApplicationV1",
    "Nca8BodySensoryModuleV1",
    "Nca8BodySensorySampleV1",
    "__version__",
]

NCA8_BODY_SENSORY_CIRCUIT_ID_V1 = "body_sensory"

_FALLEN_TOKEN = "posture:fallen"
_STANDING_TOKEN = "posture:standing"
_FALLEN_PROFILE = "lateral_ground_profile_v1"
_STANDING_PROFILE = "upright_support_profile_v1"
_MAX_PENDING_SAMPLES = 8


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_identifier(value: str, *, field_name: str, maximum: int = 160) -> str:
    """Return one non-empty bounded identifier."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character limit")
    return normalized


@dataclass(frozen=True, slots=True)
class Nca8BodySensorySampleV1:
    """One bounded interpretation of the explicit posture predicate scaffold."""

    result_id: str
    observation_number: int
    sampled_event_cycle: int
    posture: Nca8PostureStateV1
    geometry_profile_id: str | None
    scaffold_tokens: tuple[str, ...]
    reason: str
    support_observation: SupportObservationV1 | None = None
    support_observation_error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _bounded_identifier(self.result_id, field_name="result_id"))
        _positive_int(self.observation_number, field_name="observation_number")
        _positive_int(self.sampled_event_cycle, field_name="sampled_event_cycle")
        if self.observation_number != self.sampled_event_cycle:
            raise ValueError("Phase 1C requires Observation_n to be sampled in CognitiveCycle_n")
        if not isinstance(self.posture, Nca8PostureStateV1):
            raise TypeError("posture must be an Nca8PostureStateV1")
        if self.geometry_profile_id is not None:
            object.__setattr__(
                self,
                "geometry_profile_id",
                _bounded_identifier(self.geometry_profile_id, field_name="geometry_profile_id"),
            )
        tokens = tuple(sorted(_bounded_identifier(token, field_name="scaffold_token") for token in self.scaffold_tokens))
        if len(set(tokens)) != len(tokens):
            raise ValueError("scaffold_tokens must not contain duplicates")
        object.__setattr__(self, "scaffold_tokens", tokens)
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

        if self.support_observation is not None and not isinstance(self.support_observation, SupportObservationV1):
            raise TypeError("support_observation must be SupportObservationV1 or None")
        if self.support_observation_error is not None:
            _bounded_identifier(self.support_observation_error, field_name="support_observation_error")
            if self.support_observation is not None:
                raise ValueError("rejected support input cannot also carry an accepted packet")

        clear = self.posture in (Nca8PostureStateV1.FALLEN, Nca8PostureStateV1.STANDING)
        if clear != (self.geometry_profile_id is not None):
            raise ValueError("only clear posture scaffold input may select one geometry profile")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe scaffold interpretation."""
        out: dict[str, object] = {
            "result_id": self.result_id,
            "observation_number": self.observation_number,
            "sampled_event_cycle": self.sampled_event_cycle,
            "posture": self.posture.value,
            "geometry_profile_id": self.geometry_profile_id,
            "scaffold_tokens": list(self.scaffold_tokens),
            "reason": self.reason,
        }
        if self.support_observation is not None or self.support_observation_error is not None:
            out["support_observation"] = self.support_observation.as_dict() if self.support_observation is not None else None
            out["support_observation_error"] = self.support_observation_error
        return out


@dataclass(frozen=True, slots=True)
class Nca8BodySensoryApplicationV1:
    """One Phase-C body-sensory application and its owned current map state."""

    result_id: str
    observation_number: int
    sample: Nca8BodySensorySampleV1
    evidence: PostureSupportEvidenceV1
    map_state: NavMapStateV1
    update_kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _bounded_identifier(self.result_id, field_name="result_id"))
        _positive_int(self.observation_number, field_name="observation_number")
        if not isinstance(self.sample, Nca8BodySensorySampleV1):
            raise TypeError("sample must be an Nca8BodySensorySampleV1")
        if not isinstance(self.evidence, PostureSupportEvidenceV1):
            raise TypeError("evidence must be PostureSupportEvidenceV1")
        if not isinstance(self.map_state, NavMapStateV1):
            raise TypeError("map_state must be a NavMapStateV1")
        if self.result_id != self.sample.result_id:
            raise ValueError("application result_id must match the staged sensory sample")
        if self.observation_number != self.sample.observation_number:
            raise ValueError("application observation number must match the staged sensory sample")
        if self.map_state.posture is not self.evidence.posture:
            raise ValueError("current map state must preserve the interpreted posture evidence")
        if self.update_kind not in {"created", "refreshed", "changed"}:
            raise ValueError("update_kind must be created, refreshed, or changed")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic diagnostic representation."""
        return {
            "result_id": self.result_id,
            "observation_number": self.observation_number,
            "sample": self.sample.as_dict(),
            "evidence": self.evidence.as_dict(),
            "map_state": self.map_state.as_dict(),
            "update_kind": self.update_kind,
        }


class Nca8BodySensoryModuleV1:
    """Own the first body-sensory interpretation and current NavMap state.

    The module is polled during Phase A.  It publishes one immutable
    ``CircuitResultV1`` whose declared availability is ``THIS_CYCLE``.  During
    Phase C, only the scheduler-applied result can update the owned current map
    state. Durable map revision is intentionally unavailable here.

    P15-1E-A optionally stages an independent support packet alongside the A0
    scaffold. Its measured configuration remains a separate read-only companion.
    P16-1E-C optionally adds a local dynamics facet for source-linked WNM refresh;
    no measured value reaches BodyMap, Attention ranking, primitive selection,
    prediction or learning. Reset replaces this owner, watermark and history.
    """

    def __init__(
        self, map_library: Nca8MapLibraryV1, *, support_observation_enabled: bool = False, support_dynamics_enabled: bool = False,
    ) -> None:
        if not isinstance(map_library, Nca8MapLibraryV1):
            raise TypeError("map_library must be an Nca8MapLibraryV1")
        if not isinstance(support_observation_enabled, bool):
            raise TypeError("support_observation_enabled must be Boolean")
        if not isinstance(support_dynamics_enabled, bool):
            raise TypeError("support_dynamics_enabled must be Boolean")
        if support_dynamics_enabled and not support_observation_enabled:
            raise ValueError("support dynamics require the measured-observation consumer")
        self._support_dynamics = SupportDynamicsTrackerV1() if support_dynamics_enabled else None
        self._map_library = map_library
        self._pending_samples: dict[str, Nca8BodySensorySampleV1] = {}
        self._last_application: Nca8BodySensoryApplicationV1 | None = None
        self._support_observation_enabled = support_observation_enabled
        self._support_configuration: SupportConfigurationV1 | None = None
        self._last_support_observation: SupportObservationV1 | None = None
        self._motor_stream: MotorStreamRefV1 | None = None
        self._motor_reference: MotorFeedbackV1 | None = None
        self._motor_watermark: MotorFeedbackV1 | None = None
        self._motor_cutoff = -1
        self._motor_tick_seconds: float | None = None
        self._motor_context: tuple[str, str, int] | None = None
        self._outcome_attention: RightingOutcomeAttentionV1 | None = None


    @property
    def circuit_id(self) -> str:
        """Return the stable owner/source identity used by the scheduler."""
        return NCA8_BODY_SENSORY_CIRCUIT_ID_V1

    @property
    def map_library(self) -> Nca8MapLibraryV1:
        """Return the owned map library for read-only diagnostics and tests."""
        return self._map_library

    @property
    def current_state(self) -> NavMapStateV1 | None:
        """Return the current POSTURE-SUPPORT state, when one has been applied."""
        return self._map_library.current_state()

    @property
    def pending_sample_count(self) -> int:
        """Return the bounded number of staged, not-yet-applied samples."""
        return len(self._pending_samples)

    @property
    def last_application(self) -> Nca8BodySensoryApplicationV1 | None:
        """Return the latest immutable Phase-C sensory application."""
        return self._last_application

    @property
    def support_configuration(self) -> SupportConfigurationV1 | None:
        """Return the latest read-only companion, or None before use/when disabled."""
        return self._support_configuration

    @property
    def support_dynamics(self) -> SupportDynamicsV1 | None:
        """Return the optional immutable source facet; no call here updates or ages it."""
        return self._support_dynamics.current if self._support_dynamics is not None else None

    def _support_discrepancy(self, sample: Nca8BodySensorySampleV1) -> str | None:
        """Compare only contemporaneous pose evidence within the declared test profile.

        Angles <=15 degrees are near-horizontal; angles >=75 are near-upright.
        These conservative diagnostic bands are engineering choices, not action
        thresholds or biology. Intermediate poses remain non-diagnostic. Loading
        and contact never manufacture a posture. Different event times are not
        compared as though simultaneous.
        """
        measured = sample.support_observation
        if measured is None or measured.event_cycle != sample.sampled_event_cycle:
            return None
        if sample.posture is Nca8PostureStateV1.AMBIGUOUS:
            return "ambiguous_posture_scaffold"
        angle = measured.body_ground_angle_degrees
        if angle is None:
            return None
        if sample.posture is Nca8PostureStateV1.STANDING and angle <= 15.0:
            return "standing_scaffold_vs_near_horizontal_measurement"
        if sample.posture is Nca8PostureStateV1.FALLEN and angle >= 75.0:
            return "fallen_scaffold_vs_near_upright_measurement"
        return None

    def _apply_support_observation(
        self,
        sample: Nca8BodySensorySampleV1,
        result: CircuitResultV1,
        *,
        cycle_id: int,
    ) -> None:
        """Replace only the read-only measured register after owning Phase-C admission.

        One monotonic sample watermark prevents old identities becoming fresh
        again, including after missing/invalid input. Structurally valid ordered
        delayed, empty, or conflicting samples advance that watermark but do not
        refresh genuine support. Future-dated input is rejected against receipt
        time, not laundered by delayed application. When separately enabled,
        the P16-1E-C owner-local helper consumes this disposition to maintain a
        bounded history; rejected data never becomes a fresh trend endpoint.
        """
        measured = sample.support_observation
        previous = self._last_support_observation
        current = self._support_configuration
        supported = current.last_supported_event_cycle if current is not None else None
        discrepancy = self._support_discrepancy(sample)

        if sample.support_observation_error is not None:
            disposition, reason = "invalid", sample.support_observation_error
        elif measured is None:
            disposition, reason = "missing", "support_packet_absent"
        elif measured.event_cycle > sample.sampled_event_cycle:
            disposition, reason = "future", "support_event_after_receipt"
        elif previous is not None and measured.sample_id == previous.sample_id:
            if measured == previous:
                disposition, reason = "duplicate", "sample_already_seen"
            else:
                disposition, reason = "invalid", "sample_identity_reused_with_changed_content"
        elif previous is not None and (measured.sample_id < previous.sample_id or measured.event_cycle <= previous.event_cycle):
            disposition, reason = "out_of_order", "sample_identity_or_event_not_increasing"
        else:
            self._last_support_observation = measured
            if measured.event_cycle < cycle_id:
                disposition, reason = "delayed", "historical_measurement_not_current"
            elif not measured.has_measurements:
                disposition, reason = "empty", "all_measurements_missing"
            elif discrepancy is not None:
                disposition, reason = "conflict", "measurement_and_scaffold_disagree"
            else:
                disposition, reason = "current", "distinct_current_measurement"
                supported = measured.event_cycle

        self._support_configuration = SupportConfigurationV1(
            source_map_ref=self._map_library.posture_support_ref,
            observation=measured,
            scaffold_posture=sample.posture,
            available_cycle=result.timing.available_cycle,
            applied_cycle=cycle_id,
            disposition=disposition,
            reason=reason,
            discrepancy=discrepancy,
            last_supported_event_cycle=supported,
        )
        if self._support_dynamics is not None:
            self._support_dynamics.update(self._support_configuration)

    def poll_observation(
        self,
        observation: Nca8ObservationV1,
        *,
        cycle_id: int,
        observation_number: int,
    ) -> CircuitResultV1:
        """Interpret one filtered observation and publish a timed circuit result.

        A0 reads only explicitly allowed posture predicate tokens. The opt-in
        support packet is staged separately without changing that interpretation.
        No metadata, stage, milestone, policy, WorldGraph, or legacy BodyMap field
        participates. Current measured configuration cannot change before Phase C.
        """
        if not isinstance(observation, Nca8ObservationV1):
            raise TypeError("observation must be an Nca8ObservationV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        number = _positive_int(observation_number, field_name="observation_number")
        if number != cycle:
            raise ValueError("body-sensory polling requires Observation_n in CognitiveCycle_n")

        sample = self._sample_from_predicates(observation.predicates, cycle_id=cycle)
        if self._support_observation_enabled:
            sample = replace(
                sample,
                support_observation=observation.support_observation,
                support_observation_error=observation.support_observation_error,
            )
        if sample.result_id in self._pending_samples:
            raise ValueError(f"body-sensory result already pending: {sample.result_id!r}")
        if len(self._pending_samples) >= _MAX_PENDING_SAMPLES:
            raise OverflowError("bounded body-sensory sample capacity would be exceeded")
        self._pending_samples[sample.result_id] = sample

        supported_cycle = cycle if sample.posture is not Nca8PostureStateV1.UNKNOWN else None
        return CircuitResultV1.from_mapping(
            result_id=sample.result_id,
            source_circuit=self.circuit_id,
            source_sequence=number,
            timing=CircuitTimingV1.for_availability(
                sampled_event_cycle=cycle,
                availability=LogicalAvailabilityV1.THIS_CYCLE,
                last_supported_cycle=supported_cycle,
                expires_after_cycle=cycle,
            ),
            payload={
                "geometry_profile_id": sample.geometry_profile_id,
                "observation_number": number,
                "posture": sample.posture.value,
                "reason": sample.reason,
                "scaffold_source": "EnvObservation.predicates",
                "token_count": len(sample.scaffold_tokens),
            },
            event_latch=False,
        )

    def _sample_from_predicates(
        self,
        predicates: tuple[str, ...],
        *,
        cycle_id: int,
    ) -> Nca8BodySensorySampleV1:
        """Return an open-world interpretation of the posture scaffold tokens."""
        token_set = frozenset(predicates)
        fallen = _FALLEN_TOKEN in token_set
        standing = _STANDING_TOKEN in token_set
        retained = tuple(token for token in (_FALLEN_TOKEN, _STANDING_TOKEN) if token in token_set)

        if fallen and standing:
            posture = Nca8PostureStateV1.AMBIGUOUS
            profile_id = None
            reason = "conflicting_posture_predicate_scaffold"
        elif fallen:
            posture = Nca8PostureStateV1.FALLEN
            profile_id = _FALLEN_PROFILE
            reason = "fallen_posture_predicate_scaffold"
        elif standing:
            posture = Nca8PostureStateV1.STANDING
            profile_id = _STANDING_PROFILE
            reason = "standing_posture_predicate_scaffold"
        else:
            posture = Nca8PostureStateV1.UNKNOWN
            profile_id = None
            reason = "missing_posture_predicate_scaffold"

        return Nca8BodySensorySampleV1(
            result_id=f"{self.circuit_id}:{cycle_id}",
            observation_number=cycle_id,
            sampled_event_cycle=cycle_id,
            posture=posture,
            geometry_profile_id=profile_id,
            scaffold_tokens=retained,
            reason=reason,
        )

    def apply_result(
        self,
        result: CircuitResultV1,
        *,
        cycle_id: int,
    ) -> Nca8BodySensoryApplicationV1:
        """Apply one scheduler-authorized Phase-C result to the owned current state."""
        if not isinstance(result, CircuitResultV1):
            raise TypeError("result must be a CircuitResultV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if result.source_circuit != self.circuit_id:
            raise ValueError("body-sensory module can apply only its own circuit results")
        if result.timing.applied_cycle != cycle:
            raise ValueError("body-sensory result must be marked applied in the current Phase C")
        try:
            sample = self._pending_samples[result.result_id]
        except KeyError as exc:
            raise KeyError(f"no pending body-sensory sample for {result.result_id!r}") from exc

        payload_number = result.payload_dict().get("observation_number")
        if payload_number != sample.observation_number:
            raise RuntimeError("body-sensory result payload does not match its pending sample")

        existing = self._map_library.current_state()
        if sample.geometry_profile_id is not None:
            evidence = self._map_library.evaluate_profile(sample.geometry_profile_id)
            if evidence.posture is not sample.posture:
                raise RuntimeError("canonical geometry profile disagrees with the posture scaffold")
        else:
            evidence = self._map_library.open_world_evidence(sample.posture, reason=sample.reason)

        map_state = self._map_library.update_current_state(
            evidence,
            sampled_event_cycle=result.timing.sampled_event_cycle,
            available_cycle=result.timing.available_cycle,
            applied_cycle=cycle,
        )
        if existing is None:
            update_kind = "created"
        elif map_state.semantic_key() == existing.semantic_key():
            update_kind = "refreshed"
        else:
            update_kind = "changed"

        application = Nca8BodySensoryApplicationV1(
            result_id=result.result_id,
            observation_number=sample.observation_number,
            sample=sample,
            evidence=evidence,
            map_state=map_state,
            update_kind=update_kind,
        )
        if self._support_observation_enabled:
            self._apply_support_observation(sample, result, cycle_id=cycle)
        del self._pending_samples[result.result_id]
        self._last_application = application
        return application


    def apply_motor_evidence(
        self, evidence: FocalMotorEvidenceV1 | None, *, stream: MotorStreamRefV1,
        cycle_id: int, cutoff_tick: int, tick_seconds: float = 0.05,
    ) -> NavMapStateV1:
        """Apply H5 replay/live-admitted motor evidence to the existing source.

        This opt-in entry is never called by the retained A0 scheduler. H5's
        preview runner supplies the explicit eligibility boundary; H6 will wire
        that boundary to actual scheduled local feedback. Duplicate acquisitions
        may be reread while current, but generate no new rate. Missing or stale
        input breaks the pair reference without erasing the ordering watermark.
        Wrong generation, changed duplicate and reversed events fail before any
        source mutation. At most one pair plus one ordering watermark is retained.
        """
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if self._motor_stream is not None and stream != self._motor_stream:
            raise ValueError("motor stream/generation changed; create a fresh sensory owner")
        current = self.current_state
        if current is not None and cycle <= current.applied_cycle:
            raise ValueError("source application cycles must increase")
        # Construction validates type, finite time and focal/event correspondence.
        provisional = MotorSupportConfigurationV1(
            self.map_library.posture_support_ref, stream, evidence, None, cycle, cutoff_tick, tick_seconds,
        )
        if self._motor_tick_seconds is not None and tick_seconds != self._motor_tick_seconds:
            raise ValueError("source physical timebase cannot change within a generation")
        if cutoff_tick <= self._motor_cutoff:
            raise ValueError("motor focal cutoffs must increase")
        feedback, watermark = provisional.feedback, self._motor_watermark
        duplicate = feedback is not None and watermark is not None and feedback.sample_id == watermark.sample_id
        if feedback is not None and watermark is not None:
            if duplicate and feedback != watermark:
                raise ValueError("one motor sample cannot change content or time")
            if feedback.sample_id < watermark.sample_id or (not duplicate and feedback.event_tick <= watermark.event_tick):
                raise ValueError("motor source samples/events must not run backwards")
        reference = self._motor_reference
        comparable = (
            provisional.current and not duplicate and feedback is not None and reference is not None
            and 0 < feedback.event_tick - reference.event_tick <= 8
        )
        configuration = replace(provisional, previous=reference if comparable else None)
        result = self.map_library.update_motor_current_state(configuration)
        self._motor_stream = stream
        self._motor_cutoff = cutoff_tick
        self._motor_tick_seconds = tick_seconds
        self._motor_reference = feedback if provisional.current else None
        if feedback is not None:
            self._motor_watermark = feedback
        return result

    @property
    def outcome_attention(self) -> RightingOutcomeAttentionV1 | None:
        """Read the optional source-owned relevance/interpretation extension.

        The extension stores no separate sensory world. Its requests reference
        original task outcomes; interpretation may run only when this source is
        actually selected as WNM. Ordinary A0/H5/H6/1G-A construct no extension.
        """
        return self._outcome_attention

    def configure_outcome_attention(self, stream: MotorStreamRefV1) -> None:
        """Create the explicitly approved 1G-B source extension once, before sensing.

        A new generation needs a new sensory owner. This method performs no
        selection, comparison, interpretation, motor action or learned update.
        """
        if self._outcome_attention is not None or self._motor_stream is not None:
            raise RuntimeError("configure source relevance once before motor-source admission")
        self._outcome_attention = RightingOutcomeAttentionV1(stream, self.map_library.posture_support_ref)

    def retain_motor_context(self, task_id: str, context_id: str, *, cycle_id: int, expires_at_tick: int) -> None:
        """Accept one bounded selected-task continuation request, not source facts.

        A preview coordinator calls this only after Navigation selected an
        application on this source. The effect is a persistence-rank contribution
        to the next source bid. It changes no acquisition, geometry, timestamp or
        durable organization and conveys no motor permission. The task retains
        its own shorter/longer budget; this request cannot extend that budget.
        """
        task = _bounded_identifier(task_id, field_name="task_id", maximum=120)
        context = _bounded_identifier(context_id, field_name="context_id", maximum=120)
        current = self.current_state
        facet = current.motor_support if current is not None else None
        if facet is None or not facet.current or facet.applied_cycle != cycle_id:
            raise ValueError("continuation request requires this cycle's current source")
        if isinstance(expires_at_tick, bool) or not isinstance(expires_at_tick, int):
            raise TypeError("context expiry must be an integer")
        if not facet.cutoff_tick < expires_at_tick <= facet.cutoff_tick + 8:
            raise ValueError("source continuation must expire within eight lower ticks")
        self._motor_context = task, context, expires_at_tick

    def clear_motor_context(self) -> None:
        """Release the temporary continuation request without changing sensory data."""
        self._motor_context = None

    def motor_context_rank(self, task_id: str | None, context_id: str) -> int:
        """Return a bounded owner-mediated bid component under current evidence.

        The caller still sends the bid through Attention. Staleness, expiry or a
        changed task/context makes this contribution zero; no read renews it.
        """
        current = self.current_state
        facet = current.motor_support if current is not None else None
        request = self._motor_context
        if facet is None or not facet.current or request is None:
            return 0
        if request[:2] != (task_id, context_id) or facet.cutoff_tick >= request[2]:
            return 0
        return 20
