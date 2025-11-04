# -*- coding: utf-8 -*-
"""
CCA8 Feature schemas/utilities
cca8_features.py

Purpose
-------
Provide compact, typed helpers to build engram payloads/pointers:
- small numeric vectors, categorical tags, timestamps, source channel
- minimal schemas so engrams are quick to serialize/deserialize

"""
# --- Pragmas and Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
from typing import Protocol, Any, ClassVar, Optional
from dataclasses import dataclass
import struct
from array import array


# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
# --none at this time at program startup --



# --- Public API index, version, global variables and constants -------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.2.0"
__all__ = ["FeaturePayload", "TensorPayload", "FactMeta", "__version__"]


# --- Module Code  -----------------------------------------------------------------------

#pylint: disable=missing-function-docstring
class FeaturePayload(Protocol):
    """Typed payload interface for column engrams.
    Implementations may be tensors, sparse graphs, contours, etc.

    In the WorldGraph, bindings can hold embeddings/sensory features that are
    stored in the columns rather than as tags in the graph itself. Instead of
    coupling to one concrete class, we define a protocol (the *shape* a payload
    must have): attributes **kind**, **fmt**, **shape**, and three methods.

    This keeps callers flexible so in the future **we can add** new payload
    types (images, audio, sparse vectors, etc.) without changing APIs. In
    ``cca8_column.ColumnMemory.assert_fact(...)`` the payload parameter is typed
    as FeaturePayload; the Column stores ``{id, name, payload, meta}`` and
    returns an engram_id, while the WorldGraph keeps a lightweight pointer in
    ``binding.engrams``.

    The methods define the **serialization contract**:
      • ``to_bytes()/from_bytes()`` for portable **serialization** (storage/transport)
      • ``meta()`` returns a JSON-safe descriptor (kind/fmt/shape/len) that UIs
        can use without **decoding the** whole payload.

    **Note (Nov 2025)** — This is a protocol (a static typing interface), not a
    base class; protocols are not instantiable. The return annotation of
    ``from_bytes`` indicates the **type of the result** (i.e., an object that
    satisfies FeaturePayload), not recursion.

    """

    kind: str              # e.g., "scene", "edges", "embedding", "contours"
    fmt: str               # e.g., "tensor/list-f32", "sparse/csr", "graph/adjlist"
    shape: tuple[int, ...] # tensor-like

    def to_bytes(self) -> bytes: ...
    @classmethod
    def from_bytes(cls, data: bytes) -> "FeaturePayload": ...
    def meta(self) -> dict[str, Any]: ...


