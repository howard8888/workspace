#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect K's original Suckle participation at the existing Phase-F checkpoint.

The shared H trial factory and C collector remain the only execution path. Each
review also executes a fresh hook-disabled control under identical fixed source,
body, timing and J conditions. Only K's named reporting fields and bounded counts
and the existing focal-trace count are excluded from behavior comparison. The
trace count remains bounded and separately checked; K emits one extra F diagnostic
per configured cycle. I/J records, sources, permissions and motor evidence remain.

These finite physical reviews expose participation before execution, original
recipient routing, actual interpretation dependency, independent eligibility and
zero durable updates. Simultaneous-question and late-J-interpretation fixtures
remain the separately labelled Stage C contract tests. No such fixture is silently
introduced as a physical episode. Review records never become cognitive input.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json

import cca8_cli
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleApplicationV1
from nca8_suckle_demo import (
    SuckleExperimentProfileV1, SuckleExperimentV1, create_suckle_trial_v1, suckle_owner_limits_v1, suckle_profile_v1,
)
from nca8_suckle_learning import SuckleLearningPhaseFReportV1, SuckleTeachingDispositionV1

__version__ = "0.1.0"
__all__ = ["SUCKLE_LEARNING_CASES_V1", "SuckleLearningExperimentV1", "suckle_learning_profile_v1",
           "create_suckle_learning_trial_v1", "suckle_learning_behavior_signature_v1", "run_suckle_learning_v1",
           "render_suckle_learning_v1", "run_suckle_learning_menu_v1", "__version__"]

SUCKLE_LEARNING_CASES_V1 = (
    "nominal_on", "nominal_off", "competing_on", "competing_off", "attention_off", "comparison_off", "nonfocal",
    "no_capability", "missing_seal", "blocked_motor", "cancelled", "support_loss", "narrowed", "dropout", "delayed",
    "cadence_1", "cadence_8", "seek_then_latch", "stand_follow", "stand_follow_off",
)
_OFF_CASES = frozenset({"nominal_off", "competing_off", "stand_follow_off"})
_ALIASES = {"nominal_on": "nominal", "nominal_off": "nominal", "competing_on": "nonsealable",
            "competing_off": "nonsealable", "attention_off": "nonsealable", "comparison_off": "nonsealable",
            "nonfocal": "nominal", "stand_follow_off": "stand_follow"}
_K_COUNTS = frozenset({"suckle_learning_participants", "suckle_learning_dispositions"})
_LIMITS = {**suckle_owner_limits_v1(), "suckle_pending_claims": 8, "suckle_outcome_history": 32,
           "suckle_recent_acquisitions": 16, "suckle_awaiting_installation": 1, "suckle_execution_reference": 1,
           "suckle_staged_intervals": 16, "suckle_attention_pending_requests": 8, "suckle_attention_dependency": 1,
           "suckle_attention_dispositions": 32, "suckle_learning_participants": 8, "suckle_learning_dispositions": 32}


def suckle_learning_profile_v1(case: str = "nominal_on") -> SuckleExperimentProfileV1:
    """Declare unchanged H physics and the K/J switches before any results exist.

    The on/off pairs vary K only, not J. attention_off instead leaves K enabled
    and removes J; comparison_off leaves the original I records unscored. nonfocal
    offers the ordinary visual competitor at the matched endpoint's cutoff12.
    Cadence controls change only focal opportunities, not physical time or leases.
    """
    if not isinstance(case, str) or case not in SUCKLE_LEARNING_CASES_V1:
        raise ValueError("unknown Suckle participation review case")
    base = suckle_profile_v1(_ALIASES.get(case, case))
    competitors = ((8, 12) if case in {"competing_on", "competing_off", "attention_off", "comparison_off"}
                   else (12,) if case == "nonfocal" else base.run.competitor_cutoffs)
    return replace(base, run=replace(base.run, case=case, competitor_cutoffs=competitors),
                   suckle=replace(base.suckle, outcomes_enabled=True, prediction_comparison_enabled=case != "comparison_off",
                                  outcome_attention_enabled=case != "attention_off", learning_hook_enabled=case not in _OFF_CASES))


