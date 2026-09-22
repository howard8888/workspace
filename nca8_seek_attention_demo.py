#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed-time seeking outcome/Attention contrasts on the existing C/D collector.

Only the new source relevance route differs in matched on/off pairs. Current
source/body, original endpoint claims and ordinary priorities agree through the
critical allocation. A visual source competes through ordinary Attention; the
observer never supplies a WNM winner. Full exports include all later physical
consequences rather than assuming that changed allocation improves speed.

Original mismatch at event8 can be interpreted at cutoff12 after current evidence
has recovered. The recovered condition uses a predeclared opposite forcing at
[8,9), not a hidden outcome-triggered repair. All disturbances use the unchanged
provider. The fixed profile tests functional allocation, not neural timing, a
universal outcome policy or feeding/milk/Rest competence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cca8_cli
from cca8_support_world import MotorWorldPerturbationV1, OralWorldPerturbationV1, PlanarDetailObjectV1
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_attention import SeekingMismatchRequestV1, SeekingInterpretationV1
from nca8_seek_nipple_demo import SeekNippleExperimentProfileV1, SeekNippleExperimentV1, collect_seek_nipple_evidence_v1, seek_nipple_owner_limits_v1
from nca8_seek_outcomes_demo import seek_nipple_outcome_profile_v1
from nca8_seek_outcomes import SeekNippleOutcomeV1

__version__ = "0.1.0"
__all__ = ["SEEKING_ATTENTION_CASES_V1", "SeekingAttentionExperimentV1", "seeking_attention_profile_v1",
           "create_seeking_attention_trial_v1", "run_seeking_attention_v1", "render_seeking_attention_v1",
           "run_seeking_attention_menu_v1", "__version__"]

SEEKING_ATTENTION_CASES_V1 = (
    "competing_on", "competing_off", "maintain_on", "maintain_off", "nominal_on", "nominal_off", "no_surface",
    "comparison_off", "historical_resolved", "after_endpoint_drift", "routine_once", "persistent",
    "support_priority", "support_before_cutoff", "brief_gap", "dropout", "delayed", "no_capability", "narrowed", "cancelled",
    "stand_follow", "stand_follow_drift", "cadence_1", "cadence_8",
)
_LIMITS = {**seek_nipple_owner_limits_v1(), "seeking_pending_claims": 8, "seeking_outcome_history": 32,
           "seeking_recent_acquisitions": 16, "seeking_awaiting_installation": 1,
           "seeking_execution_reference": 1, "seeking_staged_intervals": 16,
           "seeking_attention_pending_requests": 8, "seeking_attention_previous_endpoint": 1,
           "seeking_attention_dependency": 1, "seeking_attention_dispositions": 32}


