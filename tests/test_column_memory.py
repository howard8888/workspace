import pytest

from cca8_column import ColumnMemory
from cca8_features import TensorPayload, FactMeta


def test_column_assert_and_basic_access():
    col = ColumnMemory(name="test_column")

    payload = TensorPayload(data=[0.1, 0.2, 0.3], shape=(3,))
    meta = FactMeta(name="vision:scene", links=["b1"], attrs={"epoch": 1, "foo": "bar"})

    eid = col.assert_fact("vision:scene", payload, meta)

    assert isinstance(eid, str) and len(eid) == 32
    assert col.exists(eid)

    rec_try = col.try_get(eid)
    rec_get = col.get(eid)

    assert rec_try == rec_get
    assert rec_get["id"] == eid
    assert rec_get["name"] == "vision:scene"
    assert rec_get["meta"]["attrs"]["epoch"] == 1
    assert col.count() == 1
    assert eid in col.list_ids()


def test_column_delete_and_redelete():
    col = ColumnMemory(name="test_delete")

    payload = TensorPayload(data=[0.5], shape=(1,))
    eid = col.assert_fact("test", payload, None)

    assert col.count() == 1
    assert col.delete(eid) is True
    assert col.count() == 0
    assert col.exists(eid) is False
    # second delete is a no-op
    assert col.delete(eid) is False


def test_column_find_by_name_epoch_and_attr():
    col = ColumnMemory(name="test_find")
    payload = TensorPayload(data=[1.0], shape=(1,))

    meta1 = FactMeta(name="vision:scene", attrs={"epoch": 2, "tag": "x"})
    meta2 = FactMeta(name="vision:other", attrs={"epoch": 3})
    meta3 = FactMeta(name="auditory:scene", attrs={"epoch": 2, "tag": "y"})

    eid1 = col.assert_fact("vision:scene", payload, meta1)
    eid2 = col.assert_fact("vision:other", payload, meta2)
    eid3 = col.assert_fact("auditory:scene", payload, meta3)

    # name_contains filter
    res = col.find(name_contains="vision")
    ids = {r["id"] for r in res}
    assert {eid1, eid2}.issubset(ids)

    # epoch filter
    res_epoch = col.find(epoch=2)
    ids_epoch = {r["id"] for r in res_epoch}
    assert ids_epoch == {eid1, eid3}

    # has_attr filter
    res_attr = col.find(has_attr="tag")
    ids_attr = {r["id"] for r in res_attr}
    assert ids_attr == {eid1, eid3}

    # combined filters
    res_combo = col.find(name_contains="vision", epoch=2, has_attr="tag")
    assert [r["id"] for r in res_combo] == [eid1]


def test_column_list_ids_limit():
    col = ColumnMemory(name="test_list")
    payload = TensorPayload(data=[0.0], shape=(1,))

    ids = [col.assert_fact("n", payload, None) for _ in range(3)]
    all_ids = col.list_ids()
    assert len(all_ids) == 3

    limited = col.list_ids(limit=2)
    assert len(limited) == 2
    assert set(limited).issubset(set(ids))
