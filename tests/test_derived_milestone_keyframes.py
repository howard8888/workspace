# -*- coding: utf-8 -*-
"""
Unit tests for derived milestone keyframe detection.

These tests exercise the env→world boundary hook in inject_obs_into_world(...):
we want a milestone keyframe when a goal-relevant outcome occurs (e.g., stood_up)
even if there is no stage/zone transition that would otherwise force a keyframe.

We keep this test intentionally small:
- Use WorldGraph + Ctx directly.
- Feed two EnvObservation packets that differ only in posture (fallen -> standing).
- Expect: second call returns keyframe=True and includes a milestone reason.
"""

from __future__ import annotations

import cca8_world_graph
from cca8_env import EnvObservation
from cca8_run import Ctx, inject_obs_into_world


def _mk_obs(preds: list[str], *, stage: str = "birth", tsb: float = 1.0, step_index: int = 1) -> EnvObservation:
    return EnvObservation(
        raw_sensors={},
        predicates=list(preds),
        cues=[],
        env_meta={
            "scenario_stage": stage,
            "time_since_birth": float(tsb),
            "step_index": int(step_index),
        },
    )


def test_derived_milestone_keyframe_stood_up() -> None:
    world = cca8_world_graph.WorldGraph()
    world.set_tag_policy("allow")
    world.set_stage("neonate")
    world.ensure_anchor("NOW")

    ctx = Ctx()
    ctx.longterm_obs_enabled = True
    ctx.longterm_obs_mode = "changes"

    # Turn OFF other keyframe triggers so only milestone logic can fire.
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_period_steps = 0
    ctx.longterm_obs_keyframe_on_pred_err = False

    # Turn ON milestone keyframes (this enables derived transitions too).
    ctx.longterm_obs_keyframe_on_milestone = True

    # First tick: establish baseline slots (no keyframe expected).
    obs1 = _mk_obs(
        ["posture:fallen", "proximity:mom:far", "proximity:shelter:far", "hazard:cliff:far"],
        stage="birth",
        tsb=1.0,
        step_index=1,
    )
    out1 = inject_obs_into_world(world, ctx, obs1)
    assert bool(out1.get("keyframe")) is False

    # Second tick: posture transition should trigger a milestone keyframe.
    obs2 = _mk_obs(
        ["posture:standing", "proximity:mom:far", "proximity:shelter:far", "hazard:cliff:far"],
        stage="birth",
        tsb=2.0,
        step_index=2,
    )
    out2 = inject_obs_into_world(world, ctx, obs2)

    assert bool(out2.get("keyframe")) is True
    reasons = out2.get("keyframe_reasons")
    assert isinstance(reasons, list)
    assert any(isinstance(r, str) and ("milestone:" in r) and ("stood_up" in r) for r in reasons)
