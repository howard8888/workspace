#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect P16-2B-A/B/C/D/E approach, correspondence, continuous stand-follow and replays.

Run from any directory. This helper delegates to the same finite functions as
NCA8 menus 10-13, writes no repository files, and reports actual owner-bound/durable
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
    FOLLOW_MOM_CASES_V1, MATERNAL_REPLAY_CASES_V1, MATERNAL_OUTCOME_CASES_V1, render_follow_mom_v1, render_maternal_replay_v1,
    run_follow_mom_v1, run_maternal_source_replay_v1,
)

from nca8_stand_follow_demo import STAND_FOLLOW_CASES_V1, render_stand_follow_v1, run_stand_follow_v1
from nca8_maternal_attention_demo import MATERNAL_ATTENTION_CASES_V1, render_maternal_attention_v1, run_maternal_attention_v1
from nca8_maternal_learning_demo import (
    MATERNAL_LEARNING_CASES_V1, render_maternal_learning_v1, run_maternal_learning_v1,
    run_maternal_learning_routing_fixture_v1, render_maternal_learning_routing_fixture_v1,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Select one declared experiment family; do not silently repair unknown selectors."""
    parser = argparse.ArgumentParser(description=__doc__)
    selected = parser.add_mutually_exclusive_group()
    selected.add_argument("--case", choices=("all", *FOLLOW_MOM_CASES_V1), default="all")
    selected.add_argument("--replay", nargs="?", const="all", choices=("all", *MATERNAL_REPLAY_CASES_V1))
    selected.add_argument("--outcomes", nargs="?", const="all", choices=("all", *MATERNAL_OUTCOME_CASES_V1))
    selected.add_argument("--stand-follow", nargs="?", const="all", choices=("all", *STAND_FOLLOW_CASES_V1),
                          help="run one continuous Righting/Follow-Mom stream, not a stage list")
    selected.add_argument("--outcome-attention", nargs="?", const="all", choices=("all", *MATERNAL_ATTENTION_CASES_V1),
                          help="inspect maternal discrepancy, actual source competition and one focal allocation")
    selected.add_argument("--learning", nargs="?", const="all", choices=("all", *MATERNAL_LEARNING_CASES_V1),
                          help="inspect maternal participation and actual no-learning Phase F")
    selected.add_argument("--learning-routing", nargs="?", const="all", choices=("all", "eligible", "expired"),
                          help="supply explicit routing fixtures without physical world steps")
    parser.add_argument("--detail", action="store_true", help="include source, PNM, target and local-drive details")
    parser.add_argument("--json", action="store_true", help="export complete detached results instead of text")
    args = parser.parse_args(argv)
    if args.learning is not None:
        learning_cases = MATERNAL_LEARNING_CASES_V1 if args.learning == "all" else (args.learning,)
        learning_results = tuple(run_maternal_learning_v1(case) for case in learning_cases)
        print(json.dumps([item.as_dict() for item in learning_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_maternal_learning_v1(item, detail=args.detail) for item in learning_results))
        return int(any(item.bound_violations or not item.durable_unchanged or not item.fixed_configuration_unchanged
                       for item in learning_results))
    if args.learning_routing is not None:
        expiry_cases = (False, True) if args.learning_routing == "all" else (args.learning_routing == "expired",)
        routing_results = tuple(run_maternal_learning_routing_fixture_v1(expired=expired) for expired in expiry_cases)
        print(json.dumps([{"physical_world_steps": 0, "evidence": "supplied_routing_fixture",
                           "cycles": [item.as_dict() for item in records]} for records in routing_results],
                         sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_maternal_learning_routing_fixture_v1(records) for records in routing_results))
        return 0
    if args.outcome_attention is not None:
        attention_cases = MATERNAL_ATTENTION_CASES_V1 if args.outcome_attention == "all" else (args.outcome_attention,)
        attention_results = tuple(run_maternal_attention_v1(case) for case in attention_cases)
        print(json.dumps([item.as_dict() for item in attention_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_maternal_attention_v1(item, detail=args.detail) for item in attention_results))
        return int(any(item.bound_violations or not item.durable_unchanged for item in attention_results))
    if args.stand_follow is not None:
        stand_cases = STAND_FOLLOW_CASES_V1 if args.stand_follow == "all" else (args.stand_follow,)
        stand_results = tuple(run_stand_follow_v1(case) for case in stand_cases)
        print(json.dumps([item.as_dict() for item in stand_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_stand_follow_v1(item, detail=args.detail) for item in stand_results))
        return int(any(item.bound_violations or not item.durable_unchanged for item in stand_results))
    if args.replay is not None:
        replay_cases = MATERNAL_REPLAY_CASES_V1 if args.replay == "all" else (args.replay,)
        replays = tuple(run_maternal_source_replay_v1(case) for case in replay_cases)
        print(json.dumps([item.as_dict() for item in replays], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_maternal_replay_v1(item) for item in replays))
        return 0
    if args.outcomes is not None:
        outcome_cases: tuple[str, ...] = MATERNAL_OUTCOME_CASES_V1 if args.outcomes == "all" else (args.outcomes,)
        results = tuple(run_follow_mom_v1(case, outcomes_enabled=True) for case in outcome_cases)
    else:
        cases: tuple[str, ...] = FOLLOW_MOM_CASES_V1 if args.case == "all" else (args.case,)
        results = tuple(run_follow_mom_v1(case) for case in cases)
    print(json.dumps([item.as_dict() for item in results], sort_keys=True, allow_nan=False) if args.json else
          "\n\n".join(render_follow_mom_v1(item, detail=args.detail) for item in results))
    return int(any(item.bound_violations or not item.durable_unchanged for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
