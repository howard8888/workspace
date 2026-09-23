#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first P16-2C-I correspondence on the unchanged H physical experiments.

The common H factory and C collector own the sole cognitive/physical loop. This
module retains observer evidence and checks original prediction, authorization,
execution and sensing separately. Every review also compares a fresh H control;
only the I observation frame and its bounded counters may differ. Comparison-off
keeps the same original claims, commands and evidence, disabling scoring alone.
No review result is supplied to cognition, and none closes feeding or B99.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

import cca8_cli
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleApplicationV1
from nca8_suckle_demo import (
    SUCKLE_LATCH_CASES_V1, SuckleExperimentV1, create_suckle_trial_v1, run_suckle_v1,
    suckle_owner_limits_v1, suckle_profile_v1,
)
from nca8_suckle_outcomes import SuckleClaimV1, SuckleOutcomeV1

__version__ = "0.1.0"
__all__ = ["SUCKLE_OUTCOME_CASES_V1", "SuckleOutcomeExperimentV1", "suckle_behavior_signature_v1",
           "run_suckle_outcome_v1", "render_suckle_outcome_v1", "run_suckle_outcome_menu_v1", "__version__"]
SUCKLE_OUTCOME_CASES_V1 = (*SUCKLE_LATCH_CASES_V1, "comparison_off", "nonsealable_comparison_off")
_EXTRA_LIMITS = {"suckle_pending_claims": 8, "suckle_outcome_history": 32, "suckle_recent_acquisitions": 16,
                 "suckle_awaiting_installation": 1, "suckle_execution_reference": 1, "suckle_staged_intervals": 16}
_INTERRUPTED = frozenset({"blocked_motor", "dropout", "delayed", "support_loss", "body_shift", "prolonged_gap", "cancelled"})
_MATCHED = frozenset({"nominal", "pnm_registration_off", "competing_on", "influence_off", "cadence_1", "cadence_8",
                      "seal_loss_after", "seek_then_latch", "stand_follow"})


