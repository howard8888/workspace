from cca8_features import time_attrs_from_ctx, FactMeta, TensorPayload
from cca8_run import Ctx
from cca8_temporal import TemporalContext

def test_time_attrs_and_factmeta_with_time_and_tensorpayload_roundtrip():
    ctx = Ctx()
    ctx.temporal = TemporalContext(dim=8, sigma=0.01, jump=0.2)
    ctx.ticks = 5
    ctx.boundary_no = 1
    ctx.boundary_vhash64 = ctx.tvec64()

    ta = time_attrs_from_ctx(ctx)
    assert ta.get("ticks") == 5
    assert ta.get("epoch") == 1
    assert isinstance(ta.get("tvec64"), str) and isinstance(ta.get("epoch_vhash64"), str)

    fm = FactMeta(name="vision:scene", links=["b1"]).with_time(ctx)
    assert fm.as_dict()["attrs"].get("ticks") == 5

    tp = TensorPayload(data=[1.0, 2.0, 3.0], shape=(3,))
    b = tp.to_bytes()
    tp2 = TensorPayload.from_bytes(b)
    assert tp2.shape == (3,)
    assert tp2.data[:3] == [1.0, 2.0, 3.0]
