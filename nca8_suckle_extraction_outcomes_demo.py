#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-D shared original-extraction and interval-milk review, with route-off controls.

The existing L-C factory and collector perform all selection, authorization,
physics and C2 work. This observer supplies only experiment conditions. Private
physical totals are displayed beside, never passed into, the live evidence reader.
Constructed scene-correspondence fixtures live in tests and are not relabelled
physical experiments. No new feeding decision or learned improvement is claimed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json

import cca8_cli

from nca8_seek_nipple_demo import SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_suckle_extraction_demo import (
    SUCKLE_EXTRACTION_CASES_V1, SuckleExtractionExperimentProfileV1,
    create_suckle_extraction_trial_v1, suckle_extraction_profile_v1,
)
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeV1

__version__ = "0.1.0"
__all__ = ["SUCKLE_EXTRACTION_OUTCOME_CASES_V1", "SuckleExtractionOutcomeExperimentV1", "suckle_extraction_outcome_profile_v1",
           "run_suckle_extraction_outcome_v1", "render_suckle_extraction_outcome_v1", "run_suckle_extraction_outcome_menu_v1", "__version__"]
SUCKLE_EXTRACTION_OUTCOME_CASES_V1 = (
    *(case for case in SUCKLE_EXTRACTION_CASES_V1 if case != "extraction_off"),
    "consumer_off", "comparison_off", "without_closure_owner", "nonfocal_outcome",
)
_NO_CLAIM = frozenset({"suckle_off", "no_need", "source_off", "attention_off", "missing_stroke", "missing_seal",
                       "nonsealable", "competing_initial", "consumer_off"})


def suckle_extraction_outcome_profile_v1(case: str = "nominal") -> SuckleExtractionExperimentProfileV1:
    """Select the optional reader independently of old I/J/K and motor behavior."""
    if not isinstance(case, str) or case not in SUCKLE_EXTRACTION_OUTCOME_CASES_V1:
        raise ValueError("unknown original-extraction correspondence review case")
    base = "nominal" if case in {"consumer_off", "comparison_off", "without_closure_owner", "nonfocal_outcome"} else case
    profile = suckle_extraction_profile_v1(base)
    if case == "nonfocal_outcome":
        profile = replace(profile, latch=replace(profile.latch, run=replace(profile.latch.run, competitor_cutoffs=(4, 8, 12, 16, 20))))
    task = replace(profile.latch.suckle, extraction_outcomes_enabled=case != "consumer_off",
                   extraction_prediction_comparison_enabled=case != "comparison_off")
    if case == "without_closure_owner":
        task = replace(task, outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False)
    return replace(profile, latch=replace(profile.latch, suckle=task))


