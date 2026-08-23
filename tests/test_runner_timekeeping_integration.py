"""Integration tests for CCA8's explicit timekeeping contract."""

from __future__ import annotations

import cca8_world_graph as wgmod
from cca8_controller import Drives, action_center_step
from cca8_run import Ctx, snapshot_text


def test_snapshot_exposes_explicit_timekeeping_without_vector_clock() -> None:
    """Snapshots should name the supported counters and omit retired vector-clock terms."""
    world = wgmod.WorldGraph()
    ctx = Ctx()
    ctx.cog_cycles = 3
    ctx.controller_steps = 5
    ctx.ticks = 2
    ctx.age_days = 0.5

    text = snapshot_text(world, drives=None, ctx=ctx, policy_rt=None)

    assert "TIMEKEEPING:" in text
    assert "cognitive_cycles=3" in text
    assert "controller_steps=5" in text
    assert "autonomic_ticks=2" in text
    assert "age_days=0.5000" in text
    assert "tvec64" not in text
    assert "cos_to_last_boundary" not in text


def test_policy_write_stamps_explicit_ordering_metadata() -> None:
    """Policy-created bindings should identify their cycle, controller step, and heartbeat."""
    world = wgmod.WorldGraph()
    ctx = Ctx()
    ctx.cog_cycles = 8
    ctx.controller_steps = 13
    ctx.ticks = 4
    ctx.age_days = 0.75

    before = set(world._bindings)  # pylint: disable=protected-access
    result = action_center_step(world, ctx, Drives())
    created = set(world._bindings) - before  # pylint: disable=protected-access

    assert isinstance(result, dict) and result.get("status") == "ok"
    assert created
    metadata = [world._bindings[bid].meta for bid in created]  # pylint: disable=protected-access
    assert any(
        row.get("cognitive_cycle") == 8
        and row.get("controller_step") == 13
        and row.get("autonomic_tick") == 4
        and row.get("age_days") == 0.75
        for row in metadata
    )
    assert all("tvec64" not in row and "epoch" not in row for row in metadata)


def test_ctx_does_not_expose_retired_vector_clock_state() -> None:
    """The mutable runtime context should not retain an unused second clock."""
    ctx = Ctx()

    for name in (
        "temporal",
        "tvec_last_boundary",
        "boundary_no",
        "boundary_vhash64",
        "tvec64",
        "cos_to_last_boundary",
        "sigma",
        "jump",
    ):
        assert not hasattr(ctx, name)
