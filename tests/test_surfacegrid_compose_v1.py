# -*- coding: utf-8 -*-
"""
SurfaceGrid compose v1 tests (Phase X Step 12)

These tests focus on:
  1) deterministic composition regardless of patch order
  2) overlay priority (hazard wins over traversable in overlaps)
  3) stable ASCII rendering
"""

from __future__ import annotations

from cca8_navpatch import (
    GRID_ENCODING_V1,
    CELL_UNKNOWN,
    CELL_TRAVERSABLE,
    CELL_HAZARD,
    CELL_GOAL,
    compose_surfacegrid_v1,
)


def _blank(w: int, h: int, code: int = CELL_UNKNOWN) -> list[int]:
    return [int(code)] * (int(w) * int(h))


def _mk_patch(cells: list[int], *, w: int, h: int, entity_id: str, role: str) -> dict:
    return {
        "schema": "navpatch_v1",
        "local_id": f"p_{entity_id}",
        "entity_id": entity_id,
        "role": role,
        "frame": "ego_schematic_v1",
        "grid_encoding_v": GRID_ENCODING_V1,
        "grid_w": int(w),
        "grid_h": int(h),
        "grid_cells": list(cells),
        "tags": [],
        "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
    }


def test_surfacegrid_compose_deterministic_order() -> None:
    w, h = 4, 4
    a = _blank(w, h)
    b = _blank(w, h)
    a[0] = CELL_GOAL
    b[1] = CELL_TRAVERSABLE

    p1 = _mk_patch(a, w=w, h=h, entity_id="scene", role="scene")
    p2 = _mk_patch(b, w=w, h=h, entity_id="cliff", role="hazard")

    g_ab = compose_surfacegrid_v1([p1, p2], grid_w=w, grid_h=h)
    g_ba = compose_surfacegrid_v1([p2, p1], grid_w=w, grid_h=h)

    assert g_ab.grid_cells == g_ba.grid_cells
    assert g_ab.sig16_v1() == g_ba.sig16_v1()


def test_surfacegrid_compose_overlay_priority_hazard_wins() -> None:
    w, h = 3, 3
    a = _blank(w, h)
    b = _blank(w, h)
    a[0] = CELL_TRAVERSABLE
    b[0] = CELL_HAZARD

    p_tr = _mk_patch(a, w=w, h=h, entity_id="terrain", role="scene")
    p_hz = _mk_patch(b, w=w, h=h, entity_id="cliff", role="hazard")

    g = compose_surfacegrid_v1([p_tr, p_hz], grid_w=w, grid_h=h)
    assert g.grid_cells[0] == CELL_HAZARD


def test_surfacegrid_ascii_render_v1() -> None:
    w, h = 3, 2
    cells = _blank(w, h)
    cells[0] = CELL_GOAL
    cells[4] = CELL_HAZARD  # (x=1,y=1)

    p = _mk_patch(cells, w=w, h=h, entity_id="scene", role="scene")
    g = compose_surfacegrid_v1([p], grid_w=w, grid_h=h)

    assert g.ascii_v1() == "G  \n ^ "