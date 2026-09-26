#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared finite Rest experiments and an isolated, explicitly stepped walkthrough.

The harness supplies a fixed physical profile and schedule, never an action list
or a task-success input. All decisions remain inside the existing trial's focal
API. Inspection and export read retained records only; explicit advance invokes
one focal opportunity followed by its intervening lower physical intervals. The
simulation intentionally pauses at the user prompt. This is not a model of a
paused biological organism or the separate hard-newborn B99 qualification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

import cca8_cli
from cca8_support_world import BodyBearingProfileV1, FeedingConsequenceProfileV1, MotorBodyStateV1, MotorWorldPerturbationV1, OralClosurePerturbationV1
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_followmom_demo import maternal_durable_signature_v1
from nca8_rest import RestApplicationV1, RestProfileV1, rest_geometry_v1
from nca8_rest_outcomes import validate_rest_outcome_v1
from nca8_righting import RightingActivityV1, RightingContextV1
from nca8_seek_nipple_demo import SeekNipplePhysicalSampleV1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, LocalTargetDispositionV1
from nca8_suckle_extraction_demo import SuckleExtractionExperimentProfileV1, suckle_extraction_profile_v1
from nca8_sustained_feeding_demo import sustained_feeding_profile_v1

__version__ = "0.1.0"
__all__ = ["REST_CASES_V1", "RestExperimentProfileV1", "RestExperimentV1", "RestWalkthroughV1", "rest_profile_v1",
           "create_rest_trial_v1", "run_rest_v1", "render_rest_v1", "render_rest_cycle_v1", "run_rest_menu_v1", "__version__"]

REST_CASES_V1 = (
    "nominal", "already_fed", "already_recumbent", "lateral_left", "lateral_right", "rest_off", "tendency_off",
    "attention_off", "navigation_off", "competing_source", "hook_off", "outcome_attention_off", "bearing_off", "bearing_sensor_off",
    "no_surface", "lower_motor_off", "release_motor_off", "withdraw_motor_off", "no_capability", "high_need", "missing_need",
    "missing_seal", "missing_reach", "missing_body", "need_loss", "feedback_gap", "delayed", "support_loss",
    "post_rest_support_loss", "cancelled", "cadence_1", "cadence_8", "release_drift", "release_drift_route_off", "release_drift_competing",
)
_COMPLETED_CASES = {"nominal", "already_fed", "already_recumbent", "lateral_left", "lateral_right", "hook_off",
                    "outcome_attention_off", "feedback_gap", "post_rest_support_loss", "cadence_1", "cadence_8"}


