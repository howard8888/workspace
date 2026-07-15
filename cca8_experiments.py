#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 experiment protocol, execution, scoring, and menu subsystem.

Purpose
-------
This module owns the complete CCA8 experiment subsystem: frozen condition and
benchmark definitions, newborn observation stressors, protocol normalization,
JSON/JSONL preparation, sandbox execution, LLM-adviser support, benchmark
scoring, repeat statistics, result rendering, and the interactive Menu 49 flow.

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. Runner-private operations needed by
experiment execution are supplied explicitly through :class:`ExperimentRuntime`.
The terminal menu receives runner-visible compatibility callables through
:class:`ExperimentMenuOperations`. This keeps the dependency direction one-way,
avoids circular imports, and preserves existing monkeypatch seams in tests and
downstream tools.

Compatibility boundary
----------------------
``cca8_run`` continues to expose its historical experiment names. Pure helpers
are aliases to this module; runtime-dependent entry points are small wrappers
that construct the current callback bridge at call time.
"""

from __future__ import annotations

import io
import json
import math
import os
import random
import time
from collections import defaultdict
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from cca8_context import Ctx, ExperimentProtocolConfig
from cca8_controller import Drives, body_space_zone, skill_q, skills_from_dict, skills_to_dict
from cca8_env import EnvConfig, EnvObservation, HybridEnvironment
from cca8_rcos_experiments import (
    rcos_robotic_run_ablation_repeats_v1,
    rcos_robotic_run_episode_v1,
    rcos_robotic_run_perturbed_repeats_v1,
    rcos_robotic_run_repeats_v1,
    rcos_robotic_run_suite_v1,
    render_rcos_robotic_ablation_protocol_v1,
    render_rcos_robotic_ablation_repeats_lines_v1,
    render_rcos_robotic_episode_lines_v1,
    render_rcos_robotic_perturbation_protocol_v1,
    render_rcos_robotic_perturbed_repeats_lines_v1,
    render_rcos_robotic_protocol_v1,
    render_rcos_robotic_repeats_lines_v1,
    render_rcos_robotic_suite_lines_v1,
)
from cca8_state_integrity import (
    render_state_integrity_event_detail_lines_v1,
    summarize_newborn_state_integrity_v1,
)
from cca8_temporal import TemporalContext

__version__ = "0.2.0"

RunIdFactory = Callable[[Ctx | None, ExperimentProtocolConfig | None], str]
BodySpaceZoneFn = Callable[[Ctx], str]


@dataclass(frozen=True, slots=True)
class ExperimentRuntime:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-owned operations required by experiment execution.

    The experiment module imports stable CCA8 data types directly, but the main
    closed-loop engine, policy-gate runtime, WorkingMap constructors, and OpenAI
    helpers remain owned by ``cca8_run``. The runner creates this immutable bridge
    immediately before each runtime-dependent call. Resolving callbacks at call
    time preserves tests and tools that monkeypatch runner-visible functions.
    """

    world_factory: Callable[[], Any]
    policy_runtime_factory: Callable[[], Any]
    init_body_world: Callable[[], tuple[Any, dict[str, str]]]
    init_working_world: Callable[[], Any]
    reset_working_world: Callable[[Ctx], None]
    apply_hardwired_profile: Callable[[Ctx, Any], None]
    configure_goat_foraging: Callable[[Any, Drives, Ctx, HybridEnvironment], Any]
    run_closed_loop: Callable[[HybridEnvironment, Any, Drives, Ctx, Any, int], None]
    build_llm_state_summary: Callable[[Any, Drives, Ctx], dict[str, Any]]
    newborn_retrieved_hint_debug: Callable[[Ctx], dict[str, Any]]
    run_id_factory: RunIdFactory
    openai_default_model_name: Callable[[], str]
    openai_response_request_options: Callable[[], dict[str, Any]]
    openai_sanitize_adviser_request_options: Callable[[dict[str, Any]], dict[str, Any]]
    openai_quiet_http_loggers: Callable[[], None]
    openai_response_text: Callable[[Any], str]
    openai_api_error_detail: Callable[[Any], dict[str, Any]]
    llm_response_usage: Callable[[Any], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ExperimentMenuOperations:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-visible operations used by the extracted Menu 49 implementation.

    Menu 49 remains behaviorally compatible with the historical runner menu,
    including its monkeypatch seams. The runner supplies these callables at menu
    entry, while this module owns the terminal flow and experiment-specific text.
    """

    make_run_id: Callable[..., str]
    prepare_logging: Callable[..., dict[str, Any]]
    build_cycle_record: Callable[..., dict[str, Any]]
    build_episode_record: Callable[..., dict[str, Any]]
    run_one_episode: Callable[..., dict[str, Any]]
    run_condition_batch: Callable[..., dict[str, Any]]
    run_repeated_abc: Callable[..., dict[str, Any]]
    run_repeated_ae: Callable[..., dict[str, Any]]
    write_repeated_bundle: Callable[..., dict[str, Any]]

__all__ = [
    "ExperimentConditionDef",
    "ExperimentBenchmarkDef",
    "ExperimentProtocolConfig",
    "ExperimentRuntime",
    "ExperimentMenuOperations",
    "NEWBORN_STRESS_PROFILES_V1",
    "AUTONOMOUS_NEWBORN_SURVIVAL_MILESTONES_V1",
    "experiment_action_vocab_v1",
    "experiment_condition_catalog_v1",
    "experiment_benchmark_catalog_v1",
    "apply_newborn_experiment_stress_v1",
    "reset_experiment_protocol_v1",
    "render_experiment_conditions_table_v1",
    "render_experiment_benchmarks_table_v1",
    "render_experiment_jsonl_schema_summary_v1",
    "render_experiment_protocol_summary_v1",
    "experiment_parse_condition_ids_v1",
    "experiment_parse_seed_list_v1",
    "experiment_normalize_protocol_v1",
    "experiment_make_run_id_v1",
    "experiment_jsonl_paths_v1",
    "append_experiment_jsonl_record_v1",
    "experiment_prepare_logging_v1",
    "experiment_build_cycle_record_stub_v1",
    "experiment_build_episode_record_stub_v1",
    "experiment_write_episode_record_v1",
    "experiment_make_sandbox_runtime_v1",
    "experiment_configure_benchmark_runtime_v1",
    "experiment_apply_condition_runtime_v1",
    "experiment_run_one_episode_v1",
    "experiment_run_condition_batch_v1",
    "experiment_run_repeated_selected_vs_a_v1",
    "experiment_run_repeated_random_abc_v1",
    "experiment_run_repeated_random_ae_v1",
    "render_experiment_episode_summary_lines_v1",
    "render_experiment_batch_summary_lines_v1",
    "render_experiment_repeat_stats_lines_v1",
    "render_experiment_logging_status_v1",
    "run_autonomous_newborn_survival_demo_v1",
    "render_autonomous_newborn_survival_demo_lines_v1",
    "experiments_menu_49_interactive",
    "__version__",
]

@dataclass(slots=True)
class ExperimentConditionDef:
    """One frozen comparison condition for the long-horizon experiments.

    I keep this intentionally small and explicit so that the paper protocol and the
    runner protocol stay aligned. Each condition answers one scientific question.
    """
    condition_id: str
    label: str
    agent_mode: str
    decision_authority: str
    retrieval_enabled: bool
    retrieval_mode: str
    llm_role: str
    notes: str = ""


@dataclass(slots=True)
class ExperimentBenchmarkDef:
    """One benchmark definition used by the experiment harness."""
    benchmark_id: str
    label: str
    goal: str
    primary_metrics: list[str] = field(default_factory=list)






def _experiment_policy_debug_record_v1(ctx: Ctx | None, event: dict[str, Any]) -> None:
    """Store one policy-selection debug event without changing behavior."""
    if ctx is None or not isinstance(event, dict):
        return

    try:
        event_copy = dict(event)
        ctx.experiment_policy_debug_last = event_copy

        hist = getattr(ctx, "experiment_policy_debug_events", None)
        if not isinstance(hist, list):
            hist = []

        hist.append(event_copy)

        if len(hist) > 128:
            del hist[:-128]

        ctx.experiment_policy_debug_events = hist
    except Exception:
        pass


def experiment_action_vocab_v1() -> list[str]:
    """Return the frozen action vocabulary used across experiment conditions A-E.

    I keep this explicit rather than deriving it dynamically from the live policy
    catalog, because the experiment protocol should stay stable even if we later
    add unrelated policies to the runner.
    """
    return [
        "policy:stand_up",
        "policy:recover_fall",
        "policy:seek_nipple",
        "policy:rest",
        "policy:probe",
        "policy:follow_mom",
        "policy:suckle",
        "policy:recover_miss",
        "policy:explore_check",
    ]


def experiment_condition_catalog_v1() -> dict[str, ExperimentConditionDef]:
    """Return the frozen A-E comparison conditions for the paper protocol."""
    items = [
        ExperimentConditionDef(
            condition_id="A",
            label="Full CCA8 (merge retrieval)",
            agent_mode="cca8",
            decision_authority="cca8",
            retrieval_enabled=True,
            retrieval_mode="merge",
            llm_role="none",
            notes="Reference condition: full layered memory with guarded episodic readback.",
        ),
        ExperimentConditionDef(
            condition_id="B",
            label="CCA8 without episodic readback",
            agent_mode="cca8",
            decision_authority="cca8",
            retrieval_enabled=False,
            retrieval_mode="merge",
            llm_role="none",
            notes="Storage remains on; auto-retrieval is disabled to isolate recall utility.",
        ),
        ExperimentConditionDef(
            condition_id="C",
            label="CCA8 with replace-mode prior injection",
            agent_mode="cca8",
            decision_authority="cca8",
            retrieval_enabled=True,
            retrieval_mode="replace",
            llm_role="none",
            notes="Tests whether guarded merge is better than strong overwrite priors.",
        ),
        ExperimentConditionDef(
            condition_id="D",
            label="LLM-only controller baseline",
            agent_mode="llm_only",
            decision_authority="llm",
            retrieval_enabled=False,
            retrieval_mode="none",
            llm_role="controller",
            notes="LLM sees only agent-visible observation packets plus the same fixed action vocabulary.",
        ),
        ExperimentConditionDef(
            condition_id="E",
            label="Hybrid CCA8 + LLM adviser",
            agent_mode="hybrid",
            decision_authority="cca8",
            retrieval_enabled=True,
            retrieval_mode="merge",
            llm_role="advisor",
            notes="CCA8 remains authoritative; the LLM ranks or advises among bounded candidate actions.",
        ),
    ]
    return {item.condition_id: item for item in items}


def experiment_benchmark_catalog_v1() -> dict[str, ExperimentBenchmarkDef]:
    """Return the current benchmark suite for the long-horizon paper."""
    items = [
        ExperimentBenchmarkDef(
            benchmark_id="goat04_context",
            label="goat_foraging_04 contextual map-switch benchmark",
            goal=(
                "Mechanistic benchmark: partial observability plus fox/hawk contextual switching "
                "to test retrieval, contamination control, and stabilization after a context change."
            ),
            primary_metrics=[
                "context_switch_accuracy",
                "cycles_to_stabilization",
                "false_retrieval_count",
                "cue_leakage_violations",
                "cumulative_prediction_error",
            ],
        ),


        ExperimentBenchmarkDef(
            benchmark_id="newborn_long_horizon",
            label="newborn-goat long-horizon milestone benchmark",
            goal=(
                "Behavioral benchmark: closed-loop milestone attainment across posture recovery, "
                "mom approach, nipple finding, latching, milk drinking, and resting."
            ),
            primary_metrics=[
                "episode_success",
                "milestone_vector",
                "milestone_score",
                "cycles_to_end",
                "repeated_action_loop_count",
                "cumulative_prediction_error",
                "recovery_latency",
            ],
        ),

    ]
    return {item.benchmark_id: item for item in items}

NEWBORN_STRESS_PROFILES_V1 = ("baseline", "blackout_short", "blackout_long", "route_loss")

NEWBORN_STRESS_DROP_PRED_PREFIXES_V1 = (
    "proximity:mom:",
    "nipple:",
    "milk:",
    "proximity:shelter:",
    "hazard:cliff:",
)

NEWBORN_STRESS_DROP_CUE_PREFIXES_V1 = (
    "vision:silhouette:mom",
    "touch:nipple",
    "odor:milk",
    "smell:milk",
    "warmth:mom",
)

NEWBORN_ROUTE_LOSS_DROP_PRED_PREFIXES_V1 = (
    "proximity:mom:",
    "nipple:",
    "milk:",
    "proximity:shelter:",
    "hazard:cliff:",
    "terrain:",
    "goal:",
    "landmark:",
    "route:",
    "nav:",
)

NEWBORN_ROUTE_LOSS_DROP_CUE_PREFIXES_V1 = (
    "vision:silhouette:mom",
    "vision:landmark",
    "vision:shelter",
    "vision:cliff",
    "touch:nipple",
    "touch:terrain",
    "odor:milk",
    "smell:milk",
    "warmth:mom",
    "nav:",
    "route:",
)

NEWBORN_ROUTE_LOSS_RAW_SENSOR_KEY_INFIXES_V1 = (
    "mom",
    "nipple",
    "milk",
    "shelter",
    "cliff",
    "hazard",
    "landmark",
    "route",
    "bearing",
    "distance",
    "goal",
)

NEWBORN_ROUTE_LOSS_META_PROTECTED_KEYS_V1 = {
    "scenario_stage",
    "milestone",
    "milestones",
    "step",
    "env_step",
    "episode_step",
    "time",
    "time_s",
    "dt",
}


def _newborn_route_loss_drop_predicates_v1(tokens: list[Any]) -> tuple[list[str], list[str]]:
    """Drop external route/task-state predicates while preserving body posture cues."""
    kept: list[str] = []
    dropped: list[str] = []

    for item in tokens:
        if not isinstance(item, str):
            continue

        token = item.strip()
        if not token:
            continue

        token_check = token.replace("pred:", "", 1) if token.startswith("pred:") else token

        # Preserve proprioceptive/body-state information. Route loss is not amnesia
        # about the body; it is loss of external route/task context.
        if token_check.startswith("posture:") or token_check in ("resting", "alert"):
            kept.append(token)
            continue

        if any(token_check.startswith(prefix) for prefix in NEWBORN_ROUTE_LOSS_DROP_PRED_PREFIXES_V1):
            dropped.append(token)
            continue

        kept.append(token)

    return kept, dropped


def _newborn_route_loss_drop_cues_v1(tokens: list[Any]) -> tuple[list[str], list[str]]:
    """Drop external route/task-state cues while preserving proprioceptive cues."""
    kept: list[str] = []
    dropped: list[str] = []

    for item in tokens:
        if not isinstance(item, str):
            continue

        token = item.strip()
        if not token:
            continue

        # Preserve fall/body/balance cues. The agent still knows its own posture.
        if token.startswith(("vestibular:", "balance:", "touch:flank_on_ground")):
            kept.append(token)
            continue

        if any(token.startswith(prefix) for prefix in NEWBORN_ROUTE_LOSS_DROP_CUE_PREFIXES_V1):
            dropped.append(token)
            continue

        kept.append(token)

    return kept, dropped


def _newborn_route_loss_drop_raw_sensors_v1(raw_sensors: Any) -> tuple[Any, list[str]]:
    """Drop external route/task-state raw sensor fields, when raw_sensors is a dict."""
    if not isinstance(raw_sensors, dict):
        return raw_sensors, []

    kept: dict[str, Any] = {}
    dropped_keys: list[str] = []

    for key, value in raw_sensors.items():
        key_text = str(key)
        key_norm = key_text.lower()

        if any(fragment in key_norm for fragment in NEWBORN_ROUTE_LOSS_RAW_SENSOR_KEY_INFIXES_V1):
            dropped_keys.append(key_text)
            continue

        kept[key] = value

    return kept, dropped_keys


def _newborn_route_loss_mask_env_meta_v1(meta: dict[str, Any]) -> list[str]:
    """Remove agent-visible external route hints from env_meta while preserving scoring metadata.

    env_meta is still part of the visible observation packet in this runner, so route
    loss should not leave direct route hints such as mom_position or bearing_to_mom.
    We preserve scenario_stage and milestones because they are used by the benchmark
    harness for storage/scoring and do not directly provide a route vector.
    """
    if not isinstance(meta, dict):
        return []

    dropped_keys: list[str] = []

    for key in list(meta.keys()):
        key_text = str(key)
        key_norm = key_text.lower()

        if key_norm.startswith("newborn_"):
            continue

        if key_norm in NEWBORN_ROUTE_LOSS_META_PROTECTED_KEYS_V1:
            continue

        drop = False
        for fragment in (
            "mom_position",
            "nipple_position",
            "shelter_position",
            "cliff_position",
            "hazard_position",
            "goal_position",
            "landmark_position",
            "mom_distance",
            "nipple_distance",
            "shelter_distance",
            "cliff_distance",
            "hazard_distance",
            "goal_distance",
            "bearing",
            "route",
            "path",
            "landmark",
        ):
            if fragment in key_norm:
                drop = True
                break

        if drop:
            dropped_keys.append(key_text)
            try:
                meta.pop(key, None)
            except Exception:
                pass

    return dropped_keys


def _newborn_route_loss_drop_nav_fields_v1(env_obs: EnvObservation) -> dict[str, int]:
    """Drop external navigation surfaces from the visible observation packet."""
    out = {
        "dropped_nav_patches": 0,
        "dropped_surface_grid": 0,
    }

    try:
        nav_patches = getattr(env_obs, "nav_patches", None)
        if isinstance(nav_patches, list):
            out["dropped_nav_patches"] = int(len(nav_patches))
            setattr(env_obs, "nav_patches", [])
    except Exception:
        pass

    try:
        surface_grid = getattr(env_obs, "surface_grid", None)
        if isinstance(surface_grid, dict) and surface_grid:
            out["dropped_surface_grid"] = 1
            setattr(env_obs, "surface_grid", {})
    except Exception:
        pass

    return out


def _newborn_effective_blackout_length_v1(profile: str, configured_length: Any) -> int:
    """Return the effective blackout length used by a newborn stress profile.

    The protocol stores one configurable length value, but each stress profile has
    its own allowed range. This helper makes the displayed/provenance value match
    the value actually used by the stressor runtime.
    """
    profile_norm = str(profile or "baseline").strip().lower()
    try:
        raw = int(configured_length or 3)
    except Exception:
        raw = 3
    raw = max(1, min(20, raw))
    if profile_norm == "blackout_short":
        return max(1, min(4, raw))
    if profile_norm == "blackout_long":
        return max(5, min(20, raw))
    if profile_norm == "route_loss":
        return max(8, min(20, raw))
    return raw


def _newborn_stress_profile_from_ctx_v1(ctx: Ctx | None) -> str:
    """Return the active newborn stress profile."""
    if ctx is None:
        return "baseline"

    cfg = getattr(ctx, "experiment_cfg", None)
    raw = getattr(cfg, "newborn_stress_profile", "baseline")
    profile = str(raw or "baseline").strip().lower()

    if profile not in NEWBORN_STRESS_PROFILES_V1:
        return "baseline"
    return profile


def _newborn_blackout_length_from_ctx_v1(ctx: Ctx | None, profile: str) -> int:
    """Return the effective blackout length for a newborn stress profile."""
    profile_norm = str(profile or "baseline").strip().lower()

    if profile_norm == "blackout_short":
        default_len = 3
    elif profile_norm == "blackout_long":
        default_len = 5
    elif profile_norm == "route_loss":
        default_len = 8
    else:
        default_len = 3

    if ctx is None:
        return _newborn_effective_blackout_length_v1(profile_norm, default_len)

    cfg = getattr(ctx, "experiment_cfg", None)
    raw = getattr(cfg, "newborn_blackout_length", default_len)

    return _newborn_effective_blackout_length_v1(profile_norm, raw)


def _newborn_stress_env_meta_v1(env_obs: EnvObservation) -> dict[str, Any]:
    """Return a mutable env_meta dict for a newborn stress operation."""
    meta = getattr(env_obs, "env_meta", None)
    if isinstance(meta, dict):
        return meta

    meta = {}
    try:
        setattr(env_obs, "env_meta", meta)
    except Exception:
        pass
    return meta


def _newborn_stress_milestones_from_obs_v1(env_obs: EnvObservation) -> list[str]:
    """Return milestone labels from an EnvObservation metadata packet."""
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}

    raw = meta.get("milestones")
    if raw is None:
        raw = meta.get("milestone")

    if isinstance(raw, str) and raw:
        return [raw]

    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item:
                out.append(item)
    return out


def _newborn_stress_drop_predicates_v1(tokens: list[Any]) -> tuple[list[str], list[str]]:
    """Drop local-state predicates for a newborn blackout stressor."""
    kept: list[str] = []
    dropped: list[str] = []

    for item in tokens:
        if not isinstance(item, str):
            continue

        token = item.strip()
        if not token:
            continue

        token_check = token.replace("pred:", "", 1) if token.startswith("pred:") else token
        if any(token_check.startswith(prefix) for prefix in NEWBORN_STRESS_DROP_PRED_PREFIXES_V1):
            dropped.append(token)
            continue

        kept.append(token)

    return kept, dropped


def _newborn_stress_drop_cues_v1(tokens: list[Any]) -> tuple[list[str], list[str]]:
    """Drop local-state cues for a newborn blackout stressor."""
    kept: list[str] = []
    dropped: list[str] = []

    for item in tokens:
        if not isinstance(item, str):
            continue

        token = item.strip()
        if not token:
            continue

        if any(token.startswith(prefix) for prefix in NEWBORN_STRESS_DROP_CUE_PREFIXES_V1):
            dropped.append(token)
            continue

        kept.append(token)

    return kept, dropped


def _newborn_stress_schedule_blackout_v1(
    ctx: Ctx,
    *,
    step_now: int,
    profile: str,
    milestone: str,
) -> None:
    """Schedule a deterministic blackout beginning on the next cycle."""
    length = _newborn_blackout_length_from_ctx_v1(ctx, profile)
    start_step = int(step_now) + 1
    until_step = start_step + int(length) - 1

    try:
        current_until = int(getattr(ctx, "experiment_newborn_blackout_until_step", -1) or -1)
    except Exception:
        current_until = -1

    if until_step <= current_until:
        return

    try:
        ctx.experiment_newborn_blackout_start_step = int(start_step)
        ctx.experiment_newborn_blackout_until_step = int(until_step)
        ctx.experiment_newborn_blackout_reason = f"after_{milestone}"
    except Exception:
        pass


def apply_newborn_experiment_stress_v1(ctx: Ctx | None, env_obs: EnvObservation) -> EnvObservation:
    """Apply deterministic newborn benchmark stressors to the visible observation packet.

    This changes what the agent observes. It does not change hidden environment truth.

    Stress profiles
    ---------------
    baseline:
        No structured stressor beyond ordinary observation masking.

    blackout_short / blackout_long:
        Hide selected local relation and feeding-state tokens after milestones.

    route_loss:
        A stronger memory-critical stressor. The agent keeps body/proprioceptive
        state, but loses external route/task-state evidence such as mother
        direction/proximity, nipple/milk state, shelter/cliff relations, and local
        navigation surfaces for a longer interval. During active route loss, the
        benchmark forces keyframes so guarded retrieval has a chance to restore
        continuity, while no-readback cannot silently coast on fresh route cues.
    """
    if ctx is None or env_obs is None:
        return env_obs

    if not bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)):
        return env_obs

    profile = _newborn_stress_profile_from_ctx_v1(ctx)
    if profile == "baseline":
        return env_obs

    route_loss = profile == "route_loss"

    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    meta = _newborn_stress_env_meta_v1(env_obs)
    milestones = _newborn_stress_milestones_from_obs_v1(env_obs)

    meta["newborn_stress_profile"] = profile

    try:
        start_step = int(getattr(ctx, "experiment_newborn_blackout_start_step", -1) or -1)
        until_step = int(getattr(ctx, "experiment_newborn_blackout_until_step", -1) or -1)
    except Exception:
        start_step = -1
        until_step = -1

    blackout_active = bool(start_step >= 0 and start_step <= step_now <= until_step)  # pylint: disable=chained-comparison

    dropped_preds: list[str] = []
    dropped_cues: list[str] = []
    dropped_raw_keys: list[str] = []
    dropped_meta_keys: list[str] = []
    dropped_nav = {"dropped_nav_patches": 0, "dropped_surface_grid": 0}

    if blackout_active:
        preds_raw = list(getattr(env_obs, "predicates", []) or [])
        cues_raw = list(getattr(env_obs, "cues", []) or [])

        if route_loss:
            preds_kept, dropped_preds = _newborn_route_loss_drop_predicates_v1(preds_raw)
            cues_kept, dropped_cues = _newborn_route_loss_drop_cues_v1(cues_raw)

            raw_sensors = getattr(env_obs, "raw_sensors", None)
            raw_sensors_kept, dropped_raw_keys = _newborn_route_loss_drop_raw_sensors_v1(raw_sensors)
            try:
                setattr(env_obs, "raw_sensors", raw_sensors_kept)
            except Exception:
                pass

            dropped_meta_keys = _newborn_route_loss_mask_env_meta_v1(meta)
            dropped_nav = _newborn_route_loss_drop_nav_fields_v1(env_obs)

            # Force a keyframe during active route loss. This gives condition A a
            # fair chance to retrieve prior route/task context, while condition B
            # cannot use readback.
            meta["newborn_force_keyframe"] = True
            meta["newborn_route_loss_active"] = True

        else:
            preds_kept, dropped_preds = _newborn_stress_drop_predicates_v1(preds_raw)
            cues_kept, dropped_cues = _newborn_stress_drop_cues_v1(cues_raw)
            meta["newborn_force_keyframe"] = False
            meta["newborn_route_loss_active"] = False

        try:
            setattr(env_obs, "predicates", preds_kept)
            setattr(env_obs, "cues", cues_kept)
        except Exception:
            pass

        meta["newborn_blackout_active"] = True
        meta["newborn_blackout_reason"] = getattr(ctx, "experiment_newborn_blackout_reason", None)
        meta["newborn_blackout_start_step"] = int(start_step)
        meta["newborn_blackout_until_step"] = int(until_step)
        meta["newborn_blackout_dropped_preds"] = int(len(dropped_preds))
        meta["newborn_blackout_dropped_cues"] = int(len(dropped_cues))
        meta["newborn_blackout_dropped_pred_tokens"] = dropped_preds[:16]
        meta["newborn_blackout_dropped_cue_tokens"] = dropped_cues[:16]

        meta["newborn_route_loss_dropped_raw_keys"] = dropped_raw_keys[:16]
        meta["newborn_route_loss_dropped_meta_keys"] = dropped_meta_keys[:16]
        meta["newborn_route_loss_dropped_nav_patches"] = int(dropped_nav.get("dropped_nav_patches", 0))
        meta["newborn_route_loss_dropped_surface_grid"] = int(dropped_nav.get("dropped_surface_grid", 0))

    else:
        meta["newborn_blackout_active"] = False
        meta["newborn_blackout_dropped_preds"] = 0
        meta["newborn_blackout_dropped_cues"] = 0
        meta["newborn_force_keyframe"] = False
        meta["newborn_route_loss_active"] = False
        meta["newborn_route_loss_dropped_raw_keys"] = []
        meta["newborn_route_loss_dropped_meta_keys"] = []
        meta["newborn_route_loss_dropped_nav_patches"] = 0
        meta["newborn_route_loss_dropped_surface_grid"] = 0

    trigger_milestones: tuple[str, ...]
    if route_loss:
        trigger_milestones = ("stood_up", "reached_mom", "found_nipple", "latched_nipple", "milk_drinking")
    else:
        trigger_milestones = ("stood_up", "reached_mom", "latched_nipple")

    for milestone in milestones:
        if milestone in trigger_milestones:
            _newborn_stress_schedule_blackout_v1(
                ctx,
                step_now=step_now,
                profile=profile,
                milestone=milestone,
            )
            break
    return env_obs


def reset_experiment_protocol_v1(ctx: Ctx) -> None:
    """Reset ctx experiment settings to the frozen paper defaults."""
    if ctx is None:
        return
    ctx.experiment_cfg = ExperimentProtocolConfig()
    ctx.experiment_last_summary.clear()


def render_experiment_conditions_table_v1(ctx: Ctx) -> str:
    """Return a compact fixed-width table of the A-E condition definitions."""
    cfg = getattr(ctx, "experiment_cfg", None) or ExperimentProtocolConfig()
    catalog = experiment_condition_catalog_v1()

    lines = []
    lines.append("Condition table (A-E)")
    lines.append("id  mode      authority  retrieve  mode     llm_role    label")
    lines.append("--  --------  ---------  --------  -------  ----------  ----------------------------------------------")

    for cid in cfg.condition_ids:
        cond = catalog.get(cid)
        if cond is None:
            continue
        retrieve_txt = "on" if cond.retrieval_enabled else "off"
        lines.append(
            f"{cond.condition_id:<2}  {cond.agent_mode:<8}  {cond.decision_authority:<9}  {retrieve_txt:<8}  "
            f"{cond.retrieval_mode:<7}  {cond.llm_role:<10}  {cond.label}"
        )

    lines.append("")
    for cid in cfg.condition_ids:
        cond = catalog.get(cid)
        if cond is None:
            continue
        lines.append(f"  {cond.condition_id}) {cond.notes}")

    return "\n".join(lines)


def render_experiment_benchmarks_table_v1() -> str:
    """Return a human-readable summary of the current benchmark suite."""
    catalog = experiment_benchmark_catalog_v1()
    order = ["goat04_context", "newborn_long_horizon"]

    lines = []
    lines.append("Benchmark suite")
    for bid in order:
        bench = catalog.get(bid)
        if bench is None:
            continue
        lines.append(f"  {bench.benchmark_id}: {bench.label}")
        lines.append(f"     goal: {bench.goal}")
        lines.append(f"     metrics: {', '.join(bench.primary_metrics)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_experiment_jsonl_schema_summary_v1() -> str:
    """Return the current JSONL record contract for experiment logging.

    This is intentionally a schema summary, not yet the actual writer. A later
    patch will make the live runner emit these records.
    """
    cycle_fields = [
        "schema", "record_type", "experiment_id", "benchmark", "condition", "seed", "episode_index",
        "cycle_index", "env_step", "stage", "zone", "obs_mask_stats", "retrieval_event", "pred_err",
        "selected_policy", "llm_advice_summary", "executed_action", "milestones", "oracle",
        "done", "termination_reason",
    ]
    episode_fields = [
        "schema", "record_type", "experiment_id", "benchmark", "condition", "seed", "episode_index",
        "success", "cycles_to_end", "milestone_vector", "milestone_score", "context_switch_accuracy",
        "false_retrieval_count", "cue_leakage_violations", "cumulative_prediction_error",
        "repeated_action_loop_count", "llm_call_count", "llm_latency_ms_total", "latency_ms_total", "recovery_latency",
        "oracle_action_accuracy", "oracle_retrieval_precision", "internal_retrieval_event_ratio",
        "stabilization_latency", "retrieval_action_dissociation_count",
        "time_to_rested_or_max_cycles",
        "newborn_stress_profile", "newborn_stress_active_cycle_count",
        "newborn_stress_dropped_pred_count", "newborn_stress_dropped_cue_count",
        "newborn_stress_reasons",
        "newborn_retrieved_hint_set_count", "newborn_retrieved_hint_active_step_count",
        "newborn_retrieved_hint_used_step_count", "newborn_retrieved_hint_events",
        "state_integrity_summary", "lhsi_state_integrity_score", "lhsi_wrong_stage_action_count",
        "lhsi_repeated_action_loop_count", "lhsi_current_state_overwrite_proxy_count",
        "lhsi_stale_memory_intrusion_proxy_count", "lhsi_retrieval_action_dissociation_proxy_count",
        "lhsi_retrieval_followup_basis_count", "lhsi_provenance_complete_cycle_rate",
    ]

    lines = []
    lines.append("JSONL schema summary")
    lines.append("  cycle record:")
    lines.append("    " + ", ".join(cycle_fields))
    lines.append("")
    lines.append("  episode summary record:")
    lines.append("    " + ", ".join(episode_fields))
    return "\n".join(lines)


def render_experiment_protocol_summary_v1(ctx: Ctx) -> str:
    """Return the current frozen experiment protocol as a readable block.

    Patch-2 extends the summary so the experiment menu can show not only the scientific
    protocol knobs, but also the file/output preparation knobs. That makes the protocol
    inspectable before we wire in actual experiment execution.
    """
    cfg = getattr(ctx, "experiment_cfg", None) or ExperimentProtocolConfig()
    bench = experiment_benchmark_catalog_v1().get(cfg.benchmark_id)
    action_vocab = experiment_action_vocab_v1()
    last = getattr(ctx, "experiment_last_summary", None)
    last = last if isinstance(last, dict) else {}

    lines = []
    lines.append("Experiment protocol summary")
    lines.append(f"  protocol_version     : {cfg.protocol_version}")
    lines.append(f"  benchmark            : {cfg.benchmark_id}")
    if bench is not None:
        lines.append(f"  benchmark_label      : {bench.label}")
    lines.append(f"  conditions           : {', '.join(cfg.condition_ids)}")
    lines.append(f"  seeds                : {cfg.seed_list}")
    lines.append(f"  episodes_per_seed    : {cfg.episodes_per_seed}")
    lines.append(f"  max_cycles           : {cfg.max_cycles}")
    lines.append(f"  obs_mask_prob        : {cfg.obs_mask_prob:.3f}")
    lines.append(f"  newborn_stress       : {cfg.newborn_stress_profile}")
    lines.append(f"  blackout_length      : {cfg.newborn_blackout_length}")
    lines.append(
        "  effective_blackout   : "
        f"{_newborn_effective_blackout_length_v1(cfg.newborn_stress_profile, cfg.newborn_blackout_length)}"
    )
    lines.append(f"  action_vocab_version : {cfg.action_vocab_version}")
    lines.append(f"  scratch_clear_policy : {cfg.scratch_clear_policy}")
    lines.append(f"  jsonl_cycle_records  : {cfg.jsonl_write_cycle_records}")
    lines.append(f"  jsonl_episode_records: {cfg.jsonl_write_episode_records}")
    lines.append(f"  llm_model            : {cfg.llm_model}")
    lines.append(f"  llm_adv_delta        : {cfg.llm_adviser_ambiguity_delta:.3f}")
    lines.append(f"  llm_adv_max_cands    : {cfg.llm_adviser_max_candidates}")
    lines.append(f"  run_label            : {cfg.run_label or '(none)'}")
    lines.append(f"  output_dir           : {cfg.output_dir}")
    if last:
        lines.append(f"  prepared_run_id      : {last.get('run_id')}")
    lines.append("")
    lines.append("  fixed action vocabulary:")
    for name in action_vocab:
        lines.append(f"    - {name}")
    return "\n".join(lines)


def _experiment_safe_token_v1(text: str, *, default: str = "") -> str:
    """Return a short filesystem-friendly token for run ids and labels.

    Purpose / intent
    ----------------
    Experiment output filenames should stay readable on Windows and should not contain
    punctuation that later complicates shell usage or path handling. This helper keeps
    only alnum / dash / underscore, translating a few common separators into underscores.

    Notes
    -----
    This is intentionally conservative. It is not intended as a full path sanitizer; it
    only prepares short filename tokens such as run_label or benchmark fragments.
    """
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


def experiment_parse_condition_ids_v1(text: str) -> list[str]:
    """Parse a comma/space-separated A-E condition list.

    We keep parsing permissive for terminal use, but validation still remains explicit:
    only A/B/C/D/E survive. Order is preserved and duplicates are removed.
    """
    if not isinstance(text, str):
        return []

    tokens = text.replace(",", " ").split()
    out: list[str] = []
    seen: set[str] = set()
    valid = {"A", "B", "C", "D", "E"}

    for tok in tokens:
        cid = tok.strip().upper()
        if cid in valid and cid not in seen:
            seen.add(cid)
            out.append(cid)

    return out


def experiment_parse_seed_list_v1(text: str) -> list[int]:
    """Parse a comma/space-separated integer seed list.

    Intent:
      - keep the menu forgiving,
      - preserve user order,
      - remove duplicates,
      - and leave final clamping/limits to experiment_normalize_protocol_v1(...).
    """
    if not isinstance(text, str):
        return []

    tokens = text.replace(",", " ").split()
    out: list[int] = []
    seen: set[int] = set()

    for tok in tokens:
        try:
            seed = int(tok)
        except Exception:
            continue

        if seed not in seen:
            seen.add(seed)
            out.append(seed)

    return out


def experiment_normalize_protocol_v1(cfg: ExperimentProtocolConfig | None) -> ExperimentProtocolConfig:
    """Return a sanitized experiment protocol configuration.

    Purpose / intent
    ----------------
    Menu 49 now edits protocol values interactively. That means we need one stable place
    that clamps numeric ranges, validates benchmark/condition identifiers, restores safe
    defaults, and makes later execution code independent of ad-hoc menu parsing.

    Design choice
    -------------
    I return a *new* ExperimentProtocolConfig rather than mutating the incoming object
    in place. That makes the normalization step easier to reason about and easier to test.
    """
    src = cfg if isinstance(cfg, ExperimentProtocolConfig) else ExperimentProtocolConfig()

    try:
        episodes_per_seed = int(getattr(src, "episodes_per_seed", 1) or 1)
    except Exception:
        episodes_per_seed = 1

    try:
        max_cycles = int(getattr(src, "max_cycles", 60) or 60)
    except Exception:
        max_cycles = 60

    try:
        obs_mask_prob = float(getattr(src, "obs_mask_prob", 0.0) or 0.0)
    except Exception:
        obs_mask_prob = 0.0

    stress_profile = str(getattr(src, "newborn_stress_profile", "baseline") or "baseline").strip().lower()
    if stress_profile not in NEWBORN_STRESS_PROFILES_V1:
        stress_profile = "baseline"

    try:
        newborn_blackout_length = int(getattr(src, "newborn_blackout_length", 3) or 3)
    except Exception:
        newborn_blackout_length = 3
    newborn_blackout_length = max(1, min(20, newborn_blackout_length))

    llm_model_raw = getattr(src, "llm_model", None)
    llm_model = None
    if isinstance(llm_model_raw, str) and llm_model_raw.strip():
        llm_model = llm_model_raw.strip()

    try:
        llm_delta = float(getattr(src, "llm_adviser_ambiguity_delta", 0.10) or 0.10)
    except Exception:
        llm_delta = 0.10

    try:
        llm_max_candidates = int(getattr(src, "llm_adviser_max_candidates", 4) or 4)
    except Exception:
        llm_max_candidates = 4

    out = ExperimentProtocolConfig(
        protocol_version=str(getattr(src, "protocol_version", "exp_protocol_v1") or "exp_protocol_v1"),
        benchmark_id=str(getattr(src, "benchmark_id", "newborn_long_horizon") or "newborn_long_horizon"),
        condition_ids=list(getattr(src, "condition_ids", []) or []),
        seed_list=list(getattr(src, "seed_list", []) or []),
        episodes_per_seed=max(1, min(1000, episodes_per_seed)),
        max_cycles=max(1, min(100000, max_cycles)),
        obs_mask_prob=max(0.0, min(1.0, obs_mask_prob)),
        newborn_stress_profile=stress_profile,
        newborn_blackout_length=newborn_blackout_length,
        action_vocab_version=str(
            getattr(src, "action_vocab_version", "cca8_action_vocab_v1") or "cca8_action_vocab_v1"
        ),
        scratch_clear_policy=str(
            getattr(src, "scratch_clear_policy", "per_episode_reset") or "per_episode_reset"
        ),
        jsonl_write_cycle_records=bool(getattr(src, "jsonl_write_cycle_records", True)),
        jsonl_write_episode_records=bool(getattr(src, "jsonl_write_episode_records", True)),
        llm_model=llm_model,
        llm_adviser_ambiguity_delta=max(0.0, min(1.0, llm_delta)),
        llm_adviser_max_candidates=max(2, min(8, llm_max_candidates)),
        run_label=str(getattr(src, "run_label", "") or ""),
        output_dir=str(getattr(src, "output_dir", "testvalues") or "testvalues"),
    )

    if out.benchmark_id not in experiment_benchmark_catalog_v1():
        out.benchmark_id = "newborn_long_horizon"

    valid_conditions = experiment_parse_condition_ids_v1(" ".join(str(x) for x in out.condition_ids))
    out.condition_ids = valid_conditions or ["A", "B", "C", "D", "E"]

    valid_seeds: list[int] = []
    seen_seeds: set[int] = set()
    for raw in out.seed_list:
        try:
            seed = int(raw)
        except Exception:
            continue

        if seed not in seen_seeds:
            seen_seeds.add(seed)
            valid_seeds.append(seed)

    out.seed_list = valid_seeds[:64] or [11, 23, 37, 41, 53]

    out.run_label = _experiment_safe_token_v1(out.run_label)
    out.output_dir = str(out.output_dir).strip() or "testvalues"

    return out


def experiment_make_run_id_v1(ctx: Ctx | None, cfg: ExperimentProtocolConfig | None = None) -> str:
    """Build a stable, human-readable run id for experiment output files.

    Current policy:
      - timestamp first (so lexicographic order is chronological),
      - benchmark id next,
      - optional run_label when provided,
      - otherwise fall back to profile if available.

    This is meant for filenames and log identity, not as a cryptographic id.
    """
    norm = experiment_normalize_protocol_v1(cfg)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    benchmark = _experiment_safe_token_v1(norm.benchmark_id, default="benchmark")
    label = _experiment_safe_token_v1(norm.run_label)
    profile = _experiment_safe_token_v1(getattr(ctx, "profile", ""), default="")

    parts = [stamp, benchmark]
    if label:
        parts.append(label)
    elif profile:
        parts.append(profile)

    return "__".join(parts)


def experiment_jsonl_paths_v1(
    ctx: Ctx,
    *,
    run_id: str | None = None,
    run_id_factory: RunIdFactory = experiment_make_run_id_v1,
) -> dict[str, Any]:
    """Return the effective output directory and JSONL paths for the current protocol.

    This is the single source of truth for prepared output locations used by
    both the interactive menu and the execution layer. The optional
    ``run_id_factory`` is supplied by the runner compatibility wrapper so tests
    and downstream tools can continue replacing the runner-visible run-id hook.
    """
    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    rid = run_id or run_id_factory(ctx, cfg)
    out_dir = os.path.normpath(cfg.output_dir)

    cycle_json_path = None
    episode_json_path = None

    if cfg.jsonl_write_cycle_records:
        cycle_json_path = os.path.join(out_dir, f"{rid}__cycle.jsonl")

    if cfg.jsonl_write_episode_records:
        episode_json_path = os.path.join(out_dir, f"{rid}__episode.jsonl")

    return {
        "run_id": rid,
        "output_dir": out_dir,
        "cycle_json_path": cycle_json_path,
        "episode_json_path": episode_json_path,
    }


def append_experiment_jsonl_record_v1(path: str | None, record: dict[str, Any]) -> None:
    """Append one JSON-safe record to a JSONL path.

    Purpose / intent
    ----------------
    The runner already has a generic per-cycle JSON writer later in the file. We still need
    a tiny generic helper for experiment-side JSONL writes, especially for episode summaries.

    Design
    ------
    - Best effort only: never raise into the runner.
    - UTF-8 JSONL, one record per line.
    - Creates the parent directory if needed.
    """
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


def _experiment_write_json_file_v1(path: str | None, payload: dict[str, Any]) -> None:
    """Write one JSON payload to disk as a pretty UTF-8 file.

    Purpose / intent
    ----------------
    The experiment runner already has JSONL append helpers for cycle and episode records.
    For paper-facing repeat statistics, I also want one stable JSON artifact that captures
    the exact repeat-level metric rows and paired statistics used to generate the tables.

    Design
    ------
    - Best effort only: never raise into the interactive runner.
    - UTF-8 JSON with indentation for human inspection.
    - Creates parent directories when needed.
    """
    if not isinstance(path, str) or not path.strip():
        return
    if not isinstance(payload, dict):
        return

    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    except Exception:
        return


def _experiment_protocol_snapshot_v1(cfg: ExperimentProtocolConfig) -> dict[str, Any]:
    """Return a compact JSON-safe snapshot of the current experiment protocol."""
    return {
        "protocol_version": str(cfg.protocol_version),
        "benchmark_id": str(cfg.benchmark_id),
        "condition_ids": list(cfg.condition_ids),
        "seed_list": list(cfg.seed_list),
        "episodes_per_seed": int(cfg.episodes_per_seed),
        "max_cycles": int(cfg.max_cycles),
        "obs_mask_prob": float(cfg.obs_mask_prob),
        "newborn_stress_profile": str(getattr(cfg, "newborn_stress_profile", "baseline")),
        "newborn_blackout_length": int(getattr(cfg, "newborn_blackout_length", 3) or 3),
        "effective_newborn_blackout_length": _newborn_effective_blackout_length_v1(
            getattr(cfg, "newborn_stress_profile", "baseline"),
            getattr(cfg, "newborn_blackout_length", 3),
        ),
        "action_vocab_version": str(cfg.action_vocab_version),
        "scratch_clear_policy": str(cfg.scratch_clear_policy),
        "jsonl_write_cycle_records": bool(cfg.jsonl_write_cycle_records),
        "jsonl_write_episode_records": bool(cfg.jsonl_write_episode_records),
        "llm_model": cfg.llm_model,
        "llm_adviser_ambiguity_delta": float(cfg.llm_adviser_ambiguity_delta),
        "llm_adviser_max_candidates": int(cfg.llm_adviser_max_candidates),
        "run_label": str(cfg.run_label or ""),
        "output_dir": str(cfg.output_dir or ""),
    }


def _experiment_collect_repeated_bundle_rows_v1(repeated_result: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flatten one repeated experiment result into episode-level and repeat-level rows.

    Why this exists
    ---------------
    The current repeat runner returns the table-generating statistics in memory, but that makes
    later provenance checking awkward. For paper use, I want two explicit row sets:

      1) episode_rows:
         one row per successfully completed episode across all repeats / conditions / seeds

      2) repeat_rows:
         one row per repeat × condition summarizing the metrics that are later aggregated into
         descriptive means, SDs, confidence intervals, and paired comparisons

    Both outputs are JSON-safe and easy to archive beside the manuscript.
    """
    episode_rows: list[dict[str, Any]] = []
    repeat_rows: list[dict[str, Any]] = []

    repeat_batches = repeated_result.get("repeat_batches")
    if not isinstance(repeat_batches, list):
        return episode_rows, repeat_rows

    for repeat_bundle in repeat_batches:
        if not isinstance(repeat_bundle, dict):
            continue

        repeat_index = repeat_bundle.get("repeat_index")
        seed_list = repeat_bundle.get("seed_list")
        batch = repeat_bundle.get("batch")
        if not isinstance(batch, dict):
            continue

        results = batch.get("results")
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                if not bool(item.get("ok")):
                    continue

                episode_record = item.get("episode_record")
                if not isinstance(episode_record, dict):
                    continue

                row = {
                    "schema": "experiment_episode_analysis_row_v1",
                    "repeat_index": int(repeat_index) if isinstance(repeat_index, int) else None,
                    "repeat_seed_list": list(seed_list) if isinstance(seed_list, list) else [],
                    "source_episode_run_id": item.get("run_id"),
                    "condition_label": item.get("condition_label"),
                    "effective_obs_mask_prob": item.get("effective_obs_mask_prob"),
                }
                row.update(dict(episode_record))
                episode_rows.append(row)

        condition_summaries = batch.get("condition_summaries")
        if isinstance(condition_summaries, list):
            for summary_row in condition_summaries:
                if not isinstance(summary_row, dict):
                    continue

                row = {
                    "schema": "experiment_repeat_condition_row_v1",
                    "repeat_index": int(repeat_index) if isinstance(repeat_index, int) else None,
                    "repeat_seed_list": list(seed_list) if isinstance(seed_list, list) else [],
                    "benchmark_id": batch.get("benchmark_id"),
                }
                row.update(dict(summary_row))
                repeat_rows.append(row)

    return episode_rows, repeat_rows


def _experiment_write_repeated_result_bundle_v1(
    ctx: Ctx,
    repeated_result: dict[str, Any],
    *,
    bundle_label: str,
    run_id_factory: RunIdFactory = experiment_make_run_id_v1,
) -> dict[str, Any]:
    """Persist the exact repeat-level data used to generate paper-facing statistics.

    Files written
    -------------
    1) <run_id>__episode_rows.jsonl
         one row per successful episode across all repeats
    2) <run_id>__repeat_rows.jsonl
         one row per repeat × condition summary
    3) <run_id>__stats.json
         the exact repeat-level metric rows and paired statistics used for the tables

    Important scientific point
    --------------------------
    The `repeat_metric_rows` object is the closest direct raw input to the repeat-level
    descriptive statistics and paired t-tests. I therefore write it explicitly into the
    stats JSON, rather than only writing the already-aggregated numbers.

    ``run_id_factory`` is an extraction seam. Direct module callers normally use
    the default; ``cca8_run`` supplies its visible helper to preserve compatibility.
    """
    if ctx is None:
        return {"ok": False, "why": "missing_ctx"}
    if not isinstance(repeated_result, dict) or not bool(repeated_result.get("ok")):
        return {"ok": False, "why": "invalid_repeated_result"}

    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    out_dir = os.path.normpath(cfg.output_dir)

    label = _experiment_safe_token_v1(bundle_label, default="repeat_bundle")
    run_id = run_id_factory(ctx, cfg)
    if label:
        run_id = f"{run_id}__{label}"

    episode_rows_path = os.path.join(out_dir, f"{run_id}__episode_rows.jsonl")
    repeat_rows_path = os.path.join(out_dir, f"{run_id}__repeat_rows.jsonl")
    stats_json_path = os.path.join(out_dir, f"{run_id}__stats.json")

    episode_rows, repeat_rows = _experiment_collect_repeated_bundle_rows_v1(repeated_result)

    for row in episode_rows:
        append_experiment_jsonl_record_v1(episode_rows_path, row)

    for row in repeat_rows:
        append_experiment_jsonl_record_v1(repeat_rows_path, row)

    stats_payload = {
        "schema": "experiment_repeated_stats_bundle_v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
        "bundle_label": label,
        "protocol": _experiment_protocol_snapshot_v1(cfg),
        "benchmark_id": repeated_result.get("benchmark_id"),
        "condition_ids": repeated_result.get("condition_ids"),
        "compare_condition_ids": repeated_result.get("compare_condition_ids"),
        "repeats": repeated_result.get("repeats"),
        "seeds_per_repeat": repeated_result.get("seeds_per_repeat"),
        "metric_keys": repeated_result.get("metric_keys"),
        "repeat_metric_rows": repeated_result.get("repeat_metric_rows"),
        "averages_by_condition": repeated_result.get("averages_by_condition"),
        "condition_metric_stats_by_condition": repeated_result.get("condition_metric_stats_by_condition"),
        "paired_stats_vs_a": repeated_result.get("paired_stats_vs_a"),
        "episode_rows_jsonl_path": episode_rows_path,
        "repeat_rows_jsonl_path": repeat_rows_path,
        "episode_row_count": int(len(episode_rows)),
        "repeat_row_count": int(len(repeat_rows)),
    }
    _experiment_write_json_file_v1(stats_json_path, stats_payload)

    try:
        if not isinstance(ctx.experiment_last_summary, dict):
            ctx.experiment_last_summary = {}
        ctx.experiment_last_summary["last_repeated_bundle_run_id"] = run_id
        ctx.experiment_last_summary["last_repeated_bundle_episode_rows_path"] = episode_rows_path
        ctx.experiment_last_summary["last_repeated_bundle_repeat_rows_path"] = repeat_rows_path
        ctx.experiment_last_summary["last_repeated_bundle_stats_json_path"] = stats_json_path
    except Exception:
        pass

    return {
        "ok": True,
        "run_id": run_id,
        "episode_rows_jsonl_path": episode_rows_path,
        "repeat_rows_jsonl_path": repeat_rows_path,
        "stats_json_path": stats_json_path,
        "episode_row_count": int(len(episode_rows)),
        "repeat_row_count": int(len(repeat_rows)),
    }


def experiment_prepare_logging_v1(
    ctx: Ctx,
    *,
    reset_buffers: bool = True,
    run_id_factory: RunIdFactory = experiment_make_run_id_v1,
) -> dict[str, Any]:
    """Normalize config and arm experiment JSONL output paths.

    What this prepares now
    ----------------------
    - validates / normalizes Menu 49 protocol fields,
    - creates the output directory,
    - points the existing cycle JSON writer at the prepared experiment cycle path,
    - stores the episode-summary JSONL path in ctx.experiment_last_summary.

    What this does NOT do yet
    -------------------------
    - it does not run any episodes,
    - it does not emit episode summaries,
    - it does not alter ordinary closed-loop runs unless Menu 49 explicitly invokes it.

    The optional ``run_id_factory`` keeps filename generation replaceable without
    importing ``cca8_run`` and creating a circular dependency.
    """
    if ctx is None:
        return {"ok": False, "why": "missing_ctx"}

    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    ctx.experiment_cfg = cfg

    paths = experiment_jsonl_paths_v1(ctx, run_id_factory=run_id_factory)
    out_dir = paths["output_dir"]

    try:
        if isinstance(out_dir, str) and out_dir:
            os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        return {"ok": False, "why": f"mkdir_failed:{e}"}

    cycle_path = paths.get("cycle_json_path")
    if cfg.jsonl_write_cycle_records and isinstance(cycle_path, str) and cycle_path:
        ctx.cycle_json_enabled = True
        ctx.cycle_json_path = cycle_path
    else:
        ctx.cycle_json_enabled = False
        ctx.cycle_json_path = None

    if reset_buffers:
        try:
            ctx.cycle_json_records.clear()
        except Exception:
            ctx.cycle_json_records = []

    summary = {
        "ok": True,
        "schema": "experiment_logging_prep_v1",
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": paths["run_id"],
        "benchmark_id": cfg.benchmark_id,
        "condition_ids": list(cfg.condition_ids),
        "seed_list": list(cfg.seed_list),
        "episodes_per_seed": int(cfg.episodes_per_seed),
        "max_cycles": int(cfg.max_cycles),
        "obs_mask_prob": float(cfg.obs_mask_prob),
        "newborn_stress_profile": str(getattr(cfg, "newborn_stress_profile", "baseline")),
        "newborn_blackout_length": int(getattr(cfg, "newborn_blackout_length", 3) or 3),
        "effective_newborn_blackout_length": _newborn_effective_blackout_length_v1(
            getattr(cfg, "newborn_stress_profile", "baseline"),
            getattr(cfg, "newborn_blackout_length", 3),
        ),
        "run_label": cfg.run_label,
        "output_dir": out_dir,
        "cycle_json_enabled": bool(ctx.cycle_json_enabled),
        "cycle_json_path": ctx.cycle_json_path,
        "episode_json_enabled": bool(cfg.jsonl_write_episode_records),
        "episode_json_path": paths.get("episode_json_path"),
        "cycle_json_max_records": int(getattr(ctx, "cycle_json_max_records", 0) or 0),
    }
    ctx.experiment_last_summary = summary
    return summary


def experiment_build_cycle_record_stub_v1(
    ctx: Ctx,
    *,
    experiment_id: str | None = None,
    condition_id: str = "A",
    seed: int = 11,
    episode_index: int = 0,
    cycle_index: int = 0,
    run_id_factory: RunIdFactory = experiment_make_run_id_v1,
    body_space_zone_fn: BodySpaceZoneFn = body_space_zone,
) -> dict[str, Any]:
    """Build one JSON-safe example cycle record using the current protocol contract.

    This is an example-record builder rather than a record captured from a live
    episode. The execution layer uses the same schema contract, while injected
    callbacks preserve the historical runner monkeypatch seams after extraction.
    """
    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    last = getattr(ctx, "experiment_last_summary", None)

    if isinstance(last, dict) and isinstance(last.get("run_id"), str) and last.get("run_id"):
        run_id = str(last["run_id"])
    else:
        run_id = run_id_factory(ctx, cfg)

    if isinstance(experiment_id, str) and experiment_id:
        run_id = experiment_id

    stage = getattr(ctx, "lt_obs_last_stage", None)

    zone = None
    try:
        zone = body_space_zone_fn(ctx)
    except Exception:
        zone = None

    retrieval_event = None
    if isinstance(getattr(ctx, "wm_mapswitch_last_events", None), list) and ctx.wm_mapswitch_last_events:
        retrieval_event = ctx.wm_mapswitch_last_events[-1]

    return {
        "schema": "experiment_cycle_record_v1",
        "record_type": "cycle",
        "experiment_id": run_id,
        "benchmark": cfg.benchmark_id,
        "condition": str(condition_id),
        "seed": int(seed),
        "episode_index": int(episode_index),
        "cycle_index": int(cycle_index),
        "env_step": int(getattr(ctx, "controller_steps", 0) or 0),
        "stage": stage if isinstance(stage, str) and stage else None,
        "zone": zone if isinstance(zone, str) and zone else None,
        "obs_mask_stats": {
            "prob": float(cfg.obs_mask_prob),
            "seed": getattr(ctx, "obs_mask_seed", None),
        },
        "retrieval_event": retrieval_event,
        "pred_err": dict(getattr(ctx, "pred_err_v0_last", {}) or {}),
        "selected_policy": None,
        "llm_advice_summary": None,
        "executed_action": getattr(ctx, "env_last_action", None),
        "milestones": [],
        "oracle": None,
        "done": False,
        "termination_reason": None,
    }


def experiment_build_episode_record_stub_v1(
    ctx: Ctx,
    *,
    experiment_id: str | None = None,
    condition_id: str = "A",
    seed: int = 11,
    episode_index: int = 0,
    run_id_factory: RunIdFactory = experiment_make_run_id_v1,
) -> dict[str, Any]:
    """Build one JSON-safe example episode-summary record using the current protocol contract.

    ``run_id_factory`` is normally left at its module default. The runner wrapper
    supplies its visible helper so existing tests can replace filename generation.
    """
    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    last = getattr(ctx, "experiment_last_summary", None)

    if isinstance(last, dict) and isinstance(last.get("run_id"), str) and last.get("run_id"):
        run_id = str(last["run_id"])
    else:
        run_id = run_id_factory(ctx, cfg)

    if isinstance(experiment_id, str) and experiment_id:
        run_id = experiment_id

    return {
        "schema": "experiment_episode_record_v1",
        "record_type": "episode_summary",
        "experiment_id": run_id,
        "benchmark": cfg.benchmark_id,
        "condition": str(condition_id),
        "seed": int(seed),
        "episode_index": int(episode_index),
        "success": None,
        "cycles_to_end": None,
        "milestone_vector": {},
        "milestone_score": None,
        "context_switch_accuracy": None,
        "false_retrieval_count": 0,
        "cue_leakage_violations": 0,
        "cumulative_prediction_error": None,
        "repeated_action_loop_count": 0,
        "llm_call_count": 0,
        "llm_latency_ms_total": None,
        "latency_ms_total": None,
        "recovery_latency": None,
        "oracle_action_accuracy": None,
        "oracle_retrieval_precision": None,
        "internal_retrieval_event_ratio": None,
        "stabilization_latency": None,
        "retrieval_action_dissociation_count": 0,
    }


def experiment_write_episode_record_v1(ctx: Ctx, record: dict[str, Any]) -> None:
    """Append an episode-summary record to the prepared experiment episode JSONL path.

    This is intentionally separate from the existing cycle writer. Later execution code can
    call this directly after an episode ends.
    """
    if ctx is None or not isinstance(record, dict):
        return

    summary = getattr(ctx, "experiment_last_summary", None)
    if not isinstance(summary, dict):
        return

    path = summary.get("episode_json_path")
    append_experiment_jsonl_record_v1(path if isinstance(path, str) else None, record)


# --- Experiment execution runtime --------------------------------------------------


def experiment_make_sandbox_runtime_v1(runtime: ExperimentRuntime) -> dict[str, Any]:
    """Build one isolated experiment runtime without touching the live interactive session.

    Purpose / intent
    ----------------
    Menu 49 needs a way to start running real experiment episodes while keeping the
    ordinary CCA8 session non-destructive. Rather than mutating the user's current
    world, drives, and context, this helper builds a fresh sandbox runtime that mirrors
    the interactive runner's default wiring closely enough for the experiment harness.

    Design notes
    ------------
    - The sandbox keeps per-cycle JSON capture ON, but defaults to in-memory buffering
      until the experiment helper transforms those raw cycle traces into experiment
      schema records.
    - Verbose ASCII/SurfaceGrid output is turned OFF here so experiment runs can stay
      compact unless a caller explicitly asks for full console output.
    """
    world = runtime.world_factory()
    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)

    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)
    ctx.navpatch_enabled = True
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    ctx.cycle_json_max_records = 2000

    ctx.efe_enabled = True
    ctx.efe_verbose = False
    ctx.efe_w_risk = 1.0
    ctx.efe_w_ambiguity = 1.0
    ctx.efe_w_preference = 1.0

    ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump)
    ctx.tvec_last_boundary = ctx.temporal.vector()
    try:
        ctx.boundary_vhash64 = ctx.tvec64()
    except Exception:
        ctx.boundary_vhash64 = None

    ctx.wm_surfacegrid_verbose = False
    ctx.wm_surfacegrid_ascii_each_tick = False
    ctx.obs_mask_verbose = False

    env = HybridEnvironment()
    ctx.body_world, ctx.body_ids = runtime.init_body_world()
    ctx.working_world = runtime.init_working_world()

    policy_rt = runtime.policy_runtime_factory()
    policy_rt.refresh_loaded(ctx)

    return {
        "world": world,
        "drives": drives,
        "ctx": ctx,
        "env": env,
        "policy_rt": policy_rt,
    }


