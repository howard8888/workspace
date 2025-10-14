# -*- coding: utf-8 -*-
"""
CCA8 World Graph (episode index)

This module implements the *symbolic episode index* for CCA8.

Mental model:
- **Predicate**: a symbolic fact token, e.g., "state:posture_standing".
- **Binding**: a *node instance* that carries a predicate tag (plus meta & engrams).
- **Edge**: a directed link between bindings with a label (e.g., "then") expressing
  weak/soft causality ("in this episode, this led to that").

Why this exists:
- The WorldGraph is a *fast index & planner substrate* (~5% of information).
- Rich content lives in column **engrams** (~95%), and bindings can point to them.
- Planning is simple BFS over binding edges to a target predicate tag.

Persistence:
- `to_dict()` / `from_dict()` serialize/restore an episode (bindings, anchors, latest).
- ID format is "b<N>"; `from_dict()` advances the internal counter to avoid collisions.

 --- Navigator --------------------------------------------------------------------
 Data model:
   Binding(id, tags, edges, meta, engrams)
     - tags must contain exactly one 'pred:<token>' for facts, or 'anchor:<name>' for anchors
     - edges: [{'to': 'bN', 'label': 'then', 'meta': {...}}, ...]
 Invariants:
   - ids are 'b1','b2',... (monotonic)
   - ONE 'NOW' anchor exists when ensure_anchor('NOW') is called
   - stored tokens always use a single 'pred:' prefix
 Public entry points:
   - ensure_anchor, add_predicate, add_edge, plan_to_predicate, to_dict/from_dict
 Read-only helpers added below keep runner code simple and consistent.

"""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Set, Optional, TypedDict


# --- Public API index and version, constants -------------------------------------------------
__version__ = "0.1.1"
__all__ = ["Binding", "WorldGraph", "Edge", "__version__"]


PRED_PREFIX = "pred:"
_ATTACH_OPTIONS: Set[str] = {"now", "latest", "none"}

# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

class Edge(TypedDict):
    #more precise typing of edges in class Binding
    to: str
    label: str
    meta: dict

@dataclass(slots=True)
class Binding:
    """One node in the episode graph.

    Attributes:
        id: Stable binding id, e.g., "b152".
        tags: A set of string tags; *must* include at least one 'pred:<token>' tag
              for predicate-carrying nodes, or 'anchor:<name>' for anchors.
        edges: Outgoing links: [{"to": "b153", "label": "then", "meta": {...}}, ...].
        meta: Arbitrary provenance/context (e.g., {"policy": "policy:stand_up", "created_at": "..."}).
        engrams: Attachments/pointers into column memory (see cca8_column); small dict.
    """
    id: str
    tags: Set[str]
    edges: List[Edge] #e.g. [{"to": "b153", "label": "then", "meta": {...}}, ...]
    meta: dict
    engrams: dict

    def to_dict(self) -> dict:
        """JSON-safe representation for persistence."""
        return {
            "id": self.id,
            "tags": sorted(self.tags),
            "edges": [dict(e) for e in self.edges],
            "meta": dict(self.meta),
            "engrams": dict(self.engrams),
        }

    @staticmethod
    def from_dict(d: dict) -> "Binding":
        """Rehydrate a Binding from its serialized form."""
        return Binding(
            id=d["id"],
            tags=set(d.get("tags", [])),
            edges=[dict(e) for e in d.get("edges", [])],
            meta=dict(d.get("meta", {})),
            engrams=dict(d.get("engrams", {})),
        )


# -----------------------------------------------------------------------------
# World graph
# -----------------------------------------------------------------------------

