#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One bounded MOM association source over the existing visual contributions.

The association is a declared initial scaffold, not learned maternal recognition:
its configured opaque region and category must be supported by the recognition
stream before geometry can be used. The associated map has its own enduring
identity and current SELF/target relation. It is neither a posture record nor a
second selected WNM. Current localization, retained identity, a possible region,
and activation have separate meanings. No method selects a task or drives a body.

A missing contribution retains identity and a widening possible region for eight
physical ticks from the last genuinely supported target. That region is never a
precise movement target. Contradiction immediately withdraws localization. Fresh
recognition can reacquire the same association, but rereading an earlier visual
sample after a gap cannot restore current access. All constants are engineering
profiles; no sensory learning, general object permanence or search is claimed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import (
    NavElementV1, NavFrameV1, NavGeometryKindV1, NavGeometryV1, NavMapRefV1,
    NavMapV2, NavPointV1, NavProvenanceV1, NavRelationV1, NavSourceClassV1,
)
from nca8_visual import VisualDetectionV1, VisualGuidanceV1, VisualNavMapStateV1

if TYPE_CHECKING:
    from nca8_maternal_attention import MaternalOutcomeAttentionV1

__version__ = "0.2.0"
__all__ = ["MaternalSeedV1", "MaternalNavMapStateV1", "MaternalCandidateV1", "MaternalSourceV1", "__version__"]

MOM_REF = NavMapRefV1("maternal_target", 1)
_MAX_TICK = 2**63 - 1


