#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Durable NavMap versus transient NavMap-state tests for NCA8 Phase 1C."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from nca8_maps import (
    Nca8PostureStateV1,
    create_posture_support_map_library_v1,
)


def _update_profile_v1(library, profile_id: str, cycle_id: int):
    """Evaluate and apply one canonical profile to the current state slot."""
    evidence = library.evaluate_profile(profile_id)
    return library.update_current_state(
        evidence,
        sampled_event_cycle=cycle_id,
        available_cycle=cycle_id,
        applied_cycle=cycle_id,
    )


def test_repeated_fallen_evidence_refreshes_one_state_without_map_revision_growth() -> None:
    """Stable perception should refresh one runtime slot, not recruit durable maps."""
    library = create_posture_support_map_library_v1()
    durable = library.durable_map()
    signature = library.durable_record_signature()

    first = _update_profile_v1(library, "lateral_ground_profile_v1", 1)
    second = _update_profile_v1(library, "lateral_ground_profile_v1", 2)

    assert first.state_id == second.state_id == "posture_support:current"
    assert first.source_map_ref == second.source_map_ref
    assert first.posture is Nca8PostureStateV1.FALLEN
    assert second.posture is Nca8PostureStateV1.FALLEN
    assert second.update_count == 2
    assert second.equivalent_refresh_count == 1
    assert second.configuration_change_count == 0
    assert library.durable_map_count == 1
    assert library.current_state_count == 1
    assert library.durable_map() is durable
    assert library.durable_record_signature() == signature
    assert library.posture_support_ref.revision == 1


def test_fallen_to_standing_changes_current_state_but_not_durable_content() -> None:
    """A posture change should replace transient content under the same map revision."""
    library = create_posture_support_map_library_v1()
    durable = library.durable_map()
    signature = library.durable_record_signature()

    fallen = _update_profile_v1(library, "lateral_ground_profile_v1", 1)
    standing = _update_profile_v1(library, "upright_support_profile_v1", 2)

    assert fallen.posture is Nca8PostureStateV1.FALLEN
    assert standing.posture is Nca8PostureStateV1.STANDING
    assert standing.state_id == fallen.state_id
    assert standing.source_map_ref == fallen.source_map_ref
    assert standing.configuration_change_count == 1
    assert standing.equivalent_refresh_count == 0
    assert library.durable_map() is durable
    assert library.durable_record_signature() == signature
    assert library.durable_map_count == 1
    assert library.current_state_count == 1


def test_durable_navmap_is_frozen_and_contains_no_runtime_authority_fields() -> None:
    """Activation/currentness/timing must stay outside the immutable decoded map."""
    library = create_posture_support_map_library_v1()
    durable = library.durable_map()

    with pytest.raises(FrozenInstanceError):
        durable.revision = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        durable.elements[0].role = "mutated"  # type: ignore[misc]

    payload = durable.as_dict()
    for forbidden in (
        "activation",
        "evidence_current",
        "sampled_event_cycle",
        "available_cycle",
        "applied_cycle",
        "last_supported_cycle",
        "ready",
        "focal",
    ):
        assert forbidden not in payload


def test_current_map_view_is_read_only_diagnostic_projection() -> None:
    """The current-state ensemble view must not become another world or authority."""
    library = create_posture_support_map_library_v1()
    _update_profile_v1(library, "lateral_ground_profile_v1", 1)

    view = library.current_map_view()
    payload = view.as_dict()

    assert len(view.states) == 1
    assert payload["authority"] == "diagnostic_only"
    assert payload["state_count"] == 1
    assert payload["states"][0]["posture"] == "fallen"
