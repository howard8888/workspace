#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated Architecture-v09.3 runtime with first body/NavMap representation.

Phase 1A established a second state-isolated brain.  Phase 1B installed the
deterministic Phase-A-to-F commitment boundary.  Phase 1C now gives that cycle
its first meaningful cognitive content: an explicit posture predicate scaffold
is interpreted by an NCA8-owned body-sensory circuit, mapped to canonical
SELF-ground geometry, stored as one transient POSTURE-SUPPORT NavMap state, and
copied into a separate protected BodyMap state.

When current evidence says SELF is fallen with inadequate support, BodyMap
publishes one bounded POSTURE-SUPPORT candidate for future Attention.  There is
still no Attention selection, WNM, Navigation arbitration, primitive, PNM, task
action, SEC, WorldIndex, or durable learning.  The cycle therefore continues to
commit an honest ``Action_n:NO_ACTION`` after doing real representational work.

Numbering contract
------------------
Cycle ``n`` consumes ``Observation_n`` and commits ``Action_n``.  The physical
boundary later returns ``Observation_(n+1)``, which is held for Cycle ``n+1``.
The environment's own step counter remains separate low-level provenance and
cannot shift the user-facing cycle/observation/action numbering.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from nca8_adapters import (
    Nca8EnvironmentBridgeV1,
    Nca8EnvironmentStepV1,
    Nca8ObservationV1,
    create_environment_bridge_v1,
)
from nca8_body import BodyMapStateV1, Nca8BodyRuntimeV1, Nca8BodyUpdateV1, PostureSupportCandidateV1
from nca8_contracts import (
    CircuitResultV1,
    CircuitTimingV1,
    CycleCommitmentV1,
    CyclePhase,
    LogicalAvailabilityV1,
)
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1, SchedulerCycleSnapshotV1
from nca8_maps import DurableNavMapV1, Nca8MapLibraryV1, NavMapStateV1, create_posture_support_map_library_v1
from nca8_sensory import Nca8BodySensoryApplicationV1, Nca8BodySensoryModuleV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1

__version__ = "0.3.0"
__all__ = [
    "NCA8_NO_ACTION",
    "Nca8CognitiveCycleResultV1",
    "Nca8CognitiveRuntimeCycleV1",
    "Nca8CognitiveRuntimeV1",
    "Nca8EpisodeRunnerV1",
    "Nca8SessionConfigV1",
    "Nca8SessionStatusV1",
    "Nca8SessionV1",
    "__version__",
]

NCA8_NO_ACTION = "NO_ACTION"
_PHASE_1C_NULL_REASON = "phase_1c_has_body_representation_but_no_attention_or_navigation"
_OBSERVATION_INGRESS_CIRCUIT = "observation_ingress"

PhaseEHookV1: TypeAlias = Callable[[CycleCommitmentV1], None]


