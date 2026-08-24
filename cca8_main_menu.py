#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Top-level CCA8 Main Menu submenus and compatibility routing shells.

Purpose
-------
The visible CCA8 Main Menu is intentionally limited to thirteen stable choices.
This module owns the small intent-oriented submenus beneath that front page:
manual controls, memory operations, WorldGraph editing/planning, experiments,
session management, and developer utilities.

The functions return the runner's established internal handler keys rather than
duplicating implementations. ``cca8_run`` remains the composition root and
continues to own the actual world, controller, persistence, experiment, and
robotics operations.

Compatibility boundary
----------------------
Historical direct menu numbers 14-51 remain available through
:mod:`cca8_cli`. The new choices 4-13 are canonical and therefore intentionally
replace the old meanings of those conflicting numbers. Text aliases continue
to route either to a stable top-level workbench or to a non-conflicting hidden
historical command.
"""

from __future__ import annotations

# Interactive boundaries report malformed input without terminating the live session.
# pylint: disable=broad-exception-caught

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cca8_cli

__version__ = "0.1.1"

__all__ = [
    "SEMANTIC_TOP_LEVEL_CHOICES_V1",
    "MainMenuRuntimeV1",
    "clear_working_map_interactive_v1",
    "developer_utilities_menu_v1",
    "experiments_menu_v1",
    "manual_controls_menu_v1",
    "memory_operations_menu_v1",
    "resolve_top_level_choice_v1",
    "session_management_menu_v1",
    "worldgraph_workbench_menu_v1",
    "__version__",
]

SEMANTIC_TOP_LEVEL_CHOICES_V1: frozenset[str] = frozenset(
    {
        "watch",
        "scope",
        "architecture",
        "manual",
        "config",
        "memory",
        "graph-menu",
        "experiments-menu",
        "rcos",
        "llm",
        "session",
        "developer",
        "quit",
    }
)


@dataclass(frozen=True, slots=True)
class MainMenuRuntimeV1:  # pylint: disable=too-few-public-methods
    """Runner-owned callbacks needed by the stable top-level menu router."""

    watch_menu: Callable[[], str | None]
    scope_menu: Callable[[], str | None]
    architecture_menu: Callable[[], None]
    versions_text: Callable[[], str]



def _route_once_v1(
    *,
    title: str,
    introduction: tuple[str, ...],
    options: tuple[tuple[str, str, str], ...],
) -> str | None:
    """Display one bounded submenu and return its selected handler key.

    ``options`` rows contain ``(display_number, label, handler_key)``. A blank
    response or terminal interruption returns ``None``. Invalid input is
    reported once and also returns ``None`` so the caller can safely redraw the
    stable Main Menu.
    """
    print()
    print(title)
    print("=" * 78)
    for line in introduction:
        print(line)
    if introduction:
        print()
    for number, label, _handler in options:
        print(f" {number:>2}) {label}")
    print("  [Enter] Return to Main Menu")

    choice = cca8_cli.read_menu_input_v1()
    if not choice:
        return None

    routes = {number: handler for number, _label, handler in options}
    routed = routes.get(choice)
    if routed is None:
        available = ", ".join(number for number, _label, _handler in options)
        print(f"Please choose one of: {available}; or press Enter to return.")
        return None
    return routed


def manual_controls_menu_v1() -> str | None:
    """Return one established manual-input or one-step-control handler key."""
    return _route_once_v1(
        title="MANUAL INPUTS & ONE-STEP CONTROLS",
        introduction=(
            "These are explicit development/test interventions, not complete closed-loop cognitive episodes.",
            "A controller step or autonomic tick may advance without incrementing the cognitive-cycle counter.",
        ),
        options=(
            ("1", "Run one manual Action Center invocation", "12"),
            ("2", "Run one autonomic / physiology tick", "14"),
            ("3", "Simulate a fall and request recovery", "18"),
            ("4", "Inject one manual sensory cue", "11"),
        ),
    )


def memory_operations_menu_v1() -> str | None:
    """Return one established memory-mutating handler key.

    Read-only memory inspection belongs in Main Menu #2. This workbench is
    intentionally limited to writes, loads, attachments, deletion, and clearing.
    """
    return _route_once_v1(
        title="MEMORY OPERATIONS -- WORKINGMAP, COLUMNS & ENGRAMS",
        introduction=(
            "These operations can change working or long-term memory state.",
            "Use Main Menu #2 for read-only inspection before or after a change.",
        ),
        options=(
            ("1", "Capture scene -> create an engram and WorldGraph pointer", "24"),
            ("2", "Store the current MapSurface in Columns", "44"),
            ("3", "Load / merge a MapSurface engram into WorkingMap", "47"),
            ("4", "Attach an existing engram to a binding", "31"),
            ("5", "Delete an engram", "30"),
            ("6", "Clear the current WorkingMap", "clear-working-map"),
        ),
    )


def worldgraph_workbench_menu_v1() -> str | None:
    """Return one established WorldGraph editing or planning handler key."""
    return _route_once_v1(
        title="WORLDGRAPH EDITING & PLANNING",
        introduction=(
            "WorldGraph is the sparse episode/retrieval index, not the operative WNM.",
            "Read-only graph inspection and visualization are available through Main Menu #2.",
        ),
        options=(
            ("1", "Add a predicate binding", "3"),
            ("2", "Connect two bindings", "4"),
            ("3", "Delete an edge", "15"),
            ("4", "Plan from NOW to a predicate", "5"),
            ("5", "Select planner strategy: BFS / Dijkstra", "25"),
        ),
    )


def experiments_menu_v1() -> str | None:
    """Return one experiment or benchmark configuration handler key."""
    return _route_once_v1(
        title="EXPERIMENTS & BENCHMARKS",
        introduction=(
            "Experiments run in their established isolated harnesses unless the selected screen states otherwise.",
        ),
        options=(
            ("1", "Open the experiment / benchmark protocol console", "49"),
            ("2", "Configure goat_foraging_04 contextual map switching", "42"),
        ),
    )


def session_management_menu_v1(
    *,
    loaded_path: str | None,
    autosave_path: str | None,
    exit_save_path: str | None,
) -> str | None:
    """Display session operations and return one established handler key.

    The status view is read-only and remains inside this submenu. Save, load,
    and reset return their historical runner keys so persistence logic remains
    single-source in ``cca8_run``.
    """
    while True:
        print()
        print("SESSION SAVE / LOAD / RESET")
        print("=" * 78)
        print("  1) Save the current session")
        print("  2) Load a session")
        print("  3) Reset the current session")
        print("  4) Show current load / autosave / exit-save paths")
        print("  [Enter] Return to Main Menu")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            return "s"
        if choice == "2":
            return "l"
        if choice == "3":
            return "r"
        if choice == "4":
            print()
            print("SESSION I/O STATUS")
            print("-" * 78)
            print(f"  loaded_from : {loaded_path or '(fresh session / none)'}")
            print(f"  autosave_to : {autosave_path or '(disabled)'}")
            print(f"  save_on_exit: {exit_save_path or '(disabled)'}")
            continue
        print("Please choose 1-4 or press Enter to return.")


def developer_utilities_menu_v1() -> str | None:
    """Return one validation or developer-utility handler key."""
    return _route_once_v1(
        title="VALIDATION & DEVELOPER UTILITIES",
        introduction=(
            "These tools inspect the checkout and development environment; they do not advance goat cognition.",
        ),
        options=(
            ("1", "Run the full CCA8 preflight", "9"),
            ("2", "Count Python source lines by directory", "33"),
            ("3", "Display component versions and source paths", "about"),
        ),
    )


def resolve_top_level_choice_v1(  # pylint: disable=too-many-branches,too-many-return-statements
    choice: str,
    *,
    runtime: MainMenuRuntimeV1,
    loaded_path: str | None,
    autosave_path: str | None,
    exit_save_path: str | None,
) -> str | None:
    """Resolve one canonical semantic Main Menu choice.

    Non-semantic historical handler keys are returned unchanged. ``None`` means
    that the selected submenu completed or was cancelled and the caller should
    redraw the Main Menu.
    """
    if choice == "watch":
        return runtime.watch_menu()
    if choice == "scope":
        return runtime.scope_menu()
    if choice == "architecture":
        runtime.architecture_menu()
        return None
    if choice == "manual":
        return manual_controls_menu_v1()
    if choice == "config":
        return "configure-runtime"
    if choice == "memory":
        return memory_operations_menu_v1()
    if choice == "graph-menu":
        return worldgraph_workbench_menu_v1()
    if choice == "experiments-menu":
        return experiments_menu_v1()
    if choice == "rcos":
        return "50"
    if choice == "llm":
        return "k"
    if choice == "session":
        return session_management_menu_v1(
            loaded_path=loaded_path,
            autosave_path=autosave_path,
            exit_save_path=exit_save_path,
        )
    if choice == "quit":
        return "8"
    if choice == "developer":
        selected = developer_utilities_menu_v1()
        if selected == "about":
            print("Selection: Component versions and source paths\n")
            print(runtime.versions_text())
            return None
        return selected
    return choice


def clear_working_map_interactive_v1(
    ctx: Any,
    *,
    reset_working_map: Callable[[Any], Any],
) -> bool:
    """Confirm and clear WorkingMap through the supplied runner-owned callback.

    Returns ``True`` only when the reset callback was invoked successfully.
    The operation is intentionally separated from the read-only WorkingMap view
    exposed in Main Menu #2.
    """
    print()
    print("CLEAR CURRENT WORKINGMAP")
    print("=" * 78)
    print("This clears the active WorkingMap workspace and its transient MapSurface/Scratch/Creative state.")
    print("It does not delete the live WorldGraph or durable Column engrams.")
    confirmation = cca8_cli.read_menu_input_v1("Type CLEAR to confirm, or press Enter to cancel: ")
    if confirmation != "CLEAR":
        print("WorkingMap unchanged.")
        return False

    try:
        reset_working_map(ctx)
    except Exception as exc:  # pragma: no cover - defensive interactive boundary
        print(f"[warn] WorkingMap could not be cleared: {type(exc).__name__}: {exc}")
        return False

    print("WorkingMap cleared.")
    return True
