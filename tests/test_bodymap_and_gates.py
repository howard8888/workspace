import pytest

from cca8_run import Ctx, init_body_world, update_body_world_from_obs, _gate_seek_nipple_trigger_body_first  # type: ignore[attr-defined]
from cca8_controller import Drives, body_posture, body_mom_distance, body_nipple_state  # type: ignore[attr-defined]
from cca8_env import EnvObservation  # type: ignore[attr-defined]
import cca8_world_graph  # for WorldGraph


def _make_ctx_with_bodymap() -> Ctx:
    """Helper: create a fresh Ctx with an initialized BodyMap."""
    ctx = Ctx()
    body_world, body_ids = init_body_world()
    ctx.body_world = body_world
    ctx.body_ids = body_ids
    return ctx


def test_bodymap_from_env_observation_posture() -> None:
    """
    BodyMap should mirror posture, mom_distance, nipple_state from EnvObservation.

    We build a fake EnvObservation with:
      - posture:standing
      - proximity:mom:close
      - nipple:latched + milk:drinking

    After update_body_world_from_obs, the BodyMap accessors should read:
      body_posture(ctx) == "standing"
      body_mom_distance(ctx) == "near"
      body_nipple_state(ctx) == "latched"
    """
    ctx = _make_ctx_with_bodymap()

    obs = EnvObservation(
        raw_sensors={},
        predicates=[
            "posture:standing",
            "proximity:mom:close",
            "nipple:latched",
            "milk:drinking",
        ],
        cues=[],
        env_meta={"scenario_stage": "first_stand"},
    )

    # Update BodyMap from this observation
    update_body_world_from_obs(ctx, obs)

    # BodyMap accessors should now reflect the observation
    assert body_posture(ctx) == "standing"
    assert body_mom_distance(ctx) == "near"
    assert body_nipple_state(ctx) == "latched"


def test_seek_nipple_gate_uses_bodymap() -> None:
    """
    SeekNipple gate should consult BodyMap and *not* fire when nipple_state=='latched',
    even if hunger is high and posture is standing.

    We:
      - seed a fresh world + ctx,
      - initialize BodyMap, then update it from an EnvObservation that encodes:
          posture:standing, proximity:mom:close, nipple:latched, milk:drinking,
      - set hunger high,
      - assert that _gate_seek_nipple_trigger_body_first(...) returns False.
    """
    # World for the gate (needs at least a NOW anchor but no specific predicates)
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    # Context with BodyMap
    ctx = _make_ctx_with_bodymap()
    obs = EnvObservation(
        raw_sensors={},
        predicates=[
            "posture:standing",
            "proximity:mom:close",
            "nipple:latched",
            "milk:drinking",
        ],
        cues=[],
        env_meta={"scenario_stage": "first_stand"},
    )
    update_body_world_from_obs(ctx, obs)

    # High hunger: would normally satisfy the hunger part of the gate
    drives = Drives(hunger=0.9, fatigue=0.1, warmth=0.6)

    # With BodyMap posture == 'standing' and nipple_state == 'latched',
    # the SeekNipple gate should refuse to fire (already latched/drinking).
    assert body_posture(ctx) == "standing"
    assert body_nipple_state(ctx) == "latched"

    ok = _gate_seek_nipple_trigger_body_first(world, drives, ctx)
    assert ok is False