def experiment_configure_benchmark_runtime_v1(
    world: Any,
    drives: Drives,
    ctx: Ctx,
    env: HybridEnvironment,
    benchmark_id: str,
    *,
    runtime: ExperimentRuntime,
) -> dict[str, Any]:
    """Configure one sandbox runtime for the chosen experiment benchmark.

    This helper is intentionally benchmark-scoped. Condition A/B/C runtime knobs are
    applied later by ``experiment_apply_condition_runtime_v1(...)`` so the benchmark
    wiring and the scientific comparison wiring remain separate.
    """
    catalog = experiment_benchmark_catalog_v1()
    if benchmark_id not in catalog:
        return {"ok": False, "why": f"unknown_benchmark:{benchmark_id}"}

    if ctx is None or env is None:
        return {"ok": False, "why": "missing_runtime"}

    try:
        runtime.apply_hardwired_profile(ctx, world)
    except Exception:
        pass

    if benchmark_id == "goat04_context":
        try:
            runtime.configure_goat_foraging(world, drives, ctx, env)
        except Exception as e:
            return {"ok": False, "why": f"benchmark_setup_failed:{e}"}
    elif benchmark_id == "newborn_long_horizon":
        try:
            env.config = EnvConfig(
                scenario_name="newborn_goat_first_hour_benchmark_hard",
                dt=getattr(env.config, "dt", 1.0),
            )
        except Exception:
            try:
                env.config.scenario_name = "newborn_goat_first_hour_benchmark_hard"
            except Exception:
                return {"ok": False, "why": "benchmark_setup_failed:newborn_env_config"}

        try:
            ctx.longterm_obs_keyframe_on_stage_change = True
            ctx.longterm_obs_keyframe_on_zone_change = True
            ctx.longterm_obs_keyframe_on_milestone = True
        except Exception:
            pass

        try:
            ctx.wm_mapsurface_autoretrieve_enabled = True
            ctx.wm_mapsurface_autoretrieve_mode = "merge"
            ctx.wm_mapsurface_autoretrieve_top_k = 5
            ctx.wm_mapsurface_autoretrieve_verbose = False
        except Exception:
            pass

        try:
            # Benchmark-only hardening:
            # during newborn B2, bridge logic must trust fresh current-state memory
            # rather than silently reconstructing "truth now" from old episode history.
            ctx.experiment_newborn_require_current_state = True
        except Exception:
            pass

        try:
            # Benchmark-only hardening:
            # if current evidence is missing during a blackout, bridge logic must
            # have a recent successful retrieval in order to resume task progress.
            ctx.experiment_newborn_require_resume_memory = True
        except Exception:
            pass

        try:
            ctx.env_episode_started = False
            ctx.env_last_action = None
        except Exception:
            pass

        try:
            drives.hunger = 0.50
            drives.fatigue = 0.30
            drives.warmth = 0.60
        except Exception:
            pass

        try:
            runtime.reset_working_world(ctx)
        except Exception:
            pass

        try:
            ctx.wm_mapswitch_last_events = []
            ctx.wm_mapswitch_history = []
        except Exception:
            pass

        try:
            ctx.wm_newborn_b2_seeded_labels = set()
            ctx.wm_newborn_b2_seed_engram_by_label = {}
        except Exception:
            pass

        try:
            ctx.experiment_newborn_retrieved_hint = {}
            ctx.experiment_newborn_retrieved_hint_until_step = -1
            ctx.experiment_newborn_retrieved_hint_source = None
            ctx.experiment_newborn_retrieved_hint_set_count = 0
            ctx.experiment_newborn_retrieved_hint_active_step_count = 0
            ctx.experiment_newborn_retrieved_hint_used_step_count = 0
            ctx.experiment_newborn_retrieved_hint_last_active_step_counted = -1
            ctx.experiment_newborn_retrieved_hint_last_used_step_counted = -1
            ctx.experiment_newborn_retrieved_hint_events = []
            ctx.experiment_policy_debug_last = {}
            ctx.experiment_policy_debug_events = []
            ctx.experiment_newborn_blackout_start_step = -1
            ctx.experiment_newborn_blackout_until_step = -1
            ctx.experiment_newborn_blackout_reason = None
        except Exception:
            pass

    else:
        return {"ok": False, "why": f"unsupported_benchmark:{benchmark_id}"}

    return {
        "ok": True,
        "benchmark_id": benchmark_id,
        "benchmark_label": catalog[benchmark_id].label,
    }


