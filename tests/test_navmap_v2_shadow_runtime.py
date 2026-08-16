# -*- coding: utf-8 -*-
"""Phase 2A/2B tests for the NavMapV2 root/SELF-ground shadow."""

from __future__ import annotations

import json

from cca8_context import Ctx
from cca8_env import EnvObservation
from cca8_navmap_kernel import (
    NavBodyStateInterpretationV1,
    NavMapRefV1,
    follow_link,
)
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import (
    navmap_v2_body_ground_from_observation_v1,
    navmap_v2_shadow_observation_step_v1,
    render_navmap_v2_shadow_lines_v1,
)
from cca8_observation_runtime import init_body_world, update_body_world_from_obs


def _ctx_with_bodymap() -> Ctx:
    """Return a context with the legacy BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(*predicates: str) -> EnvObservation:
    """Return one minimal interpreted observation packet."""
    return EnvObservation(
        raw_sensors={},
        predicates=list(predicates),
        cues=[],
        env_meta={"scenario_stage": "phase2_test"},
    )


def _update_both(ctx: Ctx, env_obs: EnvObservation) -> dict[str, object]:
    """Update authoritative BodyMap, then run the NavMapV2 shadow step."""
    update_body_world_from_obs(ctx, env_obs)
    return navmap_v2_shadow_observation_step_v1(ctx, env_obs)


def test_standing_observation_creates_root_and_body_shadow_that_agree_with_bodymap() -> None:
    """Standing evidence should create a linked root shadow and STANDING_LIKE readout."""
    ctx = _ctx_with_bodymap()

    row = _update_both(ctx, _observation("posture:standing"))

    assert row["status"] == "created"
    assert row["authority"] == "shadow_only"
    assert row["legacy_authority"] == "bodymap"
    assert row["comparison"] == "agree"
    assert row["body_state"]["interpretation"] == "standing_like"
    assert ctx.navmap_v2_shadow_state is not None
    assert ctx.navmap_v2_shadow_state.body_state.interpretation is NavBodyStateInterpretationV1.STANDING_LIKE
    assert ctx.navmap_v2_shadow_root is not None
    assert ctx.navmap_v2_shadow_body_ground is not None
    target_ref = follow_link(
        ctx.navmap_v2_shadow_root,
        source_element_id="self_context",
        link_type="self_ground_submap",
    )
    assert target_ref == NavMapRefV1(
        ctx.navmap_v2_shadow_body_ground.map_id,
        ctx.navmap_v2_shadow_body_ground.revision,
    )


def test_fallen_observation_derives_fallen_like_and_agrees_with_bodymap() -> None:
    """Fallen evidence should derive a lateral-ground pattern without a stored posture field."""
    ctx = _ctx_with_bodymap()

    row = _update_both(ctx, _observation("posture:fallen"))

    assert row["comparison"] == "agree"
    assert row["body_state"]["interpretation"] == "fallen_like"
    support = row["body_state"]["support"]
    assert support["body_ground_angle"]["value"] == 0.0
    assert support["lateral_contact"]["fraction"] == 1.0


def test_equivalent_observation_reuses_existing_shadow_revisions() -> None:
    """Repeated equivalent evidence should not create meaningless map revisions."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation("posture:standing")

    first = _update_both(ctx, env_obs)
    first_body = ctx.navmap_v2_shadow_body_ground
    first_root = ctx.navmap_v2_shadow_root
    second = _update_both(ctx, env_obs)

    assert first["status"] == "created"
    assert second["status"] == "reused"
    assert second["changed"] is False
    assert ctx.navmap_v2_shadow_body_ground is first_body
    assert ctx.navmap_v2_shadow_root is first_root
    assert second["body_ground_ref"] == first["body_ground_ref"]
    assert second["root_ref"] == first["root_ref"]


def test_meaningful_geometry_change_creates_child_revisions() -> None:
    """Standing-to-fallen evidence should revise both linked shadow map families."""
    ctx = _ctx_with_bodymap()

    _update_both(ctx, _observation("posture:standing"))
    previous_body = ctx.navmap_v2_shadow_body_ground
    previous_root = ctx.navmap_v2_shadow_root
    row = _update_both(ctx, _observation("posture:fallen"))

    assert previous_body is not None
    assert previous_root is not None
    assert row["status"] == "revised"
    assert row["changed"] is True
    assert ctx.navmap_v2_shadow_body_ground is not None
    assert ctx.navmap_v2_shadow_root is not None
    assert ctx.navmap_v2_shadow_body_ground.revision == previous_body.revision + 1
    assert ctx.navmap_v2_shadow_body_ground.parent_ref == NavMapRefV1(previous_body.map_id, previous_body.revision)
    assert ctx.navmap_v2_shadow_root.revision == previous_root.revision + 1
    assert ctx.navmap_v2_shadow_root.parent_ref == NavMapRefV1(previous_root.map_id, previous_root.revision)


