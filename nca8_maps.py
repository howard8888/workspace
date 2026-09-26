#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Durable NavMap and transient NavMap-state ownership for NCA8 Phase 1C.

Purpose
-------
Phase 1C gives the new runtime its first meaningful internal representation:
a current SELF-ground posture/support state.  The durable
:class:`cca8_navmap_kernel.NavMapV2` is a developmentally seeded, immutable
relational state space containing canonical upright-support and lateral-ground
geometry.  :class:`NavMapStateV1` separately records which configuration is
active now, its activation/current-evidence status, logical timing, and refresh
history.

The explicit ``posture:fallen`` / ``posture:standing`` observation tokens are a
temporary interpreted-perception scaffold.  They select a canonical geometry
profile; they do not revise the durable map.  Runtime activation, support,
currentness, ambiguity, and timing never enter ``NavMapV2``.

Authority boundary
------------------
This module owns durable map records and current map states only.  It contains
no Attention, WNM, Navigation, primitive selection, PNM, task action, learning,
or environment access.  ``CurrentMapViewV1`` is diagnostic and has no world or
executive authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeAlias

from cca8_navmap_kernel import (
    NavBodyStateEvidenceV1,
    NavBodyStateInterpretationV1,
    NavBodyStateThresholdsV1,
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
    body_state_evidence,
)
from nca8_contracts import CircuitValidityV1
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1

# Small validation helpers intentionally remain local so this module is
# understandable without another generic validation dependency.
# pylint: disable=duplicate-code

__version__ = "0.4.0"
__all__ = [
    "NCA8_POSTURE_SUPPORT_MAP_ID_V1",
    "Nca8ContactStateV1",
    "Nca8CurrentMapViewV1",
    "Nca8MapLibraryV1",
    "Nca8PostureStateV1",
    "Nca8SupportStateV1",
    "DurableNavMapV1",
    "DurableNavMapRefV1",
    "NavMapStateV1",
    "MotorSupportConfigurationV1",
    "SupportObservationV1",
    "SupportConfigurationV1",
    "PostureSupportEvidenceV1",
    "PostureSupportGeometryProfileV1",
    "PostureSupportSeedV1",
    "build_posture_support_seed_v1",
    "create_posture_support_map_library_v1",
    "__version__",
]

NCA8_POSTURE_SUPPORT_MAP_ID_V1 = "posture_support"
DurableNavMapV1: TypeAlias = NavMapV2
DurableNavMapRefV1: TypeAlias = NavMapRefV1
_POSTURE_SUPPORT_STATE_ID_V1 = "posture_support:current"
_POSTURE_SUPPORT_OWNER_V1 = "body_sensory"


class Nca8PostureStateV1(str, Enum):
    """Open-world current posture interpretation for the first body pathway."""

    FALLEN = "fallen"
    STANDING = "standing"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class Nca8SupportStateV1(str, Enum):
    """Current support interpretation kept outside durable NavMap content."""

    INADEQUATE = "inadequate"
    STABLE = "stable"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class Nca8ContactStateV1(str, Enum):
    """Minimum current SELF-ground contact interpretation for Phase 1C."""

    LATERAL_GROUND = "lateral_ground"
    FOOT_GROUND = "foot_ground"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_identifier(value: str, *, field_name: str, maximum: int = 120) -> str:
    """Return one non-empty bounded identifier used by NCA8 runtime records."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character limit")
    return normalized


def _unit_interval(value: float, *, field_name: str) -> float:
    """Return one finite activation value in the inclusive unit interval."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return normalized


@dataclass(frozen=True, slots=True)
class SupportObservationV1:
    """One measurement packet for the bounded ``posture_support_v1`` test profile.

    This is engineering input, not a universal NM vector. The sole supported
    frame is ``body_ground_v1``. Body/ground angle is an undirected angle in
    degrees [0, 90]. Useful loading is normalized limb load-bearing support
    [0, 1], not mere contact. Destabilization is normalized slip/rotation/collapse
    magnitude [0, 1], not a success score. Lateral contact is a separate optional
    observation. Missing quantities remain None; no quantity is inferred here.

    Each session has one support-sensor stream. ``sample_id`` is its positive,
    strictly increasing integer identity. ``event_cycle`` names the represented
    event on the NCA8 logical cycle clock (starting at 1), not the arrival cycle
    or an environment step number. The owning sensory consumer checks ordering
    and freshness. Neither the sender nor this record chooses a durable source,
    an owning circuit, a task, or an action.
    """

    sample_id: int
    event_cycle: int
    frame_id: str
    body_ground_angle_degrees: float | None = None
    useful_loading: float | None = None
    destabilization: float | None = None
    lateral_contact: bool | None = None

    def __post_init__(self) -> None:
        for name in ("sample_id", "event_cycle"):
            value = _positive_int(getattr(self, name), field_name=name)
            if value > 2**63 - 1:
                raise ValueError(f"{name} exceeds the signed 64-bit bound")
        if self.frame_id != "body_ground_v1":
            raise ValueError("support observations require frame_id='body_ground_v1'")
        for name, upper in (("body_ground_angle_degrees", 90.0), ("useful_loading", 1.0), ("destabilization", 1.0)):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric or None")
            number = float(value)
            if not math.isfinite(number) or not 0.0 <= number <= upper:
                raise ValueError(f"{name} must be finite and between 0 and {upper}")
            object.__setattr__(self, name, number)
        if self.lateral_contact is not None and not isinstance(self.lateral_contact, bool):
            raise TypeError("lateral_contact must be Boolean or None")

    @property
    def has_measurements(self) -> bool:
        """Distinguish an all-missing sample from observed zero/False values."""
        return any(value is not None for value in (
            self.body_ground_angle_degrees, self.useful_loading, self.destabilization, self.lateral_contact,
        ))

    def as_dict(self) -> dict[str, str | int | float | bool | None]:
        """Return a detached, finite, JSON-safe packet without authority fields."""
        return {
            "schema": "posture_support_v1",
            "sample_id": self.sample_id,
            "event_cycle": self.event_cycle,
            "frame_id": self.frame_id,
            "body_ground_angle_degrees": self.body_ground_angle_degrees,
            "useful_loading": self.useful_loading,
            "destabilization": self.destabilization,
            "lateral_contact": self.lateral_contact,
        }


