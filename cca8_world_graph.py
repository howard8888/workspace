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
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Set, Optional
import itertools


# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

@dataclass
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
    edges: List[dict]
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
    """Directed episode graph for predicates (facts) and weakly causal edges.

    Key operations:
        - ensure_anchor(name): create/get special timeline nodes (e.g., "NOW").
        - add_predicate(token, ...): create a Binding that carries 'pred:<token>'.
        - add_edge(src_id, dst_id, label, meta=None): link two bindings.
        - plan_to_predicate(src_id, token): BFS path to first binding with 'pred:<token>'.

    Design notes:
        - We keep the symbolic layer tiny and fast; engrams carry the heavy payloads.
        - Edges express *episode* causality (not logical necessity).
        - The planner is intentionally simple (BFS) and replaceable later.
    """

    def __init__(self) -> None:
        self._bindings: Dict[str, Binding] = {}
        self._anchors: Dict[str, str] = {}           # name -> binding_id
        self._latest_binding_id: Optional[str] = None
        self._id_counter = itertools.count(1)

    # ------------------------- internals -------------------------

    def _next_id(self) -> str:
        return f"b{next(self._id_counter)}"

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

    def add_predicate(
        self,
        token: str,
        *,
        attach: Optional[str] = None,
        meta: Optional[dict] = None,
        engrams: Optional[dict] = None,
    ) -> str:
        """Create a binding that carries the predicate token.

        Args:
            token: Predicate token like "state:posture_standing".
            attach: One of {"now", "latest", "none"} (case-insensitive):
                - "now":    auto-create an edge from the NOW anchor to this binding.
                - "latest": if a previous binding exists, edge from latest -> this.
                - "none"/None: no auto-edge.
            meta: Provenance/context to store on the binding (e.g., {"policy": "policy:stand_up"}).
            engrams: Optional pointer dict into column memory.

        Returns:
            The new binding id (e.g., "b152").
        """
        # normalize attach
        att = (attach or "none").lower()
        if att not in {"now", "latest", "none"}:
            raise ValueError("attach must be one of {'now','latest','none'}")

        # create binding
        tags = {f"pred:{token}"}
        bid = self.add_binding(tags=tags, meta=meta, engrams=engrams)

        # optional auto-attachment
        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, "then")
        elif att == "latest":
            if self._latest_binding_id and self._latest_binding_id != bid:
                self.add_edge(self._latest_binding_id, bid, "then")

        return bid

    # --------------------------- edges ---------------------------

    def add_edge(self, src_id: str, dst_id: str, label: str, meta: Optional[dict] = None) -> None:
        """Add a directed edge from src->dst with a label like 'then' and optional meta."""
        if src_id not in self._bindings or dst_id not in self._bindings:
            raise KeyError(f"unknown binding id: {src_id!r} or {dst_id!r}")
        self._bindings[src_id].edges.append(
            {"to": dst_id, "label": label, "meta": dict(meta or {})}
        )

    # -------------------------- planning -------------------------

    def plan_to_predicate(self, src_id: str, token: str) -> Optional[List[str]]:
        """BFS from src_id to the first binding that carries 'pred:<token>'.

        Returns:
            List of binding ids forming a path, or None if not found.
        """
        if src_id not in self._bindings:
            return None

        target_tag = f"pred:{token}"
        # Quick check: if source already satisfies the predicate
        if target_tag in self._bindings[src_id].tags:
            return [src_id]

        q = deque([src_id])
        visited = {src_id}
        parent: Dict[str, Optional[str]] = {src_id: None}

        while q:
            cur = q.popleft()
            # expand
            for e in self._bindings[cur].edges:
                nxt = e.get("to")
                if not nxt or nxt in visited:
                    continue
                visited.add(nxt)
                parent[nxt] = cur

                # goal test
                if target_tag in self._bindings[nxt].tags:
                    # reconstruct path
                    path = [nxt]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])  # type: ignore
                    path.reverse()
                    return path
                q.append(nxt)

        return None

    # ------------------------- persistence -----------------------

    def to_dict(self) -> dict:
        """Serialize the whole world for autosave."""
        return {
            "bindings": {bid: b.to_dict() for bid, b in self._bindings.items()},
            "anchors": dict(self._anchors),
            "latest": self._latest_binding_id,
            "version": "0.1",
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
            g._id_counter = itertools.count(mx + 1)

        return g
