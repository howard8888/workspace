#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared M review of sustained feeding, body evidence and intrinsic completion.

The existing fixed-schedule collector calls the integrated organism and records
its returned evidence. It never picks an action from observer state. The nominal
run includes seeking and latch; already-sealed entry is a separate control.
The optional body provider assumes downstream uptake competence, not realistic
digestion. Measured need is not reward, task success, causal credit or Rest.
No results from this module are imported by the cognitive implementation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json

import cca8_cli
from cca8_support_world import FeedingConsequenceProfileV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_nipple_demo import SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleExtractionApplicationV1, SuckleFeedingAssessmentV1
from nca8_suckle_extraction_demo import (
    SuckleExtractionExperimentProfileV1, create_suckle_extraction_trial_v1, suckle_extraction_profile_v1,
)
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeV1

__version__ = "0.1.0"
__all__ = ["SUSTAINED_FEEDING_CASES_V1", "SustainedFeedingProfileV1", "SustainedFeedingExperimentV1",
           "sustained_feeding_profile_v1", "create_sustained_feeding_trial_v1", "run_sustained_feeding_v1",
           "render_sustained_feeding_v1", "run_sustained_feeding_menu_v1", "__version__"]
SUSTAINED_FEEDING_CASES_V1 = (
    "nominal", "already_sealed", "latch_then_extract", "small_need", "larger_need", "slow_uptake", "uptake_off",
    "dry", "depleted", "milk_sensor_off", "internal_sensor_off", "internal_loss_after_receipt", "internal_gap",
    "already_adequate", "blocked_motor", "no_capability", "support_loss", "body_shift", "cancelled",
    "attention_off", "attention_runtime_off", "navigation_off", "source_off", "suckle_off",
    "cadence_1", "cadence_8", "hook_off", "outcome_attention_off", "missing_stroke",
)
_COMPLETES = frozenset({"nominal", "already_sealed", "latch_then_extract", "small_need", "larger_need", "slow_uptake",
                       "milk_sensor_off", "internal_gap", "cadence_1", "cadence_8", "hook_off", "outcome_attention_off"})
_NO_EXTRACTION = frozenset({"internal_sensor_off", "already_adequate", "attention_off", "attention_runtime_off",
                           "navigation_off", "source_off", "suckle_off", "missing_stroke"})


@dataclass(frozen=True, slots=True)
class SustainedFeedingProfileV1:
    """Immutable external conditions fixed before any task decision or movement.

    The case name is an observer label, never a cognitive input. Parameters state
    body competence and selective ablations. Review expectations belong to the
    observer, and neither they nor measured physical totals drive the organism.
    """

    case: str
    extraction: SuckleExtractionExperimentProfileV1
    physiology: FeedingConsequenceProfileV1
    navigation_enabled: bool = True
    attention_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.case, str) or self.case not in SUSTAINED_FEEDING_CASES_V1:
            raise ValueError("unknown sustained-feeding review case")
        if not isinstance(self.extraction, SuckleExtractionExperimentProfileV1) or not isinstance(self.physiology, FeedingConsequenceProfileV1):
            raise TypeError("sustained review requires separate typed task and physical profiles")
        if not self.extraction.latch.suckle.sustained_feeding_enabled:
            raise ValueError("the sustained review requires its explicit opt-in operation profile")
        if not isinstance(self.navigation_enabled, bool) or not isinstance(self.attention_enabled, bool):
            raise TypeError("review ablation switches must be Boolean")

    def as_dict(self) -> dict[str, object]:
        """Expose all conditions without labeling the old fixed need as new sensing."""
        run = self.extraction.latch.run
        values = {"case": self.case, "physical": asdict(run.physical), "planar": asdict(run.planar), "oral": asdict(run.oral),
                "seal": asdict(self.extraction.latch.seal), "extraction": asdict(self.extraction.extraction),
                "downstream_competence": asdict(self.physiology), "feeding_availability": run.feeding.as_dict(),
                "suckle": self.extraction.latch.suckle.as_dict(), "seeking": run.seeking.as_dict(),
                "capability": self.extraction.capability.as_dict() if self.extraction.capability is not None else None,
                "horizon_ticks": run.horizon_ticks, "cadence": run.cadence, "cancel_tick": run.cancel_tick,
                "visual_gap_cutoffs": list(run.visual_gap_cutoffs), "competitor_cutoffs": list(run.competitor_cutoffs),
                "navigation_enabled": self.navigation_enabled, "attention_enabled": self.attention_enabled,
                "need_source": "separately_measured_body_deficit", "units": "synthetic_not_biological",
                "automatic_rest": False, "durable_learning": False}
        # Normalize dataclass tuples into detached JSON arrays for observer export.
        return json.loads(json.dumps(values, allow_nan=False))


