"""Fresh-process development validation for the stochastic conflicted-repair benchmark.

The benchmark retains the same three memory-governance conditions but replaces the
balanced four-cell assignment with condition-blind stochastic environmental variation.
For each matched episode, named deterministic random streams decide:

1. whether route safety changes after the episodic state was encoded,
2. whether at least one of four critical-state encoding opportunities survives the
   ordinary 50% observation mask, and
3. on which challenge cycles current mother-distance information becomes externally
   available again.  Each exposed cue still passes through the ordinary observation
   mask before the controller can use it.

The same sampled schedule is presented to Conditions A, B, and C.  Randomness is
therefore environmental, reproducible, and matched rather than condition-specific.
Every publication-style episode runs in a fresh worker process by default.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Iterable


CONDITIONS = ("A", "B", "C")
PROFILE_SPECS: tuple[tuple[str, float], ...] = (
    ("baseline", 0.50),
    ("conflicted_repair", 0.50),
)
CHALLENGE_DEADLINE_CYCLES = 7
CONFLICT_PROBABILITY = 0.50
ENCODING_OPPORTUNITIES = 4
REACQUIRE_PROBABILITY = 0.25
REACQUIRE_START_DELAY = 1


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return statistics.mean(values) if values else None


def _rate(rows: list[dict[str, Any]], predicate) -> float | None:
    if not rows:
        return None
    return sum(bool(predicate(row)) for row in rows) / float(len(rows))


def _exact_paired_binary_p(a_success_b_fail: int, a_fail_b_success: int) -> float:
    """Return the two-sided exact McNemar/binomial probability."""
    n = int(a_success_b_fail) + int(a_fail_b_success)
    if n <= 0:
        return 1.0
    k = min(int(a_success_b_fail), int(a_fail_b_success))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def _configure_ctx(ctx: Any, *, profile: str, mask_prob: float, condition: str,
                   seed: int, output_dir: str, write_cycles: bool) -> None:
    cfg = ctx.experiment_cfg
    cfg.benchmark_id = "newborn_long_horizon"
    cfg.condition_ids = [condition]
    cfg.seed_list = [int(seed)]
    cfg.episodes_per_seed = 1
    cfg.max_cycles = 60
    cfg.obs_mask_prob = float(mask_prob)
    cfg.newborn_stress_profile = str(profile)
    cfg.newborn_blackout_length = CHALLENGE_DEADLINE_CYCLES
    cfg.conflicted_repair_variant_mode = "stochastic_v3"
    cfg.conflicted_repair_conflict_probability = CONFLICT_PROBABILITY
    cfg.conflicted_repair_encoding_opportunities = ENCODING_OPPORTUNITIES
    cfg.conflicted_repair_reacquire_probability = REACQUIRE_PROBABILITY
    cfg.conflicted_repair_reacquire_start_delay = REACQUIRE_START_DELAY
    cfg.run_label = f"stochastic_validation_{profile}_{condition}_{seed}"
    cfg.output_dir = output_dir
    cfg.jsonl_write_cycle_records = bool(write_cycles)
    cfg.jsonl_write_episode_records = bool(write_cycles)


def _run_one_episode(task: tuple[str, float, str, int, int, str]) -> dict[str, Any]:
    """Worker entry point. With maxtasksperchild=1, every task gets a new process."""
    profile, mask_prob, condition, seed, episode_index, scratch_root = task

    import cca8_column  # pylint: disable=import-outside-toplevel
    import cca8_controller  # pylint: disable=import-outside-toplevel
    import cca8_run  # pylint: disable=import-outside-toplevel
    from cca8_context import Ctx  # pylint: disable=import-outside-toplevel

    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()

    ctx = Ctx()
    worker_dir = Path(scratch_root) / f"worker_{os.getpid()}"
    _configure_ctx(
        ctx,
        profile=profile,
        mask_prob=mask_prob,
        condition=condition,
        seed=seed,
        output_dir=str(worker_dir),
        write_cycles=False,
    )

    result = cca8_run.experiment_run_one_episode_v1(
        ctx,
        condition_id=condition,
        seed=int(seed),
        episode_index=int(episode_index),
        suppress_output=True,
    )
    if result.get("ok") is not True:
        raise RuntimeError(f"episode failed: {result!r}")

    record = dict(result["episode_record"])
    record["validation_profile"] = str(profile)
    record["validation_obs_mask_prob"] = float(mask_prob)
    record["worker_pid"] = int(os.getpid())
    record["fresh_worker_process"] = True
    return record


def _run_trace(output_dir: Path, *, profile: str, mask_prob: float,
               condition: str, seed: int, episode_index: int) -> dict[str, Any]:
    """Run one fully logged trace in a clean in-process state."""
    import cca8_column
    import cca8_controller
    import cca8_run
    from cca8_context import Ctx

    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()

    trace_dir = output_dir / "traces" / f"{profile}_{condition}_{seed}_episode{episode_index}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    ctx = Ctx()
    _configure_ctx(
        ctx,
        profile=profile,
        mask_prob=mask_prob,
        condition=condition,
        seed=seed,
        output_dir=str(trace_dir),
        write_cycles=True,
    )
    result = cca8_run.experiment_run_one_episode_v1(
        ctx,
        condition_id=condition,
        seed=int(seed),
        episode_index=int(episode_index),
        suppress_output=True,
    )
    if result.get("ok") is not True:
        raise RuntimeError(f"trace failed: {result!r}")
    return {
        "profile": profile,
        "condition": condition,
        "seed": int(seed),
        "episode_index": int(episode_index),
        "cycle_json_path": str(Path(result["cycle_json_path"]).resolve()),
        "episode_json_path": str(Path(result["episode_json_path"]).resolve()),
        "episode_record": result["episode_record"],
    }


def _build_descriptive(rows: list[dict[str, Any]],
                       selected_specs: tuple[tuple[str, float], ...]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile, mask_prob in selected_specs:
        for condition in CONDITIONS:
            subset = [
                row for row in rows
                if row.get("validation_profile") == profile
                and row.get("condition") == condition
                and float(row.get("validation_obs_mask_prob", -1.0)) == float(mask_prob)
            ]
            output.append({
                "profile": profile,
                "obs_mask_prob": mask_prob,
                "condition": condition,
                "n": len(subset),
                "success_count": sum(bool(row.get("success")) for row in subset),
                "success_rate": _rate(subset, lambda row: row.get("success")),
                "mean_milestone_score": _mean(subset, "milestone_score"),
                "mean_time_to_rested_or_max_cycles": _mean(
                    subset, "time_to_rested_or_max_cycles"
                ),
                "mean_retrieval_events_to_completion": _mean(
                    subset, "newborn_retrieval_event_count_to_completion"
                ),
                "mean_non_noop_retrievals_to_completion": _mean(
                    subset, "newborn_retrieval_non_noop_count_to_completion"
                ),
                "mean_filled_slots_to_completion": _mean(
                    subset, "newborn_repair_filled_slot_total_to_completion"
                ),
                "mean_added_edges_to_completion": _mean(
                    subset, "newborn_repair_added_edge_total_to_completion"
                ),
                "mean_guarded_field_uses_to_completion": _mean(
                    subset, "newborn_guarded_field_use_count_to_completion"
                ),
                "mean_probe_count": _mean(subset, "conflicted_repair_probe_count"),
                "mean_unsafe_follow_count": _mean(
                    subset, "conflicted_repair_unsafe_follow_count"
                ),
                "challenge_pass_count": sum(
                    row.get("conflicted_repair_status") == "passed" for row in subset
                ),
                "missing_state_timeout_count": sum(
                    row.get("conflicted_repair_failure_reason") == "missing_state_timeout"
                    for row in subset
                ),
                "unsafe_follow_count": sum(
                    row.get("conflicted_repair_failure_reason") == "unsafe_follow_before_probe"
                    for row in subset
                ),
            })
    return output


def _build_paired(rows: list[dict[str, Any]],
                  selected_specs: tuple[tuple[str, float], ...]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile, mask_prob in selected_specs:
        profile_rows = [
            row for row in rows
            if row.get("validation_profile") == profile
            and float(row.get("validation_obs_mask_prob", -1.0)) == float(mask_prob)
        ]
        maps = {
            condition: {int(row["seed"]): row for row in profile_rows if row.get("condition") == condition}
            for condition in CONDITIONS
        }
        for comparator in ("B", "C"):
            shared = sorted(set(maps["A"]) & set(maps[comparator]))
            a_success_other_fail = sum(
                bool(maps["A"][seed].get("success"))
                and not bool(maps[comparator][seed].get("success"))
                for seed in shared
            )
            a_fail_other_success = sum(
                not bool(maps["A"][seed].get("success"))
                and bool(maps[comparator][seed].get("success"))
                for seed in shared
            )
            a_rate = sum(bool(maps["A"][seed].get("success")) for seed in shared) / len(shared)
            other_rate = sum(
                bool(maps[comparator][seed].get("success")) for seed in shared
            ) / len(shared)
            output.append({
                "profile": profile,
                "obs_mask_prob": mask_prob,
                "comparison": f"{comparator}_minus_A",
                "n_pairs": len(shared),
                "A_success_rate": a_rate,
                "comparator_success_rate": other_rate,
                "success_rate_difference": other_rate - a_rate,
                "A_success_comparator_fail": a_success_other_fail,
                "A_fail_comparator_success": a_fail_other_success,
                "exact_paired_binary_p": _exact_paired_binary_p(
                    a_success_other_fail, a_fail_other_success
                ),
                "mean_time_difference": statistics.mean(
                    float(maps[comparator][seed]["time_to_rested_or_max_cycles"])
                    - float(maps["A"][seed]["time_to_rested_or_max_cycles"])
                    for seed in shared
                ),
            })
    return output


def _schedule_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("conflicted_repair_schedule_mode"),
        bool(row.get("conflicted_repair_conflict_present")),
        row.get("conflicted_repair_conflict_draw"),
        bool(row.get("conflicted_repair_memory_available")),
        int(row.get("conflicted_repair_encoding_opportunities", 0) or 0),
        int(row.get("conflicted_repair_encoding_successes", 0) or 0),
        tuple(row.get("conflicted_repair_encoding_draws", []) or []),
        tuple(row.get("conflicted_repair_reacquire_offsets", []) or []),
        tuple(row.get("conflicted_repair_reacquire_draws", []) or []),
    )


def _build_schedule_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    challenge_a = [
        row for row in rows
        if row.get("validation_profile") == "conflicted_repair"
        and row.get("condition") == "A"
    ]
    combinations: dict[str, int] = {}
    for row in challenge_a:
        key = (
            f"conflict={int(bool(row.get('conflicted_repair_conflict_present')))}|"
            f"memory={int(bool(row.get('conflicted_repair_memory_available')))}|"
            f"planned_reacq={int(bool(row.get('conflicted_repair_reacquire_offsets')))}"
        )
        combinations[key] = combinations.get(key, 0) + 1
    return {
        "n_matched_schedules": len(challenge_a),
        "conflict_count": sum(
            bool(row.get("conflicted_repair_conflict_present")) for row in challenge_a
        ),
        "no_conflict_count": sum(
            not bool(row.get("conflicted_repair_conflict_present")) for row in challenge_a
        ),
        "memory_available_count": sum(
            bool(row.get("conflicted_repair_memory_available")) for row in challenge_a
        ),
        "memory_missing_count": sum(
            not bool(row.get("conflicted_repair_memory_available")) for row in challenge_a
        ),
        "planned_reacquisition_count": sum(
            bool(row.get("conflicted_repair_reacquire_offsets")) for row in challenge_a
        ),
        "no_planned_reacquisition_count": sum(
            not bool(row.get("conflicted_repair_reacquire_offsets")) for row in challenge_a
        ),
        "combination_counts": dict(sorted(combinations.items())),
    }


def _build_strata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    challenge = [row for row in rows if row.get("validation_profile") == "conflicted_repair"]
    output: list[dict[str, Any]] = []
    for conflict in (False, True):
        for memory in (False, True):
            for planned_reacq in (False, True):
                for condition in CONDITIONS:
                    subset = [
                        row for row in challenge
                        if row.get("condition") == condition
                        and bool(row.get("conflicted_repair_conflict_present")) == conflict
                        and bool(row.get("conflicted_repair_memory_available")) == memory
                        and bool(row.get("conflicted_repair_reacquire_offsets")) == planned_reacq
                    ]
                    output.append({
                        "conflict_present": conflict,
                        "memory_available": memory,
                        "planned_reacquisition": planned_reacq,
                        "condition": condition,
                        "n": len(subset),
                        "success_count": sum(bool(row.get("success")) for row in subset),
                        "success_rate": _rate(subset, lambda row: row.get("success")),
                        "actual_reacquired_count": sum(
                            bool(row.get("conflicted_repair_reacquired")) for row in subset
                        ),
                        "challenge_pass_count": sum(
                            row.get("conflicted_repair_status") == "passed" for row in subset
                        ),
                        "missing_state_timeout_count": sum(
                            row.get("conflicted_repair_failure_reason") == "missing_state_timeout"
                            for row in subset
                        ),
                        "unsafe_follow_count": sum(
                            row.get("conflicted_repair_failure_reason") == "unsafe_follow_before_probe"
                            for row in subset
                        ),
                        "mean_time_to_rested_or_max_cycles": _mean(
                            subset, "time_to_rested_or_max_cycles"
                        ),
                        "mean_repairs_to_completion": _mean(
                            subset, "newborn_retrieval_non_noop_count_to_completion"
                        ),
                    })
    return output


def _validate(rows: list[dict[str, Any]], seed_count: int,
              selected_profiles: set[str]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for profile in selected_profiles:
        for condition in CONDITIONS:
            checks[f"{profile}_{condition}_has_expected_n"] = (
                sum(
                    row.get("validation_profile") == profile
                    and row.get("condition") == condition
                    for row in rows
                ) == seed_count
            )

    challenge = [row for row in rows if row.get("validation_profile") == "conflicted_repair"]
    if challenge:
        maps = {
            condition: {
                (int(row["seed"]), int(row.get("episode_index", 0))): row
                for row in challenge if row.get("condition") == condition
            }
            for condition in CONDITIONS
        }
        shared = sorted(set(maps["A"]) & set(maps["B"]) & set(maps["C"]))
        checks["all_challenge_schedules_are_matched"] = all(
            _schedule_signature(maps["A"][key])
            == _schedule_signature(maps["B"][key])
            == _schedule_signature(maps["C"][key])
            for key in shared
        )
        a_rows = list(maps["A"].values())
        checks["conflict_varies_across_seeds"] = {
            bool(row.get("conflicted_repair_conflict_present")) for row in a_rows
        } == {False, True}
        checks["encoding_completeness_varies_across_seeds"] = {
            bool(row.get("conflicted_repair_memory_available")) for row in a_rows
        } == {False, True}
        checks["planned_reacquisition_varies_across_seeds"] = (
            any(bool(row.get("conflicted_repair_reacquire_offsets")) for row in a_rows)
            and any(not bool(row.get("conflicted_repair_reacquire_offsets")) for row in a_rows)
        )
        checks["condition_A_never_uses_direct_hint"] = all(
            int(row.get("newborn_retrieved_hint_set_count", 0) or 0) == 0
            and int(row.get("newborn_retrieved_hint_used_step_count", 0) or 0) == 0
            for row in maps["A"].values()
        )
        checks["condition_B_has_no_target_retrieval"] = all(
            int(row.get("newborn_retrieval_event_count_to_completion", 0) or 0) == 0
            for row in maps["B"].values()
        )
        checks["condition_A_performs_real_structural_repair_in_some_episodes"] = any(
            int(row.get("newborn_retrieval_non_noop_count_to_completion", 0) or 0) > 0
            and int(row.get("newborn_repair_filled_slot_total_to_completion", 0) or 0) > 0
            and int(row.get("newborn_guarded_field_use_count_to_completion", 0) or 0) > 0
            for row in maps["A"].values()
        )
        b_success = [row for row in maps["B"].values() if bool(row.get("success"))]
        checks["condition_B_success_requires_actual_reacquisition"] = bool(b_success) and all(
            bool(row.get("conflicted_repair_reacquired")) for row in b_success
        )
        c_unsafe = [
            row for row in maps["C"].values()
            if row.get("conflicted_repair_failure_reason") == "unsafe_follow_before_probe"
        ]
        checks["condition_C_unsafe_failures_require_conflict"] = bool(c_unsafe) and all(
            bool(row.get("conflicted_repair_conflict_present")) for row in c_unsafe
        )
        checks["outcomes_have_nontrivial_variability"] = all(
            0 < sum(bool(row.get("success")) for row in maps[condition].values()) < seed_count
            for condition in ("B", "C")
        )

    return {
        "schema": "conflicted_repair_stochastic_mechanism_validation_v3",
        "passed": bool(checks) and all(checks.values()),
        "checks": checks,
    }


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in materialized:
            writer.writerow({
                key: json.dumps(value, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else value
                for key, value in row.items()
            })


def _select_trace_keys(rows: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
    """Choose a few representative stochastic schedules after the run."""
    a_rows = [
        row for row in rows
        if row.get("validation_profile") == "conflicted_repair"
        and row.get("condition") == "A"
    ]
    predicates = [
        ("conflict_memory_available", lambda r: bool(r.get("conflicted_repair_conflict_present"))
         and bool(r.get("conflicted_repair_memory_available"))),
        ("no_conflict_memory_available", lambda r: not bool(r.get("conflicted_repair_conflict_present"))
         and bool(r.get("conflicted_repair_memory_available"))),
        ("memory_missing_planned_reacquisition", lambda r: not bool(r.get("conflicted_repair_memory_available"))
         and bool(r.get("conflicted_repair_reacquire_offsets"))),
        ("memory_missing_no_planned_reacquisition", lambda r: not bool(r.get("conflicted_repair_memory_available"))
         and not bool(r.get("conflicted_repair_reacquire_offsets"))),
    ]
    selected: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()
    for label, predicate in predicates:
        match = next((row for row in a_rows if predicate(row)), None)
        if match is None:
            continue
        key = (int(match["seed"]), int(match.get("episode_index", 0)))
        if key in seen:
            continue
        seen.add(key)
        selected.append((key[0], key[1], label))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-manifest", default="conflicted_repair_seed_manifest.json")
    parser.add_argument("--output-dir", default="conflicted_repair_stochastic_validation_results")
    parser.add_argument("--jobs", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--n-seeds", type=int, default=None)
    parser.add_argument(
        "--profile", action="append", choices=[profile for profile, _ in PROFILE_SPECS]
    )
    parser.add_argument("--skip-traces", action="store_true")
    parser.add_argument(
        "--no-fresh-process-per-episode", action="store_true",
        help="Reuse workers. Intended only for quick debugging.",
    )
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent
    os.chdir(repo_dir)
    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    seed_manifest_path = Path(args.seed_manifest).resolve()
    manifest = json.loads(seed_manifest_path.read_text(encoding="utf-8"))
    seeds = [int(value) for value in manifest.get("seeds", [])]
    if args.n_seeds is not None:
        seeds = seeds[: max(1, int(args.n_seeds))]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("seed manifest must contain unique integer seeds")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve() / f"run_{timestamp}"
    scratch_dir = output_dir / "scratch"
    output_dir.mkdir(parents=True, exist_ok=False)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    selected_profiles = set(args.profile or [profile for profile, _ in PROFILE_SPECS])
    selected_specs = tuple(
        (profile, mask_prob) for profile, mask_prob in PROFILE_SPECS
        if profile in selected_profiles
    )
    tasks = [
        (profile, mask_prob, condition, seed, episode_index, str(scratch_dir))
        for profile, mask_prob in selected_specs
        for condition in CONDITIONS
        for episode_index, seed in enumerate(seeds)
    ]

    started = time.time()
    rows: list[dict[str, Any]] = []
    maxtasks = None if args.no_fresh_process_per_episode else 1
    context = mp.get_context("spawn" if platform.system() == "Windows" else "fork")
    with context.Pool(processes=max(1, int(args.jobs)), maxtasksperchild=maxtasks) as pool:
        for index, row in enumerate(pool.imap_unordered(_run_one_episode, tasks, chunksize=1), 1):
            rows.append(row)
            if index % 25 == 0 or index == len(tasks):
                print(f"completed {index}/{len(tasks)} episodes", flush=True)

    rows.sort(key=lambda row: (
        str(row.get("validation_profile")), str(row.get("condition")), int(row.get("seed", 0))
    ))
    (output_dir / "episode_rows.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    descriptive = _build_descriptive(rows, selected_specs)
    paired = _build_paired(rows, selected_specs)
    schedule_summary = _build_schedule_summary(rows)
    strata = _build_strata(rows)
    validation = _validate(rows, len(seeds), selected_profiles)

    _json_dump(output_dir / "descriptive_summary.json", descriptive)
    _write_csv(output_dir / "descriptive_summary.csv", descriptive)
    _json_dump(output_dir / "paired_success_comparisons.json", paired)
    _write_csv(output_dir / "paired_success_comparisons.csv", paired)
    _json_dump(output_dir / "stochastic_schedule_summary.json", schedule_summary)
    _json_dump(output_dir / "stochastic_strata_summary.json", strata)
    _write_csv(output_dir / "stochastic_strata_summary.csv", strata)
    _json_dump(output_dir / "mechanism_validation.json", validation)

    trace_records: list[dict[str, Any]] = []
    trace_selection = _select_trace_keys(rows)
    if not args.skip_traces and "conflicted_repair" in selected_profiles:
        for seed, episode_index, label in trace_selection:
            for condition in CONDITIONS:
                trace = _run_trace(
                    output_dir,
                    profile="conflicted_repair",
                    mask_prob=0.50,
                    condition=condition,
                    seed=seed,
                    episode_index=episode_index,
                )
                trace["selection_label"] = label
                trace_records.append(trace)
    _json_dump(output_dir / "trace_manifest.json", trace_records)

    source_hashes = {
        path.name: _sha256(path)
        for path in sorted(repo_dir.glob("*.py"))
        if not path.name.startswith("_")
    }
    source_hashes[seed_manifest_path.name] = _sha256(seed_manifest_path)
    run_manifest = {
        "schema": "conflicted_repair_stochastic_validation_run_v3",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(time.time() - started, 6),
        "python_version": sys.version,
        "platform": platform.platform(),
        "process_start_method": context.get_start_method(),
        "fresh_process_per_episode": not args.no_fresh_process_per_episode,
        "jobs": int(args.jobs),
        "seed_count": len(seeds),
        "episode_count": len(rows),
        "profiles": [
            {"profile": profile, "obs_mask_prob": mask_prob}
            for profile, mask_prob in selected_specs
        ],
        "conditions": list(CONDITIONS),
        "challenge_design": {
            "mode": "stochastic_v3",
            "challenge_deadline_cycles": CHALLENGE_DEADLINE_CYCLES,
            "conflict_probability": CONFLICT_PROBABILITY,
            "encoding_opportunities": ENCODING_OPPORTUNITIES,
            "encoding_opportunity_mask_probability": 0.50,
            "reacquisition_probability_per_cycle": REACQUIRE_PROBABILITY,
            "reacquisition_start_delay_cycles": REACQUIRE_START_DELAY,
            "reacquired_cue_still_subject_to_ordinary_mask": True,
            "matched_named_rng_streams": True,
        },
        "max_episode_cycles": 60,
        "trace_selection": [
            {"seed": seed, "episode_index": index, "label": label}
            for seed, index, label in trace_selection
        ],
        "source_hashes": source_hashes,
        "mechanism_validation_passed": bool(validation["passed"]),
    }
    _json_dump(output_dir / "run_manifest.json", run_manifest)

    checksum_lines = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            checksum_lines.append(
                f"{_sha256(path)}  {path.relative_to(output_dir).as_posix()}"
            )
    (output_dir / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "output_dir": str(output_dir),
        "episode_count": len(rows),
        "mechanism_validation_passed": validation["passed"],
        "descriptive_summary": descriptive,
        "paired_success_comparisons": paired,
        "stochastic_schedule_summary": schedule_summary,
    }, indent=2))
    return 0 if validation["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
