#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimental terminal menu for the isolated new CCA8 runtime.

The module is imported lazily only after the user explicitly chooses NCA8 from
Main Menu #1.  It receives and returns only ``Nca8SessionV1``; the legacy world,
drives, Ctx, PolicyRuntime, WorkingMap, WorldGraph, and autosave path never
cross this composition boundary.
"""

from __future__ import annotations

import cca8_cli
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionV1

__version__ = "0.3.0"
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
        f"circuit_results={status.pending_circuit_results} "
        f"latched_events={status.latched_events} "
        f"map=posture_support@r{status.posture_support_map_revision} "
        f"posture={status.current_posture or '(none)'} "
        f"support={status.current_support or '(none)'} "
        f"candidate={status.posture_support_candidate_id or '(none)'} "
        f"trace={status.trace_retained}/{status.trace_capacity}"
    )


def _ensure_session_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1:
    """Return the existing session or lazily construct one isolated session."""
    if session is not None:
        return session
    print("[nca8:session] creating a fresh isolated session")
    return Nca8SessionV1()


def run_nca8_experimental_menu_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1 | None:
    """Run the bounded Phase-1C submenu and return its process-local session.

    Merely opening the menu does not construct a session.  Runtime exceptions
    are caught here, reported with an ``nca8`` prefix, and leave the established
    CCA8 session outside this function untouched.  The function deliberately
    does not pause on exit; the existing Main Menu supplies exactly one common
    ``Please press ENTER to continue...`` pause.
    """
    while True:
        print()
        print("NCA8 -- NEW ARCHITECTURE-v09.3 EXPERIMENTAL RUNTIME")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("Phase 1C runs the deterministic cycle plus the first body/NavMap representation.")
        print("The posture predicate scaffold updates POSTURE-SUPPORT NavMapState and BodyMapState.")
        print("No Attention selection, WNM, Navigation, primitive, PNM, task action, SEC, WorldIndex,")
        print("or durable learning is active yet.")
        print()
        print("  1) Show isolated-session status")
        print("  2) Create/reset the isolated session")
        print("  3) Run one deterministic body-representation cognitive cycle")
        print("  4) Show the compact NCA8 trace")
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
                result = session.run_cognitive_cycle()
                print(
                    "[nca8:cycle] "
                    f"cognitive_cycle={result.cycle_id} "
                    f"input=Observation_{result.observation_number} "
                    f"output=Action_{result.action_number}:{NCA8_NO_ACTION} "
                    f"next_input=Observation_{result.next_observation_number}"
                )
                candidate_id = (
                    result.posture_support_candidate.candidate_id
                    if result.posture_support_candidate is not None
                    else "(none)"
                )
                print(
                    "[nca8:representation] "
                    f"map_state={result.posture_support_state.state_id} "
                    f"posture={result.posture_support_state.posture.value} "
                    f"support={result.posture_support_state.support.value} "
                    f"contact={result.posture_support_state.contact.value} "
                    f"bodymap={result.body_map_state.state_id} "
                    f"candidate={candidate_id}"
                )
                print(
                    "[nca8:cycle] Body representation updated; no Attention selection, WNM, Navigation, "
                    "PNM, or task action was created."
                )
                continue

            if choice == "4":
                if session is None:
                    print("[nca8:trace] no session and therefore no trace")
                    continue
                lines = session.trace_lines()
                if not lines:
                    print("[nca8:trace] empty")
                else:
                    print("\n".join(lines))
                continue

            print("Please choose 1, 2, 3, or 4; or press Enter to return.")
        except Exception as exc:  # pragma: no cover - defensive interactive boundary
            print(f"[nca8:error] {type(exc).__name__}: {exc}")
