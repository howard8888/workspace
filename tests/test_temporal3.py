import random
from cca8_temporal import TemporalContext, dot, cosine

def test_temporal_unit_norm_and_copy():
    random.seed(42)
    t = TemporalContext(dim=8, sigma=0.02, jump=0.25)
    v0 = t.vector()
    # unit-ish length and defensive copy
    assert abs((sum(x*x for x in v0) ** 0.5) - 1.0) < 1e-9
    v0_mod = list(v0); v0_mod[0] += 0.123
    assert t.vector()[0] != v0_mod[0]

def test_temporal_step_and_boundary_cosine_ranges():
    random.seed(123)
    t = TemporalContext(dim=16, sigma=0.02, jump=0.25)
    v0 = t.vector()
    v1 = t.step()
    v2 = t.boundary()
    # step → almost same direction; boundary → noticeably different
    assert cosine(v0, v1) > 0.99
    assert cosine(v0, v2) < 0.99

def test_dot_and_cosine_agree_for_unit_vectors():
    random.seed(9)
    t = TemporalContext(dim=12)
    v = t.vector()
    assert abs(dot(v, v) - 1.0) < 1e-12
    assert abs(cosine(v, v) - 1.0) < 1e-12