@dataclass(frozen=True, slots=True)
class SuckleExtractionOutcomeExperimentV1:
    """Completed original evidence and a separate same-condition consumer-off run."""

    case: str
    profile: SuckleExtractionExperimentProfileV1
    run: SeekNippleExperimentV1
    control: SeekNippleExperimentV1

    def outcomes(self) -> tuple[SuckleExtractionOutcomeV1, ...]:
        """Read actual newly published C2/E results, never rebuild them from exports."""
        return tuple(result for cycle in self.run.cycles if cycle.extraction_correspondence is not None
                     for result in cycle.extraction_correspondence.outcomes)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Test live contribution, independent knowledge, no action/learning side effects."""
        outcomes = self.outcomes()
        registrations = tuple(c.extraction_correspondence.registration for c in self.run.cycles
                              if c.extraction_correspondence is not None and c.extraction_correspondence.registration is not None)
        expected = 0 if self.case in _NO_CLAIM else 1
        physical = self.run.physical_samples[-1].extraction
        limits = {"extraction_pending_claims": 1, "extraction_outcome_history": 1, "extraction_outcome_samples": 8,
                  "extraction_outcome_endpoint_refs": 4, "extraction_outcome_command_ticks": 8, "suckle_staged_intervals": 16}
        quantities = {"nominal": .2, "dry": 0, "depleted": .05, "one_cycle": .1, "comparison_off": .2,
                      "without_closure_owner": .2, "latch_then_extract": .2}
        old_frames = ("suckle_correspondence", "suckle_attention", "suckle_learning_report", "seeking_correspondence",
                      "seeking_attention", "seeking_learning_report", "maternal_correspondence", "learning_report")
        return (
            ("expected_single_original_claim_and_result", len(registrations) == len(outcomes) == expected),
            ("result_retains_identical_registered_claim", all(result.claim is registrations[0] for result in outcomes)),
            ("no_action_or_physics_effect", self.run.local_steps == self.control.local_steps
             and self.run.physical_samples == self.control.physical_samples and self.run.installations == self.control.installations),
            ("ordinary_commitments_unchanged", [c.commitment for c in self.run.cycles] == [c.commitment for c in self.control.cycles]),
            ("current_sources_unchanged", [c.feeding_detail_source for c in self.run.cycles] == [c.feeding_detail_source for c in self.control.cycles]),
            ("old_outcome_and_learning_routes_unchanged", len(self.run.cycles) == len(self.control.cycles) and all(
                getattr(a, field) == getattr(b, field) for a, b in zip(self.run.cycles, self.control.cycles) for field in old_frames)),
            ("independent_original_deadline", all(r.claim.last_acceptable_availability_tick == r.claim.due_tick + 8
                                                  and r.end_tick <= r.claim.due_tick for r in outcomes)),
            ("no_duplicate_acquisitions", all(len({s.feedback.sample_id for s in r.samples}) == len(r.samples) for r in outcomes)),
            ("no_out_of_window_milk", all(r.claim.start_tick < s.feedback.event_tick <= r.end_tick
                                           for r in outcomes for s in r.samples)),
            ("interval_sum_not_unknown_total", all(
                (r.milk_evidence()["exact_observed_total"] is not None) == (r.milk_evidence()["coverage"] == "complete")
                for r in outcomes)),
            ("declared_known_quantity", all(abs(float(r.milk_evidence()["known_interval_sum"]) - quantities[self.case]) < 1e-9
                                            for r in outcomes) if self.case in quantities else True),
            ("dry_not_a_milk_prediction_failure", all(dict(r.relations)["finite_reciprocation"] == "matched"
                                                     and dict(r.relations)["sealed_contact"] == "matched" for r in outcomes)
             if self.case == "dry" else True),
            ("missing_milk_sensor_not_zero_feeding", all(r.milk_evidence()["coverage"] == "unavailable"
                                                        and r.milk_evidence()["exact_observed_total"] is None for r in outcomes)
             and physical is not None and physical.transferred_milk_units > 0 if self.case == "milk_sensor_off" else True),
            ("comparison_off_disables_only_scores", all(set(dict(r.relations).values()) == {"comparison_disabled"} for r in outcomes)
             if self.case == "comparison_off" else True),
            ("bounded_reader_and_shared_ingress", all(0 <= dict(self.run.peak_counts).get(key, 0) <= value for key, value in limits.items())),
            ("durable_state_unchanged", self.run.durable_before == self.run.durable_after == self.control.durable_after),
            ("one_world_step_per_interval", len(self.run.local_steps) == self.profile.latch.run.horizon_ticks),
            ("no_nourishment_or_new_task_authority", all(not r.as_dict()["full_suckle_complete"] and r.as_dict()["durable_updates"] == 0
                                                        and r.milk_evidence()["causal_credit"] == "not_established" for r in outcomes)),
        )

    @property
    def review_status(self) -> str:
        """Fail on a declared control violation, not on an honest adverse outcome."""
        return "PASS" if all(ok for _, ok in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Detach full observer evidence without issuing commands or rescoring input."""
        physical = self.run.physical_samples[-1].extraction
        data = {"scope": "P16_2C_LD_original_extraction_correspondence", "case": self.case, "profile": self.profile.as_dict(),
                "outcomes": [item.as_dict() for item in self.outcomes()], "cycles": [c.as_dict() for c in self.run.cycles],
                "physical_milk_total_observer_only": None if physical is None else physical.transferred_milk_units,
                "peak_counts": dict(self.run.peak_counts), "checks": dict(self.checks()), "review_status": self.review_status,
                "scope_limits": "no_next_batch_attention_interpretation_learning_nourishment_or_causal_credit"}
        return json.loads(json.dumps(data, allow_nan=False))


