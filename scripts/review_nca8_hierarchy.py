#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review shared H6-A/B and P16-1G-A/B experiments; print evidence without writing files."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nca8_hierarchy_demo import render_integrated_righting_v1, run_integrated_righting_v1
from nca8_hierarchy_qualification import (
    HIERARCHY_QUALIFICATION_CASES_V1, HIERARCHY_QUALIFICATION_GROUPS_V1,
    render_hierarchy_qualification_summary_v1, render_hierarchy_qualification_v1,
    run_hierarchy_qualification_group_v1, run_hierarchy_qualification_v1,
)

from nca8_outcome_attention_demo import (
    OUTCOME_ATTENTION_CASES_V1, render_outcome_attention_summary_v1, render_outcome_attention_v1, run_outcome_attention_v1,
)
from nca8_outcomes_demo import (
    RIGHTING_OUTCOME_CASES_V1, render_righting_outcome_summary_v1, render_righting_outcome_v1, run_righting_outcome_v1,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run bounded shared examples, retaining exceptions as visible validation failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case", choices=("nominal", "disturbed", "both"), default=None, help="retained H6-A examples")
    selection.add_argument("--qualify", nargs="?", const="all", choices=HIERARCHY_QUALIFICATION_GROUPS_V1,
                           help="run an H6-B comparison group; no argument means all controls")
    selection.add_argument("--profile", choices=HIERARCHY_QUALIFICATION_CASES_V1, help="inspect one H6-B profile")
    selection.add_argument("--outcomes", nargs="?", const="all", choices=("all", *RIGHTING_OUTCOME_CASES_V1),
                           help="run the separate opt-in P16-1G-A task outcome profile")
    selection.add_argument("--outcome-attention", nargs="?", const="all", choices=("all", *OUTCOME_ATTENTION_CASES_V1),
                           help="run the approved opt-in P16-1G-B mismatch and single-focal-allocation profile")
    parser.add_argument("--detail", action="store_true", help="show each local drive and observed report")
    parser.add_argument("--json", action="store_true", help="print a detached finite observer export")
    args = parser.parse_args(argv)
    if args.outcome_attention is not None:
        attention_cases = OUTCOME_ATTENTION_CASES_V1 if args.outcome_attention == "all" else (args.outcome_attention,)
        attention_records = tuple(run_outcome_attention_v1(case) for case in attention_cases)
        if args.json:
            print(json.dumps([item.as_dict() for item in attention_records], sort_keys=True, allow_nan=False))
        else:
            print(render_outcome_attention_summary_v1(attention_records))
            if args.outcome_attention != "all" or args.detail:
                print("\n\n".join(render_outcome_attention_v1(item, detail=args.detail) for item in attention_records))
        return int(any(item.bound_violations for item in attention_records))
    if args.outcomes is not None:
        selected_cases = RIGHTING_OUTCOME_CASES_V1 if args.outcomes == "all" else (args.outcomes,)
        outcome_records = tuple(run_righting_outcome_v1(case) for case in selected_cases)
        if args.json:
            print(json.dumps([item.as_dict() for item in outcome_records], sort_keys=True, allow_nan=False))
        else:
            print(render_righting_outcome_summary_v1(outcome_records))
            if args.outcomes != "all" or args.detail:
                print("\n\n".join(render_righting_outcome_v1(item, detail=args.detail) for item in outcome_records))
        return int(any(item.bound_violations for item in outcome_records))
    if args.qualify is not None or args.profile is not None:
        records = (run_hierarchy_qualification_v1(args.profile),) if args.profile is not None else (
            run_hierarchy_qualification_group_v1(args.qualify)
        )
        if args.json:
            print(json.dumps([item.as_dict() for item in records], sort_keys=True, allow_nan=False))
        else:
            print(render_hierarchy_qualification_summary_v1(records))
            if args.profile is not None or args.detail:
                print("\n\n".join(render_hierarchy_qualification_v1(item, detail=args.detail) for item in records))
        return int(any(item.bound_violations for item in records))
    cases = ("nominal", "disturbed") if args.case in (None, "both") else (args.case,)
    results = tuple(run_integrated_righting_v1(case) for case in cases)
    if args.json:
        print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False))
    else:
        print("\n\n".join(render_integrated_righting_v1(item, detail=args.detail) for item in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
