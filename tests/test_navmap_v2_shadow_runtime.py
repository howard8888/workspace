# -*- coding: utf-8 -*-
"""Phase 2A tests for the first live NavMapV2 root/SELF-ground shadow."""

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
