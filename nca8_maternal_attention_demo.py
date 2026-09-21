#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2B-D observer reviews using the real visual/maternal source competition.

The on/off contrast has identical physical input, original endpoint claims,
current body/source evidence and ordinary priorities through cutoff20. Exogenous
post-achievement drift occurs at [6,8) and [14,16), not in response to a task
status. Visual scene relevance is supplied at cutoffs16/20; it competes through
ordinary Attention rather than being forced into WNM. Only the maternal outcome
route differs. Its effect is focal allocation, not an asserted survival advantage.

All trials use existing physical/target consumers and finite task budgets. The
stand cases use the retained 160-tick integration profile and its two-degree
inset; other cases start supported and last 80 ticks. No runner stage list, new
physics, teaching signal or hidden maternal coordinate enters cognition. Menu,
script and detailed rendering share these same observer-only records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1,
    PlanarObjectV1, PlanarPerturbationV1, PlanarWorldProfileV1, PlanarWorldStateV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import follow_mom_owner_limits_v1, maternal_durable_signature_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_sensorimotor import SensorimotorStepV1

__version__ = "0.1.0"
__all__ = [
    "MATERNAL_ATTENTION_CASES_V1", "MaternalAttentionExperimentV1", "create_maternal_attention_trial_v1",
    "run_maternal_attention_v1", "render_maternal_attention_v1", "run_maternal_attention_menu_v1", "__version__",
]
MATERNAL_ATTENTION_CASES_V1 = (
    "competing_on", "competing_off", "maintain_on", "maintain_off", "nominal_on", "nominal_off",
    "routine_once", "comparison_off", "request_expiry", "unresolved_current", "support_loss", "stand_follow", "stand_drift",
)
_OWNER_LIMITS = {
    **follow_mom_owner_limits_v1(),
    "maternal_attention_pending_requests": 8, "maternal_attention_previous_endpoint": 1,
    "maternal_attention_dependency": 1, "maternal_attention_dispositions": 32,
    "outcome_pending_claims": 8, "outcome_terminal_history": 32, "outcome_installed_targets": 2,
    "outcome_dwell_samples": 3, "outcome_recent_feedback": 16, "outcome_staged_intervals": 16, "outcome_command_ticks": 16,
}


