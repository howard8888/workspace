# tests/test_cca8_env.py
# Basic unit tests for cca8_env.EnvState / EnvObservation / HybridEnvironment / PerceptionAdapter
#
# These tests are intentionally small and deterministic:
#   1) Storyboard progression: HybridEnvironment + FsmBackend without actions.
#   2) PerceptionAdapter: mapping EnvState → EnvObservation predicates/cues.

import math

from cca8_env import (
    EnvState,
    EnvObservation,
    EnvConfig,
    FsmBackend,
    PerceptionAdapter,
    HybridEnvironment,
)


def test_storyboard_sequence_no_actions():
    """
    HybridEnvironment + FsmBackend should walk through the newborn-goat storyboard
    with default thresholds when no actions are provided.

    We check a few key milestones only, to keep the test robust to minor cosmetic changes:

      - step 0 (after reset):  stage = birth, posture = fallen, mom_distance = far
      - step 3:               stage = struggle
      - step 5:               mom_distance = near
      - step 8:               stage = first_stand, posture = standing
      - step 11:              nipple_state = reachable
      - step 13:              stage = first_latch, nipple_state = latched
      - step 16:              stage = rest, posture = resting, mom_distance = touching
    """
    env = HybridEnvironment(config=EnvConfig())
    obs0, info0 = env.reset()  # noqa: F841  # obs not used directly
    state = env.state

    # Step 0: after reset
    assert state.scenario_stage == "birth"
    assert state.kid_posture == "fallen"
    assert state.mom_distance == "far"
    assert state.nipple_state == "hidden"
    assert state.step_index == 0

    # Helper: advance N steps with action=None
    def step_n(n: int):
        for _ in range(n):
            env.step(action=None, ctx=None)
        return env.state

    # After 3 steps → struggle
    s3 = step_n(3)
    assert s3.step_index == 3
    assert s3.scenario_stage == "struggle"
    assert s3.kid_posture == "fallen"

    # After 2 more (5 total) → mom near
    s5 = step_n(2)
    assert s5.step_index == 5
    assert s5.scenario_stage == "struggle"
    assert s5.mom_distance == "near"

    # After 3 more (8 total) → first_stand
    s8 = step_n(3)
    assert s8.step_index == 8
    assert s8.scenario_stage == "first_stand"
    assert s8.kid_posture == "standing"
    assert s8.mom_distance == "near"

    # After 3 more (11 total) → nipple reachable / found
    s11 = step_n(3)
    assert s11.step_index == 11
    assert s11.scenario_stage == "first_stand"
    assert s11.nipple_state == "reachable"

    # After 2 more (13 total) → first_latch, latched
    s13 = step_n(2)
    assert s13.step_index == 13
    assert s13.scenario_stage == "first_latch"
    assert s13.nipple_state == "latched"

    # After 3 more (16 total) → rest, touching
    s16 = step_n(3)
    assert s16.step_index == 16
    assert s16.scenario_stage == "rest"
    assert s16.kid_posture == "resting"
    assert s16.mom_distance == "touching"


def test_perception_adapter_from_env_state():
    """
    PerceptionAdapter.observe should produce sensible predicates/cues from a given EnvState.

    Scenario:
      - posture = latched
      - mom_distance = near
      - nipple_state = latched
      - kid_temperature low enough to trigger drive:cold_skin

    We expect:
      - predicates include:
          posture:standing (latched implies upright),
          proximity:mom:close,
          nipple:latched,
          milk:drinking
      - cues include:
          vision:silhouette:mom,
          drive:cold_skin
      - raw_sensors contains distance_to_mom and kid_temperature.
      - env_meta includes scenario_stage and time_since_birth.
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
