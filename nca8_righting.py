#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H5 task-level Righting: relational contribution and unexecuted preview.

Navigation, not this module or the test runner, selects an applicable operation.
Righting reads the enhanced POSTURE-SUPPORT facet of that selected source. It
organizes one limited contribution; BodyMap still maps it and lower control is
not called. The inherited organizing competence is a small deterministic Python
reference function, not a claim about neural equations or an ancestral inventory.

Profile ``righting_preview_v1`` fixes activity criteria before seeing results:
mobility requires |tilt| <= 12 degrees, load >= .75 and destabilization <= .15;
supported crouch permits 40 degrees, .45 and .20; requested rest permits any
planar tilt, observed contact and destabilization <= .15, with no minimum useful
actuator load. These are synthetic functional fixtures, not goat physiology.
Current adequacy is not supported dwell, task success or action causation.

The continuation budget is 20 focal opportunities and 80 local ticks from first
selection, including opportunities when another source wins. Missing input does
not reset it. Context changes explicitly supersede the old task rather than
changing its original criterion. A budget-exhausted context never auto-restarts.
No target installation, motor command, physical step or durable learning occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from cca8_motor_contracts import MotorStreamRefV1
from nca8_body_targets import BodyMovementRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_maps import DurableNavMapRefV1, MotorSupportConfigurationV1
from nca8_prediction import ProjectedNavMapV1, SupportPreviewV1
from nca8_primitives import (
    PrimitiveApplicabilityV1, PrimitiveApplicationV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1,
)
from nca8_sensorimotor_contracts import TargetOriginV1

__version__ = "0.2.0"
__all__ = [
    "RightingActivityV1", "RightingContextV1", "RightingTaskV1", "RightingApplicationV1", "RightingIPV1", "__version__",
]


class RightingActivityV1(str, Enum):
    """Requested activities, not evaluator-supplied claims about actual success."""

    MOBILITY = "mobility"
    REST = "rest"
    CROUCH = "supported_crouch"


@dataclass(frozen=True, slots=True)
class RightingContextV1:
    """Fixed task meaning supplied as legitimate activity/developmental context.

    The context ID distinguishes an explicit new requirement from continued use
    of the same requirement. Merely receiving another source sample does not
    create a new context. REST is a request to rest, not a hidden safety answer.
    """

    context_id: str = "activity:neonatal_mobility"
    activity: RightingActivityV1 = RightingActivityV1.MOBILITY

    def __post_init__(self) -> None:
        if not isinstance(self.context_id, str) or not 1 <= len(self.context_id) <= 80:
            raise ValueError("context_id must contain 1-80 characters")
        if self.context_id != self.context_id.strip() or any(ord(char) < 32 for char in self.context_id):
            raise ValueError("context_id must be printable single-line text without surrounding spaces")
        if not isinstance(self.activity, RightingActivityV1):
            raise TypeError("activity must be RightingActivityV1")

    @property
    def criterion(self) -> tuple[float, float, float]:
        """Return maximum absolute tilt, minimum useful load and maximum instability."""
        if self.activity is RightingActivityV1.REST:
            return 90.0, 0.0, 0.15
        if self.activity is RightingActivityV1.CROUCH:
            return 40.0, 0.45, 0.20
        return 12.0, 0.75, 0.15

    def as_dict(self) -> dict[str, object]:
        """Export the fixed activity-relative criterion, not an observed result."""
        tilt, load, instability = self.criterion
        return {
            "context_id": self.context_id, "activity": self.activity.value, "maximum_absolute_tilt": tilt,
            "minimum_loading": load, "maximum_destabilization": instability, "requires_observed_contact": True,
        }