@dataclass(frozen=True, slots=True)
class SupportConfigurationV1:
    """Read-only measured companion to the existing A0 POSTURE-SUPPORT configuration.

    The sensory owner replaces one current register after Phase-C admission.
    This is not another durable NM or another WNM. The original A0 configuration
    still supplies BodyMap and primitive decisions. P16-1E-C may use this register
    in a source-local dynamics facet copied into read-only WNM content, without
    granting it behavioral authority. The received sample and any discrepancy
    remain inspectable even when not accepted as current.

    ``last_supported_event_cycle`` is the last genuinely fresh, non-conflicting
    measurement event, not a claim of mechanically adequate support. Replays,
    delayed packets, missing values, and rejected inputs do not refresh it.
    Source identity comes from the local map library, never from the packet.
    """

    source_map_ref: DurableNavMapRefV1
    observation: SupportObservationV1 | None
    scaffold_posture: Nca8PostureStateV1
    available_cycle: int
    applied_cycle: int
    disposition: str
    reason: str
    discrepancy: str | None
    last_supported_event_cycle: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_ref, DurableNavMapRefV1):
            raise TypeError("source_map_ref must be a durable NavMap reference")
        if self.source_map_ref.map_id != NCA8_POSTURE_SUPPORT_MAP_ID_V1:
            raise ValueError("the measured companion belongs to POSTURE-SUPPORT only")
        if self.observation is not None and not isinstance(self.observation, SupportObservationV1):
            raise TypeError("observation must be SupportObservationV1 or None")
        if not isinstance(self.scaffold_posture, Nca8PostureStateV1):
            raise TypeError("scaffold_posture must be Nca8PostureStateV1")
        available = _positive_int(self.available_cycle, field_name="available_cycle")
        applied = _positive_int(self.applied_cycle, field_name="applied_cycle")
        if available > applied:
            raise ValueError("support configuration cannot be applied before availability")
        allowed = {"current", "missing", "invalid", "duplicate", "out_of_order", "future", "delayed", "empty", "conflict"}
        if self.disposition not in allowed:
            raise ValueError("unknown support-configuration disposition")
        _bounded_identifier(self.reason, field_name="reason")
        if self.discrepancy is not None:
            _bounded_identifier(self.discrepancy, field_name="discrepancy")
        if self.last_supported_event_cycle is not None:
            supported = _positive_int(self.last_supported_event_cycle, field_name="last_supported_event_cycle")
            if supported > applied:
                raise ValueError("last support cannot follow application")
        if self.disposition == "current":
            sample = self.observation
            if sample is None or not sample.has_measurements or self.discrepancy is not None:
                raise ValueError("current support evidence needs non-conflicting measurements")
            if sample.event_cycle != available or available != applied:
                raise ValueError("current support evidence must describe the current available/applied cycle")
            if self.last_supported_event_cycle != sample.event_cycle:
                raise ValueError("current support evidence must retain its actual event time")

    @property
    def owner_circuit(self) -> str:
        """Return the local owning circuit, not a sender-controlled claim."""
        return _POSTURE_SUPPORT_OWNER_V1

    @property
    def evidence_current(self) -> bool:
        """Report fresh measurement evidence, never mechanical support adequacy."""
        return self.disposition == "current"

    @property
    def behavioral_authority(self) -> bool:
        """Remain False for every P15-1E-A disposition, including current evidence."""
        return False

    def trace_details(self) -> dict[str, str | int | float | bool | None]:
        """Return at most sixteen scalar details for the existing read-only trace."""
        sample = self.observation
        return {
            "source": "EnvObservation.raw_sensors.posture_support_v1",
            "owner": self.owner_circuit,
            "durable_map": f"{self.source_map_ref.map_id}@r{self.source_map_ref.revision}",
            "sample_id": sample.sample_id if sample is not None else None,
            "event_cycle": sample.event_cycle if sample is not None else None,
            "available_cycle": self.available_cycle,
            "applied_cycle": self.applied_cycle,
            "disposition": self.disposition,
            "reason": self.reason,
            "discrepancy": self.discrepancy,
            "body_ground_angle_degrees": sample.body_ground_angle_degrees if sample is not None else None,
            "useful_loading": sample.useful_loading if sample is not None else None,
            "destabilization": sample.destabilization if sample is not None else None,
            "lateral_contact": sample.lateral_contact if sample is not None else None,
            "last_supported_event_cycle": self.last_supported_event_cycle,
            "behavioral_authority": self.behavioral_authority,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a detached diagnostic snapshot; no live map is exposed."""
        return {
            "schema": "support_configuration_v1",
            "source_map_ref": self.source_map_ref.as_dict(),
            "owner_circuit": self.owner_circuit,
            "observation": self.observation.as_dict() if self.observation is not None else None,
            "scaffold_posture": self.scaffold_posture.value,
            "available_cycle": self.available_cycle,
            "applied_cycle": self.applied_cycle,
            "disposition": self.disposition,
            "reason": self.reason,
            "discrepancy": self.discrepancy,
            "last_supported_event_cycle": self.last_supported_event_cycle,
            "evidence_current": self.evidence_current,
            "behavioral_authority": self.behavioral_authority,
        }


@dataclass(frozen=True, slots=True)
class PostureSupportGeometryProfileV1:
    """Select one canonical SELF-ground geometry configuration in a durable map."""

    profile_id: str
    expected_posture: Nca8PostureStateV1
    body_element_id: str
    head_element_id: str
    foot_element_id: str
    ground_element_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _bounded_identifier(self.profile_id, field_name="profile_id"))
        if not isinstance(self.expected_posture, Nca8PostureStateV1):
            raise TypeError("expected_posture must be an Nca8PostureStateV1")
        for field_name in (
            "body_element_id",
            "head_element_id",
            "foot_element_id",
            "ground_element_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )

    @property
    def active_element_ids(self) -> tuple[str, ...]:
        """Return the bounded element set activated by this configuration."""
        return (
            self.body_element_id,
            self.head_element_id,
            self.foot_element_id,
            self.ground_element_id,
        )


@dataclass(frozen=True, slots=True)
class PostureSupportEvidenceV1:
    """Transparent current posture/support evidence derived from one map revision.

    Clear scaffold inputs select a canonical geometry profile and are evaluated
    by the existing pure ``body_state_evidence`` operator.  Missing or
    conflicting posture input produces an explicit open-world record with no
    fabricated geometry profile.
    """

    source_map_ref: NavMapRefV1
    posture: Nca8PostureStateV1
    support: Nca8SupportStateV1
    contact: Nca8ContactStateV1
    geometry_profile_id: str | None
    active_element_ids: tuple[str, ...]
    evidence_current: bool
    reason: str
    body_ground_angle_degrees: float | None = None
    foot_ground_contact: bool | None = None
    head_ground_distance: float | None = None
    lateral_contact_fraction: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be a NavMapRefV1")
        if not isinstance(self.posture, Nca8PostureStateV1):
            raise TypeError("posture must be an Nca8PostureStateV1")
        if not isinstance(self.support, Nca8SupportStateV1):
            raise TypeError("support must be an Nca8SupportStateV1")
        if not isinstance(self.contact, Nca8ContactStateV1):
            raise TypeError("contact must be an Nca8ContactStateV1")
        if not isinstance(self.evidence_current, bool):
            raise TypeError("evidence_current must be Boolean")
        if self.geometry_profile_id is not None:
            object.__setattr__(
                self,
                "geometry_profile_id",
                _bounded_identifier(self.geometry_profile_id, field_name="geometry_profile_id"),
            )
        active_ids = tuple(sorted(_bounded_identifier(item, field_name="active_element_id") for item in self.active_element_ids))
        if len(set(active_ids)) != len(active_ids):
            raise ValueError("active_element_ids must not contain duplicates")
        object.__setattr__(self, "active_element_ids", active_ids)
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason", maximum=160))

        if self.posture in (Nca8PostureStateV1.FALLEN, Nca8PostureStateV1.STANDING):
            if self.geometry_profile_id is None or not active_ids:
                raise ValueError("clear posture evidence requires one canonical geometry profile")
            if not self.evidence_current:
                raise ValueError("clear posture evidence must be current")
        else:
            if self.geometry_profile_id is not None or active_ids:
                raise ValueError("AMBIGUOUS/UNKNOWN evidence must not select one canonical geometry profile")

    def as_dict(self) -> dict[str, object]:
        """Return one JSON-safe evidence summary without exposing mutable state."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "posture": self.posture.value,
            "support": self.support.value,
            "contact": self.contact.value,
            "geometry_profile_id": self.geometry_profile_id,
            "active_element_ids": list(self.active_element_ids),
            "evidence_current": self.evidence_current,
            "reason": self.reason,
            "body_ground_angle_degrees": self.body_ground_angle_degrees,
            "foot_ground_contact": self.foot_ground_contact,
            "head_ground_distance": self.head_ground_distance,
            "lateral_contact_fraction": self.lateral_contact_fraction,
        }


