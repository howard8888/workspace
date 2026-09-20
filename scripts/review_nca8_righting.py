#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect P18-H5 source-dependent Righting and PNM previews without movement.

This permanent review entry calls the same finite examples as NCA8 menu option 7.
All source readings are explicit replay fixtures. No body target is installed,
no motor provider is created and no files, existing session or learned data change.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nca8_righting_demo import run_righting_preview_review_v1


def main() -> int:
    """Run the finite shared review and leave exceptions visible to validation."""
    run_righting_preview_review_v1()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
