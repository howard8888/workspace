#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publication analysis for the CCA8 stochastic conflicted state-repair benchmark.

The analysis is deliberately separate from the agent runtime.  It consumes the
saved episode-level JSONL file, verifies the matched design, and writes
machine-readable tables for aggregate outcomes, paired comparisons, and
mechanism-specific strata.

Statistical conventions
-----------------------
* Success proportions receive Wilson 95% confidence intervals.
* Paired success comparisons use the exact two-sided McNemar/binomial test.
* Paired effect confidence intervals use a deterministic matched-seed bootstrap.
* Non-binary paired outcomes use a deterministic paired sign-randomization test
  (exact when <=20 non-zero pairs, otherwise Monte Carlo).
* LHSI remains a secondary outcome and is never substituted for component data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from cca8_publication_integrity import write_checksum_text_v1, write_json_exclusive_v1
from cca8_publication_protocol import CONDITIONS, FROZEN_PROTOCOL, PROFILES, PROTOCOL_VERSION

__version__ = "1.0.0"
ANALYSIS_SCHEMA = "cca8_publication_analysis_v1"
DEFAULT_BOOTSTRAP_REPLICATES = 20_000
DEFAULT_RANDOMIZATION_REPLICATES = 100_000
DEFAULT_ANALYSIS_SEED = "cca8-publication-analysis-v1"


METRICS: tuple[dict[str, Any], ...] = (
    {
        "name": "success",
        "field": "success",
        "label": "Success proportion",
        "binary": True,
        "direction": "higher_is_better",
    },
    {
        "name": "milestone_score",
        "field": "milestone_score",
        "label": "Ordered milestone score",
        "binary": False,
        "direction": "higher_is_better",
    },
    {
        "name": "completion_time_or_max",
        "field": "time_to_rested_or_max_cycles",
        "label": "Completion time or 60-cycle maximum",
        "binary": False,
        "direction": "lower_is_better",
    },
    {
        "name": "lhsi",
        "field": "lhsi_state_integrity_score",
        "label": "LHSI (secondary)",
        "binary": False,
        "direction": "higher_is_better",
    },
    {
        "name": "guarded_repairs",
        "field": "publication_guarded_repair_count_pre_completion",
        "label": "Guarded structural repairs before completion",
        "binary": False,
        "direction": "mechanism",
    },
    {
        "name": "guarded_field_consultations",
        "field": "publication_guarded_field_use_count_pre_completion",
        "label": "Guarded-field consultations before completion",
        "binary": False,
        "direction": "mechanism",
    },
    {
        "name": "replacement_events",
        "field": "publication_replacement_count_pre_completion",
        "label": "Replacement events before completion",
        "binary": False,
        "direction": "mechanism",
    },
    {
        "name": "unsafe_follow_events",
        "field": "publication_unsafe_follow_count_pre_completion",
        "label": "Unsafe-follow events before completion",
        "binary": False,
        "direction": "lower_is_better",
    },
    {
        "name": "missing_state_timeouts",
        "field": "publication_missing_state_timeout_count_pre_completion",
        "label": "Missing-state timeouts before completion",
        "binary": False,
        "direction": "lower_is_better",
    },
)


AGGREGATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("milestone_score", "milestone_score"),
    ("completion_time_or_max", "time_to_rested_or_max_cycles"),
    ("lhsi", "lhsi_state_integrity_score"),
    ("guarded_repairs", "publication_guarded_repair_count_pre_completion"),
    ("guarded_field_consultations", "publication_guarded_field_use_count_pre_completion"),
    ("replacement_events", "publication_replacement_count_pre_completion"),
    ("unsafe_follow_events", "publication_unsafe_follow_count_pre_completion"),
    ("missing_state_timeouts", "publication_missing_state_timeout_count_pre_completion"),
    ("probe_events", "publication_probe_count_pre_completion"),
    ("invalidation_events", "publication_invalidation_count_pre_completion"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_episode_jsonl_v1(path: str | Path) -> list[dict[str, Any]]:
    """Load episode-level JSONL records with line-specific validation."""
    target = Path(path)
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"non-object JSONL record at {target}:{line_number}")
            rows.append(value)
    if not rows:
        raise ValueError(f"no episode records in {target}")
    return rows