@dataclass(frozen=True, slots=True)
class MotorSupportConfigurationV1:
    """One enhanced facet of POSTURE-SUPPORT, not another map or body sensor.

    ``evidence`` references the H1 physical acquisition at its eligible focal
    boundary. Local ticks are never converted into the old v1 event-cycle unit.
    ``previous`` is at most one comparable acquisition, not a remembered scene.
    Rates use actual elapsed simulation time; first/missing/stale/repeated/gapped
    samples have unknown rates, never invented zeros. The age limit is two local
    ticks and the maximum comparable pair span is eight ticks in this profile.
    These are engineering bounds, not neural timing or an outcome/dwell rule.
    BODY, GRAVITY and SUPPORT_SURFACE are roles at the declared planar resolution;
    naming the surface role does not assert that contact or useful support exists.
    """

    source_map_ref: NavMapRefV1
    stream: MotorStreamRefV1
    evidence: FocalMotorEvidenceV1 | None
    previous: MotorFeedbackV1 | None
    applied_cycle: int
    cutoff_tick: int
    tick_seconds: float = 0.05

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_ref, NavMapRefV1) or not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("motor source requires map and stream references")
        _positive_int(self.applied_cycle, field_name="applied_cycle")
        if isinstance(self.cutoff_tick, bool) or not isinstance(self.cutoff_tick, int) or not 0 <= self.cutoff_tick < 2**63 - 1:
            raise ValueError("cutoff_tick must be a bounded nonnegative integer")
        if isinstance(self.tick_seconds, bool) or not isinstance(self.tick_seconds, (int, float)):
            raise TypeError("tick_seconds must be numeric")
        if not math.isfinite(self.tick_seconds) or not 0.0 < self.tick_seconds <= 1.0:
            raise ValueError("tick_seconds must be finite and in (0,1]")
        if self.evidence is not None:
            if not isinstance(self.evidence, FocalMotorEvidenceV1):
                raise TypeError("evidence must be FocalMotorEvidenceV1 or None")
            if self.evidence.focal_cycle != self.applied_cycle or self.evidence.cutoff_tick != self.cutoff_tick:
                raise ValueError("motor source must use its actual focal admission boundary")
            self.evidence.feedback.validate_available(stream=self.stream, at_tick=self.cutoff_tick)
        if self.previous is not None:
            if not isinstance(self.previous, MotorFeedbackV1) or not self.current:
                raise ValueError("a comparable reference requires current motor evidence")
            current = self.feedback
            if current is None:  # defensive narrowing; current above already requires it
                raise ValueError("current acquisition missing")
            self.previous.validate_available(stream=self.stream, at_tick=self.cutoff_tick)
            if self.previous.sample_id >= current.sample_id or not 0 < current.event_tick - self.previous.event_tick <= 8:
                raise ValueError("motor rate reference must be an earlier comparable acquisition")
            if any(rate is not None and not math.isfinite(rate) for rate in self.rates):
                raise ValueError("motor source time resolution produces a nonfinite rate")

    @property
    def feedback(self) -> MotorFeedbackV1 | None:
        """Return the original acquisition, not a newly sampled sensor report."""
        return self.evidence.feedback if self.evidence is not None else None

    @property
    def current(self) -> bool:
        """Return freshness only; an absent individual channel remains absent."""
        feedback = self.feedback
        return feedback is not None and self.cutoff_tick - feedback.event_tick <= 2

    @property
    def rates(self) -> tuple[float | None, float | None, float | None]:
        """Return absolute-tilt, useful-load and destabilization rates per second."""
        feedback, previous = self.feedback, self.previous
        if not self.current or feedback is None or previous is None:
            return None, None, None
        seconds = (feedback.event_tick - previous.event_tick) * self.tick_seconds
        values: list[float | None] = []
        for name in ("body_tilt_degrees", "useful_loading", "destabilization"):
            old, new = getattr(previous, name), getattr(feedback, name)
            if old is None or new is None:
                values.append(None)
            else:
                difference = abs(new) - abs(old) if name == "body_tilt_degrees" else new - old
                values.append(difference / seconds)
        return values[0], values[1], values[2]

    def content_key(self) -> tuple[object, ...]:
        """Describe current relation content without treating a new ID as new learning."""
        feedback = self.feedback
        measured = () if feedback is None else (
            feedback.body_tilt_degrees, feedback.support_extension, feedback.support_contact,
            feedback.useful_loading, feedback.destabilization,
        )
        if feedback is not None and feedback.body_bearing is not None:
            measured = (*measured, feedback.body_bearing.contact, feedback.body_bearing.bearing)
        return (self.current, measured, self.rates)

    def as_dict(self) -> dict[str, object]:
        """Export one coherent source facet with explicit physical and focal times."""
        tilt_rate, load_rate, instability_rate = self.rates
        return {
            "source_map_ref": self.source_map_ref.as_dict(), "owner_circuit": "body_sensory",
            "roles": ["BODY", "GRAVITY", "SUPPORT_SURFACE"], "applied_cycle": self.applied_cycle,
            "cutoff_tick": self.cutoff_tick, "tick_seconds": self.tick_seconds, "current": self.current,
            "evidence": self.evidence.as_dict() if self.evidence is not None else None,
            "previous_sample_id": self.previous.sample_id if self.previous is not None else None,
            "absolute_tilt_rate": tilt_rate, "loading_rate": load_rate, "destabilization_rate": instability_rate,
            "independent_sensor_event": False, "durable_update": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapStateV1:
    """Transient active configuration of one immutable durable NavMap revision.

    The state ID identifies one current slot owned by the body-sensory circuit.
    Repeated equivalent observations refresh this slot rather than creating a
    durable map revision.  Timing, activation, current support, and open-world
    interpretation live here and never inside ``NavMapV2``.
    """

    state_id: str
    source_map_ref: NavMapRefV1
    owner_circuit: str
    posture: Nca8PostureStateV1
    support: Nca8SupportStateV1
    contact: Nca8ContactStateV1
    active_element_ids: tuple[str, ...]
    active_relation_labels: tuple[str, ...]
    activation: float
    evidence_current: bool
    sampled_event_cycle: int
    available_cycle: int
    applied_cycle: int
    last_supported_cycle: int | None
    validity: CircuitValidityV1
    update_count: int
    equivalent_refresh_count: int
    configuration_change_count: int
    motor_support: MotorSupportConfigurationV1 | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", _bounded_identifier(self.state_id, field_name="state_id"))
        if not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be a NavMapRefV1")
        object.__setattr__(
            self,
            "owner_circuit",
            _bounded_identifier(self.owner_circuit, field_name="owner_circuit"),
        )
        if not isinstance(self.posture, Nca8PostureStateV1):
            raise TypeError("posture must be an Nca8PostureStateV1")
        if not isinstance(self.support, Nca8SupportStateV1):
            raise TypeError("support must be an Nca8SupportStateV1")
        if not isinstance(self.contact, Nca8ContactStateV1):
            raise TypeError("contact must be an Nca8ContactStateV1")
        if not isinstance(self.validity, CircuitValidityV1):
            raise TypeError("validity must be a CircuitValidityV1")
        if not isinstance(self.evidence_current, bool):
            raise TypeError("evidence_current must be Boolean")

        active_ids = tuple(sorted(_bounded_identifier(item, field_name="active_element_id") for item in self.active_element_ids))
        relation_labels = tuple(
            sorted(_bounded_identifier(item, field_name="active_relation_label") for item in self.active_relation_labels)
        )
        if len(set(active_ids)) != len(active_ids):
            raise ValueError("active_element_ids must not contain duplicates")
        if len(set(relation_labels)) != len(relation_labels):
            raise ValueError("active_relation_labels must not contain duplicates")
        object.__setattr__(self, "active_element_ids", active_ids)
        object.__setattr__(self, "active_relation_labels", relation_labels)
        object.__setattr__(self, "activation", _unit_interval(self.activation, field_name="activation"))

        sampled = _positive_int(self.sampled_event_cycle, field_name="sampled_event_cycle")
        available = _positive_int(self.available_cycle, field_name="available_cycle")
        applied = _positive_int(self.applied_cycle, field_name="applied_cycle")
        if available < sampled:
            raise ValueError("available_cycle cannot precede sampled_event_cycle")
        if applied < available:
            raise ValueError("applied_cycle cannot precede available_cycle")
        if self.last_supported_cycle is not None:
            supported = _positive_int(self.last_supported_cycle, field_name="last_supported_cycle")
            if supported > applied:
                raise ValueError("last_supported_cycle cannot follow applied_cycle")
        if self.evidence_current and self.last_supported_cycle != applied:
            raise ValueError("current evidence must update last_supported_cycle to applied_cycle")

        update_count = _positive_int(self.update_count, field_name="update_count")
        for field_name in ("equivalent_refresh_count", "configuration_change_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.equivalent_refresh_count + self.configuration_change_count > update_count - 1:
            raise ValueError("refresh/change counts cannot exceed prior state updates")
        if self.motor_support is not None:
            if not isinstance(self.motor_support, MotorSupportConfigurationV1):
                raise TypeError("motor_support must be MotorSupportConfigurationV1 or None")
            if self.motor_support.source_map_ref != self.source_map_ref or self.motor_support.applied_cycle != applied:
                raise ValueError("motor facet must belong to this source and focal update")
            if self.owner_circuit != "body_sensory":
                raise ValueError("motor source facet must remain with its sensory owner")


    def semantic_key(self) -> tuple[object, ...]:
        """Return timing-independent current content used to detect refreshes."""
        return (
            self.source_map_ref,
            self.owner_circuit,
            self.posture,
            self.support,
            self.contact,
            self.active_element_ids,
            self.active_relation_labels,
            self.activation,
            self.evidence_current,
            self.validity,
        ) + ((self.motor_support.content_key(),) if self.motor_support is not None else ())

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe current-state representation."""
        return {
            "state_id": self.state_id,
            "source_map_ref": self.source_map_ref.as_dict(),
            "owner_circuit": self.owner_circuit,
            "posture": self.posture.value,
            "support": self.support.value,
            "contact": self.contact.value,
            "active_element_ids": list(self.active_element_ids),
            "active_relation_labels": list(self.active_relation_labels),
            "activation": self.activation,
            "evidence_current": self.evidence_current,
            "sampled_event_cycle": self.sampled_event_cycle,
            "available_cycle": self.available_cycle,
            "applied_cycle": self.applied_cycle,
            "last_supported_cycle": self.last_supported_cycle,
            "validity": self.validity.value,
            "update_count": self.update_count,
            "equivalent_refresh_count": self.equivalent_refresh_count,
            "configuration_change_count": self.configuration_change_count,
            **({"motor_support": self.motor_support.as_dict()} if self.motor_support is not None else {}),
        }


@dataclass(frozen=True, slots=True)
class Nca8CurrentMapViewV1:
    """Read-only derived view of current states with no independent authority."""

    states: tuple[NavMapStateV1, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.states, key=lambda item: (item.owner_circuit, item.state_id)))
        if len({state.state_id for state in ordered}) != len(ordered):
            raise ValueError("current map view must not contain duplicate state IDs")
        object.__setattr__(self, "states", ordered)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe diagnostic projection."""
        return {
            "authority": "diagnostic_only",
            "state_count": len(self.states),
            "states": [state.as_dict() for state in self.states],
        }


@dataclass(frozen=True, slots=True)
class PostureSupportSeedV1:
    """One explicit developmental bootstrap for the first NCA8 body pathway."""

    durable_map: NavMapV2
    thresholds: NavBodyStateThresholdsV1
    profiles: tuple[PostureSupportGeometryProfileV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.durable_map, NavMapV2):
            raise TypeError("durable_map must be a NavMapV2")
        if not isinstance(self.thresholds, NavBodyStateThresholdsV1):
            raise TypeError("thresholds must be a NavBodyStateThresholdsV1")
        profiles = tuple(sorted(self.profiles, key=lambda item: item.profile_id))
        if len({profile.profile_id for profile in profiles}) != len(profiles):
            raise ValueError("posture-support profile IDs must be unique")
        element_ids = {element.element_id for element in self.durable_map.elements}
        for profile in profiles:
            if not set(profile.active_element_ids).issubset(element_ids):
                raise ValueError(f"profile {profile.profile_id!r} references missing durable elements")
        object.__setattr__(self, "profiles", profiles)


def _provenance_v1(source_ref: str) -> NavProvenanceV1:
    """Return explicit provenance for one developmental engineering seed."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.UNKNOWN,
        source_ref=source_ref,
        quality=1.0,
    )


def _geometry_v1(kind: NavGeometryKindV1, *points: tuple[float, float]) -> NavGeometryV1:
    """Build one compact immutable geometry record."""
    return NavGeometryV1(
        kind=kind,
        points=tuple(NavPointV1(x=x, y=y) for x, y in points),
    )


def _element_v1(
    element_id: str,
    role: str,
    geometry: NavGeometryV1,
    *,
    parent_element_id: str | None = None,
) -> NavElementV1:
    """Build one seed element without runtime activation fields."""
    return NavElementV1(
        element_id=element_id,
        role=role,
        geometry=geometry,
        activations=(),
        parent_element_id=parent_element_id,
        provenance=_provenance_v1("developmental_seed:posture_support_v1"),
    )


def build_posture_support_seed_v1() -> PostureSupportSeedV1:
    """Build the immutable POSTURE-SUPPORT state space and its geometry profiles.

    Both canonical configurations live in one durable map family.  Runtime
    perception activates one profile through ``NavMapStateV1``; it does not
    create a map revision for each posture or cognitive cycle.
    """
    frame = NavFrameV1(
        frame_id="self_ground_canonical_v1",
        x_axis="body_forward",
        y_axis="gravity_up",
        units="normalized_body_length",
        min_x=-2.0,
        max_x=2.0,
        min_y=-0.5,
        max_y=2.5,
    )
    elements = (
        _element_v1(
            "ground_surface",
            "support_surface",
            _geometry_v1(NavGeometryKindV1.SEGMENT, (-1.5, 0.0), (1.5, 0.0)),
        ),
        _element_v1(
            "self_axis_lateral",
            "self_body_axis_template",
            _geometry_v1(NavGeometryKindV1.SEGMENT, (-0.8, 0.10), (0.8, 0.10)),
        ),
        _element_v1(
            "self_head_lateral",
            "self_head_template",
            _geometry_v1(NavGeometryKindV1.POINT, (0.90, 0.10)),
            parent_element_id="self_axis_lateral",
        ),
        _element_v1(
            "self_foot_lateral",
            "self_foot_template",
            _geometry_v1(NavGeometryKindV1.POINT, (-0.70, 0.05)),
            parent_element_id="self_axis_lateral",
        ),
        _element_v1(
            "self_axis_upright",
            "self_body_axis_template",
            _geometry_v1(NavGeometryKindV1.SEGMENT, (0.0, 0.10), (0.0, 1.50)),
        ),
        _element_v1(
            "self_head_upright",
            "self_head_template",
            _geometry_v1(NavGeometryKindV1.POINT, (0.0, 1.65)),
            parent_element_id="self_axis_upright",
        ),
        _element_v1(
            "self_foot_upright",
            "self_foot_template",
            _geometry_v1(NavGeometryKindV1.POINT, (0.0, 0.04)),
            parent_element_id="self_axis_upright",
        ),
    )
    relation_provenance = _provenance_v1("developmental_seed:posture_support_relations_v1")
    relations = (
        NavRelationV1(
            relation_type="references_support_surface",
            source_element_id="self_axis_lateral",
            target_element_id="ground_surface",
            provenance=relation_provenance,
        ),
        NavRelationV1(
            relation_type="references_support_surface",
            source_element_id="self_axis_upright",
            target_element_id="ground_surface",
            provenance=relation_provenance,
        ),
    )
    durable_map = NavMapV2(
        map_id=NCA8_POSTURE_SUPPORT_MAP_ID_V1,
        revision=1,
        role="posture_support_state_space",
        frame=frame,
        provenance=_provenance_v1("developmental_seed:posture_support_map_v1"),
        elements=elements,
        relations=relations,
        links=(),
    )
    thresholds = NavBodyStateThresholdsV1(
        contact_tolerance=0.10,
        lateral_distance_threshold=0.25,
        upright_angle_tolerance_degrees=15.0,
        parallel_angle_tolerance_degrees=15.0,
        minimum_standing_head_elevation=1.00,
        maximum_fallen_head_elevation=0.30,
        maximum_standing_lateral_fraction=0.20,
        minimum_fallen_lateral_fraction=0.80,
    )
    profiles = (
        PostureSupportGeometryProfileV1(
            profile_id="lateral_ground_profile_v1",
            expected_posture=Nca8PostureStateV1.FALLEN,
            body_element_id="self_axis_lateral",
            head_element_id="self_head_lateral",
            foot_element_id="self_foot_lateral",
            ground_element_id="ground_surface",
        ),
        PostureSupportGeometryProfileV1(
            profile_id="upright_support_profile_v1",
            expected_posture=Nca8PostureStateV1.STANDING,
            body_element_id="self_axis_upright",
            head_element_id="self_head_upright",
            foot_element_id="self_foot_upright",
            ground_element_id="ground_surface",
        ),
    )
    return PostureSupportSeedV1(
        durable_map=durable_map,
        thresholds=thresholds,
        profiles=profiles,
    )


class Nca8MapLibraryV1:
    """Own immutable durable maps and their separately mutable current-state table."""

    def __init__(self, seed: PostureSupportSeedV1) -> None:
        if not isinstance(seed, PostureSupportSeedV1):
            raise TypeError("seed must be a PostureSupportSeedV1")
        map_ref = NavMapRefV1(seed.durable_map.map_id, seed.durable_map.revision)
        self._durable_maps: dict[NavMapRefV1, NavMapV2] = {map_ref: seed.durable_map}
        self._profiles = {profile.profile_id: profile for profile in seed.profiles}
        self._thresholds = seed.thresholds
        self._posture_support_ref = map_ref
        self._current_states: dict[str, NavMapStateV1] = {}

    @property
    def posture_support_ref(self) -> NavMapRefV1:
        """Return the exact durable POSTURE-SUPPORT revision used by current states."""
        return self._posture_support_ref

    @property
    def durable_map_count(self) -> int:
        """Return the number of registered immutable map revisions."""
        return len(self._durable_maps)

    @property
    def current_state_count(self) -> int:
        """Return the number of owned current state slots."""
        return len(self._current_states)

    def durable_map(self, map_ref: NavMapRefV1 | None = None) -> NavMapV2:
        """Return one immutable durable map revision by exact reference."""
        requested = map_ref or self._posture_support_ref
        try:
            return self._durable_maps[requested]
        except KeyError as exc:
            raise KeyError(f"unknown durable NavMap revision: {requested.map_id}@r{requested.revision}") from exc

    def durable_record_signature(self) -> str:
        """Return the exact POSTURE-SUPPORT durable record signature."""
        return self.durable_map().record_signature()

    def current_state(self, map_id: str = NCA8_POSTURE_SUPPORT_MAP_ID_V1) -> NavMapStateV1 | None:
        """Return the immutable current state for one map family, when available."""
        return self._current_states.get(map_id)

    def current_map_view(self) -> Nca8CurrentMapViewV1:
        """Return a derived read-only view with no storage or executive authority."""
        return Nca8CurrentMapViewV1(states=tuple(self._current_states.values()))

    def evaluate_profile(self, profile_id: str) -> PostureSupportEvidenceV1:
        """Evaluate one canonical configuration using the shared pure geometry kernel."""
        normalized_profile = _bounded_identifier(profile_id, field_name="profile_id")
        try:
            profile = self._profiles[normalized_profile]
        except KeyError as exc:
            raise KeyError(f"unknown posture-support geometry profile: {normalized_profile!r}") from exc
        navmap = self.durable_map()
        kernel_evidence = body_state_evidence(
            navmap,
            body_element_id=profile.body_element_id,
            head_element_id=profile.head_element_id,
            foot_element_id=profile.foot_element_id,
            ground_element_id=profile.ground_element_id,
            thresholds=self._thresholds,
        )
        return self._evidence_from_kernel(profile, kernel_evidence)

    def _evidence_from_kernel(
        self,
        profile: PostureSupportGeometryProfileV1,
        evidence: NavBodyStateEvidenceV1,
    ) -> PostureSupportEvidenceV1:
        """Map one kernel result into the minimum Phase-1C current-state vocabulary."""
        if evidence.interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE:
            posture = Nca8PostureStateV1.FALLEN
            support = Nca8SupportStateV1.INADEQUATE
            contact = Nca8ContactStateV1.LATERAL_GROUND
        elif evidence.interpretation is NavBodyStateInterpretationV1.STANDING_LIKE:
            posture = Nca8PostureStateV1.STANDING
            support = Nca8SupportStateV1.STABLE
            contact = Nca8ContactStateV1.FOOT_GROUND
        elif evidence.interpretation is NavBodyStateInterpretationV1.AMBIGUOUS:
            posture = Nca8PostureStateV1.AMBIGUOUS
            support = Nca8SupportStateV1.AMBIGUOUS
            contact = Nca8ContactStateV1.MIXED
        else:
            posture = Nca8PostureStateV1.UNKNOWN
            support = Nca8SupportStateV1.UNKNOWN
            contact = Nca8ContactStateV1.UNKNOWN

        if posture is not profile.expected_posture:
            raise RuntimeError(
                f"canonical profile {profile.profile_id!r} produced {posture.value!r}, "
                f"expected {profile.expected_posture.value!r}"
            )
        support_record = evidence.support
        if support_record is None:
            raise RuntimeError("a canonical posture-support profile produced no complete support evidence")
        return PostureSupportEvidenceV1(
            source_map_ref=evidence.source_map_ref,
            posture=posture,
            support=support,
            contact=contact,
            geometry_profile_id=profile.profile_id,
            active_element_ids=profile.active_element_ids,
            evidence_current=True,
            reason=evidence.reason,
            body_ground_angle_degrees=support_record.body_ground_angle.value,
            foot_ground_contact=support_record.foot_ground_contact.contact,
            head_ground_distance=support_record.head_ground_distance.value,
            lateral_contact_fraction=support_record.lateral_contact.fraction,
        )

    def open_world_evidence(
        self,
        posture: Nca8PostureStateV1,
        *,
        reason: str,
    ) -> PostureSupportEvidenceV1:
        """Represent missing or conflicting input without selecting a geometry profile."""
        if posture is Nca8PostureStateV1.AMBIGUOUS:
            support = Nca8SupportStateV1.AMBIGUOUS
            contact = Nca8ContactStateV1.MIXED
            current = True
        elif posture is Nca8PostureStateV1.UNKNOWN:
            support = Nca8SupportStateV1.UNKNOWN
            contact = Nca8ContactStateV1.UNKNOWN
            current = False
        else:
            raise ValueError("open_world_evidence accepts only AMBIGUOUS or UNKNOWN posture")
        return PostureSupportEvidenceV1(
            source_map_ref=self._posture_support_ref,
            posture=posture,
            support=support,
            contact=contact,
            geometry_profile_id=None,
            active_element_ids=(),
            evidence_current=current,
            reason=reason,
        )

    def update_current_state(
        self,
        evidence: PostureSupportEvidenceV1,
        *,
        sampled_event_cycle: int,
        available_cycle: int,
        applied_cycle: int,
    ) -> NavMapStateV1:
        """Replace or refresh the transient current state without revising durable content."""
        if not isinstance(evidence, PostureSupportEvidenceV1):
            raise TypeError("evidence must be PostureSupportEvidenceV1")
        if evidence.source_map_ref != self._posture_support_ref:
            raise ValueError("posture-support evidence must reference the registered durable map")
        durable = self.durable_map(evidence.source_map_ref)
        durable_element_ids = {element.element_id for element in durable.elements}
        if not set(evidence.active_element_ids).issubset(durable_element_ids):
            raise ValueError("current state references elements absent from the durable map")

        existing = self._current_states.get(NCA8_POSTURE_SUPPORT_MAP_ID_V1)
        last_supported_cycle = applied_cycle if evidence.evidence_current else None
        if existing is not None and not evidence.evidence_current:
            last_supported_cycle = existing.last_supported_cycle

        activation = 1.0
        if evidence.posture is Nca8PostureStateV1.AMBIGUOUS:
            activation = 0.5
        elif evidence.posture is Nca8PostureStateV1.UNKNOWN:
            activation = 0.0

        active_relations = (
            f"posture:{evidence.posture.value}",
            f"support:{evidence.support.value}",
            f"contact:{evidence.contact.value}",
        )
        candidate = NavMapStateV1(
            state_id=_POSTURE_SUPPORT_STATE_ID_V1,
            source_map_ref=evidence.source_map_ref,
            owner_circuit=_POSTURE_SUPPORT_OWNER_V1,
            posture=evidence.posture,
            support=evidence.support,
            contact=evidence.contact,
            active_element_ids=evidence.active_element_ids,
            active_relation_labels=active_relations,
            activation=activation,
            evidence_current=evidence.evidence_current,
            sampled_event_cycle=sampled_event_cycle,
            available_cycle=available_cycle,
            applied_cycle=applied_cycle,
            last_supported_cycle=last_supported_cycle,
            validity=CircuitValidityV1.VALID,
            update_count=1,
            equivalent_refresh_count=0,
            configuration_change_count=0,
        )
        if existing is not None:
            same_content = candidate.semantic_key() == existing.semantic_key()
            candidate = NavMapStateV1(
                state_id=existing.state_id,
                source_map_ref=candidate.source_map_ref,
                owner_circuit=candidate.owner_circuit,
                posture=candidate.posture,
                support=candidate.support,
                contact=candidate.contact,
                active_element_ids=candidate.active_element_ids,
                active_relation_labels=candidate.active_relation_labels,
                activation=candidate.activation,
                evidence_current=candidate.evidence_current,
                sampled_event_cycle=candidate.sampled_event_cycle,
                available_cycle=candidate.available_cycle,
                applied_cycle=candidate.applied_cycle,
                last_supported_cycle=candidate.last_supported_cycle,
                validity=candidate.validity,
                update_count=existing.update_count + 1,
                equivalent_refresh_count=existing.equivalent_refresh_count + int(same_content),
                configuration_change_count=existing.configuration_change_count + int(not same_content),
            )

        self._current_states[NCA8_POSTURE_SUPPORT_MAP_ID_V1] = candidate
        return candidate


    def update_motor_current_state(self, configuration: MotorSupportConfigurationV1) -> NavMapStateV1:
        """Publish the enhanced facet in the existing current-source slot.

        The legacy coarse profile is deliberately UNKNOWN, not inferred from a
        desired task or selected by a posture label. Its cycle fields describe
        publication of that UNKNOWN compatibility slot, not a physical event.
        Only the enhanced facet carries the measured physical times and geometry.
        No v1 support packet or durable seed is changed. The caller is the source
        owner and supplies an already validated, eligible focal projection.
        """
        if not isinstance(configuration, MotorSupportConfigurationV1):
            raise TypeError("configuration must be MotorSupportConfigurationV1")
        if configuration.source_map_ref != self.posture_support_ref:
            raise ValueError("motor facet must reference this POSTURE-SUPPORT source")
        previous = self.current_state()
        cycle = configuration.applied_cycle
        if previous is not None and cycle <= previous.applied_cycle:
            raise ValueError("source publication cycles must increase")
        candidate = NavMapStateV1(
            state_id=_POSTURE_SUPPORT_STATE_ID_V1, source_map_ref=self.posture_support_ref,
            owner_circuit=_POSTURE_SUPPORT_OWNER_V1, posture=Nca8PostureStateV1.UNKNOWN,
            support=Nca8SupportStateV1.UNKNOWN, contact=Nca8ContactStateV1.UNKNOWN,
            active_element_ids=(), active_relation_labels=("body:measured_planar", "support:measured_relations"),
            activation=1.0 if configuration.current else 0.0, evidence_current=False,
            sampled_event_cycle=cycle, available_cycle=cycle, applied_cycle=cycle, last_supported_cycle=None,
            validity=CircuitValidityV1.VALID, update_count=1, equivalent_refresh_count=0,
            configuration_change_count=0, motor_support=configuration,
        )
        if previous is not None:
            equal = previous.semantic_key() == candidate.semantic_key()
            candidate = replace(
                candidate, update_count=previous.update_count + 1,
                equivalent_refresh_count=previous.equivalent_refresh_count + int(equal),
                configuration_change_count=previous.configuration_change_count + int(not equal),
            )
        self._current_states[NCA8_POSTURE_SUPPORT_MAP_ID_V1] = candidate
        return candidate


def create_posture_support_map_library_v1() -> Nca8MapLibraryV1:
    """Construct one unshared owner containing the first developmental map seed."""
    return Nca8MapLibraryV1(build_posture_support_seed_v1())
