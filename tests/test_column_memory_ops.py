import re
from cca8_column import ColumnMemory
from cca8_features import TensorPayload, FactMeta

def test_column_memory_basic_ops():
    cm = ColumnMemory(name="testcol")
    payload = TensorPayload(data=[0.1, 0.2, 0.3], shape=(3,))
    fm = FactMeta(name="vision:scene", links=["b2"], attrs={"epoch": 1})

    eid = cm.assert_fact("vision:scene", payload, meta=fm)
    assert cm.exists(eid)
    rec = cm.get(eid)

    # created + annotated
    assert "created_at" in rec["meta"]
    assert rec["meta"]["attrs"]["column"] == "testcol"

    # catalog ops
    assert cm.count() == 1
    assert eid in cm.list_ids()
    assert cm.try_get(eid)["id"] == eid

    # find() filters
    assert any(r["id"] == eid for r in cm.find(name_contains="vision"))
    assert any(r["id"] == eid for r in cm.find(epoch=1))

    # delete
    assert cm.delete(eid) is True
    assert cm.count() == 0
