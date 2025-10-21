import math
import pytest

COL = pytest.importorskip("cca8_column", reason="missing column")
FEA = pytest.importorskip("cca8_features", reason="missing features")
TMP = pytest.importorskip("cca8_temporal", reason="missing temporal")

def test_column_assert_and_get_fact_roundtrip():
    cm = COL.ColumnMemory(name="testcol")
    tp = FEA.TensorPayload(data=[0.1, 0.2, 0.3], shape=(3,), kind="scene", fmt="tensor/list-f32")
    eid = cm.assert_fact("scene:demo", tp)
    rec = cm.get(eid)
    assert rec["id"] == eid and rec["name"] == "scene:demo"
    assert rec["payload"].shape == (3,) and isinstance(rec["payload"], FEA.TensorPayload)

def test_tensorpayload_bytes_roundtrip():
    tp = FEA.TensorPayload([1.0, 2.0, 3.0, 4.0], shape=(2, 2))
    blob = tp.to_bytes()
    tp2 = FEA.TensorPayload.from_bytes(blob)
    assert tp2.shape == (2, 2)
    assert tp2.data == [1.0, 2.0, 3.0, 4.0]

def test_temporal_context_normalized_and_steps_change():
    tc = TMP.TemporalContext(dim=8, sigma=0.05, jump=0.2)
    v0 = tc.vector()
    n0 = math.isclose(sum(x*x for x in v0), 1.0, rel_tol=1e-6, abs_tol=1e-6)
    v1 = tc.step()
    v2 = tc.boundary()
    assert n0 and math.isclose(sum(x*x for x in v1), 1.0, rel_tol=1e-6)
    assert math.isclose(sum(x*x for x in v2), 1.0, rel_tol=1e-6)
    assert v1 != v0 or v2 != v1  # drift/jump should change vector

def test_tensorpayload_meta_has_shape_and_len():
    tp = FEA.TensorPayload([0.0, 0.1, 0.2], shape=(3,), kind="scene")
    m = tp.meta()
    assert m["kind"] == "scene" and m["shape"] == (3,) and m["len"] == 3
