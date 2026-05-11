# -*- coding: utf-8 -*-
"""RCOS robotic long-horizon experiment helpers for CCA8.

Purpose
-------
This module keeps the BICA/RCOS robotic experiment scaffolding out of
``cca8_run.py``. The experiments here use the existing SimRobotGoat HAL and
bounded command vocabulary to create a robot-shaped long-horizon benchmark:

    recover posture -> inspect target -> return to dock -> recharge -> rest

These helpers do not claim physical robot control and do not yet route through
the full CCA8 Action Center. They provide a deterministic software benchmark and
smoke-test suite for the RCOS/HAL contract, with JSONL provenance records that
can be cited in the BICA paper as preliminary implementation evidence.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections import deque
from datetime import datetime
from typing import Any

from cca8_rcos import SimRobotGoatConfig, SimRobotGoatEnv, SimRobotGoatHAL


__version__ = "0.1.0"

__all__ = [
    "RCOS_ROBOTIC_TASK_ORDER_V1",
    "RCOS_ROBOTIC_SUITE_SCENARIOS_V1",
    "render_rcos_robotic_protocol_v1",
    "rcos_robotic_run_episode_v1",
    "render_rcos_robotic_episode_lines_v1",
    "rcos_robotic_run_suite_v1",
    "render_rcos_robotic_suite_lines_v1",
    "rcos_robotic_run_repeats_v1",
    "render_rcos_robotic_repeats_lines_v1",
    "render_rcos_robotic_perturbation_protocol_v1",
    "rcos_robotic_run_perturbed_repeats_v1",
    "render_rcos_robotic_perturbed_repeats_lines_v1",
]

RCOS_ROBOTIC_TASK_ORDER_V1 = [
    "recovered",
    "target_inspected",
    "returned_to_dock",
    "recharged",
    "rested",
]

RCOS_ROBOTIC_SUITE_SCENARIOS_V1 = [
    "autonomy_v1",
    "scripted_success",
    "hazard_negative_control",
    "incomplete_no_return_control",
]


def _metric_text_v1(value: Any) -> str:
    """Return a compact human-readable value for terminal experiment summaries."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=isinstance(value, dict))
        except Exception:
            return str(value)
    return str(value)


def _safe_token_v1(text: str, *, default: str = "") -> str:
    """Return a filesystem-friendly token for run ids and output filenames."""
    raw = str(text or "").strip()
    chars: list[str] = []

    for ch in raw:
        if ch.isalnum() or ch in ("-", "_"):
            chars.append(ch)
        elif ch in (" ", ".", "/", "\\", ":"):
            chars.append("_")

    out = "".join(chars)
    while "__" in out:
        out = out.replace("__", "_")
    out = out.strip("_")
    return out or default


def _append_jsonl_v1(path: str | None, record: dict[str, Any]) -> None:
    """Append one JSON-safe record to a JSONL file, best-effort only."""
    if not isinstance(path, str) or not path.strip():
        return
    if not isinstance(record, dict):
        return

    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return


