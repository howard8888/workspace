#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frozen protocol and seed-manifest utilities for the publication benchmark.

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
This module is the machine-readable authority for the experimental protocol.
It defines the publication profiles, Conditions A/B/C, Python-version rule,
observation masking, route-change process, memory-encoding opportunities,
current-state reacquisition process, challenge deadline, trial-cycle limit,
and the requirement for one fresh process per trial. It also records the
primary hypotheses fixed before the final evaluation.

For each matched index, the module derives a unique seed from a master nonce
and creates a condition-blind stochastic schedule. The same schedule is later
used under A, B, and C so that differences among methods are not caused by
unequal random events. Named random streams separately generate route change,
memory completeness, and reacquisition onset. Canonical JSON serialization and
SHA-256 hashes make schedules and manifests independently checkable.

The module can build either a small development manifest or the reserved final
``holdout`` manifest used by the publication workflow. Final manifests must
contain exactly 100 matched schedules and must be generated under Python 3.11.
Validation reconstructs every schedule from its saved seed, checks ordering and
uniqueness, verifies profiles and conditions, and confirms the manifest hash.
Exclusive file creation prevents accidental overwriting of an existing
manifest.

This module does not execute CCA8 trials and does not calculate outcomes. Its
responsibility ends after defining, generating, loading, and validating the
protocol and matched schedules consumed by the batch runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import secrets
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

PROTOCOL_VERSION = "cca8_superintelligence_publication_v1"
PROFILES = ("baseline", "conflicted_repair")
CONDITIONS = ("A", "B", "C")


#pylint:disable=missing-function-docstring
@dataclass(frozen=True, slots=True)
class FrozenProtocol:
    '''class docstring todo'''
    python_major: int = 3
    python_minor: int = 11
    ordinary_observation_mask_probability: float = 0.50
    route_change_probability: float = 0.50
    memory_encoding_opportunities: int = 4
    memory_unavailable_probability_per_opportunity: float = 0.50
    current_reacquisition_onset_probability_per_cycle: float = 0.25
    current_reacquisition_first_challenge_cycle: int = 2
    reacquisition_onset_draw_count: int = 6
    challenge_deadline_cycles: int = 7
    episode_max_cycles: int = 60
    matched_seed_count: int = 100
    total_publication_episodes: int = 600
    direct_retrieved_hint_enabled: bool = False
    llm_or_external_api_enabled: bool = False
    fresh_process_per_episode: bool = True

    @property
    def memory_available_probability_per_opportunity(self) -> float:
        return 1.0 - self.memory_unavailable_probability_per_opportunity


FROZEN_PROTOCOL = FrozenProtocol()