#pylint: enable=missing-function-docstring
@dataclass
class TensorPayload:
    """Flexible container for dense numeric features (float32 semantics).

    The CCA8 has a symbolic WorldGraph but often needs to attach perceptual evidence (vectors) to episodes or
     facts. This class gives a tiny, dependency-free way to store embeddings as engrams in the Column. Also,
     gives us the ability to round-trip those vectors to the network/disk compactly without NumPy, and to describe
     them to the user interface. In the future, we can run similarity operations (e.g., cosine) for analysis methods.

    It is used in ColumnMemory.
    The Column returns an engram_id. The WorldGraph keeps a lightweight pointer to that engram on the relevant binding.

    This is a dataclass with the following fields (which act parameters and then attributes when instantiated):
        - data: flat list of floats
        - shape: logical tensor shape  e.g., (768, ) for a text/vision embedding
        - kind: str, default "embedding"
        - fmt: descriptors for downstream tools, default "tensor/list-f32"

    vocab notes:
     -"tensor" used here is essentially a generalization of 1-D vectors and 2-D matrices to any number of dimensions N-D
     -"float tensors" -- thus N-D of floats
     -"dense float tensor" means most (or all) of the floats in this N-D tensor have meaningful, non-zero values
      ("sparse tensor" would be the opposite, where most of the values are zero)
     -"1-D embedding dense float tensor" -- single vector filled with decimal values, typically representing a complex item,
         e.g., a 1-D embedding of a word in a vocabulary
     - 1-D array == a Vector (a 1-D Tensor)
       2-D array == a Matrix (a 2-D Tensor)
       N-D array == a General Tensor (a N-D Tensor)
     - [[1, 2, 3], [4, 5, 6], [7, 8, 9]] is a 3x3 Matrix == 2-D array/tensor == require 2 indices to access
     - a 2x2x2 structure is actually a 3-D tensor == require 3 indices to access
         e.g., [ [[1, 2],[3, 4]], [[5, 6],[7, 8]] ]  e.g., [1][0][1] is the element 6

    TensorPayload can be thought of as the "bag of numbers" we send to the Column when we want to store or
      move dense numeric features around the CCA8.
    It essentially is a small, concrete implementation of FeaturePayload interface above for dense float tensors,
      albeit most often 1-D embeddings.

    Typical usage in the CCA8:
    1. perception (or a stub) produces a vector v .
    2. wrap it: payload = TensorPayload(data=v, shape=len(v),)) .
    3. assert: eid = mem.assert_fact("vision:scene", payload, meta=FactMeta(...)) .
    4. link to the graph: store eid on the binding that the policy just wrote
    5. later retrieval/analysis: load payloads from Column, compare by cosine, display meta() in snapshots

    """
    data: list[float]
    shape: tuple[int, ...]
    kind: str = "embedding"
    fmt: str = "tensor/list-f32"

    _MAGIC: ClassVar[bytes] = b"TPAY\x00"
    _VER: ClassVar[int] = 1

    def to_bytes(self) -> bytes:
        """Serialize to a compact binary format.

        -We build the header with struct.pack and the settings below
        -After the header the body is just contiguous float32 values which array('f')
          allows efficient write/read

        Layout (little-endian):
          MAGIC(5) | VER(u32) | NDIMS(u32) | DIMS[NDIMS](u32…) | DATA(float32…)

        - Header uses `struct.pack` with '<I' fields.
        - DATA uses `array('f', data).tobytes()` for float32 semantics.
        Returns the concatenated header+body bytes.

        note -- python array.array() mirrors a low-level C array and is thus often
          used as a thin-wrapper over C arrays for reading and writing data
                we specify a single data type float ("f")
                tobytes() converts to bytes, e.g., #b'\x9a\x99...'
        """
        ndims = len(self.shape)
        header = self._MAGIC + struct.pack("<I", self._VER) + struct.pack("<I", ndims)
        header += struct.pack("<" + "I" * ndims, *self.shape)
        arr = array("f", self.data)
        body = arr.tobytes()
        return header + body

    @classmethod
    def from_bytes(cls, data: bytes) -> "TensorPayload":
        """Decode bytes produced by :meth:`to_bytes`.

        Validates MAGIC and version, reads NDIMS and DIMS from the header,
        then reconstructs the float32 payload via array('f').frombytes(...) .
        Returns a new `TensorPayload` with `data` list and `shape` tuple.
        Raises `ValueError` on bad magic or unsupported version.

        note -- python array.array() mirrors a low-level C array and is thus often
          used as a thin-wrapper over C arrays for reading and writing data
                we specify a single data type float ("f")
                tobytes() converts to bytes, e.g., #b'\x9a\x99...'
                fromtypes() converts back to float values
             -- note many of the methods that operate on arrays below
                e.g., tolist(), etc...
             -- memoryview() is built-in object that allows access/slices of huge, raw
          data items without making any copies, thus, quite efficient
                note that writing it (but not reading it) will mutate the original object
        """
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
        """Lightweight descriptor for indexing and logging.

        Returns:
          dict with keys: 'kind', 'fmt', 'shape', 'len' (number of scalars).
        Useful when you need to describe a payload without decoding bytes.
        """
        return {"kind": self.kind, "fmt": self.fmt, "shape": self.shape, "len": len(self.data)}


