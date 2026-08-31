#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated Architecture-v09.3 runtime through Gate-A StandUp.

Phase 1A established a second state-isolated brain. Phase 1B installed the
Phase-A-to-F deterministic commitment boundary. Phase 1C added an NCA8-owned
current POSTURE-SUPPORT NavMap state and protected BodyMap state. Phase 1D now
completes the first vertical cognitive path:

``Observation_n -> body state -> Attention -> WNM -> Navigation -> StandUp IP
-> PNM -> BodyMap/action envelope -> Action_n -> Observation_(n+1) -> outcome``.

The implementation remains narrow. Attention selects a map-state source but
never names StandUp. Navigation evaluates and applies the primitive. Prediction
creates the PNM before dispatch. BodyMap may authorize or reject the task-to-body
handoff. The environment adapter alone translates internal ``STAND_UP`` to the
compatibility token ``policy:stand_up``. Later current body evidence, never the
command itself, determines success or failure.

Numbering contract
------------------
CognitiveCycle ``n`` consumes ``Observation_n`` and commits ``Action_n``.
The resulting ``Observation_(n+1)`` is buffered and cannot be processed until
CognitiveCycle ``n+1``.
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
from nca8_body import (
    BodyActionHandoffV1,
    BodyMapStateV1,
    Nca8BodyRuntimeV1,
    Nca8BodyUpdateV1,
    PostureSupportCandidateV1,
)
from nca8_contracts import (
    CircuitResultV1,
    CircuitTimingV1,
    CycleCommitmentV1,
    CyclePhase,
    LogicalAvailabilityV1,
)
from nca8_executive import (
    AttentionBidV1,
    AttentionRuntimeV1,
    AttentionSelectionV1,
    NavigationDecisionV1,
    NavigationRuntimeV1,
    WorkingNavMapStateV1,
)
from nca8_maps import (
    DurableNavMapV1,
    Nca8MapLibraryV1,
    Nca8PostureStateV1,
    Nca8SupportStateV1,
    NavMapStateV1,
    create_posture_support_map_library_v1,
)
from nca8_prediction import (
    Nca8PredictionRuntimeV1,
    PredictionOutcomeStatusV1,
    PredictionOutcomeV1,
    ProjectedNavMapV1,
)
from nca8_primitives import (
    PrimitiveRuntimeV1,
    TaskActionV1,
    create_gate_a_primitives_v1,
)
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1, SchedulerCycleSnapshotV1
from nca8_sensory import Nca8BodySensoryApplicationV1, Nca8BodySensoryModuleV1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1

__version__ = "0.4.0"
__all__ = [
    "NCA8_NO_ACTION",
    "Nca8CognitiveCycleResultV1",
    "Nca8CognitiveRuntimeCycleV1",
    "Nca8CognitiveRuntimeV1",
    "Nca8EpisodeRunnerV1",
    "Nca8GateASummaryV1",
    "Nca8PhaseEDispatchV1",
    "Nca8SessionConfigV1",
    "Nca8SessionStatusV1",
    "Nca8SessionV1",
    "__version__",
]

NCA8_NO_ACTION = "NO_ACTION"
_OBSERVATION_INGRESS_CIRCUIT = "observation_ingress"

PhaseEHookV1: TypeAlias = Callable[["Nca8PhaseEDispatchV1"], None]


@dataclass(frozen=True, slots=True)
class Nca8SessionConfigV1:
    """Immutable engineering configuration for one isolated NCA8 session."""

    seed: int = 0
    scenario_name: str = "newborn_goat_first_hour_benchmark_hard"
    trace_capacity: int = 256
    staged_result_capacity: int = 64
    event_latch_capacity_per_source: int = 4
    attention_enabled: bool = True
    navigation_enabled: bool = True
    body_action_handoff_enabled: bool = True
    gate_a_max_cycles: int = 10

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
            "gate_a_max_cycles",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        for field_name in ("attention_enabled", "navigation_enabled", "body_action_handoff_enabled"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be Boolean")


@dataclass(frozen=True, slots=True)
class Nca8SessionStatusV1:
    """Read-only lifecycle, scheduler, representation, and Gate-A status."""

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
    attention_disposition: str | None
    wnm_id: str | None
    selected_primitive_id: str | None
    current_pnm_id: str | None
    last_prediction_outcome: str | None
    last_task_action: str | None
    current_envelope_status: str | None
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
            "attention_disposition": self.attention_disposition,
            "wnm_id": self.wnm_id,
            "selected_primitive_id": self.selected_primitive_id,
            "current_pnm_id": self.current_pnm_id,
            "last_prediction_outcome": self.last_prediction_outcome,
            "last_task_action": self.last_task_action,
            "current_envelope_status": self.current_envelope_status,
            "trace_retained": self.trace_retained,
            "trace_capacity": self.trace_capacity,
        }