def _number(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else math.nan


def _sample_sd(values: Sequence[float]) -> float:
    return float(statistics.stdev(values)) if len(values) >= 2 else 0.0


def _quantile_sorted(values: Sequence[float], probability: float) -> float:
    if not values:
        return math.nan
    p = max(0.0, min(1.0, float(probability)))
    if len(values) == 1:
        return float(values[0])
    location = (len(values) - 1) * p
    lower = int(math.floor(location))
    upper = int(math.ceil(location))
    if lower == upper:
        return float(values[lower])
    weight = location - lower
    return float(values[lower] * (1.0 - weight) + values[upper] * weight)


def wilson_interval_v1(successes: int, total: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    """Return the Wilson score interval for a binomial proportion."""
    n = int(total)
    if n <= 0:
        return (math.nan, math.nan)
    x = max(0, min(n, int(successes)))
    p = x / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denominator
    half = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denominator
    return (max(0.0, center - half), min(1.0, center + half))


def exact_paired_binary_p_v1(a_success_b_fail: int, a_fail_b_success: int) -> float:
    """Exact two-sided McNemar probability via Binomial(n, 0.5)."""
    b = max(0, int(a_success_b_fail))
    c = max(0, int(a_fail_b_success))
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail_numerator = sum(math.comb(n, i) for i in range(k + 1))
    probability = 2.0 * tail_numerator / float(2**n)
    return min(1.0, probability)


def _stable_seed(*parts: Any) -> int:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def paired_bootstrap_interval_v1(
    differences: Sequence[float],
    *,
    replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    seed_material: str = DEFAULT_ANALYSIS_SEED,
) -> tuple[float, float]:
    """Deterministic percentile CI for a matched-pair mean difference."""
    values = [float(value) for value in differences]
    n = len(values)
    if n == 0:
        return (math.nan, math.nan)
    if n == 1 or all(value == values[0] for value in values):
        return (values[0], values[0])
    reps = max(1_000, int(replicates))
    rng = random.Random(_stable_seed(seed_material, n, reps, values))
    samples: list[float] = []
    append = samples.append
    for _ in range(reps):
        append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    samples.sort()
    return (_quantile_sorted(samples, 0.025), _quantile_sorted(samples, 0.975))


def paired_sign_randomization_p_v1(
    differences: Sequence[float],
    *,
    replicates: int = DEFAULT_RANDOMIZATION_REPLICATES,
    seed_material: str = DEFAULT_ANALYSIS_SEED,
) -> tuple[float, str, int]:
    """Two-sided paired sign-randomization test around a zero mean difference.

    The test is exact when at most 20 non-zero pair differences remain.  Larger
    samples use a deterministic Monte Carlo approximation with a plus-one
    correction.
    """
    values = [float(value) for value in differences if abs(float(value)) > 1e-15]
    m = len(values)
    if m == 0:
        return (1.0, "all_pair_differences_zero", 0)
    observed = abs(sum(values))
    magnitudes = [abs(value) for value in values]
    tolerance = 1e-12
    if m <= 20:
        extreme = 0
        total = 1 << m
        for mask in range(total):
            signed_sum = 0.0
            for index, magnitude in enumerate(magnitudes):
                signed_sum += magnitude if (mask >> index) & 1 else -magnitude
            if abs(signed_sum) + tolerance >= observed:
                extreme += 1
        return (extreme / total, "exact_paired_sign_randomization", total)

    reps = max(10_000, int(replicates))
    rng = random.Random(_stable_seed(seed_material, m, reps, magnitudes))
    extreme = 0
    for _ in range(reps):
        signed_sum = sum(magnitude if rng.getrandbits(1) else -magnitude for magnitude in magnitudes)
        if abs(signed_sum) + tolerance >= observed:
            extreme += 1
    return ((extreme + 1) / (reps + 1), "monte_carlo_paired_sign_randomization", reps)


def validate_episode_design_v1(
    rows: Sequence[dict[str, Any]],
    *,
    require_frozen_holdout: bool = False,
) -> dict[str, Any]:
    """Validate scientific fields, matched schedules, isolation, and optional 600-run design."""
    errors: list[str] = []
    seen: set[tuple[str, str, int]] = set()
    schedules: dict[tuple[str, int], dict[str, tuple[Any, ...]]] = defaultdict(dict)
    schedules_across_profiles: dict[int, set[tuple[Any, ...]]] = defaultdict(set)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    process_nonces: set[str] = set()
    manifest_hashes: set[str] = set()
    source_hashes: set[str] = set()
    protocol_hashes: set[str] = set()

    required_numeric_fields = (
        "milestone_score",
        "time_to_rested_or_max_cycles",
        "lhsi_state_integrity_score",
        "lhsi_wrong_stage_action_count",
        "lhsi_current_state_overwrite_proxy_count",
        "lhsi_stale_memory_intrusion_proxy_count",
        "lhsi_repeated_action_loop_count",
        "publication_retrieval_count_pre_completion",
        "publication_guarded_repair_count_pre_completion",
        "publication_guarded_field_use_count_pre_completion",
        "publication_replacement_count_pre_completion",
        "publication_unsafe_follow_count_pre_completion",
        "publication_missing_state_timeout_count_pre_completion",
        "publication_probe_count_pre_completion",
        "publication_invalidation_count_pre_completion",
        "publication_resolution_count_pre_completion",
        "publication_direct_hint_use_count",
        "llm_call_count",
    )
    nonnegative_count_fields = {
        field
        for field in required_numeric_fields
        if field.startswith("publication_") or field == "llm_call_count"
    }

    def valid_number(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"record_not_object:row_{row_number}")
            continue
        profile = str(row.get("publication_profile") or "").lower()
        condition = str(row.get("condition") or "").upper()
        try:
            episode_index = int(row.get("episode_index"))
            episode_seed = int(row.get("seed" if "seed" in row else "episode_seed"))
        except (TypeError, ValueError):
            errors.append(f"invalid_episode_identity:row_{row_number}")
            continue
        key = (profile, condition, episode_index)

        if row.get("schema") != "experiment_episode_record_v1":
            errors.append(f"episode_schema_mismatch:{key}")
        if row.get("publication_protocol_version") != PROTOCOL_VERSION:
            errors.append(f"protocol_version_mismatch:{key}")
        if profile not in PROFILES:
            errors.append(f"invalid_profile:{key}")
        if condition not in CONDITIONS:
            errors.append(f"invalid_condition:{key}")
        if episode_index < 0 or episode_seed <= 0:
            errors.append(f"invalid_episode_identity:{key}")
        if key in seen:
            errors.append(f"duplicate_episode:{key}")
        seen.add(key)
        counts[(profile, condition)] += 1

        if not isinstance(row.get("success"), bool):
            errors.append(f"success_not_boolean:{key}")
        milestone = row.get("milestone_score")
        if valid_number(milestone) and not 0.0 <= float(milestone) <= 1.0:
            errors.append(f"milestone_score_out_of_range:{key}")
        lhsi = row.get("lhsi_state_integrity_score")
        if valid_number(lhsi) and not 0.0 <= float(lhsi) <= 1.0:
            errors.append(f"lhsi_out_of_range:{key}")

        for field in required_numeric_fields:
            if field not in row or not valid_number(row.get(field)):
                errors.append(f"missing_or_nonfinite_field:{key}:{field}")
                continue
            if field in nonnegative_count_fields and float(row[field]) < 0.0:
                errors.append(f"negative_count:{key}:{field}")

        provenance = row.get("lhsi_provenance_complete_cycle_rate")
        if provenance is not None:
            if not valid_number(provenance) or not 0.0 <= float(provenance) <= 1.0:
                errors.append(f"provenance_rate_invalid:{key}")

        schedule_hash = str(row.get("publication_schedule_hash") or "")
        if len(schedule_hash) != 64 or any(ch not in "0123456789abcdef" for ch in schedule_hash.lower()):
            errors.append(f"missing_or_invalid_schedule_hash:{key}")
        route_changed = row.get("publication_route_changed")
        memory_usable = row.get("publication_memory_usable")
        onset_draws = row.get("publication_reacquisition_onset_draws")
        if not isinstance(route_changed, bool):
            errors.append(f"route_changed_not_boolean:{key}")
        if not isinstance(memory_usable, bool):
            errors.append(f"memory_usable_not_boolean:{key}")
        if not (
            isinstance(onset_draws, list)
            and len(onset_draws) == FROZEN_PROTOCOL.reacquisition_onset_draw_count
            and all(isinstance(draw, bool) for draw in onset_draws)
        ):
            errors.append(f"reacquisition_draws_invalid:{key}")
            onset_signature: tuple[bool, ...] = ()
        else:
            onset_signature = tuple(onset_draws)

        schedule_signature = (
            schedule_hash,
            episode_seed,
            route_changed,
            memory_usable,
            onset_signature,
        )
        schedules[(profile, episode_index)][condition] = schedule_signature
        schedules_across_profiles[episode_index].add(schedule_signature)

        if int(_number(row.get("publication_direct_hint_use_count"))) != 0:
            errors.append(f"direct_hint_use:{key}")
        if int(_number(row.get("llm_call_count"))) != 0:
            errors.append(f"llm_or_api_call:{key}")
        if condition == "B" and int(_number(row.get("publication_retrieval_count_pre_completion"))) != 0:
            errors.append(f"condition_b_target_retrieval_detected:{key}")

        worker = row.get("publication_worker")
        if not isinstance(worker, dict):
            errors.append(f"publication_worker_metadata_missing:{key}")
        else:
            process_nonce = str(worker.get("process_nonce") or "")
            if not process_nonce:
                errors.append(f"worker_process_nonce_missing:{key}")
            elif process_nonce in process_nonces:
                errors.append(f"worker_process_nonce_duplicate:{key}")
            else:
                process_nonces.add(process_nonce)
            if str(worker.get("schedule_hash") or "") != schedule_hash:
                errors.append(f"worker_schedule_hash_mismatch:{key}")
            manifest_hash = str(worker.get("manifest_sha256") or "")
            source_hash = str(worker.get("source_tree_sha256") or "")
            protocol_hash = str(worker.get("protocol_sha256") or "")
            for label, value, target in (
                ("manifest", manifest_hash, manifest_hashes),
                ("source", source_hash, source_hashes),
                ("protocol", protocol_hash, protocol_hashes),
            ):
                if len(value) != 64:
                    errors.append(f"worker_{label}_hash_invalid:{key}")
                else:
                    target.add(value)
            if require_frozen_holdout:
                if str(worker.get("manifest_kind") or "") != "holdout":
                    errors.append(f"worker_manifest_kind_not_holdout:{key}")
                if not str(worker.get("python_version") or "").startswith("3.11."):
                    errors.append(f"worker_python_not_3_11:{key}")

    matched_sets = 0
    for schedule_key, by_condition in schedules.items():
        if set(by_condition) == set(CONDITIONS):
            matched_sets += 1
            signatures = set(by_condition.values())
            if len(signatures) != 1:
                errors.append(f"matched_schedule_or_seed_mismatch:{schedule_key}")

    for episode_index, signatures in schedules_across_profiles.items():
        if len(signatures) != 1:
            errors.append(f"cross_profile_schedule_mismatch:{episode_index}")

    if len(manifest_hashes) > 1:
        errors.append("multiple_manifest_hashes_in_batch")
    if len(source_hashes) > 1:
        errors.append("multiple_source_hashes_in_batch")
    if len(protocol_hashes) > 1:
        errors.append("multiple_protocol_hashes_in_batch")

    if require_frozen_holdout:
        expected_rows = FROZEN_PROTOCOL.total_publication_episodes
        if len(rows) != expected_rows:
            errors.append(f"holdout_episode_count_not_{expected_rows}")
        for profile in PROFILES:
            for condition in CONDITIONS:
                actual = counts.get((profile, condition), 0)
                if actual != FROZEN_PROTOCOL.matched_seed_count:
                    errors.append(f"holdout_cell_count:{profile}:{condition}:{actual}")
        expected_sets = len(PROFILES) * FROZEN_PROTOCOL.matched_seed_count
        if matched_sets != expected_sets:
            errors.append(f"holdout_matched_set_count:{matched_sets}")
        if len(process_nonces) != expected_rows:
            errors.append(f"holdout_unique_process_nonce_count:{len(process_nonces)}")

    return {
        "ok": not errors,
        "errors": errors,
        "episode_count": len(rows),
        "cell_counts": {
            f"{profile}:{condition}": counts.get((profile, condition), 0)
            for profile in PROFILES
            for condition in CONDITIONS
        },
        "matched_condition_sets": matched_sets,
        "unique_process_nonce_count": len(process_nonces),
        "manifest_hashes": sorted(manifest_hashes),
        "source_tree_hashes": sorted(source_hashes),
        "protocol_hashes": sorted(protocol_hashes),
        "guardrails": {
            "direct_hint_use_zero": not any(error.startswith("direct_hint_use") for error in errors),
            "llm_or_api_calls_zero": not any(error.startswith("llm_or_api_call") for error in errors),
            "condition_b_target_retrieval_zero": not any(
                error.startswith("condition_b_target_retrieval_detected") for error in errors
            ),
            "fresh_process_nonce_unique": len(process_nonces) == len(rows),
        },
    }


def _group_rows(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("publication_profile") or "").lower(), str(row.get("condition") or "").upper())].append(row)
    for values in grouped.values():
        values.sort(key=lambda item: int(item.get("episode_index", -1)))
    return grouped