def create_suckle_learning_trial_v1(
    case: str = "nominal_on", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> IntegratedRightingTrialV1:
    """Create the existing hierarchy with an explicit K opt-in; do not run a cycle."""
    profile = suckle_learning_profile_v1(case)
    return create_suckle_trial_v1(
        _ALIASES.get(case, case), trace_capacity=trace_capacity, outcomes_enabled=True,
        compare_predictions=profile.suckle.prediction_comparison_enabled,
        outcome_attention_enabled=profile.suckle.outcome_attention_enabled,
        learning_hook_enabled=profile.suckle.learning_hook_enabled, diagnostic_capacity=diagnostic_capacity,
    )


def _behavior_cycle(cycle: IntegratedRightingCycleV1) -> dict[str, object]:
    """Remove only named K reports, never I/J evidence, permissions or commitments."""
    data = cycle.as_dict()
    data.pop("suckle_learning_reconciliation", None)
    if "suckle_learning_status" in data:
        data["suckle_learning_status"] = "unimplemented_no_participation"
    for name in ("suckle_correspondence", "suckle_attention"):
        frame = data.get(name)
        if isinstance(frame, dict):
            frame["learning_route"] = "unimplemented_no_participation"
    return data


def suckle_learning_behavior_signature_v1(result: SuckleExperimentV1) -> str:
    """Hash behavior except K reports/counts and the explicitly diagnostic trace count.

    The signature is compared within this execution environment, not against a
    cross-platform golden hash. I-v02's independent portable H fixture is retained
    unchanged. Unknown new counts are not silently discarded by a prefix filter.
    """
    raw = result.run
    data = {"cycles": [_behavior_cycle(c) for c in raw.cycles],
            "local_steps": [s.as_dict() for s in raw.local_steps],
            "physical_samples": [p.as_dict() for p in raw.physical_samples], "final_feedback": raw.final_feedback.as_dict(),
            "metrics": result.metrics(), "registered_pnm_cycles": raw.registered_pnm_cycles,
            "peak_counts": {key: value for key, value in raw.peak_counts if key not in _K_COUNTS and key != "focal_trace"},
            "durable_before": raw.durable_before, "durable_after": raw.durable_after}
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def _evidence_dict(result: SuckleExperimentV1) -> dict[str, object]:
    """Export full records without borrowing H's case-specific verdict for K."""
    raw = result.run
    return {"profile": result.profile.as_dict(), "cycles": [c.as_dict() for c in raw.cycles],
            "local_steps": [s.as_dict() for s in raw.local_steps],
            "observer_physical_samples": [p.as_dict() for p in raw.physical_samples],
            "final_feedback": raw.final_feedback.as_dict(), "peak_owner_counts": dict(raw.peak_counts),
            "durable_before": raw.durable_before, "durable_after": raw.durable_after, "metrics": result.metrics(),
            "registered_pnm_cycles": list(raw.registered_pnm_cycles)}


def _known_relations(disposition: SuckleTeachingDispositionV1) -> bool:
    """Verify admitted relation membership, not merely an accepted label."""
    outcome = disposition.outcome
    return outcome is not None and bool(disposition.accepted_relations) and all(
        row in outcome.relations and row[0] in outcome.claim.compatible_relations and row[1] in {"matched", "mismatch"}
        for row in disposition.accepted_relations)


@dataclass(frozen=True, slots=True)
class SuckleLearningExperimentV1:
    """Completed K evidence and a separately executed, same-conditions K-off control.

    Reports come from real F callbacks. The retained history is diagnostic only;
    checks use the full collected reports even when that history was truncated.
    Source and task identities are original object references within each run.
    """

    evidence: SuckleExperimentV1
    control: SuckleExperimentV1
    retained_dispositions: tuple[SuckleTeachingDispositionV1, ...]

    def reports(self) -> tuple[SuckleLearningPhaseFReportV1, ...]:
        """Read actual F results, not reconstructed or re-executed owner work."""
        return tuple(c.suckle_learning_report for c in self.evidence.run.cycles if c.suckle_learning_report is not None)

    def dispositions(self) -> tuple[SuckleTeachingDispositionV1, ...]:
        """Retain every recorded F disposition independently of diagnostic eviction."""
        return tuple(d for report in self.reports() for d in report.dispositions)

    def metrics(self) -> dict[str, object]:
        """Measure evidence routing and expiry, not an acquired performance gain."""
        reports, dispositions = self.reports(), self.dispositions()
        accepted = tuple(d for d in dispositions if d.status == "accepted_no_update")
        return {**self.evidence.metrics(), "hook_enabled": self.evidence.profile.suckle.learning_hook_enabled,
                "F_calls": len(reports), "participations": sum(r.new_participation is not None for r in reports),
                "disposition_counts": dict(Counter(d.status for d in dispositions)),
                "accepted_ticks": [d.cutoff_tick for d in accepted],
                "accepted_original_statuses": [d.outcome.status for d in accepted if d.outcome is not None],
                "righting_F_calls": sum(c.learning_report is not None for c in self.evidence.run.cycles),
                "maternal_F_calls": sum(c.maternal_learning_report is not None for c in self.evidence.run.cycles),
                "seeking_F_calls": sum(c.seeking_learning_report is not None for c in self.evidence.run.cycles),
                "durable_learning_updates": 0}

    def _expected_effect(self) -> bool:
        """Require each declared control's real admission/rejection, not task success."""
        case, dispositions = self.evidence.profile.run.case, self.dispositions()
        statuses = {d.status for d in dispositions}
        accepted = tuple(d for d in dispositions if d.status == "accepted_no_update")
        if case in _OFF_CASES:
            return not self.reports() and not dispositions
        if case == "attention_off":
            return {"pending_interpretation", "eligibility_expired"} <= statuses and not accepted
        if case == "comparison_off":
            return "comparison_disabled_no_teaching" in statuses and not accepted
        if case == "no_capability":
            return "not_applied" in statuses and not accepted
        if case == "missing_seal":
            return "rejected_unknown" in statuses and not accepted
        if case in {"blocked_motor", "cancelled", "support_loss", "dropout", "delayed"}:
            return "rejected_interrupted" in statuses and not accepted
        if case == "cadence_1":
            return {"eligibility_expired", "rejected_expired_eligibility"} <= statuses and not accepted
        if case == "competing_on":
            return any(d.outcome is not None and d.outcome.status == "mismatch" and d.interpretation is not None
                       and d.interpretation.status == "still_relevant" for d in accepted)
        if case == "narrowed":
            return any(d.accepted_relations == (("mouth_position", "matched"), ("detail_anchor", "matched")) for d in accepted)
        if case == "nonfocal":
            return any(c.calculation.navigation.wnm is not None
                       and c.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "visual_scene"
                       and c.suckle_learning_report is not None
                       and any(d.status == "accepted_no_update" for d in c.suckle_learning_report.dispositions)
                       for c in self.evidence.run.cycles)
        return case in {"nominal_on", "cadence_8", "seek_then_latch", "stand_follow"} and bool(accepted)

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Check original identity, bounded timing, unchanged behavior and real F work.

        None of these observers calls an outcome/learning owner or calculates new
        J relevance. An invalid control returns FAIL rather than rewriting physics,
        extending eligibility or claiming the missing interpretation happened.
        """
        raw, profile = self.evidence.run, self.evidence.profile
        reports, dispositions = self.reports(), self.dispositions()
        participants = tuple(r.new_participation for r in reports if r.new_participation is not None)
        original = {p.pnm_id: p for p in participants}
        accepted = tuple(d for d in dispositions if d.status == "accepted_no_update")
        claims = tuple(c.suckle_correspondence.registration for c in raw.cycles if c.suckle_correspondence is not None
                       and c.suckle_correspondence.registration is not None
                       and isinstance(c.calculation.navigation.application, SuckleApplicationV1))
        outcomes = tuple(o for c in raw.cycles if c.suckle_correspondence is not None for o in c.suckle_correspondence.outcomes)
        interpretations = tuple(c.suckle_attention.allocation.interpretation for c in raw.cycles
                                if c.suckle_attention is not None and c.suckle_attention.allocation.kind == "interpretation")
        counts = dict(raw.peak_counts)
        required = {"wnm", "current_pnm", "suckle_pending_claims", "feeding_detail_current_configurations"}
        if profile.suckle.learning_hook_enabled:
            required |= _K_COUNTS
        ticks = tuple(range(0, profile.run.horizon_ticks + 1, profile.run.cadence))
        return (
            ("declared_profile", profile == suckle_learning_profile_v1(profile.run.case) and raw.profile == profile.run),
            ("control_changes_K_only", self.control.profile == replace(profile, suckle=replace(profile.suckle, learning_hook_enabled=False))
             and self.control.run.profile == profile.run and all(c.suckle_learning_report is None for c in self.control.run.cycles)),
            ("identical_complete_behavior", suckle_learning_behavior_signature_v1(self.evidence)
             == suckle_learning_behavior_signature_v1(self.control)),
            ("declared_evidence_effect", self._expected_effect()),
            ("fixed_schedule", tuple(c.calculation.cutoff_tick for c in raw.cycles) == ticks
             and tuple(s.tick for s in raw.local_steps) == tuple(range(profile.run.horizon_ticks))
             and tuple(p.tick for p in raw.physical_samples) == tuple(range(profile.run.horizon_ticks + 1))),
            ("actual_F_each_configured_cycle", len(reports) == (len(ticks) if profile.suckle.learning_hook_enabled else 0)
             and all(c.suckle_learning_report is None or (c.suckle_learning_report.cycle_id == c.commitment.cycle_id
                     and c.suckle_learning_report.cutoff_tick == c.calculation.cutoff_tick) for c in raw.cycles)),
            ("original_selected_claim", all(any(p.claim is claim for claim in claims) for p in participants)),
            ("participation_is_not_execution", all(p.outcome is None and p.request is None
             and p.as_dict()["registration_scope"] == "selected_authorized_not_execution" for p in participants)),
            ("original_Suckle_recipient", all(p.recipient_id == "feeding_detail_association:feeding_detail:suckle_consequence"
             and p.claim.preview.basis.source_map_ref.map_id == "feeding_detail" for p in participants)),
            ("published_evidence_only", all(d.outcome is None or any(d.outcome is o for o in outcomes) for d in dispositions)),
            ("one_acceptance_per_claim", len({d.pnm_id for d in accepted}) == len(accepted)),
            ("independent_eligibility", all(p.expires_before_cycle == p.created_cycle + 4 for p in participants)
             and all(d.pnm_id in original and original[d.pnm_id].created_cycle < d.cycle_id
                     < original[d.pnm_id].expires_before_cycle for d in accepted)),
            ("authorized_executed_evidence", all(d.outcome is not None and d.outcome.claim.targets
             and d.outcome.command_intervals > 0 and d.outcome.evidence is not None
             and d.outcome.evidence.feedback.available_tick <= d.cutoff_tick for d in accepted)),
            ("compatible_known_relations_only", all(_known_relations(d) for d in accepted)),
            ("actual_J_interpretation_only", all(d.interpretation is None or any(d.interpretation is i for i in interpretations)
             for d in dispositions)),
            ("one_existing_focal_allocation", all(sum(a is not None and a.kind == "interpretation" for a in (
                c.calculation.outcome_allocation, c.calculation.maternal_outcome_allocation,
                c.calculation.seeking_outcome_allocation, c.calculation.suckle_outcome_allocation))
                + int(c.calculation.navigation.application is not None) <= 1 for c in raw.cycles)),
            ("diagnostic_trace_growth_only", 0 <= counts.get("focal_trace", -1)
             - dict(self.control.run.peak_counts).get("focal_trace", -1) <= len(reports)),
            ("complete_owner_bounds", required <= counts.keys() and len(counts) == len(raw.peak_counts)
             and all(k in _LIMITS and isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= _LIMITS[k] for k, v in counts.items())),
            ("one_handoff_per_opportunity", raw.handoff_consumptions == len(ticks)),
            ("unchanged_durable_sources", bool(raw.durable_before) and raw.durable_before == raw.durable_after),
            ("no_durable_update_or_future_outcome", all(r.as_dict()["durable_learning_updates"] == 0
             and r.as_dict()["ledger_rows_executed"] == 0 and not r.as_dict()["new_action_outcome_available"] for r in reports)),
        )

    @property
    def review_status(self) -> str:
        """Report FAIL on any inconsistent or incomplete observed evidence."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export both complete runs and original dispositions without rerunning them."""
        return {"scope": "P16_2C_K_suckle_participation", "evidence": _evidence_dict(self.evidence),
                "control_evidence": _evidence_dict(self.control), "metrics": self.metrics(), "owner_limits": dict(_LIMITS),
                "retained_dispositions": [d.as_dict() for d in self.retained_dispositions],
                "observed_behavior_sha256": suckle_learning_behavior_signature_v1(self.evidence),
                "control_behavior_sha256": suckle_learning_behavior_signature_v1(self.control),
                "checks": dict(self.checks()), "review_status": self.review_status, "maturity": "eligibility_only",
                "durable_learning_updates": 0, "B99": "open",
                "late_J_and_simultaneous_questions": "separate_Stage_C_contract_tests_not_claimed_as_live_scenarios"}


def run_suckle_learning_v1(
    case: str = "nominal_on", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> SuckleLearningExperimentV1:
    """Use the existing collector twice: candidate and a fresh fixed K-off control.

    Controls are separate environment runs, explicitly reported, not hidden resets
    within one organism. Only the declared physical schedule drives either run.
    """
    profile = suckle_learning_profile_v1(case)
    trial = create_suckle_learning_trial_v1(case, trace_capacity=trace_capacity, diagnostic_capacity=diagnostic_capacity)
    raw = collect_seek_nipple_evidence_v1(trial, profile.run)
    control_profile = replace(profile, suckle=replace(profile.suckle, learning_hook_enabled=False))
    control = create_suckle_trial_v1(
        _ALIASES.get(case, case), trace_capacity=trace_capacity, outcomes_enabled=True,
        compare_predictions=profile.suckle.prediction_comparison_enabled,
        outcome_attention_enabled=profile.suckle.outcome_attention_enabled, diagnostic_capacity=diagnostic_capacity,
    )
    control_raw = collect_seek_nipple_evidence_v1(control, profile.run)
    hook = trial.core.feeding_detail.suckle_learning_hook if trial.core.feeding_detail is not None else None
    return SuckleLearningExperimentV1(SuckleExperimentV1(profile, raw), SuckleExperimentV1(control_profile, control_raw),
                                      hook.history() if hook is not None else ())


def render_suckle_learning_v1(result: SuckleLearningExperimentV1, *, detail: bool = False) -> str:
    """Display original participation and actual F outcomes; never call a live owner."""
    if not isinstance(result, SuckleLearningExperimentV1) or not isinstance(detail, bool):
        raise TypeError("Suckle participation rendering requires a completed result and Boolean detail")
    metrics = result.metrics()
    lines = [f"P16-2C-K / {result.evidence.profile.run.case} / SUCKLE PARTICIPATION REVIEW: {result.review_status}",
             f"  K={metrics['hook_enabled']}; F calls={metrics['F_calls']}; original participants={metrics['participations']}",
             f"  Dispositions={metrics['disposition_counts']}; accepted ticks={metrics['accepted_ticks']}",
             "  Participation is not execution; the original Suckle participant remains the recipient.",
             "  F consumes an already performed J result; it neither interprets nor consumes a pending question.",
             "  Eight participants; expiry before creation cycle + 4; diagnostic history <= 32.",
             "  Each review includes a separate identical-conditions K-off control; no physical or task behavior change.",
             "  No IP reapplication, remedy, motor grant, task restart or durable learning. No milk/nourishment/Rest/B99.",
             "  Late J / simultaneous-question expiry remains separately tested by the Stage C contract fixtures."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for report in result.reports():
            participant = report.new_participation
            if participant is not None:
                lines.append(f"  F cycle={report.cycle_id} tick={report.cutoff_tick}: participant={participant.pnm_id}; "
                             f"recipient={participant.recipient_id}; expires_before_cycle={participant.expires_before_cycle}; "
                             "selected/authorized, not execution")
            for item in report.dispositions:
                outcome, interpretation = item.outcome, item.interpretation
                lines.append(f"  F cycle={item.cycle_id} tick={item.cutoff_tick}: {item.status}; original={item.pnm_id}; "
                             f"outcome={outcome.status if outcome is not None else '-'}; "
                             f"J={interpretation.status if interpretation is not None else '-'}; updates=0")
    return "\n".join(lines)


def run_suckle_learning_menu_v1() -> None:
    """Offer the shared K cases and retained read-only detail under feeding option27."""
    groups = {"1": ("nominal_on", "nominal_off", "competing_on", "competing_off"),
              "2": ("attention_off", "comparison_off", "nonfocal", "cadence_1", "cadence_8"),
              "3": ("no_capability", "missing_seal", "blocked_motor", "cancelled", "support_loss", "narrowed", "dropout", "delayed"),
              "4": ("seek_then_latch", "stand_follow", "stand_follow_off"), "5": SUCKLE_LEARNING_CASES_V1}
    retained: tuple[SuckleLearningExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-K -- ORIGINAL SUCKLE PARTICIPATION / PHASE F / NO DURABLE LEARNING")
        print("  1) Hook on/off pairs / 2) Interpretation, original recipient and independent expiry")
        print("  3) Nonapplication, uncertainty, narrowing and interruption / 4) Continuous earlier tasks")
        print("  5) All cases / 6) Inspect retained detail (no new execution) / [Enter] Return")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            print("\n\n".join(render_suckle_learning_v1(item, detail=True) for item in retained) if retained else "No retained results.")
        elif choice in groups:
            retained = tuple(run_suckle_learning_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_learning_v1(item) for item in retained))
        else:
            print("Unknown choice; use 1-6 or press Enter to return.")
