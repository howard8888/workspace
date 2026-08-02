#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-episode worker used by the fresh-process publication batch runner."""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cca8_publication_integrity import (
    protocol_hash_v1,
    source_tree_manifest_v1,
    write_json_exclusive_v1,
)
from cca8_publication_protocol import FROZEN_PROTOCOL, PROTOCOL_VERSION, sha256_hex


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("job file must contain one JSON object")
    return value


def _load_cycle_records(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _precompletion_cycles(rows: list[dict[str, Any]], episode: dict[str, Any]) -> list[dict[str, Any]]:
    time_to_rested = episode.get("time_to_rested")
    if isinstance(time_to_rested, (int, float)):
        # cycle_index is zero based while time_to_rested is a one-based cognitive-cycle count.
        return [row for row in rows if int(row.get("cycle_index", -1)) < int(time_to_rested)]
    return rows


def _extract_mechanism_details(
    cycle_rows: list[dict[str, Any]],
    episode: dict[str, Any],
) -> dict[str, Any]:
    active = _precompletion_cycles(cycle_rows, episode)
    invalidation_count = 0
    invalidated_families: list[str] = []
    repaired_families: list[str] = []
    repaired_relations: list[str] = []
    repaired_metadata: list[str] = []
    structural_repairs: list[dict[str, Any]] = []
    replacement_events: list[dict[str, Any]] = []

    for row in active:
        inv = row.get("workingmap_mask_invalidation")
        if isinstance(inv, dict):
            invalidation_count += int(inv.get("invalidated_family_count", 0) or 0)
            for family in inv.get("families", []) or []:
                if isinstance(family, str) and family not in invalidated_families:
                    invalidated_families.append(family)

        event = row.get("retrieval_event")
        if not isinstance(event, dict) or not event.get("ok"):
            continue
        load = event.get("load")
        load = load if isinstance(load, dict) else {}
        mode = str(load.get("mode") or event.get("mode") or "merge").lower()
        if mode == "replace":
            replacement_events.append(
                {
                    "step": event.get("step"),
                    "reason": event.get("reason"),
                    "engram_id": (event.get("chosen_seed") or {}).get("engram_id")
                    if isinstance(event.get("chosen_seed"), dict)
                    else None,
                    "entities": int(load.get("entities", 0) or 0),
                    "relations": int(load.get("relations", 0) or 0),
                }
            )
            continue

        changed = any(
            int(load.get(name, 0) or 0) > 0
            for name in ("added_entities", "filled_slots", "added_edges", "filled_metadata")
        )
        if not changed:
            continue
        families = [x for x in (load.get("repaired_families") or []) if isinstance(x, str)]
        metadata = [x for x in (load.get("repaired_metadata") or []) if isinstance(x, str)]
        targets = [x for x in (load.get("added_edge_targets") or []) if isinstance(x, str)]
        for family in families:
            if family not in repaired_families:
                repaired_families.append(family)
        for item in metadata:
            if item not in repaired_metadata:
                repaired_metadata.append(item)
        relations = [f"self->{target}:distance_to" for target in targets]
        for relation in relations:
            if relation not in repaired_relations:
                repaired_relations.append(relation)
        structural_repairs.append(
            {
                "step": event.get("step"),
                "reason": event.get("reason"),
                "engram_id": (event.get("chosen_seed") or {}).get("engram_id")
                if isinstance(event.get("chosen_seed"), dict)
                else None,
                "filled_slots": int(load.get("filled_slots", 0) or 0),
                "added_entities": int(load.get("added_entities", 0) or 0),
                "added_edges": int(load.get("added_edges", 0) or 0),
                "filled_metadata": int(load.get("filled_metadata", 0) or 0),
                "repaired_families": families,
                "repaired_relations": relations,
                "repaired_metadata": metadata,
            }
        )

    return {
        "publication_invalidation_count_pre_completion": invalidation_count,
        "publication_invalidated_families_pre_completion": invalidated_families,
        "publication_guarded_repair_events_pre_completion": structural_repairs,
        "publication_repaired_families_pre_completion": repaired_families,
        "publication_repaired_relations_pre_completion": repaired_relations,
        "publication_repaired_metadata_pre_completion": repaired_metadata,
        "publication_replacement_events_pre_completion": replacement_events,
    }


def _normalize_episode(
    episode: dict[str, Any],
    *,
    job: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = dict(episode)
    schedule = job["schedule"]
    failure = episode.get("conflicted_repair_failure_reason")
    if failure == "unsafe_follow_before_probe":
        failure = "unsafe_follow"

    out.update(
        {
            "publication_protocol_version": PROTOCOL_VERSION,
            "publication_profile": job["profile"],
            "publication_schedule_hash": schedule["schedule_hash"],
            "publication_route_change_draw": schedule.get("route_change_draw"),
            "publication_route_changed": bool(schedule.get("route_changed")),
            "publication_encoding_draws": list(schedule.get("encoding_draws") or []),
            "publication_encoding_available": list(schedule.get("encoding_available") or []),
            "publication_memory_usable": bool(schedule.get("memory_usable")),
            "publication_reacquisition_draws": list(schedule.get("reacquisition_draws") or []),
            "publication_reacquisition_onset_draws": list(
                schedule.get("reacquisition_onset_draws") or []
            ),
            "publication_reacquisition_started": bool(
                episode.get("conflicted_repair_reacquired")
            ),
            "publication_reacquisition_onset_cycle": schedule.get(
                "reacquisition_first_onset_challenge_cycle"
            ),
            "publication_current_reacquired": bool(
                episode.get("conflicted_repair_reacquired")
            ),
            "publication_guarded_repair_count_pre_completion": int(
                episode.get("newborn_retrieval_non_noop_count_to_completion", 0) or 0
            )
            if job["condition"] == "A"
            else 0,
            "publication_guarded_field_use_count_pre_completion": int(
                episode.get("newborn_guarded_field_use_count_to_completion", 0) or 0
            ),
            "publication_guarded_field_use_events_pre_completion": list(
                episode.get("newborn_guarded_field_use_events_to_completion") or []
            ),
            "publication_retrieval_count_pre_completion": int(
                episode.get("newborn_retrieval_event_count_to_completion", 0) or 0
            ),
            "publication_replacement_count_pre_completion": int(
                episode.get("newborn_retrieval_replace_count_to_completion", 0) or 0
            ),
            "publication_probe_count_pre_completion": int(
                episode.get("conflicted_repair_probe_count", 0) or 0
            ),
            "publication_unsafe_follow_count_pre_completion": int(
                episode.get("conflicted_repair_unsafe_follow_count", 0) or 0
            ),
            "publication_missing_state_timeout_count_pre_completion": int(
                failure == "missing_state_timeout"
            ),
            "publication_challenge_resolved": str(
                episode.get("conflicted_repair_status") or ""
            )
            in {"passed", "failed"},
            "publication_resolution_count_pre_completion": int(
                str(episode.get("conflicted_repair_status") or "") in {"passed", "failed"}
            ),
            "publication_challenge_resolution_reason": (
                "passed"
                if episode.get("conflicted_repair_status") == "passed"
                else failure
            ),
            "publication_failure_reason": failure,
            "publication_direct_hint_use_count": int(
                episode.get("newborn_retrieved_hint_used_step_count", 0) or 0
            ),
            "publication_precompletion_definition": (
                "Counts include cognitive cycles through first safe-rest completion; "
                "failed episodes include the full 60-cycle budget."
            ),
        }
    )
    out.update(_extract_mechanism_details(cycle_rows, episode))
    return out


def _verify_schedule_record(job: dict[str, Any], episode: dict[str, Any]) -> list[str]:
    if job["profile"] != "conflicted_repair":
        return []
    schedule = job["schedule"]
    errors: list[str] = []

    def close_list(left: Any, right: Any, tol: float = 1e-15) -> bool:
        if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
            return False
        return all(abs(float(a) - float(b)) <= tol for a, b in zip(left, right))

    if bool(episode.get("conflicted_repair_conflict_present")) != bool(schedule["route_changed"]):
        errors.append("route_change_mismatch")
    if abs(float(episode.get("conflicted_repair_conflict_draw")) - float(schedule["route_change_draw"])) > 1e-15:
        errors.append("route_change_draw_mismatch")
    if not close_list(episode.get("conflicted_repair_encoding_draws"), schedule["encoding_draws"]):
        errors.append("encoding_draws_mismatch")
    if bool(episode.get("conflicted_repair_memory_available")) != bool(schedule["memory_usable"]):
        errors.append("memory_usable_mismatch")
    if not close_list(episode.get("conflicted_repair_reacquire_draws"), schedule["reacquisition_draws"]):
        errors.append("reacquisition_draws_mismatch")
    return errors


def run_worker_v1(job_path: Path, source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    job = _load_json(job_path)
    if job.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("job protocol version mismatch")
    if bool(job.get("strict_python311")) and (sys.version_info.major, sys.version_info.minor) != (3, 11):
        raise RuntimeError("strict publication worker requires Python 3.11")

    source_manifest = source_tree_manifest_v1(source_root)
    source_hash = source_manifest["source_tree_sha256"]
    protocol_hash = protocol_hash_v1()
    if source_hash != job.get("expected_source_tree_sha256"):
        raise RuntimeError("source tree changed after batch launch")
    if protocol_hash != job.get("expected_protocol_sha256"):
        raise RuntimeError("protocol changed after batch launch")

    # Import only after integrity checks. Each invocation is a new interpreter.
    import cca8_column  # pylint: disable=import-outside-toplevel
    import cca8_controller  # pylint: disable=import-outside-toplevel
    import cca8_run  # pylint: disable=import-outside-toplevel
    from cca8_context import Ctx, ExperimentProtocolConfig  # pylint: disable=import-outside-toplevel

    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()

    job_dir = Path(job["job_dir"]).resolve()
    job_dir.mkdir(parents=True, exist_ok=False)
    runtime_output = job_dir / "runtime"
    runtime_output.mkdir()
    schedule = job["schedule"]
    ctx = Ctx()
    ctx.experiment_cfg = ExperimentProtocolConfig(
        benchmark_id="newborn_long_horizon",
        condition_ids=[str(job["condition"])],
        seed_list=[int(job["episode_seed"])],
        episodes_per_seed=1,
        max_cycles=FROZEN_PROTOCOL.episode_max_cycles,
        obs_mask_prob=FROZEN_PROTOCOL.ordinary_observation_mask_probability,
        newborn_stress_profile=str(job["profile"]),
        newborn_blackout_length=FROZEN_PROTOCOL.challenge_deadline_cycles,
        conflicted_repair_variant_mode="stochastic_v3",
        conflicted_repair_conflict_probability=FROZEN_PROTOCOL.route_change_probability,
        conflicted_repair_encoding_opportunities=FROZEN_PROTOCOL.memory_encoding_opportunities,
        conflicted_repair_reacquire_probability=(
            FROZEN_PROTOCOL.current_reacquisition_onset_probability_per_cycle
        ),
        conflicted_repair_reacquire_start_delay=(
            FROZEN_PROTOCOL.current_reacquisition_first_challenge_cycle - 1
        ),
        llm_model=None,
        output_dir=str(runtime_output),
        run_label=str(job["job_id"]),
        jsonl_write_cycle_records=True,
        jsonl_write_episode_records=True,
    )

    result = cca8_run.experiment_run_one_episode_v1(
        ctx,
        condition_id=str(job["condition"]),
        seed=int(job["episode_seed"]),
        episode_index=int(job["episode_index"]),
        suppress_output=True,
    )
    if result.get("ok") is not True:
        raise RuntimeError(f"CCA8 episode failed: {result!r}")

    raw_cycle_path = Path(result["cycle_json_path"])
    raw_episode_path = Path(result["episode_json_path"])
    cycle_path = job_dir / "cycles.jsonl"
    raw_episode_copy = job_dir / "episode_raw.jsonl"
    shutil.copy2(raw_cycle_path, cycle_path)
    shutil.copy2(raw_episode_path, raw_episode_copy)
    cycle_rows = _load_cycle_records(cycle_path)
    normalized = _normalize_episode(
        dict(result["episode_record"]), job=job, cycle_rows=cycle_rows
    )
    schedule_errors = _verify_schedule_record(job, normalized)
    if schedule_errors:
        raise RuntimeError("condition-blind schedule verification failed: " + ", ".join(schedule_errors))
    if int(normalized.get("publication_direct_hint_use_count", 0) or 0) != 0:
        raise RuntimeError("direct retrieved-hint pathway was used")
    if int(normalized.get("llm_call_count", 0) or 0) != 0:
        raise RuntimeError("LLM/API call detected")

    process = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "process_nonce": secrets.token_hex(16),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "started_and_finished_utc": _utc_now(),
    }
    worker = {
        "schema": "cca8_publication_worker_result_v1",
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job["job_id"],
        "profile": job["profile"],
        "condition": job["condition"],
        "episode_index": int(job["episode_index"]),
        "episode_seed": int(job["episode_seed"]),
        "schedule_hash": schedule["schedule_hash"],
        "manifest_kind": job["manifest_kind"],
        "manifest_sha256": job["manifest_sha256"],
        "source_tree_sha256": source_hash,
        "protocol_sha256": protocol_hash,
        "process": process,
        "cycle_record_count": len(cycle_rows),
        "cycle_jsonl": "cycles.jsonl",
        "raw_episode_jsonl": "episode_raw.jsonl",
        "episode_record_sha256": sha256_hex(normalized),
        "episode_record": normalized,
    }
    write_json_exclusive_v1(job_dir / "worker_result.json", worker)
    return worker


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    try:
        worker = run_worker_v1(Path(args.job), Path(args.source_root))
        print(json.dumps({"ok": True, "job_id": worker["job_id"]}, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"[publication-worker] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
