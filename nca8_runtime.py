#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated Architecture-v09.3 runtime shell for the new CCA8 implementation.

Phase 1A scope
--------------
This module proves that the existing CCA8 application can host a second brain
without sharing mutable cognitive state or consulting legacy cognitive
conclusions.  ``Nca8SessionV1`` owns its own environment bridge, random-number
generator, pending whitelisted observation, trace buffer, and lifecycle.

This is intentionally *not yet cognition*.  There is no Attention, WNM,
Navigation, primitive selection, PNM, BodyMap cognition, SEC, WorldIndex, or
learning in Phase 1A.  The sole executable operation is a clearly labelled null
smoke cycle that accepts ``Observation_n``, commits ``Action_n=NO_ACTION``,
advances the private physical environment, and buffers ``Observation_(n+1)``
for the next numbered cycle.

Numbering contract
------------------
Logical event numbering is one-based and synchronized at the commitment
boundary.  Cycle ``n`` consumes ``Observation_n`` and commits ``Action_n``.
The environment's later consequence is returned as ``Observation_(n+1)`` and
is buffered for Cycle ``n+1``.  The environment may retain its own internal
zero-based step counter, but that implementation detail is not used as the
agent-visible observation number.

Dependency boundary
-------------------
The module imports only the standard library and other ``nca8_*`` modules.  It
does not import ``cca8_run``, ``Ctx``, the legacy controller, PolicyRuntime,
WorkingMap, WorldGraph, legacy WNM/prediction modules, or domain policies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from nca8_adapters import Nca8EnvironmentBridgeV1, Nca8ObservationV1, create_environment_bridge_v1
from nca8_trace import Nca8TraceBufferV1, Nca8TraceEventV1

__version__ = "0.1.1"
__all__ = [
    "NCA8_NO_ACTION",
    "Nca8NullSmokeResultV1",
    "Nca8SessionConfigV1",
    "Nca8SessionStatusV1",
    "Nca8SessionV1",
    "__version__",
]

NCA8_NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class Nca8SessionConfigV1:
    """Immutable engineering configuration for one isolated new-runtime session."""

    seed: int = 0
    scenario_name: str = "newborn_goat_first_hour"
    trace_capacity: int = 64

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not isinstance(self.scenario_name, str) or not self.scenario_name.strip():
            raise ValueError("scenario_name must not be blank")
        if len(self.scenario_name.strip()) > 120:
            raise ValueError("scenario_name exceeds the 120-character limit")
        if isinstance(self.trace_capacity, bool) or not isinstance(self.trace_capacity, int) or self.trace_capacity <= 0:
            raise ValueError("trace_capacity must be a positive integer")


@dataclass(frozen=True, slots=True)
class Nca8SessionStatusV1:
    """Read-only status surface for the Phase-1A session shell."""

    lifecycle_generation: int
    seed: int
    scenario_name: str
    environment_episode_index: int
    null_smoke_cycles: int
    pending_observation_number: int
    trace_retained: int
    trace_capacity: int

    def as_dict(self) -> dict[str, int | str | None]:
        """Return a newly allocated scalar status dictionary."""
        return {
            "lifecycle_generation": self.lifecycle_generation,
            "seed": self.seed,
            "scenario_name": self.scenario_name,
            "environment_episode_index": self.environment_episode_index,
            "null_smoke_cycles": self.null_smoke_cycles,
            "pending_observation_number": self.pending_observation_number,
            "trace_retained": self.trace_retained,
            "trace_capacity": self.trace_capacity,
        }


@dataclass(frozen=True, slots=True)
class Nca8NullSmokeResultV1:
    """Immutable result of one explicit no-cognition Phase-1A smoke cycle."""

    cycle_id: int
    observation_number: int
    action_number: int
    next_observation_number: int
    output: str
    reward: float
    done: bool


def _observation_trace_details_v1(
    observation: Nca8ObservationV1,
    *,
    observation_number: int,
) -> dict[str, str | int | float | bool | None]:
    """Return a trace summary using NCA8 logical numbering, not raw environment steps.

    ``Nca8ObservationV1.step_index`` remains available inside the environment
    adapter as a diagnostic of the physical simulator.  The runtime trace uses
    the one-based observation number governed by the cognitive-cycle contract,
    preventing a zero-based environment detail from creating an apparent
    off-by-one relationship among Cycle_n, Observation_n, and Action_n.
    """
    details = observation.compact_summary()
    details.pop("step_index", None)
    details["observation_number"] = observation_number
    return details


