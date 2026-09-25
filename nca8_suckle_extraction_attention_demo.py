#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-E shared live discrepancy-to-Attention review with identical-input controls.

The existing L-C/D factory and collector own every cognitive and physical step.
This observer chooses initial conditions, not an IP, outcome, question or motor
command. Historical extraction evidence and current relevance are shown apart.
Three-way simultaneous-question fixtures are in the tests, not misrepresented as
naturally occurring newborn trajectories. No milk-dependent feeding or learning
is demonstrated by this bounded interpretation route.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json

import cca8_cli

from nca8_seek_nipple_demo import SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleExtractionApplicationV1
from nca8_suckle_extraction_attention import ExtractionInterpretationV1, ExtractionMismatchRequestV1
from nca8_suckle_extraction_demo import SuckleExtractionExperimentProfileV1, create_suckle_extraction_trial_v1
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeV1
from nca8_suckle_extraction_outcomes_demo import suckle_extraction_outcome_profile_v1

__version__ = "0.1.0"
__all__ = ["EXTRACTION_ATTENTION_CASES_V1", "ExtractionAttentionExperimentV1", "extraction_attention_profile_v1",
           "run_extraction_attention_v1", "render_extraction_attention_v1", "run_extraction_attention_menu_v1", "__version__"]
EXTRACTION_ATTENTION_CASES_V1 = (
    "mismatch", "route_off", "competing_source", "maintain_source", "source_unavailable", "without_latch_route",
    "comparison_off", "matched", "dry", "depleted", "milk_sensor_off", "blocked_motor", "delayed", "dropout",
    "support_loss", "cancelled", "no_capability", "source_off", "no_need", "latch_then_extract", "seek_then_latch",
    "stand_follow", "one_cycle", "cadence_1", "cadence_8", "nonfocal_outcome",
)
_MISMATCH_CASES = frozenset({"mismatch", "route_off", "competing_source", "maintain_source", "source_unavailable",
                            "without_latch_route", "comparison_off", "cadence_1", "cadence_8"})


def extraction_attention_profile_v1(case: str = "mismatch") -> SuckleExtractionExperimentProfileV1:
    """Declare physical/source conditions and opt-in switches before any execution."""
    if not isinstance(case, str) or case not in EXTRACTION_ATTENTION_CASES_V1:
        raise ValueError("unknown extraction Attention review case")
    base = "body_shift" if case in _MISMATCH_CASES else "nominal" if case == "matched" else case
    profile = suckle_extraction_outcome_profile_v1(base)
    task = replace(profile.latch.suckle, extraction_outcome_attention_enabled=case != "route_off",
                   extraction_prediction_comparison_enabled=case != "comparison_off")
    if case == "without_latch_route":
        task = replace(task, outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False)
    run = profile.latch.run
    if case in {"competing_source", "maintain_source"}:
        run = replace(run, competitor_cutoffs=tuple(range(4, 33, 4)) if case == "competing_source" else (8,))
    if case == "source_unavailable":
        run = replace(run, visual_gap_cutoffs=(8, 12, 16))
    if case in {"cadence_1", "cadence_8"}:
        run = replace(run, cadence=1 if case == "cadence_1" else 8)
    return replace(profile, latch=replace(profile.latch, run=run, suckle=task))


def _outcomes(run: SeekNippleExperimentV1) -> tuple[SuckleExtractionOutcomeV1, ...]:
    """Read retained publications for observer comparison, not behavioral input."""
    return tuple(result for cycle in run.cycles if cycle.extraction_correspondence is not None
                 for result in cycle.extraction_correspondence.outcomes)


