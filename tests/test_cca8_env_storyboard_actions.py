import math

from cca8_env import EnvState, EnvConfig, FsmBackend, PerceptionAdapter, HybridEnvironment, EnvObservation


def test_fsm_stand_up_action_accelerates_transition() -> None:
    """FsmBackend.step should treat 'policy:stand_up' as an accelerator in 'struggle'.

    Without the action, standing only happens at or after _AUTO_STAND_UP.
    With the action, we should stand up immediately and move to 'first_stand'.
    """
    fsm = FsmBackend()
    cfg = EnvConfig()
    state = EnvState()
    fsm.reset(state, cfg)

    # Pretend we are already in 'struggle' just before the auto stand-up threshold.
    state.scenario_stage = "struggle"
    state.step_index = fsm._AUTO_STAND_UP - 1  # one step before auto-stand
    state.kid_posture = "fallen"
    assert state.kid_posture == "fallen"

    # Apply an explicit stand-up action
    out = fsm.step(state, action="policy:stand_up", ctx=None)

    assert out is state  # mutated in-place
    assert out.scenario_stage == "first_stand"
    assert out.kid_posture == "standing"


def test_fsm_seek_nipple_accelerates_latch() -> None:
    """FsmBackend.step should treat 'policy:seek_nipple' as an accelerator in 'first_stand'.

    With nipple_state='hidden' and step_index below AUTO_NIPPLE_REACHABLE,
    a seek_nipple action should drive the kid all the way to first_latch/latched.
    """
    fsm = FsmBackend()
    cfg = EnvConfig()
    state = EnvState()
    fsm.reset(state, cfg)

    state.scenario_stage = "first_stand"
    state.nipple_state = "hidden"
    # Just before auto nipple reachable; the action should accelerate.
    state.step_index = fsm._AUTO_NIPPLE_REACHABLE - 1

    out = fsm.step(state, action="policy:seek_nipple", ctx=None)

    assert out.scenario_stage == "first_latch"
    assert out.kid_posture == "latched"
    assert out.nipple_state == "latched"


def test_perception_adapter_mapping_posture_and_cues() -> None:
    """PerceptionAdapter.observe should map EnvState to a consistent EnvObservation."""
    state = EnvState(
        kid_posture="latched",         # will be mapped to posture:standing + feeding preds
        mom_distance="near",           # → proximity:mom:close
        nipple_state="latched",        # → nipple:latched / milk:drinking
    )
    adapter = PerceptionAdapter()
    obs = adapter.observe(state)
    assert isinstance(obs, EnvObservation)

    preds = set(obs.predicates)
    cues = set(obs.cues)

    # Latched posture is reported as posture:standing in the observation space.
    assert "posture:standing" in preds
    # Proximity and feeding predicates.
    assert "proximity:mom:close" in preds
    assert "nipple:latched" in preds
    assert "milk:drinking" in preds
    # Mom near should emit a visual cue.
    assert "vision:silhouette:mom" in cues


def test_hybridenvironment_step_shape_and_timebookkeeping() -> None:
    """HybridEnvironment.reset/step must produce the expected RL-shaped outputs.

    We only assert the shape and simple time bookkeeping; reward/done are stubs.
    """
    env = HybridEnvironment()
    obs0, info0 = env.reset()
    assert isinstance(obs0, EnvObservation)
    assert info0.get("episode_index") == env.episode_index

    # One step with a dummy action/ctx; RL slots are stubbed for now.
    obs1, reward, done, info1 = env.step(action=None, ctx=None)
    assert isinstance(obs1, EnvObservation)
    assert isinstance(reward, float)
    assert reward == 0.0
    assert done is False

    # Episode index should be stable; step index should advance.
    assert info1.get("episode_index") == info0.get("episode_index")
    assert info1.get("step_index") == env.episode_steps == 1
    assert env.state.step_index == 1
    # time_since_birth should have increased by dt
    assert math.isclose(env.state.time_since_birth, env.config.dt, rel_tol=1e-9)
