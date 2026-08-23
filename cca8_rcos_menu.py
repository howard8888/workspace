#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive terminal menu for the Stage-1 SimRobotGoat RCOS sandbox.

The simulation, command vocabulary, HAL seam, mission state, and transition
logic remain in :mod:`cca8_rcos`. This module owns only terminal prompting and
compact rendering. Keeping the menu separate prevents the main composition
root from accumulating embodiment-specific presentation code.
"""

from __future__ import annotations

# A malformed acknowledgement should remain printable rather than terminate an
# interactive robotics-development session.
# pylint: disable=broad-exception-caught

from typing import Any, Optional

from cca8_env import EnvObservation
from cca8_rcos import SIM_ROBOT_GOAT_COMMANDS, SimRobotGoatHAL

__version__ = "0.1.0"

__all__ = [
    "sim_robot_goat_ack_lines_v1",
    "sim_robot_goat_menu_50_interactive",
    "sim_robot_goat_obs_lines_v1",
    "sim_robot_goat_status_lines_v1",
    "sim_robot_goat_value_text_v1",
    "__version__",
]


def sim_robot_goat_value_text_v1(value: Any) -> str:
    """Return a compact terminal-safe text form for one sandbox value."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _dict_or_empty_v1(value: Any) -> dict[str, Any]:
    """Return one dictionary-like RCOS payload or an empty dictionary."""
    return value if isinstance(value, dict) else {}


def sim_robot_goat_obs_lines_v1(obs: EnvObservation) -> list[str]:
    """Return a compact human-readable summary of one observation."""
    raw = obs.raw_sensors if isinstance(obs.raw_sensors, dict) else {}
    meta = obs.env_meta if isinstance(obs.env_meta, dict) else {}

    position = _dict_or_empty_v1(meta.get("position"))
    goal = _dict_or_empty_v1(meta.get("goal"))
    milestones = meta.get("milestones") if isinstance(meta.get("milestones"), list) else []

    x_value = position.get("x", raw.get("x"))
    y_value = position.get("y", raw.get("y"))
    goal_x = goal.get("x")
    goal_y = goal.get("y")

    return [
        "[rcos] observation",
        (
            f"  position=({sim_robot_goat_value_text_v1(x_value)}, {sim_robot_goat_value_text_v1(y_value)}) "
            f"heading={sim_robot_goat_value_text_v1(raw.get('heading', meta.get('heading')))} "
            f"battery={sim_robot_goat_value_text_v1(raw.get('battery'))} "
            f"fatigue={sim_robot_goat_value_text_v1(raw.get('fatigue'))}"
        ),
        (
            f"  goal=({sim_robot_goat_value_text_v1(goal_x)}, {sim_robot_goat_value_text_v1(goal_y)}) "
            f"hazard_near={sim_robot_goat_value_text_v1(raw.get('hazard_near'))} "
            f"at_target={sim_robot_goat_value_text_v1(raw.get('at_target'))} "
            f"at_dock={sim_robot_goat_value_text_v1(raw.get('at_dock'))}"
        ),
        f"  predicates={list(obs.predicates or [])}",
        f"  cues={list(obs.cues or [])}",
        f"  step_index={sim_robot_goat_value_text_v1(meta.get('step_index'))} milestones={milestones}",
    ]


def sim_robot_goat_status_lines_v1(status: dict[str, Any]) -> list[str]:
    """Return one compact status block for the sandbox menu."""
    state = _dict_or_empty_v1(status.get("state"))
    summary = _dict_or_empty_v1(status.get("summary"))
    milestones = status.get("milestones") if isinstance(status.get("milestones"), list) else []

    return [
        "[rcos] status",
        (
            f"  done={sim_robot_goat_value_text_v1(status.get('done'))} "
            f"hal_estopped={sim_robot_goat_value_text_v1(status.get('hal_estopped'))} "
            f"success={sim_robot_goat_value_text_v1(summary.get('success'))} "
            f"done_reason={sim_robot_goat_value_text_v1(summary.get('done_reason'))}"
        ),
        (
            f"  milestone_score={sim_robot_goat_value_text_v1(summary.get('milestone_score'))} "
            f"steps={sim_robot_goat_value_text_v1(summary.get('steps'))}"
        ),
        (
            f"  posture={sim_robot_goat_value_text_v1(state.get('posture'))} "
            f"heading={sim_robot_goat_value_text_v1(state.get('heading'))} "
            f"position=({sim_robot_goat_value_text_v1(state.get('x'))}, "
            f"{sim_robot_goat_value_text_v1(state.get('y'))})"
        ),
        (
            f"  battery={sim_robot_goat_value_text_v1(state.get('battery'))} "
            f"fatigue={sim_robot_goat_value_text_v1(state.get('fatigue'))} "
            f"step_index={sim_robot_goat_value_text_v1(state.get('step_index'))}"
        ),
        (
            f"  milestones={milestones} "
            f"falls={sim_robot_goat_value_text_v1(summary.get('falls'))} "
            f"safety_violations={sim_robot_goat_value_text_v1(summary.get('safety_violations'))} "
            f"loops={sim_robot_goat_value_text_v1(summary.get('repeated_action_loop_count'))}"
        ),
        (
            f"  target_inspected={sim_robot_goat_value_text_v1(summary.get('target_inspected'))} "
            f"at_dock={sim_robot_goat_value_text_v1(summary.get('at_dock'))} "
            f"returned_to_dock={sim_robot_goat_value_text_v1(summary.get('returned_to_dock'))} "
            f"final_posture={sim_robot_goat_value_text_v1(summary.get('final_posture'))}"
        ),
    ]