@dataclass(frozen=True, slots=True)
class Nca8SessionConfigV1:
    """Immutable engineering configuration for one isolated NCA8 session."""

    seed: int = 0
    scenario_name: str = "newborn_goat_first_hour"
    trace_capacity: int = 64
    staged_result_capacity: int = 64
    event_latch_capacity_per_source: int = 4

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not isinstance(self.scenario_name, str) or not self.scenario_name.strip():
            raise ValueError("scenario_name must not be blank")
        if len(self.scenario_name.strip()) > 120:
            raise ValueError("scenario_name exceeds the 120-character limit")
        for field_name in (
            "trace_capacity",
            "staged_result_capacity",
            "event_latch_capacity_per_source",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class Nca8SessionStatusV1:
    """Read-only lifecycle, scheduler, and first body-state status."""

    lifecycle_generation: int
    seed: int
    scenario_name: str
    environment_episode_index: int
    cognitive_cycles: int
    pending_observation_number: int
    pending_circuit_results: int
    latched_events: int
    posture_support_map_revision: int
    current_map_state_count: int
    current_posture: str | None
    current_support: str | None
    body_map_posture: str | None
    posture_support_candidate_id: str | None
    trace_retained: int
    trace_capacity: int

    @property
    def null_smoke_cycles(self) -> int:
        """Compatibility alias for the superseded Phase-1A status name."""
        return self.cognitive_cycles

    def as_dict(self) -> dict[str, int | str | None]:
        """Return a newly allocated scalar status dictionary."""
        return {
            "lifecycle_generation": self.lifecycle_generation,
            "seed": self.seed,
            "scenario_name": self.scenario_name,
            "environment_episode_index": self.environment_episode_index,
            "cognitive_cycles": self.cognitive_cycles,
            "pending_observation_number": self.pending_observation_number,
            "pending_circuit_results": self.pending_circuit_results,
            "latched_events": self.latched_events,
            "posture_support_map_revision": self.posture_support_map_revision,
            "current_map_state_count": self.current_map_state_count,
            "current_posture": self.current_posture,
            "current_support": self.current_support,
            "body_map_posture": self.body_map_posture,
            "posture_support_candidate_id": self.posture_support_candidate_id,
            "trace_retained": self.trace_retained,
            "trace_capacity": self.trace_capacity,
        }


@dataclass(frozen=True, slots=True)
class Nca8CognitiveRuntimeCycleV1:
    """Result returned by the cognitive runtime before episode buffering."""

    cycle_id: int
    observation_number: int
    action_number: int
    output: str
    commitment: CycleCommitmentV1
    scheduler: SchedulerCycleSnapshotV1
    posture_support_state: NavMapStateV1
    body_map_state: BodyMapStateV1
    posture_support_candidate: PostureSupportCandidateV1 | None

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe runtime-cycle snapshot."""
        return {
            "cycle_id": self.cycle_id,
            "observation_number": self.observation_number,
            "action_number": self.action_number,
            "output": self.output,
            "commitment": self.commitment.as_dict(),
            "scheduler": self.scheduler.as_dict(),
            "posture_support_state": self.posture_support_state.as_dict(),
            "body_map_state": self.body_map_state.as_dict(),
            "posture_support_candidate": (
                self.posture_support_candidate.as_dict()
                if self.posture_support_candidate is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class Nca8CognitiveCycleResultV1:
    """Complete result of one Phase-1C cognitive cycle and world boundary."""

    cycle_id: int
    observation_number: int
    action_number: int
    next_observation_number: int
    output: str
    environment_action: str | None
    reward: float
    done: bool
    environment_step: int
    commitment: CycleCommitmentV1
    scheduler: SchedulerCycleSnapshotV1
    posture_support_state: NavMapStateV1
    body_map_state: BodyMapStateV1
    posture_support_candidate: PostureSupportCandidateV1 | None

    @property
    def pnm_created(self) -> bool:
        """Return whether Phase E created a PNM; always false in Phase 1B."""
        return self.commitment.pnm_id is not None

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe complete-cycle snapshot."""
        return {
            "cycle_id": self.cycle_id,
            "observation_number": self.observation_number,
            "action_number": self.action_number,
            "next_observation_number": self.next_observation_number,
            "output": self.output,
            "environment_action": self.environment_action,
            "reward": self.reward,
            "done": self.done,
            "environment_step": self.environment_step,
            "pnm_created": self.pnm_created,
            "commitment": self.commitment.as_dict(),
            "scheduler": self.scheduler.as_dict(),
            "posture_support_state": self.posture_support_state.as_dict(),
            "body_map_state": self.body_map_state.as_dict(),
            "posture_support_candidate": (
                self.posture_support_candidate.as_dict()
                if self.posture_support_candidate is not None
                else None
            ),
        }


def _observation_trace_details_v1(
    observation: Nca8ObservationV1,
    *,
    observation_number: int,
) -> dict[str, str | int | float | bool | None]:
    """Return bounded observation details using NCA8's logical numbering."""
    details = observation.compact_summary()
    environment_step = details.pop("step_index", None)
    details["observation_number"] = observation_number
    details["environment_step"] = environment_step
    return details


def _observation_ingress_result_v1(
    observation: Nca8ObservationV1,
    *,
    cycle_id: int,
    observation_number: int,
) -> CircuitResultV1:
    """Create the sole Phase-1B owning result from the buffered observation.

    This is an engineering ingress result, not a sensory NavMap or BodyMap
    interpretation.  It carries only the observation identity and bounded
    counts required to prove staging, availability, freezing, and application.
    """
    payload = _observation_trace_details_v1(
        observation,
        observation_number=observation_number,
    )
    return CircuitResultV1.from_mapping(
        result_id=f"observation_ingress:{observation_number}",
        source_circuit=_OBSERVATION_INGRESS_CIRCUIT,
        source_sequence=observation_number,
        timing=CircuitTimingV1.for_availability(
            sampled_event_cycle=cycle_id,
            availability=LogicalAvailabilityV1.THIS_CYCLE,
            last_supported_cycle=cycle_id,
            expires_after_cycle=cycle_id,
        ),
        payload=payload,
        event_latch=False,
    )


class Nca8CognitiveRuntimeV1:
    """Execute all six phases and own the first body/NavMap state pathway.

    The runtime owns no environment.  It consumes exactly one already-filtered
    ``Observation_n`` and may invoke a Phase-E boundary hook supplied by the
    episode runner.  That hook can advance the private world but cannot return
    ``Observation_(n+1)`` into this runtime, preventing same-cycle processing of
    action consequences.  Body representation is updated only from results that
    crossed the scheduler's Phase-B freeze and were applied in Phase C.
    """

    def __init__(
        self,
        *,
        trace: Nca8TraceBufferV1,
        scheduler: Nca8DeterministicSchedulerV1,
        map_library: Nca8MapLibraryV1 | None = None,
        body_sensory: Nca8BodySensoryModuleV1 | None = None,
        body_runtime: Nca8BodyRuntimeV1 | None = None,
        poll_sources: Sequence[CircuitPollSourceV1] = (),
    ) -> None:
        if not isinstance(trace, Nca8TraceBufferV1):
            raise TypeError("trace must be an Nca8TraceBufferV1")
        if not isinstance(scheduler, Nca8DeterministicSchedulerV1):
            raise TypeError("scheduler must be an Nca8DeterministicSchedulerV1")
        if map_library is None:
            map_library = body_sensory.map_library if body_sensory is not None else create_posture_support_map_library_v1()
        if not isinstance(map_library, Nca8MapLibraryV1):
            raise TypeError("map_library must be an Nca8MapLibraryV1")
        if body_sensory is None:
            body_sensory = Nca8BodySensoryModuleV1(map_library)
        if not isinstance(body_sensory, Nca8BodySensoryModuleV1):
            raise TypeError("body_sensory must be an Nca8BodySensoryModuleV1")
        if body_sensory.map_library is not map_library:
            raise ValueError("body_sensory and cognitive runtime must share one owned map library")
        if body_runtime is None:
            body_runtime = Nca8BodyRuntimeV1()
        if not isinstance(body_runtime, Nca8BodyRuntimeV1):
            raise TypeError("body_runtime must be an Nca8BodyRuntimeV1")
        self._trace = trace
        self._scheduler = scheduler
        self._map_library = map_library
        self._body_sensory = body_sensory
        self._body_runtime = body_runtime
        self._poll_sources = tuple(poll_sources)
        self._cognitive_cycles = 0
        self._last_applied_observation_number: int | None = None
        self._last_commitment: CycleCommitmentV1 | None = None
        self._last_body_sensory_application: Nca8BodySensoryApplicationV1 | None = None
        self._last_body_update: Nca8BodyUpdateV1 | None = None

    @property
    def cognitive_cycles(self) -> int:
        """Return the number of fully completed Phase-A-to-F cycles."""
        return self._cognitive_cycles

    @property
    def last_applied_observation_number(self) -> int | None:
        """Return the latest observation actually applied during Phase C."""
        return self._last_applied_observation_number

    @property
    def last_commitment(self) -> CycleCommitmentV1 | None:
        """Return the immutable most recent Phase-E commitment."""
        return self._last_commitment

    @property
    def scheduler(self) -> Nca8DeterministicSchedulerV1:
        """Return the owned scheduler for read-only diagnostics and tests."""
        return self._scheduler

    @property
    def map_library(self) -> Nca8MapLibraryV1:
        """Return the owned durable/current map service for diagnostics and tests."""
        return self._map_library

    @property
    def body_sensory(self) -> Nca8BodySensoryModuleV1:
        """Return the owning body-sensory circuit."""
        return self._body_sensory

    @property
    def body_runtime(self) -> Nca8BodyRuntimeV1:
        """Return the protected BodyMap runtime."""
        return self._body_runtime

    @property
    def posture_support_state(self) -> NavMapStateV1 | None:
        """Return the currently owned POSTURE-SUPPORT NavMap state."""
        return self._body_sensory.current_state

    @property
    def body_map_state(self) -> BodyMapStateV1 | None:
        """Return the current protected BodyMap state."""
        return self._body_runtime.current_state

    @property
    def posture_support_candidate(self) -> PostureSupportCandidateV1 | None:
        """Return the current body-published candidate for future Attention."""
        return self._body_runtime.posture_support_candidate

    def run_cycle(
        self,
        observation: Nca8ObservationV1,
        *,
        observation_number: int,
        phase_e_hook: PhaseEHookV1 | None = None,
    ) -> Nca8CognitiveRuntimeCycleV1:
        """Run one complete deterministic cognitive cycle around ``Observation_n``."""
        cycle_id = self._cognitive_cycles + 1
        if observation_number != cycle_id:
            raise RuntimeError(
                "NCA8 numbering invariant violated: "
                f"CognitiveCycle_{cycle_id} cannot consume Observation_{observation_number}"
            )

        self._trace.append(
            "cycle",
            f"CognitiveCycle_{cycle_id} opened with Observation_{observation_number}",
            cycle_id=cycle_id,
            details=_observation_trace_details_v1(
                observation,
                observation_number=observation_number,
            ),
        )

        observation_result = _observation_ingress_result_v1(
            observation,
            cycle_id=cycle_id,
            observation_number=observation_number,
        )

        def poll_observation_ingress(requested_cycle: int) -> tuple[CircuitResultV1, ...]:
            if requested_cycle != cycle_id:
                raise RuntimeError("observation ingress was polled for the wrong cycle")
            return (observation_result,)

        def poll_body_sensory(requested_cycle: int) -> tuple[CircuitResultV1, ...]:
            if requested_cycle != cycle_id:
                raise RuntimeError("body-sensory circuit was polled for the wrong cycle")
            result = self._body_sensory.poll_observation(
                observation,
                cycle_id=cycle_id,
                observation_number=observation_number,
            )
            return (result,)

        poll_sources = (
            CircuitPollSourceV1(
                circuit_id=_OBSERVATION_INGRESS_CIRCUIT,
                poll=poll_observation_ingress,
            ),
            CircuitPollSourceV1(
                circuit_id=self._body_sensory.circuit_id,
                poll=poll_body_sensory,
            ),
            *self._poll_sources,
        )
        self._scheduler.phase_a_poll_and_stage(cycle_id, poll_sources, self._trace)
        frozen = self._scheduler.phase_b_freeze_eligible(cycle_id, self._trace)
        applied = self._scheduler.phase_c_apply_frozen(cycle_id, self._trace)
        sensory_application, body_update = self._apply_phase_c_results(
            cycle_id,
            observation_number,
            applied,
        )

        self._scheduler.enter_runtime_phase(cycle_id, CyclePhase.FOCAL_COMMITMENT)
        self._trace.append(
            "runtime",
            f"{CyclePhase.FOCAL_COMMITMENT.display_name} completed without Attention or a focal operation",
            cycle_id=cycle_id,
            phase=CyclePhase.FOCAL_COMMITMENT.name,
            details={
                "applied_result_count": len(applied),
                "attention_selection": None,
                "candidate_id": (
                    body_update.posture_support_candidate.candidate_id
                    if body_update.posture_support_candidate is not None
                    else None
                ),
                "focal_operation": None,
                "reason": _PHASE_1C_NULL_REASON,
            },
        )

        self._scheduler.enter_runtime_phase(cycle_id, CyclePhase.PROJECT_DISPATCH)
        commitment = CycleCommitmentV1(
            cycle_id=cycle_id,
            observation_number=observation_number,
            eligible_result_ids=tuple(result.result_id for result in frozen),
            applied_result_ids=tuple(result.result_id for result in applied),
            focal_operation_id=None,
            pnm_id=None,
            task_action=None,
        )
        self._trace.append(
            "runtime",
            f"{CyclePhase.PROJECT_DISPATCH.display_name} committed no PNM or task action",
            cycle_id=cycle_id,
            phase=CyclePhase.PROJECT_DISPATCH.name,
            details={
                "action_number": cycle_id,
                "focal_operation": None,
                "pnm": None,
                "task_action": None,
            },
        )
        if phase_e_hook is not None:
            phase_e_hook(commitment)

        scheduler_snapshot = self._scheduler.phase_f_finish(cycle_id, self._trace)
        self._cognitive_cycles = cycle_id
        self._last_commitment = commitment
        return Nca8CognitiveRuntimeCycleV1(
            cycle_id=cycle_id,
            observation_number=observation_number,
            action_number=cycle_id,
            output=NCA8_NO_ACTION,
            commitment=commitment,
            scheduler=scheduler_snapshot,
            posture_support_state=sensory_application.map_state,
            body_map_state=body_update.body_state,
            posture_support_candidate=body_update.posture_support_candidate,
        )

    def _apply_phase_c_results(
        self,
        cycle_id: int,
        observation_number: int,
        applied: Sequence[CircuitResultV1],
    ) -> tuple[Nca8BodySensoryApplicationV1, Nca8BodyUpdateV1]:
        """Apply observation identity, body sensory state, and BodyMap in Phase C."""
        ingress_results = [result for result in applied if result.source_circuit == _OBSERVATION_INGRESS_CIRCUIT]
        if len(ingress_results) != 1:
            raise RuntimeError("Phase C requires exactly one eligible observation-ingress result")
        ingress_payload = ingress_results[0].payload_dict()
        payload_number = ingress_payload.get("observation_number")
        if payload_number != observation_number:
            raise RuntimeError("applied observation-ingress result does not match the cycle input")
        self._last_applied_observation_number = observation_number
        self._trace.append(
            "runtime",
            f"Observation_{observation_number} became the applied Phase-C cycle input",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "observation_number": observation_number,
                "result_id": ingress_results[0].result_id,
            },
        )

        body_results = [result for result in applied if result.source_circuit == self._body_sensory.circuit_id]
        if len(body_results) != 1:
            raise RuntimeError("Phase C requires exactly one eligible body-sensory result")
        sensory_application = self._body_sensory.apply_result(body_results[0], cycle_id=cycle_id)
        map_state = sensory_application.map_state
        self._trace.append(
            "sensory",
            "posture predicate scaffold interpreted as current SELF-ground evidence",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "geometry_profile": sensory_application.sample.geometry_profile_id,
                "observation_number": observation_number,
                "posture": map_state.posture.value,
                "reason": sensory_application.sample.reason,
                "result_id": sensory_application.result_id,
                "scaffold_source": "EnvObservation.predicates",
            },
        )
        self._trace.append(
            "maps",
            "POSTURE-SUPPORT NavMapState updated without durable map revision",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "activation": map_state.activation,
                "change_count": map_state.configuration_change_count,
                "contact": map_state.contact.value,
                "durable_map": f"{map_state.source_map_ref.map_id}@r{map_state.source_map_ref.revision}",
                "posture": map_state.posture.value,
                "refresh_count": map_state.equivalent_refresh_count,
                "state_id": map_state.state_id,
                "support": map_state.support.value,
                "update_kind": sensory_application.update_kind,
            },
        )

        body_update = self._body_runtime.update_from_map_state(map_state)
        body_state = body_update.body_state
        self._trace.append(
            "body",
            "BodyMapState updated from current POSTURE-SUPPORT evidence",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "authority": body_state.authority,
                "candidate_event": body_update.candidate_event,
                "contact": body_state.contact.value,
                "is_wnm": False,
                "posture": body_state.posture.value,
                "state_id": body_state.state_id,
                "support": body_state.support.value,
                "update_kind": body_update.body_update_kind,
            },
        )
        candidate = body_update.posture_support_candidate
        if candidate is not None:
            self._trace.append(
                "body",
                "POSTURE-SUPPORT map-state candidate published for future Attention",
                cycle_id=cycle_id,
                phase=CyclePhase.UPDATE_OUTCOMES.name,
                details={
                    "attention_selected": False,
                    "authority": candidate.authority,
                    "candidate_id": candidate.candidate_id,
                    "posture": candidate.source_map_state.posture.value,
                    "reason": candidate.reason,
                    "source_state_id": candidate.source_map_state.state_id,
                    "support": candidate.source_map_state.support.value,
                },
            )
        else:
            self._trace.append(
                "body",
                "no POSTURE-SUPPORT candidate published",
                cycle_id=cycle_id,
                phase=CyclePhase.UPDATE_OUTCOMES.name,
                details={
                    "attention_selected": False,
                    "candidate_event": body_update.candidate_event,
                    "posture": body_state.posture.value,
                    "reason": "candidate_requires_current_fallen_and_inadequate_support",
                    "support": body_state.support.value,
                },
            )

        self._last_body_sensory_application = sensory_application
        self._last_body_update = body_update
        return sensory_application, body_update