@dataclass(frozen=True, slots=True)
class RestExperimentProfileV1:
    """Declared external conditions and independent control removals; no next-action field."""

    case: str
    feeding: SuckleExtractionExperimentProfileV1
    physiology: FeedingConsequenceProfileV1
    bearing: BodyBearingProfileV1
    rest: RestProfileV1
    context: RightingContextV1 | None = None
    horizon_ticks: int = 320
    cadence: int = 4
    cancel_tick: int | None = None
    navigation_enabled: bool = True
    attention_enabled: bool = True
    extension_capability: bool = True
    competing_source: bool = False
    maternal_association_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.case, str) or self.case not in REST_CASES_V1:
            raise ValueError("unknown Rest experiment")
        if not isinstance(self.feeding, SuckleExtractionExperimentProfileV1) or not isinstance(self.physiology, FeedingConsequenceProfileV1):
            raise TypeError("Rest review requires the actual typed feeding/body profiles")
        if not isinstance(self.bearing, BodyBearingProfileV1) or not isinstance(self.rest, RestProfileV1):
            raise TypeError("Rest review requires explicit bearing competence and task profile")
        if self.context is not None and not isinstance(self.context, RightingContextV1):
            raise TypeError("Rest review context must be a declared activity")
        if (isinstance(self.horizon_ticks, bool) or not isinstance(self.horizon_ticks, int) or not 1 <= self.horizon_ticks <= 320
                or isinstance(self.cadence, bool) or not isinstance(self.cadence, int) or self.cadence not in (1, 4, 8)):
            raise ValueError("Rest review requires a fixed 1/4/8 cadence and at most 320 physical ticks")
        if self.cancel_tick is not None and (isinstance(self.cancel_tick, bool) or not isinstance(self.cancel_tick, int)
                                             or not 0 <= self.cancel_tick <= self.horizon_ticks):
            raise ValueError("cancellation must be an original fixed external tick")
        if not all(isinstance(flag, bool) for flag in (self.navigation_enabled, self.attention_enabled,
                                                     self.extension_capability, self.competing_source, self.maternal_association_enabled)):
            raise TypeError("Rest review switches must be Boolean")

    def as_dict(self) -> dict[str, object]:
        """Disclose synthetic physics and scenario without returning live mutable state."""
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def rest_profile_v1(case: str = "nominal") -> RestExperimentProfileV1:
    """Construct predeclared physical conditions; no task result chooses the schedule."""
    if not isinstance(case, str) or case not in REST_CASES_V1:
        raise ValueError("unknown Rest case; no silent substitute")
    base = sustained_feeding_profile_v1("uptake_off" if case == "high_need" else "already_adequate")
    feeding, physiology = base.extraction, base.physiology
    if case == "nominal":
        feeding = suckle_extraction_profile_v1("stand_follow")
        run = replace(feeding.latch.run, physical=replace(feeding.latch.run.physical, initial_body=MotorBodyStateV1(0, 1)))
        task = replace(feeding.latch.suckle, sustained_feeding_enabled=True, extraction_outcomes_enabled=True,
                       extraction_outcome_attention_enabled=True, extraction_learning_hook_enabled=True)
        feeding = replace(feeding, latch=replace(feeding.latch, run=run, suckle=task))
        physiology = FeedingConsequenceProfileV1()
    run, seal = feeding.latch.run, feeding.latch.seal
    physical, oral = run.physical, run.oral
    context = None
    bearing = BodyBearingProfileV1(competence_enabled=case != "bearing_off", sensor_available=case != "bearing_sensor_off")
    if case in {"already_recumbent", "lateral_left", "lateral_right"}:
        physical = replace(physical, initial_body=MotorBodyStateV1(
            -80 if case == "lateral_left" else 80 if case == "lateral_right" else 0,
            1.0 if case.startswith("lateral") else .20))
        oral, seal = replace(oral, initial_extension_metres=0.0), replace(seal, initial_closure=0.0)
        context = RightingContextV1("supplied_initial_rest_activity", RightingActivityV1.REST)
    if case == "no_surface":
        physical = replace(physical, surface_present=False)
    if case == "lower_motor_off":
        physical = replace(physical, extension_motor_enabled=False)
    if case in {"release_drift", "release_drift_route_off", "release_drift_competing"}:
        seal = replace(seal, perturbations=(OralClosurePerturbationV1(15, 16, 1.0),))
    if case == "release_motor_off":
        seal = replace(seal, motor_enabled=False)
    if case == "withdraw_motor_off":
        oral = replace(oral, motor_enabled=False)
    if case == "missing_need":
        physiology = replace(physiology, sensor_available=False)
    if case == "need_loss":
        physiology = replace(physiology, unavailable_ticks=tuple(range(12, 161)))
    if case == "missing_seal":
        seal = replace(seal, seal_available=False)
    if case == "missing_reach":
        oral = replace(oral, extension_available=False)
    if case == "missing_body":
        physical = replace(physical, unavailable_channels=("support_extension",))
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=8)
    if case in {"feedback_gap", "support_loss", "post_rest_support_loss"}:
        start, stop = (70, 74) if case == "feedback_gap" else (66, 321) if case == "support_loss" else (240, 321)
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(
            start, stop, remove_support=case != "feedback_gap", drop_feedback=case == "feedback_gap"),))
    run = replace(run, physical=physical, oral=oral)
    feeding = replace(feeding, latch=replace(feeding.latch, run=run, seal=seal))
    return RestExperimentProfileV1(
        case, feeding, physiology, bearing,
        RestProfileV1(enabled=case != "rest_off", tendency_enabled=case != "tendency_off",
                      learning_hook_enabled=case != "hook_off", outcome_attention_enabled=case not in {"outcome_attention_off", "release_drift_route_off"}),
        context=context, cadence=1 if case == "cadence_1" else 8 if case == "cadence_8" else 4,
        cancel_tick=12 if case == "cancelled" else None, navigation_enabled=case != "navigation_off",
        attention_enabled=case != "attention_off", extension_capability=case != "no_capability",
        competing_source=case == "competing_source",
        maternal_association_enabled=case not in {"release_drift", "release_drift_route_off"})


