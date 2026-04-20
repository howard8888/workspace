# -*- coding: utf-8 -*-
"""
CCA8 RCOS stage-1 scaffolding: SimRobotGoat environment + simulated HAL.

Purpose
-------
This module allows usage of the CCA8 as a Robotic
Cognitive Operating System (RCOS) that sits *above* a robot HAL or ROS 2 style
middleware.
Full functionality currently under development, hence the Stage 1, 2, and so on labels.

Stage 1 deliberately does **not** integrate with the CCA8 controller yet. The
intent is narrower and more foundational:

1. define a small, stable command vocabulary for an embodied task,
2. simulate a robot/goat world that can respond to those commands,
3. expose a HAL-like seam (`sense`, `act`, `status`, `emergency_stop`), and 
4. produce observations in the same broad shape already used elsewhere in CCA8
   (`EnvObservation`, local grid payloads, cues, env_meta).

Why start here
--------------
Before asking CCA8 to control a robot for long-horizon work, we need a small,
inspectable, deterministic environment where we can prove the outer loop is
sound:

    command -> world update -> observation -> metrics -> summary

That gives us a clean substrate for later patches:

- Stage 2: let CCA8 choose commands for SimRobotGoat.
- Stage 3: add a bounded GPT-5.4 adviser at ambiguity points.
- Stage 4: swap the simulated HAL for a PetitCat / ROS 2 / vendor HAL.

Design stance
-------------
- Keep this module self-contained and dependency-free (stdlib + CCA8 modules).
- Use explicit dataclasses and strings rather than clever abstractions.
- Prefer deterministic behavior by default; future patches can add stochastic
  perturbations once the baseline is stable and testable.
- Keep the API small and inspectable from the runner, tests, or REPL.

Mission in v1
-------------
The simulated robot starts fallen at the dock and must:

    recover -> inspect target -> return to dock -> recharge -> rest

A direct path to the target is blocked by a small hazard band so the episode is
not a trivial straight-line walk.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional
import random

from cca8_env import EnvObservation
from cca8_navpatch import (
    CELL_BLOCKED,
    CELL_GOAL,
    CELL_HAZARD,
    CELL_TRAVERSABLE,
    GRID_ENCODING_V1,
)

__version__ = "0.1.0"
__all__ = [
    "SIM_ROBOT_GOAT_COMMANDS",
    "SIM_ROBOT_GOAT_MILESTONES",
    "SimRobotGoatConfig",
    "SimRobotGoatState",
    "SimRobotGoatActionAck",
    "SimRobotGoatEpisodeSummary",
    "SimRobotGoatEnv",
    "SimRobotGoatHAL",
    "sim_robot_goat_demo_commands_v1",
    "run_sim_robot_goat_demo_episode_v1",
    "__version__",
]


# --- Command vocabulary ------------------------------------------------------------

CMD_STAND = "stand"
CMD_RECOVER_FALL = "recover_fall"
CMD_TURN_LEFT = "turn_left"
CMD_TURN_RIGHT = "turn_right"
CMD_WALK_FORWARD = "walk_forward"
CMD_INSPECT = "inspect"
CMD_AVOID_HAZARD = "avoid_hazard"
CMD_RETURN_TO_DOCK = "return_to_dock"
CMD_RECHARGE = "recharge"
CMD_REST = "rest"
CMD_STOP = "stop"

SIM_ROBOT_GOAT_COMMANDS = [
    CMD_STAND,
    CMD_RECOVER_FALL,
    CMD_TURN_LEFT,
    CMD_TURN_RIGHT,
    CMD_WALK_FORWARD,
    CMD_INSPECT,
    CMD_AVOID_HAZARD,
    CMD_RETURN_TO_DOCK,
    CMD_RECHARGE,
    CMD_REST,
    CMD_STOP,
]

MILESTONE_RECOVERED = "recovered"
MILESTONE_TARGET_INSPECTED = "target_inspected"
MILESTONE_RETURNED_TO_DOCK = "returned_to_dock"
MILESTONE_RECHARGED = "recharged"
MILESTONE_RESTED = "rested"

SIM_ROBOT_GOAT_MILESTONES = [
    MILESTONE_RECOVERED,
    MILESTONE_TARGET_INSPECTED,
    MILESTONE_RETURNED_TO_DOCK,
    MILESTONE_RECHARGED,
    MILESTONE_RESTED,
]

HEADINGS = ("N", "E", "S", "W")
HEADING_DELTAS = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
}


# --- Dataclasses ------------------------------------------------------------------

@dataclass(slots=True)
class SimRobotGoatConfig:
    """Configuration for the stage-1 SimRobotGoat mission.

    Geometry
    --------
    The default map is intentionally small and deterministic. The robot starts
    at the dock in the upper-left quadrant. The target marker is in the lower-
    right quadrant. A three-cell hazard band blocks the straight-line route,
    which means any successful mission must route around danger.

    Battery / fatigue
    -----------------
    The numbers are not meant as a physical battery model. They are small,
    monotonic pressures that let us measure whether a long-horizon controller is
    preserving resources, returning home in time, or wasting steps.
    """

    grid_w: int = 7
    grid_h: int = 7
    start_pos: tuple[int, int] = (1, 1)
    start_heading: str = "N"
    dock_pos: tuple[int, int] = (1, 1)
    target_pos: tuple[int, int] = (5, 5)
    hazard_cells: set[tuple[int, int]] = field(default_factory=lambda: {(3, 1), (3, 2), (3, 3)})
    obstacle_cells: set[tuple[int, int]] = field(default_factory=set)

    max_steps: int = 80
    local_grid_radius: int = 2

    battery_start: float = 1.00
    battery_turn_cost: float = 0.01
    battery_walk_cost: float = 0.04
    battery_stand_cost: float = 0.02
    battery_inspect_cost: float = 0.02
    battery_rest_cost: float = 0.005
    battery_recharge_gain: float = 0.25
    battery_low_threshold: float = 0.30
    battery_recharged_threshold: float = 0.75

    fatigue_start: float = 0.10
    fatigue_walk_gain: float = 0.03
    fatigue_turn_gain: float = 0.01
    fatigue_stand_gain: float = 0.04
    fatigue_inspect_gain: float = 0.02
    fatigue_rest_drop: float = 0.12
    fatigue_recharge_drop: float = 0.05

    step_cost: float = 0.01
    milestone_reward: float = 1.00
    success_reward: float = 2.50
    safety_violation_penalty: float = 1.00
    invalid_action_penalty: float = 0.10

    end_on_battery_empty: bool = True


@dataclass(slots=True)
class SimRobotGoatState:
    """Mutable internal state of the stage-1 robot/goat world.

    This is the environment-side "God's-eye" state for the RCOS sandbox. It is
    intentionally small and JSON-safe so later patches can log it directly or
    mirror selected pieces into CCA8 structures.
    """

    x: int
    y: int
    heading: str
    posture: str
    battery: float
    fatigue: float
    heat: float = 0.20

    target_inspected: bool = False
    recharge_count: int = 0
    rest_count: int = 0

    step_index: int = 0
    falls: int = 0
    safety_violations: int = 0
    repeated_action_loop_count: int = 0
    mission_complete: bool = False
    done_reason: Optional[str] = None
    last_command: Optional[str] = None

    def pos(self) -> tuple[int, int]:
        """Return the current position as a small tuple."""
        return (self.x, self.y)

    def to_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe snapshot of the state."""
        return {
            "x": self.x,
            "y": self.y,
            "heading": self.heading,
            "posture": self.posture,
            "battery": round(self.battery, 3),
            "fatigue": round(self.fatigue, 3),
            "heat": round(self.heat, 3),
            "target_inspected": bool(self.target_inspected),
            "recharge_count": int(self.recharge_count),
            "rest_count": int(self.rest_count),
            "step_index": int(self.step_index),
            "falls": int(self.falls),
            "safety_violations": int(self.safety_violations),
            "repeated_action_loop_count": int(self.repeated_action_loop_count),
            "mission_complete": bool(self.mission_complete),
            "done_reason": self.done_reason,
            "last_command": self.last_command,
        }


