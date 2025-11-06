from cca8_features import TensorPayload, FactMeta, time_attrs_from_ctx

class _Ctx:
    def __init__(self):
        self.ticks = 123
        self.boundary_no = 7
        self.boundary_vhash64 = "00ff"
    def tvec64(self):
        return "abcd"

def test_tensorpayload_roundtrip_and_meta():
    p = TensorPayload(data=[0.1, 0.2, 0.3, 0.4], shape=(4,))
    blob = p.to_bytes()
    p2 = TensorPayload.from_bytes(blob)
    assert p2.shape == (4,)
    assert len(p2.data) == 4
    m = p2.meta()
    assert m["kind"] == "embedding"
    assert m["fmt"] and m["shape"] == (4,) and m["len"] == 4

def test_factmeta_and_time_attrs_from_ctx():
    ctx = _Ctx()
    fm = FactMeta(name="vision:silhouette:mom", links=["b9"], attrs={"k":"v"})
    fm2 = fm.with_time(ctx)
    d = fm2.as_dict()
    assert d["name"] == "vision:silhouette:mom"
    assert d["links"] == ["b9"]
    # time attrs merged
    a = d["attrs"]
    assert a["ticks"] == 123 and a["tvec64"] == "abcd"
    assert a["epoch"] == 7 and a["epoch_vhash64"] == "00ff"
    # direct helper also works
    ta = time_attrs_from_ctx(ctx)
    assert ta["ticks"] == 123 and ta["tvec64"] == "abcd"
