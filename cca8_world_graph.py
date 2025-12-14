# -*- coding: utf-8 -*-
"""
CCA8 World Graph (episode index)

This module implements the *symbolic episode index* for CCA8.
Summary of basic concepts below but see README.MD for more explanation of these concepts.

Why this exists:
- The WorldGraph is a *fast index & planner substrate* (~5% of information).
- Rich content lives in column **engrams** (~95%), and bindings can point to them.
- Planning is simple BFS/Djikstra/other functionally equivalent algorithm over binding edges to a target predicate tag.

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
- "Provenance" -- it documents the history or lineage of the data who/what/why, lives within metadata of binding
- "Metadata" -- characteristics including admin features of the data, and in our code actually includes the provenance
- "Edge" -- a standard term for link; we use directed edges expressing weak, generic
            causality "then" (this came after that in an episode).
            Actions are represented as bindings tagged "action:*" (with a legacy
            "pred:action:*" alias on the same binding for back-compat); edges are
            primarily temporal/relational glue rather than the main carrier of
            action semantics.
- "WorldGraph" -- our graph made up of bindings + directed edges
- "Tags" -- bindings have predicate and/or cue and/or anchor tags:
  "Predicate: a symbolic fact token, e.g., "pred:posture_standing"
     -the reason we use this term with logic/AI heritage rather than a term like "fact" is because a fact
     implies a ground truth while a "predicate" is a symbolic claim
        e.g., "pred:standing"
     -terminology note:   "pred: x" or "cue:x"  -- x can be simple like "standing" or expanded eg, "standing:forest:north"
  "Cue" : while we plan to or target a predicate, a cue represents a current condition
     e.g., "cue:scent:milk"
  "Anchor": special bindings like NOW, actually created via e.g., self._anchors["NOW"] = "b100"
- "Engrams": bindings contain as dict

Persistence:
- `to_dict()` / `from_dict()` serialize/restore an episode (bindings, anchors, latest).
-new bindings get id's from internal counter __next__id(), i.e., "b1", "b2", etc
-when restore from an autosave, from_dict() rebuilds _bindings and then advances the counter so that the next id
   will be one higher than than the largest existing "b<N>"
"""

# --- Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Set, Optional, TypedDict, Iterator
import itertools
import heapq
import os


# PyPI and Third-Party Imports
# --none at this time at program startup--

# CCA8 Module Imports
# --none at this time at program startup--

# --- Public API index and version, constants -------------------------------------------------
__version__ = "0.2.0"
__all__ = ["Edge", "Binding", "WorldGraph", "__version__"]
# convenient public helpers (methods remain accessed via WorldGraph instance, this is just explicit export)

_ATTACH_OPTIONS: Set[str] = {"now", "latest", "none"}

# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