def aggregate_outcomes_v1(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _group_rows(rows)
    output: list[dict[str, Any]] = []
    for profile in PROFILES:
        for condition in CONDITIONS:
            values = grouped.get((profile, condition), [])
            n = len(values)
            if n == 0:
                continue
            successes = sum(1 for row in values if _bool(row.get("success")))
            ci_low, ci_high = wilson_interval_v1(successes, n)
            record: dict[str, Any] = {
                "profile": profile,
                "condition": condition,
                "n": n,
                "success_count": successes,
                "failure_count": n - successes,
                "success_rate": successes / n if n else math.nan,
                "success_wilson_95_low": ci_low,
                "success_wilson_95_high": ci_high,
                "route_changed_count": sum(1 for row in values if _bool(row.get("publication_route_changed"))),
                "memory_usable_count": sum(1 for row in values if _bool(row.get("publication_memory_usable"))),
                "reacquisition_started_count": sum(
                    1 for row in values if _bool(row.get("publication_reacquisition_started"))
                ),
                "current_reacquired_count": sum(
                    1 for row in values if _bool(row.get("publication_current_reacquired"))
                ),
            }
            for name, field in AGGREGATE_FIELDS:
                metric_values = [_number(row.get(field)) for row in values]
                record[f"mean_{name}"] = _mean(metric_values)
                record[f"sd_{name}"] = _sample_sd(metric_values)
            failure_categories: dict[str, int] = defaultdict(int)
            for row in values:
                reason = str(row.get("publication_failure_reason") or "none")
                failure_categories[reason] += 1
            record["failure_category_counts_json"] = json.dumps(
                dict(sorted(failure_categories.items())), sort_keys=True, separators=(",", ":")
            )
            output.append(record)
    return output


def _paired_maps(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, int], dict[str, dict[str, Any]]]:
    paired: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (str(row.get("publication_profile") or "").lower(), int(row.get("episode_index", -1)))
        paired[key][str(row.get("condition") or "").upper()] = row
    return paired