def test_missing_or_conflicting_posture_evidence_preserves_unknown() -> None:
    """The adapter should not force a body-state answer from inadequate input."""
    for env_obs, input_classification in (
        (_observation("proximity:mom:far"), "unknown_input"),
        (_observation("posture:standing", "posture:fallen"), "conflicting_input"),
    ):
        ctx = _ctx_with_bodymap()
        row = navmap_v2_shadow_observation_step_v1(ctx, env_obs)

        assert row["input_classification"] == input_classification
        assert row["body_state"]["interpretation"] == "unknown"
        assert row["body_state"]["reason"] == "missing_required_elements"
        assert row["comparison"] in {"not_comparable", "map_unknown"}


def test_shadow_map_bytes_do_not_store_posture_standing_or_fallen_shortcuts() -> None:
    """Canonical geometry may differ, but forbidden posture labels must not enter map content."""
    standing, _ = navmap_v2_body_ground_from_observation_v1(
        _observation("posture:standing"),
        revision=1,
    )
    fallen, _ = navmap_v2_body_ground_from_observation_v1(
        _observation("posture:fallen"),
        revision=1,
    )

    for navmap in (standing, fallen):
        text = navmap.to_bytes().decode("utf-8").lower()
        for forbidden in ("posture", "standing", "fallen", "is_standing", "is_fallen"):
            assert forbidden not in text
    assert standing.content_signature() != fallen.content_signature()


def test_shadow_disagreement_is_recorded_without_changing_authoritative_bodymap() -> None:
    """A map/BodyMap disagreement should remain diagnostic and leave BodyMap untouched."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    posture_id = ctx.body_ids["posture"]
    before_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access

    row = navmap_v2_shadow_observation_step_v1(ctx, _observation("posture:fallen"))

    assert row["body_state"]["interpretation"] == "fallen_like"
    assert row["legacy_bodymap_posture"] == "standing"
    assert row["comparison"] == "disagree"
    after_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_disabled_shadow_path_has_no_ctx_side_effects() -> None:
    """The runtime flag should disable the shadow bridge without clearing or inventing state."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_v2_shadow_enabled = False

    row = navmap_v2_shadow_observation_step_v1(ctx, _observation("posture:standing"))

    assert row["status"] == "disabled"
    assert ctx.navmap_v2_shadow_body_ground is None
    assert ctx.navmap_v2_shadow_root is None
    assert ctx.navmap_v2_shadow_state is None
    assert ctx.navmap_v2_shadow_last_update is None
    assert ctx.navmap_v2_shadow_history == []


def test_existing_observation_runtime_hook_populates_v2_shadow_without_changing_v1_return() -> None:
    """The live observation callback should now run the V2 shadow after its existing V1 work."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation("posture:fallen")
    update_body_world_from_obs(ctx, env_obs)

    v1_update = navmap_ctx_observation_update_step_v1(ctx, env_obs)

    assert v1_update["schema"] == "navmap_observation_update_v1"
    assert ctx.navmap_v2_shadow_last_update is not None
    assert ctx.navmap_v2_shadow_last_update["body_state"]["interpretation"] == "fallen_like"
    assert ctx.navmap_v2_shadow_last_update["comparison"] == "agree"


def test_shadow_history_is_bounded_and_json_safe() -> None:
    """Shadow traces should remain bounded, deterministic, and serializable."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_v2_shadow_history_limit = 2

    _update_both(ctx, _observation("posture:standing"))
    _update_both(ctx, _observation("posture:fallen"))
    _update_both(ctx, _observation("proximity:mom:far"))

    assert len(ctx.navmap_v2_shadow_history) == 2
    json.dumps(ctx.navmap_v2_shadow_history, allow_nan=False, sort_keys=True)
    assert ctx.navmap_v2_shadow_history[-1]["body_state"]["interpretation"] == "unknown"