def sustained_feeding_profile_v1(case: str = "nominal") -> SustainedFeedingProfileV1:
    """Declare a finite scenario without an action sequence or hidden success counter."""
    if not isinstance(case, str) or case not in SUSTAINED_FEEDING_CASES_V1:
        raise ValueError("unknown sustained-feeding review case")
    base = "seek_then_latch" if case == "nominal" else case if case in {
        "latch_then_extract", "dry", "depleted", "milk_sensor_off", "blocked_motor", "no_capability",
        "support_loss", "body_shift", "cancelled", "attention_off", "source_off", "suckle_off", "missing_stroke",
    } else "nominal"
    p = suckle_extraction_profile_v1(base)
    task = replace(p.latch.suckle, sustained_feeding_enabled=True, extraction_outcomes_enabled=True,
                   extraction_outcome_attention_enabled=case != "outcome_attention_off", extraction_learning_hook_enabled=case != "hook_off")
    run = replace(p.latch.run, horizon_ticks=128, cadence=1 if case == "cadence_1" else 8 if case == "cadence_8" else 4)
    p = replace(p, latch=replace(p.latch, run=run, suckle=task))
    body = FeedingConsequenceProfileV1()
    if case in {"small_need", "larger_need", "already_adequate"}:
        body = replace(body, initial_deficit_units={"small_need": 0.15, "larger_need": 0.85, "already_adequate": 0.0}[case])
    elif case in {"slow_uptake", "uptake_off"}:
        body = replace(body, uptake_units_per_second=0.25 if case == "slow_uptake" else 0.0)
        if case == "uptake_off":
            p = replace(p, extraction=replace(p.extraction, initial_supply_units=8.0))
    elif case == "internal_sensor_off":
        body = replace(body, sensor_available=False)
    elif case == "internal_loss_after_receipt":
        body = replace(body, unavailable_ticks=tuple(range(4, 129)))
    elif case == "internal_gap":
        body = replace(body, unavailable_ticks=(31,))
    return SustainedFeedingProfileV1(case, p, body, case != "navigation_off", case != "attention_runtime_off")


def create_sustained_feeding_trial_v1(
    profile: SustainedFeedingProfileV1, *, trace_capacity: int = 256,
) -> IntegratedRightingTrialV1:
    """Construct the declared organism; ablations remove owners before any decision."""
    if not isinstance(profile, SustainedFeedingProfileV1):
        raise TypeError("sustained trial requires a typed predeclared profile")
    trial = create_suckle_extraction_trial_v1(profile.extraction, trace_capacity=trace_capacity,
                                             feeding_consequence_profile=profile.physiology)
    if not profile.navigation_enabled:
        trial.core.cognition.navigation = NavigationRuntimeV1(enabled=False, motor_preview_enabled=True)
    if not profile.attention_enabled:
        trial.core.cognition.attention = AttentionRuntimeV1(enabled=False)
    return trial


