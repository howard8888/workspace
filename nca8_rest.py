#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Navigation-selected first Rest on the existing POSTURE-SUPPORT source.

Rest owns its developmental applicability, finite task organization and intrinsic
supported-dwell condition. It neither simulates the body nor dispatches a motor
command. BodyMap maps each selected release/stow/settle relation separately. The
same task may span several applications; budgets, original evidence and earlier
outcomes cannot be restarted by a helper or a completed-feeding label. Phase F
owns none of this work. All numerical conditions are disclosed engineering
approximations, not measured newborn physiology or a durable learning rule.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1
from nca8_body_targets import RestBodyRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_feeding_state import FeedingNeedStateV1
from nca8_maps import MotorSupportConfigurationV1, NavMapStateV1
from nca8_prediction import ProjectedNavMapV1, RestPreviewV1
from nca8_primitives import PrimitiveApplicabilityV1, PrimitiveApplicationV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, CommittedBodyTargetV1, TargetOriginV1

__version__ = "0.1.0"
__all__ = ["RestProfileV1", "RestTaskV1", "RestApplicationV1", "RestIPV1", "rest_geometry_v1", "__version__"]


def _index(value: int, name: str, *, minimum: int = 0, maximum: int = 2**63 - 321) -> None:
    """Validate finite original indices without silently normalizing booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside its declared integer bound")


def _name(value: str) -> None:
    """Reject changed/ambiguous diagnostic identity before it becomes a task key."""
    if not isinstance(value, str) or not 1 <= len(value) <= 120 or value.strip() != value or not value.isascii() or not value.isprintable():
        raise ValueError("Rest identity must be unchanged bounded printable ASCII")


@dataclass(frozen=True, slots=True)
class RestProfileV1:
    """Explicit opt-in task, drive tendency and independent no-learning controls.

    The 8-application/128-tick ceilings are incomplete-exit limits. Readiness
    consumes existing measured need, not a supplied nourished/rested flag.
    Disabling the optional hook cannot disable or enable movement or completion.
    """

    enabled: bool = True
    tendency_enabled: bool = True
    attention_enabled: bool = True
    outcome_attention_enabled: bool = True
    learning_hook_enabled: bool = True

    def __post_init__(self) -> None:
        if not all(isinstance(value, bool) for value in (self.enabled, self.tendency_enabled, self.attention_enabled,
                                                        self.outcome_attention_enabled, self.learning_hook_enabled)):
            raise TypeError("Rest profile switches must be actual booleans")

    def as_dict(self) -> dict[str, object]:
        """Disclose assumptions, not a selected action or learned preference."""
        return {"profile": "first_rest_v1", "enabled": self.enabled, "tendency_enabled": self.tendency_enabled,
                "attention_enabled": self.attention_enabled, "outcome_attention_enabled": self.outcome_attention_enabled,
                "learning_hook_enabled": self.learning_hook_enabled, "maximum_applications": 8, "maximum_ticks": 128,
                "need_limit": .01, "readiness_span_ticks": 4, "readiness_samples": 2, "evidence_gap_ticks": 8,
                "minimum_body_bearing": .90, "maximum_instability": .15, "maximum_angular_rate": 5.0,
                "maximum_extension_rate": .05, "rest_samples": 3, "rest_span_ticks": 8,
                "developmental_tendency": "supplied_not_learned", "durable_learning": False}


@dataclass(frozen=True, slots=True)
class RestTaskV1:
    """One immutable task snapshot; later current safety does not rewrite its history."""

    task_id: str
    stream: MotorStreamRefV1
    source_map_ref: NavMapRefV1
    started_cycle: int
    started_tick: int
    applications: int
    status: str = "active"
    completion_events: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _name(self.task_id)
        if not isinstance(self.stream, MotorStreamRefV1) or not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("Rest task requires original stream/source")
        if not self.task_id.startswith("rest:"):
            raise ValueError("Rest task cannot use another operation's identity")
        _index(self.started_cycle, "started_cycle", minimum=1)
        _index(self.started_tick, "started_tick")
        _index(self.applications, "applications", minimum=1, maximum=8)
        if self.status not in {"active", "completed", "cancelled", "budget_exhausted", "support_interrupted", "outcome_unresolved", "not_applied"}:
            raise ValueError("unknown Rest task status")
        if not isinstance(self.completion_events, tuple) or len(self.completion_events) not in (0, 3):
            raise ValueError("Rest completion requires exactly three retained events")
        if (self.status == "completed") != bool(self.completion_events):
            raise ValueError("only completed Rest carries dwell evidence")
        if self.completion_events:
            for event in self.completion_events:
                _index(event, "completion event", minimum=self.started_tick + 1, maximum=self.expires_at_tick - 1)
            a, b, c = self.completion_events
            if not a < b < c or c - a < 8 or b - a > 8 or c - b > 8:
                raise ValueError("Rest completion events do not meet the fixed physical dwell")

    @property
    def expires_at_tick(self) -> int:
        """Return the fixed original deadline, never a latest-application lease."""
        return self.started_tick + 128

    def as_dict(self) -> dict[str, object]:
        """Return detached task history without current-safety or motor authority."""
        return {"task_id": self.task_id, "stream": self.stream.as_dict(), "source_map_ref": self.source_map_ref.as_dict(),
                "started_cycle": self.started_cycle, "started_tick": self.started_tick, "applications": self.applications,
                "status": self.status, "expires_at_tick": self.expires_at_tick, "completion_events": list(self.completion_events)}


@dataclass(frozen=True, slots=True)
class RestApplicationV1(PrimitiveApplicationV1):
    """One ordinary Navigation application with its typed Rest relation and PNM."""

    task: RestTaskV1
    contribution: RestBodyRequestV1
    projection: RestPreviewV1

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if (not isinstance(self.task, RestTaskV1) or not isinstance(self.contribution, RestBodyRequestV1)
                or not isinstance(self.projection, RestPreviewV1)):
            raise TypeError("Rest application requires typed original task, request and projection")
        origin, pnm = self.contribution.origin, self.projection.pnm
        if (self.primitive_id != "ip:rest" or self.task.task_id != origin.task_id or origin.task_id != self.projection.task_id
                or self.application_id != origin.application_id or pnm.application_id != self.application_id
                or self.source_wnm_id != pnm.source_wnm_id or self.cycle_id != pnm.created_cycle
                or self.expected_relations != pnm.expected_relations or self.task.status != "active"
                or self.task.stream != origin.stream or self.contribution.source_map_ref != self.task.source_map_ref
                or self.contribution.contribution != self.projection.contribution or not self.task_action.is_null
                or self.envelope_request is not None or self.task.started_tick > self.projection.basis.cutoff_tick
                or self.projection.basis.cutoff_tick + self.contribution.lease_ticks > self.task.expires_at_tick):
            raise ValueError("Rest application cannot substitute a task, source, clock, projection or motor permission")

    def as_dict(self) -> dict[str, object]:
        """Export the original operation's computation, not a live actuator grant."""
        result = PrimitiveApplicationV1.as_dict(self)
        result.update(task=self.task.as_dict(), contribution=self.contribution.as_dict(), projection=self.projection.as_dict())
        return result