@dataclass
class FactMeta:
    """Compact, human-readable summary that travels with an engram.
    Heavy payload stays inside the column. The graph only needs this summary.

    FactMeta is essentially a lightweight descriptor for an engram being stored in
      the Column. It is payload-centric -- it tells us what the engram represents and how to
      index/filter in the Column space.
      e.g., assert a fact like "vision:scene" with a TensorPayload embedding, then FactMeta
        will ride along to say what this thing is and how to find/group it later, thereby
        obviating the need to open the big numeric payload

    vocab note -- the term "JSON-safe" is used in many places in the comments/docstring of the CCA8 codebase.
       -JSON-safe means that it can be encoded/decoded to/from JSON without losing info or causing errors.
       -Note below that FactMeta is indeed JSON-safe.
       -JSON is a collection of key-value pairs termed an "Object" and represented by {} .
       -the keys must be strings "some_string" but the values can be strings, numbers, bools, arrays, objects, null .
       -if a value is, e.g., NaN, Infinity, set, immutable tuple, datetime, custom classes, binary data, e.g, images, etc,
           then this is not supported and won't be JSON-safe.
       -must start and end with braces, and key:value pairs must be separated with commas .
       -e.g., have apple=22, orange=55  --> JSON form:  {"apple": 22, "orange": 55}

    This is a dataclass. Thus the fields act as a parameters and once instantiated become attributes.
        name: str -- a concise, queryable label for the fact  e.g., "vision:scene" .
        links: Optional[list[str]] = None
          -- these are optional cross-references, usually WorldGraph binding IDs or other engram IDs
            that this payload is about.
          -- very useful to allow us to hop from a Column record back to the graph episode that created
            or used it.
        attrs: Optional[dict[str, Any]] = None --freeform, JSON-safe

    FactMeta is used in cca8_column.ColumnMemory.assert_fact(name, payload, meta=FactMeta(...))
      -at this time of writing; future usage will be expanded
      -the Column stores {id, name, payload, meta} and returns an engram_id.
      -the WorldGraph does not have the rich data the Column has -- only a pointer to that engram_id .
      -it is possible to list Column facts by name, group by attrs["model"], jump via links back to the
          producing binding -- without decoding the vector

    If you're assembling a FactMeta boject explicitly, add time with .with_time(ctx)
    e.g.:
        from cca8_column import mem
        from cca8_features import TensorPayload, FactMeta

        payload = TensorPayload(data=vec, shape=(len(vec),))
        fm      = FactMeta(name="vision:silhouette:mom", links=[latest_binding_id]).with_time(ctx)
        eid     = mem.assert_fact("vision:silhouette:mom", payload, fm)

        # (optional) then attach the pointer to a binding
        world.attach_engram(latest_binding_id, column="column01", engram_id=eid, act=1.0)


    """
    name: str
    links: Optional[list[str]] = None   # references to world_graph tokens
    attrs: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        """Canonical JSON-safe view with defaults applied.

        Note that the code below simply returns the name, links and attrs values in the
         format of "name_of_field":value_of_attribute, i.e., JSON format
        Ensures:
          - 'links' is a list (defaults to [])
          - 'attrs' is a dict (defaults to {})
        """
        return {"name": self.name, "links": self.links or [], "attrs": self.attrs or {}}

    def with_time(self, ctx: Any) -> "FactMeta":
        """Return a new FactMeta with {'ticks','tvec64'} merged into attrs if present on ctx.
        """
        a = dict(self.attrs or {})
        ta = time_attrs_from_ctx(ctx)
        if ta:
            a.update(ta)
        return FactMeta(name=self.name, links=list(self.links or []), attrs=a)


def time_attrs_from_ctx(ctx: Any) -> dict[str, Any]:
    """Return {'ticks': int, 'tvec64': str, 'epoch', 'epoch_vhash64'} from ctx if available; else {}.

    Purpose
    -------
    Let column engrams mirror the runner/controller time context so you
    can correlate Column records with WorldGraph events later without
    decoding heavy payloads.

    Notes
    -----
    - ctx.ticks is an int tick counter in the runner.
    - ctx.tvec64() is a 64-bit sign-bit hash of the TemporalContext vector.
    """
    out: dict[str, Any] = {}
    t = getattr(ctx, "ticks", None)
    if isinstance(t, int):
        out["ticks"] = t
    h = getattr(ctx, "tvec64", None)
    if callable(h):
        try:
            hv = h()
            if isinstance(hv, str):
                out["tvec64"] = hv
        except Exception:
            pass

    # Epoch info (for Column records)
    bno = getattr(ctx, "boundary_no", None)
    if isinstance(bno, int):
        out["epoch"] = bno
    bvh = getattr(ctx, "boundary_vhash64", None)
    if isinstance(bvh, str):
        out["epoch_vhash64"] = bvh

    return out
