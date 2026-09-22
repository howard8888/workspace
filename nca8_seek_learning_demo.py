#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first original seeking participation and zero-learning F review.

All live cases use the retained C collector on fixed physical/time profiles.
Hook-on/off controls keep the E Attention route unchanged: an evidence-only
hook must not improve movement or choose a different task. Other cases expose
interpretation dependency, original-source routing, independent expiry and
unknown/nonapplied outcomes. These are no-learning seam tests, not acquired
feeding competence, latch, Suckle, nourishment, Rest, or full P16-2C/B99.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

import cca8_cli
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_attention_demo import seeking_attention_profile_v1, seeking_attention_owner_limits_v1
from nca8_seek_learning import SeekingLearningPhaseFReportV1, SeekingTeachingDispositionV1
from nca8_seek_nipple import SeekNippleApplicationV1
from nca8_seek_nipple_demo import SeekNippleExperimentProfileV1, SeekNippleExperimentV1, collect_seek_nipple_evidence_v1

__version__ = "0.1.0"
__all__ = ["SEEKING_LEARNING_CASES_V1", "SeekingLearningExperimentV1", "seeking_learning_profile_v1",
           "create_seeking_learning_trial_v1", "run_seeking_learning_v1", "render_seeking_learning_v1",
           "run_seeking_learning_menu_v1", "__version__"]

SEEKING_LEARNING_CASES_V1 = (
    "nominal_on", "nominal_off", "competing_on", "competing_off", "attention_off", "comparison_off", "no_surface",
    "historical_resolved", "nonfocal", "unavailable_source", "support_before_cutoff", "routine_once", "persistent",
    "no_capability", "narrowed", "dropout", "delayed", "cancelled", "brief_gap", "cadence_1", "cadence_8",
    "stand_follow", "stand_follow_off", "stand_follow_drift",
)
_LIMITS = {**seeking_attention_owner_limits_v1(), "seeking_learning_participants": 8, "seeking_learning_dispositions": 32}


def seeking_learning_profile_v1(case: str = "nominal_on") -> SeekNippleExperimentProfileV1:
    """Select the unchanged physical/evidence profile and explicit hook condition.

    nominal/competing on-off pairs vary only participation, not Attention.
    attention_off retains the hook but removes E's relevance/interpretation.
    nonfocal schedules a visual competitor at12 while a matched old endpoint
    remains available. unavailable_source suppresses visual admission at12,
    including that interval batch; it must report unknown, not repaired evidence.
    Physical equations, budgets, tolerances, and sensor timing are not retuned.
    """
    if not isinstance(case, str) or case not in SEEKING_LEARNING_CASES_V1:
        raise ValueError("unknown seeking participation review case")
    aliases = {"nominal_off": "nominal_on", "competing_off": "competing_on", "attention_off": "competing_off",
               "nonfocal": "nominal_on", "unavailable_source": "nominal_on", "stand_follow_off": "stand_follow"}
    base = seeking_attention_profile_v1(aliases.get(case, case))
    return replace(base, case=case,
                   competitor_cutoffs=(12,) if case == "nonfocal" else base.competitor_cutoffs,
                   visual_gap_cutoffs=(12,) if case == "unavailable_source" else base.visual_gap_cutoffs,
                   seeking=replace(base.seeking, learning_hook_enabled=case not in {"nominal_off", "competing_off", "stand_follow_off"}))


