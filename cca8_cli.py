#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terminal presentation and menu-routing helpers for the CCA8 runner.

Purpose
-------
This module owns the passive command-line interface layer that was previously
embedded in ``cca8_run.py``: startup logos, the welcome header, the main-menu
text, text-command aliases, and legacy menu-number routing.

The extraction is intentionally structural. ``cca8_run`` remains responsible
for runtime construction, profile selection, menu-handler execution, and the
cognitive-cycle loop. It imports these presentation helpers and keeps its
historical ``print_header`` and ``print_ascii_logo`` names available so existing
callers continue to work.

Design boundary
---------------
Only standard-library modules are imported here. Keeping this module independent
of ``cca8_run`` avoids a circular import and makes the deterministic menu-routing
logic inexpensive to test without constructing a CCA8 world or controller.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

__version__ = "0.1.0"
__all__ = [
    "ASCII_LOGOS",
    "MAIN_MENU_HEADER",
    "MAIN_MENU_PROMPT",
    "MENU_ALIASES",
    "MENU_NUMBER_COMPATIBILITY",
    "MIN_ALIAS_PREFIX",
    "TECH_MANUAL",
    "print_ascii_logo",
    "print_header",
    "route_menu_alias",
    "route_menu_number",
    "__version__",
]

TECH_MANUAL = "http://github.com/howard8888/workspace"

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
    '    \n'
    'SCROLL UP TO SEE ANY OF THE DATA SCREENS WHICH MAY HAVE SCROLLED BY QUICKLY\n'
    '\n'
    '\n'
    '\n'
    '    ============================================================================\n'
    '                               CCA8 MAIN MENU\n'
    '    ============================================================================\n'
    '\n'
    '    '
)

