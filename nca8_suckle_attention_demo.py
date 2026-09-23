#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu/CLI review of J's bounded Suckle outcome-to-Attention causal contribution.

The retained H factory and C collector supply the only physical/cognitive loop.
The cases change explicit route/comparison switches and a fixed competing-source
schedule, never task selection or physical rules. A nonsealable H surface gives
an executed seal discrepancy. Paired on/off cases share their physical profiles,
evidence timing and non-outcome Attention inputs; ordinary Attention and Navigation
still decide. These live runs do not claim a naturally occurring simultaneous
seeking/Suckle queue: that separate allocation contract has controlled unit tests.

All exported records and checks are observers. Inspection does not re-run a trial,
consume a question or refresh its original lifetime. PASS qualifies the declared
route/control, not milk, full feeding, causal diagnosis, learning or Gate B99.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cca8_cli
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle_attention import SuckleInterpretationV1, SuckleMismatchRequestV1
from nca8_suckle_demo import (
    SuckleExperimentProfileV1, SuckleExperimentV1, create_suckle_trial_v1, suckle_owner_limits_v1, suckle_profile_v1,
)
from nca8_suckle_outcomes import SuckleOutcomeV1

__version__ = "0.1.0"
__all__ = ["SUCKLE_ATTENTION_CASES_V1", "SuckleAttentionExperimentV1", "suckle_attention_profile_v1",
           "create_suckle_attention_trial_v1", "run_suckle_attention_v1", "render_suckle_attention_v1",
           "run_suckle_attention_menu_v1", "__version__"]

SUCKLE_ATTENTION_CASES_V1 = (
    "competing_on", "competing_off", "maintain_on", "maintain_off", "nominal_on", "nominal_off", "comparison_off",
    "missing_seal", "no_capability", "blocked_motor", "cancelled", "support_loss", "seek_then_latch", "stand_follow",
)
_ROUTE_CASES = frozenset({"competing_on", "competing_off", "maintain_on", "maintain_off", "comparison_off"})
_LIMITS = {**suckle_owner_limits_v1(), "suckle_pending_claims": 8, "suckle_outcome_history": 32,
           "suckle_recent_acquisitions": 16, "suckle_awaiting_installation": 1, "suckle_execution_reference": 1,
           "suckle_staged_intervals": 16, "suckle_attention_pending_requests": 8,
           "suckle_attention_dependency": 1, "suckle_attention_dispositions": 32}


def _base_case(case: str) -> str:
    """Resolve a declared review case, without repairing an unknown selector."""
    if not isinstance(case, str) or case not in SUCKLE_ATTENTION_CASES_V1:
        raise ValueError("unknown Suckle outcome-Attention review case")
    if case in _ROUTE_CASES:
        return "nonsealable"
    return "nominal" if case in {"nominal_on", "nominal_off"} else case


def suckle_attention_profile_v1(case: str = "competing_on") -> SuckleExperimentProfileV1:
    """Fix the H provider and J route before execution; create no response sequence.

    Competing cases select the visual competitor at cutoffs 8 and 12; maintaining
    cases offer it only at 12. The original seal event at tick 8 is available at 9
    and is therefore compared at cutoff 12 under the unchanged four-tick cadence.
    The same competitor inputs are used by each on/off pair. Nominal and adverse
    controls retain their own H provider, horizon, capability and schedule.
    """
    profile = suckle_profile_v1(_base_case(case))
    competitors = ((8, 12) if case in {"competing_on", "competing_off", "comparison_off"}
                   else (12,) if case in {"maintain_on", "maintain_off"} else profile.run.competitor_cutoffs)
    return replace(profile, run=replace(profile.run, case=case, competitor_cutoffs=competitors),
                   suckle=replace(profile.suckle, outcomes_enabled=True, prediction_comparison_enabled=case != "comparison_off",
                                  outcome_attention_enabled=case not in {"competing_off", "maintain_off", "nominal_off"}))


