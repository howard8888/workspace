#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for bounded DP01 EnvObservation injection in Main Menu #2."""

from __future__ import annotations

from copy import deepcopy
import json
import random

import cca8_cognitive_injection
import cca8_controller
import cca8_run
from cca8_column import mem as column_mem
from cca8_features import FactMeta, TensorPayload

# These tests deliberately inspect the process-shared skill and Column stores to
# prove that the disposable diagnostic sandbox restores them exactly.
# pylint: disable=protected-access


def test_fallen_near_cliff_preset_is_explicitly_synthetic() -> None:
    """The first preset should create a normal but source-stamped DP01 packet."""
    state, observation, metadata = cca8_cognitive_injection.build_fallen_near_cliff_injection_v1("INJTEST")

    assert state.kid_posture == "fallen"
    assert state.cliff_distance == "near"
    assert state.mom_distance == "far"
    assert "posture:fallen" in observation.predicates
    assert "hazard:cliff:near" in observation.predicates
    assert "vestibular:fall" in observation.cues
    assert "touch:flank_on_ground" in observation.cues
    assert observation.raw_sensors["diagnostic_pulse"] == 1.0
    assert observation.env_meta["source_class"] == "synthetic_test_evidence"
    assert observation.env_meta["feeding_geometry_v1"]["source_class"] == "synthetic_test_evidence"
    assert observation.env_meta["terrain_geometry_v1"]["source_class"] == "synthetic_test_evidence"
    assert observation.env_meta["lower_motor_feedback_v1"]["source_class"] == "synthetic_test_evidence"
    assert observation.surface_grid["source_class"] == "synthetic_test_evidence"
    assert observation.env_meta["diagnostic_injection_v1"]["injection_id"] == "INJTEST"
    assert metadata["boundary"] == "DP01"
    assert metadata["sandbox_only"] is True
    assert metadata["live_session_authority"] is False


def test_sandbox_injection_runs_real_cycle_and_restores_process_shared_state() -> None:
    """One injected packet should traverse DP01-DP18 without leaking sandbox writes."""
    original_skills = deepcopy(cca8_controller.SKILLS)
    original_columns = deepcopy(column_mem._store)
    original_random_state = random.getstate()

    try:
        cca8_controller.SKILLS.clear()
        cca8_controller.SKILLS["policy:legacy_sentinel"] = cca8_controller.SkillStat(
            n=2,
            succ=1,
            q=0.25,
            last_reward=0.5,
            execution_count=None,
            last_execution_reward=None,
        )
        column_mem._store.clear()
        sentinel_id = column_mem.assert_fact(
            "diagnostic:sentinel",
            TensorPayload(data=[0.25], shape=(1,), kind="diagnostic"),
            FactMeta(name="diagnostic:sentinel", attrs={"purpose": "rollback_test"}),
        )

        expected_skills = deepcopy(cca8_controller.SKILLS)
        expected_columns = deepcopy(column_mem._store)
        expected_random_state = random.getstate()

        result = cca8_cognitive_injection.run_envobservation_injection_sandbox_v1(
            cca8_run._cognitive_scope_injection_runtime_v1(),
            injection_id="INJ0001",
        )

        assert result["status"] == "completed"
        assert result["selected_policy"] == "policy:stand_up"
        assert result["action_dispatched"] == "policy:stand_up"
        assert result["live_cognitive_state_mutated"] is False
        assert result["shared_state_rollback"] == {
            "skills_restored": True,
            "columns_restored": True,
            "random_state_restored": True,
            "error": None,
        }

        assert cca8_controller.SKILLS == expected_skills
        assert column_mem._store == expected_columns
        assert sentinel_id in column_mem._store
        assert random.getstate() == expected_random_state

        snapshot = result["snapshot"]
        assert snapshot["capture_kind"] == "synthetic_envobservation_injection_v1"
        assert snapshot["injection_enabled"] is True
        assert snapshot["sandbox_only"] is True
        assert snapshot["live_cognitive_state_mutated"] is False
        assert snapshot["live_injection_enabled"] is False
        assert snapshot["sandbox_injection"]["injection_id"] == "INJ0001"

        by_id = {row["port_id"]: row for row in snapshot["ports"]}
        assert by_id["DP01"]["authority"] == "synthetic_test_evidence"
        assert by_id["DP01"]["signal"]["raw_sensors"]["diagnostic_pulse"] == 1.0
        assert by_id["DP04"]["signal_status"] == "active"
        assert by_id["DP06"]["signal"]["observation_update"]["action"] == "create_candidate"
        assert by_id["DP07"]["signal"]["posture"] == "fallen"
        assert by_id["DP07"]["signal"]["cliff_distance"] == "near"
        assert by_id["DP11"]["signal"]["operative_count"] == 1
        assert by_id["DP13"]["signal"]["chosen"] == "policy:stand_up"
        assert by_id["DP14"]["signal"]["selected_primitive"] == "policy:stand_up"
        assert by_id["DP15"]["signal"]["dispatch_succeeded"] is True
        assert by_id["DP16"]["signal"]["prediction_next_record"]["expected"] == {"posture": "standing"}
        assert "policy:stand_up" in by_id["DP18"]["signal"]["skill_stats"]

        assert "[env→controller] policy:stand_up" in result["transcript"]
        assert "[controller→env] cycle_output='policy:stand_up'" in result["transcript"]
        json.dumps(result, allow_nan=False)
    finally:
        cca8_controller.SKILLS.clear()
        cca8_controller.SKILLS.update(original_skills)
        column_mem._store.clear()
        column_mem._store.update(original_columns)
        random.setstate(original_random_state)


def test_unknown_injection_preset_returns_error_after_rollback() -> None:
    """A rejected preset must still preserve process-shared diagnostic state."""
    skills_before = deepcopy(cca8_controller.SKILLS)
    columns_before = deepcopy(column_mem._store)
    random_state_before = random.getstate()

    result = cca8_cognitive_injection.run_envobservation_injection_sandbox_v1(
        cca8_run._cognitive_scope_injection_runtime_v1(),
        injection_id="INJBAD",
        preset_id="not_a_preset",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "ValueError"
    assert result["snapshot"] == {}
    assert result["shared_state_rollback"]["skills_restored"] is True
    assert result["shared_state_rollback"]["columns_restored"] is True
    assert result["shared_state_rollback"]["random_state_restored"] is True
    assert cca8_controller.SKILLS == skills_before
    assert column_mem._store == columns_before
    assert random.getstate() == random_state_before
