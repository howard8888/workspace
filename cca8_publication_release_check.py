#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the consolidated CCA8 Superintelligence publication installation."""

from __future__ import annotations

import argparse
import compileall
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cca8_publication_analysis import analyze_batch_v1
from cca8_publication_integrity import verify_source_manifest_v1, write_json_exclusive_v1
from cca8_publication_lhsi_sensitivity import run_lhsi_sensitivity_v1
from cca8_publication_protocol import build_manifest_v1, write_manifest_exclusive_v1
from cca8_publication_run import run_batch_v1, verify_order_invariance_v1

__version__ = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    started = time.perf_counter()
    process = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": process.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "stdout": process.stdout,
        "stderr": process.stderr,
        "ok": process.returncode == 0,
    }


def run_release_check_v1(
    *,
    root: str | Path,
    with_smoke: bool,
    allow_development_python: bool,
) -> dict[str, Any]:
    source_root = Path(root).resolve()
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    python_ok = (sys.version_info.major, sys.version_info.minor) == (3, 11)
    checks.append(
        {
            "name": "python_3_11",
            "ok": python_ok or allow_development_python,
            "python_version": platform.python_version(),
            "development_override": bool(allow_development_python and not python_ok),
        }
    )

    holdout_candidates = [
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() and "holdout" in path.name.lower() and "hypoth" not in path.name.lower()
    ]
    checks.append(
        {
            "name": "no_holdout_manifest_in_source",
            "ok": not holdout_candidates,
            "candidates": holdout_candidates,
        }
    )

    manifest_path = source_root / "publication_source_manifest.json"
    if manifest_path.exists():
        source_result = verify_source_manifest_v1(source_root, manifest_path)
    else:
        source_result = {"ok": False, "errors": ["publication_source_manifest_missing"]}
    checks.append({"name": "source_manifest", **source_result})

    compile_ok = compileall.compile_dir(
        str(source_root), quiet=1, force=True, rx=None, workers=1
    )
    checks.append({"name": "compileall", "ok": bool(compile_ok)})

    pytest_command = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-q",
        "tests/test_conflicted_repair_benchmark.py",
        "tests/test_newborn_guarded_repair_mechanism.py",
        "tests/test_publication_release_v1.py",
    ]
    pytest_result = _run_command(pytest_command, cwd=source_root)
    checks.append({"name": "focused_pytest", **pytest_result})

    smoke_summary: dict[str, Any] | None = None
    if with_smoke and all(check.get("ok") for check in checks):
        with tempfile.TemporaryDirectory(prefix="cca8_publication_release_check_") as tmp:
            temp_root = Path(tmp)
            manifest = build_manifest_v1(
                master_nonce="cca8-release-check-smoke-v1",
                seed_count=1,
                manifest_kind="development",
                label="release-check smoke",
            )
            manifest_file = temp_root / "development_manifest.json"
            write_manifest_exclusive_v1(manifest_file, manifest)
            batch = run_batch_v1(
                manifest_path=manifest_file,
                output_dir=temp_root / "smoke_batch",
                profiles=["baseline", "conflicted_repair"],
                conditions=["A", "B", "C"],
                limit=None,
                allow_development_python=allow_development_python,
                holdout_confirmation=None,
                quiet=True,
            )
            order = verify_order_invariance_v1(
                manifest_path=manifest_file,
                output_dir=temp_root / "order_check",
                episode_count=1,
                allow_development_python=allow_development_python,
            )
            analysis = analyze_batch_v1(
                batch_dir=batch["output_dir"],
                output_dir=temp_root / "analysis",
                require_frozen_holdout=False,
                bootstrap_replicates=500,
                randomization_replicates=2_000,
                analysis_seed="release-check",
            )
            sensitivity = run_lhsi_sensitivity_v1(
                batch_dir=batch["output_dir"],
                output_dir=temp_root / "lhsi_sensitivity",
                require_frozen_holdout=False,
            )
            smoke_summary = {
                "batch": batch,
                "order_invariance": {
                    "ok": order["ok"],
                    "comparison_count": order["comparison_count"],
                    "mismatch_count": order["mismatch_count"],
                },
                "analysis": analysis,
                "lhsi_sensitivity": sensitivity,
            }
            checks.append(
                {
                    "name": "fresh_process_smoke",
                    "ok": bool(
                        batch.get("ok")
                        and order.get("ok")
                        and analysis.get("ok")
                        and sensitivity.get("ok")
                    ),
                    "summary": smoke_summary,
                }
            )

    ok = all(check.get("ok") for check in checks)
    return {
        "schema": "cca8_publication_release_check_v1",
        "release_check_version": __version__,
        "ok": ok,
        "created_utc": _utc_now(),
        "root": str(source_root),
        "python_version": platform.python_version(),
        "allow_development_python": bool(allow_development_python),
        "with_smoke": bool(with_smoke),
        "checks": checks,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "holdout_manifest_generated": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--with-smoke", action="store_true")
    parser.add_argument("--allow-development-python", action="store_true")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        result = run_release_check_v1(
            root=args.root,
            with_smoke=bool(args.with_smoke),
            allow_development_python=bool(args.allow_development_python),
        )
        output = write_json_exclusive_v1(args.report, result)
        summary = {
            "ok": result["ok"],
            "report": str(output.resolve()),
            "elapsed_seconds": result["elapsed_seconds"],
            "checks": [
                {"name": check.get("name"), "ok": check.get("ok")}
                for check in result["checks"]
            ],
            "holdout_manifest_generated": False,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    except Exception as exc:
        print(f"[publication-release-check] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
