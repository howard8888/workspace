# -*- coding: utf-8 -*-
"""Phase 5 tests for the single-operative WNM and bounded ready set."""

from __future__ import annotations

import json

from cca8_context import Ctx
from cca8_navmap_kernel import NavFrameV1, NavMapRefV1, NavMapV2, NavProvenanceV1, NavSourceClassV1
from cca8_wnm_runtime import (
    WNMTransitionTypeV1,
    render_wnm_lines_v1,
    wnm_commit_transition_v1,
    wnm_map_by_role_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
    wnm_refresh_map_v1,
    wnm_return_to_ref_v1,
    wnm_summary_v1,
)


def _map(map_id: str, role: str, *, revision: int = 1, frame_id: str | None = None) -> NavMapV2:
    """Return one minimal immutable map suitable for WNM transition tests."""
    provenance = NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=f"test:{map_id}:r{revision}",
        quality=0.9,
    )
    return NavMapV2(
        map_id=map_id,
        revision=revision,
        role=role,
        frame=NavFrameV1(
            frame_id=frame_id or f"{map_id}_frame",
            x_axis="x_axis",
            y_axis="y_axis",
            units="m",
            min_x=-10.0,
            max_x=10.0,
            min_y=-10.0,
            max_y=10.0,
        ),
        provenance=provenance,
        parent_ref=(NavMapRefV1(map_id, revision - 1) if revision > 1 else None),
    )


def _commit(
    ctx: Ctx,
    destination: NavMapV2,
    transition_type: WNMTransitionTypeV1,
    *,
    observation_no: int,
    support: float = 1.0,
    ambiguous: bool = False,
    expected_source_ref: NavMapRefV1 | None = None,
) -> dict[str, object]:
    """Commit one deterministic transition with concise test correspondence."""
    return wnm_commit_transition_v1(
        ctx,
        destination,
        transition_type=transition_type,
        observation_no=observation_no,
        reason=f"test_{transition_type.value}_{destination.role}",
        identity_handle="entity:shared",
        correspondence_basis="unit_test_explicit_identity_and_frame",
        support=support,
        correspondence_ambiguous=ambiguous,
        expected_source_ref=expected_source_ref,
    )


def test_initialize_establishes_exactly_one_operative_map() -> None:
    """Initialization should establish one operative substrate and no ready map."""
    ctx = Ctx()
    overview = _map("overview", "scene_overview")

    summary = _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    assert wnm_operative_map_v1(ctx) is overview
    assert wnm_ready_maps_v1(ctx) == ()
    assert summary["operative_count"] == 1
    assert summary["at_most_one_operative"] is True
    assert summary["ready_has_equal_authority"] is False
    assert summary["last_transition"]["accepted"] is True
    assert summary["last_transition"]["transition_type"] == "initialize"


def test_zoom_changes_the_real_operative_substrate_and_moves_prior_map_to_ready() -> None:
    """A committed zoom must change the map object queried as operative."""
    ctx = Ctx()
    overview = _map("overview", "scene_overview")
    detail = _map("detail", "maternal_detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        detail,
        WNMTransitionTypeV1.ZOOM_IN,
        observation_no=2,
        expected_source_ref=NavMapRefV1("overview", 1),
    )

    assert wnm_operative_map_v1(ctx) is detail
    assert wnm_ready_maps_v1(ctx) == (overview,)
    assert summary["operative_map"]["role"] == "maternal_detail"
    assert summary["ready_set"][0]["role"] == "scene_overview"
    assert summary["ready_set"][0]["operative_authority"] is False


