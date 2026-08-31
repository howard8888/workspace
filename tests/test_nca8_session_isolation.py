#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State-ownership, lifecycle, and numbering tests for the NCA8 runtime."""

from __future__ import annotations

from pathlib import Path

import nca8_runtime
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionConfigV1, Nca8SessionV1


def test_two_sessions_own_distinct_mutable_runtime_objects() -> None:
    """Separate brains must not co-own environment, scheduler, maps, BodyMap, or observations."""
    first = Nca8SessionV1(Nca8SessionConfigV1(seed=17))
    second = Nca8SessionV1(Nca8SessionConfigV1(seed=17))

    assert first is not second
    assert first._environment_bridge is not second._environment_bridge  # pylint: disable=protected-access
    assert (  # pylint: disable=protected-access
        first._environment_bridge._environment is not second._environment_bridge._environment
    )
    assert first._rng is not second._rng  # pylint: disable=protected-access
    assert first._trace is not second._trace  # pylint: disable=protected-access
    assert first._scheduler is not second._scheduler  # pylint: disable=protected-access
    assert first._map_library is not second._map_library  # pylint: disable=protected-access
    assert first._body_sensory is not second._body_sensory  # pylint: disable=protected-access
    assert first._body_runtime is not second._body_runtime  # pylint: disable=protected-access
    assert first._attention is not second._attention  # pylint: disable=protected-access
    assert first._navigation is not second._navigation  # pylint: disable=protected-access
    assert first._prediction is not second._prediction  # pylint: disable=protected-access
    assert first._primitives is not second._primitives  # pylint: disable=protected-access
    assert first._cognitive_runtime is not second._cognitive_runtime  # pylint: disable=protected-access
    assert first._episode_runner is not second._episode_runner  # pylint: disable=protected-access
    assert first.pending_observation is not second.pending_observation
    assert first.pending_observation.as_dict() == second.pending_observation.as_dict()


def test_advancing_one_session_does_not_advance_the_other() -> None:
    """One NCA8 episode must not contaminate another episode with the same seed."""
    first = Nca8SessionV1(Nca8SessionConfigV1(seed=9))
    second = Nca8SessionV1(Nca8SessionConfigV1(seed=9))

    result = first.run_cognitive_cycle()

    assert result.output == "STAND_UP"
    assert first.status().cognitive_cycles == 1
    assert first.status().pending_observation_number == 2
    assert second.status().cognitive_cycles == 0
    assert second.status().pending_observation_number == 1
    assert second._environment_bridge.episode_index == 1  # pylint: disable=protected-access


def test_reset_replaces_owned_objects_and_clears_only_the_new_session() -> None:
    """Reset should create a fresh second brain rather than reusing episode state."""
    session = Nca8SessionV1(Nca8SessionConfigV1(seed=4))
    session.run_cognitive_cycle()
    old_bridge = session._environment_bridge  # pylint: disable=protected-access
    old_environment = old_bridge._environment  # pylint: disable=protected-access
    old_rng = session._rng  # pylint: disable=protected-access
    old_trace = session._trace  # pylint: disable=protected-access
    old_scheduler = session._scheduler  # pylint: disable=protected-access
    old_map_library = session._map_library  # pylint: disable=protected-access
    old_body_sensory = session._body_sensory  # pylint: disable=protected-access
    old_body_runtime = session._body_runtime  # pylint: disable=protected-access
    old_attention = session._attention  # pylint: disable=protected-access
    old_navigation = session._navigation  # pylint: disable=protected-access
    old_prediction = session._prediction  # pylint: disable=protected-access
    old_primitives = session._primitives  # pylint: disable=protected-access
    old_runtime = session._cognitive_runtime  # pylint: disable=protected-access
    old_episode_runner = session._episode_runner  # pylint: disable=protected-access

    status = session.reset()

    assert status.lifecycle_generation == 2
    assert status.cognitive_cycles == 0
    assert status.pending_observation_number == 1
    assert status.current_map_state_count == 0
    assert status.current_posture is None
    assert status.body_map_posture is None
    assert status.posture_support_candidate_id is None
    assert session._environment_bridge is not old_bridge  # pylint: disable=protected-access
    assert session._environment_bridge._environment is not old_environment  # pylint: disable=protected-access
    assert session._rng is not old_rng  # pylint: disable=protected-access
    assert session._trace is not old_trace  # pylint: disable=protected-access
    assert session._scheduler is not old_scheduler  # pylint: disable=protected-access
    assert session._map_library is not old_map_library  # pylint: disable=protected-access
    assert session._body_sensory is not old_body_sensory  # pylint: disable=protected-access
    assert session._body_runtime is not old_body_runtime  # pylint: disable=protected-access
    assert session._attention is not old_attention  # pylint: disable=protected-access
    assert session._navigation is not old_navigation  # pylint: disable=protected-access
    assert session._prediction is not old_prediction  # pylint: disable=protected-access
    assert session._primitives is not old_primitives  # pylint: disable=protected-access
    assert session._cognitive_runtime is not old_runtime  # pylint: disable=protected-access
    assert session._episode_runner is not old_episode_runner  # pylint: disable=protected-access
    assert session.trace_lines()[0].startswith("[nca8:session]")


def test_cognitive_cycle_preserves_observation_action_ordering() -> None:
    """Cycle_n should consume Observation_n and commit Action_n before Observation_(n+1)."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()
    lines = session.trace_lines()

    assert result.cycle_id == 1
    assert result.observation_number == 1
    assert result.action_number == 1
    assert result.next_observation_number == 2
    assert result.output == "STAND_UP"

    opened_index = next(index for index, line in enumerate(lines) if "CognitiveCycle_1 opened with Observation_1" in line)
    action_index = next(index for index, line in enumerate(lines) if "Action_1:STAND_UP crossed" in line)
    buffered_index = next(index for index, line in enumerate(lines) if "Observation_2 buffered for CognitiveCycle_2" in line)
    closed_index = next(index for index, line in enumerate(lines) if "CognitiveCycle_1 closed" in line)

    assert opened_index < action_index < buffered_index < closed_index


def test_event_numbers_remain_synchronized_across_multiple_cognitive_cycles() -> None:
    """Logical observation/action numbering must never drift one behind the cycle."""
    session = Nca8SessionV1()

    for expected_number in range(1, 5):
        result = session.run_cognitive_cycle()
        assert result.cycle_id == expected_number
        assert result.observation_number == expected_number
        assert result.action_number == expected_number
        assert result.next_observation_number == expected_number + 1
        assert session.status().pending_observation_number == expected_number + 1


def test_phase1a_method_name_remains_a_compatibility_alias() -> None:
    """The old smoke-cycle call should route to the current NCA8 cognitive cycle."""
    session = Nca8SessionV1()

    result = session.run_null_smoke_cycle()

    assert result.cycle_id == 1
    assert session.status().cognitive_cycles == 1
    assert session.status().null_smoke_cycles == 1


def test_new_runtime_never_touches_an_unrelated_legacy_autosave_file(tmp_path: Path) -> None:
    """The NCA8 runtime receives no legacy autosave path and cannot rewrite it."""
    sentinel = tmp_path / "legacy_session.json"
    original = b'{"legacy": true, "unchanged": 123}\n'
    sentinel.write_bytes(original)

    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    session.reset()

    assert sentinel.read_bytes() == original


def test_runtime_module_has_no_process_global_session_singleton() -> None:
    """Importing the module must not construct mutable session state."""
    global_sessions = [value for value in vars(nca8_runtime).values() if isinstance(value, Nca8SessionV1)]

    assert global_sessions == []
