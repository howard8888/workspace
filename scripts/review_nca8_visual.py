#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review the same finite visual/frame previews exposed by NCA8 menu option 9.

This developer entry runs explicit admitted sensor and task-requirement fixtures.
The default preview invokes no physics. --translation explicitly runs the shared
physical hierarchy; it introduces neither persistence nor durable learning.
The JSON output contains completed records, not replayable motor permissions.
No files are written; callers may redirect stdout outside the repository.
"""
from __future__ import annotations

# This thin review entry intentionally resembles other developer review scripts.
# Keep duplicate-code suppressed here rather than refactoring unrelated production modules.
# pylint: disable=duplicate-code

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nca8_translation_demo import TRANSLATION_CASES_V1, run_translation_v1, render_translation_v1
from nca8_visual_demo import VISUAL_PREVIEW_CASES_V1, render_visual_preview_v1, run_visual_preview_v1


def main(argv: list[str] | None = None) -> int:
    """Run shared fixtures and return nonzero for an observed bound/durable failure.

    Unknown selectors are argparse errors, never silently substituted nominal
    runs. Unexpected runtime exceptions remain visible. --detail changes only
    text rendering; --json emits detached results with finite numbers only.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--case", choices=("all", *VISUAL_PREVIEW_CASES_V1), default="all")
    select.add_argument("--translation", nargs="?", const="all", choices=("all", *TRANSLATION_CASES_V1),
                        help="actual target/drive/contact experiment; supplied operation, not Follow-Mom")
    parser.add_argument("--detail", action="store_true", help="show original evidence and frame details")
    parser.add_argument("--json", action="store_true", help="emit complete detached records rather than text")
    args = parser.parse_args(argv)
    if args.translation is not None:
        selected = TRANSLATION_CASES_V1 if args.translation == "all" else (args.translation,)
        translations = tuple(run_translation_v1(case) for case in selected)
        if args.json:
            print(json.dumps([run.as_dict() for run in translations], sort_keys=True, allow_nan=False))
        else:
            print("\n\n".join(render_translation_v1(run, detail=args.detail) for run in translations))
        return int(any(run.bound_violations or not run.durable_unchanged for run in translations))
    cases = VISUAL_PREVIEW_CASES_V1 if args.case == "all" else (args.case,)
    runs = tuple(run_visual_preview_v1(case) for case in cases)
    if args.json:
        print(json.dumps([run.as_dict() for run in runs], sort_keys=True, allow_nan=False))
    else:
        print("\n\n".join(render_visual_preview_v1(run, detail=args.detail) for run in runs))
    return int(any(run.bound_violations or not run.durable_unchanged for run in runs))


if __name__ == "__main__":
    raise SystemExit(main())