def run_suckle_extraction_outcome_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SuckleExtractionOutcomeExperimentV1:
    """Execute the existing L-C collector twice with only the named reader changed."""
    profile = suckle_extraction_outcome_profile_v1(case)
    trial = create_suckle_extraction_trial_v1(profile, trace_capacity=trace_capacity)
    run = collect_seek_nipple_evidence_v1(trial, profile.latch.run)
    control_task = replace(profile.latch.suckle, extraction_outcomes_enabled=False, extraction_prediction_comparison_enabled=True)
    control_profile = replace(profile, latch=replace(profile.latch, suckle=control_task))
    control_trial = create_suckle_extraction_trial_v1(control_profile, trace_capacity=trace_capacity)
    control = collect_seek_nipple_evidence_v1(control_trial, control_profile.latch.run)
    return SuckleExtractionOutcomeExperimentV1(case, profile, run, control)


def render_suckle_extraction_outcome_v1(result: SuckleExtractionOutcomeExperimentV1, *, detail: bool = False) -> str:
    """Read a completed run: movement, original relations, milk quantity and coverage."""
    if not isinstance(result, SuckleExtractionOutcomeExperimentV1) or not isinstance(detail, bool):
        raise TypeError("extraction evidence renderer needs its completed experiment and Boolean detail")
    physical = result.run.physical_samples[-1].extraction
    lines = [f"L-D original extraction / interval milk: {result.case} -- {result.review_status}",
             "  Original selected claim + returned execution + paired historical sensing -> bounded C2 result.",
             "  Dry is not a failed milk forecast; yield was not predicted. No next action, nourishment or learning.",
             f"  Physical total (observer-only): {None if physical is None else physical.transferred_milk_units}"]
    for outcome in result.outcomes():
        milk = outcome.milk_evidence()
        lines.extend((f"  Execution: {outcome.status}; relations: {dict(outcome.relations)}",
                      f"  Known milk sum={milk['known_interval_sum']}; coverage={milk['coverage']}; exact observed total={milk['exact_observed_total']}",
                      f"  Missing intervals={milk['missing_event_ticks']}; unassociated measured intervals={milk['unassociated_known_event_ticks']}"))
        if detail:
            lines.append(f"  Original PNM={outcome.claim.application.projection.pnm.pnm_id}; action window="
                         f"[{outcome.claim.start_tick},{outcome.claim.due_tick}); accounted through={outcome.end_tick}; "
                         f"last permitted availability={outcome.claim.last_acceptable_availability_tick}; read at C2={outcome.evaluated_tick}")
            for endpoint in outcome.samples:
                sample = endpoint.feedback
                lines.append(f"    Sample {sample.sample_id} event={sample.event_tick} available={sample.available_tick}: "
                             f"{sample.oral_extraction.as_dict() if sample.oral_extraction else '(no extraction sensing)'}; "
                             f"paired_scene={endpoint.observation is not None}")
    lines.extend(f"  {'PASS' if ok else 'FAIL'} {name}" for name, ok in result.checks())
    return "\n".join(lines)


def run_suckle_extraction_outcome_menu_v1() -> None:
    """Shared finite reviews with read-only inspection; no hidden live execution."""
    groups = {"1": ("nominal", "consumer_off", "comparison_off", "without_closure_owner"),
              "2": ("dry", "depleted", "milk_sensor_off", "dropout", "delayed"),
              "3": ("no_capability", "blocked_motor", "cancelled", "support_loss", "competing_after", "nonfocal_outcome"),
              "4": ("one_cycle", "cadence_1", "cadence_8", "latch_then_extract", "seek_then_latch", "stand_follow"),
              "5": SUCKLE_EXTRACTION_OUTCOME_CASES_V1}
    retained: tuple[SuckleExtractionOutcomeExperimentV1, ...] = ()
    while True:
        print("\nL-D: original extraction correspondence and interval milk (not complete feeding)")
        print("1 reader controls; 2 quantity/coverage; 3 adverse; 4 continuity/time; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}: return
        if choice == "6":
            print("\n\n".join(render_suckle_extraction_outcome_v1(r, detail=True) for r in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_suckle_extraction_outcome_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_extraction_outcome_v1(r) for r in retained))
        else:
            print("Invalid selection.")