def experiment_apply_condition_runtime_v1(
    world,
    drives,
    ctx: Ctx,
    env: HybridEnvironment,
    *,
    condition_id: str,
    cfg: ExperimentProtocolConfig | None = None,
) -> dict[str, Any]:
    """Apply one frozen A-E condition onto a sandbox runtime.

    Scope of this patch
    -------------------
    - A/B/C remain the pure CCA8 memory-discipline conditions.
    - E now enables the bounded LLM adviser while keeping CCA8 authoritative.
    - D remains intentionally unsupported until we build a true LLM-only controller path.
    """
    _ = world
    _ = drives
    _ = env

    catalog = experiment_condition_catalog_v1()
    cid = str(condition_id or "").strip().upper()
    cond = catalog.get(cid)
    if cond is None:
        return {"ok": False, "why": f"unknown_condition:{condition_id}"}

    if cond.agent_mode == "llm_only":
        return {
            "ok": False,
            "why": "condition_not_yet_supported",
            "condition_id": cid,
            "agent_mode": cond.agent_mode,
            "llm_role": cond.llm_role,
        }

    cfg_norm = experiment_normalize_protocol_v1(cfg)

    try:
        ctx.experiment_cfg = cfg_norm
    except Exception:
        pass

    try:
        ctx.wm_mapsurface_autoretrieve_enabled = bool(cond.retrieval_enabled)
        ctx.wm_mapsurface_autoretrieve_mode = cond.retrieval_mode if cond.retrieval_mode in ("merge", "replace") else "merge"
        ctx.wm_mapsurface_autoretrieve_top_k = 5
        ctx.wm_mapsurface_autoretrieve_verbose = False
    except Exception:
        return {"ok": False, "why": "condition_apply_failed:autoretrieve"}

    try:
        ctx.obs_mask_prob = float(cfg_norm.obs_mask_prob)
        ctx.obs_mask_last_cfg_sig = None
        ctx.obs_mask_verbose = False
    except Exception:
        pass

    try:
        ctx.experiment_active_condition_id = cid
        ctx.experiment_active_condition_label = cond.label
        ctx.experiment_llm_role = cond.llm_role
        ctx.experiment_llm_adviser_enabled = bool(cond.llm_role == "advisor" and cond.decision_authority == "cca8")
        ctx.experiment_llm_model_name = cfg_norm.llm_model.strip() if isinstance(cfg_norm.llm_model, str) and cfg_norm.llm_model.strip() else None
        ctx.experiment_llm_call_count = 0
        ctx.experiment_llm_latency_ms_total = 0.0
        ctx.experiment_last_llm_advice_summary = {}
        ctx.experiment_llm_first_error_printed = False
        ctx.experiment_llm_first_error_summary = None
    except Exception:
        pass

    return {
        "ok": True,
        "condition_id": cid,
        "label": cond.label,
        "agent_mode": cond.agent_mode,
        "decision_authority": cond.decision_authority,
        "retrieval_enabled": bool(cond.retrieval_enabled),
        "retrieval_mode": cond.retrieval_mode,
        "llm_role": cond.llm_role,
        "llm_adviser_enabled": bool(getattr(ctx, "experiment_llm_adviser_enabled", False)),
    }


def _experiment_llm_candidate_rows_v1(
    matches: list[Any],
    *,
    world,
    drives: Drives,
    ctx: Ctx,
    deficit_fn: Callable[[str], float],
    non_drive_fn: Callable[[str], float],
    stable_idx_fn: Callable[[Any], int],
) -> dict[str, Any]:
    """Build a bounded candidate set for the hybrid LLM adviser.

    The adviser should not see every possible policy in the architecture. It should only see
    the currently-triggered candidate set, bounded further to the near-best deficit band so it
    functions as a tie-break adviser rather than a free-running controller.
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(matches, list) or len(matches) < 2:
        return {"candidate_rows": [], "all_rows": [], "best_deficit": 0.0, "delta": 0.0}

    for gate in matches:
        try:
            name = str(getattr(gate, "name", "") or "")
        except Exception:
            name = ""
        if not name:
            continue

        explain_text = None
        try:
            explain_fn = getattr(gate, "explain", None)
            if callable(explain_fn):
                explain_text = str(explain_fn(world, drives, ctx) or "")
        except Exception:
            explain_text = None

        if isinstance(explain_text, str) and len(explain_text) > 240:
            explain_text = explain_text[:237] + "..."

        rows.append(
            {
                "policy": name,
                "deficit": round(float(deficit_fn(name)), 3),
                "non_drive_priority": round(float(non_drive_fn(name)), 3),
                "q": round(float(skill_q(name, default=0.0)), 3),
                "stable_order": int(stable_idx_fn(gate)),
                "trigger_explanation": explain_text,
            }
        )

    if len(rows) < 2:
        return {"candidate_rows": [], "all_rows": rows, "best_deficit": 0.0, "delta": 0.0}

    rows.sort(key=lambda row: (-float(row["deficit"]), -float(row["non_drive_priority"]), int(row["stable_order"])))
    best_deficit = max(float(row["deficit"]) for row in rows)

    try:
        delta = float(getattr(getattr(ctx, "experiment_cfg", None), "llm_adviser_ambiguity_delta", 0.10) or 0.10)
    except Exception:
        delta = 0.10
    delta = max(0.0, min(1.0, delta))

    candidate_rows = [row for row in rows if (best_deficit - float(row["deficit"])) <= delta]
    if len(candidate_rows) < 2:
        candidate_rows = rows[:2]

    try:
        max_candidates = int(getattr(getattr(ctx, "experiment_cfg", None), "llm_adviser_max_candidates", 4) or 4)
    except Exception:
        max_candidates = 4
    max_candidates = max(2, min(8, max_candidates))
    candidate_rows = candidate_rows[:max_candidates]

    return {
        "candidate_rows": candidate_rows,
        "all_rows": rows,
        "best_deficit": round(best_deficit, 3),
        "delta": round(delta, 3),
    }


def _experiment_llm_adviser_reply_schema_v1(candidate_names: list[str]) -> dict[str, Any]:
    """Return the strict JSON schema for one bounded LLM-adviser reply."""
    names = [name for name in candidate_names if isinstance(name, str) and name]
    max_items = max(1, len(names))
    return {
        "type": "object",
        "properties": {
            "recommended_policy": {"type": "string", "enum": names},
            "ranking": {
                "type": "array",
                "items": {"type": "string", "enum": names},
                "minItems": 1,
                "maxItems": max_items,
            },
            "rationale": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["recommended_policy", "ranking", "rationale", "confidence", "risk_flags"],
        "additionalProperties": False,
    }


def _experiment_llm_adviser_prompt_v1(request_obj: dict[str, Any]) -> str:
    """Build the conservative adviser prompt for condition E."""
    return (
        "You are a bounded policy adviser inside a CCA8 experiment. "
        "The architecture remains authoritative. "
        "Use only the supplied JSON state summary and the supplied candidate policies. "
        "Choose exactly one policy from the candidate list. "
        "Do not invent policies, sensors, goals, or hidden world state. "
        "Prefer conservative, safety-aware advice. "
        "Return only a JSON object matching the required schema.\n\n"
        "CCA8 HYBRID-ADVISER REQUEST JSON:\n"
        f"{json.dumps(request_obj, ensure_ascii=False)}"
    )


def _run_experiment_llm_adviser_once_v1(
    world: Any,
    drives: Drives,
    ctx: Ctx,
    candidate_rows: list[dict[str, Any]],
    *,
    runtime: ExperimentRuntime,
) -> dict[str, Any]:
    """Call the OpenAI Responses API once for condition E and return a JSON-safe summary.

    The caller is expected to fall back to the normal CCA8 heuristic if this returns `ok=False`
    or if the reply recommends a policy outside the supplied bounded candidate list.
    """
    names: list[str] = []
    for row in candidate_rows:
        if not isinstance(row, dict):
            continue
        policy_name = row.get("policy")
        if isinstance(policy_name, str) and policy_name:
            names.append(policy_name)
    if len(names) < 2:
        return {
            "enabled": True,
            "called": False,
            "ok": False,
            "why": "not_ambiguous",
            "candidate_policies": list(names),
        }

    model_name = None
    try:
        model_name = getattr(ctx, "experiment_llm_model_name", None)
    except Exception:
        model_name = None
    if not isinstance(model_name, str) or not model_name.strip():
        try:
            model_name = runtime.openai_default_model_name()
        except Exception:
            model_name = None
    if not isinstance(model_name, str) or not model_name.strip():
        return {
            "enabled": True,
            "called": False,
            "ok": False,
            "why": "no_model",
            "candidate_policies": list(names),
            "model": None,
        }
    model_name = model_name.strip()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "enabled": True,
            "called": False,
            "ok": False,
            "why": "no_api_key",
            "candidate_policies": list(names),
            "model": model_name,
        }

    state_summary = runtime.build_llm_state_summary(world, drives, ctx)
    request_obj = {
        "schema": "cca8_experiment_llm_adviser_request_v1",
        "benchmark": getattr(getattr(ctx, "experiment_cfg", None), "benchmark_id", None),
        "condition": getattr(ctx, "experiment_active_condition_id", None),
        "state": state_summary,
        "candidate_policies": candidate_rows,
    }
    schema = _experiment_llm_adviser_reply_schema_v1(names)
    prompt = _experiment_llm_adviser_prompt_v1(request_obj)

    try:
        request_opts = runtime.openai_response_request_options()
        if not isinstance(request_opts, dict):
            request_opts = {}
    except Exception:
        request_opts = {}

    request_opts = runtime.openai_sanitize_adviser_request_options(request_opts)
    if "max_output_tokens" not in request_opts:
        request_opts["max_output_tokens"] = 220

    runtime.openai_quiet_http_loggers()

    t0 = time.time()
    try:
        import openai  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
        from openai import OpenAI  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
    except Exception as e:
        return {
            "enabled": True,
            "called": False,
            "ok": False,
            "why": "sdk_import_error",
            "error": str(e),
            "candidate_policies": list(names),
            "model": model_name,
        }

    try:
        client = OpenAI(api_key=api_key, timeout=20.0)
        response = client.responses.create(
            model=model_name,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "cca8_experiment_llm_adviser_reply_v1",
                    "strict": True,
                    "schema": schema,
                }
            },
            **request_opts,
        )
        duration_ms = int((time.time() - t0) * 1000.0)
        raw = runtime.openai_response_text(response)

    except openai.RateLimitError as e:
        duration_ms = int((time.time() - t0) * 1000.0)
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "rate_limit_error",
            "error": str(e),
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
        }
    except openai.APIConnectionError as e:
        duration_ms = int((time.time() - t0) * 1000.0)
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "api_connection_error",
            "error": str(e),
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
        }
    except openai.APIStatusError as e:
        duration_ms = int((time.time() - t0) * 1000.0)
        detail = runtime.openai_api_error_detail(e)
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "api_status_error",
            "error": detail.get("message"),
            "error_detail": detail,
            "status_code": detail.get("status_code"),
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000.0)
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "unexpected_error",
            "error": f"{e.__class__.__name__}: {e}",
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
        }

    if not isinstance(raw, str) or not raw.strip():
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "no_output_text",
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
            "response_id": getattr(response, "id", None),
            "usage": runtime.llm_response_usage(response),
        }

    try:
        reply = json.loads(raw)
    except Exception as e:
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "json_parse_error",
            "error": str(e),
            "raw_text": raw,
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
            "response_id": getattr(response, "id", None),
            "usage": runtime.llm_response_usage(response),
        }

    recommended = reply.get("recommended_policy")
    if not isinstance(recommended, str) or recommended not in names:
        return {
            "enabled": True,
            "called": True,
            "ok": False,
            "why": "invalid_recommended_policy",
            "reply": reply,
            "candidate_policies": list(names),
            "model": model_name,
            "latency_ms": duration_ms,
            "response_id": getattr(response, "id", None),
            "usage": runtime.llm_response_usage(response),
        }

    ranking_in = reply.get("ranking")
    ranking: list[str] = []
    if isinstance(ranking_in, list):
        for item in ranking_in:
            if isinstance(item, str) and item in names and item not in ranking:
                ranking.append(item)
    if recommended not in ranking:
        ranking.insert(0, recommended)

    risk_flags = reply.get("risk_flags")
    if not isinstance(risk_flags, list):
        risk_flags = []
    risk_flags = [str(item) for item in risk_flags if isinstance(item, str) and item]

    confidence = reply.get("confidence")
    try:
        confidence_val = float(confidence)
    except Exception:
        confidence_val = None

    return {
        "enabled": True,
        "called": True,
        "ok": True,
        "why": "ok",
        "model": model_name,
        "candidate_policies": list(names),
        "recommended_policy": recommended,
        "ranking": ranking,
        "rationale": reply.get("rationale"),
        "confidence": confidence_val,
        "risk_flags": risk_flags,
        "latency_ms": duration_ms,
        "response_id": getattr(response, "id", None),
        "usage": runtime.llm_response_usage(response),
    }


def _experiment_extract_generic_milestones_v1(raw_record: dict[str, Any]) -> list[str]:
    """Extract a normalized milestone list from one generic cycle JSON record."""
    obs = raw_record.get("obs") if isinstance(raw_record, dict) else None
    env_meta = obs.get("env_meta") if isinstance(obs, dict) else None
    env_meta = env_meta if isinstance(env_meta, dict) else {}

    raw = env_meta.get("milestones")
    if raw is None:
        raw = env_meta.get("milestone")

    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]

    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    return out


def _experiment_summarize_newborn_b2_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the paper-frozen B2 newborn benchmark from raw cycle records.

    B2 is the behavioral long-horizon benchmark. The experiment freezes a
    six-step ordered milestone ladder:
        1) stood_up
        2) reached_mom
        3) found_nipple
        4) latched_nipple
        5) milk_drinking
        6) rested

    v2 scoring / debugging additions
    --------------------------------
    The old summary told us whether the episode eventually succeeded, but it hid the
    later timing structure. We now keep the old fields and add milestone-step timing
    so A/B/C separation can show up even when all three conditions eventually succeed.

    Returns a small JSON-safe dict containing:
      - milestone_vector
      - milestone_steps
      - milestone_score
      - recovery_latency          (time to stood_up; preserved for back-compat)
      - time_to_rested            (absolute env step of final completion)
      - mom_approach_latency      (reached_mom - stood_up)
      - nipple_find_latency       (found_nipple - reached_mom)
      - latch_latency             (latched_nipple - found_nipple)
      - rest_completion_latency   (rested - latched_nipple)
      - success
    """
    ordered = [
        "stood_up",
        "reached_mom",
        "found_nipple",
        "latched_nipple",
        "milk_drinking",
        "rested",
    ]
    milestone_vector = {name: False for name in ordered}
    milestone_steps: dict[str, int | None] = {name: None for name in ordered}
    recovery_latency: float | None = None

    def _step_delta(start_name: str, end_name: str) -> float | None:
        start = milestone_steps.get(start_name)
        end = milestone_steps.get(end_name)
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        return float(end - start)

    next_idx = 0
    for cycle_index, raw in enumerate(raw_records):
        obs = raw.get("obs") if isinstance(raw, dict) else None
        obs = obs if isinstance(obs, dict) else {}
        preds_raw = obs.get("predicates") if isinstance(obs, dict) else None
        preds = {str(x) for x in preds_raw} if isinstance(preds_raw, list) else set()

        posture = raw.get("posture") if isinstance(raw, dict) else None
        mom_distance = raw.get("mom_distance") if isinstance(raw, dict) else None
        nipple_state = raw.get("nipple_state") if isinstance(raw, dict) else None
        zone = raw.get("zone") if isinstance(raw, dict) else None

        events: set[str] = set()

        if posture in ("standing", "latched", "resting") or "posture:standing" in preds:
            events.add("stood_up")

        if mom_distance in ("near", "touching") or "proximity:mom:close" in preds:
            events.add("reached_mom")

        if nipple_state in ("visible", "reachable", "latched") or "nipple:found" in preds:
            events.add("found_nipple")

        if nipple_state == "latched" or "nipple:latched" in preds:
            events.add("latched_nipple")

        if "milk:drinking" in preds:
            events.add("milk_drinking")

        if (posture == "resting" or "resting" in preds) and zone == "safe":
            events.add("rested")

        while next_idx < len(ordered) and ordered[next_idx] in events:
            name = ordered[next_idx]
            env_step = raw.get("env_step") if isinstance(raw, dict) else None
            try:
                step_value = int(env_step) if env_step is not None else int(cycle_index)
            except Exception:
                step_value = int(cycle_index)

            milestone_vector[name] = True
            milestone_steps[name] = step_value

            if name == "stood_up" and recovery_latency is None:
                recovery_latency = float(step_value)

            next_idx += 1

    achieved_count = sum(1 for name in ordered if milestone_vector[name])
    milestone_score = achieved_count / float(len(ordered))

    time_to_rested = None
    rested_step = milestone_steps.get("rested")
    if isinstance(rested_step, int):
        time_to_rested = float(rested_step)

    return {
        "milestone_vector": milestone_vector,
        "milestone_steps": milestone_steps,
        "milestone_score": milestone_score,
        "recovery_latency": recovery_latency,
        "time_to_rested": time_to_rested,
        "mom_approach_latency": _step_delta("stood_up", "reached_mom"),
        "nipple_find_latency": _step_delta("reached_mom", "found_nipple"),
        "latch_latency": _step_delta("found_nipple", "latched_nipple"),
        "rest_completion_latency": _step_delta("latched_nipple", "rested"),
        "success": bool(achieved_count == len(ordered)),
    }


