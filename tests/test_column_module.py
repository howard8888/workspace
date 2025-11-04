import importlib
import inspect
import random
import pytest

column = importlib.import_module("cca8_column")  # adjust if name differs

def test_module_loads_and_has_doc():
    assert column.__doc__ and isinstance(column.__doc__, str)

def test_public_api_symbols_exist():
    if not hasattr(column, "__all__"):
        pytest.skip("__all__ not defined in column module")
    for name in column.__all__:
        assert hasattr(column, name), f"public symbol missing: {name}"

def _first_class_named(mod, prefixes=("Column", "Cortical", "MiniColumn")):
    for nm, obj in inspect.getmembers(mod, inspect.isclass):
        if obj.__module__ == mod.__name__ and any(nm.startswith(p) for p in prefixes):
            return obj
    return None

def test_column_basic_lifecycle():
    Col = _first_class_named(column)
    if Col is None:
        pytest.skip("no Column-like class found")
    # init should succeed with defaults
    c = Col()
    # optional: seed/determinism if present
    if hasattr(c, "seed"):
        c.seed(123)  # type: ignore[attr-defined]
    # optional: to_dict/from_dict round trip
    if hasattr(c, "to_dict") and hasattr(Col, "from_dict"):
        snap = c.to_dict()  # type: ignore[attr-defined]
        c2 = Col.from_dict(snap)  # type: ignore[attr-defined]
        assert c2 is not None
    # optional: step() should not raise
    if hasattr(c, "step"):
        random.seed(12345)
        c.step()  # type: ignore[attr-defined]

# tests/test_column_module.py
import importlib
from cca8_features import TensorPayload, FactMeta

column = importlib.import_module("cca8_column")

def test_assert_and_get_roundtrip():
    mem = column.mem  # default ColumnMemory
    payload = TensorPayload(data=[0.1, 0.2], shape=(2,))
    meta = FactMeta(name="vision:silhouette:mom")

    eid = mem.assert_fact("scene", payload, meta=meta)
    rec = mem.get(eid)

    assert rec["id"] == eid
    assert rec["name"] == "scene"
    assert rec["payload"] == payload
    assert rec["meta"]["name"] == "vision:silhouette:mom"