@dataclass(frozen=True, slots=True)
class SustainedFeedingExperimentV1:
    """Complete fixed-horizon observer evidence, not a restorable cognitive state."""

    profile: SustainedFeedingProfileV1
    run: SeekNippleExperimentV1

    def applications(self) -> tuple[SuckleExtractionApplicationV1, ...]:
        """Read actual Navigation applications rather than counting lower strokes."""
        return tuple(c.calculation.navigation.application for c in self.run.cycles
                     if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1))

    def outcomes(self) -> tuple[SuckleExtractionOutcomeV1, ...]:
        """Read original new publications; no later history entry is replayed."""
        return tuple(r for c in self.run.cycles if c.extraction_correspondence is not None for r in c.extraction_correspondence.outcomes)

    @property
    def final(self) -> SuckleFeedingAssessmentV1:
        """Require a real returned task assessment; missing evidence fails the review."""
        assessment = self.run.cycles[-1].sustained_feeding if self.run.cycles else None
        if assessment is None:
            raise ValueError("sustained review lacks its actual final task assessment")
        return assessment

    def metrics(self) -> dict[str, object]:
        """Keep receipt, body consequence, task completion and timing separate."""
        applications = self.applications()
        first_complete = next((c for c in self.run.cycles if c.sustained_feeding is not None
                               and c.sustained_feeding.task is not None and c.sustained_feeding.task.status == "completed"), None)
        sample = self.run.physical_samples[-1]
        body = sample.feeding_consequence
        return {"applications": len(applications), "application_ticks": [a.projection.basis.cutoff_tick for a in applications],
                "application_ids": [a.application_id for a in applications], "task_status": self.final.task.status if self.final.task else "not_started",
                "reason": self.final.reason, "completed_tick": first_complete.calculation.cutoff_tick if first_complete else None,
                "physical_receipt_units": sample.extraction.transferred_milk_units if sample.extraction else None,
                "physical_remaining_deficit": body.deficit_units if body is not None else None,
                "sensed_remaining_deficit": self.final.need.deficit_units if self.final.need is not None else None,
                "known_milk_coverage": [o.milk_evidence()["coverage"] for o in self.outcomes()],
                "causal_credit": "not_established", "automatic_rest": False, "durable_updates": 0}

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Discriminate authority, physical delay, original clocks and honest outcomes.

        Case-specific completion expectations are evaluation only. Missing task or
        sensory records fail the evidence checks rather than being silently
        filtered into success. These checks never alter or rerun the experiment.
        """
        apps, outcomes, run = self.applications(), self.outcomes(), self.run
        tasks = tuple(c.sustained_feeding.task for c in run.cycles
                      if c.sustained_feeding is not None and c.sustained_feeding.task is not None)
        completed = tuple(c.sustained_feeding for c in run.cycles if c.sustained_feeding is not None
                          and c.sustained_feeding.task is not None and c.sustained_feeding.task.status == "completed")
        grants = tuple(r.current for c in run.cycles for r in c.reservations
                       if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1))
        reports = tuple(c.extraction_learning_report for c in run.cycles if c.extraction_learning_report is not None)
        acquired = tuple(r.new_participation for r in reports if r.new_participation is not None)
        uptake_ok = True
        for before, after in zip(run.physical_samples, run.physical_samples[1:]):
            old, new = before.feeding_consequence, after.feeding_consequence
            if old is None or new is None or after.extraction is None:
                uptake_ok = False
                break
            uptake = min(old.pending_units, self.profile.physiology.uptake_units_per_second * self.profile.extraction.latch.run.physical.dt_seconds)
            uptake_ok = uptake_ok and abs(new.pending_units - (old.pending_units - uptake + after.extraction.interval_milk_units)) < 1e-10
            uptake_ok = uptake_ok and abs(new.deficit_units - max(0.0, old.deficit_units - uptake)) < 1e-10
        proof_ok = all(a.task is not None and len(a.confirmation) == 2
                       and a.confirmation[0].sample_id != a.confirmation[1].sample_id
                       and all(n.current and n.new_acquisition and n.deficit_units is not None and n.deficit_units <= 0.01 for n in a.confirmation)
                       and a.confirmation[0].event_tick is not None and a.confirmation[1].event_tick is not None
                       and 4 <= a.confirmation[1].event_tick - a.confirmation[0].event_tick <= 8
                       and a.confirmation[1].cutoff_tick < a.task.expires_at_tick for a in completed)
        selected = tuple(c for c in run.cycles if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1))
        participant_claims = tuple(p.claim for p in acquired)
        expected_claims = tuple(c.extraction_correspondence.registration for c in run.cycles
                                if c.extraction_correspondence is not None and c.extraction_correspondence.registration is not None
                                and c.extraction_correspondence.registration.targets
                                and self.profile.extraction.latch.suckle.extraction_learning_hook_enabled
                                and self.profile.extraction.latch.suckle.extraction_prediction_comparison_enabled)
        budgets = all(a.task.sustained and a.task.expires_at_tick == a.task.started_tick + 96
                      and a.projection.basis.cutoff_tick + a.projection.horizon_ticks <= a.task.expires_at_tick for a in apps)
        checks = (
            ("complete_focal_and_physical_evidence", tuple(c.calculation.cutoff_tick for c in run.cycles)
             == tuple(range(0, self.profile.extraction.latch.run.horizon_ticks + 1, self.profile.extraction.latch.run.cadence))
             and all(c.sustained_feeding is not None and c.sustained_feeding.need is not None for c in run.cycles)
             and tuple(s.tick for s in run.physical_samples) == tuple(range(self.profile.extraction.latch.run.horizon_ticks + 1))),
            ("every_authorized_original_has_actual_F_registration", len(participant_claims) == len(expected_claims)
             and all(actual is expected for actual, expected in zip(participant_claims, expected_claims))),
            ("expected_completion_or_truthful_noncompletion", bool(completed) == (self.profile.case in _COMPLETES)),
            ("selection_control", not apps if self.profile.case in _NO_EXTRACTION else bool(apps)),
            ("body_consequence_uses_prior_intake_and_real_new_receipt", uptake_ok),
            ("finite_fixed_schedule", tuple(s.tick for s in run.local_steps) == tuple(range(self.profile.extraction.latch.run.horizon_ticks))),
            ("one_episode_eight_originals_96_ticks", len({t.task_id for t in tasks}) <= 1 and len(apps) <= 8 and budgets),
            ("fresh_originals_not_replayed_handoffs", len({a.application_id for a in apps}) == len(apps)
             and tuple(a.task.applications for a in apps) == tuple(range(1, len(apps) + 1))),
            ("completion_has_two_current_distinct_body_samples", proof_ok),
            ("source_linked_navigation_before_body", all(isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)
             and c.calculation.navigation.wnm is not None
             and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source
             and c.receipt.dispatch.pnm is c.calculation.navigation.application.projection.pnm for c in selected)),
            ("each_motor_increment_has_original_finite_permission", all(any(t.committed_tick <= s.tick < t.expires_at_tick for t in grants)
             for s in run.local_steps if s.command is not None and s.command.oral_extraction_drive not in (None, 0.0))),
            ("outcomes_retain_selected_original", all(any(o.claim.application is a for a in apps) for o in outcomes)
             and len({o.claim.application.application_id for o in outcomes}) == len(outcomes)),
            ("new_F_participation_has_no_future_outcome", all(p.outcome is None and p.expires_before_tick == p.claim.start_tick + 24
                                                           for p in acquired)),
            ("old_A_outcome_new_B_participant_remain_distinct", all(d.outcome is None or d.outcome.claim is not r.new_participation.claim
                for r in reports if r.new_participation is not None for d in r.dispositions)),
            ("configured_F_reconciliation_called", all((c.extraction_learning_report is not None)
             == self.profile.extraction.latch.suckle.extraction_learning_hook_enabled for c in run.cycles)),
            ("actual_original_storage_bounded", self._retention_is_bounded()),
            ("one_demanding_allocation", all(sum(int(frame is not None and frame.allocation.kind == "interpretation") for frame in
                (c.seeking_attention, c.suckle_attention, c.extraction_attention)) <= 1 for c in run.cycles)),
            ("no_Rest_selection_or_durable_learning", all(c.commitment.selected_primitive_id != "ip:rest" for c in run.cycles)
             and run.durable_before == run.durable_after and all(r.as_dict()["durable_learning_updates"] == 0 for r in reports)),
        )
        return checks

    def _retention_is_bounded(self) -> bool:
        """Require actual owner counters; absent mandatory instrumentation is not zero.

        Optional route counters are required precisely when those routes are
        configured. The limits concern retained source/task/identity state, not
        the length of the observer's fixed-horizon trace or its exported copies.
        """
        limits = {"suckle_feeding_tasks": 1, "suckle_extraction_applications": 8,
                  "suckle_feeding_confirmation_samples": 2, "suckle_feeding_retained_results": 8,
                  "body_feeding_current_records": 1, "body_feeding_watermarks": 1,
                  "extraction_pending_claims": 1, "extraction_original_claims": 8,
                  "extraction_outcome_history": 8, "extraction_outcome_samples": 64,
                  "extraction_outcome_endpoint_refs": 32, "extraction_outcome_command_ticks": 64}
        if self.profile.extraction.latch.suckle.extraction_outcome_attention_enabled:
            limits.update({"extraction_attention_pending_requests": 8, "extraction_attention_dependency": 8,
                           "extraction_attention_seen_outcomes": 8, "extraction_attention_dispositions": 8,
                           "extraction_attention_original_applications": 8})
        if self.profile.extraction.latch.suckle.extraction_learning_hook_enabled:
            limits.update({"extraction_learning_participants": 8, "extraction_learning_registrations": 8,
                           "extraction_learning_seen_outcomes": 8, "extraction_learning_dependencies": 8,
                           "extraction_learning_dispositions": 8, "extraction_learning_originals": 8})
        counts = dict(self.run.peak_counts)
        return all(name in counts and 0 <= counts[name] <= maximum for name, maximum in limits.items())

    @property
    def review_status(self) -> str:
        """Differentiate failed invariants from legitimate adverse task outcomes."""
        return "PASS" if all(ok for _, ok in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export actual evidence and checks; the output is never a cognitive input."""
        return {"scope": "P16_2C_M_sustained_feeding", "profile": self.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in self.run.cycles], "local_steps": [s.as_dict() for s in self.run.local_steps],
                "observer_physical_samples": [s.as_dict() for s in self.run.physical_samples],
                "peak_owner_counts": dict(self.run.peak_counts), "checks": dict(self.checks()), "review_status": self.review_status,
                "P16_2C_complete": False, "B99": "open", "Rest": "separate_next_update"}


