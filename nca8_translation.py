#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One explicitly supplied operation fixture for P16-2A-B translation qualification.

The LEARNED interface kind permits an externally supplied task transformation
without adding an innate visual primitive. Nothing is acquired here: the fixture
and its region handle are installed before the trial and are labelled as such in
every application. Navigation still performs ordinary applicability/selection.
One application is permitted, not a covert Follow-Mom loop or route planner.
Its source-relative proposal/PNM and BodyMap's independent egocentric target
remain separate calculations with their original evidence and finite bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import VisualApproachRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_prediction import ProjectedNavMapV1, VisualTranslationPreviewV1
from nca8_primitives import (
    PrimitiveApplicationV1, PrimitiveApplicabilityV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1,
)
from nca8_sensorimotor_contracts import TargetOriginV1
from nca8_visual import VisualNavMapStateV1

__version__ = "0.1.0"
__all__ = ["TranslationFixtureV1", "TranslationApplicationV1", "SuppliedTranslationOperationV1", "__version__"]


@dataclass(frozen=True, slots=True)
class TranslationFixtureV1:
    """Fixed test requirement, not inferred maternal identity or an acquired LP.

    Region selection and the desired stand-off are supplied by the experiment.
    At most one quarter-metre contribution can be selected; fresh observations
    do not grant a second application. The lower target receives its own eight-
    tick lease and protected support checks. Independent stream switches remove
    source products, not motor capabilities or physical observations.
    """

    region_id: str = "region_1"
    stand_off_metres: float = 0.5
    maximum_step_metres: float = 0.25
    recognition_enabled: bool = True
    spatial_enabled: bool = True

    def __post_init__(self) -> None:
        if (not isinstance(self.region_id, str) or not self.region_id or len(self.region_id) > 80
                or any(not (char.isascii() and (char.isalnum() or char in "_:.-/")) for char in self.region_id)):
            raise ValueError("fixture requires a bounded opaque region handle")
        for name, minimum, maximum in (("stand_off_metres", 0.0, 100.0), ("maximum_step_metres", 0.000001, 0.25)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{name} lies outside the fixed fixture range")
        if not isinstance(self.recognition_enabled, bool) or not isinstance(self.spatial_enabled, bool):
            raise TypeError("stream switches must be Boolean")


@dataclass(frozen=True, slots=True)
class TranslationApplicationV1(PrimitiveApplicationV1):
    """Selected test contribution with actual source-conditioned prospective geometry.

    The inherited A0 transport is null, just as in the enhanced Righting subtype.
    Only the typed contribution may become an authorized motor target, after the
    common E handoff and closure. Calling a renderer cannot execute this object.
    """

    contribution: VisualApproachRequestV1
    projection: VisualTranslationPreviewV1

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if not isinstance(self.contribution, VisualApproachRequestV1) or not isinstance(self.projection, VisualTranslationPreviewV1):
            raise TypeError("translation requires its original typed request and prediction")
        if (self.contribution.origin.application_id != self.application_id or self.projection.pnm.application_id != self.application_id
                or self.contribution.source_map_ref != self.projection.basis.source_map_ref
                or self.contribution.origin.task_id != self.projection.task_id
                or self.contribution.region_id != self.projection.region_id):
            raise ValueError("translation projection and contribution have different origins")

    def as_dict(self) -> dict[str, object]:
        """Expose the fixture status without claiming acquisition or movement."""
        return {**PrimitiveApplicationV1.as_dict(self), "contribution": self.contribution.as_dict(),
                "projection": self.projection.as_dict(), "origin_status": "supplied_LP_kind_fixture_not_acquired"}


class SuppliedTranslationOperationV1:
    """Use the common selector once; no world, lower control or hidden task sequence.

    Eligibility reads only the current selected visual source and fixed fixture.
    Body support and actual effector capability remain BodyMap's decisions.
    Cancellation closes this one-shot fixture rather than restarting it on a new
    sample. A fresh trial/reset creates a fresh explicitly supplied fixture.
    """

    primitive_id = "fixture:translation"
    primitive_kind = PrimitiveKindV1.LEARNED

    def __init__(self, fixture: TranslationFixtureV1) -> None:
        if not isinstance(fixture, TranslationFixtureV1):
            raise TypeError("expected TranslationFixtureV1")
        self.fixture = fixture
        self._spent = False

    def cancel(self) -> None:
        """Prevent a later application; this grants no motor rights or task success."""
        self._spent = True

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Report source compatibility without modifying source or consuming budget."""
        if not isinstance(wnm, WorkingNavMapStateV1) or wnm.refreshed_cycle != cycle_id:
            raise ValueError("translation requires the current WNM")
        source = wnm.primary_source_state
        reason = "visual_source_unavailable"
        if self._spent:
            reason = "supplied_operation_already_spent"
        elif isinstance(source, VisualNavMapStateV1) and source.evidence_current and source.self_position is not None:
            target = next((item.position for item in source.guidance if item.region_id == self.fixture.region_id), None)
            if target is not None:
                distance = math.hypot(target.x - source.self_position.x, target.y - source.self_position.y)
                reason = "supplied_translation_applicable" if distance > self.fixture.stand_off_metres + 1e-12 else "already_within_stand_off"
        eligible = reason == "supplied_translation_applicable"
        return PrimitiveApplicabilityV1(
            self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
            0, 100 if eligible else 0, 0, 0, 0, () if eligible else (reason,), (reason,), self.primitive_id,
        )

    def apply(
        self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int,
    ) -> TranslationApplicationV1:
        """Compute one bounded source-relative change; BodyMap computes its own frame."""
        actual = self.evaluate_applicability(wnm, cycle_id=cycle_id)
        if actual != applicability or not actual.eligible:
            raise ValueError("translation needs its current eligible selection")
        source = wnm.primary_source_state
        if not isinstance(source, VisualNavMapStateV1) or source.self_position is None:
            raise ValueError("selected source lacks current visual position")
        target = next(item.position for item in source.guidance if item.region_id == self.fixture.region_id)
        dx, dy = target.x - source.self_position.x, target.y - source.self_position.y
        distance = math.hypot(dx, dy)
        scale = min(self.fixture.maximum_step_metres, distance - self.fixture.stand_off_metres) / distance
        predicted = NavPointV1(source.self_position.x + scale * dx, source.self_position.y + scale * dy)
        app_id = f"translation:{source.stream.generation}:{cycle_id}"
        task_id = f"supplied_translation:{source.stream.generation}"
        expected = ("SELF:bounded_toward_represented_region", "target:original_scene_anchor_retained")
        pnm = ProjectedNavMapV1(f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id,
                               expected, "later corresponding visual acquisition; conditional displacement", cycle_id + 1, cycle_id + 2)
        contribution = VisualApproachRequestV1(
            TargetOriginV1(source.stream, task_id, app_id, f"translation_envelope:{app_id}"),
            source.source_map_ref, self.fixture.region_id, self.fixture.stand_off_metres, self.fixture.maximum_step_metres,
        )
        projection = VisualTranslationPreviewV1(pnm, source, task_id, self.fixture.region_id, target, predicted)
        result = TranslationApplicationV1(
            app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
            ("supplied_operation:single_bounded_translation",), expected, pnm.observation_condition,
            TaskActionV1(f"transport:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None, contribution, projection,
        )
        self._spent = True
        return result
