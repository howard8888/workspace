import pytest

import cca8_world_graph
from cca8_env import EnvState, FsmBackend
from cca8_controller import Drives, body_space_zone
from cca8_run import (
    Ctx,
    init_body_world,
    update_body_world_from_obs,
    _gate_rest_trigger_body_space,
)


class _ObsStub:
    """Minimal EnvObservation-like stub for BodyMap tests."""
    def __init__(self, predicates):
        self.predicates = predicates
        self.cues = []


# ---------------------------------------------------------------------------
# Phase VI-C geometry: FollowMom → move off cliff, then into shelter
# ---------------------------------------------------------------------------

def test_follow_mom_moves_off_cliff():
    """
    Phase VI-C: in stage 'first_stand', a FollowMom action should move
    the kid from cliff_edge → open_field and set cliff_distance to 'far',
    while leaving shelter_distance as 'far'. The coarse zone label on
    EnvState should become 'neutral' (via update_zone_from_position()).
    """
    backend = FsmBackend()
    state = EnvState()

    # Place the storyboard directly into 'first_stand' geometry.
    state.scenario_stage = "first_stand"
    state.kid_posture = "standing"
    state.mom_distance = "near"
    state.nipple_state = "hidden"
    state.shelter_distance = "far"
    state.cliff_distance = "near"
    state.step_index = 1  # well below any auto thresholds
    state.position = "cliff_edge"
    state.zone = "unsafe"

    # One storyboard step with FollowMom as the last action.
    backend.step(state, action="policy:follow_mom", ctx=None)

    # Geometry should now be off the exposed cliff edge.
    assert state.scenario_stage == "first_stand"
    assert state.position == "open_field"
    assert state.cliff_distance == "far"
    # FollowMom does not touch shelter_distance in the first hop.
    assert state.shelter_distance == "far"
    # Coarse symbolic zone should reflect 'open_field' → neutral.
    assert state.zone == "neutral"


def test_follow_mom_moves_into_shelter():
    """
    Phase VI-C: in stage 'first_stand', a second FollowMom step should move
    open_field → shelter_area, with shelter_distance='near' and
    cliff_distance='far', and EnvState.zone='safe'.
    """
    backend = FsmBackend()
    state = EnvState()

    # Start in first_stand, already off the cliff on neutral ground.
    state.scenario_stage = "first_stand"
    state.kid_posture = "standing"
    state.mom_distance = "near"
    state.nipple_state = "hidden"
    state.shelter_distance = "far"
    state.cliff_distance = "near"  # will be overridden inside step
    state.step_index = 1
    state.position = "open_field"
    state.zone = "neutral"

    backend.step(state, action="policy:follow_mom", ctx=None)

    # Geometry should now represent a sheltered niche.
    assert state.scenario_stage == "first_stand"
    assert state.position == "shelter_area"
    assert state.shelter_distance == "near"
    assert state.cliff_distance == "far"
    # Coarse symbolic zone should now be 'safe'.
    assert state.zone == "safe"


# ---------------------------------------------------------------------------
# Phase VI-C gating: Rest gate uses BodyMap zone (unsafe_cliff_near vs safe)
# ---------------------------------------------------------------------------

def _make_ctx_with_bodymap(predicates):
    """
    Build a Ctx + BodyMap reflecting given EnvObservation predicates,
    and keep BodyMap fresh (controller_steps=0).
    """
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.controller_steps = 0
    obs = _ObsStub(predicates)
    update_body_world_from_obs(ctx, obs)
    return ctx


def test_rest_gate_vetoes_in_unsafe_zone():
    """
    Rest gate should NOT trigger when fatigue is high but BodyMap reports an
    'unsafe_cliff_near' zone (cliff=near, shelter=far).
    """
    # World is only used for drive cues; a fresh WorldGraph is fine.
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    # High fatigue so Rest would normally be eligible.
    drives = Drives(hunger=0.2, fatigue=0.9, warmth=0.6)

    # BodyMap: standing, mom close, shelter far, cliff near → unsafe_cliff_near.
    ctx = _make_ctx_with_bodymap(
        [
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:far",
            "hazard:cliff:near",
        ]
    )

    zone = body_space_zone(ctx)
    assert zone == "unsafe_cliff_near"

    allowed = _gate_rest_trigger_body_space(world, drives, ctx)
    assert allowed is False, "Rest gate should veto rest in unsafe_cliff_near geometry"


def test_rest_gate_allows_in_safe_zone():
    """
    Rest gate should allow rest when fatigue is high and BodyMap reports 'safe'
    (shelter=near, cliff=far).
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    drives = Drives(hunger=0.2, fatigue=0.9, warmth=0.6)

    # BodyMap: standing, mom close, shelter near, cliff far → safe.
    ctx = _make_ctx_with_bodymap(
        [
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ]
    )

    zone = body_space_zone(ctx)
    assert zone == "safe"

    allowed = _gate_rest_trigger_body_space(world, drives, ctx)
    assert allowed is True, "Rest gate should permit rest when zone is safe"
