#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded synthetic ``EnvObservation`` injection for the CCA8 oscilloscope.

Purpose
-------
This module implements the first diagnostic signal-injection slice for Main
Menu #2. It introduces one source-stamped synthetic ``EnvObservation`` at the
DP01 sensor/adapter boundary, runs exactly one ordinary CCA8 cognitive cycle in
an isolated disposable sandbox, and returns the resulting DP00-DP18 scope
snapshot.

Safety and authority boundary
-----------------------------
The first implementation is deliberately narrow:

- injection is available only through a fresh disposable sandbox;
- no object from the live session is passed to the sandbox cycle;
- synthetic evidence is explicitly stamped ``synthetic_test_evidence``;
- the live WorldGraph, WorkingMap/WNM, environment, drives, and scope trace are
  not mutated;
- process-shared skill telemetry and Column memory are snapshotted and restored
  in ``finally`` before the result is returned;
- the sandbox is discarded after the diagnostic snapshot and optional terminal
  transcript are captured.

This is test instrumentation, not a new source of live cognitive authority.
The module does not provide arbitrary DP injection, live-state injection,
actuator injection, or a general scenario editor.
"""

from __future__ import annotations

# The diagnostic boundary must restore process-shared state even when a sandbox
# cycle fails. Defensive exception handling is therefore intentional here.
# pylint: disable=broad-exception-caught
# pylint: disable=protected-access
# pylint: disable=too-many-locals

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import random
from typing import Any, Callable, Mapping

import cca8_cognitive_scope
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, EnvState, HybridEnvironment, PerceptionAdapter
from cca8_observation_runtime import init_body_world
from cca8_working_memory import init_working_world
from cca8_world_graph import WorldGraph

__version__ = "0.1.0"

__all__ = [
    "CognitiveInjectionRuntimeV1",
    "build_fallen_near_cliff_injection_v1",
    "cognitive_injection_preset_rows_v1",
    "render_cognitive_injection_result_lines_v1",
    "render_cognitive_injection_transcript_lines_v1",
    "run_envobservation_injection_sandbox_v1",
    "__version__",
]

_PRESET_FALLEN_NEAR_CLIFF_V1 = "fallen_near_cliff_v1"
_TRANSCRIPT_LIMIT_V1 = 100_000


@dataclass(frozen=True, slots=True)
class CognitiveInjectionRuntimeV1:  # pylint: disable=too-few-public-methods
    """Runner-owned callbacks and shared stores required by the sandbox.

    The injection module intentionally does not import :mod:`cca8_run`. The
    composition root supplies the established closed-loop cycle function and a
    PolicyRuntime factory after all runner hooks have been configured.
    ``skill_store`` and ``column_memory`` are used only to preserve and
    restore process-shared diagnostic side effects exactly, including legacy
    skill-ledger records that may not round-trip through current serializers.
    """

    policy_runtime_factory: Callable[[], Any]
    run_closed_loop_steps: Callable[..., None]
    skill_store: dict[str, Any]
    column_memory: Any


def cognitive_injection_preset_rows_v1() -> tuple[dict[str, str], ...]:
    """Return the bounded preset catalog for the first injection controller."""
    return (
        {
            "preset_id": _PRESET_FALLEN_NEAR_CLIFF_V1,
            "label": "Fallen near a cliff; Mom and shelter far",
            "expected_path": "DP01 evidence -> BodyMap/WNM -> StandUp selection -> sandbox dispatch",
        },
    )


def _injection_metadata_v1(injection_id: str, preset_id: str) -> dict[str, Any]:
    """Return one compact provenance stamp copied into observation and trace."""
    return {
        "schema": "cognitive_scope_injection_metadata_v1",
        "injection_id": str(injection_id),
        "preset_id": str(preset_id),
        "boundary": "DP01",
        "source_class": "synthetic_test_evidence",
        "created_by": "main_menu_2_cognitive_scope",
        "sandbox_only": True,
        "live_session_authority": False,
        "arbitrary_dp_injection_allowed": False,
        "actuator_bypass_allowed": False,
    }


def build_fallen_near_cliff_injection_v1(injection_id: str) -> tuple[EnvState, EnvObservation, dict[str, Any]]:
    """Build the first deterministic synthetic state/observation pair.

    The external sandbox reference and the injected observation agree on the
    important scene relations. ``PerceptionAdapter`` creates the ordinary
    observation payload, NavPatch, and SurfaceGrid so the test enters CCA8 at
    the same DP01 contract used by real/simulated sensor packets. Two canonical
    fall cues and one numeric ``diagnostic_pulse`` channel make the signal easy
    to recognize during DP drill-down.
    """
    metadata = _injection_metadata_v1(injection_id, _PRESET_FALLEN_NEAR_CLIFF_V1)
    state = EnvState(
        kid_posture="fallen",
        mom_distance="far",
        shelter_distance="far",
        cliff_distance="near",
        nipple_state="hidden",
        scenario_stage="struggle",
        kid_position=(0.0, 0.0),
        mom_position=(1.25, 0.0),
        kid_fatigue=0.2,
        kid_temperature=0.6,
        time_since_birth=0.0,
        step_index=0,
        position="cliff_edge",
        zone="unsafe",
    )
    observation = PerceptionAdapter().observe(state, ctx=None)

    observation.raw_sensors = dict(observation.raw_sensors)
    observation.raw_sensors["diagnostic_pulse"] = 1.0

    observation.cues = list(observation.cues)
    for cue in ("vestibular:fall", "touch:flank_on_ground"):
        if cue not in observation.cues:
            observation.cues.append(cue)

    observation.env_meta = dict(observation.env_meta)
    observation.env_meta["source_class"] = "synthetic_test_evidence"
    observation.env_meta["diagnostic_injection_v1"] = deepcopy(metadata)
    for key in ("feeding_geometry_v1", "terrain_geometry_v1", "lower_motor_feedback_v1"):
        raw_product = observation.env_meta.get(key)
        if not isinstance(raw_product, Mapping):
            continue
        product = deepcopy(dict(raw_product))
        original_source_class = product.get("source_class")
        if original_source_class is not None:
            product["adapter_source_class_before_injection"] = original_source_class
        product["source_class"] = "synthetic_test_evidence"
        product["diagnostic_injection_id"] = str(injection_id)
        observation.env_meta[key] = product

    stamped_patches: list[dict[str, Any]] = []
    for raw_patch in observation.nav_patches:
        patch = deepcopy(raw_patch)
        patch_obs = patch.get("obs")
        patch_obs = dict(patch_obs) if isinstance(patch_obs, Mapping) else {}
        patch_obs["source_class"] = "synthetic_test_evidence"
        patch_obs["diagnostic_injection_id"] = str(injection_id)
        patch["obs"] = patch_obs
        stamped_patches.append(patch)
    observation.nav_patches = stamped_patches

    observation.surface_grid = deepcopy(observation.surface_grid)
    observation.surface_grid["source_class"] = "synthetic_test_evidence"
    observation.surface_grid["diagnostic_injection_id"] = str(injection_id)
    return state, observation, metadata


def _sandbox_context_v1() -> Ctx:
    """Construct a quiet, deterministic, one-cycle diagnostic context."""
    ctx = Ctx(age_days=0.0, ticks=0, profile="Mountain Goat")
    ctx.winners_k = 2
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.working_world = init_working_world()

    ctx.navpatch_enabled = True
    ctx.working_enabled = True
    ctx.working_verbose = False
    ctx.phase7_working_first = True
    ctx.wm_surfacegrid_enabled = True
    ctx.wm_surfacegrid_verbose = False
    ctx.wm_surfacegrid_ascii_each_tick = False

    ctx.longterm_obs_enabled = True
    ctx.longterm_obs_mode = "changes"
    ctx.longterm_obs_verbose = False
    ctx.longterm_obs_keyframe_log = False

    # Keep the first injection focused on one current signal path. Rich memory
    # retrieval and durable writeback have their own established tests and are
    # disabled here so the shared Column store remains observationally inert.
    ctx.wm_mapsurface_autoretrieve_enabled = False
    ctx.wm_mapsurface_autoretrieve_verbose = False
    ctx.navmap_memory_auto_consolidate_v1 = False
    ctx.navmap_memory_spontaneous_retrieval_v1 = False
    ctx.navmap_memory_spontaneous_ready_admission_v1 = False

    ctx.obs_mask_prob = 0.0
    ctx.rl_enabled = False
    ctx.rl_epsilon = 0.0
    ctx.efe_enabled = False
    ctx.cycle_json_enabled = False
    ctx.mini_snapshot = False
    ctx.env_loop_cycle_summary = False
    ctx.env_loop_legend_printed = True
    ctx.cognitive_scope_enabled_v1 = True
    ctx.cognitive_scope_capacity_v1 = 4
    return ctx


def _sandbox_world_v1() -> WorldGraph:
    """Construct the disposable sparse episode/index graph."""
    world = WorldGraph()
    world.set_stage("neonate")
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")
    world.ensure_anchor("NOW_ORIGIN")
    return world


def _install_pending_observation_v1(
    env: HybridEnvironment,
    ctx: Ctx,
    state: EnvState,
    observation: EnvObservation,
) -> None:
    """Place the synthetic packet on the established between-cycle I/O seam."""
    env._state = state.copy()
    env._episode_index = 1
    env._episode_steps = 0

    ctx.env_episode_started = True
    ctx.env_last_action = None
    ctx.env_pending_observation = observation
    ctx.env_pending_info = {
        "episode_index": 1,
        "step_index": 0,
        "scenario_name": "diagnostic_envobservation_injection_v1",
    }
    ctx.env_pending_reward = 0.0
    ctx.env_pending_done = False
    ctx.env_pending_previous_state = state.copy()
    ctx.navmap_pending_action_v1 = None
    ctx.navmap_pending_reward_v1 = 0.0


def _snapshot_process_shared_state_v1(runtime: CognitiveInjectionRuntimeV1) -> tuple[dict[str, Any], dict[str, Any], tuple[Any, ...]]:
    """Copy process-shared skills, Column records, and RNG state for rollback."""
    column_store = getattr(runtime.column_memory, "_store", None)
    if not isinstance(column_store, dict):
        raise RuntimeError("The configured ColumnMemory does not expose the expected in-memory store.")
    return deepcopy(runtime.skill_store), deepcopy(column_store), random.getstate()


def _restore_process_shared_state_v1(
    runtime: CognitiveInjectionRuntimeV1,
    skills_before: dict[str, Any],
    columns_before: dict[str, Any],
    random_state_before: tuple[Any, ...],
) -> dict[str, Any]:
    """Restore process-shared state and return an explicit rollback report."""
    report: dict[str, Any] = {
        "skills_restored": False,
        "columns_restored": False,
        "random_state_restored": False,
        "error": None,
    }
    try:
        runtime.skill_store.clear()
        runtime.skill_store.update(deepcopy(skills_before))
        report["skills_restored"] = runtime.skill_store == skills_before

        column_store = getattr(runtime.column_memory, "_store", None)
        if not isinstance(column_store, dict):
            raise RuntimeError("The configured ColumnMemory store disappeared during rollback.")
        column_store.clear()
        column_store.update(deepcopy(columns_before))
        report["columns_restored"] = column_store == columns_before

        random.setstate(random_state_before)
        report["random_state_restored"] = True
    except Exception as exc:  # pragma: no cover - defensive boundary
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def _annotate_injection_snapshot_v1(snapshot: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe injected-sandbox copy of one ordinary scope snapshot."""
    out = deepcopy(dict(snapshot))
    out["capture_kind"] = "synthetic_envobservation_injection_v1"
    out["injection_enabled"] = True
    out["sandbox_injection_available"] = True
    out["live_injection_enabled"] = False
    out["sandbox_injection"] = deepcopy(dict(metadata))
    out["sandbox_only"] = True
    out["live_cognitive_state_mutated"] = False
    out["sandbox_discarded_after_capture"] = True

    ports = out.get("ports")
    if isinstance(ports, list):
        for row in ports:
            if not isinstance(row, dict):
                continue
            if row.get("port_id") == "DP00":
                row["note"] = "Synthetic matching world reference inside the disposable diagnostic sandbox; not the live world."
            elif row.get("port_id") == "DP01":
                row["authority"] = "synthetic_test_evidence"
                row["source"] = "Menu #2 synthetic EnvObservation at DP01"
                row["note"] = "Source-stamped synthetic evidence; usable only inside this discarded sandbox cycle."
    return out


