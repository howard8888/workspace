from __future__ import annotations

from cca8_context import Ctx
from cca8_env import EnvObservation
import cca8_column
import cca8_controller
import cca8_run
from cca8_working_memory import (
    init_working_world,
    inject_obs_into_working_world,
    merge_mapsurface_payload_v1_into_workingmap,
    _newborn_active_retrieved_hint_v1,
)


def _ctx_with_workingmap() -> Ctx:
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.experiment_newborn_explicit_missingness = True
    ctx.experiment_newborn_require_current_state = True
    ctx.experiment_newborn_direct_hint_enabled = False
    return ctx


def _entity_tags(ctx: Ctx, eid: str) -> set[str]:
    bid = ctx.wm_entities[eid]
    binding = ctx.working_world._bindings[bid]  # pylint: disable=protected-access
    return set(binding.tags or [])


def test_masked_predicate_creates_workingmap_gap_then_guarded_merge_repairs_it() -> None:
    ctx = _ctx_with_workingmap()

    first = EnvObservation(
        predicates=["posture:standing", "proximity:mom:far"],
        env_meta={},
    )
    inject_obs_into_working_world(ctx, first)
    assert "pred:proximity:mom:far" in _entity_tags(ctx, "mom")

    masked = EnvObservation(
        predicates=["posture:standing"],
        env_meta={"obs_mask_dropped_pred_tokens": ["proximity:mom:far"]},
    )
    info = inject_obs_into_working_world(ctx, masked)
    assert info["mask_invalidation"]["invalidated_family_count"] == 1
    assert not any(tag.startswith("pred:proximity:mom:") for tag in _entity_tags(ctx, "mom"))

    payload = {
        "entities": [
            {"eid": "self", "kind": "agent", "preds": ["posture:standing"], "cues": []},
            {
                "eid": "mom",
                "kind": "agent",
                "preds": ["proximity:mom:far"],
                "cues": [],
                "pos": {"x": 1.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": 1.0,
                "dist_class": "far",
            },
        ],
        "relations": [
            {"src": "self", "dst": "mom", "rel": "distance_to", "meters": 1.0, "class": "far"}
        ],
    }
    load = merge_mapsurface_payload_v1_into_workingmap(ctx, payload, reason="test")
    assert load["filled_slots"] == 1
    assert "mom:proximity:mom" in load["repaired_families"]
    assert "pred:proximity:mom:far" in _entity_tags(ctx, "mom")

    mom_bid = ctx.wm_entities["mom"]
    meta = ctx.working_world._bindings[mom_bid].meta["wm"]  # pylint: disable=protected-access
    assert meta["source_by_family"]["proximity:mom"]["source"] == "retrieved_guarded"


def test_visible_same_family_observation_wins_over_mask_metadata() -> None:
    ctx = _ctx_with_workingmap()
    inject_obs_into_working_world(
        ctx,
        EnvObservation(predicates=["proximity:mom:far"], env_meta={}),
    )

    info = inject_obs_into_working_world(
        ctx,
        EnvObservation(
            predicates=["proximity:mom:close"],
            env_meta={"obs_mask_dropped_pred_tokens": ["proximity:mom:far"]},
        ),
    )
    assert info["mask_invalidation"]["requested_family_count"] == 0
    tags = _entity_tags(ctx, "mom")
    assert "pred:proximity:mom:close" in tags
    assert "pred:proximity:mom:far" not in tags


def test_bodymap_missing_nipple_observation_remains_unknown() -> None:
    ctx = Ctx()
    ctx.experiment_newborn_explicit_missingness = True
    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()

    cca8_run.update_body_world_from_obs(
        ctx,
        EnvObservation(predicates=["posture:standing", "nipple:found"]),
    )
    assert cca8_run.body_nipple_state(ctx) == "found"

    cca8_run.update_body_world_from_obs(
        ctx,
        EnvObservation(predicates=["posture:standing"]),
    )
    assert cca8_run.body_nipple_state(ctx) is None


def test_publication_benchmark_disables_direct_hint_path() -> None:
    ctx = Ctx()
    ctx.experiment_newborn_direct_hint_enabled = False
    ctx.experiment_newborn_retrieved_hint = {"mom_distance": "near"}
    ctx.experiment_newborn_retrieved_hint_until_step = 100
    assert _newborn_active_retrieved_hint_v1(ctx) == {}


def test_recent_retrieval_requires_structural_change() -> None:
    ctx = Ctx()
    ctx.controller_steps = 10
    ctx.wm_mapswitch_last_events = [
        {
            "ok": True,
            "step": 9,
            "load": {
                "mode": "merge",
                "added_entities": 0,
                "filled_slots": 0,
                "added_edges": 0,
                "filled_metadata": 0,
                "stored_prior_cues": 4,
            },
        }
    ]
    assert cca8_run._newborn_recent_retrieval_ok_v1(ctx) is False

    ctx.wm_mapswitch_last_events[-1]["load"]["filled_slots"] = 1
    assert cca8_run._newborn_recent_retrieval_ok_v1(ctx) is True


def test_strict_gate_can_consult_guarded_repaired_workingmap_state() -> None:
    ctx = _ctx_with_workingmap()
    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()

    # BodyMap receives no mom-distance token, so the strict gate must consult WM.
    cca8_run.update_body_world_from_obs(ctx, EnvObservation(predicates=["posture:standing"]))
    inject_obs_into_working_world(
        ctx,
        EnvObservation(
            predicates=["posture:standing"],
            env_meta={"obs_mask_dropped_pred_tokens": ["proximity:mom:far"]},
        ),
    )
    merge_mapsurface_payload_v1_into_workingmap(
        ctx,
        {
            "entities": [
                {"eid": "self", "kind": "agent", "preds": ["posture:standing"], "cues": []},
                {"eid": "mom", "kind": "agent", "preds": ["proximity:mom:far"], "cues": []},
            ],
            "relations": [],
        },
        reason="test",
    )

    state = cca8_run._follow_mom_bridge_state_v1(None, ctx)
    assert state["mom_distance"] == "far"
    assert ctx.experiment_newborn_guarded_use_count >= 1
    assert any(event.get("field") == "mom_distance" for event in ctx.experiment_newborn_guarded_use_events)


def _run_route_loss_episode(tmp_path, condition: str) -> dict:
    """Run one clean mechanism-integration episode for a fixed paired seed."""
    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()

    ctx = Ctx()
    cfg = ctx.experiment_cfg
    cfg.benchmark_id = "newborn_long_horizon"
    cfg.output_dir = str(tmp_path / condition)
    cfg.run_label = "mechanism_integration"
    cfg.newborn_stress_profile = "route_loss"
    cfg.newborn_blackout_length = 12
    cfg.obs_mask_prob = 0.50
    cfg.max_cycles = 60
    cfg.condition_ids = [condition]
    cfg.seed_list = [955014]

    result = cca8_run.experiment_run_one_episode_v1(
        ctx,
        condition_id=condition,
        seed=955014,
        episode_index=0,
        suppress_output=True,
    )
    assert result.get("ok") is True
    return result["episode_record"]


def test_route_loss_uses_structural_guarded_repair_without_direct_hint(tmp_path) -> None:
    guarded = _run_route_loss_episode(tmp_path, "A")
    disabled = _run_route_loss_episode(tmp_path, "B")

    assert guarded["newborn_retrieval_non_noop_count_to_completion"] > 0
    assert guarded["newborn_repair_filled_slot_total_to_completion"] > 0
    assert guarded["newborn_workingmap_invalidated_family_total_to_completion"] > 0
    assert guarded["newborn_guarded_field_use_count_to_completion"] > 0
    assert guarded["newborn_retrieved_hint_set_count"] == 0
    assert guarded["newborn_retrieved_hint_used_step_count"] == 0

    assert disabled["newborn_retrieval_event_count_to_completion"] == 0
    assert disabled["newborn_retrieval_non_noop_count_to_completion"] == 0
    assert disabled["newborn_guarded_field_use_count_to_completion"] == 0