def suckle_behavior_signature_v1(result: SuckleExperimentV1) -> str:
    """Hash complete retained H behavior, excluding only I's observer additions.

    This includes source/selection/task/PNM/authorization/handoff/F/schedule data,
    local commands and reports, all physical observer samples, final feedback,
    original nondiagnostic owner counts and durable state. It does not drop failed cycles or
    compare only the final latch. Original H review labels and checks are not
    behavior. The focal diagnostic trace count may increase by I events; it stays
    present in exported bounds evidence but is not a behavioral state variable.
    """
    cycles = []
    for cycle in result.run.cycles:
        data = cycle.as_dict()
        data.pop("suckle_correspondence", None)
        cycles.append(data)
    payload = {"cycles": cycles, "local_steps": [item.as_dict() for item in result.run.local_steps],
               "physical_samples": [item.as_dict() for item in result.run.physical_samples],
               "final_feedback": result.run.final_feedback.as_dict(), "metrics": result.metrics(),
               "peak_counts": {key: value for key, value in result.run.peak_counts if key not in _EXTRA_LIMITS and key != "focal_trace"},
               "durable_before": result.run.durable_before, "durable_after": result.run.durable_after}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SuckleOutcomeExperimentV1:
    """Completed I evidence with a separately executed H behavior control.

    The retained H wrapper supplies its existing latch/selection/physical checks.
    Only its owner-bound check is extended for I, without hiding new counts.
    The control signature is evidence of these experiments, not a guarantee for
    every possible environment or proof that prediction changes behavior.
    """

    case: str
    evidence: SuckleExperimentV1
    comparison_enabled: bool
    control_signature: str

    def claims(self) -> tuple[SuckleClaimV1, ...]:
        """Read original pre-handoff registrations without recreating predictions."""
        return tuple(c.suckle_correspondence.registration for c in self.evidence.run.cycles
                     if c.suckle_correspondence is not None and c.suckle_correspondence.registration is not None)

    def outcomes(self) -> tuple[SuckleOutcomeV1, ...]:
        """Read each newly published terminal result from its original cycle frame."""
        return tuple(item for c in self.evidence.run.cycles if c.suckle_correspondence is not None
                     for item in c.suckle_correspondence.outcomes)

    def _expected_disposition(self) -> bool:
        """Apply named controls without moving the original forecast's criterion.

        Early protection invalidates the planned execution, so blocked/dropout
        cases are interrupted rather than manufactured endpoint failures. A
        nonsealable surface retains exposure and genuinely tests the seal claim.
        """
        statuses = tuple(item.status for item in self.outcomes())
        if not self.comparison_enabled:
            return statuses == ("comparison_disabled",)
        if self.case in _MATCHED:
            return statuses == ("matched",)
        if self.case in _INTERRUPTED:
            return statuses == ("interrupted",)
        if self.case == "nonsealable":
            return statuses == ("mismatch",)
        if self.case == "missing_seal":
            return statuses == ("unknown",)
        if self.case == "narrowed":
            return statuses == ("partly_matched", "matched")
        if self.case == "brief_gap":
            return statuses == ("interrupted", "matched")
        if self.case == "no_capability":
            return bool(statuses) and all(status == "not_applied" for status in statuses)
        return not self.claims() and not statuses

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Check historical identity, actual exposure, timing, bounds and unchanged H."""
        claims, outcomes = self.claims(), self.outcomes()
        selected = tuple(c for c in self.evidence.run.cycles if isinstance(c.calculation.navigation.application, SuckleApplicationV1))
        counts = dict(self.evidence.run.peak_counts)
        limits = {**suckle_owner_limits_v1(), **_EXTRA_LIMITS}
        retained = tuple(("retained_H_" + name, passed) for name, passed in self.evidence.checks() if name != "bounded_live_owners")
        return retained + (
            ("original_registration_before_handoff", len(claims) == len(selected) and all(
                c.suckle_correspondence is not None and c.suckle_correspondence.registration is not None
                and isinstance(c.calculation.navigation.application, SuckleApplicationV1)
                and c.suckle_correspondence.registration.preview is c.calculation.navigation.application.projection
                and c.suckle_correspondence.registration.request is c.calculation.navigation.application.contribution
                for c in selected)),
            ("expected_correspondence_disposition", self._expected_disposition()),
            ("terminal_claim_consumed_once", len({item.claim.preview.pnm.pnm_id for item in outcomes}) == len(outcomes)),
            ("original_event_and_arrival_window", all(item.evidence is None or (
                item.evidence.feedback.event_tick == item.claim.due_tick
                and item.evidence.feedback.available_tick <= item.claim.expires_at_tick
                and item.evidence.feedback.available_tick <= item.evaluated_tick) for item in outcomes)),
            ("veto_is_not_executed_failure", all(item.status != "not_applied" or
                (not item.installed and not item.claim.targets and not item.command_intervals and item.evidence is None) for item in outcomes)),
            ("scored_execution_has_exposure", all(item.status not in {"matched", "mismatch", "partly_matched"} or
                (item.installed and item.command_intervals > 0) for item in outcomes)),
            ("complete_extended_owner_bounds", len(counts) == len(self.evidence.run.peak_counts)
             and all(key in counts for key in _EXTRA_LIMITS)
             and all(key in limits and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= limits[key]
                     for key, value in counts.items())),
            ("unchanged_H_behavior_against_fresh_control", suckle_behavior_signature_v1(self.evidence) == self.control_signature),
            ("no_suckle_attention_learning_or_milk", all(c.suckle_correspondence is not None
             and c.suckle_correspondence.as_dict()["attention_route"] == "deferred_suckle_attention"
             and c.suckle_correspondence.as_dict()["learning_route"] == "unimplemented_no_participation"
             for c in self.evidence.run.cycles) and self.evidence.run.durable_before == self.evidence.run.durable_after),
        )

    @property
    def review_status(self) -> str:
        """Return a computed review result, not a task-success or feeding flag."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export all evidence without H's obsolete no-correspondence scope label."""
        data = self.evidence.as_dict()
        data.update(scope="P16_2C_I_execution_sensitive_suckle_correspondence", case=self.case,
                    suckle_pnm_correspondence="suckle_correspondence_v1", comparison_enabled=self.comparison_enabled,
                    original_claims=[item.as_dict() for item in self.claims()], outcomes=[item.as_dict() for item in self.outcomes()],
                    owner_limits={**suckle_owner_limits_v1(), **_EXTRA_LIMITS}, checks=dict(self.checks()), review_status=self.review_status,
                    control_behavior_sha256=self.control_signature, observed_behavior_sha256=suckle_behavior_signature_v1(self.evidence))
        return data