def _cohen_dz(differences: Sequence[float]) -> float | None:
    if len(differences) < 2:
        return None
    sd = _sample_sd(differences)
    if sd == 0.0:
        return None
    return _mean(differences) / sd


def paired_comparisons_v1(
    rows: Sequence[dict[str, Any]],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    randomization_replicates: int = DEFAULT_RANDOMIZATION_REPLICATES,
    analysis_seed: str = DEFAULT_ANALYSIS_SEED,
) -> list[dict[str, Any]]:
    paired = _paired_maps(rows)
    output: list[dict[str, Any]] = []
    for profile in PROFILES:
        complete = [
            by_condition
            for (row_profile, _), by_condition in sorted(paired.items())
            if row_profile == profile and set(by_condition) == set(CONDITIONS)
        ]
        if not complete:
            continue
        for comparator in ("B", "C"):
            for metric in METRICS:
                a_values = [_number(pair["A"].get(metric["field"])) for pair in complete]
                x_values = [_number(pair[comparator].get(metric["field"])) for pair in complete]
                differences = [a - x for a, x in zip(a_values, x_values)]
                seed_material = f"{analysis_seed}|{profile}|A-{comparator}|{metric['name']}"
                ci_low, ci_high = paired_bootstrap_interval_v1(
                    differences,
                    replicates=bootstrap_replicates,
                    seed_material=seed_material,
                )
                record: dict[str, Any] = {
                    "profile": profile,
                    "comparison": f"A_minus_{comparator}",
                    "reference_condition": "A",
                    "comparator_condition": comparator,
                    "metric": metric["name"],
                    "metric_label": metric["label"],
                    "direction": metric["direction"],
                    "n_pairs": len(differences),
                    "reference_mean": _mean(a_values),
                    "comparator_mean": _mean(x_values),
                    "mean_paired_difference_A_minus_comparator": _mean(differences),
                    "paired_bootstrap_95_low": ci_low,
                    "paired_bootstrap_95_high": ci_high,
                    "paired_difference_sd": _sample_sd(differences),
                    "cohen_dz": _cohen_dz(differences),
                    "test_method": None,
                    "test_p_two_sided": None,
                    "test_draw_count": None,
                    "a_success_comparator_failure": None,
                    "a_failure_comparator_success": None,
                    "concordant_success": None,
                    "concordant_failure": None,
                }
                if metric["binary"]:
                    a_success_x_failure = sum(1 for a, x in zip(a_values, x_values) if a == 1.0 and x == 0.0)
                    a_failure_x_success = sum(1 for a, x in zip(a_values, x_values) if a == 0.0 and x == 1.0)
                    both_success = sum(1 for a, x in zip(a_values, x_values) if a == 1.0 and x == 1.0)
                    both_failure = sum(1 for a, x in zip(a_values, x_values) if a == 0.0 and x == 0.0)
                    record.update(
                        {
                            "test_method": "exact_two_sided_mcnemar_binomial",
                            "test_p_two_sided": exact_paired_binary_p_v1(
                                a_success_x_failure, a_failure_x_success
                            ),
                            "test_draw_count": a_success_x_failure + a_failure_x_success,
                            "a_success_comparator_failure": a_success_x_failure,
                            "a_failure_comparator_success": a_failure_x_success,
                            "concordant_success": both_success,
                            "concordant_failure": both_failure,
                        }
                    )
                else:
                    p_value, method, draws = paired_sign_randomization_p_v1(
                        differences,
                        replicates=randomization_replicates,
                        seed_material=seed_material,
                    )
                    record.update(
                        {
                            "test_method": method,
                            "test_p_two_sided": p_value,
                            "test_draw_count": draws,
                        }
                    )
                output.append(record)
    return output


