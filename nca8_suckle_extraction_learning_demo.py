#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-F shared extraction-participation review with complete hook-off controls.

The accepted extraction factory and collector perform all source processing,
Navigation, BodyMap authorization, physical execution and outcome publication.
This observer supplies only fixed conditions and the new optional hook switch.
Removing the hook must remove only participation/reconciliation reporting, not
change a single cognitive decision, physical sample, original outcome or L-E
allocation. Neither path demonstrates a durable learner or complete feeding.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json

import cca8_cli

from nca8_hierarchy import IntegratedRightingCycleV1
from nca8_seek_nipple_demo import SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_suckle_extraction_attention_demo import EXTRACTION_ATTENTION_CASES_V1, extraction_attention_profile_v1
from nca8_suckle_extraction_demo import SuckleExtractionExperimentProfileV1, create_suckle_extraction_trial_v1
from nca8_suckle_extraction_learning import ExtractionParticipationV1, ExtractionTeachingDispositionV1

__version__ = "0.1.0"
__all__ = ["EXTRACTION_LEARNING_CASES_V1", "ExtractionLearningExperimentV1", "extraction_learning_profile_v1",
           "run_extraction_learning_v1", "render_extraction_learning_v1", "run_extraction_learning_menu_v1", "__version__"]
EXTRACTION_LEARNING_CASES_V1 = (*EXTRACTION_ATTENTION_CASES_V1, "nominal_cadence_1", "nominal_cadence_8")


def extraction_learning_profile_v1(case: str = "matched") -> SuckleExtractionExperimentProfileV1:
    """Declare conditions before running; no outcome or next operation is supplied."""
    if not isinstance(case, str) or case not in EXTRACTION_LEARNING_CASES_V1:
        raise ValueError("unknown extraction participation review case")
    profile = extraction_attention_profile_v1("matched" if case.startswith("nominal_cadence_") else case)
    run = profile.latch.run
    if case in {"nominal_cadence_1", "nominal_cadence_8"}:
        run = replace(run, cadence=1 if case == "nominal_cadence_1" else 8)
    return replace(profile, latch=replace(profile.latch, run=run, suckle=replace(
        profile.latch.suckle, extraction_learning_hook_enabled=True)))


def _without_hook_reporting(cycle: IntegratedRightingCycleV1) -> IntegratedRightingCycleV1:
    """Remove only the new diagnostic report/route flags for full-cycle comparison.

    All source samples, applications, commitments, scheduler results, reservations,
    original L-D evidence, L-E questions/allocations and older learning reports
    remain in the comparison. This is an observer-only copy, never a runtime input.
    """
    frame, assessment = cycle.extraction_correspondence, cycle.suckle_extraction
    return replace(cycle, extraction_learning_report=None,
                   extraction_correspondence=replace(frame, learning_hook_enabled=False) if frame is not None else None,
                   suckle_extraction=replace(assessment, participation_enabled=False) if assessment is not None else None)