class Nca8SessionV1:
    """Own all mutable state for one isolated Architecture-v09.3 experiment.

    Construction performs one fresh reset so the session immediately owns a
    private environment and one buffered agent-visible observation.  ``reset``
    replaces the environment bridge, RNG, trace buffer, and pending observation
    rather than mutating any legacy CCA8 runtime object.
    """

    def __init__(self, config: Nca8SessionConfigV1 | None = None) -> None:
        self._config = config or Nca8SessionConfigV1()
        self._lifecycle_generation = 0
        self._environment_bridge: Nca8EnvironmentBridgeV1
        self._rng: random.Random
        self._trace: Nca8TraceBufferV1
        self._pending_observation: Nca8ObservationV1
        self._pending_observation_number: int
        self._null_smoke_cycles = 0
        self.reset()

    @property
    def config(self) -> Nca8SessionConfigV1:
        """Return the immutable session configuration."""
        return self._config

    @property
    def pending_observation(self) -> Nca8ObservationV1:
        """Return the recursively immutable observation buffered for later use."""
        return self._pending_observation

    def reset(self) -> Nca8SessionStatusV1:
        """Replace all Phase-1A mutable state with a fresh isolated episode.

        New objects are constructed and reset before being installed on the
        session.  If environment construction fails, the previously functioning
        session remains intact rather than becoming half-reset.
        """
        new_rng = random.Random(self._config.seed)
        new_bridge = create_environment_bridge_v1(scenario_name=self._config.scenario_name)
        reset_result = new_bridge.reset(seed=self._config.seed)
        new_trace = Nca8TraceBufferV1(capacity=self._config.trace_capacity)
        next_generation = self._lifecycle_generation + 1
        first_observation_number = 1

        new_trace.append(
            "session",
            "isolated Phase-1A session reset",
            details={
                "generation": next_generation,
                "seed": self._config.seed,
                "episode_index": reset_result.episode_index,
                "pending_observation_number": first_observation_number,
            },
        )
        new_trace.append(
            "firewall",
            f"Observation_{first_observation_number} buffered as the first cycle input",
            details=_observation_trace_details_v1(
                reset_result.observation,
                observation_number=first_observation_number,
            ),
        )

        self._rng = new_rng
        self._environment_bridge = new_bridge
        self._trace = new_trace
        self._pending_observation = reset_result.observation
        self._pending_observation_number = first_observation_number
        self._null_smoke_cycles = 0
        self._lifecycle_generation = next_generation
        return self.status()

    def status(self) -> Nca8SessionStatusV1:
        """Return a read-only status snapshot without exposing owned objects."""
        return Nca8SessionStatusV1(
            lifecycle_generation=self._lifecycle_generation,
            seed=self._config.seed,
            scenario_name=self._config.scenario_name,
            environment_episode_index=self._environment_bridge.episode_index,
            null_smoke_cycles=self._null_smoke_cycles,
            pending_observation_number=self._pending_observation_number,
            trace_retained=self._trace.retained_count,
            trace_capacity=self._trace.capacity,
        )

    def run_null_smoke_cycle(self) -> Nca8NullSmokeResultV1:
        """Exercise the isolated observation/action boundary with ``NO_ACTION``.

        The method does not claim that a full Architecture-v09.3 cognitive cycle
        occurred.  It simply proves this causal shell:

        ``Observation_n -> Action_n=NO_ACTION -> private environment -> buffered Observation_(n+1)``.

        The logical numbering invariant is checked on every call: smoke Cycle_n
        consumes Observation_n and commits Action_n.  The returned observation
        is labelled Observation_(n+1) for the following cycle.
        """
        current_observation = self._pending_observation
        cycle_id = self._null_smoke_cycles + 1
        observation_number = self._pending_observation_number
        action_number = cycle_id
        if observation_number != cycle_id:
            raise RuntimeError(
                "NCA8 numbering invariant violated: "
                f"Cycle_{cycle_id} cannot consume Observation_{observation_number}"
            )

        current_details = _observation_trace_details_v1(
            current_observation,
            observation_number=observation_number,
        )
        current_details["cycle_id"] = cycle_id
        self._trace.append(
            "smoke",
            f"Observation_{observation_number} accepted for SmokeCycle_{cycle_id}",
            details=current_details,
        )
        self._trace.append(
            "smoke",
            f"Action_{action_number} committed as {NCA8_NO_ACTION}",
            details={
                "action_number": action_number,
                "cycle_id": cycle_id,
                "reason": "phase_1a_has_no_cognitive_authority",
            },
        )

        environment_result = self._environment_bridge.apply_no_action()
        next_observation_number = cycle_id + 1
        self._pending_observation = environment_result.observation
        self._pending_observation_number = next_observation_number
        self._null_smoke_cycles = cycle_id

        self._trace.append(
            "environment",
            f"Action_{action_number} applied to the private environment",
            details={
                "action_number": action_number,
                "cycle_id": cycle_id,
                "action": None,
                "reward": environment_result.reward,
                "done": environment_result.done,
                "environment_step": environment_result.step_index,
            },
        )
        next_details = _observation_trace_details_v1(
            environment_result.observation,
            observation_number=next_observation_number,
        )
        next_details["next_cycle_id"] = next_observation_number
        self._trace.append(
            "smoke",
            f"Observation_{next_observation_number} buffered for SmokeCycle_{next_observation_number}",
            details=next_details,
        )

        return Nca8NullSmokeResultV1(
            cycle_id=cycle_id,
            observation_number=observation_number,
            action_number=action_number,
            next_observation_number=next_observation_number,
            output=NCA8_NO_ACTION,
            reward=environment_result.reward,
            done=environment_result.done,
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
