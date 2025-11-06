import re
from cca8_column import ColumnMemory
from cca8_features import TensorPayload, FactMeta

def _tp(vec=(0.1, 0.2, 0.3)):
    return TensorPayload(data=list(vec), shape=(len(vec),), kind="scene", fmt="tensor/list-f32")

def test_assert_fact_sets_created_at_and_column_attr():
    col = ColumnMemory(name="column01")
    fm  = FactMeta(name="scene:vision:silhouette:mom", links=["b3"], attrs={"epoch": 7})
    eid = col.assert_fact("scene:vision:silhouette:mom", _tp(), fm)
    rec = col.get(eid)
    # created_at present and ISO-like
    assert "created_at" in rec["meta"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", rec["meta"]["created_at"])
    # attrs["column"] annotated by column
    assert rec["meta"]["attrs"]["column"] == "column01"
    # epoch mirrored, name carried through
    assert rec["meta"]["attrs"]["epoch"] == 7
    assert rec["name"] == "scene:vision:silhouette:mom"

def test_exists_try_get_delete_id_uniqueness_and_count():
    col = ColumnMemory()
    e1 = col.assert_fact("x", _tp(), FactMeta(name="x"))
    e2 = col.assert_fact("y", _tp(), FactMeta(name="y"))
    assert e1 != e2
    assert col.exists(e1) and col.exists(e2)
    assert col.count() == 2
    assert col.try_get("nope") is None
    assert col.delete(e1) is True
    assert col.delete(e1) is False  # already deleted
    assert not col.exists(e1)
    assert col.count() == 1

def test_find_filters_name_epoch_has_attr():
    col = ColumnMemory()
    a = col.assert_fact("vision:silhouette:mom", _tp(), FactMeta(name="vision:silhouette:mom", attrs={"epoch": 0, "model": "demo"}))
    b = col.assert_fact("olfaction:scent:mom",  _tp(), FactMeta(name="olfaction:scent:mom",  attrs={"epoch": 1}))
    # name substring
    res = col.find(name_contains="scent")
    assert [r["id"] for r in res] == [b]
    # epoch filter
    res = col.find(epoch=0)
    assert [r["id"] for r in res] == [a]
    # has_attr filter
    res = col.find(has_attr="model")
    assert [r["id"] for r in res] == [a]