@dataclass(frozen=True, slots=True)
class ExtractionAttentionExperimentV1:
    """Two complete live runs differing only in the new source-relevance route."""

    case: str
    profile: SuckleExtractionExperimentProfileV1
    run: SeekNippleExperimentV1
    control: SeekNippleExperimentV1
    dispositions: tuple[tuple[str, str, int], ...]

    def requests(self) -> tuple[ExtractionMismatchRequestV1, ...]:
        """Read newly admitted question records without turning history into input."""
        return tuple(request for cycle in self.run.cycles if cycle.extraction_attention is not None
                     for request in cycle.extraction_attention.created)

    def interpretations(self) -> tuple[ExtractionInterpretationV1, ...]:
        """Count performed work only, not retained dependency references."""
        return tuple(cycle.extraction_attention.allocation.interpretation for cycle in self.run.cycles
                     if cycle.extraction_attention is not None and cycle.extraction_attention.allocation.kind == "interpretation"
                     and cycle.extraction_attention.allocation.interpretation is not None)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Distinguish changed focal allocation from unchanged historical evidence.

        An enabled route can legitimately change later focal decisions. Preservation
        is asserted for the original outcome and the pre-publication physical prefix,
        not by claiming all later cycles must be identical in a causal Attention test.
        """
        questions, interpretations = self.requests(), self.interpretations()
        result, control_result = _outcomes(self.run), _outcomes(self.control)
        interpreted_cycles = tuple(c for c in self.run.cycles if c.extraction_attention is not None
                                   and c.extraction_attention.allocation.kind == "interpretation")
        cutoff = questions[0].admitted_tick if questions else self.profile.latch.run.horizon_ticks
        prefix = tuple(s for s in self.run.local_steps if s.tick < cutoff)
        control_prefix = tuple(s for s in self.control.local_steps if s.tick < cutoff)
        expected_question = self.case in _MISMATCH_CASES - {"route_off", "comparison_off"}
        # Fixed body-shift controls have one qualifying touch/seal loss. Other cases
        # explicitly test that milk/unknown/interruption alone does not create one.
        compare_at = questions[0].admitted_tick if questions else None
        pair = tuple(c for c in self.control.cycles if c.calculation.cutoff_tick == compare_at)
        own = tuple(c for c in self.run.cycles if c.calculation.cutoff_tick == compare_at)
        competition_ok = True
        if self.case in {"competing_source", "maintain_source"}:
            competition_ok = bool(own and pair and own[0].calculation.attention.selected_source_state is not None
                                  and pair[0].calculation.attention.selected_source_state is not None
                                  and pair[0].feeding_detail_source is not None
                                  and own[0].calculation.attention.selected_source_state is own[0].feeding_detail_source
                                  and pair[0].calculation.attention.selected_source_state.source_map_ref
                                  != pair[0].feeding_detail_source.source_map_ref)
        bounds = {"extraction_attention_pending_requests": 1, "extraction_attention_dependency": 1,
                  "extraction_attention_seen_outcomes": 1, "extraction_attention_dispositions": 8}
        return (
            ("expected_bounded_question", len(questions) == int(expected_question)),
            ("at_most_one_performed_interpretation", len(interpretations) <= 1),
            ("exact_original_publication", all(q.outcome is result[0] and q.admitted_tick == q.outcome.evaluated_tick for q in questions)),
            ("original_outcome_and_milk_unchanged", result == control_result),
            ("same_prepublication_execution", prefix == control_prefix),
            ("ordinary_source_bid_max_not_sum", all(c.extraction_attention.source_bid is None
                or c.extraction_attention.source_bid.prediction_or_envelope_failure_rank == 40
                for c in self.run.cycles if c.extraction_attention is not None and c.extraction_attention.created)),
            ("real_Attention_consequence", competition_ok),
            ("grant_matches_question_and_current_WNM", all(c.extraction_attention is not None
                and c.extraction_attention.allocation.interpretation is not None
                and c.calculation.navigation.wnm is not None and c.feeding_detail_source is not None
                and c.calculation.navigation.reason
                == "outcome_interpretation:" + c.extraction_attention.allocation.interpretation.request.request_id
                and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in interpreted_cycles)),
            ("no_extra_IP_projection_handoff_or_target", all(c.calculation.navigation.application is None
                and c.calculation.proposal is None and c.receipt.dispatch.pnm is None and not c.reservations for c in interpreted_cycles)),
            ("one_original_extraction_contribution", sum(isinstance(c.calculation.navigation.application,
                SuckleExtractionApplicationV1) for c in self.run.cycles) <= 1),
            ("original_question_expiry", all(i.cutoff_tick < i.request.expires_at_tick
                == i.request.admitted_tick + 8 for i in interpretations)),
            ("unavailable_source_expires_without_fabricated_access", not interpretations
                and any(status == "expired_uninterpreted" for _, status, _ in self.dispositions)
                if self.case == "source_unavailable" else True),
            ("no_unknown_milk_as_prediction_failure", not questions if self.case in
                {"matched", "dry", "depleted", "milk_sensor_off", "comparison_off", "blocked_motor"} else True),
            ("original_learning_reports_unchanged", tuple(c.suckle_learning_report for c in self.run.cycles)
                == tuple(c.suckle_learning_report for c in self.control.cycles)),
            ("finite_owner_state", all(0 <= dict(self.run.peak_counts).get(key, 0) <= bound for key, bound in bounds.items())),
            ("durable_state_unchanged", self.run.durable_before == self.run.durable_after == self.control.durable_after),
            ("one_world_step_per_tick", len(self.run.local_steps) == len(self.control.local_steps)
                == self.profile.latch.run.horizon_ticks),
        )

    @property
    def review_status(self) -> str:
        """A truthful adverse outcome can pass; an invariant violation cannot."""
        return "PASS" if all(ok for _, ok in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export detached observer records without granting further cognition."""
        physical = self.run.physical_samples[-1].extraction
        data = {"scope": "P16_2C_LE_extraction_relevance", "case": self.case, "profile": self.profile.as_dict(),
                "original_outcomes": [r.as_dict() for r in _outcomes(self.run)],
                "questions": [q.as_dict() for q in self.requests()], "interpretations": [i.as_dict() for i in self.interpretations()],
                "cycles": [c.as_dict() for c in self.run.cycles], "control_cycles": [c.as_dict() for c in self.control.cycles],
                "dispositions": self.dispositions, "peak_counts": dict(self.run.peak_counts),
                "physical_milk_observer_only": None if physical is None else physical.transferred_milk_units,
                "checks": dict(self.checks()), "review_status": self.review_status,
                "limits": "no_remedy_retry_new_batch_learning_nourishment_or_causal_credit"}
        return json.loads(json.dumps(data, allow_nan=False))


