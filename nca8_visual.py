#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded visual source and independent recognition/guidance for P16-2A-A.

The input is an admitted structured surface, not pixels or private world state.
Provider region handles and category labels are declared recognition scaffolds;
this owner does not learn identity or interpret a handle as a maternal relation.
Current points and SELF-to-region displacements live outside the enduring seeded
NavMap. Suppressing recognition preserves geometry, and suppressing geometry
preserves recognition. Neither stream chooses WNM, a task, or a motor target.

Times are the existing integer lower ticks plus the separately supplied focal
cycle. One immutable acquisition is retained for ordering; a reread never makes
it younger. Missing input clears current access without erasing that watermark.
There is no extrapolation, Ready set, durable learning, or autonomous clock.
"""

# The visual acquisition and planar-body records intentionally share the
# canonical stream/sample/event/availability/frame identity header.
# Keeping the domain contracts separate is clearer than inheritance solely
# to satisfy Pylint's cross-module similarity heuristic.
# pylint: disable=duplicate-code

from __future__ import annotations

from dataclasses import dataclass

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import (
    NavElementV1, NavFrameV1, NavGeometryKindV1, NavGeometryV1, NavMapRefV1,
    NavMapV2, NavPointV1, NavProvenanceV1, NavRelationV1, NavSourceClassV1,
)
from nca8_contracts import CircuitValidityV1

__version__ = "0.1.0"
__all__ = [
    "VisualDetectionV1", "VisualObservationV1", "VisualRecognitionV1", "VisualGuidanceV1",
    "VisualNavMapStateV1", "VisualAttentionCandidateV1", "VisualSourceV1",
    "build_visual_seed_v1", "__version__",
]

_MAX_TICK = 2**63 - 1
_MAX_REGIONS = 8
_COORDINATE_LIMIT = 10000.0
_DESCRIPTORS = frozenset({"object", "landmark", "hazard", "social", "feeding"})


def _index(value: int, name: str, minimum: int = 0) -> int:
    """Validate bounded tick/sample identities without accepting Boolean counters."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= _MAX_TICK:
        raise ValueError(f"{name} must be a bounded integer >= {minimum}")
    return value


def _name(value: str, name: str) -> str:
    """Validate a short opaque handle without converting it to task semantics."""
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 80:
        raise ValueError(f"{name} must be 1-80 unpadded characters")
    if any(not (char.isascii() and (char.isalnum() or char in "_:.-/")) for char in value):
        raise ValueError(f"{name} contains unsupported characters")
    return value


def _point(value: NavPointV1 | None) -> None:
    """Check the declared metre-coordinate envelope; None stays unknown."""
    if value is not None:
        if not isinstance(value, NavPointV1):
            raise TypeError("position must be NavPointV1 or None")
        if max(abs(value.x), abs(value.y)) > _COORDINATE_LIMIT:
            raise ValueError("position exceeds the declared 10000-metre frame bounds")


def _frame(value: str) -> str:
    """Require an explicitly named horizontal scene frame, never the old body label."""
    _name(value, "frame_id")
    if not value.startswith("scene_xy:") or len(value) == len("scene_xy:"):
        raise ValueError("frame_id requires an explicit scene_xy: basis in metres")
    return value


@dataclass(frozen=True, slots=True)
class VisualDetectionV1:
    """One supplied region handle, optional category and optional localization.

    A category is a provider interpretation, not learned CCA recognition. A point
    is the declared point-localization surrogate, not a confidence distribution.
    Unknown location can coexist with a known category and vice versa.
    """

    region_id: str
    descriptor: str | None
    position: NavPointV1 | None

    def __post_init__(self) -> None:
        _name(self.region_id, "region_id")
        if self.descriptor is not None and self.descriptor not in _DESCRIPTORS:
            raise ValueError("descriptor is outside the declared recognition scaffold")
        _point(self.position)

    def as_dict(self) -> dict[str, object]:
        """Export only the represented acquisition, with no live owner reference."""
        return {"region_id": self.region_id, "descriptor": self.descriptor,
                "position": None if self.position is None else self.position.as_dict()}


