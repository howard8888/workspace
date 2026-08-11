#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture the exact software environment used for publication validation or holdout.

Capture the software and host environment associated with a publication run.

Publication pipeline
--------------------
1. ``cca8_publication_protocol.py`` defines the frozen parameters and creates
   or validates development and reserved final-evaluation seed manifests.
2. ``cca8_publication_integrity.py`` hashes the source tree and protocol and
   verifies checksums for generated output trees.
3. ``cca8_publication_release_check.py`` validates the installed publication
   code before a final manifest or final evaluation is generated.
4. ``cca8_publication_environment.py`` records Python, packages, platform,
   Git state, and the source and protocol hashes.
5. ``cca8_publication_run.py`` expands a manifest into jobs and launches one
   fresh Python subprocess for every experimental trial.
6. ``cca8_publication_worker.py`` executes one isolated trial and writes its
   normalized trial, cycle, mechanism, and process records.
7. ``cca8_publication_analysis.py`` produces the primary aggregate, paired,
   and mechanism-level statistical analyses.
8. ``cca8_publication_lhsi_sensitivity.py`` recalculates the legacy LHSI,
   termed TIC in the manuscript, under the 17 post hoc robustness
   specifications.

Purpose of this module
----------------------
This module creates a provenance record for the environment in which the
publication source was validated or the reserved final evaluation was run. It
records the Python version, executable, implementation, prefixes, virtual-
environment status, operating system, machine and processor description, CPU
count, and the complete installed Python package name/version list.

When Git is available, the record also includes the current commit, working-
tree status, whether the tree is clean, and the configured origin URL. The
module independently calculates the current publication source-tree hash and
protocol hash so that the environment record can be linked to a specific code
and protocol state rather than only to a machine description.

By default, command-line capture requires Python 3.11, matching the publication
workflow. A development-only override permits capture under another Python
version without changing the recorded facts. The output is written with
exclusive creation to prevent silent replacement of an earlier provenance
record.

This module does not validate experiment outcomes, execute trials, or install
packages. Because an exact environment record may contain local executable
paths, Git remotes, and other machine-specific provenance, public distributions
may use a separately documented sanitized copy while preserving the exact
original in the private execution archive.
"""


from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cca8_publication_integrity import protocol_hash_v1, source_tree_manifest_v1, write_json_exclusive_v1
from cca8_publication_protocol import PROTOCOL_VERSION


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    process = subprocess.run(
        ["git", *args], cwd=str(root), text=True, capture_output=True, check=False
    )
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def capture_environment_v1(root: str | Path) -> dict[str, Any]:
    '''docstring to do'''
    source_root = Path(root).resolve()
    packages = sorted(
        (
            {"name": dist.metadata.get("Name") or dist.name, "version": dist.version}
            for dist in importlib.metadata.distributions()
        ),
        key=lambda row: str(row["name"]).lower(),
    )
    head_rc, head, head_err = _git(source_root, "rev-parse", "HEAD")
    status_rc, status, status_err = _git(source_root, "status", "--porcelain=v1", "--branch")
    remote_rc, remote, _ = _git(source_root, "remote", "get-url", "origin")
    source = source_tree_manifest_v1(source_root)
    return {
        "schema": "cca8_publication_environment_v1",
        "protocol_version": PROTOCOL_VERSION,
        "captured_utc": _utc_now(),
        "python": {
            "version": platform.python_version(),
            "version_info": list(sys.version_info[:5]),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "prefix": sys.prefix,
            "base_prefix": getattr(sys, "base_prefix", sys.prefix),
            "virtual_environment_active": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        },
        "platform": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "git": {
            "available": head_rc == 0 and status_rc == 0,
            "head": head if head_rc == 0 else None,
            "head_error": head_err if head_rc != 0 else None,
            "status": status if status_rc == 0 else None,
            "status_error": status_err if status_rc != 0 else None,
            "working_tree_clean": status_rc == 0 and not any(
                line and not line.startswith("##") for line in status.splitlines()
            ),
            "origin": remote if remote_rc == 0 else None,
        },
        "source_tree_sha256": source["source_tree_sha256"],
        "source_file_count": source["file_count"],
        "protocol_sha256": protocol_hash_v1(),
        "packages": packages,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-development-python", action="store_true")
    args = parser.parse_args()
    try:
        if not args.allow_development_python and (sys.version_info.major, sys.version_info.minor) != (3, 11):
            raise RuntimeError("publication environment capture requires Python 3.11")
        record = capture_environment_v1(args.root)
        output = write_json_exclusive_v1(args.output, record)
        result = {
            "ok": True,
            "output": str(output.resolve()),
            "python_version": record["python"]["version"],
            "git_head": record["git"]["head"],
            "working_tree_clean": record["git"]["working_tree_clean"],
            "source_tree_sha256": record["source_tree_sha256"],
            "protocol_sha256": record["protocol_sha256"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"[publication-environment] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
