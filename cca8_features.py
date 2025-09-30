# -*- coding: utf-8 -*-

"""
CCA8 Feature schemas/utilities

Purpose
-------
Provide compact, typed helpers to build engram payloads/pointers:
- small numeric vectors, categorical tags, timestamps, source channel
- minimal schemas so engrams are quick to serialize/deserialize

Guidelines
----------
- Prefer fixed small structures (dicts/lists of primitives) over large objects.
- Avoid heavyweight libs here; this is a hot path for many small ops.
- Validate shapes at the boundary (raise ValueError with clear messages).

Traceability-Lite
-----------------
- REQ-BIND-02: Feature helpers produce JSON-safe pieces for engrams.
- REQ-PERS-09: Keep structures stable; bump minor "schema" keys if needed.
"""

from __future__ import annotations
from typing import Protocol, Any, ClassVar, Optional
from dataclasses import dataclass
import struct
from array import array

# in cca8_features.py
__version__ = "0.1.0"

class FeaturePayload(Protocol):
    """Typed payload interface for column engrams.
    Implementations may be tensors, sparse graphs, contours, etc.
    """
    kind: str              # e.g., "scene", "edges", "embedding", "contours"
    fmt: str               # e.g., "tensor/list-f32", "sparse/csr", "graph/adjlist"
    shape: tuple[int, ...] # tensor-like; else () or None

    def to_bytes(self) -> bytes: ...
    @classmethod
    def from_bytes(cls, data: bytes) -> "FeaturePayload": ...
    def meta(self) -> dict[str, Any]: ...

@dataclass
class TensorPayload:
    """Flexible container for dense numeric features (float32 semantics).

    - data: flat list of floats
    - shape: logical tensor shape
    - kind/fmt: descriptors for downstream tools
    """
    data: list[float]
    shape: tuple[int, ...]
    kind: str = "embedding"
    fmt: str = "tensor/list-f32"

    _MAGIC: ClassVar[bytes] = b"TPAY\x00"
    _VER: ClassVar[int] = 1

    def to_bytes(self) -> bytes:
        ndims = len(self.shape)
        header = self._MAGIC + struct.pack("<I", self._VER) + struct.pack("<I", ndims)
        header += struct.pack("<" + "I" * ndims, *self.shape)
        arr = array("f", self.data)
        body = arr.tobytes()
        return header + body

    @classmethod
    def from_bytes(cls, data: bytes) -> "TensorPayload":
        mv = memoryview(data)
        if mv[:5].tobytes() != cls._MAGIC:
            raise ValueError("Bad magic for TensorPayload")
        off = 5
        ver = struct.unpack_from("<I", mv, off)[0]; off += 4
        if ver != cls._VER:
            raise ValueError(f"Unsupported version {ver}")
        ndims = struct.unpack_from("<I", mv, off)[0]; off += 4
        dims = struct.unpack_from("<" + "I" * ndims, mv, off); off += 4 * ndims
        float_bytes = mv[off:].tobytes()
        arr = array("f"); arr.frombytes(float_bytes)
        data_list = arr.tolist()
        return cls(data=data_list, shape=tuple(int(d) for d in dims))

    def meta(self) -> dict[str, Any]:
        return {"kind": self.kind, "fmt": self.fmt, "shape": self.shape, "len": len(self.data)}

@dataclass
class FactMeta:
    """Compact, human-readable summary that travels with an engram.
    Heavy payload stays inside the column. The graph only needs this summary.
    """
    name: str
    links: Optional[list[str]] = None   # references to world_graph tokens
    attrs: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "links": self.links or [], "attrs": self.attrs or {}}
