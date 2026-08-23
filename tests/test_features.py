"""CCA8 feature schema tests."""

from __future__ import annotations

from cca8_features import FactMeta, TensorPayload, time_attrs_from_ctx


class _Ctx:
    cog_cycles = 7
    controller_steps = 123
    ticks = 9
    age_days = 0.5


def test_tensorpayload_roundtrip_and_meta() -> None:
    """TensorPayload should preserve dense values and compact descriptors."""
    payload = TensorPayload(data=[0.1, 0.2, 0.3, 0.4], shape=(4,))
    restored = TensorPayload.from_bytes(payload.to_bytes())

    assert restored.shape == (4,)
    assert len(restored.data) == 4
    assert restored.meta() == {
        "kind": "embedding",
        "fmt": "tensor/list-f32",
        "shape": (4,),
        "len": 4,
    }


def test_factmeta_and_time_attrs_from_ctx() -> None:
    """Fact metadata should merge source attrs with the explicit counters."""
    ctx = _Ctx()
    fact = FactMeta(name="vision:silhouette:mom", links=["b9"], attrs={"k": "v"}).with_time(ctx)

    assert fact.as_dict() == {
        "name": "vision:silhouette:mom",
        "links": ["b9"],
        "attrs": {
            "k": "v",
            "cognitive_cycle": 7,
            "controller_step": 123,
            "autonomic_tick": 9,
            "age_days": 0.5,
        },
    }
    assert time_attrs_from_ctx(ctx) == {
        "cognitive_cycle": 7,
        "controller_step": 123,
        "autonomic_tick": 9,
        "age_days": 0.5,
    }
