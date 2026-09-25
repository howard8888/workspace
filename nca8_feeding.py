#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One feeding-detail source with optional paired oral evidence and task relevance.

A fixed association seed relates two DISTINCT observed region handles. The
maternal owner supports the parent; the existing visual owner supplies the
feeding category and independent detail localization. A geometric consistency
check can reject that declared part relation. It cannot discover an unseen
nipple from the maternal overview, create contact, or report milk.

The source can nominate its current configuration to ordinary Attention. No
operation is selected here. The opt-in P16-2C-C task consumes a same-acquisition
mouth/detail relation and may retain one finite source-relevance request. The
source does not own a PNM, target, executor, interoceptive learner or durable change. Missing detail
immediately loses current localization/access; this first profile supplies no
feeding-specific continuity model. Old immutable views keep their old times.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import (
    NavElementV1, NavFrameV1, NavGeometryKindV1, NavGeometryV1, NavMapRefV1,
    NavMapV2, NavPointV1, NavProvenanceV1, NavRelationV1, NavSourceClassV1,
)
from nca8_contracts import CircuitValidityV1
from nca8_maternal import MaternalNavMapStateV1
from nca8_visual import VisualDetectionV1

if TYPE_CHECKING:
    from nca8_seek_attention import SeekingOutcomeAttentionV1
    from nca8_suckle_attention import SuckleOutcomeAttentionV1
    from nca8_suckle_extraction_attention import SuckleExtractionAttentionV1
    from nca8_seek_learning import SeekingLearningHookV1
    from nca8_suckle_learning import SuckleLearningHookV1

__version__ = "0.9.0"
__all__ = [
    "FeedingDetailSeedV1", "FeedingDetailProfileV1", "FeedingDetailNavMapStateV1",
    "FeedingDetailCandidateV1", "FeedingDetailSourceV1", "__version__",
]

_FEEDING_REF = NavMapRefV1("feeding_detail", 1)


@dataclass(frozen=True, slots=True)
class FeedingDetailSeedV1:
    """Declare initial part correspondence, not learned nipple recognition.

    The opaque parent/detail handles must differ. A category alone does not
    establish the association: current maternal support and compatible measured
    parent/detail geometry are also required. Distances are metres in the
    shared horizontal scene; these small bounds are an engineering scaffold,
    not goat anatomy or a general object-part recognition algorithm.
    """

    parent_region_id: str = "region_1"
    detail_region_id: str = "region_2"
    maximum_parent_distance: float = 0.3
    maximum_self_distance: float = 0.65

    def __post_init__(self) -> None:
        VisualDetectionV1(self.parent_region_id, "object", None)
        VisualDetectionV1(self.detail_region_id, "feeding", None)
        if self.parent_region_id == self.detail_region_id:
            raise ValueError("maternal overview and feeding detail require distinct region handles")
        for name in ("maximum_parent_distance", "maximum_self_distance"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 2.0 or not math.isfinite(value):
                raise ValueError(f"{name} requires a finite distance in (0, 2] metres")
            object.__setattr__(self, name, float(value))

    def as_dict(self) -> dict[str, object]:
        """Describe the supplied recognition/correspondence assumptions explicitly."""
        return {"parent_region_id": self.parent_region_id, "detail_region_id": self.detail_region_id,
                "detail_descriptor": "feeding", "maximum_parent_distance": self.maximum_parent_distance,
                "maximum_self_distance": self.maximum_self_distance,
                "origin": "declared_initial_part_association", "learned_identity": False}


@dataclass(frozen=True, slots=True)
class FeedingDetailProfileV1:
    """Opt in to source maintenance and separately controllable focal nomination.

    feeding_need is a supplied developmental condition held fixed for this
    experiment, not an inferred hunger level or a benchmark-stage flag. Turning
    off nomination or this condition preserves the represented sensory detail.
    It never disables BodyMap protection or modifies the maternal operation.
    """

    seed: FeedingDetailSeedV1 = FeedingDetailSeedV1()
    source_enabled: bool = True
    attention_enabled: bool = True
    feeding_need: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.seed, FeedingDetailSeedV1):
            raise TypeError("feeding detail requires its declared association seed")
        if not all(isinstance(flag, bool) for flag in (self.source_enabled, self.attention_enabled, self.feeding_need)):
            raise TypeError("feeding-detail profile switches must be Boolean")

    def as_dict(self) -> dict[str, object]:
        """Export fixed conditions without claiming physiological acquisition."""
        return {"seed": self.seed.as_dict(), "source_enabled": self.source_enabled,
                "attention_enabled": self.attention_enabled, "feeding_need": self.feeding_need,
                "need_origin": "supplied_developmental_condition", "feeding_motor_authority": False}