PRIMARY_HYPOTHESES = (
    "Condition A will outperform B when decision-critical current state remains missing.",
    "Condition A will outperform C when retrieved state conflicts with newer current evidence.",
    "Condition B will sometimes succeed when current evidence returns before the deadline.",
    "Condition C will sometimes succeed when stored state remains current rather than stale.",
    "Condition A may occasionally fail when the necessary information was neither encoded nor reacquired.",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    """Return SHA-256 for bytes or a canonically serialized JSON value."""
    payload = value if isinstance(value, (bytes, bytearray)) else _canonical_bytes(value)
    return hashlib.sha256(bytes(payload)).hexdigest()


def protocol_metadata_v1() -> dict[str, Any]:
    frozen = asdict(FROZEN_PROTOCOL)
    frozen["memory_available_probability_per_opportunity"] = (
        FROZEN_PROTOCOL.memory_available_probability_per_opportunity
    )
    return {
        "schema": "cca8_publication_protocol_metadata_v1",
        "protocol_version": PROTOCOL_VERSION,
        "frozen_protocol": frozen,
        "conditions": {
            "A": "Guarded Merge fills genuinely missing WorkingMap fields while preserving populated current state.",
            "B": "Target episodic readback is disabled.",
            "C": "Replacement-style readback reconstructs WorkingMap from retrieved episodic state.",
        },
        "primary_hypotheses": list(PRIMARY_HYPOTHESES),
        "stochastic_semantics": {
            "route_change": "One condition-blind Bernoulli draw after episodic encoding.",
            "memory_completeness": "Four condition-blind encoding draws; memory is usable when at least one opportunity survives ordinary masking.",
            "current_reacquisition": "Beginning on challenge cycle 2, six condition-blind Bernoulli onset draws are modeled. The first positive draw starts external availability; the observed cue remains subject to ordinary masking.",
            "observation_mask": "Ordinary masking is derived from the matched episode seed and cognitive step, independently of memory condition.",
        },
    }


def _named_rng(seed: int, episode_index: int, stream: str, *, index: int = 0) -> Random:
    payload = (
        f"cca8_conflicted_repair_stochastic_v3|{int(seed)}|{int(episode_index)}|"
        f"{stream}|{int(index)}"
    ).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return Random(int.from_bytes(digest, byteorder="big", signed=False))


def schedule_from_seed_v1(seed: int, episode_index: int) -> dict[str, Any]:
    """Reproduce the condition-blind stochastic schedule used by the CCA8 core."""
    conflict_draw = float(_named_rng(seed, episode_index, "route_conflict").random())
    route_changed = conflict_draw < FROZEN_PROTOCOL.route_change_probability

    encoding_rng = _named_rng(seed, episode_index, "critical_encoding")
    encoding_draws = [
        float(encoding_rng.random())
        for _ in range(FROZEN_PROTOCOL.memory_encoding_opportunities)
    ]
    encoding_available = [
        draw >= FROZEN_PROTOCOL.memory_unavailable_probability_per_opportunity
        for draw in encoding_draws
    ]
    memory_usable = any(encoding_available)

    reacq_rng = _named_rng(seed, episode_index, "current_reacquisition")
    reacquisition_draws = [
        float(reacq_rng.random())
        for _ in range(FROZEN_PROTOCOL.reacquisition_onset_draw_count)
    ]
    reacquisition_onset_draws = [
        draw < FROZEN_PROTOCOL.current_reacquisition_onset_probability_per_cycle
        for draw in reacquisition_draws
    ]
    first_index = next(
        (idx for idx, value in enumerate(reacquisition_onset_draws) if value),
        None,
    )
    onset_cycle = (
        FROZEN_PROTOCOL.current_reacquisition_first_challenge_cycle + first_index
        if first_index is not None
        else None
    )
    core: dict[str, Any] = {
        "schema": "cca8_publication_episode_schedule_v1",
        "protocol_version": PROTOCOL_VERSION,
        "episode_index": int(episode_index),
        "episode_seed": int(seed),
        "route_change_draw": conflict_draw,
        "route_changed": bool(route_changed),
        "encoding_draws": encoding_draws,
        "encoding_available": encoding_available,
        "memory_usable": bool(memory_usable),
        "reacquisition_draws": reacquisition_draws,
        "reacquisition_onset_draws": reacquisition_onset_draws,
        # Compatibility alias used by focused tests and archived documentation.
        "reacquisition_planned": reacquisition_onset_draws,
        "reacquisition_first_onset_challenge_cycle": onset_cycle,
        "reacquisition_ever_planned": onset_cycle is not None,
    }
    core["schedule_hash"] = sha256_hex(core)
    return core


def _seed_from_nonce(master_nonce: str, episode_index: int, salt: int = 0) -> int:
    raw = hashlib.sha256(
        f"{PROTOCOL_VERSION}|{master_nonce}|{episode_index}|{salt}".encode("utf-8")
    ).digest()
    # Positive 31-bit seeds work consistently across Python's random and CCA8.
    return 1 + (int.from_bytes(raw[:8], "big") % 2_147_483_646)


def schedule_for_episode_v1(master_nonce: str, episode_index: int) -> dict[str, Any]:
    return schedule_from_seed_v1(
        _seed_from_nonce(str(master_nonce), int(episode_index)),
        int(episode_index),
    )


def _manifest_hash_basis(manifest: dict[str, Any]) -> dict[str, Any]:
    basis = dict(manifest)
    basis.pop("manifest_hash", None)
    return basis


def build_manifest_v1(
    *,
    master_nonce: str,
    seed_count: int,
    manifest_kind: str,
    label: str = "",
    created_utc: str | None = None,
) -> dict[str, Any]:
    kind = str(manifest_kind).strip().lower()
    if kind not in {"development", "holdout"}:
        raise ValueError("manifest_kind must be 'development' or 'holdout'")
    count = int(seed_count)
    if count < 1:
        raise ValueError("seed_count must be positive")
    if kind == "holdout" and count != FROZEN_PROTOCOL.matched_seed_count:
        raise ValueError(
            f"holdout manifests require exactly {FROZEN_PROTOCOL.matched_seed_count} matched seeds"
        )
    nonce = str(master_nonce).strip()
    if not nonce:
        raise ValueError("master_nonce must not be empty")

    entries: list[dict[str, Any]] = []
    used_seeds: set[int] = set()
    for episode_index in range(count):
        salt = 0
        seed = _seed_from_nonce(nonce, episode_index, salt)
        while seed in used_seeds:
            salt += 1
            seed = _seed_from_nonce(nonce, episode_index, salt)
        used_seeds.add(seed)
        entries.append(schedule_from_seed_v1(seed, episode_index))

    manifest: dict[str, Any] = {
        "schema": "cca8_publication_seed_manifest_v1",
        "protocol_version": PROTOCOL_VERSION,
        "manifest_kind": kind,
        "label": str(label),
        "created_utc": created_utc or _utc_now(),
        "master_nonce_sha256": sha256_hex(nonce.encode("utf-8")),
        "seed_count": count,
        "profiles": list(PROFILES),
        "conditions": list(CONDITIONS),
        "entries": entries,
        "generator": {
            "module": Path(__file__).name,
            "python_version": platform.python_version(),
        },
    }
    manifest["manifest_hash"] = sha256_hex(_manifest_hash_basis(manifest))
    return manifest


def validate_manifest_v1(
    manifest: dict[str, Any],
    *,
    require_kind: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"ok": False, "errors": ["manifest_not_object"]}
    if manifest.get("schema") != "cca8_publication_seed_manifest_v1":
        errors.append("schema_mismatch")
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("protocol_version_mismatch")
    kind = str(manifest.get("manifest_kind") or "")
    if kind not in {"development", "holdout"}:
        errors.append("manifest_kind_invalid")
    if require_kind and kind != require_kind:
        errors.append("manifest_kind_unexpected")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        errors.append("entries_not_list")
        entries = []
    if int(manifest.get("seed_count", -1)) != len(entries):
        errors.append("seed_count_mismatch")
    if kind == "holdout" and len(entries) != FROZEN_PROTOCOL.matched_seed_count:
        errors.append("holdout_seed_count_mismatch")
    if list(manifest.get("profiles") or []) != list(PROFILES):
        errors.append("profiles_mismatch")
    if list(manifest.get("conditions") or []) != list(CONDITIONS):
        errors.append("conditions_mismatch")

    seen_seeds: set[int] = set()
    for expected_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry_not_object:{expected_index}")
            continue
        try:
            episode_index = int(entry.get("episode_index"))
            seed = int(entry.get("episode_seed"))
        except Exception:
            errors.append(f"entry_identity_invalid:{expected_index}")
            continue
        if episode_index != expected_index:
            errors.append(f"entry_index_mismatch:{expected_index}")
        if seed in seen_seeds:
            errors.append(f"duplicate_seed:{seed}")
        seen_seeds.add(seed)
        expected = schedule_from_seed_v1(seed, episode_index)
        if entry != expected:
            errors.append(f"schedule_mismatch:{expected_index}")

    expected_hash = sha256_hex(_manifest_hash_basis(manifest))
    if str(manifest.get("manifest_hash") or "") != expected_hash:
        errors.append("manifest_hash_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "manifest_kind": kind,
        "seed_count": len(entries),
        "manifest_hash": expected_hash,
    }


def load_manifest_v1(path: str | Path, *, require_kind: str | None = None) -> dict[str, Any]:
    target = Path(path)
    with target.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    result = validate_manifest_v1(manifest, require_kind=require_kind)
    if not result["ok"]:
        raise ValueError("invalid manifest: " + ", ".join(result["errors"]))
    return manifest


def write_manifest_exclusive_v1(path: str | Path, manifest: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return target


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("protocol", help="print the frozen protocol")

    generate = sub.add_parser("generate", help="generate a development or holdout manifest")
    generate.add_argument("--kind", choices=("development", "holdout"), required=True)
    generate.add_argument("--count", type=int, required=True)
    generate.add_argument("--label", default="")
    generate.add_argument("--nonce", default=None)
    generate.add_argument("--output", required=True)

    validate = sub.add_parser("validate", help="validate an existing manifest")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--kind", choices=("development", "holdout"), default=None)

    args = parser.parse_args()
    try:
        if args.command == "protocol":
            result = protocol_metadata_v1()
        elif args.command == "generate":
            if args.kind == "holdout" and (sys.version_info.major, sys.version_info.minor) != (3, 11):
                raise RuntimeError("the final holdout manifest must be generated under Python 3.11")
            nonce = args.nonce or secrets.token_hex(32)
            manifest = build_manifest_v1(
                master_nonce=nonce,
                seed_count=args.count,
                manifest_kind=args.kind,
                label=args.label,
            )
            output = write_manifest_exclusive_v1(args.output, manifest)
            result = {
                "ok": True,
                "output": str(output.resolve()),
                "manifest_kind": manifest["manifest_kind"],
                "seed_count": manifest["seed_count"],
                "manifest_hash": manifest["manifest_hash"],
                "master_nonce": nonce,
                "warning": "Store the nonce and manifest securely; the file will not be overwritten.",
            }
        else:
            manifest = load_manifest_v1(args.manifest, require_kind=args.kind)
            result = validate_manifest_v1(manifest, require_kind=args.kind)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok", True) else 2
    except Exception as exc:
        print(f"[publication-protocol] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