def _newborn_retrieval_debug_from_raw_records_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize newborn B2 retrieval/apply behavior from raw cycle records.

    Why this exists
    ---------------
    We now know that "retrieval happened" is not enough. We need to distinguish:

      - no retrieval at all,
      - retrieval events that were merge no-ops,
      - retrieval events that actually changed the WorkingMap,
      - and replace-mode retrieval frequency.

    This helper is purely diagnostic. It does not change behavior.
    """
    retrieval_event_count = 0
    retrieval_ok_count = 0
    retrieval_non_noop_count = 0
    retrieval_merge_noop_count = 0
    retrieval_replace_count = 0
    retrieval_steps: list[int] = []

    for raw in raw_records:
        wm = raw.get("wm") if isinstance(raw, dict) else None
        wm = wm if isinstance(wm, dict) else {}
        mapswitch = wm.get("mapswitch") if isinstance(wm, dict) else None
        mapswitch = mapswitch if isinstance(mapswitch, dict) else {}
        events = mapswitch.get("events") if isinstance(mapswitch, dict) else None
        events = events if isinstance(events, list) else []

        for event in events:
            if not isinstance(event, dict):
                continue
            reason = event.get("reason")
            if not (isinstance(reason, str) and reason.startswith("newborn_b2:")):
                continue

            retrieval_event_count += 1
            if bool(event.get("ok")):
                retrieval_ok_count += 1

            step_value = raw.get("env_step")
            if isinstance(step_value, int):
                retrieval_steps.append(int(step_value))

            load = event.get("load")
            load = load if isinstance(load, dict) else {}
            mode = str(load.get("mode") or "").strip().lower()

            if mode == "replace":
                retrieval_replace_count += 1
                ent_n = int(load.get("entities", 0) or 0)
                rel_n = int(load.get("relations", 0) or 0)
                if ent_n > 0 or rel_n > 0:
                    retrieval_non_noop_count += 1
            else:
                ae = int(load.get("added_entities", 0) or 0)
                fs = int(load.get("filled_slots", 0) or 0)
                ed = int(load.get("added_edges", 0) or 0)
                pc = int(load.get("stored_prior_cues", 0) or 0)

                if ae > 0 or fs > 0 or ed > 0 or pc > 0:
                    retrieval_non_noop_count += 1
                else:
                    retrieval_merge_noop_count += 1

    return {
        "retrieval_event_count": int(retrieval_event_count),
        "retrieval_ok_count": int(retrieval_ok_count),
        "retrieval_non_noop_count": int(retrieval_non_noop_count),
        "retrieval_merge_noop_count": int(retrieval_merge_noop_count),
        "retrieval_replace_count": int(retrieval_replace_count),
        "retrieval_steps": retrieval_steps[:24],
    }


def _newborn_stress_debug_from_raw_records_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize newborn stress exposure from raw cycle records."""
    profiles: set[str] = set()
    active_cycle_count = 0
    dropped_pred_count = 0
    dropped_cue_count = 0
    reasons: set[str] = set()

    for raw in raw_records:
        if not isinstance(raw, dict):
            continue

        obs = raw.get("obs")
        obs = obs if isinstance(obs, dict) else {}
        meta = obs.get("env_meta")
        meta = meta if isinstance(meta, dict) else {}

        profile = meta.get("newborn_stress_profile")
        if isinstance(profile, str) and profile:
            profiles.add(profile)

        if bool(meta.get("newborn_blackout_active")):
            active_cycle_count += 1

        try:
            dropped_pred_count += int(meta.get("newborn_blackout_dropped_preds", 0) or 0)
        except Exception:
            pass

        try:
            dropped_cue_count += int(meta.get("newborn_blackout_dropped_cues", 0) or 0)
        except Exception:
            pass

        reason = meta.get("newborn_blackout_reason")
        if isinstance(reason, str) and reason:
            reasons.add(reason)

    if not profiles:
        profiles.add("baseline")

    if len(profiles) == 1:
        profile_out = sorted(profiles)[0]
    else:
        profile_out = "+".join(sorted(profiles))

    return {
        "newborn_stress_profile": profile_out,
        "newborn_stress_active_cycle_count": int(active_cycle_count),
        "newborn_stress_dropped_pred_count": int(dropped_pred_count),
        "newborn_stress_dropped_cue_count": int(dropped_cue_count),
        "newborn_stress_reasons": sorted(reasons),
    }


def _goat04_oracle_from_raw_record_v1(raw_record: dict[str, Any]) -> dict[str, Any]:
    """Return the hidden goat04 oracle payload from one raw cycle record."""
    oracle = raw_record.get("oracle") if isinstance(raw_record, dict) else None
    oracle = oracle if isinstance(oracle, dict) else {}
    goat04 = oracle.get("goat04") if isinstance(oracle, dict) else None
    return goat04 if isinstance(goat04, dict) else {}


def _goat04_seed_context_by_engram_v1(ctx: Ctx) -> dict[str, str]:
    """Build reverse map engram_id -> goat04 context label from seeded benchmark snapshots."""
    raw = getattr(ctx, "wm_goat04_seed_engram_by_context", None)
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for label, engram_id in raw.items():
            if isinstance(label, str) and label and isinstance(engram_id, str) and engram_id:
                out[engram_id] = label
    return out


def _goat04_retrieved_context_from_event_v1(ctx: Ctx, event: dict[str, Any]) -> str | None:
    """Best-effort recovered context label for one goat04 retrieval/apply event."""
    chosen_seed = event.get("chosen_seed") if isinstance(event, dict) else None
    chosen_seed = chosen_seed if isinstance(chosen_seed, dict) else {}
    engram_id = chosen_seed.get("engram_id")
    if not isinstance(engram_id, str) or not engram_id:
        return None
    return _goat04_seed_context_by_engram_v1(ctx).get(engram_id)


def _goat04_context_hint_active_v1(ctx: Ctx | None) -> str | None:
    """Return the currently active goat04 control hint, if any.

    This helper is intentionally tiny and read-only from the point of view of gates.
    A hint is active only if:
      - ctx.goat04_control_context is a recognized label ('fox' or 'hawk')
      - and the current controller step has not passed goat04_control_until_step

    We do not silently invent fallback labels here. If retrieval did not produce a usable
    context hint, the gates should behave as they normally do.
    """
    if ctx is None:
        return None

    label = getattr(ctx, "goat04_control_context", None)
    if not (isinstance(label, str) and label in ("fox", "hawk")):
        return None

    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
        until_step = int(getattr(ctx, "goat04_control_until_step", -1) or -1)
    except Exception:
        return None

    if step_now > until_step:
        return None
    return label


def _goat04_update_control_hint_v1(ctx: Ctx | None) -> dict[str, Any]:
    """Update the short-lived goat04 control hint from the latest map-switch event.

    Design intent
    -------------
    B1 should not merely show that a retrieval event occurred. It should show that a
    recovered context can influence downstream control. This helper creates the minimal
    bridge from WorkingMap/Column retrieval into policy gating.

    Rules
    -----
    - Only goat04 retrieval/apply events are considered.
    - Successful retrieval with a decoded context label ('fox' or 'hawk') activates a
      control hint lasting through the current step plus the next 3 steps. That matches
      the environment-side oracle response window size.
    - Failed retrieval clears any previous hint so stale context does not bleed across
      a new switch opportunity.

    Returns
    -------
    JSON-safe dict for logging/debugging:
      {
        "updated": bool,
        "active": "fox" | "hawk" | None,
        "source": "retrieval" | None,
        "until_step": int,
      }
    """
    if ctx is None:
        return {"updated": False, "active": None, "source": None, "until_step": -1}

    events = getattr(ctx, "wm_mapswitch_last_events", None)
    event = events[-1] if isinstance(events, list) and events and isinstance(events[-1], dict) else None
    if not isinstance(event, dict):
        return {
            "updated": False,
            "active": _goat04_context_hint_active_v1(ctx),
            "source": getattr(ctx, "goat04_control_source", None),
            "until_step": int(getattr(ctx, "goat04_control_until_step", -1) or -1),
        }

    reason = event.get("reason")
    if not (isinstance(reason, str) and reason.startswith("goat04_context:")):
        return {
            "updated": False,
            "active": _goat04_context_hint_active_v1(ctx),
            "source": getattr(ctx, "goat04_control_source", None),
            "until_step": int(getattr(ctx, "goat04_control_until_step", -1) or -1),
        }

    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    retrieved_context = _goat04_retrieved_context_from_event_v1(ctx, event)
    ok = bool(event.get("ok"))

    if ok and isinstance(retrieved_context, str) and retrieved_context in ("fox", "hawk"):
        ctx.goat04_control_context = retrieved_context
        ctx.goat04_control_source = "retrieval"
        ctx.goat04_control_until_step = step_now + 3
        return {
            "updated": True,
            "active": retrieved_context,
            "source": "retrieval",
            "until_step": step_now + 3,
        }

    # Retrieval attempt happened but did not produce a usable context.
    ctx.goat04_control_context = None
    ctx.goat04_control_source = None
    ctx.goat04_control_until_step = -1
    return {"updated": True, "active": None, "source": None, "until_step": -1}


def _experiment_transform_generic_cycle_records_v1(
    ctx: Ctx,
    *,
    experiment_id: str,
    condition_id: str,
    seed: int,
    episode_index: int,
    raw_records: list[dict[str, Any]],
    termination_reason: str,
) -> list[dict[str, Any]]:
    """Convert generic per-cycle JSON traces into experiment cycle-record schema rows.

    This version is goat04-oracle aware:
      - retrieval_event remains the internal/self-report trace
      - oracle.goat04 holds hidden benchmark truth for later scientific scoring
    """
    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    out: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_records):
        obs = raw.get("obs") if isinstance(raw, dict) else None
        env_meta = obs.get("env_meta") if isinstance(obs, dict) else None
        env_meta = env_meta if isinstance(env_meta, dict) else {}

        wm = raw.get("wm") if isinstance(raw, dict) else None
        wm = wm if isinstance(wm, dict) else {}
        mapswitch = wm.get("mapswitch") if isinstance(wm, dict) else None
        mapswitch = mapswitch if isinstance(mapswitch, dict) else {}
        events = mapswitch.get("events") if isinstance(mapswitch, dict) else None
        events = events if isinstance(events, list) else []
        retrieval_event = events[-1] if events and isinstance(events[-1], dict) else None

        pred_err = raw.get("pred_err_v0") if isinstance(raw, dict) else None
        pred_err = dict(pred_err) if isinstance(pred_err, dict) else {}

        selected_policy = raw.get("policy_fired") if isinstance(raw.get("policy_fired"), str) else None
        executed_action = raw.get("action_applied") if isinstance(raw.get("action_applied"), str) else None

        goat04_oracle = _goat04_oracle_from_raw_record_v1(raw)
        oracle_block = None
        if goat04_oracle:
            true_context = goat04_oracle.get("true_context")
            true_context = true_context if isinstance(true_context, str) and true_context else None

            expected_policy = goat04_oracle.get("expected_policy")
            expected_policy = expected_policy if isinstance(expected_policy, str) and expected_policy else None

            retrieved_context = None
            retrieval_correct = None
            if isinstance(retrieval_event, dict):
                retrieved_context = _goat04_retrieved_context_from_event_v1(ctx, retrieval_event)
                if true_context is not None and retrieved_context is not None:
                    retrieval_correct = retrieved_context == true_context

            action_correct_now = None
            if expected_policy:
                action_correct_now = bool(
                    selected_policy == expected_policy or executed_action == expected_policy  #pylint: disable=consider-using-in
                )

            oracle_block = {
                "goat04": {
                    "true_context": true_context,
                    "expected_policy": expected_policy,
                    "switch_event": bool(goat04_oracle.get("switch_event")),
                    "response_window_open": bool(goat04_oracle.get("response_window_open")),
                    "response_deadline_step": goat04_oracle.get("response_deadline_step"),
                    "retrieved_context": retrieved_context,
                    "retrieval_correct": retrieval_correct,
                    "action_correct_now": action_correct_now,
                }
            }

        rec = {
            "schema": "experiment_cycle_record_v1",
            "record_type": "cycle",
            "experiment_id": experiment_id,
            "benchmark": cfg.benchmark_id,
            "condition": str(condition_id),
            "seed": int(seed),
            "episode_index": int(episode_index),
            "cycle_index": int(idx),
            "env_step": int(raw.get("env_step", idx) or idx),
            "stage": raw.get("scenario_stage") if isinstance(raw.get("scenario_stage"), str) else None,
            "zone": raw.get("zone") if isinstance(raw.get("zone"), str) else None,
            "obs_mask_stats": {
                "prob": float(cfg.obs_mask_prob),
                "seed": getattr(ctx, "obs_mask_seed", None),
            },
            "retrieval_event": retrieval_event,
            "pred_err": pred_err,
            "selected_policy": selected_policy,
            "executed_action": executed_action,
            "posture": raw.get("posture") if isinstance(raw.get("posture"), str) else None,
            "mom_distance": raw.get("mom_distance") if isinstance(raw.get("mom_distance"), str) else None,
            "nipple_state": raw.get("nipple_state") if isinstance(raw.get("nipple_state"), str) else None,
            "policy_debug": dict(raw.get("policy_debug", {}) or {}) if isinstance(raw.get("policy_debug"), dict) else {},
            "llm_advice_summary": dict(raw.get("llm_advice_summary", {}) or {}),
            "milestones": _experiment_extract_generic_milestones_v1(raw),
            "oracle": oracle_block,
            "done": bool(idx == (len(raw_records) - 1)),
            "termination_reason": termination_reason if idx == (len(raw_records) - 1) else None,
        }
        out.append(rec)

    return out