class Nca8EpisodeRunnerV1:
    """Coordinate one private environment with one NCA8 cognitive runtime.

    ``Observation_(n+1)`` may be produced at the Phase-E physical boundary, but
    the callback stores it only in this episode runner.  The cognitive runtime
    receives no reference to that new observation.  It becomes an input only
    when the next explicit call begins ``CognitiveCycle_(n+1)``.
    """

    def __init__(
        self,
        *,
        environment_bridge: Nca8EnvironmentBridgeV1,
        cognitive_runtime: Nca8CognitiveRuntimeV1,
        trace: Nca8TraceBufferV1,
        initial_observation: Nca8ObservationV1,
        initial_observation_number: int = 1,
    ) -> None:
        self._environment_bridge = environment_bridge
        self._cognitive_runtime = cognitive_runtime
        self._trace = trace
        self._pending_observation = initial_observation
        self._pending_observation_number = initial_observation_number

    @property
    def pending_observation(self) -> Nca8ObservationV1:
        """Return the immutable observation waiting for the next cycle."""
        return self._pending_observation

    @property
    def pending_observation_number(self) -> int:
        """Return the logical number of the observation waiting for processing."""
        return self._pending_observation_number

    def run_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Run one cycle, advance the world with no task token, and buffer the next observation."""
        current_observation = self._pending_observation
        observation_number = self._pending_observation_number
        boundary_result: Nca8EnvironmentStepV1 | None = None

        def phase_e_boundary(commitment: CycleCommitmentV1) -> None:
            nonlocal boundary_result
            if not commitment.is_null:
                raise RuntimeError("Phase 1B can dispatch only a null commitment")
            step_result = self._environment_bridge.apply_no_action()
            boundary_result = step_result
            self._trace.append(
                "environment",
                f"Action_{commitment.cycle_id}:{NCA8_NO_ACTION} advanced the private environment with no task token",
                cycle_id=commitment.cycle_id,
                phase=CyclePhase.PROJECT_DISPATCH.name,
                details={
                    "action": None,
                    "action_number": commitment.cycle_id,
                    "done": step_result.done,
                    "environment_step": step_result.step_index,
                    "reward": step_result.reward,
                },
            )

        runtime_result = self._cognitive_runtime.run_cycle(
            current_observation,
            observation_number=observation_number,
            phase_e_hook=phase_e_boundary,
        )
        if boundary_result is None:
            raise RuntimeError("Phase E completed without advancing the private environment boundary")

        next_observation_number = runtime_result.cycle_id + 1
        self._pending_observation = boundary_result.observation
        self._pending_observation_number = next_observation_number
        next_details = _observation_trace_details_v1(
            boundary_result.observation,
            observation_number=next_observation_number,
        )
        next_details["next_cycle_id"] = next_observation_number
        self._trace.append(
            "firewall",
            f"Observation_{next_observation_number} buffered for CognitiveCycle_{next_observation_number} without same-cycle processing",
            cycle_id=runtime_result.cycle_id,
            details=next_details,
        )
        self._trace.append(
            "cycle",
            f"CognitiveCycle_{runtime_result.cycle_id} closed",
            cycle_id=runtime_result.cycle_id,
            details={
                "input": f"Observation_{runtime_result.observation_number}",
                "next_input": f"Observation_{next_observation_number}",
                "output": f"Action_{runtime_result.action_number}:{NCA8_NO_ACTION}",
            },
        )

        return Nca8CognitiveCycleResultV1(
            cycle_id=runtime_result.cycle_id,
            observation_number=runtime_result.observation_number,
            action_number=runtime_result.action_number,
            next_observation_number=next_observation_number,
            output=runtime_result.output,
            environment_action=None,
            reward=boundary_result.reward,
            done=boundary_result.done,
            environment_step=boundary_result.step_index,
            commitment=runtime_result.commitment,
            scheduler=runtime_result.scheduler,
            posture_support_state=runtime_result.posture_support_state,
            body_map_state=runtime_result.body_map_state,
            posture_support_candidate=runtime_result.posture_support_candidate,
        )


class Nca8SessionV1:
    """Own every mutable object for one isolated Architecture-v09.3 experiment."""

    def __init__(self, config: Nca8SessionConfigV1 | None = None) -> None:
        self._config = config or Nca8SessionConfigV1()
        self._lifecycle_generation = 0
        self._environment_bridge: Nca8EnvironmentBridgeV1
        self._rng: random.Random
        self._trace: Nca8TraceBufferV1
        self._scheduler: Nca8DeterministicSchedulerV1
        self._map_library: Nca8MapLibraryV1
        self._body_sensory: Nca8BodySensoryModuleV1
        self._body_runtime: Nca8BodyRuntimeV1
        self._cognitive_runtime: Nca8CognitiveRuntimeV1
        self._episode_runner: Nca8EpisodeRunnerV1
        self.reset()

    @property
    def config(self) -> Nca8SessionConfigV1:
        """Return the immutable session configuration."""
        return self._config

    @property
    def pending_observation(self) -> Nca8ObservationV1:
        """Return the observation buffered for the next cognitive cycle."""
        return self._episode_runner.pending_observation

    @property
    def durable_posture_support_map(self) -> DurableNavMapV1:
        """Return the immutable developmental POSTURE-SUPPORT NavMap revision."""
        return self._map_library.durable_map()

    @property
    def posture_support_state(self) -> NavMapStateV1 | None:
        """Return the current transient POSTURE-SUPPORT NavMap state."""
        return self._body_sensory.current_state

    @property
    def body_map_state(self) -> BodyMapStateV1 | None:
        """Return the current protected BodyMap state."""
        return self._body_runtime.current_state

    @property
    def posture_support_candidate(self) -> PostureSupportCandidateV1 | None:
        """Return the body-published candidate for future Attention."""
        return self._body_runtime.posture_support_candidate

    def reset(self) -> Nca8SessionStatusV1:
        """Atomically replace all NCA8 mutable state with a fresh isolated episode."""
        new_rng = random.Random(self._config.seed)
        new_bridge = create_environment_bridge_v1(scenario_name=self._config.scenario_name)
        reset_result = new_bridge.reset(seed=self._config.seed)
        new_trace = Nca8TraceBufferV1(capacity=self._config.trace_capacity)
        new_scheduler = Nca8DeterministicSchedulerV1(
            staged_result_capacity=self._config.staged_result_capacity,
            event_latch_capacity_per_source=self._config.event_latch_capacity_per_source,
        )
        new_map_library = create_posture_support_map_library_v1()
        new_body_sensory = Nca8BodySensoryModuleV1(new_map_library)
        new_body_runtime = Nca8BodyRuntimeV1()
        new_runtime = Nca8CognitiveRuntimeV1(
            trace=new_trace,
            scheduler=new_scheduler,
            map_library=new_map_library,
            body_sensory=new_body_sensory,
            body_runtime=new_body_runtime,
        )
        first_observation_number = 1
        new_episode_runner = Nca8EpisodeRunnerV1(
            environment_bridge=new_bridge,
            cognitive_runtime=new_runtime,
            trace=new_trace,
            initial_observation=reset_result.observation,
            initial_observation_number=first_observation_number,
        )
        next_generation = self._lifecycle_generation + 1

        new_trace.append(
            "session",
            "isolated Phase-1C session reset",
            details={
                "durable_posture_support_map": (
                    f"{new_map_library.posture_support_ref.map_id}@r"
                    f"{new_map_library.posture_support_ref.revision}"
                ),
                "episode_index": reset_result.episode_index,
                "generation": next_generation,
                "pending_observation_number": first_observation_number,
                "seed": self._config.seed,
            },
        )
        new_trace.append(
            "firewall",
            f"Observation_{first_observation_number} buffered as the first cognitive-cycle input",
            details=_observation_trace_details_v1(
                reset_result.observation,
                observation_number=first_observation_number,
            ),
        )

        self._rng = new_rng
        self._environment_bridge = new_bridge
        self._trace = new_trace
        self._scheduler = new_scheduler
        self._map_library = new_map_library
        self._body_sensory = new_body_sensory
        self._body_runtime = new_body_runtime
        self._cognitive_runtime = new_runtime
        self._episode_runner = new_episode_runner
        self._lifecycle_generation = next_generation
        return self.status()

    def status(self) -> Nca8SessionStatusV1:
        """Return a read-only status snapshot without exposing owned objects."""
        pending_results = self._scheduler.pending_results_snapshot()
        latched_results = self._scheduler.latched_results_snapshot()
        map_state = self._body_sensory.current_state
        body_state = self._body_runtime.current_state
        candidate = self._body_runtime.posture_support_candidate
        return Nca8SessionStatusV1(
            lifecycle_generation=self._lifecycle_generation,
            seed=self._config.seed,
            scenario_name=self._config.scenario_name,
            environment_episode_index=self._environment_bridge.episode_index,
            cognitive_cycles=self._cognitive_runtime.cognitive_cycles,
            pending_observation_number=self._episode_runner.pending_observation_number,
            pending_circuit_results=len(pending_results),
            latched_events=len(latched_results),
            posture_support_map_revision=self._map_library.posture_support_ref.revision,
            current_map_state_count=self._map_library.current_state_count,
            current_posture=map_state.posture.value if map_state is not None else None,
            current_support=map_state.support.value if map_state is not None else None,
            body_map_posture=body_state.posture.value if body_state is not None else None,
            posture_support_candidate_id=candidate.candidate_id if candidate is not None else None,
            trace_retained=self._trace.retained_count,
            trace_capacity=self._trace.capacity,
        )

    def run_cognitive_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Execute one full Phase-A-to-F cycle and buffer the next observation."""
        return self._episode_runner.run_cycle()

    def run_null_smoke_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Compatibility alias for the Phase-1A method; use ``run_cognitive_cycle``."""
        return self.run_cognitive_cycle()

    def trace_snapshot(self) -> tuple[Nca8TraceEventV1, ...]:
        """Return immutable retained trace events in causal order."""
        return self._trace.snapshot()

    def trace_lines(self) -> tuple[str, ...]:
        """Return deterministic human-readable trace lines."""
        return self._trace.render_lines()

    def trace_json_safe(self) -> list[dict[str, object]]:
        """Return a newly allocated JSON-safe trace export."""
        return self._trace.as_json_safe()

    def trace_canonical_bytes(self) -> bytes:
        """Return byte-stable canonical trace JSON for deterministic replay tests."""
        return self._trace.as_canonical_json_bytes()
