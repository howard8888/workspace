#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded source-local support dynamics for P16-1E-C, without action authority.

This helper belongs to the existing body-sensory owner. It consumes that owner's
Phase-C SupportConfigurationV1, never raw world state or a predicted outcome.
Two distinct comparable measurements permit finite differences; this is not SEC,
learning, a supported-dwell test, or a persistent Righting controller. A missing
packet can retain a labelled old measurement briefly, never extrapolated geometry
or a freshly observed trend. Invalid/contradictory evidence breaks the history.

The immutable output is a measured facet of the same POSTURE-SUPPORT source.
Navigation may copy it into the one WNM as read-only working content. It is kept
out of the A0 primitive's input view until a separately reviewed behavioral slice.
The tracker is an owner-local service, not an additional cognitive PART or memory
system. Storage is constant: one last good configuration and one current snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from nca8_maps import Nca8PostureStateV1, SupportConfigurationV1, SupportObservationV1

__version__ = "0.1.0"
__all__ = ["SupportDynamicsProfileV1", "SupportDynamicsV1", "SupportDynamicsTrackerV1", "__version__"]


@dataclass(frozen=True, slots=True)
class SupportDynamicsProfileV1:
    """Declared finite-difference/continuity limits; engineering units, not biology.

    Rates use represented event-cycle intervals, never poll count or elapsed wall
    time. Angle has units degrees/event-cycle; loading and destabilization have
    normalized units/event-cycle. Absolute rates at or below their deadband are
    approximately stable, not mechanically adequate support. A tiny floating-point
    tolerance prevents a rounded equality from crossing the deadband.

    The default pair interval of two permits one missing intervening event. A held
    reference may be retained for two cycles after its actual measurement event.
    Holding evidence does not compute a fresh rate or extend either deadline.
    The supported experimental bounds below prevent accidental unlimited history.
    """

    angle_deadband: float = 1.0
    loading_deadband: float = 0.02
    destabilization_deadband: float = 0.02
    max_pair_interval: int = 2
    continuity_cycles: int = 2

    def __post_init__(self) -> None:
        for name, upper in (("angle_deadband", 90.0), ("loading_deadband", 1.0), ("destabilization_deadband", 1.0)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            value = float(value)
            if not math.isfinite(value) or not 0.0 <= value <= upper:
                raise ValueError(f"{name} must be finite and in [0, {upper}]")
            object.__setattr__(self, name, value)
        for name in ("max_pair_interval", "continuity_cycles"):
            value = getattr(self, name)
            minimum = 1 if name == "max_pair_interval" else 0
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 8:
                raise ValueError(f"{name} must be an integer in [{minimum}, 8]")

    @property
    def profile_id(self) -> str:
        """Identify this rule family; serialized parameters identify the actual profile."""
        return "support_trend_v1"

    def as_dict(self) -> dict[str, str | int | float]:
        """Return detached rule parameters independently of the world's dynamics profile."""
        return {
            "profile_id": self.profile_id,
            "angle_deadband": self.angle_deadband,
            "loading_deadband": self.loading_deadband,
            "destabilization_deadband": self.destabilization_deadband,
            "max_pair_interval": self.max_pair_interval,
            "continuity_cycles": self.continuity_cycles,
        }


def _rate(previous: float | None, current: float | None, interval: int) -> float | None:
    """Return a measured difference only where both quantities were actually observed."""
    if previous is None or current is None:
        return None
    return (current - previous) / interval


def _direction(rate: float | None, deadband: float) -> str:
    """Describe change, not desirability, adequacy, task progress, or prediction error."""
    if rate is None:
        return "unknown"
    if abs(rate) <= deadband or math.isclose(abs(rate), deadband, rel_tol=1e-12, abs_tol=1e-12):
        return "approximately_stable"
    return "increasing" if rate > 0.0 else "decreasing"


@dataclass(frozen=True, slots=True)
class SupportDynamicsV1:
    """Immutable source facet, with current input separated from any held reference.

    ``configuration`` preserves the owner's actual admission result, including a
    rejected or delayed sample. ``reference`` is only a genuinely current sample
    or explicitly aged bounded-continuity evidence. It is never the rejected
    sample relabelled as current. ``previous`` exists only for a current, distinct,
    comparable pair; rates cannot persist into a missing-input cycle.

    Partial samples stay partial. A fresh contact observation does not refresh an
    absent loading value. This implementation does not retain a separate older
    value for each missing quantity. Evidence-current is therefore a statement
    about the quantities actually present, not a complete sensed body package.
    """

    configuration: SupportConfigurationV1
    profile: SupportDynamicsProfileV1
    continuity: str
    reason: str
    reference: SupportObservationV1 | None = None
    previous: SupportObservationV1 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, SupportConfigurationV1):
            raise TypeError("configuration must be SupportConfigurationV1")
        if not isinstance(self.profile, SupportDynamicsProfileV1):
            raise TypeError("profile must be SupportDynamicsProfileV1")
        if self.continuity not in {"current", "bounded_continuity", "insufficient_evidence", "contradicted"}:
            raise ValueError("unknown support continuity status")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 120:
            raise ValueError("reason must be nonblank and bounded to 120 characters")
        for sample in (self.reference, self.previous):
            if sample is not None and not isinstance(sample, SupportObservationV1):
                raise TypeError("support references must be SupportObservationV1 or None")
        if self.continuity in {"insufficient_evidence", "contradicted"}:
            if self.reference is not None or self.previous is not None:
                raise ValueError("unsupported or contradicted history cannot supply measured working content")
            return
        reference = self.reference
        if reference is None or not reference.has_measurements:
            raise ValueError("supported working content needs an actual measurement")
        if self.configuration.last_supported_event_cycle != reference.event_cycle:
            raise ValueError("reference must retain the owner's last genuine support event")
        if self.continuity == "current":
            if not self.configuration.evidence_current or reference != self.configuration.observation:
                raise ValueError("current dynamics must use the owner's current measurement")
        else:
            if self.configuration.disposition not in {"missing", "duplicate", "delayed", "empty"}:
                raise ValueError("only missing/repeated/historical input may retain bounded continuity")
            age = self.configuration.applied_cycle - reference.event_cycle
            if not 1 <= age <= self.profile.continuity_cycles or self.previous is not None:
                raise ValueError("held evidence must be aged, bounded and have no newly computed pair")
        previous = self.previous
        if previous is not None:
            interval = reference.event_cycle - previous.event_cycle
            if self.continuity != "current" or reference.sample_id <= previous.sample_id:
                raise ValueError("a trajectory needs distinct increasing current sample identities")
            if previous.frame_id != reference.frame_id or not 1 <= interval <= self.profile.max_pair_interval:
                raise ValueError("a trajectory needs comparable frames and a bounded positive event interval")

    @property
    def behavioral_authority(self) -> bool:
        """Stay read-only for every status, including a clear measured trend."""
        return False

    @property
    def evidence_age(self) -> int | None:
        """Age the actual reference event, not its most recent read or application."""
        return None if self.reference is None else self.configuration.applied_cycle - self.reference.event_cycle

    @property
    def pair_interval(self) -> int | None:
        """Return the measured event interval, absent when no fresh comparison occurred."""
        if self.reference is None or self.previous is None:
            return None
        return self.reference.event_cycle - self.previous.event_cycle

    def _measurement_rate(self, name: str) -> float | None:
        """Compute a finite difference from the validated pair, without filling missing fields."""
        if self.previous is None or self.reference is None:
            return None
        return _rate(getattr(self.previous, name), getattr(self.reference, name), self.reference.event_cycle - self.previous.event_cycle)

    @property
    def angle_rate(self) -> float | None:
        """Degrees per event-cycle; increasing angle is not a universal support objective."""
        return self._measurement_rate("body_ground_angle_degrees")

    @property
    def loading_rate(self) -> float | None:
        """Normalized loading change per event-cycle, with no task-adequacy verdict."""
        return self._measurement_rate("useful_loading")

    @property
    def destabilization_rate(self) -> float | None:
        """Normalized destabilization change per event-cycle, not a new action choice."""
        return self._measurement_rate("destabilization")

    @property
    def trends(self) -> tuple[str, str, str]:
        """Return angle, loading and destabilization directions in that explicit order."""
        return (
            _direction(self.angle_rate, self.profile.angle_deadband),
            _direction(self.loading_rate, self.profile.loading_deadband),
            _direction(self.destabilization_rate, self.profile.destabilization_deadband),
        )

    @property
    def lateral_contact_change(self) -> str:
        """Describe a Boolean contact change only; never invent a contact-fraction derivative."""
        if self.previous is None or self.reference is None:
            return "unknown"
        before, after = self.previous.lateral_contact, self.reference.lateral_contact
        if before is None or after is None:
            return "unknown"
        if before == after:
            return "unchanged"
        return "appeared" if after else "disappeared"

    def as_dict(self) -> dict[str, object]:
        """Return complete detached source/parameter/evidence content for inspection or a WNM copy."""
        return {
            "configuration": self.configuration.as_dict(),
            "profile": self.profile.as_dict(),
            "continuity": self.continuity,
            "reason": self.reason,
            "reference": self.reference.as_dict() if self.reference is not None else None,
            "previous": self.previous.as_dict() if self.previous is not None else None,
            "evidence_age": self.evidence_age,
            "pair_interval": self.pair_interval,
            "angle_rate": self.angle_rate,
            "loading_rate": self.loading_rate,
            "destabilization_rate": self.destabilization_rate,
            "trends": list(self.trends),
            "lateral_contact_change": self.lateral_contact_change,
            "behavioral_authority": False,
        }

    def trace_details(self) -> dict[str, str | int | float | bool | None]:
        """Return sixteen source-owned scalars; raw samples remain in the measured companion."""
        source = self.configuration.source_map_ref
        return {
            "source_map": f"{source.map_id}@r{source.revision}",
            "profile_id": self.profile.profile_id,
            "applied_cycle": self.configuration.applied_cycle,
            "input_disposition": self.configuration.disposition,
            "continuity": self.continuity,
            "reference_sample": self.reference.sample_id if self.reference is not None else None,
            "reference_event": self.reference.event_cycle if self.reference is not None else None,
            "previous_sample": self.previous.sample_id if self.previous is not None else None,
            "pair_interval": self.pair_interval,
            "evidence_age": self.evidence_age,
            "angle_rate": self.angle_rate,
            "loading_rate": self.loading_rate,
            "destabilization_rate": self.destabilization_rate,
            "trends": ",".join(self.trends),
            "reason": self.reason,
            "behavioral_authority": False,
        }


