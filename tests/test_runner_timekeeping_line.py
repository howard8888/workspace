"""Compact runner timekeeping-line tests."""

from __future__ import annotations

from cca8_run import Ctx, timekeeping_line


def test_timekeeping_line_formats_supported_counters() -> None:
    """The compact line should expose one explicit, non-vector counter set."""
    ctx = Ctx()
    ctx.controller_steps = 2
    ctx.ticks = 3
    ctx.age_days = 0.125
    ctx.cog_cycles = 1

    text = timekeeping_line(ctx)

    assert text == "cognitive_cycles=1, controller_steps=2, autonomic_ticks=3, age_days=0.1250"
    assert "epoch" not in text
    assert "cos" not in text
