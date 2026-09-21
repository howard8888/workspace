#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2B-F: combined maternal qualification, strictly outside cognitive authority.

This observer composes the accepted stand-follow profile with the maternal
correspondence, outcome-Attention and no-learning routes. The actual A-F core,
BodyMap, local executor and world remain unchanged. Fixed input interventions
are chosen before execution, never from task success or evaluator milestones.

Each live run uses one body and 160 lower intervals of 0.05 seconds, with one
focal opportunity every four intervals and a final boundary read: 41 in total.
Each task retains its own twenty-opportunity/eighty-tick limit. Source-only
motion/contradiction replays and original-recipient fixtures are retained as
separately labelled nonphysical evidence; they are not new physical Mom motion
or general Ready/offloading. A complete passing report supports review of the
P16-2B scope, not automatic acceptance, feeding, B99 or default promotion.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import PlanarPerturbationV1
from nca8_followmom_demo import (
    MATERNAL_REPLAY_CASES_V1, MaternalSourceReplayV1, follow_mom_owner_limits_v1,
    maternal_durable_signature_v1, run_maternal_source_replay_v1,
)
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_maternal_learning_demo import run_maternal_learning_routing_fixture_v1
from nca8_outcome_attention_demo import outcome_attention_owner_limits_v1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1
from nca8_stand_follow_demo import StandFollowPhysicalSampleV1, StandFollowProfileV1, stand_follow_profile_v1

__version__ = "0.1.0"
__all__ = [
    "FOLLOW_MOM_QUALIFICATION_CASES_V1", "FollowMomQualificationRunV1", "FollowMomQualificationCheckV1",
    "FollowMomQualificationReportV1", "follow_mom_qualification_profile_v1", "run_follow_mom_qualification_case_v1",
    "run_follow_mom_qualification_v1", "render_follow_mom_qualification_v1", "run_follow_mom_qualification_menu_v1", "__version__",
]

FOLLOW_MOM_QUALIFICATION_CASES_V1 = (
    "nominal", "brief_gap", "prolonged_gap", "support_loss", "righting_off", "following_off", "association_off",
    "translation_unavailable", "heading_90", "different_target", "already_supported", "motor_blocked", "boundary_aim",
    "drift_attention_on", "drift_attention_off", "drift_hook_off",
)
_DRIFT_CASES = ("drift_attention_on", "drift_attention_off", "drift_hook_off")
_COMPLETION_CASES = ("nominal", "brief_gap", "heading_90", "different_target", "already_supported", *_DRIFT_CASES)
_LIMITS = {
    **outcome_attention_owner_limits_v1(), **follow_mom_owner_limits_v1(),
    "maternal_attention_pending_requests": 8, "maternal_attention_previous_endpoint": 1,
    "maternal_attention_dependency": 1, "maternal_attention_dispositions": 32,
    "learning_participants": 8, "learning_dispositions": 32,
    "maternal_learning_participants": 8, "maternal_learning_dispositions": 32,
}


def follow_mom_qualification_profile_v1(case: str) -> StandFollowProfileV1:
    """Freeze one combined profile without constructing a brain or moving a body.

    Ordinary cases reuse the accepted C physical, source and capability settings.
    All enable maternal Attention and the no-learning hook. Drift cases preserve
    the E stand-drift forcing intervals [46,48) and [54,56), then add the D-style
    competing visual priority at cutoffs 56 and 60. The attention-off and hook-off
    controls disable only their named maternal route. Righting Attention remains
    disabled as in E; its correspondence and no-learning hook remain enabled.
    """
    if not isinstance(case, str) or case not in FOLLOW_MOM_QUALIFICATION_CASES_V1:
        raise ValueError("unknown combined Follow-Mom qualification case")
    base = stand_follow_profile_v1("nominal" if case in _DRIFT_CASES else case)
    maternal = replace(base.maternal, outcome_attention_enabled=case != "drift_attention_off",
                       learning_hook_enabled=case != "drift_hook_off")
    planar = base.planar
    if case in _DRIFT_CASES:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(46, 48, velocity=(0.6, 0.3)),
                                                PlanarPerturbationV1(54, 56, velocity=(0.6, 0.3))))
    return replace(base, case=case, maternal=maternal, planar=planar)


