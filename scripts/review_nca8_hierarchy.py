#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the menu's integrated H6-A review; print evidence without writing files."""

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


def main(argv: Sequence[str] | None = None) -> int:
    """Run bounded shared examples, retaining exceptions as visible validation failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("nominal", "disturbed", "both"), default="both")
    parser.add_argument("--detail", action="store_true", help="show each local drive and observed report")
    parser.add_argument("--json", action="store_true", help="print a detached finite observer export")
    args = parser.parse_args(argv)
    cases = ("nominal", "disturbed") if args.case == "both" else (args.case,)
    results = tuple(run_integrated_righting_v1(case) for case in cases)
    if args.json:
        print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False))
    else:
        print("\n\n".join(render_integrated_righting_v1(item, detail=args.detail) for item in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
