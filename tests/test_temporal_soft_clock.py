# tests/test_temporal_soft_clock.py
from cca8_temporal import TemporalContext, dot, cosine

def test_drift_small_boundary_larger():
    t = TemporalContext(dim=16, sigma=0.1, jump=0.5)
    v0 = t.vector()
    v1 = t.step()          # small drift
    v2 = t.boundary()      # larger jump

    assert dot(v0, v1) < 1.0000001
    assert cosine(v0, v2) < cosine(v0, v1)  # boundary moves farther
