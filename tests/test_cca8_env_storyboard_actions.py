# tests/test_cca8_env_storyboard_actions.py
# Action-focused tests for the hardened newborn-goat storyboard.

from cca8_env import EnvState, EnvConfig, FsmBackend, PerceptionAdapter, HybridEnvironment


def _newborn_env() -> HybridEnvironment:
    env = HybridEnvironment(config=EnvConfig(scenario_name="newborn_goat_first_hour"))
    env.reset()
    return env


def test_fsm_follow_then_stand_transitions_to_first_stand():
    """
    In the hardened B2 environment, useful action sequencing matters.

    One practical recovery route is:
      birth -> struggle -> follow_mom (move off cliff / bring mom near) -> stand_up
    """
    env = _newborn_env()

    # Reach struggle
    for _ in range(3):
        env.step(action=None, ctx=None)

    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"
    assert env.state.position == "cliff_edge"
    assert env.state.zone == "unsafe"

    # Move toward mom / safer terrain first
    env.step(action="policy:follow_mom", ctx=None)
    assert env.state.scenario_stage == "struggle"
    assert env.state.mom_distance == "near"
    assert env.state.position == "open_field"
    assert env.state.zone == "neutral"

    # Then stand successfully
    env.step(action="policy:stand_up", ctx=None)
    assert env.state.scenario_stage == "first_stand"
    assert env.state.kid_posture == "standing"
    assert "stood_up" in env.state.milestones
    assert "reached_mom" in env.state.milestones


def test_fsm_two_stand_attempts_work_even_without_follow_mom():
    """
    Standing from the exposed cliff-edge route is harder and should require two
    stand attempts when the kid has not first moved to open_field/shelter_area.
    """
    env = _newborn_env()

    for _ in range(3):
        env.step(action=None, ctx=None)

    env.step(action="policy:stand_up", ctx=None)
    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"
    assert env.state.newborn_stand_attempts == 1

    env.step(action="policy:stand_up", ctx=None)
    assert env.state.scenario_stage == "first_stand"
    assert env.state.kid_posture == "standing"
    assert env.state.mom_distance == "far"


def test_fsm_two_seek_actions_reach_first_latch_after_reaching_mom():
    """
    After recovery and reaching mom, the first seek finds the nipple and the
    second seek latches.
    """
    env = _newborn_env()

    for action in [None, None, None, "policy:follow_mom", "policy:stand_up"]:
        env.step(action=action, ctx=None)

    assert env.state.scenario_stage == "first_stand"
    assert env.state.mom_distance == "near"

    env.step(action="policy:seek_nipple", ctx=None)
    assert env.state.scenario_stage == "first_stand"
    assert env.state.nipple_state == "reachable"
    assert "found_nipple" in env.state.milestones

    env.step(action="policy:seek_nipple", ctx=None)
    assert env.state.scenario_stage == "first_latch"
    assert env.state.kid_posture == "latched"
    assert env.state.nipple_state == "latched"
    assert "latched_nipple" in env.state.milestones


def test_fsm_seek_without_mom_near_causes_setback():
    """
    Seeking before the mother is reachable should produce a setback.
    """
    env = _newborn_env()

    # Reach struggle, then stand without following mom first.
    for _ in range(3):
        env.step(action=None, ctx=None)

    env.step(action="policy:stand_up", ctx=None)
    env.step(action="policy:stand_up", ctx=None)

    assert env.state.scenario_stage == "first_stand"
    assert env.state.mom_distance == "far"

    env.step(action="policy:seek_nipple", ctx=None)
    assert env.state.scenario_stage == "struggle"
    assert env.state.kid_posture == "fallen"
    assert env.state.nipple_state == "hidden"
    assert env.state.newborn_setback_count >= 1


def test_rest_requires_milk_ticks_and_safe_zone():
    """
    Rest should not complete immediately after latching. The kid needs enough
    milk ticks first, and resting should complete only from the safe niche.
    """
    env = _newborn_env()

    for action in [None, None, None, "policy:follow_mom", "policy:stand_up", "policy:seek_nipple", "policy:seek_nipple"]:
        env.step(action=action, ctx=None)

    assert env.state.scenario_stage == "first_latch"
    assert env.state.position == "shelter_area"
    assert env.state.zone == "safe"

    # Too early: still not enough milk ticks
    env.step(action="policy:rest", ctx=None)
    assert env.state.scenario_stage == "first_latch"
    assert env.state.kid_posture == "latched"

    # One neutral tick lets milk accumulate
    env.step(action=None, ctx=None)

    # Now rest can complete
    env.step(action="policy:rest", ctx=None)
    assert env.state.scenario_stage == "rest"
    assert env.state.kid_posture == "resting"
    assert env.state.zone == "safe"
    assert env.state.mom_distance == "touching"


def test_perception_adapter_mapping_posture_and_cues_without_blackout():
    """
    Regression guard for the step_index=0 blackout bug.
    """
    state = EnvState(
        kid_posture="latched",
        mom_distance="near",
        nipple_state="latched",
        scenario_stage="first_latch",
        kid_position=(0.0, 0.0),
        mom_position=(0.5, 0.0),
        kid_temperature=0.30,
        step_index=0,
        newborn_obs_blackout_until_step=-1,
        newborn_obs_blackout_kind="",
    )
    obs = PerceptionAdapter().observe(state)

    preds = set(obs.predicates)
    cues = set(obs.cues)

    assert "posture:standing" in preds
    assert "proximity:mom:close" in preds
    assert "nipple:latched" in preds
    assert "milk:drinking" in preds
    assert "vision:silhouette:mom" in cues
    assert "drive:cold_skin" in cues


def test_legacy_storyboard_threshold_constants_remain_available():
    """
    Keep a tiny compatibility guard so older docs/tests referring to the old
    threshold names do not crash with AttributeError.
    """
    backend = FsmBackend()
    assert backend._STRUGGLE_MOM_NEAR == 5
    assert backend._AUTO_STAND_UP == 8
    assert backend._AUTO_NIPPLE_REACHABLE == 11
    assert backend._AUTO_LATCH == 13
    assert backend._AUTO_REST == 16