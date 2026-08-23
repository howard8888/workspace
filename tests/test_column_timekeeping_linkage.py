"""Column engrams retain explicit CCA8 runtime-ordering metadata."""

from __future__ import annotations

import cca8_world_graph as wgmod
from cca8_features import time_attrs_from_ctx
from cca8_run import Ctx


def test_engram_carries_explicit_runtime_time_attrs() -> None:
    """The WorldGraph-to-Column bridge should preserve all supported counters."""
    world = wgmod.WorldGraph()
    ctx = Ctx()
    ctx.cog_cycles = 4
    ctx.controller_steps = 9
    ctx.ticks = 2
    ctx.age_days = 0.125

    attrs = time_attrs_from_ctx(ctx)
    _bid, eid = world.capture_scene(
        "vision",
        "silhouette:mom",
        [0.1, 0.2, 0.3],
        attach="now",
        family="cue",
        attrs=attrs,
    )
    record = world.get_engram(engram_id=eid)
    stored_attrs = record["meta"]["attrs"]

    assert stored_attrs["cognitive_cycle"] == 4
    assert stored_attrs["controller_step"] == 9
    assert stored_attrs["autonomic_tick"] == 2
    assert stored_attrs["age_days"] == 0.125
    assert "tvec64" not in stored_attrs
    assert "epoch" not in stored_attrs