def run_sustained_feeding_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SustainedFeedingExperimentV1:
    """Run only the predeclared fixed schedule; no outcome chooses a next action."""
    profile = sustained_feeding_profile_v1(case)
    trial = create_sustained_feeding_trial_v1(profile, trace_capacity=trace_capacity)
    return SustainedFeedingExperimentV1(profile, collect_seek_nipple_evidence_v1(trial, profile.extraction.latch.run))


def render_sustained_feeding_v1(result: SustainedFeedingExperimentV1, *, detail: bool = False) -> str:
    """Render retained evidence without rereading sensors, stepping or learning."""
    if not isinstance(result, SustainedFeedingExperimentV1) or not isinstance(detail, bool):
        raise TypeError("sustained renderer needs a typed retained experiment and Boolean detail")
    lines = [f"P16-2C-M sustained feeding: {result.profile.case} -- {result.review_status}",
             "  Navigation-selected contributions -> physical milk -> delayed uptake -> sensed need -> Suckle completion.",
             "  Synthetic body competence; not biological nutrition, reward, learned change or permission to Rest.",
             "  " + json.dumps(result.metrics(), sort_keys=True, allow_nan=False)]
    lines.extend(f"  {'PASS' if ok else 'FAIL'} {name}" for name, ok in result.checks())
    if detail:
        for cycle in result.run.cycles:
            a = cycle.sustained_feeding
            if a is None:
                lines.append("  MISSING sustained assessment")
                continue
            lines.append(f"  Tick {cycle.calculation.cutoff_tick}: {cycle.commitment.selected_primitive_id or '(no new task)'}; "
                         f"need={a.need.deficit_units if a.need else None}; {a.reason}; contributions={a.task.applications if a.task else 0}")
    return "\n".join(lines)


