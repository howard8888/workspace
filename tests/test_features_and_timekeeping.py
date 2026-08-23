"""Tensor payload and explicit timekeeping metadata tests."""

from __future__ import annotations

import pytest

from cca8_features import FactMeta, TensorPayload, time_attrs_from_ctx


def test_tensorpayload_roundtrip() -> None:
    """A TensorPayload should preserve its shape, values, and compact metadata."""
    payload = TensorPayload(data=[1.0, 2.5, -3.25], shape=(3,))
    restored = TensorPayload.from_bytes(payload.to_bytes())

    assert restored.shape == payload.shape
    assert restored.data == pytest.approx(payload.data)
    meta = restored.meta()
    assert meta == {
        "kind": payload.kind,
        "fmt": payload.fmt,
        "shape": payload.shape,
        "len": len(payload.data),
    }


def test_tensorpayload_from_bytes_bad_magic_raises() -> None:
    """A corrupted TensorPayload header must be rejected."""
    payload = TensorPayload(data=[0.0], shape=(1,))
    encoded = bytearray(payload.to_bytes())
    encoded[0] ^= 0x01

    with pytest.raises(ValueError):
        TensorPayload.from_bytes(bytes(encoded))


class _FakeCtx:
    """Small context exposing only the supported explicit timekeeping values."""

    cog_cycles = 7
    controller_steps = 11
    ticks = 3
    age_days = 0.25


def test_time_attrs_and_factmeta_with_time() -> None:
    """Engram metadata should use interpretable counters rather than vector fingerprints."""
    ctx = _FakeCtx()
    attrs = time_attrs_from_ctx(ctx)

    assert attrs == {
        "cognitive_cycle": 7,
        "controller_step": 11,
        "autonomic_tick": 3,
        "age_days": 0.25,
    }

    fact = FactMeta(name="vision:scene", links=["b1"], attrs={"source": "test"}).with_time(ctx)
    data = fact.as_dict()

    assert data["name"] == "vision:scene"
    assert data["links"] == ["b1"]
    assert data["attrs"] == {"source": "test", **attrs}
    assert "tvec64" not in data["attrs"]
    assert "epoch" not in data["attrs"]