def create_maternal_attention_trial_v1(case: str, *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct a fixed experiment; no source/primitive is selected by this function.

    Positive drift is a small external movement after local target achievement,
    when no local target is being pursued. One such endpoint is routine under the
    declared relevance policy; two comparable executed discrepancies are a
    persistent task-level question. The physical model/tolerances are untouched.
    The missing-current case drops new acquisitions from interval17 onward while
    preserving the original second endpoint16 already delivered. Support loss
    at20 exercises the independent local protection path during focal allocation.
    Both maintain controls disable the separate task-persistence nomination, so
    the same visual competitor can expose the outcome effect without an already
    sufficient non-outcome persistence rank masking it. Task continuity remains.
    """
    if not isinstance(case, str) or case not in MATERNAL_ATTENTION_CASES_V1:
        raise ValueError("unknown maternal outcome-Attention experiment")
    stand = case in {"stand_follow", "stand_drift"}
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1() if stand else MotorBodyStateV1(0.0, 1.0))
    planar = PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2.0, 1.0)),))
    if case not in {"nominal_on", "nominal_off", "stand_follow"}:
        offset = 40 if stand else 0
        drift: tuple[PlanarPerturbationV1, ...] = (PlanarPerturbationV1(offset + 6, offset + 8, velocity=(0.6, 0.3)),)
        if case != "routine_once":
            drift += (PlanarPerturbationV1(offset + 14, offset + 16, velocity=(0.6, 0.3)),)
        planar = replace(planar, perturbations=drift)
    if case == "unresolved_current":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(17, 81, drop_feedback=True),))
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(20, 81, remove_support=True),))
    profile = FollowMomProfileV1(outcomes_enabled=True, influence_enabled=case not in {"maintain_on", "maintain_off"},
                                 prediction_comparison_enabled=case != "comparison_off",
                                 outcome_attention_enabled=case not in {"competing_off", "maintain_off", "nominal_off"})
    return IntegratedRightingTrialV1(
        physical, stream_id="maternal_attention_reference_body", planar_profile=planar, follow_mom_profile=profile,
        translation_capability=BodyTranslationCapabilityV1(), trace_capacity=trace_capacity,
        task_outcomes_enabled=stand, stand_follow_enabled=stand, righting_target_inset_degrees=2.0 if stand else 0.0,
    )


def _visual_priority(case: str, tick: int) -> tuple[int, int] | None:
    """Supply declared ordinary visual relevance, never the Attention winner."""
    if case in {"competing_on", "competing_off", "comparison_off"} and tick in (16, 20):
        return (10, 60)
    if case in {"maintain_on", "maintain_off"} and tick == 20:
        return (10, 60)
    if case == "request_expiry" and 16 <= tick <= 32:
        return (11, 60)
    return None


@dataclass(frozen=True, slots=True)
class MaternalAttentionExperimentV1:
    """Finite external review data, separate from current cognition and permissions."""

    case: str
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[PlanarWorldStateV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str
    dispositions: tuple[tuple[str, str, int], ...]

    @property
    def durable_unchanged(self) -> bool:
        """Compare the actual three enduring source organizations before and after."""
        return self.durable_before == self.durable_after

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check every observed owner count, including unexpected/unregistered owners."""
        return tuple(name for name, count in self.peak_counts if name not in _OWNER_LIMITS or not 0 <= count <= _OWNER_LIMITS[name])

    def metrics(self) -> dict[str, object]:
        """Report focal work and actual task consequences without inferring causal credit."""
        frames = [item for item in self.cycles if item.maternal_attention is not None]
        interpreted = [item for item in frames if item.maternal_attention is not None
                       and item.maternal_attention.allocation.kind == "interpretation"]
        reconsidered = [item.calculation.cutoff_tick for item in frames if item.maternal_attention is not None
                        and item.maternal_attention.allocation.kind == "response_reconsideration"]
        task = self.cycles[-1].maternal_task
        at20 = next(item for item in self.cycles if item.calculation.cutoff_tick == 20)
        selected = at20.calculation.attention.selected_bid
        return {
            "case": self.case, "physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
            "focal_opportunities": len(self.cycles), "route_enabled": bool(frames),
            "task_persistence_nomination_enabled": self.case not in {"maintain_on", "maintain_off"},
            "request_ticks": [item.calculation.cutoff_tick for item in frames
                              if item.maternal_attention is not None and item.maternal_attention.created],
            "interpretation_ticks": [item.calculation.cutoff_tick for item in interpreted],
            "interpretation_results": [item.maternal_attention.allocation.interpretation.status for item in interpreted
                                       if item.maternal_attention is not None and item.maternal_attention.allocation.interpretation is not None],
            "response_reconsideration_ticks": reconsidered,
            "cutoff20_source": selected.candidate_id if selected is not None else None,
            "cutoff20_disposition": at20.calculation.attention.disposition.value,
            "maternal_final_status": task.task.status if task is not None and task.task is not None else "no_task",
            "first_proximity_completion_tick": next((item.calculation.cutoff_tick for item in self.cycles
                                                     if item.maternal_task is not None and item.maternal_task.task is not None
                                                     and item.maternal_task.task.status == "completed"), None),
            "target_installations": sum(bool(item.reservations) for item in self.cycles),
            "nonnull_command_intervals": sum(item.command is not None for item in self.local_steps),
            "final_sensed_separation": self.cycles[-1].maternal_source.separation if self.cycles[-1].maternal_source is not None else None,
            "causal_credit": "not_established", "durable_learning_updates": 0,
        }

    def as_dict(self) -> dict[str, object]:
        """Export recorded results without rerunning allocation, source updating or physics."""
        return {
            "profile": "maternal_outcome_attention_v1", "metrics": self.metrics(),
            "cycles": [item.as_dict() for item in self.cycles], "local_steps": [item.as_dict() for item in self.local_steps],
            "observer_planar_samples": [asdict(item) for item in self.physical_samples],
            "final_feedback": self.final_feedback.as_dict(), "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_OWNER_LIMITS), "bound_violations": list(self.bound_violations),
            "request_dispositions": list(self.dispositions), "durable_unchanged": self.durable_unchanged,
            "restores_motor_permission": False, "remaining_P16_2B": "maternal_no_learning_and_Phase_F_reconciliation",
            "B99": "open_feeding_rest_and_full_newborn_qualification",
        }


def run_maternal_attention_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> MaternalAttentionExperimentV1:
    """Run one fixed-horizon experiment; outcome never chooses the next runner stage.

    Four local updates per focal opportunity are retained. An interpretation is
    charged to one of those opportunities, never added as a second cycle. No
    success-dependent early exit or budget extension makes the control pass.
    """
    trial = create_maternal_attention_trial_v1(case, trace_capacity=trace_capacity)
    before = maternal_durable_signature_v1(trial)
    horizon = 160 if case in {"stand_follow", "stand_drift"} else 80
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[PlanarWorldStateV1] = []
    peaks: dict[str, int] = {}

    def observe() -> None:
        """Read owner storage after actual work; do not use counts to drive behavior."""
        for name, count in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), count)

    for tick in range(horizon):
        if tick % 4 == 0:
            cycles.append(trial.focal_step(visual_bid_priority=_visual_priority(case, tick)))
            observe()
        local.append(trial.advance_lower())
        body = trial.observer_planar_body
        if body is None:
            raise RuntimeError("maternal review lost its physical planar provider")
        physical.append(body)
        observe()
    cycles.append(trial.focal_step(visual_bid_priority=_visual_priority(case, horizon)))
    observe()
    route = trial.core.maternal.outcome_attention if trial.core.maternal is not None else None
    return MaternalAttentionExperimentV1(
        case, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback, tuple(sorted(peaks.items())),
        before, maternal_durable_signature_v1(trial), () if route is None else route.dispositions(),
    )