@dataclass(frozen=True, slots=True)
class Nca8PhaseEDispatchV1:
    """One immutable post-PNM dispatch package passed to the episode runner."""

    commitment: CycleCommitmentV1
    task_action: TaskActionV1 | None
    pnm: ProjectedNavMapV1 | None
    body_handoff: BodyActionHandoffV1 | None

    @property
    def authorized_task_action(self) -> TaskActionV1 | None:
        """Return the task action only when BodyMap authorized its handoff."""
        if self.body_handoff is None or not self.body_handoff.authorized:
            return None
        return self.task_action

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dispatch snapshot."""
        return {
            "commitment": self.commitment.as_dict(),
            "task_action": self.task_action.as_dict() if self.task_action is not None else None,
            "pnm": self.pnm.as_dict() if self.pnm is not None else None,
            "body_handoff": self.body_handoff.as_dict() if self.body_handoff is not None else None,
            "authorized_task_action": (
                self.authorized_task_action.as_dict() if self.authorized_task_action is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class Nca8CognitiveRuntimeCycleV1:
    """Result returned by cognition before Observation_(n+1) is buffered."""

    cycle_id: int
    observation_number: int
    action_number: int
    output: str
    commitment: CycleCommitmentV1
    scheduler: SchedulerCycleSnapshotV1
    posture_support_state: NavMapStateV1
    body_map_state: BodyMapStateV1
    posture_support_candidate: PostureSupportCandidateV1 | None
    attention_bid: AttentionBidV1 | None
    attention_selection: AttentionSelectionV1
    wnm: WorkingNavMapStateV1 | None
    navigation: NavigationDecisionV1
    pnm: ProjectedNavMapV1 | None
    body_handoff: BodyActionHandoffV1 | None
    prediction_outcomes: tuple[PredictionOutcomeV1, ...]
    phase_e_dispatch: Nca8PhaseEDispatchV1

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
                self.posture_support_candidate.as_dict() if self.posture_support_candidate is not None else None
            ),
            "attention_bid": self.attention_bid.as_dict() if self.attention_bid is not None else None,
            "attention_selection": self.attention_selection.as_dict(),
            "wnm": self.wnm.as_dict() if self.wnm is not None else None,
            "navigation": self.navigation.as_dict(),
            "pnm": self.pnm.as_dict() if self.pnm is not None else None,
            "body_handoff": self.body_handoff.as_dict() if self.body_handoff is not None else None,
            "prediction_outcomes": [outcome.as_dict() for outcome in self.prediction_outcomes],
            "phase_e_dispatch": self.phase_e_dispatch.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class Nca8CognitiveCycleResultV1:
    """Complete result of one Gate-A cognitive cycle and physical boundary."""

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
    attention_bid: AttentionBidV1 | None
    attention_selection: AttentionSelectionV1
    wnm: WorkingNavMapStateV1 | None
    navigation: NavigationDecisionV1
    pnm: ProjectedNavMapV1 | None
    body_handoff: BodyActionHandoffV1 | None
    prediction_outcomes: tuple[PredictionOutcomeV1, ...]

    @property
    def pnm_created(self) -> bool:
        """Return whether Phase E created a PNM for this cycle."""
        return self.pnm is not None

    @property
    def task_action(self) -> str | None:
        """Return the internal task-action kind committed this cycle."""
        return self.commitment.task_action

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
                self.posture_support_candidate.as_dict() if self.posture_support_candidate is not None else None
            ),
            "attention_bid": self.attention_bid.as_dict() if self.attention_bid is not None else None,
            "attention_selection": self.attention_selection.as_dict(),
            "wnm": self.wnm.as_dict() if self.wnm is not None else None,
            "navigation": self.navigation.as_dict(),
            "pnm": self.pnm.as_dict() if self.pnm is not None else None,
            "body_handoff": self.body_handoff.as_dict() if self.body_handoff is not None else None,
            "prediction_outcomes": [outcome.as_dict() for outcome in self.prediction_outcomes],
        }


@dataclass(frozen=True, slots=True)
class Nca8GateASummaryV1:
    """Bounded observable result of one fresh StandUp Gate-A run."""

    achieved_standing: bool
    cycles_run: int
    stand_up_actions: int
    final_posture: str | None
    final_support: str | None
    successful_application_id: str | None
    last_outcome_status: str | None
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe Gate-A summary."""
        return {
            "achieved_standing": self.achieved_standing,
            "cycles_run": self.cycles_run,
            "stand_up_actions": self.stand_up_actions,
            "final_posture": self.final_posture,
            "final_support": self.final_support,
            "successful_application_id": self.successful_application_id,
            "last_outcome_status": self.last_outcome_status,
            "reason": self.reason,
        }


