"""Column and dense-feature integration tests."""

from __future__ import annotations

import pytest

COL = pytest.importorskip("cca8_column", reason="missing column")
FEA = pytest.importorskip("cca8_features", reason="missing features")


def test_column_assert_and_get_fact_roundtrip() -> None:
    """ColumnMemory should return the exact rich payload asserted under an engram id."""
    column = COL.ColumnMemory(name="testcol")
    payload = FEA.TensorPayload(data=[0.1, 0.2, 0.3], shape=(3,), kind="scene", fmt="tensor/list-f32")

    eid = column.assert_fact("scene:demo", payload)
    record = column.get(eid)

    assert record["id"] == eid
    assert record["name"] == "scene:demo"
    assert record["payload"].shape == (3,)
    assert isinstance(record["payload"], FEA.TensorPayload)


def test_tensorpayload_bytes_roundtrip() -> None:
    """Dense float values should survive the compact binary serialization contract."""
    payload = FEA.TensorPayload([1.0, 2.0, 3.0, 4.0], shape=(2, 2))
    restored = FEA.TensorPayload.from_bytes(payload.to_bytes())

    assert restored.shape == (2, 2)
    assert restored.data == [1.0, 2.0, 3.0, 4.0]


def test_tensorpayload_meta_has_shape_and_len() -> None:
    """Payload metadata should remain available without decoding the float buffer."""
    payload = FEA.TensorPayload([0.0, 0.1, 0.2], shape=(3,), kind="scene")

    assert payload.meta() == {
        "kind": "scene",
        "fmt": "tensor/list-f32",
        "shape": (3,),
        "len": 3,
    }