def render_maternal_attention_v1(result: MaternalAttentionExperimentV1, *, detail: bool = False) -> str:
    """Render the recorded causal contrast; detail has no cognitive side effects."""
    if not isinstance(detail, bool):
        raise TypeError("detail must be Boolean")
    lines = [
        f"P16-2B-D MATERNAL OUTCOME -> ATTENTION | {result.case}",
        "  Real visual/maternal source competition; one body, one clock and one focal allocation.",
        "  Original 0.02-m correspondence tolerance; fixed rank40 relevance; eight-tick request lifetime.",
        "  Persistent-drift fixture: external velocity at [6,8), [14,16); stand_drift shifts these by40.",
        "  Nominal has no drift; routine_once uses only [6,8). No physical/profile retuning by outcome.",
        f"  Results: {result.metrics()}",
    ]
    for focal in result.cycles:
        frame = focal.maternal_attention
        source = focal.calculation.attention.selected_bid
        name = source.source_map_state.source_map_ref.map_id if source is not None else "none"
        lines.append(f"  focal {focal.calculation.cutoff_tick}: source={name}; IP={focal.commitment.selected_primitive_id}; "
                     f"allocation={frame.allocation.kind if frame is not None else 'route_disabled'}")
        if frame is not None:
            for request in frame.created:
                lines.append(f"    request={request.request_id}; significance={request.significance}; expires={request.expires_at_tick}")
            if frame.allocation.kind == "interpretation" and frame.allocation.interpretation is not None:
                item = frame.allocation.interpretation
                lines.append(f"    interpreted={item.status}; current_relations={dict(item.relation_relevance)}; no new task in this slot")
            if detail:
                lines.append(f"    maternal Attention record={frame.as_dict()}")
        if detail and focal.maternal_correspondence is not None:
            for outcome in focal.maternal_correspondence.outcomes:
                lines.append(f"    original endpoint outcome={outcome.as_dict()}")
    lines.extend([
        f"  dispositions={result.dispositions}",
        f"  bounds={list(result.bound_violations)}; durable unchanged={result.durable_unchanged}; durable updates=0",
        "  Interpretation is not a motor command, task success, learned identity or causal credit.",
        "  Maternal no-learning/Phase-F reconciliation remains next; full P16-2B/B99 are not closed.",
    ])
    return "\n".join(lines)


def run_maternal_attention_menu_v1() -> None:
    """Run isolated menu-accessible reviews without changing an existing NCA8 session."""
    groups = {
        "1": ("competing_on", "competing_off"), "2": ("maintain_on", "maintain_off"),
        "3": ("nominal_on", "nominal_off", "routine_once", "comparison_off"),
        "4": ("request_expiry", "unresolved_current", "support_loss"),
        "5": ("stand_follow", "stand_drift"), "6": MATERNAL_ATTENTION_CASES_V1,
        "7": ("competing_on",), "8": ("unresolved_current", "support_loss"),
    }
    while True:
        print("\nMATERNAL OUTCOME / ATTENTION REVIEW (P16-2B-D)")
        print("  1) Competing visual source: route on/off")
        print("  2) Same-source maintain: route on/off")
        print("  3) Nominal, routine mismatch and comparison-off controls")
        print("  4) Expiry, missing current evidence and local support protection")
        print("  5) Continuous stand-follow: nominal and persistent drift")
        print("  6) All profiles (compact)")
        print("  7) Detailed competing-source evidence / 8) Detailed missing-evidence and support-loss controls")
        print("  Enter returns without resetting the existing session")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice not in groups:
            print("Choose 1-8 or press Enter to return.")
            continue
        for case in groups[choice]:
            print(render_maternal_attention_v1(run_maternal_attention_v1(case), detail=choice in {"7", "8"}))
