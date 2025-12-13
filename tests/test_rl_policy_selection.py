import cca8_controller as ctrl
import cca8_world_graph as wg
import cca8_run as run


def test_rl_tiebreak_prefers_higher_q_when_enabled():
    """When RL is enabled, use SkillStat.q as a secondary tie-break.

    Setup a state where both SeekNipple and Rest are triggered and their
    drive-deficit scores tie. With rl_enabled=True and epsilon=0, the
    Action Center should prefer the policy with the higher learned q.
    """
    ctrl.reset_skills()
    ctrl.SKILLS["policy:rest"] = ctrl.SkillStat(n=10, succ=10, q=0.90, last_reward=0.2)
    ctrl.SKILLS["policy:seek_nipple"] = ctrl.SkillStat(n=10, succ=10, q=0.10, last_reward=0.5)

    world = wg.WorldGraph()
    world.add_predicate("posture:standing", attach="now")

    # Choose hunger/fatigue so their deficit formulas tie:
    #   hunger_deficit = hunger - 0.60
    #   fatigue_deficit = (fatigue - 0.70) * 0.70
    # Let fatigue=0.90 → fatigue_deficit=0.14, so hunger=0.74.
    drives = ctrl.Drives(hunger=0.74, fatigue=0.90, warmth=0.60)

    ctx = run.Ctx()
    ctx.rl_enabled = True
    ctx.rl_epsilon = 0.0

    out = ctrl.action_center_step(world, ctx, drives)
    assert out["policy"] == "policy:rest"
