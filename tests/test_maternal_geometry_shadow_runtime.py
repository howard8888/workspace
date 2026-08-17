# -*- coding: utf-8 -*-
"""Phase 4A tests for SELF-maternal common-frame geometry shadowing."""

from __future__ import annotations

import json
import math

import pytest

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_maternal_geometry import (
    MaternalProximityV1,
    maternal_geometry_evidence_from_observation_v1,
    maternal_geometry_readout_v1,
    maternal_geometry_shadow_observation_step_v1,
    render_maternal_geometry_shadow_lines_v1,
)
from cca8_navmap_kernel import (
    NavMapRefV1,
    NavSourceClassV1,
    follow_link,
    get_element,
    stored_relation,
)
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap() -> Ctx:
    """Return a context with the legacy BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(
    *,
    kid: tuple[float, float] = (0.0, 0.0),
    maternal: tuple[float, float] | None = (3.0, 0.0),
    proximity_predicate: str | None = "proximity:mom:far",
) -> EnvObservation:
    """Return one deterministic observation with explicit position metadata."""
    predicates = ["posture:standing"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    return EnvObservation(
        raw_sensors={"distance_to_mom": 999.0},
        predicates=predicates,
        cues=[],
        env_meta={
            "scenario_stage": "phase4a_test",
            "kid_position": {"x": float(kid[0]), "y": float(kid[1])},
            "mom_position": (
                {"x": float(maternal[0]), "y": float(maternal[1])}
                if maternal is not None
                else None
            ),
        },
    )


def _update_all(ctx: Ctx, env_obs: EnvObservation) -> dict[str, object]:
    """Update BodyMap, SELF-ground shadow, then the maternal geometry shadow."""
    update_body_world_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    return maternal_geometry_shadow_observation_step_v1(ctx, env_obs)


def test_common_frame_uses_self_origin_and_derives_distance_and_bearing() -> None:
    """Absolute simulated positions should become a SELF-centered relational map."""
    env_obs = _observation(kid=(10.0, 4.0), maternal=(13.0, 8.0))

    evidence, classification = maternal_geometry_evidence_from_observation_v1(
        env_obs,
        observation_no=1,
    )
    readout = maternal_geometry_readout_v1(evidence)

    assert classification == "position_input"
    self_point = get_element(evidence, "self_anchor").geometry.points[0]
    maternal_point = get_element(evidence, "maternal_individual").geometry.points[0]
    assert self_point.as_dict() == {"x": 0.0, "y": 0.0}
    assert maternal_point.as_dict() == {"x": 3.0, "y": 4.0}
    assert readout.valid is True
    assert readout.distance is not None
    assert readout.bearing is not None
    assert math.isclose(readout.distance.value, 5.0)
    assert math.isclose(readout.bearing.value, 53.13010235415598)
    assert readout.proximity is MaternalProximityV1.FAR


def test_symbolic_proximity_and_precomputed_distance_do_not_build_geometry() -> None:
    """Equivalent positions must yield equal evidence regardless of legacy labels/scalars."""
    far_labeled = _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:far")
    close_labeled = _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close")
    far_labeled.raw_sensors["distance_to_mom"] = 1000.0
    close_labeled.raw_sensors["distance_to_mom"] = 0.001

    first, _ = maternal_geometry_evidence_from_observation_v1(far_labeled, observation_no=1)
    second, _ = maternal_geometry_evidence_from_observation_v1(close_labeled, observation_no=1)

    assert first.to_bytes() == second.to_bytes()
    content_text = first.to_bytes().decode("utf-8").lower()
    for forbidden in ("proximity:mom", "mom_distance", "distance_to_mom"):
        assert forbidden not in content_text
    assert maternal_geometry_readout_v1(first).proximity is MaternalProximityV1.NEAR


def test_maternal_role_is_separate_from_identity_and_geometry_provenance() -> None:
    """The maternal role should be an explicit non-geometric relation with its own source."""
    evidence, _ = maternal_geometry_evidence_from_observation_v1(
        _observation(),
        observation_no=1,
    )

    maternal = get_element(evidence, "maternal_individual")
    relation = stored_relation(
        evidence,
        "maternal_caregiver_of",
        "maternal_individual",
        "self_anchor",
    )

    assert maternal.role == "individual_entity"
    assert maternal.provenance.source_class is NavSourceClassV1.OBSERVED
    assert relation.provenance.source_class is NavSourceClassV1.INFERRED
    assert relation.provenance.source_ref == "runtime:known_maternal_role_v1"
    assert relation.provenance != maternal.provenance


def test_symbolic_proximity_without_position_preserves_unknown_and_does_not_create_map() -> None:
    """A legacy far label must not fabricate maternal geometry when position evidence is absent."""
    ctx = _ctx_with_bodymap()

    row = _update_all(ctx, _observation(maternal=None, proximity_predicate="proximity:mom:far"))

    assert row["status"] == "deferred"
    assert row["input_classification"] == "maternal_position_missing"
    assert row["evidence_readout"]["valid"] is False
    assert row["evidence_readout"]["proximity"] == "unknown"
    assert row["legacy_mom_distance"] == "far"
    assert row["evidence_comparison"] == "map_unknown"
    assert row["stable_map_ref"] is None
    assert row["root_view_ref"] is None
    assert ctx.navmap_maternal_map is None
    assert ctx.navmap_maternal_root_view is None


def test_first_complete_observation_creates_stable_map_and_root_view() -> None:
    """Initial complete evidence should create a maintained map and linked root view."""
    ctx = _ctx_with_bodymap()

    row = _update_all(ctx, _observation())

    assert row["status"] == "created"
    assert row["authority"] == "shadow_only"
    assert row["map_can_trigger_follow_mom"] is False
    assert row["evidence_readout"]["proximity"] == "far"
    assert row["maintained_readout"]["proximity"] == "far"
    assert ctx.navmap_maternal_map is not None
    assert ctx.navmap_maternal_root_view is not None
    assert follow_link(
        ctx.navmap_maternal_root_view,
        link_type="self_maternal_submap",
        source_element_id="self_context",
    ) == NavMapRefV1(ctx.navmap_maternal_map.map_id, ctx.navmap_maternal_map.revision)


def test_root_view_preserves_self_ground_link_without_replacing_phase2_root() -> None:
    """Phase 4A should add a diagnostic maternal link while preserving Phase 3 state."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation())

    base_root = ctx.navmap_v2_shadow_root
    root_view = ctx.navmap_maternal_root_view
    body_map = ctx.navmap_v2_shadow_body_ground
    maternal_map = ctx.navmap_maternal_map

    assert base_root is not None
    assert root_view is not None
    assert body_map is not None
    assert maternal_map is not None
    base_bytes = base_root.to_bytes()
    assert follow_link(
        root_view,
        link_type="self_ground_submap",
        source_element_id="self_context",
    ) == NavMapRefV1(body_map.map_id, body_map.revision)
    assert follow_link(
        root_view,
        link_type="self_maternal_submap",
        source_element_id="self_context",
    ) == NavMapRefV1(maternal_map.map_id, maternal_map.revision)
    assert ctx.navmap_v2_shadow_root is base_root
    assert ctx.navmap_v2_shadow_root.to_bytes() == base_bytes
    assert root_view.map_id != base_root.map_id