def _observation_trace_details_v1(
    observation: Nca8ObservationV1,
    *,
    observation_number: int,
) -> dict[str, str | int | float | bool | None]:
    """Return bounded observation details using NCA8 logical numbering."""
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
    """Create one timed engineering ingress result for the filtered observation."""
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
        payload=_observation_trace_details_v1(observation, observation_number=observation_number),
        event_latch=False,
    )


class Nca8CognitiveRuntimeV1:
    """Own Phase C representation, Phase D focal cognition, and Phase E commitment."""

    def __init__(
        self,
        *,
        trace: Nca8TraceBufferV1,
        scheduler: Nca8DeterministicSchedulerV1,
        map_library: Nca8MapLibraryV1 | None = None,
        body_sensory: Nca8BodySensoryModuleV1 | None = None,
        body_runtime: Nca8BodyRuntimeV1 | None = None,
        attention: AttentionRuntimeV1 | None = None,
        navigation: NavigationRuntimeV1 | None = None,
        prediction: Nca8PredictionRuntimeV1 | None = None,
        primitives: Sequence[PrimitiveRuntimeV1] | None = None,
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
        body_sensory = body_sensory or Nca8BodySensoryModuleV1(map_library)
        if body_sensory.map_library is not map_library:
            raise ValueError("body_sensory and runtime must share one owned map library")
        self._trace = trace
        self._scheduler = scheduler
        self._map_library = map_library
        self._body_sensory = body_sensory
        self._body_runtime = body_runtime or Nca8BodyRuntimeV1()
        self._attention = attention or AttentionRuntimeV1()
        self._navigation = navigation or NavigationRuntimeV1()
        self._prediction = prediction or Nca8PredictionRuntimeV1()
        self._primitives = tuple(primitives) if primitives is not None else create_gate_a_primitives_v1()
        self._poll_sources = tuple(poll_sources)
        self._cognitive_cycles = 0
        self._last_applied_observation_number: int | None = None
        self._last_commitment: CycleCommitmentV1 | None = None
        self._last_prediction_outcomes: tuple[PredictionOutcomeV1, ...] = ()

    @property
    def cognitive_cycles(self) -> int:
        """Return the number of fully completed Phase-A-to-F cycles."""
        return self._cognitive_cycles

    @property
    def last_applied_observation_number(self) -> int | None:
        """Return the latest observation applied during Phase C."""
        return self._last_applied_observation_number

    @property
    def last_commitment(self) -> CycleCommitmentV1 | None:
        """Return the immutable most recent Phase-E commitment."""
        return self._last_commitment

    @property
    def scheduler(self) -> Nca8DeterministicSchedulerV1:
        """Return the owned deterministic scheduler."""
        return self._scheduler

    @property
    def map_library(self) -> Nca8MapLibraryV1:
        """Return the owned durable/current map service."""
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
    def attention(self) -> AttentionRuntimeV1:
        """Return the distinct Attention service."""
        return self._attention

    @property
    def navigation(self) -> NavigationRuntimeV1:
        """Return the distinct Navigation service."""
        return self._navigation

    @property
    def prediction(self) -> Nca8PredictionRuntimeV1:
        """Return the current/pending PNM service."""
        return self._prediction

    @property
    def primitives(self) -> tuple[PrimitiveRuntimeV1, ...]:
        """Return the explicit Gate-A primitive repertoire."""
        return self._primitives

    @property
    def posture_support_state(self) -> NavMapStateV1 | None:
        """Return the current POSTURE-SUPPORT state."""
        return self._body_sensory.current_state

    @property
    def body_map_state(self) -> BodyMapStateV1 | None:
        """Return the current protected BodyMap state."""
        return self._body_runtime.current_state

    @property
    def posture_support_candidate(self) -> PostureSupportCandidateV1 | None:
        """Return the current BodyMap-derived Attention candidate."""
        return self._body_runtime.posture_support_candidate

    @property
    def last_prediction_outcomes(self) -> tuple[PredictionOutcomeV1, ...]:
        """Return the outcomes evaluated in the most recent Phase C."""
        return self._last_prediction_outcomes

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
            details=_observation_trace_details_v1(observation, observation_number=observation_number),
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
            return (
                self._body_sensory.poll_observation(
                    observation,
                    cycle_id=cycle_id,
                    observation_number=observation_number,
                ),
            )

        poll_sources = (
            CircuitPollSourceV1(_OBSERVATION_INGRESS_CIRCUIT, poll_observation_ingress),
            CircuitPollSourceV1(self._body_sensory.circuit_id, poll_body_sensory),
            *self._poll_sources,
        )
        self._scheduler.phase_a_poll_and_stage(cycle_id, poll_sources, self._trace)
        frozen = self._scheduler.phase_b_freeze_eligible(cycle_id, self._trace)
        applied = self._scheduler.phase_c_apply_frozen(cycle_id, self._trace)
        sensory_application, body_update, outcomes = self._apply_phase_c_results(
            cycle_id,
            observation_number,
            applied,
        )

        self._scheduler.enter_runtime_phase(cycle_id, CyclePhase.FOCAL_COMMITMENT)
        candidate = body_update.posture_support_candidate
        bid = self._attention.build_bid(candidate, cycle_id=cycle_id) if candidate is not None else None
        if bid is not None:
            self._trace.append(
                "attention",
                "POSTURE-SUPPORT map-state candidate submitted as an Attention bid",
                cycle_id=cycle_id,
                phase=CyclePhase.FOCAL_COMMITMENT.name,
                details={
                    "bid_id": bid.bid_id,
                    "candidate_id": bid.candidate_id,
                    "primitive_id": None,
                    "protected_safety_rank": bid.protected_safety_rank,
                    "new_task_need_rank": bid.new_task_need_rank,
                    "source_state_id": bid.source_map_state.state_id,
                },
            )
        selection = self._attention.select(
            (bid,) if bid is not None else (),
            current_wnm=self._navigation.current_wnm,
            cycle_id=cycle_id,
        )
        attention_message = {
            "maintain": "Attention maintained the primary source map state",
            "switch": "Attention switched the primary source map state",
            "release": "Attention released the primary source map state",
        }[selection.disposition.value]
        self._trace.append(
            "attention",
            attention_message,
            cycle_id=cycle_id,
            phase=CyclePhase.FOCAL_COMMITMENT.name,
            details={
                "disposition": selection.disposition.value,
                "primitive_selected": None,
                "selection_id": selection.selection_id,
                "source_state_id": (
                    selection.selected_source_state.state_id if selection.selected_source_state is not None else None
                ),
            },
        )
        wnm = self._navigation.update_wnm(selection)
        if wnm is not None:
            self._trace.append(
                "wnm",
                "source-linked WNM constructed or refreshed from Attention's selected state",
                cycle_id=cycle_id,
                phase=CyclePhase.FOCAL_COMMITMENT.name,
                details={
                    "context_ref_count": len(wnm.context_refs),
                    "focus_age": wnm.focus_age,
                    "source_map": (
                        f"{wnm.primary_source_state.source_map_ref.map_id}@r"
                        f"{wnm.primary_source_state.source_map_ref.revision}"
                    ),
                    "source_state_id": wnm.primary_source_state.state_id,
                    "working_id": wnm.working_id,
                    "working_relations": ",".join(wnm.working_relations),
                },
            )
        else:
            self._trace.append(
                "wnm",
                "no WNM exists because Attention released or selected no source",
                cycle_id=cycle_id,
                phase=CyclePhase.FOCAL_COMMITMENT.name,
                details={"working_id": None},
            )

        navigation = self._navigation.commit(wnm, self._primitives, cycle_id=cycle_id)
        for record in navigation.applicability_records:
            self._trace.append(
                "navigation",
                "primitive applicability evaluated from the WNM",
                cycle_id=cycle_id,
                phase=CyclePhase.FOCAL_COMMITMENT.name,
                details={
                    "eligible": record.eligible,
                    "fit_rank": record.fit_rank,
                    "primitive_id": record.primitive_id,
                    "safety_rank": record.safety_rank,
                    "vetoes": ",".join(record.vetoes) if record.vetoes else "(none)",
                },
            )
        application = navigation.application
        self._trace.append(
            "navigation",
            "Navigation commitment completed",
            cycle_id=cycle_id,
            phase=CyclePhase.FOCAL_COMMITMENT.name,
            details={
                "application_id": application.application_id if application is not None else None,
                "reason": navigation.reason,
                "selected_primitive_id": navigation.selected_primitive_id,
                "wnm_id": wnm.working_id if wnm is not None else None,
            },
        )
        self._trace.append(
            "runtime",
            f"{CyclePhase.FOCAL_COMMITMENT.display_name} completed",
            cycle_id=cycle_id,
            phase=CyclePhase.FOCAL_COMMITMENT.name,
            details={
                "attention_disposition": selection.disposition.value,
                "focal_operation": application.application_id if application is not None else None,
                "selected_primitive": navigation.selected_primitive_id,
                "wnm": wnm.working_id if wnm is not None else None,
            },
        )

        self._scheduler.enter_runtime_phase(cycle_id, CyclePhase.PROJECT_DISPATCH)
        pnm: ProjectedNavMapV1 | None = None
        body_handoff: BodyActionHandoffV1 | None = None
        task_action: TaskActionV1 | None = None
        if application is not None:
            pnm = self._prediction.create_current(application)
            self._trace.append(
                "pnm",
                "current PNM created before task-action dispatch",
                cycle_id=cycle_id,
                phase=CyclePhase.PROJECT_DISPATCH.name,
                details={
                    "application_id": pnm.application_id,
                    "expected_relations": ",".join(pnm.expected_relations),
                    "observation_condition": pnm.observation_condition,
                    "pnm_id": pnm.pnm_id,
                    "source_wnm_id": pnm.source_wnm_id,
                },
            )
            body_handoff = self._body_runtime.authorize_application(application, pnm_id=pnm.pnm_id)
            self._trace.append(
                "bodymap",
                "BodyMap mapped the selected task to a body-relative target and envelope",
                cycle_id=cycle_id,
                phase=CyclePhase.PROJECT_DISPATCH.name,
                details={
                    "authorized": body_handoff.authorized,
                    "body_target": (
                        body_handoff.task_target.target_id if body_handoff.task_target is not None else None
                    ),
                    "envelope": body_handoff.envelope.envelope_id if body_handoff.envelope is not None else None,
                    "reason": body_handoff.reason,
                    "task_action": application.task_action.kind.value,
                },
            )
            if body_handoff.authorized:
                task_action = application.task_action
            else:
                not_applied = self._prediction.mark_not_applied(
                    pnm.pnm_id,
                    cycle_id=cycle_id,
                    reason=body_handoff.reason,
                )
                outcomes = (*outcomes, not_applied)
                self._trace_prediction_outcome(not_applied, cycle_id=cycle_id)

        commitment = CycleCommitmentV1(
            cycle_id=cycle_id,
            observation_number=observation_number,
            eligible_result_ids=tuple(result.result_id for result in frozen),
            applied_result_ids=tuple(result.result_id for result in applied),
            attention_selection_id=selection.selection_id,
            wnm_id=wnm.working_id if wnm is not None else None,
            selected_primitive_id=navigation.selected_primitive_id,
            focal_operation_id=application.application_id if application is not None else None,
            pnm_id=pnm.pnm_id if pnm is not None else None,
            task_action=task_action.kind.value if task_action is not None else None,
            task_action_id=task_action.task_action_id if task_action is not None else None,
            action_envelope_id=(
                body_handoff.envelope.envelope_id
                if body_handoff is not None and body_handoff.envelope is not None
                else None
            ),
        )
        output = task_action.kind.value if task_action is not None else NCA8_NO_ACTION
        self._trace.append(
            "runtime",
            f"{CyclePhase.PROJECT_DISPATCH.display_name} committed Action_{cycle_id}:{output}",
            cycle_id=cycle_id,
            phase=CyclePhase.PROJECT_DISPATCH.name,
            details={
                "action_number": cycle_id,
                "attention_selection": commitment.attention_selection_id,
                "envelope": commitment.action_envelope_id,
                "pnm": commitment.pnm_id,
                "selected_primitive": commitment.selected_primitive_id,
                "task_action": commitment.task_action,
                "wnm": commitment.wnm_id,
            },
        )
        dispatch = Nca8PhaseEDispatchV1(
            commitment=commitment,
            task_action=task_action,
            pnm=pnm,
            body_handoff=body_handoff,
        )
        if phase_e_hook is not None:
            phase_e_hook(dispatch)

        self._trace.append(
            "learning",
            "Phase-F durable learning made no changes for initial Gate A",
            cycle_id=cycle_id,
            phase=CyclePhase.LEARNING_SCHEDULE.name,
            details={"durable_updates": 0},
        )
        scheduler_snapshot = self._scheduler.phase_f_finish(cycle_id, self._trace)
        self._cognitive_cycles = cycle_id
        self._last_commitment = commitment
        self._last_prediction_outcomes = outcomes
        return Nca8CognitiveRuntimeCycleV1(
            cycle_id=cycle_id,
            observation_number=observation_number,
            action_number=cycle_id,
            output=output,
            commitment=commitment,
            scheduler=scheduler_snapshot,
            posture_support_state=sensory_application.map_state,
            body_map_state=body_update.body_state,
            posture_support_candidate=body_update.posture_support_candidate,
            attention_bid=bid,
            attention_selection=selection,
            wnm=wnm,
            navigation=navigation,
            pnm=pnm,
            body_handoff=body_handoff,
            prediction_outcomes=outcomes,
            phase_e_dispatch=dispatch,
        )

    def _apply_phase_c_results(
        self,
        cycle_id: int,
        observation_number: int,
        applied: Sequence[CircuitResultV1],
    ) -> tuple[Nca8BodySensoryApplicationV1, Nca8BodyUpdateV1, tuple[PredictionOutcomeV1, ...]]:
        """Apply observation identity, sensory state, BodyMap, and prior outcomes."""
        ingress_results = [result for result in applied if result.source_circuit == _OBSERVATION_INGRESS_CIRCUIT]
        if len(ingress_results) != 1:
            raise RuntimeError("Phase C requires exactly one eligible observation-ingress result")
        if ingress_results[0].payload_dict().get("observation_number") != observation_number:
            raise RuntimeError("applied observation-ingress result does not match the cycle input")
        self._last_applied_observation_number = observation_number
        self._trace.append(
            "runtime",
            f"Observation_{observation_number} became the applied Phase-C cycle input",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={"observation_number": observation_number, "result_id": ingress_results[0].result_id},
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
                "POSTURE-SUPPORT map-state candidate published for Attention",
                cycle_id=cycle_id,
                phase=CyclePhase.UPDATE_OUTCOMES.name,
                details={
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
                    "candidate_event": body_update.candidate_event,
                    "posture": body_state.posture.value,
                    "support": body_state.support.value,
                },
            )

        envelope = self._body_runtime.reconcile_envelope_from_current_state()
        if envelope is not None:
            self._trace.append(
                "bodymap",
                "prior authorized action envelope reconciled from later body evidence",
                cycle_id=cycle_id,
                phase=CyclePhase.UPDATE_OUTCOMES.name,
                details={
                    "envelope_id": envelope.envelope_id,
                    "status": envelope.status.value,
                    "status_reason": envelope.status_reason,
                },
            )
        outcomes = self._prediction.evaluate_ready(map_state, cycle_id=cycle_id)
        for outcome in outcomes:
            self._trace_prediction_outcome(outcome, cycle_id=cycle_id)
        return sensory_application, body_update, outcomes

    def _trace_prediction_outcome(self, outcome: PredictionOutcomeV1, *, cycle_id: int) -> None:
        """Append one explicit source-linked later-evidence outcome event."""
        self._trace.append(
            "outcome",
            "later body evidence evaluated an operation-linked pending prediction",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "application_id": outcome.application_id,
                "evidence_sampled_cycle": outcome.evidence_sampled_cycle,
                "pnm_id": outcome.pnm_id,
                "reason": outcome.reason,
                "status": outcome.status.value,
            },
        )