class SupportDynamicsTrackerV1:
    """Maintain bounded history on behalf of one session's body-sensory owner.

    Call once per new Phase-C application. The input consumer already enforces
    sensor identity/time ordering. This helper also rejects repeated application
    calls and invalidates history on source revision changes. A current sample
    after a broken history establishes a baseline, not a rate from rejected data.

    Invalid, out-of-order, future or conflicting input invalidates history.
    Missing, duplicate, delayed or empty input can hold the last good sample for
    the profile's fixed event-age window. A clear changed posture or an ambiguous
    posture also invalidates held content; a new sample can never be replaced by
    an old precise value merely to preserve continuity. Neither deadline is
    extended by repeated reads. No history survives replacement/reset of the owner.
    """

    def __init__(self, profile: SupportDynamicsProfileV1 | None = None) -> None:
        if profile is not None and not isinstance(profile, SupportDynamicsProfileV1):
            raise TypeError("profile must be SupportDynamicsProfileV1 or None")
        self._profile = profile if profile is not None else SupportDynamicsProfileV1()
        self._last_good: SupportConfigurationV1 | None = None
        self._current: SupportDynamicsV1 | None = None

    @property
    def current(self) -> SupportDynamicsV1 | None:
        """Return the latest immutable source facet; a read never changes freshness."""
        return self._current

    def update(self, configuration: SupportConfigurationV1) -> SupportDynamicsV1:
        """Apply one later owner result and return its dynamics/continuity without learning.

        State is published only after validating the next snapshot. Cross-source
        history, invalid inputs and large gaps cannot produce a difference.
        Absent quantities in a partial current sample stay absent independently.
        """
        if not isinstance(configuration, SupportConfigurationV1):
            raise TypeError("configuration must be SupportConfigurationV1")
        existing = self._current
        if existing is not None and configuration.applied_cycle <= existing.configuration.applied_cycle:
            raise ValueError("support dynamics require a strictly later Phase-C application")
        good = self._last_good
        source_changed = existing is not None and existing.configuration.source_map_ref != configuration.source_map_ref
        if source_changed:
            good = None
        reference = good.observation if good is not None else None
        previous = None
        disposition = configuration.disposition
        clear_poses = {Nca8PostureStateV1.FALLEN, Nca8PostureStateV1.STANDING}
        changed_pose = (
            good is not None and good.scaffold_posture in clear_poses and configuration.scaffold_posture in clear_poses
            and good.scaffold_posture is not configuration.scaffold_posture
        )
        if disposition in {"invalid", "out_of_order", "future", "conflict"} or (
            configuration.scaffold_posture is Nca8PostureStateV1.AMBIGUOUS
            or (not configuration.evidence_current and changed_pose)
        ):
            continuity = "contradicted" if disposition == "conflict" or changed_pose or (
                configuration.scaffold_posture is Nca8PostureStateV1.AMBIGUOUS
            ) else "insufficient_evidence"
            reason = "history_invalidated_by_input_or_posture"
            reference, good = None, None
        elif configuration.evidence_current:
            current = configuration.observation
            if current is None:  # guarded by SupportConfigurationV1
                raise ValueError("current support input has no observation")
            reason = "source_changed_new_baseline" if source_changed else "first_current_sample"
            if reference is not None:
                interval = current.event_cycle - reference.event_cycle
                if current.sample_id <= reference.sample_id or current.frame_id != reference.frame_id or interval <= 0:
                    reason = "incomparable_sample_new_baseline"
                elif interval > self._profile.max_pair_interval:
                    reason = "pair_interval_exceeded_new_baseline"
                else:
                    previous = reference
                    reason = "distinct_comparable_pair"
            reference, good = current, configuration
            continuity = "current"
        elif reference is not None and 1 <= configuration.applied_cycle - reference.event_cycle <= self._profile.continuity_cycles:
            continuity, reason = "bounded_continuity", "held_previous_measurement_without_extrapolation"
        else:
            continuity = "insufficient_evidence"
            reason = "continuity_expired" if reference is not None else "no_valid_reference"
            reference, good = None, None
        snapshot = SupportDynamicsV1(configuration, self._profile, continuity, reason, reference, previous)
        self._last_good, self._current = good, snapshot
        return snapshot
