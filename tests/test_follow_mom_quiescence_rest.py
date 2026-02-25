from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import cca8_world_graph
from cca8_controller import Drives
from cca8_run import (
    Ctx,
    init_body_world,
    update_body_world_from_obs,
    _gate_follow_mom_trigger_body_space,
)


@dataclass
class _Obs:
    predicates: List[str] = field(default_factory=list)
    cues: List[str] = field(default_factory=list)
    raw_sensors: Dict[str, Any] = field(default_factory=dict)
    nav_patches: List[Dict[str, Any]] = field(default_factory=list)
    env_meta: Dict[str, Any] = field(default_factory=dict)


def test_follow_mom_quiescent_when_resting_bodymap() -> None:
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.controller_steps = 0

    obs = _Obs(predicates=["resting"])
    update_body_world_from_obs(ctx, obs)

    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)

    assert _gate_follow_mom_trigger_body_space(world, drives, ctx) is False