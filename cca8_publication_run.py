#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-process batch runner and validation utilities for the publication benchmark."""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cca8_publication_integrity import (
    protocol_hash_v1,
    source_tree_manifest_v1,
    write_checksum_text_v1,
    write_json_exclusive_v1,
)
from cca8_publication_protocol import (
    CONDITIONS,
    PROFILES,
    PROTOCOL_VERSION,
    load_manifest_v1,
    protocol_metadata_v1,
    sha256_hex,
    validate_manifest_v1,
)

__version__ = "1.0.0"
BATCH_SCHEMA = "cca8_publication_batch_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_csv_values(raw: str, allowed: tuple[str, ...], *, upper: bool) -> list[str]:
    values = []
    for token in str(raw or "").replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        token = token.upper() if upper else token.lower()
        if token not in allowed:
            raise ValueError(f"unsupported value {token!r}; allowed={list(allowed)}")
        if token not in values:
            values.append(token)
    return values or list(allowed)


def _python_is_311() -> bool:
    return (sys.version_info.major, sys.version_info.minor) == (3, 11)


def _job_rows(
    manifest: dict[str, Any],
    *,
    profiles: Iterable[str],
    conditions: Iterable[str],
    limit: int | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        for profile in profiles:
            for condition in conditions:
                idx = int(entry["episode_index"])
                job_id = f"e{idx:03d}__{profile}__{condition}"
                rows.append(
                    {
                        "schema": "cca8_publication_job_v1",
                        "protocol_version": PROTOCOL_VERSION,
                        "manifest_hash": manifest["manifest_hash"],
                        "manifest_sha256": manifest["manifest_hash"],
                        "manifest_kind": manifest["manifest_kind"],
                        "job_id": job_id,
                        "profile": profile,
                        "condition": condition,
                        "episode_index": idx,
                        "episode_seed": int(entry["episode_seed"]),
                        "schedule": copy.deepcopy(entry),
                    }
                )
    if limit is not None:
        return rows[: max(0, int(limit))]
    return rows


def _episode_signature(record: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic scientific fields used for order-invariance checks."""
    keys = (
        "success",
        "milestone_vector",
        "milestone_score",
        "milestone_steps",
        "time_to_rested",
        "time_to_rested_or_max_cycles",
        "publication_profile",
        "publication_schedule_hash",
        "publication_route_changed",
        "publication_memory_usable",
        "publication_reacquisition_started",
        "publication_reacquisition_onset_cycle",
        "publication_current_reacquired",
        "publication_guarded_repair_count_pre_completion",
        "publication_guarded_field_use_count_pre_completion",
        "publication_replacement_count_pre_completion",
        "publication_unsafe_follow_count_pre_completion",
        "publication_missing_state_timeout_count_pre_completion",
        "publication_probe_count_pre_completion",
        "publication_challenge_resolved",
        "publication_challenge_resolution_reason",
        "publication_failure_reason",
        "publication_direct_hint_use_count",
        "llm_call_count",
    )
    return {key: record.get(key) for key in keys}


def validate_batch_records_v1(
    workers: list[dict[str, Any]],
    *,
    expected_job_count: int | None = None,
    expected_manifest_sha256: str | None = None,
    expected_source_tree_sha256: str | None = None,
    expected_protocol_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate process isolation, matched schedules, and publication guardrails."""
    errors: list[str] = []
    if expected_job_count is not None and len(workers) != int(expected_job_count):
        errors.append("worker_count_mismatch")

    process_nonces: set[str] = set()
    worker_pids: list[int] = []
    matched: dict[tuple[int, str], dict[str, tuple[str, int]]] = {}
    for row in workers:
        process = row.get("process") if isinstance(row, dict) else None
        process = process if isinstance(process, dict) else {}
        nonce = str(process.get("process_nonce") or "")
        if not nonce:
            errors.append(f"missing_process_nonce:{row.get('job_id')}")
        elif nonce in process_nonces:
            errors.append(f"duplicate_process_nonce:{row.get('job_id')}")
        else:
            process_nonces.add(nonce)
        try:
            pid = int(process.get("pid"))
            worker_pids.append(pid)
            if pid == os.getpid():
                errors.append(f"episode_not_in_fresh_process:{row.get('job_id')}")
        except Exception:
            errors.append(f"invalid_worker_pid:{row.get('job_id')}")

        if expected_manifest_sha256 and str(row.get("manifest_sha256") or "") != expected_manifest_sha256:
            errors.append(f"manifest_hash_mismatch:{row.get('job_id')}")
        if expected_source_tree_sha256 and str(row.get("source_tree_sha256") or "") != expected_source_tree_sha256:
            errors.append(f"source_tree_hash_mismatch:{row.get('job_id')}")
        if expected_protocol_sha256 and str(row.get("protocol_sha256") or "") != expected_protocol_sha256:
            errors.append(f"protocol_hash_mismatch:{row.get('job_id')}")

        episode = row.get("episode_record") if isinstance(row, dict) else None
        episode = episode if isinstance(episode, dict) else {}
        if int(episode.get("llm_call_count", 0) or 0) != 0:
            errors.append(f"llm_call_detected:{row.get('job_id')}")
        if int(episode.get("publication_direct_hint_use_count", 0) or 0) != 0:
            errors.append(f"direct_hint_use_detected:{row.get('job_id')}")
        if str(episode.get("publication_schedule_hash") or "") != str(row.get("schedule_hash") or ""):
            errors.append(f"schedule_hash_record_mismatch:{row.get('job_id')}")

        key = (int(row.get("episode_index", -1)), str(row.get("profile") or ""))
        condition = str(row.get("condition") or "")
        matched.setdefault(key, {})[condition] = (
            str(row.get("schedule_hash") or ""),
            int(row.get("episode_seed", -1)),
        )

    for key, by_condition in matched.items():
        if set(by_condition) == set(CONDITIONS):
            schedule_hashes = {item[0] for item in by_condition.values()}
            seeds = {item[1] for item in by_condition.values()}
            if len(schedule_hashes) != 1:
                errors.append(f"matched_schedule_hash_mismatch:{key}")
            if len(seeds) != 1:
                errors.append(f"matched_seed_mismatch:{key}")

    return {
        "ok": not errors,
        "errors": errors,
        "worker_count": len(workers),
        "unique_process_nonce_count": len(process_nonces),
        "unique_worker_pid_count": len(set(worker_pids)),
        "fresh_process_per_episode_verified": len(process_nonces) == len(workers) and not any(
            error.startswith("episode_not_in_fresh_process") for error in errors
        ),
        "matched_condition_sets_checked": sum(1 for value in matched.values() if set(value) == set(CONDITIONS)),
    }


def run_batch_v1(
    *,
    manifest_path: Path,
    output_dir: Path,
    profiles: list[str],
    conditions: list[str],
    limit: int | None,
    allow_development_python: bool,
    holdout_confirmation: str | None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Execute a manifest as one fresh subprocess per episode."""
    manifest = load_manifest_v1(manifest_path)
    kind = str(manifest["manifest_kind"])
    if kind == "holdout":
        if holdout_confirmation != "RUN_FROZEN_HOLDOUT":
            raise ValueError(
                "holdout execution requires --confirm-holdout RUN_FROZEN_HOLDOUT"
            )
        if limit is not None:
            raise ValueError("a holdout run may not use --limit")
        if profiles != list(PROFILES) or conditions != list(CONDITIONS):
            raise ValueError("a holdout run must execute both profiles and all A/B/C conditions")
        if not _python_is_311():
            raise RuntimeError("the frozen holdout must run under Python 3.11")
    elif not _python_is_311() and not allow_development_python:
        raise RuntimeError(
            "development execution outside Python 3.11 requires --allow-development-python"
        )

    source_root = Path(__file__).resolve().parent
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "jobs").mkdir()
    (output_dir / "process_logs").mkdir()

    source_manifest = source_tree_manifest_v1(source_root)
    protocol_meta = protocol_metadata_v1()
    protocol_hash = protocol_hash_v1()
    jobs = _job_rows(manifest, profiles=profiles, conditions=conditions, limit=limit)
    if not jobs:
        raise ValueError("no jobs selected")

    shutil.copy2(manifest_path, output_dir / "seed_manifest.json")
    write_json_exclusive_v1(output_dir / "source_manifest.json", source_manifest)
    write_json_exclusive_v1(output_dir / "protocol_metadata.json", protocol_meta)

    initial = {
        "schema": BATCH_SCHEMA,
        "batch_runner_version": __version__,
        "protocol_version": PROTOCOL_VERSION,
        "manifest_kind": kind,
        "manifest_sha256": manifest["manifest_hash"],
        "manifest_file_sha256": sha256_hex(manifest_path.read_bytes()),
        "source_tree_sha256": source_manifest["source_tree_sha256"],
        "protocol_sha256": protocol_hash,
        "profiles": profiles,
        "conditions": conditions,
        "job_count": len(jobs),
        "strict_python311": not allow_development_python,
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "started_at_utc": _utc_now(),
        "status": "running",
    }
    write_json_exclusive_v1(output_dir / "batch_metadata_initial.json", initial)

    worker_script = source_root / "cca8_publication_worker.py"
    workers: list[dict[str, Any]] = []
    episodes_path = output_dir / "episodes.jsonl"
    workers_path = output_dir / "workers.jsonl"
    started = time.perf_counter()

    for ordinal, base_job in enumerate(jobs, start=1):
        job = dict(base_job)
        job_dir = output_dir / "episodes" / job["job_id"]
        job.update(
            {
                "job_dir": str(job_dir),
                "expected_source_tree_sha256": source_manifest["source_tree_sha256"],
                "expected_protocol_sha256": protocol_hash,
                "strict_python311": not allow_development_python,
            }
        )
        job_path = output_dir / "jobs" / f"{job['job_id']}.json"
        write_json_exclusive_v1(job_path, job)

        env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(job["episode_seed"])
        env["PYTHONNOUSERSITE"] = "1"
        command = [sys.executable, str(worker_script), "--job", str(job_path), "--source-root", str(source_root)]
        process = subprocess.run(
            command,
            cwd=str(source_root),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path = output_dir / "process_logs" / f"{job['job_id']}.stdout.txt"
        stderr_path = output_dir / "process_logs" / f"{job['job_id']}.stderr.txt"
        stdout_path.write_text(process.stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(process.stderr, encoding="utf-8", newline="\n")

        if process.returncode != 0:
            failure = {
                "schema": "cca8_publication_batch_failure_v1",
                "job": job,
                "returncode": process.returncode,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "failed_at_utc": _utc_now(),
            }
            write_json_exclusive_v1(output_dir / "BATCH_FAILED.json", failure)
            raise RuntimeError(
                f"worker failed for {job['job_id']}; see {stderr_path}"
            )

        result_path = job_dir / "worker_result.json"
        worker_result = _load_json(result_path)
        workers.append(worker_result)
        _append_jsonl(workers_path, worker_result)

        episode_record = dict(worker_result["episode_record"])
        episode_record["publication_worker"] = {
            "job_id": worker_result["job_id"],
            "pid": worker_result["process"]["pid"],
            "process_nonce": worker_result["process"]["process_nonce"],
            "python_version": worker_result["process"]["python_version"],
            "source_tree_sha256": worker_result["source_tree_sha256"],
            "protocol_sha256": worker_result["protocol_sha256"],
            "manifest_sha256": worker_result["manifest_sha256"],
            "manifest_kind": worker_result["manifest_kind"],
            "schedule_hash": worker_result["schedule_hash"],
        }
        _append_jsonl(episodes_path, episode_record)

        if not quiet:
            success = episode_record.get("success")
            failure_reason = episode_record.get("publication_failure_reason")
            print(
                f"[publication] {ordinal:>3}/{len(jobs)} {job['job_id']} "
                f"success={success} failure={failure_reason or '-'}"
            )

    validation = validate_batch_records_v1(
        workers,
        expected_job_count=len(jobs),
        expected_manifest_sha256=str(manifest["manifest_hash"]),
        expected_source_tree_sha256=str(source_manifest["source_tree_sha256"]),
        expected_protocol_sha256=str(protocol_hash),
    )
    if not validation["ok"]:
        write_json_exclusive_v1(output_dir / "BATCH_VALIDATION_FAILED.json", validation)
        raise RuntimeError("batch validation failed: " + ", ".join(validation["errors"]))

    elapsed = time.perf_counter() - started
    final = dict(initial)
    final.update(
        {
            "finished_at_utc": _utc_now(),
            "elapsed_seconds": round(elapsed, 3),
            "status": "complete",
            "validation": validation,
            "episode_jsonl": "episodes.jsonl",
            "worker_jsonl": "workers.jsonl",
        }
    )
    write_json_exclusive_v1(output_dir / "batch_metadata_final.json", final)
    checksum_path = write_checksum_text_v1(output_dir)
    return {
        "ok": True,
        "output_dir": str(output_dir),
        "job_count": len(jobs),
        "elapsed_seconds": round(elapsed, 3),
        "validation": validation,
        "checksums": str(checksum_path),
    }


def _read_worker_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"non-object row at {path}:{line_number}")
            rows.append(value)
    return rows


def verify_existing_batch_v1(batch_dir: Path) -> dict[str, Any]:
    workers = _read_worker_jsonl(batch_dir / "workers.jsonl")
    metadata = _load_json(batch_dir / "batch_metadata_final.json")
    result = validate_batch_records_v1(
        workers,
        expected_job_count=int(metadata.get("job_count", -1)),
        expected_manifest_sha256=str(metadata.get("manifest_sha256") or ""),
        expected_source_tree_sha256=str(metadata.get("source_tree_sha256") or ""),
        expected_protocol_sha256=str(metadata.get("protocol_sha256") or ""),
    )
    result["batch_dir"] = str(batch_dir.resolve())
    return result


def verify_order_invariance_v1(
    *,
    manifest_path: Path,
    output_dir: Path,
    episode_count: int,
    allow_development_python: bool,
) -> dict[str, Any]:
    manifest = load_manifest_v1(manifest_path, require_kind="development")
    if episode_count < 1:
        raise ValueError("episode_count must be positive")
    # Use the first N schedules, one profile, and all conditions in opposite order.
    reduced = copy.deepcopy(manifest)
    reduced["entries"] = reduced["entries"][:episode_count]
    reduced["seed_count"] = episode_count
    basis = copy.deepcopy(reduced)
    basis.pop("manifest_hash", None)
    reduced["manifest_hash"] = sha256_hex(basis)

    output_dir.mkdir(parents=True, exist_ok=False)
    reduced_path = output_dir / "order_check_manifest.json"
    write_json_exclusive_v1(reduced_path, reduced)

    run_abc = run_batch_v1(
        manifest_path=reduced_path,
        output_dir=output_dir / "order_ABC",
        profiles=["conflicted_repair"],
        conditions=["A", "B", "C"],
        limit=None,
        allow_development_python=allow_development_python,
        holdout_confirmation=None,
        quiet=True,
    )
    run_cba = run_batch_v1(
        manifest_path=reduced_path,
        output_dir=output_dir / "order_CBA",
        profiles=["conflicted_repair"],
        conditions=["C", "B", "A"],
        limit=None,
        allow_development_python=allow_development_python,
        holdout_confirmation=None,
        quiet=True,
    )

    def load_signatures(path: Path) -> dict[tuple[int, str, str], dict[str, Any]]:
        out: dict[tuple[int, str, str], dict[str, Any]] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                key = (
                    int(record["episode_index"]),
                    str(record["publication_profile"]),
                    str(record["condition"]),
                )
                out[key] = _episode_signature(record)
        return out

    signatures_abc = load_signatures(Path(run_abc["output_dir"]) / "episodes.jsonl")
    signatures_cba = load_signatures(Path(run_cba["output_dir"]) / "episodes.jsonl")
    mismatches = []
    for key in sorted(set(signatures_abc) | set(signatures_cba)):
        if signatures_abc.get(key) != signatures_cba.get(key):
            mismatches.append(
                {"key": list(key), "ABC": signatures_abc.get(key), "CBA": signatures_cba.get(key)}
            )
    report = {
        "schema": "cca8_publication_order_invariance_report_v1",
        "ok": not mismatches,
        "episode_count": episode_count,
        "comparison_count": len(signatures_abc),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "order_ABC": run_abc,
        "order_CBA": run_cba,
    }
    write_json_exclusive_v1(output_dir / "order_invariance_report.json", report)
    return report


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run a development or frozen holdout manifest")
    run_parser.add_argument("--manifest", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--profiles", default=",".join(PROFILES))
    run_parser.add_argument("--conditions", default=",".join(CONDITIONS))
    run_parser.add_argument("--limit", type=int, default=None)
    run_parser.add_argument("--allow-development-python", action="store_true")
    run_parser.add_argument("--confirm-holdout", default=None)
    run_parser.add_argument("--quiet", action="store_true")

    validate_parser = sub.add_parser("validate-results", help="validate a completed batch")
    validate_parser.add_argument("--batch", required=True)

    order_parser = sub.add_parser("verify-order", help="run opposite condition orders and compare outcomes")
    order_parser.add_argument("--manifest", required=True)
    order_parser.add_argument("--output", required=True)
    order_parser.add_argument("--episode-count", type=int, default=2)
    order_parser.add_argument("--allow-development-python", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            profiles = _parse_csv_values(args.profiles, PROFILES, upper=False)
            conditions = _parse_csv_values(args.conditions, CONDITIONS, upper=True)
            result = run_batch_v1(
                manifest_path=Path(args.manifest).resolve(),
                output_dir=Path(args.output),
                profiles=profiles,
                conditions=conditions,
                limit=args.limit,
                allow_development_python=bool(args.allow_development_python),
                holdout_confirmation=args.confirm_holdout,
                quiet=bool(args.quiet),
            )
        elif args.command == "validate-results":
            result = verify_existing_batch_v1(Path(args.batch))
        else:
            result = verify_order_invariance_v1(
                manifest_path=Path(args.manifest).resolve(),
                output_dir=Path(args.output),
                episode_count=int(args.episode_count),
                allow_development_python=bool(args.allow_development_python),
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 2
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"[publication] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
