#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect retained sources, supplied oral targets, or selected SeekNipple.

All routes use the same functions as NCA8 menu 15. The --seek route invokes
the retained bounded selected-task review. --seek-outcomes adds original seeking
prediction correspondence without changing that default. --seek-attention adds
source relevance and one focal interpretation. --seek-learning adds source-owned
participation and the real Phase-F callback, with zero durable learning.
The --oral route supplies
one relation fixture; it is not Navigation-selected feeding, latch or milk.
The default source/access route and its complete exports remain unchanged.
This helper writes no repository files; neither review closes P16-2C or B99.
Any failed review check produces a nonzero exit. Run from any directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nca8_feeding_demo import FEEDING_DETAIL_CASES_V1, render_feeding_detail_v1, run_feeding_detail_v1
from nca8_oral_demo import ORAL_CONTACT_CASES_V1, render_oral_contact_v1, run_oral_contact_v1
from nca8_seek_nipple_demo import SEEK_NIPPLE_CASES_V1, render_seek_nipple_v1, run_seek_nipple_v1
from nca8_seek_outcomes_demo import SEEK_NIPPLE_OUTCOME_CASES_V1, render_seek_nipple_outcome_v1, run_seek_nipple_outcome_v1
from nca8_seek_attention_demo import SEEKING_ATTENTION_CASES_V1, render_seeking_attention_v1, run_seeking_attention_v1
from nca8_seek_learning_demo import SEEKING_LEARNING_CASES_V1, render_seeking_learning_v1, run_seeking_learning_v1


def main(argv: Sequence[str] | None = None) -> int:
    """Run a declared finite case; never infer or repair an unknown selector."""
    parser = argparse.ArgumentParser(description=__doc__)
    family = parser.add_mutually_exclusive_group()
    family.add_argument("--oral", action="store_true", help="review the separate supplied-target/contact foundation")
    family.add_argument("--seek", action="store_true", help="review Navigation-selected bounded seeking; no latch or milk")
    family.add_argument("--seek-outcomes", action="store_true", help="compare original seeking PNM with actual execution and later evidence")
    family.add_argument("--seek-attention", action="store_true", help="review seeking outcome relevance and one focal interpretation")
    family.add_argument("--seek-learning", action="store_true", help="review original seeking participation and no-learning Phase F")
    parser.add_argument("--case", default="all", help="case name for the selected review, or all")
    parser.add_argument("--detail", action="store_true", help="include actual source-selection timeline")
    parser.add_argument("--json", action="store_true", help="export complete detached evidence rather than text")
    args = parser.parse_args(argv)
    allowed = (SEEKING_LEARNING_CASES_V1 if args.seek_learning else SEEKING_ATTENTION_CASES_V1 if args.seek_attention else
               SEEK_NIPPLE_OUTCOME_CASES_V1 if args.seek_outcomes else SEEK_NIPPLE_CASES_V1 if args.seek else
               ORAL_CONTACT_CASES_V1 if args.oral else FEEDING_DETAIL_CASES_V1)
    if args.case != "all" and args.case not in allowed:
        parser.error("case is not available in this review; choose: all, " + ", ".join(allowed))
    cases = allowed if args.case == "all" else (args.case,)
    if args.seek_learning:
        learning_results = tuple(run_seeking_learning_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in learning_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_seeking_learning_v1(item, detail=args.detail) for item in learning_results))
        return int(any(item.review_status != "PASS" for item in learning_results))
    if args.seek_attention:
        attention_results = tuple(run_seeking_attention_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in attention_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_seeking_attention_v1(item, detail=args.detail) for item in attention_results))
        return int(any(item.review_status != "PASS" for item in attention_results))
    if args.seek_outcomes:
        outcome_results = tuple(run_seek_nipple_outcome_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in outcome_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_seek_nipple_outcome_v1(item, detail=args.detail) for item in outcome_results))
        return int(any(item.review_status != "PASS" for item in outcome_results))
    if args.seek:
        seek_results = tuple(run_seek_nipple_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in seek_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_seek_nipple_v1(item, detail=args.detail) for item in seek_results))
        return int(any(item.review_status != "PASS" for item in seek_results))
    if args.oral:
        oral_results = tuple(run_oral_contact_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in oral_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_oral_contact_v1(item, detail=args.detail) for item in oral_results))
        return int(any(item.review_status != "PASS" for item in oral_results))
    results = tuple(run_feeding_detail_v1(case) for case in cases)
    print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False) if args.json else
          "\n\n".join(render_feeding_detail_v1(item, detail=args.detail) for item in results))
    return int(any(item.review_status != "PASS" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
