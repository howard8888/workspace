"""Snapshot coverage for explicit timekeeping and compact engram pointers."""

from __future__ import annotations

import re

import cca8_world_graph as wg
from cca8_run import Ctx, snapshot_text


def test_snapshot_shows_timekeeping_legend_and_short_engram_id() -> None:
    """The diagnostic snapshot should explain counters and render compact engram pointers."""
    world = wg.WorldGraph()
    world.ensure_anchor("NOW")
    ctx = Ctx()
    ctx.cog_cycles = 1
    ctx.controller_steps = 1

    world.capture_scene("vision", "silhouette:mom", [0.1, 0.2, 0.3], attach="now", family="cue")
    text = snapshot_text(world, drives=None, ctx=ctx, policy_rt=None)

    assert "LEGEND (timekeeping terms):" in text
    assert "TIMEKEEPING:" in text
    assert "cognitive_cycles=1" in text
    assert "controller_steps=1" in text
    assert re.search(r"\bb\d+:\s*\[.*\]\s*engrams=\[(?:column01(?::[0-9a-f]{8}…)?)]", text)
    assert "POLICIES ELIGIBLE" in text
    assert "tvec64" not in text