def test_role_lookup_is_addressability_only_and_does_not_promote_ready_map() -> None:
    """Looking up a ready map must not change operative authority."""
    ctx = Ctx()
    overview = _map("overview", "scene_overview")
    detail = _map("detail", "maternal_detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, detail, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)

    found = wnm_map_by_role_v1(ctx, "scene_overview")

    assert found is overview
    assert wnm_operative_map_v1(ctx) is detail
    assert wnm_ready_maps_v1(ctx) == (overview,)


def test_ready_set_bound_evicts_the_deterministic_least_recent_entry() -> None:
    """The small ready set should remain bounded with deterministic eviction."""
    ctx = Ctx()
    ctx.wnm_ready_capacity_v1 = 2
    maps = [
        _map("overview", "overview"),
        _map("detail", "detail"),
        _map("closeup", "closeup"),
        _map("other", "other"),
    ]
    _commit(ctx, maps[0], WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, maps[1], WNMTransitionTypeV1.ZOOM_IN, observation_no=2)
    _commit(ctx, maps[2], WNMTransitionTypeV1.ZOOM_IN, observation_no=3)
    summary = _commit(ctx, maps[3], WNMTransitionTypeV1.ZOOM_IN, observation_no=4)

    assert wnm_operative_map_v1(ctx) is maps[3]
    assert [item.map_id for item in wnm_ready_maps_v1(ctx)] == ["detail", "closeup"]
    assert summary["ready_count"] == 2
    assert summary["last_transition"]["evicted_ref"] == {"map_id": "overview", "revision": 1}


def test_ambiguous_correspondence_rejects_atomically() -> None:
    """An ambiguous identity/frame handoff must leave both activation tiers unchanged."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    detail = _map("detail", "detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    operative_before = wnm_operative_map_v1(ctx)
    ready_before = wnm_ready_maps_v1(ctx)

    summary = _commit(
        ctx,
        detail,
        WNMTransitionTypeV1.ZOOM_IN,
        observation_no=2,
        ambiguous=True,
        expected_source_ref=NavMapRefV1("overview", 1),
    )

    assert wnm_operative_map_v1(ctx) is operative_before
    assert wnm_ready_maps_v1(ctx) == ready_before
    assert summary["last_transition"]["accepted"] is False
    assert summary["last_transition"]["failure_reason"] == "cross_map_correspondence_ambiguous"
    assert summary["last_transition"]["ready_before"] == summary["last_transition"]["ready_after"]


def test_zero_support_rejects_without_fabricating_authority() -> None:
    """Unsupported correspondence must preserve the source WNM."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    detail = _map("detail", "detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        detail,
        WNMTransitionTypeV1.ZOOM_IN,
        observation_no=2,
        support=0.0,
        expected_source_ref=NavMapRefV1("overview", 1),
    )

    assert wnm_operative_map_v1(ctx) is overview
    assert summary["last_transition"]["failure_reason"] == "cross_map_correspondence_unsupported"
    assert summary["last_transition"]["candidate_or_link_grants_authority"] is False


def test_expected_source_mismatch_is_an_atomic_failure() -> None:
    """A transition built against a stale source reference must not commit."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    detail = _map("detail", "detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        detail,
        WNMTransitionTypeV1.ZOOM_IN,
        observation_no=2,
        expected_source_ref=NavMapRefV1("overview", 99),
    )

    assert wnm_operative_map_v1(ctx) is overview
    assert summary["last_transition"]["failure_reason"] == "operative_source_reference_mismatch"


def test_same_destination_cannot_create_a_fake_zoom_event() -> None:
    """The operative revision cannot be re-promoted as though zoom occurred."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(ctx, overview, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)

    assert wnm_operative_map_v1(ctx) is overview
    assert summary["last_transition"]["failure_reason"] == "destination_already_operative"


