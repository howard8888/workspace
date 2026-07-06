# -*- coding: utf-8 -*-
"""Runner-side NavMap diagnostic integration tests."""

from cca8_env import EnvObservation
from cca8_run import (
    Ctx,
    inject_obs_into_world,
    navmap_ctx_observation_update_step_v1,
    navmap_observation_update_history_append_v1,
    navmap_observation_update_mini_line_v1,
    navmap_observation_update_summary_v1,
    render_navmap_observation_update_lines_v1,
    navmap_ctx_transition_from_payloads_v1,
    navmap_transition_history_append_v1,
)
from cca8_world_graph import WorldGraph


def _fallen_mom_far_obs() -> EnvObservation:
    """Return a small newborn-goat observation with scene_body slots."""
    return EnvObservation(
        predicates=["posture:fallen", "proximity:mom:far", "nipple:hidden"],
        cues=[],
        env_meta={"zone": "unsafe", "scenario_stage": "birth", "time_since_birth": 0.0},
    )


def _standing_mom_near_obs() -> EnvObservation:
    """Return a small observation after a successful stand/approach transition."""
    return EnvObservation(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        cues=[],
        env_meta={"zone": "safe", "scenario_stage": "standing", "time_since_birth": 2.0},
    )


def test_navmap_history_append_is_bounded_and_pure() -> None:
    """The bounded history helper should not mutate caller-owned history rows."""
    original = [{"n": 1}, {"n": 2}]

    bounded = navmap_observation_update_history_append_v1(original, {"n": 3}, limit=2)

    assert original == [{"n": 1}, {"n": 2}]
    assert bounded == [{"n": 2}, {"n": 3}]


def test_navmap_ctx_observation_update_step_stores_json_safe_diagnostic() -> None:
    """A read-only ctx update should create a candidate and store last/history records."""
    ctx = Ctx()
    ctx.controller_steps = 7

    update = navmap_ctx_observation_update_step_v1(ctx, _fallen_mom_far_obs())

    assert update["schema"] == "navmap_observation_update_v1"
    assert update["action"] == "create_candidate"
    assert update["candidate_count_before"] == 0
    assert update["candidate_count_after"] == 1
    assert update["current_payload"]["slots"]["posture"] == "fallen"
    assert update["current_payload"]["slots"]["mom_distance"] == "far"
    assert update["current_payload"]["slots"]["nipple_state"] == "hidden"
    assert update["current_payload"]["slots"]["zone"] == "unsafe"

    assert len(ctx.navmap_scene_body_candidates_v1) == 1
    assert ctx.navmap_last_observation_update_v1 == update
    assert ctx.navmap_observation_update_history_v1 == [update]


def test_inject_obs_into_world_runs_navmap_diagnostic_without_longterm_writes() -> None:
    """Long-term WorldGraph injection can be disabled while NavMap ctx diagnostics still update."""
    world = WorldGraph()
    world.ensure_anchor("NOW")
    before_count = len(world._bindings)  # pylint: disable=protected-access
    ctx = Ctx()
    ctx.longterm_obs_enabled = False
    ctx.working_enabled = False

    result = inject_obs_into_world(world, ctx, _fallen_mom_far_obs())

    assert result == {"predicates": [], "cues": [], "token_to_bid": {}, "working": None}
    assert len(world._bindings) == before_count  # pylint: disable=protected-access
    assert ctx.navmap_last_observation_update_v1 is not None
    assert ctx.navmap_last_observation_update_v1["schema"] == "navmap_observation_update_v1"
    assert len(ctx.navmap_scene_body_candidates_v1) == 1
    assert len(ctx.navmap_observation_update_history_v1) == 1


def test_inject_obs_into_world_uses_local_navmap_candidate_store_across_ticks() -> None:
    """The ctx candidate store should let a repeated observation become a keep_candidate diagnostic."""
    world = WorldGraph()
    world.ensure_anchor("NOW")
    ctx = Ctx()
    ctx.longterm_obs_enabled = False
    ctx.working_enabled = False
    obs = _fallen_mom_far_obs()

    inject_obs_into_world(world, ctx, obs)
    first = ctx.navmap_last_observation_update_v1
    inject_obs_into_world(world, ctx, obs)
    second = ctx.navmap_last_observation_update_v1

    assert first is not None
    assert second is not None
    assert first["action"] == "create_candidate"
    assert second["action"] == "keep_candidate"
    assert second["matched"] is True
    assert len(ctx.navmap_scene_body_candidates_v1) == 1
    assert len(ctx.navmap_observation_update_history_v1) == 2
    

def test_navmap_observation_update_summary_is_idle_before_first_update() -> None:
    """The NavMap summary should be readable before any env observation arrives."""
    ctx = Ctx()

    summary = navmap_observation_update_summary_v1(ctx)

    assert summary["schema"] == "navmap_observation_update_summary_v1"
    assert summary["status"] == "idle"
    assert summary["has_last_update"] is False
    assert summary["candidate_store_count"] == 0
    assert summary["history_count"] == 0
    assert summary["slots"] == {}

    lines = render_navmap_observation_update_lines_v1(ctx)
    assert lines[0] == "NAVMAP OBSERVATION UPDATE:"
    assert "status=idle" in lines[1]
    assert navmap_observation_update_mini_line_v1(ctx) == "[navmap] status=idle store_count=0 history_count=0"


