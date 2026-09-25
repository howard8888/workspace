#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect retained sources, supplied oral targets, or selected SeekNipple.

All routes use the same functions as NCA8 menu 15. The --seek route invokes
the retained bounded selected-task review. --seek-outcomes adds original seeking
prediction correspondence without changing that default. --seek-attention adds
source relevance and one focal interpretation. --seek-learning adds source-owned
participation and the real Phase-F callback, with zero durable learning.
The --oral route supplies a reach fixture; --oral-seal supplies bounded closure
with independently measured seal evidence. Neither is Navigation-selected
Suckle, a latch task verdict, or observed milk.
The --suckle route selects the initial latch contribution through Navigation;
milk and full Suckle remain deferred. The --suckle-outcomes route adds original
Suckle correspondence without Attention or learning consequences.
The --suckle-attention route adds the J relevance/interpretation consumer;
request selection is not IP reapplication and supplies no movement permission.
The --suckle-learning route adds original Suckle participation and the real F
checkpoint, including a separate hook-disabled behavioral control. It consumes
an actual J result, never interprets, reapplies an IP or changes durable values.
The --oral-extraction route supplies fixed direct motor drives and observes physical
milk transfer/sensing; it is not autonomous Suckle or BodyMap target execution.
The --oral-extraction-control route supplies a BodyMap requirement and observes the
existing executor following it. It still does not select a Suckle IP or complete feeding.
The --suckle-extraction route makes one genuine Navigation-selected extraction
contribution; task-PNM/milk scoring, nourishment and full feeding remain deferred.
The --suckle-extraction-outcomes route adds original C2 relation/interval-milk
accounting, with a separate unchanged-action consumer-off control. It grants no
next task, interpretation, nourishment, new participation or learning.
The --suckle-extraction-attention route adds a bounded measured-discrepancy
question and one Navigation-granted interpretation, never another extraction batch.
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

from nca8_suckle_extraction_attention_demo import (
    EXTRACTION_ATTENTION_CASES_V1, render_extraction_attention_v1, run_extraction_attention_v1,
)
from nca8_suckle_extraction_outcomes_demo import (
    SUCKLE_EXTRACTION_OUTCOME_CASES_V1, render_suckle_extraction_outcome_v1, run_suckle_extraction_outcome_v1,
)
from nca8_feeding_demo import FEEDING_DETAIL_CASES_V1, render_feeding_detail_v1, run_feeding_detail_v1
from nca8_oral_demo import ORAL_CONTACT_CASES_V1, render_oral_contact_v1, run_oral_contact_v1
from nca8_oral_extraction_control_demo import (
    ORAL_EXTRACTION_CONTROL_CASES_V1, render_oral_extraction_control_v1, run_oral_extraction_control_v1,
)
from nca8_oral_extraction_demo import ORAL_EXTRACTION_CASES_V1, render_oral_extraction_v1, run_oral_extraction_v1
from nca8_oral_seal_demo import ORAL_SEAL_CASES_V1, render_oral_seal_v1, run_oral_seal_v1
from nca8_suckle_extraction_demo import (
    SUCKLE_EXTRACTION_CASES_V1, render_suckle_extraction_v1, run_suckle_extraction_v1,
)
from nca8_suckle_demo import SUCKLE_LATCH_CASES_V1, render_suckle_v1, run_suckle_v1
from nca8_suckle_attention_demo import SUCKLE_ATTENTION_CASES_V1, render_suckle_attention_v1, run_suckle_attention_v1
from nca8_suckle_learning_demo import SUCKLE_LEARNING_CASES_V1, render_suckle_learning_v1, run_suckle_learning_v1
from nca8_suckle_outcomes_demo import SUCKLE_OUTCOME_CASES_V1, render_suckle_outcome_v1, run_suckle_outcome_v1
from nca8_seek_nipple_demo import SEEK_NIPPLE_CASES_V1, render_seek_nipple_v1, run_seek_nipple_v1
from nca8_seek_outcomes_demo import SEEK_NIPPLE_OUTCOME_CASES_V1, render_seek_nipple_outcome_v1, run_seek_nipple_outcome_v1
from nca8_seek_attention_demo import SEEKING_ATTENTION_CASES_V1, render_seeking_attention_v1, run_seeking_attention_v1
from nca8_seek_learning_demo import SEEKING_LEARNING_CASES_V1, render_seeking_learning_v1, run_seeking_learning_v1


