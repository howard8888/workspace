# -*- coding: utf-8 -*-
"""
CCA8 World Graph (episode index)

This module implements the *symbolic episode index* for CCA8.
Summary of basic concepts below but see README.MD for more explanation of these concepts.

Why this exists:
- The WorldGraph is a *fast index & planner substrate* (~5% of information).
- Rich content lives in column **engrams** (~95%), and bindings can point to them.
- Planning is simple BFS over binding edges to a target predicate tag.

Explaining the terminology chosen:
- "Binding" -- indeed a node instance but binding implies the binding, i.e., association, of 
facts and pointers, much like in neuro/cog systems linking features, time  and cause into abs
coherent moment or episode; we are aiming for knowledge representation rather than just
graph topology
    -bindings can contain predicates and/or cues and/or anchors 
    (or none although not recommended -- add at least one tag if need a placeholder)
    (technically allow bindings without tags or edges, but not recommended stylistically)
    -bindings usually contain edges but can existed isolated without edges (e.g., checkpoint to be connected later, placeholders, etc)
    -see code below for structure of a binding, note that it stores id, tags, engrams, metadata, source edge data
- "Provenance" -- it documents the history or lineage of the data who/what/why
- "Metadata" -- characteristics including admin features of the data, and in our code actually includes the provenance
- "Edge" -- a standard term for link; note that we use directed edges expressing weak causality "then"
         - actions -- we usually encode as edge labels rather than as predicates
           e.g., pred:stand:alone --run-->pred:stand:mom
- "WorldGraph" -- our graph made up of bindings + directed edges
- "Tags" -- bindings have predicate and/or cue and/or anchor tags:
  "Predicate: a symbolic fact token, e.g., "state:posture_standing"
     -the reason we use this term with logic/AI heritage rather than a term like "fact" is because a fact
     implies a ground truth while a "predicate" is a symbolic claim
        e.g., "pred:standing"
     -terminology note:   "pred: x" or "cue:x"  -- x can be simple like "standing" or expanded eg, "standing:forest:north"
  "Cue" : while we plan to or target a predicate, a cue represents a current condition
     e.g., "cue:scent:milk"
  "Anchor": special bindings like NOW, actually created via e.g., self._anchors["NOW"] = "b100"

Persistence:
- `to_dict()` / `from_dict()` serialize/restore an episode (bindings, anchors, latest).
- ID format is "b<N>"; `from_dict()` advances the internal counter to avoid collisions.
"""

# --- Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Set, Optional, TypedDict
import itertools

# PyPI and Third-Party Imports
# --none at this time at program startup--

# CCA8 Module Imports
# --none at this time at program startup--

# --- Public API index and version, constants -------------------------------------------------
__version__ = "0.1.1"
__all__ = ["Binding", "WorldGraph", "Edge", "__version__"]


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

# ------------------------- Developmental Tag Lexicon -------------------------

