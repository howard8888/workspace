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
# Minimal column module with ColumnMemory, as per ADR-001.
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import uuid

__version__ = "0.1.0"

try:
    from cca8_features import FeaturePayload, FactMeta, TensorPayload  # noqa: F401
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
        """Record a new engram and return its id."""
        engram_id = uuid.uuid4().hex
        record = {
            "id": engram_id,
            "name": name,
            "payload": payload,
            "meta": meta.as_dict() if meta else {"name": name},
        }
        self._store[engram_id] = record
        return engram_id

    def get(self, engram_id: str) -> dict:
        """Return the full record for this engram (payload + meta)."""
        return self._store[engram_id]

# Default, module-level memory instance for convenience.
mem = ColumnMemory(name="column01")