def seeking_attention_profile_v1(case: str = "competing_on") -> SeekNippleExperimentProfileV1:
    """Freeze the actual provider, need, competition and route before any execution.

    Small endpoint drift adds 0.01m at [7,8). Routine/persistent controls use
    intermediate predictions rather than already predicted final reach. The
    persistent problem has detail at 0.34m and drift at [7,8) and [15,16).
    Support loss at [11,65) is first available after cutoff12; [10,65)
    is already visible at cutoff12 and prevents seeking focal capture. Both
    preserve original event8 and test the unchanged event/availability contract.
    No control modifies prediction/reach tolerances, lease or task budgets.
    """
    if not isinstance(case, str) or case not in SEEKING_ATTENTION_CASES_V1:
        raise ValueError("unknown seeking outcome-Attention review case")
    aliases = {"nominal_on": "nominal", "nominal_off": "nominal", "stand_follow_drift": "stand_follow",
               "routine_once": "intermediate_target", "persistent": "intermediate_target"}
    special = {"competing_on", "competing_off", "maintain_on", "maintain_off", "comparison_off",
               "historical_resolved", "support_priority", "support_before_cutoff"}
    base = seek_nipple_outcome_profile_v1("endpoint_drift" if case in special else aliases.get(case, case))
    oral, planar, physical = base.oral, base.planar, base.physical
    competitors = (8, 12) if case in {"competing_on", "competing_off", "comparison_off"} else (12,) if case in {"maintain_on", "maintain_off"} else ()
    if case == "historical_resolved":
        oral = replace(oral, perturbations=(*oral.perturbations, OralWorldPerturbationV1(8, 9, -0.2)))
    if case in {"routine_once", "persistent"}:
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(7, 8, 0.2),))
        if case == "persistent":
            planar = replace(planar, objects=tuple(replace(item, position=(0.34, 0.0)) if isinstance(item, PlanarDetailObjectV1) else item
                                                  for item in planar.objects))
            oral = replace(oral, surfaces=tuple(replace(item, position=(0.34, 0.0)) for item in oral.surfaces),
                           perturbations=(*oral.perturbations, OralWorldPerturbationV1(15, 16, 0.2)))
    if case in {"support_priority", "support_before_cutoff"}:
        start = 10 if case == "support_before_cutoff" else 11
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(start, 65, remove_support=True),))
    if case == "stand_follow_drift":
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(107, 108, 0.2),))
        competitors = (108, 112)
    return replace(base, case=case, oral=oral, planar=planar, physical=physical, competitor_cutoffs=competitors,
                   seeking=replace(base.seeking, outcome_attention_enabled=case not in {"competing_off", "maintain_off", "nominal_off"},
                                   prediction_comparison_enabled=case != "comparison_off"))