def run_sustained_feeding_menu_v1() -> None:
    """Use shared finite reviews and inspect their retained traces without rerunning."""
    groups = {"1": ("nominal", "already_sealed", "latch_then_extract"),
              "2": ("small_need", "larger_need", "slow_uptake", "uptake_off", "dry", "depleted", "milk_sensor_off", "internal_sensor_off"),
              "3": ("support_loss", "body_shift", "cancelled", "no_capability", "blocked_motor", "navigation_off", "attention_off"),
              "4": ("cadence_1", "cadence_8", "internal_gap", "hook_off", "outcome_attention_off"),
              "5": SUSTAINED_FEEDING_CASES_V1}
    retained: tuple[SustainedFeedingExperimentV1, ...] = ()
    while True:
        print("\nM: sustained feeding and sensed bodily satisfaction; no Rest or durable learning")
        print("1 integrated; 2 need/uptake/sensing; 3 authority/adverse; 4 timing/routes; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}:
            return
        if choice == "6":
            print("\n\n".join(render_sustained_feeding_v1(r, detail=True) for r in retained) if retained else "No retained result.")
        elif choice in groups:
            retained = tuple(run_sustained_feeding_v1(case) for case in groups[choice])
            print("\n\n".join(render_sustained_feeding_v1(r) for r in retained))
        else:
            print("Invalid selection.")
