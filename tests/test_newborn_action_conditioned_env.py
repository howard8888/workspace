# -*- coding: utf-8 -*-
"""Tests for the action-conditioned newborn-goat environment path.

These tests deliberately exercise only ``HybridEnvironment`` and ``FsmBackend``.
They do not depend on the runner, WorldGraph, BodyMap, PolicyRuntime, or any
controller heuristics. The purpose is to lock down the environment-side contract:
a hard-mode newborn episode should not complete the survival sequence merely
because time passes; progress after the birth setup should require correctly
staged agent actions.
"""

from __future__ import annotations

from typing import Iterable

from cca8_env import EnvConfig, HybridEnvironment


HARD_NEWBORN = EnvConfig(scenario_name="newborn_goat_first_hour_benchmark_hard")


def _make_hard_newborn_env() -> HybridEnvironment:
    """Return a fresh hard-mode newborn-goat environment."""
    env = HybridEnvironment(config=HARD_NEWBORN)
    _obs, _info = env.reset()
    return env


def _step_many(env: HybridEnvironment, actions: Iterable[str | None]) -> None:
    """Step the environment through the supplied action sequence."""
    for action in actions:
        _obs, _reward, _done, _info = env.step(action=action, ctx=None)


def _advance_to_struggle(env: HybridEnvironment) -> None:
    """Advance through the initial birth setup into the action-conditioned struggle phase."""
    _step_many(env, [None, None, None])
    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"


def test_hard_newborn_passive_time_does_not_complete_survival_sequence() -> None:
    """Hard-mode newborn episodes should not solve themselves without useful actions."""
    env = _make_hard_newborn_env()

    _step_many(env, [None] * 25)

    assert env.state.newborn_benchmark_hard is True
    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"
    assert env.state.mom_distance == "far"
    assert env.state.nipple_state == "hidden"
    assert env.state.newborn_milk_ticks == 0
    assert "milk_drinking" not in env.state.milestones


def test_hard_newborn_premature_nipple_seek_causes_setback() -> None:
    """Seeking the nipple before re-securing mom proximity should not make progress."""
    env = _make_hard_newborn_env()
    _advance_to_struggle(env)

    _step_many(env, ["policy:stand_up", "policy:stand_up"])
    assert env.state.scenario_stage == "first_stand"
    assert env.state.kid_posture == "standing"

    _obs, _reward, _done, _info = env.step(action="policy:seek_nipple", ctx=None)

    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"
    assert env.state.nipple_state == "hidden"
    assert env.state.newborn_setback_count == 1


def test_hard_newborn_correct_action_ladder_reaches_resting_milk_state() -> None:
    """A correctly staged action sequence should complete the newborn survival ladder."""
    env = _make_hard_newborn_env()
    _advance_to_struggle(env)

    # Hard-mode ladder:
    #   2 stand attempts -> stood_up
    #   2 follow attempts -> reached_mom
    #   3 seek/suckle attempts -> found_nipple, then latched_nipple
    #   3 milk ticks + 2 rest actions -> rested
    actions = [
        "policy:stand_up",
        "policy:stand_up",
        "policy:follow_mom",
        "policy:follow_mom",
        "policy:seek_nipple",
        "policy:seek_nipple",
        "policy:seek_nipple",
        None,
        None,
        None,
        "policy:rest",
        "policy:rest",
    ]
    _step_many(env, actions)

    assert env.state.scenario_stage == "rest"
    assert env.state.kid_posture == "resting"
    assert env.state.mom_distance == "touching"
    assert env.state.nipple_state == "latched"
    assert env.state.shelter_distance == "near"
    assert env.state.cliff_distance == "far"
    assert env.state.newborn_setback_count == 0
    assert env.state.newborn_milk_ticks >= 3

    final_obs, _reward, _done, _info = env.step(action=None, ctx=None)
    assert "resting" in final_obs.predicates
    assert "milk:drinking" in final_obs.predicates
    assert "proximity:mom:close" in final_obs.predicates