@dataclass(frozen=True, slots=True)
class ExtractionLearningExperimentV1:
    """Two complete identical-input trials differing only in the L-F hook switch."""

    case: str
    profile: SuckleExtractionExperimentProfileV1
    run: SeekNippleExperimentV1
    control: SeekNippleExperimentV1
    dispositions: tuple[ExtractionTeachingDispositionV1, ...]

    def registrations(self) -> tuple[ExtractionParticipationV1, ...]:
        """Read actual F-created recipients, not later reconstructed participation."""
        return tuple(c.extraction_learning_report.new_participation for c in self.run.cycles
                     if c.extraction_learning_report is not None and c.extraction_learning_report.new_participation is not None)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Test causal removal and identity/time rather than only a status counter."""
        reports = tuple(c.extraction_learning_report for c in self.run.cycles if c.extraction_learning_report is not None)
        participants = self.registrations()
        dispositions = tuple(d for r in reports for d in r.dispositions)
        accepted = tuple(d for d in dispositions if d.status == "accepted_no_update")
        outcomes = tuple(outcome for c in self.run.cycles if c.extraction_correspondence is not None
                         for outcome in c.extraction_correspondence.outcomes)
        claims = tuple(c.extraction_correspondence.registration for c in self.run.cycles
                       if c.extraction_correspondence is not None and c.extraction_correspondence.registration is not None)
        expected_participation = 0 if self.case in {"source_off", "no_need", "no_capability", "comparison_off"} else 1
        bounds = {"extraction_learning_participants": 1, "extraction_learning_registrations": 1,
                  "extraction_learning_seen_outcomes": 1, "extraction_learning_dependencies": 1,
                  "extraction_learning_dispositions": 8}
        performed = tuple(c.extraction_attention.allocation.interpretation for c in self.run.cycles
                          if c.extraction_attention is not None and c.extraction_attention.allocation.kind == "interpretation")
        return (
            ("expected_original_participation", len(participants) == expected_participation),
            ("exact_original_selected_claim", all(any(p.claim is claim for claim in claims) for p in participants)),
            ("fixed_application_not_latch_clock", all(p.expires_before_tick == p.claim.start_tick + 24 for p in participants)),
            ("no_future_action_result_at_registration", all(r.offered_outcomes == 0 and r.new_participation.outcome is None
                                                          for r in reports if r.new_participation is not None)),
            ("canonical_published_evidence", all(any(d.outcome is item for item in outcomes)
                                                for d in dispositions if d.outcome is not None)),
            ("accept_only_known_original_relations", all(d.outcome is not None and d.accepted_relations
                == tuple(row for row in d.outcome.relations if row[1] in {"matched", "mismatch"}) for d in accepted)),
            ("accepted_before_exclusive_expiry", all(d.outcome is not None and d.cutoff_tick < d.outcome.claim.start_tick + 24
                                                   for d in accepted)),
            ("only_actual_D_interpretation", all(any(d.interpretation is item for item in performed)
                and d.interpretation.cycle_id == d.cycle_id and d.interpretation.cutoff_tick == d.cutoff_tick
                for d in dispositions if d.interpretation is not None)),
            ("uninterpreted_discrepancy_expires", not accepted and any(d.status == "eligibility_expired" for d in dispositions)
             if self.case in {"route_off", "source_unavailable"} else True),
            ("ordinary_known_relations_reach_F", len(accepted) == 1 if self.case in
                {"matched", "dry", "depleted", "milk_sensor_off", "latch_then_extract", "nominal_cadence_1", "nominal_cadence_8"}
             else True),
            ("all_cognitive_decisions_and_old_routes_unchanged",
             tuple(_without_hook_reporting(c) for c in self.run.cycles) == self.control.cycles),
            ("all_physical_commands_and_samples_unchanged", self.run.local_steps == self.control.local_steps
             and self.run.physical_samples == self.control.physical_samples and self.run.installations == self.control.installations),
            ("bounded_owner_and_disposable_history", all(0 <= dict(self.run.peak_counts).get(key, 0) <= bound
                                                        for key, bound in bounds.items())),
            ("durable_state_unchanged", self.run.durable_before == self.run.durable_after == self.control.durable_after),
            ("zero_durable_updates_no_motor_grant", all(r.as_dict()["durable_learning_updates"] == 0
                                                       and not r.as_dict()["restores_motor_permission"] for r in reports)),
            ("one_physical_step_per_interval", len(self.run.local_steps) == self.profile.latch.run.horizon_ticks),
        )

    @property
    def review_status(self) -> str:
        """Report failed invariants, not truthful adverse outcomes, as review failure."""
        return "PASS" if all(ok for _, ok in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export detached evidence; reading cannot teach, step or restore permission."""
        data = {"scope": "P16_2C_LF_extraction_participation", "case": self.case, "profile": self.profile.as_dict(),
                "registrations": [p.as_dict() for p in self.registrations()],
                "cycles": [c.as_dict() for c in self.run.cycles], "control_cycles": [c.as_dict() for c in self.control.cycles],
                "dispositions": [d.as_dict() for d in self.dispositions], "peak_counts": dict(self.run.peak_counts),
                "checks": dict(self.checks()), "review_status": self.review_status,
                "limits": "eligibility_only_no_retry_new_batch_nourishment_rest_durable_learning_or_causal_credit"}
        return json.loads(json.dumps(data, allow_nan=False))