def test_refresh_replaces_a_higher_operative_revision_without_transition() -> None:
    """Ordinary material revision refresh should preserve operative role and transition count."""
    ctx = Ctx()
    overview_v1 = _map("overview", "overview", revision=1)
    overview_v2 = _map("overview", "overview", revision=2)
    _commit(ctx, overview_v1, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    transition_count = len(ctx.wnm_transition_history_v1)

    row = wnm_refresh_map_v1(ctx, overview_v2, observation_no=2, reason="material_overview_revision")

    assert row["status"] == "updated"
    assert row["location"] == "operative"
    assert row["operative_role_changed"] is False
    assert row["transition_created"] is False
    assert wnm_operative_map_v1(ctx) is overview_v2
    assert len(ctx.wnm_transition_history_v1) == transition_count


def test_refresh_replaces_a_higher_ready_revision_without_promotion() -> None:
    """A ready map can refresh in place without gaining operative authority."""
    ctx = Ctx()
    overview_v1 = _map("overview", "overview", revision=1)
    overview_v2 = _map("overview", "overview", revision=2)
    detail = _map("detail", "detail")
    _commit(ctx, overview_v1, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, detail, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)

    row = wnm_refresh_map_v1(ctx, overview_v2, observation_no=3, reason="refresh_ready_overview")

    assert row["status"] == "updated"
    assert row["location"] == "ready"
    assert wnm_operative_map_v1(ctx) is detail
    assert wnm_ready_maps_v1(ctx) == (overview_v2,)


def test_return_promotes_the_exact_ready_map_and_keeps_departed_map_ready() -> None:
    """A deterministic return should swap operative and ready roles atomically."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    detail = _map("detail", "detail")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, detail, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)

    summary = wnm_return_to_ref_v1(
        ctx,
        NavMapRefV1("overview", 1),
        observation_no=3,
        reason="return_to_overview",
        identity_handle="entity:shared",
        correspondence_basis="reverse_explicit_correspondence",
        support=1.0,
    )

    assert wnm_operative_map_v1(ctx) is overview
    assert wnm_ready_maps_v1(ctx) == (detail,)
    assert summary["last_transition"]["transition_type"] == "return"
    assert summary["last_transition"]["accepted"] is True


def test_return_to_nonready_ref_preserves_state() -> None:
    """A return request cannot retrieve or fabricate a destination map."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = wnm_return_to_ref_v1(
        ctx,
        NavMapRefV1("missing", 1),
        observation_no=2,
        reason="missing_return_target",
        identity_handle="entity:shared",
        correspondence_basis="unit_test",
        support=1.0,
    )

    assert wnm_operative_map_v1(ctx) is overview
    assert wnm_ready_maps_v1(ctx) == ()
    assert summary["operative_map"]["map_ref"] == {"map_id": "overview", "revision": 1}
    assert ctx.wnm_last_update_v1["failure_reason"] == "destination_not_in_ready_set"