def run_extraction_attention_v1(case: str = "mismatch", *, trace_capacity: int = 256) -> ExtractionAttentionExperimentV1:
    """Run the unchanged integrated collector twice with fixed source/body inputs."""
    profile = extraction_attention_profile_v1(case)
    trial = create_suckle_extraction_trial_v1(profile, trace_capacity=trace_capacity)
    run = collect_seek_nipple_evidence_v1(trial, profile.latch.run)
    source = trial.core.feeding_detail
    if source is None:
        raise RuntimeError("extraction Attention review requires its feeding-detail source")
    owner = source.extraction_outcome_attention
    dispositions = owner.dispositions() if owner is not None else ()
    control_profile = replace(profile, latch=replace(profile.latch, suckle=replace(
        profile.latch.suckle, extraction_outcome_attention_enabled=False)))
    control_trial = create_suckle_extraction_trial_v1(control_profile, trace_capacity=trace_capacity)
    control = collect_seek_nipple_evidence_v1(control_trial, control_profile.latch.run)
    return ExtractionAttentionExperimentV1(case, profile, run, control, dispositions)


def render_extraction_attention_v1(result: ExtractionAttentionExperimentV1, *, detail: bool = False) -> str:
    """Show historical discrepancy and present interpretation as different facts."""
    lines = [f"L-E extraction Attention: {result.case} -- {result.review_status}",
             "  Original L-D mismatch -> ordinary feeding bid -> Attention/WNM -> one Navigation interpretation.",
             f"  Questions={len(result.requests())}; performed interpretations={len(result.interpretations())}.",
             "  Outcome questions are not IPs; no remedy, new motor permission, retry or learning is supplied."]
    for outcome in _outcomes(result.run):
        lines.append(f"  Original execution={outcome.status}; relations={dict(outcome.relations)}; milk={outcome.milk_evidence()}")
    for interpretation in result.interpretations():
        lines.append(f"  Current relevance={interpretation.status} at tick {interpretation.cutoff_tick}; original outcome unchanged.")
    lines.extend(f"  {'PASS' if ok else 'FAIL'} {name}" for name, ok in result.checks())
    if detail:
        lines.append("  Original questions: " + str([q.as_dict() for q in result.requests()]))
        for cycle in result.run.cycles:
            frame = cycle.extraction_attention
            lines.append(f"  Tick {cycle.calculation.cutoff_tick}: {cycle.calculation.navigation.reason}; "
                         f"extraction allocation={frame.allocation.kind if frame is not None else 'disabled'}")
        lines.append("  Dispositions: " + str(result.dispositions))
    return "\n".join(lines)


def run_extraction_attention_menu_v1() -> None:
    """Inspect shared finite cases; retained detail is read-only and runs no world."""
    groups = {
        "1": ("mismatch", "route_off", "competing_source", "maintain_source"),
        "2": ("matched", "dry", "depleted", "milk_sensor_off", "comparison_off", "without_latch_route"),
        "3": ("source_unavailable", "blocked_motor", "delayed", "dropout", "support_loss", "cancelled"),
        "4": ("latch_then_extract", "seek_then_latch", "stand_follow", "one_cycle", "cadence_1", "cadence_8", "nonfocal_outcome"),
        "5": EXTRACTION_ATTENTION_CASES_V1,
    }
    retained: tuple[ExtractionAttentionExperimentV1, ...] = ()
    while True:
        print("\nL-E: extraction discrepancy and one Navigation interpretation")
        print("1 causal Attention; 2 negative/independent controls; 3 bounded adverse; 4 continuity; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}:
            return
        if choice == "6":
            print("\n\n".join(render_extraction_attention_v1(r, detail=True) for r in retained) if retained else "No retained result.")
        elif choice in groups:
            retained = tuple(run_extraction_attention_v1(case) for case in groups[choice])
            print("\n\n".join(render_extraction_attention_v1(r) for r in retained))
        else:
            print("Invalid selection.")
