import math
import random

import pytest

from cca8_temporal import TemporalContext, dot, cosine


def _norm_sq(v: list[float]) -> float:
    return math.fsum(x * x for x in v)


def test_temporalcontext_unit_norm_and_drift_vs_boundary() -> None:
    """TemporalContext vectors stay unit-norm; drift is tiny, boundary is larger.

    This exercises:
      - __post_init__ (initial vector),
      - step() (drift noise),
      - boundary() (jump noise),
      - cosine() helper.
    """
    random.seed(42)
    t = TemporalContext(dim=8, sigma=0.02, jump=0.25)

    v0 = t.vector()
    assert pytest.approx(_norm_sq(v0), rel=0, abs=1e-6) == 1.0

    v1 = t.step()
    assert pytest.approx(_norm_sq(v1), rel=0, abs=1e-6) == 1.0
    c01 = cosine(v0, v1)
    # Drift should be very small: cosine close to 1.0
    assert 0.99 < c01 <= 1.0

    v2 = t.boundary()
    assert pytest.approx(_norm_sq(v2), rel=0, abs=1e-6) == 1.0
    c02 = cosine(v0, v2)
    # Boundary jump should be noticeably larger than a drift
    assert c02 < c01
    # Still pointing roughly in the same general half-space
    assert c02 > 0.5


def test_temporalcontext_normalize_zero_vector_safe() -> None:
    """_normalize() must handle zero-norm vectors gracefully.

    A zero vector normalizes to another zero vector rather than throwing.
    """
    vals = [0.0, 0.0, 0.0]
    out = TemporalContext._normalize(vals)
    assert out == [0.0, 0.0, 0.0]


def test_temporalcontext_dot_and_cosine_agree_on_unit_vectors() -> None:
    """dot() and cosine() should agree when vectors are already unit-norm."""
    random.seed(7)
    t = TemporalContext(dim=4, sigma=0.02, jump=0.25)
    v = t.vector()
    # v is unit-norm by construction
    assert pytest.approx(_norm_sq(v), rel=0, abs=1e-6) == 1.0
    d = dot(v, v)
    c = cosine(v, v)
    # For unit-norm vectors, dot == cosine
    assert pytest.approx(d, rel=0, abs=1e-12) == c
    assert pytest.approx(d, rel=0, abs=1e-12) == 1.0