class WorldGraph:
    """Directed episode graph for predicates (facts) and weakly causal ('then') edges.

    Key operations:
        - ensure_anchor(name): create/get special timeline nodes (e.g., "NOW").
        - add_predicate(token, ...): create a Binding that carries 'pred:<token>'.
        - add_edge(src_id, dst_id, label, meta=None): link two bindings.
        - plan_to_predicate(src_id, token): BFS path to first binding with 'pred:<token>'.

    Design notes:
        - We keep the symbolic layer tiny and fast; engrams carry the heavy payloads.
        - Edges express *episode* causality (not logical necessity).
        - The planner is intentionally simple (BFS) and replaceable later.

    Invariants:
        - Each predicate binding has exactly one 'pred:<token>' tag.
        - Anchor bindings carry 'anchor:<name>' and live in self._anchors (e.g., 'NOW').
        - Binding ids are 'b1', 'b2', ... and never reused.
        - 'attach="latest"' links the previous 'latest' binding -> newly created one.

    The API offers: ensure_anchor, add_predicate, add_edge, plan_to_predicate,
         and full serialization via to_dict()/from_dict().

    """

    def __init__(self) -> None:
        """Initializes an empty episode graph
        ids are b1, b2, .... via an internal counter
        """
        self._bindings: Dict[str, Binding] = {}
        self._anchors: Dict[str, str] = {}           # name -> binding_id
        self._latest_binding_id: Optional[str] = None
        self._id_next: int = 1                      # was: itertools.count(1)

    # ------------------------- internals -------------------------

    def _next_id(self) -> str:
        """Return the next binding id as 'b<N>' using the internal counter."""
        nid = self._id_next
        self._id_next += 1
        return f"b{nid}"

    # ------------------------- anchors ---------------------------

    def ensure_anchor(self, name: str) -> str:
        """Ensure a named anchor binding exists (e.g., 'NOW') and return its id.

        Anchors are special attachment points in the episode timeline (start points for plans).
        """
        if name in self._anchors:
            return self._anchors[name]
        bid = self._next_id()
        b = Binding(id=bid, tags={f"anchor:{name}"}, edges=[], meta={}, engrams={})
        self._bindings[bid] = b
        self._anchors[name] = bid
        # latest may remain whatever last predicate node was; anchor creation doesn't change latest
        return bid

    # ------------------------- creation --------------------------

    def add_binding(
        self,
        tags: Set[str],
        meta: Optional[dict] = None,
        engrams: Optional[dict] = None,
    ) -> str:
        """Create a new Binding node with given tags/meta/engrams. Returns the id.

        Note:
            Use `add_predicate(token, ...)` for the common case so the 'pred:' tag is standardized.
        """
        bid = self._next_id()
        b = Binding(
            id=bid,
            tags=set(tags),
            edges=[],
            meta=dict(meta or {}),
            engrams=dict(engrams or {}),
        )
        self._bindings[bid] = b
        self._latest_binding_id = bid
        return bid

    def add_predicate(self, token: str, *, attach: Optional[str] = None, meta: Optional[dict] = None, engrams: Optional[dict] = None) -> str:
        """Create a new predicate binding and optionally auto-link it.

        Args:
            token: Predicate token. Accepts either "<token>" or "pred:<token>".
                   We normalize so the stored tag is always "pred:<token>" (no double "pred:").
                   Examples: "state:posture_standing", "action:push_up", "vision:silhouette:mom".
            attach: If "now", link NOW → new. If "latest", link <previous latest> → new.
                    If None or "none", no auto-link is added.
            meta:   Optional provenance dictionary to store on the binding.
            engrams:Optional engram attachments (small dict).

        Returns:
            The new binding id (e.g., "b42").
        """
        # --- normalize token to a single 'pred:' prefix --------------------------------
        tok = (token or "").strip()
        if tok.startswith("pred:"):
            tok = tok[5:]
        tag = f"pred:{tok}"

        # --- validate attach option -----------------------------------------------------
        att = (attach or "none").lower()
        if att not in _ATTACH_OPTIONS:  # e.g., {"now", "latest", "none"}
            raise ValueError(f"attach must be one of {_ATTACH_OPTIONS!r}")

        # --- allocate id and construct the binding ---
        prev_latest = self._latest_binding_id         # keep BEFORE we change it
        bid = self._next_id()
        b = Binding(
            id=bid,
            tags={tag},
            edges=[],
            meta=dict(meta) if meta else {},
            engrams=dict(engrams) if engrams else {},
        )
        self._bindings[bid] = b
        self._latest_binding_id = bid

        # --- optional auto-linking ---
        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, "then", meta or {})
        elif att == "latest" and prev_latest and prev_latest in self._bindings:
            # link from the binding that was 'latest' BEFORE creating this one
            self.add_edge(prev_latest, bid, "then", meta or {})

        return bid

    # --------------------------- edges ---------------------------

    def add_edge(self, src_id: str, dst_id: str, label: str, meta: Optional[dict] = None) -> None:
        """Add a directed edge from src->dst with a label like 'then' and optional meta.

        Raises:
            KeyError: if either binding id is unknown.
        """
        if src_id not in self._bindings or dst_id not in self._bindings:
            raise KeyError(f"unknown binding id: {src_id!r} or {dst_id!r}")
        self._bindings[src_id].edges.append(
            {"to": dst_id, "label": label, "meta": dict(meta or {})}
        )

    # -------------------------- planning -------------------------

    def _reconstruct_path(self, parent: Dict[str, Optional[str]], goal: str) -> List[str]:
        """Rebuild a path from parent links (goal back to source)."""
        path: List[str] = []
        cur: Optional[str] = goal
        while cur is not None:
            path.append(cur)
            cur = parent.get(cur)
        path.reverse()
        return path

    def plan_to_predicate(self, src_id: str, token: str) -> Optional[List[str]]:
        """Breadth-first search from src_id to the first binding that carries the target predicate.

        Args:
            src_id: Starting binding id (e.g., "b1").
            token: Predicate token to search for. May be given as "pred:<token>" or just "<token>".

        Returns:
            A list of binding ids forming a path from src_id to the goal (inclusive), or None if no path.

        Notes:
            - This traverses all outgoing edges (label-agnostic).
            - If the source already carries the predicate, returns [src_id].
            - Uses _reconstruct_path(parent, goal) to rebuild the path once the goal is found.
        """
        # Normalize the tag we are searching for
        token = (token or "").strip()
        target_tag = token if token.startswith("pred:") else f"pred:{token}"

        # Quick checks
        if not src_id or src_id not in self._bindings:
            return None
        if target_tag in self._bindings[src_id].tags:
            return [src_id]

        q: deque[str] = deque([src_id])
        parent: Dict[str, Optional[str]] = {src_id: None}
        visited: Set[str] = {src_id}

        while q:
            cur = q.popleft()
            cur_binding = self._bindings.get(cur)
            if not cur_binding:
                continue  # defensive; shouldn't happen

            # Explore neighbors
            for e in cur_binding.edges:
                nxt = e.get("to")
                if not nxt or nxt in visited or nxt not in self._bindings:
                    continue

                visited.add(nxt)
                parent[nxt] = cur

                # Goal test: does this neighbor carry the predicate?
                if target_tag in self._bindings[nxt].tags:
                    return self._reconstruct_path(parent, nxt)

                q.append(nxt)

        # No path found
        return None

        # --- Read-only helpers (for clarity; no behavior change) --------------

    def get_binding(self, bid: str) -> Optional["Binding"]:
        """Return the binding by id, or None if missing."""
        return self._bindings.get(bid)

    def num_bindings(self) -> int:
        """Total number of bindings in the graph."""
        return len(self._bindings)

    def num_edges(self) -> int:
        """Total number of outgoing edges in the graph."""
        return sum(len(b.edges) for b in self._bindings.values())

    def get_anchor(self, name: str) -> Optional[str]:
        """Return the binding id for a named anchor, if present (e.g., 'NOW')."""
        return self._anchors.get(name)

    def bindings_with_tag(self, tag: str) -> Set[str]:
        """Return ids of all bindings that carry the exact tag (e.g., 'pred:stand')."""
        return {bid for bid, b in self._bindings.items() if tag in b.tags}

    def has_tag(self, tag: str) -> bool:
        """True if any binding carries the exact tag."""
        return any(tag in b.tags for b in self._bindings.values())

    def list_predicates(self, limit: Optional[int] = None) -> List[str]:
        """Unique sorted predicate tokens present (without 'pred:')."""
        preds = []
        seen = set()
        for b in self._bindings.values():
            for t in b.tags:
                if t.startswith(PRED_PREFIX):
                    tok = t[len(PRED_PREFIX):]
                    if tok not in seen:
                        seen.add(tok); preds.append(tok)
        preds.sort()
        return preds[:limit] if limit else preds

    def last_n_bindings(self, n: int = 5) -> List[str]:
        """Return up to N most recent ids by numeric order (bK ... bN)."""
        # reconstruct from the highest numeric id we have
        ids = sorted(
            (int(bid[1:]) for bid in self._bindings if bid.startswith("b")),
            reverse=True,
        )
        take = [f"b{i}" for i in ids[:max(0, n)]]
        take.reverse()  # chronological
        return take

    def neighbors(self, bid: str, label: Optional[str] = None) -> List[str]:
        """Return ids of direct neighbors from 'bid' (optionally filtered by label)."""
        b = self._bindings.get(bid)
        if not b:
            return []
        if label is None:
            return [e.get("to") for e in b.edges if e.get("to")]
        return [e.get("to") for e in b.edges if e.get("to") and e.get("label") == label]

    def stats_text(self) -> str:
        """Human-readable one-liner of graph stats (nice in the runner)."""
        nb = self.num_bindings()
        ne = self.num_edges()
        na = len(self._anchors)
        return f"WorldGraph: bindings={nb}, edges={ne}, anchors={na}"


    # ------------------------- persistence -----------------------

    def to_dict(self) -> dict:
        """Serialize the whole world for autosave."""
        return {
            "bindings": {bid: b.to_dict() for bid, b in self._bindings.items()},
            "anchors": dict(self._anchors),
            "latest": self._latest_binding_id,
            "version": "schema",
        }


    @classmethod
    def from_dict(cls, data: dict) -> "WorldGraph":
        """Restore a world from autosave and advance the id counter to avoid collisions."""
        g = cls()
        g._bindings = {bid: Binding.from_dict(b) for bid, b in data.get("bindings", {}).items()}
        g._anchors = dict(data.get("anchors", {}))
        g._latest_binding_id = data.get("latest")

        # Advance the id counter past the max numeric suffix to avoid collisions
        if g._bindings:
            try:
                mx = max(int(bid[1:]) for bid in g._bindings if bid.startswith("b"))
            except ValueError:
                mx = 0
            g._id_next = mx + 1          # was: itertools.count(mx + 1)
        else:
            g._id_next = 1

        return g
