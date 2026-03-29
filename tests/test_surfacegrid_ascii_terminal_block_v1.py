# -*- coding: utf-8 -*-
"""
Focused regression test for SurfaceGrid terminal change detection.

This test is intentionally narrow:

- first call with a given wm_surfacegrid_last_ascii should print a full map block
- second call with the same ASCII should print the short unchanged marker

I monkeypatch the ASCII formatter so the test stays deterministic and does not depend
on the exact framing/legend implementation of format_surfacegrid_ascii_map_v1(...).
"""

import cca8_run as runmod


def test_surfacegrid_ascii_terminal_block_prints_full_map_then_unchanged(monkeypatch):
    """The helper should print the full map once, then collapse identical repeats."""

    def fake_format_surfacegrid_ascii_map_v1(ascii_txt, title=None, legend=None, show_axes=True):
        _ = title
        _ = legend
        _ = show_axes
        return f"FORMATTED<{ascii_txt}>"

    monkeypatch.setattr(
        runmod,
        "format_surfacegrid_ascii_map_v1",
        fake_format_surfacegrid_ascii_map_v1,
    )

    ctx = runmod.Ctx()
    ctx.wm_surfacegrid_last_ascii = "@\n"
    ctx.wm_surfacegrid_last_printed_ascii = None
    ctx.wm_surfacegrid_ascii_each_tick = False

    first = runmod._surfacegrid_ascii_terminal_block_v1(
        ctx,
        None,
        sig16="abc123",
        line_prefix="[cycle] SG   ",
        title="WM.SurfaceGrid (sig16=abc123)",
        legend="legend",
    )

    assert first == "[cycle] SG   map:\nFORMATTED<@\n>"
    assert ctx.wm_surfacegrid_last_printed_ascii == "@\n"

    second = runmod._surfacegrid_ascii_terminal_block_v1(
        ctx,
        None,
        sig16="abc123",
        line_prefix="[cycle] SG   ",
        title="WM.SurfaceGrid (sig16=abc123)",
        legend="legend",
    )

    assert second == "[cycle] SG   ++SurfaceGrid ASCII Map is unchanged++"
    assert ctx.wm_surfacegrid_last_printed_ascii == "@\n"
    
    
def test_surfacegrid_ascii_terminal_block_suppresses_visually_identical_maps(monkeypatch):
    """Whitespace-only raw ascii differences should not force a visible reprint."""

    ascii_values = iter(["@   \n", "@\n"])

    def fake_surfacegrid_ascii_text_v1(ctx, sg):
        _ = ctx
        _ = sg
        return next(ascii_values)

    def fake_format_surfacegrid_ascii_map_v1(ascii_txt, title=None, legend=None, show_axes=True):
        _ = title
        _ = legend
        _ = show_axes
        norm = "\n".join(line.rstrip() for line in ascii_txt.splitlines()).strip()
        return f"FORMATTED<{norm}>"

    monkeypatch.setattr(runmod, "_surfacegrid_ascii_text_v1", fake_surfacegrid_ascii_text_v1)
    monkeypatch.setattr(runmod, "format_surfacegrid_ascii_map_v1", fake_format_surfacegrid_ascii_map_v1)

    ctx = runmod.Ctx()
    ctx.wm_surfacegrid_last_printed_ascii = None
    ctx.wm_surfacegrid_last_printed_block = None
    ctx.wm_surfacegrid_ascii_each_tick = False

    first = runmod._surfacegrid_ascii_terminal_block_v1(
        ctx,
        None,
        sig16="abc123",
        line_prefix="[cycle] SG   ",
        title="WM.SurfaceGrid (sig16=abc123)",
        legend="legend",
    )

    assert first == "[cycle] SG   map:\nFORMATTED<@>"
    assert ctx.wm_surfacegrid_last_printed_block == "FORMATTED<@>"

    second = runmod._surfacegrid_ascii_terminal_block_v1(
        ctx,
        None,
        sig16="abc123",
        line_prefix="[cycle] SG   ",
        title="WM.SurfaceGrid (sig16=abc123)",
        legend="legend",
    )

    assert second == "[cycle] SG   ++SurfaceGrid ASCII Map is unchanged++"
    assert ctx.wm_surfacegrid_last_printed_block == "FORMATTED<@>"