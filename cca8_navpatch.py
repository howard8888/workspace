# -*- coding: utf-8 -*-
"""cca8_navpatch.py

NavPatch + SurfaceGrid utilities (Phase X scaffolding)

Purpose
-------
The CCA8 NavPatch pipeline uses small, explicit *topological* grids to represent
local navigational structure.

In v1 we keep this extremely simple and deterministic:

- A NavPatch carries a JSON-safe grid payload ("grid_v1") with small integer
  cell codes.
- A WorkingMap SurfaceGrid is composed once-per-tick by overlaying active
  NavPatch instances (no transforms in v1; all patches are already SELF-local).
- A tiny set of grid-derived slot-families ("hazard:near", "terrain:traversable_near",
  optional "goal:dir") can be derived deterministically for cheap policy gating.

This module is deliberately dependency-free (stdlib only) and conservative:

- No NumPy.
- Signatures are stable across runs and platform.
- JSON round-trippable structures only.

Design stance
-------------
- "Grid semantics" and "overlay priority" are separated.
  The cell *codes* are semantic labels; the overlay rule is a safety policy.

- Signature excludes volatile fields.
  We treat local ids, timestamps, confidences, and transient diagnostic fields as
  volatile and do not include them in `navpatch_sig_v1(...)`.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import hashlib
import json


__version__ = "0.1.0"
__all__ = [
    "CELL_UNKNOWN",
    "CELL_TRAVERSABLE",
    "CELL_HAZARD",
    "CELL_GOAL",
    "CELL_BLOCKED",
    "GRID_ENCODING_V1",
    "navpatch_grid_errors_v1",
    "navpatch_sig_v1",
    "navpatch_sig16_v1",
    "SurfaceGridV1",
    "compose_surfacegrid_v1",
    "surfacegrid_ascii_v1",
    "derive_grid_slot_families_v1",
    "grid_overlap_fraction_v1",
    "__version__",
]


# --- Grid cell semantics (v1) -------------------------------------------------------

GRID_ENCODING_V1 = "grid_v1"

CELL_UNKNOWN = 0
CELL_TRAVERSABLE = 1
CELL_HAZARD = 2
CELL_GOAL = 3
CELL_BLOCKED = 4

_ALLOWED_CELLS_V1 = {CELL_UNKNOWN, CELL_TRAVERSABLE, CELL_HAZARD, CELL_GOAL, CELL_BLOCKED}

# ASCII renderer mapping (v1). Keep it simple and stable.
_ASCII_CELL_V1 = {
    CELL_UNKNOWN: " ",
    CELL_TRAVERSABLE: ".",
    CELL_HAZARD: "^",
    CELL_GOAL: "G",
    CELL_BLOCKED: "#",
}

# Overlay priority (v1): higher means "wins" in overlaps.
# Safety stance: BLOCKED and HAZARD win over GOAL.
_OVERLAY_PRI_V1 = {
    CELL_UNKNOWN: 0,
    CELL_TRAVERSABLE: 1,
    CELL_GOAL: 2,
    CELL_HAZARD: 3,
    CELL_BLOCKED: 4,
}


# --- Validation ---------------------------------------------------------------------


def navpatch_grid_errors_v1(patch: Dict[str, Any]) -> List[str]:
    """Return a list of schema errors for a navpatch grid payload (grid_v1)."""
    errs: List[str] = []
    if not isinstance(patch, dict):
        return ["patch is not a dict"]

    enc = patch.get("grid_encoding_v")
    if enc != GRID_ENCODING_V1:
        errs.append(f"grid_encoding_v must be {GRID_ENCODING_V1!r}")

    w = patch.get("grid_w")
    h = patch.get("grid_h")
    if not (isinstance(w, int) and w > 0):
        errs.append("grid_w must be int > 0")
    if not (isinstance(h, int) and h > 0):
        errs.append("grid_h must be int > 0")

    cells = patch.get("grid_cells")
    if not isinstance(cells, list):
        errs.append("grid_cells must be a list")
        return errs

    if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
        want = w * h
        if len(cells) != want:
            errs.append(f"grid_cells length must be grid_w*grid_h ({want})")

    bad: List[str] = []
    for i, c in enumerate(cells[: 10_000]):
        if not isinstance(c, int):
            bad.append(f"cell[{i}] not int")
            if len(bad) >= 3:
                break
            continue
        if c not in _ALLOWED_CELLS_V1:
            bad.append(f"cell[{i}] invalid code {c}")
            if len(bad) >= 3:
                break
    errs.extend(bad)
    return errs


# --- Signatures ---------------------------------------------------------------------


def _sorted_unique_strs(xs: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for x in xs:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort()
    return out


def navpatch_sig_v1(patch: Dict[str, Any]) -> str:
    """Deterministic signature for a navpatch payload (v1)."""
    if not isinstance(patch, dict):
        return ""

    schema = patch.get("schema")
    if not isinstance(schema, str) or not schema:
        schema = "navpatch_v1"

    core: Dict[str, Any] = {
        "schema": schema,
        "role": patch.get("role") if isinstance(patch.get("role"), str) else None,
        "frame": patch.get("frame") if isinstance(patch.get("frame"), str) else None,
        "entity_id": patch.get("entity_id") if isinstance(patch.get("entity_id"), str) else None,
    }

    tags = patch.get("tags")
    if isinstance(tags, list):
        core["tags"] = _sorted_unique_strs(tags)

    ext = patch.get("extent")
    if isinstance(ext, dict):
        ok = True
        for k, v in list(ext.items())[:32]:
            if not isinstance(k, str):
                ok = False
                break
            if not isinstance(v, (int, float, str, bool)) and v is not None:
                ok = False
                break
        if ok:
            core["extent"] = ext

    core["grid_encoding_v"] = patch.get("grid_encoding_v")
    core["grid_w"] = patch.get("grid_w")
    core["grid_h"] = patch.get("grid_h")
    core["grid_cells"] = patch.get("grid_cells")

    payload = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def navpatch_sig16_v1(patch: Dict[str, Any]) -> str:
    """Convenience: first 16 hex chars of `navpatch_sig_v1`."""
    s = navpatch_sig_v1(patch)
    return s[:16] if s else ""


# --- SurfaceGrid --------------------------------------------------------------------


def _overlay_cell_v1(old: int, new: int) -> int:
    """Overlay rule for a single cell (v1)."""
    try:
        if _OVERLAY_PRI_V1.get(new, -1) > _OVERLAY_PRI_V1.get(old, -1):
            return new
    except Exception:
        return old
    return old


@dataclass(slots=True)
class SurfaceGridV1:
    """A single composed topological grid for the current tick (v1)."""
    grid_w: int
    grid_h: int
    grid_cells: List[int]
    grid_encoding_v: str = GRID_ENCODING_V1

    def sig_v1(self) -> str:
        ''' within class SurfaceGridV1
        '''
        core = {
            "grid_encoding_v": self.grid_encoding_v,
            "grid_w": self.grid_w,
            "grid_h": self.grid_h,
            "grid_cells": self.grid_cells,
        }
        payload = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def sig16_v1(self) -> str:
        ''' within class SurfaceGridV1
        '''
        s = self.sig_v1()
        return s[:16] if s else ""

    def ascii_v1(self) -> str:
        ''' within class SurfaceGridV1
        '''
        return surfacegrid_ascii_v1(self)

    def to_dict(self) -> Dict[str, Any]:
        ''' within class SurfaceGridV1
        '''
        return {
            "grid_encoding_v": self.grid_encoding_v,
            "grid_w": self.grid_w,
            "grid_h": self.grid_h,
            "grid_cells": list(self.grid_cells),
        }


def compose_surfacegrid_v1(patches: List[Dict[str, Any]], *, grid_w: int, grid_h: int) -> SurfaceGridV1:
    """Compose a SurfaceGrid from active navpatch instances (v1)."""
    out = [CELL_UNKNOWN] * (int(grid_w) * int(grid_h))

    if not isinstance(patches, list) or not patches:
        return SurfaceGridV1(grid_w=int(grid_w), grid_h=int(grid_h), grid_cells=out)

    # Deterministic order
    try:
        patches_sorted = sorted(patches, key=navpatch_sig_v1)
    except Exception:
        patches_sorted = list(patches)

    for p in patches_sorted:
        if not isinstance(p, dict):
            continue
        if p.get("grid_encoding_v") != GRID_ENCODING_V1:
            continue
        w = p.get("grid_w")
        h = p.get("grid_h")
        if w != grid_w or h != grid_h:
            continue
        cells = p.get("grid_cells")
        if not (isinstance(cells, list) and len(cells) == grid_w * grid_h):
            continue

        for i, c in enumerate(cells):
            if not isinstance(c, int):
                continue
            if c not in _ALLOWED_CELLS_V1:
                continue
            out[i] = _overlay_cell_v1(out[i], c)

    return SurfaceGridV1(grid_w=int(grid_w), grid_h=int(grid_h), grid_cells=out)


def surfacegrid_ascii_v1(grid: SurfaceGridV1) -> str:
    """Render a SurfaceGridV1 as ASCII (v1)."""
    w = int(getattr(grid, "grid_w", 0) or 0)
    h = int(getattr(grid, "grid_h", 0) or 0)
    cells = getattr(grid, "grid_cells", None)
    if w <= 0 or h <= 0 or not isinstance(cells, list) or len(cells) != w * h:
        return ""

    lines: List[str] = []
    for y in range(h):
        row = []
        base = y * w
        for x in range(w):
            c = cells[base + x]
            row.append(_ASCII_CELL_V1.get(c, "?"))
        lines.append("".join(row))
    return "\n".join(lines)


# --- Grid-derived slot-families -----------------------------------------------------


def _iter_disk_cells(w: int, h: int, cx: int, cy: int, r: int) -> Iterable[Tuple[int, int]]:
    r2 = r * r
    x0 = max(0, cx - r)
    x1 = min(w - 1, cx + r)
    y0 = max(0, cy - r)
    y1 = min(h - 1, cy + r)
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            if dx * dx + dy * dy <= r2:
                yield x, y


def _dir8(dx: int, dy: int) -> str:
    sx = 0 if dx == 0 else (1 if dx > 0 else -1)
    sy = 0 if dy == 0 else (1 if dy > 0 else -1)

    if sx == 0 and sy == 0:
        return "C"
    if sx == 0 and sy < 0:
        return "N"
    if sx == 0 and sy > 0:
        return "S"
    if sx > 0 and sy == 0:
        return "E"
    if sx < 0 and sy == 0:
        return "W"
    if sx > 0 > sy:
        return "NE"
    if sx > 0 and sy > 0:
        return "SE"
    if sx < 0 and sy < 0:
        return "NW"
    return "SW"


def derive_grid_slot_families_v1(
    grid: SurfaceGridV1,
    *,
    self_xy: Optional[Tuple[int, int]] = None,
    r: int = 2,
    include_goal_dir: bool = True,
) -> Dict[str, Any]:
    """Derive deterministic slot-families from SurfaceGrid (v1)."""
    w = int(getattr(grid, "grid_w", 0) or 0)
    h = int(getattr(grid, "grid_h", 0) or 0)
    cells = getattr(grid, "grid_cells", None)
    if w <= 0 or h <= 0 or not isinstance(cells, list) or len(cells) != w * h:
        return {}

    if self_xy is None:
        cx, cy = w // 2, h // 2
    else:
        cx, cy = int(self_xy[0]), int(self_xy[1])
        cx = max(0, min(w - 1, cx))
        cy = max(0, min(h - 1, cy))

    r = max(0, int(r))

    hazard_near = False
    traversable_near = False

    for x, y in _iter_disk_cells(w, h, cx, cy, r):
        c = cells[y * w + x]
        if c == CELL_TRAVERSABLE:
            traversable_near = True
        if c in (CELL_HAZARD, CELL_BLOCKED):
            hazard_near = True

    out: Dict[str, Any] = {
        "hazard:near": hazard_near,
        "terrain:traversable_near": traversable_near,
    }

    if include_goal_dir:
        best: Optional[Tuple[int, int, int]] = None
        for y in range(h):
            base = y * w
            for x in range(w):
                if cells[base + x] != CELL_GOAL:
                    continue
                d = abs(x - cx) + abs(y - cy)
                if best is None:
                    best = (d, x, y)
                elif d < best[0]:
                    best = (d, x, y)
        if best is not None:
            _, gx, gy = best
            out["goal:dir"] = _dir8(gx - cx, gy - cy)

    return out


# --- Similarity (optional; used in matching later) ---------------------------------


def grid_overlap_fraction_v1(a_cells: List[int], b_cells: List[int]) -> float:
    """Simple overlap metric for two grid_v1 flat lists."""
    if not (isinstance(a_cells, list) and isinstance(b_cells, list)):
        return 0.0
    if len(a_cells) != len(b_cells) or not a_cells:
        return 0.0

    denom = 0
    num = 0
    for a, b in zip(a_cells, b_cells):
        if a == CELL_UNKNOWN and b == CELL_UNKNOWN:
            continue
        denom += 1
        if a == b:
            num += 1
    return (num / denom) if denom else 0.0
