import math
from cca8_temporal import TemporalContext

def _l2(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def test_temporal_unit_norm_and_dim():
    tc = TemporalContext(dim=64)  # smaller dim for speed
    v0 = tc.vector()
    assert len(v0) == 64
    assert abs(math.sqrt(sum(x*x for x in v0)) - 1.0) < 1e-7

def test_vector_returns_copy_not_alias():
    tc = TemporalContext()
    v = tc.vector()
    v[0] = 999.0
    assert tc.vector()[0] != 999.0  # internal state unaffected

def test_step_and_boundary_move_vector_different_magnitudes():
    tc = TemporalContext(sigma=0.02, jump=0.25)
    v0 = tc.vector()
    v1 = tc.step()
    v2 = tc.boundary()
    d_step = _l2(v0, v1)
    d_jump = _l2(v1, v2)
    assert d_step > 0.0
    assert d_jump > d_step  # boundary should move more than a typical step

def test_zero_sigma_is_stable_under_step():
    tc = TemporalContext(sigma=0.0, jump=0.25)
    v0 = tc.vector()
    v1 = tc.step()
    # normalization should keep the vector identical when no noise is added
    assert _l2(v0, v1) < 1e-12