def test_navmap_observation_update_summary_renders_active_update() -> None:
    """The NavMap summary/render helpers should expose the last diagnostic update."""
    ctx = Ctx()

    navmap_ctx_observation_update_step_v1(ctx, _fallen_mom_far_obs())
    summary = navmap_observation_update_summary_v1(ctx)

    assert summary["status"] == "active"
    assert summary["has_last_update"] is True
    assert summary["action"] == "create_candidate"
    assert summary["matched"] is False
    assert summary["changed"] is True
    assert summary["candidate_count_before"] == 0
    assert summary["candidate_count_after"] == 1
    assert summary["candidate_store_count"] == 1
    assert summary["history_count"] == 1
    assert summary["slot_count"] == 4
    assert summary["slots"]["posture"] == "fallen"
    assert summary["slots"]["mom_distance"] == "far"
    assert summary["slots"]["nipple_state"] == "hidden"
    assert summary["slots"]["zone"] == "unsafe"

    rendered = "\n".join(render_navmap_observation_update_lines_v1(ctx))
    assert "NAVMAP OBSERVATION UPDATE:" in rendered
    assert "action=create_candidate" in rendered
    assert "current_slots={" in rendered

    mini = navmap_observation_update_mini_line_v1(ctx)
    assert mini.startswith("[navmap] action=create_candidate")
    assert "posture=fallen" in mini
    assert "candidates=0->1" in mini


def test_navmap_transition_history_append_is_bounded_and_pure() -> None:
    """Transition history should use the same bounded-history semantics."""
    original = [{"n": 1}, {"n": 2}]

    bounded = navmap_transition_history_append_v1(original, {"n": 3}, limit=2)

    assert original == [{"n": 1}, {"n": 2}]
    assert bounded == [{"n": 2}, {"n": 3}]


def test_navmap_ctx_transition_from_payloads_stores_transition_and_policy_outcome() -> None:
    """A before/action/after map transition should be stored as ctx-local diagnostics."""
    ctx = Ctx()
    before_payload = {
        "schema": "navmap_payload_v1",
        "modality": "scene_body",
        "slots": {"posture": "fallen", "mom_distance": "far"},
        "confidence": 1.0,
        "source": "test",
        "basis": {},
        "created_at": "test",
    }
    after_payload = {
        "schema": "navmap_payload_v1",
        "modality": "scene_body",
        "slots": {"posture": "standing", "mom_distance": "near"},
        "confidence": 1.0,
        "source": "test",
        "basis": {},
        "created_at": "test",
    }
    ctx.navmap_pending_action_v1 = "policy:stand_up"
    ctx.navmap_pending_reward_v1 = 1.0

    transition = navmap_ctx_transition_from_payloads_v1(ctx, before_payload, after_payload)

    assert transition["schema"] == "navmap_transition_v1"
    assert transition["action"] == "policy:stand_up"
    assert transition["reward"] == 1.0
    assert transition["changed"] is True
    assert transition["before_payload"]["slots"]["posture"] == "fallen"
    assert transition["after_payload"]["slots"]["posture"] == "standing"
    assert len(ctx.navmap_transition_history_v1) == 1

    assert ctx.navmap_last_policy_outcome_v1 is not None
    assert ctx.navmap_last_policy_outcome_v1["schema"] == "navmap_policy_outcome_v1"
    assert ctx.navmap_last_policy_outcome_v1["action"] == "policy:stand_up"
    assert ctx.navmap_last_policy_outcome_v1["success"] is True
    assert len(ctx.navmap_policy_outcome_history_v1) == 1


def test_navmap_observation_update_step_records_transition_after_second_payload() -> None:
    """The observation bridge should seed the first payload and transition on the second."""
    ctx = Ctx()

    navmap_ctx_observation_update_step_v1(ctx, _fallen_mom_far_obs())
    assert ctx.navmap_last_payload_v1 is not None
    assert ctx.navmap_last_transition_v1 is None

    ctx.navmap_pending_action_v1 = "policy:stand_up"
    ctx.navmap_pending_reward_v1 = 1.0
    navmap_ctx_observation_update_step_v1(ctx, _standing_mom_near_obs())

    assert ctx.navmap_last_transition_v1 is not None
    assert ctx.navmap_last_transition_v1["action"] == "policy:stand_up"
    assert ctx.navmap_last_transition_v1["changed"] is True
    assert ctx.navmap_last_transition_v1["before_payload"]["slots"]["posture"] == "fallen"
    assert ctx.navmap_last_transition_v1["after_payload"]["slots"]["posture"] == "standing"
    assert len(ctx.navmap_transition_history_v1) == 1

    assert ctx.navmap_last_policy_outcome_v1 is not None
    assert ctx.navmap_last_policy_outcome_v1["action"] == "policy:stand_up"
    assert ctx.navmap_pending_action_v1 is None
    assert ctx.navmap_pending_reward_v1 == 0.0