@dataclass(slots=True)
class SimRobotGoatActionAck:
    """Result of applying one command to the simulated HAL / environment."""

    command: str
    ok: bool
    status: str
    note: str = ""
    changed: bool = False
    reward: float = 0.0
    new_milestones: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for logs and test assertions."""
        return {
            "command": self.command,
            "ok": bool(self.ok),
            "status": self.status,
            "note": self.note,
            "changed": bool(self.changed),
            "reward": round(float(self.reward), 3),
            "new_milestones": list(self.new_milestones),
        }


@dataclass(slots=True)
class SimRobotGoatEpisodeSummary:
    """Episode-level metrics for the stage-1 RCOS sandbox.

    These metrics are intentionally close to the later experiment language:
    milestone completion, safety, looping, resource use, and the final mission
    outcome.
    """

    success: bool
    done_reason: str
    steps: int
    milestone_vector: dict[str, bool]
    milestone_score: float
    falls: int
    safety_violations: int
    repeated_action_loop_count: int
    battery_final: float
    fatigue_final: float
    target_inspected: bool
    returned_to_dock: bool
    at_dock: bool
    final_posture: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for logs and tests."""
        return {
            "success": bool(self.success),
            "done_reason": self.done_reason,
            "steps": int(self.steps),
            "milestone_vector": dict(self.milestone_vector),
            "milestone_score": round(float(self.milestone_score), 3),
            "falls": int(self.falls),
            "safety_violations": int(self.safety_violations),
            "repeated_action_loop_count": int(self.repeated_action_loop_count),
            "battery_final": round(float(self.battery_final), 3),
            "fatigue_final": round(float(self.fatigue_final), 3),
            "target_inspected": bool(self.target_inspected),
            "returned_to_dock": bool(self.returned_to_dock),
            "at_dock": bool(self.at_dock),
            "final_posture": self.final_posture,
        }


