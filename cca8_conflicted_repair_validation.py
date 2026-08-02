"""Compatibility launcher for the stochastic conflicted-repair validation.

The balanced 2x2 v2 runner has been superseded.  This module retains the old
filename so existing commands continue to work, but delegates to the v3
stochastic validation runner.
"""
from __future__ import annotations

from cca8_conflicted_repair_stochastic_validation import main


if __name__ == "__main__":
    raise SystemExit(main())
