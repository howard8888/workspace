#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review P16-1E-B support evidence and optional P16-1E-C source dynamics.

Usage from the repository root (Windows CMD or a normal shell)::

    python scripts/run_nca8_support_evidence.py
    python scripts/run_nca8_support_evidence.py --case recovery --trace
    python scripts/run_nca8_support_evidence.py --case disturbed --trace
    python scripts/run_nca8_support_evidence.py --dynamics
    python scripts/run_nca8_support_evidence.py --continuity-demo

This small review harness is not a task selector or another cognitive runtime.
It calls the existing session API for a fixed, bounded number of cycles; it
never supplies a scripted list of actions, reads simulator state, changes
stored observations, or declares A99/Righting competence. The existing A0
selector still uses coarse posture evidence, while measured support is a
read-only companion. The no-action control explicitly disables Navigation.

Every printed "input" sample has been processed in that cycle. The following
"pending" sample comes from the completed outer world step and is not yet
processed cognitively. The final pending sample is left pending. The optional
flowchart renders saved events only. Each case has a new session and private
world, not an automatic retry or an alteration of the interactive menu session.
The separate --continuity-demo uses labelled synthetic owner input only;
it is not a physical run and does not issue body actions.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

# Direct script execution puts scripts/, not the project root, on sys.path.
# Insert this file's own repository root, independent of the launch directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1
from nca8_maps import SupportObservationV1, create_posture_support_map_library_v1
from nca8_sensory import Nca8BodySensoryModuleV1
from nca8_support_dynamics import SupportDynamicsV1
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import render_flow_trace_lines_v1

__version__ = "0.2.0"
_CASES = ("recovery", "disturbed", "no-action")


def _sample_text(sample: SupportObservationV1 | None) -> str:
    """Format retained measurements without turning missing input into a zero value."""
    if sample is None:
        return "packet absent"
    values = []
    for label, value in (
        ("angle_deg", sample.body_ground_angle_degrees),
        ("loading", sample.useful_loading),
        ("sliding", sample.destabilization),
    ):
        values.append(f"{label}={value:.6f}" if value is not None else f"{label}=missing")
    contact = "missing" if sample.lateral_contact is None else str(sample.lateral_contact)
    return f"sample={sample.sample_id} event={sample.event_cycle} " + " ".join(values) + f" lateral_contact={contact}"


def _dynamics_text(dynamics: SupportDynamicsV1) -> str:
    """Print actual source/working content without treating a held measurement as current."""
    reference = dynamics.reference
    prior = dynamics.previous
    identity = "none" if reference is None else f"sample={reference.sample_id}/event={reference.event_cycle}"
    previous = "none" if prior is None else f"sample={prior.sample_id}/event={prior.event_cycle}"
    return (
        f"continuity={dynamics.continuity}; reference={identity}; age={dynamics.evidence_age}; "
        f"previous={previous}; interval={dynamics.pair_interval}"
    )


def _rate_text(dynamics: SupportDynamicsV1) -> str:
    """Print measured directions/rates; unknown remains unknown rather than a flat trend."""
    rates = (dynamics.angle_rate, dynamics.loading_rate, dynamics.destabilization_rate)
    labels = ("angle", "loading", "destabilization")
    values = []
    for label, rate, direction in zip(labels, rates, dynamics.trends):
        if rate is None:
            values.append(f"{label}=unknown")
        else:
            values.append(f"{label}={rate:+.6f} ({direction})")
    return "; ".join(values)


