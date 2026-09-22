#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first original SeekNipple prediction correspondence on the common driver.

D enables only execution-sensitive endpoint comparison. All tasks, physical
models, motor commands, lower controllers and C reach criteria remain intact.
Fixed-time external reach forcing isolates prediction scoring from successful
local target completion. The comparison-off control retains the same forcing,
exposure, source and task. These tests do not give the comparator executive or
learning authority, and do not establish latch, suckling, milk, Rest or B99.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cca8_cli
from cca8_support_world import OralWorldPerturbationV1
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_nipple import SeekNippleApplicationV1
from nca8_seek_nipple_demo import (
    SeekNippleExperimentProfileV1, SeekNippleExperimentV1, collect_seek_nipple_evidence_v1,
    seek_nipple_owner_limits_v1, seek_nipple_profile_v1,
)
from nca8_seek_outcomes import SeekNippleClaimV1, SeekNippleOutcomeV1

__version__ = "0.1.0"
__all__ = ["SEEK_NIPPLE_OUTCOME_CASES_V1", "SeekNippleOutcomeExperimentV1", "seek_nipple_outcome_profile_v1",
           "create_seek_nipple_outcome_trial_v1", "run_seek_nipple_outcome_v1", "render_seek_nipple_outcome_v1",
           "run_seek_nipple_outcome_menu_v1", "__version__"]

SEEK_NIPPLE_OUTCOME_CASES_V1 = (
    "nominal", "no_surface", "seek_off", "no_capability", "blocked_motor", "heading_90", "out_of_reach", "intermediate_target",
    "brief_gap", "prolonged_gap", "dropout", "delayed", "support_loss", "body_shift", "body_turn", "early_contact",
    "cancelled", "cadence_1", "cadence_8", "stand_follow", "stand_follow_no_surface", "stand_follow_seek_off",
    "endpoint_drift", "drift_comparison_off", "after_endpoint_drift", "narrowing_control", "narrowed", "comparison_off", "pnm_registration_off",
)
_LIMITS = {**seek_nipple_owner_limits_v1(), "seeking_pending_claims": 8, "seeking_outcome_history": 32,
           "seeking_recent_acquisitions": 16, "seeking_awaiting_installation": 1,
           "seeking_execution_reference": 1, "seeking_staged_intervals": 16}


def seek_nipple_outcome_profile_v1(case: str = "nominal") -> SeekNippleExperimentProfileV1:
    """Freeze one declared world/control profile before reading any outcome.

    The original C cases keep their physical parameters. Endpoint-drift adds
    0.01 metres of external forcing over tick [7,8); after-endpoint drift adds
    the same over [8,9). Local achievement has already stopped pursuit, so an
    original event-8 claim can disagree with later state. These are fixed-time
    experiments, not outcome-triggered disturbances or biological constants.
    """
    if not isinstance(case, str) or case not in SEEK_NIPPLE_OUTCOME_CASES_V1:
        raise ValueError("unknown seeking correspondence review case")
    extras = {"endpoint_drift", "drift_comparison_off", "after_endpoint_drift", "narrowing_control", "narrowed", "comparison_off"}
    base = seek_nipple_profile_v1("nominal" if case in extras else case)
    oral = base.oral
    if case in {"endpoint_drift", "drift_comparison_off", "after_endpoint_drift"}:
        start = 8 if case == "after_endpoint_drift" else 7
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(start, start + 1, 0.2),))
    return replace(base, case=case, oral=oral, cadence=8 if case in {"narrowed", "narrowing_control"} else base.cadence,
                   seeking=replace(base.seeking, outcomes_enabled=True,
                                   prediction_comparison_enabled=case not in {"comparison_off", "drift_comparison_off"}))