def _build_seed(seed: FeedingDetailSeedV1) -> NavMapV2:
    """Build one bounded relational substrate; template points are not observations."""
    provenance = NavProvenanceV1(NavSourceClassV1.UNKNOWN, "nca8:feeding:initial_part_association_scaffold", 1.0)
    elements = tuple(
        NavElementV1(name, role, NavGeometryV1(NavGeometryKindV1.POINT, (NavPointV1(x, 0),)), (), None, provenance)
        for name, role, x in (("parent_template", "maternal_parent_template", 0), ("detail_template", "feeding_part_template", 1))
    )
    return NavMapV2(_FEEDING_REF.map_id, _FEEDING_REF.revision, "feeding_detail_association",
                    NavFrameV1("feeding_template_v1", "scene_x", "scene_y", "metres", -10000, 10000, -10000, 10000),
                    provenance, elements=elements,
                    relations=(NavRelationV1(f"part:{seed.detail_region_id}:{seed.parent_region_id}",
                                             "detail_template", "parent_template", provenance),))


@dataclass(frozen=True, slots=True)
class FeedingDetailNavMapStateV1:
    """Immutable current detail, linked to the original maternal/visual acquisition.

    Derived properties keep recognition, localization, current part association
    and near-space relevance separate. No caller can insert a desired point or
    'found' status: each comes from this immutable evidence. The maternal and
    feeding sources refer to the same visual occurrence, not independent sensors
    or two active WNMs. There is no current-position fallback to the seed.
    """

    maternal: MaternalNavMapStateV1
    seed: FeedingDetailSeedV1
    enabled: bool = True
    oral_feedback: MotorFeedbackV1 | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.maternal, MaternalNavMapStateV1) or not isinstance(self.seed, FeedingDetailSeedV1):
            raise TypeError("feeding detail requires a typed original maternal basis and seed")
        if not isinstance(self.enabled, bool):
            raise TypeError("source enablement must be Boolean")
        if self.oral_feedback is not None:
            if not isinstance(self.oral_feedback, MotorFeedbackV1):
                raise TypeError("oral source evidence must be canonical motor feedback")
            self.oral_feedback.validate_available(stream=self.stream, at_tick=self.cutoff_tick)

    @property
    def stream(self) -> MotorStreamRefV1:
        """Keep the acquisition's stream/generation, not a newly generated identity."""
        return self.maternal.stream

    @property
    def source_map_ref(self) -> NavMapRefV1:
        """Identify this enduring source separately from the maternal overview."""
        return _FEEDING_REF

    @property
    def state_id(self) -> str:
        """Name one current slot; a new sample does not create another durable map."""
        return "feeding_detail:current"

    @property
    def owner_circuit(self) -> str:
        """Name the part-association responsibility, not a second executive."""
        return "feeding_association"

    @property
    def applied_cycle(self) -> int:
        """Use the current C boundary shared with the input source."""
        return self.maternal.applied_cycle

    @property
    def cutoff_tick(self) -> int:
        """Keep the frozen lower-time cutoff; a read cannot advance it."""
        return self.maternal.cutoff_tick

    @property
    def frame_id(self) -> str | None:
        """Expose the actual horizontal scene frame, not a body target frame."""
        return self.maternal.frame_id

    @property
    def recognition_status(self) -> str:
        """Recognize only the separately supplied feeding category contribution."""
        visual = self.maternal.visual
        if not self.enabled or not visual.evidence_current:
            return "unavailable"
        descriptor = next((item.descriptor for item in visual.recognition if item.region_id == self.seed.detail_region_id), None)
        return "unavailable" if descriptor is None else "supported" if descriptor == "feeding" else "contradicted"

    @property
    def detail_position(self) -> NavPointV1 | None:
        """Read independent current localization, even when identity is uncertain.

        A located region with a wrong category remains located, but its part
        association is rejected and it cannot obtain a feeding source bid.
        Missing vision or a disabled source supplies no current detail point.
        """
        visual = self.maternal.visual
        if not self.enabled or not visual.evidence_current:
            return None
        return next((item.position for item in visual.guidance if item.region_id == self.seed.detail_region_id), None)

    @property
    def parent_distance(self) -> float | None:
        """Compute part geometry only when both observed points are available."""
        point, parent = self.detail_position, self.maternal.target_position
        if point is None or parent is None:
            return None
        return math.hypot(point.x - parent.x, point.y - parent.y)

    @property
    def self_distance(self) -> float | None:
        """Compute the observed SELF/detail separation, not oral reach or contact."""
        point, body = self.detail_position, self.maternal.self_position
        if point is None or body is None:
            return None
        return math.hypot(point.x - body.x, point.y - body.y)

    @property
    def association_status(self) -> str:
        """Preserve missingness, contradiction, and compatible part evidence."""
        if not self.enabled:
            return "disabled"
        if not self.maternal.visual.evidence_current:
            return "visual_unavailable"
        if self.seed.parent_region_id != self.maternal.seed.region_id:
            return "parent_seed_mismatch"
        if not self.maternal.evidence_current:
            return "maternal_unavailable"
        if self.recognition_status == "contradicted":
            return "detail_category_contradicted"
        if self.recognition_status != "supported":
            return "detail_unrecognized"
        if self.detail_position is None:
            return "detail_unlocalized"
        distance = self.parent_distance
        if distance is None:
            return "parent_unlocalized"
        if distance > self.seed.maximum_parent_distance + 1e-12:
            return "part_geometry_contradicted"
        return "compatible"

    @property
    def focal_accessible(self) -> bool:
        """Permit this initial detail view only with current, nearby part evidence.

        This conservative first-slice rule does not implement general uncertain
        object-part inspection. BodyMap still owns any eventual motor permission.
        """
        distance = self.self_distance
        return self.association_status == "compatible" and distance is not None and distance <= self.seed.maximum_self_distance + 1e-12

    @property
    def oral_evidence_current(self) -> bool:
        """Pair the actual body/visual occurrence, never fill gaps from a prediction.

        P16-2C-C opts in to this derived cortical relation. The original body
        acquisition remains independently available to protected BodyMap. The
        same sample/event/frame and SELF position must agree; mere arrival in
        one focal cycle cannot fuse unrelated acquisitions into current truth.
        Unpaired evidence is unusable. A paired acquisition can still have an
        unknown oral channel; derived properties preserve that missingness.
        """
        body, visual = self.oral_feedback, self.maternal.visual
        if not self.focal_accessible or body is None or self.cutoff_tick - body.event_tick > 2:
            return False
        planar = body.planar
        if planar is None or planar.position is None or planar.heading_degrees is None or body.oral is None:
            return False
        return (body.sample_id == visual.sample_id and body.event_tick == visual.event_tick
                and planar.frame_id == visual.frame_id and visual.self_position is not None
                and planar.position == (visual.self_position.x, visual.self_position.y))

    @property
    def mouth_position(self) -> NavPointV1 | None:
        """Express the observed one-axis oral tip in the source's scene coordinates.

        This is an explicit aggregate body model, not inferred head anatomy.
        Missing reach or heading cannot be replaced by a desired target. The
        transform uses only paired admitted sensing, not the physical provider.
        """
        body = self.oral_feedback
        if not self.oral_evidence_current or body is None or body.planar is None or body.oral is None:
            return None
        position, heading, reach = body.planar.position, body.planar.heading_degrees, body.oral.extension_metres
        if position is None or heading is None or reach is None:
            return None
        angle = math.radians(heading)
        return NavPointV1(position[0] + reach * math.cos(angle), position[1] + reach * math.sin(angle))

    @property
    def mouth_detail_distance(self) -> float | None:
        """Measure current mouth/detail geometry independently of tactile contact."""
        mouth, detail = self.mouth_position, self.detail_position
        return None if mouth is None or detail is None else math.hypot(detail.x - mouth.x, detail.y - mouth.y)

    @property
    def oral_contact(self) -> bool | None:
        """Retain valid touch, valid no-touch and unavailable touch as three states."""
        body = self.oral_feedback
        return body.oral.contact if self.oral_evidence_current and body is not None and body.oral is not None else None

    @property
    def contact_correspondence_status(self) -> str:
        """Compare current touch with the independently represented detail location.

        Compatible means touch at a mouth position within 0.005 metres of the
        represented detail, not independently sensed surface identity. Generic
        touch elsewhere cannot be called feeding contact. No past sample is
        accumulated, and no geometric endpoint manufactures a tactile report.
        """
        if not self.oral_evidence_current:
            return "unavailable"
        contact = self.oral_contact
        if contact is None:
            return "touch_unknown"
        if not contact:
            return "no_touch"
        distance = self.mouth_detail_distance
        if distance is None:
            return "location_unknown"
        return "compatible" if distance <= 0.005 + 1e-12 else "touch_elsewhere"

    @property
    def oral_sealed(self) -> bool | None:
        """Expose the paired measured seal without inferring it from closure or PNM."""
        body = self.oral_feedback
        if not self.oral_evidence_current or body is None or body.oral_seal is None:
            return None
        return body.oral_seal.sealed

    @property
    def seal_correspondence_status(self) -> str:
        """Relate seal sensing to contact evidence; this is not a latch task verdict.

        Unknown seal remains unknown even with known closure and touch. A seal
        sensor contradicting known no-touch is explicitly inconsistent. Current
        compatible location is required; a missing visual product cannot borrow
        a past source configuration as current truth.
        """
        body = self.oral_feedback
        if body is None or body.oral_seal is None:
            return "not_supplied"
        if not self.oral_evidence_current:
            return "unavailable"
        if self.oral_sealed is None:
            return "seal_unknown"
        if not self.oral_sealed:
            return "no_seal"
        contact_status = self.contact_correspondence_status
        if contact_status == "no_touch":
            return "inconsistent_touch_and_seal"
        return "compatible" if contact_status == "compatible" else "seal_unlocalized"

    @property
    def validity(self) -> CircuitValidityV1:
        """Mark unavailable visual evidence as stale; never refresh its timestamp."""
        return self.maternal.visual.validity if self.enabled else CircuitValidityV1.STALE

    @property
    def activation(self) -> float:
        """Supply a fixed activation scaffold independently from nomination."""
        return 0.6 if self.focal_accessible else 0.0

    @property
    def active_relation_labels(self) -> tuple[str, ...]:
        """Describe evidence without emitting a found/latch/milk milestone."""
        return (f"feeding:recognition:{self.recognition_status}",
                "feeding:detail_localized" if self.detail_position is not None else "feeding:detail_location_unknown",
                f"feeding:part_relation:{self.association_status}",
                "feeding:near_detail" if self.focal_accessible else "feeding:detail_not_available_for_focus")

    def as_dict(self) -> dict[str, object]:
        """Detach the source and original-evidence links; export confers no rights."""
        visual, point = self.maternal.visual, self.detail_position
        return {"state_id": self.state_id, "source_map_ref": self.source_map_ref.as_dict(), "owner_circuit": self.owner_circuit,
                "stream": self.stream.as_dict(), "applied_cycle": self.applied_cycle, "cutoff_tick": self.cutoff_tick,
                "frame_id": self.frame_id, "units": "metres", "seed": self.seed.as_dict(), "enabled": self.enabled,
                "maternal_source_ref": self.maternal.source_map_ref.as_dict(),
                "visual_source_ref": visual.source_map_ref.as_dict(), "sample_id": visual.sample_id,
                "event_tick": visual.event_tick, "available_tick": visual.available_tick,
                "recognition_status": self.recognition_status, "detail_position": None if point is None else point.as_dict(),
                "parent_distance": self.parent_distance, "self_distance": self.self_distance,
                "association_status": self.association_status, "focal_accessible": self.focal_accessible,
                "active_relation_labels": list(self.active_relation_labels), "feeding_motor_authority": False,
                "contact_evidence": "not_supplied" if self.oral_feedback is None else self.oral_contact,
                "latch_evidence": "not_supplied", "milk_evidence": "not_supplied", "durable_learning_updates": 0,
                **({"oral_relation": {"body_acquisition": self.oral_feedback.as_dict(),
                                      "paired_current": self.oral_evidence_current,
                                      "mouth_position": None if self.mouth_position is None else self.mouth_position.as_dict(),
                                      "mouth_detail_distance_metres": self.mouth_detail_distance,
                                      "contact": self.oral_contact, "contact_identifies_surface": False}}
                   if self.oral_feedback is not None else {}),
                **({"seal_relation": {"contact_correspondence": self.contact_correspondence_status,
                                      "sealed": self.oral_sealed, "correspondence": self.seal_correspondence_status,
                                      "establishes_surface_identity": False, "establishes_latch_task": False,
                                      "establishes_nourishment": False}}
                   if self.oral_feedback is not None and self.oral_feedback.oral_seal is not None else {})}


