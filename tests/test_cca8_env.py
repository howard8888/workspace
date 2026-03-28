# tests/test_cca8_env.py
# Basic unit tests for cca8_env.EnvState / EnvObservation / HybridEnvironment / PerceptionAdapter
#
# These tests now match the hardened newborn-goat environment:
#   1) No-action runs should stall in struggle rather than auto-completing B2.
#   2) PerceptionAdapter should expose full local detail when blackout is not active.
#   3) PerceptionAdapter should suppress local detail during an explicit blackout window.

import math

from cca8_env import (
    EnvState,
    EnvObservation,
    EnvConfig,
    PerceptionAdapter,
    HybridEnvironment,
)


def test_storyboard_sequence_no_actions_stalls_in_struggle():
    """
    The hardened newborn-goat environment should no longer auto-progress all the way
    to standing/latching/resting when no actions are supplied.

    We still expect the initial birth -> struggle transition, but after that the kid
    should remain stuck in struggle until useful actions occur.
    """
    env = HybridEnvironment(config=EnvConfig())
    obs0, info0 = env.reset()  # noqa: F841
    state = env.state

    # Step 0: after reset
    assert state.scenario_stage == "birth"
    assert state.kid_posture == "fallen"
    assert state.mom_distance == "far"
    assert state.nipple_state == "hidden"
    assert state.step_index == 0

    def step_n(n: int):
        for _ in range(n):
            env.step(action=None, ctx=None)
        return env.state

    # After 3 steps we should enter struggle.
    s3 = step_n(3)
    assert s3.step_index == 3
    assert s3.scenario_stage == "struggle"
    assert s3.kid_posture == "fallen"
    assert s3.position == "cliff_edge"
    assert s3.zone == "unsafe"

    # Even much later, no-action should still leave the kid stuck in struggle.
    s16 = step_n(13)
    assert s16.step_index == 16
    assert s16.scenario_stage == "struggle"
    assert s16.kid_posture == "fallen"
    assert s16.mom_distance == "far"
    assert s16.nipple_state == "hidden"
    assert s16.position == "cliff_edge"
    assert s16.zone == "unsafe"
    assert s16.milestones == []


def test_perception_adapter_from_env_state_without_blackout():
    """
    A directly constructed EnvState at step_index=0 should NOT be blacked out unless
    blackout was explicitly requested.

    This test specifically guards against the bug where step_index=0 was coerced to -1
    and blackout activated unexpectedly.
    """
    state = EnvState(
        kid_posture="latched",
        mom_distance="near",
        nipple_state="latched",
        scenario_stage="first_latch",
        kid_position=(0.0, 0.0),
        mom_position=(0.5, 0.0),
        kid_temperature=0.30,
        time_since_birth=42.0,
        step_index=0,
        newborn_obs_blackout_until_step=-1,
        newborn_obs_blackout_kind="",
    )
    adapter = PerceptionAdapter()
    obs: EnvObservation = adapter.observe(state)

    # Predicates
    preds = set(obs.predicates)
    assert "posture:standing" in preds
    assert "proximity:mom:close" in preds
    assert "nipple:latched" in preds
    assert "milk:drinking" in preds

    # Cues
    cues = set(obs.cues)
    assert "vision:silhouette:mom" in cues
    assert "drive:cold_skin" in cues

    # Raw sensors
    assert "distance_to_mom" in obs.raw_sensors
    assert "kid_temperature" in obs.raw_sensors
    assert math.isclose(obs.raw_sensors["distance_to_mom"], 0.5, rel_tol=1e-6)

    # Meta
    assert obs.env_meta.get("scenario_stage") == "first_latch"
    assert obs.env_meta.get("time_since_birth") == 42.0
    assert "newborn_obs_blackout" not in obs.env_meta


def test_perception_adapter_explicit_blackout_suppresses_local_detail():
    """
    During an explicit blackout window, local relation/feeding detail should be hidden
    while posture remains visible.
    """
    state = EnvState(
        kid_posture="latched",
        mom_distance="near",
        nipple_state="latched",
        scenario_stage="first_latch",
        kid_position=(0.0, 0.0),
        mom_position=(0.5, 0.0),
        kid_temperature=0.30,
        step_index=5,
        newborn_obs_blackout_until_step=6,
        newborn_obs_blackout_kind="transition",
    )
    adapter = PerceptionAdapter()
    obs: EnvObservation = adapter.observe(state)

    preds = set(obs.predicates)
    cues = set(obs.cues)

    # Posture remains, but local feeding/proximity detail is hidden.
    assert "posture:standing" in preds
    assert "proximity:mom:close" not in preds
    assert "nipple:latched" not in preds
    assert "milk:drinking" not in preds

    assert "vision:silhouette:mom" not in cues
    assert "drive:cold_skin" not in cues

    assert obs.env_meta.get("newborn_obs_blackout") is True
    assert obs.env_meta.get("newborn_obs_blackout_kind") == "transition"