import types
import pytest

R = pytest.importorskip("cca8_run", reason="runner not found")


def test_normalize_pred_idempotent_and_prefix():
    assert R._normalize_pred("goal") == "pred:goal"
    assert R._normalize_pred("pred:goal") == "pred:goal"


def test_neighbors_handles_links_layout():
    # Build a minimal world-like object where per-binding adjacency is under 'links'
    node = types.SimpleNamespace(links=[{"to": "b2"}, {"to": "b3"}], edges=None, out=None)
    world = types.SimpleNamespace(_bindings={"b1": node})
    neigh = R._neighbors(world, "b1")
    assert set(neigh) == {"b2", "b3"}
