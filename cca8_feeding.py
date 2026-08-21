# -*- coding: utf-8 -*-
"""Phase 5 feeding close-up, WNM zoom round-trip, and map-native expectations.

Purpose
-------
Phase 5 is the first CCA8 slice in which zoom changes the operative Working
Navigation Map rather than merely changing a renderer or focus label.  The
module reuses the maintained Phase 4 SELF-maternal map as the coarse overview,
adds a maternal-body detail map and a nipple-mouth feeding close-up, and drives
an explicit round trip through :mod:`cca8_wnm_runtime`::

    SELF-maternal overview
        -> maternal-body detail
        -> nipple-mouth feeding close-up
        -> maternal-body detail
        -> SELF-maternal overview

Every transition carries cross-scale identity and frame correspondence.  The
prior operative map enters a small bounded ready set and loses operative
authority.  A rejected or ambiguous transition leaves the source WNM and ready
set unchanged.

Feeding evidence and live dynamics
----------------------------------
The environment adapter supplies a small sensor-like geometry packet.  This
module converts that packet into a transient evidence NavMap and derives
mouth-to-nipple distance/contact through the existing NavMap geometry operators.
Search, reachability, contact, latch, milk evidence, contact acquisition/loss,
duration, and micro-adjustment are compressed into one bounded live overlay.
The overlay, not a sequence of full NavMaps, carries ordinary per-cycle dynamics.
The maintained detail maps are revised only for material structural changes;
the first implementation therefore uses stable structural revisions and current
source-linked overlays.

Map-native expectations
-----------------------
When PolicyRuntime actually selects ``policy:seek_nipple`` or
``policy:suckle``, this module may arm one compact expected feeding relation.
The next observation closes it as ``success``, ``failure``, ``unknown``, or
``not_applied``.  This replaces the old detached nipple-state expectation for
those two primitives while leaving hunger as a legitimate compact drive.
Selection itself remains in the existing PolicyRuntime/controller path.

Authority and motor boundary
----------------------------
Operative WNM status grants the right to perform detailed map queries; it does
not convert inferred structure or retrieved content into observed truth.  The
module never mutates BodyMap, WorldGraph, drives, policy arbitration, or the
environment.  It does not calculate oral/head trajectories, forces, or timing.
Those remain lower-controller responsibilities; CCA8 consumes only task-level
progress, contact, completion, loss, and error evidence.
"""

from __future__ import annotations

# The complete Phase 5 vertical slice is intentionally kept in one focused
# module so source, transition, expectation, and authority boundaries remain
# inspectable during the first zoom implementation.
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional

from cca8_env import EnvObservation
from cca8_maternal_continuity import (
    MaternalContinuityShadowStateV1,
    MaternalIdentitySupportV1,
    MaternalLocalizationStatusV1,
    MaternalObservabilityV1,
    MaternalTrackStatusV1,
)
from cca8_maternal_geometry import MaternalGeometryShadowStateV1
from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapLinkV1,
    NavMapRefV1,
    NavMapV2,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavSourceClassV1,
    geometries_contact,
    minimum_distance_between,
)
from cca8_wnm_runtime import (
    WNMTransitionTypeV1,
    wnm_commit_transition_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
    wnm_refresh_map_v1,
    wnm_summary_v1,
)

__version__ = "0.2.0"

__all__ = [
    "FeedingReachabilityV1",
    "FeedingContactEventV1",
    "FeedingExpectationKindV1",
    "FeedingCrossScaleCorrespondenceV1",
    "FeedingRelationOverlayV1",
    "FeedingExpectedSuccessorV1",
    "FeedingPendingExpectationV1",
    "FeedingObservedOutcomeV1",
    "FeedingWnmStateV1",
    "feeding_reset_v1",
    "feeding_wnm_observation_step_v1",
    "feeding_selection_step_v1",
    "feeding_operative_readout_v1",
    "feeding_milk_evidence_v1",
    "feeding_latch_evidence_v1",
    "feeding_summary_v1",
    "render_feeding_lines_v1",
    "__version__",
]

_OVERVIEW_ROLE = "self_maternal_scene"
_BODY_ROLE = "maternal_body_detail"
_CLOSEUP_ROLE = "nipple_mouth_feeding_closeup"
_EVIDENCE_ROLE = "feeding_relation_evidence"
_BODY_MAP_ID = "goat_maternal_body_feeding_v2"
_CLOSEUP_MAP_ID = "goat_nipple_mouth_feeding_v2"
_EVIDENCE_MAP_ID = "goat_nipple_mouth_evidence_v2"
_MATERNAL_BODY_FRAME = "maternal_body_feeding_frame_v1"
_CLOSEUP_FRAME = "nipple_mouth_closeup_frame_v1"
_OVERVIEW_MATERNAL_ELEMENT = "maternal_individual"
_BODY_MATERNAL_ELEMENT = "maternal_body"
_BODY_NIPPLE_ELEMENT = "maternal_nipple_region"
_CLOSEUP_NIPPLE_ELEMENT = "nipple_target"
_CLOSEUP_MUZZLE_ELEMENT = "self_muzzle"
_EXPECTED_SOURCE_PREFIX = "behavioral_primitive:feeding:phase5"
_DEFAULT_HISTORY_LIMIT = 25
_DEFAULT_READY_CAPACITY = 3


class FeedingReachabilityV1(str, Enum):
    """Current source-linked mouth-to-nipple reachability."""

    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class FeedingContactEventV1(str, Enum):
    """Compressed change in feeding contact across supported observations."""

    NONE = "none"
    ACQUIRED = "acquired"
    MAINTAINED = "maintained"
    LOST = "lost"
    UNKNOWN = "unknown"


class FeedingExpectationKindV1(str, Enum):
    """Compact task-level relation expected after a feeding primitive."""

    LOCALIZE_OR_REACH_NIPPLE = "localize_or_reach_nipple"
    ACQUIRE_LATCH = "acquire_latch"
    MAINTAIN_CONTACT_AND_OBTAIN_MILK = "maintain_contact_and_obtain_milk"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float while rejecting bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _finite_non_negative_float(value: Any, *, field_name: str) -> float:
    """Return one finite non-negative float."""
    number = _finite_float(value, field_name=field_name)
    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _unit_interval(value: Any, *, field_name: str) -> float:
    """Return one finite value in the closed unit interval."""
    number = _finite_float(value, field_name=field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _optional_bool(value: Any) -> Optional[bool]:
    """Return an actual bool or ``None`` without truthiness coercion."""
    return value if isinstance(value, bool) else None


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return one immutable map reference."""
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _point_geometry(point: NavPointV1) -> NavGeometryV1:
    """Return one point geometry."""
    return NavGeometryV1(kind=NavGeometryKindV1.POINT, points=(point,))


def _activation(name: str, provenance: NavProvenanceV1) -> tuple[NavActivationV1, ...]:
    """Return one deterministic decoded activation."""
    return (NavActivationV1(name=name, strength=1.0, provenance=provenance),)


def _inferred_provenance(source_ref: str, *, quality: float = 0.80) -> NavProvenanceV1:
    """Return stable inferred provenance for learned cross-scale structure."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=source_ref,
        quality=quality,
    )


def _observed_provenance(source_ref: str, *, quality: float) -> NavProvenanceV1:
    """Return observed-adapter provenance for one current evidence map."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.OBSERVED,
        source_ref=source_ref,
        quality=quality,
    )


@dataclass(frozen=True, slots=True)
class FeedingCrossScaleCorrespondenceV1:
    """One explicit identity and frame correspondence between two map scales.

    The developer-readable element ids are addresses only.  ``identity_handle``
    carries the cross-map correspondence and is checked independently.  The
    translation/rotation/scale fields make the frame relation inspectable; they
    are deterministic engineering transforms rather than a neural claim.
    """

    source_map_ref: NavMapRefV1
    destination_map_ref: NavMapRefV1
    identity_handle: str
    source_element_id: str
    destination_element_id: str
    source_frame_id: str
    destination_frame_id: str
    relation_type: str
    translation_x: float
    translation_y: float
    rotation_degrees: float
    scale: float
    support: float
    ambiguous: bool
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("source_map_ref", "destination_map_ref"):
            if not isinstance(getattr(self, field_name), NavMapRefV1):
                raise TypeError(f"{field_name} must be NavMapRefV1")
        for field_name in (
            "identity_handle",
            "source_element_id",
            "destination_element_id",
            "source_frame_id",
            "destination_frame_id",
            "relation_type",
            "reason",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in ("translation_x", "translation_y", "rotation_degrees"):
            object.__setattr__(self, field_name, _finite_float(getattr(self, field_name), field_name=field_name))
        scale = _finite_float(self.scale, field_name="scale")
        if scale <= 0.0:
            raise ValueError("scale must be positive")
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "support", _unit_interval(self.support, field_name="support"))
        if not isinstance(self.ambiguous, bool):
            raise TypeError("ambiguous must be bool")

    @property
    def frame_method(self) -> str:
        """Return one compact inspectable frame-method name."""
        return (
            f"translate({self.translation_x:.3f},{self.translation_y:.3f})/"
            f"rotate({self.rotation_degrees:.3f})/scale({self.scale:.3f})"
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe cross-scale correspondence."""
        return {
            "schema": "feeding_cross_scale_correspondence_v1",
            "source_map_ref": self.source_map_ref.as_dict(),
            "destination_map_ref": self.destination_map_ref.as_dict(),
            "identity_handle": self.identity_handle,
            "source_element_id": self.source_element_id,
            "destination_element_id": self.destination_element_id,
            "source_frame_id": self.source_frame_id,
            "destination_frame_id": self.destination_frame_id,
            "relation_type": self.relation_type,
            "transform": {
                "translation_x": self.translation_x,
                "translation_y": self.translation_y,
                "rotation_degrees": self.rotation_degrees,
                "scale": self.scale,
                "method": self.frame_method,
            },
            "support": self.support,
            "ambiguous": self.ambiguous,
            "reason": self.reason,
            "element_names_supply_identity": False,
        }


