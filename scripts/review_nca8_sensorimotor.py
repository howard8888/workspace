#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the same bounded P18-H4 movement experiments available from the NCA8 menu.

Use --detail to print each local feedback/command boundary. This permanent review
program supplies task requirements as explicit fixtures and performs real H2
movement through H4 control. It does not run Righting, cognitive cycles or a
learner. No file is written, no live hardware is used and no session is reused.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nca8_sensorimotor_demo import run_sensorimotor_review_v1


def main(argv: list[str] | None = None) -> int:
    """Parse the one display option and run the shared finite experiment function."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", action="store_true", help="print the local command/feedback timeline")
    args = parser.parse_args(argv)
    run_sensorimotor_review_v1(detailed=args.detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