def _fixed_configuration(trial: IntegratedRightingTrialV1) -> str:
    """Capture actual fixed cognitive/control settings, not current task progress.

    This comparison supplements the three durable map signatures. The supplied
    immutable translation capability is recorded in the profile; no new private
    body-mapper access or authority is introduced for diagnostics.
    """
    operation = trial.core.follow_mom
    if operation is None:
        raise RuntimeError("qualification requires the configured maternal operation")
    return repr((trial.core.cognition.mapper.capabilities, trial.controller.profile,
                 trial.core.cognition.righting.context, trial.core.cognition.righting.target_inset_degrees, operation.profile))


def _source_id(cycle: IntegratedRightingCycleV1) -> str | None:
    """Read the source actually serving as WNM, not a preferred observer source."""
    working = cycle.calculation.navigation.wnm
    return None if working is None else working.primary_source_state.source_map_ref.map_id


def _translation_step(step: SensorimotorStepV1) -> bool:
    """Recognize an actual nonzero translation drive independently of task labels."""
    drive = step.command.translation if step.command is not None else None
    return drive is not None and (drive.forward != 0.0 or drive.left != 0.0)


@dataclass(frozen=True, slots=True)
class FollowMomQualificationRunV1:
    """Finite observer evidence from one isolated live run, not a saved organism.

    Physical samples include the initial boundary followed by each real lower
    step. Historical cycle records, claims and hook reports remain immutable.
    The exported result has no API for restoring actuator permission. Diagnostics
    may be truncated independently of these finite external evidence tuples.
    """

    profile: StandFollowProfileV1
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[StandFollowPhysicalSampleV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str
    fixed_before: str
    fixed_after: str
    handoff_consumptions: int
    target_installations: int

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Reject unknown/negative/over-limit counts, never silently ignore an owner."""
        return tuple(name for name, value in self.peak_counts
                     if name not in _LIMITS or isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _LIMITS[name])

    def metrics(self) -> dict[str, object]:
        """Compute task, focal, motor and F observations only after execution ends."""
        righting = [c.calculation.cutoff_tick for c in self.cycles
                    if c.calculation.task is not None and c.calculation.task.status == "completed"]
        completed = [c.calculation.cutoff_tick for c in self.cycles
                     if c.maternal_task is not None and c.maternal_task.task is not None and c.maternal_task.task.status == "completed"]
        follow = [c.calculation.cutoff_tick for c in self.cycles if c.commitment.selected_primitive_id == "ip:follow_mom"]
        reports = tuple(c.maternal_learning_report for c in self.cycles if c.maternal_learning_report is not None)
        final = self.cycles[-1].maternal_task if self.cycles else None
        task = None if final is None else final.task
        return {
            "case": self.profile.case, "physical_ticks": len(self.local_steps), "focal_opportunities": len(self.cycles),
            "elapsed_seconds": len(self.local_steps) * 0.05,
            "righting_completed_at_tick": righting[0] if righting else None,
            "first_follow_at_tick": follow[0] if follow else None,
            "proximity_completed_at_tick": completed[0] if completed else None,
            "maternal_final_status": task.status if task is not None else "no_task",
            "maternal_applications": task.applications if task is not None else 0,
            "translation_command_intervals": sum(_translation_step(step) for step in self.local_steps),
            "target_installations": self.target_installations, "handoff_consumptions": self.handoff_consumptions,
            "interpretation_ticks": [c.calculation.cutoff_tick for c in self.cycles if c.maternal_attention is not None
                                     and c.maternal_attention.allocation.kind == "interpretation"],
            "response_ticks": [c.calculation.cutoff_tick for c in self.cycles if c.maternal_attention is not None
                                and c.maternal_attention.allocation.kind == "response_reconsideration"],
            "righting_F_calls": sum(c.learning_report is not None for c in self.cycles), "maternal_F_calls": len(reports),
            "maternal_dispositions": dict(sorted(Counter(d.status for r in reports for d in r.dispositions).items())),
            "durable_unchanged": self.durable_before == self.durable_after,
            "fixed_configuration_unchanged": self.fixed_before == self.fixed_after,
            "durable_learning_updates": 0, "causal_credit": "not_established_by_completion",
        }

    def as_dict(self) -> dict[str, object]:
        """Export detached observations; the profile discloses all selective controls."""
        return {
            "profile": {**self.profile.as_dict(), "profile": "follow_mom_qualification_v1",
                        "righting_correspondence": True, "righting_learning_hook": True, "righting_outcome_attention": False,
                        "visual_competitor": {"cutoffs": [56, 60], "priority": [10, 60]} if self.profile.case in _DRIFT_CASES else None},
            "metrics": self.metrics(), "cycles": [c.as_dict() for c in self.cycles],
            "local_steps": [s.as_dict() for s in self.local_steps],
            "observer_physical_samples": [s.as_dict() for s in self.physical_samples],
            "final_feedback": self.final_feedback.as_dict(), "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations), "restores_motor_permission": False,
        }


def run_follow_mom_qualification_case_v1(
    case: str = "nominal", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> FollowMomQualificationRunV1:
    """Run a predeclared case through the existing core; never select tasks here.

    The only scheduling branches depend on fixed tick or predeclared input gaps.
    Every focal call consumes its own closed handoff without moving the world;
    every lower call advances exactly one interval. A final read at tick160
    supplies no extra physical time. Faults propagate rather than become PASS.
    """
    profile = follow_mom_qualification_profile_v1(case)
    trial = IntegratedRightingTrialV1(
        profile.physical, stream_id="follow_mom_qualification_body", planar_profile=profile.planar,
        follow_mom_profile=profile.maternal, translation_capability=profile.translation,
        righting_enabled=profile.righting_enabled, righting_target_inset_degrees=profile.target_inset_degrees,
        task_outcomes_enabled=True, task_learning_hook_enabled=True, stand_follow_enabled=True,
        trace_capacity=trace_capacity, learning_diagnostic_capacity=diagnostic_capacity,
    )
    before, fixed_before = maternal_durable_signature_v1(trial), _fixed_configuration(trial)
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[StandFollowPhysicalSampleV1] = []
    peaks: dict[str, int] = {}

    def inspect(*, body: bool = False) -> None:
        """Observe real storage after each call, with no influence on that call."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)
        if body:
            planar = trial.observer_planar_body
            if planar is None:
                raise RuntimeError("qualification lost its physical planar provider")
            physical.append(StandFollowPhysicalSampleV1(trial.tick, trial.observer_body, planar))

    inspect(body=True)
    for tick in range(160):
        if tick % 4 == 0:
            priority = (10, 60) if case in _DRIFT_CASES and tick in (56, 60) else None
            cycles.append(trial.focal_step(visual_input_enabled=tick not in profile.visual_gap_cutoffs, visual_bid_priority=priority))
            inspect()
        local.append(trial.advance_lower())
        inspect(body=True)
    cycles.append(trial.focal_step())
    inspect()
    return FollowMomQualificationRunV1(
        profile, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback, tuple(sorted(peaks.items())),
        before, maternal_durable_signature_v1(trial), fixed_before, _fixed_configuration(trial),
        trial.handoff_consumptions, trial.controller.installation_count,
    )


@dataclass(frozen=True, slots=True)
class FollowMomQualificationCheckV1:
    """One observer assertion with its evidence description, not a cognitive rule."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        """Return an independent small JSON-compatible assessment."""
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _run_checks(run: FollowMomQualificationRunV1) -> tuple[FollowMomQualificationCheckV1, ...]:
    """Check the combined run rather than trusting its completion/status banner."""
    checks: list[FollowMomQualificationCheckV1] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append(FollowMomQualificationCheckV1(f"{run.profile.case}/{name}", bool(passed), detail))

    cycles, local = run.cycles, run.local_steps
    metrics = run.metrics()
    check("fixed_profile", run.profile == follow_mom_qualification_profile_v1(run.profile.case), "predeclared conditions unchanged")
    timeline_ok = (tuple(s.tick for s in local) == tuple(range(160))
                   and tuple(s.tick for s in run.physical_samples) == tuple(range(161))
                   and tuple(c.calculation.cutoff_tick for c in cycles) == tuple(range(0, 161, 4))
                   and tuple(c.commitment.cycle_id for c in cycles) == tuple(range(1, 42)))
    check("time_and_handoff", timeline_ok and run.handoff_consumptions == len(cycles)
          and run.target_installations == sum(bool(c.reservations) for c in cycles), "160 physical intervals / 41 focal handoffs; no resets")
    counts = dict(run.peak_counts)
    required = {"wnm", "current_pnm", "durable_maps", "visual_durable_maps", "maternal_durable_maps", "learning_participants"}
    if run.profile.maternal.learning_hook_enabled:
        required.add("maternal_learning_participants")
    if run.profile.maternal.outcome_attention_enabled:
        required.add("maternal_attention_pending_requests")
    check("owner_bounds", bool(counts) and required <= counts.keys() and len(counts) == len(run.peak_counts)
          and not run.bound_violations, f"actual measured owner counts; violations={list(run.bound_violations)}")
    check("no_durable_change", bool(run.durable_before) and run.durable_before == run.durable_after
          and bool(run.fixed_before) and run.fixed_before == run.fixed_after, "three source organizations and fixed configuration preserved")
    check("actual_F", bool(cycles) and all(c.learning_report is not None for c in cycles)
          and all((c.maternal_learning_report is not None) == run.profile.maternal.learning_hook_enabled for c in cycles),
          "both original recipients use the existing F; maternal-off constructs no maternal hook report")
    interpretations = [c for c in cycles if c.maternal_attention is not None and c.maternal_attention.allocation.kind == "interpretation"]
    check("single_focal_work", all(c.commitment.selected_primitive_id is None and c.commitment.pnm_id is None
                                  and not c.reservations for c in interpretations), "interpretation does not also issue another IP/PNM/target")
    completed = [c for c in cycles if c.maternal_task is not None and c.maternal_task.task is not None
                 and c.maternal_task.task.status == "completed"]
    dwell_ok = True
    if completed:
        first = completed[0]
        assessment = first.maternal_task
        if assessment is None or assessment.task is None:
            dwell_ok = False
        else:
            samples = assessment.supported_samples
            event_ticks = [s.event_tick for s in samples if s.event_tick is not None]
            dwell_ok = (len(samples) == 3 and len({s.sample_id for s in samples if s.sample_id is not None}) == 3
                        and len(event_ticks) == 3 and event_ticks[-1] - event_ticks[0] >= 8
                        and all(s.separation is not None and s.separation <= 0.5 and s.target_position is not None for s in samples)
                        and first.calculation.cutoff_tick - assessment.task.started_tick <= 80
                        and first.commitment.cycle_id - assessment.task.started_cycle <= 20)
    check("supported_completion", dwell_ok, "completion requires distinct current samples, physical dwell and original task limits")
    accepted = [d for c in cycles if c.maternal_learning_report is not None
                for d in c.maternal_learning_report.dispositions if d.status == "accepted_no_update"]
    check("original_evidence_once", len({d.pnm_id for d in accepted}) == len(accepted)
          and all(d.outcome is not None and d.outcome.evidence is not None
                  and d.outcome.evidence.available_tick <= d.cutoff_tick and bool(d.accepted_relations) for d in accepted),
          "one accepted no-update disposition per original claim; no unobserved future evidence")
    expected_completion = run.profile.case in _COMPLETION_CASES
    check("declared_outcome", bool(completed) == expected_completion, f"completion expected={expected_completion}; observed={metrics['maternal_final_status']}")
    if run.profile.case == "already_supported":
        check("no_forced_righting", bool(cycles) and all(c.calculation.task is None for c in cycles)
              and cycles[0].commitment.selected_primitive_id == "ip:follow_mom", "supported start follows directly without a stage-list Righting step")
    elif expected_completion:
        righting = [c.calculation.cutoff_tick for c in cycles if c.calculation.task is not None and c.calculation.task.status == "completed"]
        following = [c.calculation.cutoff_tick for c in cycles if c.commitment.selected_primitive_id == "ip:follow_mom"]
        check("source_driven_transition", bool(righting and following) and righting[0] < following[0], "evidence-backed Righting closes before Follow-Mom")
    if run.profile.visual_gap_cutoffs:
        gaps = [c for c in cycles if c.calculation.cutoff_tick in run.profile.visual_gap_cutoffs]
        check("gap_withholds_precision", len(gaps) == len(run.profile.visual_gap_cutoffs)
              and all(c.maternal_source is not None and c.maternal_source.target_position is None and not c.reservations for c in gaps),
              "missing vision retains no precise movement target")
    if run.profile.case == "brief_gap":
        tasks = {c.maternal_task.task.task_id for c in cycles if c.maternal_task is not None and c.maternal_task.task is not None}
        check("same_task_return", len(tasks) == 1 and any(c.calculation.cutoff_tick > 60 and c.reservations for c in cycles),
              "fresh evidence resumes the same bounded task after the fixed gap")
    elif run.profile.case == "prolonged_gap":
        check("no_automatic_restart", metrics["maternal_final_status"] == "target_unavailable"
              and not any(c.reservations for c in cycles if c.calculation.cutoff_tick >= 76), "expired target availability is a terminal exit")
    elif run.profile.case == "support_loss":
        check("local_protection", not any(_translation_step(s) for s in local if s.tick >= 60)
              and any(s.significant_events_added for s in local if 57 <= s.tick < 60),
              "physical support loss at57 stops translation before the next focal boundary60")
    elif run.profile.case in {"righting_off", "following_off", "association_off", "translation_unavailable", "boundary_aim"}:
        check("no_hidden_rescue", not any(_translation_step(s) for s in local), "unavailable required mechanism does not fall back to hidden following")
    elif run.profile.case == "motor_blocked":
        check("attempt_is_not_motion", any(_translation_step(s) for s in local)
              and all(s.planar.position == (0.0, 0.0) for s in run.physical_samples), "commands occur but the blocked physical body does not translate")
    return tuple(checks)


def _hook_neutral_cycle(cycle: IntegratedRightingCycleV1) -> IntegratedRightingCycleV1:
    """Remove only the maternal F report and its two route-enabled metadata flags.

    These flags describe hook configuration, not evidence, a decision or a motor
    permission. All source/claim/interpretation/commitment content stays intact.
    """
    attention = None if cycle.maternal_attention is None else replace(cycle.maternal_attention, learning_enabled=False)
    correspondence = None if cycle.maternal_correspondence is None else replace(cycle.maternal_correspondence, learning_enabled=False)
    return replace(cycle, maternal_learning_report=None, maternal_attention=attention, maternal_correspondence=correspondence)


def _pair_checks(runs: tuple[FollowMomQualificationRunV1, ...]) -> tuple[FollowMomQualificationCheckV1, ...]:
    """Compare full evidence, not merely endpoint equality or generated PASS flags."""
    by_case = {r.profile.case: r for r in runs}
    checks: list[FollowMomQualificationCheckV1] = []
    on, off = by_case.get("drift_attention_on"), by_case.get("drift_attention_off")
    if on is not None and off is not None:
        matching_conditions = (replace(on.profile, case=off.profile.case,
                                       maternal=replace(on.profile.maternal, outcome_attention_enabled=False)) == off.profile)
        on_by_tick = {c.calculation.cutoff_tick: c for c in on.cycles}
        off_by_tick = {c.calculation.cutoff_tick: c for c in off.cycles}
        on60, off60 = on_by_tick.get(60), off_by_tick.get(60)
        isolated = False
        if on60 is not None and off60 is not None:
            isolated = (on60.maternal_source == off60.maternal_source and on60.visual_source == off60.visual_source
                        and on60.calculation.source == off60.calculation.source
                        and on60.maternal_correspondence is not None
                        and replace(on60.maternal_correspondence, attention_enabled=False) == off60.maternal_correspondence
                        and _source_id(on60) == "maternal_target" and _source_id(off60) == "visual_scene"
                        and on60.maternal_attention is not None and on60.maternal_attention.allocation.kind == "interpretation")
        checks.append(FollowMomQualificationCheckV1(
            "pair/attention_allocation", matching_conditions and isolated
            and tuple(s for s in on.local_steps if s.tick < 60) == tuple(s for s in off.local_steps if s.tick < 60),
            "same physical/source/claim history through tick60; only the maternal outcome route wins the focal contrast",
        ))
        responses = [c.calculation.cutoff_tick for c in on.cycles if c.maternal_attention is not None
                     and c.maternal_attention.allocation.kind == "response_reconsideration"]
        actual_interpretation = on60.maternal_attention.allocation.interpretation if on60 is not None and on60.maternal_attention is not None else None
        taught = on60.maternal_learning_report.dispositions if on60 is not None and on60.maternal_learning_report is not None else ()
        checks.append(FollowMomQualificationCheckV1(
            "pair/interpretation_before_F", actual_interpretation is not None
            and any(d.status == "accepted_no_update" and d.interpretation is actual_interpretation for d in taught),
            "the existing focal interpretation actually releases its original dependent maternal contribution at F",
        ))
        off_accepted = [d for c in off.cycles if c.maternal_learning_report is not None
                        for d in c.maternal_learning_report.dispositions if d.status == "accepted_no_update"]
        off_expired = [d for c in off.cycles if c.maternal_learning_report is not None
                       for d in c.maternal_learning_report.dispositions if d.status == "eligibility_expired"]
        checks.append(FollowMomQualificationCheckV1(
            "pair/no_free_interpretation", bool(off_expired) and all(d.outcome is not None and d.outcome.status != "mismatch" for d in off_accepted),
            "with Attention routing disabled, discrepant participation expires rather than receiving free interpretation",
        ))
        checks.append(FollowMomQualificationCheckV1("pair/later_response", bool(responses) and responses[0] > 60,
                                                   "dependent response waits for a later existing focal opportunity; no speed benefit required"))
    hook_off = by_case.get("drift_hook_off")
    if on is not None and hook_off is not None:
        same_profile = (replace(on.profile, case=hook_off.profile.case,
                                maternal=replace(on.profile.maternal, learning_hook_enabled=False)) == hook_off.profile)
        neutral = (tuple(_hook_neutral_cycle(c) for c in on.cycles) == tuple(_hook_neutral_cycle(c) for c in hook_off.cycles)
                   and on.local_steps == hook_off.local_steps and on.physical_samples == hook_off.physical_samples
                   and on.final_feedback == hook_off.final_feedback)
        checks.append(FollowMomQualificationCheckV1("pair/hook_neutrality", same_profile and neutral,
                                                   "entire cognitive/motor/physical records equal except the maternal F report and two hook-enabled labels"))
    nominal, heading = by_case.get("nominal"), by_case.get("heading_90")
    if nominal is not None and heading is not None:
        a = [r.current.target for c in nominal.cycles for r in c.reservations if isinstance(r.current.target, BodyTranslationTargetV1)]
        b = [r.current.target for c in heading.cycles for r in c.reservations if isinstance(r.current.target, BodyTranslationTargetV1)]
        same_path = (len(nominal.physical_samples) == len(heading.physical_samples)
                     and all(math.dist(x.planar.position, y.planar.position) < 1e-9
                             for x, y in zip(nominal.physical_samples, heading.physical_samples)))
        checks.append(FollowMomQualificationCheckV1("pair/body_heading", bool(a and b) and a[0].origin == b[0].origin
                                                   and math.isclose(a[0].offset[0], -b[0].offset[1], abs_tol=1e-12)
                                                   and math.isclose(a[0].offset[1], b[0].offset[0], abs_tol=1e-12) and same_path,
                                                   "changed body heading changes egocentric target while preserving the physical destination/path"))
    return tuple(checks)


@dataclass(frozen=True, slots=True)
class FollowMomQualificationReportV1:
    """Combined review with explicit incomplete coverage and independent evidence lanes.

    A report can contain a selected live case without claiming the full matrix.
    Duplicate/unknown case identities and mutable input collections are rejected.
    A complete PASS still needs the external static/pytest/preflight wall and
    Howard's acceptance; it does not automatically change repository authority.
    """

    runs: tuple[FollowMomQualificationRunV1, ...]
    source_replays: tuple[MaternalSourceReplayV1, ...] = ()
    routing_fixtures: tuple[tuple[str, tuple[IntegratedRightingCycleV1, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.runs, tuple) or not self.runs or any(not isinstance(r, FollowMomQualificationRunV1) for r in self.runs):
            raise ValueError("qualification requires a nonempty immutable tuple of live results")
        names = [r.profile.case for r in self.runs]
        if len(set(names)) != len(names) or any(n not in FOLLOW_MOM_QUALIFICATION_CASES_V1 for n in names):
            raise ValueError("duplicate or unknown qualification case")
        if not isinstance(self.source_replays, tuple) or any(not isinstance(r, MaternalSourceReplayV1) for r in self.source_replays):
            raise TypeError("source replays must be an immutable tuple of source-only results")
        replay_names = [r.case for r in self.source_replays]
        if len(set(replay_names)) != len(replay_names) or any(n not in MATERNAL_REPLAY_CASES_V1 for n in replay_names):
            raise ValueError("duplicate or unknown source replay")
        if not isinstance(self.routing_fixtures, tuple):
            raise TypeError("routing fixtures must be immutable")
        route_names: list[str] = []
        for fixture in self.routing_fixtures:
            if (not isinstance(fixture, tuple) or len(fixture) != 2 or fixture[0] not in {"eligible", "expired"}
                    or not isinstance(fixture[1], tuple) or not fixture[1]
                    or any(not isinstance(c, IntegratedRightingCycleV1) for c in fixture[1])):
                raise ValueError("malformed original-recipient fixture")
            route_names.append(fixture[0])
        if len(set(route_names)) != len(route_names):
            raise ValueError("duplicate original-recipient fixture")

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        """List unrun cases; absence is never silently converted into a passing check."""
        live = {r.profile.case for r in self.runs}
        replay = {r.case for r in self.source_replays}
        routing = {name for name, _ in self.routing_fixtures}
        return (tuple(f"live:{name}" for name in FOLLOW_MOM_QUALIFICATION_CASES_V1 if name not in live)
                + tuple(f"source_replay:{name}" for name in MATERNAL_REPLAY_CASES_V1 if name not in replay)
                + tuple(f"routing_fixture:{name}" for name in ("eligible", "expired") if name not in routing))

    def checks(self) -> tuple[FollowMomQualificationCheckV1, ...]:
        """Evaluate retained records only; never rerun a world or call a learning owner."""
        checks = [check for run in self.runs for check in _run_checks(run)]
        checks.extend(_pair_checks(self.runs))
        expected = {"independent_approach": "independently_approaching_target_wait", "own_closing": "initiate_following",
                    "contradiction": "maternal_location_unavailable", "relocated_target": "initiate_following"}
        for replay in self.source_replays:
            passed = len(replay.sources) == 2 and len(replay.dispositions) == 2 and replay.dispositions[-1] == expected[replay.case]
            if replay.case == "contradiction" and replay.sources:
                passed = (passed and replay.sources[-1].identity_status == "contradicted"
                          and replay.sources[-1].target_position is None and replay.sources[-1].possible_center is None)
            checks.append(FollowMomQualificationCheckV1(f"source_replay/{replay.case}", passed,
                                                       "supplied source/applicability evidence only; zero physical steps or selected applications"))
        for name, records in self.routing_fixtures:
            first, last = records[0], records[-1]
            original = first.maternal_learning_report.new_participation if first.maternal_learning_report is not None else None
            report = last.maternal_learning_report
            passed = False
            if original is not None and report is not None and last.maternal_source is not None and len(report.dispositions) == 1:
                disposition = report.dispositions[0]
                selected = last.calculation.attention.selected_bid
                passed = (selected is not None and selected.candidate_id == "fixture:competing_source"
                          and not last.maternal_source.focal_accessible and last.maternal_source.target_position is None
                          and report.recipient_id == original.recipient_id and disposition.outcome is not None
                          and disposition.outcome.claim == original.claim and disposition.outcome.status == "matched"
                          and disposition.status == ("accepted_no_update" if name == "eligible" else "rejected_expired_eligibility"))
                if name == "expired":
                    passed = passed and any(c.commitment.cycle_id == original.expires_before_cycle
                                            and c.maternal_correspondence is not None and c.maternal_correspondence.pending
                                            and c.maternal_learning_report is not None and not c.maternal_learning_report.pending for c in records)
            checks.append(FollowMomQualificationCheckV1(f"routing_fixture/{name}", bool(passed),
                                                       "synthetic endpoint/core-F evidence; A remains recipient while B is focal; no physical world steps"))
        return tuple(checks)

    @property
    def status(self) -> str:
        """FAIL overrides incomplete coverage; only complete experimental evidence earns PASS."""
        if any(not c.passed for c in self.checks()):
            return "FAIL"
        return "PARTIAL" if self.missing_evidence else "PASS"

    def as_dict(self) -> dict[str, object]:
        """Export finite independent lanes and scope; this is not a cognitive save file."""
        return {
            "profile": "follow_mom_qualification_v1", "status": self.status,
            "acceptance": "requires_local_validation_and_Howard_review", "scope": "P16-2B_only_not_B99",
            "missing_evidence": list(self.missing_evidence), "checks": [c.as_dict() for c in self.checks()],
            "live_runs": [r.as_dict() for r in self.runs], "source_replays": [r.as_dict() for r in self.source_replays],
            "routing_fixtures": [{"case": name, "physical_steps": 0, "evidence": "supplied_endpoint_core_routing_fixture",
                                  "cycles": [c.as_dict() for c in records]} for name, records in self.routing_fixtures],
            "next_after_acceptance": "P16-2C_feeding_detail_contact_suckling_rest",
            "limits": ["seeded maternal identity", "no physical Mom motion in the source replays", "no general Ready/offloading",
                       "fixed surrogate/control, no durable learner", "no full hard-newborn feeding/rest or B99", "legacy remains default"],
        }


def run_follow_mom_qualification_v1(
    case: str = "all", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> FollowMomQualificationReportV1:
    """Run the selected fixed evidence set once; full mode adds the six nonphysical controls.

    A single-case report intentionally remains PARTIAL. It can expose a passing
    adverse outcome without claiming that unrun controls passed. Test failures,
    missing completion or broken invariants remain FAIL; no attempt is retried.
    """
    if not isinstance(case, str) or case not in ("all", *FOLLOW_MOM_QUALIFICATION_CASES_V1):
        raise ValueError("unknown qualification selector")
    cases = FOLLOW_MOM_QUALIFICATION_CASES_V1 if case == "all" else (case,)
    runs = tuple(run_follow_mom_qualification_case_v1(c, trace_capacity=trace_capacity, diagnostic_capacity=diagnostic_capacity) for c in cases)
    replays = tuple(run_maternal_source_replay_v1(c) for c in MATERNAL_REPLAY_CASES_V1) if case == "all" else ()
    routing = tuple((name, run_maternal_learning_routing_fixture_v1(expired=name == "expired"))
                    for name in ("eligible", "expired")) if case == "all" else ()
    return FollowMomQualificationReportV1(runs, replays, routing)


def render_follow_mom_qualification_v1(report: FollowMomQualificationReportV1, *, detail: bool = False) -> str:
    """Render the completed evidence without repeating experiments or changing RNG.

    Compact output gives one row per run, aggregate checks and every failure.
    Detail adds the actual focal source, task, PNM, target and F decisions. It does
    not emit full per-tick trace walls by default or manufacture missing evidence.
    """
    if not isinstance(report, FollowMomQualificationReportV1) or not isinstance(detail, bool):
        raise TypeError("qualification rendering requires a report and Boolean detail")
    checks = report.checks()
    lines = ["P16-2B-F COMBINED FOLLOW-MOM QUALIFICATION",
             "  One existing core/body per live run; fixed160 ticks /8.0s /41 focal opportunities. No task stage list.",
             "  Maternal Attention + both no-learning recipients enabled, except the named maternal-route controls.",
             "  Righting outcome Attention remains disabled; this is not a new dual-domain mismatch experiment."]
    for run in report.runs:
        values = run.metrics()
        lines.append(f"  {run.profile.case}: Righting={values['righting_completed_at_tick']}; follow={values['first_follow_at_tick']}; "
                     f"proximity={values['proximity_completed_at_tick']}; final={values['maternal_final_status']}; "
                     f"interpret={values['interpretation_ticks']}; response={values['response_ticks']}")
        lines.append(f"    F maternal/righting={values['maternal_F_calls']}/{values['righting_F_calls']}; "
                     f"bounds={list(run.bound_violations)}; durable unchanged={values['durable_unchanged']}; "
                     f"fixed configuration unchanged={values['fixed_configuration_unchanged']}")
        if detail:
            for cycle in run.cycles:
                frame = cycle.maternal_task
                learning = cycle.maternal_learning_report
                lines.append(f"    tick={cycle.calculation.cutoff_tick} WNM={_source_id(cycle)}; "
                             f"IP={cycle.commitment.selected_primitive_id}; PNM={cycle.commitment.pnm_id}; "
                             f"maternal={None if frame is None else frame.reason}; targets={len(cycle.reservations)}; "
                             f"F={None if learning is None else [d.status for d in learning.dispositions]}")
    lines.append(f"  SOURCE-ONLY REPLAYS: {len(report.source_replays)}; zero physical steps / zero selected applications.")
    lines.append(f"  SYNTHETIC ORIGINAL-RECIPIENT FIXTURES: {len(report.routing_fixtures)}; zero physical world steps; not general Ready.")
    lines.append(f"  CHECKS: {sum(c.passed for c in checks)}/{len(checks)}; evidence sets={len(report.runs) + len(report.source_replays) + len(report.routing_fixtures)}/22")
    lines.extend(f"    FAIL {c.name}: {c.detail}" for c in checks if not c.passed)
    lines.append(f"  RESULT: {report.status}; missing evidence={list(report.missing_evidence)}")
    lines.append("  P16-2B experimental qualification only; local wall and Howard acceptance still required. No feeding/rest, B99 or default promotion.")
    return "\n".join(lines)


def run_follow_mom_qualification_menu_v1() -> None:
    """Open a read-only menu14 review; entering/returning alone performs no trial.

    Run the complete report once to inspect the full qualification. Individual
    selected profiles deliberately show PARTIAL and never pretend to close 2B.
    The existing A0 session is neither passed in nor reset by this host utility.
    """
    selectors = {"1": "all", "2": "nominal", "3": "brief_gap", "4": "prolonged_gap", "5": "support_loss", "6": "drift_attention_on"}
    while True:
        print("\nP16-2B-F -- COMBINED FOLLOW-MOM QUALIFICATION\n"
              "  1) Complete qualification (compact; all live and nonphysical controls)\n"
              "  2) Detailed nominal / 3) Detailed brief gap / 4) Detailed prolonged gap\n"
              "  5) Detailed support loss / 6) Detailed maternal interpretation\n"
              "  Enter returns without resetting the existing session")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice not in selectors:
            print("Choose 1-6 or press Enter to return.")
            continue
        print(render_follow_mom_qualification_v1(run_follow_mom_qualification_v1(selectors[choice]), detail=choice != "1"))