def _stratum_rows(
    rows: Sequence[dict[str, Any]],
    *,
    stratum_type: str,
    stratum_value: str,
    predicate: Callable[[dict[str, Any]], bool],
) -> list[dict[str, Any]]:
    selected = [row for row in rows if predicate(row)]
    grouped = _group_rows(selected)
    output: list[dict[str, Any]] = []
    for profile in PROFILES:
        for condition in CONDITIONS:
            values = grouped.get((profile, condition), [])
            n = len(values)
            if n == 0:
                continue
            successes = sum(1 for row in values if _bool(row.get("success")))
            output.append(
                {
                    "stratum_type": stratum_type,
                    "stratum_value": stratum_value,
                    "profile": profile,
                    "condition": condition,
                    "n": n,
                    "success_count": successes,
                    "success_rate": successes / n,
                    "mean_milestone_score": _mean([_number(row.get("milestone_score")) for row in values]),
                    "mean_completion_time_or_max": _mean(
                        [_number(row.get("time_to_rested_or_max_cycles"), default=60.0) for row in values]
                    ),
                    "guarded_repair_total": sum(
                        int(_number(row.get("publication_guarded_repair_count_pre_completion"))) for row in values
                    ),
                    "guarded_field_consultation_total": sum(
                        int(_number(row.get("publication_guarded_field_use_count_pre_completion"))) for row in values
                    ),
                    "replacement_total": sum(
                        int(_number(row.get("publication_replacement_count_pre_completion"))) for row in values
                    ),
                    "unsafe_follow_total": sum(
                        int(_number(row.get("publication_unsafe_follow_count_pre_completion"))) for row in values
                    ),
                    "missing_state_timeout_total": sum(
                        int(_number(row.get("publication_missing_state_timeout_count_pre_completion"))) for row in values
                    ),
                }
            )
    return output


