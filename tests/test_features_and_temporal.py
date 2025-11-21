import math
import pytest

from cca8_features import TensorPayload, FactMeta, time_attrs_from_ctx
from cca8_temporal import TemporalContext, dot, cosine


def test_tensorpayload_roundtrip():
    payload = TensorPayload(data=[1.0, 2.5, -3.25], shape=(3,))
    b = payload.to_bytes()
    restored = TensorPayload.from_bytes(b)

    assert restored.shape == payload.shape
    assert restored.data == pytest.approx(payload.data)
    meta = restored.meta()
    assert meta["kind"] == payload.kind
    assert meta["fmt"] == payload.fmt
    assert meta["shape"] == payload.shape
    assert meta["len"] == len(payload.data)


def test_tensorpayload_from_bytes_bad_magic_raises():
    payload = TensorPayload(data=[0.0], shape=(1,))
    good = bytearray(payload.to_bytes())
    # Corrupt the MAGIC header
    good[0] ^= 0x01
    with pytest.raises(ValueError):
        TensorPayload.from_bytes(bytes(good))


class _FakeCtx:
    def __init__(self):
        self.ticks = 10
        self.boundary_no = 3
        self.boundary_vhash64 = "deadbeef"

    def tvec64(self) -> str:
        return "cafebabe"

def test_time_attrs_and_factmeta_with_time():
    ctx = _FakeCtx()
    attrs = time_attrs_from_ctx(ctx)
    assert attrs["ticks"] == 10
    assert attrs["tvec64"] == "cafebabe"
    assert attrs["epoch"] == 3
    assert attrs["epoch_vhash64"] == "deadbeef"

    fm = FactMeta(name="vision:scene", links=["b1"])
    fm2 = fm.with_time(ctx)
    d = fm2.as_dict()

    assert d["name"] == "vision:scene"
    assert d["links"] == ["b1"]
    for key in ("ticks", "tvec64", "epoch", "epoch_vhash64"):
        assert key in d["attrs"]

def test_temporalcontext_drift_and_boundary():
    import random
    random.seed(12345)

    t = TemporalContext(dim=8, sigma=0.02, jump=0.25)
    v0 = t.vector()
    norm0 = math.sqrt(sum(x * x for x in v0))
    assert norm0 == pytest.approx(1.0, rel=1e-6)

    v1 = t.step()
    norm1 = math.sqrt(sum(x * x for x in v1))
    assert norm1 == pytest.approx(1.0, rel=1e-6)
    cos01 = cosine(v0, v1)
    assert cos01 <= 1.0
    assert cos01 > 0.9  # small drift

    v2 = t.boundary()
    norm2 = math.sqrt(sum(x * x for x in v2))
    assert norm2 == pytest.approx(1.0, rel=1e-6)
    cos02 = cosine(v0, v2)
    # event-boundary jump should move us further than a drift
    assert cos02 < cos01

    # dot/cosine consistency on unit vectors
    assert dot(v0, v0) == pytest.approx(1.0, rel=1e-6)
    assert cosine(v0, v0) == pytest.approx(1.0, rel=1e-6)