def create_seeking_attention_trial_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct a fresh isolated trial; choose no primitive or body requirement."""
    profile = seeking_attention_profile_v1(case)
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
    )


@dataclass(frozen=True, slots=True)
class SeekingAttentionExperimentV1:
    """Complete observer evidence and retained dispositions, never an execution input."""

    evidence: SeekNippleExperimentV1
    dispositions: tuple[tuple[str, str, int], ...]

    def requests(self) -> tuple[SeekingMismatchRequestV1, ...]:
        """Read actual source requests created from corresponding original outcomes."""
        return tuple(request for cycle in self.evidence.cycles if cycle.seeking_attention is not None for request in cycle.seeking_attention.created)

    def interpretations(self) -> tuple[SeekingInterpretationV1, ...]:
        """Count a focal result once, not again when a dependent response reads it."""
        return tuple(c.seeking_attention.allocation.interpretation for c in self.evidence.cycles if c.seeking_attention is not None
                     and c.seeking_attention.allocation.kind == "interpretation" and c.seeking_attention.allocation.interpretation is not None)

    def outcomes(self) -> tuple[SeekNippleOutcomeV1, ...]:
        """Read the unchanged D correspondence result independently from relevance."""
        return tuple(result for c in self.evidence.cycles if c.seeking_correspondence is not None for result in c.seeking_correspondence.outcomes)

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Reject missing/duplicate/coerced counts and unknown or overflowing owners."""
        raw = self.evidence
        required = {"wnm", "current_pnm", "seeking_pending_claims", "feeding_detail_current_configurations"}
        if raw.profile.seeking.outcome_attention_enabled:
            required |= {"seeking_attention_pending_requests", "seeking_attention_dependency", "seeking_attention_previous_endpoint"}
        missing = tuple("missing:" + key for key in sorted(required - dict(raw.peak_counts).keys()))
        duplicates = ("duplicate_counts",) if len(raw.peak_counts) != len(dict(raw.peak_counts)) else ()
        return missing + duplicates + tuple(key for key, count in raw.peak_counts if key not in _LIMITS
                                            or isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= _LIMITS[key])

    def metrics(self) -> dict[str, object]:
        """Report actual allocation and complete task/physical costs, without speed claims."""
        raw = self.evidence
        at12 = next((c for c in raw.cycles if c.calculation.cutoff_tick == 12), None)
        selected = at12.calculation.attention.selected_source_state if at12 is not None else None
        return {**raw.metrics(), "route_enabled": raw.profile.seeking.outcome_attention_enabled,
                "request_ticks": [item.admitted_tick for item in self.requests()],
                "significance": [item.significance for item in self.requests()],
                "interpretation_ticks": [item.cutoff_tick for item in self.interpretations()],
                "interpretation_statuses": [item.status for item in self.interpretations()],
                "response_ticks": [c.calculation.cutoff_tick for c in raw.cycles if c.seeking_attention is not None
                                   and c.seeking_attention.allocation.kind == "response_reconsideration"],
                "cutoff12_source": selected.source_map_ref.map_id if selected is not None else None,
                "cutoff12_disposition": at12.calculation.attention.disposition.value if at12 is not None else None}

    def _expected_effect(self) -> bool:
        """Falsifiable named causal predictions; adverse cases are not forced successes."""
        case, requests, interpretations = self.evidence.profile.case, self.requests(), self.interpretations()
        metrics = self.metrics()
        if case in {"competing_on", "maintain_on"}:
            return metrics["cutoff12_source"] == "feeding_detail" and metrics["interpretation_ticks"] == [12]
        if case in {"competing_off", "maintain_off", "comparison_off"}:
            return metrics["cutoff12_source"] == "visual_scene" and not requests and not interpretations
        if case == "historical_resolved":
            return bool(interpretations) and interpretations[0].status == "historical_resolved" and requests[0].outcome.status == "mismatch"
        if case == "persistent":
            return any(item.significance == "persistent_executed_seeking_discrepancy" for item in requests)
        if case == "support_priority":
            later = next(c for c in self.evidence.cycles if c.calculation.cutoff_tick == 16)
            chosen = later.calculation.attention.selected_source_state
            return (metrics["interpretation_ticks"] == [12] and chosen is not None
                    and chosen.source_map_ref.map_id == "posture_support")
        if case == "support_before_cutoff":
            return (bool(requests) and not interpretations and metrics["cutoff12_source"] == "posture_support"
                    and any(reason == "expired_uninterpreted" for _, reason, _ in self.dispositions))
        if case == "stand_follow_drift":
            return any(item.admitted_tick == 112 for item in requests) and any(item.cutoff_tick == 112 for item in interpretations)
        if case in {"nominal_on", "nominal_off", "no_surface", "after_endpoint_drift", "routine_once", "dropout", "delayed",
                    "no_capability", "narrowed", "cancelled", "stand_follow"}:
            return not requests and not interpretations
        return all(item.outcome.status in {"mismatch", "identity_contradicted"} for item in requests)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Check provenance, slot exclusivity, original timing, boundedness and no learning."""
        raw, requests, interpretations = self.evidence, self.requests(), self.interpretations()
        expected_ticks = tuple(range(0, raw.profile.horizon_ticks + 1, raw.profile.cadence))
        outcomes = self.outcomes()
        unique = {item.request_id: item for item in requests}
        outcome_ids = {id(item) for item in outcomes}
        frames = [c for c in raw.cycles if c.seeking_attention is not None]
        slot_valid = all(sum(int(a is not None and a.kind == "interpretation") for a in (
            c.calculation.outcome_allocation, c.calculation.maternal_outcome_allocation, c.calculation.seeking_outcome_allocation,
        )) + int(c.calculation.navigation.application is not None) <= 1 for c in raw.cycles)
        return (
            ("profile_is_the_declared_experiment", isinstance(raw.profile.case, str) and raw.profile.case in SEEKING_ATTENTION_CASES_V1
             and raw.profile == seeking_attention_profile_v1(raw.profile.case)),
            ("complete_fixed_schedule", tuple(c.calculation.cutoff_tick for c in raw.cycles) == expected_ticks
             and tuple(s.tick for s in raw.local_steps) == tuple(range(raw.profile.horizon_ticks))
             and tuple(p.tick for p in raw.physical_samples) == tuple(range(raw.profile.horizon_ticks + 1))),
            ("declared_causal_effect", self._expected_effect()),
            ("route_enablement_is_explicit", len(frames) == (len(expected_ticks) if raw.profile.seeking.outcome_attention_enabled else 0)),
            ("request_refers_to_actual_published_outcome", all(id(item.outcome) in outcome_ids for item in requests)),
            ("only_executed_informative_results_request_work", all(item.outcome.command_intervals > 0 and item.outcome.evidence is not None
             and item.outcome.status in {"mismatch", "identity_contradicted"} for item in requests)),
            ("admission_does_not_borrow_future_evidence", all(item.outcome.evaluated_tick == item.admitted_tick
             and item.outcome.evidence is not None and item.outcome.evidence.feedback.available_tick <= item.admitted_tick for item in requests)),
            ("one_request_per_result", len(unique) == len(requests)),
            ("one_consumption_per_request", len({i.request.request_id for i in interpretations}) == len(interpretations)),
            ("interpretation_uses_original_request", all(unique.get(item.request.request_id) is item.request for item in interpretations)),
            ("interpretation_within_original_relevance_window", all(item.request.admitted_tick <= item.cutoff_tick < item.request.expires_at_tick
             for item in interpretations)),
            ("exact_current_source_is_the_one_wnm", all(c.calculation.navigation.wnm is not None
             and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in frames
             if c.seeking_attention is not None and c.seeking_attention.allocation.kind == "interpretation")),
            ("single_demanding_operation", slot_valid),
            ("no_target_or_primitive_from_interpretation", all(c.calculation.navigation.application is None and not c.reservations
             for c in frames if c.seeking_attention is not None and not c.seeking_attention.allocation.permits_primitive_selection)),
            ("response_is_a_later_opportunity", all(c.seeking_attention is not None and c.seeking_attention.allocation.interpretation is not None
             and c.seeking_attention.allocation.interpretation.cycle_id < c.commitment.cycle_id for c in frames
             if c.seeking_attention is not None and c.seeking_attention.allocation.kind == "response_reconsideration")),
            ("original_task_budget_includes_interpretation", all(c.seeking_task is not None and c.seeking_task.task is not None
             and c.commitment.cycle_id - c.seeking_task.task.started_cycle < 12
             and c.calculation.cutoff_tick - c.seeking_task.task.started_tick < 48 for c in frames
             if c.seeking_attention is not None and c.seeking_attention.allocation.kind == "interpretation")),
            ("finite_owner_storage", not self.bound_violations),
            ("one_handoff_consumption_per_focal_opportunity", raw.handoff_consumptions == len(expected_ticks)),
            ("installations_have_actual_authorization", raw.installations == sum(bool(c.reservations) for c in raw.cycles)),
            ("durable_sources_unchanged", bool(raw.durable_before) and raw.durable_before == raw.durable_after),
            ("no_feeding_learning_claim", all(c.seeking_attention is not None and c.seeking_attention.as_dict()["durable_updates"] == 0 for c in frames)),
        )

    @property
    def review_status(self) -> str:
        """Fail the review when recorded evidence does not meet its declared checks."""
        return "PASS" if all(value for _, value in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export every collected causal record, without invoking any owner or world."""
        raw = self.evidence
        return {"scope": "P16_2C_E_seeking_attention", "profile": raw.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in raw.cycles], "local_steps": [s.as_dict() for s in raw.local_steps],
                "observer_physical_samples": [s.as_dict() for s in raw.physical_samples], "final_feedback": raw.final_feedback.as_dict(),
                "peak_owner_counts": dict(raw.peak_counts), "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
                "durable_before": raw.durable_before, "durable_after": raw.durable_after, "dispositions": list(self.dispositions),
                "registered_pnm_cycles": list(raw.registered_pnm_cycles), "checks": dict(self.checks()), "review_status": self.review_status,
                "feeding_learning": "unimplemented_no_participation", "causal_credit": "not_established", "B99": "open"}