def run_extraction_learning_v1(case: str = "matched", *, trace_capacity: int = 256) -> ExtractionLearningExperimentV1:
    """Use the unchanged factory/collector twice; disable only this hook in control."""
    profile = extraction_learning_profile_v1(case)
    trial = create_suckle_extraction_trial_v1(profile, trace_capacity=trace_capacity)
    run = collect_seek_nipple_evidence_v1(trial, profile.latch.run)
    owner = trial.core.feeding_detail.extraction_learning_hook if trial.core.feeding_detail is not None else None
    history = owner.history() if owner is not None else ()
    control_profile = replace(profile, latch=replace(profile.latch, suckle=replace(
        profile.latch.suckle, extraction_learning_hook_enabled=False)))
    control_trial = create_suckle_extraction_trial_v1(control_profile, trace_capacity=trace_capacity)
    control = collect_seek_nipple_evidence_v1(control_trial, control_profile.latch.run)
    return ExtractionLearningExperimentV1(case, profile, run, control, history)


def render_extraction_learning_v1(result: ExtractionLearningExperimentV1, *, detail: bool = False) -> str:
    """Show original participation, known evidence and independent expiry separately."""
    if not isinstance(result, ExtractionLearningExperimentV1) or not isinstance(detail, bool):
        raise TypeError("extraction participation renderer needs a completed experiment and Boolean detail")
    lines = [f"L-F extraction participation / Phase F: {result.case} -- {result.review_status}",
             "  Original selected extraction -> earlier participation -> L-D evidence -> actual L-E interpretation when required -> F.",
             "  Eligibility ends BEFORE application cutoff + 24 physical ticks; latch K keeps its own four-cycle window.",
             "  Known relations are evidence only. No durable learning, new batch, retry, nourishment or Rest."]
    for participant in result.registrations():
        lines.append(f"  Registered {participant.pnm_id} at cycle {participant.created_cycle}, tick {participant.claim.start_tick}; "
                     f"eligibility expires before tick {participant.expires_before_tick}.")
    for item in result.dispositions:
        lines.append(f"  F cycle {item.cycle_id}, tick {item.cutoff_tick}: {item.status}; known accepted={dict(item.accepted_relations)}")
        if item.outcome is not None:
            milk = item.outcome.milk_evidence()
            lines.append(f"    Original execution={item.outcome.status}; known milk sum={milk['known_interval_sum']}; "
                         f"coverage={milk['coverage']}; nourishment not established.")
    lines.extend(f"  {'PASS' if ok else 'FAIL'} {name}" for name, ok in result.checks())
    if detail:
        for cycle in result.run.cycles:
            report = cycle.extraction_learning_report
            if report is not None:
                lines.append(f"  Tick {report.cutoff_tick}: {cycle.calculation.navigation.reason}; pending={len(report.pending)}; "
                             f"offered earlier outcomes={report.offered_outcomes}; durable updates=0")
        lines.append("  Complete dispositions: " + str([d.as_dict() for d in result.dispositions]))
    return "\n".join(lines)


def run_extraction_learning_menu_v1() -> None:
    """Run shared finite cases or inspect retained results without further execution."""
    groups = {
        "1": ("matched", "mismatch", "route_off", "without_latch_route"),
        "2": ("dry", "depleted", "milk_sensor_off", "comparison_off"),
        "3": ("source_unavailable", "no_capability", "blocked_motor", "delayed", "dropout", "cancelled", "support_loss"),
        "4": ("latch_then_extract", "seek_then_latch", "stand_follow", "nonfocal_outcome", "nominal_cadence_1", "nominal_cadence_8"),
        "5": EXTRACTION_LEARNING_CASES_V1,
    }
    retained: tuple[ExtractionLearningExperimentV1, ...] = ()
    while True:
        print("\nL-F: extraction participation and actual Phase F (no durable learning)")
        print("1 causal/independent routes; 2 milk/negative controls; 3 adverse; 4 continuity/time; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}:
            return
        if choice == "6":
            print("\n\n".join(render_extraction_learning_v1(r, detail=True) for r in retained) if retained else "No retained result.")
        elif choice in groups:
            retained = tuple(run_extraction_learning_v1(case) for case in groups[choice])
            print("\n\n".join(render_extraction_learning_v1(r) for r in retained))
        else:
            print("Invalid selection.")
