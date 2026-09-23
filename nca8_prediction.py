#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Current PNM and event-matched pending outcome support for NCA8 Gate A.

Purpose
-------
A Projected NavMap (PNM) is created only after Navigation applies one selected
focal primitive and before its task action reaches the environment boundary.
It contains only the minimum expected task-level relations for that concrete
application.  Later current body evidence closes the originating expectation as
success, failure, unresolved, expired, or not applied.

Authority boundary
------------------
Prediction records are prospective and never become present truth, WNM content,
or action authority.  The prediction runtime cannot dispatch an action or read
the physical environment.  It compares only a later NCA8-owned current
``NavMapStateV1`` whose sampled event follows the originating application.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence

from cca8_navmap_kernel import NavPointV1
from nca8_visual import VisualNavMapStateV1
from nca8_maternal import MaternalNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1
from nca8_maps import MotorSupportConfigurationV1, Nca8PostureStateV1, Nca8SupportStateV1, NavMapStateV1
from nca8_primitives import PrimitiveApplicationV1

# Small validators intentionally remain local for readable standalone modules.
# pylint: disable=duplicate-code

__version__ = "0.7.0"
__all__ = [
    "Nca8PredictionRuntimeV1",
    "PendingPredictionTraceV1",
    "PredictionOutcomeStatusV1",
    "PredictionOutcomeV1",
    "ProjectedNavMapV1",
    "SupportPreviewV1", "VisualTranslationPreviewV1", "MaternalApproachPreviewV1", "SeekNipplePreviewV1", "SucklePreviewV1",
    "__version__",
]