class Nca8EpisodeRunnerV1:
    """Coordinate one private environment with one NCA8 cognitive runtime."""

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
        """Return the logical number of the next observation."""
        return self._pending_observation_number

    def run_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Run one cycle, apply its authorized output once, and buffer later evidence."""
        current_observation = self._pending_observation
        observation_number = self._pending_observation_number
        boundary_result: Nca8EnvironmentStepV1 | None = None

        def phase_e_boundary(dispatch: Nca8PhaseEDispatchV1) -> None:
            nonlocal boundary_result
            step_result = self._environment_bridge.apply_task_action(dispatch.authorized_task_action)
            boundary_result = step_result
            output = dispatch.commitment.task_action or NCA8_NO_ACTION
            self._trace.append(
                "dispatch",
                f"Action_{dispatch.commitment.cycle_id}:{output} crossed the physical environment boundary",
                cycle_id=dispatch.commitment.cycle_id,
                phase=CyclePhase.PROJECT_DISPATCH.name,
                details={
                    "action_number": dispatch.commitment.cycle_id,
                    "body_authorized": (
                        dispatch.body_handoff.authorized if dispatch.body_handoff is not None else False
                    ),
                    "done": step_result.done,
                    "environment_action": step_result.environment_action,
                    "environment_step": step_result.step_index,
                    "pnm_id": dispatch.commitment.pnm_id,
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
                "output": f"Action_{runtime_result.action_number}:{runtime_result.output}",
            },
        )
        return Nca8CognitiveCycleResultV1(
            cycle_id=runtime_result.cycle_id,
            observation_number=runtime_result.observation_number,
            action_number=runtime_result.action_number,
            next_observation_number=next_observation_number,
            output=runtime_result.output,
            environment_action=boundary_result.environment_action,
            reward=boundary_result.reward,
            done=boundary_result.done,
            environment_step=boundary_result.step_index,
            commitment=runtime_result.commitment,
            scheduler=runtime_result.scheduler,
            posture_support_state=runtime_result.posture_support_state,
            body_map_state=runtime_result.body_map_state,
            posture_support_candidate=runtime_result.posture_support_candidate,
            attention_bid=runtime_result.attention_bid,
            attention_selection=runtime_result.attention_selection,
            wnm=runtime_result.wnm,
            navigation=runtime_result.navigation,
            pnm=runtime_result.pnm,
            body_handoff=runtime_result.body_handoff,
            prediction_outcomes=runtime_result.prediction_outcomes,
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
        self._attention: AttentionRuntimeV1
        self._navigation: NavigationRuntimeV1
        self._prediction: Nca8PredictionRuntimeV1
        self._primitives: tuple[PrimitiveRuntimeV1, ...]
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
        """Return the immutable developmental POSTURE-SUPPORT map revision."""
        return self._map_library.durable_map()

    @property
    def posture_support_state(self) -> NavMapStateV1 | None:
        """Return the current transient POSTURE-SUPPORT state."""
        return self._body_sensory.current_state

    @property
    def body_map_state(self) -> BodyMapStateV1 | None:
        """Return the current protected BodyMap state."""
        return self._body_runtime.current_state

    @property
    def posture_support_candidate(self) -> PostureSupportCandidateV1 | None:
        """Return the current body-published Attention candidate."""
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
        new_body_runtime = Nca8BodyRuntimeV1(
            action_handoff_enabled=self._config.body_action_handoff_enabled,
        )
        new_attention = AttentionRuntimeV1(enabled=self._config.attention_enabled)
        new_navigation = NavigationRuntimeV1(enabled=self._config.navigation_enabled)
        new_prediction = Nca8PredictionRuntimeV1()
        new_primitives = create_gate_a_primitives_v1()
        new_runtime = Nca8CognitiveRuntimeV1(
            trace=new_trace,
            scheduler=new_scheduler,
            map_library=new_map_library,
            body_sensory=new_body_sensory,
            body_runtime=new_body_runtime,
            attention=new_attention,
            navigation=new_navigation,
            prediction=new_prediction,
            primitives=new_primitives,
        )
        new_episode_runner = Nca8EpisodeRunnerV1(
            environment_bridge=new_bridge,
            cognitive_runtime=new_runtime,
            trace=new_trace,
            initial_observation=reset_result.observation,
            initial_observation_number=1,
        )
        next_generation = self._lifecycle_generation + 1
        new_trace.append(
            "session",
            "isolated Phase-1D Gate-A session reset",
            details={
                "attention_enabled": self._config.attention_enabled,
                "body_action_handoff_enabled": self._config.body_action_handoff_enabled,
                "durable_posture_support_map": (
                    f"{new_map_library.posture_support_ref.map_id}@r"
                    f"{new_map_library.posture_support_ref.revision}"
                ),
                "episode_index": reset_result.episode_index,
                "generation": next_generation,
                "navigation_enabled": self._config.navigation_enabled,
                "pending_observation_number": 1,
                "seed": self._config.seed,
            },
        )
        new_trace.append(
            "firewall",
            "Observation_1 buffered as the first cognitive-cycle input",
            details=_observation_trace_details_v1(reset_result.observation, observation_number=1),
        )
        self._rng = new_rng
        self._environment_bridge = new_bridge
        self._trace = new_trace
        self._scheduler = new_scheduler
        self._map_library = new_map_library
        self._body_sensory = new_body_sensory
        self._body_runtime = new_body_runtime
        self._attention = new_attention
        self._navigation = new_navigation
        self._prediction = new_prediction
        self._primitives = new_primitives
        self._cognitive_runtime = new_runtime
        self._episode_runner = new_episode_runner
        self._lifecycle_generation = next_generation
        return self.status()

    def status(self) -> Nca8SessionStatusV1:
        """Return a read-only status snapshot without exposing owned mutable objects."""
        map_state = self._body_sensory.current_state
        body_state = self._body_runtime.current_state
        candidate = self._body_runtime.posture_support_candidate
        attention = self._attention.last_selection
        navigation = self._navigation.last_decision
        outcomes = self._prediction.outcome_history()
        last_commitment = self._cognitive_runtime.last_commitment
        envelope = self._body_runtime.current_envelope
        return Nca8SessionStatusV1(
            lifecycle_generation=self._lifecycle_generation,
            seed=self._config.seed,
            scenario_name=self._config.scenario_name,
            environment_episode_index=self._environment_bridge.episode_index,
            cognitive_cycles=self._cognitive_runtime.cognitive_cycles,
            pending_observation_number=self._episode_runner.pending_observation_number,
            pending_circuit_results=len(self._scheduler.pending_results_snapshot()),
            latched_events=len(self._scheduler.latched_results_snapshot()),
            posture_support_map_revision=self._map_library.posture_support_ref.revision,
            current_map_state_count=self._map_library.current_state_count,
            current_posture=map_state.posture.value if map_state is not None else None,
            current_support=map_state.support.value if map_state is not None else None,
            body_map_posture=body_state.posture.value if body_state is not None else None,
            posture_support_candidate_id=candidate.candidate_id if candidate is not None else None,
            attention_disposition=attention.disposition.value if attention is not None else None,
            wnm_id=self._navigation.current_wnm.working_id if self._navigation.current_wnm is not None else None,
            selected_primitive_id=navigation.selected_primitive_id if navigation is not None else None,
            current_pnm_id=(
                self._prediction.current_pnm.pnm_id if self._prediction.current_pnm is not None else None
            ),
            last_prediction_outcome=outcomes[-1].status.value if outcomes else None,
            last_task_action=last_commitment.task_action if last_commitment is not None else None,
            current_envelope_status=envelope.status.value if envelope is not None else None,
            trace_retained=self._trace.retained_count,
            trace_capacity=self._trace.capacity,
        )

    def run_cognitive_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Execute one full Gate-A-capable cognitive cycle and buffer later evidence."""
        return self._episode_runner.run_cycle()


    def run_null_smoke_cycle(self) -> Nca8CognitiveCycleResultV1:
        """Compatibility alias for the old Phase-1A method."""
        return self.run_cognitive_cycle()


    def run_gate_a(self, *, max_cycles: int | None = None, reset_first: bool = True) -> Nca8GateASummaryV1:
        """Run a fresh bounded StandUp path until later evidence confirms standing."""
        limit = max_cycles if max_cycles is not None else self._config.gate_a_max_cycles
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("max_cycles must be a positive integer")
        if reset_first:
            self.reset()

        stand_up_actions = 0
        successful_application_id: str | None = None
        last_outcome_status: str | None = None
        achieved = False
        cycles_run = 0

        for _ in range(limit):
            result = self.run_cognitive_cycle()
            cycles_run += 1

            if result.task_action == "STAND_UP":
                stand_up_actions += 1

            for outcome in result.prediction_outcomes:
                last_outcome_status = outcome.status.value
                if outcome.status is PredictionOutcomeStatusV1.SUCCESS:
                    successful_application_id = outcome.application_id

            cycle_state = result.posture_support_state
            achieved = bool(
                successful_application_id is not None
                and cycle_state.posture is Nca8PostureStateV1.STANDING
                and cycle_state.support is Nca8SupportStateV1.STABLE
            )
            if achieved:
                break

        final_state = self._body_sensory.current_state
        reason = (
            "later_current_body_evidence_confirmed_standing"
            if achieved
            else "bounded_gate_a_cycle_limit_reached_without_success"
        )

        return Nca8GateASummaryV1(
            achieved_standing=achieved,
            cycles_run=cycles_run,
            stand_up_actions=stand_up_actions,
            final_posture=final_state.posture.value if final_state is not None else None,
            final_support=final_state.support.value if final_state is not None else None,
            successful_application_id=successful_application_id,
            last_outcome_status=last_outcome_status,
            reason=reason,
        )

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
        """Return byte-stable canonical trace JSON for replay tests."""
        return self._trace.as_canonical_json_bytes()