def create_seek_nipple_outcome_trial_v1(case: str = "nominal", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct a fresh opt-in correspondence experiment; choose no task or target.

    Compared with narrowing_control, the narrowed fixture changes only BodyMap
    maximum contribution to 0.04 metres. Both use cadence eight and identical
    initial geometry; the task's original 0.10-metre prediction stays unchanged.
    It is a fixed capability fixture, not retuned physics or a weaker success
    criterion. Construction reuses the existing integrated core/local driver.
    """
    profile = seek_nipple_outcome_profile_v1(case)
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
class SeekNippleOutcomeExperimentV1:
    """Complete shared-driver evidence, with D-specific correspondence qualification.

    The underlying collector holds every focal decision, lower update and private
    physical sample. D does not silently strip fields, replace adverse trials,
    or use C's case-specific success assumptions for its different controls.
    """

    evidence: SeekNippleExperimentV1

    def claims(self) -> tuple[SeekNippleClaimV1, ...]:
        """Read each original E registration, including known pre-execution vetoes."""
        return tuple(c.seeking_correspondence.registration for c in self.evidence.cycles
                     if c.seeking_correspondence is not None and c.seeking_correspondence.registration is not None)

    def outcomes(self) -> tuple[SeekNippleOutcomeV1, ...]:
        """Read terminal reports where actually produced, not reconstructed from history."""
        return tuple(item for c in self.evidence.cycles if c.seeking_correspondence is not None for item in c.seeking_correspondence.outcomes)

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check actual ownership, including missing/duplicate diagnostic counts."""
        counts = self.evidence.peak_counts
        required = {"wnm", "current_pnm", "seeking_pending_claims", "seeking_outcome_history", "seeking_staged_intervals"}
        failures = tuple(f"missing:{key}" for key in sorted(required - dict(counts).keys()))
        if len(dict(counts)) != len(counts):
            failures += ("duplicate_owner_count",)
        return failures + tuple(key for key, value in counts if key not in _LIMITS or isinstance(value, bool)
                                or not isinstance(value, int) or not 0 <= value <= _LIMITS[key])

    def _expected_disposition(self) -> bool:
        """Check the predeclared meaningful contrast, not universal task success."""
        case, outcomes = self.evidence.profile.case, self.outcomes()
        if case in {"seek_off", "stand_follow_seek_off"}:
            return not outcomes and not self.claims()
        if not outcomes:
            return False
        first = outcomes[0]
        if case in {"comparison_off", "drift_comparison_off"}:
            return first.status == "comparison_disabled" and not first.relations and not first.residuals
        if case == "endpoint_drift":
            return first.status == "mismatch" and dict(first.relations).get("mouth_position") == "mismatch"
        if case == "narrowed":
            return first.status == "partly_matched" and first.claim.unevaluable_relations == ("mouth_position", "separation")
        if case in {"no_capability", "heading_90", "out_of_reach"}:
            return all(item.status == "not_applied" and item.command_intervals == 0 for item in outcomes)
        if case == "cadence_1":
            return (first.status == "matched" and any(item.status == "interrupted" for item in outcomes)
                    and self.evidence.metrics()["final_task_status"] == "budget_exhausted")
        if case in {"brief_gap", "prolonged_gap", "dropout", "delayed", "support_loss", "body_shift", "body_turn", "early_contact", "cancelled"}:
            return first.status in {"interrupted", "cancelled", "expired_unresolved"}
        if case == "blocked_motor":
            return first.status in {"mismatch", "interrupted"} and first.command_intervals > 0
        return first.status == "matched"

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Verify actual claims, exposure, timings, isolation and declared control effects."""
        raw, claims, outcomes = self.evidence, self.claims(), self.outcomes()
        expected_ticks = tuple(range(0, raw.profile.horizon_ticks + 1, raw.profile.cadence))
        selected = tuple(c for c in raw.cycles if isinstance(c.calculation.navigation.application, SeekNippleApplicationV1))
        claims_by_id = {c.preview.pnm.pnm_id: c for c in claims}
        exposure_valid = all(item.command_intervals == sum(
            step.command is not None and step.command.oral_drive not in (None, 0.0)
            and step.tick < min(item.claim.due_tick, item.evaluated_tick)
            and any(report.committed_target is item.claim.targets[0] for report in step.reports)
            for step in raw.local_steps) for item in outcomes if item.claim.targets)
        return (
            ("complete_fixed_horizon", tuple(s.tick for s in raw.local_steps) == tuple(range(raw.profile.horizon_ticks))
             and tuple(c.calculation.cutoff_tick for c in raw.cycles) == expected_ticks
             and tuple(p.tick for p in raw.physical_samples) == tuple(range(raw.profile.horizon_ticks + 1))),
            ("expected_correspondence_or_bounded_failure", self._expected_disposition()),
            ("one_source_linked_wnm", all(c.calculation.navigation.wnm is not None
             and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in selected)),
            ("one_original_claim_per_selected_application", len(claims) == len(selected) == len(claims_by_id)),
            ("claims_precede_handoff", all(c.seeking_correspondence is not None and c.seeking_correspondence.registration is not None
             and isinstance(c.calculation.navigation.application, SeekNippleApplicationV1)
             and c.seeking_correspondence.registration.preview is c.calculation.navigation.application.projection for c in selected)),
            ("outcomes_reference_exact_registered_claims", all(claims_by_id.get(item.claim.preview.pnm.pnm_id) is item.claim for item in outcomes)),
            ("consume_each_claim_once", len({item.claim.preview.pnm.pnm_id for item in outcomes}) == len(outcomes)),
            ("original_event_and_availability", all(item.evidence is None or (
             item.evidence.feedback.event_tick == item.claim.due_tick
             and item.evidence.feedback.available_tick <= min(item.claim.expires_at_tick, item.evaluated_tick)) for item in outcomes)),
            ("actual_oral_exposure_only", exposure_valid),
            ("unknown_and_nonapplication_not_success", all(item.status not in {"matched", "partly_matched", "mismatch"}
             or item.evidence is not None and item.command_intervals > 0 for item in outcomes)),
            ("finite_owner_storage", not self.bound_violations),
            ("no_durable_learning", bool(raw.durable_before) and raw.durable_before == raw.durable_after),
            ("one_consumption_per_focal_opportunity", raw.handoff_consumptions == len(expected_ticks)),
            ("actual_installations_only", raw.installations == sum(bool(c.reservations) for c in raw.cycles)),
            ("no_seeking_attention_or_learning_authority", all(c.seeking_correspondence is not None
             and c.seeking_correspondence.as_dict()["attention_route"] == "deferred_seeking_attention"
             and c.seeking_correspondence.as_dict()["durable_updates"] == 0 for c in raw.cycles)),
        )

    @property
    def review_status(self) -> str:
        """Propagate any missing, tampered or failed evidence rather than force PASS."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export every collected causal record, plus this review's explicit results."""
        raw = self.evidence
        return {"scope": "P16_2C_D_seek_nipple_correspondence", "profile": raw.profile.as_dict(), "metrics": raw.metrics(),
                "oral_capability_maximum_step_metres": 0.04 if raw.profile.case == "narrowed" else oral_body_capability_v1().maximum_step,
                "cycles": [c.as_dict() for c in raw.cycles], "local_steps": [s.as_dict() for s in raw.local_steps],
                "observer_physical_samples": [p.as_dict() for p in raw.physical_samples], "final_feedback": raw.final_feedback.as_dict(),
                "peak_owner_counts": dict(raw.peak_counts), "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
                "durable_before": raw.durable_before, "durable_after": raw.durable_after,
                "registered_pnm_cycles": list(raw.registered_pnm_cycles), "claims": [c.as_dict() for c in self.claims()],
                "outcomes": [o.as_dict() for o in self.outcomes()], "checks": dict(self.checks()), "review_status": self.review_status,
                "feeding_learning": "unimplemented_no_participation", "seeking_attention": "deferred", "B99": "open"}


def run_seek_nipple_outcome_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SeekNippleOutcomeExperimentV1:
    """Use the same fixed-schedule collector as C; no second cognitive or motor loop."""
    profile = seek_nipple_outcome_profile_v1(case)
    trial = create_seek_nipple_outcome_trial_v1(case, trace_capacity=trace_capacity)
    return SeekNippleOutcomeExperimentV1(collect_seek_nipple_evidence_v1(trial, profile))


def render_seek_nipple_outcome_v1(result: SeekNippleOutcomeExperimentV1, *, detail: bool = False) -> str:
    """Render retained results only; detail never reruns a physical or cognitive step."""
    if not isinstance(result, SeekNippleOutcomeExperimentV1) or not isinstance(detail, bool):
        raise TypeError("correspondence rendering requires a completed result and Boolean detail switch")
    raw = result.evidence
    metrics = raw.metrics()
    statuses: dict[str, int] = {}
    for outcome in result.outcomes():
        statuses[outcome.status] = statuses.get(outcome.status, 0) + 1
    lines = [f"P16-2C-D / {raw.profile.case} / SEEKING CORRESPONDENCE REVIEW: {result.review_status}",
             f"  physical ticks={len(raw.local_steps)}; focal opportunities={len(raw.cycles)}; cadence={raw.profile.cadence}",
             f"  original claims={len(result.claims())}; terminal results={statuses}; oral commands={metrics['oral_commands']}",
             f"  reached detail={metrics['first_reached_detail_tick']}; physical touch={metrics['first_physical_touch_tick']}",
             "  Prediction match is not reach, touch, latch, milk or causal credit. Attention/learning routes remain deferred."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for item in result.outcomes():
            feedback = item.evidence.feedback if item.evidence is not None else None
            lines.append(f"  {item.claim.preview.pnm.pnm_id}: {item.status}; original endpoint={item.claim.due_tick}; "
                         f"sensed event/available={str(feedback.event_tick) + '/' + str(feedback.available_tick) if feedback else 'none'}; "
                         f"C2 cutoff={item.evaluated_tick}; oral exposure={item.command_intervals}")
            lines.append(f"    relations={dict(item.relations)}; residual metres={dict(item.residuals)}; {item.reason}")
        lines.append("  Fixed reference predictions remain unchanged after current source, target or task changes.")
    return "\n".join(lines)


def run_seek_nipple_outcome_menu_v1() -> None:
    """Offer causal contrasts and retained inspection using the common experiment API."""
    groups = {"1": ("nominal", "no_surface", "comparison_off"),
              "2": ("endpoint_drift", "drift_comparison_off", "after_endpoint_drift"),
              "3": ("narrowing_control", "narrowed", "no_capability", "heading_90", "blocked_motor"),
              "4": ("brief_gap", "prolonged_gap", "dropout", "delayed", "support_loss", "early_contact", "cancelled"),
              "5": ("stand_follow", "stand_follow_no_surface", "stand_follow_seek_off"), "6": SEEK_NIPPLE_OUTCOME_CASES_V1}
    retained: tuple[SeekNippleOutcomeExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-D -- ORIGINAL SEEKING PREDICTION / ACTUAL EXECUTION")
        print("  1) Match versus touch / 2) Endpoint drift and comparison-off")
        print("  3) Narrowing, veto and blocked motor / 4) Gaps, interruption and cancellation")
        print("  5) Continuous stand-follow-seek / 6) All cases / 7) Inspect retained detail (no new movement)")
        print("  [Enter] Return to feeding review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "7":
            print("\n\n".join(render_seek_nipple_outcome_v1(item, detail=True) for item in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_seek_nipple_outcome_v1(case) for case in groups[choice])
            print("\n\n".join(render_seek_nipple_outcome_v1(item) for item in retained))
        else:
            print("Choose 1-7 or press Enter to return.")