def sim_robot_goat_ack_lines_v1(ack: Any) -> list[str]:
    """Return a compact acknowledgement block for one sandbox command."""
    if isinstance(ack, dict):
        data = dict(ack)
    elif hasattr(ack, "to_dict") and callable(getattr(ack, "to_dict")):
        try:
            data = dict(ack.to_dict())
        except Exception:
            data = {"note": str(ack)}
    else:
        data = {"note": str(ack)}

    new_milestones = data.get("new_milestones")
    if not isinstance(new_milestones, list):
        new_milestones = []

    return [
        "[rcos] ack",
        (
            f"  command={sim_robot_goat_value_text_v1(data.get('command'))} "
            f"ok={sim_robot_goat_value_text_v1(data.get('ok'))} "
            f"status={sim_robot_goat_value_text_v1(data.get('status'))} "
            f"changed={sim_robot_goat_value_text_v1(data.get('changed'))} "
            f"reward={sim_robot_goat_value_text_v1(data.get('reward'))}"
        ),
        f"  note={sim_robot_goat_value_text_v1(data.get('note'))}",
        f"  new_milestones={new_milestones}",
    ]


def sim_robot_goat_menu_50_interactive(sim_hal: Optional[SimRobotGoatHAL]) -> SimRobotGoatHAL:
    """Run the thin interactive wrapper over the Stage-1 RCOS sandbox."""
    hal = sim_hal if isinstance(sim_hal, SimRobotGoatHAL) else SimRobotGoatHAL()

    if getattr(getattr(hal, "env", None), "state", None) is None:
        observation = hal.reset()
        print("\n[rcos] Initialized SimRobotGoat sandbox.")
        for line in sim_robot_goat_obs_lines_v1(observation):
            print(line)
        print()
        for line in sim_robot_goat_status_lines_v1(hal.status()):
            print(line)
        print()
        print(hal.env.render_ascii())

    while True:
        print("\nSelection: SimRobotGoat RCOS sandbox")
        print("  1) Reset episode")
        print("  2) Show ASCII map")
        print("  3) Show status / summary")
        print("  4) Sense current observation")
        print("  5) Step one Stage-1 command")
        print("  6) HAL emergency stop")
        print("  Enter) Return to main menu")

        choice = input("\nChoose [1,2,3,4,5,6, Enter]: ").strip().lower()

        if choice == "":
            print("[rcos] Returning to main menu.")
            return hal

        if choice in ("1", "reset", "r"):
            raw_seed = input("\nReset seed (blank = keep current deterministic stream): ").strip()
            seed_value: Optional[int] = None
            if raw_seed:
                try:
                    seed_value = int(raw_seed)
                except ValueError:
                    print("[rcos] Invalid seed. Please enter an integer or leave blank.")
                    continue

            observation = hal.reset(seed=seed_value)
            print("\n[rcos] Episode reset.")
            for line in sim_robot_goat_obs_lines_v1(observation):
                print(line)
            print()
            for line in sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            print()
            print(hal.env.render_ascii())
            continue

        if choice in ("2", "map", "ascii", "render"):
            print("\n[rcos] ASCII map")
            print(hal.env.render_ascii())
            continue

        if choice in ("3", "status", "summary"):
            print()
            for line in sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            continue

        if choice in ("4", "sense", "obs", "observe"):
            observation = hal.sense()
            print()
            for line in sim_robot_goat_obs_lines_v1(observation):
                print(line)
            continue

        if choice in ("5", "step", "command", "act"):
            print("\n[rcos] Available Stage-1 commands:")
            for index, command_name in enumerate(SIM_ROBOT_GOAT_COMMANDS, start=1):
                print(f"  {index}) {command_name}")

            raw_command = input("\nCommand number or name (blank = cancel): ").strip().lower()
            if not raw_command:
                print("[rcos] Command step cancelled.")
                continue

            command = raw_command
            if raw_command.isdigit():
                command_index = int(raw_command)
                if 1 <= command_index <= len(SIM_ROBOT_GOAT_COMMANDS):
                    command = SIM_ROBOT_GOAT_COMMANDS[command_index - 1]
                else:
                    print("[rcos] Invalid command number.")
                    continue

            acknowledgement = hal.act(command)
            print()
            for line in sim_robot_goat_ack_lines_v1(acknowledgement):
                print(line)

            observation = hal.sense()
            print()
            for line in sim_robot_goat_obs_lines_v1(observation):
                print(line)

            print()
            for line in sim_robot_goat_status_lines_v1(hal.status()):
                print(line)

            print()
            print(hal.env.render_ascii())
            continue

        if choice in ("6", "estop", "stop", "emergency"):
            hal.emergency_stop()
            print("\n[rcos] HAL emergency stop latched. Use reset to clear it.")
            for line in sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            continue

        print(f"[rcos] Unknown selection: {choice!r}")