def _observation_summary_v1(observation: EnvObservation | None) -> dict[str, Any]:
    """Return the compact injected packet shown above the DP trace."""
    if observation is None:
        return {}
    meta = observation.env_meta if isinstance(observation.env_meta, Mapping) else {}
    return {
        "raw_sensors": deepcopy(dict(observation.raw_sensors)),
        "predicates": list(observation.predicates),
        "cues": list(observation.cues),
        "nav_patch_count": len(observation.nav_patches),
        "surface_grid_present": bool(observation.surface_grid),
        "source_class": meta.get("source_class"),
        "diagnostic_injection_v1": deepcopy(meta.get("diagnostic_injection_v1", {})),
    }


def run_envobservation_injection_sandbox_v1(
    runtime: CognitiveInjectionRuntimeV1,
    *,
    injection_id: str,
    preset_id: str = _PRESET_FALLEN_NEAR_CLIFF_V1,
) -> dict[str, Any]:
    """Inject one preset ``EnvObservation`` and return its disposable-cycle trace.

    The established ``run_env_closed_loop_steps`` function performs the actual
    cognition. The only special mechanism is how the first observation is
    placed on the normal pending-observation seam. Shared skill and Column state
    are always restored before this function returns.
    """
    transcript_buffer = StringIO()
    observation: EnvObservation | None = None
    metadata = _injection_metadata_v1(injection_id, preset_id)
    snapshot: dict[str, Any] = {}
    selected_policy: str | None = None
    action_dispatched: str | None = None
    status = "error"
    error_type: str | None = None
    error_message: str | None = None

    skills_before, columns_before, random_state_before = _snapshot_process_shared_state_v1(runtime)
    try:
        if preset_id != _PRESET_FALLEN_NEAR_CLIFF_V1:
            raise ValueError(f"Unknown cognitive-injection preset: {preset_id!r}")

        state, observation, metadata = build_fallen_near_cliff_injection_v1(injection_id)
        env = HybridEnvironment()
        world = _sandbox_world_v1()
        drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)
        ctx = _sandbox_context_v1()
        policy_runtime = runtime.policy_runtime_factory()
        policy_runtime.refresh_loaded(ctx)
        _install_pending_observation_v1(env, ctx, state, observation)

        with redirect_stdout(transcript_buffer):
            runtime.run_closed_loop_steps(
                env,
                world,
                drives,
                ctx,
                policy_runtime,
                n_steps=1,
                teaching_mode=False,
            )

        raw_snapshot = cca8_cognitive_scope.cognitive_scope_latest_snapshot_v1(ctx)
        if not isinstance(raw_snapshot, Mapping):
            raise RuntimeError("The sandbox cognitive cycle completed without a retained DP00-DP18 snapshot.")
        snapshot = _annotate_injection_snapshot_v1(raw_snapshot, metadata)
        selected_raw = snapshot.get("cycle_output_action")
        selected_policy = selected_raw if isinstance(selected_raw, str) and selected_raw else None
        dispatched_raw = snapshot.get("action_dispatched")
        action_dispatched = dispatched_raw if isinstance(dispatched_raw, str) and dispatched_raw else None
        status = "completed"
    except Exception as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
    finally:
        rollback = _restore_process_shared_state_v1(runtime, skills_before, columns_before, random_state_before)

    if rollback.get("error") is not None:
        status = "error"
        if error_type is None:
            error_type = "RollbackError"
            error_message = str(rollback.get("error"))

    transcript = transcript_buffer.getvalue()
    transcript_truncated = len(transcript) > _TRANSCRIPT_LIMIT_V1
    if transcript_truncated:
        transcript = transcript[-_TRANSCRIPT_LIMIT_V1:]

    return {
        "schema": "cognitive_scope_injection_result_v1",
        "status": status,
        "injection_id": str(injection_id),
        "preset_id": str(preset_id),
        "boundary": "DP01",
        "source_class": "synthetic_test_evidence",
        "sandbox_only": True,
        "live_cognitive_state_mutated": False,
        "live_diagnostic_record_updated": False,
        "live_worldgraph_mutated": False,
        "live_wnm_mutated": False,
        "live_environment_mutated": False,
        "live_drives_mutated": False,
        "selected_policy": selected_policy,
        "action_dispatched": action_dispatched,
        "observation": _observation_summary_v1(observation),
        "snapshot": snapshot,
        "transcript": transcript,
        "transcript_truncated": transcript_truncated,
        "shared_state_rollback": rollback,
        "error_type": error_type,
        "error_message": error_message,
    }