_MAX_RELATIONS = 16
_MAX_EVIDENCE = 8
_MAX_PENDING = 8
_MAX_OUTCOME_HISTORY = 32


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_identifier(value: str, *, field_name: str, maximum: int = 180) -> str:
    """Return one non-empty bounded identifier."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character limit")
    return normalized


def _bounded_unique_strings(
    values: Sequence[str],
    *,
    field_name: str,
    maximum_items: int,
) -> tuple[str, ...]:
    """Return one bounded unique tuple while preserving caller order."""
    if len(values) > maximum_items:
        raise ValueError(f"{field_name} may contain at most {maximum_items} items")
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = _bounded_identifier(raw, field_name=field_name)
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(item)
        out.append(item)
    return tuple(out)


class PredictionOutcomeStatusV1(str, Enum):
    """Terminal and nonterminal states of one operation-linked expectation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    UNRESOLVED = "unresolved"
    EXPIRED = "expired"
    NOT_APPLIED = "not_applied"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ProjectedNavMapV1:
    """One sparse current task-level prospective layer for one application."""

    pnm_id: str
    application_id: str
    primitive_id: str
    source_wnm_id: str
    created_cycle: int
    expected_relations: tuple[str, ...]
    observation_condition: str
    eligible_from_cycle: int
    expires_after_cycle: int

    def __post_init__(self) -> None:
        for field_name in ("pnm_id", "application_id", "primitive_id", "source_wnm_id"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        created = _positive_int(self.created_cycle, field_name="created_cycle")
        eligible = _positive_int(self.eligible_from_cycle, field_name="eligible_from_cycle")
        expiry = _positive_int(self.expires_after_cycle, field_name="expires_after_cycle")
        if eligible <= created:
            raise ValueError("PNM evidence cannot be eligible in its creation cycle")
        if expiry < eligible:
            raise ValueError("PNM expiry cannot precede its first evidence cycle")
        object.__setattr__(
            self,
            "expected_relations",
            _bounded_unique_strings(
                self.expected_relations,
                field_name="expected relation",
                maximum_items=_MAX_RELATIONS,
            ),
        )
        if not self.expected_relations:
            raise ValueError("PNM requires at least one expected relation")
        object.__setattr__(
            self,
            "observation_condition",
            _bounded_identifier(self.observation_condition, field_name="observation_condition"),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe PNM snapshot."""
        return {
            "pnm_id": self.pnm_id,
            "application_id": self.application_id,
            "primitive_id": self.primitive_id,
            "source_wnm_id": self.source_wnm_id,
            "created_cycle": self.created_cycle,
            "expected_relations": list(self.expected_relations),
            "observation_condition": self.observation_condition,
            "eligible_from_cycle": self.eligible_from_cycle,
            "expires_after_cycle": self.expires_after_cycle,
            "present_state_authority": False,
        }


@dataclass(frozen=True, slots=True)
class SupportPreviewV1:
    """Sparse unexecuted task PNM with fixed planar source anchors.

    The wrapped ``pnm`` is one prospective representation, not a second PNM.
    This record retains only the originating measured support facet and bounded
    expectations; it never copies a durable map or invokes the physical plant.
    Expected coordinates/loading are conditional reference-model predictions,
    not observations or guaranteed BodyMap endpoints. ``None`` preserves an
    unknown/unpredicted channel. The physical horizon is separate from the old
    PNM's focal-cycle metadata. No executed prediction obligation is armed here.
    """

    pnm: ProjectedNavMapV1
    basis: MotorSupportConfigurationV1
    task_id: str
    context_id: str
    horizon_ticks: int
    predicted_tilt: float | None
    predicted_extension: float | None
    predicted_loading: float | None
    predicted_destabilization: float | None
    expected_contact: bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.pnm, ProjectedNavMapV1) or not isinstance(self.basis, MotorSupportConfigurationV1):
            raise TypeError("support preview requires one PNM and its source basis")
        if not self.basis.current or self.pnm.created_cycle != self.basis.applied_cycle:
            raise ValueError("support preview requires its current originating source")
        for name in ("task_id", "context_id"):
            object.__setattr__(self, name, _bounded_identifier(getattr(self, name), field_name=name, maximum=120))
        if isinstance(self.horizon_ticks, bool) or not isinstance(self.horizon_ticks, int) or not 1 <= self.horizon_ticks <= 8:
            raise ValueError("preview horizon must be one to eight lower ticks")
        for name, lower, upper in (
            ("predicted_tilt", -90.0, 90.0), ("predicted_extension", 0.0, 1.0),
            ("predicted_loading", 0.0, 1.0), ("predicted_destabilization", 0.0, 1.0),
        ):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError("prospective values must be numbers or None")
                if not math.isfinite(value) or not lower <= value <= upper:
                    raise ValueError("prospective value outside its represented range")
        observed = self.basis.feedback
        for predicted_name, observed_name in (
            ("predicted_tilt", "body_tilt_degrees"), ("predicted_extension", "support_extension"),
            ("predicted_loading", "useful_loading"), ("predicted_destabilization", "destabilization"),
        ):
            if getattr(self, predicted_name) is not None and (observed is None or getattr(observed, observed_name) is None):
                raise ValueError("this reference preview cannot manufacture an absent source coordinate")
        if self.expected_contact is not None and not isinstance(self.expected_contact, bool):
            raise TypeError("expected_contact must be Boolean or None")
        if self.expected_contact is True:
            feedback = self.basis.feedback
            if feedback is None or feedback.support_contact is not True:
                raise ValueError("this preview can retain observed contact, not invent a supporting surface")

    def as_dict(self) -> dict[str, object]:
        """Export the immutable old claim, not a live reference to the next source."""
        return {
            "pnm": self.pnm.as_dict(), "status": "preview_not_dispatched", "task_id": self.task_id,
            "context_id": self.context_id, "basis": self.basis.as_dict(),
            "observation_ticks": [self.basis.cutoff_tick + 1, self.basis.cutoff_tick + self.horizon_ticks],
            "predicted_tilt": self.predicted_tilt, "predicted_extension": self.predicted_extension,
            "predicted_loading": self.predicted_loading, "predicted_destabilization": self.predicted_destabilization,
            "expected_contact": self.expected_contact, "model": "righting_linear_preview_v1",
            "uncertainty": "conditional_unvalidated_reference_model", "executed_obligation": False,
            "motor_authority": False, "establishes_task_success": False,
        }


@dataclass(frozen=True, slots=True)
class VisualTranslationPreviewV1:
    """Sparse source-relative expectation of one supplied translation operation.

    This is neither body permission nor a plant simulation. The selected fixture
    predicts a bounded SELF displacement while retaining the original target and
    source acquisition. A narrowed/blocked/perturbed execution may not realize it.
    Contact is deliberately not predicted from an unmeasured obstacle radius.
    Later local reports establish local achievement, not an acquired Follow-Mom
    skill or a task-level visual correspondence/learning mechanism.
    """

    pnm: ProjectedNavMapV1
    basis: VisualNavMapStateV1
    task_id: str
    region_id: str
    scene_target: NavPointV1
    predicted_self: NavPointV1
    horizon_ticks: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.pnm, ProjectedNavMapV1) or not isinstance(self.basis, VisualNavMapStateV1):
            raise TypeError("visual projection requires its original PNM/source")
        if not self.basis.evidence_current or self.basis.self_position is None or self.basis.applied_cycle != self.pnm.created_cycle:
            raise ValueError("visual projection requires the current selected source")
        _bounded_identifier(self.task_id, field_name="task_id")
        _bounded_identifier(self.region_id, field_name="region_id")
        if not isinstance(self.scene_target, NavPointV1) or not isinstance(self.predicted_self, NavPointV1):
            raise TypeError("projected geometry requires typed points")
        if not any(item.region_id == self.region_id and item.position == self.scene_target for item in self.basis.guidance):
            raise ValueError("projection cannot invent the target position")
        distance = math.hypot(self.predicted_self.x - self.basis.self_position.x, self.predicted_self.y - self.basis.self_position.y)
        if distance > 0.25 + 1e-12 or max(abs(self.predicted_self.x), abs(self.predicted_self.y)) > 10000:
            raise ValueError("projection exceeds the fixed quarter-metre fixture envelope")
        if isinstance(self.horizon_ticks, bool) or not isinstance(self.horizon_ticks, int) or not 1 <= self.horizon_ticks <= 8:
            raise ValueError("projection horizon must be one to eight lower ticks")

    def as_dict(self) -> dict[str, object]:
        """Export original conditional geometry; no observed change or action credit."""
        return {"pnm": self.pnm.as_dict(), "basis": self.basis.as_dict(), "task_id": self.task_id,
                "region_id": self.region_id, "scene_target": self.scene_target.as_dict(),
                "predicted_self": self.predicted_self.as_dict(), "horizon_ticks": self.horizon_ticks,
                "model": "supplied_translation_reference_v1", "status": "conditional_not_observed",
                "contact_prediction": "not_supplied", "learned_operation": False}


@dataclass(frozen=True, slots=True)
class MaternalApproachPreviewV1:
    """Sparse conditional maternal relation from one selected Follow-Mom application.

    The unchanged target anchor, current SELF and expected bounded displacement
    retain their original source acquisition. Target identity is the configured
    association, not a private physical entity lookup. No contact or target motion
    is invented. Later task-level prediction correspondence remains a separate
    consumer from local target reports and current-proximity evidence.
    """

    pnm: ProjectedNavMapV1
    basis: MaternalNavMapStateV1
    task_id: str
    region_id: str
    scene_target: NavPointV1
    predicted_self: NavPointV1
    horizon_ticks: int = 8
    outcome_consumer_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.outcome_consumer_enabled, bool):
            raise TypeError("maternal outcome consumer marker must be Boolean")
        if not isinstance(self.pnm, ProjectedNavMapV1) or not isinstance(self.basis, MaternalNavMapStateV1):
            raise TypeError("maternal projection requires its original typed PNM/source")
        if not self.basis.action_localized or self.basis.self_position is None or self.basis.applied_cycle != self.pnm.created_cycle:
            raise ValueError("maternal projection requires current SELF and target localization")
        _bounded_identifier(self.task_id, field_name="task_id")
        if self.region_id != self.basis.seed.region_id or self.scene_target != self.basis.target_position:
            raise ValueError("maternal projection cannot replace its original target")
        if not isinstance(self.predicted_self, NavPointV1):
            raise TypeError("predicted SELF must be a typed point")
        distance = math.hypot(self.predicted_self.x - self.basis.self_position.x, self.predicted_self.y - self.basis.self_position.y)
        if distance > 0.25 + 1e-12 or max(abs(self.predicted_self.x), abs(self.predicted_self.y)) > 10000:
            raise ValueError("maternal projection exceeds its fixed quarter-metre envelope")
        # Physical tick counts require built-in integers, not bool or integer subclasses.
        # pylint: disable-next=unidiomatic-typecheck
        if type(self.horizon_ticks) is not int or not 1 <= self.horizon_ticks <= 8:
            raise ValueError("maternal projection horizon must be one to eight physical ticks")

    @property
    def predicted_separation(self) -> float:
        """Compute the expected SELF/target relation, not an observed outcome."""
        return math.hypot(self.scene_target.x - self.predicted_self.x, self.scene_target.y - self.predicted_self.y)

    def as_dict(self) -> dict[str, object]:
        """Expose original conditional meaning without granting motor or learned authority."""
        return {"pnm": self.pnm.as_dict(), "basis": self.basis.as_dict(), "task_id": self.task_id,
                "region_id": self.region_id, "scene_target": self.scene_target.as_dict(), "predicted_self": self.predicted_self.as_dict(),
                "predicted_separation_metres": self.predicted_separation, "horizon_ticks": self.horizon_ticks,
                "model": "follow_mom_static_anchor_v1", "status": "conditional_not_observed",
                "target_motion_assumption": "original_target_stationary_during_contribution", "contact_prediction": "not_supplied",
                "task_outcome_consumer": "maternal_correspondence_v1" if self.outcome_consumer_enabled else "deferred_maternal_qualification",
                "learned_operation": False}


@dataclass(frozen=True, slots=True)
class SeekNipplePreviewV1:
    """Sparse oral approach prediction from the selected feeding-detail source.

    The original scene detail and observed mouth anchors are immutable. The
    operation predicts a limited reduction of their separation assuming a
    stationary body/target and available lower competence. BodyMap independently
    tests whether its one-axis capability can realize that request. This record
    neither supplies an actuator endpoint nor predicts touch from visual position.
    Execution-sensitive comparison is a separate opt-in P16-2C-D consumer; its
    enablement label changes neither this original forecast nor motor permission.
    """

    pnm: ProjectedNavMapV1
    basis: FeedingDetailNavMapStateV1
    task_id: str
    region_id: str
    scene_target: NavPointV1
    predicted_mouth: NavPointV1
    horizon_ticks: int = 8
    outcome_consumer_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.pnm, ProjectedNavMapV1) or not isinstance(self.basis, FeedingDetailNavMapStateV1):
            raise TypeError("seeking prediction requires its typed PNM and feeding source")
        if not isinstance(self.outcome_consumer_enabled, bool):
            raise TypeError("seeking outcome-consumer switch must be Boolean")
        mouth = self.basis.mouth_position
        if mouth is None or not self.basis.oral_evidence_current or self.basis.applied_cycle != self.pnm.created_cycle:
            raise ValueError("seeking prediction requires this opportunity's paired current mouth/detail evidence")
        if self.pnm.primitive_id != "ip:seek_nipple":
            raise ValueError("seeking prediction must belong to the selected SeekNipple operation")
        if _bounded_identifier(self.task_id, field_name="task_id", maximum=100) != self.task_id:
            raise ValueError("seeking task identity cannot be normalized into another identity")
        if self.region_id != self.basis.seed.detail_region_id or self.scene_target != self.basis.detail_position:
            raise ValueError("seeking prediction cannot replace its originating detail anchor")
        if not isinstance(self.predicted_mouth, NavPointV1):
            raise TypeError("predicted mouth must be a scene point")
        if isinstance(self.horizon_ticks, bool) or not isinstance(self.horizon_ticks, int) or not 1 <= self.horizon_ticks <= 8:
            raise ValueError("seeking prediction horizon must be one to eight physical ticks")
        extent = math.hypot(self.predicted_mouth.x - mouth.x, self.predicted_mouth.y - mouth.y)
        if extent > min(0.15, self.horizon_ticks * 0.025) + 1e-12:
            raise ValueError("seeking prediction exceeds its declared bounded reference motion")
        if self.predicted_separation > math.hypot(self.scene_target.x - mouth.x, self.scene_target.y - mouth.y) + 1e-12:
            raise ValueError("seeking prediction cannot increase the requested mouth/detail separation")

    @property
    def predicted_separation(self) -> float:
        """Read expected scene geometry, not local target achievement or touch."""
        return math.hypot(self.scene_target.x - self.predicted_mouth.x, self.scene_target.y - self.predicted_mouth.y)

    def as_dict(self) -> dict[str, object]:
        """Export the original sparse claim without creating evidence or permission."""
        return {"pnm": self.pnm.as_dict(), "basis": self.basis.as_dict(), "task_id": self.task_id,
                "region_id": self.region_id, "scene_target": self.scene_target.as_dict(),
                "predicted_mouth": self.predicted_mouth.as_dict(), "predicted_separation_metres": self.predicted_separation,
                "horizon_ticks": self.horizon_ticks, "model": "seek_nipple_straight_relation_v1",
                "status": "conditional_not_observed", "body_and_detail_assumption": "stationary_during_contribution",
                "contact_prediction": "not_inferred_from_visual_geometry", "latch_prediction": "not_supplied",
                "task_outcome_consumer": "seek_nipple_correspondence_v1" if self.outcome_consumer_enabled else "deferred_seek_correspondence", "learned_operation": False}


@dataclass(frozen=True, slots=True)
class SucklePreviewV1:
    """Original sparse expectation for Suckle's initial latch contribution.

    The original detail and mouth positions remain anchors. Closure is expected
    to increase under declared competence; seal is conditional on the represented
    feeding surface actually being sealable. The model cannot inspect private
    surface properties. Actual BodyMap narrowing never rewrites this forecast.
    H has no original-Suckle-PNM comparator or milk prediction.
    """

    pnm: ProjectedNavMapV1
    basis: FeedingDetailNavMapStateV1
    task_id: str
    region_id: str
    scene_target: NavPointV1
    predicted_closure: float
    horizon_ticks: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.pnm, ProjectedNavMapV1) or not isinstance(self.basis, FeedingDetailNavMapStateV1):
            raise TypeError("Suckle prediction requires its typed PNM and feeding source")
        if (not self.basis.oral_evidence_current or self.basis.contact_correspondence_status != "compatible"
                or self.basis.applied_cycle != self.pnm.created_cycle or self.basis.mouth_position is None):
            raise ValueError("Suckle preview requires this opportunity's paired feeding contact")
        if self.pnm.primitive_id != "ip:suckle":
            raise ValueError("Suckle prediction must belong to the selected operation")
        if _bounded_identifier(self.task_id, field_name="task_id", maximum=100) != self.task_id:
            raise ValueError("Suckle task identity must be unchanged")
        if self.region_id != self.basis.seed.detail_region_id or self.scene_target != self.basis.detail_position:
            raise ValueError("Suckle preview cannot replace the original detail anchor")
        if isinstance(self.horizon_ticks, bool) or not isinstance(self.horizon_ticks, int) or not 1 <= self.horizon_ticks <= 8:
            raise ValueError("Suckle preview needs one to eight physical ticks")
        body = self.basis.oral_feedback
        if body is None or body.oral_seal is None or body.oral_seal.closure is None:
            raise ValueError("Suckle prediction requires known measured closure")
        expected = min(0.6, body.oral_seal.closure + min(0.6, 0.1 * self.horizon_ticks))
        if (isinstance(self.predicted_closure, bool) or not isinstance(self.predicted_closure, (int, float))
                or not math.isfinite(self.predicted_closure) or abs(self.predicted_closure - expected) > 1e-12
                or self.predicted_closure < body.oral_seal.closure):
            raise ValueError("Suckle prediction must preserve the declared bounded closure calculation")
        object.__setattr__(self, "predicted_closure", float(self.predicted_closure))

    def as_dict(self) -> dict[str, object]:
        """Export original conditional relations without manufacturing later evidence."""
        mouth = self.basis.mouth_position
        return {"pnm": self.pnm.as_dict(), "basis": self.basis.as_dict(), "task_id": self.task_id,
                "region_id": self.region_id, "scene_target": self.scene_target.as_dict(),
                "predicted_mouth": None if mouth is None else mouth.as_dict(), "predicted_closure": self.predicted_closure,
                "predicted_seal": self.predicted_closure >= 0.6 - 1e-12, "horizon_ticks": self.horizon_ticks,
                "model": "suckle_initial_closure_v1", "status": "conditional_not_observed",
                "surface_assumption": "represented_feeding_surface_sealable_not_privately_verified",
                "task_outcome_consumer": "deferred_suckle_correspondence", "milk_prediction": "not_supplied",
                "learned_operation": False}


@dataclass(frozen=True, slots=True)
class PendingPredictionTraceV1:
    """One bounded operation-linked expectation awaiting matching evidence."""

    trace_id: str
    pnm: ProjectedNavMapV1
    status: PredictionOutcomeStatusV1 = PredictionOutcomeStatusV1.PENDING
    matching_evidence: tuple[str, ...] = ()
    evaluated_cycle: int | None = None
    reason: str = "awaiting_matching_current_body_evidence"

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _bounded_identifier(self.trace_id, field_name="trace_id"))
        if not isinstance(self.pnm, ProjectedNavMapV1):
            raise TypeError("pnm must be a ProjectedNavMapV1")
        if not isinstance(self.status, PredictionOutcomeStatusV1):
            raise TypeError("status must be a PredictionOutcomeStatusV1")
        object.__setattr__(
            self,
            "matching_evidence",
            _bounded_unique_strings(
                self.matching_evidence,
                field_name="matching evidence",
                maximum_items=_MAX_EVIDENCE,
            ),
        )
        if self.evaluated_cycle is not None:
            evaluated = _positive_int(self.evaluated_cycle, field_name="evaluated_cycle")
            if evaluated <= self.pnm.created_cycle:
                raise ValueError("prediction outcome evidence must follow the originating application")
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    @property
    def is_terminal(self) -> bool:
        """Return whether this prediction no longer awaits evidence."""
        return self.status in {
            PredictionOutcomeStatusV1.SUCCESS,
            PredictionOutcomeStatusV1.FAILURE,
            PredictionOutcomeStatusV1.EXPIRED,
            PredictionOutcomeStatusV1.NOT_APPLIED,
            PredictionOutcomeStatusV1.CANCELLED,
            PredictionOutcomeStatusV1.SUPERSEDED,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe pending-trace snapshot."""
        return {
            "trace_id": self.trace_id,
            "pnm": self.pnm.as_dict(),
            "status": self.status.value,
            "matching_evidence": list(self.matching_evidence),
            "evaluated_cycle": self.evaluated_cycle,
            "reason": self.reason,
            "is_terminal": self.is_terminal,
            "action_authority": False,
        }


@dataclass(frozen=True, slots=True)
class PredictionOutcomeV1:
    """One explicit evaluation result linked to its originating PNM/application."""

    outcome_id: str
    pnm_id: str
    application_id: str
    primitive_id: str
    status: PredictionOutcomeStatusV1
    evaluated_cycle: int
    evidence_sampled_cycle: int | None
    matching_evidence: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("outcome_id", "pnm_id", "application_id", "primitive_id"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        if self.status in {PredictionOutcomeStatusV1.PENDING, PredictionOutcomeStatusV1.UNRESOLVED}:
            raise ValueError("PredictionOutcomeV1 records only terminal or explicit not-applied outcomes")
        _positive_int(self.evaluated_cycle, field_name="evaluated_cycle")
        if self.evidence_sampled_cycle is not None:
            _positive_int(self.evidence_sampled_cycle, field_name="evidence_sampled_cycle")
        object.__setattr__(
            self,
            "matching_evidence",
            _bounded_unique_strings(
                self.matching_evidence,
                field_name="matching evidence",
                maximum_items=_MAX_EVIDENCE,
            ),
        )
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe outcome snapshot."""
        return {
            "outcome_id": self.outcome_id,
            "pnm_id": self.pnm_id,
            "application_id": self.application_id,
            "primitive_id": self.primitive_id,
            "status": self.status.value,
            "evaluated_cycle": self.evaluated_cycle,
            "evidence_sampled_cycle": self.evidence_sampled_cycle,
            "matching_evidence": list(self.matching_evidence),
            "reason": self.reason,
        }


class Nca8PredictionRuntimeV1:
    """Own one current PNM, bounded pending traces, and outcome history."""

    def __init__(self, *, pending_capacity: int = _MAX_PENDING) -> None:
        if isinstance(pending_capacity, bool) or not isinstance(pending_capacity, int) or pending_capacity <= 0:
            raise ValueError("pending_capacity must be a positive integer")
        self._pending_capacity = pending_capacity
        self._current: PendingPredictionTraceV1 | None = None
        self._pending: list[PendingPredictionTraceV1] = []
        self._outcome_history: list[PredictionOutcomeV1] = []
        self._preview: SupportPreviewV1 | VisualTranslationPreviewV1 | MaternalApproachPreviewV1 | SeekNipplePreviewV1 | SucklePreviewV1 | None = None
        self._preview_history: list[SupportPreviewV1 | VisualTranslationPreviewV1 | MaternalApproachPreviewV1 | SeekNipplePreviewV1 | SucklePreviewV1] = []
        self._last_preview_cycle = 0

    @property
    def current_pnm(self) -> ProjectedNavMapV1 | None:
        """Return the one current executed claim or explicitly unexecuted preview."""
        if self._current is not None:
            return self._current.pnm
        return self._preview.pnm if self._preview is not None else None

    @property
    def current_trace(self) -> PendingPredictionTraceV1 | None:
        """Return the current application-linked pending prediction trace."""
        return self._current

    def pending_snapshot(self) -> tuple[PendingPredictionTraceV1, ...]:
        """Return all unresolved prediction traces in deterministic order."""
        traces = list(self._pending)
        if self._current is not None:
            traces.append(self._current)
        return tuple(sorted(traces, key=lambda item: (item.pnm.created_cycle, item.pnm.pnm_id)))

    def outcome_history(self) -> tuple[PredictionOutcomeV1, ...]:
        """Return bounded terminal outcome history in causal order."""
        return tuple(self._outcome_history)

    def create_current(
        self,
        application: PrimitiveApplicationV1,
        *,
        expiry_cycles: int = 2,
    ) -> ProjectedNavMapV1:
        """Create one PNM before dispatch and preserve any displaced expectation."""
        if not isinstance(application, PrimitiveApplicationV1):
            raise TypeError("application must be a PrimitiveApplicationV1")
        if self._preview is not None:
            raise ValueError("release the unexecuted preview before arming an executed prediction")
        expiry_window = _positive_int(expiry_cycles, field_name="expiry_cycles")
        if self._current is not None:
            if len(self._pending) >= self._pending_capacity:
                raise OverflowError("bounded pending-prediction capacity would be exceeded")
            self._pending.append(self._current)

        pnm = ProjectedNavMapV1(
            pnm_id=f"pnm:{application.application_id}",
            application_id=application.application_id,
            primitive_id=application.primitive_id,
            source_wnm_id=application.source_wnm_id,
            created_cycle=application.cycle_id,
            expected_relations=application.expected_relations,
            observation_condition=application.observation_condition,
            eligible_from_cycle=application.cycle_id + 1,
            expires_after_cycle=application.cycle_id + expiry_window,
        )
        self._current = PendingPredictionTraceV1(
            trace_id=f"pending:{pnm.pnm_id}",
            pnm=pnm,
        )
        return pnm

    def evaluate_ready(
        self,
        evidence: NavMapStateV1,
        *,
        cycle_id: int,
    ) -> tuple[PredictionOutcomeV1, ...]:
        """Evaluate event-matched later body evidence and retain unresolved traces."""
        if not isinstance(evidence, NavMapStateV1):
            raise TypeError("evidence must be a NavMapStateV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if evidence.applied_cycle != cycle:
            raise ValueError("prediction evaluation requires current-cycle applied evidence")

        current = self._current
        traces = list(self._pending)
        if current is not None:
            traces.append(current)
        self._pending = []
        self._current = None

        outcomes: list[PredictionOutcomeV1] = []
        retained: list[PendingPredictionTraceV1] = []
        for trace in sorted(traces, key=lambda item: (item.pnm.created_cycle, item.pnm.pnm_id)):
            evaluated, outcome = self._evaluate_one(trace, evidence=evidence, cycle_id=cycle)
            if outcome is not None:
                outcomes.append(outcome)
                self._append_outcome(outcome)
            elif evaluated.is_terminal:
                raise RuntimeError("terminal prediction trace did not produce an outcome")
            else:
                retained.append(evaluated)

        if retained:
            self._current = retained[-1]
            self._pending = retained[:-1]
        return tuple(outcomes)

    def _evaluate_one(
        self,
        trace: PendingPredictionTraceV1,
        *,
        evidence: NavMapStateV1,
        cycle_id: int,
    ) -> tuple[PendingPredictionTraceV1, PredictionOutcomeV1 | None]:
        """Evaluate one trace only when its event window and sample time match."""
        pnm = trace.pnm
        if cycle_id < pnm.eligible_from_cycle:
            return trace, None
        if evidence.sampled_event_cycle <= pnm.created_cycle:
            return trace, None

        evidence_relations = tuple(evidence.active_relation_labels)
        if evidence.posture is Nca8PostureStateV1.STANDING and evidence.support is Nca8SupportStateV1.STABLE:
            status = PredictionOutcomeStatusV1.SUCCESS
            reason = "later_current_body_evidence_matches_upright_stable_expectation"
        elif evidence.posture is Nca8PostureStateV1.FALLEN and evidence.support is Nca8SupportStateV1.INADEQUATE:
            status = PredictionOutcomeStatusV1.FAILURE
            reason = "later_current_body_evidence_contradicts_upright_stable_expectation"
        elif cycle_id > pnm.expires_after_cycle:
            status = PredictionOutcomeStatusV1.EXPIRED
            reason = "matching_current_body_evidence_not_resolved_before_expiry"
        else:
            updated = replace(
                trace,
                status=PredictionOutcomeStatusV1.UNRESOLVED,
                matching_evidence=evidence_relations,
                evaluated_cycle=cycle_id,
                reason="current_body_evidence_missing_or_ambiguous",
            )
            return updated, None

        updated = replace(
            trace,
            status=status,
            matching_evidence=evidence_relations,
            evaluated_cycle=cycle_id,
            reason=reason,
        )
        outcome = PredictionOutcomeV1(
            outcome_id=f"outcome:{pnm.pnm_id}:{cycle_id}",
            pnm_id=pnm.pnm_id,
            application_id=pnm.application_id,
            primitive_id=pnm.primitive_id,
            status=status,
            evaluated_cycle=cycle_id,
            evidence_sampled_cycle=evidence.sampled_event_cycle,
            matching_evidence=evidence_relations,
            reason=reason,
        )
        return updated, outcome

    def mark_not_applied(
        self,
        pnm_id: str,
        *,
        cycle_id: int,
        reason: str,
    ) -> PredictionOutcomeV1:
        """Close a just-created PNM when BodyMap cannot authorize its task action."""
        target = _bounded_identifier(pnm_id, field_name="pnm_id")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        trace = self._remove_trace(target)
        if trace is None:
            raise KeyError(f"unknown pending PNM: {target!r}")
        outcome = PredictionOutcomeV1(
            outcome_id=f"outcome:{target}:{cycle}:not_applied",
            pnm_id=target,
            application_id=trace.pnm.application_id,
            primitive_id=trace.pnm.primitive_id,
            status=PredictionOutcomeStatusV1.NOT_APPLIED,
            evaluated_cycle=cycle,
            evidence_sampled_cycle=None,
            matching_evidence=(),
            reason=_bounded_identifier(reason, field_name="reason"),
        )
        self._append_outcome(outcome)
        return outcome

    def _remove_trace(self, pnm_id: str) -> PendingPredictionTraceV1 | None:
        """Remove and return one trace from the current/pending bounded stores."""
        if self._current is not None and self._current.pnm.pnm_id == pnm_id:
            result = self._current
            self._current = None
            return result
        for index, trace in enumerate(self._pending):
            if trace.pnm.pnm_id == pnm_id:
                return self._pending.pop(index)
        return None

    def _append_outcome(self, outcome: PredictionOutcomeV1) -> None:
        """Append one terminal outcome to bounded causal history."""
        self._outcome_history.append(outcome)
        if len(self._outcome_history) > _MAX_OUTCOME_HISTORY:
            del self._outcome_history[:-_MAX_OUTCOME_HISTORY]


    @property
    def current_support_preview(self) -> SupportPreviewV1 | None:
        """Return the one current unexecuted prospective record, if any."""
        return self._preview if isinstance(self._preview, SupportPreviewV1) else None

    @property
    def current_visual_preview(self) -> VisualTranslationPreviewV1 | None:
        """Return the visual member of the same single prospective slot, if any."""
        return self._preview if isinstance(self._preview, VisualTranslationPreviewV1) else None

    def preview_history(self) -> tuple[SupportPreviewV1 | VisualTranslationPreviewV1 | MaternalApproachPreviewV1 | SeekNipplePreviewV1 | SucklePreviewV1, ...]:
        """Return at most eight immutable superseded previews, not pending outcomes."""
        return tuple(self._preview_history)

    def adopt_support_preview(self, preview: SupportPreviewV1 | None) -> None:
        """Display/retain one task preview without fabricating an executed claim.

        A null focal selection clears the current preview. Displaced forecasts
        retain their original meaning in an eight-record diagnostic history;
        trimming it changes no task budget, learned parameter or action permission.
        Mixing live executed obligations and this no-dispatch review is refused.
        """
        if preview is not None and not isinstance(preview, SupportPreviewV1):
            raise TypeError("preview must be SupportPreviewV1 or None")
        self._adopt_preview(preview)

    def adopt_visual_preview(self, preview: VisualTranslationPreviewV1) -> None:
        """Use the existing single slot for a selected supplied operation, not a new IP."""
        if not isinstance(preview, VisualTranslationPreviewV1):
            raise TypeError("expected a typed visual projection")
        self._adopt_preview(preview)

    @property
    def current_maternal_preview(self) -> MaternalApproachPreviewV1 | None:
        """Read the maternal member of the same single current prospective role."""
        return self._preview if isinstance(self._preview, MaternalApproachPreviewV1) else None

    def adopt_maternal_preview(self, preview: MaternalApproachPreviewV1) -> None:
        """Register the selected IP's expectation without making it an observed fact."""
        if not isinstance(preview, MaternalApproachPreviewV1):
            raise TypeError("expected an original maternal projection")
        self._adopt_preview(preview)

    @property
    def current_seeking_preview(self) -> SeekNipplePreviewV1 | None:
        """Read the current selected oral prediction, never a second active PNM."""
        return self._preview if isinstance(self._preview, SeekNipplePreviewV1) else None

    def adopt_seeking_preview(self, preview: SeekNipplePreviewV1) -> None:
        """Register an original seeking forecast without claiming execution or fulfilment."""
        if not isinstance(preview, SeekNipplePreviewV1):
            raise TypeError("seeking registration requires its typed original prediction")
        self._adopt_preview(preview)

    @property
    def current_suckle_preview(self) -> SucklePreviewV1 | None:
        """Read the Suckle member of the existing single current prospective role."""
        return self._preview if isinstance(self._preview, SucklePreviewV1) else None

    def adopt_suckle_preview(self, preview: SucklePreviewV1) -> None:
        """Register the original selected latch expectation, not observed fulfilment."""
        if not isinstance(preview, SucklePreviewV1):
            raise TypeError("Suckle registration requires its typed original prediction")
        self._adopt_preview(preview)

    def _adopt_preview(self, preview: SupportPreviewV1 | VisualTranslationPreviewV1 | MaternalApproachPreviewV1 | SeekNipplePreviewV1 | SucklePreviewV1 | None) -> None:
        """Replace one prospective role; retain bounded immutable earlier meanings."""
        if self._current is not None or self._pending:
            raise ValueError("cannot mix unexecuted previews with pending executed claims")
        if preview is not None and preview.pnm.created_cycle <= self._last_preview_cycle:
            raise ValueError("a new preview must follow the current preview")
        if self._preview is not None:
            self._preview_history.append(self._preview)
            del self._preview_history[:-8]
        self._preview = preview
        if preview is not None:
            self._last_preview_cycle = preview.pnm.created_cycle
