from types import SimpleNamespace

import pytest

import cca8_world_graph
from cca8_controller import Drives
from cca8_run import (
    _drive_tags,
    _emit_interoceptive_cues,
    timekeeping_line,
    Ctx,
    _io_banner,
)

def test_drive_tags_thresholds():
    d = Drives(hunger=0.7, fatigue=0.8, warmth=0.2)
    tags = set(_drive_tags(d))
    assert "drive:hunger_high" in tags
    assert "drive:fatigue_high" in tags
    assert "drive:cold" in tags

def test_emit_interoceptive_cues_rising_edge_and_binding_creation():
    w = cca8_world_graph.WorldGraph()
    w.ensure_anchor("NOW")
    ctx = Ctx()
    d = Drives(hunger=0.7, fatigue=0.2, warmth=0.6)

    # First call: rising-edge for hunger_high
    started1 = _emit_interoceptive_cues(w, d, ctx, attach="now")
    assert "drive:hunger_high" in started1
    assert "drive:hunger_high" in (ctx.last_drive_flags or set())

    # There should be a cue binding with cue:drive:hunger_high
    has_cue = any(
        any(t == "cue:drive:hunger_high" for t in getattr(b, "tags", []))
        for b in w._bindings.values()
    )
    assert has_cue

    # Second call with same drives: no new rising-edge flags
    started2 = _emit_interoceptive_cues(w, d, ctx, attach="now")
    assert started2 == set()

def test_timekeeping_line_basic_fields():
    ctx = Ctx()
    line = timekeeping_line(ctx)
    assert "controller_steps=" in line
    assert "temporal_epochs=" in line
    assert "autonomic_ticks=" in line
    assert "age_days=" in line
    assert "cog_cycles=" in line

def test_io_banner_loaded_with_autosave_same_file(capsys):
    args = SimpleNamespace(autosave="session.json")
    _io_banner(args, "session.json", True)
    out = capsys.readouterr().out
    assert "Loaded 'session.json'" in out
    assert "Autosave ON to the same file" in out


def test_io_banner_loaded_with_autosave_different_file(capsys):
    args = SimpleNamespace(autosave="new_session.json")
    _io_banner(args, "old_session.json", True)
    out = capsys.readouterr().out
    assert "Loaded 'old_session.json'" in out
    assert "Autosave ON to 'new_session.json'" in out
    assert "original load file remains unchanged" in out


def test_io_banner_new_session_autosave_on_and_off(capsys):
    # autosave ON, no loaded_path
    args_on = SimpleNamespace(autosave="session.json")
    _io_banner(args_on, None, False)
    out_on = capsys.readouterr().out
    assert "Started a NEW session. Autosave ON to 'session.json'." in out_on

    # autosave OFF, no loaded_path
    args_off = SimpleNamespace(autosave=None)
    _io_banner(args_off, None, False)
    out_off = capsys.readouterr().out
    assert "Started a NEW session. Autosave OFF" in out_off