@dataclass(frozen=True, slots=True)
class RightingTaskV1:
    """One continuing need across applications; no actuator rights are stored here."""

    task_id: str
    context: RightingContextV1
    source_map_ref: DurableNavMapRefV1
    stream: MotorStreamRefV1
    started_cycle: int
    started_tick: int
    last_cycle: int
    applications: int
    status: str = "active"

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not 1 <= len(self.task_id) <= 120:
            raise ValueError("task_id must be bounded text")
        if not isinstance(self.context, RightingContextV1) or not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("task requires its activity context and body stream")
        if not isinstance(self.source_map_ref, DurableNavMapRefV1):
            raise TypeError("task requires its originating source reference")
        for name in ("started_cycle", "started_tick", "last_cycle", "applications"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("task counters must be nonnegative integers")
        if self.started_cycle < 1 or self.last_cycle < self.started_cycle or self.applications > 20:
            raise ValueError("task counters violate the finite opportunity profile")
        if self.status not in {"active", "budget_exhausted", "cancelled"}:
            raise ValueError("tasks are active, budget-exhausted or explicitly cancelled, never observed successful")

    def as_dict(self) -> dict[str, object]:
        """Report task persistence separately from current local or physical success."""
        return {
            "task_id": self.task_id, "context": self.context.as_dict(), "source_map_ref": self.source_map_ref.as_dict(),
            "stream": self.stream.as_dict(), "started_cycle": self.started_cycle, "started_tick": self.started_tick,
            "last_cycle": self.last_cycle, "focal_opportunities": self.last_cycle - self.started_cycle + 1,
            "applications": self.applications, "status": self.status, "expires_at_tick": self.started_tick + 80,
            "maximum_focal_opportunities": 20, "task_success_established": False,
        }


@dataclass(frozen=True, slots=True)
class RightingApplicationV1(PrimitiveApplicationV1):
    """The common Navigation application plus its actual typed H5 computation.

    NO_ACTION in the inherited transport field means no motor task is dispatched
    by this preview. The separate contribution is consumed by H3 to propose
    targets, not reserved/installed. The PNM is registered as unexecuted. This
    subtype avoids a parallel selection interface or an untyped result sidecar.
    """

    task: RightingTaskV1
    contribution: BodyMovementRequestV1
    projection: SupportPreviewV1
    strategy: str

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if not isinstance(self.task, RightingTaskV1) or not isinstance(self.contribution, BodyMovementRequestV1):
            raise TypeError("Righting application requires a task and body contribution")
        if not isinstance(self.projection, SupportPreviewV1):
            raise TypeError("Righting application requires its sparse preview")
        if self.contribution.origin.application_id != self.application_id or self.projection.pnm.application_id != self.application_id:
            raise ValueError("task contribution and PNM must refer to the selected application")
        if self.task.task_id != self.contribution.origin.task_id or self.task.task_id != self.projection.task_id:
            raise ValueError("Righting task identity must agree throughout the preview")
        if not self.task_action.is_null or self.envelope_request is not None:
            raise ValueError("H5 applications must not dispatch a motor task")

    def as_dict(self) -> dict[str, object]:
        """Expose the consumed computation rather than only transformed label text."""
        result = PrimitiveApplicationV1.as_dict(self)
        result.update({
            "task": self.task.as_dict(), "strategy": self.strategy, "contribution": self.contribution.as_dict(),
            "projection": self.projection.as_dict(), "motor_dispatch": False,
        })
        return result


def _bounded_step(value: float, limit: float) -> float:
    """Clip a computed signed contribution; this is not a measured-value repair."""
    return max(-limit, min(limit, value))


def _unit_prediction(value: float) -> float:
    """Bound a prospective reference-model value to the represented unit interval."""
    return min(1.0, max(0.0, value))


class RightingIPV1:
    """One inherited task operation under the existing primitive selection API.

    Preparing an opportunity only ages an existing task and accepts explicit
    context changes. Applicability is read-only. Only apply(), after Navigation's
    choice, starts a task and produces a contribution and prospective change.
    The task is not a hidden motor sequence, and application count never selects
    a pre-scripted next target. H5 retains at most eight application descriptions.
    """

    primitive_id = "ip:righting"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, *, enabled: bool = True) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be Boolean")
        self._enabled = enabled
        self._context = RightingContextV1()
        self._task: RightingTaskV1 | None = None
        self._cycle = 0
        self._tick = -1
        self._task_number = 0
        self._last_applied_cycle = 0
        self._history: list[RightingApplicationV1] = []

    @property
    def task(self) -> RightingTaskV1 | None:
        """Return immutable task context; no query resets its finite budget."""
        return self._task

    @property
    def context(self) -> RightingContextV1:
        """Return the current legitimate activity requirement."""
        return self._context

    def history(self) -> tuple[RightingApplicationV1, ...]:
        """Return bounded prior applications without making them current futures."""
        return tuple(self._history)

    def prepare_opportunity(self, *, cycle_id: int, at_tick: int, context: RightingContextV1) -> None:
        """Age one task at every focal opportunity, even when another source wins.

        Invalid/repeated logical boundaries are refused before mutation. A context
        change releases the previous task rather than labeling it successful;
        immutable earlier applications retain the earlier criterion. Exhaustion
        is sticky within a context. Source/motor generation reset uses a fresh
        preview session and therefore never reuses old task permissions.
        """
        if isinstance(cycle_id, bool) or not isinstance(cycle_id, int) or not self._cycle < cycle_id < 2**63 - 1:
            raise ValueError("focal opportunity must increase")
        if isinstance(at_tick, bool) or not isinstance(at_tick, int) or not self._tick < at_tick < 2**63 - 1:
            raise ValueError("physical cutoff must increase")
        if not isinstance(context, RightingContextV1):
            raise TypeError("context must be RightingContextV1")
        if context.context_id == self._context.context_id and context != self._context:
            raise ValueError("changing the criterion requires an explicit new context ID")
        if context != self._context:
            self._task = None
        elif self._task is not None:
            exhausted = cycle_id - self._task.started_cycle >= 20 or at_tick - self._task.started_tick >= 80
            status = "budget_exhausted" if exhausted and self._task.status == "active" else self._task.status
            self._task = replace(self._task, last_cycle=cycle_id, status=status)
        self._context, self._cycle, self._tick = context, cycle_id, at_tick

    def cancel_task(self) -> RightingTaskV1 | None:
        """Record explicit cancellation without rewriting applications or claiming success.

        This does not itself stop an actuator. The integrated owner separately
        revokes lower authority before another physical update. The same context
        cannot automatically restart a cancelled task; a new context is explicit.
        """
        if self._task is not None and self._task.status == "active":
            self._task = replace(self._task, status="cancelled")
        return self._task

    def source_status(self, source: MotorSupportConfigurationV1 | None) -> str:
        """Assess current support need, without selecting this task or creating PNM.

        Missing rate information never prevents an otherwise justified first
        attempt. Missing load/contact/instability is genuinely unresolved. A
        missing signed tilt can still permit a separately supported extension.
        REST is not automatically safe: actual contact and instability matter.
        """
        if self._task is not None and self._task.status in {"budget_exhausted", "cancelled"}:
            return self._task.status
        if self._task is None and self._tick > 2**63 - 81:
            return "time_budget_unrepresentable"
        if source is None or not source.current or source.feedback is None:
            return "current_source_unavailable"
        if source.applied_cycle != self._cycle or source.cutoff_tick != self._tick:
            return "source_not_from_this_opportunity"
        feedback = source.feedback
        if self._task is not None and (source.stream != self._task.stream or source.source_map_ref != self._task.source_map_ref):
            return "task_source_or_stream_changed"
        if feedback.support_contact is None or feedback.useful_loading is None or feedback.destabilization is None:
            return "support_relation_unknown"
        max_tilt, min_load, max_instability = self._context.criterion
        orientation_ok = feedback.body_tilt_degrees is not None and abs(feedback.body_tilt_degrees) <= max_tilt
        if self._context.activity is RightingActivityV1.REST:
            orientation_ok = True
        if orientation_ok and feedback.support_contact and feedback.useful_loading >= min_load and feedback.destabilization <= max_instability:
            return "currently_adequate_not_dwell"
        return "support_needed"

    def _contribution(self, source: MotorSupportConfigurationV1) -> tuple[str, float | None, float | None]:
        """Compute a bounded situation-dependent contribution, never a motor plan.

        Poor loading or deteriorating support prioritizes limited extension and
        withholds further rotation. Inadequate current stability can also justify
        an extension attempt, without forcing requested rest upright.
        Useful support permits bounded orientation;
        unknown trends halve the normal extent. Contact is required for rotation.
        If neither represented coordinate offers a contribution, report that
        limit rather than issuing a fake hold/arrest command or resetting a task.
        """
        feedback = source.feedback
        if feedback is None or feedback.useful_loading is None:
            return "no_supported_contribution", None, None
        tilt_rate, load_rate, instability_rate = source.rates
        deteriorating = (
            (tilt_rate is not None and tilt_rate > 5.0)
            or (load_rate is not None and load_rate < -0.1)
            or (instability_rate is not None and instability_rate > 0.1)
        )
        improving = (
            (tilt_rate is not None and tilt_rate < -5.0)
            or (load_rate is not None and load_rate > 0.1)
            or (instability_rate is not None and instability_rate < -0.1)
        )
        unknown = all(value is None for value in source.rates)
        max_tilt, min_load, max_instability = self._context.criterion
        desired_tilt: float | None = None
        desired_extension: float | None = None
        if feedback.support_extension is not None and feedback.support_extension < 0.99:
            instability_inadequate = feedback.destabilization is not None and feedback.destabilization > max_instability
            if feedback.useful_loading < min_load or instability_inadequate or deteriorating or feedback.support_contact is False:
                extent = 0.1 if unknown or deteriorating else 0.2
                desired_extension = min(1.0, feedback.support_extension + extent)
        if not deteriorating and feedback.support_contact is True and feedback.useful_loading >= 0.30:
            tilt = feedback.body_tilt_degrees
            if tilt is not None and abs(tilt) > max_tilt:
                extent = (6.0 + 6.0 * feedback.useful_loading) * (0.5 if unknown else 1.0)
                destination = max_tilt if tilt > 0 else -max_tilt
                desired_tilt = tilt + _bounded_step(destination - tilt, extent)
        if desired_tilt is None and desired_extension is None:
            return "no_supported_contribution", None, None
        if deteriorating:
            strategy = "support_first_deteriorating"
        elif feedback.useful_loading < 0.30 or feedback.support_contact is False:
            strategy = "develop_support_before_rotation"
        elif unknown:
            strategy = "conservative_unknown_trend"
        elif improving:
            strategy = "continue_useful_recovery"
        else:
            strategy = "bounded_support_adjustment"
        return strategy, desired_tilt, desired_extension

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Read the selected source; return ranks/vetoes without starting a task."""
        if not isinstance(wnm, WorkingNavMapStateV1) or cycle_id != self._cycle or wnm.refreshed_cycle != cycle_id:
            raise ValueError("Righting requires the prepared current WNM opportunity")
        source = wnm.primary_source_state.motor_support
        status = self.source_status(source) if self._enabled else "righting_disabled"
        if status == "support_needed" and source is not None:
            status = self._contribution(source)[0]
        eligible = status in {
            "support_first_deteriorating", "develop_support_before_rotation", "conservative_unknown_trend",
            "continue_useful_recovery", "bounded_support_adjustment",
        }
        if self._last_applied_cycle == cycle_id:
            eligible, status = False, "already_applied_this_opportunity"
        return PrimitiveApplicabilityV1(
            self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
            0, 100 if eligible else 0, 50 if eligible else 0, 20 if self._task is not None else 0, 0,
            () if eligible else (status,), (status,), self.primitive_id,
        )

    def apply(
        self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int,
    ) -> RightingApplicationV1:
        """Apply the Navigation-selected operation once; return its real computation.

        Revalidate against the current source/opportunity before any task change.
        The sparse reference prediction is calculated here, not by asking the
        external physical provider to simulate a desired future. No lower actor
        is imported or called. The common action transport is explicitly null.
        """
        actual = self.evaluate_applicability(wnm, cycle_id=cycle_id)
        if applicability != actual or not actual.eligible:
            raise ValueError("Righting requires its current eligible applicability record")
        source = wnm.primary_source_state.motor_support
        if source is None or source.feedback is None:
            raise ValueError("current motor support is required")
        strategy, desired_tilt, desired_extension = self._contribution(source)
        task = self._task
        if task is None:
            task = RightingTaskV1(
                f"righting:{source.stream.generation}:{self._task_number + 1}", self._context,
                source.source_map_ref, source.stream, cycle_id, self._tick, cycle_id, 0,
            )
        task = replace(task, applications=task.applications + 1, last_cycle=cycle_id, status="active")
        app_id = f"righting_application:{source.stream.generation}:{cycle_id}"
        contribution = BodyMovementRequestV1(
            TargetOriginV1(source.stream, task.task_id, app_id, f"preview_envelope:{source.stream.generation}:{cycle_id}"),
            desired_tilt, desired_extension, min(8, task.started_tick + 80 - self._tick),
        )
        expected = tuple(
            name for enabled, name in (
                (desired_tilt is not None, "orientation:toward_activity_support"),
                (desired_extension is not None, "extension:limited_support_attempt"),
                (True, "loading:conditional_development"),
                (True, "destabilization:conditional_change"),
            ) if enabled
        )
        pnm = ProjectedNavMapV1(
            f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id, expected,
            "preview_only; later corresponding physical support evidence required", cycle_id + 1, cycle_id + 2,
        )
        projection = self._project(source, contribution, pnm, task.task_id)
        application = RightingApplicationV1(
            app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
            (f"task_contribution:{strategy}", "source_context:bounded_continuation"), expected, pnm.observation_condition,
            TaskActionV1(f"preview_action:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None,
            task, contribution, projection, strategy,
        )
        if self._task is None:
            self._task_number += 1
        self._task = task
        self._last_applied_cycle = cycle_id
        self._history.append(application)
        del self._history[:-8]
        return application

    def _project(
        self, source: MotorSupportConfigurationV1, request: BodyMovementRequestV1, pnm: ProjectedNavMapV1, task_id: str,
    ) -> SupportPreviewV1:
        """Use a deliberately coarse linear relation model, not perfect plant dynamics.

        Anticipated load changes by .8 times extension increment plus .3 times
        absolute tilt reduction/90. Supported load/instability trends contribute
        one quarter of their bounded short-horizon continuation. Instability falls
        by .3 of anticipated load development and .1 of orientation reduction/90.
        Unknown channels stay unknown. Contact is only retained conditionally when
        actually observed; no surface is invented. These fixed coefficients are
        engineering scaffolds awaiting later calibration, not an active learner.
        """
        feedback = source.feedback
        if feedback is None:
            raise ValueError("prediction requires a measured source")
        tilt = request.desired_tilt_degrees if request.desired_tilt_degrees is not None else feedback.body_tilt_degrees
        extension = request.desired_extension if request.desired_extension is not None else feedback.support_extension
        reduction = 0.0 if tilt is None or feedback.body_tilt_degrees is None else abs(feedback.body_tilt_degrees) - abs(tilt)
        increase = 0.0 if extension is None or feedback.support_extension is None else extension - feedback.support_extension
        _tilt_rate, load_rate, instability_rate = source.rates
        horizon = min(4, request.lease_ticks)
        seconds = horizon * source.tick_seconds
        load_change = 0.8 * increase + 0.3 * reduction / 90.0
        if load_rate is not None:
            load_change += 0.25 * _bounded_step(load_rate * seconds, 0.2)
        loading = None if feedback.useful_loading is None else _unit_prediction(feedback.useful_loading + load_change)
        instability = feedback.destabilization
        if instability is not None:
            continuation = 0.0 if instability_rate is None else 0.25 * _bounded_step(instability_rate * seconds, 0.2)
            instability = _unit_prediction(instability + continuation - 0.3 * load_change - 0.1 * reduction / 90.0)
        return SupportPreviewV1(
            pnm, source, task_id, self._context.context_id, horizon, tilt, extension, loading, instability,
            True if feedback.support_contact is True else None,
        )
