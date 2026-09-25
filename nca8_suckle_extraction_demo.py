#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-C: the first genuine Navigation-selected Suckle extraction contribution.

Profiles choose initial conditions and ablations, never an action list. The common
integrated hierarchy/collector performs all cognitive, handoff and lower work.
Private physical milk totals are observer evidence only; movement success is not
a task-PNM verdict, nourishment or learned performance. Earlier latch I/J/K remain
their original consumers; they do not score the new extraction application.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json

import cca8_cli

from cca8_support_world import FeedingConsequenceProfileV1
from cca8_support_world import OralExtractionWorldProfileV1, PlanarObjectV1
from nca8_body_targets import BodyAxisCapabilityV1, BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1, oral_extraction_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_nipple_demo import SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleExtractionApplicationV1, SuckleApplicationV1
from nca8_suckle_demo import SuckleExperimentProfileV1, suckle_profile_v1, suckle_owner_limits_v1

__version__ = "0.2.0"
__all__ = ["SUCKLE_EXTRACTION_CASES_V1", "SuckleExtractionExperimentProfileV1", "SuckleExtractionExperimentV1",
           "suckle_extraction_profile_v1", "create_suckle_extraction_trial_v1", "run_suckle_extraction_v1",
           "render_suckle_extraction_v1", "run_suckle_extraction_menu_v1", "__version__"]

SUCKLE_EXTRACTION_CASES_V1 = (
    "nominal", "extraction_off", "suckle_off", "no_need", "source_off", "attention_off", "no_capability",
    "missing_stroke", "missing_seal", "latch_then_extract", "nonsealable", "blocked_motor", "dry", "depleted",
    "milk_sensor_off", "delayed", "dropout", "body_shift", "support_loss", "one_cycle", "cadence_1", "cadence_8",
    "competing_initial", "competing_after", "cancelled", "seek_then_latch", "stand_follow", "pnm_registration_off",
)
_NO_SELECTION = frozenset({"extraction_off", "suckle_off", "no_need", "source_off", "attention_off",
                          "missing_stroke", "missing_seal", "nonsealable", "competing_initial"})
_EXPECTED_ACHIEVED = frozenset({"nominal", "dry", "depleted", "milk_sensor_off", "one_cycle", "cadence_1", "cadence_8",
                              "competing_after", "latch_then_extract", "seek_then_latch", "stand_follow",
                              "pnm_registration_off"})


@dataclass(frozen=True, slots=True)
class SuckleExtractionExperimentProfileV1:
    """Predeclared initial conditions; no profile field directs a selected action."""

    case: str
    latch: SuckleExperimentProfileV1
    extraction: OralExtractionWorldProfileV1
    capability: BodyAxisCapabilityV1 | None

    def as_dict(self) -> dict[str, object]:
        """Expose the fixed experiment inputs and limits, never a cognitive script."""
        return {"case": self.case, "initial_conditions": json.loads(json.dumps(self.latch.as_dict(), allow_nan=False)), "extraction_physics": json.loads(json.dumps(asdict(self.extraction), allow_nan=False)),
                "capability": self.capability.as_dict() if self.capability is not None else None,
                "scope": "one_navigation_selected_extraction_contribution", "full_feeding": False}


def suckle_extraction_profile_v1(case: str = "nominal") -> SuckleExtractionExperimentProfileV1:
    """Choose fixed controls before running, reusing accepted H physical conditions."""
    if not isinstance(case, str) or case not in SUCKLE_EXTRACTION_CASES_V1:
        raise ValueError("unknown selected Suckle extraction case")
    base_case = {"latch_then_extract": "nominal", "seek_then_latch": "seek_then_latch",
                 "stand_follow": "stand_follow", "nonsealable": "closed_without_seal"}.get(case, "already_sealed")
    if case in {"no_need", "source_off", "attention_off", "missing_seal", "delayed", "dropout", "body_shift", "support_loss", "cancelled"}:
        base_case = case
    latch = suckle_profile_v1(base_case)
    seal = latch.seal if case in {"latch_then_extract", "seek_then_latch", "stand_follow"} else replace(latch.seal, initial_closure=0.6)
    task = replace(latch.suckle, enabled=case != "suckle_off", extraction_enabled=case != "extraction_off",
                   extraction_repetitions=1 if case == "one_cycle" else 2,
                   outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True)
    run = replace(latch.run, case=case, horizon_ticks=160 if case == "stand_follow" else 48 if case == "seek_then_latch" else 32,
                  cadence=1 if case == "cadence_1" else 8 if case == "cadence_8" else 4,
                  pnm_registration=case != "pnm_registration_off",
                  competitor_cutoffs=tuple(range(0, 33, 4)) if case == "competing_initial" else (4, 8) if case == "competing_after" else ())
    latch = replace(latch, run=run, suckle=task, seal=seal)
    position = (1.8, 0.0) if case == "stand_follow" else (0.1, 0.0)
    extraction = OralExtractionWorldProfileV1(
        supplying_surface=PlanarObjectV1("extraction_supply", position, 0.004),
        initial_supply_units=0.0 if case == "dry" else 0.05 if case == "depleted" else 1.0,
        motor_enabled=case != "blocked_motor", stroke_available=case != "missing_stroke", milk_available=case != "milk_sensor_off",
    )
    return SuckleExtractionExperimentProfileV1(case, latch, extraction, None if case == "no_capability" else oral_extraction_capability_v1())