def rest_geometry_v1(feedback: MotorFeedbackV1 | None) -> bool | None:
    """Read the task's current body-supported/stowed relation; quietness is separate.

    This owner-local fixed requirement never fills missing body bearing from limb
    loading or a desired target. It cannot establish time-spanning task success.
    """
    if feedback is None:
        return None
    if not isinstance(feedback, MotorFeedbackV1):
        raise TypeError("Rest geometry requires admitted body feedback")
    bearing, oral, seal = feedback.body_bearing, feedback.oral, feedback.oral_seal
    if (bearing is None or oral is None or seal is None or any(item is None for item in
            (bearing.contact, bearing.bearing, oral.contact, oral.extension_metres,
             seal.sealed, seal.closure, feedback.destabilization))):
        return None
    return (bearing.contact is True and bearing.bearing is not None and bearing.bearing >= .90
            and oral.contact is False and oral.extension_metres is not None and oral.extension_metres <= .0025
            and seal.sealed is False and seal.closure is not None and seal.closure <= .025
            and feedback.destabilization is not None and feedback.destabilization <= .15)


class RestIPV1:
    """Finite Rest owner; only Navigation calls apply and BodyMap grants movement.

    Preparation maintains current need and local intrinsic completion using actual
    timed source acquisitions. It performs no demanding outcome interpretation.
    A known serious failed contribution ends this first-rest attempt rather than
    inventing a general recovery/search strategy or relabeling it as success.
    """

    primitive_id = "ip:rest"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, source_map_ref: NavMapRefV1, profile: RestProfileV1) -> None:
        if not isinstance(source_map_ref, NavMapRefV1) or not isinstance(profile, RestProfileV1):
            raise TypeError("Rest requires its existing source and explicit profile")
        self.source_map_ref, self.profile = source_map_ref, profile
        self._task: RestTaskV1 | None = None
        self._source: MotorSupportConfigurationV1 | None = None
        self._need: FeedingNeedStateV1 | None = None
        self._cycle, self._tick = 0, -1
        self._last_applied = 0
        self._readiness: list[FeedingNeedStateV1] = []
        self._dwell: list[MotorFeedbackV1] = []
        self._history: list[RestApplicationV1] = []
        self._target: CommittedBodyTargetV1 | None = None
        self._results: dict[str, str] = {}
        self._reason = "not_prepared"
        self._closed = False
        self._safe: bool | None = None

    @property
    def task(self) -> RestTaskV1 | None:
        """Expose an immutable original task snapshot without granting authority."""
        return self._task

    @property
    def authorized_target(self) -> CommittedBodyTargetV1 | None:
        """Return the actually bound latest target for exact-owner retirement."""
        return self._target

    @property
    def cancel_previous(self) -> bool:
        """Request retirement of only this task's target after its terminal result."""
        return self._target is not None and self._task is not None and self._task.status != "active"

    @property
    def reason(self) -> str:
        """Explain current applicability; this text is never an input to another task."""
        return self._reason

    @property
    def current_safe_rest(self) -> bool | None:
        """Report current supported/quiet evidence independently of historical completion."""
        return self._safe

    @property
    def wants_attention(self) -> bool:
        """Supply source relevance only; Attention still decides focal access."""
        return (self.profile.enabled and self.profile.tendency_enabled and self.profile.attention_enabled
                and not self._closed and (self._reason == "ready" or self._task is not None and self._task.status == "active"))

    def retained_counts(self) -> dict[str, int]:
        """Report independently bounded live/history state without renewing anything."""
        return {"rest_tasks": int(self._task is not None), "rest_applications": len(self._history),
                "rest_readiness_samples": len(self._readiness), "rest_dwell_samples": len(self._dwell),
                "rest_result_ids": len(self._results)}

    def applications(self) -> tuple[RestApplicationV1, ...]:
        """Return the bounded original application catalog, not a sequence to execute."""
        return tuple(self._history)

    def _read_need(self, need: FeedingNeedStateV1) -> bool:
        """Confirm current readiness from two distinct acquisitions, never from M."""
        if not need.current or need.deficit_units is None or need.deficit_units > .01:
            self._readiness.clear()
            return False
        if need.new_acquisition:
            if self._readiness:
                last = self._readiness[-1]
                if need.event_tick is None or last.event_tick is None or need.event_tick - last.event_tick > 8:
                    self._readiness.clear()
                elif need.sample_id == last.sample_id:
                    return False
                elif self._readiness[0].event_tick is not None and need.event_tick - self._readiness[0].event_tick > 8:
                    self._readiness = [last]
            self._readiness.append(need)
            if len(self._readiness) > 2:
                self._readiness = [self._readiness[0], self._readiness[-1]]
        if len(self._readiness) != 2:
            return False
        first, last = self._readiness
        return (first.event_tick is not None and last.event_tick is not None
                and 4 <= last.event_tick - first.event_tick <= 8 and self._tick - last.event_tick <= 8)

    def _observe_quiet(self, source: MotorSupportConfigurationV1 | None) -> None:
        """Maintain intrinsic rest evidence; no PNM scoring or focal interpretation."""
        self._safe = None
        feedback = None if source is None or not source.current else source.feedback
        geometry = rest_geometry_v1(feedback)
        if geometry is False:
            self._safe = False
        if geometry is not True or source is None or feedback is None:
            self._dwell.clear()
            return
        previous = source.previous
        if (previous is None or previous.sample_id == feedback.sample_id
                or not 0 < feedback.event_tick - previous.event_tick <= 8
                or previous.body_tilt_degrees is None or feedback.body_tilt_degrees is None
                or previous.support_extension is None or feedback.support_extension is None):
            self._dwell.clear()
            return
        seconds = (feedback.event_tick - previous.event_tick) * source.tick_seconds
        self._safe = (abs(feedback.body_tilt_degrees - previous.body_tilt_degrees) / seconds <= 5.0 + 1e-12
                      and abs(feedback.support_extension - previous.support_extension) / seconds <= .05 + 1e-12)
        task = self._task
        if not self._safe or task is None or task.status != "active" or feedback.event_tick <= task.started_tick:
            self._dwell.clear()
            return
        if self._dwell and feedback.sample_id == self._dwell[-1].sample_id:
            return
        if self._dwell and feedback.event_tick - self._dwell[-1].event_tick > 8:
            self._dwell.clear()
        self._dwell.append(feedback)
        # Retain a recent three-sample chain; no diagnostic ring controls this proof.
        if len(self._dwell) > 3:
            self._dwell = [self._dwell[0], self._dwell[-2], self._dwell[-1]]
        if len(self._dwell) == 3 and self._dwell[1].event_tick - self._dwell[0].event_tick > 8:
            self._dwell = self._dwell[-2:]
        if len(self._dwell) == 3 and self._dwell[-1].event_tick - self._dwell[0].event_tick >= 8:
            self._task = replace(task, status="completed", completion_events=tuple(item.event_tick for item in self._dwell))

    def prepare(
        self, source: MotorSupportConfigurationV1 | None, need: FeedingNeedStateV1, *, cycle_id: int, cutoff_tick: int,
        movement_blocked: bool,
    ) -> None:
        """Update this owner's current evidence before selection, without granting work."""
        _index(cycle_id, "cycle", minimum=self._cycle + 1)
        _index(cutoff_tick, "tick", minimum=self._tick + 1)
        if not isinstance(need, FeedingNeedStateV1) or not isinstance(movement_blocked, bool):
            raise TypeError("Rest needs typed body need and actual conflict status")
        if (need.cycle_id, need.cutoff_tick) != (cycle_id, cutoff_tick):
            raise ValueError("Rest cannot read a different focal need sample")
        if source is not None and (not isinstance(source, MotorSupportConfigurationV1)
                or source.stream != need.stream or source.source_map_ref != self.source_map_ref
                or source.applied_cycle != cycle_id or source.cutoff_tick != cutoff_tick):
            raise ValueError("Rest source and need do not share an original opportunity")
        if self._task is not None and self._task.stream != need.stream:
            raise ValueError("Rest cannot reuse another generation's task")
        self._source, self._need, self._cycle, self._tick = source, need, cycle_id, cutoff_tick
        if self._task is not None and self._task.status == "active" and cutoff_tick >= self._task.expires_at_tick:
            self._task = replace(self._task, status="budget_exhausted")
        self._observe_quiet(source)
        ready = self._read_need(need)
        if self._closed or not self.profile.enabled or not self.profile.tendency_enabled:
            self._reason = "rest_disabled"
        elif self._task is not None and self._task.status != "active":
            self._reason = self._task.status
        elif source is None or not source.current or source.feedback is None:
            self._reason = "current_source_unavailable"
        elif not ready:
            self._reason = "current_need_not_confirmed"
        elif movement_blocked:
            self._reason = "movement_permission_conflict"
        else:
            feedback = source.feedback
            bearing = feedback.body_bearing
            support = ((feedback.support_contact is True and feedback.useful_loading is not None and feedback.useful_loading > 0)
                       or (bearing is not None and bearing.contact is True and bearing.bearing is not None and bearing.bearing > 0))
            if not support or feedback.destabilization is None or feedback.destabilization > .35:
                self._reason = "support_unavailable"
                if self._task is not None and not support and feedback.support_contact is False and bearing is not None and bearing.contact is False:
                    self._task = replace(self._task, status="support_interrupted")
            elif (feedback.oral is None or feedback.oral_seal is None or feedback.oral.extension_metres is None
                  or feedback.oral.contact is None or feedback.oral_seal.closure is None or feedback.oral_seal.sealed is None
                  or feedback.support_extension is None or feedback.body_tilt_degrees is None or bearing is None
                  or bearing.contact is None or bearing.bearing is None):
                self._reason = "required_body_relation_unknown"
            elif self._task is not None and rest_geometry_v1(feedback) is True:
                self._reason = "awaiting_supported_rest_dwell"
            elif self._history and self._history[-1].application_id not in self._results:
                self._reason = "awaiting_original_outcome"
            elif self._history and self._results[self._history[-1].application_id] != "matched":
                self._task = replace(self._task, status="outcome_unresolved") if self._task is not None else None
                self._reason = "outcome_unresolved"
            elif self._task is not None and self._task.applications >= 8:
                self._task = replace(self._task, status="budget_exhausted")
                self._reason = "budget_exhausted"
            else:
                self._reason = "ready"

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Offer one bounded candidate; neither querying nor ranking mutates the task."""
        if not isinstance(wnm, WorkingNavMapStateV1) or cycle_id != self._cycle or wnm.refreshed_cycle != cycle_id:
            raise ValueError("Rest requires the prepared WNM opportunity")
        actual = wnm.primary_source_state
        current = isinstance(actual, NavMapStateV1) and actual.motor_support is self._source
        eligible = current and self._reason == "ready" and self._last_applied != cycle_id
        reason = "ready" if eligible else self._reason if current else "different_source_selected"
        return PrimitiveApplicabilityV1(self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
                                        0, 110 if eligible else 0, 50 if eligible else 0, 20 if self._task else 0, 0,
                                        () if eligible else (reason,), (reason,), self.primitive_id)

    def apply(self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int) -> RestApplicationV1:
        """Return one selected relation and its original conditional PNM, not movement."""
        if applicability != self.evaluate_applicability(wnm, cycle_id=cycle_id) or not applicability.eligible:
            raise ValueError("Rest requires its actual current selected applicability")
        source = self._source
        if source is None or source.feedback is None:
            raise RuntimeError("selected Rest lost its current source")
        f = source.feedback
        if (f.oral is None or f.oral.extension_metres is None or f.oral_seal is None or f.oral_seal.closure is None
                or f.support_extension is None or f.body_tilt_degrees is None):
            raise RuntimeError("selected Rest lost required measured relations")
        if f.oral_seal.closure > .025 or f.oral_seal.sealed:
            part, current, goal, step = "release", f.oral_seal.closure, 0.0, .60
        elif f.oral.extension_metres > .0025 or f.oral.contact:
            part, current, goal, step = "withdraw", f.oral.extension_metres, 0.0, .15
        elif rest_geometry_v1(f) is True:
            part, current, goal, step = "hold", f.support_extension, f.support_extension, .20
        else:
            part, current, step = "settle", f.support_extension, .20
            goal = min(current, .20 / max(math.cos(math.radians(f.body_tilt_degrees)), 1e-12))
        task = self._task
        if task is None:
            task = RestTaskV1(f"rest:{source.stream.generation}:1", source.stream, source.source_map_ref, cycle_id, self._tick, 1)
        else:
            task = replace(task, applications=task.applications + 1)
        horizon = min(8, task.expires_at_tick - self._tick)
        app_id = f"rest_application:{source.stream.generation}:{cycle_id}"
        request = RestBodyRequestV1(TargetOriginV1(source.stream, task.task_id, app_id, f"rest_envelope:{source.stream.generation}:{cycle_id}"),
                                    self.source_map_ref, part, horizon)
        rate = 2.0 if part == "release" else .5 if part == "withdraw" else 1.0
        expected_coordinate = max(goal, current - min(step, rate * source.tick_seconds * horizon))
        relations = (f"rest:{part}:bounded_coordinate", "support:retained_conditionally")
        pnm = ProjectedNavMapV1(f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id, relations,
                                "original_rest_coordinate_at_due_tick_not_full_rest", cycle_id + 1, cycle_id + 16)
        projection = RestPreviewV1(pnm, source, task.task_id, part, expected_coordinate, horizon)
        app = RestApplicationV1(app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
                                (f"rest_relation:{part}",), relations, pnm.observation_condition,
                                TaskActionV1(f"rest_action:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None,
                                task, request, projection)
        self._task, self._last_applied = task, cycle_id
        self._history.append(app)
        return app

    def bind_authorization(self, application: RestApplicationV1, target: CommittedBodyTargetV1 | None) -> None:
        """Bind only the current application's actual BodyMap grant; no movement."""
        if not self._history or application is not self._history[-1] or application.cycle_id != self._cycle:
            raise ValueError("Rest authorization requires its original current application")
        if target is not None and (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyRelativeTargetV1)
                or target.target.origin != application.contribution.origin or target.target.rest_constraint != application.contribution.contribution
                or target.target.basis != application.projection.basis.feedback or target.committed_tick != self._tick):
            raise ValueError("Rest authorization differs from original task/body/clock")
        if self._target is not None and self._target.target.origin.application_id == application.application_id:
            raise ValueError("Rest application cannot bind twice")
        self._target = target
        if target is None and self._task is not None:
            self._task = replace(self._task, status="not_applied")

    def observe_outcome(self, application: RestApplicationV1, status: str) -> None:
        """Accept a canonical owner-published disposition for this exact original only.

        The caller is the source-owned correspondence integration, not a renderer.
        It supplies no replacement sensory fact or task-completion label.
        """
        if not any(item is application for item in self._history):
            raise ValueError("Rest outcome cannot invent prior selected participation")
        if status not in {"matched", "mismatch", "unknown", "interrupted", "not_applied", "expired_unresolved", "cancelled"}:
            raise ValueError("Rest outcome has no supported disposition")
        if application.application_id in self._results and self._results[application.application_id] != status:
            raise ValueError("one original Rest outcome cannot change")
        self._results[application.application_id] = status

    def close(self, reason: str) -> None:
        """Stop future work without changing a previously completed historical task."""
        _name(reason)
        if self._task is not None and self._task.status == "active":
            self._task = replace(self._task, status="cancelled")
        self._closed = True
        self._reason = reason

    def as_dict(self) -> dict[str, object]:
        """Snapshot this owner; no inspection call advances proof, clocks or task."""
        return {"owner": "ip:rest", "task": None if self.task is None else self.task.as_dict(), "reason": self._reason,
                "current_safe_rest": self._safe, "cancel_previous": self.cancel_previous,
                "readiness_events": [item.event_tick for item in self._readiness],
                "rest_events": [item.event_tick for item in self._dwell], "applications": len(self._history),
                "durable_learning_updates": 0}