def test_equivalent_positions_refresh_without_revision_churn() -> None:
    """Repeated equivalent evidence should reuse stable maternal/root revisions."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation()

    first = _update_all(ctx, env_obs)
    stable_map = ctx.navmap_maternal_map
    root_view = ctx.navmap_maternal_root_view
    second = _update_all(ctx, env_obs)

    assert first["status"] == "created"
    assert second["status"] == "reused"
    assert second["changed"] is False
    assert second["root_view_changed"] is False
    assert ctx.navmap_maternal_map is stable_map
    assert ctx.navmap_maternal_root_view is root_view
    assert second["maintenance_action"] == "refresh"


def test_changed_maternal_position_revises_only_maternal_entity_and_root_link() -> None:
    """A real position change should create local maternal and root-view child revisions."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(3.0, 0.0), proximity_predicate="proximity:mom:far"))
    previous_map = ctx.navmap_maternal_map
    previous_root = ctx.navmap_maternal_root_view

    row = _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))

    assert previous_map is not None
    assert previous_root is not None
    assert row["status"] == "revised"
    assert row["revision_proposal"]["decision"] == "revise"
    assert row["revision_proposal"]["changed_element_ids"] == ["maternal_individual"]
    assert ctx.navmap_maternal_map is not None
    assert ctx.navmap_maternal_root_view is not None
    assert ctx.navmap_maternal_map.revision == previous_map.revision + 1
    assert ctx.navmap_maternal_map.parent_ref == NavMapRefV1(previous_map.map_id, previous_map.revision)
    assert ctx.navmap_maternal_root_view.revision == previous_root.revision + 1
    assert ctx.navmap_maternal_root_view.parent_ref == NavMapRefV1(previous_root.map_id, previous_root.revision)
    assert row["maintained_readout"]["proximity"] == "near"