def mechanism_strata_v1(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    output.extend(_stratum_rows(rows, stratum_type="overall", stratum_value="all", predicate=lambda _: True))

    binary_fields = (
        ("route_changed", "publication_route_changed"),
        ("memory_usable", "publication_memory_usable"),
        ("reacquisition_started", "publication_reacquisition_started"),
        ("current_reacquired", "publication_current_reacquired"),
    )
    for label, field in binary_fields:
        for value in (False, True):
            output.extend(
                _stratum_rows(
                    rows,
                    stratum_type=label,
                    stratum_value=str(value).lower(),
                    predicate=lambda row, field=field, value=value: _bool(row.get(field)) is value,
                )
            )

    challenge_rows = [row for row in rows if str(row.get("publication_profile") or "") == "conflicted_repair"]
    for route_changed in (False, True):
        for memory_usable in (False, True):
            for reacquisition_started in (False, True):
                label = (
                    f"route_changed={str(route_changed).lower()}|"
                    f"memory_usable={str(memory_usable).lower()}|"
                    f"reacquisition_started={str(reacquisition_started).lower()}"
                )
                output.extend(
                    _stratum_rows(
                        challenge_rows,
                        stratum_type="stochastic_schedule_combination",
                        stratum_value=label,
                        predicate=lambda row, rc=route_changed, mu=memory_usable, ra=reacquisition_started: (
                            _bool(row.get("publication_route_changed")) is rc
                            and _bool(row.get("publication_memory_usable")) is mu
                            and _bool(row.get("publication_reacquisition_started")) is ra
                        ),
                    )
                )

    mechanism_flags = (
        ("guarded_repair_observed", "publication_guarded_repair_count_pre_completion"),
        ("guarded_field_consulted", "publication_guarded_field_use_count_pre_completion"),
        ("replacement_observed", "publication_replacement_count_pre_completion"),
        ("unsafe_follow_observed", "publication_unsafe_follow_count_pre_completion"),
        ("missing_state_timeout_observed", "publication_missing_state_timeout_count_pre_completion"),
    )
    for label, field in mechanism_flags:
        for observed in (False, True):
            output.extend(
                _stratum_rows(
                    rows,
                    stratum_type=label,
                    stratum_value=str(observed).lower(),
                    predicate=lambda row, field=field, observed=observed: (_number(row.get(field)) > 0.0) is observed,
                )
            )
    return output


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_safe(row.get(key)) for key in fieldnames})


