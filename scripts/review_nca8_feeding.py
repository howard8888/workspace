#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect the source-only P16-2C-A cases shared with NCA8 menu 15.

This helper writes no repository files. PASS qualifies only the displayed
source/access checks, not oral movement, contact, nourishment, rest or B99.
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run a declared finite case; never infer or repair an unknown selector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *FEEDING_DETAIL_CASES_V1), default="all")
    parser.add_argument("--detail", action="store_true", help="include actual source-selection timeline")
    parser.add_argument("--json", action="store_true", help="export complete detached evidence rather than text")
    args = parser.parse_args(argv)
    cases = FEEDING_DETAIL_CASES_V1 if args.case == "all" else (args.case,)
    results = tuple(run_feeding_detail_v1(case) for case in cases)
    print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False) if args.json else
          "\n\n".join(render_feeding_detail_v1(item, detail=args.detail) for item in results))
    return int(any(item.review_status != "PASS" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