def test_shadow_rendering_reports_refs_comparison_and_authority_boundary() -> None:
    """The trace renderer should make shadow status and BodyMap authority explicit."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:standing"))

    lines = render_navmap_v2_shadow_lines_v1(ctx)
    text = "\n".join(lines)

    assert "NAVMAP V2 SHADOW:" in text
    assert "authority=shadow_only legacy_authority=bodymap" in text
    assert "derived=standing_like" in text
    assert "legacy=standing comparison=agree" in text
    assert "goat_root_scene_v2@r1" in text
    assert "goat_self_ground_v2@r1" in text


def test_shadow_maps_have_no_runtime_authority_attributes() -> None:
    """Neither root nor submap may smuggle current-world authority into NavMapV2."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:fallen"))

    assert ctx.navmap_v2_shadow_root is not None
    assert ctx.navmap_v2_shadow_body_ground is not None
    for navmap in (ctx.navmap_v2_shadow_root, ctx.navmap_v2_shadow_body_ground):
        for forbidden in ("candidate", "active", "focused", "accepted", "root_wnm", "authoritative"):
            assert not hasattr(navmap, forbidden)


def test_missing_evidence_maintains_standing_and_ages_support_without_revision_churn() -> None:
    """One posture-less packet should age support without erasing stable standing content."""
    ctx = _ctx_with_bodymap()
    created = _update_both(ctx, _observation("posture:standing"))
    body_map = ctx.navmap_v2_shadow_body_ground
    root_map = ctx.navmap_v2_shadow_root

    assert body_map is not None
    assert root_map is not None
    body_bytes = body_map.to_bytes()
    root_bytes = root_map.to_bytes()
    row = _update_both(ctx, _observation("proximity:mom:far"))

    assert created["body_ground_ref"] == {"map_id": body_map.map_id, "revision": body_map.revision}
    assert row["status"] == "maintained"
    assert row["body_state"]["interpretation"] == "unknown"
    assert row["maintained_body_state"]["interpretation"] == "standing_like"
    assert row["current_shadow_maintained"] is True
    assert row["maintenance_action"] == "maintain_missing"
    assert row["support_status"] == "aging"
    assert row["support_age_observations"] == 1
    assert row["changed"] is False
    assert ctx.navmap_v2_shadow_body_ground is body_map
    assert ctx.navmap_v2_shadow_root is root_map
    assert body_map.to_bytes() == body_bytes
    assert root_map.to_bytes() == root_bytes
    assert ctx.navmap_v2_shadow_evidence_body_ground is not None
    assert [element.element_id for element in ctx.navmap_v2_shadow_evidence_body_ground.elements] == ["ground_surface"]


def test_repeated_missing_evidence_becomes_stale_then_invalidates_under_declared_bound() -> None:
    """The default two-observation maintenance window should not persist unsupported content forever."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_v2_shadow_max_missing_observations = 2
    _update_both(ctx, _observation("posture:standing"))
    body_map = ctx.navmap_v2_shadow_body_ground
    root_map = ctx.navmap_v2_shadow_root

    first_missing = _update_both(ctx, _observation("proximity:mom:far"))
    second_missing = _update_both(ctx, _observation("proximity:mom:far"))
    third_missing = _update_both(ctx, _observation("proximity:mom:far"))

    assert body_map is not None
    assert root_map is not None
    assert first_missing["support_status"] == "aging"
    assert first_missing["current_shadow_maintained"] is True
    assert second_missing["support_status"] == "stale"
    assert second_missing["support_age_observations"] == 2
    assert second_missing["current_shadow_maintained"] is True
    assert third_missing["status"] == "invalidated"
    assert third_missing["support_status"] == "invalidated"
    assert third_missing["support_age_observations"] == 3
    assert third_missing["current_shadow_maintained"] is False
    assert third_missing["body_ground_ref"] is None
    assert third_missing["root_ref"] is None
    assert third_missing["last_stable_body_ground_ref"] == {"map_id": body_map.map_id, "revision": 1}
    assert third_missing["last_stable_root_ref"] == {"map_id": root_map.map_id, "revision": 1}
    assert ctx.navmap_v2_shadow_body_ground is body_map
    assert ctx.navmap_v2_shadow_root is root_map


def test_compatible_evidence_after_gap_refreshes_support_and_reuses_revision() -> None:
    """Equivalent standing evidence should refresh support without manufacturing r2."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:standing"))
    body_map = ctx.navmap_v2_shadow_body_ground
    root_map = ctx.navmap_v2_shadow_root
    _update_both(ctx, _observation("proximity:mom:far"))

    row = _update_both(ctx, _observation("posture:standing"))

    assert body_map is not None
    assert root_map is not None
    assert row["status"] == "reused"
    assert row["maintenance_action"] == "refresh"
    assert row["evidence_relation"] == "compatible"
    assert row["support_status"] == "fresh"
    assert row["support_age_observations"] == 0
    assert row["last_supported_observation_no"] == 3
    assert row["revision_proposal"]["decision"] == "keep"
    assert row["changed"] is False
    assert ctx.navmap_v2_shadow_body_ground is body_map
    assert ctx.navmap_v2_shadow_root is root_map
    assert body_map.revision == 1
    assert root_map.revision == 1