def _format_probability(value: Any) -> str:
    number = _number(value, default=math.nan)
    if not math.isfinite(number):
        return "n/a"
    if number < 0.000001:
        return f"{number:.2e}"
    return f"{number:.6f}"


def _markdown_tables(
    aggregate: Sequence[dict[str, Any]],
    paired: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# CCA8 Publication Analysis Tables",
        "",
        "LHSI is a secondary composite. Behavioral and mechanism-specific outcomes should receive priority.",
        "",
        "## Aggregate outcomes",
        "",
        "| Profile | Condition | n | Success | Wilson 95% CI | Milestone | Completion/max | Repairs | Field uses | Replacements | Unsafe follows | Timeouts |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate:
        lines.append(
            "| {profile} | {condition} | {n} | {success_rate:.3f} | [{lo:.3f}, {hi:.3f}] | "
            "{milestone:.3f} | {completion:.2f} | {repairs:.2f} | {uses:.2f} | {replacement:.2f} | "
            "{unsafe:.2f} | {timeouts:.2f} |".format(
                profile=row["profile"],
                condition=row["condition"],
                n=row["n"],
                success_rate=row["success_rate"],
                lo=row["success_wilson_95_low"],
                hi=row["success_wilson_95_high"],
                milestone=row["mean_milestone_score"],
                completion=row["mean_completion_time_or_max"],
                repairs=row["mean_guarded_repairs"],
                uses=row["mean_guarded_field_consultations"],
                replacement=row["mean_replacement_events"],
                unsafe=row["mean_unsafe_follow_events"],
                timeouts=row["mean_missing_state_timeouts"],
            )
        )

    lines.extend(
        [
            "",
            "## Paired effects against Condition A",
            "",
            "Positive values are A minus comparator. For completion time, a negative value favors A.",
            "",
            "| Profile | Comparison | Metric | A mean | Comparator mean | A−X | Bootstrap 95% CI | Test | p |",
            "|---|---|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    for row in paired:
        if row["metric"] not in {"success", "milestone_score", "completion_time_or_max", "lhsi"}:
            continue
        lines.append(
            "| {profile} | {comparison} | {metric} | {a:.4f} | {x:.4f} | {diff:.4f} | "
            "[{lo:.4f}, {hi:.4f}] | {method} | {p} |".format(
                profile=row["profile"],
                comparison=row["comparison"],
                metric=row["metric"],
                a=row["reference_mean"],
                x=row["comparator_mean"],
                diff=row["mean_paired_difference_A_minus_comparator"],
                lo=row["paired_bootstrap_95_low"],
                hi=row["paired_bootstrap_95_high"],
                method=row["test_method"],
                p=_format_probability(row["test_p_two_sided"]),
            )
        )
    lines.extend(
        [
            "",
            "The exact McNemar/binomial test is used for paired success. Other p values use paired sign randomization.",
            "Confidence intervals are deterministic matched-seed percentile bootstrap intervals.",
            "",
        ]
    )
    return "\n".join(lines)


def analyze_batch_v1(
    *,
    batch_dir: str | Path,
    output_dir: str | Path,
    require_frozen_holdout: bool = False,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    randomization_replicates: int = DEFAULT_RANDOMIZATION_REPLICATES,
    analysis_seed: str = DEFAULT_ANALYSIS_SEED,
) -> dict[str, Any]:
    """Run the complete publication analysis and write immutable artifacts."""
    batch = Path(batch_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)

    episodes_path = batch / "episodes.jsonl"
    rows = load_episode_jsonl_v1(episodes_path)
    design = validate_episode_design_v1(rows, require_frozen_holdout=require_frozen_holdout)
    if not design["ok"]:
        write_json_exclusive_v1(output / "ANALYSIS_VALIDATION_FAILED.json", design)
        raise ValueError("episode design validation failed: " + ", ".join(design["errors"]))

    aggregate = aggregate_outcomes_v1(rows)
    paired = paired_comparisons_v1(
        rows,
        bootstrap_replicates=bootstrap_replicates,
        randomization_replicates=randomization_replicates,
        analysis_seed=analysis_seed,
    )
    strata = mechanism_strata_v1(rows)

    _write_csv(output / "aggregate_outcomes.csv", aggregate)
    _write_csv(output / "paired_comparisons.csv", paired)
    _write_csv(output / "mechanism_strata.csv", strata)
    write_json_exclusive_v1(output / "aggregate_outcomes.json", _json_safe(aggregate))
    write_json_exclusive_v1(output / "paired_comparisons.json", _json_safe(paired))
    write_json_exclusive_v1(output / "mechanism_strata.json", _json_safe(strata))
    (output / "publication_tables.md").write_text(
        _markdown_tables(aggregate, paired), encoding="utf-8", newline="\n"
    )

    metadata = {
        "schema": ANALYSIS_SCHEMA,
        "analysis_version": __version__,
        "created_utc": _utc_now(),
        "batch_dir": str(batch),
        "episode_jsonl": str(episodes_path),
        "episode_count": len(rows),
        "require_frozen_holdout": bool(require_frozen_holdout),
        "design_validation": design,
        "statistical_methods": {
            "success_proportion_ci": "Wilson 95% interval",
            "paired_success_test": "exact two-sided McNemar/binomial test",
            "paired_effect_ci": "deterministic matched-seed percentile bootstrap",
            "paired_nonbinary_test": "paired sign randomization, exact <=20 nonzero pairs else deterministic Monte Carlo",
            "bootstrap_replicates": int(bootstrap_replicates),
            "randomization_replicates": int(randomization_replicates),
            "analysis_seed": str(analysis_seed),
            "multiplicity_adjustment": "none; primary contrasts and outcomes are reported explicitly",
        },
        "interpretation_guardrail": (
            "LHSI is secondary. Success, milestones, completion time, structural repair, guarded-field consultation, "
            "replacement, unsafe-follow, and missing-state timeout outcomes receive priority."
        ),
        "outputs": [
            "aggregate_outcomes.csv",
            "paired_comparisons.csv",
            "mechanism_strata.csv",
            "aggregate_outcomes.json",
            "paired_comparisons.json",
            "mechanism_strata.json",
            "publication_tables.md",
        ],
    }
    write_json_exclusive_v1(output / "analysis_metadata.json", metadata)
    checksum_path = write_checksum_text_v1(output)
    return {
        "ok": True,
        "output_dir": str(output),
        "episode_count": len(rows),
        "aggregate_row_count": len(aggregate),
        "paired_row_count": len(paired),
        "stratum_row_count": len(strata),
        "checksums": str(checksum_path),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="completed batch directory")
    parser.add_argument("--output", required=True, help="new analysis output directory")
    parser.add_argument("--require-frozen-holdout", action="store_true")
    parser.add_argument("--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP_REPLICATES)
    parser.add_argument("--randomization-replicates", type=int, default=DEFAULT_RANDOMIZATION_REPLICATES)
    parser.add_argument("--analysis-seed", default=DEFAULT_ANALYSIS_SEED)
    args = parser.parse_args()
    try:
        result = analyze_batch_v1(
            batch_dir=args.batch,
            output_dir=args.output,
            require_frozen_holdout=bool(args.require_frozen_holdout),
            bootstrap_replicates=int(args.bootstrap_replicates),
            randomization_replicates=int(args.randomization_replicates),
            analysis_seed=str(args.analysis_seed),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"[publication-analysis] ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
