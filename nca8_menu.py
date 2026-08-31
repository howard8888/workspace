#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimental terminal menu for the isolated new CCA8 runtime.

The module is imported lazily only after the user explicitly chooses NCA8 from
Main Menu #1. It receives and returns only ``Nca8SessionV1``; the legacy world,
drives, Ctx, PolicyRuntime, WorkingMap, WorldGraph, and autosave path never
cross this composition boundary.
"""

from __future__ import annotations

import cca8_cli
from nca8_runtime import Nca8SessionV1

__version__ = "0.4.0"
__all__ = ["run_nca8_experimental_menu_v1", "__version__"]


def _print_status_v1(session: Nca8SessionV1 | None) -> None:
    """Print one compact session-status panel."""
    if session is None:
        print("[nca8:status] session=not-created")
        return
    status = session.status()
    print(
        "[nca8:status] "
        f"generation={status.lifecycle_generation} "
        f"episode={status.environment_episode_index} "
        f"cognitive_cycles={status.cognitive_cycles} "
        f"pending=Observation_{status.pending_observation_number} "
        f"map=posture_support@r{status.posture_support_map_revision} "
        f"posture={status.current_posture or '(none)'} "
        f"support={status.current_support or '(none)'} "
        f"attention={status.attention_disposition or '(none)'} "
        f"wnm={status.wnm_id or '(none)'} "
        f"primitive={status.selected_primitive_id or '(none)'} "
        f"pnm={status.current_pnm_id or '(none)'} "
        f"outcome={status.last_prediction_outcome or '(none)'} "
        f"trace={status.trace_retained}/{status.trace_capacity}"
    )


def _ensure_session_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1:
    """Return the existing session or lazily construct one isolated session."""
    if session is not None:
        return session
    print("[nca8:session] creating a fresh isolated session")
    return Nca8SessionV1()


def _print_cycle_result_v1(session: Nca8SessionV1) -> None:
    """Run and print one compact causal Gate-A-capable cycle."""
    result = session.run_cognitive_cycle()
    print(
        "[nca8:cycle] "
        f"cognitive_cycle={result.cycle_id} "
        f"input=Observation_{result.observation_number} "
        f"output=Action_{result.action_number}:{result.output} "
        f"next_input=Observation_{result.next_observation_number}"
    )
    print(
        "[nca8:focal] "
        f"attention={result.attention_selection.disposition.value} "
        f"source_state={result.wnm.primary_source_state.state_id if result.wnm is not None else '(none)'} "
        f"wnm={result.wnm.working_id if result.wnm is not None else '(none)'} "
        f"primitive={result.navigation.selected_primitive_id or '(none)'}"
    )
    print(
        "[nca8:prospective] "
        f"pnm={result.pnm.pnm_id if result.pnm is not None else '(none)'} "
        f"task_action={result.task_action or '(none)'} "
        f"body_authorized={result.body_handoff.authorized if result.body_handoff is not None else False} "
        f"env_action={result.environment_action!r}"
    )
    for outcome in result.prediction_outcomes:
        print(
            "[nca8:outcome] "
            f"application={outcome.application_id} status={outcome.status.value} "
            f"evidence_cycle={outcome.evidence_sampled_cycle}"
        )


def run_nca8_experimental_menu_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1 | None:
    """Run the bounded Phase-1D submenu and return its process-local session.

    Merely opening the menu does not construct a session. Runtime exceptions are
    caught here and cannot mutate the separately owned legacy CCA8 runtime. The
    established Main Menu, not this submenu, owns the one common return pause.
    """
    while True:
        print()
        print("NCA8 -- NEW ARCHITECTURE-v09.3 EXPERIMENTAL RUNTIME")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("Phase 1D / Gate A runs the first complete new cognitive action path.")
        print("POSTURE-SUPPORT evidence can reach Attention, WNM, Navigation, StandUp IP,")
        print("PNM, BodyMap/action-envelope authorization, environment dispatch, and later outcome.")
        print("No legacy cognitive authority, SEC, WorldIndex, or durable learning is active.")
        print()
        print("  1) Show isolated-session status")
        print("  2) Create/reset the isolated session")
        print("  3) Run one deterministic NCA8 cognitive cycle")
        print("  4) Show the compact NCA8 trace")
        print("  5) Run a fresh bounded Gate-A StandUp demonstration")
        print("  [Enter] Return to Main Menu")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return session

        try:
            if choice == "1":
                _print_status_v1(session)
                continue
            if choice == "2":
                if session is None:
                    session = Nca8SessionV1()
                    print("[nca8:session] isolated session created")
                else:
                    status = session.reset()
                    print(f"[nca8:session] isolated session reset generation={status.lifecycle_generation}")
                _print_status_v1(session)
                continue
            if choice == "3":
                session = _ensure_session_v1(session)
                _print_cycle_result_v1(session)
                continue
            if choice == "4":
                if session is None:
                    print("[nca8:trace] no session and therefore no trace")
                    continue
                lines = session.trace_lines()
                print("\n".join(lines) if lines else "[nca8:trace] empty")
                continue
            if choice == "5":
                session = _ensure_session_v1(session)
                summary = session.run_gate_a(reset_first=True)
                print(
                    "[nca8:gate-a] "
                    f"standing={summary.achieved_standing} cycles={summary.cycles_run} "
                    f"stand_up_actions={summary.stand_up_actions} "
                    f"final_posture={summary.final_posture} final_support={summary.final_support} "
                    f"outcome={summary.last_outcome_status}"
                )
                print(f"[nca8:gate-a] reason={summary.reason}")
                continue
            print("Please choose 1, 2, 3, 4, or 5; or press Enter to return.")
        except Exception as exc:  # pragma: no cover - defensive interactive boundary
            print(f"[nca8:error] {type(exc).__name__}: {exc}")