def test_direct_return_cannot_promote_a_map_that_is_not_ready() -> None:
    """RETURN semantics should reject a destination that was not retained in the ready set."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    unrelated = _map("unrelated", "unrelated")
    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        unrelated,
        WNMTransitionTypeV1.RETURN,
        observation_no=2,
        expected_source_ref=NavMapRefV1("overview", 1),
    )

    assert wnm_operative_map_v1(ctx) is overview
    assert wnm_ready_maps_v1(ctx) == ()
    assert summary["last_transition"]["accepted"] is False
    assert summary["last_transition"]["failure_reason"] == "return_destination_not_in_ready_set"


def test_transition_never_mutates_source_or_destination_map_content() -> None:
    """Activation-state changes must leave immutable map bytes untouched."""
    ctx = Ctx()
    overview = _map("overview", "overview")
    detail = _map("detail", "detail")
    overview_bytes = overview.to_bytes()
    detail_bytes = detail.to_bytes()

    _commit(ctx, overview, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, detail, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)

    assert overview.to_bytes() == overview_bytes
    assert detail.to_bytes() == detail_bytes


def test_lateral_shift_is_a_first_class_atomic_operative_transition() -> None:
    """Overlapping route sheets should exchange WNM authority without a focus-only shortcut."""
    ctx = Ctx()
    west = _map("west_route", "terrain_route_west", frame_id="west_route_frame")
    east = _map("east_route", "terrain_route_east", frame_id="east_route_frame")
    _commit(ctx, west, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        east,
        WNMTransitionTypeV1.LATERAL_SHIFT,
        observation_no=2,
        expected_source_ref=NavMapRefV1("west_route", 1),
    )

    assert wnm_operative_map_v1(ctx) is east
    assert wnm_ready_maps_v1(ctx) == (west,)
    assert summary["last_transition"]["transition_type"] == "lateral_shift"
    assert summary["last_transition"]["accepted"] is True
    assert summary["last_transition"]["prior_wnm_disposition"] == "moved_to_ready_set"


def test_summary_renderer_and_histories_are_json_safe_and_bounded() -> None:
    """Transition diagnostics should remain deterministic, JSON-safe, and bounded."""
    ctx = Ctx()
    ctx.wnm_transition_history_limit_v1 = 2
    first = _map("first", "first")
    second = _map("second", "second")
    third = _map("third", "third")
    _commit(ctx, first, WNMTransitionTypeV1.INITIALIZE, observation_no=1)
    _commit(ctx, second, WNMTransitionTypeV1.ZOOM_IN, observation_no=2)
    _commit(ctx, third, WNMTransitionTypeV1.ZOOM_IN, observation_no=3)

    summary = wnm_summary_v1(ctx)
    rendered = render_wnm_lines_v1(ctx)

    json.dumps(summary, sort_keys=True)
    json.dumps(ctx.wnm_transition_history_v1, sort_keys=True)
    assert len(ctx.wnm_transition_history_v1) == 2
    assert rendered[0] == "PHASE 5 OPERATIVE WNM:"
    assert any("operative=third" in line for line in rendered)
    assert all("operative_authority" in item for item in summary["ready_set"])


def test_ready_admission_adds_non_authoritative_map_without_changing_operative() -> None:
    """Phase 8 retrieval may admit a map to ready status without changing current WNM authority."""
    from cca8_wnm_runtime import wnm_admit_ready_map_v1

    ctx = Ctx()
    operative = _map("operative", "operative")
    retrieved = _map("retrieved", "retrieved")
    _commit(ctx, operative, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = wnm_admit_ready_map_v1(
        ctx,
        retrieved,
        observation_no=2,
        reason="phase8_retrieval_ready",
        identity_handle="entity:retrieved",
        correspondence_basis="bounded_reinstatement_and_match",
        support=0.9,
        expected_source_ref=NavMapRefV1("operative", 1),
    )

    assert wnm_operative_map_v1(ctx) is operative
    assert wnm_ready_maps_v1(ctx) == (retrieved,)
    assert summary["last_transition"]["transition_type"] == "ready_admission"
    assert summary["last_transition"]["prior_wnm_disposition"] == "unchanged"
    assert summary["ready_set"][0]["operative_authority"] is False


def test_ready_admission_rejects_ambiguous_candidate_atomically() -> None:
    """Ambiguous reinstatement must not alter either activation tier."""
    from cca8_wnm_runtime import wnm_admit_ready_map_v1

    ctx = Ctx()
    operative = _map("operative", "operative")
    retrieved = _map("retrieved", "retrieved")
    _commit(ctx, operative, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = wnm_admit_ready_map_v1(
        ctx,
        retrieved,
        observation_no=2,
        reason="ambiguous_retrieval",
        identity_handle="entity:retrieved",
        correspondence_basis="ambiguous_test",
        support=0.9,
        correspondence_ambiguous=True,
    )

    assert wnm_operative_map_v1(ctx) is operative
    assert wnm_ready_maps_v1(ctx) == ()
    assert summary["last_transition"]["accepted"] is False
    assert summary["last_transition"]["failure_reason"] == "cross_map_correspondence_ambiguous"


def test_repeated_exact_ready_admission_is_idempotent_and_refreshes_recency() -> None:
    """Repeated retrieval should not duplicate one ready map family."""
    from cca8_wnm_runtime import wnm_admit_ready_map_v1

    ctx = Ctx()
    operative = _map("operative", "operative")
    retrieved = _map("retrieved", "retrieved")
    _commit(ctx, operative, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    for observation_no in (2, 3):
        wnm_admit_ready_map_v1(
            ctx,
            retrieved,
            observation_no=observation_no,
            reason="repeat_retrieval",
            identity_handle="entity:retrieved",
            correspondence_basis="unit_test",
            support=1.0,
        )

    assert wnm_ready_maps_v1(ctx) == (retrieved,)
    assert ctx.wnm_last_transition_v1.acceptance_result == "destination_ready_membership_refreshed"


def test_associative_jump_is_explicit_and_moves_prior_operative_to_ready() -> None:
    """A retrieved map becomes operative only through an explicit associative-jump transaction."""
    ctx = Ctx()
    operative = _map("operative", "operative")
    retrieved = _map("retrieved", "retrieved")
    _commit(ctx, operative, WNMTransitionTypeV1.INITIALIZE, observation_no=1)

    summary = _commit(
        ctx,
        retrieved,
        WNMTransitionTypeV1.ASSOCIATIVE_JUMP,
        observation_no=2,
        expected_source_ref=NavMapRefV1("operative", 1),
    )

    assert wnm_operative_map_v1(ctx) is retrieved
    assert wnm_ready_maps_v1(ctx) == (operative,)
    assert summary["last_transition"]["transition_type"] == "associative_jump"
