#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BodyMap action-envelope and environment-adapter tests for NCA8 Gate A."""

from __future__ import annotations

from nca8_prediction import PredictionOutcomeStatusV1
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionConfigV1, Nca8SessionV1


def test_bodymap_authorizes_body_relative_standup_target_and_envelope() -> None:
    """A Navigation-selected task should be mapped through BodyMap before dispatch."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()
    handoff = result.body_handoff

    assert handoff is not None and handoff.authorized is True
    assert handoff.task_target.body_frame == "self_ground_egocentric_v1"
    assert handoff.task_target.target_relations == (
        "target_posture:upright",
        "target_support:stable",
    )
    assert handoff.envelope.status.value == "authorized"
    assert "whole_body_posture" in handoff.envelope.permitted_resources
    assert handoff.lower_request.task_action.kind.value == "STAND_UP"
    assert result.environment_action == "policy:stand_up"


def test_bodymap_ablation_blocks_environment_action_without_legacy_fallback() -> None:
    """PNM may exist, but a rejected body handoff must emit explicit NO_ACTION."""
    session = Nca8SessionV1(Nca8SessionConfigV1(body_action_handoff_enabled=False))

    result = session.run_cognitive_cycle()

    assert result.navigation.selected_primitive_id == "ip:stand_up"
    assert result.pnm is not None
    assert result.body_handoff is not None and result.body_handoff.authorized is False
    assert result.output == NCA8_NO_ACTION
    assert result.environment_action is None
    assert len(result.prediction_outcomes) == 1
    assert result.prediction_outcomes[0].status is PredictionOutcomeStatusV1.NOT_APPLIED
    assert "ablation" in result.prediction_outcomes[0].reason