@dataclass(frozen=True, slots=True)
class VisualObservationV1:
    """Canonical visual input after the existing surface-grid whitelist.

    The transport supplies stream/generation, sample identity, represented event
    and first availability. The adapter verifies event_tick against the original
    observation step_index; neither time is inferred from a later polling call.
    A valid empty acquisition is not a missing packet or proof of object absence.
    Frames are explicitly horizontal, right-handed XY coordinates in metres.
    """

    stream: MotorStreamRefV1
    sample_id: int
    event_tick: int
    available_tick: int
    frame_id: str
    self_position: NavPointV1 | None
    detections: tuple[VisualDetectionV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("visual acquisition requires a motor-stream generation")
        _index(self.sample_id, "sample_id", 1)
        _index(self.event_tick, "event_tick")
        _index(self.available_tick, "available_tick", self.event_tick)
        _frame(self.frame_id)
        _point(self.self_position)
        if not isinstance(self.detections, tuple) or len(self.detections) > _MAX_REGIONS:
            raise ValueError("visual acquisition holds at most eight immutable detections")
        if any(not isinstance(item, VisualDetectionV1) for item in self.detections):
            raise TypeError("detections must be VisualDetectionV1")
        if len({item.region_id for item in self.detections}) != len(self.detections):
            raise ValueError("region handles must be unique within the acquisition")
        object.__setattr__(self, "detections", tuple(sorted(self.detections, key=lambda item: item.region_id)))

    def validate_available(self, *, stream: MotorStreamRefV1, at_tick: int) -> None:
        """Reject foreign/future input before any consumer changes state."""
        _index(at_tick, "at_tick")
        if self.stream != stream or self.available_tick > at_tick:
            raise ValueError("visual acquisition is foreign or not yet available")

    def as_dict(self) -> dict[str, object]:
        """Return a detached observation description, not current-source authority."""
        return {"stream": self.stream.as_dict(), "sample_id": self.sample_id,
                "event_tick": self.event_tick, "available_tick": self.available_tick,
                "frame_id": self.frame_id, "units": "metres",
                "self_position": None if self.self_position is None else self.self_position.as_dict(),
                "detections": [item.as_dict() for item in self.detections]}


@dataclass(frozen=True, slots=True)
class VisualRecognitionV1:
    """The category stream's current contribution, not location or maternal identity."""

    region_id: str
    descriptor: str

    def __post_init__(self) -> None:
        VisualDetectionV1(self.region_id, self.descriptor, None)
        if self.descriptor is None:
            raise ValueError("a recognition contribution needs a category")

    def as_dict(self) -> dict[str, object]:
        """Label the fixed provider classification as a scaffold, not acquisition."""
        return {"region_id": self.region_id, "descriptor": self.descriptor,
                "evidence": "provider_category_scaffold", "learned_identity": False}


@dataclass(frozen=True, slots=True)
class VisualGuidanceV1:
    """A located region and optional SELF-relative displacement in the scene frame."""

    region_id: str
    position: NavPointV1
    relative_to_self: NavPointV1 | None

    def __post_init__(self) -> None:
        _name(self.region_id, "region_id")
        _point(self.position)
        if self.position is None:
            raise ValueError("guidance requires a located region")
        if self.relative_to_self is not None and not isinstance(self.relative_to_self, NavPointV1):
            raise TypeError("relative displacement must be NavPointV1 or None")

    def as_dict(self) -> dict[str, object]:
        """Describe scene geometry without conferring a bodily movement target."""
        return {"region_id": self.region_id, "position": self.position.as_dict(),
                "relative_to_self": None if self.relative_to_self is None else self.relative_to_self.as_dict(),
                "uncertainty": "structured_point_scaffold_no_noise_model"}


@dataclass(frozen=True, slots=True)
class VisualNavMapStateV1:
    """One visual source's current configuration, independent of posture fields.

    Only the common source identity, owner, application cycle and relation labels
    cross the heterogeneous Attention/WNM interface. The concrete visual payload
    remains typed and separate; no dummy posture or motor_support field is added.
    Unavailable/stale samples retain their original metadata but no current facts.
    """

    stream: MotorStreamRefV1
    source_map_ref: NavMapRefV1
    applied_cycle: int
    cutoff_tick: int
    frame_id: str | None
    sample_id: int | None
    event_tick: int | None
    available_tick: int | None
    input_status: str
    recognition_enabled: bool
    spatial_enabled: bool
    self_position: NavPointV1 | None
    recognition: tuple[VisualRecognitionV1, ...]
    guidance: tuple[VisualGuidanceV1, ...]
    update_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1) or self.source_map_ref != NavMapRefV1("visual_scene", 1):
            raise ValueError("visual state requires its declared stream and enduring visual_scene@r1")
        _index(self.applied_cycle, "applied_cycle", 1)
        _index(self.update_count, "update_count", 1)
        _index(self.cutoff_tick, "cutoff_tick")
        if self.input_status not in {"current", "reread", "missing", "stale", "unavailable_after_gap"}:
            raise ValueError("unknown visual input status")
        if not isinstance(self.recognition_enabled, bool) or not isinstance(self.spatial_enabled, bool):
            raise TypeError("visual stream switches must be Boolean")
        if self.sample_id is None:
            if any(value is not None for value in (self.event_tick, self.available_tick, self.frame_id)):
                raise ValueError("missing sample identity cannot carry partial time/frame metadata")
            if self.input_status != "missing":
                raise ValueError("only missing input can have no acquisition identity")
        else:
            _index(self.sample_id, "sample_id", 1)
            if self.event_tick is None or self.available_tick is None or self.frame_id is None:
                raise ValueError("a retained acquisition requires all original metadata")
            _index(self.event_tick, "event_tick")
            _index(self.available_tick, "available_tick", self.event_tick)
            _frame(self.frame_id)
            if self.available_tick > self.cutoff_tick:
                raise ValueError("current source cannot contain unavailable future input")
            if self.evidence_current and self.cutoff_tick - self.event_tick > 2:
                raise ValueError("stale visual input cannot be marked current")
        if not isinstance(self.recognition, tuple) or len(self.recognition) > _MAX_REGIONS:
            raise ValueError("recognition contributions must be a bounded immutable tuple")
        if any(not isinstance(item, VisualRecognitionV1) for item in self.recognition):
            raise TypeError("recognition contributions must be VisualRecognitionV1")
        if len({item.region_id for item in self.recognition}) != len(self.recognition):
            raise ValueError("recognition contribution repeats one region")
        if not isinstance(self.guidance, tuple) or len(self.guidance) > _MAX_REGIONS:
            raise ValueError("guidance contributions must be a bounded immutable tuple")
        if any(not isinstance(item, VisualGuidanceV1) for item in self.guidance):
            raise TypeError("guidance contributions must be VisualGuidanceV1")
        if len({item.region_id for item in self.guidance}) != len(self.guidance):
            raise ValueError("guidance contribution repeats one region")
        _point(self.self_position)
        if (not self.recognition_enabled or not self.evidence_current) and self.recognition:
            raise ValueError("disabled or unavailable recognition cannot expose current categories")
        if (not self.spatial_enabled or not self.evidence_current) and (self.guidance or self.self_position is not None):
            raise ValueError("disabled or unavailable guidance cannot expose current coordinates")
        for item in self.guidance:
            relative = None if self.self_position is None else NavPointV1(
                item.position.x - self.self_position.x, item.position.y - self.self_position.y,
            )
            if item.relative_to_self != relative:
                raise ValueError("guidance must preserve the actual SELF-to-region relation")

    @property
    def state_id(self) -> str:
        """Return the enduring current-slot identity, not a per-acquisition map ID."""
        return "visual_scene:current"

    @property
    def owner_circuit(self) -> str:
        """Return the visual owner, never the body-sensory owner."""
        return "visual_sensory"

    @property
    def evidence_current(self) -> bool:
        """Whether this configuration expresses an eligible observed acquisition."""
        return self.input_status in {"current", "reread"}

    @property
    def validity(self) -> CircuitValidityV1:
        """Return validity without refreshing or recovering a missing acquisition."""
        return CircuitValidityV1.VALID if self.evidence_current else CircuitValidityV1.STALE

    @property
    def active_relation_labels(self) -> tuple[str, ...]:
        """Return only visual relation labels; domain facts are never posture aliases."""
        labels = []
        if self.recognition:
            labels.append("visual:category_evidence")
        if self.guidance:
            labels.append("visual:located_regions")
        if self.self_position is not None:
            labels.append("visual:self_localized")
        return tuple(labels)

    @property
    def activation(self) -> float:
        """Fixed initial availability scaffold, not learned urgency or confidence."""
        return 0.4 if self.recognition or self.guidance else 0.0

    def as_dict(self) -> dict[str, object]:
        """Export both independent sensory products, their scope, and original times."""
        return {"state_id": self.state_id, "source_map_ref": self.source_map_ref.as_dict(),
                "owner_circuit": self.owner_circuit, "stream": self.stream.as_dict(),
                "applied_cycle": self.applied_cycle, "cutoff_tick": self.cutoff_tick,
                "frame_id": self.frame_id, "units": "metres", "sample_id": self.sample_id,
                "event_tick": self.event_tick, "available_tick": self.available_tick,
                "input_status": self.input_status, "evidence_current": self.evidence_current,
                "recognition_enabled": self.recognition_enabled, "spatial_enabled": self.spatial_enabled,
                "self_position": None if self.self_position is None else self.self_position.as_dict(),
                "recognition": [item.as_dict() for item in self.recognition],
                "guidance": [item.as_dict() for item in self.guidance],
                "active_relation_labels": list(self.active_relation_labels), "update_count": self.update_count,
                "durable_updates": 0, "selects_wnm": False, "motor_authority": False}


