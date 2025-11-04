# tests/test_features_module.py
import dataclasses
import importlib
import math
from typing import Any

import pytest

features = importlib.import_module("cca8_features")
TensorPayload = getattr(features, "TensorPayload")
FactMeta = getattr(features, "FactMeta")


def _example_instance(cls: type[Any]) -> Any:
    if cls is TensorPayload:
        # minimal valid payload
        return TensorPayload(data=[0.1, -0.2, 0.3], shape=(3,))
    if cls is FactMeta:
        return FactMeta(name="demo", links=["b1"], attrs={"k": 1})
    # Fallback for any future dataclass with all-default fields
    return cls()  # may never be used today


@pytest.mark.parametrize("cls", [TensorPayload, FactMeta])
def test_dataclass_invariants_and_repr(cls):
    inst = _example_instance(cls)
    assert dataclasses.is_dataclass(inst)
    assert cls.__name__ in repr(inst)


def test_factmeta_as_dict_defaults_and_custom():
    m1 = FactMeta(name="x")
    d1 = m1.as_dict()
    assert d1 == {"name": "x", "links": [], "attrs": {}}

    m2 = FactMeta(name="y", links=["b1"], attrs={"a": 1})
    d2 = m2.as_dict()
    assert d2["name"] == "y" and d2["links"] == ["b1"] and d2["attrs"]["a"] == 1


def test_tensorpayload_bytes_roundtrip_and_meta():
    p = TensorPayload(data=[0.0, 1.0, 2.0, 3.0], shape=(4,))
    blob = p.to_bytes()
    q = TensorPayload.from_bytes(blob)

    # round-trip equality on core fields
    assert q.data == p.data
    assert q.shape == p.shape
    # defaults preserved
    assert q.kind == p.kind and q.fmt == p.fmt
    # meta() sanity
    meta = q.meta()
    assert meta["kind"] == "embedding"
    assert meta["fmt"] == "tensor/list-f32"
    assert meta["shape"] == (4,)
    assert meta["len"] == 4


def test_public_api_symbols_exist():
    # __all__ should surface FeaturePayload protocol + dataclasses + version
    exp = {"FeaturePayload", "TensorPayload", "FactMeta", "__version__"}
    assert hasattr(features, "__all__")
    assert exp.issubset(set(features.__all__))
