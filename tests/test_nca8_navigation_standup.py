#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Navigation arbitration and StandUp primitive tests for NCA8 Gate A."""

from __future__ import annotations

from nca8_executive import NavigationRuntimeV1, WorkingNavMapStateV1
from nca8_primitives import (
    PrimitiveApplicabilityV1,
    PrimitiveKindV1,
    StandUpIPV1,
)
from nca8_runtime import Nca8SessionV1


class _LowPriorityEligiblePrimitiveV1:
    """Test primitive proving registration order cannot displace visible priority."""

    primitive_id = "ip:test_low_priority"

    def evaluate_applicability(
        self,
        wnm: WorkingNavMapStateV1,
        *,
        cycle_id: int,
    ) -> PrimitiveApplicabilityV1:
        return PrimitiveApplicabilityV1(
            primitive_id=self.primitive_id,
            primitive_kind=PrimitiveKindV1.INSTINCTIVE,
            cycle_id=cycle_id,
            source_wnm_id=wnm.working_id,
            eligible=True,
            safety_rank=0,
            fit_rank=1,
            drive_rank=0,
            persistence_rank=0,
            learned_success_rank=0,
            vetoes=(),
            reasons=("test_only_low_priority_candidate",),
            stable_tie_key=self.primitive_id,
        )

    def apply(self, *_args, **_kwargs):
        raise AssertionError("the lower-priority test primitive must not be selected")


def test_navigation_selects_and_applies_standup_from_wnm_relations() -> None:
    """The first focal application should come from Navigation, not the runner or BodyMap."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()
    application = result.navigation.application

    assert result.navigation.selected_primitive_id == "ip:stand_up"
    assert application is not None
    assert application.application_id == "application:stand_up:1"
    assert application.source_wnm_id == result.wnm.working_id
    assert application.task_action.kind.value == "STAND_UP"
    assert application.expected_relations == ("posture:standing", "support:stable")
    assert result.commitment.selected_primitive_id == "ip:stand_up"
    assert result.commitment.focal_operation_id == application.application_id


def test_primitive_registration_order_does_not_change_navigation_winner() -> None:
    """Stable visible rank components, not registration order, should choose StandUp."""
    source_session = Nca8SessionV1()
    wnm = source_session.run_cognitive_cycle().wnm
    assert wnm is not None

    first = NavigationRuntimeV1().commit(
        wnm,
        (StandUpIPV1(), _LowPriorityEligiblePrimitiveV1()),
        cycle_id=1,
    )
    second = NavigationRuntimeV1().commit(
        wnm,
        (_LowPriorityEligiblePrimitiveV1(), StandUpIPV1()),
        cycle_id=1,
    )

    assert first.selected_primitive_id == "ip:stand_up"
    assert second.selected_primitive_id == "ip:stand_up"
    assert first.application.as_dict() == second.application.as_dict()
    assert [record.primitive_id for record in first.applicability_records] == [
        "ip:stand_up",
        "ip:test_low_priority",
    ]
