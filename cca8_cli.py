#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terminal presentation and menu-routing helpers for the CCA8 runner.

Purpose
-------
This module owns the lightweight command-line presentation and routing layer
that was previously embedded in ``cca8_run.py``: startup logos, the welcome
header, main-menu text, text-command aliases, legacy number routing, and the
small Main Menu #1 watch-mode chooser.

The extraction is intentionally structural. ``cca8_run`` remains responsible
for runtime construction, profile selection, menu-handler execution, and the
cognitive-cycle loop. It imports these presentation helpers and keeps its
historical ``print_header`` and ``print_ascii_logo`` names available so existing
callers continue to work.

Design boundary
---------------
Only standard-library modules are imported here. Keeping this module independent
of ``cca8_run`` avoids a circular import and makes deterministic routing and the
small watch-mode prompt inexpensive to test without constructing a CCA8 world or
controller.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

__version__ = "0.5.5"
__all__ = [
    "ASCII_LOGOS",
    "MAIN_MENU_HEADER",
    "MAIN_MENU_PROMPT",
    "MENU_RESPONSE_DIVIDER",
    "menu_selection_banner",
    "MENU_ALIASES",
    "MENU_NUMBER_COMPATIBILITY",
    "MIN_ALIAS_PREFIX",
    "TECH_MANUAL",
    "print_ascii_logo",
    "print_header",
    "read_menu_input_v1",
    "wait_for_main_menu_continue_v1",
    "route_menu_alias",
    "route_menu_number",
    "watch_cognition_menu_v1",
    "__version__",
]

TECH_MANUAL = "http://github.com/howard8888/workspace" #online source for tech info, on startup screen
MENU_RESPONSE_DIVIDER = "-" * 78

ASCII_LOGOS = {
    "badge": r"""


+--------------------------------------------------------------+
|  C C A 8  —  Causal Cognitive Architecture                   |
+--------------------------------------------------------------+""".strip("\n"),
    "goat": r"""
    ____            CCA8
 .'    `-.       mountain goat
/  _  _   \
| (o)(o)  |
\    __  /
 `'-.____'""".strip("\n"),
}

MAIN_MENU_HEADER = (
    "    ============================================================================\n"
    "                  CCA8 MAIN MENU -- MOUNTAIN GOAT-LIKE SIMULATION\n"
    "    ============================================================================\n"
)

MAIN_MENU_PROMPT = (
    "    Enter a menu number or one of the bracketed text commands.\n"
    "\n"
    "    RUN / UNDERSTAND\n"
    "     1) Watch Cognition Run [watch]\n"
    "     2) Cognitive Storage Oscilloscope / System Inspector [scope]\n"
    "     3) Architecture, Documentation & Tutorial [architecture]\n"
    "\n"
    "    OPERATE / CONFIGURE\n"
    "     4) Manual Inputs & One-Step Controls [control]\n"
    "     5) Runtime / Episode Configuration [config]\n"
    "\n"
    "    MEMORY / PLANNING\n"
    "     6) Memory Operations: WorkingMap, Columns & Engrams [memory]\n"
    "     7) WorldGraph Editing & Planning [graph]\n"
    "\n"
    "    RESEARCH / INTEGRATION\n"
    "     8) Experiments & Benchmarks [experiments]\n"
    "     9) RCOS / Robotics [rcos]\n"
    "    10) LLM / External Model Integration [llm]\n"
    "\n"
    "    SESSION / DEVELOPMENT\n"
    "    11) Session Save / Load / Reset [session]\n"
    "    12) Validation & Developer Utilities [developer]\n"
    "    13) Quit [quit]\n"
    "\n"
    "    New users: 1 -> 2 -> 3\n"
    "    Enter Menu Choice: "
)

MIN_ALIAS_PREFIX = 3