@dataclass(frozen=True, slots=True)
class _FeedingEvidenceV1:
    """Decoded current feeding evidence before geometry derivation."""

    observation_no: int
    source_ref: str
    quality: float
    frame_id: str
    units: str
    maternal_identity_handle: str
    nipple_identity_handle: str
    muzzle_identity_handle: str
    observability: str
    stage: str
    muzzle_point: Optional[NavPointV1]
    nipple_point: Optional[NavPointV1]
    reach_distance: float
    contact_distance: float
    latch_evidence: Optional[bool]
    milk_evidence: Optional[bool]
    search_progress: Optional[int]
    suckle_progress: Optional[int]
    blackout_active: bool
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in (
            "source_ref",
            "frame_id",
            "units",
            "maternal_identity_handle",
            "nipple_identity_handle",
            "muzzle_identity_handle",
            "observability",
            "stage",
            "reason",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        object.__setattr__(self, "quality", _unit_interval(self.quality, field_name="quality"))
        for field_name in ("muzzle_point", "nipple_point"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        object.__setattr__(
            self,
            "reach_distance",
            _finite_non_negative_float(self.reach_distance, field_name="reach_distance"),
        )
        object.__setattr__(
            self,
            "contact_distance",
            _finite_non_negative_float(self.contact_distance, field_name="contact_distance"),
        )
        for field_name in ("latch_evidence", "milk_evidence"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        for field_name in ("search_progress", "suckle_progress"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name=field_name)
        if not isinstance(self.blackout_active, bool):
            raise TypeError("blackout_active must be bool")


@dataclass(frozen=True, slots=True)
class FeedingRelationOverlayV1:
    """One compact live feeding relation linked to current map evidence."""

    observation_no: int
    operative_map_ref: Optional[NavMapRefV1]
    operative_role: Optional[str]
    source_evidence_map_ref: Optional[NavMapRefV1]
    maternal_identity_handle: str
    nipple_identity_handle: str
    observability: str
    stage: str
    target_localized: Optional[bool]
    mouth_nipple_distance: Optional[float]
    reachability: FeedingReachabilityV1
    contact: Optional[bool]
    latch_evidence: Optional[bool]
    milk_evidence: Optional[bool]
    contact_event: FeedingContactEventV1
    contact_duration_observations: Optional[int]
    milk_duration_observations: Optional[int]
    search_progress: Optional[int]
    suckle_progress: Optional[int]
    micro_adjustment_required: Optional[bool]
    closeup_query_authorized: bool
    freshness: str
    support_status: str
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("operative_map_ref", "source_evidence_map_ref"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, NavMapRefV1):
                raise TypeError(f"{field_name} must be NavMapRefV1 or None")
        if self.operative_role is not None:
            _require_nonempty_text(self.operative_role, field_name="operative_role")
        for field_name in (
            "maternal_identity_handle",
            "nipple_identity_handle",
            "observability",
            "stage",
            "freshness",
            "support_status",
            "reason",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "target_localized",
            "contact",
            "latch_evidence",
            "milk_evidence",
            "micro_adjustment_required",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        if self.mouth_nipple_distance is not None:
            object.__setattr__(
                self,
                "mouth_nipple_distance",
                _finite_non_negative_float(self.mouth_nipple_distance, field_name="mouth_nipple_distance"),
            )
        if not isinstance(self.reachability, FeedingReachabilityV1):
            raise TypeError("reachability must be FeedingReachabilityV1")
        if not isinstance(self.contact_event, FeedingContactEventV1):
            raise TypeError("contact_event must be FeedingContactEventV1")
        for field_name in (
            "contact_duration_observations",
            "milk_duration_observations",
            "search_progress",
            "suckle_progress",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name=field_name)
        if not isinstance(self.closeup_query_authorized, bool):
            raise TypeError("closeup_query_authorized must be bool")
        if self.closeup_query_authorized and self.operative_role != _CLOSEUP_ROLE:
            raise ValueError("closeup query authority requires the feeding close-up to be operative")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe overlay with explicit motor/source boundaries."""
        return {
            "schema": "feeding_relation_overlay_v1",
            "phase": "5",
            "observation_no": self.observation_no,
            "operative_map_ref": self.operative_map_ref.as_dict() if self.operative_map_ref is not None else None,
            "operative_role": self.operative_role,
            "source_evidence_map_ref": (
                self.source_evidence_map_ref.as_dict() if self.source_evidence_map_ref is not None else None
            ),
            "maternal_identity_handle": self.maternal_identity_handle,
            "nipple_identity_handle": self.nipple_identity_handle,
            "observability": self.observability,
            "stage": self.stage,
            "target_localized": self.target_localized,
            "mouth_nipple_distance": self.mouth_nipple_distance,
            "reachability": self.reachability.value,
            "contact": self.contact,
            "latch_evidence": self.latch_evidence,
            "milk_evidence": self.milk_evidence,
            "contact_event": self.contact_event.value,
            "contact_duration_observations": self.contact_duration_observations,
            "milk_duration_observations": self.milk_duration_observations,
            "search_progress": self.search_progress,
            "suckle_progress": self.suckle_progress,
            "micro_adjustment_required": self.micro_adjustment_required,
            "closeup_query_authorized": self.closeup_query_authorized,
            "freshness": self.freshness,
            "support_status": self.support_status,
            "reason": self.reason,
            "stores_full_navmap_history": False,
            "lower_oral_head_timing_delegated": True,
            "lower_motor_trajectory_present": False,
        }


@dataclass(frozen=True, slots=True)
class FeedingExpectedSuccessorV1:
    """One compact expected feeding relation after an applied primitive."""

    transaction_no: int
    source_observation_no: int
    source_operative_map_ref: NavMapRefV1
    maternal_identity_handle: str
    nipple_identity_handle: str
    selected_policy: str
    expectation_kind: FeedingExpectationKindV1
    source_target_localized: Optional[bool]
    source_reachability: FeedingReachabilityV1
    source_contact: Optional[bool]
    source_latch_evidence: Optional[bool]
    source_milk_evidence: Optional[bool]
    source_search_progress: Optional[int]
    source_suckle_progress: Optional[int]
    provenance: NavProvenanceV1

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.source_observation_no, field_name="source_observation_no")
        if not isinstance(self.source_operative_map_ref, NavMapRefV1):
            raise TypeError("source_operative_map_ref must be NavMapRefV1")
        for field_name in ("maternal_identity_handle", "nipple_identity_handle", "selected_policy"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if self.selected_policy not in {"policy:seek_nipple", "policy:suckle"}:
            raise ValueError("feeding expectation requires seek_nipple or suckle")
        if not isinstance(self.expectation_kind, FeedingExpectationKindV1):
            raise TypeError("expectation_kind must be FeedingExpectationKindV1")
        if not isinstance(self.source_reachability, FeedingReachabilityV1):
            raise TypeError("source_reachability must be FeedingReachabilityV1")
        for field_name in (
            "source_target_localized",
            "source_contact",
            "source_latch_evidence",
            "source_milk_evidence",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        for field_name in ("source_search_progress", "source_suckle_progress"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name=field_name)
        if not isinstance(self.provenance, NavProvenanceV1):
            raise TypeError("provenance must be NavProvenanceV1")
        if self.provenance.source_class is not NavSourceClassV1.EXPECTED:
            raise ValueError("feeding expected successor requires EXPECTED provenance")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe compact expectation."""
        return {
            "schema": "feeding_expected_successor_v1",
            "phase": "5",
            "source_class": "expected",
            "current_truth": False,
            "creates_navmap_revision": False,
            "transaction_no": self.transaction_no,
            "source_observation_no": self.source_observation_no,
            "source_operative_map_ref": self.source_operative_map_ref.as_dict(),
            "maternal_identity_handle": self.maternal_identity_handle,
            "nipple_identity_handle": self.nipple_identity_handle,
            "selected_policy": self.selected_policy,
            "expectation_kind": self.expectation_kind.value,
            "source_target_localized": self.source_target_localized,
            "source_reachability": self.source_reachability.value,
            "source_contact": self.source_contact,
            "source_latch_evidence": self.source_latch_evidence,
            "source_milk_evidence": self.source_milk_evidence,
            "source_search_progress": self.source_search_progress,
            "source_suckle_progress": self.source_suckle_progress,
            "provenance": self.provenance.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class FeedingPendingExpectationV1:
    """One feeding expectation armed only after actual policy selection."""

    transaction_no: int
    expected_successor: FeedingExpectedSuccessorV1
    selected_policy: str
    selected_controller_step: int

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor, FeedingExpectedSuccessorV1):
            raise TypeError("expected_successor must be FeedingExpectedSuccessorV1")
        if self.selected_policy != self.expected_successor.selected_policy:
            raise ValueError("pending selected_policy must match expected successor")
        _require_non_negative_int(self.selected_controller_step, field_name="selected_controller_step")


@dataclass(frozen=True, slots=True)
class FeedingObservedOutcomeV1:
    """Observed current feeding relation compared with one compact expectation."""

    transaction_no: int
    expected_successor: FeedingExpectedSuccessorV1
    action_applied: Optional[str]
    outcome: str
    evidence_map_ref: Optional[NavMapRefV1]
    observed_target_localized: Optional[bool]
    observed_reachability: FeedingReachabilityV1
    observed_contact: Optional[bool]
    observed_latch_evidence: Optional[bool]
    observed_milk_evidence: Optional[bool]
    observed_search_progress: Optional[int]
    observed_suckle_progress: Optional[int]
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor, FeedingExpectedSuccessorV1):
            raise TypeError("expected_successor must be FeedingExpectedSuccessorV1")
        if self.action_applied is not None and not isinstance(self.action_applied, str):
            raise TypeError("action_applied must be str or None")
        if self.outcome not in {"success", "failure", "unknown", "not_applied"}:
            raise ValueError("outcome must be success, failure, unknown, or not_applied")
        if self.evidence_map_ref is not None and not isinstance(self.evidence_map_ref, NavMapRefV1):
            raise TypeError("evidence_map_ref must be NavMapRefV1 or None")
        if not isinstance(self.observed_reachability, FeedingReachabilityV1):
            raise TypeError("observed_reachability must be FeedingReachabilityV1")
        for field_name in (
            "observed_target_localized",
            "observed_contact",
            "observed_latch_evidence",
            "observed_milk_evidence",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        for field_name in ("observed_search_progress", "observed_suckle_progress"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name=field_name)
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe expected-versus-observed outcome."""
        return {
            "schema": "feeding_observed_outcome_v1",
            "phase": "5",
            "authority": "map_native_expectation_observation",
            "policy_selection_mutation_allowed": False,
            "motor_command_is_outcome": False,
            "transaction_no": self.transaction_no,
            "expected_successor": self.expected_successor.as_dict(),
            "action_applied": self.action_applied,
            "outcome": self.outcome,
            "evidence_map_ref": self.evidence_map_ref.as_dict() if self.evidence_map_ref is not None else None,
            "observed_target_localized": self.observed_target_localized,
            "observed_reachability": self.observed_reachability.value,
            "observed_contact": self.observed_contact,
            "observed_latch_evidence": self.observed_latch_evidence,
            "observed_milk_evidence": self.observed_milk_evidence,
            "observed_search_progress": self.observed_search_progress,
            "observed_suckle_progress": self.observed_suckle_progress,
            "reason": self.reason,
            "creates_navmap_revision": False,
        }


@dataclass(frozen=True, slots=True)
class FeedingWnmStateV1:
    """Current Phase 5 map family, correspondence, and live overlay."""

    observation_no: int
    overview_map_ref: NavMapRefV1
    maternal_body_map_ref: NavMapRefV1
    feeding_closeup_map_ref: NavMapRefV1
    evidence_map_ref: Optional[NavMapRefV1]
    maternal_correspondence: FeedingCrossScaleCorrespondenceV1
    nipple_correspondence: FeedingCrossScaleCorrespondenceV1
    overlay: FeedingRelationOverlayV1
    transition_attempted: bool

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("overview_map_ref", "maternal_body_map_ref", "feeding_closeup_map_ref"):
            if not isinstance(getattr(self, field_name), NavMapRefV1):
                raise TypeError(f"{field_name} must be NavMapRefV1")
        if self.evidence_map_ref is not None and not isinstance(self.evidence_map_ref, NavMapRefV1):
            raise TypeError("evidence_map_ref must be NavMapRefV1 or None")
        if not isinstance(self.maternal_correspondence, FeedingCrossScaleCorrespondenceV1):
            raise TypeError("maternal_correspondence must be FeedingCrossScaleCorrespondenceV1")
        if not isinstance(self.nipple_correspondence, FeedingCrossScaleCorrespondenceV1):
            raise TypeError("nipple_correspondence must be FeedingCrossScaleCorrespondenceV1")
        if not isinstance(self.overlay, FeedingRelationOverlayV1):
            raise TypeError("overlay must be FeedingRelationOverlayV1")
        if not isinstance(self.transition_attempted, bool):
            raise TypeError("transition_attempted must be bool")

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe Phase 5 state without full map payloads."""
        return {
            "schema": "feeding_wnm_state_v1",
            "phase": "5",
            "observation_no": self.observation_no,
            "overview_map_ref": self.overview_map_ref.as_dict(),
            "maternal_body_map_ref": self.maternal_body_map_ref.as_dict(),
            "feeding_closeup_map_ref": self.feeding_closeup_map_ref.as_dict(),
            "evidence_map_ref": self.evidence_map_ref.as_dict() if self.evidence_map_ref is not None else None,
            "maternal_correspondence": self.maternal_correspondence.as_dict(),
            "nipple_correspondence": self.nipple_correspondence.as_dict(),
            "overlay": self.overlay.as_dict(),
            "transition_attempted": self.transition_attempted,
            "contains_full_navmap": False,
        }


def _history_limit(ctx: Any, field_name: str) -> int:
    """Return one configured positive history limit."""
    try:
        value = int(getattr(ctx, field_name, _DEFAULT_HISTORY_LIMIT) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_history(ctx: Any, *, field_name: str, limit_field_name: str, row: dict[str, Any]) -> None:
    """Append one defensive compact row to a bounded history."""
    raw = getattr(ctx, field_name, [])
    clean = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    clean.append(dict(row))
    setattr(ctx, field_name, clean[-_history_limit(ctx, limit_field_name):])


def _next_observation_no(ctx: Any) -> int:
    """Advance and return the deterministic feeding-observation counter."""
    try:
        current = int(getattr(ctx, "feeding_observation_no_v1", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    value = max(0, current) + 1
    ctx.feeding_observation_no_v1 = value
    return value


def _next_transaction_no(ctx: Any) -> int:
    """Advance and return the deterministic feeding-expectation counter."""
    try:
        current = int(getattr(ctx, "feeding_expectation_transaction_no_v1", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    value = max(0, current) + 1
    ctx.feeding_expectation_transaction_no_v1 = value
    return value


def _controller_step(ctx: Any) -> int:
    """Return a defensive non-negative controller-step value."""
    try:
        return max(0, int(getattr(ctx, "controller_steps", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _point_from_mapping(value: Any) -> Optional[NavPointV1]:
    """Decode one finite point mapping or return ``None``."""
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    if isinstance(y, bool) or not isinstance(y, (int, float)):
        return None
    try:
        return NavPointV1(float(x), float(y))
    except (TypeError, ValueError):
        return None


def _optional_non_negative_int(value: Any) -> Optional[int]:
    """Return one non-negative integer or ``None``."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _decode_evidence(ctx: Any, env_obs: EnvObservation, observation_no: int) -> _FeedingEvidenceV1:
    """Decode current masked observation support into one feeding evidence row."""
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}
    raw = meta.get("feeding_geometry_v1")
    raw = raw if isinstance(raw, dict) else {}
    predicates_raw = getattr(env_obs, "predicates", None)
    predicates = {str(item) for item in predicates_raw if isinstance(item, str)} if isinstance(predicates_raw, list) else set()

    continuity = getattr(ctx, "navmap_maternal_continuity_state", None)
    maternal_identity = raw.get("maternal_identity_handle")
    if isinstance(continuity, MaternalContinuityShadowStateV1):
        maternal_identity = continuity.tracked_identity_handle
    if not isinstance(maternal_identity, str) or not maternal_identity.strip():
        maternal_identity = "maternal_identity_unavailable"

    nipple_identity = raw.get("nipple_identity_handle")
    if not isinstance(nipple_identity, str) or not nipple_identity.strip():
        nipple_identity = f"{maternal_identity}:part:nipple"
    muzzle_identity = raw.get("self_muzzle_identity_handle")
    if not isinstance(muzzle_identity, str) or not muzzle_identity.strip():
        muzzle_identity = "self:part:muzzle"

    observability_raw = raw.get("observability")
    observability = observability_raw if isinstance(observability_raw, str) and observability_raw else "unavailable"
    stage_raw = meta.get("scenario_stage")
    stage = stage_raw if isinstance(stage_raw, str) and stage_raw else "unknown"
    blackout_active = bool(meta.get("newborn_obs_blackout")) or observability == "blackout"

    # The geometry packet is built before the generic observation mask.  Target,
    # latch, and milk support are therefore accepted only when the corresponding
    # masked predicate remains present on the packet crossing into cognition.
    target_predicate_present = bool({"nipple:found", "nipple:latched"} & predicates)
    muzzle_point = _point_from_mapping(raw.get("muzzle_point"))
    nipple_point = _point_from_mapping(raw.get("nipple_point")) if target_predicate_present else None
    if blackout_active:
        muzzle_point = None
        nipple_point = None
    elif observability == "target_observed" and not target_predicate_present:
        observability = "masked_target_unavailable"

    latch_evidence = None
    if nipple_point is not None:
        latch_evidence = "nipple:latched" in predicates and bool(raw.get("latch_evidence"))
    milk_evidence = None
    if nipple_point is not None:
        milk_evidence = "milk:drinking" in predicates and bool(raw.get("milk_evidence"))

    quality_raw = raw.get("quality", 0.0)
    try:
        quality = _unit_interval(float(quality_raw), field_name="quality")
    except (TypeError, ValueError):
        quality = 0.0
    source_ref = raw.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        source_ref = f"adapter:feeding_geometry:observation:{observation_no}"
    frame_id = raw.get("frame_id")
    if not isinstance(frame_id, str) or not frame_id.strip():
        frame_id = _MATERNAL_BODY_FRAME
    units = raw.get("units")
    if not isinstance(units, str) or not units.strip():
        units = "m"

    try:
        reach_distance = _finite_non_negative_float(raw.get("reach_distance", 0.20), field_name="reach_distance")
    except (TypeError, ValueError):
        reach_distance = 0.20
    try:
        contact_distance = _finite_non_negative_float(
            raw.get("contact_distance", 0.03),
            field_name="contact_distance",
        )
    except (TypeError, ValueError):
        contact_distance = 0.03

    search_progress = _optional_non_negative_int(raw.get("search_progress"))
    suckle_progress = _optional_non_negative_int(raw.get("suckle_progress"))
    reason = (
        "current_masked_feeding_geometry_supported"
        if muzzle_point is not None
        else f"feeding_geometry_{observability}"
    )
    return _FeedingEvidenceV1(
        observation_no=observation_no,
        source_ref=source_ref,
        quality=quality,
        frame_id=frame_id,
        units=units,
        maternal_identity_handle=maternal_identity,
        nipple_identity_handle=nipple_identity,
        muzzle_identity_handle=muzzle_identity,
        observability=observability,
        stage=stage,
        muzzle_point=muzzle_point,
        nipple_point=nipple_point,
        reach_distance=reach_distance,
        contact_distance=contact_distance,
        latch_evidence=latch_evidence,
        milk_evidence=milk_evidence,
        search_progress=search_progress,
        suckle_progress=suckle_progress,
        blackout_active=blackout_active,
        reason=reason,
    )


def _closeup_structural_map() -> NavMapV2:
    """Return the stable task-level nipple-mouth close-up map."""
    provenance = _inferred_provenance("runtime:phase5_feeding_closeup_structure_v1", quality=0.80)
    frame = NavFrameV1(
        frame_id=_CLOSEUP_FRAME,
        x_axis="mouth_to_nipple_axis",
        y_axis="feeding_lateral_axis",
        units="m",
        min_x=-1.0,
        max_x=1.0,
        min_y=-1.0,
        max_y=1.0,
    )
    elements = (
        NavElementV1(
            element_id=_CLOSEUP_MUZZLE_ELEMENT,
            role="self_muzzle_anchor",
            geometry=_point_geometry(NavPointV1(-0.20, 0.0)),
            activations=_activation("feeding_effector", provenance),
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id=_CLOSEUP_NIPPLE_ELEMENT,
            role="maternal_nipple_target",
            geometry=_point_geometry(NavPointV1(0.0, 0.0)),
            activations=_activation("feeding_target", provenance),
            parent_element_id=None,
            provenance=provenance,
        ),
    )
    relations = (
        NavRelationV1("feeding_target_for", _CLOSEUP_NIPPLE_ELEMENT, _CLOSEUP_MUZZLE_ELEMENT, provenance),
    )
    return NavMapV2(
        map_id=_CLOSEUP_MAP_ID,
        revision=1,
        role=_CLOSEUP_ROLE,
        frame=frame,
        provenance=provenance,
        elements=elements,
        relations=relations,
    )


def _maternal_body_structural_map(closeup_ref: NavMapRefV1) -> NavMapV2:
    """Return the stable maternal-body detail map linked to the feeding close-up."""
    provenance = _inferred_provenance("runtime:phase5_maternal_body_structure_v1", quality=0.80)
    frame = NavFrameV1(
        frame_id=_MATERNAL_BODY_FRAME,
        x_axis="maternal_longitudinal_axis",
        y_axis="maternal_vertical_axis",
        units="m",
        min_x=-2.0,
        max_x=2.0,
        min_y=-1.5,
        max_y=1.5,
    )
    elements = (
        NavElementV1(
            element_id=_BODY_MATERNAL_ELEMENT,
            role="maternal_body",
            geometry=_point_geometry(NavPointV1(0.0, 0.0)),
            activations=_activation("maternal_individual", provenance),
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id="udder_region",
            role="feeding_region",
            geometry=_point_geometry(NavPointV1(0.0, -0.35)),
            activations=_activation("feeding_region", provenance),
            parent_element_id=_BODY_MATERNAL_ELEMENT,
            provenance=provenance,
        ),
        NavElementV1(
            element_id=_BODY_NIPPLE_ELEMENT,
            role="maternal_nipple_region",
            geometry=_point_geometry(NavPointV1(0.0, -0.35)),
            activations=_activation("feeding_target_region", provenance),
            parent_element_id="udder_region",
            provenance=provenance,
        ),
    )
    relations = (
        NavRelationV1("part_of", "udder_region", _BODY_MATERNAL_ELEMENT, provenance),
        NavRelationV1("part_of", _BODY_NIPPLE_ELEMENT, "udder_region", provenance),
    )
    links = (
        NavMapLinkV1(
            link_type="feeding_closeup",
            target_ref=closeup_ref,
            source_element_id=_BODY_NIPPLE_ELEMENT,
            provenance=provenance,
        ),
    )
    return NavMapV2(
        map_id=_BODY_MAP_ID,
        revision=1,
        role=_BODY_ROLE,
        frame=frame,
        provenance=provenance,
        elements=elements,
        relations=relations,
        links=links,
    )


def _feeding_evidence_map(evidence: _FeedingEvidenceV1) -> Optional[NavMapV2]:
    """Build one transient current evidence map without retaining a map movie."""
    if evidence.muzzle_point is None:
        return None
    provenance = _observed_provenance(
        f"{evidence.source_ref}:observation:{evidence.observation_no}",
        quality=evidence.quality,
    )
    frame = NavFrameV1(
        frame_id=evidence.frame_id,
        x_axis="maternal_longitudinal_axis",
        y_axis="maternal_vertical_axis",
        units=evidence.units,
        min_x=-2.0,
        max_x=2.0,
        min_y=-1.5,
        max_y=1.5,
    )
    elements = [
        NavElementV1(
            element_id=_CLOSEUP_MUZZLE_ELEMENT,
            role="observed_self_muzzle",
            geometry=_point_geometry(evidence.muzzle_point),
            activations=_activation("observed_feeding_effector", provenance),
            parent_element_id=None,
            provenance=provenance,
        )
    ]
    if evidence.nipple_point is not None:
        elements.append(
            NavElementV1(
                element_id=_CLOSEUP_NIPPLE_ELEMENT,
                role="observed_maternal_nipple",
                geometry=_point_geometry(evidence.nipple_point),
                activations=_activation("observed_feeding_target", provenance),
                parent_element_id=None,
                provenance=provenance,
            )
        )
    return NavMapV2(
        map_id=_EVIDENCE_MAP_ID,
        revision=evidence.observation_no,
        role=_EVIDENCE_ROLE,
        frame=frame,
        provenance=provenance,
        elements=tuple(elements),
    )


def _continuity_support(ctx: Any, maternal_identity_handle: str) -> tuple[float, bool, str]:
    """Return support/ambiguity for current maternal cross-scale identity."""
    state = getattr(ctx, "navmap_maternal_continuity_state", None)
    if not isinstance(state, MaternalContinuityShadowStateV1):
        return 0.0, True, "maternal_continuity_unavailable"
    if state.tracked_identity_handle != maternal_identity_handle:
        return 0.0, True, "maternal_identity_handle_mismatch"
    if state.identity_support is MaternalIdentitySupportV1.AMBIGUOUS:
        return 0.0, True, "maternal_identity_ambiguous"
    if state.identity_support is MaternalIdentitySupportV1.MISMATCH:
        return 0.0, True, "maternal_identity_mismatch"
    exact = bool(
        state.identity_support is MaternalIdentitySupportV1.SUPPORTED
        and state.role_retained
        and state.observability is MaternalObservabilityV1.OBSERVED
        and state.localization_status is MaternalLocalizationStatusV1.CURRENT_EXACT
        and state.track_status is MaternalTrackStatusV1.ACTIVE
    )
    if exact:
        return 1.0, False, "current_exact_maternal_identity_correspondence"
    if state.role_retained and state.identity_support is MaternalIdentitySupportV1.RETAINED:
        return 0.50, False, "retained_maternal_identity_without_exact_localization"
    return 0.0, True, f"maternal_identity_{state.identity_support.value}"


def _correspondences(
    ctx: Any,
    overview: NavMapV2,
    body: NavMapV2,
    closeup: NavMapV2,
    evidence: _FeedingEvidenceV1,
) -> tuple[FeedingCrossScaleCorrespondenceV1, FeedingCrossScaleCorrespondenceV1]:
    """Build current overview/body and body/close-up correspondence records."""
    support, ambiguous, reason = _continuity_support(ctx, evidence.maternal_identity_handle)
    maternal = FeedingCrossScaleCorrespondenceV1(
        source_map_ref=_map_ref(overview),
        destination_map_ref=_map_ref(body),
        identity_handle=evidence.maternal_identity_handle,
        source_element_id=_OVERVIEW_MATERNAL_ELEMENT,
        destination_element_id=_BODY_MATERNAL_ELEMENT,
        source_frame_id=overview.frame.frame_id,
        destination_frame_id=body.frame.frame_id,
        relation_type="whole_to_maternal_body_detail",
        translation_x=0.0,
        translation_y=0.0,
        rotation_degrees=0.0,
        scale=1.0,
        support=support,
        ambiguous=ambiguous,
        reason=reason,
    )
    nipple_support = support if not ambiguous else 0.0
    nipple = FeedingCrossScaleCorrespondenceV1(
        source_map_ref=_map_ref(body),
        destination_map_ref=_map_ref(closeup),
        identity_handle=evidence.nipple_identity_handle,
        source_element_id=_BODY_NIPPLE_ELEMENT,
        destination_element_id=_CLOSEUP_NIPPLE_ELEMENT,
        source_frame_id=body.frame.frame_id,
        destination_frame_id=closeup.frame.frame_id,
        relation_type="part_to_nipple_mouth_closeup",
        translation_x=0.0,
        translation_y=-0.35,
        rotation_degrees=0.0,
        scale=1.0,
        support=nipple_support,
        ambiguous=ambiguous,
        reason=("nipple_part_correspondence_from_supported_maternal_identity" if not ambiguous else reason),
    )
    return maternal, nipple


def _operative_role(ctx: Any) -> tuple[Optional[NavMapRefV1], Optional[str]]:
    """Return the exact operative map reference and role."""
    operative = wnm_operative_map_v1(ctx)
    if operative is None:
        return None, None
    return _map_ref(operative), operative.role


def _derive_overlay(
    ctx: Any,
    evidence: _FeedingEvidenceV1,
    evidence_map: Optional[NavMapV2],
) -> FeedingRelationOverlayV1:
    """Derive one compact live relation from current evidence and prior overlay."""
    distance: Optional[float] = None
    target_localized: Optional[bool]
    contact: Optional[bool] = None
    reachability = FeedingReachabilityV1.UNKNOWN

    if evidence.muzzle_point is None:
        target_localized = None
    elif evidence.nipple_point is None:
        target_localized = False
    else:
        target_localized = True
        if evidence_map is None:
            raise RuntimeError("localized feeding evidence requires an evidence map")
        distance_result = minimum_distance_between(evidence_map, _CLOSEUP_MUZZLE_ELEMENT, _CLOSEUP_NIPPLE_ELEMENT)
        contact_result = geometries_contact(
            evidence_map,
            _CLOSEUP_MUZZLE_ELEMENT,
            _CLOSEUP_NIPPLE_ELEMENT,
            tolerance=evidence.contact_distance,
        )
        distance = distance_result.value
        contact = contact_result.contact
        reachability = (
            FeedingReachabilityV1.REACHABLE
            if distance <= evidence.reach_distance
            else FeedingReachabilityV1.UNREACHABLE
        )

    previous_raw = getattr(ctx, "feeding_overlay_v1", None)
    compatible_previous: Optional[FeedingRelationOverlayV1] = None
    if (
        isinstance(previous_raw, FeedingRelationOverlayV1)
        and previous_raw.maternal_identity_handle == evidence.maternal_identity_handle
        and previous_raw.nipple_identity_handle == evidence.nipple_identity_handle
    ):
        compatible_previous = previous_raw

    if contact is None:
        contact_event = FeedingContactEventV1.UNKNOWN
        contact_duration = None
    elif contact:
        prior_contact = compatible_previous.contact if compatible_previous is not None else None
        contact_event = FeedingContactEventV1.MAINTAINED if prior_contact is True else FeedingContactEventV1.ACQUIRED
        prior_duration = (
            compatible_previous.contact_duration_observations
            if compatible_previous is not None
            else None
        )
        contact_duration = int(prior_duration or 0) + 1 if prior_contact is True else 1
    else:
        prior_contact = compatible_previous.contact if compatible_previous is not None else None
        contact_event = FeedingContactEventV1.LOST if prior_contact is True else FeedingContactEventV1.NONE
        contact_duration = 0

    milk = evidence.milk_evidence
    if milk is None:
        milk_duration = None
    elif milk:
        prior_milk = compatible_previous.milk_evidence if compatible_previous is not None else None
        prior_duration = (
            compatible_previous.milk_duration_observations
            if compatible_previous is not None
            else None
        )
        milk_duration = int(prior_duration or 0) + 1 if prior_milk is True else 1
    else:
        milk_duration = 0
    micro_adjustment: Optional[bool]
    if target_localized is None:
        micro_adjustment = None
    else:
        micro_adjustment = bool(reachability is FeedingReachabilityV1.REACHABLE and contact is False)

    operative_ref, operative_role = _operative_role(ctx)
    closeup_authorized = operative_role == _CLOSEUP_ROLE
    if evidence.blackout_active or evidence.muzzle_point is None:
        freshness = "missing"
        support_status = "unsupported_current_evidence"
    elif target_localized is False:
        freshness = "fresh"
        support_status = "search_required"
    else:
        freshness = "fresh"
        support_status = "current_geometry_supported"

    reason = evidence.reason
    if closeup_authorized:
        reason += ":feeding_closeup_is_operative"
    elif operative_role is not None:
        reason += f":detail_query_not_authorized_from_{operative_role}"

    return FeedingRelationOverlayV1(
        observation_no=evidence.observation_no,
        operative_map_ref=operative_ref,
        operative_role=operative_role,
        source_evidence_map_ref=_map_ref(evidence_map) if evidence_map is not None else None,
        maternal_identity_handle=evidence.maternal_identity_handle,
        nipple_identity_handle=evidence.nipple_identity_handle,
        observability=evidence.observability,
        stage=evidence.stage,
        target_localized=target_localized,
        mouth_nipple_distance=distance,
        reachability=reachability,
        contact=contact,
        latch_evidence=evidence.latch_evidence,
        milk_evidence=milk,
        contact_event=contact_event,
        contact_duration_observations=contact_duration,
        milk_duration_observations=milk_duration,
        search_progress=evidence.search_progress,
        suckle_progress=evidence.suckle_progress,
        micro_adjustment_required=micro_adjustment,
        closeup_query_authorized=closeup_authorized,
        freshness=freshness,
        support_status=support_status,
        reason=reason,
    )


def _transition_support(correspondence: FeedingCrossScaleCorrespondenceV1) -> float:
    """Return zero for ambiguous correspondence and support otherwise."""
    return 0.0 if correspondence.ambiguous else correspondence.support


def _commit_feeding_transition(
    ctx: Any,
    destination: NavMapV2,
    *,
    transition_type: WNMTransitionTypeV1,
    observation_no: int,
    reason: str,
    correspondence: FeedingCrossScaleCorrespondenceV1,
    reverse: bool = False,
) -> dict[str, Any]:
    """Commit one feeding transition through the generic atomic WNM runtime."""
    source_ref = correspondence.destination_map_ref if reverse else correspondence.source_map_ref
    return wnm_commit_transition_v1(
        ctx,
        destination,
        transition_type=transition_type,
        observation_no=observation_no,
        reason=reason,
        identity_handle=correspondence.identity_handle,
        correspondence_basis=(
            f"{correspondence.relation_type}:{correspondence.frame_method}:"
            f"source_element={correspondence.source_element_id}:"
            f"destination_element={correspondence.destination_element_id}"
        ),
        support=_transition_support(correspondence),
        correspondence_ambiguous=correspondence.ambiguous,
        expected_source_ref=source_ref,
    )


def _initialize_or_transition(
    ctx: Any,
    *,
    overview: NavMapV2,
    body: NavMapV2,
    closeup: NavMapV2,
    maternal_correspondence: FeedingCrossScaleCorrespondenceV1,
    nipple_correspondence: FeedingCrossScaleCorrespondenceV1,
    overlay: FeedingRelationOverlayV1,
    evidence: _FeedingEvidenceV1,
    applied_policy: Optional[str],
) -> bool:
    """Initialize or attempt at most one overview/detail/return transition."""
    operative = wnm_operative_map_v1(ctx)
    if operative is None:
        wnm_commit_transition_v1(
            ctx,
            overview,
            transition_type=WNMTransitionTypeV1.INITIALIZE,
            observation_no=evidence.observation_no,
            reason="phase5_initialize_self_maternal_overview",
            identity_handle=evidence.maternal_identity_handle,
            correspondence_basis="initial_current_phase4a_self_maternal_map",
            support=1.0,
            expected_source_ref=None,
        )
        return True

    # Refresh the current revision of a known overview family without turning an
    # ordinary evidence update into a zoom transition.
    wnm_refresh_map_v1(
        ctx,
        overview,
        observation_no=evidence.observation_no,
        reason="phase5_refresh_current_self_maternal_overview_revision",
    )
    operative = wnm_operative_map_v1(ctx)
    if operative is None:
        return False

    # Phase 6 terrain navigation runs earlier in the observation pipeline. When
    # an active route task owns the one operative WNM, feeding may continue to
    # maintain evidence and close pending outcomes but must not perform a second
    # substrate transition in the same cycle or displace the route sheet.
    if bool(getattr(ctx, "terrain_route_claims_wnm_v1", False)):
        return False

    feeding_task_active = evidence.stage in {"first_stand", "first_latch"}

    if operative.map_id == overview.map_id and feeding_task_active:
        _commit_feeding_transition(
            ctx,
            body,
            transition_type=WNMTransitionTypeV1.ZOOM_IN,
            observation_no=evidence.observation_no,
            reason="feeding_task_requires_maternal_body_detail",
            correspondence=maternal_correspondence,
        )
        return True

    if operative.map_id == body.map_id and evidence.stage != "rest":
        # Search is a legitimate reason to enter the close-up even before the
        # target is localized; the nipple correspondence must still be unambiguous.
        closeup_needed = bool(
            feeding_task_active
            or applied_policy in {"policy:seek_nipple", "policy:suckle"}
            or overlay.target_localized is not None
        )
        if closeup_needed:
            _commit_feeding_transition(
                ctx,
                closeup,
                transition_type=WNMTransitionTypeV1.ZOOM_IN,
                observation_no=evidence.observation_no,
                reason="feeding_search_or_contact_requires_nipple_mouth_closeup",
                correspondence=nipple_correspondence,
            )
            return True

    if operative.map_id == closeup.map_id and evidence.stage == "rest":
        ready_body = next((item for item in wnm_ready_maps_v1(ctx) if item.map_id == body.map_id), body)
        _commit_feeding_transition(
            ctx,
            ready_body,
            transition_type=WNMTransitionTypeV1.RETURN,
            observation_no=evidence.observation_no,
            reason="feeding_complete_return_to_maternal_body_detail",
            correspondence=nipple_correspondence,
            reverse=True,
        )
        return True

    if operative.map_id == body.map_id and evidence.stage == "rest":
        ready_overview = next((item for item in wnm_ready_maps_v1(ctx) if item.map_id == overview.map_id), overview)
        _commit_feeding_transition(
            ctx,
            ready_overview,
            transition_type=WNMTransitionTypeV1.RETURN,
            observation_no=evidence.observation_no,
            reason="feeding_round_trip_return_to_self_maternal_overview",
            correspondence=maternal_correspondence,
            reverse=True,
        )
        return True

    return False


def _evaluate_pending(
    ctx: Any,
    *,
    applied_policy: Optional[str],
    overlay: FeedingRelationOverlayV1,
) -> Optional[FeedingObservedOutcomeV1]:
    """Close one prior feeding expectation against current supported evidence."""
    pending = getattr(ctx, "feeding_pending_expectation_v1", None)
    if not isinstance(pending, FeedingPendingExpectationV1):
        return None
    expected = pending.expected_successor

    if applied_policy != expected.selected_policy:
        outcome = "not_applied"
        reason = "armed_feeding_primitive_was_not_the_applied_action"
    elif overlay.maternal_identity_handle != expected.maternal_identity_handle:
        outcome = "unknown"
        reason = "maternal_identity_changed"
    elif overlay.nipple_identity_handle != expected.nipple_identity_handle:
        outcome = "unknown"
        reason = "nipple_part_identity_changed"
    elif overlay.freshness != "fresh":
        outcome = "unknown"
        reason = "current_feeding_evidence_unavailable"
    elif expected.expectation_kind is FeedingExpectationKindV1.LOCALIZE_OR_REACH_NIPPLE:
        search_progressed = bool(
            overlay.search_progress is not None
            and expected.source_search_progress is not None
            and overlay.search_progress > expected.source_search_progress
        )
        if overlay.target_localized is True or overlay.reachability is FeedingReachabilityV1.REACHABLE:
            outcome = "success"
            reason = "nipple_target_localized_or_reached"
        elif search_progressed:
            outcome = "success"
            reason = "lower_search_controller_reported_progress"
        else:
            outcome = "failure"
            reason = "supported_observation_showed_no_search_progress"
    elif expected.expectation_kind is FeedingExpectationKindV1.ACQUIRE_LATCH:
        if overlay.contact is True or overlay.latch_evidence is True:
            outcome = "success"
            reason = "feeding_contact_or_latch_acquired"
        elif overlay.target_localized is True:
            outcome = "failure"
            reason = "target_remained_localized_without_contact_or_latch"
        else:
            outcome = "unknown"
            reason = "target_localization_unavailable_for_latch_evaluation"
    else:
        suckle_progressed = bool(
            overlay.suckle_progress is not None
            and expected.source_suckle_progress is not None
            and overlay.suckle_progress > expected.source_suckle_progress
        )
        if overlay.milk_evidence is True:
            outcome = "success"
            reason = "current_milk_evidence_observed"
        elif overlay.contact is False or overlay.latch_evidence is False:
            outcome = "failure"
            reason = "feeding_contact_or_latch_lost"
        elif suckle_progressed or overlay.contact is True:
            outcome = "unknown"
            reason = "contact_or_lower_controller_progress_without_milk_yet"
        else:
            outcome = "unknown"
            reason = "suckle_outcome_not_yet_supported"

    result = FeedingObservedOutcomeV1(
        transaction_no=pending.transaction_no,
        expected_successor=expected,
        action_applied=applied_policy,
        outcome=outcome,
        evidence_map_ref=overlay.source_evidence_map_ref,
        observed_target_localized=overlay.target_localized,
        observed_reachability=overlay.reachability,
        observed_contact=overlay.contact,
        observed_latch_evidence=overlay.latch_evidence,
        observed_milk_evidence=overlay.milk_evidence,
        observed_search_progress=overlay.search_progress,
        observed_suckle_progress=overlay.suckle_progress,
        reason=reason,
    )
    ctx.feeding_pending_expectation_v1 = None
    ctx.feeding_last_outcome_v1 = result
    row = result.as_dict()
    ctx.feeding_last_outcome_update_v1 = dict(row)
    _append_history(
        ctx,
        field_name="feeding_outcome_history_v1",
        limit_field_name="feeding_outcome_history_limit_v1",
        row=row,
    )
    return result


def _expectation_from_overlay(
    ctx: Any,
    overlay: FeedingRelationOverlayV1,
    selected_policy: str,
) -> Optional[FeedingExpectedSuccessorV1]:
    """Build one compact map-native expectation from the operative feeding readout."""
    operative = wnm_operative_map_v1(ctx)
    if operative is None:
        return None
    if selected_policy == "policy:seek_nipple":
        if operative.role not in {_BODY_ROLE, _CLOSEUP_ROLE}:
            return None
        if overlay.target_localized is not True or overlay.reachability is FeedingReachabilityV1.UNREACHABLE:
            kind = FeedingExpectationKindV1.LOCALIZE_OR_REACH_NIPPLE
        else:
            kind = FeedingExpectationKindV1.ACQUIRE_LATCH
    elif selected_policy == "policy:suckle":
        if operative.role != _CLOSEUP_ROLE:
            return None
        if overlay.contact is not True and overlay.latch_evidence is not True:
            return None
        kind = FeedingExpectationKindV1.MAINTAIN_CONTACT_AND_OBTAIN_MILK
    else:
        return None

    transaction_no = _next_transaction_no(ctx)
    provenance = NavProvenanceV1(
        source_class=NavSourceClassV1.EXPECTED,
        source_ref=f"{_EXPECTED_SOURCE_PREFIX}:{transaction_no}",
        quality=0.75,
    )
    return FeedingExpectedSuccessorV1(
        transaction_no=transaction_no,
        source_observation_no=overlay.observation_no,
        source_operative_map_ref=_map_ref(operative),
        maternal_identity_handle=overlay.maternal_identity_handle,
        nipple_identity_handle=overlay.nipple_identity_handle,
        selected_policy=selected_policy,
        expectation_kind=kind,
        source_target_localized=overlay.target_localized,
        source_reachability=overlay.reachability,
        source_contact=overlay.contact,
        source_latch_evidence=overlay.latch_evidence,
        source_milk_evidence=overlay.milk_evidence,
        source_search_progress=overlay.search_progress,
        source_suckle_progress=overlay.suckle_progress,
        provenance=provenance,
    )


def feeding_reset_v1(ctx: Any) -> None:
    """Reset episode-local Phase 5 WNM, overlay, and expectation registers.

    Stable structural maps are also cleared so the next episode reconstructs a
    clean map family from its own identity and frame evidence. Long-term Column
    memory and WorldGraph are outside this runtime and remain untouched.
    """
    if ctx is None:
        return
    ctx.wnm_operative_map_v1 = None
    ctx.wnm_ready_set_v1 = []
    ctx.wnm_transition_no_v1 = 0
    ctx.wnm_last_transition_v1 = None
    ctx.wnm_last_update_v1 = {}
    ctx.wnm_last_refresh_v1 = {}
    ctx.wnm_transition_history_v1 = []
    ctx.feeding_observation_no_v1 = 0
    ctx.feeding_overview_map_v1 = None
    ctx.feeding_maternal_body_map_v1 = None
    ctx.feeding_closeup_map_v1 = None
    ctx.feeding_evidence_map_v1 = None
    ctx.feeding_state_v1 = None
    ctx.feeding_overlay_v1 = None
    ctx.feeding_last_update_v1 = {}
    ctx.feeding_overlay_history_v1 = []
    ctx.feeding_expectation_transaction_no_v1 = 0
    ctx.feeding_pending_expectation_v1 = None
    ctx.feeding_last_expectation_update_v1 = {}
    ctx.feeding_expectation_history_v1 = []
    ctx.feeding_last_outcome_v1 = None
    ctx.feeding_last_outcome_update_v1 = {}
    ctx.feeding_outcome_history_v1 = []


def feeding_wnm_observation_step_v1(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    applied_policy: Optional[str] = None,
) -> dict[str, Any]:
    """Update Phase 5 maps/overlay, close outcomes, and attempt one WNM transition.

    The function must run after Phase 4A geometry and Phase 4C continuity have
    processed the current observation.  It stores only the current full maps;
    bounded histories contain compact summaries and overlays, never a NavMap
    movie.
    """
    if ctx is None:
        return {"schema": "feeding_summary_v1", "phase": "5", "status": "ctx_unavailable"}
    if not bool(getattr(ctx, "feeding_wnm_enabled_v1", True)):
        ctx.feeding_state_v1 = None
        ctx.feeding_overlay_v1 = None
        ctx.feeding_evidence_map_v1 = None
        ctx.feeding_last_update_v1 = {
            "schema": "feeding_summary_v1",
            "phase": "5",
            "status": "disabled",
            "authority": "single_operative_wnm_feeding_domain",
            "policy_selection_mutation_allowed": False,
        }
        return dict(ctx.feeding_last_update_v1)
    if not isinstance(env_obs, EnvObservation):
        raise TypeError("env_obs must be EnvObservation")

    geometry_state = getattr(ctx, "navmap_maternal_state", None)
    if not isinstance(geometry_state, MaternalGeometryShadowStateV1):
        ctx.feeding_last_update_v1 = {
            "schema": "feeding_summary_v1",
            "phase": "5",
            "status": "dependency_error",
            "reason": "phase4a_maternal_geometry_unavailable",
        }
        return dict(ctx.feeding_last_update_v1)
    overview = geometry_state.stable_map if isinstance(geometry_state.stable_map, NavMapV2) else geometry_state.evidence_map
    if not isinstance(overview, NavMapV2):
        raise RuntimeError("Phase 4A did not expose an overview NavMap")

    observation_no = _next_observation_no(ctx)
    evidence = _decode_evidence(ctx, env_obs, observation_no)
    closeup = getattr(ctx, "feeding_closeup_map_v1", None)
    if not isinstance(closeup, NavMapV2):
        closeup = _closeup_structural_map()
        ctx.feeding_closeup_map_v1 = closeup
    body = getattr(ctx, "feeding_maternal_body_map_v1", None)
    if not isinstance(body, NavMapV2):
        body = _maternal_body_structural_map(_map_ref(closeup))
        ctx.feeding_maternal_body_map_v1 = body
    evidence_map = _feeding_evidence_map(evidence)
    ctx.feeding_overview_map_v1 = overview
    ctx.feeding_evidence_map_v1 = evidence_map

    maternal_corr, nipple_corr = _correspondences(ctx, overview, body, closeup, evidence)
    overlay = _derive_overlay(ctx, evidence, evidence_map)
    _evaluate_pending(
        ctx,
        applied_policy=applied_policy if isinstance(applied_policy, str) else None,
        overlay=overlay,
    )
    transition_attempted = _initialize_or_transition(
        ctx,
        overview=overview,
        body=body,
        closeup=closeup,
        maternal_correspondence=maternal_corr,
        nipple_correspondence=nipple_corr,
        overlay=overlay,
        evidence=evidence,
        applied_policy=applied_policy if isinstance(applied_policy, str) else None,
    )

    # Rebuild the overlay after the transition so operative-query authority
    # describes the destination actually committed in this observation.
    overlay = _derive_overlay(ctx, evidence, evidence_map)
    state = FeedingWnmStateV1(
        observation_no=observation_no,
        overview_map_ref=_map_ref(overview),
        maternal_body_map_ref=_map_ref(body),
        feeding_closeup_map_ref=_map_ref(closeup),
        evidence_map_ref=_map_ref(evidence_map) if evidence_map is not None else None,
        maternal_correspondence=maternal_corr,
        nipple_correspondence=nipple_corr,
        overlay=overlay,
        transition_attempted=transition_attempted,
    )
    ctx.feeding_state_v1 = state
    ctx.feeding_overlay_v1 = overlay
    row = state.as_dict()
    ctx.feeding_last_update_v1 = dict(row)
    _append_history(
        ctx,
        field_name="feeding_overlay_history_v1",
        limit_field_name="feeding_overlay_history_limit_v1",
        row=overlay.as_dict(),
    )
    return feeding_summary_v1(ctx)


def feeding_selection_step_v1(ctx: Any, *, selected_policy: Optional[str]) -> dict[str, Any]:
    """Observe the selected primitive and arm one map-native feeding expectation.

    This post-selection hook cannot change the already selected primitive.  It
    records an expectation only for SeekNipple or Suckle when the required
    operative feeding map is active and current source-linked support exists.
    """
    if ctx is None:
        return {"schema": "feeding_summary_v1", "phase": "5", "status": "ctx_unavailable"}
    overlay = getattr(ctx, "feeding_overlay_v1", None)
    if not isinstance(overlay, FeedingRelationOverlayV1):
        return feeding_summary_v1(ctx)
    policy = selected_policy if isinstance(selected_policy, str) and selected_policy else None
    expected = _expectation_from_overlay(ctx, overlay, policy) if policy is not None else None
    if expected is not None:
        pending = FeedingPendingExpectationV1(
            transaction_no=expected.transaction_no,
            expected_successor=expected,
            selected_policy=expected.selected_policy,
            selected_controller_step=_controller_step(ctx),
        )
        ctx.feeding_pending_expectation_v1 = pending
        row = expected.as_dict()
        ctx.feeding_last_expectation_update_v1 = dict(row)
        _append_history(
            ctx,
            field_name="feeding_expectation_history_v1",
            limit_field_name="feeding_expectation_history_limit_v1",
            row=row,
        )
    elif policy in {"policy:seek_nipple", "policy:suckle"}:
        ctx.feeding_last_expectation_update_v1 = {
            "schema": "feeding_expected_successor_v1",
            "phase": "5",
            "status": "deferred",
            "selected_policy": policy,
            "reason": "required_operative_feeding_map_or_relation_unavailable",
            "policy_selection_mutation_allowed": False,
        }
    return feeding_summary_v1(ctx)


def feeding_operative_readout_v1(ctx: Any) -> dict[str, Any]:
    """Return feeding detail permitted by the one currently operative map.

    Overview exposes only that maternal context exists.  Maternal-body detail may
    expose search/localization.  Mouth-to-nipple distance, contact, latch, milk,
    duration, and micro-adjustment are exposed only while the feeding close-up is
    the operative WNM.  This is the destination-only-substrate proof for Phase 5.
    """
    overlay = getattr(ctx, "feeding_overlay_v1", None) if ctx is not None else None
    operative = wnm_operative_map_v1(ctx)
    if not isinstance(overlay, FeedingRelationOverlayV1) or operative is None:
        return {
            "schema": "feeding_operative_readout_v1",
            "phase": "5",
            "status": "unavailable",
            "operative_role": operative.role if operative is not None else None,
            "closeup_detail_authorized": False,
        }
    base: dict[str, Any] = {
        "schema": "feeding_operative_readout_v1",
        "phase": "5",
        "status": "active",
        "operative_map_ref": _map_ref(operative).as_dict(),
        "operative_role": operative.role,
        "maternal_identity_handle": overlay.maternal_identity_handle,
        "nipple_identity_handle": overlay.nipple_identity_handle,
        "closeup_detail_authorized": operative.role == _CLOSEUP_ROLE,
        "source_evidence_map_ref": (
            overlay.source_evidence_map_ref.as_dict() if overlay.source_evidence_map_ref is not None else None
        ),
    }
    if operative.role == _OVERVIEW_ROLE:
        base.update(
            {
                "detail_level": "overview",
                "target_localized": None,
                "reachability": "unknown",
                "contact": None,
                "latch_evidence": None,
                "milk_evidence": None,
                "reason": "feeding_detail_requires_zoom",
            }
        )
        return base
    if operative.role == _BODY_ROLE:
        base.update(
            {
                "detail_level": "maternal_body",
                "target_localized": overlay.target_localized,
                "reachability": overlay.reachability.value,
                "contact": None,
                "latch_evidence": None,
                "milk_evidence": None,
                "reason": "contact_and_milk_require_feeding_closeup",
            }
        )
        return base
    if operative.role == _CLOSEUP_ROLE:
        base.update(
            {
                "detail_level": "feeding_closeup",
                "target_localized": overlay.target_localized,
                "mouth_nipple_distance": overlay.mouth_nipple_distance,
                "reachability": overlay.reachability.value,
                "contact": overlay.contact,
                "latch_evidence": overlay.latch_evidence,
                "milk_evidence": overlay.milk_evidence,
                "contact_event": overlay.contact_event.value,
                "contact_duration_observations": overlay.contact_duration_observations,
                "milk_duration_observations": overlay.milk_duration_observations,
                "micro_adjustment_required": overlay.micro_adjustment_required,
                "lower_oral_head_timing_delegated": True,
                "reason": overlay.reason,
            }
        )
        return base
    base.update(
        {
            "detail_level": "other_operative_map",
            "target_localized": None,
            "reachability": "unknown",
            "contact": None,
            "latch_evidence": None,
            "milk_evidence": None,
            "reason": "operative_map_is_outside_feeding_family",
        }
    )
    return base


def feeding_milk_evidence_v1(ctx: Any) -> Optional[bool]:
    """Return current close-up milk evidence or ``None`` when unsupported.

    This helper is the deliberate replacement for policy-runtime scans of old
    cycle-history records.  It exposes only current map-linked evidence and only
    while the feeding close-up is operative.
    """
    readout = feeding_operative_readout_v1(ctx)
    if readout.get("detail_level") != "feeding_closeup":
        return None
    value = readout.get("milk_evidence")
    return value if isinstance(value, bool) else None


def feeding_latch_evidence_v1(ctx: Any) -> Optional[bool]:
    """Return current close-up latch evidence or ``None`` when unsupported."""
    readout = feeding_operative_readout_v1(ctx)
    if readout.get("detail_level") != "feeding_closeup":
        return None
    value = readout.get("latch_evidence")
    return value if isinstance(value, bool) else None


def feeding_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe Phase 5 feeding/WNM summary."""
    if ctx is None:
        return {"schema": "feeding_summary_v1", "phase": "5", "status": "ctx_unavailable"}
    state = getattr(ctx, "feeding_state_v1", None)
    pending = getattr(ctx, "feeding_pending_expectation_v1", None)
    outcome = getattr(ctx, "feeding_last_outcome_v1", None)
    last_update = getattr(ctx, "feeding_last_update_v1", None)
    if not isinstance(state, FeedingWnmStateV1) and isinstance(last_update, dict):
        status = last_update.get("status")
        if status in {"disabled", "dependency_error", "error"}:
            out = dict(last_update)
            out.setdefault("schema", "feeding_summary_v1")
            out.setdefault("phase", "5")
            out.setdefault("authority", "single_operative_wnm_feeding_domain")
            out.setdefault("policy_selection_mutation_allowed", False)
            out["wnm"] = wnm_summary_v1(ctx)
            return out
    return {
        "schema": "feeding_summary_v1",
        "phase": "5",
        "status": "active" if isinstance(state, FeedingWnmStateV1) else "idle",
        "authority": "single_operative_wnm_feeding_domain",
        "policy_selection_mutation_allowed": False,
        "seek_nipple_authority_changed": False,
        "suckle_authority_changed": False,
        "hunger_remains_compact_drive": True,
        "lower_oral_head_timing_delegated": True,
        "state": state.as_dict() if isinstance(state, FeedingWnmStateV1) else None,
        "operative_readout": feeding_operative_readout_v1(ctx),
        "wnm": wnm_summary_v1(ctx),
        "pending_expectation": (
            pending.expected_successor.as_dict() if isinstance(pending, FeedingPendingExpectationV1) else None
        ),
        "observed_outcome": outcome.as_dict() if isinstance(outcome, FeedingObservedOutcomeV1) else None,
        "overlay_history_count": len(getattr(ctx, "feeding_overlay_history_v1", []) or []),
        "expectation_history_count": len(getattr(ctx, "feeding_expectation_history_v1", []) or []),
        "outcome_history_count": len(getattr(ctx, "feeding_outcome_history_v1", []) or []),
    }


def _ref_text(value: Any) -> str:
    """Return compact text for one optional map-reference dictionary."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id')}@r{value.get('revision')}"


def render_feeding_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 5 feeding/zoom lines."""
    summary = feeding_summary_v1(ctx)
    lines = ["PHASE 5 FEEDING CLOSE-UP / WNM ZOOM:"]
    if summary.get("status") != "active":
        lines.append(f"  status={summary.get('status')} policy_selection_mutation_allowed=False")
        return lines
    readout = summary.get("operative_readout")
    readout = readout if isinstance(readout, dict) else {}
    lines.append(
        "  "
        f"operative={readout.get('detail_level')} map={_ref_text(readout.get('operative_map_ref'))} "
        f"closeup_detail_authorized={readout.get('closeup_detail_authorized')}"
    )
    lines.append(
        "  "
        f"target={readout.get('target_localized')} reach={readout.get('reachability')} "
        f"distance={readout.get('mouth_nipple_distance')} contact={readout.get('contact')} "
        f"latch={readout.get('latch_evidence')} milk={readout.get('milk_evidence')}"
    )
    lines.append(
        "  "
        f"contact_event={readout.get('contact_event')} duration={readout.get('contact_duration_observations')} "
        f"milk_duration={readout.get('milk_duration_observations')} "
        f"micro_adjust={readout.get('micro_adjustment_required')} lower_motor_timing=delegated"
    )
    wnm = summary.get("wnm")
    wnm = wnm if isinstance(wnm, dict) else {}
    last = wnm.get("last_transition")
    last = last if isinstance(last, dict) else {}
    lines.append(
        "  "
        f"ready={wnm.get('ready_count')}/{wnm.get('ready_capacity')} "
        f"transition={last.get('transition_type')} accepted={last.get('accepted')} "
        f"failure={last.get('failure_reason')}"
    )
    pending = summary.get("pending_expectation")
    pending = pending if isinstance(pending, dict) else {}
    outcome = summary.get("observed_outcome")
    outcome = outcome if isinstance(outcome, dict) else {}
    lines.append(
        "  "
        f"expected={pending.get('expectation_kind', 'none')} outcome={outcome.get('outcome', 'none')} "
        f"reason={outcome.get('reason', readout.get('reason'))}"
    )
    return lines
