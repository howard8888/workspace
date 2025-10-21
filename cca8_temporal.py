# -*- coding: utf-8 -*-

"""
CCA8 Temporal utilities

Purpose
-------
Time helpers for stamping bindings (e.g., `meta["created_at"]`) and optional
period/year tagging. The WorldGraph itself is atemporal except for anchors
like `NOW`; temporal semantics are layered via meta and planning constraints.

Guidelines
----------
- Use ISO 8601 (seconds precision is sufficient for this sim).
- Keep any period/year helpers simple (int fields in meta).
- Do not bake clock logic into the graph—keep it in this module or the runner.

Traceability-Lite
-----------------
- REQ-PERS-09: Timestamps must be JSON-friendly and stable across loads.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import random, math
from typing import List


# in temporal_context.py
__version__ = "0.1.0"
__all__ = ["TemporalContext", "__version__"]


@dataclass
class TemporalContext:
    """128-D unit-norm temporal context with drift and boundary jumps.
    No NumPy dependency; uses stdlib only.
    """
    dim: int = 128
    sigma: float = 0.02   # per-tick drift scale
    jump: float = 0.25    # event-boundary jump scale
    _v: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self._v:
            vals = [random.gauss(0.0, 1.0) for _ in range(self.dim)]
            self._v = self._normalize(vals)

    def vector(self) -> list[float]:
        """Return a copy of the current context vector."""
        return list(self._v)

    def step(self) -> list[float]:
        """Drift the temporal vector by Gaussian noise (σ = self.sigma), renormalize to unit length, and return a copy."""
        vals = [a + random.gauss(0.0, self.sigma) for a in self._v]
        self._v = self._normalize(vals)
        return self.vector()

    def boundary(self) -> list[float]:
        """Apply a larger 'event-boundary' jump (σ = self.jump), renormalize to unit length, and return a copy."""
        vals = [a + random.gauss(0.0, self.jump) for a in self._v]
        self._v = self._normalize(vals)
        return self.vector()

    @staticmethod
    def _normalize(vals: list[float]) -> list[float]:
        """Return a unit-norm copy of `vals` (L2 normalize); safeguards against zero norm by using 1.0."""
        s = math.sqrt(sum(a * a for a in vals)) or 1.0
        return [a / s for a in vals]