def create_rest_trial_v1(profile: RestExperimentProfileV1, *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Create one isolated organism using existing owners and independent ablations."""
    if not isinstance(profile, RestExperimentProfileV1):
        raise TypeError("Rest trial requires a typed experiment profile")
    feeding, latch = profile.feeding, profile.feeding.latch
    run = latch.run
    capabilities = nominal_body_capabilities_v1()
    if not profile.extension_capability:
        capabilities = tuple(item for item in capabilities if item.kind.value != "support_extension")
    trial = IntegratedRightingTrialV1(
        run.physical, stream_id="rest_review_body", context=profile.context, planar_profile=run.planar, oral_profile=run.oral,
        oral_seal_profile=latch.seal, oral_extraction_profile=feeding.extraction, feeding_consequence_profile=profile.physiology,
        body_bearing_profile=profile.bearing, rest_profile=profile.rest, suckle_profile=latch.suckle,
        capabilities=(*capabilities, oral_body_capability_v1(), *((latch.capability,) if latch.capability is not None else ()),
                      *((feeding.capability,) if feeding.capability is not None else ())),
        follow_mom_profile=FollowMomProfileV1(association_enabled=profile.maternal_association_enabled, outcomes_enabled=run.stand_follow, outcome_attention_enabled=run.stand_follow,
                                             learning_hook_enabled=run.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=run.feeding, seek_nipple_profile=run.seeking,
        stand_follow_enabled=run.stand_follow, task_outcomes_enabled=run.stand_follow,
        task_outcome_attention_enabled=run.stand_follow, task_learning_hook_enabled=run.stand_follow,
        righting_target_inset_degrees=2.0, task_pnm_consumer_enabled=run.pnm_registration, trace_capacity=trace_capacity)
    _configure_controls(trial, profile)
    return trial


def _configure_controls(trial: IntegratedRightingTrialV1, profile: RestExperimentProfileV1) -> None:
    """Apply fixed owner ablations at construction/reset, never from an observer verdict."""
    if not profile.navigation_enabled:
        trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False, motor_preview_enabled=True)
    if not profile.attention_enabled:
        trial.core.cognition.attention = AttentionRuntimeV1(enabled=False)


def _durable(trial: IntegratedRightingTrialV1) -> str:
    """Measure actual existing durable sources; this signature is never a cognitive input."""
    owner = trial.core.feeding_detail
    if owner is None:
        raise RuntimeError("Rest review lost its declared feeding source")
    return json.dumps({"existing": maternal_durable_signature_v1(trial), "feeding": owner.durable_map.as_dict()},
                      sort_keys=True, allow_nan=False)


@dataclass(frozen=True, slots=True)
class RestExperimentV1:
    """Complete finite retained evidence, suitable for inspection but not restoring authority."""

    profile: RestExperimentProfileV1
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[SeekNipplePhysicalSampleV1, ...]
    durable_before: str
    durable_after: str
    handoff_consumptions: int
    installations: int

    def applications(self) -> tuple[RestApplicationV1, ...]:
        """Read actual Navigation-selected Rest applications, not planned stages."""
        return tuple(c.calculation.navigation.application for c in self.cycles
                     if isinstance(c.calculation.navigation.application, RestApplicationV1))

    def metrics(self) -> dict[str, object]:
        """Keep historical task completion, current safety and physical geometry separate."""
        completed = [c.calculation.cutoff_tick for c in self.cycles if c.rest is not None and c.rest.task is not None
                     and c.rest.task.status == "completed"]
        final = self.cycles[-1].rest if self.cycles else None
        body = self.physical_samples[-1] if self.physical_samples else None
        return {"physical_ticks": len(self.local_steps), "focal_opportunities": len(self.cycles),
                "rest_applications": len(self.applications()), "rest_application_ticks": [a.projection.basis.cutoff_tick for a in self.applications()],
                "first_completed_tick": completed[0] if completed else None,
                "final_task_status": final.task.status if final is not None and final.task is not None else "no_task",
                "current_safe_rest": final.current_safe_rest if final is not None else None,
                "final_extension": body.support.support_extension if body is not None else None,
                "final_tilt": body.support.body_tilt_degrees if body is not None else None,
                "handoff_consumptions": self.handoff_consumptions, "installations": self.installations,
                "durable_learning_updates": 0, "B99": "not_claimed"}

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Test returned evidence against declared controls; no check drives the organism."""
        applications = self.applications()
        targets = tuple(r.current for c in self.cycles for r in c.reservations
                        if isinstance(c.calculation.navigation.application, RestApplicationV1))
        outcomes = tuple(r for c in self.cycles if c.rest is not None for r in c.rest.outcomes)
        canonical = True
        try:
            for outcome in outcomes:
                validate_rest_outcome_v1(outcome)
        except (ValueError, TypeError):
            canonical = False
        completed = self.metrics()["first_completed_tick"] is not None
        actual_ticks = tuple(c.calculation.cutoff_tick for c in self.cycles)
        proof = True
        for cycle in self.cycles:
            rest = cycle.rest
            if rest is None:
                proof = False
                continue
            if rest.task is not None and rest.task.status == "completed":
                events = rest.task.completion_events
                witnesses = [c for c in self.cycles if c.rest is not None and c.rest.current_safe_rest is True
                             and c.calculation.source.motor_support is not None and c.calculation.source.motor_support.feedback is not None
                             and c.calculation.source.motor_support.feedback.event_tick in events
                             and rest_geometry_v1(c.calculation.source.motor_support.feedback) is True]
                proof = proof and len(events) == 3 and len(witnesses) >= 3 and events[-1] - events[0] >= 8
        authorized = True
        target_ids = {id(target) for target in targets}
        for step in self.local_steps:
            for report in step.reports:
                target = report.committed_target
                if not isinstance(target.target, BodyRelativeTargetV1) or target.target.rest_constraint is None:
                    continue
                authorized = authorized and id(target) in target_ids
                command = step.command
                drive = 0.0 if command is None else (command.oral_closure_drive or 0.0) if target.target.rest_constraint == "release" else (
                    (command.oral_drive or 0.0) if target.target.rest_constraint == "withdraw" else command.extension_drive)
                if drive:
                    authorized = (authorized and report.reported_tick == step.tick
                                  and report.disposition in {LocalTargetDispositionV1.ACTIVE, LocalTargetDispositionV1.PARTIAL}
                                  and target.committed_tick <= step.tick < target.expires_at_tick)
        registered = tuple(c.rest.registration for c in self.cycles if c.rest is not None and c.rest.registration is not None)
        original_claims = (len(registered) == len(applications) == len(outcomes)
                           and all(claim.application is app for claim, app in zip(registered, applications))
                           and all(outcome.claim is claim for outcome, claim in zip(outcomes, registered)))
        selected_sources = all(c.calculation.navigation.wnm is not None
                               and c.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "posture_support"
                               for c in self.cycles if isinstance(c.calculation.navigation.application, RestApplicationV1))
        return (
            ("complete_declared_schedule", actual_ticks == tuple(range(0, self.profile.horizon_ticks + 1, self.profile.cadence))
             and tuple(s.tick for s in self.local_steps) == tuple(range(self.profile.horizon_ticks))
             and tuple(s.tick for s in self.physical_samples) == tuple(range(self.profile.horizon_ticks + 1))),
            ("declared_completion_or_truthful_failure", completed == (self.profile.case in _COMPLETED_CASES)),
            ("one_original_source", selected_sources),
            ("original_PNM_and_fresh_handoff", all(c.commitment.pnm_id == c.calculation.navigation.application.projection.pnm.pnm_id
                and c.receipt.dispatch.motor is not None for c in self.cycles if isinstance(c.calculation.navigation.application, RestApplicationV1))),
            ("original_claims_canonical", canonical and original_claims and len({r.claim.application_id for r in outcomes}) == len(outcomes)),
            ("bounded_original_episode", len(applications) <= 8 and all(a.projection.basis.cutoff_tick < a.task.expires_at_tick for a in applications)),
            ("evidence_confirmed_dwell", proof),
            ("finite_authorized_targets", authorized and all(t.expires_at_tick - t.committed_tick <= 8 for t in targets)),
            ("one_interpretation_no_simultaneous_task", all(c.rest is None or c.rest.allocation is None
                or c.rest.allocation.kind != "interpretation" or c.commitment.selected_primitive_id is None for c in self.cycles)),
            ("actual_handoff_install_counts", self.handoff_consumptions == len(self.cycles)
             and self.installations == sum(bool(c.reservations) for c in self.cycles)),
            ("durable_sources_unchanged", self.durable_before == self.durable_after),
            ("zero_durable_learning", all(c.rest is not None and (c.rest.learning is None
                or c.rest.learning.as_dict()["durable_learning_updates"] == 0) for c in self.cycles)),
        )

    @property
    def review_status(self) -> str:
        """Return evidence qualification, not a task-success signal."""
        return "PASS" if all(ok for _, ok in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export retained evidence only; never construct or advance another trial."""
        return {"profile": self.profile.as_dict(), "metrics": self.metrics(), "checks": dict(self.checks()),
                "review_status": self.review_status, "cycles": [c.as_dict() for c in self.cycles],
                "local_steps": [s.as_dict() for s in self.local_steps],
                "observer_physical_samples": [s.as_dict() for s in self.physical_samples],
                "durable_before": self.durable_before, "durable_after": self.durable_after,
                "P16_2C": "candidate_for_user_acceptance", "B99": "not_claimed"}


class RestWalkthroughV1:
    """One paused, bounded experiment; user advancement and read-only browsing differ.

    ``advance`` calls the trial's existing focal method exactly once, then its
    existing physical method once for each scheduled intervening interval. No
    observer value selects an action. Retained snapshots can be browsed/exported
    without advancing or modifying the organism. Reset affects this instance only.
    """

    def __init__(self, profile: RestExperimentProfileV1, *, trace_capacity: int = 256) -> None:
        if not isinstance(profile, RestExperimentProfileV1):
            raise TypeError("walkthrough requires a declared Rest profile")
        self.profile = profile
        self.trial = create_rest_trial_v1(profile, trace_capacity=trace_capacity)
        self._cycles: list[IntegratedRightingCycleV1] = []
        self._steps: list[SensorimotorStepV1] = []
        self._physical: list[SeekNipplePhysicalSampleV1] = []
        self._before = _durable(self.trial)
        self._finished = False

    @property
    def finished(self) -> bool:
        """Report exhaustion of the external schedule, not successful Rest."""
        return self._finished

    def _observe(self) -> None:
        """Append an observer snapshot; no private physical value returns to cognition."""
        if self._physical and self._physical[-1].tick == self.trial.tick:
            return
        planar, oral = self.trial.observer_planar_body, self.trial.observer_oral_body
        if planar is None or oral is None:
            raise RuntimeError("Rest walkthrough requires the declared planar/oral provider")
        self._physical.append(SeekNipplePhysicalSampleV1(
            self.trial.tick, self.trial.observer_body, planar, oral, seal=self.trial.observer_oral_seal_body,
            extraction=self.trial.observer_oral_extraction_body, feeding_consequence=self.trial.observer_feeding_consequence))

    def advance(self) -> IntegratedRightingCycleV1:
        """Advance one explicit focal opportunity and its intervening physical interval."""
        if self._finished:
            raise ValueError("walkthrough schedule is complete; inspect or explicitly reset")
        tick = self.trial.tick
        self._observe()
        if tick == self.profile.cancel_tick:
            self.trial.cancel()
        cycle = self.trial.focal_step(visual_bid_priority=(100, 100) if self.profile.competing_source else None)
        self._cycles.append(cycle)
        stop = min(tick + self.profile.cadence, self.profile.horizon_ticks)
        for interval in range(tick, stop):
            if interval != tick and interval == self.profile.cancel_tick:
                self.trial.cancel()
            self._steps.append(self.trial.advance_lower())
            self._observe()
        if tick >= self.profile.horizon_ticks or stop == self.profile.horizon_ticks and stop % self.profile.cadence:
            self._finished = True
        return cycle

    def run_to_end(self) -> RestExperimentV1:
        """Use exactly the same explicit advance method until the fixed bound is reached."""
        while not self.finished:
            self.advance()
        return self.snapshot()

    def snapshot(self) -> RestExperimentV1:
        """Read retained records; partial schedules remain visibly incomplete reviews."""
        return RestExperimentV1(self.profile, tuple(self._cycles), tuple(self._steps), tuple(self._physical), self._before,
                                _durable(self.trial), self.trial.handoff_consumptions, self.trial.controller.installation_count)

    def inspect(self, index: int = -1) -> str:
        """Render one retained cycle; this never executes a second experiment."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("cycle index must be an integer")
        if not self._cycles:
            return "No retained cycle. Advance explicitly first."
        cycle = self._cycles[index]
        start = cycle.calculation.cutoff_tick
        stop = min(start + self.profile.cadence, self.profile.horizon_ticks)
        lines = [render_rest_cycle_v1(cycle), "EXTERNAL BODY / RETAINED INTERVENING EXECUTION (observer only)"]
        for step in self._steps:
            if start <= step.tick < stop:
                command = step.command
                lines.append(f"  Tick {step.tick}: drive={command.as_dict() if command is not None else '(none)'}; "
                             f"local results={[(r.committed_target.target.kind.value, r.disposition.value) for r in step.reports]}.")
        after = next((item for item in self._physical if item.tick == stop), None)
        if after is not None:
            lines.append(f"  Observed body at {stop}: {asdict(after.support)}; oral={after.oral.as_dict()}; "
                         f"seal={after.seal.as_dict() if after.seal else '(none)'}. Not backfilled into the earlier decision.")
        return "\n".join(lines)

    def export(self, path: str | Path) -> None:
        """Write a user-selected UTF-8 diagnostic file without restoring or advancing state.

        Refuse overwrite: a diagnostic export must not replace repository source or
        an existing review. No file is created unless the caller explicitly asks.
        """
        with Path(path).open("x", encoding="utf-8", newline="\n") as output:
            json.dump(self.snapshot().as_dict(), output, indent=2, allow_nan=False)
            output.write("\n")

    def reset(self) -> None:
        """Replace this organism's generation and retained records, never another session."""
        self.trial.reset()
        _configure_controls(self.trial, self.profile)
        self._cycles.clear()
        self._steps.clear()
        self._physical.clear()
        self._before, self._finished = _durable(self.trial), False


def run_rest_v1(case: str = "nominal", *, trace_capacity: int = 256) -> RestExperimentV1:
    """Run the same bounded walkthrough used by the menu; no success-driven scheduling."""
    return RestWalkthroughV1(rest_profile_v1(case), trace_capacity=trace_capacity).run_to_end()


def render_rest_cycle_v1(cycle: IntegratedRightingCycleV1) -> str:
    """Expose source, selection, PNM, body permission and subsequent evidence separately."""
    if not isinstance(cycle, IntegratedRightingCycleV1):
        raise TypeError("retained inspection requires an actual returned cycle")
    calculation, rest = cycle.calculation, cycle.rest
    wnm = calculation.navigation.wnm
    facet = calculation.source.motor_support
    feedback = None if facet is None else facet.feedback
    lines = [f"Cognitive cycle {calculation.cycle_id} | physical cutoff {calculation.cutoff_tick}",
             "C1 / BODY-SENSORY OWNER: current evidence, not a desired outcome"]
    if feedback is None:
        lines.append("  Current body acquisition unavailable.")
    else:
        lines.append(f"  Acquisition {feedback.sample_id}: event={feedback.event_tick}; available={feedback.available_tick}.")
        lines.append(f"  Tilt={feedback.body_tilt_degrees}; extension={feedback.support_extension}; "
                     f"limb contact={feedback.support_contact}; limb load={feedback.useful_loading}; instability={feedback.destabilization}.")
        lines.append(f"  Body bearing={feedback.body_bearing.as_dict() if feedback.body_bearing else 'unavailable'}.")
        lines.append(f"  Feeding need={feedback.feeding_deficit.as_dict() if feedback.feeding_deficit else 'unavailable'}.")
        lines.append(f"  Oral={feedback.oral.as_dict() if feedback.oral else 'unavailable'}; "
                     f"closure/seal={feedback.oral_seal.as_dict() if feedback.oral_seal else 'unavailable'}.")
    lines.extend(["D / ATTENTION AND NAVIGATION: one selected source and one demanding operation",
                  f"  WNM source={wnm.primary_source_state.source_map_ref.map_id if wnm else '(none)'}; "
                  f"selected IP={cycle.commitment.selected_primitive_id or '(none)'}.",
                  f"  Navigation reason={calculation.navigation.reason}.",
                  "E / TASK PNM AND BODYMAP: expected change is not execution",
                  f"  Original PNM={cycle.commitment.pnm_id or '(none)'}; receipt={cycle.receipt.receipt_id}."])
    application = calculation.navigation.application
    if application is not None:
        lines.append(f"  Task prospective relations={application.expected_relations}.")
    if cycle.sustained_feeding is not None:
        lines.append(f"  Suckle owner current status={cycle.sustained_feeding.as_dict()}; not a Rest selection instruction.")
    for reservation in cycle.reservations:
        target = reservation.current
        lines.append(f"  {target.target.kind.value}: {target.target.as_dict()}; expires={target.expires_at_tick}.")
    if not cycle.reservations:
        lines.append("  No new target installed by this focal result.")
    if rest is not None:
        lines.append(f"REST OWNER: {rest.reason}; historical task={rest.task.status if rest.task else '(none)'}; "
                     f"current safe rest={rest.current_safe_rest}.")
        if rest.task is not None:
            lines.append(f"  Original deadline={rest.task.expires_at_tick}; contributions={rest.task.applications}/8; "
                         f"completion events={rest.task.completion_events}.")
        for outcome in rest.outcomes:
            lines.append(f"C2 ORIGINAL OUTCOME: {outcome.claim.application_id}; {outcome.status}; "
                         f"event={outcome.claim.due_tick}; publication={outcome.published_tick}; {dict(outcome.relations)}.")
        if rest.allocation is not None:
            lines.append(f"  Rest question allocation={rest.allocation.kind}; "
                         f"interpretation={rest.allocation.interpretation.status if rest.allocation.interpretation else '(none)'}.")
        lines.append(f"F / SOURCE-OWNED RECONCILIATION: {rest.learning.as_dict() if rest.learning else 'hook disabled'}.")
    lines.append("Physical execution occurs after this focal record. Inspection performs no step. No durable learning is claimed.")
    return "\n".join(lines)


def render_rest_v1(result: RestExperimentV1, *, detail: bool = False) -> str:
    """Render measured results; a historical completed task is not permanent safety."""
    if not isinstance(result, RestExperimentV1) or not isinstance(detail, bool):
        raise TypeError("Rest renderer requires a retained result and Boolean detail")
    lines = [f"P16-2C-N Rest: {result.profile.case} -- {result.review_status}",
             "  Existing source -> Navigation-selected Rest -> BodyMap -> lower execution -> later supported dwell.",
             "  Synthetic body-bearing competence; no durable learning, automatic benchmark stage or B99 claim.",
             "  " + json.dumps(result.metrics(), sort_keys=True)]
    lines.extend(f"  {'PASS' if ok else 'FAIL'} {name}" for name, ok in result.checks())
    if detail:
        for cycle in result.cycles:
            rest = cycle.rest
            lines.append(f"  Tick {cycle.calculation.cutoff_tick}: {cycle.commitment.selected_primitive_id or '(no new task)'}; "
                         f"Rest={rest.reason if rest else 'missing'}; current_safe={rest.current_safe_rest if rest else None}")
    return "\n".join(lines)


def run_rest_menu_v1() -> None:
    """Menu 35: explicit stepping, read-only retained detail and the same shared reviews."""
    walkthrough: RestWalkthroughV1 | None = None
    retained: tuple[RestExperimentV1, ...] = ()
    while True:
        print("\nN: safe Rest / integrated feeding-to-Rest walkthrough; simulation pauses at this prompt.")
        print("1 start nominal; 2 advance one opportunity; 3 run remainder; 4 inspect latest; 5 inspect numbered cycle")
        print("6 all review cases; 7 retained summaries; 8 export current JSON; 9 reset this walkthrough; 0 return")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}:
            return
        try:
            if choice == "1":
                walkthrough = RestWalkthroughV1(rest_profile_v1())
                print("New isolated walkthrough at tick 0; no focal operation executed yet.")
            elif choice in {"2", "3", "4", "5", "8", "9"} and walkthrough is None:
                print("Start a walkthrough first.")
            elif choice == "2" and walkthrough is not None:
                walkthrough.advance()
                print(walkthrough.inspect())
                print(f"Next paused physical cutoff: {walkthrough.trial.tick}")
            elif choice == "3" and walkthrough is not None:
                retained = (walkthrough.run_to_end(),)
                print(render_rest_v1(retained[0]))
            elif choice == "4" and walkthrough is not None:
                print(walkthrough.inspect())
            elif choice == "5" and walkthrough is not None:
                print("Retained cycle number (1-based):")
                raw_number = cca8_cli.read_menu_input_v1()
                if raw_number is None:
                    raise ValueError("cycle number is required")
                number = int(raw_number)
                if number <= 0:
                    raise ValueError("cycle number must be positive")
                print(walkthrough.inspect(number - 1))
            elif choice == "6":
                retained = tuple(run_rest_v1(case) for case in REST_CASES_V1)
                print("\n\n".join(render_rest_v1(item) for item in retained))
            elif choice == "7":
                print("\n\n".join(render_rest_v1(item, detail=True) for item in retained) if retained else "No retained review.")
            elif choice == "8" and walkthrough is not None:
                print("New export file path (existing files are never overwritten):")
                path = cca8_cli.read_menu_input_v1()
                if path is None:
                    raise ValueError("export path is required")
                walkthrough.export(path)
                print("UTF-8 diagnostic export written; no simulation step.")
            elif choice == "9" and walkthrough is not None:
                walkthrough.reset()
                print("This walkthrough reset only; other sessions are unchanged.")
        except (ValueError, TypeError, IndexError, OSError) as error:
            print(f"Review request refused: {error}")