class Edge(TypedDict):
    """more precise typing of edges in class Binding
    -TypedDict therfore treat like a dictionary, not a dataclass
    -thus, no instances, no dot attribute accesses
    e.g., aa: Edge = {'to': 'Nodexxx', 'label': 'then', 'meta': {'created by':'me'}}
          print(aa['to'])  --> 'Nodexxx'
    """
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
    - Part of implementation of Spelke's core knowledge idea, here as a contrained early lexicon and then
       in more advanced stages richer tokens are allowed
    -TagLexicon that defines which tokens are allowed at each developmental stage
       (e.g., neonate → infant → juvenile → adult), including some legacy forms for devp't ease
    -there is light enforcement in WorldGraph.add_predicate/add_cue (configurable: "allow" | "warn" | "strict");

    - Families (i.e., the three namespaces of tags): 'pred', 'cue', 'anchor' -- lexicon keeps separate allowed
       sets per family
    - Stages are cumulative: infant, neonate, juvenile, infant, etc. -- later stages include earlier ones
    - Legacy tokens from earlier software versions are accepted but a preferred canonical is suggested.

    This is deliberately small and focused on the newborn goat domain. Pending fuller development.
    """

    #class attribute (constants by convention) for development stages considered
    STAGE_ORDER = ("neonate", "infant", "juvenile", "adult")

    #class attribute for preferred tokens by family and stage
    BASE: dict[str, dict[str, set[str]]] = {
        "neonate": {
            "pred": {
                # Posture / body facts
                "posture:standing",
                "posture:fallen",
                # Spatial / proximity
                "proximity:mom:close",
                "proximity:mom:far",
                "proximity:shelter:near",
                "proximity:shelter:far",
                # Hazard / cliff proximity
                "hazard:cliff:near",
                "hazard:cliff:far",
                # Feeding / episode facts
                "nipple:found",
                "nipple:latched",
                "milk:drinking",
                "resting",
                "alert",
                "seeking_mom",
                # Intent predicates (if you still use these)
                "stand",
                # Valence (available from birth)
                "valence:like",
                "valence:hate",
            },
            "action": {
                "push_up",
                "extend_legs",
                "look_around",
                "orient_to_mom",
            },

            "cue": {
                "vision:silhouette:mom",
                "scent:milk",
                "sound:bleat:mom",
                "terrain:rocky",
                "vestibular:fall",
                "touch:flank_on_ground",
                "drive:hunger_high",   # if you treat this as a cue
            },
            "anchor": {
                "NOW",
                "NOW_ORIGIN",
                "HERE",
            },
        },
        "juvenile": {"pred": set(), "action": set(), "cue": set(), "anchor": set()},
        "adult":    {"pred": set(), "action": set(), "cue": set(), "anchor": set()},
    }

    # Legacy map: currently unused (no state:* tokens left).
    LEGACY_MAP: dict[str, str] = {}


    def __init__(self):
        """
         Build cumulative sets per stage, i.e.,
            allowed[stage][family] -> set of permitted tokens (cumulative by stage)
            { "<stage>": { "pred": {...}, "cue": {...}, "anchor": {...}, "action": {...} }, ... }
        """
        self.allowed: dict[str, dict[str, set[str]]] = {}
        # Start accumulators for all families we support
        acc = {"pred": set(), "cue": set(), "anchor": set(), "action": set()}

        for stage in self.STAGE_ORDER:
            stage_base = self.BASE.get(stage, {})
            for fam in ("pred", "cue", "anchor", "action"):
                acc[fam] |= set(stage_base.get(fam, set()))
            # Freeze a snapshot for this stage (copy the sets)
            self.allowed[stage] = {fam: set(vals) for fam, vals in acc.items()}


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
        e.g., lex = TagLexicon
              family, local = lex.normalize_family_and_token("pred", "pred:posture_standing")
              Example: ('pred', 'pred:posture_standing') -> ('pred', 'pred:posture_standing')
        """
        tok = (raw or "").strip()
        prefix = family + ":"
        return family, tok[len(prefix):] if tok.startswith(prefix) else tok


    # Compatibility helpers (used by newer callers / refactors)


    def normalize_pred(self, raw: str) -> str:
        """
        Normalize a predicate token into *family-local* form (no 'pred:' prefix).

        Examples:
          - "pred:posture:standing" -> "posture:standing"
          - "posture:standing"      -> "posture:standing"
        """
        _, tok = self.normalize_family_and_token("pred", raw)
        return tok


    def normalize_cue(self, raw: str) -> str:
        """
        Normalize a cue token into *family-local* form (no 'cue:' prefix).

        Examples:
          - "cue:vision:silhouette:mom" -> "vision:silhouette:mom"
          - "vision:silhouette:mom"     -> "vision:silhouette:mom"
        """
        _, tok = self.normalize_family_and_token("cue", raw)
        return tok


    def aliases_for_pred(self, token_local: str) -> list[str]:
        """
        Return legacy aliases (family-local, no 'pred:' prefix) for a canonical predicate token.

        IMPORTANT: This is intentionally conservative to avoid cluttering the WorldGraph with
        redundant tags. We only return aliases implied by LEGACY_MAP (reverse lookup).

        If you want 'posture_standing' as an alias for 'posture:standing', put it in LEGACY_MAP:
            LEGACY_MAP["posture_standing"] = "posture:standing"
        """
        aliases: list[str] = []
        for legacy, preferred in self.LEGACY_MAP.items():
            if preferred == token_local:
                aliases.append(legacy)

        # de-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for a in aliases:
            if a and a not in seen:
                seen.add(a)
                out.append(a)
        return out

# -----------------------------------------------------------------------------
# World graph
# -----------------------------------------------------------------------------