def test_bearing_change_in_same_declared_frame_cannot_be_aligned_away() -> None:
    """Equal-distance movement around SELF should revise because bearing changed."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(3.0, 0.0)))
    previous_map = ctx.navmap_maternal_map

    row = _update_all(ctx, _observation(maternal=(0.0, 3.0)))

    assert previous_map is not None
    assert row["status"] == "revised"
    assert row["evidence_readout"]["distance"]["value"] == 3.0
    assert row["evidence_readout"]["bearing"]["value"] == 90.0
    assert ctx.navmap_maternal_map is not None
    assert ctx.navmap_maternal_map.revision == previous_map.revision + 1


def test_one_missing_maternal_position_preserves_map_and_ages_support() -> None:
    """A missing position packet should remain UNKNOWN without erasing the stable map."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))
    stable_map = ctx.navmap_maternal_map
    root_view = ctx.navmap_maternal_root_view

    row = _update_all(ctx, _observation(maternal=None, proximity_predicate=None))

    assert row["status"] == "maintained"
    assert row["input_classification"] == "maternal_position_missing"
    assert row["evidence_readout"]["proximity"] == "unknown"
    assert row["maintained_readout"]["proximity"] == "near"
    assert row["support_status"] == "aging"
    assert row["support_age_observations"] == 1
    assert ctx.navmap_maternal_map is stable_map
    assert ctx.navmap_maternal_root_view is root_view


def test_repeated_missing_position_becomes_stale_then_invalidated() -> None:
    """Unsupported maternal geometry should lose current status under the bounded rule."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))

    first_missing = _update_all(ctx, _observation(maternal=None, proximity_predicate=None))
    second_missing = _update_all(ctx, _observation(maternal=None, proximity_predicate=None))
    third_missing = _update_all(ctx, _observation(maternal=None, proximity_predicate=None))

    assert first_missing["support_status"] == "aging"
    assert second_missing["support_status"] == "stale"
    assert second_missing["stable_map_ref"] is not None
    assert third_missing["status"] == "invalidated"
    assert third_missing["stable_map_ref"] is None
    assert third_missing["root_view_ref"] is None
    assert third_missing["last_stable_map_ref"] is not None
    assert third_missing["last_stable_readout"]["proximity"] == "near"


def test_matching_evidence_reinstates_same_stable_revision_after_invalidation() -> None:
    """Returning equivalent evidence should reinstate rather than duplicate stable content."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))
    stable_map = ctx.navmap_maternal_map
    root_view = ctx.navmap_maternal_root_view
    for _ in range(3):
        _update_all(ctx, _observation(maternal=None, proximity_predicate=None))

    row = _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))

    assert row["status"] == "reinstated"
    assert row["maintenance_action"] == "reinstate"
    assert row["changed"] is False
    assert ctx.navmap_maternal_map is stable_map
    assert ctx.navmap_maternal_root_view is root_view
    assert row["support_status"] == "fresh"