def create_seeking_learning_trial_v1(
    case: str = "nominal_on", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> IntegratedRightingTrialV1:
    """Create a fresh isolated trial; construction neither selects a task nor moves.

    The shared diagnostic-capacity option changes only disposable hook histories.
    Original participation, pending outcomes and focal schedules retain their
    own limits. Default old profiles never construct the new hook.
    """
    profile = seeking_learning_profile_v1(case)
    oral = oral_body_capability_v1()
    if case == "narrowed":
        oral = replace(oral, maximum_step=0.04)
    return IntegratedRightingTrialV1(
        profile.physical, stream_id="seek_nipple_reference_body", planar_profile=profile.planar, oral_profile=profile.oral,
        capabilities=(*nominal_body_capabilities_v1(), *((oral,) if profile.oral_capability else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=profile.stand_follow,
                                             outcome_attention_enabled=profile.stand_follow, learning_hook_enabled=profile.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=profile.feeding,
        seek_nipple_profile=profile.seeking, stand_follow_enabled=profile.stand_follow,
        task_outcomes_enabled=profile.stand_follow, task_outcome_attention_enabled=profile.stand_follow,
        task_learning_hook_enabled=profile.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=profile.pnm_registration, trace_capacity=trace_capacity,
        learning_diagnostic_capacity=diagnostic_capacity,
    )


def _compatible_known_relations(disposition: SeekingTeachingDispositionV1) -> bool:
    """Require original scored relations; accepted labels alone cannot certify evidence."""
    outcome = disposition.outcome
    if outcome is None or not disposition.accepted_relations:
        return False
    return all(row in outcome.relations and row[0] in outcome.claim.compatible_relations
               and row[1] in {"matched", "mismatch"} for row in disposition.accepted_relations)


@dataclass(frozen=True, slots=True)
class SeekingLearningExperimentV1:
    """Complete causal evidence; no observer record is an input to task selection."""

    evidence: SeekNippleExperimentV1
    retained_dispositions: tuple[SeekingTeachingDispositionV1, ...]

    def reports(self) -> tuple[SeekingLearningPhaseFReportV1, ...]:
        """Read actual F callback results, not reconstructions from terminal history."""
        return tuple(c.seeking_learning_report for c in self.evidence.cycles if c.seeking_learning_report is not None)

    def dispositions(self) -> tuple[SeekingTeachingDispositionV1, ...]:
        """Read every actual F disposition, independent of the hook diagnostic ring."""
        return tuple(item for report in self.reports() for item in report.dispositions)

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Reject absent required counts, unknown owners, duplicates and overflow."""
        raw = self.evidence
        required = {"wnm", "current_pnm", "seeking_pending_claims", "feeding_detail_current_configurations"}
        if raw.profile.seeking.learning_hook_enabled:
            required |= {"seeking_learning_participants", "seeking_learning_dispositions"}
        missing = tuple("missing:" + key for key in sorted(required - dict(raw.peak_counts).keys()))
        duplicates = ("duplicate_counts",) if len(raw.peak_counts) != len(dict(raw.peak_counts)) else ()
        return missing + duplicates + tuple(key for key, count in raw.peak_counts if key not in _LIMITS
                                            or isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= _LIMITS[key])

    def metrics(self) -> dict[str, object]:
        """Measure real admissions and original-recipient effects, not learned gains."""
        dispositions = self.dispositions()
        return {**self.evidence.metrics(), "hook_enabled": self.evidence.profile.seeking.learning_hook_enabled,
                "F_calls": len(self.reports()), "new_participations": sum(r.new_participation is not None for r in self.reports()),
                "disposition_counts": dict(Counter(item.status for item in dispositions)),
                "accepted_ticks": [item.cutoff_tick for item in dispositions if item.status == "accepted_no_update"],
                "accepted_original_statuses": [item.outcome.status for item in dispositions
                                               if item.status == "accepted_no_update" and item.outcome is not None],
                "righting_F_calls": sum(c.learning_report is not None for c in self.evidence.cycles),
                "maternal_F_calls": sum(c.maternal_learning_report is not None for c in self.evidence.cycles),
                "durable_learning_updates": 0}

    def _expected_effect(self) -> bool:
        """Check the declared acceptance/rejection rather than force physical success."""
        case, dispositions = self.evidence.profile.case, self.dispositions()
        statuses = {item.status for item in dispositions}
        accepted = [item for item in dispositions if item.status == "accepted_no_update"]
        if case in {"nominal_off", "competing_off", "stand_follow_off"}:
            return not self.reports() and not dispositions
        if case == "attention_off":
            return "pending_interpretation" in statuses and "eligibility_expired" in statuses and not accepted
        if case == "comparison_off":
            return "comparison_disabled_no_teaching" in statuses and not accepted
        if case == "no_capability":
            return "not_applied" in statuses and not accepted
        if case == "unavailable_source":
            return "rejected_unknown" in statuses and not accepted
        if case == "dropout":
            return not accepted and bool(statuses & {"rejected_interrupted", "eligibility_expired", "rejected_expired_eligibility"})
        if case == "cancelled":
            return "rejected_interrupted" in statuses and not accepted
        if case == "cadence_1":
            return "eligibility_expired" in statuses and "rejected_expired_eligibility" in statuses and not accepted
        if case == "support_before_cutoff":
            return "pending_interpretation" in statuses and "eligibility_expired" in statuses and not accepted
        if case == "historical_resolved":
            return any(item.outcome is not None and item.outcome.status == "mismatch" and item.interpretation is not None
                       and item.interpretation.status == "historical_resolved" for item in accepted)
        if case == "narrowed":
            return any(item.accepted_relations == (("detail_anchor", "matched"),) for item in accepted)
        if case == "nonfocal":
            return any(c.seeking_learning_report is not None and c.calculation.navigation.wnm is not None
                       and c.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "visual_scene"
                       and any(d.status == "accepted_no_update" for d in c.seeking_learning_report.dispositions) for c in self.evidence.cycles)
        if case in {"nominal_on", "no_surface", "competing_on", "routine_once", "persistent", "stand_follow", "stand_follow_drift", "cadence_8"}:
            return bool(accepted)
        # Brief gaps and delayed sensing keep their actual outcome dispositions;
        # neither permission interruption nor unknown evidence is forced to pass as teaching.
        return bool(dispositions)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Check original recipients, once-only F work, timing and unchanged authority."""
        raw, reports, dispositions = self.evidence, self.reports(), self.dispositions()
        expected_ticks = tuple(range(0, raw.profile.horizon_ticks + 1, raw.profile.cadence))
        registrations = [c.seeking_correspondence.registration for c in raw.cycles
                         if c.seeking_correspondence is not None and c.seeking_correspondence.registration is not None
                         and isinstance(c.calculation.navigation.application, SeekNippleApplicationV1)]
        outcomes = [item for c in raw.cycles if c.seeking_correspondence is not None for item in c.seeking_correspondence.outcomes]
        accepted = [item for item in dispositions if item.status == "accepted_no_update"]
        participants = [r.new_participation for r in reports if r.new_participation is not None]
        original = {item.pnm_id: item for item in participants}
        interpretations = [c.seeking_attention.allocation.interpretation for c in raw.cycles if c.seeking_attention is not None
                           and c.seeking_attention.allocation.kind == "interpretation"]
        slot_valid = all(sum(int(a is not None and a.kind == "interpretation") for a in (
            c.calculation.outcome_allocation, c.calculation.maternal_outcome_allocation, c.calculation.seeking_outcome_allocation,
        )) + int(c.calculation.navigation.application is not None) <= 1 for c in raw.cycles)
        return (
            ("declared_fixed_profile", raw.profile.case in SEEKING_LEARNING_CASES_V1 and raw.profile == seeking_learning_profile_v1(raw.profile.case)),
            ("complete_fixed_schedule", tuple(c.calculation.cutoff_tick for c in raw.cycles) == expected_ticks
             and tuple(s.tick for s in raw.local_steps) == tuple(range(raw.profile.horizon_ticks))
             and tuple(p.tick for p in raw.physical_samples) == tuple(range(raw.profile.horizon_ticks + 1))),
            ("declared_no_learning_effect", self._expected_effect()),
            ("actual_F_callback_every_configured_cycle", len(reports) == (len(expected_ticks) if raw.profile.seeking.learning_hook_enabled else 0)
             and all(c.seeking_learning_report is None or (c.seeking_learning_report.cycle_id == c.commitment.cycle_id
             and c.seeking_learning_report.cutoff_tick == c.calculation.cutoff_tick) for c in raw.cycles)),
            ("original_selected_claim_only", all(any(p.claim is claim for claim in registrations) for p in participants)),
            ("no_future_outcome_in_new_participation", all(p.outcome is None and p.request is None for p in participants)),
            ("source_recipient_not_current_wnm", all(p.recipient_id == "feeding_detail_association:feeding_detail:consequence"
             and p.claim.preview.basis.source_map_ref.map_id == "feeding_detail" for p in participants)),
            ("outcomes_are_actual_canonical_results", all(d.outcome is None or any(d.outcome is outcome for outcome in outcomes) for d in dispositions)),
            ("accepted_once_per_original_claim", len({d.pnm_id for d in accepted}) == len(accepted)),
            ("acceptance_before_independent_expiry", all(d.pnm_id in original and original[d.pnm_id].created_cycle < d.cycle_id
             < original[d.pnm_id].expires_before_cycle for d in accepted)),
            ("acceptance_uses_authorized_executed_evidence", all(d.outcome is not None and d.outcome.claim.targets
             and d.outcome.command_intervals > 0 and d.outcome.evidence is not None
             and d.outcome.evidence.feedback.available_tick <= d.cutoff_tick for d in accepted)),
            ("only_compatible_known_relations", all(_compatible_known_relations(d) for d in accepted)),
            ("interpretation_not_recomputed_at_F", all(d.interpretation is None or any(d.interpretation is i for i in interpretations)
             for d in dispositions)),
            ("single_demanding_operation", slot_valid),
            ("one_handoff_per_focal_opportunity", raw.handoff_consumptions == len(expected_ticks)),
            ("installations_have_actual_authorization", raw.installations == sum(bool(c.reservations) for c in raw.cycles)),
            ("finite_owner_storage", not self.bound_violations),
            ("durable_sources_unchanged", bool(raw.durable_before) and raw.durable_before == raw.durable_after),
            ("no_durable_or_ledger_execution", all(r.as_dict()["durable_learning_updates"] == 0
             and r.as_dict()["ledger_rows_executed"] == 0 and not r.as_dict()["new_action_outcome_available"] for r in reports)),
        )

    @property
    def review_status(self) -> str:
        """Reject incomplete or inconsistent evidence rather than printing blind success."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export full collected histories; no omission of physical or rejected evidence."""
        raw = self.evidence
        return {"scope": "P16_2C_F_seeking_participation", "profile": raw.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in raw.cycles], "local_steps": [s.as_dict() for s in raw.local_steps],
                "observer_physical_samples": [p.as_dict() for p in raw.physical_samples], "final_feedback": raw.final_feedback.as_dict(),
                "peak_owner_counts": dict(raw.peak_counts), "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
                "durable_before": raw.durable_before, "durable_after": raw.durable_after,
                "registered_pnm_cycles": list(raw.registered_pnm_cycles),
                "retained_hook_dispositions": [d.as_dict() for d in self.retained_dispositions],
                "checks": dict(self.checks()), "review_status": self.review_status,
                "feeding_learning": "eligibility_only_no_durable_updates", "B99": "open"}


def run_seeking_learning_v1(
    case: str = "nominal_on", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> SeekingLearningExperimentV1:
    """Run the same fixed-schedule collector; no outcome-dependent driver policy."""
    profile = seeking_learning_profile_v1(case)
    trial = create_seeking_learning_trial_v1(case, trace_capacity=trace_capacity, diagnostic_capacity=diagnostic_capacity)
    evidence = collect_seek_nipple_evidence_v1(trial, profile)
    hook = trial.core.feeding_detail.learning_hook if trial.core.feeding_detail is not None else None
    return SeekingLearningExperimentV1(evidence, () if hook is None else hook.history())


def render_seeking_learning_v1(result: SeekingLearningExperimentV1, *, detail: bool = False) -> str:
    """Render completed evidence, never rerun cognition, movement or learning."""
    if not isinstance(result, SeekingLearningExperimentV1) or not isinstance(detail, bool):
        raise TypeError("seeking participation rendering requires a completed result and Boolean detail")
    metrics = result.metrics()
    lines = [f"P16-2C-F / {result.evidence.profile.case} / SEEKING PARTICIPATION REVIEW: {result.review_status}",
             f"  hook={metrics['hook_enabled']}; actual F calls={metrics['F_calls']}; participation={metrics['new_participations']}",
             f"  dispositions={metrics['disposition_counts']}; accepted at={metrics['accepted_ticks']}",
             f"  oral commands={metrics['oral_commands']}; reached detail={metrics['first_reached_detail_tick']}; "
             f"physical touch={metrics['first_physical_touch_tick']}",
             "  Original recipient; four-opportunity eligibility; zero durable learning, causal credit, latch or milk."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for cycle in result.evidence.cycles:
            report = cycle.seeking_learning_report
            if report is not None:
                selected = cycle.calculation.attention.selected_source_state
                lines.append(f"  cutoff={report.cutoff_tick}: focal={selected.source_map_ref.map_id if selected else 'none'}; "
                             f"recipient={report.recipient_id}; new={report.new_participation.pnm_id if report.new_participation else None}; "
                             f"pending={[p.pnm_id for p in report.pending]}")
                lines.extend(f"    {item.as_dict()}" for item in report.dispositions)
    return "\n".join(lines)


def run_seeking_learning_menu_v1() -> None:
    """Run shared cases and inspect retained detail with no new simulation on reads."""
    groups = {"1": ("nominal_on", "nominal_off", "competing_on", "competing_off", "attention_off", "comparison_off"),
              "2": ("historical_resolved", "nonfocal", "unavailable_source", "support_before_cutoff", "routine_once", "persistent"),
              "3": ("no_surface", "no_capability", "narrowed", "dropout", "delayed", "cancelled", "brief_gap", "cadence_1", "cadence_8"),
              "4": ("stand_follow", "stand_follow_off", "stand_follow_drift"), "5": SEEKING_LEARNING_CASES_V1}
    retained: tuple[SeekingLearningExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-F -- SEEKING PARTICIPATION / ACTUAL PHASE F / NO DURABLE LEARNING")
        print("  1) Hook and Attention controls / 2) Original recipient and interpretation / 3) Missing, narrowed and expired")
        print("  4) Continuous stand-follow-seek / 5) All cases / 6) Inspect retained detail (no new movement)")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            if not retained:
                print("No retained run. Choose a review first.")
            for result in retained:
                print(render_seeking_learning_v1(result, detail=True))
        elif choice in groups:
            retained = tuple(run_seeking_learning_v1(case) for case in groups[choice])
            for result in retained:
                print(render_seeking_learning_v1(result))
        else:
            print("Choose 1-6 or press Enter to return.")