MENU_ALIASES = {
    # Stable top-level Main Menu workbenches.
    "watch": "1",
    "cognition": "1",
    "run": "1",
    "cycle": "1",
    "cycles": "1",
    "demo": "1",
    "env": "1",
    "environment": "1",
    "hybrid": "1",
    "verbose": "1",
    "envloop": "1",
    "envrun": "1",
    "envsteps": "1",
    "survival": "1",
    "survival-demo": "1",
    "newborn-demo": "1",
    "newborn-survival": "1",

    "snapshot": "2",
    "display": "2",
    "scope": "2",
    "oscilloscope": "2",
    "cognitive-scope": "2",
    "world": "2",
    "stats": "2",
    "last": "2",
    "bindings": "2",
    "drives": "2",
    "skills": "2",
    "timekeeping": "2",
    "time": "2",
    "clocks": "2",

    "understanding": "3",
    "tagging": "3",
    "help": "3",
    "docs": "3",
    "architecture": "3",
    "explain": "3",
    "overview": "3",
    "tutorial": "3",
    "tour": "3",

    "control": "4",
    "controls": "4",
    "manual": "4",
    "inputs": "4",
    "intervene": "4",
    "instinct": "4",
    "act": "4",
    "autonomic": "4",
    "tick": "4",
    "fall": "4",
    "simulate": "4",
    "sensory": "4",
    "cue": "4",

    "config": "5",
    "settings": "5",
    "runtime": "5",
    "episode-config": "5",

    "memory": "6",
    "memories": "6",
    "memory-ops": "6",
    "capture": "6",
    "cap": "6",
    "scene": "6",

    "graph": "7",
    "worldgraph": "7",
    "planning": "7",
    "graph-workbench": "7",

    "experiments": "8",
    "experiment": "8",
    "bench": "8",
    "benchmark": "8",

    "rcos": "9",
    "robotics": "9",
    "simgoat": "9",
    "robotgoat": "9",
    "simrobotgoat": "9",

    "llm": "10",
    "openai": "10",
    "llmkey": "10",
    "apikey": "10",
    "external-model": "10",

    "session": "11",
    "sessions": "11",
    "persistence": "11",

    "developer": "12",
    "validation": "12",
    "utilities": "12",
    "tools": "12",
    "about": "12",

    "quit": "13",
    "exit": "13",

    # Non-conflicting historical direct commands retained for compatibility.
    "resolve": "14",
    "engrams": "14",
    "engram": "15",
    "engr": "15",
    "ei": "15",
    "engrams-all": "16",
    "list-engrams": "16",
    "le": "16",
    "la": "16",
    "search-engrams": "17",
    "find-engrams": "17",
    "se": "17",
    "delete-engram": "18",
    "del-engram": "18",
    "de": "18",
    "attach-engram": "19",
    "ae": "19",

    "inspect": "20",
    "details": "20",
    "id": "20",
    "listpredicates": "21",
    "listpreds": "21",
    "listp": "21",
    "add": "22",
    "predicate": "22",
    "connect": "23",
    "link": "23",
    "delete": "24",
    "del": "24",
    "rm": "24",
    "plan": "25",
    "planner": "26",
    "strategy": "26",
    "dijkstra": "26",
    "bfs": "26",
    "pyvis": "27",
    "viz": "27",
    "html": "27",
    "interactive": "27",
    "export and display": "27",

    "export snapshot": "28",
    "save": "29",
    "load": "30",
    "preflight": "31",
    "loc": "33",
    "sloc": "33",
    "pygount": "33",
    "reset": "34",
    "mini": "36",
    "msnap": "36",

    "bodymap": "38",
    "bsnap": "38",
    "spatial": "39",
    "near": "39",
    "config-episode": "40",
    "cfg-epi": "40",
    "retired": "41",
    "future": "42",
    "goat04": "42",
    "wsnap": "43",
    "wm-snapshot": "43",
    "wmsnap": "43",
    "wstore": "44",
    "wmstore": "44",
    "recent_wm_amp": "45",
    "wpick": "46",
    "wpickwm": "46",
    "wload": "47",
    "wmload": "47",

    # Single-letter historical shortcuts remain direct.
    "s": "s",
    "l": "l",
    "t": "t",
    "d": "d",
    "r": "r",
}