def run_support_case_v1(
    case: str, *, cycles: int = 6, show_trace: bool = False, dynamics: bool = False,
) -> Nca8SessionV1:
    """Print one bounded experiment and return its isolated session for read-only review.

    Recovery and disturbed cases use the same initial physical body and the
    same A0 decision machinery; their surface forcing differs. The no-action
    control uses the recovery world with Navigation disabled, not a world in
    which time stops. Failures propagate to the command boundary: there is
    no legacy fallback, replacement input or unsafe automatic action retry.
    The default retains the 1E-B provider-only experiment. With dynamics=True,
    the source computes actual finite differences and bounded continuity and
    Navigation copies them into its selected WNM. The A0 primitive cannot read
    that facet. These are represented changes, not learned calibration or proof
    that measured values selected the action.
    """
    if case not in _CASES:
        raise ValueError(f"unknown support experiment: {case}")
    if isinstance(cycles, bool) or not isinstance(cycles, int) or not 1 <= cycles <= 10:
        raise ValueError("cycles must be an integer in [1, 10]")
    if not isinstance(show_trace, bool):
        raise TypeError("show_trace must be Boolean")
    if not isinstance(dynamics, bool):
        raise TypeError("dynamics must be Boolean")
    scenario = "posture_support_disturbed_v1" if case == "disturbed" else "posture_support_recovery_v1"
    session = Nca8SessionV1(Nca8SessionConfigV1(
        scenario_name=scenario,
        support_observation_enabled=True,
        support_dynamics_enabled=dynamics,
        navigation_enabled=case != "no-action",
        seed=0,
    ))
    phase = "P16-1E-C" if dynamics else "P16-1E-B"
    print(f"\n{phase} SUPPORT EVIDENCE | case={case} | scenario={scenario}")
    print("Profile: support_dynamics_v1; deterministic world-side surrogate, not validated goat biomechanics.")
    if dynamics:
        print("Source dynamics: support_trend_v1; two-sample event differences; bounded continuity; no learning.")
        print("Deadbands: angle 1 degree/event; loading/destabilization 0.02/event; pair gap <=2; held evidence age <=2.")
        print("Measured working facet: behavioral_authority=False; omitted from A0 primitive input.")
    else:
        print("Measured companion: read-only; behavioral_authority=False; no learning or CCA trajectory estimator.")
    print("Coarse A0 posture still selects the task. This experiment is separate from retained Gate A.")
    if case == "no-action":
        print("Control: Navigation disabled; null output still advances the physical world once per cycle.")
    for _ in range(cycles):
        result = session.run_cognitive_cycle()
        current = session.support_configuration
        if current is None:
            raise RuntimeError("the read-only support consumer produced no configuration")
        print(
            f"Cycle {result.cycle_id}: output={result.output}; world_step={result.environment_step}; "
            f"input_disposition={current.disposition}; coarse_posture={result.posture_support_state.posture.value}"
        )
        print(f"  input   (processed): {_sample_text(current.observation)}")
        if dynamics:
            source = session.support_dynamics
            if source is None:
                raise RuntimeError("the source produced no dynamics facet")
            print(f"  source (processed): {_dynamics_text(source)}")
            print(f"  rate per event:     {_rate_text(source)}")
            if result.wnm is not None and result.wnm.support_dynamics is not None:
                print(f"  WNM (read-only):    {_dynamics_text(result.wnm.support_dynamics)}; refreshed={result.wnm.refreshed_cycle}")
            else:
                print("  WNM (read-only):    none; source dynamics remain nonfocal, not a second WNM")
        print(f"  pending (not used):  {_sample_text(session.pending_observation.support_observation)}")
    status = session.status()
    print(
        f"Completed {status.cognitive_cycles} cycles; durable_source=posture_support@r{status.posture_support_map_revision}; "
        f"trace_entries={status.trace_retained}/{status.trace_capacity}; reset_required={status.reset_required}"
    )
    print("End of bounded provider experiment; no A99 gate, supported dwell or learned improvement is claimed.")
    if show_trace:
        print("\n".join(render_flow_trace_lines_v1(session.trace_snapshot())))
    return session


def run_support_continuity_demo_v1() -> None:
    """Exercise the real sensory owner with labelled synthetic input, not a closed-loop world.

    This small input-only control omits packets, repeats one, introduces a frame
    error, then resumes valid measurements. It demonstrates bounded time and
    history invalidation, not body physics, WNM selection or action competence.
    A complete missing EnvObservation remains a 1R-B transport failure; only the
    optional support field is absent in the missing-sample rows below.
    """
    module = Nca8BodySensoryModuleV1(
        create_posture_support_map_library_v1(), support_observation_enabled=True, support_dynamics_enabled=True,
    )
    print("\nP16-1E-C SYNTHETIC CONTINUITY CONTROL | owner-only; no environment execution or action")
    retained: dict[str, str | int | float | bool | None] | None = None
    for cycle, condition in enumerate(("fresh", "missing", "duplicate", "missing", "fresh", "bad-frame", "fresh", "fresh"), 1):
        packet = SupportObservationV1(cycle, cycle, "body_ground_v1", 10.0 + cycle, 0.4 + cycle / 100, 0.3, True).as_dict()
        if condition == "bad-frame":
            packet["frame_id"] = "unsupported_changed_frame"
        if condition == "fresh":
            retained = packet
        elif condition == "duplicate":
            packet = retained if retained is not None else packet
        raw = {} if condition == "missing" else {"posture_support_v1": packet}
        observation = adapt_env_observation_v1(EnvObservation(raw_sensors=raw, predicates=["posture:fallen"]))
        result = module.poll_observation(observation, cycle_id=cycle, observation_number=cycle)
        module.apply_result(result.mark_applied(cycle), cycle_id=cycle)
        current = module.support_dynamics
        if current is None:
            raise RuntimeError("the synthetic source produced no dynamics facet")
        print(f"Cycle {cycle}: {condition}; input_disposition={current.configuration.disposition}; {_dynamics_text(current)}")
        print(f"  {_rate_text(current)}; reason={current.reason}")
    print("End of synthetic control. Unknown rates are not zero; invalid frames break history, never change the wire schema.")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the review command and stop on error without retrying a possibly executed action."""
    parser = argparse.ArgumentParser(description=(__doc__ or "Run the bounded NCA8 support-evidence experiment.").split("\n", 1)[0])
    parser.add_argument("--case", choices=("all", *_CASES), default="all", help="independent physical/control condition")
    parser.add_argument("--cycles", type=int, choices=range(1, 11), default=6, metavar="1..10")
    parser.add_argument("--trace", action="store_true", help="also print the retained parts-first flowchart for each case")
    parser.add_argument("--dynamics", action="store_true", help="enable the P16-1E-C read-only source/WNM dynamics facet")
    parser.add_argument("--continuity-demo", action="store_true", help="run only the synthetic owner-side missing/invalid-input control")
    args = parser.parse_args(argv)
    cases = _CASES if args.case == "all" else (args.case,)
    try:
        if args.continuity_demo:
            run_support_continuity_demo_v1()
        else:
            for case in cases:
                run_support_case_v1(case, cycles=args.cycles, show_trace=args.trace, dynamics=args.dynamics)
    except (RuntimeError, ValueError, TypeError, OverflowError, OSError) as exc:
        print(f"[support experiment stopped] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
