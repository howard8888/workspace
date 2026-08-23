"""Combined feature-payload and explicit time-attribute coverage."""

from __future__ import annotations

from cca8_features import FactMeta, TensorPayload, time_attrs_from_ctx
from cca8_run import Ctx


def test_time_attrs_factmeta_and_tensorpayload_roundtrip() -> None:
    """The features seam should preserve counters and dense payload values."""
    ctx = Ctx()
    ctx.cog_cycles = 2
    ctx.controller_steps = 5
    ctx.ticks = 7
    ctx.age_days = 0.25

    attrs = time_attrs_from_ctx(ctx)
    assert attrs == {
        "cognitive_cycle": 2,
        "controller_step": 5,
        "autonomic_tick": 7,
        "age_days": 0.25,
    }

    fact = FactMeta(name="vision:scene", links=["b1"]).with_time(ctx)
    assert fact.as_dict()["attrs"] == attrs

    payload = TensorPayload(data=[1.0, 2.0, 3.0], shape=(3,))
    restored = TensorPayload.from_bytes(payload.to_bytes())
    assert restored.shape == (3,)
    assert restored.data[:3] == [1.0, 2.0, 3.0]