MENU_NUMBER_COMPATIBILITY = {
    # Stable canonical Main Menu numbers.
    "1": "watch",
    "2": "scope",
    "3": "architecture",
    "4": "manual",
    "5": "config",
    "6": "memory",
    "7": "graph-menu",
    "8": "experiments-menu",
    "9": "rcos",
    "10": "llm",
    "11": "session",
    "12": "developer",
    "13": "quit",

    # Historical direct numbers 14-51 remain available but are hidden.
    "14": "6",   # Resolve engrams on a binding
    "15": "27",  # Inspect engram by id
    "16": "28",  # List all engrams
    "17": "29",  # Search engrams
    "18": "30",  # Delete engram by id
    "19": "31",  # Attach existing engram
    "20": "10",  # Inspect binding details
    "21": "2",   # List predicates
    "22": "3",   # Add predicate
    "23": "4",   # Connect two bindings
    "24": "15",  # Delete edge
    "25": "5",   # Plan from NOW -> predicate
    "26": "25",  # Planner strategy
    "27": "22",  # Interactive graph
    "28": "16",  # Export snapshot text
    "29": "s",   # Save session
    "30": "l",   # Load session
    "31": "9",   # Full preflight
    "32": "8",   # Historical quit number
    "33": "33",  # LOC report
    "34": "r",   # Reset session
    "35": "35",  # One cognitive cycle
    "36": "36",  # Mini-snapshot toggle
    "37": "37",  # Several cognitive cycles
    "38": "38",  # BodyMap
    "39": "39",  # Spatial scene
    "40": "40",  # Legacy combined runtime configuration
    "41": "41",  # Retired memory/RL guide
    "42": "42",  # goat_foraging_04 configuration
    "43": "43",  # WorkingMap read-only snapshot
    "44": "44",  # Store MapSurface
    "45": "45",  # List MapSurface engrams
    "46": "46",  # Pick MapSurface engram
    "47": "47",  # Load MapSurface engram
    "48": "k",   # LLM/OpenAI console
    "49": "49",  # Experiments
    "50": "50",  # RCOS sandbox
    "51": "51",  # Autonomous newborn demo
}



def read_menu_input_v1(prompt: str = "Choose: ") -> str | None:
    """Read one stripped menu response without propagating terminal interruptions.

    ``None`` means the prompt was interrupted or the input provider failed. A
    blank line remains the empty string so each caller can apply its own
    cancel/default semantics. Keeping this boundary in the CLI module gives all
    interactive submenus one consistent terminal-input contract.
    """
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def wait_for_main_menu_continue_v1() -> bool:
    """Pause before the Main Menu is redrawn after one completed selection.

    Returns ``True`` after ordinary user input. A terminal interruption or input
    failure returns ``False`` so the runner can end the interactive session
    cleanly rather than attempting to redraw another menu.
    """
    return read_menu_input_v1("Please press ENTER to continue...") is not None


def menu_selection_banner(selection: str) -> str:
    """Return a visible start marker for one Main Menu response.

    The displayed menu number is preserved here, before compatibility routing
    translates it to a historical internal handler key. This keeps long terminal
    responses easy to find when the user scrolls back through prior output.
    """
    normalized = selection.strip()
    label = f"#{normalized}" if normalized.isdigit() else normalized.upper()
    return f"{MENU_RESPONSE_DIVIDER}\nMENU SELECTION {label}\n"


def watch_cognition_menu_v1() -> str | None:
    """Return one legacy demonstration or the explicit new-runtime route.

    Main Menu #1 remains a navigation shell. Options 1-3 retain the established
    legacy handlers 35, 37, and 51. Option 4 returns a semantic key that the
    runner handles through a lazily imported, isolated ``nca8_*`` session.
    """
    print("Selection: Watch Cognition Run\n")
    print("Choose how you would like to watch the cognitive architecture operate:")
    print("  1) Watch one cognitive cycle slowly (verbose teaching mode; legacy runtime)")
    print("  2) Watch several cognitive cycles (compact closed-loop timeline; legacy runtime)")
    print("  3) Watch a complete autonomous newborn survival episode (isolated legacy sandbox)")
    print("  4) Open the new Architecture-v09.3 experimental runtime (NCA8 Phase 1B)")
    print("  [Enter] Return to Main Menu")
    pick = read_menu_input_v1()
    if pick is None:
        return None

    if pick == "1":
        return "35"
    if pick == "2":
        return "37"
    if pick == "3":
        return "51"
    if pick == "4":
        return "nca8-runtime"
    print("(cancelled)")
    return None



def print_ascii_logo(style: str | None = None, color: bool = True) -> None:  # pragma: no cover
    """Print one small CCA8 ASCII logo.

    Args:
        style:
            Logo key to display. When omitted, ``CCA8_LOGO`` selects ``badge``,
            ``goat``, or ``off``; an unknown key falls back to ``badge``.
        color:
            Allow ANSI coloring when stdout is a terminal and ``NO_COLOR`` is
            not set.

    Returns:
        None. The function writes directly to stdout.
    """
    #selected = (style or os.getenv("CCA8_LOGO", "badge")).lower()
    selected = (style or os.getenv("CCA8_LOGO") or "badge").lower()
    if selected == "off":
        return

    art = ASCII_LOGOS.get(selected, ASCII_LOGOS["badge"])
    want_color = color and sys.stdout.isatty() and not os.getenv("NO_COLOR")

    if want_color:
        cyan = "\033[36m"
        yellow = "\033[33m"
        bold = "\033[1m"
        reset = "\033[0m"
        if selected == "badge":
            art = art.replace("C C A 8", f"{bold}{cyan}C C A 8{reset}")
        elif selected == "goat":
            art = f"{yellow}{art}{reset}"

    print(art)  # pragma: no cover
    print()  # pragma: no cover