def main(argv: Sequence[str] | None = None) -> int:
    """Run a declared finite case; never infer or repair an unknown selector."""
    parser = argparse.ArgumentParser(description=__doc__)
    family = parser.add_mutually_exclusive_group()
    family.add_argument("--suckle-extraction-attention", action="store_true", help="review extraction relevance and one Navigation interpretation")
    family.add_argument("--suckle-extraction-outcomes", action="store_true", help="review original extraction and measured interval milk; no next action")
    family.add_argument("--suckle-extraction", action="store_true", help="review one Navigation-selected Suckle extraction contribution")
    family.add_argument("--oral-extraction-control", action="store_true", help="review supplied BodyMap extraction/return control")
    family.add_argument("--oral-extraction", action="store_true", help="review direct-drive physical extraction/milk sensing only")
    family.add_argument("--suckle-learning", action="store_true", help="review original Suckle participation and no-learning Phase F")
    family.add_argument("--suckle-attention", action="store_true", help="review Suckle relevance and one Navigation interpretation; no learning")
    family.add_argument("--suckle-outcomes", action="store_true", help="review execution-sensitive Suckle correspondence; no milk or learning")
    family.add_argument("--suckle", action="store_true", help="review selected initial latch; no milk or full Suckle task")
    family.add_argument("--oral-seal", action="store_true", help="review supplied closure and independently observed seal; no Suckle")
    family.add_argument("--oral", action="store_true", help="review the separate supplied-target/contact foundation")
    family.add_argument("--seek", action="store_true", help="review Navigation-selected bounded seeking; no latch or milk")
    family.add_argument("--seek-outcomes", action="store_true", help="compare original seeking PNM with actual execution and later evidence")
    family.add_argument("--seek-attention", action="store_true", help="review seeking outcome relevance and one focal interpretation")
    family.add_argument("--seek-learning", action="store_true", help="review original seeking participation and no-learning Phase F")
    parser.add_argument("--case", default="all", help="case name for the selected review, or all")
    parser.add_argument("--detail", action="store_true", help="include actual source-selection timeline")
    parser.add_argument("--json", action="store_true", help="export complete detached evidence rather than text")
    args = parser.parse_args(argv)
    allowed = (EXTRACTION_ATTENTION_CASES_V1 if args.suckle_extraction_attention else SUCKLE_EXTRACTION_OUTCOME_CASES_V1 if args.suckle_extraction_outcomes else SUCKLE_EXTRACTION_CASES_V1 if args.suckle_extraction else ORAL_EXTRACTION_CONTROL_CASES_V1 if args.oral_extraction_control else ORAL_EXTRACTION_CASES_V1 if args.oral_extraction else SUCKLE_LEARNING_CASES_V1 if args.suckle_learning else SUCKLE_ATTENTION_CASES_V1 if args.suckle_attention else SUCKLE_OUTCOME_CASES_V1 if args.suckle_outcomes else SUCKLE_LATCH_CASES_V1 if args.suckle else ORAL_SEAL_CASES_V1 if args.oral_seal else SEEKING_LEARNING_CASES_V1 if args.seek_learning else SEEKING_ATTENTION_CASES_V1 if args.seek_attention else
               SEEK_NIPPLE_OUTCOME_CASES_V1 if args.seek_outcomes else SEEK_NIPPLE_CASES_V1 if args.seek else
               ORAL_CONTACT_CASES_V1 if args.oral else FEEDING_DETAIL_CASES_V1)
    if args.case != "all" and args.case not in allowed:
        parser.error("case is not available in this review; choose: all, " + ", ".join(allowed))
    cases = allowed if args.case == "all" else (args.case,)
    if args.suckle_extraction_attention:
        extraction_attention_results = tuple(run_extraction_attention_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in extraction_attention_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_extraction_attention_v1(item, detail=args.detail) for item in extraction_attention_results))
        return int(any(item.review_status != "PASS" for item in extraction_attention_results))
    if args.suckle_extraction_outcomes:
        extraction_outcomes = tuple(run_suckle_extraction_outcome_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in extraction_outcomes], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_extraction_outcome_v1(item, detail=args.detail) for item in extraction_outcomes))
        return int(any(item.review_status != "PASS" for item in extraction_outcomes))
    if args.suckle_extraction:
        selected_extractions = tuple(run_suckle_extraction_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in selected_extractions], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_extraction_v1(item, detail=args.detail) for item in selected_extractions))
        return int(any(item.review_status != "PASS" for item in selected_extractions))
    if args.oral_extraction_control:
        extraction_control_results = tuple(run_oral_extraction_control_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in extraction_control_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_oral_extraction_control_v1(item, detail=args.detail) for item in extraction_control_results))
        return int(any(item.review_status != "PASS" for item in extraction_control_results))
    if args.oral_extraction:
        extraction_results = tuple(run_oral_extraction_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in extraction_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_oral_extraction_v1(item, detail=args.detail) for item in extraction_results))
        return int(any(item.review_status != "PASS" for item in extraction_results))
    if args.suckle_learning:
        learning_results_k = tuple(run_suckle_learning_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in learning_results_k], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_learning_v1(item, detail=args.detail) for item in learning_results_k))
        return int(any(item.review_status != "PASS" for item in learning_results_k))
    if args.suckle_attention:
        attention_results_j = tuple(run_suckle_attention_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in attention_results_j], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_attention_v1(item, detail=args.detail) for item in attention_results_j))
        return int(any(item.review_status != "PASS" for item in attention_results_j))
    if args.suckle_outcomes:
        suckle_outcomes = tuple(run_suckle_outcome_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in suckle_outcomes], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_outcome_v1(item, detail=args.detail) for item in suckle_outcomes))
        return int(any(item.review_status != "PASS" for item in suckle_outcomes))
    if args.suckle:
        suckle_results = tuple(run_suckle_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in suckle_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_suckle_v1(item, detail=args.detail) for item in suckle_results))
        return int(any(item.review_status != "PASS" for item in suckle_results))
    if args.oral_seal:
        seal_results = tuple(run_oral_seal_v1(case) for case in cases)
        print(json.dumps([item.as_dict() for item in seal_results], sort_keys=True, allow_nan=False) if args.json else
              "\n\n".join(render_oral_seal_v1(item, detail=args.detail) for item in seal_results))
        return int(any(item.review_status != "PASS" for item in seal_results))
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