def create_suckle_extraction_trial_v1(
    profile: SuckleExtractionExperimentProfileV1, *, trace_capacity: int = 256,
    feeding_consequence_profile: FeedingConsequenceProfileV1 | None = None,
) -> IntegratedRightingTrialV1:
    """Construct one integrated organism; construction performs no selection or step."""
    if not isinstance(profile, SuckleExtractionExperimentProfileV1):
        raise TypeError("selected extraction factory requires its declared typed profile")
    latch, run = profile.latch, profile.latch.run
    return IntegratedRightingTrialV1(
        run.physical, stream_id="selected_suckle_extraction_body", planar_profile=run.planar, oral_profile=run.oral,
        oral_seal_profile=latch.seal, oral_extraction_profile=profile.extraction, feeding_consequence_profile=feeding_consequence_profile, suckle_profile=latch.suckle,
        capabilities=(*nominal_body_capabilities_v1(), oral_body_capability_v1(),
                      *((latch.capability,) if latch.capability is not None else ()),
                      *((profile.capability,) if profile.capability is not None else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=run.stand_follow,
                                             outcome_attention_enabled=run.stand_follow, learning_hook_enabled=run.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=run.feeding,
        seek_nipple_profile=run.seeking, stand_follow_enabled=run.stand_follow,
        task_outcomes_enabled=run.stand_follow, task_outcome_attention_enabled=run.stand_follow,
        task_learning_hook_enabled=run.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=run.pnm_registration, trace_capacity=trace_capacity,
    )


@dataclass(frozen=True, slots=True)
class SuckleExtractionExperimentV1:
    """Complete selected-operation, handoff and physical evidence; all read-only."""

    profile: SuckleExtractionExperimentProfileV1
    run: SeekNippleExperimentV1

    def metrics(self) -> dict[str, object]:
        """Count actual applications and observed lower work separately from milk."""
        selected = [c for c in self.run.cycles if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)]
        commands = [s.command for s in self.run.local_steps if s.command is not None and s.command.oral_extraction_drive not in (None, 0.0)]
        final = self.run.cycles[-1].suckle_extraction if self.run.cycles else None
        physical = self.run.physical_samples[-1].extraction if self.run.physical_samples else None
        return {"selected_extraction_applications": len(selected),
                "first_extraction_tick": selected[0].calculation.cutoff_tick if selected else None,
                "extraction_installations": sum(bool(c.reservations) for c in selected),
                "extraction_commands": len(commands),
                "local_status": final.status if final is not None else "disabled",
                "physical_milk_units": physical.transferred_milk_units if physical is not None else None,
                "closure_applications": sum(isinstance(c.calculation.navigation.application, SuckleApplicationV1) for c in self.run.cycles),
                "full_suckle_complete": False, "task_pnm_fulfilment": "unimplemented_unscored", "durable_updates": 0}

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Discriminate selected authority, evidence, boundedness and honest nonclaims."""
        selected = [c for c in self.run.cycles if isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)]
        targets = [r.current for c in selected for r in c.reservations]
        metrics = self.metrics()
        limits = {**suckle_owner_limits_v1(), "suckle_extraction_applications": 1,
                  "suckle_extraction_targets": 1, "suckle_extraction_reports": 1}
        # Existing optional I/J/K limits are checked by their own original contracts;
        # this observer checks the new counts plus the one focal/target bound.
        peaks = dict(self.run.peak_counts)
        identity_ok = all(
            isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)
            and c.commitment.selected_primitive_id == "ip:suckle"
            and c.receipt.dispatch.pnm is c.calculation.navigation.application.projection.pnm
            and c.receipt.dispatch.motor is not None
            and c.receipt.dispatch.motor.projection is c.calculation.navigation.application.projection
            and c.calculation.navigation.application.contribution.origin_status == "selected_suckle_extraction"
            and all(r.current.target.origin == c.calculation.navigation.application.contribution.origin for r in c.reservations)
            for c in selected)
        return (
            ("at_most_one_extraction_application", len(selected) <= 1),
            ("selection_control", not selected if self.profile.case in _NO_SELECTION else len(selected) == 1),
            ("actual_navigation_projection_handoff_links", identity_ok),
            ("no_fixture_installations", self.run.installations == sum(bool(c.reservations) for c in self.run.cycles)),
            ("commands_require_original_target", all(
                any(t.committed_tick <= s.command.issued_tick < t.expires_at_tick for t in targets)
                for s in self.run.local_steps if s.command is not None and s.command.oral_extraction_drive not in (None, 0.0))),
            ("target_keeps_episode_deadline", all(
                isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)
                and t.expires_at_tick <= c.calculation.navigation.application.task.started_tick + 48
                and t.expires_at_tick - t.committed_tick <= 8 for c in selected for t in [r.current for r in c.reservations])),
            ("ordered_local_completion", metrics["local_status"] == "local_achieved" if self.profile.case in _EXPECTED_ACHIEVED else True),
            ("refusal_has_no_movement", metrics["extraction_commands"] == 0 if self.profile.case in _NO_SELECTION | {"no_capability"} else True),
            ("no_second_focal_work", all(
                not (c.suckle_attention is not None and c.suckle_attention.allocation.kind == "interpretation"
                     and c.calculation.navigation.application is not None) for c in self.run.cycles)),
            ("closure_correspondence_stays_closure_only", all(
                c.suckle_correspondence is None or c.suckle_correspondence.registration is None for c in selected)),
            ("extraction_does_not_register_K_participation", all(
                c.suckle_learning_report is None or c.suckle_learning_report.new_participation is None for c in selected)),
            ("new_state_and_focal_counts_bounded", all(0 <= peaks.get(k, 0) <= v for k, v in limits.items()
                                                       if k.startswith("suckle_extraction_") or k in {"wnm", "current_pnm"})),
            ("durable_sources_unchanged", self.run.durable_before == self.run.durable_after),
            ("one_external_world_step_per_tick", len(self.run.local_steps) == self.profile.latch.run.horizon_ticks),
            ("no_feeding_or_learning_claim", all(c.suckle_extraction is None or
                                               not c.suckle_extraction.as_dict()["full_suckle_complete"] for c in self.run.cycles)),
        )

    @property
    def review_status(self) -> str:
        """Fail when any declared control/invariant fails, never a decorative label."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Detach all sampled evidence; diagnostic records never re-enter cognition."""
        data = {"scope": "P16_2C_LC_selected_suckle_extraction", "profile": self.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in self.run.cycles], "local_steps": [s.as_dict() for s in self.run.local_steps],
                "physical_samples": [p.as_dict() for p in self.run.physical_samples],
                "final_feedback": self.run.final_feedback.as_dict(), "checks": dict(self.checks()), "review_status": self.review_status,
                "peak_counts": dict(self.run.peak_counts), "durable_before": self.run.durable_before, "durable_after": self.run.durable_after}
        return json.loads(json.dumps(data, allow_nan=False))


