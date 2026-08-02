#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Weight-and-cap sensitivity analysis for the secondary CCA8 LHSI metric.

The Long-Horizon State-Integrity score (LHSI) is a heuristic secondary
composite.  This tool recomputes it under prespecified global scaling,
leave-one-component-out, uniform-weight, and cap variants.  It does not alter
any behavioral result and must be interpreted after success, milestones,
completion time, and mechanism-specific event counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from cca8_publication_analysis import load_episode_jsonl_v1, validate_episode_design_v1
from cca8_publication_integrity import write_checksum_text_v1, write_json_exclusive_v1
from cca8_publication_protocol import CONDITIONS, PROFILES

__version__ = "1.0.0"
SENSITIVITY_SCHEMA = "cca8_publication_lhsi_sensitivity_v1"


@dataclass(frozen=True, slots=True)
class LHSISpec:
    name: str
    description: str
    wrong_stage_weight: float = 0.03
    wrong_stage_cap: float = 0.25
    overwrite_weight: float = 0.04
    overwrite_cap: float = 0.25
    stale_weight: float = 0.04
    stale_cap: float = 0.20
    loop_weight: float = 0.02
    loop_cap: float = 0.15
    provenance_weight: float = 0.10
    provenance_cap: float = 0.10
    missing_provenance_penalty: float = 0.05


DEFAULT_SPEC = LHSISpec(
    name="default",
    description="Published heuristic weights and caps.",
)


def _scaled_spec(base: LHSISpec, *, name: str, description: str, weight_scale: float = 1.0, cap_scale: float = 1.0) -> LHSISpec:
    return LHSISpec(
        name=name,
        description=description,
        wrong_stage_weight=base.wrong_stage_weight * weight_scale,
        wrong_stage_cap=base.wrong_stage_cap * cap_scale,
        overwrite_weight=base.overwrite_weight * weight_scale,
        overwrite_cap=base.overwrite_cap * cap_scale,
        stale_weight=base.stale_weight * weight_scale,
        stale_cap=base.stale_cap * cap_scale,
        loop_weight=base.loop_weight * weight_scale,
        loop_cap=base.loop_cap * cap_scale,
        provenance_weight=base.provenance_weight * weight_scale,
        provenance_cap=base.provenance_cap * cap_scale,
        missing_provenance_penalty=base.missing_provenance_penalty * weight_scale,
    )


