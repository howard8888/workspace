from __future__ import annotations

from cca8_run import (
    Ctx,
    init_working_world,
    wm_salience_force_focus_entity_v1,
    wm_salience_tick_v1,
)


def _set_entity(ww, ctx: Ctx, entity_id: str, *, kind: str, x: float, y: float) -> str:
    """Minimal WM entity binding consistent with the Step-14 salience/overlay code."""
    ent = entity_id.strip().lower()
    anchor = "WM_SELF" if ent == "self" else f"WM_ENT_{ent.upper()}"

    bid = ww.ensure_anchor(anchor)
    b = ww._bindings[bid]  # pylint: disable=protected-access

    tags = set(getattr(b, "tags", set()) or set())
    tags.discard(f"anchor:{anchor}")  # keep it clean; anchor-ness is not relevant in this test
    tags.add("wm:entity")
    tags.add(f"wm:eid:{ent}")
    tags.add(f"wm:kind:{kind}")
    b.tags = tags

    if not isinstance(getattr(b, "meta", None), dict):
        b.meta = {}
    wmm = b.meta.setdefault("wm", {})
    if isinstance(wmm, dict):
        wmm["pos"] = {"x": float(x), "y": float(y), "frame": "wm_schematic_v1"}

    ctx.wm_entities[ent] = bid
    return bid


def test_step14_forced_focus_persists_then_expires() -> None:
    """
    Step 14 "forced focus" contract:

    - When we force-focus an entity with TTL=N, it must appear in focus_entities for N ticks.
    - The TTL counter must decrement once per salience tick and then disappear when it reaches 0.
    - Forced focus is attention/display only; we only verify focus list + TTL bookkeeping here.
    """
    ctx = Ctx()
    ww = init_working_world()
    ctx.working_world = ww
    ctx.wm_entities.clear()

    _set_entity(ww, ctx, "self", kind="agent", x=0.0, y=0.0)
    _set_entity(ww, ctx, "cliff", kind="hazard", x=3.0, y=0.0)

    wm_salience_force_focus_entity_v1(ctx, "cliff", ttl=2, reason="inspect_policy:unit_test")

    # Tick 1: cliff must be in focus; forced TTL decremented to 1.
    sal1 = wm_salience_tick_v1(ctx, ww, changed_entities=set(), new_cue_entities=set(), ambiguous_entities=set())
    focus1 = sal1.get("focus_entities", [])
    assert "self" in focus1
    assert "cliff" in focus1
    assert isinstance(getattr(ctx, "wm_salience_forced_focus", None), dict)
    assert ctx.wm_salience_forced_focus.get("cliff") == 1

    # Tick 2: cliff still in focus; forced TTL decremented to 0 and removed.
    sal2 = wm_salience_tick_v1(ctx, ww, changed_entities=set(), new_cue_entities=set(), ambiguous_entities=set())
    focus2 = sal2.get("focus_entities", [])
    assert "cliff" in focus2
    assert "cliff" not in ctx.wm_salience_forced_focus

    # Tick 3: cliff no longer forced into focus (it may still appear via OTHER mechanisms; in this test it should not).
    sal3 = wm_salience_tick_v1(ctx, ww, changed_entities=set(), new_cue_entities=set(), ambiguous_entities=set())
    focus3 = sal3.get("focus_entities", [])
    assert "cliff" not in focus3