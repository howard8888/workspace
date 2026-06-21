# -*- coding: utf-8 -*-
"""Autonomous newborn-goat survival loop regression test.

This is the next step after ``test_newborn_action_conditioned_env.py``.

The earlier test proved the environment-side contract:

    scripted correct actions -> hard newborn environment completes the survival ladder

This test asks a stronger question:

    CCA8 closed-loop policy selection -> hard newborn environment completes the survival ladder

The test intentionally uses the same closed-loop engine as Menu 37, but suppresses
terminal output so pytest remains readable. It does not script the actions. The
only actions fed into ``HybridEnvironment.step(...)`` are whatever CCA8 selected
on the previous cognitive cycle.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from typing import Any

from cca8_run import (
    experiment_configure_benchmark_runtime_v1,
    experiment_make_sandbox_runtime_v1,
    run_env_closed_loop_steps,
)


REQUIRED_NEWBORN_MILESTONES = (
    "stood_up",
    "reached_mom",
    "found_nipple",
    "latched_nipple",
    "milk_drinking",
    "rested",
)


def _as_string_list(value: Any) -> list[str]:
    """Return a normalized list of non-empty strings from a scalar/list milestone field."""
    if isinstance(value, str) and value:
        return [value]

    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            out.append(item)
    return out


def _policy_trace_from_output(text: str) -> list[str]:
    """Extract policy names from the captured Menu-37-style terminal output."""
    out: list[str] = []

    for line in text.splitlines():
        if "[env→controller]" not in line:
            continue

        tail = line.split("[env→controller]", 1)[1].strip()
        if not tail:
            continue

        first = tail.split(maxsplit=1)[0].strip()
        if first.startswith("policy:"):
            out.append(first)

    return out


def _observed_milestones_from_ctx(ctx: Any) -> list[str]:
    """Collect milestone labels from in-memory cycle JSON records, if available."""
    out: list[str] = []

    records = getattr(ctx, "cycle_json_records", None)
    if not isinstance(records, list):
        return out

    for record in records:
        if not isinstance(record, dict):
            continue

        obs = record.get("obs")
        obs = obs if isinstance(obs, dict) else {}

        env_meta = obs.get("env_meta")
        env_meta = env_meta if isinstance(env_meta, dict) else {}

        raw = env_meta.get("milestones")
        if raw is None:
            raw = env_meta.get("milestone")

        out.extend(_as_string_list(raw))

    return out


def _final_state_summary(state: Any) -> dict[str, Any]:
    """Return a compact JSON-safe summary of the final EnvState."""
    return {
        "stage": getattr(state, "scenario_stage", None),
        "posture": getattr(state, "kid_posture", None),
        "mom_distance": getattr(state, "mom_distance", None),
        "nipple_state": getattr(state, "nipple_state", None),
        "shelter_distance": getattr(state, "shelter_distance", None),
        "cliff_distance": getattr(state, "cliff_distance", None),
        "position": getattr(state, "position", None),
        "zone": getattr(state, "zone", None),
        "milestones": list(getattr(state, "milestones", []) or []),
        "stand_attempts": int(getattr(state, "newborn_stand_attempts", 0) or 0),
        "follow_attempts": int(getattr(state, "newborn_follow_attempts", 0) or 0),
        "seek_attempts": int(getattr(state, "newborn_seek_attempts", 0) or 0),
        "rest_attempts": int(getattr(state, "newborn_rest_attempts", 0) or 0),
        "milk_ticks": int(getattr(state, "newborn_milk_ticks", 0) or 0),
        "setbacks": int(getattr(state, "newborn_setback_count", 0) or 0),
        "step_index": int(getattr(state, "step_index", 0) or 0),
    }


def _run_autonomous_newborn_episode(max_cycles: int = 60) -> dict[str, Any]:
    """Run one hard-mode newborn episode using CCA8's own policy loop."""
    sandbox = experiment_make_sandbox_runtime_v1()

    world = sandbox["world"]
    drives = sandbox["drives"]
    ctx = sandbox["ctx"]
    env = sandbox["env"]
    policy_rt = sandbox["policy_rt"]

    setup = experiment_configure_benchmark_runtime_v1(
        world,
        drives,
        ctx,
        env,
        "newborn_long_horizon",
    )
    assert bool(setup.get("ok")), setup

    # This test isolates ordinary autonomous current-state control.
    # It is not testing route-loss or episodic-readback stress; those belong to Menu 49 benchmarks.
    ctx.obs_mask_prob = 0.0
    ctx.obs_mask_verbose = False
    ctx.obs_mask_seed = 123
    ctx.obs_mask_last_cfg_sig = None
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    ctx.cycle_json_records = []
    ctx.experiment_newborn_require_resume_memory = False
    ctx.experiment_newborn_blackout_start_step = -1
    ctx.experiment_newborn_blackout_until_step = -1
    ctx.experiment_newborn_blackout_reason = None

    # Keep the normal newborn sandbox drive profile. The controller should now be able
    # to bridge the survival sequence without requiring us to script actions by hand.
    drives.hunger = 0.50
    drives.fatigue = 0.30
    drives.warmth = 0.60

    try:
        policy_rt.refresh_loaded(ctx)
    except Exception:
        pass

    capture = StringIO()
    with redirect_stdout(capture):
        run_env_closed_loop_steps(env, world, drives, ctx, policy_rt, int(max_cycles))

    output = capture.getvalue()
    state = env.state
    final_state = _final_state_summary(state)

    observed_milestones = set(_observed_milestones_from_ctx(ctx))
    observed_milestones.update(_as_string_list(final_state.get("milestones")))

    missing_milestones = [
        milestone for milestone in REQUIRED_NEWBORN_MILESTONES
        if milestone not in observed_milestones
    ]

    policy_trace = _policy_trace_from_output(output)
    policy_counts = {name: policy_trace.count(name) for name in sorted(set(policy_trace))}

    stand_actions = policy_counts.get("policy:stand_up", 0) + policy_counts.get("policy:recover_fall", 0)

    final_rest_state = (
        final_state["stage"] == "rest"
        and final_state["posture"] == "resting"
        and final_state["mom_distance"] == "touching"
        and final_state["nipple_state"] == "latched"
        and final_state["shelter_distance"] == "near"
        and final_state["cliff_distance"] == "far"
    )

    required_policy_evidence = (
        stand_actions >= 2
        and policy_counts.get("policy:follow_mom", 0) >= 2
        and policy_counts.get("policy:seek_nipple", 0) >= 2
        and policy_counts.get("policy:rest", 0) >= 1
    )

    return {
        "success": bool(final_rest_state and not missing_milestones and required_policy_evidence),
        "final_rest_state": bool(final_rest_state),
        "required_policy_evidence": bool(required_policy_evidence),
        "missing_milestones": missing_milestones,
        "observed_milestones": sorted(observed_milestones),
        "policy_counts": policy_counts,
        "policy_trace": policy_trace,
        "final_state": final_state,
        "output_tail": "\n".join(output.splitlines()[-80:]),
    }


def test_hard_newborn_autonomous_policy_loop_completes_survival_ladder() -> None:
    """CCA8 should autonomously drive the hard newborn environment to the resting/milk state."""
    result = _run_autonomous_newborn_episode(max_cycles=60)

    assert result["success"], (
        "Autonomous newborn survival loop did not complete.\n"
        f"final_rest_state={result['final_rest_state']}\n"
        f"required_policy_evidence={result['required_policy_evidence']}\n"
        f"missing_milestones={result['missing_milestones']}\n"
        f"observed_milestones={result['observed_milestones']}\n"
        f"policy_counts={result['policy_counts']}\n"
        f"final_state={result['final_state']}\n\n"
        f"Captured output tail:\n{result['output_tail']}"
    )