MAIN_MENU_PROMPT = (
    '    Enter a menu number or one of the bracketed text commands.\n'
    '\n'
    '    # Quick Start & Tutorial\n'
    '    1) Understanding bindings, edges, predicates, policies [understanding, tagging]\n'
    '    2) Help: System Docs and/or Tutorial with demo tour [help, tutorial, demo]\n'
    '\n'
    '    # Quick Start / Overview\n'
    '    3) Snapshot (bindings + edges + ctx + policies) [snapshot, display]\n'
    '    4) World stats [world, stats]\n'
    '    5) Recent bindings (last 5) [last, bindings]\n'
    '    6) Drives & drive tags [drives]\n'
    '    7) Skill ledger [skills]\n'
    '    8) Temporal probe (epoch/hash/cos/hamming) [temporal, probe]\n'
    '\n'
    '    # Act / Simulate\n'
    '    9) Instinct step (Action Center) [instinct, act]\n'
    '    10) Autonomic tick (emit interoceptive cues) [autonomic, tick]\n'
    '    11) Simulate fall (add posture:fallen and try recovery) [fall, simulate]\n'
    '\n'
    '    # Simulation of the Environment (HybridEnvironment demo)\n'
    '    35) Run 1 Cognitive Cycle (verbose teaching mode) [env, hybrid, verbose]\n'
    '    37) Run n Cognitive Cycles (closed-loop timeline) [envloop, envrun]\n'
    '    38) Inspect BodyMap (summary from BodyMap helpers) [bodymap, bsnap]\n'
    '    39) Spatial scene demo (NOW-near + resting-in-shelter?) [spatial, near]\n'
    '    51) Autonomous newborn survival demo (isolated hard-mode sandbox) [survival, newborn-demo]\n'
    '\n'
    '    # Perception & Memory (Cues & Engrams)\n'
    '    12) Input [sensory] cue [sensory, cue]\n'
    '    13) Capture scene → tiny engram (signal bridge) [capture, scene]\n'
    '    14) Resolve engrams on a binding [resolve, engrams]\n'
    '    15) Inspect engram by id (or binding) [engram, ei]\n'
    '    16) List all engrams [engrams-all, list-engrams]\n'
    '    17) Search engrams (by name / epoch) [search-engrams, find-engrams]\n'
    '    18) Delete engram by bid or eid [delete-engram, del-engram]\n'
    '    19) Attach existing engram to a binding [attach-engram, ae]\n'
    '\n'
    '    # Graph Inspect / Build / Plan\n'
    '    20) Inspect binding details [inspect, details]\n'
    '    21) List predicates [listpredicates, listpreds]\n'
    '    22) [Add] predicate [add, predicate]\n'
    '    23) Connect two bindings (src, dst, relation) [connect, link]\n'
    '    24) Delete edge (source, destn, relation) [delete, rm]\n'
    '    25) Plan from NOW -> <predicate> [plan]\n'
    '    26) Planner strategy (toggle BFS ↔ Dijkstra) [planner, strategy]\n'
    '    27) Export and display interactive graph with options [pyvis, graph]\n'
    '\n'
    '    # Save / System / Help\n'
    '    28) Export snapshot (text only) [export snapshot]\n'
    '    29) Save session → path [save]\n'
    '    30) Load session → path [load]\n'
    '    31) Run preflight now [preflight]\n'
    '    32) Quit [quit, exit]\n'
    '    33) Lines of Python code LOC by directory [loc, sloc]\n'
    '    34) Reset current saved session [reset]\n'
    '    36) Toggle mini-snapshot after each menu selection [mini, msnap]\n'
    '\n'
    '    # Memories\n'
    '    40) Configure episode starting state (drives + age_days) [config-episode, cfg-epi]\n'
    '    41) Retired: WorkingMap & WorldGraph settings, toggle RL policy\n'
    '    42) Configure goat_foraging_04 contextual map-switch evaluation [goat04]\n'
    '    43) WorkingMap snapshot (last N bindings; optional clear) [wsnap, wmsnap]\n'
    '    44) Store MapSurface snapshot to Column + WG pointer (dedup vs last) [wstore, wmstore]\n'
    '    45) List recent wm_mapsurface engrams (Column)\n'
    '    46) Pick best wm_mapsurface engram for current stage/zone (read-only) [wpick, wpickwm]\n'
    '    47) Load wm_mapsurface engram into WorkingMap (replace MapSurface) [wload, wmload]\n'
    '    48) LLM API setup + first demo [llmkey, apikey, openai, llm]\n'
    '    49) Experiments / Benchmarks (protocol scaffolding) [experiments, bench]\n'
    '\n'
    '    # RCOS / Robotics\n'
    '    50) SimRobotGoat RCOS sandbox [rcos, simgoat, robotgoat]\n'
    '\n'
    '        New user suggestion:\n'
    '      #35: Watch one cognitive cycle slowly -->\n'
    '      #3 : Inspect what that cycle produced -->\n'
    '      #51: Watch the architecture conduct a complete autonomous episode\n'
    '      (Use #2 at any time for the tutorial and documentation)\n'
    '      SCROLL UP TO SEE ALL OF THE MENU CHOICES\n'
    '\n'
    '    Enter Menu Choice: '
)

MIN_ALIAS_PREFIX = 3

