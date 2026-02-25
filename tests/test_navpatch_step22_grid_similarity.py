# -*- coding: utf-8 -*-
"""
Step 2.2 unit test: grid similarity must influence NavPatch matching.

This test is designed to FAIL if grid_sim is computed but NOT used in the
precision-weighted evidence score.

We construct:
- proto_A: grid matches the observation, but tags mismatch
- proto_B: tags match the observation, but grid mismatches

We then set precision weights:
  tags=0, extent=0, grid=1
so the winner MUST be proto_A (grid drives the match).

If grid is ignored, proto_B wins (because tags/ext dominate the fallback).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cca8_env import EnvObservation  # noqa: E402
from cca8_run import Ctx, store_navpatch_engram_v1, navpatch_predictive_match_loop_v1  # noqa: E402
from cca8_column import mem as column_mem  # noqa: E402
from cca8_navpatch import GRID_ENCODING_V1, CELL_UNKNOWN, CELL_HAZARD  # noqa: E402


def _grid(w: int, h: int, hazard_at: int | None) -> list[int]:
    cells = [CELL_UNKNOWN] * (w * h)
    if hazard_at is not None:
        cells[int(hazard_at)] = CELL_HAZARD
    return cells


def _patch(*, local_id: str, role: str, tags: list[str], grid_cells: list[int]) -> dict:
    w = 4
    h = 4
    return {
        "schema": "navpatch_v1",
        "local_id": local_id,
        "entity_id": "unit_test_entity_step22",
        "role": role,
        "frame": "ego_schematic_v1",
        "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
        "tags": list(tags),
        "layers": {},
        "obs": {"source": "unit_test"},
        "grid_encoding_v": GRID_ENCODING_V1,
        "grid_w": w,
        "grid_h": h,
        "grid_origin": [w // 2, h // 2],
        "grid_resolution": 1.0,
        "grid_cells": list(grid_cells),
    }


def test_step22_grid_similarity_changes_winner() -> None:
    # --- create two stored prototypes (role is unique so we filter out any other Column records) ---
    role = "unit_test_role_step22"

    proto_a = _patch(
        local_id="p_proto_a_step22",
        role=role,
        tags=["unit:A"],                     # tag mismatch vs obs
        grid_cells=_grid(4, 4, hazard_at=5),  # grid MATCH vs obs
    )
    proto_b = _patch(
        local_id="p_proto_b_step22",
        role=role,
        tags=["unit:OBS"],                   # tag match vs obs
        grid_cells=_grid(4, 4, hazard_at=9),  # grid MISMATCH vs obs
    )

    ctx_store = Ctx()
    ctx_store.navpatch_enabled = True

    st_a = store_navpatch_engram_v1(ctx_store, proto_a, reason="unit_test_proto")
    st_b = store_navpatch_engram_v1(ctx_store, proto_b, reason="unit_test_proto")

    eid_a = st_a.get("engram_id")
    eid_b = st_b.get("engram_id")
    assert isinstance(eid_a, str) and eid_a
    assert isinstance(eid_b, str) and eid_b

    # Track which ones we actually created so we don't delete pre-existing dedup hits.
    created = []
    if st_a.get("stored") is True:
        created.append(eid_a)
    if st_b.get("stored") is True:
        created.append(eid_b)

    try:
        # --- observation patch: tag matches proto_B, grid matches proto_A ---
        obs = _patch(
            local_id="p_obs_step22",
            role=role,
            tags=["unit:OBS"],
            grid_cells=_grid(4, 4, hazard_at=5),
        )

        ctx = Ctx()
        ctx.navpatch_enabled = True
        ctx.navpatch_store_to_column = False
        ctx.navpatch_priors_enabled = False

        # Precision: ONLY grid counts
        ctx.navpatch_precision_tags = 0.0
        ctx.navpatch_precision_extent = 0.0
        ctx.navpatch_precision_grid = 1.0

        ctx.navpatch_match_top_k = 2

        env_obs = EnvObservation(nav_patches=[obs])
        out = navpatch_predictive_match_loop_v1(ctx, env_obs)
        assert len(out) == 1

        top = out[0].get("top_k")
        assert isinstance(top, list) and len(top) >= 2

        # Winner must be proto_A because grid dominates under these precision settings.
        assert top[0].get("engram_id") == eid_a
        assert top[1].get("engram_id") == eid_b

        # And grid_sim should reflect why (A higher than B)
        gs0 = top[0].get("grid_sim")
        gs1 = top[1].get("grid_sim")
        assert isinstance(gs0, (int, float))
        assert isinstance(gs1, (int, float))
        assert float(gs0) > float(gs1)

    finally:
        # Cleanup only the engrams this test created (avoid deleting pre-existing items).
        for eid in created:
            try:
                column_mem.delete(eid)
            except Exception:
                pass