def _experiment_summarize_generic_episode_v1(
    ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    experiment_id: str,
    condition_id: str,
    seed: int,
    episode_index: int,
    raw_records: list[dict[str, Any]],
    latency_ms_total: float,
) -> dict[str, Any]:
    """Summarize one sandbox episode into the experiment episode-record schema.

    This version keeps the generic metrics, but for goat04 it now scores contextual
    switching from a hidden environment-side oracle rather than from retrieval
    self-report alone.
    """
    record = experiment_build_episode_record_stub_v1(
        ctx,
        experiment_id=experiment_id,
        condition_id=condition_id,
        seed=seed,
        episode_index=episode_index,
        run_id_factory=runtime.run_id_factory,
    )

    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    milestone_vector: dict[str, Any] = {}
    repeated_action_loop_count = 0
    same_action_streak = 0
    prev_action = None
    pred_err_total = 0.0
    pred_err_seen = False

    cue_leakage_violations = 0

    # Goat04 oracle-scored metrics
    goat04_switch_events: list[dict[str, Any]] = []
    retrieval_attempts = 0
    correct_retrievals = 0
    internal_retrieval_success_count = 0
    false_retrieval_count = 0
    correct_action_count = 0
    stabilization_latencies: list[float] = []
    retrieval_action_dissociation_count = 0
    llm_call_count = 0
    llm_latency_ms_total = 0.0
    llm_ok_count = 0
    llm_first_error = None

    for raw in raw_records:

        fired = raw.get("policy_fired") if isinstance(raw.get("policy_fired"), str) else None
        if fired and fired == prev_action:
            same_action_streak += 1
            if same_action_streak >= 2:
                repeated_action_loop_count += 1
        else:
            same_action_streak = 0
            prev_action = fired

        pred_err = raw.get("pred_err_v0")
        if isinstance(pred_err, dict):
            pred_err_seen = True
            for val in pred_err.values():
                if isinstance(val, (int, float)):
                    pred_err_total += abs(float(val))

        llm_summary = raw.get("llm_advice_summary") if isinstance(raw, dict) else None
        llm_summary = llm_summary if isinstance(llm_summary, dict) else {}

        if bool(llm_summary.get("called")):
            llm_call_count += 1

            lat_v = llm_summary.get("latency_ms")
            if isinstance(lat_v, (int, float)) and not isinstance(lat_v, bool):
                llm_latency_ms_total += float(lat_v)

            if bool(llm_summary.get("ok")):
                llm_ok_count += 1
            elif llm_first_error is None:
                detail = llm_summary.get("error_detail")
                detail = detail if isinstance(detail, dict) else {}

                msg = detail.get("message") or llm_summary.get("error") or llm_summary.get("why")
                param = detail.get("param")
                code = detail.get("code")

                llm_first_error = str(msg) if msg is not None else str(llm_summary.get("why"))
                if isinstance(param, str) and param:
                    llm_first_error += f" | param={param}"
                if isinstance(code, str) and code:
                    llm_first_error += f" | code={code}"

        # Track cue-leakage guardrail from any goat04 retrieval event.
        wm = raw.get("wm") if isinstance(raw, dict) else None
        wm = wm if isinstance(wm, dict) else {}
        mapswitch = wm.get("mapswitch") if isinstance(wm, dict) else None
        mapswitch = mapswitch if isinstance(mapswitch, dict) else {}
        events = mapswitch.get("events") if isinstance(mapswitch, dict) else None
        events = events if isinstance(events, list) else []
        for event in events:
            if not isinstance(event, dict):
                continue
            reason = event.get("reason")
            if isinstance(reason, str) and reason.startswith("goat04_context:"):
                load_raw = event.get("load")
                load = load_raw if isinstance(load_raw, dict) else {}
                if load.get("merge_guardrail_ok") is False:
                    cue_leakage_violations += 1

        # Harvest hidden goat04 switch opportunities.
        goat04_oracle = _goat04_oracle_from_raw_record_v1(raw)
        if goat04_oracle and bool(goat04_oracle.get("switch_event")):
            true_context = goat04_oracle.get("true_context")
            expected_policy = goat04_oracle.get("expected_policy")
            switch_step = goat04_oracle.get("switch_step")
            deadline_step = goat04_oracle.get("response_deadline_step")

            if isinstance(true_context, str) and true_context and isinstance(expected_policy, str) and expected_policy:
                try:
                    switch_step_i = int(switch_step) if switch_step is not None else -1
                except Exception:
                    switch_step_i = -1
                try:
                    deadline_step_i = int(deadline_step) if deadline_step is not None else switch_step_i
                except Exception:
                    deadline_step_i = switch_step_i
                deadline_step_i = max(deadline_step_i, switch_step_i)

                goat04_switch_events.append(
                    {
                        "true_context": true_context,
                        "expected_policy": expected_policy,
                        "switch_step": switch_step_i,
                        "response_deadline_step": deadline_step_i,
                    }
                )

    benchmark_id = str(record.get("benchmark") or "")
    success = False
    context_switch_accuracy = None
    oracle_retrieval_precision = None
    internal_retrieval_event_ratio = None
    stabilization_latency = None

    if benchmark_id == "goat04_context":
        for switch in goat04_switch_events:
            true_context = switch["true_context"]
            expected_policy = switch["expected_policy"]
            switch_step = int(switch["switch_step"])
            deadline_step = int(switch["response_deadline_step"])

            first_retrieval_event = None
            first_retrieved_context = None
            first_internal_ok = False
            first_correct_action_step = None

            for raw in raw_records:
                env_step = raw.get("env_step")
                if not isinstance(env_step, int):
                    continue
                if env_step < switch_step or env_step > deadline_step:
                    continue

                wm = raw.get("wm") if isinstance(raw, dict) else None
                wm = wm if isinstance(wm, dict) else {}
                mapswitch = wm.get("mapswitch") if isinstance(wm, dict) else None
                mapswitch = mapswitch if isinstance(mapswitch, dict) else {}
                events = mapswitch.get("events") if isinstance(mapswitch, dict) else None
                events = events if isinstance(events, list) else []

                if first_retrieval_event is None:
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        reason = event.get("reason")
                        if isinstance(reason, str) and reason.startswith("goat04_context:"):
                            first_retrieval_event = event
                            first_internal_ok = bool(event.get("ok"))
                            first_retrieved_context = _goat04_retrieved_context_from_event_v1(ctx, event)
                            break

                if first_correct_action_step is None:
                    fired = raw.get("policy_fired") if isinstance(raw.get("policy_fired"), str) else None
                    applied = raw.get("action_applied") if isinstance(raw.get("action_applied"), str) else None
                    if fired == expected_policy or applied == expected_policy:  #pylint: disable=consider-using-in
                        first_correct_action_step = env_step

            if first_retrieval_event is not None:
                retrieval_attempts += 1
                if first_internal_ok:
                    internal_retrieval_success_count += 1
                if first_retrieved_context == true_context:
                    correct_retrievals += 1
                else:
                    false_retrieval_count += 1

            if first_correct_action_step is not None:
                correct_action_count += 1
                stabilization_latencies.append(float(first_correct_action_step - switch_step))

            if first_retrieved_context == true_context and first_correct_action_step is None:
                retrieval_action_dissociation_count += 1

        if goat04_switch_events:
            context_switch_accuracy = correct_action_count / float(len(goat04_switch_events))
            internal_retrieval_event_ratio = internal_retrieval_success_count / float(len(goat04_switch_events))

        if retrieval_attempts > 0:
            oracle_retrieval_precision = correct_retrievals / float(retrieval_attempts)

        if stabilization_latencies:
            stabilization_latency = sum(stabilization_latencies) / float(len(stabilization_latencies))

        success = bool(
            context_switch_accuracy is not None
            and context_switch_accuracy >= 0.75
            and cue_leakage_violations == 0
        )

    else:
        newborn = _experiment_summarize_newborn_b2_v1(raw_records)
        retrieval_dbg = _newborn_retrieval_debug_from_raw_records_v1(raw_records)
        stress_dbg = _newborn_stress_debug_from_raw_records_v1(raw_records)
        hint_dbg = runtime.newborn_retrieved_hint_debug(ctx)

        milestone_vector = dict(newborn.get("milestone_vector", {}) or {})
        success = bool(newborn.get("success"))

        record["milestone_score"] = float(newborn.get("milestone_score", 0.0) or 0.0)

        recovery_latency = newborn.get("recovery_latency")
        record["recovery_latency"] = float(recovery_latency) if isinstance(recovery_latency, (int, float)) else None

        record["milestone_steps"] = dict(newborn.get("milestone_steps", {}) or {})

        for key in (
            "time_to_rested",
            "mom_approach_latency",
            "nipple_find_latency",
            "latch_latency",
            "rest_completion_latency",
        ):
            value = newborn.get(key)
            record[key] = float(value) if isinstance(value, (int, float)) else None

        rest_t = record.get("time_to_rested")
        if isinstance(rest_t, (int, float)) and not isinstance(rest_t, bool):
            record["time_to_rested_or_max_cycles"] = float(rest_t)
        else:
            record["time_to_rested_or_max_cycles"] = float(cfg.max_cycles)

        record["newborn_retrieval_event_count"] = int(retrieval_dbg.get("retrieval_event_count", 0) or 0)
        record["newborn_retrieval_ok_count"] = int(retrieval_dbg.get("retrieval_ok_count", 0) or 0)
        record["newborn_retrieval_non_noop_count"] = int(retrieval_dbg.get("retrieval_non_noop_count", 0) or 0)
        record["newborn_retrieval_merge_noop_count"] = int(retrieval_dbg.get("retrieval_merge_noop_count", 0) or 0)
        record["newborn_retrieval_replace_count"] = int(retrieval_dbg.get("retrieval_replace_count", 0) or 0)
        record["newborn_retrieval_steps"] = list(retrieval_dbg.get("retrieval_steps", []) or [])
        record["newborn_stress_profile"] = str(stress_dbg.get("newborn_stress_profile") or "baseline")
        record["newborn_stress_active_cycle_count"] = int(
            stress_dbg.get("newborn_stress_active_cycle_count", 0) or 0
        )
        record["newborn_stress_dropped_pred_count"] = int(
            stress_dbg.get("newborn_stress_dropped_pred_count", 0) or 0
        )
        record["newborn_stress_dropped_cue_count"] = int(
            stress_dbg.get("newborn_stress_dropped_cue_count", 0) or 0
        )
        record["newborn_stress_reasons"] = list(stress_dbg.get("newborn_stress_reasons", []) or [])

        record["newborn_retrieved_hint_set_count"] = int(
            hint_dbg.get("newborn_retrieved_hint_set_count", 0) or 0
        )
        record["newborn_retrieved_hint_active_step_count"] = int(
            hint_dbg.get("newborn_retrieved_hint_active_step_count", 0) or 0
        )
        record["newborn_retrieved_hint_used_step_count"] = int(
            hint_dbg.get("newborn_retrieved_hint_used_step_count", 0) or 0
        )
        record["newborn_retrieved_hint_events"] = list(
            hint_dbg.get("newborn_retrieved_hint_events", []) or []
        )

        lhsi = summarize_newborn_state_integrity_v1(raw_records)
        record["state_integrity_summary"] = dict(lhsi)

        lhsi_numeric_fields = {
            "state_integrity_score": "lhsi_state_integrity_score",
            "wrong_stage_action_count": "lhsi_wrong_stage_action_count",
            "repeated_action_loop_count_lhsi": "lhsi_repeated_action_loop_count",
            "current_state_overwrite_proxy_count": "lhsi_current_state_overwrite_proxy_count",
            "stale_memory_intrusion_proxy_count": "lhsi_stale_memory_intrusion_proxy_count",
            "retrieval_action_dissociation_proxy_count": "lhsi_retrieval_action_dissociation_proxy_count",
            "retrieval_followup_basis_count": "lhsi_retrieval_followup_basis_count",
            "provenance_complete_cycle_rate": "lhsi_provenance_complete_cycle_rate",
            "cumulative_prediction_error_lhsi": "lhsi_cumulative_prediction_error",
        }

        for source_key, record_key in lhsi_numeric_fields.items():
            value = lhsi.get(source_key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                record[record_key] = float(value)
            else:
                record[record_key] = None

    record["success"] = success
    record["cycles_to_end"] = int(len(raw_records))
    record["milestone_vector"] = milestone_vector
    record["context_switch_accuracy"] = context_switch_accuracy
    record["false_retrieval_count"] = int(false_retrieval_count)
    record["cue_leakage_violations"] = int(cue_leakage_violations)
    record["cumulative_prediction_error"] = float(pred_err_total) if pred_err_seen else None

    record["repeated_action_loop_count"] = int(repeated_action_loop_count)
    record["llm_call_count"] = int(llm_call_count)
    record["llm_latency_ms_total"] = round(float(llm_latency_ms_total), 3) if llm_call_count > 0 else None
    record["llm_ok_count"] = int(llm_ok_count)
    record["llm_first_error"] = llm_first_error
    record["latency_ms_total"] = round(float(latency_ms_total), 3)

    record["oracle_action_accuracy"] = context_switch_accuracy
    record["oracle_retrieval_precision"] = oracle_retrieval_precision
    record["internal_retrieval_event_ratio"] = internal_retrieval_event_ratio
    record["stabilization_latency"] = round(float(stabilization_latency), 3) if stabilization_latency is not None else None
    record["retrieval_action_dissociation_count"] = int(retrieval_action_dissociation_count)
    return record


def experiment_run_one_episode_v1(
    protocol_ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    condition_id: str | None = None,
    seed: int | None = None,
    episode_index: int = 0,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run one experiment episode inside an isolated sandbox runtime.

    Why this helper exists
    ----------------------
    This is the first execution seam for Menu 49. It keeps the user's live CCA8 session
    untouched by building a fresh runtime, preparing experiment logging, running one
    benchmark episode, transforming the generic per-cycle trace into the experiment
    cycle schema, and writing one episode-summary JSONL record.

    Current scope
    -------------
    - Real CCA8 execution is wired for memory conditions A/B/C.
    - Hybrid condition E uses the bounded LLM adviser while CCA8 remains authoritative.
    - LLM-only condition D remains explicitly unsupported until a separate controller path exists.
    """
    if protocol_ctx is None:
        return {"ok": False, "why": "missing_protocol_ctx"}

    cfg = experiment_normalize_protocol_v1(getattr(protocol_ctx, "experiment_cfg", None))
    # Benchmark-effective default:
    # newborn_long_horizon needs genuine partial observability or A/B/C collapse
    # into the same easy storyboard. If the protocol is still at zero masking,
    # use a modest benchmark floor here without changing ordinary simulation.
    if cfg.benchmark_id == "newborn_long_horizon" and float(cfg.obs_mask_prob) <= 0.0:
        cfg.obs_mask_prob = 0.35
    chosen_condition = str(condition_id or (cfg.condition_ids[0] if cfg.condition_ids else "A")).strip().upper()
    chosen_seed = int(seed if isinstance(seed, int) else (cfg.seed_list[0] if cfg.seed_list else 11))

    sandbox = experiment_make_sandbox_runtime_v1(runtime)
    world = sandbox["world"]
    drives = sandbox["drives"]
    run_ctx = sandbox["ctx"]
    env = sandbox["env"]
    policy_rt = sandbox["policy_rt"]

    run_ctx.experiment_cfg = cfg
    prep = experiment_prepare_logging_v1(
        run_ctx,
        reset_buffers=True,
        run_id_factory=runtime.run_id_factory,
    )
    if not bool(prep.get("ok")):
        return {"ok": False, "why": prep.get("why", "logging_prepare_failed")}

    # Keep generic cycle logging in-memory only; experiment-schema JSONL writing happens after transform.
    run_ctx.cycle_json_enabled = True
    run_ctx.cycle_json_path = None
    run_ctx.cycle_json_max_records = max(2000, int(cfg.max_cycles) + 10)

    bench_info = experiment_configure_benchmark_runtime_v1(
        world,
        drives,
        run_ctx,
        env,
        cfg.benchmark_id,
        runtime=runtime,
    )
    if not bool(bench_info.get("ok")):
        return {"ok": False, "why": bench_info.get("why", "benchmark_setup_failed")}

    cond_info = experiment_apply_condition_runtime_v1(
        world,
        drives,
        run_ctx,
        env,
        condition_id=chosen_condition,
        cfg=cfg,
    )
    if not bool(cond_info.get("ok")):
        return {
            "ok": False,
            "why": cond_info.get("why", "condition_apply_failed"),
            "condition_id": chosen_condition,
            "agent_mode": cond_info.get("agent_mode"),
            "llm_role": cond_info.get("llm_role"),
        }

    try:
        run_ctx.obs_mask_prob = float(cfg.obs_mask_prob)
        run_ctx.obs_mask_seed = int(chosen_seed)
        run_ctx.obs_mask_last_cfg_sig = None
        run_ctx.obs_mask_verbose = False
    except Exception:
        pass

    random.seed(int(chosen_seed))

    started = time.perf_counter()
    captured_stdout = ""
    try:
        if suppress_output:
            buf = io.StringIO()
            with redirect_stdout(buf):
                runtime.run_closed_loop(env, world, drives, run_ctx, policy_rt, int(cfg.max_cycles))
            captured_stdout = buf.getvalue()
        else:
            runtime.run_closed_loop(env, world, drives, run_ctx, policy_rt, int(cfg.max_cycles))
    except Exception as e:
        return {
            "ok": False,
            "why": f"episode_run_failed:{e}",
            "run_id": prep.get("run_id"),
            "condition_id": chosen_condition,
            "seed": int(chosen_seed),
        }
    latency_ms_total = (time.perf_counter() - started) * 1000.0

    raw_records = list(getattr(run_ctx, "cycle_json_records", []) or [])
    termination_reason = "max_cycles_exhausted"

    cycle_records = _experiment_transform_generic_cycle_records_v1(
        run_ctx,
        experiment_id=str(prep.get("run_id") or ""),
        condition_id=chosen_condition,
        seed=int(chosen_seed),
        episode_index=int(episode_index),
        raw_records=raw_records,
        termination_reason=termination_reason,
    )
    for rec in cycle_records:
        append_experiment_jsonl_record_v1(prep.get("cycle_json_path"), rec)

    episode_record = _experiment_summarize_generic_episode_v1(
        run_ctx,
        runtime=runtime,
        experiment_id=str(prep.get("run_id") or ""),
        condition_id=chosen_condition,
        seed=int(chosen_seed),
        episode_index=int(episode_index),
        raw_records=raw_records,
        latency_ms_total=latency_ms_total,
    )
    experiment_write_episode_record_v1(run_ctx, episode_record)

    try:
        protocol_ctx.experiment_last_summary = dict(run_ctx.experiment_last_summary)
        protocol_ctx.experiment_last_summary["last_run_condition_id"] = chosen_condition
        protocol_ctx.experiment_last_summary["last_run_seed"] = int(chosen_seed)
        protocol_ctx.experiment_last_summary["last_run_episode_index"] = int(episode_index)
        protocol_ctx.experiment_last_summary["last_run_cycle_count"] = int(len(cycle_records))
        protocol_ctx.experiment_last_summary["last_run_success"] = episode_record.get("success")
        protocol_ctx.experiment_last_summary["last_run_latency_ms_total"] = episode_record.get("latency_ms_total")
    except Exception:
        pass

    return {
        "ok": True,
        "run_id": prep.get("run_id"),
        "benchmark_id": cfg.benchmark_id,
        "condition_id": chosen_condition,
        "condition_label": cond_info.get("label"),
        "seed": int(chosen_seed),
        "effective_obs_mask_prob": float(cfg.obs_mask_prob),
        "effective_newborn_stress_profile": str(getattr(cfg, "newborn_stress_profile", "baseline")),
        "effective_newborn_blackout_length": _newborn_effective_blackout_length_v1(
            getattr(cfg, "newborn_stress_profile", "baseline"),
            getattr(cfg, "newborn_blackout_length", 3),
        ),
        "episode_index": int(episode_index),
        "cycle_record_count": int(len(cycle_records)),
        "episode_record": episode_record,
        "cycle_json_path": prep.get("cycle_json_path"),
        "episode_json_path": prep.get("episode_json_path"),
        "suppressed_output": bool(suppress_output),
        "captured_output_lines": int(len(captured_stdout.splitlines())) if captured_stdout else 0,
    }


AUTONOMOUS_NEWBORN_SURVIVAL_MILESTONES_V1 = (
    "stood_up",
    "reached_mom",
    "found_nipple",
    "latched_nipple",
    "milk_drinking",
    "rested",
)


def _autonomous_newborn_demo_final_state_v1(state: Any) -> dict[str, Any]:
    """Return a compact final-state summary for the autonomous newborn survival demo."""
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
        "suckle_ticks": int(getattr(state, "newborn_suckle_ticks", 0) or 0),
        "setbacks": int(getattr(state, "newborn_setback_count", 0) or 0),
        "step_index": int(getattr(state, "step_index", 0) or 0),
    }


def _autonomous_newborn_demo_policy_counts_v1(raw_records: list[dict[str, Any]]) -> dict[str, int]:
    """Count selected policies from generic cycle JSON records."""
    out: dict[str, int] = {}

    for record in raw_records:
        if not isinstance(record, dict):
            continue

        policy = record.get("policy_fired")
        if not isinstance(policy, str) or not policy.startswith("policy:"):
            continue

        out[policy] = out.get(policy, 0) + 1

    return out


def _autonomous_newborn_demo_policy_counts_from_stdout_v1(text: str) -> dict[str, int]:
    """Fallback policy counter for captured Menu-37-style terminal output."""
    out: dict[str, int] = {}

    if not isinstance(text, str):
        return out

    for line in text.splitlines():
        if "[env→controller]" not in line:
            continue

        tail = line.split("[env→controller]", 1)[1].strip()
        if not tail:
            continue

        token = tail.split(maxsplit=1)[0].strip()
        if token.startswith("policy:"):
            out[token] = out.get(token, 0) + 1

    return out


def _autonomous_newborn_demo_counts_text_v1(policy_counts: dict[str, int]) -> str:
    """Return a stable, compact policy-count string for terminal display."""
    preferred = [
        "policy:stand_up",
        "policy:recover_fall",
        "policy:follow_mom",
        "policy:seek_nipple",
        "policy:rest",
        "policy:suckle",
        "policy:probe",
        "policy:explore_check",
    ]

    parts: list[str] = []
    seen: set[str] = set()

    for name in preferred:
        count = int(policy_counts.get(name, 0) or 0)
        if count > 0:
            parts.append(f"{name}={count}")
            seen.add(name)

    for name in sorted(policy_counts):
        if name not in seen:
            parts.append(f"{name}={int(policy_counts.get(name, 0) or 0)}")

    return ", ".join(parts) if parts else "(none)"


def run_autonomous_newborn_survival_demo_v1(
    max_cycles: int = 60,
    *,
    show_timeline: bool = True,
    runtime: ExperimentRuntime,
) -> dict[str, Any]:
    """Run an isolated hard-mode newborn survival demo using CCA8 autonomous policy selection.

    This is a user-facing demo wrapper around the same closed-loop machinery as Menu 37, but with
    a fresh sandbox runtime so the live interactive WorldGraph/session is not mutated.

    The demo intentionally disables observation masking and route-loss stress. It asks the simpler
    baseline question first:

        Can the newborn goat autonomously complete the hard survival ladder when the current state
        is fully observable?

    Returns a JSON-safe summary suitable for terminal rendering and pytest assertions.
    """
    try:
        cycles = int(max_cycles)
    except Exception:
        cycles = 60
    cycles = max(1, min(500, cycles))

    prior_skills: dict[str, Any] = {}
    try:
        prior_skills = skills_to_dict()
    except Exception:
        prior_skills = {}

    started = time.perf_counter()
    captured_stdout = ""

    try:
        # Keep this demo isolated from the user's live skill ledger as much as the current global
        # skill-ledger implementation allows.
        try:
            skills_from_dict({})
        except Exception:
            pass

        sandbox = experiment_make_sandbox_runtime_v1(runtime)
        world = sandbox["world"]
        drives = sandbox["drives"]
        run_ctx = sandbox["ctx"]
        env = sandbox["env"]
        policy_rt = sandbox["policy_rt"]

        setup = experiment_configure_benchmark_runtime_v1(
            world,
            drives,
            run_ctx,
            env,
            "newborn_long_horizon",
            runtime=runtime,
        )
        if not bool(setup.get("ok")):
            return {
                "ok": False,
                "why": setup.get("why", "benchmark_setup_failed"),
                "success": False,
            }

        # Baseline survival demo: no route-loss / blackout stress. Those remain Menu 49 work.
        run_ctx.obs_mask_prob = 0.0
        run_ctx.obs_mask_verbose = False
        run_ctx.obs_mask_seed = 123
        run_ctx.obs_mask_last_cfg_sig = None
        run_ctx.cycle_json_enabled = True
        run_ctx.cycle_json_path = None
        run_ctx.cycle_json_records = []
        run_ctx.cycle_json_max_records = max(2000, cycles + 10)
        run_ctx.experiment_newborn_require_resume_memory = False
        run_ctx.experiment_newborn_blackout_start_step = -1
        run_ctx.experiment_newborn_blackout_until_step = -1
        run_ctx.experiment_newborn_blackout_reason = None

        drives.hunger = 0.50
        drives.fatigue = 0.30
        drives.warmth = 0.60

        try:
            policy_rt.refresh_loaded(run_ctx)
        except Exception:
            pass

        random.seed(123)

        if show_timeline:
            runtime.run_closed_loop(env, world, drives, run_ctx, policy_rt, cycles)
        else:
            buf = io.StringIO()
            with redirect_stdout(buf):
                runtime.run_closed_loop(env, world, drives, run_ctx, policy_rt, cycles)
            captured_stdout = buf.getvalue()

        raw_records = list(getattr(run_ctx, "cycle_json_records", []) or [])

        if raw_records:
            newborn_summary = _experiment_summarize_newborn_b2_v1(raw_records)
        else:
            newborn_summary = {
                "milestone_vector": {},
                "milestone_steps": {},
                "milestone_score": 0.0,
                "success": False,
            }

        final_state = _autonomous_newborn_demo_final_state_v1(getattr(env, "state", None))
        milestone_vector = newborn_summary.get("milestone_vector")
        if not isinstance(milestone_vector, dict):
            milestone_vector = {}

        missing_milestones = [
            name for name in AUTONOMOUS_NEWBORN_SURVIVAL_MILESTONES_V1
            if not bool(milestone_vector.get(name))
        ]

        policy_counts = _autonomous_newborn_demo_policy_counts_v1(raw_records)
        if not policy_counts and captured_stdout:
            policy_counts = _autonomous_newborn_demo_policy_counts_from_stdout_v1(captured_stdout)

        stand_actions = int(policy_counts.get("policy:stand_up", 0) or 0)
        stand_actions += int(policy_counts.get("policy:recover_fall", 0) or 0)

        final_rest_state = (
            final_state.get("stage") == "rest"
            and final_state.get("posture") == "resting"
            and final_state.get("mom_distance") == "touching"
            and final_state.get("nipple_state") == "latched"
            and final_state.get("shelter_distance") == "near"
            and final_state.get("cliff_distance") == "far"
        )

        required_policy_evidence = (
            stand_actions >= 2
            and int(policy_counts.get("policy:follow_mom", 0) or 0) >= 2
            and int(policy_counts.get("policy:seek_nipple", 0) or 0) >= 2
            and int(policy_counts.get("policy:suckle", 0) or 0) > 0
            and int(policy_counts.get("policy:rest", 0) or 0) >= 2
        )

        success = bool(final_rest_state and not missing_milestones and required_policy_evidence)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        return {
            "ok": True,
            "success": success,
            "max_cycles": int(cycles),
            "cycles_recorded": int(len(raw_records)),
            "latency_ms_total": round(float(elapsed_ms), 3),
            "final_rest_state": bool(final_rest_state),
            "required_policy_evidence": bool(required_policy_evidence),
            "missing_milestones": missing_milestones,
            "milestone_vector": dict(milestone_vector),
            "milestone_steps": dict(newborn_summary.get("milestone_steps", {}) or {}),
            "milestone_score": float(newborn_summary.get("milestone_score", 0.0) or 0.0),
            "policy_counts": dict(policy_counts),
            "policy_counts_text": _autonomous_newborn_demo_counts_text_v1(policy_counts),
            "final_state": final_state,
            "captured_output_lines": int(len(captured_stdout.splitlines())) if captured_stdout else 0,
            "captured_output_tail": "\n".join(captured_stdout.splitlines()[-80:]) if captured_stdout else "",
        }

    except Exception as e:
        return {
            "ok": False,
            "why": f"{e.__class__.__name__}: {e}",
            "success": False,
            "max_cycles": int(cycles),
        }

    finally:
        try:
            skills_from_dict(prior_skills)
        except Exception:
            pass


def render_autonomous_newborn_survival_demo_lines_v1(result: dict[str, Any]) -> list[str]:
    """Return terminal summary lines for the autonomous newborn survival demo."""
    if not isinstance(result, dict):
        return ["[newborn-demo] result: invalid result payload"]

    if not bool(result.get("ok")):
        return [
            "[newborn-demo] RESULT: ERROR",
            f"[newborn-demo] why: {result.get('why', '(unknown)')}",
        ]

    status = "PASS" if bool(result.get("success")) else "FAIL"
    lines = [
        f"[newborn-demo] RESULT: {status}",
        f"[newborn-demo] cycles_recorded: {result.get('cycles_recorded')} / max_cycles={result.get('max_cycles')}",
        f"[newborn-demo] milestone_score: {result.get('milestone_score')}",
        f"[newborn-demo] missing_milestones: {result.get('missing_milestones')}",
        f"[newborn-demo] policy_counts: {result.get('policy_counts_text')}",
        f"[newborn-demo] final_rest_state: {result.get('final_rest_state')}",
        f"[newborn-demo] required_policy_evidence: {result.get('required_policy_evidence')}",
        f"[newborn-demo] final_state: {json.dumps(result.get('final_state', {}), ensure_ascii=False, sort_keys=True)}",
        f"[newborn-demo] milestone_steps: {json.dumps(result.get('milestone_steps', {}), ensure_ascii=False, sort_keys=True)}",
        f"[newborn-demo] elapsed_ms: {result.get('latency_ms_total')}",
    ]

    tail = result.get("captured_output_tail")
    if not bool(result.get("success")) and isinstance(tail, str) and tail:
        lines.append("")
        lines.append("[newborn-demo] captured output tail:")
        lines.extend(tail.splitlines())

    return lines


def render_experiment_logging_status_v1(ctx: Ctx) -> str:
    """Return a compact summary of experiment logging/output preparation state."""
    cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
    last = getattr(ctx, "experiment_last_summary", None)
    last = last if isinstance(last, dict) else {}

    lines = []
    lines.append("Experiment logging / output status")
    lines.append(f"  run_label           : {cfg.run_label or '(none)'}")
    lines.append(f"  output_dir          : {cfg.output_dir}")
    lines.append(f"  cycle_json_enabled  : {bool(getattr(ctx, 'cycle_json_enabled', False))}")
    lines.append(f"  cycle_json_path     : {getattr(ctx, 'cycle_json_path', None)}")
    lines.append(f"  prepared_run_id     : {last.get('run_id') if last else '(not prepared yet)'}")
    lines.append(f"  prepared_at         : {last.get('prepared_at') if last else '(not prepared yet)'}")
    lines.append(
        f"  episode_json_path   : {last.get('episode_json_path') if last else '(not prepared yet)'}"
    )
    lines.append(f"  cycle_ring_records  : {len(getattr(ctx, 'cycle_json_records', []) or [])}")
    lines.append(
        "  note                : preparing logging arms the existing cycle JSON writer but does not run experiments"
    )
    return "\n".join(lines)


def _experiment_metric_text_v1(value: Any) -> str:
    """Return a compact human-readable text form for experiment menu metrics.

    The experiment menu prints a mix of bools, ints, floats, dicts, and sometimes
    missing values. This helper keeps the display stable and easy to read:
      - None -> "(none)"
      - float -> 3 decimal places
      - dict/list -> compact JSON
      - everything else -> str(...)
    """
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


def render_experiment_episode_summary_lines_v1(result: dict[str, Any]) -> list[str]:
    """Return benchmark-aware summary lines for Menu 49 single-episode runs.

    Goal
    ----
    Submenu 17 used to print only a compact generic summary. After the goat04
    oracle patch, the most important B1 values are now oracle-based metrics such
    as oracle_action_accuracy and oracle_retrieval_precision. This helper keeps
    the display logic in one place and prints different details for goat04 vs
    newborn_long_horizon.
    """
    if not isinstance(result, dict):
        return ["[experiments] run result       : (invalid)"]

    episode_record = result.get("episode_record")
    episode_record = episode_record if isinstance(episode_record, dict) else {}

    benchmark = result.get("benchmark_id")
    if not isinstance(benchmark, str) or not benchmark:
        raw_bench = episode_record.get("benchmark")
        benchmark = raw_bench if isinstance(raw_bench, str) and raw_bench else "(unknown)"

    condition_id = result.get("condition_id")
    condition_label = result.get("condition_label")

    lines = [
        f"[experiments] run_id            : {_experiment_metric_text_v1(result.get('run_id'))}",
        f"[experiments] benchmark         : {_experiment_metric_text_v1(benchmark)}",
        f"[experiments] condition         : {_experiment_metric_text_v1(condition_id)}"
        f"  ({_experiment_metric_text_v1(condition_label)})",
        f"[experiments] seed              : {_experiment_metric_text_v1(result.get('seed'))}",
        f"[experiments] obs_mask_prob     : {_experiment_metric_text_v1(result.get('effective_obs_mask_prob'))}",
        f"[experiments] cycles_to_end     : {_experiment_metric_text_v1(episode_record.get('cycles_to_end'))}",
        f"[experiments] success           : {_experiment_metric_text_v1(episode_record.get('success'))}",
        f"[experiments] llm_calls         : {_experiment_metric_text_v1(episode_record.get('llm_call_count'))}",
        f"[experiments] llm_ok_count      : {_experiment_metric_text_v1(episode_record.get('llm_ok_count'))}",
        f"[experiments] llm_lat_ms_total  : {_experiment_metric_text_v1(episode_record.get('llm_latency_ms_total'))}",
    ]

    if benchmark == "goat04_context":
        lines.extend(
            [
                f"[experiments] context_switch_acc: {_experiment_metric_text_v1(episode_record.get('context_switch_accuracy'))}",
                f"[experiments] oracle_action_acc : {_experiment_metric_text_v1(episode_record.get('oracle_action_accuracy'))}",
                f"[experiments] oracle_retr_prec  : {_experiment_metric_text_v1(episode_record.get('oracle_retrieval_precision'))}",
                f"[experiments] internal_retr_rt  : {_experiment_metric_text_v1(episode_record.get('internal_retrieval_event_ratio'))}",
                f"[experiments] stabilize_lat     : {_experiment_metric_text_v1(episode_record.get('stabilization_latency'))}",
                f"[experiments] retr_act_dissoc   : {_experiment_metric_text_v1(episode_record.get('retrieval_action_dissociation_count'))}",
                f"[experiments] false_retrievals  : {_experiment_metric_text_v1(episode_record.get('false_retrieval_count'))}",
                f"[experiments] cue_leakage       : {_experiment_metric_text_v1(episode_record.get('cue_leakage_violations'))}",
            ]
        )
    else:
        lines.extend(
            [
                f"[experiments] milestones        : {_experiment_metric_text_v1(episode_record.get('milestone_vector'))}",
                f"[experiments] milestone_steps   : {_experiment_metric_text_v1(episode_record.get('milestone_steps'))}",
                f"[experiments] milestone_score   : {_experiment_metric_text_v1(episode_record.get('milestone_score'))}",
                f"[experiments] recovery_latency  : {_experiment_metric_text_v1(episode_record.get('recovery_latency'))}",
                f"[experiments] time_to_rested    : {_experiment_metric_text_v1(episode_record.get('time_to_rested'))}",
                f"[experiments] rest_t_or_max     : {_experiment_metric_text_v1(episode_record.get('time_to_rested_or_max_cycles'))}",
                f"[experiments] phase_lats        : mom={_experiment_metric_text_v1(episode_record.get('mom_approach_latency'))} "
                f"find={_experiment_metric_text_v1(episode_record.get('nipple_find_latency'))} "
                f"latch={_experiment_metric_text_v1(episode_record.get('latch_latency'))} "
                f"rest={_experiment_metric_text_v1(episode_record.get('rest_completion_latency'))}",
                f"[experiments] newborn_stress   : profile={_experiment_metric_text_v1(episode_record.get('newborn_stress_profile'))} "
                f"active={_experiment_metric_text_v1(episode_record.get('newborn_stress_active_cycle_count'))} "
                f"drop_pred={_experiment_metric_text_v1(episode_record.get('newborn_stress_dropped_pred_count'))} "
                f"drop_cue={_experiment_metric_text_v1(episode_record.get('newborn_stress_dropped_cue_count'))}",
                f"[experiments] retrieved_hint   : set={_experiment_metric_text_v1(episode_record.get('newborn_retrieved_hint_set_count'))} "
                f"active_steps={_experiment_metric_text_v1(episode_record.get('newborn_retrieved_hint_active_step_count'))} "
                f"used_steps={_experiment_metric_text_v1(episode_record.get('newborn_retrieved_hint_used_step_count'))}",
                f"[experiments] retrieval_debug   : evt={_experiment_metric_text_v1(episode_record.get('newborn_retrieval_event_count'))} "
                f"nonnoop={_experiment_metric_text_v1(episode_record.get('newborn_retrieval_non_noop_count'))} "
                f"merge_noop={_experiment_metric_text_v1(episode_record.get('newborn_retrieval_merge_noop_count'))} "
                f"replace={_experiment_metric_text_v1(episode_record.get('newborn_retrieval_replace_count'))}",
                f"[experiments] lhsi_state        : score={_experiment_metric_text_v1(episode_record.get('lhsi_state_integrity_score'))} "
                f"wrong={_experiment_metric_text_v1(episode_record.get('lhsi_wrong_stage_action_count'))} "
                f"loops={_experiment_metric_text_v1(episode_record.get('lhsi_repeated_action_loop_count'))}",
                f"[experiments] lhsi_retrieval    : overwrite={_experiment_metric_text_v1(episode_record.get('lhsi_current_state_overwrite_proxy_count'))} "
                f"stale={_experiment_metric_text_v1(episode_record.get('lhsi_stale_memory_intrusion_proxy_count'))} "
                f"dissoc={_experiment_metric_text_v1(episode_record.get('lhsi_retrieval_action_dissociation_proxy_count'))} "
                f"basis={_experiment_metric_text_v1(episode_record.get('lhsi_retrieval_followup_basis_count'))} "
                f"prov={_experiment_metric_text_v1(episode_record.get('lhsi_provenance_complete_cycle_rate'))}",
            ]
        )

        lhsi_summary = episode_record.get("state_integrity_summary")
        if isinstance(lhsi_summary, dict):
            lines.extend(
                render_state_integrity_event_detail_lines_v1(
                    lhsi_summary,
                    max_events=3,
                    prefix="[experiments]",
                )
            )

    lines.extend(
        [
            f"[experiments] full_run_loops    : {_experiment_metric_text_v1(episode_record.get('repeated_action_loop_count'))}",
            f"[experiments] cumulative_pred_e : {_experiment_metric_text_v1(episode_record.get('cumulative_prediction_error'))}",
            f"[experiments] latency_ms_total  : {_experiment_metric_text_v1(episode_record.get('latency_ms_total'))}",
        ]
    )

    first_err = episode_record.get("llm_first_error")
    if isinstance(first_err, str) and first_err:
        lines.append(f"[experiments] llm_first_error   : {first_err}")

    return lines


def _experiment_mean_v1(values: list[Any]) -> float | None:
    """Return the arithmetic mean of numeric values, ignoring missing/non-numeric items.

    Purpose / intent
    ----------------
    The experiment batch summary needs a very small, predictable aggregator. I keep it here rather
    than pulling in statistics helpers because the behavior should stay obvious and robust:
      - ignore None / strings / dicts / lists,
      - ignore bools (so True/False do not silently behave like 1/0 unless we convert explicitly),
      - return None when there is nothing numeric to average.
    """
    nums: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            nums.append(float(value))

    if not nums:
        return None
    return sum(nums) / float(len(nums))


_EXPERIMENT_TCRIT_CACHE_V1: dict[tuple[float, int], float] = {}


def _experiment_numeric_values_v1(values: list[Any]) -> list[float]:
    """Return numeric values as floats, ignoring non-numeric items and bools.

    This keeps the experiment stats path defensive. Menu 49 summaries are JSON-safe
    dicts and may contain None or non-numeric fields, so I normalize the numeric
    subset once here and reuse it for mean / SD / CI calculations.
    """
    out: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out.append(float(value))
    return out


def _experiment_sample_sd_v1(values: list[Any]) -> float | None:
    """Return the sample standard deviation (n-1 denominator), or None when undefined."""
    nums = _experiment_numeric_values_v1(values)
    n = len(nums)
    if n < 2:
        return None

    mean_v = sum(nums) / float(n)
    var = sum((x - mean_v) ** 2 for x in nums) / float(n - 1)
    return math.sqrt(var)


def _student_t_pdf_v1(x: float, df: int) -> float:
    """Return the Student-t probability density for x and degrees of freedom df.

    I keep this dependency-free on purpose. The local CCA8 workflow should not
    require SciPy just to print submenu 19 statistics.
    """
    if int(df) <= 0:
        return 0.0

    df_f = float(df)
    log_norm = (
        math.lgamma((df_f + 1.0) / 2.0)
        - math.lgamma(df_f / 2.0)
        - 0.5 * (math.log(df_f) + math.log(math.pi))
    )
    log_tail = -((df_f + 1.0) / 2.0) * math.log1p((float(x) * float(x)) / df_f)
    return math.exp(log_norm + log_tail)


def _student_t_cdf_v1(x: float, df: int) -> float:
    """Return the Student-t cumulative distribution function by Simpson integration.

    Why Simpson integration
    -----------------------
    The runner should stay self-contained and readable. This is accurate enough
    for submenu 19 reporting and avoids introducing a heavy scientific dependency.
    """
    if int(df) <= 0:
        return 0.5

    x_f = float(x)
    if abs(x_f) < 1e-12:
        return 0.5

    upper = abs(x_f)
    n_intervals = max(200, min(8000, int(upper * 240.0)))
    if n_intervals % 2 == 1:
        n_intervals += 1

    h = upper / float(n_intervals)
    total = _student_t_pdf_v1(0.0, df) + _student_t_pdf_v1(upper, df)

    for i in range(1, n_intervals):
        coeff = 4.0 if i % 2 == 1 else 2.0
        total += coeff * _student_t_pdf_v1(float(i) * h, df)

    area = (total * h) / 3.0
    if x_f > 0.0:
        return min(1.0, 0.5 + area)
    return max(0.0, 0.5 - area)


def _student_t_critical_two_sided_v1(confidence: float, df: int) -> float | None:
    """Return the two-sided t critical value for the requested confidence level."""
    df_i = int(df)
    conf_f = float(confidence)

    if df_i <= 0:
        return None

    key = (round(conf_f, 6), df_i)
    cached = _EXPERIMENT_TCRIT_CACHE_V1.get(key)
    if cached is not None:
        return cached

    target = 0.5 + (conf_f / 2.0)
    lo = 0.0
    hi = 1.0

    while _student_t_cdf_v1(hi, df_i) < target and hi < 100.0:
        hi *= 2.0

    for _ in range(35):
        mid = (lo + hi) / 2.0
        if _student_t_cdf_v1(mid, df_i) < target:
            lo = mid
        else:
            hi = mid

    _EXPERIMENT_TCRIT_CACHE_V1[key] = hi
    return hi


def _experiment_descriptive_stats_v1(values: list[Any], *, confidence: float = 0.95) -> dict[str, Any]:
    """Return n / mean / sample SD / 95% CI for one repeat-level metric series.

    The CI here is the confidence interval of the mean across repeats, not a
    prediction interval.
    """
    nums = _experiment_numeric_values_v1(values)
    n = len(nums)

    out: dict[str, Any] = {
        "n": int(n),
        "mean": None,
        "sd": None,
        "ci_low": None,
        "ci_high": None,
        "confidence": float(confidence),
    }

    if n <= 0:
        return out

    mean_v = sum(nums) / float(n)
    out["mean"] = float(mean_v)

    sd_v = _experiment_sample_sd_v1(nums)
    if sd_v is None:
        out["ci_low"] = float(mean_v)
        out["ci_high"] = float(mean_v)
        return out

    out["sd"] = float(sd_v)

    if n == 1:
        out["ci_low"] = float(mean_v)
        out["ci_high"] = float(mean_v)
        return out

    tcrit = _student_t_critical_two_sided_v1(confidence, n - 1)
    if tcrit is None:
        out["ci_low"] = float(mean_v)
        out["ci_high"] = float(mean_v)
        return out

    se_v = sd_v / math.sqrt(float(n))
    margin = float(tcrit) * se_v
    out["ci_low"] = float(mean_v - margin)
    out["ci_high"] = float(mean_v + margin)
    return out


def _experiment_paired_diff_stats_v1(
    ref_values: list[Any],
    cmp_values: list[Any],
    *,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Return paired repeat-level comparison stats for cmp minus ref.

    Statistical contract
    --------------------
    - pairing is by repeat index,
    - test is a two-sided paired t test,
    - reported delta is mean(cmp - ref),
    - CI is the confidence interval of that paired mean difference.
    """
    pairs: list[tuple[float, float]] = []

    for ref_v, cmp_v in zip(ref_values, cmp_values):
        if isinstance(ref_v, bool) or isinstance(cmp_v, bool):
            continue
        if isinstance(ref_v, (int, float)) and isinstance(cmp_v, (int, float)):
            pairs.append((float(ref_v), float(cmp_v)))

    n = len(pairs)
    out: dict[str, Any] = {
        "n": int(n),
        "mean_ref": None,
        "mean_cmp": None,
        "mean_diff": None,
        "sd_diff": None,
        "ci_low": None,
        "ci_high": None,
        "t_stat": None,
        "p_value": None,
        "confidence": float(confidence),
    }

    if n <= 0:
        return out

    ref_nums = [a for a, _ in pairs]
    cmp_nums = [b for _, b in pairs]
    diffs = [b - a for a, b in pairs]

    mean_ref = sum(ref_nums) / float(n)
    mean_cmp = sum(cmp_nums) / float(n)
    mean_diff = sum(diffs) / float(n)

    out["mean_ref"] = float(mean_ref)
    out["mean_cmp"] = float(mean_cmp)
    out["mean_diff"] = float(mean_diff)

    if n == 1:
        out["ci_low"] = float(mean_diff)
        out["ci_high"] = float(mean_diff)
        return out

    sd_diff = _experiment_sample_sd_v1(diffs)
    if sd_diff is None:
        out["ci_low"] = float(mean_diff)
        out["ci_high"] = float(mean_diff)
        return out

    out["sd_diff"] = float(sd_diff)

    if sd_diff < 1e-12:
        out["ci_low"] = float(mean_diff)
        out["ci_high"] = float(mean_diff)
        out["t_stat"] = None
        out["p_value"] = 1.0 if abs(mean_diff) < 1e-12 else 0.0
        return out

    se_diff = sd_diff / math.sqrt(float(n))
    t_stat = mean_diff / se_diff
    out["t_stat"] = float(t_stat)

    tcrit = _student_t_critical_two_sided_v1(confidence, n - 1)
    if tcrit is None:
        out["ci_low"] = float(mean_diff)
        out["ci_high"] = float(mean_diff)
    else:
        margin = float(tcrit) * se_diff
        out["ci_low"] = float(mean_diff - margin)
        out["ci_high"] = float(mean_diff + margin)

    p_value = 2.0 * (1.0 - _student_t_cdf_v1(abs(float(t_stat)), n - 1))
    out["p_value"] = max(0.0, min(1.0, float(p_value)))
    return out


def _experiment_ci_text_v1(low: Any, high: Any) -> str:
    """Render a compact CI string."""
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return f"[{float(low):.3f}, {float(high):.3f}]"
    return "(none)"


def _experiment_p_text_v1(value: Any) -> str:
    """Render p-values with slightly more useful precision than the generic metric formatter."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "(none)"
    p_v = float(value)
    if p_v < 0.001:
        return f"{p_v:.3e}"
    return f"{p_v:.4f}"


def _experiment_repeat_metric_label_v1(benchmark_id: str, metric_key: str) -> str:
    """Map internal metric keys to the short labels printed in submenu 19."""
    goat_map = {
        "success_rate": "success_rt",
        "mean_context_switch_accuracy": "ctx_switch",
        "mean_oracle_retrieval_precision": "retr_prec",
        "mean_internal_retrieval_event_ratio": "retr_rt",
        "mean_stabilization_latency": "stabilize",
        "mean_cumulative_prediction_error": "pred_e",
        "mean_llm_call_count": "llm_calls",
    }
    newborn_map = {
        "success_rate": "success_rt",
        "mean_milestone_score": "milestone_score",
        "mean_time_to_rested": "rest_t_success",
        "mean_time_to_rested_or_max_cycles": "rest_t_or_max",
        "mean_newborn_retrieval_event_count": "retr_evt",
        "mean_newborn_retrieval_non_noop_count": "retr_eff",
        "mean_lhsi_state_integrity_score": "lhsi",
        "mean_lhsi_wrong_stage_action_count": "wrong_stage",
        "mean_lhsi_repeated_action_loop_count": "lhsi_loops",
        "mean_lhsi_current_state_overwrite_proxy_count": "overwrite",
        "mean_lhsi_stale_memory_intrusion_proxy_count": "stale",
        "mean_lhsi_retrieval_action_dissociation_proxy_count": "dissoc",
        "mean_lhsi_retrieval_followup_basis_count": "basis",
        "mean_lhsi_provenance_complete_cycle_rate": "provenance",
        "mean_newborn_stress_active_cycle_count": "stress_act",
        "mean_newborn_stress_dropped_pred_count": "stress_pred",
        "mean_newborn_stress_dropped_cue_count": "stress_cue",
        "mean_newborn_retrieved_hint_set_count": "hint_set",
        "mean_newborn_retrieved_hint_active_step_count": "hint_active",
        "mean_newborn_retrieved_hint_used_step_count": "hint_used",
        "mean_cumulative_prediction_error": "pred_e",
        "mean_llm_call_count": "llm_calls",
    }

    metric_map = goat_map if benchmark_id == "goat04_context" else newborn_map
    return metric_map.get(metric_key, metric_key)


def render_experiment_repeat_stats_lines_v1(repeated_result: dict[str, Any]) -> list[str]:
    """Return repeat-level descriptive and paired comparison statistics.

    This renderer now supports any reference-vs-A comparison set, not just B/C.
    """
    if not isinstance(repeated_result, dict):
        return ["[experiments] stats mode   : (invalid)"]

    benchmark_id = repeated_result.get("benchmark_id")
    benchmark_id = benchmark_id if isinstance(benchmark_id, str) else ""

    metric_keys = repeated_result.get("metric_keys")
    metric_keys = metric_keys if isinstance(metric_keys, list) else []

    cond_stats = repeated_result.get("condition_metric_stats_by_condition")
    cond_stats = cond_stats if isinstance(cond_stats, dict) else {}

    paired_vs_a = repeated_result.get("paired_stats_vs_a")
    paired_vs_a = paired_vs_a if isinstance(paired_vs_a, dict) else {}

    compare_condition_ids = repeated_result.get("compare_condition_ids")
    if isinstance(compare_condition_ids, list):
        compare_ids = [cid for cid in compare_condition_ids if isinstance(cid, str) and cid]
    else:
        compare_ids = sorted(cid for cid in paired_vs_a.keys() if isinstance(cid, str) and cid)

    lines = [
        "[experiments] stats mode   : repeat-level paired two-sided t-test; mean, sample SD, and 95% CI.",
    ]

    for metric_key in metric_keys:
        label = _experiment_repeat_metric_label_v1(benchmark_id, str(metric_key))
        a_stats = (cond_stats.get("A") or {}).get(metric_key, {})

        lines.append(f"[experiments] stats {label}")
        lines.append(
            f"[experiments]   A mean={_experiment_metric_text_v1(a_stats.get('mean'))} "
            f"sd={_experiment_metric_text_v1(a_stats.get('sd'))} "
            f"ci95={_experiment_ci_text_v1(a_stats.get('ci_low'), a_stats.get('ci_high'))} "
            f"n={_experiment_metric_text_v1(a_stats.get('n'))}"
        )

        for cmp_cid in compare_ids:
            cmp_stats = (cond_stats.get(cmp_cid) or {}).get(metric_key, {})
            cmp_diff = (paired_vs_a.get(cmp_cid) or {}).get(metric_key, {})
            lines.append(
                f"[experiments]   {cmp_cid} mean={_experiment_metric_text_v1(cmp_stats.get('mean'))} "
                f"sd={_experiment_metric_text_v1(cmp_stats.get('sd'))} "
                f"ci95={_experiment_ci_text_v1(cmp_stats.get('ci_low'), cmp_stats.get('ci_high'))} "
                f"n={_experiment_metric_text_v1(cmp_stats.get('n'))} "
                f"vs_A n_pair={_experiment_metric_text_v1(cmp_diff.get('n'))} "
                f"delta({cmp_cid}-A)={_experiment_metric_text_v1(cmp_diff.get('mean_diff'))} "
                f"sd_delta={_experiment_metric_text_v1(cmp_diff.get('sd_diff'))} "
                f"ci95_delta={_experiment_ci_text_v1(cmp_diff.get('ci_low'), cmp_diff.get('ci_high'))} "
                f"p={_experiment_p_text_v1(cmp_diff.get('p_value'))}"
            )

    return lines


def experiment_run_condition_batch_v1(
    protocol_ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    run_one_episode_fn: Callable[..., dict[str, Any]] | None = None,
    condition_ids: list[str] | None = None,
    seed_list: list[int] | None = None,
    episodes_per_seed: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run a small benchmark batch by reusing the existing single-episode sandbox runner.

    Purpose / intent
    ----------------
    Menu 49 already has a stable single-run seam:
        experiment_run_one_episode_v1(...)

    This helper adds the next practical layer for the paper workflow:
        run condition A vs B vs C over the currently selected seeds
        and summarize the result in a benchmark-aware way.

    Current design choice
    ---------------------
    I intentionally reuse experiment_run_one_episode_v1(...) rather than introducing a second
    execution pathway. That keeps the behavior aligned with the already-tested single-run path
    and minimizes new moving parts.

    Important limitation
    --------------------
    Because this helper reuses the existing single-run function, each episode still writes its own
    cycle/episode JSONL files. A later patch can consolidate an entire batch under one shared run id.
    """
    if protocol_ctx is None:
        return {"ok": False, "why": "missing_protocol_ctx"}

    cfg = experiment_normalize_protocol_v1(getattr(protocol_ctx, "experiment_cfg", None))

    if run_one_episode_fn is None:
        def _default_episode_runner(
            protocol_ctx_arg: Ctx,
            *,
            condition_id: str | None = None,
            seed: int | None = None,
            episode_index: int = 0,
            suppress_output: bool = True,
        ) -> dict[str, Any]:
            return experiment_run_one_episode_v1(
                protocol_ctx_arg,
                runtime=runtime,
                condition_id=condition_id,
                seed=seed,
                episode_index=episode_index,
                suppress_output=suppress_output,
            )

        episode_runner: Callable[..., dict[str, Any]] = _default_episode_runner
    else:
        episode_runner = run_one_episode_fn

    # Keep batch runs aligned with single-run behavior: newborn_long_horizon should
    # use a real partial-observability setting unless the user explicitly chose one.
    if cfg.benchmark_id == "newborn_long_horizon" and float(cfg.obs_mask_prob) <= 0.0:
        cfg.obs_mask_prob = 0.35

    raw_conditions = condition_ids if isinstance(condition_ids, list) and condition_ids else ["A", "B", "C"]
    run_conditions = experiment_parse_condition_ids_v1(" ".join(str(x) for x in raw_conditions))
    run_conditions = run_conditions or ["A", "B", "C"]

    raw_seeds = seed_list if isinstance(seed_list, list) and seed_list else list(cfg.seed_list)
    run_seeds: list[int] = []
    seen_seeds: set[int] = set()
    for raw_seed in raw_seeds:
        try:
            seed_value = int(raw_seed)
        except Exception:
            continue

        if seed_value not in seen_seeds:
            seen_seeds.add(seed_value)
            run_seeds.append(seed_value)

    if not run_seeds:
        run_seeds = [11]

    try:
        eps = int(episodes_per_seed if episodes_per_seed is not None else cfg.episodes_per_seed)
    except Exception:
        eps = int(cfg.episodes_per_seed)
    eps = max(1, min(1000, eps))

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    ok_by_condition: dict[str, list[dict[str, Any]]] = {cid: [] for cid in run_conditions}

    for cid in run_conditions:
        for seed_value in run_seeds:
            for episode_no in range(eps):
                result = episode_runner(
                    protocol_ctx,
                    condition_id=cid,
                    seed=seed_value,
                    episode_index=episode_no,
                    suppress_output=suppress_output,
                )
                results.append(result)

                if not bool(result.get("ok")):
                    failures.append(
                        {
                            "condition_id": cid,
                            "seed": int(seed_value),
                            "episode_index": int(episode_no),
                            "why": result.get("why"),
                            "agent_mode": result.get("agent_mode"),
                            "llm_role": result.get("llm_role"),
                        }
                    )
                    continue

                ok_by_condition[cid].append(result)

    benchmark_id = str(cfg.benchmark_id or "")
    catalog = experiment_condition_catalog_v1()
    condition_summaries: list[dict[str, Any]] = []

    for cid in run_conditions:
        rows = ok_by_condition.get(cid, [])
        success_vals: list[float] = []
        milestone_scores: list[float] = []
        recovery_latencies: list[float] = []
        time_to_rested_vals: list[float] = []
        time_to_rested_or_max_vals: list[float] = []
        repeated_loops: list[float] = []
        retrieval_event_counts: list[float] = []
        retrieval_non_noop_counts: list[float] = []
        lhsi_scores: list[float] = []
        lhsi_wrong_stage: list[float] = []
        lhsi_repeated_loops: list[float] = []
        lhsi_overwrite_proxy: list[float] = []
        lhsi_stale_proxy: list[float] = []
        lhsi_dissoc_proxy: list[float] = []
        lhsi_followup_basis: list[float] = []
        lhsi_provenance_rates: list[float] = []
        stress_active_counts: list[float] = []
        stress_dropped_pred_counts: list[float] = []
        stress_dropped_cue_counts: list[float] = []
        hint_set_counts: list[float] = []
        hint_active_step_counts: list[float] = []
        hint_used_step_counts: list[float] = []
        context_switch_accs: list[float] = []
        oracle_retr_precs: list[float] = []
        internal_retr_rts: list[float] = []
        stabilization_lats: list[float] = []
        false_retrievals: list[float] = []
        cue_leakages: list[float] = []
        pred_errs: list[float] = []
        llm_calls: list[float] = []

        for row in rows:
            episode_record = row.get("episode_record")
            episode_record = episode_record if isinstance(episode_record, dict) else {}

            success = episode_record.get("success")
            if isinstance(success, bool):
                success_vals.append(1.0 if success else 0.0)

            value = episode_record.get("llm_call_count")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                llm_calls.append(float(value))

            if benchmark_id == "goat04_context":
                value = episode_record.get("context_switch_accuracy")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    context_switch_accs.append(float(value))

                value = episode_record.get("oracle_retrieval_precision")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    oracle_retr_precs.append(float(value))

                value = episode_record.get("internal_retrieval_event_ratio")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    internal_retr_rts.append(float(value))

                value = episode_record.get("stabilization_latency")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stabilization_lats.append(float(value))

                value = episode_record.get("false_retrieval_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    false_retrievals.append(float(value))

                value = episode_record.get("cue_leakage_violations")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cue_leakages.append(float(value))

            else:
                value = episode_record.get("milestone_score")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    milestone_scores.append(float(value))

                value = episode_record.get("recovery_latency")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    recovery_latencies.append(float(value))

                value = episode_record.get("time_to_rested")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    time_to_rested_vals.append(float(value))

                value = episode_record.get("time_to_rested_or_max_cycles")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    time_to_rested_or_max_vals.append(float(value))

                value = episode_record.get("repeated_action_loop_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    repeated_loops.append(float(value))

                value = episode_record.get("newborn_retrieval_event_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    retrieval_event_counts.append(float(value))

                value = episode_record.get("newborn_retrieval_non_noop_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    retrieval_non_noop_counts.append(float(value))

                value = episode_record.get("lhsi_state_integrity_score")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_scores.append(float(value))

                value = episode_record.get("lhsi_wrong_stage_action_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_wrong_stage.append(float(value))

                value = episode_record.get("lhsi_repeated_action_loop_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_repeated_loops.append(float(value))

                value = episode_record.get("lhsi_current_state_overwrite_proxy_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_overwrite_proxy.append(float(value))

                value = episode_record.get("lhsi_stale_memory_intrusion_proxy_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_stale_proxy.append(float(value))

                value = episode_record.get("lhsi_retrieval_action_dissociation_proxy_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_dissoc_proxy.append(float(value))

                value = episode_record.get("lhsi_retrieval_followup_basis_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_followup_basis.append(float(value))

                value = episode_record.get("lhsi_provenance_complete_cycle_rate")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lhsi_provenance_rates.append(float(value))

                value = episode_record.get("newborn_stress_active_cycle_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stress_active_counts.append(float(value))

                value = episode_record.get("newborn_stress_dropped_pred_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stress_dropped_pred_counts.append(float(value))

                value = episode_record.get("newborn_stress_dropped_cue_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    stress_dropped_cue_counts.append(float(value))

                value = episode_record.get("newborn_retrieved_hint_set_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    hint_set_counts.append(float(value))

                value = episode_record.get("newborn_retrieved_hint_active_step_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    hint_active_step_counts.append(float(value))

                value = episode_record.get("newborn_retrieved_hint_used_step_count")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    hint_used_step_counts.append(float(value))

            value = episode_record.get("cumulative_prediction_error")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                pred_errs.append(float(value))

        condition_def = catalog.get(cid)
        summary = {
            "condition_id": cid,
            "condition_label": condition_def.label if condition_def is not None else cid,
            "n_ok": int(len(rows)),
            "n_fail": int(sum(1 for item in failures if item.get("condition_id") == cid)),
            "success_rate": _experiment_mean_v1(success_vals),
            "mean_llm_call_count": _experiment_mean_v1(llm_calls),
        }

        if benchmark_id == "goat04_context":
            summary.update(
                {
                    "mean_context_switch_accuracy": _experiment_mean_v1(context_switch_accs),
                    "mean_oracle_retrieval_precision": _experiment_mean_v1(oracle_retr_precs),
                    "mean_internal_retrieval_event_ratio": _experiment_mean_v1(internal_retr_rts),
                    "mean_stabilization_latency": _experiment_mean_v1(stabilization_lats),
                    "mean_false_retrieval_count": _experiment_mean_v1(false_retrievals),
                    "mean_cue_leakage_violations": _experiment_mean_v1(cue_leakages),
                    "mean_cumulative_prediction_error": _experiment_mean_v1(pred_errs),
                }
            )

        else:
            summary.update(
                {
                    "mean_milestone_score": _experiment_mean_v1(milestone_scores),
                    "mean_recovery_latency": _experiment_mean_v1(recovery_latencies),
                    "mean_time_to_rested": _experiment_mean_v1(time_to_rested_vals),
                    "mean_time_to_rested_or_max_cycles": _experiment_mean_v1(time_to_rested_or_max_vals),
                    "mean_repeated_loops": _experiment_mean_v1(repeated_loops),
                    "mean_newborn_retrieval_event_count": _experiment_mean_v1(retrieval_event_counts),
                    "mean_newborn_retrieval_non_noop_count": _experiment_mean_v1(retrieval_non_noop_counts),
                    "mean_lhsi_state_integrity_score": _experiment_mean_v1(lhsi_scores),
                    "mean_lhsi_wrong_stage_action_count": _experiment_mean_v1(lhsi_wrong_stage),
                    "mean_lhsi_repeated_action_loop_count": _experiment_mean_v1(lhsi_repeated_loops),
                    "mean_lhsi_current_state_overwrite_proxy_count": _experiment_mean_v1(lhsi_overwrite_proxy),
                    "mean_lhsi_stale_memory_intrusion_proxy_count": _experiment_mean_v1(lhsi_stale_proxy),
                    "mean_lhsi_retrieval_action_dissociation_proxy_count": _experiment_mean_v1(lhsi_dissoc_proxy),
                    "mean_lhsi_retrieval_followup_basis_count": _experiment_mean_v1(lhsi_followup_basis),
                    "mean_lhsi_provenance_complete_cycle_rate": _experiment_mean_v1(lhsi_provenance_rates),
                    "mean_newborn_stress_active_cycle_count": _experiment_mean_v1(stress_active_counts),
                    "mean_newborn_stress_dropped_pred_count": _experiment_mean_v1(stress_dropped_pred_counts),
                    "mean_newborn_stress_dropped_cue_count": _experiment_mean_v1(stress_dropped_cue_counts),
                    "mean_newborn_retrieved_hint_set_count": _experiment_mean_v1(hint_set_counts),
                    "mean_newborn_retrieved_hint_active_step_count": _experiment_mean_v1(hint_active_step_counts),
                    "mean_newborn_retrieved_hint_used_step_count": _experiment_mean_v1(hint_used_step_counts),
                    "mean_cumulative_prediction_error": _experiment_mean_v1(pred_errs),
                }
            )

        condition_summaries.append(summary)

    try:
        protocol_ctx.experiment_last_summary["last_batch_benchmark_id"] = benchmark_id
        protocol_ctx.experiment_last_summary["last_batch_condition_ids"] = list(run_conditions)
        protocol_ctx.experiment_last_summary["last_batch_seed_list"] = list(run_seeds)
        protocol_ctx.experiment_last_summary["last_batch_episodes_per_seed"] = int(eps)
        protocol_ctx.experiment_last_summary["last_batch_run_count"] = int(len(results))
        protocol_ctx.experiment_last_summary["last_batch_ok_count"] = int(len(results) - len(failures))
        protocol_ctx.experiment_last_summary["last_batch_fail_count"] = int(len(failures))
    except Exception:
        pass

    return {
        "ok": True,
        "benchmark_id": benchmark_id,
        "condition_ids": list(run_conditions),
        "seed_list": list(run_seeds),
        "effective_obs_mask_prob": float(cfg.obs_mask_prob),
        "effective_newborn_stress_profile": str(getattr(cfg, "newborn_stress_profile", "baseline")),
        "effective_newborn_blackout_length": _newborn_effective_blackout_length_v1(
            getattr(cfg, "newborn_stress_profile", "baseline"),
            getattr(cfg, "newborn_blackout_length", 3),
        ),
        "episodes_per_seed": int(eps),
        "run_count": int(len(results)),
        "ok_count": int(len(results) - len(failures)),
        "fail_count": int(len(failures)),
        "results": results,
        "failures": failures,
        "condition_summaries": condition_summaries,
    }


def render_experiment_batch_summary_lines_v1(batch_result: dict[str, Any]) -> list[str]:
    """Return compact benchmark-aware lines for a condition-batch summary.

    This is intentionally terminal-oriented rather than report-oriented. The goal is to let you
    glance at A/B/C separation immediately after a run without opening JSONL files first.
    """
    if not isinstance(batch_result, dict):
        return ["[experiments] batch result     : (invalid)"]

    benchmark = batch_result.get("benchmark_id")
    benchmark = benchmark if isinstance(benchmark, str) and benchmark else "(unknown)"

    lines = [
        f"[experiments] batch benchmark   : {_experiment_metric_text_v1(benchmark)}",
        f"[experiments] batch conditions  : {_experiment_metric_text_v1(batch_result.get('condition_ids'))}",
        f"[experiments] batch seeds       : {_experiment_metric_text_v1(batch_result.get('seed_list'))}",
        f"[experiments] batch obs_mask    : {_experiment_metric_text_v1(batch_result.get('effective_obs_mask_prob'))}",
        f"[experiments] batch stress      : {_experiment_metric_text_v1(batch_result.get('effective_newborn_stress_profile'))} "
        f"effective_blackout_len={_experiment_metric_text_v1(batch_result.get('effective_newborn_blackout_length'))}",
        f"[experiments] batch eps/seed    : {_experiment_metric_text_v1(batch_result.get('episodes_per_seed'))}",
        f"[experiments] batch run_count   : {_experiment_metric_text_v1(batch_result.get('run_count'))}",
        f"[experiments] batch fail_count  : {_experiment_metric_text_v1(batch_result.get('fail_count'))}",
    ]

    summaries = batch_result.get("condition_summaries")
    summaries = summaries if isinstance(summaries, list) else []

    for row in summaries:
        if not isinstance(row, dict):
            continue

        cid = row.get("condition_id")
        label = row.get("condition_label")
        head = (
            f"[experiments] {cid} ({_experiment_metric_text_v1(label)}) "
            f"n_ok={_experiment_metric_text_v1(row.get('n_ok'))} "
            f"n_fail={_experiment_metric_text_v1(row.get('n_fail'))} "
            f"success_rt={_experiment_metric_text_v1(row.get('success_rate'))}"
        )

        if benchmark == "goat04_context":
            tail = (
                f" ctx_switch={_experiment_metric_text_v1(row.get('mean_context_switch_accuracy'))}"
                f" retr_prec={_experiment_metric_text_v1(row.get('mean_oracle_retrieval_precision'))}"
                f" retr_rt={_experiment_metric_text_v1(row.get('mean_internal_retrieval_event_ratio'))}"
                f" stabilize={_experiment_metric_text_v1(row.get('mean_stabilization_latency'))}"
                f" false_retr={_experiment_metric_text_v1(row.get('mean_false_retrieval_count'))}"
                f" cue_leak={_experiment_metric_text_v1(row.get('mean_cue_leakage_violations'))}"
                f" pred_e={_experiment_metric_text_v1(row.get('mean_cumulative_prediction_error'))}"
                f" llm_calls={_experiment_metric_text_v1(row.get('mean_llm_call_count'))}"
            )
        else:
            tail = (
                f" milestone_score={_experiment_metric_text_v1(row.get('mean_milestone_score'))}"
                f" recovery_lat={_experiment_metric_text_v1(row.get('mean_recovery_latency'))}"
                f" rest_t_success={_experiment_metric_text_v1(row.get('mean_time_to_rested'))}"
                f" rest_t_or_max={_experiment_metric_text_v1(row.get('mean_time_to_rested_or_max_cycles'))}"
                f" full_loops={_experiment_metric_text_v1(row.get('mean_repeated_loops'))}"
                f" retr_evt={_experiment_metric_text_v1(row.get('mean_newborn_retrieval_event_count'))}"
                f" retr_eff={_experiment_metric_text_v1(row.get('mean_newborn_retrieval_non_noop_count'))}"
                f" lhsi={_experiment_metric_text_v1(row.get('mean_lhsi_state_integrity_score'))}"
                f" wrong={_experiment_metric_text_v1(row.get('mean_lhsi_wrong_stage_action_count'))}"
                f" lhsi_loops={_experiment_metric_text_v1(row.get('mean_lhsi_repeated_action_loop_count'))}"
                f" overwrite={_experiment_metric_text_v1(row.get('mean_lhsi_current_state_overwrite_proxy_count'))}"
                f" stale={_experiment_metric_text_v1(row.get('mean_lhsi_stale_memory_intrusion_proxy_count'))}"
                f" dissoc={_experiment_metric_text_v1(row.get('mean_lhsi_retrieval_action_dissociation_proxy_count'))}"
                f" basis={_experiment_metric_text_v1(row.get('mean_lhsi_retrieval_followup_basis_count'))}"
                f" stress_act={_experiment_metric_text_v1(row.get('mean_newborn_stress_active_cycle_count'))}"
                f" stress_pred={_experiment_metric_text_v1(row.get('mean_newborn_stress_dropped_pred_count'))}"
                f" stress_cue={_experiment_metric_text_v1(row.get('mean_newborn_stress_dropped_cue_count'))}"
                f" hint_set={_experiment_metric_text_v1(row.get('mean_newborn_retrieved_hint_set_count'))}"
                f" hint_used={_experiment_metric_text_v1(row.get('mean_newborn_retrieved_hint_used_step_count'))}"
                f" pred_e={_experiment_metric_text_v1(row.get('mean_cumulative_prediction_error'))}"
            )

        lines.append(head + tail)

    lines.append(
        "[experiments] note             : batch mode currently reuses the single-episode runner, "
        "so each episode keeps its own JSONL files."
    )
    return lines


def _experiment_repeat_metric_keys_v1(benchmark_id: str) -> list[str]:
    """Return the compact metric set that best separates A/B/C for the active benchmark.

    I intentionally keep this small and benchmark-specific so submenu 19 stays readable in the
    terminal and focuses on the paper-facing numbers that have been most useful so far.
    """
    if benchmark_id == "goat04_context":
        return [
            "success_rate",
            "mean_context_switch_accuracy",
            "mean_oracle_retrieval_precision",
            "mean_internal_retrieval_event_ratio",
            "mean_stabilization_latency",
            "mean_cumulative_prediction_error",
            "mean_llm_call_count",
        ]

    return [
        "success_rate",
        "mean_milestone_score",
        "mean_time_to_rested",
        "mean_time_to_rested_or_max_cycles",
        "mean_newborn_retrieval_event_count",
        "mean_newborn_retrieval_non_noop_count",
        "mean_lhsi_state_integrity_score",
        "mean_lhsi_wrong_stage_action_count",
        "mean_lhsi_repeated_action_loop_count",
        "mean_lhsi_current_state_overwrite_proxy_count",
        "mean_lhsi_stale_memory_intrusion_proxy_count",
        "mean_lhsi_retrieval_action_dissociation_proxy_count",
        "mean_lhsi_retrieval_followup_basis_count",
        "mean_lhsi_provenance_complete_cycle_rate",
        "mean_newborn_stress_active_cycle_count",
        "mean_newborn_stress_dropped_pred_count",
        "mean_newborn_stress_dropped_cue_count",
        "mean_newborn_retrieved_hint_set_count",
        "mean_newborn_retrieved_hint_active_step_count",
        "mean_newborn_retrieved_hint_used_step_count",
        "mean_cumulative_prediction_error",
        "mean_llm_call_count",
    ]


def _experiment_random_seed_list_v1(
    count: int,
    *,
    low: int = 1,
    high: int = 999_999,
    rng: random.Random | None = None,
) -> list[int]:
    """Return a unique random seed list for one repeat.

    Important design point:
    experiment_run_one_episode_v1(...) reseeds the module-global random generator on every run.
    Therefore I use a local RNG here so the repeat driver keeps producing genuinely fresh seed lists.
    """
    try:
        n = int(count)
    except Exception:
        n = 1
    n = max(1, min(64, n))

    try:
        lo = int(low)
        hi = int(high)
    except Exception:
        lo = 1
        hi = 999_999

    if hi < lo:  #pylint: disable=consider-using-max-builtin
        hi = lo

    chooser = rng if rng is not None else random.SystemRandom()
    out: set[int] = set()

    while len(out) < n:
        out.add(int(chooser.randrange(lo, hi + 1)))

    return list(out)


def _render_experiment_repeat_condition_line_v1(
    condition_summary: dict[str, Any],
    *,
    benchmark_id: str,
    repeat_index: int | None = None,
    prefix: str = "[experiments]",
) -> str:
    """Render one compact condition line for submenu 19.

    The goal is to mirror the existing batch summary style, but keep it short enough that
    twenty repeats remain readable in a text terminal.
    """
    cid = condition_summary.get("condition_id")
    head = f"{prefix} "
    if isinstance(repeat_index, int):
        head += f"repeat {repeat_index:02d} "
    head += f"{_experiment_metric_text_v1(cid)}"

    if benchmark_id == "goat04_context":
        tail = (
            f" success_rt={_experiment_metric_text_v1(condition_summary.get('success_rate'))}"
            f" ctx_switch={_experiment_metric_text_v1(condition_summary.get('mean_context_switch_accuracy'))}"
            f" retr_prec={_experiment_metric_text_v1(condition_summary.get('mean_oracle_retrieval_precision'))}"
            f" retr_rt={_experiment_metric_text_v1(condition_summary.get('mean_internal_retrieval_event_ratio'))}"
            f" stabilize={_experiment_metric_text_v1(condition_summary.get('mean_stabilization_latency'))}"
            f" pred_e={_experiment_metric_text_v1(condition_summary.get('mean_cumulative_prediction_error'))}"
            f" llm_calls={_experiment_metric_text_v1(condition_summary.get('mean_llm_call_count'))}"
        )
    else:
        tail = (
            f" success_rt={_experiment_metric_text_v1(condition_summary.get('success_rate'))}"
            f" milestone_score={_experiment_metric_text_v1(condition_summary.get('mean_milestone_score'))}"
            f" rest_t_success={_experiment_metric_text_v1(condition_summary.get('mean_time_to_rested'))}"
            f" rest_t_or_max={_experiment_metric_text_v1(condition_summary.get('mean_time_to_rested_or_max_cycles'))}"
            f" retr_evt={_experiment_metric_text_v1(condition_summary.get('mean_newborn_retrieval_event_count'))}"
            f" retr_eff={_experiment_metric_text_v1(condition_summary.get('mean_newborn_retrieval_non_noop_count'))}"
            f" lhsi={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_state_integrity_score'))}"
            f" wrong={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_wrong_stage_action_count'))}"
            f" lhsi_loops={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_repeated_action_loop_count'))}"
            f" overwrite={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_current_state_overwrite_proxy_count'))}"
            f" stale={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_stale_memory_intrusion_proxy_count'))}"
            f" dissoc={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_retrieval_action_dissociation_proxy_count'))}"
            f" basis={_experiment_metric_text_v1(condition_summary.get('mean_lhsi_retrieval_followup_basis_count'))}"
            f" stress_act={_experiment_metric_text_v1(condition_summary.get('mean_newborn_stress_active_cycle_count'))}"
            f" stress_pred={_experiment_metric_text_v1(condition_summary.get('mean_newborn_stress_dropped_pred_count'))}"
            f" stress_cue={_experiment_metric_text_v1(condition_summary.get('mean_newborn_stress_dropped_cue_count'))}"
            f" hint_set={_experiment_metric_text_v1(condition_summary.get('mean_newborn_retrieved_hint_set_count'))}"
            f" hint_used={_experiment_metric_text_v1(condition_summary.get('mean_newborn_retrieved_hint_used_step_count'))}"
            f" pred_e={_experiment_metric_text_v1(condition_summary.get('mean_cumulative_prediction_error'))}"
            f" llm_calls={_experiment_metric_text_v1(condition_summary.get('mean_llm_call_count'))}"
        )

    return head + tail


def experiment_run_repeated_selected_vs_a_v1(
    protocol_ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    run_condition_batch_fn: Callable[..., dict[str, Any]] | None = None,
    condition_ids: list[str] | None = None,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run selected conditions repeatedly with fresh shared seeds and compare everything against A.

    Statistical intent
    ------------------
    Each repeat builds one shared random seed list, runs the selected condition set on that exact
    seed list, and then treats the repeat-level summaries as paired observations for comparisons
    against reference condition A.
    """
    if protocol_ctx is None:
        return {"ok": False, "why": "missing_protocol_ctx"}

    cfg = experiment_normalize_protocol_v1(getattr(protocol_ctx, "experiment_cfg", None))
    benchmark_id = str(cfg.benchmark_id or "")

    if run_condition_batch_fn is None:
        def _default_batch_runner(
            protocol_ctx_arg: Ctx,
            *,
            condition_ids: list[str] | None = None,
            seed_list: list[int] | None = None,
            episodes_per_seed: int | None = None,
            suppress_output: bool = True,
        ) -> dict[str, Any]:
            return experiment_run_condition_batch_v1(
                protocol_ctx_arg,
                runtime=runtime,
                condition_ids=condition_ids,
                seed_list=seed_list,
                episodes_per_seed=episodes_per_seed,
                suppress_output=suppress_output,
            )

        batch_runner: Callable[..., dict[str, Any]] = _default_batch_runner
    else:
        batch_runner = run_condition_batch_fn

    run_conditions = experiment_parse_condition_ids_v1(" ".join(str(x) for x in (condition_ids or ["A", "B", "C"])))
    run_conditions = run_conditions or ["A", "B", "C"]
    if "A" not in run_conditions:
        return {"ok": False, "why": "reference_condition_A_required"}

    compare_ids = [cid for cid in run_conditions if cid != "A"]

    try:
        repeat_count = int(repeats)
    except Exception:
        repeat_count = 20
    repeat_count = max(1, min(200, repeat_count))

    try:
        seed_count = int(seeds_per_repeat if seeds_per_repeat is not None else len(cfg.seed_list))
    except Exception:
        seed_count = len(cfg.seed_list)
    seed_count = max(1, min(64, seed_count or 5))

    rng = random.SystemRandom()
    metric_keys = _experiment_repeat_metric_keys_v1(benchmark_id)

    repeat_batches: list[dict[str, Any]] = []
    repeat_metric_rows: list[dict[str, dict[str, float]]] = []
    result_lines: list[str] = []

    aggregate: dict[str, dict[str, list[float]]] = {cid: defaultdict(list) for cid in run_conditions}

    for repeat_idx in range(1, repeat_count + 1):
        seed_values = _experiment_random_seed_list_v1(seed_count, rng=rng)
        print(f"[experiments] repeat {repeat_idx:02d}/{repeat_count}: seeds={seed_values}")

        batch = batch_runner(
            protocol_ctx,
            condition_ids=list(run_conditions),
            seed_list=seed_values,
            episodes_per_seed=int(cfg.episodes_per_seed),
            suppress_output=suppress_output,
        )

        repeat_batches.append(
            {
                "repeat_index": int(repeat_idx),
                "seed_list": list(seed_values),
                "batch": batch,
            }
        )

        repeat_metric_row: dict[str, dict[str, float]] = {}

        if not bool(batch.get("ok")):
            line = f"[experiments] repeat {repeat_idx:02d} failed: {_experiment_metric_text_v1(batch.get('why'))}"
            print(line)
            result_lines.append(line)
            repeat_metric_rows.append(repeat_metric_row)
            continue

        summaries = batch.get("condition_summaries")
        summaries = summaries if isinstance(summaries, list) else []

        for summary_row in summaries:
            if not isinstance(summary_row, dict):
                continue

            cid = summary_row.get("condition_id")
            if cid not in aggregate:
                continue

            line = _render_experiment_repeat_condition_line_v1(
                summary_row,
                benchmark_id=benchmark_id,
                repeat_index=repeat_idx,
            )
            print(line)
            result_lines.append(line)

            metric_row: dict[str, float] = {}
            for key in metric_keys:
                value = summary_row.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    value_f = float(value)
                    aggregate[str(cid)][key].append(value_f)
                    metric_row[key] = value_f

            repeat_metric_row[str(cid)] = metric_row

        repeat_metric_rows.append(repeat_metric_row)

    averages_by_condition: dict[str, dict[str, Any]] = {}
    average_lines: list[str] = []

    for cid in run_conditions:
        avg_row: dict[str, Any] = {"condition_id": cid}
        for key in metric_keys:
            avg_row[key] = _experiment_mean_v1(aggregate[cid].get(key, []))

        averages_by_condition[cid] = avg_row
        average_lines.append(
            _render_experiment_repeat_condition_line_v1(
                avg_row,
                benchmark_id=benchmark_id,
                prefix="[experiments] avg",
            )
        )

    condition_metric_stats_by_condition: dict[str, dict[str, dict[str, Any]]] = {}
    for cid in run_conditions:
        metric_stats: dict[str, dict[str, Any]] = {}
        for key in metric_keys:
            metric_stats[key] = _experiment_descriptive_stats_v1(aggregate[cid].get(key, []), confidence=0.95)
        condition_metric_stats_by_condition[cid] = metric_stats

    paired_stats_vs_a: dict[str, dict[str, dict[str, Any]]] = {}
    for cmp_cid in compare_ids:
        cmp_metric_stats: dict[str, dict[str, Any]] = {}
        for key in metric_keys:
            ref_series: list[float] = []
            cmp_series: list[float] = []

            for repeat_row in repeat_metric_rows:
                if not isinstance(repeat_row, dict):
                    continue

                ref_map = repeat_row.get("A")
                ref_map = ref_map if isinstance(ref_map, dict) else {}
                cmp_map = repeat_row.get(cmp_cid)
                cmp_map = cmp_map if isinstance(cmp_map, dict) else {}

                ref_value = ref_map.get(key)
                cmp_value = cmp_map.get(key)

                if (
                    isinstance(ref_value, (int, float))
                    and not isinstance(ref_value, bool)
                    and isinstance(cmp_value, (int, float))
                    and not isinstance(cmp_value, bool)
                ):
                    ref_series.append(float(ref_value))
                    cmp_series.append(float(cmp_value))

            cmp_metric_stats[key] = _experiment_paired_diff_stats_v1(ref_series, cmp_series, confidence=0.95)

        paired_stats_vs_a[cmp_cid] = cmp_metric_stats

    return {
        "ok": True,
        "benchmark_id": benchmark_id,
        "repeats": int(repeat_count),
        "seeds_per_repeat": int(seed_count),
        "condition_ids": list(run_conditions),
        "compare_condition_ids": list(compare_ids),
        "metric_keys": metric_keys,
        "repeat_batches": repeat_batches,
        "repeat_metric_rows": repeat_metric_rows,
        "result_lines": result_lines,
        "averages_by_condition": averages_by_condition,
        "average_lines": average_lines,
        "condition_metric_stats_by_condition": condition_metric_stats_by_condition,
        "paired_stats_vs_a": paired_stats_vs_a,
    }


def experiment_run_repeated_random_abc_v1(
    protocol_ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    run_condition_batch_fn: Callable[..., dict[str, Any]] | None = None,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run A/B/C batches repeatedly with fresh random seeds and aggregate repeat-level stats."""
    return experiment_run_repeated_selected_vs_a_v1(
        protocol_ctx,
        runtime=runtime,
        run_condition_batch_fn=run_condition_batch_fn,
        condition_ids=["A", "B", "C"],
        repeats=repeats,
        seeds_per_repeat=seeds_per_repeat,
        suppress_output=suppress_output,
    )


def experiment_run_repeated_random_ae_v1(
    protocol_ctx: Ctx,
    *,
    runtime: ExperimentRuntime,
    run_condition_batch_fn: Callable[..., dict[str, Any]] | None = None,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run A/E batches repeatedly with fresh random seeds and aggregate repeat-level stats."""
    return experiment_run_repeated_selected_vs_a_v1(
        protocol_ctx,
        runtime=runtime,
        run_condition_batch_fn=run_condition_batch_fn,
        condition_ids=["A", "E"],
        repeats=repeats,
        seeds_per_repeat=seeds_per_repeat,
        suppress_output=suppress_output,
    )


def experiments_menu_49_interactive(ctx: Ctx, operations: ExperimentMenuOperations) -> None:
    """Richer interactive config menu for the long-horizon experiment protocol.

    The menu keeps ordinary simulation untouched unless Menu 49 is used. It owns
    protocol configuration, JSONL preparation, isolated episode/batch execution,
    repeated statistical comparisons, and RCOS experiment launchers. Runner-visible
    callables are supplied through ``ExperimentMenuOperations`` for compatibility.
    """
    if ctx is None:
        print("[experiments] ctx missing; cannot open experiments menu.")
        return

    if not isinstance(getattr(ctx, "experiment_cfg", None), ExperimentProtocolConfig):
        ctx.experiment_cfg = ExperimentProtocolConfig()

    while True:
        cfg = experiment_normalize_protocol_v1(getattr(ctx, "experiment_cfg", None))
        ctx.experiment_cfg = cfg

        print("\nSelection: Experiments / Benchmarks (config + JSONL plumbing)\n")
        print(
            f"  benchmark={cfg.benchmark_id}  conditions={cfg.condition_ids}  seeds={cfg.seed_list}  "
            f"episodes_per_seed={cfg.episodes_per_seed}  max_cycles={cfg.max_cycles}"
        )
        effective_blackout_len = _newborn_effective_blackout_length_v1(
            cfg.newborn_stress_profile,
            cfg.newborn_blackout_length,
        )
        print(
            f"  obs_mask_prob={cfg.obs_mask_prob:.3f}  stress={cfg.newborn_stress_profile} "
            f"blackout_len={cfg.newborn_blackout_length} effective_blackout_len={effective_blackout_len}  "
            f"run_label={cfg.run_label or '(none)'}  output_dir={cfg.output_dir}"
        )
        print("  1) Show frozen protocol summary")
        print("  2) Show A-E condition table")
        print("  3) Show benchmark suite")
        print("  4) Show JSONL schema summary")
        print("  5) Show logging / output status")
        print("  6) Set benchmark id")
        print("  7) Set condition ids")
        print("  8) Set random seed list")
        print("  9) Set episodes per seed")
        print(" 10) Set max cycles")
        print(" 11) Set observation-mask probability")
        print(" 12) Set run label")
        print(" 13) Set output directory")
        print(" 14) Show example cycle / episode records")
        print(" 15) Prepare JSONL logging / output paths")
        print(" 16) Reset experiment protocol to defaults")
        print(" 17) Run one prepared experiment episode now (isolated sandbox)")
        print(" 18) Run A/B/C batch over current seeds (isolated sandbox)")
        print(" 19) Run x20 random-seed A/B/C repeats + averages")
        print(" 20) Run A/E batch over current seeds (isolated sandbox)")
        print(" 21) Run x20 random-seed A/E repeats + averages")
        print(" 22) Show RCOS robotic long-horizon protocol")
        print(" 23) Run one RCOS robotic long-horizon episode")
        print(" 24) Run RCOS robotic success/control suite")
        print(" 25) Run x20 RCOS robotic autonomy repeats")
        print(" 26) Show RCOS robotic perturbation protocol")
        print(" 27) Run x50 RCOS robotic perturbation repeats")
        print(" 28) Run x50 RCOS/no-RCOS ablation comparison")
        print(" 29) Show RCOS/no-RCOS ablation protocol")
        print(" 30) Set newborn stress profile")
        print(" 31) Set newborn blackout length")
        print("  0) Return to Main Menu")

        sub = input("Experiment menu select: ").strip().lower()
        if sub in ("0", "q", "quit", "return", "back"):
            return

        if sub == "1":
            print()
            print(render_experiment_protocol_summary_v1(ctx))
            continue

        if sub == "2":
            print()
            print(render_experiment_conditions_table_v1(ctx))
            continue

        if sub == "3":
            print()
            print(render_experiment_benchmarks_table_v1())
            continue

        if sub == "4":
            print()
            print(render_experiment_jsonl_schema_summary_v1())
            continue

        if sub == "5":
            print()
            print(render_experiment_logging_status_v1(ctx))
            continue

        if sub == "6":
            raw = input(
                "Benchmark id [goat04_context | newborn_long_horizon; blank=keep current]: "
            ).strip()
            if not raw:
                continue

            if raw in experiment_benchmark_catalog_v1():
                ctx.experiment_cfg.benchmark_id = raw
                print(f"[experiments] benchmark set to {raw}")
            else:
                print(f"[experiments] unknown benchmark id: {raw!r}")
            continue

        if sub == "7":
            raw = input(
                f"Condition ids (comma/space separated A-E) [current: {cfg.condition_ids}]: "
            ).strip()
            if not raw:
                continue

            parsed_conditions = experiment_parse_condition_ids_v1(raw)
            if parsed_conditions:
                ctx.experiment_cfg.condition_ids = parsed_conditions
                print(f"[experiments] conditions set to {parsed_conditions}")
            else:
                print("[experiments] no valid condition ids found; expected values like: A B C")
            continue

        if sub == "8":
            raw = input(
                f"Seed list (comma/space separated integers) [current: {cfg.seed_list}]: "
            ).strip()
            if not raw:
                continue

            parsed_seeds = experiment_parse_seed_list_v1(raw)
            if parsed_seeds:
                ctx.experiment_cfg.seed_list = parsed_seeds
                print(f"[experiments] seeds set to {parsed_seeds}")
            else:
                print("[experiments] no valid integer seeds found.")
            continue

        if sub == "9":
            raw = input(f"Episodes per seed [current: {cfg.episodes_per_seed}]: ").strip()
            if not raw:
                continue

            try:
                ctx.experiment_cfg.episodes_per_seed = int(raw)
                ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
                print(f"[experiments] episodes_per_seed set to {ctx.experiment_cfg.episodes_per_seed}")
            except Exception:
                print("[experiments] invalid integer for episodes_per_seed.")
            continue

        if sub == "10":
            raw = input(f"Max cycles [current: {cfg.max_cycles}]: ").strip()
            if not raw:
                continue

            try:
                ctx.experiment_cfg.max_cycles = int(raw)
                ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
                print(f"[experiments] max_cycles set to {ctx.experiment_cfg.max_cycles}")
            except Exception:
                print("[experiments] invalid integer for max_cycles.")
            continue

        if sub == "11":
            raw = input(f"Observation-mask probability 0.0..1.0 [current: {cfg.obs_mask_prob:.3f}]: ").strip()
            if not raw:
                continue

            try:
                ctx.experiment_cfg.obs_mask_prob = float(raw)
                ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
                print(f"[experiments] obs_mask_prob set to {ctx.experiment_cfg.obs_mask_prob:.3f}")
            except Exception:
                print("[experiments] invalid float for obs_mask_prob.")
            continue

        if sub == "12":
            raw = input(
                f"Run label (used in output filenames) [current: {cfg.run_label or '(none)'}]: "
            ).strip()
            ctx.experiment_cfg.run_label = raw
            ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
            print(f"[experiments] run_label set to {ctx.experiment_cfg.run_label or '(none)'}")
            continue

        if sub == "13":
            raw = input(f"Output directory [current: {cfg.output_dir}]: ").strip()
            if not raw:
                continue

            ctx.experiment_cfg.output_dir = raw
            ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
            print(f"[experiments] output_dir set to {ctx.experiment_cfg.output_dir}")
            continue

        if sub == "14":
            run_id = operations.make_run_id(ctx, cfg)
            cond0 = cfg.condition_ids[0] if cfg.condition_ids else "A"
            seed0 = cfg.seed_list[0] if cfg.seed_list else 11

            cycle_stub = operations.build_cycle_record(
                ctx,
                experiment_id=run_id,
                condition_id=cond0,
                seed=seed0,
                episode_index=0,
                cycle_index=0,
            )
            episode_stub = operations.build_episode_record(
                ctx,
                experiment_id=run_id,
                condition_id=cond0,
                seed=seed0,
                episode_index=0,
            )

            print()
            print("Example cycle record:")
            print(json.dumps(cycle_stub, indent=2, ensure_ascii=False))
            print()
            print("Example episode summary record:")
            print(json.dumps(episode_stub, indent=2, ensure_ascii=False))
            continue

        if sub == "15":
            info = operations.prepare_logging(ctx, reset_buffers=True)
            if not bool(info.get("ok")):
                print(f"[experiments] logging preparation failed: {info.get('why')}")
                continue

            print()
            print("[experiments] logging prepared.")
            print(f"  run_id            : {info.get('run_id')}")
            print(f"  cycle_json_path   : {info.get('cycle_json_path')}")
            print(f"  episode_json_path : {info.get('episode_json_path')}")
            print("  note              : normal CCA8 simulation is still unchanged until a later run hook uses this protocol.")
            continue

        if sub == "16":
            reset_experiment_protocol_v1(ctx)
            print("[experiments] protocol reset to exp_protocol_v1 defaults.")
            continue

        if sub == "17":
            raw_condition = input(
                f"Condition id for single run (blank = first selected: {cfg.condition_ids[0] if cfg.condition_ids else 'A'}): "
            ).strip()
            raw_seed = input(
                f"Seed for single run (blank = first selected: {cfg.seed_list[0] if cfg.seed_list else 11}): "
            ).strip()

            run_condition = raw_condition or (cfg.condition_ids[0] if cfg.condition_ids else "A")
            try:
                run_seed = int(raw_seed) if raw_seed else (cfg.seed_list[0] if cfg.seed_list else 11)
            except Exception:
                print("[experiments] invalid integer seed.")
                continue

            print()
            print("[experiments] running one isolated sandbox episode...")
            result = operations.run_one_episode(
                ctx,
                condition_id=run_condition,
                seed=run_seed,
                episode_index=0,
                suppress_output=True,
            )

            if not bool(result.get("ok")):
                print(f"[experiments] run failed: {result.get('why')}")
                if result.get("agent_mode") or result.get("llm_role"):
                    print(
                        f"  detail: agent_mode={result.get('agent_mode')} llm_role={result.get('llm_role')} "
                        "still needs the later LLM action hook patch."
                    )
                continue

            for line in render_experiment_episode_summary_lines_v1(result):
                print(line)

            print(f"[experiments] cycle_json_path   : {result.get('cycle_json_path')}")
            print(f"[experiments] episode_json_path : {result.get('episode_json_path')}")
            if result.get("captured_output_lines"):
                print(f"[experiments] sandbox console   : {result.get('captured_output_lines')} lines captured and suppressed")
            continue

        if sub == "18":
            print()
            print("[experiments] running A/B/C batch over current seeds...")
            batch = operations.run_condition_batch(
                ctx,
                condition_ids=["A", "B", "C"],
                seed_list=list(cfg.seed_list),
                episodes_per_seed=int(cfg.episodes_per_seed),
                suppress_output=True,
            )

            if not bool(batch.get("ok")):
                print(f"[experiments] batch failed: {batch.get('why')}")
                continue

            for line in render_experiment_batch_summary_lines_v1(batch):
                print(line)

            failures = batch.get("failures")
            if isinstance(failures, list) and failures:
                print("[experiments] failure details:")
                for item in failures[:5]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"  condition={item.get('condition_id')} seed={item.get('seed')} "
                        f"episode={item.get('episode_index')} why={item.get('why')}"
                    )
                if len(failures) > 5:
                    print(f"  ... plus {len(failures) - 5} more failure(s)")
            continue

        if sub == "19":
            print()
            print("[experiments] running x20 A/B/C batches with fresh random seeds...")

            repeated = operations.run_repeated_abc(
                ctx,
                repeats=20,
                seeds_per_repeat=len(cfg.seed_list) if cfg.seed_list else 5,
                suppress_output=True,
            )

            if not bool(repeated.get("ok")):
                print(f"[experiments] repeated run failed: {repeated.get('why')}")
                continue

            print()
            print("[experiments] result list (20 repeats):")
            for line in repeated.get("result_lines", []):
                print(line)

            print()
            print(f"[experiments] averages over {repeated.get('repeats')} repeats:")
            for line in repeated.get("average_lines", []):
                print(line)

            print()
            print("[experiments] repeat-level stats:")
            for line in render_experiment_repeat_stats_lines_v1(repeated):
                print(line)

            bundle = operations.write_repeated_bundle(
                ctx,
                repeated,
                bundle_label="abc_repeats",
            )
            if bool(bundle.get("ok")):
                print()
                print("[experiments] repeated analysis bundle written:")
                print(f"  run_id             : {bundle.get('run_id')}")
                print(f"  episode_rows_path  : {bundle.get('episode_rows_jsonl_path')}")
                print(f"  repeat_rows_path   : {bundle.get('repeat_rows_jsonl_path')}")
                print(f"  stats_json_path    : {bundle.get('stats_json_path')}")
                print(
                    f"  counts             : episode_rows={bundle.get('episode_row_count')} "
                    f"repeat_rows={bundle.get('repeat_row_count')}"
                )
            else:
                print(f"[experiments] repeated analysis bundle failed: {bundle.get('why')}")
            continue

        if sub == "20":
            print()
            print("[experiments] running A/E batch over current seeds...")
            batch = operations.run_condition_batch(
                ctx,
                condition_ids=["A", "E"],
                seed_list=list(cfg.seed_list),
                episodes_per_seed=int(cfg.episodes_per_seed),
                suppress_output=True,
            )

            if not bool(batch.get("ok")):
                print(f"[experiments] batch failed: {batch.get('why')}")
                continue

            for line in render_experiment_batch_summary_lines_v1(batch):
                print(line)

            failures = batch.get("failures")
            if isinstance(failures, list) and failures:
                print("[experiments] failure details:")
                for item in failures[:5]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"  condition={item.get('condition_id')} seed={item.get('seed')} "
                        f"episode={item.get('episode_index')} why={item.get('why')}"
                    )
                if len(failures) > 5:
                    print(f"  ... plus {len(failures) - 5} more failure(s)")
            continue

        if sub == "21":
            print()
            print("[experiments] running x20 A/E batches with fresh random seeds...")

            repeated = operations.run_repeated_ae(
                ctx,
                repeats=20,
                seeds_per_repeat=len(cfg.seed_list) if cfg.seed_list else 5,
                suppress_output=True,
            )

            if not bool(repeated.get("ok")):
                print(f"[experiments] repeated run failed: {repeated.get('why')}")
                continue

            print()
            print("[experiments] result list (20 repeats):")
            for line in repeated.get("result_lines", []):
                print(line)

            print()
            print(f"[experiments] averages over {repeated.get('repeats')} repeats:")
            for line in repeated.get("average_lines", []):
                print(line)

            print()
            print("[experiments] repeat-level stats:")
            for line in render_experiment_repeat_stats_lines_v1(repeated):
                print(line)

            bundle = operations.write_repeated_bundle(
                ctx,
                repeated,
                bundle_label="ae_repeats",
            )
            if bool(bundle.get("ok")):
                print()
                print("[experiments] repeated analysis bundle written:")
                print(f"  run_id             : {bundle.get('run_id')}")
                print(f"  episode_rows_path  : {bundle.get('episode_rows_jsonl_path')}")
                print(f"  repeat_rows_path   : {bundle.get('repeat_rows_jsonl_path')}")
                print(f"  stats_json_path    : {bundle.get('stats_json_path')}")
                print(
                    f"  counts             : episode_rows={bundle.get('episode_row_count')} "
                    f"repeat_rows={bundle.get('repeat_row_count')}"
                )
            else:
                print(f"[experiments] repeated analysis bundle failed: {bundle.get('why')}")
            continue

        if sub == "22":
            print()
            print(render_rcos_robotic_protocol_v1())
            continue

        if sub == "23":
            raw_controller = input(
                "Controller [autonomy_v1 | scripted_success | hazard_negative_control | incomplete_no_return_control; "
                "blank=autonomy_v1]: "
            ).strip()
            raw_seed = input("Seed for RCOS robotic run (blank = 11): ").strip()

            controller_id = raw_controller or "autonomy_v1"
            try:
                run_seed = int(raw_seed) if raw_seed else 11
            except Exception:
                print("[rcos-exp] invalid integer seed.")
                continue

            print()
            print(f"[rcos-exp] running one RCOS robotic episode: controller={controller_id} seed={run_seed}")
            result = rcos_robotic_run_episode_v1(
                controller_id=controller_id,
                seed=run_seed,
                max_steps=int(cfg.max_cycles),
                output_dir=str(cfg.output_dir),
                run_label=str(cfg.run_label or "bica_rcos"),
                write_jsonl=bool(cfg.jsonl_write_cycle_records or cfg.jsonl_write_episode_records),
            )

            for line in render_rcos_robotic_episode_lines_v1(result):
                print(line)
            continue

        if sub == "24":
            raw_seed = input("Seed for RCOS robotic suite (blank = 11): ").strip()
            try:
                run_seed = int(raw_seed) if raw_seed else 11
            except Exception:
                print("[rcos-exp] invalid integer seed.")
                continue

            print()
            print(f"[rcos-exp] running RCOS robotic success/control suite: seed={run_seed}")
            suite = rcos_robotic_run_suite_v1(
                seed=run_seed,
                max_steps=int(cfg.max_cycles),
                output_dir=str(cfg.output_dir),
                run_label=str(cfg.run_label or "bica_rcos"),
                write_jsonl=bool(cfg.jsonl_write_cycle_records or cfg.jsonl_write_episode_records),
            )

            for line in render_rcos_robotic_suite_lines_v1(suite):
                print(line)
            continue

        if sub == "25":
            print()
            print("[rcos-exp] running x20 RCOS robotic autonomy repeats...")
            repeated = rcos_robotic_run_repeats_v1(
                repeats=20,
                max_steps=int(cfg.max_cycles),
                output_dir=str(cfg.output_dir),
                run_label=str(cfg.run_label or "bica_rcos"),
                write_jsonl=bool(cfg.jsonl_write_cycle_records or cfg.jsonl_write_episode_records),
            )

            for line in render_rcos_robotic_repeats_lines_v1(repeated):
                print(line)
            continue

        if sub == "26":
            print()
            print(render_rcos_robotic_perturbation_protocol_v1())
            continue

        if sub == "27":
            raw_repeats = input("Perturbed repeat count (blank = 50): ").strip()
            raw_intensity = input("Perturbation intensity [mild | moderate | severe; blank = moderate]: ").strip()

            try:
                repeat_count = int(raw_repeats) if raw_repeats else 50
            except Exception:
                print("[rcos-perturb] invalid integer repeat count.")
                continue

            intensity = raw_intensity or "moderate"
            run_max_steps = max(80, int(cfg.max_cycles))

            print()
            print(
                f"[rcos-perturb] running x{repeat_count} perturbed RCOS robotic repeats: "
                f"intensity={intensity} max_steps={run_max_steps}"
            )
            repeated = rcos_robotic_run_perturbed_repeats_v1(
                repeats=repeat_count,
                intensity=intensity,
                max_steps=run_max_steps,
                output_dir=str(cfg.output_dir),
                run_label=str(cfg.run_label or "bica_rcos_perturbed"),
                write_jsonl=bool(cfg.jsonl_write_cycle_records or cfg.jsonl_write_episode_records),
            )

            for line in render_rcos_robotic_perturbed_repeats_lines_v1(repeated):
                print(line)
            continue

        if sub == "28":
            raw_repeats = input("Ablation repeat count (blank = 50): ").strip()
            raw_intensity = input("Perturbation intensity [mild | moderate | severe; blank = moderate]: ").strip()

            try:
                repeat_count = int(raw_repeats) if raw_repeats else 50
            except Exception:
                print("[rcos-ablate] invalid integer repeat count.")
                continue

            intensity = raw_intensity or "moderate"
            run_max_steps = max(80, int(cfg.max_cycles))

            print()
            print(
                f"[rcos-ablate] running x{repeat_count} paired RCOS/no-RCOS ablation repeats: "
                f"intensity={intensity} max_steps={run_max_steps}"
            )
            ablation = rcos_robotic_run_ablation_repeats_v1(
                repeats=repeat_count,
                intensity=intensity,
                max_steps=run_max_steps,
                output_dir=str(cfg.output_dir),
                run_label=str(cfg.run_label or "bica_rcos_ablation"),
                write_jsonl=bool(cfg.jsonl_write_cycle_records or cfg.jsonl_write_episode_records),
            )

            for line in render_rcos_robotic_ablation_repeats_lines_v1(ablation):
                print(line)
            continue

        if sub == "29":
            print()
            print(render_rcos_robotic_ablation_protocol_v1())
            continue

        if sub == "30":
            raw = input(
                "Newborn stress profile [baseline | blackout_short | blackout_long | route_loss; blank=keep current]: "
            ).strip().lower()
            if not raw:
                continue
            if raw not in NEWBORN_STRESS_PROFILES_V1:
                print("[experiments] invalid newborn stress profile.")
                continue
            ctx.experiment_cfg.newborn_stress_profile = raw
            ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
            print(f"[experiments] newborn_stress_profile set to {ctx.experiment_cfg.newborn_stress_profile}")
            continue

        if sub == "31":
            raw = input(
                f"Newborn blackout length in cycles [current: {cfg.newborn_blackout_length}]: "
            ).strip()

            if not raw:
                continue

            try:
                ctx.experiment_cfg.newborn_blackout_length = int(raw)
                ctx.experiment_cfg = experiment_normalize_protocol_v1(ctx.experiment_cfg)
                print(f"[experiments] newborn_blackout_length set to {ctx.experiment_cfg.newborn_blackout_length}")
            except Exception:
                print("[experiments] invalid integer for newborn blackout length.")
            continue

        print("[experiments] Unknown selection. Use 0..31.")
