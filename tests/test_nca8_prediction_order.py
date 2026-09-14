#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PNM-before-dispatch and later event-matched outcome tests for NCA8 Gate A."""

from __future__ import annotations

from nca8_maps import Nca8PostureStateV1, create_posture_support_map_library_v1
from nca8_prediction import Nca8PredictionRuntimeV1, PredictionOutcomeStatusV1
from nca8_runtime import Nca8SessionV1


def test_trace_proves_pnm_and_body_envelope_exist_before_environment_dispatch() -> None:
    """The environment transition must not participate in constructing the current PNM."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()
    lines = session.trace_lines()

    navigation_index = next(index for index, line in enumerate(lines) if "Navigation commitment completed" in line)
    pnm_index = next(index for index, line in enumerate(lines) if "current PNM created before" in line)
    body_index = next(index for index, line in enumerate(lines) if "BodyMap mapped" in line)
    commitment_index = next(index for index, line in enumerate(lines) if "committed Action_1:STAND_UP" in line)
    dispatch_index = next(index for index, line in enumerate(lines) if "Action_1:STAND_UP completed the external world step" in line)

    handoff_index = next(index for index, line in enumerate(lines) if "[nca8:handoff]" in line)
    close_index = next(index for index, line in enumerate(lines) if "CognitiveCycle_1 closed" in line)
    assert navigation_index < pnm_index < body_index < commitment_index < handoff_index < close_index < dispatch_index
    assert result.pnm.created_cycle == 1
    assert result.pnm.eligible_from_cycle == 2
    assert result.pnm.expected_relations == ("posture:standing", "support:stable")


def test_later_fallen_evidence_fails_the_originating_attempt_and_retry_remains_possible() -> None:
    """Command time is not success; the next current body state closes attempt 1 as failure."""
    session = Nca8SessionV1()
    first = session.run_cognitive_cycle()
    second = session.run_cognitive_cycle()

    assert first.prediction_outcomes == ()
    assert len(second.prediction_outcomes) == 1
    outcome = second.prediction_outcomes[0]
    assert outcome.status is PredictionOutcomeStatusV1.FAILURE
    assert outcome.application_id == "application:stand_up:1"
    assert outcome.pnm_id == "pnm:application:stand_up:1"
    assert second.navigation.application.application_id == "application:stand_up:2"


def test_missing_body_evidence_remains_unresolved_until_matching_or_expiry() -> None:
    """Unknown posture must not be fabricated into success or failure."""
    session = Nca8SessionV1()
    application = session.run_cognitive_cycle().navigation.application
    assert application is not None
    prediction = Nca8PredictionRuntimeV1()
    prediction.create_current(application)
    library = create_posture_support_map_library_v1()
    unknown = library.update_current_state(
        library.open_world_evidence(
            Nca8PostureStateV1.UNKNOWN,
            reason="missing_posture_predicate_scaffold",
        ),
        sampled_event_cycle=2,
        available_cycle=2,
        applied_cycle=2,
    )

    outcomes = prediction.evaluate_ready(unknown, cycle_id=2)

    assert outcomes == ()
    assert prediction.current_trace is not None
    assert prediction.current_trace.status is PredictionOutcomeStatusV1.UNRESOLVED