@dataclass(frozen=True, slots=True)
class VisualAttentionCandidateV1:
    """A source nomination for the existing selector, never a selected source/task."""

    source_map_state: VisualNavMapStateV1

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_state, VisualNavMapStateV1) or not self.source_map_state.evidence_current:
            raise ValueError("visual nomination requires current visual evidence")
        if self.source_map_state.activation == 0:
            raise ValueError("an empty visual source cannot nominate itself")

    candidate_id = "visual:scene_candidate"
    reason = "current_visual_contribution_not_task_selection"
    protected_safety_rank = 0
    new_task_need_rank = 0
    prediction_or_envelope_failure_rank = 0
    novelty_or_ambiguity_rank = 0
    current_task_persistence_rank = 0
    activation_rank = 40
    stable_tie_key = "visual_scene"

    @property
    def published_cycle(self) -> int:
        """Return the actual source application cycle for the common bid contract."""
        return self.source_map_state.applied_cycle


def build_visual_seed_v1() -> NavMapV2:
    """Build two declared relation templates, not a map of future observed objects.

    Template coordinates have no current-world authority. Current localized points
    remain in the visual owner's configuration and never rewrite these seeds.
    The kernel's existing relational representation is reused without alteration.
    """
    provenance = NavProvenanceV1(source_class=NavSourceClassV1.UNKNOWN, source_ref="nca8:visual:developmental_scaffold", quality=1.0)
    elements = tuple(NavElementV1(name, role, NavGeometryV1(NavGeometryKindV1.POINT, (NavPointV1(x, 0),)), (), None, provenance)
                     for name, role, x in (("self_template", "self_anchor_template", 0), ("region_template", "visible_region_template", 1)))
    return NavMapV2("visual_scene", 1, "visual_local_scene",
                    NavFrameV1("visual_template_v1", "scene_x", "scene_y", "metres", -10000, 10000, -10000, 10000),
                    provenance, elements=elements,
                    relations=(NavRelationV1("spatial_relation_template", "self_template", "region_template", provenance),))