def sensitivity_specs_v1() -> list[LHSISpec]:
    """Return the frozen prespecified LHSI sensitivity family."""
    specs: list[LHSISpec] = [DEFAULT_SPEC]
    for weight_scale in (0.5, 1.5, 2.0):
        specs.append(
            _scaled_spec(
                DEFAULT_SPEC,
                name=f"all_weights_x{weight_scale:g}",
                description=f"All penalty weights and the missing-provenance penalty multiplied by {weight_scale:g}; caps unchanged.",
                weight_scale=weight_scale,
            )
        )
    for cap_scale in (0.5, 1.5, 2.0):
        specs.append(
            _scaled_spec(
                DEFAULT_SPEC,
                name=f"all_caps_x{cap_scale:g}",
                description=f"All per-component caps multiplied by {cap_scale:g}; weights unchanged.",
                cap_scale=cap_scale,
            )
        )
    for component, fields in (
        ("wrong_stage", {"wrong_stage_weight": 0.0, "wrong_stage_cap": 0.0}),
        ("overwrite", {"overwrite_weight": 0.0, "overwrite_cap": 0.0}),
        ("stale", {"stale_weight": 0.0, "stale_cap": 0.0}),
        ("loops", {"loop_weight": 0.0, "loop_cap": 0.0}),
        (
            "provenance",
            {"provenance_weight": 0.0, "provenance_cap": 0.0, "missing_provenance_penalty": 0.0},
        ),
    ):
        specs.append(
            replace(
                DEFAULT_SPEC,
                name=f"drop_{component}",
                description=f"Leave-one-component-out ablation for {component}.",
                **fields,
            )
        )
    specs.extend(
        [
            LHSISpec(
                name="uniform_low",
                description="All event penalties use weight 0.02 and cap 0.15; provenance weight/cap 0.05.",
                wrong_stage_weight=0.02,
                wrong_stage_cap=0.15,
                overwrite_weight=0.02,
                overwrite_cap=0.15,
                stale_weight=0.02,
                stale_cap=0.15,
                loop_weight=0.02,
                loop_cap=0.15,
                provenance_weight=0.05,
                provenance_cap=0.05,
                missing_provenance_penalty=0.025,
            ),
            LHSISpec(
                name="uniform_high",
                description="All event penalties use weight 0.05 and cap 0.25; provenance weight/cap 0.10.",
                wrong_stage_weight=0.05,
                wrong_stage_cap=0.25,
                overwrite_weight=0.05,
                overwrite_cap=0.25,
                stale_weight=0.05,
                stale_cap=0.25,
                loop_weight=0.05,
                loop_cap=0.25,
                provenance_weight=0.10,
                provenance_cap=0.10,
                missing_provenance_penalty=0.05,
            ),
            replace(
                DEFAULT_SPEC,
                name="minimal_caps_0.10",
                description="All event caps and the provenance cap are 0.10.",
                wrong_stage_cap=0.10,
                overwrite_cap=0.10,
                stale_cap=0.10,
                loop_cap=0.10,
                provenance_cap=0.10,
            ),
            replace(
                DEFAULT_SPEC,
                name="effectively_uncapped",
                description="All caps are set to 1.00 while default per-event weights are retained.",
                wrong_stage_cap=1.00,
                overwrite_cap=1.00,
                stale_cap=1.00,
                loop_cap=1.00,
                provenance_cap=1.00,
            ),
            LHSISpec(
                name="milestone_only",
                description="No integrity penalties; LHSI equals ordered milestone score.",
                wrong_stage_weight=0.0,
                wrong_stage_cap=0.0,
                overwrite_weight=0.0,
                overwrite_cap=0.0,
                stale_weight=0.0,
                stale_cap=0.0,
                loop_weight=0.0,
                loop_cap=0.0,
                provenance_weight=0.0,
                provenance_cap=0.0,
                missing_provenance_penalty=0.0,
            ),
        ]
    )
    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate LHSI sensitivity scenario name")
    return specs


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def compute_lhsi_v1(row: dict[str, Any], spec: LHSISpec) -> tuple[float, dict[str, float]]:
    """Compute one score and its transparent component penalties."""
    milestone = max(0.0, min(1.0, _number(row.get("milestone_score"))))
    wrong = max(0.0, _number(row.get("lhsi_wrong_stage_action_count")))
    overwrite = max(0.0, _number(row.get("lhsi_current_state_overwrite_proxy_count")))
    stale = max(0.0, _number(row.get("lhsi_stale_memory_intrusion_proxy_count")))
    loops = max(0.0, _number(row.get("lhsi_repeated_action_loop_count")))
    provenance_raw = row.get("lhsi_provenance_complete_cycle_rate")
    provenance_available = isinstance(provenance_raw, (int, float)) and math.isfinite(float(provenance_raw))

    components = {
        "wrong_stage_penalty": min(spec.wrong_stage_cap, spec.wrong_stage_weight * wrong),
        "overwrite_penalty": min(spec.overwrite_cap, spec.overwrite_weight * overwrite),
        "stale_penalty": min(spec.stale_cap, spec.stale_weight * stale),
        "loop_penalty": min(spec.loop_cap, spec.loop_weight * loops),
    }
    if provenance_available:
        provenance = max(0.0, min(1.0, float(provenance_raw)))
        components["provenance_penalty"] = min(
            spec.provenance_cap,
            spec.provenance_weight * max(0.0, 1.0 - provenance),
        )
    else:
        components["provenance_penalty"] = spec.missing_provenance_penalty
    components["total_penalty"] = sum(components.values())
    score = max(0.0, milestone - components["total_penalty"])
    return (round(score, 6), components)