# --- Environment ------------------------------------------------------------------

class SimRobotGoatEnv:
    """Deterministic stage-1 robot/goat environment.

    Public surface
    --------------
    - ``reset(...)`` returns the first observation plus a small info dict.
    - ``sense()`` returns the current observation without advancing the world.
    - ``step(command, ctx=None)`` advances the world one command and returns the
      Gym-like tuple ``(obs, reward, done, info)``.
    - ``status()`` returns a compact machine-readable status snapshot.
    - ``episode_summary()`` returns end-of-episode metrics.
    - ``render_ascii()`` gives a tiny human-readable map for debugging.

    This keeps the module useful from unit tests, from a future runner menu, or
    from an eventual CCA8 control bridge.
    """

    def __init__(self, config: Optional[SimRobotGoatConfig] = None, *, seed: Optional[int] = None):
        self.config = config if isinstance(config, SimRobotGoatConfig) else SimRobotGoatConfig()
        self._rng = random.Random(seed)
        self._seed = seed
        self.state: Optional[SimRobotGoatState] = None
        self._done = False
        self._milestones: list[str] = []
        self._recent_commands: deque[str] = deque(maxlen=4)
        self._recent_loop_signatures: deque[tuple[str, int, int, str, str]] = deque(maxlen=4)
        self._last_observation: Optional[EnvObservation] = None
        self._last_ack: Optional[SimRobotGoatActionAck] = None

    def reset(self, *, seed: Optional[int] = None) -> tuple[EnvObservation, dict[str, Any]]:
        """Reset the simulated world to a deterministic start state.

        The robot starts *fallen at the dock*. That means a successful episode
        must establish posture recovery as the first meaningful milestone.
        """
        if seed is not None:
            self._seed = seed
            self._rng.seed(seed)

        cfg = self.config
        self.state = SimRobotGoatState(
            x=int(cfg.start_pos[0]),
            y=int(cfg.start_pos[1]),
            heading=str(cfg.start_heading),
            posture="fallen",
            battery=float(cfg.battery_start),
            fatigue=float(cfg.fatigue_start),
        )
        self._done = False
        self._milestones = []
        self._recent_commands.clear()
        self._recent_loop_signatures.clear()
        self._last_ack = None
        self._last_observation = self._build_observation()

        return self._last_observation, {
            "sim_env": "sim_robot_goat_v1",
            "seed": self._seed,
            "mission": "recover -> inspect target -> return to dock -> recharge -> rest",
            "state": self.state.to_dict(),
            "milestones": list(self._milestones),
        }

    def sense(self) -> EnvObservation:
        """Return the current observation without advancing the environment."""
        if self.state is None:
            obs, _ = self.reset(seed=self._seed)
            return obs
        self._last_observation = self._build_observation()
        return self._last_observation

    def status(self) -> dict[str, Any]:
        """Return a compact, HAL-friendly status snapshot."""
        state = self._require_state()
        return {
            "sim_env": "sim_robot_goat_v1",
            "done": bool(self._done),
            "state": state.to_dict(),
            "milestones": list(self._milestones),
            "summary": self.episode_summary().to_dict(),
        }

    def step(self, command: str, ctx: Any = None) -> tuple[EnvObservation, float, bool, dict[str, Any]]:
        """Advance the world by one command.

        The unused ``ctx`` parameter is accepted intentionally. A later patch can
        call this environment from the CCA8 runner using the same broad calling
        style already used by ``HybridEnvironment.step(action, ctx)``.
        """
        _ = ctx
        state = self._require_state()
        if self._done:
            obs = self.sense()
            ack = SimRobotGoatActionAck(
                command=str(command),
                ok=False,
                status="done",
                note="episode already finished",
                changed=False,
                reward=0.0,
            )
            self._last_ack = ack
            return obs, 0.0, True, {
                "ack": ack.to_dict(),
                "state": state.to_dict(),
                "milestones": list(self._milestones),
            }

        cmd = str(command or "").strip()
        reward = -float(self.config.step_cost)
        ack = self._apply_command(cmd)
        reward += ack.reward

        state.step_index += 1
        state.last_command = cmd or None
        self._update_loop_counter(cmd)

        if state.battery <= 0.0 and self.config.end_on_battery_empty:
            self._done = True
            state.done_reason = "battery_empty"

        if state.step_index >= int(self.config.max_steps) and not self._done:
            self._done = True
            state.done_reason = "max_steps"

        if state.mission_complete and not self._done:
            self._done = True
            state.done_reason = "mission_complete"
            reward += float(self.config.success_reward)
            ack.reward += float(self.config.success_reward)

        obs = self._build_observation()
        self._last_observation = obs
        self._last_ack = ack

        info = {
            "ack": ack.to_dict(),
            "state": state.to_dict(),
            "milestones": list(self._milestones),
            "summary": self.episode_summary().to_dict(),
        }
        return obs, reward, self._done, info

    def episode_summary(self) -> SimRobotGoatEpisodeSummary:
        """Return the current end-of-episode metrics.

        This method is safe to call even mid-episode, which is useful for tests
        and for later live dashboards.
        """
        state = self._require_state()
        milestone_vector = {name: (name in self._milestones) for name in SIM_ROBOT_GOAT_MILESTONES}
        milestone_hits = sum(1 for hit in milestone_vector.values() if hit)
        milestone_score = milestone_hits / float(len(SIM_ROBOT_GOAT_MILESTONES))
        at_dock = state.pos() == self.config.dock_pos
        returned_to_dock = MILESTONE_RETURNED_TO_DOCK in self._milestones
        success = bool(state.mission_complete) and state.safety_violations == 0
        done_reason = state.done_reason or ("mission_complete" if success else "in_progress")

        return SimRobotGoatEpisodeSummary(
            success=success,
            done_reason=done_reason,
            steps=state.step_index,
            milestone_vector=milestone_vector,
            milestone_score=milestone_score,
            falls=state.falls,
            safety_violations=state.safety_violations,
            repeated_action_loop_count=state.repeated_action_loop_count,
            battery_final=state.battery,
            fatigue_final=state.fatigue,
            target_inspected=state.target_inspected,
            returned_to_dock=returned_to_dock,
            at_dock=at_dock,
            final_posture=state.posture,
        )

    def render_ascii(self) -> str:
        """Render the current map as a small ASCII block.

        Symbols:
          @ = robot
          D = dock
          T = target marker (uninspected)
          t = target location after inspection
          ^ = hazard
          # = blocked / obstacle
          . = traversable floor
        """
        state = self._require_state()
        rows: list[str] = []
        for y in range(self.config.grid_h):
            chars: list[str] = []
            for x in range(self.config.grid_w):
                pos = (x, y)
                ch = "."
                if pos in self.config.obstacle_cells:
                    ch = "#"
                elif pos in self.config.hazard_cells:
                    ch = "^"
                elif pos == self.config.dock_pos:
                    ch = "D"
                if pos == self.config.target_pos:
                    ch = "t" if state.target_inspected else "T"
                if pos == state.pos():
                    ch = "@"
                chars.append(ch)
            rows.append("".join(chars))
        return "\n".join(rows)

    # --- Internal helpers -----------------------------------------------------------

    def _require_state(self) -> SimRobotGoatState:
        if self.state is None:
            self.reset(seed=self._seed)
        return self.state  # type: ignore[return-value]

    def _in_bounds(self, pos: tuple[int, int]) -> bool:
        return 0 <= pos[0] < self.config.grid_w and 0 <= pos[1] < self.config.grid_h

    def _cell_is_blocked(self, pos: tuple[int, int]) -> bool:
        return (not self._in_bounds(pos)) or pos in self.config.obstacle_cells

    def _cell_is_hazard(self, pos: tuple[int, int]) -> bool:
        return pos in self.config.hazard_cells

    def _turn_left(self, heading: str) -> str:
        idx = HEADINGS.index(heading)
        return HEADINGS[(idx - 1) % len(HEADINGS)]

    def _turn_right(self, heading: str) -> str:
        idx = HEADINGS.index(heading)
        return HEADINGS[(idx + 1) % len(HEADINGS)]

    def _forward_pos(self, pos: tuple[int, int], heading: str) -> tuple[int, int]:
        dx, dy = HEADING_DELTAS[heading]
        return (pos[0] + dx, pos[1] + dy)

    def _manhattan(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _nearest_hazard_distance(self, pos: tuple[int, int]) -> int:
        if not self.config.hazard_cells:
            return 99
        return min(self._manhattan(pos, hz) for hz in self.config.hazard_cells)

    def _hazard_near(self, pos: tuple[int, int]) -> bool:
        return self._nearest_hazard_distance(pos) <= 1

    def _goal_pos(self, state: SimRobotGoatState) -> tuple[int, int]:
        return self.config.dock_pos if state.target_inspected else self.config.target_pos

    def _safe_neighbors(self, pos: tuple[int, int]) -> list[tuple[str, tuple[int, int]]]:
        out: list[tuple[str, tuple[int, int]]] = []
        for heading in HEADINGS:
            nxt = self._forward_pos(pos, heading)
            if self._cell_is_blocked(nxt) or self._cell_is_hazard(nxt):
                continue
            out.append((heading, nxt))
        return out

    def _move_one_step(self, heading: str, *, note_prefix: str = "move") -> SimRobotGoatActionAck:
        state = self._require_state()
        if state.posture == "fallen":
            return SimRobotGoatActionAck(
                command=note_prefix,
                ok=False,
                status="blocked",
                note="robot is fallen",
                changed=False,
            )

        nxt = self._forward_pos(state.pos(), heading)
        if self._cell_is_blocked(nxt):
            return SimRobotGoatActionAck(
                command=note_prefix,
                ok=False,
                status="blocked",
                note="blocked or out of bounds",
                changed=False,
            )

        state.heading = heading
        state.x, state.y = nxt
        self._apply_walk_costs()

        ack = SimRobotGoatActionAck(
            command=note_prefix,
            ok=True,
            status="moved",
            note=f"moved to {nxt}",
            changed=True,
        )
        if self._cell_is_hazard(nxt):
            state.posture = "fallen"
            state.falls += 1
            state.safety_violations += 1
            ack.status = "hazard_fall"
            ack.note = f"entered hazard at {nxt} and fell"
            ack.reward -= float(self.config.safety_violation_penalty)
        return ack

    def _apply_walk_costs(self) -> None:
        state = self._require_state()
        state.battery = max(0.0, state.battery - float(self.config.battery_walk_cost))
        state.fatigue = min(1.0, state.fatigue + float(self.config.fatigue_walk_gain))

    def _apply_turn_costs(self) -> None:
        state = self._require_state()
        state.battery = max(0.0, state.battery - float(self.config.battery_turn_cost))
        state.fatigue = min(1.0, state.fatigue + float(self.config.fatigue_turn_gain))

    def _apply_command(self, command: str) -> SimRobotGoatActionAck:
        state = self._require_state()
        if command not in SIM_ROBOT_GOAT_COMMANDS:
            return SimRobotGoatActionAck(
                command=command,
                ok=False,
                status="invalid",
                note="unknown command",
                changed=False,
                reward=-float(self.config.invalid_action_penalty),
            )

        if state.posture == "resting" and command not in (CMD_REST, CMD_RECHARGE, CMD_STOP):
            state.posture = "standing"

        if command == CMD_STAND:
            if state.posture != "fallen":
                return SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="noop",
                    note="already upright",
                    changed=False,
                )
            state.posture = "standing"
            state.battery = max(0.0, state.battery - float(self.config.battery_stand_cost))
            state.fatigue = min(1.0, state.fatigue + float(self.config.fatigue_stand_gain))
            ack = SimRobotGoatActionAck(command=command, ok=True, status="ok", note="stood up", changed=True)
            return self._finalize_ack(ack)

        if command == CMD_RECOVER_FALL:
            if state.posture != "fallen":
                return SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="noop",
                    note="not fallen",
                    changed=False,
                )
            state.posture = "standing"
            state.battery = max(0.0, state.battery - float(self.config.battery_stand_cost))
            state.fatigue = min(1.0, state.fatigue + float(self.config.fatigue_stand_gain))
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note="recovered from fall",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_TURN_LEFT:
            state.heading = self._turn_left(state.heading)
            self._apply_turn_costs()
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note=f"heading {state.heading}",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_TURN_RIGHT:
            state.heading = self._turn_right(state.heading)
            self._apply_turn_costs()
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note=f"heading {state.heading}",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_WALK_FORWARD:
            ack = self._move_one_step(state.heading, note_prefix=command)
            return self._finalize_ack(ack)

        if command == CMD_INSPECT:
            state.battery = max(0.0, state.battery - float(self.config.battery_inspect_cost))
            state.fatigue = min(1.0, state.fatigue + float(self.config.fatigue_inspect_gain))
            if state.pos() != self.config.target_pos or state.posture == "fallen":
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="fail",
                    note="target not reachable for inspection",
                    changed=False,
                )
                return self._finalize_ack(ack)
            state.target_inspected = True
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note="target inspected",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_AVOID_HAZARD:
            if not self._hazard_near(state.pos()) and not self._cell_is_hazard(state.pos()):
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="noop",
                    note="no nearby hazard",
                    changed=False,
                )
                return self._finalize_ack(ack)

            candidates = self._safe_neighbors(state.pos())
            if not candidates:
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="fail",
                    note="no safe neighbor available",
                    changed=False,
                )
                return self._finalize_ack(ack)

            best_heading = None
            best_pos = None
            best_score = None
            for heading, nxt in candidates:
                score = (self._nearest_hazard_distance(nxt), -self._manhattan(nxt, self._goal_pos(state)))
                if best_score is None or score > best_score:
                    best_heading = heading
                    best_pos = nxt
                    best_score = score

            assert best_heading is not None and best_pos is not None
            state.heading = best_heading
            state.x, state.y = best_pos
            self._apply_walk_costs()
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note=f"moved away from hazard to {best_pos}",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_RETURN_TO_DOCK:
            if state.posture == "fallen":
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="blocked",
                    note="robot is fallen",
                    changed=False,
                )
                return self._finalize_ack(ack)
            if state.pos() == self.config.dock_pos:
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="noop",
                    note="already at dock",
                    changed=False,
                )
                return self._finalize_ack(ack)

            candidates = self._safe_neighbors(state.pos())
            if not candidates:
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="fail",
                    note="no safe path toward dock",
                    changed=False,
                )
                return self._finalize_ack(ack)

            best_heading = None
            best_pos = None
            best_score = None
            for heading, nxt in candidates:
                score = (-self._manhattan(nxt, self.config.dock_pos), self._nearest_hazard_distance(nxt))
                if best_score is None or score > best_score:
                    best_heading = heading
                    best_pos = nxt
                    best_score = score

            assert best_heading is not None and best_pos is not None
            state.heading = best_heading
            state.x, state.y = best_pos
            self._apply_walk_costs()
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note=f"stepped toward dock to {best_pos}",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_RECHARGE:
            if state.pos() != self.config.dock_pos:
                ack = SimRobotGoatActionAck(
                    command=command,
                    ok=False,
                    status="fail",
                    note="not at dock",
                    changed=False,
                )
                return self._finalize_ack(ack)
            state.recharge_count += 1
            state.battery = min(1.0, state.battery + float(self.config.battery_recharge_gain))
            state.fatigue = max(0.0, state.fatigue - float(self.config.fatigue_recharge_drop))
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note="recharging",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_REST:
            state.rest_count += 1
            state.posture = "resting"
            state.battery = max(0.0, state.battery - float(self.config.battery_rest_cost))
            state.fatigue = max(0.0, state.fatigue - float(self.config.fatigue_rest_drop))
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note="resting",
                changed=True,
            )
            return self._finalize_ack(ack)

        if command == CMD_STOP:
            ack = SimRobotGoatActionAck(
                command=command,
                ok=True,
                status="ok",
                note="stopped",
                changed=False,
            )
            return self._finalize_ack(ack)

        ack = SimRobotGoatActionAck(
            command=command,
            ok=False,
            status="invalid",
            note="unhandled command",
            changed=False,
        )
        return self._finalize_ack(ack)

    def _update_loop_counter(self, command: str) -> None:
        state = self._require_state()
        if command:
            self._recent_commands.append(command)
            self._recent_loop_signatures.append((command, state.x, state.y, state.posture, state.heading))

        if len(self._recent_loop_signatures) == self._recent_loop_signatures.maxlen:
            if len(set(self._recent_loop_signatures)) == 1:
                state.repeated_action_loop_count += 1

    def _finalize_ack(self, ack: SimRobotGoatActionAck) -> SimRobotGoatActionAck:
        new_milestones = self._update_milestones()
        ack.new_milestones.extend(new_milestones)
        ack.reward += float(len(new_milestones)) * float(self.config.milestone_reward)
        return ack

    def _update_milestones(self) -> list[str]:
        state = self._require_state()
        new_items: list[str] = []

        def add(name: str) -> None:
            if name not in self._milestones:
                self._milestones.append(name)
                new_items.append(name)

        if state.posture in ("standing", "resting"):
            add(MILESTONE_RECOVERED)

        if state.target_inspected:
            add(MILESTONE_TARGET_INSPECTED)

        if state.target_inspected and state.pos() == self.config.dock_pos:
            add(MILESTONE_RETURNED_TO_DOCK)

        if state.battery >= float(self.config.battery_recharged_threshold):
            if MILESTONE_RETURNED_TO_DOCK in self._milestones:
                add(MILESTONE_RECHARGED)

        if state.posture == "resting" and state.pos() == self.config.dock_pos and MILESTONE_RECHARGED in self._milestones:
            add(MILESTONE_RESTED)
            state.mission_complete = True

        return new_items

    def _build_observation(self) -> EnvObservation:
        state = self._require_state()
        pos = state.pos()
        goal_pos = self._goal_pos(state)
        hazard_near = self._hazard_near(pos)
        next_pos = self._forward_pos(pos, state.heading)
        marker_visible = self._manhattan(pos, self.config.target_pos) <= self.config.local_grid_radius
        dock_visible = self._manhattan(pos, self.config.dock_pos) <= self.config.local_grid_radius

        predicates: list[str] = []
        if state.posture == "fallen":
            predicates.append("posture:fallen")
        elif state.posture == "resting":
            predicates.append("resting")
        else:
            predicates.append("posture:standing")
            predicates.append("alert")

        predicates.append("hazard:near" if hazard_near else "hazard:far")
        predicates.append(
            "proximity:shelter:near"
            if self._manhattan(pos, self.config.dock_pos) <= 1
            else "proximity:shelter:far"
        )

        cues: list[str] = []
        if marker_visible and not state.target_inspected:
            cues.append("vision:marker:visible")
        if dock_visible:
            cues.append("vision:dock:visible")
        if self._cell_is_hazard(next_pos):
            cues.append("hazard:ahead")
        if state.battery <= float(self.config.battery_low_threshold):
            cues.append("battery:low")
        if pos == self.config.target_pos:
            cues.append("position:on_target")
        if pos == self.config.dock_pos:
            cues.append("position:at_dock")

        nav_patch = self._build_local_nav_patch(goal_pos)
        surface_grid = {
            "grid_encoding_v": nav_patch["grid_encoding_v"],
            "grid_w": nav_patch["grid_w"],
            "grid_h": nav_patch["grid_h"],
            "grid_cells": list(nav_patch["grid_cells"]),
            "goal_label": "dock" if state.target_inspected else "target",
            "robot_heading": state.heading,
        }

        return EnvObservation(
            raw_sensors={
                "x": state.x,
                "y": state.y,
                "heading": state.heading,
                "battery": round(state.battery, 3),
                "fatigue": round(state.fatigue, 3),
                "hazard_near": hazard_near,
                "at_target": pos == self.config.target_pos,
                "at_dock": pos == self.config.dock_pos,
                "target_distance_l1": self._manhattan(pos, self.config.target_pos),
                "dock_distance_l1": self._manhattan(pos, self.config.dock_pos),
            },
            predicates=predicates,
            cues=cues,
            env_meta={
                "sim_env": "sim_robot_goat_v1",
                "position": {"x": state.x, "y": state.y},
                "heading": state.heading,
                "goal": {"x": goal_pos[0], "y": goal_pos[1]},
                "target_inspected": bool(state.target_inspected),
                "milestones": list(self._milestones),
                "step_index": int(state.step_index),
                "nav_patch": nav_patch,
                "surface_grid": surface_grid,
            },
        )

    def _build_local_nav_patch(self, goal_pos: tuple[int, int]) -> dict[str, Any]:
        state = self._require_state()
        radius = int(self.config.local_grid_radius)
        size = radius * 2 + 1
        cells: list[int] = []

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                world_pos = (state.x + dx, state.y + dy)
                if not self._in_bounds(world_pos) or world_pos in self.config.obstacle_cells:
                    cells.append(CELL_BLOCKED)
                elif world_pos in self.config.hazard_cells:
                    cells.append(CELL_HAZARD)
                elif world_pos == goal_pos:
                    cells.append(CELL_GOAL)
                else:
                    cells.append(CELL_TRAVERSABLE)

        return {
            "schema": "navpatch_v1",
            "role": "local_scene",
            "frame": "SELF",
            "entity_id": "sim_robot_goat:self",
            "tags": ["sim_robot_goat", "self_local"],
            "extent": {"radius": radius},
            "grid_encoding_v": GRID_ENCODING_V1,
            "grid_w": size,
            "grid_h": size,
            "grid_cells": cells,
        }


