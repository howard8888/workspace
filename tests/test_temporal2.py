# tests/test_temporal.py
import math
import random
from typing import List

import pytest

from cca8_temporal import TemporalContext


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def test_init_unit_norm_and_dim() -> None:
    random.seed(12345)
    t = TemporalContext(dim=8, sigma=0.02, jump=0.25)
    v = t.vector()
    assert len(v) == 8
    assert math.isclose(_norm(v), 1.0, rel_tol=1e-9, abs_tol=1e-9)


def test_vector_returns_defensive_copy() -> None:
    random.seed(123)
    t = TemporalContext(dim=8)
    v1 = t.vector()
    v1[0] += 123.0  # mutate the copy
    v2 = t.vector()
    assert v1 != v2  # internal state untouched


def test_step_produces_small_change_high_cosine() -> None:
    # Keep drift small; cosine with prior vector should remain very high.
    random.seed(2024)
    t = TemporalContext(dim=128, sigma=0.01, jump=0.3)
    v0 = t.vector()
    random.seed(999)  # make the noise sequence reproducible
    v1 = t.step()
    cos01 = _dot(v0, v1)
    assert 0.98 <= cos01 <= 1.0000001


def test_boundary_produces_larger_change_than_step() -> None:
    # Build two identical contexts (same seed) so we can compare step vs boundary fairly.
    random.seed(42)
    t_step = TemporalContext(dim=128, sigma=0.01, jump=0.25)
    random.seed(42)
    t_jump = TemporalContext(dim=128, sigma=0.01, jump=0.25)

    v0s = t_step.vector()
    v0j = t_jump.vector()
    assert pytest.approx(v0s) == v0j  # identical initial state

    # Use the same noise sequence for both operations; only sigma vs jump differs.
    random.seed(111)
    v_step = t_step.step()
    random.seed(111)
    v_jump = t_jump.boundary()

    cos_step = _dot(v0s, v_step)
    cos_jump = _dot(v0j, v_jump)

    # The boundary jump should move farther than a drift step.
    assert cos_jump < cos_step - 0.01


def test_norm_invariant_over_many_steps() -> None:
    random.seed(77)
    t = TemporalContext(dim=64, sigma=0.02, jump=0.25)
    for _ in range(100):
        t.step()
        assert math.isclose(_norm(t.vector()), 1.0, rel_tol=1e-8, abs_tol=1e-8)
    # And a boundary preserves unit norm too
    t.boundary()
    assert math.isclose(_norm(t.vector()), 1.0, rel_tol=1e-8, abs_tol=1e-8)


def test_normalize_guard_and_behavior() -> None:
    # Zero vector: guard path should not crash; returns zeros (norm==0).
    z = TemporalContext._normalize([0.0] * 8)
    assert all(x == 0.0 for x in z)
    assert _norm(z) == 0.0

    # Nonzero vector: result should be unit norm.
    u = TemporalContext._normalize([1.0, 1.0, 0.0, 0.0])
    assert math.isclose(_norm(u), 1.0, rel_tol=1e-12, abs_tol=1e-12)
