# tests/test_interoception_rising_edge.py
import cca8_world_graph as wg
from cca8_controller import Drives
from cca8_run import Ctx, _emit_interoceptive_cues

def _has_tag(world, full_tag: str) -> bool:
    return any(full_tag in (getattr(b, "tags", []) or []) for b in world._bindings.values())

def test_rising_edge_cues_written_once():
    world = wg.WorldGraph(); world.ensure_anchor("NOW")
    d = Drives()  # hunger=0.7, fatigue=0.2, warmth=0.6
    ctx = Ctx()

    started = _emit_interoceptive_cues(world, d, ctx, attach="latest")
    assert "drive:hunger_high" in started  # rising edge
    assert _has_tag(world, "cue:drive:hunger_high")  # cue node created

    # call again without changing drives → no new starts
    started2 = _emit_interoceptive_cues(world, d, ctx, attach="latest")
    assert started2 == set()