def print_header(
    hal_str: str = "HAL: off (no embodiment)",
    body_str: str = "Body: (none)",
    *,
    runner_version: str,
    technical_manual: str = TECH_MANUAL,
    logo_printer: Callable[..., None] | None = None,
) -> None:
    """Print the CCA8 startup welcome header.

    Args:
        hal_str:
            Human-readable HAL status supplied by the runner.
        body_str:
            Human-readable robotic embodiment status supplied by the runner.
        runner_version:
            Version of ``cca8_run.py`` shown in the banner. This is supplied
            explicitly so this module does not import the runner.
        technical_manual:
            Documentation location printed in the startup block.
        logo_printer:
            Optional logo callback. The runner supplies its compatibility name
            so monkeypatching and existing integrations continue to work.

    Returns:
        None. The function writes the welcome block directly to stdout.
    """
    printer = logo_printer or print_ascii_logo
    entry = os.path.abspath(sys.argv[0])
    platform_text = sys.platform

    print("\n\n# --------------------------------------------------------------------------------------")
    print("# NEW RUN   NEW RUN")
    print("# --------------------------------------------------------------------------------------")
    print("\nA Warm Welcome to the CCA8 Mammalian Brain Simulation")
    print(f"(cca8_run.py v{runner_version})\n")
    printer(style="goat", color=True)
    print(f"Entry point program being run: {entry}")
    print(f"OS: {platform_text} (see system-dependent utilities for more detailed system/simulation info)")
    print('(for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)')
    print(f"\nEmbodiment:  HAL (hardware abstraction layer) setting: {hal_str}")
    print(f"Embodiment:  body_type|version_number|serial_number (i.e., robotic embodiment): {body_str} ")
    print(f"User and Technical Manual (including portions of source code): {technical_manual}")

    print("\nThe simulation of the cognitive architecture can be adjusted to add or take away")
    print("  various features, allowing exploration of different evolutionary-like configurations.\n")
    print("  1. Mountain Goat-like brain simulation")
    print("  2. Chimpanzee-like brain simulation")
    print("  3. Human-like brain simulation")
    print("  4. Human-like one-agent multiple-brains simulation")
    print("  5. Human-like one-brain simulation × multiple-agents society")
    print("  6. Human-like one-agent multiple-brains simulation with combinatorial planning")
    print("  7. Super-Human-like machine simulation")
    print("  8. CCA11: one coherent superhuman mind with governed cognitive plurality")
    print("  9. CCA12: governed pod of complete CCA11 cognitive architectures")
    print("  T. Tutorial (more information) on using and maintaining this program, references\n")


def route_menu_alias(command: str) -> tuple[str | None, list[str]]:
    """Resolve one text command or unique text prefix to a displayed menu number.

    Args:
        command:
            User-entered command. Leading/trailing whitespace and case are
            ignored.

    Returns:
        A tuple ``(routed_choice, matches)``. An exact alias returns its menu
        number and an empty match list. A unique prefix of at least
        ``MIN_ALIAS_PREFIX`` characters returns its menu number and the matching
        alias. Ambiguous or unmatched input returns ``None`` plus the candidate
        aliases available for the caller's help message.
    """
    normalized = command.strip().lower()

    if normalized in MENU_ALIASES:
        return MENU_ALIASES[normalized], []

    if len(normalized) >= MIN_ALIAS_PREFIX:
        matches = [alias for alias in MENU_ALIASES if alias.startswith(normalized)]
        if len(matches) == 1:
            return MENU_ALIASES[matches[0]], matches
        return None, matches

    return None, []


def route_menu_number(choice: str) -> str:
    """Translate a displayed menu number to the runner's historical handler key.

    Args:
        choice:
            Displayed menu number or existing historical key. Whitespace and
            case are normalized before lookup.

    Returns:
        The historical handler key when a compatibility mapping exists;
        otherwise the normalized input unchanged.
    """
    normalized = choice.strip().lower()
    return MENU_NUMBER_COMPATIBILITY.get(normalized, normalized)