MENU_ALIASES = {
    # Quick Start & Tutorial
    "understanding": "1",
    "tagging": "1",
    "help": "2",
    "tutorial": "2",
    "tour": "2",
    "demo": "2",

    # Quick Start / Overview
    "snapshot": "3",
    "display": "3",
    "world": "4",
    "stats": "4",
    "last": "5",
    "bindings": "5",
    "drives": "6",
    "skills": "7",
    "temporal": "8",
    "tp": "8",
    "probe": "8",

    # Act / Simulate
    "instinct": "9",
    "act": "9",
    "autonomic": "10",
    "tick": "10",
    "fall": "11",
    "simulate": "11",

    # Perception & Memory
    "sensory": "12",
    "cue": "12",
    "capture": "13",
    "cap": "13",
    "scene": "13",
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

    # Graph Inspect / Build / Plan
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
    "graph": "27",
    "viz": "27",
    "html": "27",
    "interactive": "27",
    "export and display": "27",

    # Save / System / Help
    "export snapshot": "28",
    "save": "29",
    "load": "30",
    "preflight": "31",
    "quit": "32",
    "exit": "32",
    "loc": "33",
    "sloc": "33",
    "pygount": "33",
    "reset": "34",
    "env": "35",
    "environment": "35",
    "hybrid": "35",
    "mini": "36",
    "msnap": "36",

    # Memories
    "envloop": "37",
    "envrun": "37",
    "envsteps": "37",
    "bodymap": "38",
    "bsnap": "38",
    "spatial": "39",
    "near": "39",
    "config-episode": "40",
    "cfg-epi": "40",
    "retired": "41",
    "future": "42",
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
    "experiments": "49",
    "experiment": "49",
    "bench": "49",
    "benchmark": "49",
    "rcos": "50",
    "simgoat": "50",
    "robotgoat": "50",
    "simrobotgoat": "50",
    "survival": "51",
    "survival-demo": "51",
    "newborn-demo": "51",
    "newborn-survival": "51",

    # Keep letter shortcuts working too.
    "s": "s",
    "l": "l",
    "t": "t",
    "d": "d",
    "r": "r",
    "llmkey": "k",
    "apikey": "k",
    "openai": "k",
    "llm": "k",
}

MENU_NUMBER_COMPATIBILITY = {
    # Quick Start & Tutorial
    "1": "23",  # Understanding (help pane)
    "2": "t",  # Tutorial (letter branch)

    # Quick Start / Overview
    "3": "17",  # Snapshot (display)
    "4": "1",  # World stats
    "5": "7",  # Recent bindings (last 5)
    "6": "d",  # Drives & tags (letter branch)
    "7": "13",  # Skill ledger
    "8": "26",  # Temporal probe

    # Act / Simulate
    "9": "12",  # Instinct step
    "10": "14",  # Autonomic tick
    "11": "18",  # Simulate fall

    # Perception & Memory
    "12": "11",  # Input sensory cue
    "13": "24",  # Capture scene → engram
    "14": "6",  # Resolve engrams on a binding
    "15": "27",  # Inspect engram by id
    "16": "28",  # List all engrams
    "17": "29",  # Search engrams
    "18": "30",  # Delete engram by id
    "19": "31",  # Attach existing engram

    # Graph Inspect / Build / Plan
    "20": "10",  # Inspect binding details
    "21": "2",  # List predicates
    "22": "3",  # Add predicate
    "23": "4",  # Connect two bindings
    "24": "15",  # Delete edge
    "25": "5",  # Plan from NOW -> <predicate>
    "26": "25",  # Planner strategy (toggle)
    "27": "22",  # Export interactive graph

    # Save / System / Help
    "28": "16",  # Export snapshot (text)
    "29": "s",  # Save session
    "30": "l",  # Load session
    "31": "9",  # Run preflight now
    "32": "8",  # Quit
    "33": "33",  # Lines of Count
    "34": "r",  # Reset current saved session
    "35": "35",  # Environment simulation
    "36": "36",  # Mini-snapshot toggle
    "37": "37",  # Environment loop
    "38": "38",  # Inspect BodyMap
    "39": "39",  # Spatial / near demo
    "40": "40",  # Configure episode starting state
    "41": "41",  # Retired memory/RL settings
    "42": "42",  # Future usage
    "43": "43",  # WorkingMap snapshot
    "44": "44",  # Store MapSurface snapshot
    "45": "45",  # List recent wm_mapsurface engrams
    "46": "46",  # Pick wm_mapsurface
    "47": "47",  # Load wm_mapsurface
    "48": "k",  # Configure OpenAI / LLM API key
    "49": "49",  # Experiments / Benchmarks
    "50": "50",  # SimRobotGoat RCOS sandbox
    "51": "51",  # Autonomous newborn survival demo
}



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