class VisualSourceV1:
    """Own one enduring visual seed and one bounded current sensory configuration.

    Update accepts only canonical admitted observations. Domain switches are fixed
    for the owner lifetime. Clock/order violations fail before mutation. Missing
    data clears both present streams; an old duplicate after a gap cannot restore
    access. A fresh acquisition restores the source without recruiting a new map.
    """

    def __init__(self, stream: MotorStreamRefV1, *, recognition_enabled: bool = True, spatial_enabled: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("visual owner requires MotorStreamRefV1")
        if not isinstance(recognition_enabled, bool) or not isinstance(spatial_enabled, bool):
            raise TypeError("visual switches must be Boolean")
        self._stream = stream
        self._recognition_enabled = recognition_enabled
        self._spatial_enabled = spatial_enabled
        self._seed = build_visual_seed_v1()
        self._observation: VisualObservationV1 | None = None
        self._current: VisualNavMapStateV1 | None = None
        self._available = False

    @property
    def durable_map(self) -> NavMapV2:
        """Return the immutable seed; current samples do not revise it."""
        return self._seed

    @property
    def current(self) -> VisualNavMapStateV1 | None:
        """Read the existing current configuration without aging or refreshing it."""
        return self._current

    def candidate(self) -> VisualAttentionCandidateV1 | None:
        """Publish availability only; the external common Attention service decides."""
        current = self._current
        if current is None or not current.evidence_current or current.activation == 0:
            return None
        return VisualAttentionCandidateV1(current)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual bounded owner storage, independently of trace retention."""
        return {"durable_maps": 1, "acquisitions": int(self._observation is not None),
                "current_configurations": int(self._current is not None),
                "retained_detections": 0 if self._observation is None else len(self._observation.detections),
                "recognition_contributions": 0 if self._current is None else len(self._current.recognition),
                "guidance_contributions": 0 if self._current is None else len(self._current.guidance)}

    def update(self, observation: VisualObservationV1 | None, *, cycle_id: int, cutoff_tick: int) -> VisualNavMapStateV1:
        """Apply one already-frozen input in C, preserving its original acquisition.

        A missing packet is explicit None, not a future packet. Future/foreign,
        reused-but-changed, duplicate-event and reversed samples are rejected.
        The two-tick freshness bound is this experimental profile only; valid
        empty detections supply no precise target and no automatic source bid.
        """
        _index(cycle_id, "cycle_id", 1)
        _index(cutoff_tick, "cutoff_tick")
        if self._current is not None and (cycle_id <= self._current.applied_cycle or cutoff_tick <= self._current.cutoff_tick):
            raise ValueError("visual updates require increasing focal cycles and lower cutoffs")
        retained = self._observation
        status = "missing"
        available = False
        if observation is not None:
            if not isinstance(observation, VisualObservationV1):
                raise TypeError("visual update requires canonical input or None")
            observation.validate_available(stream=self._stream, at_tick=cutoff_tick)
            duplicate = retained is not None and observation.sample_id == retained.sample_id
            if retained is not None:
                if duplicate and observation != retained:
                    raise ValueError("visual acquisition identity was reused with changed content")
                if not duplicate and (observation.sample_id <= retained.sample_id or observation.event_tick <= retained.event_tick):
                    raise ValueError("new visual acquisition must advance sample and physical event")
            available = self._available if duplicate else True
            status = "reread" if duplicate else "current"
            if not available:
                status = "unavailable_after_gap"
            elif cutoff_tick - observation.event_tick > 2:
                status = "stale"
            retained = observation
        current_input = retained if status in {"current", "reread"} else None
        recognition: tuple[VisualRecognitionV1, ...] = ()
        guidance: tuple[VisualGuidanceV1, ...] = ()
        position: NavPointV1 | None = None
        if current_input is not None:
            if self._recognition_enabled:
                recognition = tuple(VisualRecognitionV1(item.region_id, item.descriptor)
                                    for item in current_input.detections if item.descriptor is not None)
            if self._spatial_enabled:
                position = current_input.self_position
                guidance = tuple(VisualGuidanceV1(item.region_id, item.position, None if position is None else NavPointV1(
                    item.position.x - position.x, item.position.y - position.y,
                )) for item in current_input.detections if item.position is not None)
        result = VisualNavMapStateV1(
            self._stream, NavMapRefV1("visual_scene", 1), cycle_id, cutoff_tick,
            None if retained is None else retained.frame_id, None if retained is None else retained.sample_id,
            None if retained is None else retained.event_tick, None if retained is None else retained.available_tick,
            status, self._recognition_enabled, self._spatial_enabled, position, recognition, guidance,
            1 if self._current is None else self._current.update_count + 1,
        )
        self._observation, self._current, self._available = retained, result, available
        return result
