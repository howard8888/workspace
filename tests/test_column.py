# tests/test_column.py
import re
from cca8_column import ColumnMemory
from cca8_features import TensorPayload, FactMeta

def _payload(vec=(0.1, 0.2, 0.3)):
    return TensorPayload(data=list(vec), shape=(len(vec),), kind="embedding")

def test_assert_fact_roundtrip_and_meta():
    col = ColumnMemory(name="column01")
    fm = FactMeta(name="vision:silhouette:mom", links=["b3"], attrs={"epoch": 0, "epoch_vhash64": "deadbeef"})
    eid = col.assert_fact("vision:silhouette:mom", _payload(), fm)
    rec = col.get(eid)
    assert rec["id"] == eid
    assert rec["name"] == "vision:silhouette:mom"
    assert isinstance(rec["payload"], TensorPayload)
    meta = rec["meta"]
    assert meta["name"] == "vision:silhouette:mom"
    assert meta["attrs"]["epoch"] == 0
    assert meta["attrs"]["column"] == "column01"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", meta["created_at"])

def test_exists_try_get_delete_and_count():
    col = ColumnMemory()
    eid = col.assert_fact("x", _payload(), FactMeta(name="x"))
    assert col.exists(eid)
    assert col.try_get(eid)["id"] == eid
    assert col.count() == 1
    assert col.delete(eid) is True
    assert not col.exists(eid)
    assert col.try_get(eid) is None
    assert col.count() == 0

def test_list_and_find_helpers():
    col = ColumnMemory()
    e1 = col.assert_fact("vision:silhouette:mom", _payload(), FactMeta(name="vision:silhouette:mom", attrs={"epoch": 0}))
    e2 = col.assert_fact("olfaction:scent:mom",    _payload(), FactMeta(name="olfaction:scent:mom",    attrs={"epoch": 1}))
    ids = col.list_ids()
    assert e1 in ids and e2 in ids
    f1 = col.find(name_contains="scent")
    assert len(f1) == 1 and f1[0]["id"] == e2
    f2 = col.find(epoch=0)
    assert len(f2) == 1 and f2[0]["id"] == e1
