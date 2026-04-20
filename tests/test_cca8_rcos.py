# -*- coding: utf-8 -*-
"""Tests for the stage-1 SimRobotGoat RCOS sandbox."""

from cca8_rcos import (
    CMD_STAND,
    CMD_TURN_RIGHT,
    CMD_WALK_FORWARD,
    MILESTONE_RECOVERED,
    MILESTONE_RESTED,
    MILESTONE_RETURNED_TO_DOCK,
    MILESTONE_RECHARGED,
    MILESTONE_TARGET_INSPECTED,
    SimRobotGoatEnv,
    run_sim_robot_goat_demo_episode_v1,
)


def test_sim_robot_goat_reset_starts_fallen_at_dock() -> None:
    env = SimRobotGoatEnv()
    obs, info = env.reset(seed=11)

    assert info["sim_env"] == "sim_robot_goat_v1"
    assert obs.raw_sensors["x"] == 1
    assert obs.raw_sensors["y"] == 1
    assert "posture:fallen" in obs.predicates
    assert "position:at_dock" in obs.cues


def test_sim_robot_goat_hazard_step_causes_fall_and_violation() -> None:
    env = SimRobotGoatEnv()
    env.reset(seed=11)

    env.step(CMD_STAND)
    env.step(CMD_TURN_RIGHT)
    env.step(CMD_WALK_FORWARD)
    _obs, _reward, _done, info = env.step(CMD_WALK_FORWARD)

    assert info["state"]["posture"] == "fallen"
    assert info["state"]["falls"] == 1
    assert info["state"]["safety_violations"] == 1
    assert info["ack"]["status"] == "hazard_fall"


def test_sim_robot_goat_demo_episode_completes_all_milestones() -> None:
    result = run_sim_robot_goat_demo_episode_v1()
    summary = result["summary"]

    assert summary["success"] is True
    assert summary["done_reason"] == "mission_complete"
    assert summary["milestone_vector"][MILESTONE_RECOVERED] is True
    assert summary["milestone_vector"][MILESTONE_TARGET_INSPECTED] is True
    assert summary["milestone_vector"][MILESTONE_RETURNED_TO_DOCK] is True
    assert summary["milestone_vector"][MILESTONE_RECHARGED] is True
    assert summary["milestone_vector"][MILESTONE_RESTED] is True
    assert summary["milestone_score"] == 1.0
    assert summary["safety_violations"] == 0