# -*- coding: utf-8 -*-
"""Phase 8 tests for Column-backed NavMap memory and sparse retrieval."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cca8_column import ColumnMemory
from cca8_context import Ctx
from cca8_env import EnvObservation
from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapRefV1,
    NavMapV2,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavSourceClassV1,
)
from cca8_navmap_memory import (
    NavMapConsolidationEligibilityV1,
    NavMapMemoryFormV1,
    NavMapMemoryKindV1,
    NavMapRetrievalCommitModeV1,
    NavMapRetrievalModeV1,
    NavMapRetrievalStatusV1,
    navmap_memory_build_before_action_after_map_v1,
    navmap_memory_build_primitive_map_v1,
    navmap_memory_build_trajectory_map_v1,
    navmap_memory_observation_step_v1,
    navmap_memory_replay_eligible_refs_v1,
    navmap_memory_request_strategic_retrieval_v1,
    navmap_memory_reset_episode_v1,
    navmap_memory_retrieve_v1,
    navmap_memory_store_map_v1,
    navmap_memory_summary_v1,
    render_navmap_memory_lines_v1,
)
from cca8_wnm_runtime import (
    WNMTransitionTypeV1,
    wnm_commit_transition_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
)


def _provenance(
    source_ref: str,
    *,
    source_class: NavSourceClassV1 = NavSourceClassV1.OBSERVED,
    quality: float = 0.95,
) -> NavProvenanceV1:
    """Return deterministic provenance for Phase 8 fixtures."""
    return NavProvenanceV1(source_class=source_class, source_ref=source_ref, quality=quality)


def _point(x: float, y: float) -> NavGeometryV1:
    """Return one immutable point geometry."""
    return NavGeometryV1(kind=NavGeometryKindV1.POINT, points=(NavPointV1(x=x, y=y),))


def _map(
    map_id: str,
    *,
    revision: int = 1,
    role: str = "object_scene",
    points: tuple[tuple[str, str, float, float], ...] = (
        ("anchor_a", "landmark", 0.0, 0.0),
        ("anchor_b", "landmark", 1.0, 0.0),
        ("target", "target", 0.5, 1.0),
    ),
    activation: str = "familiar_pattern",
    source_class: NavSourceClassV1 = NavSourceClassV1.OBSERVED,
    quality: float = 0.95,
) -> NavMapV2:
    """Return one alignable immutable map with stable local element ids."""
    provenance = _provenance(
        f"fixture:{map_id}:r{revision}",
        source_class=source_class,
        quality=quality,
    )
    elements = tuple(
        NavElementV1(
            element_id=element_id,
            role=element_role,
            geometry=_point(x, y),
            activations=(NavActivationV1(activation, 0.9, provenance),),
            parent_element_id=None,
            provenance=provenance,
        )
        for element_id, element_role, x, y in points
    )
    relations = ()
    if {item[0] for item in points}.issuperset({"anchor_a", "target"}):
        relations = (NavRelationV1("orients_to", "anchor_a", "target", provenance),)
    return NavMapV2(
        map_id=map_id,
        revision=revision,
        role=role,
        frame=NavFrameV1(
            frame_id=f"{map_id}_frame",
            x_axis="right",
            y_axis="forward",
            units="m",
            min_x=-10.0,
            max_x=10.0,
            min_y=-10.0,
            max_y=10.0,
        ),
        provenance=provenance,
        parent_ref=(NavMapRefV1(map_id, revision - 1) if revision > 1 else None),
        elements=elements,
        relations=relations,
    )


def _store(
    ctx: Ctx,
    column: ColumnMemory,
    navmap: NavMapV2,
    *,
    observation_no: int = 1,
    cue_tokens: tuple[str, ...] = ("cue:familiar",),
    context_tokens: tuple[str, ...] = (),
    task_tokens: tuple[str, ...] = (),
    kinds: tuple[NavMapMemoryKindV1, ...] = (NavMapMemoryKindV1.OBJECT,),
    forms: tuple[NavMapMemoryFormV1, ...] = (NavMapMemoryFormV1.EPISODIC,),
    support: bool = True,
    exception: bool = False,
):
    """Store one map through the public Phase 8 contract."""
    return navmap_memory_store_map_v1(
        ctx,
        navmap,
        memory_kinds=kinds,
        memory_forms=forms,
        observation_no=observation_no,
        reason="unit_test_storage",
        column_memory=column,
        cue_tokens=cue_tokens,
        context_tokens=context_tokens,
        task_tokens=task_tokens,
        identity_handles=("identity:fixture",),
        support=support,
        exception=exception,
    )


def _retrieve(
    ctx: Ctx,
    column: ColumnMemory,
    query_map: NavMapV2 | None,
    *,
    cue_tokens: tuple[str, ...] = ("cue:familiar",),
    task_tokens: tuple[str, ...] = (),
    mode: NavMapRetrievalModeV1 = NavMapRetrievalModeV1.SPONTANEOUS,
    commit_mode: NavMapRetrievalCommitModeV1 = NavMapRetrievalCommitModeV1.NONE,
    candidate_limit: int = 8,
    reinstatement_limit: int = 3,
) -> dict[str, object]:
    """Run one concise public retrieval transaction."""
    return navmap_memory_retrieve_v1(
        ctx,
        query_map=query_map,
        mode=mode,
        cue_tokens=cue_tokens,
        task_bias_tokens=task_tokens,
        commit_mode=commit_mode,
        reason="unit_test_retrieval",
        observation_no=max(1, int(getattr(ctx, "navmap_memory_observation_no_v1", 0) or 0) + 1),
        candidate_ref_limit=candidate_limit,
        reinstatement_limit=reinstatement_limit,
        column_memory=column,
    )


def _last_retrieval(ctx: Ctx) -> dict[str, object]:
    """Return the latest JSON-safe retrieval transaction."""
    row = navmap_memory_summary_v1(ctx).get("last_retrieval")
    assert isinstance(row, dict)
    return row


def _initialize_wnm(ctx: Ctx, navmap: NavMapV2, *, observation_no: int = 1) -> None:
    """Initialize one operative WNM for authority tests."""
    wnm_commit_transition_v1(
        ctx,
        navmap,
        transition_type=WNMTransitionTypeV1.INITIALIZE,
        observation_no=observation_no,
        reason="phase8_test_initialize",
        identity_handle="identity:self",
        correspondence_basis="unit_test",
        support=1.0,
    )


def test_context_defaults_enable_bounded_phase8_memory_without_authority() -> None:
    """New contexts should expose bounded memory settings and no implicit retrieval truth."""
    ctx = Ctx()

    assert ctx.navmap_memory_enabled_v1 is True
    assert ctx.navmap_memory_candidate_ref_limit_v1 == 8
    assert ctx.navmap_memory_reinstatement_limit_v1 == 3
    assert ctx.navmap_memory_index_v1 == {}
    assert ctx.navmap_memory_last_retrieval_v1 is None


def test_column_stores_exact_navmap_payload_and_lightweight_index_only() -> None:
    """Rich content should live in Column while the sparse index contains no payload."""
    ctx = Ctx()
    column = ColumnMemory(name="phase8_test_column")
    navmap = _map("stored_map")

    record = _store(ctx, column, navmap)
    entry = next(iter(ctx.navmap_memory_index_v1.values()))

    assert record.payload_stored is True
    assert column.get(record.engram_id)["payload"] is navmap
    assert entry.map_ref == NavMapRefV1("stored_map", 1)
    assert "payload" not in entry.as_dict()
    assert entry.as_dict()["contains_payload"] is False


@pytest.mark.parametrize("kind", list(NavMapMemoryKindV1))
def test_all_planned_memory_kinds_are_indexable(kind: NavMapMemoryKindV1) -> None:
    """The first storage fabric should represent every Phase 8 map kind."""
    ctx = Ctx()
    column = ColumnMemory(name=f"kind_{kind.value}")

    _store(ctx, column, _map(f"map_{kind.value}"), kinds=(kind,))

    entry = next(iter(ctx.navmap_memory_index_v1.values()))
    assert entry.memory_kinds == (kind,)


@pytest.mark.parametrize("form", list(NavMapMemoryFormV1))
def test_all_planned_memory_forms_are_indexable(form: NavMapMemoryFormV1) -> None:
    """Episodic, prototype, identity, and transition memory remain distinct."""
    ctx = Ctx()
    column = ColumnMemory(name=f"form_{form.value}")

    _store(ctx, column, _map(f"map_{form.value}"), forms=(form,))

    entry = next(iter(ctx.navmap_memory_index_v1.values()))
    assert entry.memory_forms == (form,)


def test_repeated_exact_revision_avoids_duplicate_payload_and_strengthens_support() -> None:
    """Equivalent support should update the index rather than duplicate Column content."""
    ctx = Ctx()
    column = ColumnMemory(name="dedup")
    navmap = _map("same_revision")

    first = _store(ctx, column, navmap, observation_no=1)
    second = _store(ctx, column, navmap, observation_no=2)
    entry = next(iter(ctx.navmap_memory_index_v1.values()))

    assert first.engram_id == second.engram_id
    assert column.count() == 1
    assert second.duplicate_payload_avoided is True
    assert entry.support_count == 2


def test_new_revision_is_a_distinct_versioned_long_term_record() -> None:
    """Material immutable revisions should remain individually addressable."""
    ctx = Ctx()
    column = ColumnMemory(name="revisioned")

    _store(ctx, column, _map("route", revision=1), observation_no=1)
    _store(ctx, column, _map("route", revision=2), observation_no=2)

    assert column.count() == 2
    assert set(ctx.navmap_memory_ref_index_v1) == {"route@r1", "route@r2"}


def test_support_and_exception_counts_remain_separate() -> None:
    """Failures should not masquerade as additional supporting examples."""
    ctx = Ctx()
    column = ColumnMemory(name="examples_exceptions")
    navmap = _map("transition_case")

    _store(ctx, column, navmap, support=True, exception=False, observation_no=1)
    _store(ctx, column, navmap, support=False, exception=True, observation_no=2)
    entry = next(iter(ctx.navmap_memory_index_v1.values()))

    assert entry.support_count == 1
    assert entry.exception_count == 1


def test_candidate_reference_generation_does_not_scan_column_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sparse activation should use ctx indexes and exact-id payload access only."""
    ctx = Ctx()
    column = ColumnMemory(name="no_scan")
    stored = _map("stored_no_scan")
    query = _map("query_no_scan")
    _store(ctx, column, stored, cue_tokens=("cue:unique",))

    monkeypatch.setattr(column, "list_ids", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scan")))
    monkeypatch.setattr(column, "find", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scan")))

    _retrieve(ctx, column, query, cue_tokens=("cue:unique",))

    row = _last_retrieval(ctx)
    assert row["status"] == NavMapRetrievalStatusV1.CLEAR_WINNER.value
    assert row["candidate_refs_generated_without_payload_scan"] is True


def test_candidate_and_reinstatement_bounds_are_enforced() -> None:
    """Broad activation may address many maps but only bounded subsets are returned and loaded."""
    ctx = Ctx()
    column = ColumnMemory(name="bounded")
    for index in range(10):
        _store(ctx, column, _map(f"candidate_{index:02d}"), cue_tokens=("cue:shared",))

    _retrieve(
        ctx,
        column,
        _map("bounded_query"),
        cue_tokens=("cue:shared",),
        candidate_limit=4,
        reinstatement_limit=2,
    )
    row = _last_retrieval(ctx)

    assert len(row["candidate_refs"]) == 4
    assert len(row["reinstatements"]) == 2


def test_partial_cue_map_can_reinstate_a_more_complete_memory() -> None:
    """A two-landmark partial map should enter and match a three-element stored map."""
    ctx = Ctx()
    column = ColumnMemory(name="partial")
    stored = _map("complete_memory")
    partial = _map(
        "partial_current",
        points=(
            ("anchor_a", "landmark", 0.0, 0.0),
            ("anchor_b", "landmark", 1.0, 0.0),
        ),
    )
    _store(ctx, column, stored, cue_tokens=("cue:partial",))

    _retrieve(ctx, column, partial, cue_tokens=("cue:partial",))
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.CLEAR_WINNER.value
    assert row["winner_ref"] == {"map_id": "complete_memory", "revision": 1}
    assert row["reinstatements"][0]["current_truth"] is False


def test_empty_library_preserves_explicit_no_candidates() -> None:
    """Best-of-empty must remain an explicit open-world result."""
    ctx = Ctx()
    column = ColumnMemory(name="empty")

    _retrieve(ctx, column, None, cue_tokens=("cue:absent",))

    assert _last_retrieval(ctx)["status"] == NavMapRetrievalStatusV1.NO_CANDIDATES.value


def test_queryless_retrieval_returns_references_and_reinstatement_without_winner() -> None:
    """Cue activation alone may load candidates but cannot perform detailed comparison."""
    ctx = Ctx()
    column = ColumnMemory(name="queryless")
    _store(ctx, column, _map("queryless_memory"), cue_tokens=("cue:entry",))

    _retrieve(ctx, column, None, cue_tokens=("cue:entry",))
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.CANDIDATE_REFS_ONLY.value
    assert row["winner_ref"] is None
    assert len(row["reinstatements"]) == 1


def test_two_equivalent_reinstatements_preserve_ambiguity() -> None:
    """The memory system must not accept a winner when detailed matches tie."""
    ctx = Ctx()
    column = ColumnMemory(name="ambiguous")
    _store(ctx, column, _map("memory_a"), cue_tokens=("cue:ambiguous",))
    _store(ctx, column, _map("memory_b"), cue_tokens=("cue:ambiguous",))

    _retrieve(ctx, column, _map("ambiguous_query"), cue_tokens=("cue:ambiguous",), reinstatement_limit=2)
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.AMBIGUOUS.value
    assert row["winner_ref"] is None


def test_strategic_task_bias_controls_the_bounded_reinstatement_entry() -> None:
    """PFC-like task bias should change which candidate is decoded when only one may be loaded."""
    ctx = Ctx()
    column = ColumnMemory(name="strategic")
    _store(ctx, column, _map("feeding_memory"), cue_tokens=("cue:shared",), task_tokens=("task:feeding",))
    _store(ctx, column, _map("shelter_memory"), cue_tokens=("cue:shared",), task_tokens=("task:shelter",))

    _retrieve(
        ctx,
        column,
        _map("strategic_query"),
        cue_tokens=("cue:shared",),
        task_tokens=("task:feeding",),
        mode=NavMapRetrievalModeV1.STRATEGIC,
        reinstatement_limit=1,
    )
    row = _last_retrieval(ctx)

    assert row["winner_ref"] == {"map_id": "feeding_memory", "revision": 1}
    assert row["request"]["mode"] == "strategic"


def test_missing_or_invalid_payload_reports_reinstatement_failure() -> None:
    """A stale sparse pointer should not fabricate a decoded map."""
    ctx = Ctx()
    column = ColumnMemory(name="broken_payload")
    record = _store(ctx, column, _map("broken_memory"), cue_tokens=("cue:broken",))
    column._store[record.engram_id]["payload"] = "not-a-navmap"  # pylint: disable=protected-access

    _retrieve(ctx, column, _map("broken_query"), cue_tokens=("cue:broken",))

    assert _last_retrieval(ctx)["status"] == NavMapRetrievalStatusV1.REINSTATEMENT_FAILED.value


def test_reliable_current_evidence_defeats_conflicting_memory() -> None:
    """A clear but locally conflicting memory must not displace reliable observation."""
    ctx = Ctx()
    column = ColumnMemory(name="evidence_wins")
    stored = _map("stored_prior")
    conflicting_points = (
        ("anchor_a", "landmark", 0.0, 0.0),
        ("anchor_b", "landmark", 1.0, 0.0),
        ("target", "hazard", 0.5, 1.0),
    )
    current = _map("current_evidence", points=conflicting_points, quality=0.99)
    _store(ctx, column, stored, cue_tokens=("cue:conflict",))

    _retrieve(ctx, column, current, cue_tokens=("cue:conflict",), commit_mode=NavMapRetrievalCommitModeV1.READY)
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.EVIDENCE_DEFEATS_MEMORY.value
    assert row["evidence_defeats_memory"] is True
    assert wnm_ready_maps_v1(ctx) == ()


def test_low_quality_current_map_does_not_claim_protected_evidence_defeat() -> None:
    """An uncertain current candidate may compare poorly without posing as protected observation."""
    ctx = Ctx()
    column = ColumnMemory(name="uncertain_query")
    stored = _map("uncertain_prior")
    current = _map(
        "uncertain_current",
        points=(
            ("anchor_a", "landmark", 0.0, 0.0),
            ("anchor_b", "landmark", 1.0, 0.0),
            ("target", "hazard", 0.5, 1.0),
        ),
        quality=0.30,
    )
    _store(ctx, column, stored, cue_tokens=("cue:uncertain",))

    _retrieve(ctx, column, current, cue_tokens=("cue:uncertain",))
    row = _last_retrieval(ctx)

    assert row["evidence_defeats_memory"] is False


def test_clear_winner_can_enter_ready_set_without_changing_operative_map() -> None:
    """Ready admission should make retrieval rapidly available but non-operative."""
    ctx = Ctx()
    column = ColumnMemory(name="ready")
    operative = _map("current_operating_map", role="current_scene")
    stored = _map("retrieved_ready_map")
    query = _map("query_for_ready")
    _initialize_wnm(ctx, operative)
    _store(ctx, column, stored, cue_tokens=("cue:ready",))

    _retrieve(ctx, column, query, cue_tokens=("cue:ready",), commit_mode=NavMapRetrievalCommitModeV1.READY)
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.READY_ADMITTED.value
    assert wnm_operative_map_v1(ctx) is operative
    assert wnm_ready_maps_v1(ctx) == (stored,)


def test_explicit_strategic_associative_jump_changes_operative_wnm() -> None:
    """Only an explicit strategic jump should promote the retrieved map to operative authority."""
    ctx = Ctx()
    column = ColumnMemory(name="jump")
    operative = _map("jump_source", role="current_scene")
    stored = _map("jump_destination")
    query = _map("jump_query")
    _initialize_wnm(ctx, operative)
    _store(ctx, column, stored, cue_tokens=("cue:jump",))

    _retrieve(
        ctx,
        column,
        query,
        cue_tokens=("cue:jump",),
        mode=NavMapRetrievalModeV1.STRATEGIC,
        commit_mode=NavMapRetrievalCommitModeV1.ASSOCIATIVE_JUMP,
    )
    row = _last_retrieval(ctx)

    assert row["status"] == NavMapRetrievalStatusV1.ASSOCIATIVE_JUMP_COMMITTED.value
    assert wnm_operative_map_v1(ctx) is stored
    assert operative in wnm_ready_maps_v1(ctx)


def test_primitive_map_is_task_level_and_contains_no_motor_trajectory() -> None:
    """Stored primitive structure should stop at precondition/intent/expectation."""
    navmap = navmap_memory_build_primitive_map_v1("policy:follow_mom")

    assert navmap.role == "behavioral_primitive_map"
    assert {element.role for element in navmap.elements} == {
        "primitive_precondition",
        "primitive_action_intent",
        "primitive_expected_outcome",
    }
    assert "trajectory" not in navmap.to_bytes().decode("utf-8").lower()


def test_before_action_after_map_preserves_explicit_map_links_and_transition_form() -> None:
    """A compact transition memory should link its exact before/after revisions."""
    navmap = navmap_memory_build_before_action_after_map_v1(
        action="policy:follow_mom",
        observation_no=4,
        before_ref=NavMapRefV1("before", 2),
        after_ref=NavMapRefV1("after", 3),
        outcome="success",
        support=True,
        exception=False,
    )

    assert navmap.role == "before_action_after_episode"
    assert {link.target_ref for link in navmap.links} == {NavMapRefV1("before", 2), NavMapRefV1("after", 3)}


def test_trajectory_builder_requires_sparse_phase7_event_boundary() -> None:
    """Ordinary continuous dynamics should not generate a long-term trajectory map."""
    ctx = Ctx()
    ctx.live_dynamics_state_v1 = SimpleNamespace(
        materiality=SimpleNamespace(event_boundary=False),
        overlays=(),
    )

    assert navmap_memory_build_trajectory_map_v1(ctx, observation_no=1) is None


def test_trajectory_builder_compresses_one_event_without_full_navmap_movie() -> None:
    """An event boundary may produce one start/end trajectory record only."""
    ctx = Ctx()
    overlay = SimpleNamespace(
        relation=SimpleNamespace(value="self_route"),
        velocity_x=0.5,
        velocity_y=0.0,
        scalar_rate=None,
        lower_motor_progress=None,
        event_labels=("slip",),
        material_event=True,
        phase=SimpleNamespace(value="interrupted"),
        source_map_ref=NavMapRefV1("route", 1),
    )
    ctx.live_dynamics_state_v1 = SimpleNamespace(
        materiality=SimpleNamespace(event_boundary=True),
        overlays=(overlay,),
    )

    navmap = navmap_memory_build_trajectory_map_v1(ctx, observation_no=2)

    assert navmap is not None
    assert navmap.role == "temporal_trajectory_episode"
    assert len(navmap.elements) == 2
    assert len(navmap.links) == 1


def test_eligibility_separates_content_change_pending_and_consolidated_states() -> None:
    """The four planned consolidation states should remain explicit and independently inspectable."""
    ctx = Ctx()
    column = ColumnMemory(name="eligibility")
    ctx.navmap_memory_auto_consolidate_v1 = False
    operative = _map("eligible_operative")
    _initialize_wnm(ctx, operative)

    navmap_memory_observation_step_v1(
        ctx,
        EnvObservation(cues=["cue:eligible"], env_meta={"scenario_stage": "test"}),
        column_memory=column,
    )
    row = next(iter(ctx.navmap_memory_eligibility_v1.values()))

    assert row.content_changed is True
    assert row.plasticity_eligible is True
    assert row.consolidation_pending is True
    assert row.consolidated is False
    assert column.count() == 0


def test_repeated_equivalent_observation_strengthens_one_eligibility_row_without_duplicates() -> None:
    """Equivalent activations should not create a permanent eligibility history."""
    ctx = Ctx()
    column = ColumnMemory(name="eligibility_dedup")
    ctx.navmap_memory_auto_consolidate_v1 = False
    operative = _map("eligibility_same")
    _initialize_wnm(ctx, operative)
    obs = EnvObservation(cues=["cue:same"], env_meta={})

    navmap_memory_observation_step_v1(ctx, obs, column_memory=column)
    navmap_memory_observation_step_v1(ctx, obs, column_memory=column)

    assert len(ctx.navmap_memory_eligibility_v1) == 1
    assert len(ctx.navmap_memory_pending_maps_v1) == 1


def test_transient_eligibility_decays_and_expires_when_source_is_no_longer_active() -> None:
    """Eligibility should remain a bounded local signal rather than a permanent activation log."""
    ctx = Ctx()
    column = ColumnMemory(name="eligibility_expiry")
    ctx.navmap_memory_auto_consolidate_v1 = False
    ctx.navmap_memory_eligibility_ttl_v1 = 1
    ctx.navmap_memory_eligibility_decay_v1 = 0.60
    _initialize_wnm(ctx, _map("short_lived"))

    navmap_memory_observation_step_v1(ctx, EnvObservation(cues=["cue:first"]), column_memory=column)
    ctx.wnm_operative_map_v1 = None
    navmap_memory_observation_step_v1(ctx, EnvObservation(), column_memory=column)
    navmap_memory_observation_step_v1(ctx, EnvObservation(), column_memory=column)

    assert ctx.navmap_memory_eligibility_v1 == {}
    assert ctx.navmap_memory_pending_maps_v1 == {}


def test_auto_consolidation_respects_per_observation_budget() -> None:
    """Even many eligible maps should not cause unbounded Column writes in one cycle."""
    ctx = Ctx()
    column = ColumnMemory(name="budget")
    ctx.navmap_memory_consolidation_budget_v1 = 1
    _initialize_wnm(ctx, _map("budget_operative"))
    ctx.navmap_v2_shadow_body_ground = _map("budget_body", role="body_ground")
    ctx.navmap_maternal_map = _map("budget_maternal", role="maternal_scene")

    summary = navmap_memory_observation_step_v1(
        ctx,
        EnvObservation(cues=["cue:budget"], env_meta={"milestone": "important"}),
        column_memory=column,
    )

    assert len(summary["consolidated_this_observation"]) == 1
    assert column.count() == 1
    assert len(ctx.navmap_memory_eligibility_v1) >= 2


def test_replay_eligible_refs_returns_only_bounded_unconsolidated_maps() -> None:
    """Offline replay should receive sparse references rather than the complete library."""
    ctx = Ctx()
    column = ColumnMemory(name="replay")
    ctx.navmap_memory_auto_consolidate_v1 = False
    _initialize_wnm(ctx, _map("replay_oper"))
    ctx.navmap_v2_shadow_body_ground = _map("replay_body", role="body_ground")

    navmap_memory_observation_step_v1(
        ctx,
        EnvObservation(cues=["cue:replay"], env_meta={"milestone": "event"}),
        column_memory=column,
    )

    refs = navmap_memory_replay_eligible_refs_v1(ctx, limit=1)
    assert len(refs) == 1
    assert isinstance(refs[0], NavMapRefV1)


def test_strategic_request_is_one_shot_and_does_not_grant_authority_by_itself() -> None:
    """A PFC-like request should remain pending metadata until the observation transaction consumes it."""
    ctx = Ctx()
    row = navmap_memory_request_strategic_retrieval_v1(
        ctx,
        task_bias_tokens=("task:feeding",),
        commit_mode=NavMapRetrievalCommitModeV1.ASSOCIATIVE_JUMP,
    )

    assert row["status"] == "pending"
    assert row["grants_authority"] is False
    assert ctx.navmap_memory_strategic_request_v1 is not None


def test_spontaneous_recognition_signature_suppresses_identical_requery() -> None:
    """Familiar settling should stop repeated retrieval for unchanged cues and current map."""
    ctx = Ctx()
    column = ColumnMemory(name="settling")
    ctx.navmap_memory_auto_consolidate_v1 = False
    ctx.navmap_memory_spontaneous_ready_admission_v1 = False
    operative = _map("settling_oper")
    _initialize_wnm(ctx, operative)
    _store(ctx, column, _map("settling_memory"), cue_tokens=("cue:settle",))
    obs = EnvObservation(cues=["cue:settle"])

    first = navmap_memory_observation_step_v1(ctx, obs, column_memory=column)
    second = navmap_memory_observation_step_v1(ctx, obs, column_memory=column)

    assert first["retrieval_ran"] is True
    assert second["retrieval_ran"] is False
    assert second["recognition_settled_without_requery"] is True


def test_episode_reset_preserves_long_term_index_but_clears_transient_state() -> None:
    """Episode reset should not erase Column memory or its sparse addresses."""
    ctx = Ctx()
    column = ColumnMemory(name="reset")
    _store(ctx, column, _map("persistent_memory"))
    ctx.navmap_memory_eligibility_v1 = {
        "x": NavMapConsolidationEligibilityV1(
            eligibility_key="x",
            map_ref=NavMapRefV1("persistent_memory", 1),
            source_role="object_scene",
            memory_kinds=(NavMapMemoryKindV1.OBJECT,),
            memory_forms=(NavMapMemoryFormV1.EPISODIC,),
            created_observation_no=1,
            last_signal_observation_no=1,
            expires_after_observation_no=2,
            strength=0.5,
            reasons=("test",),
            content_changed=True,
            plasticity_eligible=True,
            consolidation_pending=True,
            consolidated=False,
            unresolved_mismatch=False,
        )
    }

    navmap_memory_reset_episode_v1(ctx)

    assert len(ctx.navmap_memory_index_v1) == 1
    assert column.count() == 1
    assert ctx.navmap_memory_eligibility_v1 == {}
    assert ctx.navmap_memory_last_retrieval_v1 is None


def test_summary_renderer_and_histories_are_json_safe_and_bounded() -> None:
    """Phase 8 reporting should stay deterministic, bounded, and payload-free."""
    ctx = Ctx()
    column = ColumnMemory(name="reporting")
    ctx.navmap_memory_retrieval_history_limit_v1 = 2
    stored = _map("report_memory")
    _store(ctx, column, stored, cue_tokens=("cue:report",))
    for index in range(3):
        _retrieve(ctx, column, _map(f"report_query_{index}"), cue_tokens=("cue:report",))

    summary = navmap_memory_summary_v1(ctx)
    lines = render_navmap_memory_lines_v1(ctx)

    json.dumps(summary, sort_keys=True)
    json.dumps(ctx.navmap_memory_retrieval_history_v1, sort_keys=True)
    assert len(ctx.navmap_memory_retrieval_history_v1) == 2
    assert lines[0] == "PHASE 8 LONG-TERM NAVMAP MEMORY / SPARSE RETRIEVAL:"
    assert summary["candidate_generation_uses_full_payload_scan"] is False
    assert summary["retrieval_grants_truth"] is False