def run_suckle_extraction_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SuckleExtractionExperimentV1:
    """Run the shared hierarchy on the finite predeclared schedule, no task script."""
    profile = suckle_extraction_profile_v1(case)
    trial = create_suckle_extraction_trial_v1(profile, trace_capacity=trace_capacity)
    return SuckleExtractionExperimentV1(profile, collect_seek_nipple_evidence_v1(trial, profile.latch.run))


def render_suckle_extraction_v1(result: SuckleExtractionExperimentV1, *, detail: bool = False) -> str:
    """Show selected authority and lower outcomes without calling a live owner."""
    if not isinstance(result, SuckleExtractionExperimentV1) or not isinstance(detail, bool):
        raise TypeError("selected extraction renderer needs a completed experiment and Boolean detail")
    lines = [f"L-C selected Suckle extraction: {result.profile.case} -- {result.review_status}",
             "  Current source -> Attention/WNM -> ip:suckle -> original PNM / BodyMap -> consumed handoff -> lower execution.",
             f"  {result.metrics()}",
             "  One bounded contribution; movement is not milk, nourishment, task-PNM fulfilment or learning."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'} {name}" for name, passed in result.checks())
    if detail:
        for cycle in result.run.cycles:
            state = cycle.suckle_extraction
            lines.append(f"  Cycle {cycle.commitment.cycle_id} tick {cycle.calculation.cutoff_tick}: "
                         f"IP={cycle.commitment.selected_primitive_id}, action={cycle.commitment.task_action}, "
                         f"extraction={state.status if state else 'disabled'}, local_report="
                         f"{state.local_report.reason if state and state.local_report else '(none)'}")
    return "\n".join(lines)


def run_suckle_extraction_menu_v1() -> None:
    """Inspect finite shared runs; returning or rereading never advances an organism."""
    groups = {"1": ("nominal", "extraction_off", "latch_then_extract"),
              "2": ("no_need", "source_off", "attention_off", "no_capability", "competing_initial", "competing_after"),
              "3": ("dry", "depleted", "milk_sensor_off", "blocked_motor", "delayed", "support_loss"),
              "4": ("one_cycle", "cadence_1", "cadence_8", "seek_then_latch", "stand_follow"),
              "5": SUCKLE_EXTRACTION_CASES_V1}
    retained: tuple[SuckleExtractionExperimentV1, ...] = ()
    while True:
        print("\nL-C: Navigation-selected Suckle extraction (not complete feeding)")
        print("1 selected/latch controls; 2 authority; 3 evidence/adverse; 4 continuity; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1()
        if choice in {"", "0"}:
            return
        if choice == "6":
            print("\n\n".join(render_suckle_extraction_v1(r, detail=True) for r in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_suckle_extraction_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_extraction_v1(r) for r in retained))
        else:
            print("Invalid selection.")