def run_suckle_outcome_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SuckleOutcomeExperimentV1:
    """Run the common fixed H experiment with I, then its independent H control.

    No physics, success criterion or trajectory is changed. The two additional
    cases disable only correspondence scoring on nominal/nonsealable H fixtures.
    Their results cannot become task input, including the control hash/checks.
    """
    if not isinstance(case, str) or case not in SUCKLE_OUTCOME_CASES_V1:
        raise ValueError("unknown Suckle correspondence case")
    comparison = case not in {"comparison_off", "nonsealable_comparison_off"}
    base = "nominal" if case == "comparison_off" else "nonsealable" if case == "nonsealable_comparison_off" else case
    base_profile = suckle_profile_v1(base)
    profile = replace(base_profile, suckle=replace(base_profile.suckle, outcomes_enabled=True, prediction_comparison_enabled=comparison))
    trial = create_suckle_trial_v1(base, trace_capacity=trace_capacity, outcomes_enabled=True, compare_predictions=comparison)
    evidence = SuckleExperimentV1(profile, collect_seek_nipple_evidence_v1(trial, profile.run))
    return SuckleOutcomeExperimentV1(case, evidence, comparison, suckle_behavior_signature_v1(run_suckle_v1(base, trace_capacity=trace_capacity)))


def render_suckle_outcome_v1(result: SuckleOutcomeExperimentV1, *, detail: bool = False) -> str:
    """Inspect retained evidence only; detail cannot rerun cognition or movement."""
    if not isinstance(result, SuckleOutcomeExperimentV1) or not isinstance(detail, bool):
        raise TypeError("Suckle outcome rendering needs a completed experiment and Boolean detail")
    statuses: dict[str, int] = {}
    for outcome in result.outcomes():
        statuses[outcome.status] = statuses.get(outcome.status, 0) + 1
    metrics = result.evidence.metrics()
    lines = [f"P16-2C-I / {result.case} / SUCKLE CORRESPONDENCE REVIEW: {result.review_status}",
             f"  Original claims={len(result.claims())}; outcomes={statuses}; closure commands={metrics['closure_commands']}",
             f"  Physical seal tick={metrics['first_physical_seal_tick']}; separate H latch proof tick={metrics['latch_established_tick']}",
             "  Original PNM != local target achieved != physical seal != sensed seal != two-sample latch proof.",
             "  No Suckle Attention/learning route, milk, nourishment, Rest, full feeding or B99 claim."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for item in result.outcomes():
            sample = item.evidence.feedback if item.evidence else None
            lines.append(f"  {item.claim.preview.pnm.pnm_id}: {item.status}; authorization={item.claim.authorization_status}; "
                         f"original endpoint={item.claim.due_tick}; event/available="
                         f"{(sample.event_tick, sample.available_tick) if sample else None}; C2={item.evaluated_tick}; "
                         f"command intervals={item.command_intervals}; installed={item.installed}")
            lines.append(f"    original closure={item.claim.preview.predicted_closure}; relations={dict(item.relations)}; "
                         f"residuals={dict(item.residuals)}; {item.reason}")
        lines.append("  H control behavior SHA-256: " + result.control_signature)
    return "\n".join(lines)


def run_suckle_outcome_menu_v1() -> None:
    """Offer causal controls and read-only retained detail from the feeding menu."""
    groups = {"1": ("nominal", "nonsealable", "missing_seal", "comparison_off", "nonsealable_comparison_off"),
              "2": ("no_capability", "narrowed", "blocked_motor", "cancelled"),
              "3": ("dropout", "delayed", "brief_gap", "support_loss", "seal_loss_after"),
              "4": ("seek_then_latch", "stand_follow", "pnm_registration_off"), "5": SUCKLE_OUTCOME_CASES_V1}
    retained: tuple[SuckleOutcomeExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-I -- ORIGINAL SUCKLE PREDICTION / ACTUAL EXECUTION / LATER EVIDENCE")
        print("  1) Match, mismatch, absent sensing and comparison-off / 2) Veto, narrowing and interruption")
        print("  3) Timing, gaps and later source change / 4) Continuous and registration controls")
        print("  5) All cases / 6) Inspect retained detail (no new movement) / [Enter] Return")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            print("\n\n".join(render_suckle_outcome_v1(item, detail=True) for item in retained) if retained else "No retained results to inspect.")
        elif choice in groups:
            retained = tuple(run_suckle_outcome_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_outcome_v1(item) for item in retained))
        else:
            print("Unknown choice; no movement was performed.")
