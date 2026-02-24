# -*- coding: utf-8 -*-
"""
Phase X — Step 13 tests: Grid → predicates v1

We test:
  1) Deterministic derivation of slot-families from a small SurfaceGrid fixture.
  2) Overwrite-by-slot-family behavior when applying derived slot-families onto MapSurface SELF.
  3) No cue leakage: we must not create any cue:* tags from derived facts.
"""

from __future__ import annotations

from cca8_navpatch import (
    SurfaceGridV1,
    CELL_UNKNOWN,
    CELL_HAZARD,
    CELL_GOAL,
    derive_grid_slot_families_v1,
)
from cca8_world_graph import WorldGraph
from cca8_run import wm_apply_grid_slot_families_to_mapsurface_v1


def test_derive_grid_slot_families_v1_hazard_and_goal_dir() -> None:
    w, h = 5, 5
    cells = [CELL_UNKNOWN] * (w * h)

    cx, cy = w // 2, h // 2

    # Put one hazard within r=2 of center and a goal to the east on the same row.
    cells[cy * w + (cx + 1)] = CELL_HAZARD
    cells[cy * w + (w - 1)] = CELL_GOAL

    grid = SurfaceGridV1(grid_w=w, grid_h=h, grid_cells=cells)
    slots = derive_grid_slot_families_v1(grid, r=2, include_goal_dir=True)

    assert slots.get("hazard:near") is True
    assert slots.get("goal:dir") == "E"


def test_wm_apply_grid_slot_families_overwrite_and_no_cues() -> None:
    ww = WorldGraph()
    self_bid = ww.add_predicate("dummy", attach=None)

    # Seed with an older goal dir plus a normal posture tag we must preserve.
    b = ww._bindings[self_bid]
    b.tags = ["pred:goal:dir:W", "pred:posture:standing"]

    slots = {"hazard:near": True, "terrain:traversable_near": False, "goal:dir": "E"}
    written = wm_apply_grid_slot_families_to_mapsurface_v1(ww, self_bid, slots)

    tags = set(getattr(ww._bindings[self_bid], "tags", []))

    # Preserved
    assert "pred:posture:standing" in tags

    # Overwritten goal dir
    assert "pred:goal:dir:W" not in tags
    assert "pred:goal:dir:E" in tags

    # Hazard derived tag added
    assert "pred:hazard:near" in tags

    # No cue leakage
    assert all(not t.startswith("cue:") for t in tags)

    # Return value should be a subset of the final tags.
    assert set(written).issubset(tags)