def run_seeking_attention_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> SeekingAttentionExperimentV1:
    """Run the existing fixed-schedule collector; the observer never chooses a task."""
    profile = seeking_attention_profile_v1(case)
    trial = create_seeking_attention_trial_v1(case, trace_capacity=trace_capacity)
    evidence = collect_seek_nipple_evidence_v1(trial, profile)
    route = trial.core.feeding_detail.outcome_attention if trial.core.feeding_detail is not None else None
    return SeekingAttentionExperimentV1(evidence, () if route is None else route.dispositions())


def render_seeking_attention_v1(result: SeekingAttentionExperimentV1, *, detail: bool = False) -> str:
    """Render retained original/current evidence; neither view reruns movement."""
    if not isinstance(result, SeekingAttentionExperimentV1) or not isinstance(detail, bool):
        raise TypeError("seeking Attention rendering requires a completed result and Boolean detail flag")
    metrics = result.metrics()
    lines = [f"P16-2C-E / {result.evidence.profile.case} / SEEKING ATTENTION REVIEW: {result.review_status}",
             f"  requests={metrics['request_ticks']}; interpretations={metrics['interpretation_ticks']}; response={metrics['response_ticks']}",
             f"  current relevance={metrics['interpretation_statuses']}; cutoff12 source={metrics['cutoff12_source']}",
             f"  oral commands={metrics['oral_commands']}; reached detail={metrics['first_reached_detail_tick']}; "
             f"physical touch={metrics['first_physical_touch_tick']}",
             "  One focal allocation; original mismatch is not causal credit, contact/latch, milk, learning or B99."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for item in result.interpretations():
            lines.append(f"  {item.request.request_id}: original endpoint={item.request.outcome.claim.due_tick}; "
                         f"admitted={item.request.admitted_tick}; interpreted={item.cutoff_tick}; {item.status}; "
                         f"current relations={dict(item.relation_relevance)}")
        for cycle in result.evidence.cycles:
            frame = cycle.seeking_attention
            if frame is not None:
                source = cycle.calculation.attention.selected_source_state
                lines.append(f"  cutoff={cycle.calculation.cutoff_tick}: source={source.source_map_ref.map_id if source else 'none'}; "
                             f"allocation={frame.allocation.kind}; pending={len(frame.pending)}; targets={len(cycle.reservations)}")
        lines.append(f"  dispositions={result.dispositions}")
    return "\n".join(lines)


def run_seeking_attention_menu_v1() -> None:
    """Offer shared causal contrasts and inspection of retained results without rerun."""
    groups = {"1": ("competing_on", "competing_off", "maintain_on", "maintain_off"),
              "2": ("nominal_on", "nominal_off", "no_surface", "comparison_off", "routine_once", "persistent"),
              "3": ("historical_resolved", "after_endpoint_drift", "support_priority", "support_before_cutoff", "brief_gap", "dropout"),
              "4": ("no_capability", "narrowed", "cancelled", "delayed", "cadence_1", "cadence_8"),
              "5": ("stand_follow", "stand_follow_drift"), "6": SEEKING_ATTENTION_CASES_V1}
    retained: tuple[SeekingAttentionExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-E -- SEEKING MISMATCH / ONE FOCAL ALLOCATION")
        print("  1) Competing and maintained source on/off / 2) Match, touch, routine and persistent discrepancy")
        print("  3) Historical/current evidence and support / 4) Permission, delay and cadence")
        print("  5) Continuous stand-follow-seek / 6) All cases / 7) Inspect retained detail (no new movement)")
        print("  [Enter] Return to feeding review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "7":
            print("\n\n".join(render_seeking_attention_v1(item, detail=True) for item in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_seeking_attention_v1(case) for case in groups[choice])
            print("\n\n".join(render_seeking_attention_v1(item) for item in retained))
        else:
            print("Choose 1-7 or press Enter to return.")