def render_cognitive_injection_result_lines_v1(result: Mapping[str, Any]) -> list[str]:
    """Render one concise front-panel summary above the ordinary DP trace."""
    rollback = result.get("shared_state_rollback")
    rollback = rollback if isinstance(rollback, Mapping) else {}
    observation = result.get("observation")
    observation = observation if isinstance(observation, Mapping) else {}
    lines = [
        "CCA8 SYNTHETIC ENVOBSERVATION INJECTION -- DISPOSABLE SANDBOX",
        "=" * 78,
        (
            f"status={result.get('status')} injection={result.get('injection_id')} "
            f"boundary={result.get('boundary')} preset={result.get('preset_id')}"
        ),
        (
            "Guardrail: the packet entered a fresh sandbox only; the live WorldGraph, WNM, environment, drives, "
            "and ordinary scope trace were not supplied to the test cycle."
        ),
        (
            f"rollback skills={rollback.get('skills_restored')} columns={rollback.get('columns_restored')} "
            f"random_state={rollback.get('random_state_restored')}"
        ),
        "-" * 78,
        f"predicates={observation.get('predicates', [])}",
        f"cues={observation.get('cues', [])}",
        f"raw_sensors={observation.get('raw_sensors', {})}",
        (
            f"nav_patches={observation.get('nav_patch_count')} surface_grid={observation.get('surface_grid_present')} "
            f"source_class={observation.get('source_class')}"
        ),
        "-" * 78,
        (
            f"sandbox selected_policy={result.get('selected_policy')!r} "
            f"action_dispatched={result.get('action_dispatched')!r}"
        ),
    ]
    if result.get("status") != "completed":
        lines.append(f"error={result.get('error_type')}: {result.get('error_message')}")
    lines.extend(
        [
            (
                "The following scope snapshot is evidence about the sandbox run, not a write into live goat cognition. "
                f"live_diagnostic_record_updated={result.get('live_diagnostic_record_updated')}"
            ),
            "=" * 78,
        ]
    )
    return lines


def render_cognitive_injection_transcript_lines_v1(result: Mapping[str, Any]) -> list[str]:
    """Render the captured ordinary one-cycle terminal transcript."""
    transcript = result.get("transcript")
    text = transcript if isinstance(transcript, str) else ""
    lines = [
        "CCA8 SYNTHETIC ENVOBSERVATION INJECTION -- SANDBOX CYCLE TRANSCRIPT",
        "=" * 78,
        (
            f"injection={result.get('injection_id')} preset={result.get('preset_id')} "
            f"truncated={result.get('transcript_truncated')}"
        ),
        "-" * 78,
    ]
    lines.extend(text.splitlines() if text else ["(no transcript captured)"])
    lines.append("=" * 78)
    return lines
