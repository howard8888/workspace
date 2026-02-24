# -*- coding: utf-8 -*-
"""tests/test_navpatch_grid_v1.py

Unit tests for NavPatch grid payload v1.

These tests cover the Phase X Step 11 contract:

- JSON-safe grid schema (grid_encoding_v, grid_w, grid_h, grid_cells)
- Deterministic signature that includes the topology core
- Basic end-to-end check: PerceptionAdapter emits grid_v1 patches

We keep these tests small and deterministic; no external fixtures required.

Note
----
Some environments run pytest with a working directory that does not automatically
place the repo root on sys.path. We add the parent folder of tests/ explicitly
so `import cca8_navpatch` works when running tests from arbitrary cwd.
"""

from __future__ import annotations

import json
import os
import sys


# Ensure repo root is importable when running pytest from arbitrary cwd.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cca8_navpatch as nav  # noqa: E402  pylint: disable=wrong-import-position


def _make_patch(*, w: int = 4, h: int = 4, cells: list[int] | None = None) -> dict:
    """Create a minimal navpatch dict suitable for signature + validation tests."""
    if cells is None:
        cells = [nav.CELL_TRAVERSABLE] * (w * h)
        cells[0] = nav.CELL_HAZARD
        cells[-1] = nav.CELL_GOAL

    return {
        "schema": "navpatch_v1",
        "local_id": "p_test",  # volatile (must not affect signature)
        "entity_id": "scene",
        "role": "scene",
        "frame": "ego_schematic_v1",
        "grid_encoding_v": nav.GRID_ENCODING_V1,
        "grid_w": w,
        "grid_h": h,
        "grid_cells": list(cells),
        "tags": ["zone:neutral", "stage:test"],
        "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
        "layers": {},  # volatile
        "obs": {"source": "unit_test"},  # volatile
    }


def test_navpatch_grid_errors_v1_valid_patch() -> None:
    p = _make_patch(w=3, h=3)
    assert nav.navpatch_grid_errors_v1(p) == []


def test_navpatch_grid_errors_v1_rejects_bad_length_and_codes() -> None:
    # wrong length
    p = _make_patch(w=2, h=2, cells=[nav.CELL_TRAVERSABLE, nav.CELL_TRAVERSABLE, nav.CELL_TRAVERSABLE])
    errs = nav.navpatch_grid_errors_v1(p)
    assert any("grid_cells length" in e for e in errs)

    # invalid code
    p2 = _make_patch(w=2, h=2, cells=[nav.CELL_TRAVERSABLE, 999, nav.CELL_UNKNOWN, nav.CELL_GOAL])
    errs2 = nav.navpatch_grid_errors_v1(p2)
    assert any("invalid code" in e for e in errs2)


def test_navpatch_sig_v1_is_deterministic_and_sensitive_to_grid_core() -> None:
    p = _make_patch(w=4, h=4)
    sig1 = nav.navpatch_sig_v1(p)
    sig2 = nav.navpatch_sig_v1(p)
    assert sig1 and sig1 == sig2

    # tags ordering + duplicates must not change the signature
    p_tags = dict(p)
    p_tags["tags"] = ["stage:test", "zone:neutral", "zone:neutral"]
    assert nav.navpatch_sig_v1(p_tags) == sig1

    # volatile fields must not change the signature
    p_vol = dict(p)
    p_vol["local_id"] = "p_other"
    p_vol["obs"] = {"source": "different"}
    p_vol["layers"] = {"debug": True}
    assert nav.navpatch_sig_v1(p_vol) == sig1

    # one-cell change must change the signature
    p2 = _make_patch(w=4, h=4)
    p2["grid_cells"][5] = nav.CELL_BLOCKED
    assert nav.navpatch_sig_v1(p2) != sig1


def test_navpatch_json_roundtrip_preserves_grid_and_signature() -> None:
    p = _make_patch(w=5, h=5)
    sig1 = nav.navpatch_sig_v1(p)

    wire = json.dumps(p, ensure_ascii=False)
    p2 = json.loads(wire)

    assert p2["grid_w"] == p["grid_w"]
    assert p2["grid_h"] == p["grid_h"]
    assert p2["grid_cells"] == p["grid_cells"]
    assert nav.navpatch_sig_v1(p2) == sig1


def test_perception_adapter_emits_grid_v1_patches() -> None:
    # End-to-end smoke test: PerceptionAdapter uses the same grid_v1 schema.
    from cca8_env import EnvState, PerceptionAdapter  # noqa: E402  pylint: disable=wrong-import-position

    obs = PerceptionAdapter().observe(EnvState())
    assert isinstance(obs.nav_patches, list)
    assert obs.nav_patches, "Expected PerceptionAdapter to emit at least one patch"

    for patch in obs.nav_patches:
        assert patch.get("grid_encoding_v") == nav.GRID_ENCODING_V1
        assert nav.navpatch_grid_errors_v1(patch) == []