def _mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else math.nan


def _sd(values: Sequence[float]) -> float:
    return float(statistics.stdev(values)) if len(values) >= 2 else 0.0


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[indexed[position][0]] = average_rank
        start = end
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mx = _mean(x)
    my = _mean(y)
    dx = [value - mx for value in x]
    dy = [value - my for value in y]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denominator == 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denominator


def _spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    return _pearson(_average_ranks(x), _average_ranks(y))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_lhsi_sensitivity_v1(
    *,
    batch_dir: str | Path,
    output_dir: str | Path,
    require_frozen_holdout: bool = False,
) -> dict[str, Any]:
    batch = Path(batch_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = load_episode_jsonl_v1(batch / "episodes.jsonl")
    design = validate_episode_design_v1(rows, require_frozen_holdout=require_frozen_holdout)
    if not design["ok"]:
        write_json_exclusive_v1(output / "LHSI_VALIDATION_FAILED.json", design)
        raise ValueError("episode design validation failed: " + ", ".join(design["errors"]))

    specs = sensitivity_specs_v1()
    episode_rows: list[dict[str, Any]] = []
    by_scenario_cell: dict[tuple[str, str, str], list[float]] = {}
    default_scores: list[float] = []
    scenario_scores: dict[str, list[float]] = {spec.name: [] for spec in specs}
    max_default_error = 0.0

    for row in rows:
        default_score, _ = compute_lhsi_v1(row, DEFAULT_SPEC)
        stored_default = _number(row.get("lhsi_state_integrity_score"), default=default_score)
        max_default_error = max(max_default_error, abs(default_score - stored_default))
        default_scores.append(default_score)
        for spec in specs:
            score, components = compute_lhsi_v1(row, spec)
            scenario_scores[spec.name].append(score)
            profile = str(row.get("publication_profile") or "")
            condition = str(row.get("condition") or "").upper()
            by_scenario_cell.setdefault((spec.name, profile, condition), []).append(score)
            episode_rows.append(
                {
                    "scenario": spec.name,
                    "profile": profile,
                    "condition": condition,
                    "episode_index": int(row.get("episode_index", -1)),
                    "episode_seed": int(row.get("seed" if "seed" in row else "episode_seed", -1)),
                    "lhsi": score,
                    "stored_default_lhsi": stored_default if spec.name == "default" else "",
                    **components,
                }
            )

    summary_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []
    for spec in specs:
        for profile in PROFILES:
            means: dict[str, float] = {}
            for condition in CONDITIONS:
                values = by_scenario_cell.get((spec.name, profile, condition), [])
                if not values:
                    continue
                mean_value = _mean(values)
                means[condition] = mean_value
                summary_rows.append(
                    {
                        "scenario": spec.name,
                        "description": spec.description,
                        "profile": profile,
                        "condition": condition,
                        "n": len(values),
                        "mean_lhsi": mean_value,
                        "sd_lhsi": _sd(values),
                        "min_lhsi": min(values),
                        "max_lhsi": max(values),
                    }
                )
            if "A" in means:
                for comparator in ("B", "C"):
                    if comparator not in means:
                        continue
                    contrast_rows.append(
                        {
                            "scenario": spec.name,
                            "profile": profile,
                            "comparison": f"A_minus_{comparator}",
                            "mean_A": means["A"],
                            "mean_comparator": means[comparator],
                            "mean_difference": means["A"] - means[comparator],
                            "A_higher": means["A"] > means[comparator],
                            "A_equal": means["A"] == means[comparator],
                        }
                    )

    correlation_rows: list[dict[str, Any]] = []
    for spec in specs:
        values = scenario_scores[spec.name]
        correlation_rows.append(
            {
                "scenario": spec.name,
                "pearson_with_default_episode_scores": _pearson(default_scores, values),
                "spearman_with_default_episode_scores": _spearman(default_scores, values),
            }
        )

    robustness: dict[str, Any] = {}
    for profile in PROFILES:
        for comparator in ("B", "C"):
            selected = [
                row
                for row in contrast_rows
                if row["profile"] == profile and row["comparison"] == f"A_minus_{comparator}"
            ]
            key = f"{profile}:A_minus_{comparator}"
            robustness[key] = {
                "scenario_count": len(selected),
                "A_higher_count": sum(1 for row in selected if row["A_higher"]),
                "A_equal_count": sum(1 for row in selected if row["A_equal"]),
                "A_lower_count": sum(1 for row in selected if not row["A_higher"] and not row["A_equal"]),
                "minimum_mean_difference": min((row["mean_difference"] for row in selected), default=None),
                "maximum_mean_difference": max((row["mean_difference"] for row in selected), default=None),
            }

    _write_csv(output / "lhsi_sensitivity_episode_scores.csv", episode_rows)
    _write_csv(output / "lhsi_sensitivity_summary.csv", summary_rows)
    _write_csv(output / "lhsi_sensitivity_contrasts.csv", contrast_rows)
    _write_csv(output / "lhsi_sensitivity_correlations.csv", correlation_rows)
    write_json_exclusive_v1(output / "lhsi_sensitivity_specs.json", [asdict(spec) for spec in specs])

    metadata = {
        "schema": SENSITIVITY_SCHEMA,
        "analysis_version": __version__,
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "batch_dir": str(batch),
        "episode_count": len(rows),
        "scenario_count": len(specs),
        "require_frozen_holdout": bool(require_frozen_holdout),
        "design_validation": design,
        "default_reproduction_max_absolute_error": max_default_error,
        "default_reproduced_within_1e_6": max_default_error <= 1.000001e-6,
        "robustness": robustness,
        "interpretation_guardrail": (
            "LHSI is a heuristic secondary composite. Sensitivity results do not replace behavioral outcomes or "
            "mechanism-specific event counts."
        ),
    }
    write_json_exclusive_v1(output / "lhsi_sensitivity_metadata.json", metadata)

    markdown = [
        "# LHSI Weight and Cap Sensitivity",
        "",
        f"Scenarios evaluated: {len(specs)}",
        "",
        "LHSI remains a secondary heuristic composite. Success, milestones, timing, repair events, state conflicts, and failure categories receive priority.",
        "",
        "## Robustness of A-versus-comparator mean direction",
        "",
        "| Profile and contrast | A higher | Equal | A lower | Minimum difference | Maximum difference |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, value in robustness.items():
        minimum = value["minimum_mean_difference"]
        maximum = value["maximum_mean_difference"]
        markdown.append(
            f"| {key} | {value['A_higher_count']} | {value['A_equal_count']} | {value['A_lower_count']} | "
            f"{minimum:.4f} | {maximum:.4f} |"
            if minimum is not None and maximum is not None
            else f"| {key} | 0 | 0 | 0 | n/a | n/a |"
        )
    markdown.extend(
        [
            "",
            f"Maximum absolute discrepancy between recomputed and stored default LHSI: {max_default_error:.8f}",
            "",
        ]
    )
    (output / "lhsi_sensitivity_report.md").write_text("\n".join(markdown), encoding="utf-8", newline="\n")
    checksum_path = write_checksum_text_v1(output)
    return {
        "ok": True,
        "output_dir": str(output),
        "episode_count": len(rows),
        "scenario_count": len(specs),
        "default_reproduction_max_absolute_error": max_default_error,
        "checksums": str(checksum_path),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-frozen-holdout", action="store_true")
    args = parser.parse_args()
    try:
        result = run_lhsi_sensitivity_v1(
            batch_dir=args.batch,
            output_dir=args.output,
            require_frozen_holdout=bool(args.require_frozen_holdout),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"[lhsi-sensitivity] ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
