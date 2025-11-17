# tests/test_runner_timekeeping_line.py
from cca8_run import Ctx, timekeeping_line

def test_timekeeping_line_formats_without_temporal():
    ctx = Ctx()
    ctx.controller_steps = 2
    ctx.boundary_no = 1
    ctx.ticks = 0
    ctx.age_days = 0.0
    ctx.cog_cycles = 1
    s = timekeeping_line(ctx)
    assert "controller_steps=2" in s
    assert "temporal_epochs=1" in s
    assert "autonomic_ticks=0" in s
    assert "age_days=0.0000" in s
    assert "cog_cycles=1" in s
    # no TemporalContext → cos is (n/a)
    assert "cos_to_last_boundary=(n/a)" in s
