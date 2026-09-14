#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the opt-in P16-1E-B world-provider experiment through real NCA8 sessions.

Usage from the repository root (Windows CMD or a normal shell)::

    python scripts/run_nca8_support_evidence.py
    python scripts/run_nca8_support_evidence.py --case recovery --trace
    python scripts/run_nca8_support_evidence.py --case disturbed --trace

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

from nca8_maps import SupportObservationV1
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import render_flow_trace_lines_v1

__version__ = "0.1.0"
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


def run_support_case_v1(case: str, *, cycles: int = 6, show_trace: bool = False) -> Nca8SessionV1:
    """Print one bounded experiment and return its isolated session for read-only review.

    Recovery and disturbed cases use the same initial physical body and the
    same A0 decision machinery; their surface forcing differs. The no-action
    control uses the recovery world with Navigation disabled, not a world in
    which time stops. Failures propagate to the command boundary: there is
    no legacy fallback, replacement input or unsafe automatic action retry.
    Numerical output shows physical change, not a CCA trajectory estimate,
    learned calibration, or proof that measured values selected the action.
    """
    if case not in _CASES:
        raise ValueError(f"unknown support experiment: {case}")
    if isinstance(cycles, bool) or not isinstance(cycles, int) or not 1 <= cycles <= 10:
        raise ValueError("cycles must be an integer in [1, 10]")
    if not isinstance(show_trace, bool):
        raise TypeError("show_trace must be Boolean")
    scenario = "posture_support_disturbed_v1" if case == "disturbed" else "posture_support_recovery_v1"
    session = Nca8SessionV1(Nca8SessionConfigV1(
        scenario_name=scenario,
        support_observation_enabled=True,
        navigation_enabled=case != "no-action",
        seed=0,
    ))
    print(f"\nP16-1E-B SUPPORT EVIDENCE | case={case} | scenario={scenario}")
    print("Profile: support_dynamics_v1; deterministic world-side surrogate, not validated goat biomechanics.")
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


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the review command and stop on error without retrying a possibly executed action."""
    parser = argparse.ArgumentParser(description=(__doc__ or "Run the bounded NCA8 support-evidence experiment.").split("\n", 1)[0])
    parser.add_argument("--case", choices=("all", *_CASES), default="all", help="independent physical/control condition")
    parser.add_argument("--cycles", type=int, choices=range(1, 11), default=6, metavar="1..10")
    parser.add_argument("--trace", action="store_true", help="also print the retained parts-first flowchart for each case")
    args = parser.parse_args(argv)
    cases = _CASES if args.case == "all" else (args.case,)
    try:
        for case in cases:
            run_support_case_v1(case, cycles=args.cycles, show_trace=args.trace)
    except (RuntimeError, ValueError, TypeError, OverflowError, OSError) as exc:
        print(f"[support experiment stopped] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
