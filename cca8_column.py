# -*- coding: utf-8 -*-
"""
CCA8 Column provider (engrams)

Purpose
-------
Bindings in the WorldGraph can attach small `engrams` dicts that point into
column memory (features, traces, sensory snapshots). The graph stays small
and symbolic (fast index + planner) while the heavy content lives here.

Design notes
------------
- Engrams are lightweight *pointers* or small descriptors, not blobs.
- Retrieval helpers should be fast and typed (vision/smell/touch/sound/time).
- Keep schemas compact and version them if they evolve (e.g., "v": "1").

Traceability-Lite
-----------------
- REQ-BIND-02: Bindings may hold `engrams` pointers (not heavy content).
- REQ-PERS-09: Engram pointers should be JSON-serializable (autosave compatibility).
"""

from __future__ import annotations
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import uuid

__version__ = "0.1.0"
__all__ = ["ColumnMemory", "mem", "__version__"]


try:
    from cca8_features import FeaturePayload, FactMeta, TensorPayload  #pylint:disable=unused-import
except ImportError as e:
    raise RuntimeError("Place cca8_features.py alongside column01_patched.py") from e

@dataclass
class ColumnMemory:
    """Stores this column's engrams (facts/scenes/etc.) in RAM.
    Returns a stable engram_id for each assertion so the world_graph can
    point to it without copying heavy payloads.
    """
    name: str = "column01"
    _store: Dict[str, dict] = field(default_factory=dict)


    def assert_fact(self, name: str, payload: FeaturePayload, meta: Optional[FactMeta] = None) -> str:
        """Record a new engram and return its id.
        Adds created_at (ISO-8601), version 'v', and ensures meta.attrs exists.
        """
        engram_id = uuid.uuid4().hex
        meta_dict: Dict[str, Any] = meta.as_dict() if meta else {"name": name}
        # ensure attrs exists and annotate the column name
        attrs = meta_dict.get("attrs")
        if not isinstance(attrs, dict):
            attrs = {}
            meta_dict["attrs"] = attrs
        attrs.setdefault("column", self.name)
        meta_dict.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))

        record = {
            "id": engram_id,
            "name": name,
            "payload": payload,
            "meta": meta_dict,
            "v": "1",
        }
        self._store[engram_id] = record
        return engram_id

    def exists(self, engram_id: str) -> bool:
        """True if an engram id is present."""
        return engram_id in self._store

    def try_get(self, engram_id: str) -> Optional[dict]:
        """Return the record or None; unlike get(), never raises."""
        return self._store.get(engram_id)

    def delete(self, engram_id: str) -> bool:
        """Remove an engram if present. Returns True if removed."""
        return self._store.pop(engram_id, None) is not None

    def list_ids(self, limit: Optional[int] = None) -> List[str]:
        """Return known engram ids (optionally capped)."""
        ids = list(self._store.keys())
        return ids[:limit] if isinstance(limit, int) else ids

    def find(self, *, name_contains: Optional[str] = None,
             epoch: Optional[int] = None, has_attr: Optional[str] = None,
             limit: Optional[int] = None) -> List[dict]:
        """Light search over records by name substring / epoch / attr key."""
        out: List[dict] = []
        needle = (name_contains or "").lower()
        for rec in self._store.values():
            if needle and needle not in (rec.get("name") or "").lower():
                continue
            if epoch is not None:
                attrs = rec.get("meta", {}).get("attrs", {})
                if not (isinstance(attrs, dict) and attrs.get("epoch") == epoch):
                    continue
            if has_attr:
                attrs = rec.get("meta", {}).get("attrs", {})
                if not (isinstance(attrs, dict) and has_attr in attrs):
                    continue
            out.append(rec)
            if isinstance(limit, int) and len(out) >= limit:
                break
        return out

    def count(self) -> int:
        """Number of engrams in memory."""
        return len(self._store)

    def get(self, engram_id: str) -> dict:
        """Return the full record for this engram (payload + meta)."""
        return self._store[engram_id]

# Default, module-level memory instance for convenience.
mem = ColumnMemory(name="column01")
