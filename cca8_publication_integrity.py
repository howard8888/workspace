#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source and output integrity helpers for the CCA8 publication workflow.

Create and verify source manifests and publication-output checksums.

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
This module provides the cross-cutting integrity layer used before, during,
and after publication execution. It computes SHA-256 hashes for individual
files, creates a deterministic manifest of the publication source tree, derives
a hash of the frozen protocol metadata, and writes or verifies checksum files
for result and analysis directories.

Source-tree manifests include each publication-relevant file's relative path,
size, and SHA-256 digest, plus one hash over the ordered manifest entries. The
exclusion policy omits Git metadata, virtual environments, caches, compiled or
temporary files, generated publication output directories, and existing
checksum/manifest files. Verification reports missing, unexpected, or changed
files and confirms the overall tree hash.

Output-tree checksums cover every non-cache file beneath a completed result or
analysis directory. Verification detects missing, added, malformed, or changed
files. JSON and manifest writers use exclusive creation by default so that a
previous artifact cannot be silently overwritten during the frozen workflow.

The command-line interface can create or verify a source manifest and create
or verify output checksums. These operations establish byte-level provenance
and detect change; they do not by themselves establish that an experiment is
scientifically valid. Scientific design validation remains the responsibility
of the protocol, batch runner, worker, and analysis modules.
"""

#pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
import hashlib
import json
#import os  #unused-import
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any    #unused-import -- Iterable

from cca8_publication_protocol import protocol_metadata_v1, sha256_hex

__version__ = "1.0.0"
SOURCE_MANIFEST_SCHEMA = "cca8_publication_source_manifest_v1"
CHECKSUM_FILENAME = "CHECKSUMS.sha256"
SOURCE_MANIFEST_FILENAME = "publication_source_manifest.json"

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    "publication_results",
    "publication_analysis",
    "lhsi_sensitivity",
}
EXCLUDED_FILE_NAMES = {
    SOURCE_MANIFEST_FILENAME,
    "SOURCE_CHECKSUMS.sha256",
    CHECKSUM_FILENAME,
    ".coverage",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak", ".swp"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file_v1(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_exclusive_v1(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return target


def _is_excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1]):
        return True
    if relative.name in EXCLUDED_FILE_NAMES:
        return True
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if relative.name.startswith("~$"):
        return True
    return False


def source_files_v1(root: str | Path) -> list[Path]:
    base = Path(root).resolve()
    files: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if _is_excluded(relative):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(base).as_posix())


def source_tree_manifest_v1(root: str | Path) -> dict[str, Any]:
    base = Path(root).resolve()
    entries = []
    for path in source_files_v1(base):
        relative = path.relative_to(base).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file_v1(path),
            }
        )
    tree_basis = [{"path": row["path"], "size": row["size"], "sha256": row["sha256"]} for row in entries]
    return {
        "schema": SOURCE_MANIFEST_SCHEMA,
        "manifest_version": __version__,
        "created_utc": _utc_now(),
        "root_name": base.name,
        "file_count": len(entries),
        "files": entries,
        "source_tree_sha256": sha256_hex(tree_basis),
        "exclusion_policy": {
            "directory_names": sorted(EXCLUDED_DIRECTORY_NAMES),
            "file_names": sorted(EXCLUDED_FILE_NAMES),
            "suffixes": sorted(EXCLUDED_SUFFIXES),
        },
    }


def _manifest_comparable(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_count": manifest.get("file_count"),
        "files": manifest.get("files"),
        "source_tree_sha256": manifest.get("source_tree_sha256"),
    }


def verify_source_manifest_v1(root: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    with Path(manifest_path).open("r", encoding="utf-8") as handle:
        expected = json.load(handle)
    current = source_tree_manifest_v1(root)
    errors: list[str] = []
    expected_by_path = {
        str(row.get("path")): row for row in expected.get("files", []) if isinstance(row, dict)
    }
    current_by_path = {
        str(row.get("path")): row for row in current.get("files", []) if isinstance(row, dict)
    }
    for path in sorted(set(expected_by_path) - set(current_by_path)):
        errors.append(f"missing:{path}")
    for path in sorted(set(current_by_path) - set(expected_by_path)):
        errors.append(f"unexpected:{path}")
    for path in sorted(set(expected_by_path) & set(current_by_path)):
        e = expected_by_path[path]
        c = current_by_path[path]
        if e.get("size") != c.get("size") or e.get("sha256") != c.get("sha256"):
            errors.append(f"changed:{path}")
    if expected.get("source_tree_sha256") != current.get("source_tree_sha256"):
        errors.append("source_tree_sha256_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "expected_source_tree_sha256": expected.get("source_tree_sha256"),
        "current_source_tree_sha256": current.get("source_tree_sha256"),
        "expected_file_count": expected.get("file_count"),
        "current_file_count": current.get("file_count"),
    }


def protocol_hash_v1() -> str:
    return sha256_hex(protocol_metadata_v1())


def checksum_rows_v1(root: str | Path, *, checksum_name: str = CHECKSUM_FILENAME) -> list[tuple[str, str]]:
    base = Path(root).resolve()
    rows: list[tuple[str, str]] = []
    for path in sorted(base.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if relative.name == checksum_name:
            continue
        if any(part in {"__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        rows.append((sha256_file_v1(path), relative.as_posix()))
    return rows


def write_checksum_text_v1(
    root: str | Path,
    *,
    output_name: str = CHECKSUM_FILENAME,
    overwrite: bool = False,
) -> Path:
    base = Path(root).resolve()
    target = base / output_name
    rows = checksum_rows_v1(base, checksum_name=output_name)
    mode = "w" if overwrite else "x"
    with target.open(mode, encoding="utf-8", newline="\n") as handle:
        for digest, relative in rows:
            handle.write(f"{digest}  {relative}\n")
    return target


def verify_checksums_v1(root: str | Path, *, checksum_name: str = CHECKSUM_FILENAME) -> dict[str, Any]:
    base = Path(root).resolve()
    target = base / checksum_name
    if not target.exists():
        return {"ok": False, "errors": ["checksum_file_missing"]}
    errors: list[str] = []
    expected: dict[str, str] = {}
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"malformed_checksum_line:{line_number}")
            continue
        expected[relative] = digest
    current = {relative: digest for digest, relative in checksum_rows_v1(base, checksum_name=checksum_name)}
    for relative in sorted(set(expected) - set(current)):
        errors.append(f"missing:{relative}")
    for relative in sorted(set(current) - set(expected)):
        errors.append(f"unexpected:{relative}")
    for relative in sorted(set(expected) & set(current)):
        if expected[relative] != current[relative]:
            errors.append(f"changed:{relative}")
    return {
        "ok": not errors,
        "errors": errors,
        "file_count": len(expected),
        "checksum_path": str(target),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a frozen source manifest")
    create.add_argument("--root", default=".")
    create.add_argument("--output", default=SOURCE_MANIFEST_FILENAME)

    verify = sub.add_parser("verify", help="verify a frozen source manifest")
    verify.add_argument("--root", default=".")
    verify.add_argument("--manifest", default=SOURCE_MANIFEST_FILENAME)

    checksums = sub.add_parser("checksums", help="write checksums for an output tree")
    checksums.add_argument("--root", required=True)
    checksums.add_argument("--output-name", default=CHECKSUM_FILENAME)

    verify_checksums = sub.add_parser("verify-checksums", help="verify output-tree checksums")
    verify_checksums.add_argument("--root", required=True)
    verify_checksums.add_argument("--checksum-name", default=CHECKSUM_FILENAME)

    args = parser.parse_args()
    try:
        if args.command == "create":
            manifest = source_tree_manifest_v1(args.root)
            output = Path(args.output)
            if not output.is_absolute():
                output = Path(args.root) / output
            write_json_exclusive_v1(output, manifest)
            result = {"ok": True, "output": str(output.resolve()), **_manifest_comparable(manifest)}
        elif args.command == "verify":
            result = verify_source_manifest_v1(args.root, args.manifest)
        elif args.command == "checksums":
            output = write_checksum_text_v1(args.root, output_name=args.output_name)
            result = {"ok": True, "output": str(output.resolve())}
        else:
            result = verify_checksums_v1(args.root, checksum_name=args.checksum_name)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 2
    except Exception as exc:
        print(f"[publication-integrity] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
