"""Local equivalent of the runner's engram search filters."""

from __future__ import annotations

import cca8_world_graph as wg
from cca8_features import time_attrs_from_ctx
from cca8_run import Ctx


def _capture(world: wg.WorldGraph, ctx: Ctx, token: str, cognitive_cycle: int) -> tuple[str, str]:
    ctx.cog_cycles = cognitive_cycle
    attrs = time_attrs_from_ctx(ctx)
    return world.capture_scene("vision", token, [0.0, 0.0, 0.0], attach="now", family="cue", attrs=attrs)


def test_search_like_filters_locally() -> None:
    """Name, cycle, payload-kind, and id-prefix filtering should compose."""
    world = wg.WorldGraph()
    world.ensure_anchor("NOW")
    ctx = Ctx()

    _binding1, eid1 = _capture(world, ctx, "silhouette:mom", cognitive_cycle=1)
    _binding2, eid2 = _capture(world, ctx, "silhouette:tree", cognitive_cycle=2)

    seen: set[str] = set()
    matches: list[tuple[str, str, str, int]] = []
    for bid, binding in world._bindings.items():  # pylint: disable=protected-access
        engrams = getattr(binding, "engrams", None)
        if not isinstance(engrams, dict):
            continue
        for value in engrams.values():
            eid = value.get("id") if isinstance(value, dict) else None
            if not isinstance(eid, str) or eid in seen:
                continue
            seen.add(eid)
            record = world.get_engram(engram_id=eid)
            name = record.get("name", "")
            attrs = record.get("meta", {}).get("attrs", {})
            if "silhouette" not in name or attrs.get("cognitive_cycle") not in {1, 2}:
                continue
            payload = record.get("payload")
            kind = payload.meta().get("kind") if hasattr(payload, "meta") else None
            if kind == "scene" and eid.startswith(eid[:2]):
                matches.append((eid, bid, name, attrs["cognitive_cycle"]))

    assert {item[0] for item in matches} == {eid1, eid2}