# --- HAL wrapper ------------------------------------------------------------------

class SimRobotGoatHAL:
    """Very small HAL-like wrapper over ``SimRobotGoatEnv``.

    The purpose of this class is architectural, not just cosmetic. It gives us a
    seam that looks like a future robot adapter while still running entirely in a
    deterministic software sandbox.
    """

    def __init__(self, env: Optional[SimRobotGoatEnv] = None):
        self.env = env if isinstance(env, SimRobotGoatEnv) else SimRobotGoatEnv()
        self._estopped = False
        self._last_info: dict[str, Any] = {}

    def reset(self, *, seed: Optional[int] = None) -> EnvObservation:
        """Reset the underlying environment and clear estop state."""
        self._estopped = False
        obs, info = self.env.reset(seed=seed)
        self._last_info = dict(info)
        return obs

    def sense(self) -> EnvObservation:
        """Return the latest observation from the simulated body/world."""
        return self.env.sense()

    def act(self, command: str) -> SimRobotGoatActionAck:
        """Apply one command to the simulated environment.

        I return the action acknowledgement rather than the whole transition so
        the calling shape resembles a hardware adapter. The latest observation is
        then available through ``sense()`` and the latest summary through
        ``status()``.
        """
        if self._estopped:
            return SimRobotGoatActionAck(
                command=str(command),
                ok=False,
                status="estopped",
                note="HAL estop is active",
            )

        _obs, _reward, _done, info = self.env.step(command)
        self._last_info = dict(info)
        ack_data = info.get("ack", {}) if isinstance(info, dict) else {}
        return SimRobotGoatActionAck(
            command=str(ack_data.get("command", command)),
            ok=bool(ack_data.get("ok", False)),
            status=str(ack_data.get("status", "unknown")),
            note=str(ack_data.get("note", "")),
            changed=bool(ack_data.get("changed", False)),
            reward=float(ack_data.get("reward", 0.0) or 0.0),
            new_milestones=list(ack_data.get("new_milestones", []) or []),
        )

    def status(self) -> dict[str, Any]:
        """Return a compact HAL status payload."""
        out = self.env.status()
        out["hal_estopped"] = bool(self._estopped)
        return out

    def emergency_stop(self) -> None:
        """Latch the HAL into estop until the next reset."""
        self._estopped = True