def _make_run_id_v1(*, controller_id: str, seed: int | None, run_label: str = "") -> str:
    """Build a stable, readable run id for one RCOS robotic episode."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    controller = _safe_token_v1(controller_id, default="controller")
    label = _safe_token_v1(run_label, default="rcos")
    seed_token = "seed_none" if seed is None else f"seed_{int(seed)}"
    return f"{stamp}__rcos_robotic__{label}__{controller}__{seed_token}"


def render_rcos_robotic_protocol_v1() -> str:
    """Return the protocol summary for the robot-shaped long-horizon benchmark."""
    lines = []
    lines.append("RCOS robotic long-horizon benchmark v1")
    lines.append("")
    lines.append("Purpose:")
    lines.append("  Test a robot-shaped task sequence using the SimRobotGoat HAL seam and bounded command vocabulary.")
    lines.append("  This is preliminary software evidence for RCOS/HAL execution, not physical robot control.")
    lines.append("")
    lines.append("Milestone ladder:")
    for i, name in enumerate(RCOS_ROBOTIC_TASK_ORDER_V1, start=1):
        lines.append(f"  {i}) {name}")
    lines.append("")
    lines.append("Canonical task:")
    lines.append("  recover posture -> navigate/inspect target -> return to dock -> recharge -> rest")
    lines.append("")
    lines.append("Controllers / controls:")
    lines.append("  autonomy_v1                  simple bounded planner using sense/status + turn/walk/inspect/recharge/rest")
    lines.append("  scripted_success             known-good command sequence for HAL/milestone smoke testing")
    lines.append("  hazard_negative_control      deliberately walks into a hazard; expected to fall and record a safety violation")
    lines.append("  incomplete_no_return_control inspects target but omits return/recharge/rest; expected to fail final mission")
    lines.append("")
    lines.append("Reported metrics:")
    lines.append("  success, expected_outcome_met, milestone_score, steps, falls, safety_violations,")
    lines.append("  repeated_action_loop_count, battery_final, fatigue_final, target_inspected, returned_to_dock, final_posture")
    lines.append("")
    lines.append("Scientific claim supported:")
    lines.append("  The RCOS command vocabulary, HAL surface, safety accounting, milestone scoring, and provenance-oriented")
    lines.append("  episode summaries are executable and testable in simulation.")
    lines.append("")
    lines.append("Scientific claim NOT yet supported:")
    lines.append("  This does not yet show full CCA8 Action Center control of SimRobotGoat and does not show physical robot control.")
    return "\n".join(lines)


def _robotic_state_from_status_v1(status: dict[str, Any]) -> dict[str, Any]:
    """Extract the state dict from a SimRobotGoatHAL status payload."""
    if not isinstance(status, dict):
        return {}
    state = status.get("state")
    return dict(state) if isinstance(state, dict) else {}


def _robotic_summary_from_status_v1(status: dict[str, Any]) -> dict[str, Any]:
    """Extract the summary dict from a SimRobotGoatHAL status payload."""
    if not isinstance(status, dict):
        return {}
    summary = status.get("summary")
    return dict(summary) if isinstance(summary, dict) else {}


def _robotic_pos_from_state_v1(state: dict[str, Any]) -> tuple[int, int] | None:
    """Return integer (x, y) position from a SimRobotGoat state dict."""
    if isinstance(state, dict):
        x_direct = state.get("x")
        y_direct = state.get("y")
        if isinstance(x_direct, int) and isinstance(y_direct, int):
            return (int(x_direct), int(y_direct))

    pos = state.get("position") if isinstance(state, dict) else None
    if isinstance(pos, dict):
        x_val = pos.get("x")
        y_val = pos.get("y")
        if isinstance(x_val, int) and isinstance(y_val, int):
            return (int(x_val), int(y_val))
    if isinstance(pos, (list, tuple)) and len(pos) == 2 and isinstance(pos[0], int) and isinstance(pos[1], int):
        return (int(pos[0]), int(pos[1]))
    return None

#pylint: disable=too-many-locals
def _robotic_shortest_path_v1(start: tuple[int, int], goal: tuple[int, int], config: SimRobotGoatConfig) -> list[tuple[int, int]]:
    """Return a shortest safe 4-neighbor path, avoiding hazard and obstacle cells.

    The helper is intentionally small and deterministic. It is not meant to be a general robotics planner; it exists only so the
    autonomy_v1 controller has a bounded, transparent way to choose the next turn/walk command in the current SimRobotGoat map.
    """
    width = int(getattr(config, "grid_w", 0) or 0)
    height = int(getattr(config, "grid_h", 0) or 0)
    hazards = set(getattr(config, "hazard_cells", set()) or set())
    obstacles = set(getattr(config, "obstacle_cells", set()) or set())
    blocked = hazards | obstacles

    if start == goal:
        return [start]
    if width <= 0 or height <= 0:
        return []

    queue: deque[tuple[int, int]] = deque([start])
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

    while queue:
        cur = queue.popleft()
        if cur == goal:
            break

        x_cur, y_cur = cur
        for nxt in ((x_cur + 1, y_cur), (x_cur - 1, y_cur), (x_cur, y_cur + 1), (x_cur, y_cur - 1)):
            x_next, y_next = nxt
            if x_next < 0 or y_next < 0 or x_next >= width or y_next >= height:
                continue
            if nxt in blocked and nxt != goal:
                continue
            if nxt in came_from:
                continue
            came_from[nxt] = cur
            queue.append(nxt)

    if goal not in came_from:
        return []

    path: list[tuple[int, int]] = []
    cur2: tuple[int, int] | None = goal
    while cur2 is not None:
        path.append(cur2)
        cur2 = came_from.get(cur2)
    path.reverse()
    return path


def _robotic_heading_for_step_v1(src: tuple[int, int], dst: tuple[int, int]) -> str | None:
    """Return the cardinal heading needed to move from src to adjacent dst."""
    dx = int(dst[0]) - int(src[0])
    dy = int(dst[1]) - int(src[1])
    if dx == 1 and dy == 0:
        return "E"
    if dx == -1 and dy == 0:
        return "W"
    if dx == 0 and dy == 1:
        return "S"
    if dx == 0 and dy == -1:
        return "N"
    return None


def _robotic_turn_command_v1(current: str, desired: str) -> str:
    """Return the shorter bounded turn command from current heading toward desired heading."""
    order = ["N", "E", "S", "W"]
    if current not in order or desired not in order:
        return "turn_right"

    cur_i = order.index(current)
    des_i = order.index(desired)
    delta = (des_i - cur_i) % 4
    if delta == 0:
        return "walk_forward"
    if delta == 1:
        return "turn_right"
    if delta == 3:
        return "turn_left"
    return "turn_right"


def _robotic_autonomy_command_v1(status: dict[str, Any], config: SimRobotGoatConfig) -> str:
    """Choose the next bounded command for the autonomy_v1 robotic long-horizon controller.

    This is deliberately not a learned controller. It is a small transparent bridge controller that makes the robot-shaped
    benchmark executable before the full CCA8 Action Center -> RCOS command bridge is finished.
    """
    state = _robotic_state_from_status_v1(status)
    summary = _robotic_summary_from_status_v1(status)

    posture = str(state.get("posture", ""))
    if posture == "fallen":
        return "recover_fall"

    if bool(summary.get("mission_complete")):
        return "stop"

    pos = _robotic_pos_from_state_v1(state)
    if pos is None:
        return "stop"

    target_pos = tuple(getattr(config, "target_pos", (6, 4)))
    dock_pos = tuple(getattr(config, "dock_pos", (0, 0)))
    target_inspected = bool(summary.get("target_inspected")) or bool(state.get("target_inspected"))
    at_dock = bool(summary.get("at_dock")) or pos == dock_pos
    recharge_count = int(summary.get("recharge_count", state.get("recharge_count", 0)) or 0)
    rest_count = int(summary.get("rest_count", state.get("rest_count", 0)) or 0)

    if not target_inspected:
        if pos == target_pos:
            return "inspect"

        path = _robotic_shortest_path_v1(pos, target_pos, config)
        if len(path) < 2:
            return "avoid_hazard"

        desired = _robotic_heading_for_step_v1(pos, path[1])
        heading = str(state.get("heading", "N"))
        if desired is None:
            return "stop"
        if heading != desired:
            return _robotic_turn_command_v1(heading, desired)
        return "walk_forward"

    if not at_dock:
        path = _robotic_shortest_path_v1(pos, dock_pos, config)
        if len(path) < 2:
            return "return_to_dock"

        desired = _robotic_heading_for_step_v1(pos, path[1])
        heading = str(state.get("heading", "N"))
        if desired is None:
            return "stop"
        if heading != desired:
            return _robotic_turn_command_v1(heading, desired)
        return "walk_forward"

    if recharge_count <= 0:
        return "recharge"

    if rest_count <= 0:
        return "rest"

    return "stop"


def _robotic_script_command_v1(controller_id: str, step_index: int) -> str | None:
    """Return scripted control commands for smoke/control episodes."""
    scripted_success = [
        "recover_fall",
        "turn_right",
        "walk_forward",
        "turn_right",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "turn_left",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "inspect",
        "turn_right",
        "turn_right",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "turn_right",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "turn_left",
        "walk_forward",
        "recharge",
        "rest",
    ]

    hazard_negative = [
        "recover_fall",
        "turn_right",
        "walk_forward",
        "walk_forward",
        "walk_forward",
    ]

    incomplete_no_return = [
        "recover_fall",
        "turn_right",
        "walk_forward",
        "turn_right",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "turn_left",
        "walk_forward",
        "walk_forward",
        "walk_forward",
        "inspect",
    ]

    scripts = {
        "scripted_success": scripted_success,
        "hazard_negative_control": hazard_negative,
        "incomplete_no_return_control": incomplete_no_return,
    }
    seq = scripts.get(str(controller_id))
    if not isinstance(seq, list):
        return None
    if step_index < 0 or step_index >= len(seq):
        return None
    return seq[step_index]


def rcos_robotic_run_episode_v1(
    *,
    controller_id: str = "autonomy_v1",
    seed: int | None = None,
    max_steps: int | None = None,
    output_dir: str = "testvalues",
    run_label: str = "",
    write_jsonl: bool = True,
) -> dict[str, Any]:
    """Run one SimRobotGoat robotic long-horizon episode and return a JSON-safe result.

    Args:
        controller_id:
            One of autonomy_v1, scripted_success, hazard_negative_control, or incomplete_no_return_control.
        seed:
            Optional random seed. SimRobotGoat is mostly deterministic today, but the seed is recorded for repeat protocols.
        max_steps:
            Episode cap. If None, use the SimRobotGoatConfig default.
        output_dir:
            Directory for JSONL cycle and episode records.
        run_label:
            Short filename token identifying the paper/dev run.
        write_jsonl:
            If True, write cycle and episode JSONL records under output_dir.

    Returns:
        JSON-safe dict with episode_record, cycle_records, and output paths.
    """
    controller = str(controller_id or "autonomy_v1").strip() or "autonomy_v1"
    if controller not in RCOS_ROBOTIC_SUITE_SCENARIOS_V1:
        return {"ok": False, "why": f"unknown_controller:{controller}"}

    if seed is not None:
        try:
            random.seed(int(seed))
        except Exception:
            pass

    config = SimRobotGoatConfig()
    # Keep the robot-shaped autonomy benchmark focused on task sequencing/safety rather than battery depletion from path length.
    try:
        config.battery_walk_cost = 0.025
        config.battery_turn_cost = 0.005
    except Exception:
        pass

    step_cap = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else int(getattr(config, "max_steps", 80) or 80)
    config.max_steps = max(1, min(100000, step_cap))

    hal = SimRobotGoatHAL(env=SimRobotGoatEnv(config=config))
    reset_obs = hal.reset(seed=seed)
    run_id = _make_run_id_v1(controller_id=controller, seed=seed, run_label=run_label)
    out_dir = os.path.normpath(str(output_dir or "testvalues"))
    cycle_path = os.path.join(out_dir, f"{run_id}__cycle.jsonl")
    episode_path = os.path.join(out_dir, f"{run_id}__episode.jsonl")

    cycle_records: list[dict[str, Any]] = []
    started = time.perf_counter()
    last_ack: dict[str, Any] | None = None

    reset_summary: dict[str, Any]
    if isinstance(reset_obs, dict):
        reset_summary = reset_obs
    else:
        reset_summary = {"observation_type": type(reset_obs).__name__}

    for step_index in range(config.max_steps):
        status_before = hal.status()

        if controller == "autonomy_v1":
            command = _robotic_autonomy_command_v1(status_before, config)
        else:
            scripted = _robotic_script_command_v1(controller, step_index)
            if scripted is None:
                break
            command = scripted

        ack_obj = hal.act(command)
        if hasattr(ack_obj, "to_dict"):
            ack = ack_obj.to_dict()
        elif isinstance(ack_obj, dict):
            ack = dict(ack_obj)
        else:
            ack = {"ok": False, "command": command, "error": str(ack_obj)}
        last_ack = ack

        status_after = hal.status()
        state_after = _robotic_state_from_status_v1(status_after)
        summary_after = _robotic_summary_from_status_v1(status_after)

        rec = {
            "schema": "rcos_robotic_cycle_record_v1",
            "record_type": "cycle",
            "run_id": run_id,
            "controller_id": controller,
            "seed": seed,
            "step_index": int(step_index),
            "command": command,
            "ack": ack,
            "state": state_after,
            "summary": summary_after,
            "milestones": {
                "recovered": str(state_after.get("posture")) != "fallen",
                "target_inspected": bool(summary_after.get("target_inspected")),
                "returned_to_dock": bool(summary_after.get("at_dock")) and bool(summary_after.get("target_inspected")),
                "recharged": int(summary_after.get("recharge_count", state_after.get("recharge_count", 0)) or 0) > 0,
                "rested": int(summary_after.get("rest_count", state_after.get("rest_count", 0)) or 0) > 0,
            },
        }
        cycle_records.append(rec)
        if write_jsonl:
            _append_jsonl_v1(cycle_path, rec)

        if bool(summary_after.get("success") or summary_after.get("mission_complete")):
            break
        if str(summary_after.get("done_reason")) in ("battery_empty", "emergency_stop"):
            break

    latency_ms_total = (time.perf_counter() - started) * 1000.0
    final_status = hal.status()
    final_state = _robotic_state_from_status_v1(final_status)
    final_summary = _robotic_summary_from_status_v1(final_status)

    milestone_vector = {
        "recovered": str(final_state.get("posture")) != "fallen",
        "target_inspected": bool(final_summary.get("target_inspected")),
        "returned_to_dock": bool(final_summary.get("at_dock")) and bool(final_summary.get("target_inspected")),
        "recharged": int(final_summary.get("recharge_count", final_state.get("recharge_count", 0)) or 0) > 0,
        "rested": int(final_summary.get("rest_count", final_state.get("rest_count", 0)) or 0) > 0,
    }
    milestone_score = sum(1 for name in RCOS_ROBOTIC_TASK_ORDER_V1 if bool(milestone_vector.get(name))) / float(len(RCOS_ROBOTIC_TASK_ORDER_V1))

    success = bool(final_summary.get("success") or final_summary.get("mission_complete") or final_state.get("mission_complete"))
    success = success and all(bool(milestone_vector.get(name)) for name in RCOS_ROBOTIC_TASK_ORDER_V1)
    falls = int(final_summary.get("falls", 0) or 0)
    safety_violations = int(final_summary.get("safety_violations", 0) or 0)
    target_inspected = bool(final_summary.get("target_inspected"))
    returned_to_dock = bool(milestone_vector.get("returned_to_dock"))

    if controller == "hazard_negative_control":
        expected_outcome_met = (not success) and falls > 0 and safety_violations > 0
        expected_success = False
    elif controller == "incomplete_no_return_control":
        expected_outcome_met = (not success) and target_inspected and not returned_to_dock
        expected_success = False
    else:
        expected_outcome_met = success
        expected_success = True

    episode_record = {
        "schema": "rcos_robotic_episode_record_v1",
        "record_type": "episode_summary",
        "run_id": run_id,
        "controller_id": controller,
        "seed": seed,
        "expected_success": expected_success,
        "expected_outcome_met": bool(expected_outcome_met),
        "success": bool(success),
        "steps": int(len(cycle_records)),
        "max_steps": int(config.max_steps),
        "milestone_vector": milestone_vector,
        "milestone_score": float(milestone_score),
        "falls": falls,
        "safety_violations": safety_violations,
        "repeated_action_loop_count": int(final_summary.get("repeated_action_loop_count", 0) or 0),
        "battery_final": float(final_state.get("battery", 0.0) or 0.0),
        "fatigue_final": float(final_state.get("fatigue", 0.0) or 0.0),
        "target_inspected": target_inspected,
        "returned_to_dock": returned_to_dock,
        "recharge_count": int(final_summary.get("recharge_count", final_state.get("recharge_count", 0)) or 0),
        "rest_count": int(final_summary.get("rest_count", final_state.get("rest_count", 0)) or 0),
        "final_posture": final_state.get("posture"),
        "done_reason": final_summary.get("done_reason"),
        "last_ack": last_ack,
        "latency_ms_total": round(float(latency_ms_total), 3),
        "reset_observation_summary": reset_summary,
    }
    if write_jsonl:
        _append_jsonl_v1(episode_path, episode_record)

    return {
        "ok": True,
        "run_id": run_id,
        "controller_id": controller,
        "seed": seed,
        "cycle_json_path": cycle_path if write_jsonl else None,
        "episode_json_path": episode_path if write_jsonl else None,
        "cycle_records": cycle_records,
        "episode_record": episode_record,
    }


def render_rcos_robotic_episode_lines_v1(result: dict[str, Any]) -> list[str]:
    """Return terminal summary lines for one RCOS robotic episode result."""
    if not isinstance(result, dict):
        return ["[rcos-exp] result          : (invalid)"]
    if not bool(result.get("ok")):
        return [f"[rcos-exp] run failed      : {_metric_text_v1(result.get('why'))}"]

    rec = result.get("episode_record")
    rec = rec if isinstance(rec, dict) else {}

    return [
        f"[rcos-exp] run_id          : {_metric_text_v1(result.get('run_id'))}",
        f"[rcos-exp] controller      : {_metric_text_v1(result.get('controller_id'))}",
        f"[rcos-exp] seed            : {_metric_text_v1(result.get('seed'))}",
        f"[rcos-exp] success         : {_metric_text_v1(rec.get('success'))}",
        f"[rcos-exp] expected_ok     : {_metric_text_v1(rec.get('expected_outcome_met'))}",
        f"[rcos-exp] steps           : {_metric_text_v1(rec.get('steps'))}",
        f"[rcos-exp] milestones      : {_metric_text_v1(rec.get('milestone_vector'))}",
        f"[rcos-exp] milestone_score : {_metric_text_v1(rec.get('milestone_score'))}",
        f"[rcos-exp] safety/falls    : violations={_metric_text_v1(rec.get('safety_violations'))} falls={_metric_text_v1(rec.get('falls'))}",
        f"[rcos-exp] loops           : {_metric_text_v1(rec.get('repeated_action_loop_count'))}",
        f"[rcos-exp] battery/fatigue : battery={_metric_text_v1(rec.get('battery_final'))} fatigue={_metric_text_v1(rec.get('fatigue_final'))}",
        f"[rcos-exp] final           : posture={_metric_text_v1(rec.get('final_posture'))} reason={_metric_text_v1(rec.get('done_reason'))}",
        f"[rcos-exp] cycle_json_path : {_metric_text_v1(result.get('cycle_json_path'))}",
        f"[rcos-exp] episode_json    : {_metric_text_v1(result.get('episode_json_path'))}",
    ]


def rcos_robotic_run_suite_v1(
    *,
    seed: int | None = None,
    max_steps: int | None = None,
    output_dir: str = "testvalues",
    run_label: str = "",
    write_jsonl: bool = True,
) -> dict[str, Any]:
    """Run the robot-shaped success and control suite once."""
    results: list[dict[str, Any]] = []
    for controller_id in RCOS_ROBOTIC_SUITE_SCENARIOS_V1:
        results.append(
            rcos_robotic_run_episode_v1(
                controller_id=controller_id,
                seed=seed,
                max_steps=max_steps,
                output_dir=output_dir,
                run_label=run_label,
                write_jsonl=write_jsonl,
            )
        )

    ok_results = [item for item in results if isinstance(item, dict) and bool(item.get("ok"))]
    expected_ok = 0
    for item in ok_results:
        rec = item.get("episode_record")
        rec = rec if isinstance(rec, dict) else {}
        if bool(rec.get("expected_outcome_met")):
            expected_ok += 1

    return {
        "ok": True,
        "seed": seed,
        "scenario_count": int(len(results)),
        "ok_count": int(len(ok_results)),
        "expected_outcome_rate": expected_ok / float(len(ok_results)) if ok_results else None,
        "results": results,
    }


def render_rcos_robotic_suite_lines_v1(suite: dict[str, Any]) -> list[str]:
    """Return compact terminal summary lines for one RCOS robotic suite run."""
    if not isinstance(suite, dict) or not bool(suite.get("ok")):
        return [f"[rcos-exp] suite failed    : {_metric_text_v1(suite.get('why') if isinstance(suite, dict) else None)}"]

    lines = [
        f"[rcos-exp] suite seed      : {_metric_text_v1(suite.get('seed'))}",
        f"[rcos-exp] scenarios       : {_metric_text_v1(suite.get('scenario_count'))}",
        f"[rcos-exp] ok_count        : {_metric_text_v1(suite.get('ok_count'))}",
        f"[rcos-exp] expected_rate   : {_metric_text_v1(suite.get('expected_outcome_rate'))}",
    ]

    results = suite.get("results")
    results = results if isinstance(results, list) else []
    for item in results:
        if not isinstance(item, dict):
            continue
        rec = item.get("episode_record")
        rec = rec if isinstance(rec, dict) else {}
        lines.append(
            f"[rcos-exp]   {item.get('controller_id')}: success={_metric_text_v1(rec.get('success'))} "
            f"expected_ok={_metric_text_v1(rec.get('expected_outcome_met'))} score={_metric_text_v1(rec.get('milestone_score'))} "
            f"steps={_metric_text_v1(rec.get('steps'))} safety={_metric_text_v1(rec.get('safety_violations'))} "
            f"falls={_metric_text_v1(rec.get('falls'))} reason={_metric_text_v1(rec.get('done_reason'))}"
        )
    return lines


def rcos_robotic_run_repeats_v1(
    *,
    repeats: int = 20,
    max_steps: int | None = None,
    output_dir: str = "testvalues",
    run_label: str = "",
    write_jsonl: bool = True,
) -> dict[str, Any]:
    """Run repeated autonomy_v1 robot-shaped long-horizon episodes.

    This is intentionally narrower than the full suite. It gives the BICA paper a simple repeated metric for the robot-shaped
    task while keeping the negative controls as a separate one-shot suite.
    """
    try:
        repeat_count = int(repeats)
    except Exception:
        repeat_count = 20
    repeat_count = max(1, min(200, repeat_count))

    rng = random.SystemRandom()
    rows: list[dict[str, Any]] = []

    for repeat_index in range(1, repeat_count + 1):
        seed = int(rng.randrange(1, 999_999 + 1))
        result = rcos_robotic_run_episode_v1(
            controller_id="autonomy_v1",
            seed=seed,
            max_steps=max_steps,
            output_dir=output_dir,
            run_label=run_label,
            write_jsonl=write_jsonl,
        )
        rec = result.get("episode_record") if isinstance(result, dict) else None
        rec = rec if isinstance(rec, dict) else {}
        rows.append(
            {
                "repeat_index": int(repeat_index),
                "seed": int(seed),
                "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                "success": bool(rec.get("success")),
                "expected_outcome_met": bool(rec.get("expected_outcome_met")),
                "milestone_score": rec.get("milestone_score"),
                "steps": rec.get("steps"),
                "falls": rec.get("falls"),
                "safety_violations": rec.get("safety_violations"),
                "battery_final": rec.get("battery_final"),
                "run_id": result.get("run_id") if isinstance(result, dict) else None,
            }
        )

    success_vals = [1.0 if bool(row.get("success")) else 0.0 for row in rows if bool(row.get("ok"))]
    expected_vals = [1.0 if bool(row.get("expected_outcome_met")) else 0.0 for row in rows if bool(row.get("ok"))]
    scores = [float(row["milestone_score"]) for row in rows if isinstance(row.get("milestone_score"), (int, float))]
    steps = [float(row["steps"]) for row in rows if isinstance(row.get("steps"), (int, float))]
    safety = [float(row["safety_violations"]) for row in rows if isinstance(row.get("safety_violations"), (int, float))]

    def _mean(nums: list[float]) -> float | None:
        return sum(nums) / float(len(nums)) if nums else None

    return {
        "ok": True,
        "controller_id": "autonomy_v1",
        "repeats": int(repeat_count),
        "ok_count": int(sum(1 for row in rows if bool(row.get("ok")))),
        "success_rate": _mean(success_vals),
        "expected_outcome_rate": _mean(expected_vals),
        "mean_milestone_score": _mean(scores),
        "mean_steps": _mean(steps),
        "mean_safety_violations": _mean(safety),
        "rows": rows,
    }


def render_rcos_robotic_repeats_lines_v1(result: dict[str, Any]) -> list[str]:
    """Return terminal lines for repeated autonomy_v1 RCOS robotic episodes."""
    if not isinstance(result, dict) or not bool(result.get("ok")):
        return [f"[rcos-exp] repeats failed  : {_metric_text_v1(result.get('why') if isinstance(result, dict) else None)}"]

    lines = [
        f"[rcos-exp] repeats         : {_metric_text_v1(result.get('repeats'))}",
        f"[rcos-exp] ok_count        : {_metric_text_v1(result.get('ok_count'))}",
        f"[rcos-exp] success_rate    : {_metric_text_v1(result.get('success_rate'))}",
        f"[rcos-exp] expected_rate   : {_metric_text_v1(result.get('expected_outcome_rate'))}",
        f"[rcos-exp] mean_score      : {_metric_text_v1(result.get('mean_milestone_score'))}",
        f"[rcos-exp] mean_steps      : {_metric_text_v1(result.get('mean_steps'))}",
        f"[rcos-exp] mean_safety     : {_metric_text_v1(result.get('mean_safety_violations'))}",
    ]

    rows = result.get("rows")
    rows = rows if isinstance(rows, list) else []
    lines.append("[rcos-exp] first repeats:")
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"[rcos-exp]   repeat={_metric_text_v1(row.get('repeat_index'))} seed={_metric_text_v1(row.get('seed'))} "
            f"success={_metric_text_v1(row.get('success'))} score={_metric_text_v1(row.get('milestone_score'))} "
            f"steps={_metric_text_v1(row.get('steps'))} safety={_metric_text_v1(row.get('safety_violations'))}"
        )
    if len(rows) > 8:
        lines.append(f"[rcos-exp]   ... plus {len(rows) - 8} more repeat row(s)")
    return lines

# -----------------------------------------------------------------------------
# Perturbed RCOS robotic benchmark
# -----------------------------------------------------------------------------


def _wilson_ci95_v1(successes: int, total: int) -> tuple[float | None, float | None]:
    """Return the Wilson 95% confidence interval for a binomial success proportion.

    This is useful for paper-facing repeated success-rate reporting. It is more
    informative than reporting only a raw percentage, especially when the observed
    rate is near 0% or 100%.
    """
    n = int(total)
    if n <= 0:
        return None, None

    k = max(0, min(int(successes), n))
    z = 1.959963984540054
    phat = float(k) / float(n)
    denom = 1.0 + (z * z / float(n))
    centre = phat + (z * z / (2.0 * float(n)))
    margin = z * ((phat * (1.0 - phat) + (z * z / (4.0 * float(n)))) / float(n)) ** 0.5

    low = (centre - margin) / denom
    high = (centre + margin) / denom
    return max(0.0, float(low)), min(1.0, float(high))


def _mean_numeric_v1(values: list[Any]) -> float | None:
    """Return the arithmetic mean of numeric values, ignoring bools and non-numeric items."""
    nums: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            nums.append(float(value))

    if not nums:
        return None
    return sum(nums) / float(len(nums))


def _perturb_params_v1(intensity: str) -> dict[str, Any]:
    """Return seed-dependent perturbation parameters for one named stress level.

    The perturbation benchmark keeps the original deterministic task intact, but
    adds controlled stochastic stressors so repeated seeds produce different
    episodes and more informative metrics.
    """
    label = str(intensity or "moderate").strip().lower()
    if label not in ("mild", "moderate", "severe"):
        label = "moderate"

    if label == "mild":
        return {
            "intensity": "mild",
            "action_noop_prob": 0.04,
            "fall_prob": 0.01,
            "blackout_start_prob": 0.03,
            "blackout_duration": 2,
            "target_occlusion_prob": 0.10,
            "extra_obstacles": 0,
            "battery_cost_scale": 1.15,
            "environmental_battery_drain": 0.002,
            "environmental_fatigue_gain": 0.002,
        }

    if label == "severe":
        return {
            "intensity": "severe",
            "action_noop_prob": 0.22,
            "fall_prob": 0.08,
            "blackout_start_prob": 0.12,
            "blackout_duration": 4,
            "target_occlusion_prob": 0.40,
            "extra_obstacles": 2,
            "battery_cost_scale": 2.00,
            "environmental_battery_drain": 0.010,
            "environmental_fatigue_gain": 0.008,
        }

    return {
        "intensity": "moderate",
        "action_noop_prob": 0.12,
        "fall_prob": 0.04,
        "blackout_start_prob": 0.07,
        "blackout_duration": 3,
        "target_occlusion_prob": 0.25,
        "extra_obstacles": 1,
        "battery_cost_scale": 1.55,
        "environmental_battery_drain": 0.005,
        "environmental_fatigue_gain": 0.004,
    }


def _apply_battery_pressure_v1(config: SimRobotGoatConfig, params: dict[str, Any]) -> None:
    """Scale selected battery/fatigue costs in-place for perturbation episodes."""
    try:
        scale = float(params.get("battery_cost_scale", 1.0) or 1.0)
    except Exception:
        scale = 1.0

    scale = max(0.25, min(5.0, scale))

    for name in (
        "battery_walk_cost",
        "battery_turn_cost",
        "battery_stand_cost",
        "battery_inspect_cost",
        "battery_rest_cost",
    ):
        try:
            setattr(config, name, float(getattr(config, name)) * scale)
        except Exception:
            pass


def _perturb_obstacle_candidates_v1(config: SimRobotGoatConfig) -> list[tuple[int, int]]:
    """Return safe candidate cells for seed-dependent obstacle insertion."""
    protected = {
        tuple(config.start_pos),
        tuple(config.dock_pos),
        tuple(config.target_pos),
    }
    protected.update(set(config.hazard_cells))

    out: list[tuple[int, int]] = []
    for y in range(int(config.grid_h)):
        for x in range(int(config.grid_w)):
            pos = (x, y)
            if pos in protected:
                continue
            if pos in config.obstacle_cells:
                continue
            out.append(pos)
    return out


def _add_seeded_obstacles_v1(config: SimRobotGoatConfig, rng: random.Random, *, count: int) -> list[tuple[int, int]]:
    """Add up to count seed-dependent obstacles while preserving a route to target and dock."""
    added: list[tuple[int, int]] = []
    candidates = _perturb_obstacle_candidates_v1(config)
    rng.shuffle(candidates)

    for pos in candidates:
        if len(added) >= max(0, int(count)):
            break

        before = set(config.obstacle_cells)
        config.obstacle_cells = set(before)
        config.obstacle_cells.add(pos)

        start_to_target = _robotic_shortest_path_v1(tuple(config.start_pos), tuple(config.target_pos), config)
        target_to_dock = _robotic_shortest_path_v1(tuple(config.target_pos), tuple(config.dock_pos), config)

        if len(start_to_target) >= 2 and len(target_to_dock) >= 2:
            added.append(pos)
        else:
            config.obstacle_cells = before

    return added


def _status_for_blackout_v1(current_status: dict[str, Any], last_visible_status: dict[str, Any] | None) -> dict[str, Any]:
    """Return the status packet used for control during a temporary sensor blackout.

    During blackout we use the last visible status as a simple stale-memory proxy.
    This makes perturbations meaningful without replacing the controller with a
    full CCA8 memory/action bridge in this patch.
    """
    if isinstance(last_visible_status, dict) and last_visible_status:
        return dict(last_visible_status)
    return dict(current_status)


def _fake_ack_v1(command: str, *, status: str, note: str) -> dict[str, Any]:
    """Return a JSON-safe action acknowledgement for perturbation-induced non-execution."""
    return {
        "command": str(command),
        "ok": False,
        "status": str(status),
        "note": str(note),
        "changed": False,
        "reward": 0.0,
        "new_milestones": [],
    }


def _apply_environmental_pressure_v1(hal: SimRobotGoatHAL, params: dict[str, Any]) -> None:
    """Apply per-cycle battery/fatigue pressure after the action step."""
    state_obj = getattr(getattr(hal, "env", None), "state", None)
    if state_obj is None:
        return

    try:
        drain = float(params.get("environmental_battery_drain", 0.0) or 0.0)
        state_obj.battery = max(0.0, float(state_obj.battery) - max(0.0, drain))
    except Exception:
        pass

    try:
        gain = float(params.get("environmental_fatigue_gain", 0.0) or 0.0)
        state_obj.fatigue = min(1.0, float(state_obj.fatigue) + max(0.0, gain))
    except Exception:
        pass

    try:
        if float(state_obj.battery) <= 0.0:
            state_obj.done_reason = "battery_empty"
    except Exception:
        pass


def _apply_random_fall_v1(hal: SimRobotGoatHAL) -> bool:
    """Force a recoverable fall in the simulated body, returning True if applied."""
    state_obj = getattr(getattr(hal, "env", None), "state", None)
    if state_obj is None:
        return False

    try:
        if bool(getattr(state_obj, "mission_complete", False)):
            return False
        if str(getattr(state_obj, "posture", "")) == "fallen":
            return False

        state_obj.posture = "fallen"
        state_obj.falls = int(getattr(state_obj, "falls", 0) or 0) + 1
        return True
    except Exception:
        return False


def _failure_reason_v1(episode_record: dict[str, Any]) -> str:
    """Return a compact failure reason for perturbed episode summaries."""
    if bool(episode_record.get("success")):
        return "success"

    done_reason = episode_record.get("done_reason")
    if isinstance(done_reason, str) and done_reason and done_reason != "in_progress":
        return done_reason

    milestones = episode_record.get("milestone_vector")
    milestones = milestones if isinstance(milestones, dict) else {}

    for name in RCOS_ROBOTIC_TASK_ORDER_V1:
        if not bool(milestones.get(name)):
            return f"missing:{name}"

    return "unknown_failure"


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def rcos_robotic_run_perturbed_episode_v1(
    *,
    seed: int,
    intensity: str = "moderate",
    max_steps: int | None = None,
    output_dir: str = "testvalues",
    run_label: str = "",
    write_jsonl: bool = True,
) -> dict[str, Any]:
    """Run one perturbed SimRobotGoat episode.

    The task is the same long-horizon sequence as the baseline RCOS robotic
    benchmark, but the episode can now include seed-dependent perturbations:
    action no-ops, brief sensor blackouts, target occlusion, random falls,
    battery pressure, and added obstacles.
    """
    params = _perturb_params_v1(intensity)
    rng = random.Random(int(seed))

    config = SimRobotGoatConfig()
    try:
        config.battery_walk_cost = 0.025
        config.battery_turn_cost = 0.005
    except Exception:
        pass

    _apply_battery_pressure_v1(config, params)
    added_obstacles = _add_seeded_obstacles_v1(config, rng, count=int(params.get("extra_obstacles", 0) or 0))

    step_cap = int(max_steps) if isinstance(max_steps, int) and max_steps > 0 else int(getattr(config, "max_steps", 80) or 80)
    config.max_steps = max(1, min(100000, step_cap))

    hal = SimRobotGoatHAL(env=SimRobotGoatEnv(config=config))
    reset_obs = hal.reset(seed=int(seed))

    run_id = _make_run_id_v1(
        controller_id=f"perturbed_{params['intensity']}",
        seed=int(seed),
        run_label=run_label or "bica_rcos_perturbed",
    )
    out_dir = os.path.normpath(str(output_dir or "testvalues"))
    cycle_path = os.path.join(out_dir, f"{run_id}__cycle.jsonl")
    episode_path = os.path.join(out_dir, f"{run_id}__episode.jsonl")

    reset_summary: dict[str, Any]
    if isinstance(reset_obs, dict):
        reset_summary = dict(reset_obs)
    else:
        reset_summary = {"observation_type": type(reset_obs).__name__}

    cycle_records: list[dict[str, Any]] = []
    last_visible_status: dict[str, Any] | None = None
    blackout_remaining = 0
    last_ack: dict[str, Any] | None = None
    started = time.perf_counter()

    perturb_counts = {
        "action_noop": 0,
        "sensor_blackout_cycles": 0,
        "target_occlusion": 0,
        "random_fall": 0,
        "added_obstacles": int(len(added_obstacles)),
    }

    for cycle_index in range(config.max_steps):
        current_status = hal.status()
        current_summary = _robotic_summary_from_status_v1(current_status)

        if bool(current_summary.get("success") or current_summary.get("mission_complete")):
            break
        if str(current_summary.get("done_reason")) in ("battery_empty", "emergency_stop"):
            break

        if blackout_remaining <= 0 and rng.random() < float(params.get("blackout_start_prob", 0.0) or 0.0):
            blackout_remaining = int(params.get("blackout_duration", 1) or 1)

        blackout_active = blackout_remaining > 0
        if blackout_active:
            perturb_counts["sensor_blackout_cycles"] += 1
            control_status = _status_for_blackout_v1(current_status, last_visible_status)
            blackout_remaining -= 1
        else:
            control_status = dict(current_status)
            last_visible_status = dict(current_status)

        command = _robotic_autonomy_command_v1(control_status, config)
        perturb_events: list[str] = []

        if command == "inspect" and rng.random() < float(params.get("target_occlusion_prob", 0.0) or 0.0):
            ack = _fake_ack_v1(command, status="target_occluded", note="temporary target occlusion prevented inspection")
            perturb_counts["target_occlusion"] += 1
            perturb_events.append("target_occlusion")
        elif rng.random() < float(params.get("action_noop_prob", 0.0) or 0.0):
            ack = _fake_ack_v1(command, status="action_noop", note="stochastic action failure; command did not execute")
            perturb_counts["action_noop"] += 1
            perturb_events.append("action_noop")
        else:
            ack_obj = hal.act(command)
            if hasattr(ack_obj, "to_dict"):
                ack = ack_obj.to_dict()
            elif isinstance(ack_obj, dict):
                ack = dict(ack_obj)
            else:
                ack = {"ok": False, "command": command, "error": str(ack_obj)}

        last_ack = dict(ack)

        if rng.random() < float(params.get("fall_prob", 0.0) or 0.0):
            if _apply_random_fall_v1(hal):
                perturb_counts["random_fall"] += 1
                perturb_events.append("random_fall")

        _apply_environmental_pressure_v1(hal, params)

        status_after = hal.status()
        state_after = _robotic_state_from_status_v1(status_after)
        summary_after = _robotic_summary_from_status_v1(status_after)

        rec = {
            "schema": "rcos_robotic_perturbed_cycle_record_v1",
            "record_type": "cycle",
            "run_id": run_id,
            "controller_id": "autonomous_task_selection_perturbed",
            "seed": int(seed),
            "intensity": str(params["intensity"]),
            "cycle_index": int(cycle_index),
            "env_step_index": int(state_after.get("step_index", 0) or 0),
            "sensor_blackout": bool(blackout_active),
            "command": command,
            "ack": ack,
            "perturb_events": list(perturb_events),
            "state": state_after,
            "summary": summary_after,
            "milestones": {
                "recovered": str(state_after.get("posture")) != "fallen",
                "target_inspected": bool(summary_after.get("target_inspected")),
                "returned_to_dock": bool(summary_after.get("at_dock")) and bool(summary_after.get("target_inspected")),
                "recharged": int(summary_after.get("recharge_count", state_after.get("recharge_count", 0)) or 0) > 0,
                "rested": int(summary_after.get("rest_count", state_after.get("rest_count", 0)) or 0) > 0,
            },
        }
        cycle_records.append(rec)
        if write_jsonl:
            _append_jsonl_v1(cycle_path, rec)

        if bool(summary_after.get("success") or summary_after.get("mission_complete")):
            break
        if str(summary_after.get("done_reason")) in ("battery_empty", "emergency_stop"):
            break

    latency_ms_total = (time.perf_counter() - started) * 1000.0
    final_status = hal.status()
    final_state = _robotic_state_from_status_v1(final_status)
    final_summary = _robotic_summary_from_status_v1(final_status)

    milestone_vector = {
        "recovered": str(final_state.get("posture")) != "fallen",
        "target_inspected": bool(final_summary.get("target_inspected")),
        "returned_to_dock": bool(final_summary.get("at_dock")) and bool(final_summary.get("target_inspected")),
        "recharged": int(final_summary.get("recharge_count", final_state.get("recharge_count", 0)) or 0) > 0,
        "rested": int(final_summary.get("rest_count", final_state.get("rest_count", 0)) or 0) > 0,
    }
    milestone_score = sum(1 for name in RCOS_ROBOTIC_TASK_ORDER_V1 if bool(milestone_vector.get(name))) / float(len(RCOS_ROBOTIC_TASK_ORDER_V1))

    success = bool(final_summary.get("success") or final_summary.get("mission_complete") or final_state.get("mission_complete"))
    success = success and all(bool(milestone_vector.get(name)) for name in RCOS_ROBOTIC_TASK_ORDER_V1)
    failure_reason = "success" if success else _failure_reason_v1(
        {
            "success": success,
            "done_reason": final_summary.get("done_reason"),
            "milestone_vector": milestone_vector,
        }
    )

    episode_record = {
        "schema": "rcos_robotic_perturbed_episode_record_v1",
        "record_type": "episode_summary",
        "run_id": run_id,
        "controller_id": "autonomous_task_selection_perturbed",
        "seed": int(seed),
        "intensity": str(params["intensity"]),
        "success": bool(success),
        "failure_reason": failure_reason,
        "cycles": int(len(cycle_records)),
        "env_steps": int(final_state.get("step_index", 0) or 0),
        "max_cycles": int(config.max_steps),
        "milestone_vector": milestone_vector,
        "milestone_score": float(milestone_score),
        "falls": int(final_summary.get("falls", 0) or 0),
        "safety_violations": int(final_summary.get("safety_violations", 0) or 0),
        "repeated_action_loop_count": int(final_summary.get("repeated_action_loop_count", 0) or 0),
        "battery_final": float(final_state.get("battery", 0.0) or 0.0),
        "fatigue_final": float(final_state.get("fatigue", 0.0) or 0.0),
        "target_inspected": bool(final_summary.get("target_inspected")),
        "returned_to_dock": bool(milestone_vector.get("returned_to_dock")),
        "recharge_count": int(final_summary.get("recharge_count", final_state.get("recharge_count", 0)) or 0),
        "rest_count": int(final_summary.get("rest_count", final_state.get("rest_count", 0)) or 0),
        "final_posture": final_state.get("posture"),
        "done_reason": final_summary.get("done_reason"),
        "last_ack": last_ack,
        "perturbation_params": dict(params),
        "perturbation_counts": dict(perturb_counts),
        "added_obstacles": [list(pos) for pos in added_obstacles],
        "latency_ms_total": round(float(latency_ms_total), 3),
        "reset_observation_summary": reset_summary,
    }

    if write_jsonl:
        _append_jsonl_v1(episode_path, episode_record)

    return {
        "ok": True,
        "run_id": run_id,
        "controller_id": "autonomous_task_selection_perturbed",
        "seed": int(seed),
        "intensity": str(params["intensity"]),
        "cycle_json_path": cycle_path if write_jsonl else None,
        "episode_json_path": episode_path if write_jsonl else None,
        "cycle_records": cycle_records,
        "episode_record": episode_record,
    }


def render_rcos_robotic_perturbation_protocol_v1() -> str:
    """Return a human-readable protocol summary for the perturbed RCOS benchmark."""
    lines = []
    lines.append("RCOS robotic perturbation benchmark v1")
    lines.append("")
    lines.append("Purpose:")
    lines.append("  Stress-test the same robot-shaped long-horizon task under seed-dependent perturbations.")
    lines.append("  This turns repeated runs into meaningful data rather than repeating one deterministic path.")
    lines.append("")
    lines.append("Task ladder:")
    for i, name in enumerate(RCOS_ROBOTIC_TASK_ORDER_V1, start=1):
        lines.append(f"  {i}) {name}")
    lines.append("")
    lines.append("Perturbation families:")
    lines.append("  - stochastic action no-op failures")
    lines.append("  - temporary sensor blackout using the last visible status as a stale-memory proxy")
    lines.append("  - temporary target occlusion during inspection")
    lines.append("  - random recoverable falls")
    lines.append("  - battery/resource pressure")
    lines.append("  - seed-dependent obstacle insertion while preserving a nominal path")
    lines.append("")
    lines.append("Intensity levels:")
    for label in ("mild", "moderate", "severe"):
        params = _perturb_params_v1(label)
        lines.append(
            f"  {label:<8} noop={params['action_noop_prob']:.2f} fall={params['fall_prob']:.2f} "
            f"blackout={params['blackout_start_prob']:.2f} occlusion={params['target_occlusion_prob']:.2f} "
            f"extra_obstacles={params['extra_obstacles']} battery_scale={params['battery_cost_scale']:.2f}"
        )
    lines.append("")
    lines.append("Reported metrics:")
    lines.append("  success_rate with Wilson 95% CI, mean milestone score, mean cycles, mean falls,")
    lines.append("  mean safety violations, mean final battery, perturbation counts, and failure reasons.")
    return "\n".join(lines)


def rcos_robotic_run_perturbed_repeats_v1(
    *,
    repeats: int = 50,
    intensity: str = "moderate",
    max_steps: int | None = None,
    output_dir: str = "testvalues",
    run_label: str = "",
    write_jsonl: bool = True,
) -> dict[str, Any]:
    """Run repeated perturbed autonomous RCOS robotic episodes."""
    try:
        repeat_count = int(repeats)
    except Exception:
        repeat_count = 50
    repeat_count = max(1, min(500, repeat_count))

    params = _perturb_params_v1(intensity)
    rng = random.SystemRandom()
    rows: list[dict[str, Any]] = []
    failure_reasons: dict[str, int] = {}
    perturb_totals: dict[str, int] = {
        "action_noop": 0,
        "sensor_blackout_cycles": 0,
        "target_occlusion": 0,
        "random_fall": 0,
        "added_obstacles": 0,
    }

    for repeat_index in range(1, repeat_count + 1):
        seed = int(rng.randrange(1, 999_999 + 1))
        result = rcos_robotic_run_perturbed_episode_v1(
            seed=seed,
            intensity=str(params["intensity"]),
            max_steps=max_steps,
            output_dir=output_dir,
            run_label=run_label or "bica_rcos_perturbed",
            write_jsonl=write_jsonl,
        )

        rec = result.get("episode_record") if isinstance(result, dict) else None
        rec = rec if isinstance(rec, dict) else {}

        reason = str(rec.get("failure_reason") or "unknown")
        failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        counts = rec.get("perturbation_counts")
        counts = counts if isinstance(counts, dict) else {}
        for key in perturb_totals:
            try:
                perturb_totals[key] += int(counts.get(key, 0) or 0)
            except Exception:
                pass

        rows.append(
            {
                "repeat_index": int(repeat_index),
                "seed": int(seed),
                "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                "success": bool(rec.get("success")),
                "failure_reason": reason,
                "milestone_score": rec.get("milestone_score"),
                "cycles": rec.get("cycles"),
                "env_steps": rec.get("env_steps"),
                "falls": rec.get("falls"),
                "safety_violations": rec.get("safety_violations"),
                "battery_final": rec.get("battery_final"),
                "perturbation_counts": counts,
                "run_id": result.get("run_id") if isinstance(result, dict) else None,
            }
        )

    ok_rows = [row for row in rows if bool(row.get("ok"))]
    success_count = sum(1 for row in ok_rows if bool(row.get("success")))
    ci_low, ci_high = _wilson_ci95_v1(success_count, len(ok_rows))

    scores = [row.get("milestone_score") for row in ok_rows]
    cycles = [row.get("cycles") for row in ok_rows]
    env_steps = [row.get("env_steps") for row in ok_rows]
    falls = [row.get("falls") for row in ok_rows]
    safety = [row.get("safety_violations") for row in ok_rows]
    battery = [row.get("battery_final") for row in ok_rows]

    return {
        "ok": True,
        "controller_id": "autonomous_task_selection_perturbed",
        "intensity": str(params["intensity"]),
        "repeats": int(repeat_count),
        "ok_count": int(len(ok_rows)),
        "success_count": int(success_count),
        "success_rate": (float(success_count) / float(len(ok_rows))) if ok_rows else None,
        "success_ci95_low": ci_low,
        "success_ci95_high": ci_high,
        "mean_milestone_score": _mean_numeric_v1(scores),
        "mean_cycles": _mean_numeric_v1(cycles),
        "mean_env_steps": _mean_numeric_v1(env_steps),
        "mean_falls": _mean_numeric_v1(falls),
        "mean_safety_violations": _mean_numeric_v1(safety),
        "mean_battery_final": _mean_numeric_v1(battery),
        "perturbation_params": dict(params),
        "perturbation_totals": perturb_totals,
        "failure_reasons": failure_reasons,
        "rows": rows,
    }


def render_rcos_robotic_perturbed_repeats_lines_v1(result: dict[str, Any]) -> list[str]:
    """Return terminal lines for repeated perturbed RCOS robotic episodes."""
    if not isinstance(result, dict) or not bool(result.get("ok")):
        return [f"[rcos-perturb] repeats failed: {_metric_text_v1(result.get('why') if isinstance(result, dict) else None)}"]

    ci_low = result.get("success_ci95_low")
    ci_high = result.get("success_ci95_high")
    if isinstance(ci_low, (int, float)) and isinstance(ci_high, (int, float)):
        ci_txt = f"[{float(ci_low):.3f}, {float(ci_high):.3f}]"
    else:
        ci_txt = "(none)"

    lines = [
        f"[rcos-perturb] intensity       : {_metric_text_v1(result.get('intensity'))}",
        f"[rcos-perturb] repeats         : {_metric_text_v1(result.get('repeats'))}",
        f"[rcos-perturb] ok_count        : {_metric_text_v1(result.get('ok_count'))}",
        f"[rcos-perturb] success_count   : {_metric_text_v1(result.get('success_count'))}",
        f"[rcos-perturb] success_rate    : {_metric_text_v1(result.get('success_rate'))}  Wilson95={ci_txt}",
        f"[rcos-perturb] mean_score      : {_metric_text_v1(result.get('mean_milestone_score'))}",
        f"[rcos-perturb] mean_cycles     : {_metric_text_v1(result.get('mean_cycles'))}",
        f"[rcos-perturb] mean_env_steps  : {_metric_text_v1(result.get('mean_env_steps'))}",
        f"[rcos-perturb] mean_falls      : {_metric_text_v1(result.get('mean_falls'))}",
        f"[rcos-perturb] mean_safety     : {_metric_text_v1(result.get('mean_safety_violations'))}",
        f"[rcos-perturb] mean_battery    : {_metric_text_v1(result.get('mean_battery_final'))}",
        f"[rcos-perturb] perturb_totals  : {_metric_text_v1(result.get('perturbation_totals'))}",
        f"[rcos-perturb] failure_reasons : {_metric_text_v1(result.get('failure_reasons'))}",
    ]

    rows = result.get("rows")
    rows = rows if isinstance(rows, list) else []
    lines.append("[rcos-perturb] first repeats:")
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"[rcos-perturb]   repeat={_metric_text_v1(row.get('repeat_index'))} "
            f"seed={_metric_text_v1(row.get('seed'))} success={_metric_text_v1(row.get('success'))} "
            f"score={_metric_text_v1(row.get('milestone_score'))} cycles={_metric_text_v1(row.get('cycles'))} "
            f"falls={_metric_text_v1(row.get('falls'))} safety={_metric_text_v1(row.get('safety_violations'))} "
            f"reason={_metric_text_v1(row.get('failure_reason'))}"
        )
    if len(rows) > 10:
        lines.append(f"[rcos-perturb]   ... plus {len(rows) - 10} more repeat row(s)")

    return lines
