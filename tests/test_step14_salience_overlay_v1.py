from __future__ import annotations

from cca8_run import (
    Ctx,
    init_working_world,
    render_surfacegrid_ascii_with_salience_v1,
    wm_salience_tick_v1,
)
from cca8_navpatch import (
    compose_surfacegrid_v1,
    CELL_TRAVERSABLE,
)


def _set_entity(ww, ctx: Ctx, entity_id: str, *, kind: str, x: float, y: float) -> str:
    # Minimal WM entity binding consistent with MapSurface conventions.
    ent = entity_id.strip().lower()
    if ent == "self":
        anchor = "WM_SELF"
    else:
        anchor = f"WM_ENT_{ent.upper()}"

    bid = ww.ensure_anchor(anchor)
    b = ww._bindings[bid]  # pylint: disable=protected-access

    # tags
    tags = set(getattr(b, "tags", set()) or set())
    tags.discard(f"anchor:{anchor}")  # keep it clean; anchor-ness is not relevant in this test
    tags.add("wm:entity")
    tags.add(f"wm:eid:{ent}")
    tags.add(f"wm:kind:{kind}")
    b.tags = tags

    # meta
    if not isinstance(getattr(b, "meta", None), dict):
        b.meta = {}
    wmm = b.meta.setdefault("wm", {})
    if isinstance(wmm, dict):
        wmm["pos"] = {"x": float(x), "y": float(y), "frame": "wm_schematic_v1"}

    ctx.wm_entities[ent] = bid
    return bid


def test_step14_salience_ttl_and_ascii_overlay_smoke() -> None:
    ctx = Ctx()
    ctx.wm_surfacegrid_ascii_sparse = True
    ctx.wm_surfacegrid_ascii_show_entities = True
    ctx.wm_salience_novelty_ttl = 3
    ctx.wm_salience_promote_ttl = 8
    ctx.wm_salience_max_items = 3

    ww = init_working_world()
    ctx.working_world = ww
    ctx.wm_entities.clear()

    _set_entity(ww, ctx, "self", kind="agent", x=0.0, y=0.0)
    _set_entity(ww, ctx, "mom", kind="agent", x=2.0, y=0.0)
    _set_entity(ww, ctx, "cliff", kind="hazard", x=3.0, y=0.0)

    # Compose a trivial grid: everything traversable (dense), so ASCII-sparse matters.
    patch = {
        "schema": "navpatch_v1",
        "local_id": "p_scene",
        "entity_id": "scene",
        "role": "scene",
        "frame": "ego_schematic_v1",
        "grid_encoding_v": "grid_v1",
        "grid_w": 7,
        "grid_h": 7,
        "grid_cells": [CELL_TRAVERSABLE] * (7 * 7),
        "tags": ["zone:test"],
        "layers": {},
        "obs": {"source": "unit_test"},
    }
    sg = compose_surfacegrid_v1([patch], grid_w=7, grid_h=7)

    # Tick salience: mom changed + cliff ambiguous → both should enter focus.
    sal = wm_salience_tick_v1(
        ctx,
        ww,
        changed_entities={"mom"},
        new_cue_entities=set(),
        ambiguous_entities={"cliff"},
    )
    focus = sal.get("focus_entities", [])
    assert "self" in focus
    assert "mom" in focus
    assert "cliff" in focus

    # TTL was written into meta
    mom_bid = ctx.wm_entities["mom"]
    cliff_bid = ctx.wm_entities["cliff"]
    mom_ttl = ww._bindings[mom_bid].meta["wm"].get("salience_ttl")  # pylint: disable=protected-access
    cliff_ttl = ww._bindings[cliff_bid].meta["wm"].get("salience_ttl")  # pylint: disable=protected-access
    assert isinstance(mom_ttl, int) and mom_ttl >= 3
    assert isinstance(cliff_ttl, int) and cliff_ttl >= 8  # promoted by ambiguity/hazard

    # ASCII overlay should show landmark letters; sparse mode should hide most '.' noise.
    txt = render_surfacegrid_ascii_with_salience_v1(ctx, ww, sg, focus_entities=list(focus))
    assert "@" in txt
    assert "M" in txt
    assert "C" in txt