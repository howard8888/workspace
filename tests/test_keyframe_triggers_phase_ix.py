import cca8_world_graph
from cca8_run import Ctx, inject_obs_into_world


class _ObsStub:
    def __init__(self, *, predicates, cues=None, env_meta=None):
        self.predicates = list(predicates or [])
        self.cues = list(cues or [])
        self.env_meta = dict(env_meta or {})


def _mk_world():
    w = cca8_world_graph.WorldGraph()
    w.set_tag_policy("allow")
    w.ensure_anchor("NOW")
    return w


def test_keyframe_zone_change_triggers_in_changes_mode():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_keyframe_on_zone_change = True
    ctx.longterm_obs_keyframe_on_stage_change = False  # isolate
    ctx.longterm_obs_keyframe_period_steps = 0
    ctx.longterm_obs_keyframe_on_pred_err = False
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False

    obs1 = _ObsStub(
        predicates=["posture:standing", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )
    r1 = inject_obs_into_world(w, ctx, obs1)
    assert not r1.get("keyframe", False)

    obs2 = _ObsStub(
        predicates=["posture:standing", "proximity:shelter:far", "hazard:cliff:near"],
        env_meta={"scenario_stage": "x", "time_since_birth": 2.0},
    )
    r2 = inject_obs_into_world(w, ctx, obs2)
    assert r2.get("keyframe", False)
    assert any("zone_change" in str(x) for x in (r2.get("keyframe_reasons") or []))


def test_keyframe_periodic_triggers():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_period_steps = 3
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False
    ctx.longterm_obs_keyframe_on_pred_err = False

    obs = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )

    ctx.controller_steps = 1
    r1 = inject_obs_into_world(w, ctx, obs)
    assert not r1.get("keyframe", False)

    ctx.controller_steps = 2
    r2 = inject_obs_into_world(w, ctx, obs)
    assert not r2.get("keyframe", False)

    ctx.controller_steps = 3
    r3 = inject_obs_into_world(w, ctx, obs)
    assert r3.get("keyframe", False)
    assert any("periodic(" in str(x) for x in (r3.get("keyframe_reasons") or []))


def test_keyframe_periodic_resets_on_any_keyframe_when_enabled():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"

    # isolate keyframe sources
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_on_pred_err = False
    ctx.longterm_obs_keyframe_on_emotion = False

    # periodic + milestone
    ctx.longterm_obs_keyframe_period_steps = 3
    ctx.longterm_obs_keyframe_period_reset_on_any_keyframe = True
    ctx.longterm_obs_keyframe_on_milestone = True

    # Step 1: no keyframe
    obs1 = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )
    ctx.controller_steps = 1
    r1 = inject_obs_into_world(w, ctx, obs1)
    assert not r1.get("keyframe", False)

    # Step 2: milestone keyframe happens -> should reset periodic counter
    obs2 = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 2.0, "milestones": ["stood_up"]},
    )
    ctx.controller_steps = 2
    r2 = inject_obs_into_world(w, ctx, obs2)
    assert r2.get("keyframe", False)
    assert any("milestone:" in str(x) for x in (r2.get("keyframe_reasons") or []))

    # Step 3: would have been periodic under legacy (3 % 3 == 0),
    # but in reset-on-any-keyframe mode it should NOT fire (3-2 < 3).
    obs3 = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 3.0},
    )
    ctx.controller_steps = 3
    r3 = inject_obs_into_world(w, ctx, obs3)
    assert not r3.get("keyframe", False)

    # Step 5: now (5-2 == 3) periodic should fire
    obs5 = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 5.0},
    )
    ctx.controller_steps = 5
    r5 = inject_obs_into_world(w, ctx, obs5)
    assert r5.get("keyframe", False)
    assert any("periodic(" in str(x) for x in (r5.get("keyframe_reasons") or []))


def test_keyframe_pred_err_streak_triggers():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_period_steps = 0
    ctx.longterm_obs_keyframe_on_pred_err = True
    ctx.longterm_obs_keyframe_pred_err_min_streak = 2
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False

    obs = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )

    ctx.controller_steps = 1
    ctx.pred_err_v0_last = {"posture": 1}
    r1 = inject_obs_into_world(w, ctx, obs)
    assert not r1.get("keyframe", False)

    ctx.controller_steps = 2
    ctx.pred_err_v0_last = {"posture": 1}
    r2 = inject_obs_into_world(w, ctx, obs)
    assert r2.get("keyframe", False)
    assert any("pred_err_v0" in str(x) for x in (r2.get("keyframe_reasons") or []))


def test_keyframe_milestone_stub_triggers_when_enabled():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_on_milestone = True
    ctx.longterm_obs_keyframe_on_emotion = False

    obs = _ObsStub(
        predicates=["posture:standing", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0, "milestones": ["stood_up"]},
    )
    r = inject_obs_into_world(w, ctx, obs)
    assert r.get("keyframe", False)
    assert any("milestone:" in str(x) for x in (r.get("keyframe_reasons") or []))


def test_keyframe_emotion_stub_triggers_when_enabled():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_on_emotion = True
    ctx.longterm_obs_keyframe_emotion_threshold = 0.85

    obs = _ObsStub(
        predicates=["posture:standing", "proximity:shelter:far", "hazard:cliff:far"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0, "emotion": {"label": "fear", "intensity": 0.95}},
    )
    r = inject_obs_into_world(w, ctx, obs)
    assert r.get("keyframe", False)
    assert any("emotion:" in str(x) for x in (r.get("keyframe_reasons") or []))


def test_keyframe_periodic_suppressed_while_sleeping_nondreaming():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"

    # isolate: only periodic is relevant here
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_on_pred_err = False
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False

    ctx.longterm_obs_keyframe_period_steps = 3
    ctx.longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming = True
    ctx.longterm_obs_keyframe_period_suppress_when_sleeping_dreaming = False

    obs = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far", "sleeping:non_dreaming"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )

    ctx.controller_steps = 1
    r1 = inject_obs_into_world(w, ctx, obs)
    assert not r1.get("keyframe", False)

    ctx.controller_steps = 2
    r2 = inject_obs_into_world(w, ctx, obs)
    assert not r2.get("keyframe", False)

    # Would normally fire periodic here, but should be suppressed
    ctx.controller_steps = 3
    r3 = inject_obs_into_world(w, ctx, obs)
    assert not r3.get("keyframe", False)


def test_keyframe_periodic_suppressed_while_sleeping_dreaming():
    w = _mk_world()
    ctx = Ctx()
    ctx.longterm_obs_mode = "changes"

    # isolate: only periodic is relevant here
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_on_pred_err = False
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False

    ctx.longterm_obs_keyframe_period_steps = 3
    ctx.longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming = False
    ctx.longterm_obs_keyframe_period_suppress_when_sleeping_dreaming = True

    obs = _ObsStub(
        predicates=["posture:fallen", "proximity:shelter:far", "hazard:cliff:far", "sleeping:dreaming"],
        env_meta={"scenario_stage": "x", "time_since_birth": 1.0},
    )

    ctx.controller_steps = 1
    r1 = inject_obs_into_world(w, ctx, obs)
    assert not r1.get("keyframe", False)

    ctx.controller_steps = 2
    r2 = inject_obs_into_world(w, ctx, obs)
    assert not r2.get("keyframe", False)

    # Would normally fire periodic here, but should be suppressed
    ctx.controller_steps = 3
    r3 = inject_obs_into_world(w, ctx, obs)
    assert not r3.get("keyframe", False)