@dataclass(frozen=True, slots=True)
class FeedingDetailCandidateV1:
    """Nominate current detail without selecting SeekNipple or ending another task.

    The ordinary need rank equals maternal relevance. Existing maternal task
    persistence wins before the activation tie-break; a current support need has
    a higher ordinary need rank. The fixed rank is an inspectable initial profile,
    not acquired salience or a general safety-priority solution.
    """

    source_map_state: FeedingDetailNavMapStateV1
    current_task_persistence_rank: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_state, FeedingDetailNavMapStateV1) or not self.source_map_state.focal_accessible:
            raise ValueError("feeding nomination needs current nearby compatible part evidence")
        if (isinstance(self.current_task_persistence_rank, bool) or not isinstance(self.current_task_persistence_rank, int)
                or self.current_task_persistence_rank not in (0, 20)):
            raise ValueError("feeding persistence uses only the declared zero/twenty ranks")

    candidate_id = "source:feeding_detail"
    protected_safety_rank = 0
    new_task_need_rank = 10
    prediction_or_envelope_failure_rank = 0
    novelty_or_ambiguity_rank = 0
    activation_rank = 60
    safety_escalation = False
    stable_tie_key = "feeding_detail"
    reason = "current_feeding_detail_with_supplied_developmental_need"

    @property
    def published_cycle(self) -> int:
        """Bind the nomination to this source's actual C opportunity."""
        return self.source_map_state.applied_cycle