# --- Demo helpers -----------------------------------------------------------------

def sim_robot_goat_demo_commands_v1() -> list[str]:
    """Return a deterministic command script that completes the default mission.

    The script deliberately routes around the hazard band, inspects the target,
    returns home, recharges, and then rests.
    """
    return [
        CMD_STAND,
        CMD_TURN_RIGHT,
        CMD_WALK_FORWARD,
        CMD_TURN_RIGHT,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_TURN_LEFT,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_INSPECT,
        CMD_TURN_LEFT,
        CMD_TURN_LEFT,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_WALK_FORWARD,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RETURN_TO_DOCK,
        CMD_RECHARGE,
        CMD_RECHARGE,
        CMD_REST,
    ]


def run_sim_robot_goat_demo_episode_v1(
    commands: Optional[list[str]] = None,
    *,
    config: Optional[SimRobotGoatConfig] = None,
    seed: Optional[int] = None,
) -> dict[str, Any]:
    """Run one scripted episode and return a compact result bundle.

    This helper is meant for unit tests, quick REPL checks, and a later runner
    menu entry.
    """
    env = SimRobotGoatEnv(config=config, seed=seed)
    obs, info = env.reset(seed=seed)
    trace: list[dict[str, Any]] = []

    for command in commands or sim_robot_goat_demo_commands_v1():
        obs, reward, done, step_info = env.step(command)
        trace.append(
            {
                "command": command,
                "reward": round(float(reward), 3),
                "done": bool(done),
                "ack": dict(step_info.get("ack", {})),
                "state": dict(step_info.get("state", {})),
                "milestones": list(step_info.get("milestones", [])),
            }
        )
        if done:
            break

    return {
        "summary": env.episode_summary().to_dict(),
        "trace": trace,
        "final_observation": obs,
        "reset_info": info,
        "final_ascii": env.render_ascii(),
    }