class WorldGraph:
    """Directed episode graph for predicates (facts) and weakly causal edges.

    Key operations:
        - ensure_anchor(name): create/get special timeline nodes (e.g., "NOW").
        - add_predicate(token, ...): create a Binding that carries 'pred:<token>'.
        - add_edge(src_id, dst_id, label, meta=None): link two bindings.
        - plan_to_predicate(src_id, token): BFS/Djikstra/other path to first binding with 'pred:<token>'.
        - others -- see code below

    Design notes:
        - We keep the symbolic layer tiny and fast; engrams carry the heavy payloads.
        - Edges express *episode* causality (not logical necessity).
        - The planner is intentionally simple (BFS/Djikstra/other) and replaceable later.
    """

    def __init__(self, *, memory_mode: str = "episodic") -> None:
        """Initializes an empty episode graph.

        Args:
            memory_mode:
                - "episodic": every add_predicate/add_cue call creates a fresh binding
                              (this is the existing/default behavior).
                - "semantic": add_predicate/add_cue will *reuse* an existing binding when the
                              identical tag already exists, enabling basic consolidation
                              (reduces repetitive nodes in long-term graphs).
        """
        self._bindings: Dict[str, Binding] = {}
        self._anchors: Dict[str, str] = {}           # name -> binding_id
        self._latest_binding_id: Optional[str] = None
        #self._id_counter: int = 1
        self._id_counter: Iterator[int] = itertools.count(1)


        # Stage-aware tag gating (existing behavior)
        self._tag_policy: str = "allow"              # default: permissive
        self._stage: str = "neonate"
        self._lexicon: TagLexicon = TagLexicon()

        # Tag lexicon (existing behavior)
        self._tag_lexicon = TagLexicon()

        # Planning strategy (existing behavior)
        #self._plan_strategy: str = "bfs"
        # Planning strategy (default BFS).
        #
        # IMPORTANT: tests and CLI behavior expect that if the user sets:
        #     CCA8_PLANNER=dijkstra
        # before constructing the WorldGraph, the new instance starts in that mode.
        #
        # This keeps "global default planner" configuration easy, while still allowing
        # explicit runtime switching via world.set_planner(...).
        self._plan_strategy: str = "bfs"
        env_planner = (os.environ.get("CCA8_PLANNER", "") or "").strip().lower()
        if env_planner:
            try:
                self.set_planner(env_planner)
            except ValueError:
                # Ignore invalid env values; keep BFS.
                pass

        # Memory / consolidation mode (NEW)
        self._memory_mode: str = "episodic"
        self._semantic_tag_index: Dict[str, str] = {}  # tag -> canonical binding_id (semantic mode only)
        self.set_memory_mode(memory_mode)

    # --- tag policy / developmental stage -----------------------------------

    #self._lexicon: TagLexicon = TagLexicon()  # predeclare for pylint; _init_lexicon will reset if desired
    def _init_lexicon(self):
        """Initialize stage/tag-lexicon and default tag policy."""
        self._lexicon = TagLexicon()
        self._stage = "neonate"         # default
        self._tag_policy = "warn"       # 'allow' | 'warn' | 'strict'


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
            if self._tag_policy == "warn":
                print("WARN", msg, "(allowing)")
        else:
            preferred = self._lexicon.preferred_of(token_local)
            if preferred and preferred != token_local:
                # Legacy accepted but suggest canonical
                if self._tag_policy != "allow":
                    print(f"WARN [tags] legacy '{family}:{token_local}' — prefer '{family}:{preferred}' (kept legacy to avoid breakage)")
        return token_local


    def _warn_if_tag_not_allowed(self, tag_or_family: str, token_local: Optional[str] = None) -> str:
        """
        Lexicon enforcement helper (back-compat and ergonomics).

        Some call sites naturally want to say:
            _warn_if_tag_not_allowed("pred:posture:fallen")

        Other call sites are clearer as:
            _warn_if_tag_not_allowed("pred", "posture:fallen")

        This function supports BOTH forms.

        Parameters
        ----------
        tag_or_family:
            Either a full tag (e.g., "pred:posture:fallen") OR a family (e.g., "pred").
        token_local:
            If provided, the family-local token (e.g., "posture:fallen").
            If None, we parse tag_or_family as a full tag and split on the first ":".

        Returns
        -------
        str
            The token_local that will be stored (we warn/raise but do not auto-rewrite legacy tokens).
        """
        if token_local is None:
            raw = (tag_or_family or "").strip()
            if ":" in raw:
                family, token_local = raw.split(":", 1)
            else:
                # If someone accidentally passes just the local token, treat it as a pred by default.
                family, token_local = "pred", raw
        else:
            family = (tag_or_family or "").strip()

        return self._enforce_tag(family, token_local)


    def set_planner(self, strategy: str = "bfs") -> None:
        """
        Set the path planner used by plan_to_predicate().
        Accepts 'bfs' (default) or 'dijkstra'.
        """
        s = (strategy or "bfs").lower()
        if s not in {"bfs", "dijkstra"}:
            raise ValueError("strategy must be 'bfs' or 'dijkstra'")
        self._plan_strategy = s


    def get_planner(self) -> str:
        """Return the current planner strategy ('bfs' or 'dijkstra')."""
        return getattr(self, "_plan_strategy", "bfs")

    # --- memory / consolidation --------------------------------------------

    def set_memory_mode(self, mode: str) -> None:
        """Set how predicates/cues are stored.

        Modes:
          - "episodic": every observation becomes a new node (default / current behavior)
          - "semantic": identical predicate/cue tags are consolidated to a single node

        Important:
          This only affects add_predicate() and add_cue(). It does not change anchor
          behavior or edge labels. It is an opt-in clutter-reduction mechanism.
        """
        mode_norm = (mode or "episodic").strip().lower()
        if mode_norm not in ("episodic", "semantic"):
            raise ValueError(f"Unknown memory_mode={mode!r}; expected 'episodic' or 'semantic'")
        self._memory_mode = mode_norm
        self._rebuild_semantic_index()


    def get_memory_mode(self) -> str:
        """Return current memory mode: 'episodic' or 'semantic'."""
        return getattr(self, "_memory_mode", "episodic")


    def _semantic_lookup(self, tag: str) -> Optional[str]:
        """Return canonical binding_id for tag if in semantic mode; else None."""
        if self.get_memory_mode() != "semantic":
            return None
        bid = self._semantic_tag_index.get(tag)
        if bid and bid in self._bindings:
            return bid
        return None


    def _semantic_index(self, bid: str) -> None:
        """Index a binding's pred:/cue: tags for semantic reuse."""
        if self.get_memory_mode() != "semantic":
            return
        b = self._bindings.get(bid)
        if not b:
            return
        for t in b.tags:
            if t.startswith("pred:") or t.startswith("cue:"):
                # Keep the first-seen (oldest) binding as canonical.
                self._semantic_tag_index.setdefault(t, bid)


    def _rebuild_semantic_index(self) -> None:
        """Rebuild semantic index from current graph contents."""
        self._semantic_tag_index = {}
        if self.get_memory_mode() != "semantic":
            return

        def _bid_key(x: str) -> int:
            try:
                return int(x[1:]) if x.startswith("b") else 10**9
            except Exception:
                return 10**9

        for bid in sorted(self._bindings.keys(), key=_bid_key):
            self._semantic_index(bid)

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
                b.tags = set()
            elif isinstance(ts, list):
                # upgrade legacy snapshots that stored a list
                b.tags = set(ts)
            # now guaranteed a set
            return b.tags


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


    def add_predicate(
        self,
        token: str,
        *,
        attach: Optional[str] = None,
        meta: Optional[dict] = None,
        engrams: Optional[dict] = None,
    ) -> str:
        """
        Adds a predicate node.

        Args:
            token: e.g. 'posture:fallen', 'proximity:mom:far' (WITHOUT the 'pred:' prefix)
            attach: None | 'now' | 'latest'
            meta: optional metadata dict
            engrams: optional engram pointers dict

        Memory mode:
            - episodic: always creates a new binding (existing behavior)
            - semantic: reuses an existing binding if identical 'pred:{token}' already exists
        """
        # --- validate / normalize ---
        norm_token = self._tag_lexicon.normalize_pred(token)
        tag = f"pred:{norm_token}"
        self._warn_if_tag_not_allowed(tag)

        att: Optional[str] = (attach or "").strip().lower() or None
        if att == "none":
            att = None
        if att not in (None, "now", "latest"):
            raise ValueError("attach must be None|'now'|'latest'|'none'")

        # --- semantic consolidation fast-path ---
        existing = self._semantic_lookup(tag)
        if existing:
            prev_latest = self._latest_binding_id
            self._latest_binding_id = existing

            # lightweight consolidation telemetry (safe + optional)
            if meta:
                b_exist = self._bindings.get(existing)
                if b_exist is not None:
                    c = b_exist.meta.setdefault("_consolidated", {})
                    c["seen"] = int(c.get("seen", 0)) + 1
                    c["last_meta"] = dict(meta)

            def _edge_exists(src_id: str, dst_id: str, label: str) -> bool:
                src = self._bindings.get(src_id)
                if not src:
                    return False
                return any(e.get("to") == dst_id and e.get("label") == label for e in src.edges)

            # Preserve basic sequencing if requested (but avoid duplicate edges / self-loops)
            if att == "now":
                src = self.ensure_anchor("NOW")
                if src != existing and not _edge_exists(src, existing, "then"):
                    self.add_edge(src, existing, label="then", meta=dict(meta or {}))
            elif att == "latest" and prev_latest and prev_latest in self._bindings:
                if prev_latest != existing and not _edge_exists(prev_latest, existing, "then"):
                    self.add_edge(prev_latest, existing, label="then", meta=dict(meta or {}))

            return existing

        # --- allocate id and construct a fresh binding (episodic behavior) ---
        prev_latest = self._latest_binding_id
        bid = self._next_id()
        b = Binding(
            id=bid,
            tags={tag},
            edges=[],
            meta=dict(meta or {}),
            engrams=dict(engrams or {}),
        )

        # Add alias tags (TagLexicon)
        for alias in self._tag_lexicon.aliases_for_pred(norm_token):
            alias_tag = f"pred:{alias}"
            b.tags.add(alias_tag)
            self._warn_if_tag_not_allowed(alias_tag)

        self._bindings[bid] = b
        self._latest_binding_id = bid

        # Attach edges
        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, label="then", meta=dict(meta or {}))
        elif att == "latest" and prev_latest:
            self.add_edge(prev_latest, bid, label="then", meta=dict(meta or {}))

        # Index for semantic reuse if enabled
        self._semantic_index(bid)
        return bid


    def add_cue(
        self,
        token: str,
        *,
        attach: Optional[str] = None,
        meta: Optional[dict] = None,
        engrams: Optional[dict] = None,
    ) -> str:
        """
        Adds a cue node.

        Args:
            token: e.g. 'vision:silhouette:mom' (WITHOUT the 'cue:' prefix)
            attach: None | 'now' | 'latest'
            meta: optional metadata dict
            engrams: optional engram pointers dict

        Memory mode:
            - episodic: always creates a new binding (existing behavior)
            - semantic: reuses an existing binding if identical 'cue:{token}' already exists
        """
        norm_token = self._tag_lexicon.normalize_cue(token)
        tag = f"cue:{norm_token}"
        self._warn_if_tag_not_allowed(tag)

        att = (attach or "").lower() or None
        if att not in (None, "now", "latest"):
            raise ValueError("attach must be None|'now'|'latest'")

        # --- semantic consolidation fast-path ---
        existing = self._semantic_lookup(tag)
        if existing:
            prev_latest = self._latest_binding_id
            self._latest_binding_id = existing

            if meta:
                b_exist = self._bindings.get(existing)
                if b_exist is not None:
                    c = b_exist.meta.setdefault("_consolidated", {})
                    c["seen"] = int(c.get("seen", 0)) + 1
                    c["last_meta"] = dict(meta)

            def _edge_exists(src_id: str, dst_id: str, label: str) -> bool:
                src = self._bindings.get(src_id)
                if not src:
                    return False
                return any(e.get("to") == dst_id and e.get("label") == label for e in src.edges)

            if att == "now":
                src = self.ensure_anchor("NOW")
                if src != existing and not _edge_exists(src, existing, "then"):
                    self.add_edge(src, existing, label="then", meta=dict(meta or {}))
            elif att == "latest" and prev_latest and prev_latest in self._bindings:
                if prev_latest != existing and not _edge_exists(prev_latest, existing, "then"):
                    self.add_edge(prev_latest, existing, label="then", meta=dict(meta or {}))

            return existing

        # --- allocate id and create fresh binding ---
        prev_latest = self._latest_binding_id
        bid = self._next_id()
        b = Binding(
            id=bid,
            tags={tag},
            edges=[],
            meta=dict(meta or {}),
            engrams=dict(engrams or {}),
        )
        self._bindings[bid] = b
        self._latest_binding_id = bid

        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, label="then", meta=dict(meta or {}))
        elif att == "latest" and prev_latest:
            self.add_edge(prev_latest, bid, label="then", meta=dict(meta or {}))

        self._semantic_index(bid)
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
        # pylint: disable=import-outside-toplevel
        _ = column  #to mark used and keep for future multi-column routing
        from cca8_column import mem as _mem   # column memory (RAM)  :contentReference[oaicite:3]{index=3}
        return _mem.get(engram_id)


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
        # pylint: disable=import-outside-toplevel, broad-exception-caught

        # 1) make/normalize the predicate binding
        bid = self.add_predicate(token, attach=attach, meta=meta)

        # 2) assert a lightweight engram in column memory
        from cca8_column import mem as _mem   #, ColumnMemory   # :contentReference[oaicite:4]{index=4}
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
        # pylint: disable=import-outside-toplevel
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
        # pylint: disable=import-outside-toplevel
        try:
            from cca8_features import TensorPayload           # :contentReference[oaicite:8]{index=8}
        except Exception:
            TensorPayload = None  # type: ignore[assignment, misc]

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

    def add_edge(self, src_id: str, dst_id: str, label: str, meta: Optional[dict] = None, *, allow_self_loop: bool = False) -> None:
        """Add a directed edge src->dst.

        Raises:
            KeyError: if either id is unknown.
            ValueError: if a self-loop is attempted without allow_self_loop=True.
        """
        if src_id not in self._bindings or dst_id not in self._bindings:
            raise KeyError(f"unknown binding id: {src_id!r} or {dst_id!r}")
        if (src_id == dst_id) and not allow_self_loop:
            raise ValueError("self-loop rejected (pass allow_self_loop=True to permit)")
        self._bindings[src_id].edges.append({"to": dst_id, "label": label, "meta": dict(meta or {})})


    def delete_edge(self, src_id: str, dst_id: str, label: str | None = None) -> int:
        """
        Remove edges matching (src_id -> dst_id [label]) from the per-binding adjacency list.

        Returns:
            int: number of removed edges.

        Raises:
            KeyError: if src_id is unknown in this world.
        """
        if src_id not in self._bindings:
            raise KeyError(f"unknown binding id: {src_id!r}")

        b = self._bindings[src_id]
        edges = getattr(b, "edges", None)
        if not isinstance(edges, list):
            return 0


        def _rel(e: dict) -> str:
            return e.get("label") or e.get("rel") or e.get("relation") or "then"

        before = len(edges)
        if label is None:
            edges[:] = [e for e in edges if e.get("to") != dst_id]
        else:
            edges[:] = [e for e in edges if not (e.get("to") == dst_id and _rel(e) == label)]
        return before - len(edges)
    # alias (older callers may still use remove_edge() )
    remove_edge = delete_edge


    def delete_binding(self, bid: str, *, prune_incoming: bool = True, prune_anchors: bool = True) -> bool:
        """Delete a binding node from the graph.

        This is intentionally conservative and used primarily for WorkingMap pruning.

        - Removes incoming edges that point to `bid` (optional)
        - Removes anchors that point to `bid` (optional)
        - Cleans the semantic index if it pointed at this node

        Returns:
            True if deleted, False if `bid` did not exist.
        """
        if bid not in self._bindings:
            return False

        if prune_incoming:
            for b in self._bindings.values():
                b.edges = [e for e in b.edges if e.get("to") != bid]

        if prune_anchors:
            for name, aid in list(self._anchors.items()):
                if aid == bid:
                    del self._anchors[name]

        del self._bindings[bid]

        if self._latest_binding_id == bid:
            self._latest_binding_id = None

        for t, xid in list(getattr(self, "_semantic_tag_index", {}).items()):
            if xid == bid:
                del self._semantic_tag_index[t]

        return True


    def add_action(self, token: str, attach: str = "latest", meta: Optional[dict] = None, engrams: Optional[dict] = None) -> str:
        """
        Create an action binding carrying 'action:<token>'.
        Accepts either 'push_up' or 'action:push_up'; normalizes to 'action:push_up'.
        ----
        Prev docstring:
        Create a new action binding and optionally auto-link it.
        Args:
        token:
            Action token. Accepts either "<token>" (e.g., "push_up") or
            "action:<token>" (e.g., "action:push_up").

            Stored tags include both:
                • "action:<token>"      (new action-family tag)
                • "pred:action:<token>" (legacy alias for back-compat)
        attach:
            If "now", link NOW → new (label 'then').
            If "latest", link <previous latest> → new.
            If None or "none", no auto-link is added.
        meta:
            Optional provenance dictionary to store on the binding.
        engrams:
            Optional engram attachments (small dict).
        Returns:
        bid : str
            The new binding id (e.g., "b42").
        ----
        """

        # Normalize to family 'action' / local token
        tok = (token or "").strip()
        if tok.startswith("action:"):
            local = tok.split(":", 1)[1]
        else:
            local = tok
        # Lexicon enforcement (no auto-rewrite; just warn or raise)
        local = self._enforce_tag("action", local)
        full_tag = f"action:{local}"
        # Validate attach option
        att = (attach or "none").lower()
        if att not in _ATTACH_OPTIONS:  # {"now", "latest", "none"}
            raise ValueError(f"attach must be one of {_ATTACH_OPTIONS!r}")
        # Allocate binding id and create the node
        prev_latest = self._latest_binding_id
        bid = self._next_id()
        b = Binding(
            id=bid,
            tags={full_tag},
            edges=[],
            meta=dict(meta or {}),
            engrams=dict(engrams or {}),
        )
        self._bindings[bid] = b
        self._latest_binding_id = bid
        # Optional auto-linking
        if att == "now":
            src = self.ensure_anchor("NOW")
            self.add_edge(src, bid, "then", meta or {})
        elif att == "latest" and prev_latest and prev_latest in self._bindings:
            self.add_edge(prev_latest, bid, "then", meta or {})
        return bid


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
        """Plan from src_id to first binding carrying 'pred:<token>'.
        Strategy chosen by self._plan_strategy ('bfs' | 'dijkstra').
        """
        # Normalize the tag we are searching for
        token = (token or "").strip()
        target_tag = token if token.startswith("pred:") else f"pred:{token}"

        # Quick checks
        if not src_id or src_id not in self._bindings:
            return None
        if target_tag in self._bindings[src_id].tags:
            return [src_id]

        # Strategy dispatch
        if getattr(self, "_plan_strategy", "bfs") == "dijkstra":
            return self._plan_to_predicate_dijkstra(src_id, target_tag)

        # --- BFS (current behavior) ---
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


    def _edge_cost(self, e: Edge) -> float:
        """
        Return numeric cost/weight for an edge.
        Priority: meta['weight'] → meta['cost'] → meta['distance'] → meta['duration_s'] → 1.0
        """
        meta = (e.get("meta") or {}) if isinstance(e, dict) else {}
        for k in ("weight", "cost", "distance", "duration_s"):
            v = meta.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return 1.0  # default infrastructure: unweighted edges


    def _plan_to_predicate_dijkstra(self, src_id: str, target_tag: str) -> Optional[List[str]]:
        """
        Dijkstra search from src_id to the first node that carries 'target_tag'.
        With all edge weights = 1, this is equivalent to BFS.
        """
        if not src_id or src_id not in self._bindings:
            return None
        if target_tag in self._bindings[src_id].tags:
            return [src_id]

        # distance & parent maps
        dist: Dict[str, float] = {src_id: 0.0}
        parent: Dict[str, Optional[str]] = {src_id: None}
        seen: Set[str] = set()

        # (total_cost, node_id)
        pq: list[tuple[float, str]] = [(0.0, src_id)]

        while pq:
            d_u, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)

            # goal test when node is *popped* (guaranteed minimal cost)
            b_u = self._bindings.get(u)
            if b_u and (target_tag in getattr(b_u, "tags", [])):
                return self._reconstruct_path(parent, u)

            # relax outgoing edges
            if not b_u:
                continue
            for e in getattr(b_u, "edges", []) or []:
                v = e.get("to")
                if not v or v not in self._bindings:
                    continue
                w = self._edge_cost(e)
                if w < 0:
                    # ignore pathological negatives; infra is for non-negative costs
                    continue
                nd = d_u + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    parent[v] = u
                    heapq.heappush(pq, (nd, v))

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
                # pylint: disable=consider-using-in
                if "NOW" == anch or "HERE" == anch:  #more explicit than writing if anch in ....
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
        # pylint: disable=import-outside-toplevel
        from collections import Counter
        c = Counter()  # type: ignore[var-annotated]
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
            if e.get("label", "then") == label:
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
        # pylint: disable=import-outside-toplevel
        import numbers
        out = {"count": 0, "keys": {}}
        acc = {k: {"count": 0, "sum": 0.0} for k in numeric_keys}
        n = 0
        for _src, _dst, meta in self.edges_with_action(label):
            n += 1
            for k in numeric_keys:
                v = meta.get(k, None)
                if isinstance(v, numbers.Real):
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
            - 'id+first_pred': 'b42\\npred:posture_standing' (if present)

        Notes:
            - Highlights NOW (amber) and LATEST (green) to help navigation.
            - Edge labels (e.g., 'then') appear as edge labels/tooltips if enabled.
        """
        # pylint: disable=import-outside-toplevel
        _ = title
        try:
            from pyvis.network import Network
        except Exception as e:
            raise RuntimeError(
                "Pyvis not installed. Install with:  pip install pyvis"
            ) from e

        net = Network(height=height, width=width, directed=True, notebook=False)
        #pylint: disable=expression-not-assigned
        net.barnes_hut() if physics else net.toggle_physics(False)
        #pylint: enable=expression-not-assigned

        now_id = self._anchors.get("NOW")
        #here_id = self._anchors.get("HERE")
        _here_id = self._anchors.get("HERE")  # currently unused; reserved for future highlighting
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
            # pylint: disable=import-outside-toplevel
            import html
            import json
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
        #import os
        out = os.path.abspath(path_html)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        net.write_html(out, notebook=False)
        return out


    # ------------------------- persistence -----------------------

    def to_dict(self) -> dict:
        """Serialize the whole world for autosave.
        """
        return {
            "bindings": {bid: b.to_dict() for bid, b in self._bindings.items()},
            "anchors": dict(self._anchors),
            "latest": self._latest_binding_id,
            "memory_mode": self.get_memory_mode(),
            "version": "0.1",
        }


    @classmethod
    def from_dict(cls, data: dict) -> "WorldGraph":
        """Restore a world from autosave and advance the id counter to avoid collisions.
        """
        g = cls(memory_mode=data.get("memory_mode", "episodic"))
        g._bindings = {bid: Binding.from_dict(b) for bid, b in data.get("bindings", {}).items()}
        g._anchors = dict(data.get("anchors", {}))
        g._latest_binding_id = data.get("latest")

        # Advance id counter
        def _idnum(x: str) -> int:
            try:
                return int(x[1:]) if x.startswith("b") else 0
            except Exception:
                return 0

        max_id = max((_idnum(bid) for bid in g._bindings.keys()), default=0)
        #g._id_counter = max_id + 1
        g._id_counter = itertools.count(max_id + 1)


        # Ensure semantic index matches loaded graph content
        g.set_memory_mode(data.get("memory_mode", g.get_memory_mode()))
        return g


    def check_invariants(self, *, raise_on_error: bool = True) -> list[str]:
        """Validate basic graph invariants. Return a list of human-readable issues.

        Checks:
          - anchors['NOW'] exists and its binding carries 'anchor:NOW'
          - latest id (if set) exists
          - all edges point to existing nodes (dst)
        """
        issues: list[str] = []

        # NOW anchor sanity
        now_id = self._anchors.get("NOW")
        if now_id is not None:
            if now_id not in self._bindings:
                issues.append("anchors['NOW'] points to unknown binding id")
            else:
                tags = getattr(self._bindings[now_id], "tags", []) or []
                if "anchor:NOW" not in tags:
                    issues.append("NOW binding missing 'anchor:NOW' tag")

        # latest sanity
        if self._latest_binding_id and self._latest_binding_id not in self._bindings:
            issues.append("latest binding id is not present in _bindings")

        # edges must point to existing nodes
        for src_id, b in self._bindings.items():
            for e in getattr(b, "edges", []) or []:
                dst = e.get("to")
                if not dst or dst not in self._bindings:
                    issues.append(f"edge {src_id} -> {dst!r} points to unknown binding")

        if raise_on_error and issues:
            raise AssertionError("WorldGraph invariant violations:\n  - " + "\n  - ".join(issues))
        return issues
