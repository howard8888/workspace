#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect P16-2B-A maternal approach and labelled source-only replays.

Run from any directory. This helper delegates to the same finite functions as
NCA8 menu 10, writes no repository files, and reports actual owner-bound/durable
violations as a nonzero exit. A valid adverse task outcome is not a test failure.
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

from nca8_followmom_demo import (
    FOLLOW_MOM_CASES_V1, MATERNAL_REPLAY_CASES_V1, render_follow_mom_v1, render_maternal_replay_v1,
    run_follow_mom_v1, run_maternal_source_replay_v1,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Select one declared experiment family; do not silently repair unknown selectors."""
    parser = argparse.ArgumentParser(description=__doc__)
    selected = parser.add_mutually_exclusive_group()
    selected.add_argument("--case", choices=("all", *FOLLOW_MOM_CASES_V1), default="all")
    selected.add_argument("--replay", nargs="?", const="all", choices=("all", *MATERNAL_REPLAY_CASES_V1))
    parser.add_argument("--detail", action="store_true", help="include source, PNM, target and local-drive details")
    parser.add_argument("--json", action="store_true", help="export complete detached results instead of text")
    args = parser.parse_args(argv)
    if args.replay is not None:
        replay_cases = MATERNAL_REPLAY_CASES_V1 if args.replay == "all" else (args.replay,)
        replays = tuple(run_maternal_source_replay_v1(case) for case in replay_cases)
        print(json.dumps([item.as_dict() for item in replays], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_maternal_replay_v1(item) for item in replays))
        return 0
    cases = FOLLOW_MOM_CASES_V1 if args.case == "all" else (args.case,)
    results = tuple(run_follow_mom_v1(case) for case in cases)
    print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False) if args.json else
          "\n\n".join(render_follow_mom_v1(item, detail=args.detail) for item in results))
    return int(any(item.bound_violations or not item.durable_unchanged for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