def _index(value: int, name: str, minimum: int = 0) -> None:
    """Reject Boolean, fractional, negative and unbounded logical identifiers."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= _MAX_TICK:
        raise ValueError(f"{name} requires a bounded integer >= {minimum}")


@dataclass(frozen=True, slots=True)
class MaternalSeedV1:
    """Pre-established association used only when recognition supplies its evidence.

    The region handle is configuration, not a provider's hidden maternal flag.
    The default object category reflects the existing idealized sensor provider;
    it does not say every object is Mom. Changing the handle changes which of the
    observed regions can activate this particular seed. Geometry alone cannot
    establish the association. Full acquisition remains a later learning task.
    """

    region_id: str = "region_1"
    descriptor: str = "object"

    def __post_init__(self) -> None:
        VisualDetectionV1(self.region_id, self.descriptor, None)
        if self.descriptor is None:
            raise ValueError("maternal association requires an explicit recognition category")

    def as_dict(self) -> dict[str, object]:
        """Expose exactly what was supplied, rather than claiming acquired identity."""
        return {"region_id": self.region_id, "descriptor": self.descriptor,
                "origin": "declared_initial_maternal_association", "learned_identity": False}


def _build_seed(seed: MaternalSeedV1) -> NavMapV2:
    """Reuse the map kernel for a relation template with no current-world position."""
    provenance = NavProvenanceV1(NavSourceClassV1.UNKNOWN, "nca8:maternal:initial_association_scaffold", 1.0)
    elements = tuple(
        NavElementV1(name, role, NavGeometryV1(NavGeometryKindV1.POINT, (NavPointV1(x, 0),)), (), None, provenance)
        for name, role, x in (("self_template", "self_anchor_template", 0), ("maternal_template", "maternal_target_template", 1))
    )
    return NavMapV2(MOM_REF.map_id, MOM_REF.revision, "maternal_association",
                    NavFrameV1("maternal_template_v1", "scene_x", "scene_y", "metres", -10000, 10000, -10000, 10000),
                    provenance, elements=elements,
                    relations=(NavRelationV1(f"association:{seed.region_id}", "self_template", "maternal_template", provenance),))


@dataclass(frozen=True, slots=True)
class MaternalNavMapStateV1:
    """Immutable current association configuration linked to its actual visual basis.

    ``target_position`` is present only with current recognized, located evidence.
    ``possible_center`` and ``uncertainty_radius`` describe old limited support,
    never an exact replacement for missing localization. They confer no motor
    authority. Rates use two distinct compatible acquisitions in physical time;
    they do not attribute causation or treat an unknown rate as zero.
    """

    visual: VisualNavMapStateV1
    seed: MaternalSeedV1
    identity_status: str
    target_position: NavPointV1 | None
    last_supported_tick: int | None
    possible_center: NavPointV1 | None = None
    uncertainty_radius: float | None = None
    separation_rate: float | None = None
    self_closing_rate: float | None = None
    target_closing_rate: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.visual, VisualNavMapStateV1) or not isinstance(self.seed, MaternalSeedV1):
            raise TypeError("maternal configuration requires its original visual basis and seed")
        if self.identity_status not in {"supported", "retained", "contradicted", "unestablished", "disabled", "expired"}:
            raise ValueError("unknown maternal identity disposition")
        if self.last_supported_tick is not None:
            _index(self.last_supported_tick, "last_supported_tick")
            if self.last_supported_tick > self.cutoff_tick:
                raise ValueError("maternal support cannot come from the future")
        if self.target_position is not None:
            if self.identity_status != "supported" or not self.visual.evidence_current:
                raise ValueError("precise target requires current recognized support")
            if not any(item.region_id == self.seed.region_id and item.position == self.target_position for item in self.visual.guidance):
                raise ValueError("maternal target must be an actual located visual contribution")
            if not any(item.region_id == self.seed.region_id and item.descriptor == self.seed.descriptor for item in self.visual.recognition):
                raise ValueError("maternal target lacks its recognition contribution")
            if self.last_supported_tick != self.visual.event_tick:
                raise ValueError("target must preserve its genuine visual acquisition time")
        if (self.possible_center is None) != (self.uncertainty_radius is None):
            raise ValueError("possible region requires both center and uncertainty")
        if self.possible_center is not None:
            if not isinstance(self.possible_center, NavPointV1) or self.last_supported_tick is None:
                raise ValueError("possible region needs an original supported point")
            if self.identity_status != "retained" or not 0 <= self.cutoff_tick - self.last_supported_tick <= 8:
                raise ValueError("possible region cannot outlive its eight-tick evidence bound")
            expected = (self.cutoff_tick - self.last_supported_tick) * 0.025
            if self.uncertainty_radius != expected:
                raise ValueError("possible-region radius must widen with original evidence age")
        for value in (self.separation_rate, self.self_closing_rate, self.target_closing_rate):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
                raise ValueError("maternal rates must be finite or unknown")
        if any(value is not None for value in (self.separation_rate, self.self_closing_rate, self.target_closing_rate)):
            if not self.action_localized:
                raise ValueError("rates require current self and target positions")

    source_map_ref = MOM_REF
    owner_circuit = "maternal_association"
    state_id = "maternal_target:current"

    @property
    def stream(self) -> MotorStreamRefV1:
        """Keep the original generation; association does not manufacture a sensor."""
        return self.visual.stream

    @property
    def applied_cycle(self) -> int:
        """Return the C opportunity that produced this current configuration."""
        return self.visual.applied_cycle

    @property
    def cutoff_tick(self) -> int:
        """Return the frozen physical cutoff, not a new autonomous clock."""
        return self.visual.cutoff_tick

    @property
    def frame_id(self) -> str | None:
        """Retain the actual visual reference frame even when its data is unavailable."""
        return self.visual.frame_id

    @property
    def event_tick(self) -> int | None:
        """Do not refresh the visual event merely because the association is read."""
        return self.visual.event_tick

    @property
    def sample_id(self) -> int | None:
        """Return the original acquired sample, independent of focal rereads."""
        return self.visual.sample_id

    @property
    def spatial_enabled(self) -> bool:
        """Expose the independently controlled geometric contribution."""
        return self.visual.spatial_enabled

    @property
    def self_position(self) -> NavPointV1 | None:
        """Current SELF position comes only from the original visual configuration."""
        return self.visual.self_position

    @property
    def evidence_current(self) -> bool:
        """Current target support is stricter than activation or retained identity."""
        return self.identity_status == "supported" and self.visual.evidence_current

    @property
    def action_localized(self) -> bool:
        """Directional action additionally needs both positions in the same basis."""
        return self.evidence_current and self.target_position is not None and self.self_position is not None

    @property
    def focal_accessible(self) -> bool:
        """Unknown location can remain relevant, but not indefinitely after a gap."""
        return self.identity_status in {"supported", "retained", "contradicted"}

    @property
    def separation(self) -> float | None:
        """Compute present separation only, never distance from a held point."""
        if not self.action_localized or self.target_position is None or self.self_position is None:
            return None
        return math.hypot(self.target_position.x - self.self_position.x, self.target_position.y - self.self_position.y)

    @property
    def guidance(self) -> tuple[VisualGuidanceV1, ...]:
        """Supply the common geometric port from the actual associated target only."""
        if self.target_position is None:
            return ()
        relation = None if self.self_position is None else NavPointV1(
            self.target_position.x - self.self_position.x, self.target_position.y - self.self_position.y,
        )
        return (VisualGuidanceV1(self.seed.region_id, self.target_position, relation),)

    @property
    def active_relation_labels(self) -> tuple[str, ...]:
        """Keep identity, localization and motion separately inspectable."""
        labels = [f"maternal:identity:{self.identity_status}"]
        labels.append("maternal:localized" if self.action_localized else "maternal:location_unknown")
        if self.separation_rate is not None:
            labels.append("maternal:closing" if self.separation_rate < -1e-9 else "maternal:not_closing")
        return tuple(labels)

    def as_dict(self) -> dict[str, object]:
        """Detach diagnostic data without upgrading held geometry or learned maturity."""
        return {"state_id": self.state_id, "source_map_ref": self.source_map_ref.as_dict(), "owner_circuit": self.owner_circuit,
                "seed": self.seed.as_dict(), "visual_basis": self.visual.as_dict(), "identity_status": self.identity_status,
                "action_localized": self.action_localized, "focal_accessible": self.focal_accessible,
                "target_position": None if self.target_position is None else self.target_position.as_dict(),
                "separation": self.separation, "last_supported_tick": self.last_supported_tick,
                "possible_center": None if self.possible_center is None else self.possible_center.as_dict(),
                "uncertainty_radius_metres": self.uncertainty_radius, "separation_rate_m_s": self.separation_rate,
                "self_closing_rate_m_s": self.self_closing_rate, "target_closing_rate_m_s": self.target_closing_rate,
                "durable_updates": 0, "selects_wnm": False, "motor_authority": False}


@dataclass(frozen=True, slots=True)
class MaternalCandidateV1:
    """Source relevance only; selected operation influence has a separate component."""

    source_map_state: MaternalNavMapStateV1
    current_task_persistence_rank: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_state, MaternalNavMapStateV1) or not self.source_map_state.focal_accessible:
            raise ValueError("maternal bid needs currently accessible association content")
        # Keep exact-integer rank validation, including rejection of bool and integer subclasses.
        # pylint: disable-next=unidiomatic-typecheck
        if type(self.current_task_persistence_rank) is not int or self.current_task_persistence_rank not in (0, 20):
            raise ValueError("maternal continuation rank is either absent or twenty")

    candidate_id = "maternal:target_candidate"
    protected_safety_rank = 0
    new_task_need_rank = 10
    prediction_or_envelope_failure_rank = 0
    novelty_or_ambiguity_rank = 0
    activation_rank = 50
    stable_tie_key = "maternal_target"

    @property
    def reason(self) -> str:
        """Distinguish current association from selected-operation persistence."""
        return "maternal_relation_with_selected_continuation" if self.current_task_persistence_rank else "maternal_relation_available"

    @property
    def published_cycle(self) -> int:
        """Bind the nomination to its original C opportunity."""
        return self.source_map_state.applied_cycle


class MaternalSourceV1:
    """Own one initial association and bounded, evidence-supported current content.

    Updating this source is not a second focal operation. Only one prior visual
    basis is used for rates; only one last supported point can form a possible
    region. Neither reference is a current-target substitute. A selected IP may
    request eight-tick relevance, not rewrite evidence, change identity or renew
    its own task/motor budget. Disabled association leaves the visual owner intact.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: MaternalSeedV1, *, enabled: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, MaternalSeedV1) or not isinstance(enabled, bool):
            raise TypeError("maternal owner requires a stream, seed and Boolean enablement")
        self._stream, self._seed, self._enabled = stream, seed, enabled
        self._durable = _build_seed(seed)
        self._current: MaternalNavMapStateV1 | None = None
        self._last_supported: VisualNavMapStateV1 | None = None
        self._identity_seen = False
        self._influence: tuple[str, int] | None = None
        self._outcome_attention: MaternalOutcomeAttentionV1 | None = None

    @property
    def outcome_attention(self) -> MaternalOutcomeAttentionV1 | None:
        """Read the opt-in source-owned relevance extension, not a second representation."""
        return self._outcome_attention

    def configure_outcome_attention(self) -> None:
        """Attach the no-learning maternal outcome route once, before source processing.

        The local import keeps the source schema independent of its optional
        executive-facing consumer. Configuration changes no seeded organization,
        current evidence or motor permission. Reset constructs a fresh owner.
        """
        if self._current is not None or self._outcome_attention is not None:
            raise RuntimeError("configure maternal relevance only once before source updates")
        import nca8_maternal_attention  # pylint: disable=import-outside-toplevel
        self._outcome_attention = nca8_maternal_attention.MaternalOutcomeAttentionV1(self._stream, self._seed)

    @property
    def durable_map(self) -> NavMapV2:
        """Read the seeded organization without confusing updates with learning."""
        return self._durable

    @property
    def current(self) -> MaternalNavMapStateV1 | None:
        """Read current content without refreshing a single evidence timestamp."""
        return self._current

    def clear_influence(self) -> None:
        """Withdraw operation relevance without erasing maternal identity."""
        self._influence = None

    def retain_influence(self, task_id: str, *, cycle_id: int, expires_at_tick: int) -> None:
        """Accept a current selected-operation request, never permission to move."""
        current = self._current
        _index(cycle_id, "cycle_id", 1)
        _index(expires_at_tick, "expires_at_tick")
        if current is None or current.applied_cycle != cycle_id or not current.action_localized:
            raise ValueError("continuation requires the original current localized source")
        if not isinstance(task_id, str) or not 1 <= len(task_id) <= 100 or not task_id.isascii():
            raise ValueError("continuation task identity must be bounded text")
        if not current.cutoff_tick < expires_at_tick <= current.cutoff_tick + 8:
            raise ValueError("continuation cannot grant more than eight physical ticks")
        self._influence = (task_id, expires_at_tick)

    def candidate(self, *, task_id: str | None = None) -> MaternalCandidateV1 | None:
        """Publish bounded relevance; reads never renew the old influence request."""
        current = self._current
        if current is None or not current.focal_accessible:
            return None
        influence = self._influence
        rank = 20 if influence is not None and influence[0] == task_id and current.cutoff_tick < influence[1] else 0
        return MaternalCandidateV1(current, rank)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual source-owned storage rather than print assumed bounds."""
        return {"durable_maps": 1, "current_configurations": int(self._current is not None),
                "supported_bases": int(self._last_supported is not None), "influence_requests": int(self._influence is not None)}

    def update(self, visual: VisualNavMapStateV1) -> MaternalNavMapStateV1:
        """Apply an already-frozen visual contribution once, atomically before D.

        Identity uses the configured recognized region, not the nearest object or
        a private world label. A known contradictory category takes precedence
        over old association support. Losing just localization retains identity
        but provides no directional target. Two distinct current geometries are
        required for motion; repeated samples preserve unknown/new-evidence status.
        """
        if not isinstance(visual, VisualNavMapStateV1) or visual.stream != self._stream:
            raise ValueError("maternal source requires its own generation's visual configuration")
        previous = self._current
        if previous is not None and (visual.applied_cycle <= previous.applied_cycle or visual.cutoff_tick <= previous.cutoff_tick):
            raise ValueError("maternal updates must advance both focal and physical cutoffs")
        retained = self._last_supported
        identity_seen = self._identity_seen
        category = next((item.descriptor for item in visual.recognition if item.region_id == self._seed.region_id), None)
        point = next((item.position for item in visual.guidance if item.region_id == self._seed.region_id), None)
        status = "unestablished"
        target: NavPointV1 | None = None
        center: NavPointV1 | None = None
        radius: float | None = None
        last_tick = None if retained is None else retained.event_tick
        rates: tuple[float | None, float | None, float | None] = (None, None, None)
        if not self._enabled:
            status = "disabled"
        elif visual.evidence_current and category is not None and category != self._seed.descriptor:
            status = "contradicted"
            retained, last_tick, identity_seen = None, None, False
        elif visual.evidence_current and category == self._seed.descriptor:
            status, identity_seen, target = "supported", True, point
            if point is not None:
                last_tick = visual.event_tick
                # Preserve short-circuit validation of comparable, localized acquisitions before rates.
                # pylint: disable-next=too-many-boolean-expressions
                if (previous is not None and previous.action_localized and retained is not None
                        and retained.event_tick is not None and visual.event_tick is not None
                        and 0 < visual.event_tick - retained.event_tick <= 8 and retained.frame_id == visual.frame_id
                        and retained.self_position is not None and visual.self_position is not None):
                    old_point = next(item.position for item in retained.guidance if item.region_id == self._seed.region_id)
                    old_self, new_self = retained.self_position, visual.self_position
                    dx, dy = old_point.x - old_self.x, old_point.y - old_self.y
                    old_distance = math.hypot(dx, dy)
                    dt = (visual.event_tick - retained.event_tick) * 0.05
                    distance = math.hypot(point.x - new_self.x, point.y - new_self.y)
                    if old_distance > 1e-12:
                        rates = ((distance - old_distance) / dt,
                                 ((new_self.x - old_self.x) * dx + (new_self.y - old_self.y) * dy) / old_distance / dt,
                                 -((point.x - old_point.x) * dx + (point.y - old_point.y) * dy) / old_distance / dt)
                retained = visual
        elif identity_seen:
            status = "retained" if last_tick is not None and visual.cutoff_tick - last_tick <= 8 else "expired"
            if status == "retained" and retained is not None and visual.frame_id == retained.frame_id:
                center = next(item.position for item in retained.guidance if item.region_id == self._seed.region_id)
                radius = (visual.cutoff_tick - last_tick) * 0.025 if last_tick is not None else None
        result = MaternalNavMapStateV1(visual, self._seed, status, target, last_tick, center, radius, *rates)
        self._current, self._last_supported, self._identity_seen = result, retained, identity_seen
        if self._influence is not None and (visual.cutoff_tick >= self._influence[1] or status in {"contradicted", "expired", "disabled"}):
            self._influence = None
        return result
