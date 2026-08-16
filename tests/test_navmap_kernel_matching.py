# -*- coding: utf-8 -*-
"""Phase 1C tests for immutable transforms, alignment, matching, residuals, and revision."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from cca8_navmap_kernel import (
    NavActivationV1,
    NavAlignmentStatusV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapLinkV1,
    NavMapRefV1,
    NavMapV2,
    NavMatchRankStatusV1,
    NavMatchStatusV1,
    NavMatchThresholdsV1,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavRevisionDecisionV1,
    NavRevisionThresholdsV1,
    NavRigidTransformV1,
    NavSourceClassV1,
    align_navmaps,
    apply_revision,
    geometry_orientation_degrees,
    match_navmaps,
    match_rank,
    propose_revision,
    reframe_navmap,
    rotate_navmap,
    structured_residual,
    transform_navmap,
    translate_navmap,
)


def _provenance(
    source_class: NavSourceClassV1 = NavSourceClassV1.OBSERVED,
    source_ref: str = "fixture:phase1c",
) -> NavProvenanceV1:
    """Return deterministic provenance for Phase 1C fixtures."""
    return NavProvenanceV1(source_class=source_class, source_ref=source_ref, quality=0.95)


def _frame(
    *,
    frame_id: str = "self_sagittal_v1",
    units: str = "normalized",
    x_axis: str = "forward",
    y_axis: str = "up",
) -> NavFrameV1:
    """Return a roomy frame for rigid-transform tests."""
    return NavFrameV1(
        frame_id=frame_id,
        x_axis=x_axis,
        y_axis=y_axis,
        units=units,
        min_x=-5.0,
        max_x=5.0,
        min_y=-5.0,
        max_y=5.0,
    )


def _geometry(kind: NavGeometryKindV1, *points: tuple[float, float]) -> NavGeometryV1:
    """Build compact test geometry."""
    return NavGeometryV1(kind=kind, points=tuple(NavPointV1(x, y) for x, y in points))


def _scene_map(
    *,
    map_id: str,
    revision: int = 1,
    horizontal: bool = False,
    provenance: NavProvenanceV1 | None = None,
    frame: NavFrameV1 | None = None,
) -> NavMapV2:
    """Return a compact SELF-ground map with one landmark and one detail link."""
    provenance = provenance or _provenance()
    if horizontal:
        body_geometry = _geometry(NavGeometryKindV1.SEGMENT, (-1.0, 0.2), (1.0, 0.2))
        head_geometry = _geometry(NavGeometryKindV1.POINT, (-1.2, 0.2))
        foot_geometry = _geometry(NavGeometryKindV1.POINT, (1.2, 0.0))
    else:
        body_geometry = _geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.2), (0.0, 2.0))
        head_geometry = _geometry(NavGeometryKindV1.POINT, (0.0, 2.2))
        foot_geometry = _geometry(NavGeometryKindV1.POINT, (0.0, 0.0))
    body_activations = (
        NavActivationV1("body_axis", 0.95, provenance),
        NavActivationV1("self_related", 1.0, provenance),
    )
    part_activations = (NavActivationV1("body_part", 0.9, provenance),)
    elements = (
        NavElementV1(
            "ground_surface",
            "ground_surface",
            _geometry(NavGeometryKindV1.SEGMENT, (-2.0, 0.0), (2.0, 0.0)),
            (NavActivationV1("surface", 1.0, provenance),),
            None,
            provenance,
        ),
        NavElementV1("self_body", "self_body", body_geometry, body_activations, None, provenance),
        NavElementV1("self_head", "self_head", head_geometry, part_activations, "self_body", provenance),
        NavElementV1("self_foot", "self_foot", foot_geometry, part_activations, "self_body", provenance),
        NavElementV1(
            "landmark",
            "landmark",
            _geometry(NavGeometryKindV1.POINT, (2.0, 1.0)),
            (NavActivationV1("salient", 0.8, provenance),),
            None,
            provenance,
        ),
    )
    relations = (
        NavRelationV1("part_of", "self_head", "self_body", provenance),
        NavRelationV1("part_of", "self_foot", "self_body", provenance),
    )
    links = (NavMapLinkV1("detail", NavMapRefV1("self_body_detail", 2), "self_body", provenance),)
    return NavMapV2(
        map_id=map_id,
        revision=revision,
        role="self_ground_scene",
        frame=frame or _frame(),
        provenance=provenance,
        elements=elements,
        relations=relations,
        links=links,
    )


def _independent_map(
    navmap: NavMapV2,
    *,
    map_id: str,
    provenance: NavProvenanceV1 | None = None,
) -> NavMapV2:
    """Copy map content into an independent revision-1 family."""
    return NavMapV2(
        map_id=map_id,
        revision=1,
        role=navmap.role,
        frame=navmap.frame,
        provenance=provenance or navmap.provenance,
        elements=navmap.elements,
        relations=navmap.relations,
        links=navmap.links,
    )


def _rename_elements(navmap: NavMapV2, mapping: dict[str, str], *, map_id: str) -> NavMapV2:
    """Return an independent map whose local element ids are renamed consistently."""
    elements = tuple(
        replace(
            element,
            element_id=mapping.get(element.element_id, element.element_id),
            parent_element_id=(
                mapping.get(element.parent_element_id, element.parent_element_id)
                if element.parent_element_id is not None
                else None
            ),
        )
        for element in navmap.elements
    )
    relations = tuple(
        replace(
            relation,
            source_element_id=mapping.get(relation.source_element_id, relation.source_element_id),
            target_element_id=mapping.get(relation.target_element_id, relation.target_element_id),
        )
        for relation in navmap.relations
    )
    links = tuple(
        replace(
            link,
            source_element_id=(
                mapping.get(link.source_element_id, link.source_element_id)
                if link.source_element_id is not None
                else None
            ),
        )
        for link in navmap.links
    )
    return NavMapV2(
        map_id=map_id,
        revision=1,
        role=navmap.role,
        frame=navmap.frame,
        provenance=navmap.provenance,
        elements=elements,
        relations=relations,
        links=links,
    )


def _match_thresholds(
    *,
    maximum_alignment_rms_error: float = 2.0,
    minimum_rank_score: float = 0.20,
    ambiguity_margin: float = 0.05,
) -> NavMatchThresholdsV1:
    """Return explicit permissive thresholds for the small Phase 1C maps."""
    return NavMatchThresholdsV1(
        maximum_alignment_rms_error=maximum_alignment_rms_error,
        maximum_geometry_rms_error=0.05,
        maximum_geometry_point_error=0.08,
        maximum_activation_strength_delta=0.05,
        minimum_correspondence_coverage=0.25,
        minimum_rank_score=minimum_rank_score,
        ambiguity_margin=ambiguity_margin,
        maximum_candidate_count=8,
    )


def _revision_thresholds(
    *,
    minimum_revise_score: float = 0.30,
    maximum_reject_all_score: float = 0.10,
) -> NavRevisionThresholdsV1:
    """Return explicit revision-decision thresholds."""
    return NavRevisionThresholdsV1(
        minimum_keep_score=0.99,
        minimum_revise_score=minimum_revise_score,
        minimum_revise_coverage=0.50,
        maximum_reject_all_score=maximum_reject_all_score,
    )


def _rigid_candidate(source: NavMapV2, *, map_id: str, rename: bool = False) -> NavMapV2:
    """Return the same map content expressed in a different compatible frame."""
    target_frame = replace(source.frame, frame_id=f"{map_id}_frame")
    transform = NavRigidTransformV1(
        source_frame_id=source.frame.frame_id,
        target_frame_id=target_frame.frame_id,
        rotation_degrees=20.0,
        translation_x=0.4,
        translation_y=-0.2,
        pivot=NavPointV1(0.0, 0.0),
        method="fixture_rigid_reframe",
    )
    transformed = transform_navmap(
        source,
        transform,
        new_revision=2,
        target_frame=target_frame,
    ).result_map
    candidate = _independent_map(transformed, map_id=map_id)
    if not rename:
        return candidate
    return _rename_elements(
        candidate,
        {
            "ground_surface": "surface_a",
            "self_body": "entity_a",
            "self_head": "part_a",
            "self_foot": "part_b",
            "landmark": "landmark_a",
        },
        map_id=map_id,
    )


def _element(navmap: NavMapV2, element_id: str) -> NavElementV1:
    """Return a fixture element without coupling tests to tuple order."""
    return next(element for element in navmap.elements if element.element_id == element_id)


def test_translate_named_elements_creates_child_and_preserves_unrelated_content() -> None:
    """A local transform preserves unrelated elements and the source map exactly."""
    source = _scene_map(map_id="translate_source")
    before_bytes = source.to_bytes()
    result = translate_navmap(
        source,
        delta_x=0.5,
        delta_y=-0.1,
        new_revision=2,
        element_ids=("self_body", "self_head", "self_foot"),
    )

    assert result.source_map_ref == NavMapRefV1("translate_source", 1)
    assert result.result_map.parent_ref == result.source_map_ref
    assert result.result_map.revision == 2
    assert result.element_ids == ("self_body", "self_foot", "self_head")
    assert _element(result.result_map, "ground_surface") == _element(source, "ground_surface")
    assert _element(result.result_map, "landmark") == _element(source, "landmark")
    assert source.to_bytes() == before_bytes


def test_transform_builds_offline_standup_expected_successor() -> None:
    """A rigid transform creates upright expected geometry without invoking a controller."""
    fallen = _scene_map(map_id="standup_expected", horizontal=True)
    expected_provenance = _provenance(NavSourceClassV1.EXPECTED, "primitive:stand_up")
    transform = NavRigidTransformV1(
        source_frame_id=fallen.frame.frame_id,
        target_frame_id=fallen.frame.frame_id,
        rotation_degrees=-90.0,
        translation_x=-1.0,
        translation_y=0.0,
        pivot=NavPointV1(1.0, 0.2),
        method="standup_expected_successor",
    )
    result = transform_navmap(
        fallen,
        transform,
        new_revision=2,
        element_ids=("self_body", "self_head", "self_foot"),
        result_provenance=expected_provenance,
    )

    assert geometry_orientation_degrees(fallen, "self_body").value == pytest.approx(0.0)
    assert geometry_orientation_degrees(result.result_map, "self_body").value == pytest.approx(90.0)
    assert result.result_map.provenance.source_class is NavSourceClassV1.EXPECTED
    assert _element(result.result_map, "self_body").provenance.source_class is NavSourceClassV1.EXPECTED
    assert _element(result.result_map, "ground_surface") == _element(fallen, "ground_surface")
    assert _element(result.result_map, "ground_surface").provenance.source_class is NavSourceClassV1.OBSERVED

    rotated_landmark = rotate_navmap(
        fallen,
        angle_degrees=90.0,
        pivot=NavPointV1(0.0, 0.0),
        new_revision=3,
        element_ids=("landmark",),
    )
    assert rotated_landmark.result_map.revision == 3


def test_transform_rejects_out_of_bounds_geometry_and_partial_reframing() -> None:
    """Destination-frame violations and partial reframing fail explicitly."""
    source = _scene_map(map_id="transform_validation")
    with pytest.raises(ValueError, match="outside the declared frame"):
        translate_navmap(source, delta_x=20.0, delta_y=0.0, new_revision=2)

    target_frame = _frame(frame_id="allocentric_v1")
    transform = NavRigidTransformV1(
        source_frame_id=source.frame.frame_id,
        target_frame_id=target_frame.frame_id,
        rotation_degrees=0.0,
        translation_x=0.0,
        translation_y=0.0,
        pivot=NavPointV1(0.0, 0.0),
        method="identity_reframe",
    )
    with pytest.raises(ValueError, match="reframing requires every map element"):
        transform_navmap(
            source,
            transform,
            new_revision=2,
            element_ids=("self_body",),
            target_frame=target_frame,
        )
    reframed = reframe_navmap(source, target_frame=target_frame, transform=transform, new_revision=2)
    assert reframed.result_map.frame.frame_id == "allocentric_v1"

    incompatible_units = _frame(frame_id="metric_frame", units="meters")
    unit_transform = replace(transform, target_frame_id=incompatible_units.frame_id)
    with pytest.raises(ValueError, match="identical source and target units"):
        reframe_navmap(source, target_frame=incompatible_units, transform=unit_transform, new_revision=3)

    incompatible_axes = _frame(frame_id="body_plan_v1", x_axis="right", y_axis="forward")
    axis_transform = replace(transform, target_frame_id=incompatible_axes.frame_id)
    with pytest.raises(ValueError, match="identical source and target axis semantics"):
        reframe_navmap(source, target_frame=incompatible_axes, transform=axis_transform, new_revision=3)


def test_alignment_recovers_rigid_transform_and_reports_frame_incompatibility() -> None:
    """Compatible maps align explicitly; incompatible units remain UNKNOWN."""
    source = _scene_map(map_id="alignment_source")
    target = _rigid_candidate(source, map_id="alignment_target")
    alignment = align_navmaps(source, target, thresholds=_match_thresholds())

    assert alignment.status is NavAlignmentStatusV1.ALIGNED
    assert alignment.transform is not None
    assert alignment.transform.rotation_degrees == pytest.approx(20.0)
    assert alignment.rms_error == pytest.approx(0.0, abs=1.0e-12)
    assert alignment.maximum_error == pytest.approx(0.0, abs=1.0e-12)
    assert alignment.overlap_fraction == pytest.approx(1.0)
    assert alignment.inlier_fraction == pytest.approx(1.0)
    assert alignment.uncertainty == pytest.approx(0.0, abs=1.0e-12)

    incompatible = _scene_map(
        map_id="alignment_incompatible",
        frame=_frame(frame_id="metric_frame", units="meters"),
    )
    unknown = align_navmaps(source, incompatible, thresholds=_match_thresholds())
    assert unknown.status is NavAlignmentStatusV1.UNKNOWN
    assert unknown.reason == "incompatible_frame_units"
    assert unknown.transform is None


def test_robust_alignment_localizes_one_changed_element() -> None:
    """One changed landmark must not drag the frame and make every stable element look changed."""
    source = _scene_map(map_id="robust_source")
    target = _independent_map(source, map_id="robust_target")
    target = replace(
        target,
        elements=tuple(
            replace(element, geometry=_geometry(NavGeometryKindV1.POINT, (2.4, 1.0)))
            if element.element_id == "landmark"
            else element
            for element in target.elements
        ),
    )
    result = match_navmaps(source, target, thresholds=_match_thresholds())

    assert result.alignment.status is NavAlignmentStatusV1.ALIGNED
    assert result.alignment.inlier_fraction == pytest.approx(0.8)
    assert result.conflicted_element_pairs == (("landmark", "landmark"),)
    assert result.element_score == pytest.approx(0.8)


def test_alignment_and_matching_survive_renamed_local_ids() -> None:
    """Local developer ids are not required when unique represented roles correspond."""
    source = _scene_map(map_id="renamed_source")
    target = _rigid_candidate(source, map_id="renamed_target", rename=True)
    result = match_navmaps(source, target, thresholds=_match_thresholds())

    assert result.status is NavMatchStatusV1.EXACT
    assert result.score == pytest.approx(1.0)
    assert result.coverage == pytest.approx(1.0)
    assert any(item.method == "unique_role" for item in result.correspondences)
    assert not result.missing_source_element_ids
    assert not result.novel_target_element_ids


def test_match_retains_geometry_activation_parent_relation_and_link_conflicts() -> None:
    """A partial match retains structural evidence instead of only one scalar."""
    source = _scene_map(map_id="partial_source")
    provenance = source.provenance
    elements: list[NavElementV1] = []
    for element in source.elements:
        if element.element_id == "self_body":
            elements.append(
                replace(element, geometry=_geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.2), (0.8, 1.2)))
            )
        elif element.element_id == "self_head":
            elements.append(
                replace(
                    element,
                    activations=(NavActivationV1("different_feature", 0.9, provenance),),
                    parent_element_id=None,
                )
            )
        elif element.element_id != "self_foot":
            elements.append(element)
    elements.append(
        NavElementV1(
            "tail",
            "tail",
            _geometry(NavGeometryKindV1.POINT, (-0.5, 0.5)),
            (),
            "self_body",
            provenance,
        )
    )
    target = NavMapV2(
        map_id="partial_target",
        revision=1,
        role=source.role,
        frame=source.frame,
        provenance=provenance,
        elements=tuple(elements),
        relations=(NavRelationV1("part_of", "tail", "self_body", provenance),),
        links=(),
    )
    result = match_navmaps(source, target, thresholds=_match_thresholds())

    assert result.status is NavMatchStatusV1.PARTIAL
    assert "self_foot" in result.missing_source_element_ids
    assert "tail" in result.novel_target_element_ids
    assert ("self_body", "self_body") in result.conflicted_element_pairs
    assert ("self_head", "self_head") in result.conflicted_element_pairs
    assert result.relation_score < 1.0
    assert result.link_score < 1.0
    assert result.score < 1.0


def test_match_preserves_map_role_as_explicit_content() -> None:
    """Identical elements in a differently purposed map are not an exact content match."""
    source = _scene_map(map_id="role_source")
    target = replace(_independent_map(source, map_id="role_target"), role="different_scene_role")
    result = match_navmaps(source, target, thresholds=_match_thresholds())
    residual = structured_residual(source, target, match_result=result)

    assert result.status is NavMatchStatusV1.PARTIAL
    assert result.map_role_match is False
    assert result.score < 1.0
    assert residual.map_role_changed is True
    assert residual.has_content_difference is True
    proposal = propose_revision(source, target, residual=residual, thresholds=_revision_thresholds())
    assert proposal.decision is NavRevisionDecisionV1.CREATE


def test_match_rank_returns_clear_winner_and_explicit_margin() -> None:
    """A bounded candidate set produces a winner without accepting it as current truth."""
    query = _scene_map(map_id="rank_query")
    exact = _rigid_candidate(query, map_id="rank_exact")
    altered = _rigid_candidate(query, map_id="rank_altered")
    altered = replace(
        altered,
        elements=tuple(
            replace(element, role="other_role") if element.element_id == "landmark" else element
            for element in altered.elements
        ),
    )
    ranking = match_rank(query, (altered, exact), thresholds=_match_thresholds())

    assert ranking.status is NavMatchRankStatusV1.RANKED
    assert ranking.winner_ref == NavMapRefV1("rank_exact", 1)
    assert ranking.best_candidate_ref == ranking.winner_ref
    assert ranking.margin is not None and ranking.margin > 0.0
    assert ranking.ranked_matches[0].target_map_ref == ranking.winner_ref


def test_match_rank_preserves_ambiguity_and_unknown() -> None:
    """Equal candidates remain AMBIGUOUS and incompatible candidates remain UNKNOWN."""
    query = _scene_map(map_id="ambiguous_query")
    first = _rigid_candidate(query, map_id="ambiguous_a")
    second = _rigid_candidate(query, map_id="ambiguous_b")
    ambiguous = match_rank(query, (first, second), thresholds=_match_thresholds(ambiguity_margin=0.01))
    assert ambiguous.status is NavMatchRankStatusV1.AMBIGUOUS
    assert ambiguous.winner_ref is None
    assert ambiguous.margin == pytest.approx(0.0)

    incompatible = _scene_map(
        map_id="unknown_candidate",
        frame=_frame(frame_id="different_units", units="meters"),
    )
    unknown = match_rank(query, (incompatible,), thresholds=_match_thresholds())
    assert unknown.status is NavMatchRankStatusV1.UNKNOWN
    assert unknown.winner_ref is None


def test_standup_expected_successor_residual_localizes_failed_body_change() -> None:
    """Expected upright versus observed lateral geometry names the changed SELF parts."""
    fallen = _scene_map(map_id="standup_residual", horizontal=True)
    expected_provenance = _provenance(NavSourceClassV1.EXPECTED, "primitive:stand_up")
    transform = NavRigidTransformV1(
        source_frame_id=fallen.frame.frame_id,
        target_frame_id=fallen.frame.frame_id,
        rotation_degrees=-90.0,
        translation_x=-1.0,
        translation_y=0.0,
        pivot=NavPointV1(1.0, 0.2),
        method="standup_expected_successor",
    )
    expected = transform_navmap(
        fallen,
        transform,
        new_revision=2,
        element_ids=("self_body", "self_head", "self_foot"),
        result_provenance=expected_provenance,
    ).result_map
    observed_failed = _scene_map(map_id="standup_observed_failed", horizontal=True)

    match = match_navmaps(expected, observed_failed, thresholds=_match_thresholds())
    residual = structured_residual(expected, observed_failed, match_result=match)
    changed_ids = {
        item.expected_element_id
        for item in residual.element_residuals
        if item.content_difference
    }

    assert match.alignment.reason == "aligned_declared_frame_identity"
    assert match.status is NavMatchStatusV1.PARTIAL
    assert changed_ids == {"self_body", "self_head", "self_foot"}
    assert residual.has_content_difference is True
    assert _element(expected, "ground_surface") == _element(fallen, "ground_surface")


def test_structured_residual_separates_content_from_source_provenance() -> None:
    """Expected and observed copies can be content-equal while retaining source differences."""
    expected = _scene_map(
        map_id="expected_equal",
        provenance=_provenance(NavSourceClassV1.EXPECTED, "primitive:stand_up"),
    )
    evidence = _scene_map(
        map_id="evidence_equal",
        provenance=_provenance(NavSourceClassV1.OBSERVED, "sensor:body_ground"),
    )
    match = match_navmaps(expected, evidence, thresholds=_match_thresholds())
    residual = structured_residual(expected, evidence, match_result=match)

    assert match.status is NavMatchStatusV1.EXACT
    assert residual.has_content_difference is False
    assert residual.has_source_difference is True
    assert residual.map_provenance_changed is True
    assert residual.reason == "content_equal_source_changed"


def test_structured_residual_names_element_relation_and_link_changes() -> None:
    """Residuals localize geometry/features and sparse relation/link changes."""
    expected = _scene_map(map_id="residual_expected")
    evidence = _scene_map(map_id="residual_evidence")
    changed_body = replace(
        _element(evidence, "self_body"),
        geometry=_geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.2), (0.8, 1.4)),
        activations=(NavActivationV1("body_axis", 0.60, evidence.provenance),),
    )
    evidence = replace(
        evidence,
        elements=tuple(changed_body if element.element_id == "self_body" else element for element in evidence.elements),
        relations=(NavRelationV1("part_of", "self_head", "self_body", evidence.provenance),),
        links=(),
    )
    match = match_navmaps(expected, evidence, thresholds=_match_thresholds())
    residual = structured_residual(expected, evidence, match_result=match)
    body_residual = next(item for item in residual.element_residuals if item.expected_element_id == "self_body")

    assert residual.has_content_difference is True
    assert body_residual.geometry_outside_tolerance is True
    assert "self_related" in body_residual.missing_activation_names
    delta_by_name = dict(body_residual.activation_strength_deltas)
    assert delta_by_name["body_axis"] == pytest.approx(-0.35)
    assert residual.missing_relations
    assert residual.missing_links


def test_revision_proposal_returns_keep_revise_create_unknown_and_reject_all() -> None:
    """The pure proposal layer preserves all five open-world outcomes."""
    base = _scene_map(map_id="proposal_base")
    observed_equal = _independent_map(base, map_id="proposal_equal")
    equal_match = match_navmaps(base, observed_equal, thresholds=_match_thresholds())
    equal_residual = structured_residual(base, observed_equal, match_result=equal_match)
    keep = propose_revision(base, observed_equal, residual=equal_residual, thresholds=_revision_thresholds())
    assert keep.decision is NavRevisionDecisionV1.KEEP

    changed = _independent_map(base, map_id="proposal_changed")
    changed = replace(
        changed,
        elements=tuple(
            replace(element, geometry=_geometry(NavGeometryKindV1.POINT, (2.4, 1.0)))
            if element.element_id == "landmark"
            else element
            for element in changed.elements
        ),
    )
    changed_match = match_navmaps(base, changed, thresholds=_match_thresholds())
    changed_residual = structured_residual(base, changed, match_result=changed_match)
    revise = propose_revision(base, changed, residual=changed_residual, thresholds=_revision_thresholds())
    assert revise.decision is NavRevisionDecisionV1.REVISE

    unrelated = NavMapV2(
        map_id="proposal_unrelated",
        revision=1,
        role="different_scene",
        frame=base.frame,
        provenance=base.provenance,
        elements=(
            NavElementV1(
                "food_patch",
                "food_patch",
                _geometry(NavGeometryKindV1.POLYGON, (-1.0, -1.0), (0.0, -1.0), (-0.5, 0.0)),
                (),
                None,
                base.provenance,
            ),
        ),
    )
    unrelated_match = match_navmaps(base, unrelated, thresholds=_match_thresholds())
    unrelated_residual = structured_residual(base, unrelated, match_result=unrelated_match)
    create = propose_revision(base, unrelated, residual=unrelated_residual, thresholds=_revision_thresholds())
    assert create.decision is NavRevisionDecisionV1.CREATE

    incompatible = _scene_map(
        map_id="proposal_incompatible",
        frame=_frame(frame_id="metric", units="meters"),
    )
    incompatible_match = match_navmaps(base, incompatible, thresholds=_match_thresholds())
    incompatible_residual = structured_residual(base, incompatible, match_result=incompatible_match)
    unknown = propose_revision(base, incompatible, residual=incompatible_residual, thresholds=_revision_thresholds())
    assert unknown.decision is NavRevisionDecisionV1.UNKNOWN

    incompatible_content = _independent_map(base, map_id="proposal_reject")
    incompatible_content = replace(
        incompatible_content,
        elements=tuple(replace(element, role=f"other_{element.role}", activations=()) for element in base.elements),
        relations=(),
        links=(),
    )
    reject_match = match_navmaps(base, incompatible_content, thresholds=_match_thresholds())
    reject_residual = structured_residual(base, incompatible_content, match_result=reject_match)
    reject = propose_revision(
        base,
        incompatible_content,
        residual=reject_residual,
        thresholds=_revision_thresholds(minimum_revise_score=0.50, maximum_reject_all_score=0.30),
    )
    assert reject.decision is NavRevisionDecisionV1.REJECT_ALL


def test_apply_revision_preserves_family_ids_and_can_create_new_family() -> None:
    """REVISE preserves stable ids; CREATE requires an explicit new family id."""
    base = _scene_map(map_id="apply_base")
    changed = _rigid_candidate(base, map_id="apply_evidence", rename=True)
    changed = replace(
        changed,
        elements=tuple(
            replace(element, geometry=_geometry(NavGeometryKindV1.POINT, (2.8, 1.4)))
            if element.role == "landmark"
            else element
            for element in changed.elements
        ),
    )
    match = match_navmaps(base, changed, thresholds=_match_thresholds())
    residual = structured_residual(base, changed, match_result=match)
    proposal = propose_revision(base, changed, residual=residual, thresholds=_revision_thresholds())
    assert proposal.decision is NavRevisionDecisionV1.REVISE

    child = apply_revision(base, changed, proposal, new_revision=2)
    assert child.map_id == base.map_id
    assert child.parent_ref == NavMapRefV1(base.map_id, 1)
    assert {element.element_id for element in child.elements} == {element.element_id for element in base.elements}
    assert child.provenance == changed.provenance

    unrelated = NavMapV2(
        map_id="create_evidence",
        revision=1,
        role="food_scene",
        frame=base.frame,
        provenance=base.provenance,
        elements=(
            NavElementV1(
                "food_patch",
                "food_patch",
                _geometry(NavGeometryKindV1.POINT, (1.0, 1.0)),
                (),
                None,
                base.provenance,
            ),
        ),
    )
    create_match = match_navmaps(base, unrelated, thresholds=_match_thresholds())
    create_residual = structured_residual(base, unrelated, match_result=create_match)
    create_proposal = propose_revision(base, unrelated, residual=create_residual, thresholds=_revision_thresholds())
    created = apply_revision(base, unrelated, create_proposal, new_map_id="new_food_family")
    assert created == replace(unrelated, map_id="new_food_family")

    with pytest.raises(ValueError, match="CREATE requires new_map_id"):
        apply_revision(base, unrelated, create_proposal)
    with pytest.raises(ValueError, match="must differ from the base"):
        apply_revision(base, unrelated, create_proposal, new_map_id=base.map_id)


def test_apply_revision_keep_and_unknown_are_authority_safe() -> None:
    """KEEP returns the base; UNKNOWN cannot be applied as if it were evidence authority."""
    base = _scene_map(map_id="apply_keep_base")
    equal = _independent_map(base, map_id="apply_keep_evidence")
    match = match_navmaps(base, equal, thresholds=_match_thresholds())
    residual = structured_residual(base, equal, match_result=match)
    keep = propose_revision(base, equal, residual=residual, thresholds=_revision_thresholds())
    assert apply_revision(base, equal, keep) is base
    with pytest.raises(ValueError, match="KEEP does not create"):
        apply_revision(base, equal, keep, new_revision=2)

    incompatible = _scene_map(
        map_id="apply_unknown",
        frame=_frame(frame_id="metric", units="meters"),
    )
    unknown_match = match_navmaps(base, incompatible, thresholds=_match_thresholds())
    unknown_residual = structured_residual(base, incompatible, match_result=unknown_match)
    unknown = propose_revision(base, incompatible, residual=unknown_residual, thresholds=_revision_thresholds())
    with pytest.raises(ValueError, match="cannot apply unknown"):
        apply_revision(base, incompatible, unknown, new_revision=2)


def test_threshold_records_reject_inconsistent_values() -> None:
    """Phase 1C decisions must not depend on hidden or inconsistent thresholds."""
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        _match_thresholds(ambiguity_margin=1.1)
    query = _scene_map(map_id="candidate_bound_query")
    first_candidate = _scene_map(map_id="candidate_bound_a")
    second_candidate = _scene_map(map_id="candidate_bound_b")
    with pytest.raises(ValueError, match="candidate count exceeds"):
        thresholds = replace(_match_thresholds(), maximum_candidate_count=1)
        match_rank(query, (first_candidate, second_candidate), thresholds=thresholds)
    with pytest.raises(ValueError, match="candidate map references must be unique"):
        match_rank(query, (first_candidate, first_candidate), thresholds=_match_thresholds())
    with pytest.raises(ValueError, match="greater than or equal"):
        NavRevisionThresholdsV1(0.4, 0.5, 0.5, 0.1)
    with pytest.raises(ValueError, match="must not exceed"):
        NavRevisionThresholdsV1(0.9, 0.5, 0.5, 0.6)


def test_phase1c_results_are_immutable_and_json_safe() -> None:
    """All Phase 1C trace records are immutable and JSON-safe."""
    source = _scene_map(map_id="json_source")
    target = _rigid_candidate(source, map_id="json_target")
    transform_result = translate_navmap(source, delta_x=0.1, delta_y=0.0, new_revision=2)
    alignment = align_navmaps(source, target, thresholds=_match_thresholds())
    match = match_navmaps(source, target, thresholds=_match_thresholds())
    ranking = match_rank(source, (target,), thresholds=_match_thresholds())
    residual = structured_residual(source, target, match_result=match)
    proposal = propose_revision(source, target, residual=residual, thresholds=_revision_thresholds())

    for result in (transform_result, alignment, match, ranking, residual, proposal):
        json.dumps(result.as_dict(), sort_keys=True)
    with pytest.raises(FrozenInstanceError):
        alignment.reason = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        proposal.decision = NavRevisionDecisionV1.CREATE  # type: ignore[misc]


def test_phase1c_operations_do_not_mutate_source_or_candidate_maps() -> None:
    """All Phase 1C operators leave source bytes and signatures unchanged."""
    source = _scene_map(map_id="purity_source")
    target = _rigid_candidate(source, map_id="purity_target")
    source_snapshot = (source.to_bytes(), source.content_signature(), source.record_signature())
    target_snapshot = (target.to_bytes(), target.content_signature(), target.record_signature())

    translate_navmap(source, delta_x=0.1, delta_y=0.1, new_revision=2)
    alignment = align_navmaps(source, target, thresholds=_match_thresholds())
    match = match_navmaps(source, target, thresholds=_match_thresholds())
    match_rank(source, (target,), thresholds=_match_thresholds())
    residual = structured_residual(source, target, match_result=match)
    propose_revision(source, target, residual=residual, thresholds=_revision_thresholds())

    assert alignment.status is NavAlignmentStatusV1.ALIGNED
    assert (source.to_bytes(), source.content_signature(), source.record_signature()) == source_snapshot
    assert (target.to_bytes(), target.content_signature(), target.record_signature()) == target_snapshot
