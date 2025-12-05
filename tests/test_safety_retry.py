"""
Unit tests for Phase V safety / BodyMap behaviour.

These verify that:
  • BodyMap posture 'fallen' is seen as "fallen near NOW" even when the WorldGraph
    has no posture:fallen predicate.
  • BodyMap posture 'standing' is NOT seen as fallen.
  • BodyMap staleness (bodymap_is_stale) flips from fresh → stale when the
    controller_steps – last_update exceeds the configured window.
"""

import cca8_world_graph
from cca8_run import Ctx
from cca8_controller import Drives, _fallen_near_now, bodymap_is_stale  # type: ignore[attr-defined]


def _make_ctx_with_body_posture(posture: str, step: int = 0) -> Ctx:
    """Utility: construct a Ctx with a minimal BodyMap slot for posture."""
    ctx = Ctx()
    ctx.body_world = cca8_world_graph.WorldGraph()
    bid = ctx.body_world._next_id()  # pylint: disable=protected-access
    ctx.body_ids = {"posture": bid}
    ctx.body_world._bindings[bid] = cca8_world_graph.Binding(
        id=bid,
        tags={f"pred:posture:{posture}"},
        edges=[],
        meta={},
        engrams={},
    )
    ctx.controller_steps = step
    ctx.bodymap_last_update_step = step
    return ctx


def test_fallen_detected_from_bodymap_even_when_world_empty():
    """
    If BodyMap says posture='fallen' and the WorldGraph has no posture:fallen
    predicate at all, _fallen_near_now(...) should still return True.

    This ensures the safety check is truly Body-first (Phase V behaviour).
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")
    drives = Drives()  # unused here; kept for signature parity

    ctx = _make_ctx_with_body_posture("fallen", step=10)

    # Sanity: world has no pred:posture:fallen yet.
    assert not any(
        "pred:posture:fallen" in (getattr(b, "tags", []) or [])
        for b in world._bindings.values()
    )

    assert _fallen_near_now(world, ctx, max_hops=3) is True


def test_standing_not_considered_fallen_from_bodymap():
    """
    If BodyMap says posture='standing' and there is no fallen predicate near NOW,
    _fallen_near_now(...) should return False.
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")
    drives = Drives()  # unused

    ctx = _make_ctx_with_body_posture("standing", step=10)

    assert _fallen_near_now(world, ctx, max_hops=3) is False


def test_bodymap_staleness_threshold():
    """
    bodymap_is_stale should treat a freshly updated BodyMap as fresh, and mark it
    stale once controller_steps - last_update exceeds max_steps.
    """
    ctx = _make_ctx_with_body_posture("fallen", step=0)

    # Fresh immediately after update
    assert bodymap_is_stale(ctx, max_steps=5) is False

    # After more than max_steps controller steps with no new update, it should be stale
    ctx.controller_steps = 6
    assert bodymap_is_stale(ctx, max_steps=5) is True
