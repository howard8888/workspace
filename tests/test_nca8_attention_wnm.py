#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attention and source-linked WNM authority tests for NCA8 Phase 1D."""

from __future__ import annotations

from nca8_runtime import NCA8_NO_ACTION, Nca8SessionConfigV1, Nca8SessionV1


def test_attention_selects_current_map_state_without_selecting_primitive() -> None:
    """Attention should choose the body-state source while primitive authority remains separate."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()

    assert result.attention_bid is not None
    assert result.attention_bid.source_map_state is result.posture_support_candidate.source_map_state
    assert result.attention_bid.as_dict()["primitive_id"] is None
    assert result.attention_selection.disposition.value == "switch"
    assert result.attention_selection.selected_source_state is result.posture_support_state
    assert result.attention_selection.as_dict()["selected_primitive_id"] is None
    assert result.navigation.selected_primitive_id == "ip:stand_up"


def test_wnm_is_bounded_source_linked_and_does_not_write_back() -> None:
    """The WNM should preserve one source reference and minimum current relations only."""
    session = Nca8SessionV1()
    durable_signature = session._map_library.durable_record_signature()  # pylint: disable=protected-access

    result = session.run_cognitive_cycle()
    wnm = result.wnm

    assert wnm is not None
    assert wnm.working_id == "wnm:current"
    assert wnm.primary_source_state is result.posture_support_state
    assert wnm.source_candidate_id == result.posture_support_candidate.candidate_id
    assert set(wnm.working_relations) == {
        "contact:lateral_ground",
        "posture:fallen",
        "support:inadequate",
    }
    assert wnm.context_refs == ()
    assert wnm.as_dict()["automatic_writeback"] is False
    assert session._map_library.durable_record_signature() == durable_signature  # pylint: disable=protected-access


def test_attention_ablation_prevents_wnm_and_task_action_without_fallback() -> None:
    """A current candidate must not bypass disabled Attention through a hidden StandUp route."""
    session = Nca8SessionV1(Nca8SessionConfigV1(attention_enabled=False))

    result = session.run_cognitive_cycle()

    assert result.posture_support_candidate is not None
    assert result.attention_selection.disposition.value == "release"
    assert result.wnm is None
    assert result.navigation.selected_primitive_id is None
    assert result.pnm is None
    assert result.output == NCA8_NO_ACTION
    assert result.environment_action is None
    assert any(
        "Attention released the primary source map state" in line
        for line in session.trace_lines()
    )