class TagLexicon:
    """
    Constrained vocabulary for tags by developmental stage, with a small legacy map.
    - Part of implementation of Spelke's core knowledge idea, here as a contrained early lexicon
        that then unlocks richer tokens with development
    -TagLexicon that defines which tokens are allowed at each developmental stage 
       (e.g., neonate → infant → juvenile → adult), including some legacy forms for devp't ease
    -there is light enforcement in WorldGraph.add_predicate/add_cue (configurable: "allow" | "warn" | "strict");
 
    - Families: 'pred', 'cue', 'anchor'
    - Stages are cumulative: infant ⊇ neonate, juvenile ⊇ infant, etc.
    - Legacy tokens are accepted but a preferred canonical is suggested.

    This is deliberately small and focused on the newborn goat domain. Pending fuller development.
    """

    STAGE_ORDER = ("neonate", "infant", "juvenile", "adult")

    # Preferred tokens by family and stage
    BASE: dict[str, dict[str, set[str]]] = {
        "neonate": {
            "pred": {
                # posture / proximity
                "posture:standing", "posture:fallen",
                "proximity:mom:close", "proximity:mom:far",
                # feeding milestones
                "nipple:found", "nipple:latched", "milk:drinking",
                "seeking_mom",
                # action-like states we currently model as predicates
                "action:push_up", "action:extend_legs", "action:orient_to_mom",
                "stand", "action:look_around", "state:alert",
                # drives as *plannable* states, if ever used that way
                "drive:hunger_high",
            },
            "cue": {
                "vision:silhouette:mom", "scent:milk", "sound:bleat:mom",
                "vestibular:fall", "touch:flank_on_ground", "balance:lost",
                # optional cue form for drives (if used only as triggers)
                "drive:hunger_high",
            },
            "anchor": {"NOW", "HERE"},
        },
        #   can extend these as   grow the task space
        "infant":  {"pred": set(), "cue": set(), "anchor": set()},
        "juvenile":{"pred": set(), "cue": set(), "anchor": set()},
        "adult":   {"pred": set(), "cue": set(), "anchor": set()},
    }

    # Legacy → preferred (we *accept* the legacy but suggest the preferred)
    LEGACY_MAP = {
        "state:posture_standing": "posture:standing",
        "state:posture_fallen":   "posture:fallen",
        "state:seeking_mom":      "seeking_mom",
        # add more renames as   migrate
    }

    def __init__(self):
        # Build cumulative sets per stage
        self.allowed: dict[str, dict[str, set[str]]] = {}
        acc = {"pred": set(), "cue": set(), "anchor": set()}
        for stage in self.STAGE_ORDER:
            # accumulate
            for fam in ("pred", "cue", "anchor"):
                acc[fam] |= set(self.BASE.get(stage, {}).get(fam, set()))
            self.allowed[stage] = {fam: set(acc[fam]) for fam in acc}

    def is_allowed(self, family: str, token: str, stage: str) -> bool:
        """Return True if 'token' is permitted (preferred or legacy) at 'stage'."""
        # accept canonical preferred
        if token in self.allowed.get(stage, {}).get(family, set()):
            return True
        # accept legacy if we have a mapping for it
        if token in self.LEGACY_MAP:
            return True
        return False

    def preferred_of(self, token: str) -> str | None:
        """If 'token' is legacy, return its preferred canonical form, else None."""
        return self.LEGACY_MAP.get(token)

    def normalize_family_and_token(self, family: str, raw: str) -> tuple[str, str]:
        """
        Ensure the *family-local* token is returned (strip 'pred:'/'cue:' prefix if present).
        Example: ('pred', 'pred:state:posture_standing') -> ('pred', 'state:posture_standing')
        """
        tok = (raw or "").strip()
        prefix = family + ":"
        return family, tok[len(prefix):] if tok.startswith(prefix) else tok

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
        """Initializes an empty episode graph
        ids are b1, b2, .... via an internal counter
        """
        self._bindings: Dict[str, Binding] = {}
        self._anchors: Dict[str, str] = {}           # name -> binding_id
        self._latest_binding_id: Optional[str] = None
        self._id_counter = itertools.count(1)
        self._init_lexicon()
        
    # --- tag policy / developmental stage -----------------------------------

    def _init_lexicon(self):
        self._lexicon = TagLexicon()
        self._stage: str = "neonate"         # default
        self._tag_policy: str = "warn"       # 'allow' | 'warn' | 'strict'

    def set_stage(self, stage: str) -> None:
        """Set developmental stage for tag constraints ('neonate'|'infant'|'juvenile'|'adult')."""
        if stage not in TagLexicon.STAGE_ORDER:
            raise ValueError(f"Unknown stage: {stage!r}")
        self._stage = stage

    def set_stage_from_ctx(self, ctx) -> None:
        """Derive stage from ctx.age_days (toy thresholds; adjust as desired)."""
        age = float(getattr(ctx, "age_days", 0.0) or 0.0)
        stage = "neonate" if age <= 3.0 else "infant"
        self.set_stage(stage)

    def set_tag_policy(self, policy: str) -> None:
        """Set enforcement: 'allow' (off), 'warn' (default), or 'strict' (raise on out-of-lexicon)."""
        if policy not in ("allow", "warn", "strict"):
            raise ValueError("policy must be 'allow' | 'warn' | 'strict'")
        self._tag_policy = policy

    def _enforce_tag(self, family: str, token_local: str) -> str:
        """
        Enforce lexicon constraints for a single tag *without* family prefix (e.g., 'posture:standing').
        Returns the tag-local string that will be stored (we do not auto-rewrite legacy—only warn).
        """
        ok = self._lexicon.is_allowed(family, token_local, self._stage)
        if not ok:
            msg = f"[tags] {family}:{token_local} not allowed at stage={self._stage}"
            if self._tag_policy == "strict":
                raise ValueError(msg)
            elif self._tag_policy == "warn":
                print("WARN", msg, "(allowing)")
        else:
            preferred = self._lexicon.preferred_of(token_local)
            if preferred and preferred != token_local:
                # Legacy accepted but suggest canonical
                if self._tag_policy != "allow":
                    print(f"WARN [tags] legacy '{family}:{token_local}' — prefer '{family}:{preferred}' (kept legacy to avoid breakage)")
        return token_local

    # ------------------------- internals -------------------------

    def _next_id(self) -> str:
        """Return the next binding id as 'b<N>' using the internal counter."""
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
        
    def set_now(self, bid: str, *, tag: bool = True, clean_previous: bool = True) -> str | None:
        """
        Re-point the NOW anchor to an existing binding id and (optionally) keep tags tidy.

        Why this helper:
          - In CCA8, "NOW" is a temporal orientation used by the runner and planner.
            The authoritative source of truth is the anchors map: self._anchors["NOW"].
          - It's easy to forget to update the human-facing tag 'anchor:NOW' when moving NOW,
            or to leave two bindings visually tagged as NOW. This helper updates both.

        Parameters
        ----------
        bid : str
            Binding id to become the NOW anchor. Must exist in this world.
        tag : bool, default True
            If True, ensure the new NOW binding's tags include 'anchor:NOW'.
        clean_previous : bool, default True
            If True, remove 'anchor:NOW' from the old NOW binding's tags (if present).

        Returns
        -------
        prev_now : str | None
            The previous NOW binding id (if any), for logging/inspection.

        Notes
        -----
        - No-op if bid is already the NOW anchor (still ensures tag housekeeping).
        - Does not create bindings; bid must exist (raises KeyError otherwise).
        - Does not alter edges or LATEST; it only changes orientation.
        """

        if bid not in self._bindings:
            raise KeyError(f"Unknown binding id for NOW: {bid!r}")

        def _tags_of(bid_: str):
            b = self._bindings[bid_]
            ts = getattr(b, "tags", None)
            if ts is None:
                # default to a list for compatibility with existing snapshots
                b.tags = []
                ts = b.tags
            return ts

        def _tag_add(ts, t: str):
            # works for set or list
            try:
                ts.add(t)        # set
            except AttributeError:
                if t not in ts:  # list
                    ts.append(t)

        def _tag_discard(ts, t: str):
            # works for set or list
            try:
                ts.discard(t)    # set
            except AttributeError:
                try:
                    ts.remove(t) # list
                except ValueError:
                    pass

        prev = self._anchors.get("NOW")

        if clean_previous and prev and prev in self._bindings and prev != bid:
            _tag_discard(_tags_of(prev), "anchor:NOW")

        # point NOW to the new id
        self._anchors["NOW"] = bid

        if tag:
            _tag_add(_tags_of(bid), "anchor:NOW")

        return prev

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
        # enforce against lexicon (do not auto-rewrite legacy; just warn/allow)
        tok = self._enforce_tag("pred", tok)
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
        
    
    def add_cue(self, token: str, *, attach: Optional[str] = None,
            meta: Optional[dict] = None, engrams: Optional[dict] = None) -> str:
        """Create a new cue binding (tag normalized to 'cue:<token>') and optionally auto-link it.

        Use this for sensory/context evidence that policies will react to (not planning targets).
        attach: 'now' → NOW→new, 'latest' → LATEST→new, 'none'/None → no auto edge.
        """
        tok = (token or "").strip()
        if tok.startswith("cue:"):
            tok = tok[4:]
        tok = self._enforce_tag("cue", tok)
        tag = f"cue:{tok}"

        att = (attach or "none").lower()
        if att not in _ATTACH_OPTIONS:
            raise ValueError(f"attach must be one of {_ATTACH_OPTIONS!r}")

        prev_latest = self._latest_binding_id
        bid = self._next_id()
        b = Binding(
            id=bid, tags={tag}, edges=[],
            meta=dict(meta or {}), engrams=dict(engrams or {}))
        self._bindings[bid] = b
        self._latest_binding_id = bid

        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, "then", meta or {})
        elif att == "latest" and prev_latest and prev_latest in self._bindings:
            self.add_edge(prev_latest, bid, "then", meta or {})

        return bid
        
        
        
    # ------------------------- engram / signal bridge -------------------------

    def attach_engram(self, bid: str, *, column: str = "column01",
                      engram_id: str, act: float = 1.0, extra_meta: dict | None = None) -> None:
        """
        Attach an existing engram pointer to a binding.
        
        
        At this time, we We can put a thin “signal bridge” between the WorldGraph (symbols) and the column (engrams),
        without committing to heavy perception, although to implement in near future.
        The bridge does three things:
        1. Emit a signal from WorldGraph → Column (creates an engram and returns its id)
        2. Attach that engram id to a binding’s engrams dict
        3. Fetch engrams back (Column → WorldGraph) for inspection/analytics later

        This uses existing column memory and feature payloads (no new dependencies): the column
        already stores engrams and hands back ids, and provides a get() to retrieve them ; the
        features module defines a small TensorPayload and FactMeta we can use for toy “scene” vectors
        and metadata . (Temporal helpers stay separate and can be used to stamp meta["created_at"] later.)

        Parameters
        ----------
        bid : binding id to decorate
        column : name of the column provider that owns this engram ('column01' by default)
        engram_id : id returned by the column after asserting a fact
        act : optional activation weight (kept small and human-friendly)
        extra_meta : optional small dict to travel with the pointer

        Notes
        -----
        - This keeps WorldGraph lightweight: only the pointer (id) + tiny numbers
          live on the binding; the heavy payload stays inside the column.
        """
        if bid not in self._bindings:
            raise KeyError(f"Unknown binding: {bid!r}")
        b = self._bindings[bid]
        if b.engrams is None:
            b.engrams = {}
        payload = {"id": engram_id, "act": float(act)}
        if extra_meta:
            payload["meta"] = dict(extra_meta)
        b.engrams[column] = payload

    def get_engram(self, *, column: str = "column01", engram_id: str) -> dict:
        """
        Fetch a full engram record from the column. Read-only convenience.

        Returns
        -------
        dict : whatever the column stored for this engram id (payload + meta).

        Implementation note: imports at call-site to avoid tight coupling.
        """
        from cca8_column import mem as _mem   # column memory (RAM)  :contentReference[oaicite:3]{index=3}
        return _mem.get(engrams_id := engram_id)  # will raise KeyError if missing

    def emit_pred_with_engram(self, token: str, *, payload=None, name: str | None = None,
                              column: str = "column01", attach: str | None = "now",
                              links: list[str] | None = None, attrs: dict | None = None,
                              meta: dict | None = None) -> tuple[str, str]:
        """
        Create a predicate binding and simultaneously assert an engram in the column,
        then attach the engram pointer to the new binding.
        
        As a result this signal bridge to the engrams for initial work:
        -A policy (or the runner) can emit a cue/predicate and a small engram in one call
        -The new binding’s engrams dict will carry a pointer like:
                {"column01": {"id": "<engram_id>", "act": 1.0, "meta": {...}}}
        -We can later get_engram(engram_id=...) to retrieve the full record from the column
        
        Returns
        -------
        (bid, engram_id)

        This is a stub-level bridge: it records a small payload and links so that
        later perception/planning can coordinate. Heavy computation stays in the column.
        """
        # 1) make/normalize the predicate binding
        bid = self.add_predicate(token, attach=attach, meta=meta)

        # 2) assert a lightweight engram in column memory
        from cca8_column import mem as _mem, ColumnMemory   # :contentReference[oaicite:4]{index=4}
        try:
            from cca8_features import FactMeta              # optional sugar  :contentReference[oaicite:5]{index=5}
            _fm = FactMeta(name=(name or token), links=links, attrs=attrs)
        except Exception:
            _fm = None
        engram_id = _mem.assert_fact(name or token, payload, _fm)

        # 3) attach pointer to the binding
        self.attach_engram(bid, column=column, engram_id=engram_id, act=1.0)

        return bid, engram_id

    def emit_cue_with_engram(self, cue_token: str, *, payload=None, name: str | None = None,
                             column: str = "column01", attach: str | None = "now",
                             links: list[str] | None = None, attrs: dict | None = None,
                             meta: dict | None = None) -> tuple[str, str]:
        """
        Create a cue binding (cue:*), assert an engram in the column, and attach the pointer.

        Returns
        -------
        (bid, engram_id)

        Usage example:
            bid, eid = world.emit_cue_with_engram(
                "vision:silhouette:mom",
                payload=TensorPayload([0.1,0.2,0.3], shape=(3,)),
                name="scene:vision:silhouette:mom",
                links=["cue:vision:silhouette:mom"]
            )
        """
        # 1) add the cue binding (normalized to cue:*)
        bid = self.add_cue(cue_token, attach=attach, meta=meta)

        # 2) assert a lightweight engram in column memory
        from cca8_column import mem as _mem                    # :contentReference[oaicite:6]{index=6}
        try:
            from cca8_features import FactMeta                 # :contentReference[oaicite:7]{index=7}
            _fm = FactMeta(name=(name or cue_token), links=links, attrs=attrs)
        except Exception:
            _fm = None
        engram_id = _mem.assert_fact(name or cue_token, payload, _fm)

        # 3) attach pointer to the cue binding
        self.attach_engram(bid, column=column, engram_id=engram_id, act=1.0)

        return bid, engram_id

    def capture_scene(self, channel: str, token: str, vector: list[float],
                      *, shape: tuple[int, ...] | None = None, attach: str = "now",
                      family: str = "cue", name: str | None = None,
                      links: list[str] | None = None, attrs: dict | None = None) -> tuple[str, str]:
        """
        Convenience for creating a tiny numeric 'scene' payload and emitting it
        as a cue or predicate with an attached engram pointer.

        Parameters
        ----------
        channel : e.g., 'vision' | 'scent' | 'sound'
        token   : e.g., 'silhouette:mom'
        vector  : small float list (toy embedding); use shape=(N,) if not provided
        attach  : 'now'|'latest'|'none'
        family  : 'cue' (default) or 'pred'
        name    : optional column record name; default uses channel:token
        links   : optional world tokens to record alongside the engram
        attrs   : optional dict for extra descriptors

        Returns
        -------
        (bid, engram_id)
        """
        try:
            from cca8_features import TensorPayload           # :contentReference[oaicite:8]{index=8}
        except Exception:
            TensorPayload = None

        if TensorPayload is not None:
            payload = TensorPayload(data=list(vector), shape=shape or (len(vector),),
                                    kind="scene", fmt="tensor/list-f32")
        else:
            payload = {"kind": "scene", "fmt": "raw/list", "data": list(vector), "shape": shape or (len(vector),)}

        full_token = f"{channel}:{token}"
        name = name or f"scene:{full_token}"
        links = links or [f"{'cue' if family=='cue' else 'pred'}:{full_token}"]

        if family == "cue":
            return self.emit_cue_with_engram(full_token, payload=payload, name=name,
                                             attach=attach, links=links, attrs=attrs)
        elif family == "pred":
            return self.emit_pred_with_engram(full_token, payload=payload, name=name,
                                              attach=attach, links=links, attrs=attrs)
        else:
            raise ValueError("family must be 'cue' or 'pred'")


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
        
    def add_action(self, src_id: str, dst_id: str, action: str, meta: dict | None = None):
        """
        Syntactic sugar for adding an action-labeled edge: src --action--> dst.
        Equivalent to add_edge(src_id, dst_id, label=action, meta=meta).
        """
        return self.add_edge(src_id, dst_id, label=action, meta=meta)


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


    # ------------------------- pretty path helpers -------------------------

    def _first_pred_of(self, bid: str) -> str | None:
        """Return the first 'pred:*' tag (without the 'pred:' prefix) if present."""
        b = self._bindings.get(bid)
        if not b:
            return None
        for t in b.tags:
            if isinstance(t, str) and t.startswith("pred:"):
                return t[5:]
        return None

    def _anchor_name_of(self, bid: str) -> str | None:
        b = self._bindings.get(bid)
        if not b:
            return None
        for t in b.tags:
            if isinstance(t, str) and t.startswith("anchor:"):
                return t.split(":", 1)[1]
        return None

    def _edge_label(self, src: str, dst: str) -> str | None:
        b = self._bindings.get(src)
        if not b or not b.edges:
            return None
        for e in b.edges:
            if e.get("to") == dst:
                return e.get("label") or "then"
        return None

    def pretty_path(
        self,
        ids: list[str] | None,
        *,
        node_mode: str = "id+pred",       # 'id' | 'pred' | 'id+pred'
        show_edge_labels: bool = True,
        annotate_anchors: bool = True
        ) -> str:
        """Return a readable, single-line rendering of a path of binding IDs."""
        if not ids:
            return "(no path)"
        def node_label(bid: str) -> str:
            pred = self._first_pred_of(bid)
            anch = self._anchor_name_of(bid)
            if node_mode == "id":
                base = bid
            elif node_mode == "pred":
                base = pred or anch or bid
            else:  # id+pred
                base = f"{bid}[{pred}]" if pred else (f"{bid}({anch})" if anch else bid)
            if annotate_anchors and anch:
                # make anchors explicit even if node_mode != 'id+pred'
                if "NOW" == anch or "HERE" == anch:
                    if "[" in base or "(" in base:
                        return base.replace("]", "](NOW)") if anch == "NOW" else base.replace("]", "](HERE)")
                    return f"{base}({anch})"
            return base

        parts: list[str] = []
        for i, u in enumerate(ids):
            parts.append(node_label(u))
            if i + 1 < len(ids):
                v = ids[i + 1]
                lbl = self._edge_label(u, v) if show_edge_labels else None
                parts.append(f" --{lbl}--> " if lbl else " -> ")
        return "".join(parts)

    def plan_pretty(
        self, src_id: str, token: str, **kwargs
        ) -> str:
        """Convenience: plan_to_predicate then pretty_path (returns text or '(no path)')."""
        path = self.plan_to_predicate(src_id, token)
        return self.pretty_path(path, **kwargs) if path else "(no path)"
        
        
    # ------------------------- action / edge-label utilities -------------------------

    def _iter_edges(self):
        """
        Internal: yield (src_id, dst_id, edge_dict) for every well-formed edge.
        Skips edges that point to unknown dst ids.
        """
        for src_id, b in self._bindings.items():
            edges = getattr(b, "edges", None) or []
            for e in edges:
                dst = e.get("to")
                if not dst or dst not in self._bindings:
                    continue
                yield src_id, dst, e

    def list_actions(self, *, include_then: bool = True) -> list[str]:
        """
        Return a sorted list of unique edge labels present in the graph.
        By default includes the generic 'then'; pass include_then=False to hide it.
        """
        labels: set[str] = set()
        for _src, _dst, e in self._iter_edges():
            lab = e.get("label", "then")
            if lab == "then" and not include_then:
                continue
            labels.add(lab)
        return sorted(labels)

    def action_counts(self, *, include_then: bool = True) -> dict[str, int]:
        """
        Return a dict: {label -> count of edges with that label}.
        Include or exclude the generic 'then' via include_then.
        """
        from collections import Counter
        c = Counter()
        for _src, _dst, e in self._iter_edges():
            lab = e.get("label", "then")
            if lab == "then" and not include_then:
                continue
            c[lab] += 1
        return dict(c)

    def edges_with_action(self, label: str):
        """
        Generator over edges that match a given action label.
        Yields tuples: (src_id, dst_id, meta_dict).
        """
        for src, dst, e in self._iter_edges():
            if (e.get("label", "then") == label):
                yield (src, dst, e.get("meta", {}) or {})

    def action_metrics(self, label: str, *, numeric_keys: tuple[str, ...] = ("meters", "duration_s", "speed_mps")) -> dict:
        """
        Aggregate simple numeric metrics from edge.meta for all edges with a given label.
        Returns a dict: {
            'count': N,
            'keys': {
                <key>: {'count': kN, 'sum': Σ, 'avg': Σ/kN}
            }
        }
        Only keys present AND numeric are aggregated; others are ignored.
        """
        import numbers
        out = {"count": 0, "keys": {}}
        acc = {k: {"count": 0, "sum": 0.0} for k in numeric_keys}
        n = 0
        for _src, _dst, meta in self.edges_with_action(label):
            n += 1
            for k in numeric_keys:
                v = meta.get(k, None)
                if isinstance(v, numbers.Number):
                    acc[k]["count"] += 1
                    acc[k]["sum"] += float(v)
        out["count"] = n
        for k, d in acc.items():
            if d["count"] > 0:
                out.setdefault("keys", {})[k] = {
                    "count": d["count"],
                    "sum": d["sum"],
                    "avg": d["sum"] / d["count"],
                }
        return out

    def action_summary_text(self, *, include_then: bool = False, examples_per_action: int = 2) -> str:
        """
        Return a human-readable summary of actions (edge labels) in the graph:
        - unique labels with counts
        - a couple of example edges per label (src --label--> dst)
        Hide the generic 'then' by default to reduce noise.
        """
        lines: list[str] = []
        counts = self.action_counts(include_then=include_then)
        if not counts:
            return "No actions (edge labels) recorded."
        # header
        total = sum(counts.values())
        lines.append(f"Actions summary (labels) — total labeled edges: {total}")
        for lab in sorted(counts):
            lines.append(f"  • {lab}: {counts[lab]}")
            # examples
            i = 0
            for src, dst, _meta in self.edges_with_action(lab):
                # use first pred:* as short label if present
                def _first_pred(bid: str) -> str:
                    b = self._bindings.get(bid)
                    if not b:
                        return bid
                    for t in getattr(b, "tags", []) or []:
                        if isinstance(t, str) and t.startswith("pred:"):
                            return t[5:]
                    return bid
                if i < examples_per_action:
                    lines.append(f"      e.g., {src}[{_first_pred(src)}] --{lab}--> {dst}[{_first_pred(dst)}]")
                    i += 1
                else:
                    break
        return "\n".join(lines)


    # ------------------------- visualize the graph -----------------------


    def to_pyvis_html(
        self,
        path_html: str = "world_graph.html",
        *,
        label_mode: str = "first_pred",   # 'first_pred' | 'id' | 'id+first_pred'
        show_edge_labels: bool = True,
        physics: bool = True,
        height: str = "750px",
        width: str = "100%",
        title: str = "CCA8 WorldGraph"
        ) -> str:
        """
        Export the current episode graph to an interactive HTML (Pyvis).
        Returns the absolute output path.

        Node labels:
            - 'first_pred': use the first 'pred:*' tag if present; else anchor name; else the id (default)
            - 'id': just the binding id (e.g., b42)
            - 'id+first_pred': 'b42\\nstate:posture_standing' (if present)

        Notes:
            - Highlights NOW (amber) and LATEST (green) to help navigation.
            - Edge labels (e.g., 'then') appear as edge labels/tooltips if enabled.
        """
        try:
            from pyvis.network import Network
        except Exception as e:
            raise RuntimeError(
                "Pyvis not installed. Install with:  pip install pyvis"
            ) from e

        net = Network(height=height, width=width, directed=True, notebook=False)
        net.barnes_hut() if physics else net.toggle_physics(False)

        now_id = self._anchors.get("NOW")
        here_id = self._anchors.get("HERE")
        latest_id = self._latest_binding_id

        def _first_pred(b) -> str | None:
            for t in b.tags:
                if isinstance(t, str) and t.startswith("pred:"):
                    return t[5:]
            return None

        def _anchor_name(b) -> str | None:
            for t in b.tags:
                if isinstance(t, str) and t.startswith("anchor:"):
                    return t.split(":", 1)[1]
            return None

        def _first_cue(b) -> str | None:
            for t in getattr(b, "tags", []) or []:
                if isinstance(t, str) and t.startswith("cue:"):
                    return t[4:]
            return None

        # Nodes
        for bid, b in self._bindings.items():
            pred = _first_pred(b)
            cue  = _first_cue(b)
            anch = _anchor_name(b)

            if label_mode == "id":
                label_txt = bid
            elif label_mode == "id+first_pred":
                # show pred if present; else show cue; else show anchor name; else id only
                second = pred or cue or anch
                label_txt = f"{bid}\n{second}" if second else bid
            elif label_mode == "first_pred":
                label_txt = pred or cue or anch or bid
            else:
                label_txt = pred or cue or anch or bid

            # Tooltip with id, tags, and a small meta preview
            import html, json
            tags_str = ", ".join(sorted(b.tags))
            meta_preview = html.escape(json.dumps(b.meta, ensure_ascii=False)[:240])
            eng = ", ".join((b.engrams or {}).keys()) or "(none)"
            title_html = "<br/>".join([
                f"<b>{html.escape(bid)}</b>",
                f"tags: {html.escape(tags_str)}" if tags_str else "tags: (none)",
                f"engrams: {html.escape(eng)}",
                f"meta: {meta_preview}" if b.meta else "meta: (none)"
            ])

            # A bit of visual affordance
            color = None
            shape = "ellipse"
            if anch:
                shape = "box"
                color = "#FFD54F" if bid == now_id else "#64B5F6"
            if bid == latest_id and bid != now_id:
                color = "#81C784"

            node_kwargs = {"label": label_txt, "title": title_html, "shape": shape}
            if color:
                node_kwargs["color"] = color
            net.add_node(bid, **node_kwargs)

        # Edges
        for src, b in self._bindings.items():
            for e in (b.edges or []):
                dst = e.get("to")
                if not dst or dst not in self._bindings:
                    continue
                rel = e.get("label", "then")
                edge_kwargs = {"title": rel}
                if show_edge_labels:
                    edge_kwargs["label"] = rel
                net.add_edge(src, dst, **edge_kwargs)

        # Write HTML
        import os
        out = os.path.abspath(path_html)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        net.write_html(out, notebook=False)
        return out


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