def create_suckle_attention_trial_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Reuse the H factory with explicit I/J switches; construction performs no work."""
    profile = suckle_attention_profile_v1(case)
    return create_suckle_trial_v1(_base_case(case), trace_capacity=trace_capacity, outcomes_enabled=True,
                                  compare_predictions=profile.suckle.prediction_comparison_enabled,
                                  outcome_attention_enabled=profile.suckle.outcome_attention_enabled)


def _source_name(cycle: IntegratedRightingCycleV1 | None) -> str | None:
    """Read the actual ordinary Attention choice, not an expected case label."""
    source = cycle.calculation.attention.selected_source_state if cycle is not None else None
    return source.source_map_ref.map_id if source is not None else None


@dataclass(frozen=True, slots=True)
class SuckleAttentionExperimentV1:
    """Completed observer evidence with J-specific checks, not inherited H verdicts."""

    evidence: SuckleExperimentV1
    dispositions: tuple[tuple[str, str, int], ...]

    def outcomes(self) -> tuple[SuckleOutcomeV1, ...]:
        """Read each original I publication once, including unresolved/refused results."""
        return tuple(item for cycle in self.evidence.run.cycles if cycle.suckle_correspondence is not None
                     for item in cycle.suckle_correspondence.outcomes)

    def requests(self) -> tuple[SuckleMismatchRequestV1, ...]:
        """Read admitted questions with their original evidence and lifetime."""
        return tuple(item for cycle in self.evidence.run.cycles if cycle.suckle_attention is not None
                     for item in cycle.suckle_attention.created)

    def interpretations(self) -> tuple[SuckleInterpretationV1, ...]:
        """Count performed interpretations, not repeated dependency readouts."""
        return tuple(cycle.suckle_attention.allocation.interpretation for cycle in self.evidence.run.cycles
                     if cycle.suckle_attention is not None and cycle.suckle_attention.allocation.kind == "interpretation"
                     and cycle.suckle_attention.allocation.interpretation is not None)

    def metrics(self) -> dict[str, object]:
        """Expose actual source choice, interpretation and execution as separate facts."""
        at12 = next((cycle for cycle in self.evidence.run.cycles if cycle.calculation.cutoff_tick == 12), None)
        return {**self.evidence.metrics(), "route_enabled": self.evidence.profile.suckle.outcome_attention_enabled,
                "cutoff12_source": _source_name(at12),
                "cutoff12_disposition": at12.calculation.attention.disposition.value if at12 is not None else None,
                "outcome_statuses": [item.status for item in self.outcomes()],
                "request_ticks": [item.admitted_tick for item in self.requests()],
                "request_expiries": [item.expires_at_tick for item in self.requests()],
                "interpretation_ticks": [item.cutoff_tick for item in self.interpretations()],
                "interpretation_statuses": [item.status for item in self.interpretations()]}

    def _expected_effect(self) -> bool:
        """Check declared case predictions without substituting a desired task result."""
        case, metrics = self.evidence.profile.run.case, self.metrics()
        statuses = tuple(item.status for item in self.outcomes())
        if case in _ROUTE_CASES:
            expected = "comparison_disabled" if case == "comparison_off" else "mismatch"
            if statuses != (expected,):
                return False
            if case in {"competing_on", "maintain_on"}:
                disposition = "switch" if case == "competing_on" else "maintain"
                return (metrics["cutoff12_source"] == "feeding_detail" and metrics["cutoff12_disposition"] == disposition
                        and metrics["interpretation_ticks"] == [12] and metrics["interpretation_statuses"] == ["still_relevant"])
            return metrics["cutoff12_source"] == "visual_scene" and not self.requests() and not self.interpretations()
        if self.requests() or self.interpretations():
            return False
        if case == "missing_seal":
            return statuses == ("unknown",)
        if case == "no_capability":
            return bool(statuses) and all(status == "not_applied" for status in statuses)
        if case in {"blocked_motor", "cancelled", "support_loss"}:
            return statuses == ("interrupted",)
        return statuses == ("matched",)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Qualify routing, original identity, single allocation, timing and bounds.

        These checks consume only completed observer records. They do not call an
        outcome owner, interpret current relations again, or generate an action.
        H task success is not required for an adverse J control to pass.
        """
        raw, profile = self.evidence.run, self.evidence.profile
        outcomes, requests, interpretations = self.outcomes(), self.requests(), self.interpretations()
        consumed = tuple(c for c in raw.cycles if c.suckle_attention is not None
                         and c.suckle_attention.allocation.kind == "interpretation")
        counts = dict(raw.peak_counts)
        required = {"wnm", "current_pnm", "suckle_pending_claims", "feeding_detail_current_configurations"}
        if profile.suckle.outcome_attention_enabled:
            required |= {"suckle_attention_pending_requests", "suckle_attention_dependency", "suckle_attention_dispositions"}
        return (
            ("declared_attention_or_adverse_effect", self._expected_effect()),
            ("original_outcome_identity", all(any(request.outcome is outcome for outcome in outcomes) for request in requests)),
            ("original_claim_registered", all(any(c.suckle_correspondence is not None
                and c.suckle_correspondence.registration is outcome.claim for c in raw.cycles) for outcome in outcomes)),
            ("one_publication_and_consumption", len({item.number for item in outcomes}) == len(outcomes)
             and len({item.request.request_id for item in interpretations}) == len(interpretations)),
            ("original_bounded_lifetime", all(item.expires_at_tick == item.admitted_tick + 8 for item in requests)
             and all(item.request.admitted_tick <= item.cutoff_tick < item.request.expires_at_tick for item in interpretations)),
            ("ordinary_selected_source_is_WNM", all(c.calculation.navigation.wnm is not None
                and c.calculation.attention.selected_source_state is c.feeding_detail_source
                and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in consumed)),
            ("Navigation_grant_no_IP_or_new_permission", all(c.calculation.navigation.application is None
                and c.calculation.proposal is None and not c.reservations and c.commitment.selected_primitive_id is None
                and c.calculation.navigation.reason.startswith("outcome_interpretation:suckle_mismatch:") for c in consumed)),
            ("one_domain_interpretation", all(sum(item is not None and item.kind == "interpretation" for item in (
                c.calculation.outcome_allocation, c.calculation.maternal_outcome_allocation,
                c.calculation.seeking_outcome_allocation, c.calculation.suckle_outcome_allocation)) <= 1 for c in raw.cycles)),
            ("disabled_route_absent", profile.suckle.outcome_attention_enabled or all(c.suckle_attention is None for c in raw.cycles)),
            ("complete_measured_owner_bounds", required <= counts.keys() and len(counts) == len(raw.peak_counts)
             and all(key in _LIMITS and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _LIMITS[key]
                     for key, value in counts.items())),
            ("unchanged_finite_outer_schedule", len(raw.local_steps) == profile.run.horizon_ticks
             and len(raw.physical_samples) == profile.run.horizon_ticks + 1
             and len(raw.cycles) == profile.run.horizon_ticks // profile.run.cadence + 1),
            ("no_durable_update", bool(raw.durable_before) and raw.durable_before == raw.durable_after),
            ("no_suckle_learning", all(c.suckle_correspondence is not None
                and c.suckle_correspondence.as_dict()["learning_route"] == "unimplemented_no_participation" for c in raw.cycles)),
        )

    @property
    def review_status(self) -> str:
        """Compute PASS from all checks; never conceal a failed control."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export complete evidence with J labels, not obsolete H/C scope assertions."""
        raw = self.evidence.run
        return {"scope": "P16_2C_J_suckle_outcome_attention", "case": self.evidence.profile.run.case,
                "profile": self.evidence.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [item.as_dict() for item in raw.cycles], "local_steps": [item.as_dict() for item in raw.local_steps],
                "observer_physical_samples": [item.as_dict() for item in raw.physical_samples],
                "final_feedback": raw.final_feedback.as_dict(), "peak_owner_counts": dict(raw.peak_counts),
                "owner_limits": dict(_LIMITS), "durable_before": raw.durable_before, "durable_after": raw.durable_after,
                "outcomes": [item.as_dict() for item in self.outcomes()], "requests": [item.as_dict() for item in self.requests()],
                "interpretations": [item.as_dict() for item in self.interpretations()], "dispositions": list(self.dispositions),
                "checks": dict(self.checks()), "review_status": self.review_status, "B99": "open",
                "suckle_learning": "unimplemented_no_participation", "causal_credit": "not_established",
                "simultaneous_requests": "separate_controlled_contract_tests_not_claimed_by_this_live_run"}


def run_suckle_attention_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> SuckleAttentionExperimentV1:
    """Run the shared fixed-schedule collector and retain this route's dispositions."""
    profile = suckle_attention_profile_v1(case)
    trial = create_suckle_attention_trial_v1(case, trace_capacity=trace_capacity)
    raw = collect_seek_nipple_evidence_v1(trial, profile.run)
    owner = trial.core.feeding_detail.suckle_outcome_attention if trial.core.feeding_detail is not None else None
    return SuckleAttentionExperimentV1(SuckleExperimentV1(profile, raw), owner.dispositions() if owner is not None else ())


def render_suckle_attention_v1(result: SuckleAttentionExperimentV1, *, detail: bool = False) -> str:
    """Inspect completed evidence only; no callbacks into the live trial or owners."""
    if not isinstance(result, SuckleAttentionExperimentV1) or not isinstance(detail, bool):
        raise TypeError("Suckle Attention rendering requires a completed experiment and Boolean detail")
    metrics = result.metrics()
    lines = [f"P16-2C-J / {result.evidence.profile.run.case} / SUCKLE ATTENTION REVIEW: {result.review_status}",
             "  Original discrepancy -> feeding relevance -> ordinary Attention -> WNM -> Navigation interpretation.",
             f"  Route={metrics['route_enabled']}; cutoff12 source={metrics['cutoff12_source']}; "
             f"disposition={metrics['cutoff12_disposition']}; original outcomes={metrics['outcome_statuses']}",
             f"  Requests={metrics['request_ticks']}; original expiries={metrics['request_expiries']}; "
             f"interpretations={metrics['interpretation_ticks']}; present relevance={metrics['interpretation_statuses']}",
             "  Interpretation is not an IP application, remedy, movement grant or task restart.",
             "  Same-source queue arbitration has separate controlled contract tests; no second scheduler/WNM.",
             "  No milk, nourishment, Rest, Suckle learning or full-feeding/B99 claim."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        lines.append("  cutoff | focal source | Navigation operation | J allocation | present relevance")
        for cycle in result.evidence.run.cycles:
            frame = cycle.suckle_attention
            interpretation = frame.allocation.interpretation if frame is not None else None
            lines.append(f"  {cycle.calculation.cutoff_tick:6d} | {_source_name(cycle)} | {cycle.commitment.selected_primitive_id} | "
                         f"{frame.allocation.kind if frame is not None else 'route_off'} | "
                         f"{interpretation.status if interpretation is not None else '-'}")
        for request in result.requests():
            lines.append(f"  {request.request_id}: original={request.outcome.claim.preview.pnm.pnm_id}; "
                         f"outcome={request.outcome.status}; event={request.outcome.claim.due_tick}; "
                         f"admitted={request.admitted_tick}; expires={request.expires_at_tick}; {request.significance}")
    return "\n".join(lines)


def run_suckle_attention_menu_v1() -> None:
    """Share CLI experiments and offer retained detail without a second execution."""
    groups = {"1": ("competing_on", "competing_off", "maintain_on", "maintain_off"),
              "2": ("nominal_on", "nominal_off", "comparison_off", "missing_seal"),
              "3": ("no_capability", "blocked_motor", "cancelled", "support_loss"),
              "4": ("seek_then_latch", "stand_follow"), "5": SUCKLE_ATTENTION_CASES_V1}
    retained: tuple[SuckleAttentionExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-J -- SUCKLE DISCREPANCY / ATTENTION / ONE NAVIGATION INTERPRETATION")
        print("  1) Competing and maintained source: route on/off / 2) Match, comparison-off and missing evidence")
        print("  3) Capability, interrupted execution and protection / 4) Continuous earlier tasks")
        print("  5) All cases / 6) Inspect retained detail (no new movement) / [Enter] Return")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            print("\n\n".join(render_suckle_attention_v1(item, detail=True) for item in retained) if retained else "No retained results.")
        elif choice in groups:
            retained = tuple(run_suckle_attention_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_attention_v1(item) for item in retained))
        else:
            print("Unknown choice; use 1-6 or press Enter to return.")
