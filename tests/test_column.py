"""ColumnMemory behavior and explicit cognitive-cycle filtering."""

from __future__ import annotations

import re

from cca8_column import ColumnMemory
from cca8_features import FactMeta, TensorPayload


def _payload(vec: tuple[float, ...] = (0.1, 0.2, 0.3)) -> TensorPayload:
    return TensorPayload(data=list(vec), shape=(len(vec),), kind="embedding")


def test_assert_fact_roundtrip_and_meta() -> None:
    """A stored record should preserve payload metadata and add Column provenance."""
    column = ColumnMemory(name="column01")
    fact = FactMeta(
        name="vision:silhouette:mom",
        links=["b3"],
        attrs={"cognitive_cycle": 0, "controller_step": 1},
    )

    eid = column.assert_fact("vision:silhouette:mom", _payload(), fact)
    record = column.get(eid)

    assert record["id"] == eid
    assert record["name"] == "vision:silhouette:mom"
    assert isinstance(record["payload"], TensorPayload)
    meta = record["meta"]
    assert meta["name"] == "vision:silhouette:mom"
    assert meta["attrs"]["cognitive_cycle"] == 0
    assert meta["attrs"]["column"] == "column01"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", meta["created_at"])


def test_exists_try_get_delete_and_count() -> None:
    """Basic in-memory Column record operations should remain stable."""
    column = ColumnMemory()
    eid = column.assert_fact("x", _payload(), FactMeta(name="x"))

    assert column.exists(eid)
    assert column.try_get(eid)["id"] == eid
    assert column.count() == 1
    assert column.delete(eid) is True
    assert not column.exists(eid)
    assert column.try_get(eid) is None
    assert column.count() == 0


def test_list_and_find_helpers() -> None:
    """Column search should support names, attrs, and cognitive-cycle filters."""
    column = ColumnMemory()
    first = column.assert_fact(
        "vision:silhouette:mom",
        _payload(),
        FactMeta(name="vision:silhouette:mom", attrs={"cognitive_cycle": 0}),
    )
    second = column.assert_fact(
        "olfaction:scent:mom",
        _payload(),
        FactMeta(name="olfaction:scent:mom", attrs={"cognitive_cycle": 1}),
    )

    assert first in column.list_ids() and second in column.list_ids()
    assert [row["id"] for row in column.find(name_contains="scent")] == [second]
    assert [row["id"] for row in column.find(cognitive_cycle=0)] == [first]