class FeedingDetailSourceV1:
    """Maintain one part-association source and publish its bounded nomination.

    The owner retains one current immutable basis and one durable seed. Updating
    it is source maintenance, not a second focal task. No history or counters
    stand in for finding, contact or nourishment. Reset creates a fresh owner.
    """

    def __init__(self, stream: MotorStreamRefV1, profile: FeedingDetailProfileV1) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(profile, FeedingDetailProfileV1):
            raise TypeError("feeding source requires a stream and explicit profile")
        self._stream, self._profile = stream, profile
        self._durable = _build_seed(profile.seed)
        self._current: FeedingDetailNavMapStateV1 | None = None
        self._influence: tuple[str, int] | None = None
        self._outcome_attention: SeekingOutcomeAttentionV1 | None = None
        self._suckle_outcome_attention: SuckleOutcomeAttentionV1 | None = None
        self._extraction_outcome_attention: SuckleExtractionAttentionV1 | None = None
        self._learning_hook: SeekingLearningHookV1 | None = None
        self._suckle_learning_hook: SuckleLearningHookV1 | None = None

    @property
    def outcome_attention(self) -> SeekingOutcomeAttentionV1 | None:
        """Read the optional source-owned relevance extension, not a second focus."""
        return self._outcome_attention

    def configure_outcome_attention(self) -> None:
        """Attach the fixed seeking relevance profile once, before source processing.

        The late import follows the existing maternal ownership boundary: the
        source schema does not import executive work at module initialization.
        Configuration changes no sensory fact, durable map or actuator right.
        Reset constructs a new source; core stopping closes its old extension.
        """
        if self._current is not None or self._outcome_attention is not None:
            raise RuntimeError("configure seeking relevance only once before source updates")
        import nca8_seek_attention  # pylint: disable=import-outside-toplevel
        self._outcome_attention = nca8_seek_attention.SeekingOutcomeAttentionV1(self._stream, self._profile.seed)

    @property
    def extraction_outcome_attention(self) -> SuckleExtractionAttentionV1 | None:
        """Read L-E's bounded question owner, not an IP or a new executive."""
        return self._extraction_outcome_attention

    def configure_extraction_outcome_attention(self, *, diagnostic_capacity: int = 8) -> None:
        """Attach one historical-extraction route before processing this generation.

        The local import retains the existing source-schema/executive boundary.
        No source fact, original task lifetime, motor right or learner is changed.
        """
        if self._current is not None or self._extraction_outcome_attention is not None:
            raise RuntimeError("configure extraction relevance once before source updates")
        import nca8_suckle_extraction_attention  # pylint: disable=import-outside-toplevel
        self._extraction_outcome_attention = nca8_suckle_extraction_attention.SuckleExtractionAttentionV1(
            self._stream, self._profile.seed, diagnostic_capacity=diagnostic_capacity,
        )

    @property
    def suckle_outcome_attention(self) -> SuckleOutcomeAttentionV1 | None:
        """Read J's optional question owner; it has no focal or motor authority."""
        return self._suckle_outcome_attention

    def configure_suckle_outcome_attention(self) -> None:
        """Attach one J relevance owner before processing this source generation.

        The late import preserves the source-schema/executive dependency boundary.
        Configuration creates no sensory fact, new map, IP or motor permission.
        Reset constructs a fresh source and therefore a fresh bounded question owner.
        """
        if self._current is not None or self._suckle_outcome_attention is not None:
            raise RuntimeError("configure Suckle relevance once before source updates")
        import nca8_suckle_attention  # pylint: disable=import-outside-toplevel
        self._suckle_outcome_attention = nca8_suckle_attention.SuckleOutcomeAttentionV1(self._stream, self._profile.seed)

    @property
    def learning_hook(self) -> SeekingLearningHookV1 | None:
        """Read this source's optional participation owner, not a durable learner."""
        return self._learning_hook

    def configure_learning_hook(self, *, diagnostic_capacity: int = 32) -> None:
        """Attach bounded no-learning participation once, before source processing.

        Configuration has no sensory, focal, physical or learned effect. The
        real F callback is its consumer; only original selected seeking can
        register participation. Reset/stop closes the old extension. The late
        import preserves the existing source-schema/executive import boundary.
        """
        if self._current is not None or self._learning_hook is not None:
            raise RuntimeError("configure seeking participation only once before source updates")
        import nca8_seek_learning  # pylint: disable=import-outside-toplevel
        self._learning_hook = nca8_seek_learning.SeekingLearningHookV1(
            self._stream, self._profile.seed, diagnostic_capacity=diagnostic_capacity,
        )

    @property
    def suckle_learning_hook(self) -> SuckleLearningHookV1 | None:
        """Read K's original Suckle recipient, distinct from seeking and J questions."""
        return self._suckle_learning_hook

    def configure_suckle_learning_hook(self, *, diagnostic_capacity: int = 32) -> None:
        """Attach one no-durable-learning Suckle hook before source processing.

        This owner holds bounded participation in original selected applications.
        Configuration changes no evidence, focal allocation, task or body permission.
        The late import preserves the existing source schema's dependency direction.
        Failed configuration leaves this optional owner absent; reset creates a new
        source generation and stop closes the old hook without replaying evidence.
        """
        if self._current is not None or self._suckle_learning_hook is not None:
            raise RuntimeError("configure Suckle participation once before source updates")
        import nca8_suckle_learning  # pylint: disable=import-outside-toplevel
        self._suckle_learning_hook = nca8_suckle_learning.SuckleLearningHookV1(
            self._stream, self._profile.seed, diagnostic_capacity=diagnostic_capacity,
        )

    @property
    def profile(self) -> FeedingDetailProfileV1:
        """Read fixed experiment conditions; reading does not change eligibility."""
        return self._profile

    @property
    def durable_map(self) -> NavMapV2:
        """Read the unlearned seed without treating current refreshes as revisions."""
        return self._durable

    @property
    def current(self) -> FeedingDetailNavMapStateV1 | None:
        """Read the current slot, including an explicit unavailable configuration."""
        return self._current

    def update(
        self, maternal: MaternalNavMapStateV1, *, oral_feedback: MotorFeedbackV1 | None = None,
    ) -> FeedingDetailNavMapStateV1:
        """Apply one already-frozen maternal/visual basis atomically before Attention.

        Foreign generations and repeated/reordered source opportunities are
        rejected before mutation. A known wrong category/geometry is ordinary
        contradictory evidence, not a transport exception or a desired repair.
        """
        if not isinstance(maternal, MaternalNavMapStateV1) or maternal.stream != self._stream:
            raise ValueError("feeding detail requires its own generation's maternal basis")
        previous = self._current
        if previous is not None and (maternal.applied_cycle <= previous.applied_cycle or maternal.cutoff_tick <= previous.cutoff_tick):
            raise ValueError("feeding updates must advance focal and physical cutoffs")
        current = FeedingDetailNavMapStateV1(maternal, self._profile.seed, self._profile.source_enabled, oral_feedback=oral_feedback)
        self._current = current
        if self._influence is not None and current.cutoff_tick >= self._influence[1]:
            self._influence = None
        return current

    def candidate(self) -> FeedingDetailCandidateV1 | None:
        """Request focal consideration only; no source read renews task/motor rights."""
        current = self._current
        if current is None or not current.focal_accessible or not self._profile.attention_enabled or not self._profile.feeding_need:
            return None
        rank = 20 if self._influence is not None and current.cutoff_tick < self._influence[1] else 0
        return FeedingDetailCandidateV1(current, rank)

    def retain_influence(self, task_id: str, *, cycle_id: int, expires_at_tick: int) -> None:
        """Retain one selected-task relevance request for at most eight physical ticks.

        This changes only the source's ordinary persistence rank. It does not
        renew sensory support, revive unavailable detail, select an IP or grant
        a motor lease. P16-2C-A/B never call this optional task-owner seam.
        """
        current = self._current
        if not isinstance(task_id, str) or not 1 <= len(task_id) <= 100 or not task_id.isascii() or not task_id.isprintable() or task_id.strip() != task_id:
            raise ValueError("feeding influence requires a bounded task identity")
        if (current is None or not current.focal_accessible or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or cycle_id != current.applied_cycle):
            raise ValueError("feeding influence requires this current source opportunity")
        if (isinstance(expires_at_tick, bool) or not isinstance(expires_at_tick, int)
                or not current.cutoff_tick < expires_at_tick <= current.cutoff_tick + 8):
            raise ValueError("feeding influence cannot extend beyond eight physical ticks")
        self._influence = (task_id, expires_at_tick)

    def clear_influence(self, *, task_id: str | None = None) -> None:
        """Release relevance without deleting source content or another task's request.

        An omitted identity retains the original explicit clear-all API. Task
        owners pass their own identity: completed seeking must not erase a later
        selected Suckle influence. No clear grants a new bid or motor lease.
        """
        if task_id is not None and (not isinstance(task_id, str) or not task_id):
            raise ValueError("influence release requires a nonempty task identity")
        if task_id is None or self._influence is not None and self._influence[0] == task_id:
            self._influence = None

    def retained_counts(self) -> dict[str, int]:
        """Report measured owner storage, independent of observer history capacity."""
        return {"durable_maps": 1, "current_configurations": int(self._current is not None),
                **({"task_influences": 1} if self._influence is not None else {})}
