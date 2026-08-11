"""Compatibility launcher for the stochastic conflicted-repair validation.

The balanced 2x2 v2 runner has been superseded.  This module retains the old
filename so existing commands continue to work, but delegates to the v3
stochastic validation runner.

UPDATED DOCSTRING

Compatibility entry point for stochastic conflicted-repair validation.

Research context
----------------
This filename belongs to the development history of the Journal of
Superintelligence state-repair benchmark. An earlier balanced 2-by-2 validator
was replaced by the more realistic stochastic validation program in
``cca8_conflicted_repair_stochastic_validation.py``.

Purpose
-------
The module preserves the historical command name so scripts, notes, and manual
workflows that still invoke ``cca8_conflicted_repair_validation.py`` continue to
work. It imports the stochastic validator's ``main()`` function and delegates the
entire command-line run to that function.

Relationship to other modules
-----------------------------
All command-line options, validation orchestration, process isolation,
summaries, trace selection, manifests, and output files are implemented by
``cca8_conflicted_repair_stochastic_validation.py``, which calls the underlying
CCA8 experiment subsystem. This compatibility module contains no independent
experiment logic and should not acquire a second set of options or validation
rules.

Running this file therefore has the same command-line interface, output format,
and exit status as running the stochastic validator directly.
"""

from __future__ import annotations

from cca8_conflicted_repair_stochastic_validation import main


if __name__ == "__main__":
    raise SystemExit(main())