def test_compatible_evidence_after_invalidation_reinstates_same_stable_revision() -> None:
    """A valid old map may re-enter the shadow current set without a content revision."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_v2_shadow_max_missing_observations = 1
    _update_both(ctx, _observation("posture:standing"))
    body_map = ctx.navmap_v2_shadow_body_ground
    root_map = ctx.navmap_v2_shadow_root
    _update_both(ctx, _observation("proximity:mom:far"))
    invalidated = _update_both(ctx, _observation("proximity:mom:far"))

    row = _update_both(ctx, _observation("posture:standing"))

    assert body_map is not None
    assert root_map is not None
    assert invalidated["current_shadow_maintained"] is False
    assert row["status"] == "reinstated"
    assert row["maintenance_action"] == "reinstate"
    assert row["current_shadow_maintained"] is True
    assert row["revision_proposal"]["decision"] == "keep"
    assert row["changed"] is False
    assert ctx.navmap_v2_shadow_body_ground is body_map
    assert ctx.navmap_v2_shadow_root is root_map


def test_reliable_fallen_evidence_produces_structured_residual_and_child_revisions() -> None:
    """Reliable contradiction must defeat maintained standing and expose the local geometry change."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:standing"))
    previous_body = ctx.navmap_v2_shadow_body_ground
    previous_root = ctx.navmap_v2_shadow_root
    _update_both(ctx, _observation("proximity:mom:far"))

    row = _update_both(ctx, _observation("posture:fallen"))

    assert previous_body is not None
    assert previous_root is not None
    assert row["status"] == "revised"
    assert row["maintenance_action"] == "revise"
    assert row["evidence_relation"] == "contradictory"
    assert row["structured_residual"]["has_content_difference"] is True
    assert row["structured_residual"]["reason"] == "content_changed"
    assert row["revision_proposal"]["decision"] == "revise"
    assert row["revision_proposal"]["changed_element_ids"] == ["self_body", "self_foot", "self_head"]
    assert row["maintained_body_state"]["interpretation"] == "fallen_like"
    assert row["current_shadow_maintained"] is True
    assert row["support_status"] == "fresh"
    assert ctx.navmap_v2_shadow_body_ground is not None
    assert ctx.navmap_v2_shadow_body_ground.revision == previous_body.revision + 1
    assert ctx.navmap_v2_shadow_body_ground.parent_ref == NavMapRefV1(previous_body.map_id, previous_body.revision)
    assert ctx.navmap_v2_shadow_root is not None
    assert ctx.navmap_v2_shadow_root.revision == previous_root.revision + 1
    assert ctx.navmap_v2_shadow_root.parent_ref == NavMapRefV1(previous_root.map_id, previous_root.revision)


def test_conflicting_evidence_remains_unknown_and_uses_ambiguous_maintenance_path() -> None:
    """Conflicting interpreted posture inputs must not force either stable body geometry."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:standing"))
    body_map = ctx.navmap_v2_shadow_body_ground

    row = _update_both(ctx, _observation("posture:standing", "posture:fallen"))

    assert body_map is not None
    assert row["body_state"]["interpretation"] == "unknown"
    assert row["evidence_relation"] == "ambiguous"
    assert row["maintenance_action"] == "maintain_ambiguous"
    assert row["current_shadow_maintained"] is True
    assert row["maintained_body_state"]["interpretation"] == "standing_like"
    assert row["revision_proposal"] is None
    assert row["structured_residual"] is None
    assert ctx.navmap_v2_shadow_body_ground is body_map


def test_phase2b_renderer_separates_current_evidence_from_maintained_shadow() -> None:
    """The manual trace should make UNKNOWN evidence and provisional standing visible together."""
    ctx = _ctx_with_bodymap()
    _update_both(ctx, _observation("posture:standing"))
    _update_both(ctx, _observation("proximity:mom:far"))

    text = "\n".join(render_navmap_v2_shadow_lines_v1(ctx))

    assert "derived=unknown input=unknown_input" in text
    assert "maintained=True action=maintain_missing support=aging age=1/2" in text
    assert "body=goat_self_ground_v2@r1 derived=standing_like" in text
    assert "authority=shadow_only legacy_authority=bodymap" in text