def test_geometry_bodymap_disagreement_is_recorded_without_mutating_bodymap() -> None:
    """Shadow geometry may disagree with legacy proximity while BodyMap remains unchanged."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(4.0, 0.0), proximity_predicate="proximity:mom:close")
    update_body_world_from_obs(ctx, env_obs)
    mom_id = ctx.body_ids["mom"]
    before_tags = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)

    row = maternal_geometry_shadow_observation_step_v1(ctx, env_obs)

    assert row["evidence_readout"]["proximity"] == "far"
    assert row["legacy_mom_distance"] == "near"
    assert row["evidence_comparison"] == "disagree"
    assert row["maintained_comparison"] == "disagree"
    after_tags = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_touching_geometry_preserves_distance_and_explicitly_undefined_bearing() -> None:
    """Coincident SELF/maternal points should derive touching without inventing a bearing."""
    evidence, _ = maternal_geometry_evidence_from_observation_v1(
        _observation(maternal=(0.0, 0.0), proximity_predicate="proximity:mom:close"),
        observation_no=1,
    )

    readout = maternal_geometry_readout_v1(evidence)

    assert readout.valid is True
    assert readout.distance is not None
    assert readout.distance.value == 0.0
    assert readout.bearing is None
    assert readout.proximity is MaternalProximityV1.TOUCHING
    assert readout.reason == "coincident_positions_bearing_undefined"


def test_live_observation_runtime_populates_phase4a_without_changing_v1_return() -> None:
    """The existing observation callback should run Phase 4A after Phase 2 shadowing."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation()
    update_body_world_from_obs(ctx, env_obs)

    v1_update = navmap_ctx_observation_update_step_v1(ctx, env_obs)

    assert v1_update["schema"] == "navmap_observation_update_v1"
    assert ctx.navmap_maternal_last_update is not None
    assert ctx.navmap_maternal_last_update["status"] == "created"
    assert ctx.navmap_maternal_last_update["evidence_readout"]["distance"]["value"] == 3.0
    assert ctx.navmap_maternal_last_update["map_can_trigger_follow_mom"] is False


def test_disabled_phase4a_path_has_no_context_side_effects() -> None:
    """The runtime flag should disable maternal shadow construction cleanly."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_maternal_shadow_enabled = False

    row = maternal_geometry_shadow_observation_step_v1(ctx, _observation())

    assert row["status"] == "disabled"
    assert ctx.navmap_maternal_evidence_map is None
    assert ctx.navmap_maternal_map is None
    assert ctx.navmap_maternal_root_view is None
    assert ctx.navmap_maternal_state is None
    assert ctx.navmap_maternal_last_update is None
    assert ctx.navmap_maternal_history == []


def test_history_is_bounded_and_json_safe() -> None:
    """Phase 4A traces should remain bounded and strictly JSON serializable."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_maternal_history_limit = 2

    _update_all(ctx, _observation(maternal=(3.0, 0.0)))
    _update_all(ctx, _observation(maternal=(0.5, 0.0), proximity_predicate="proximity:mom:close"))
    _update_all(ctx, _observation(maternal=None, proximity_predicate=None))

    assert len(ctx.navmap_maternal_history) == 2
    json.dumps(ctx.navmap_maternal_history, allow_nan=False, sort_keys=True)
    assert ctx.navmap_maternal_history[-1]["evidence_readout"]["proximity"] == "unknown"


def test_renderer_reports_geometry_role_separation_and_authority_boundary() -> None:
    """The human trace should expose common-frame computation without claiming authority."""
    ctx = _ctx_with_bodymap()
    _update_all(ctx, _observation(maternal=(3.0, 4.0)))

    text = "\n".join(render_maternal_geometry_shadow_lines_v1(ctx))

    assert "MATERNAL GEOMETRY PHASE 4A SHADOW:" in text
    assert "authority=shadow_only" in text
    assert "follow_mom_authority=legacy_bodymap_policy_runtime" in text
    assert "distance=5.000" in text
    assert "bearing=53.1deg" in text
    assert "role_relation=maternal_caregiver_of" in text
    assert "root_view_is_accepted_wnm=False" in text


def test_cycle_json_exposes_phase4a_maternal_shadow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should expose the maternal geometry shadow."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    world = WorldGraph()
    world.ensure_anchor("NOW")

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    assert ctx.cycle_json_records
    summary = ctx.cycle_json_records[-1]["maternal_geometry_shadow"]
    assert summary["schema"] == "maternal_geometry_shadow_summary_v1"
    assert summary["phase"] == "4A"
    assert summary["authority"] == "shadow_only"
    assert summary["map_can_trigger_follow_mom"] is False
    assert summary["evidence_readout"]["valid"] is True
