#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experiment protocol, logging, and record helpers for CCA8.

Purpose
-------
This module owns the stable, runner-independent part of the CCA8 experiment
subsystem: condition and benchmark definitions, newborn observation stressors,
protocol parsing and normalization, JSON/JSONL path preparation, record-schema
builders, and repeat-result archival helpers.

The actual experiment execution loop remains in ``cca8_run.py`` for this first
extraction. It still owns sandbox construction, controller/environment wiring,
Menu 49, LLM adviser calls, and closed-loop episode execution. Keeping that
runtime-dependent layer in the runner makes this refactor structural and avoids
introducing a circular import.

Compatibility boundary
----------------------
``cca8_run`` continues to expose its historical experiment names. Most are
aliases to this module. A few small runner wrappers supply runner-visible
callbacks at call time so existing monkeypatch-based tests and downstream tools
continue to work after the extraction.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from cca8_context import Ctx, ExperimentProtocolConfig
from cca8_controller import body_space_zone
from cca8_env import EnvObservation

__version__ = "0.1.0"

RunIdFactory = Callable[[Ctx | None, ExperimentProtocolConfig | None], str]
BodySpaceZoneFn = Callable[[Ctx], str]

__all__ = [
    "ExperimentConditionDef",
    "ExperimentBenchmarkDef",
    "ExperimentProtocolConfig",
    "NEWBORN_STRESS_PROFILES_V1",
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

    Patch-2 uses this as the single source of truth for prepared output locations.
    The later execution patch can reuse the same helper unchanged. The optional
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

    This is not yet the live experiment runner output. It is the stable builder/helper that
    the later execution patch can call once episodes are being driven automatically. The
    injected callbacks preserve the historical runner monkeypatch seams after extraction.
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
