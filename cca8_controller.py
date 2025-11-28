# -*- coding: utf-8 -*-
"""
CCA8 Controller: drives, primitives ("policies"), and action center.

Concepts
--------
- Drives: numeric homeostatic values (hunger, fatigue, warmth) → derive 'drive:*' flags (ephemeral tags that are not written to worldgraph)
- Policy (primitive): behavior object with two parts -- trigger(...) and execute(...)
    -parameter 'world' represents the episode state, e.g., already standing? fallen?, cues present?, anchors/latest?
    -parameter 'drives' represent internal needs, i.e., homeostatic values (e.g., hunger, fatigue, etc)
        -drive tags are derived from numeric levels, e.g., hunger > 0.60 --> "drive:hunger_high"
        [note: WorldGraph index layer uses four tag families: pred:*, action:*, cue:*, anchor:*.
         drive:* are ephemeral controller flags, not graph tags.
         On a real WorldGraph, action nodes carry both "action:*" and legacy "pred:action:*" tags
         (for back-compat); edges are generic "then" links that encode weak temporal/causal
         succession between bindings.]

        [created by Drives.flags() for trigger logic only and are never written to WorldGraph]
        [e.g., plannable drive condition, then yes, can create a node with e.g., "pred:drive:hunger_high", or evidence, e.g., cue:drive:hunger_high]
        -policies use drive tags in triggering (e.g., SeekNipple needs hunger), while execute may update drives (e.g., Rest reduces fatigue a bit)
    -parameter 'ctx' represents runtime context
        -includes age_days, sigma and jump (tie-breaking, exploration settings), ticks (i.e., how many autonomic 'heartbeats' have passed), profile (e.g., "goat", "chimp", etc),
           winners_k, hal and body (for multi-brain scaffolding and embodiment stub)
        -policies don't really require ctx but useful for gating behavior by age/profile, calling into HAL stubs, writing provenance, e.g., ticks, to meta
    -trigger(world, drives)
    -execute(world, drives, ctx) -- appends small chain of bindings/edges and set provenance to world; adjust internal states to drives; optional gating, embodiment via ctx
    -e.g.,  def trigger (self, world, drives): if _has(world, ...) or drives.fatigue... return False
            def execute (self, world, ctx, drives): meta=... ; world.add_predicate("action:look_around"); return self._success(reward, notes, binding)
            -if display WorldGraph:  b1(NOW) --then--> b2[action:look_around]--then--> b3[state:alert]
    -when executed, a policy appends a *small chain* of predicates/edges to the WorldGraph and returns a status dict
       -status dict: {"policy": "policy:<name>", "status": "ok|fail|noop|error", "reward": float, "notes": str}.
    - Provenance: bindings created by a policy stamp meta.policy = "policy:<name>".
        "provenance" means when a primitive/policy fires and creates bindings or links we stamp metadata
        eg, "created_by: policy:<name>", timestamp, tag "policy:stand_up", "note: 'standing'"
        thus effective means recording origin so later debugging/credit assignment skill ledger,RL is explainable
        -state predicates, e.g., state:posture_standing, assert something about the agent or world that reasoner can use as facts
        -provenance tags, e.g., policy:stand_up, assert who/what produced this binding/edge rather than something  plan for, it already occurred
        -despite the same effect predicate being produced there could have been two different policies creating it, provenance tags help figure out which one
        - Skill ledger: tiny RL-style counters (n, succ, q, last_reward) per policy; not used for selection yet.

Clarification of Predicates versus other similar looking terms
--------------------------------------------------------------
-only predicates or cues or anchors are written to the WorldGraph, i.e., they live in the bindings (nodes)
-drive:* tags which we now call "flags" to reduce confusion are ephemeral and are not written to the WorldGraph or the binding's records
-it is possible to make a drive:* flag into a predicate or cue to put on the WorldGraph if it was to be used for planning /inspection purposes,
    e.g., "pred:drive:*" or "cue:drive:*"
-"state:posture_standing" is shorthand for the token part of the full predicate which is "pred:state:posture_standing", i.e, "pred:state:*"
-   we use state:* tokens for relatively stable facts about the agent/world and are ok to persist in the WorldGraph
-"action:run" would normally be stored on the edges as execution provenance; however can turn into a predicate "pred:action:run" for
   WorldGraph is want the action as a fact for planning or for inspection
-worldgraph==world stores pred:<token>, where <token> may be state:*, action:*, etc.
-the controller uses ephemeral drive:* flags (never written as pred:*) to decide triggers.
-for compatibility, we sometimes write a legacy alias and the canonical tag on the same binding
   (e.g., pred:posture:standing and pred:state:posture_standing) so older tests/tools still work while new code reads the canonical form.


Token quick-ref (canonicalization & usage)
------------------------------------------

Families in the WorldGraph:
  • pred:*     — facts (assertions the reasoner can use)
  • action:*   — action nodes (verbs in the navigation map)
  • cue:*      — observations/engram evidence (non-factual sensory tags)
  • anchor:*   — structural anchors (NOW, NOW_ORIGIN, etc.)

Canonical tokens (second-level namespaces under pred:*):
  • posture:*  — body posture facts (e.g., posture:standing, posture:fallen)
  • proximity:*— spatial relations (e.g., proximity:mom:close, proximity:mom:far)
  • nipple:*, milk:* — feeding milestones (e.g., nipple:latched, milk:drinking)

Canonical tokens (second-level namespaces under action:*):
  • <verb>     — action semantics / provenance (e.g., push_up, extend_legs, look_around, orient_to_mom)

    NOTE:
      - On a real WorldGraph, actions are stored as both "action:<verb>" and the legacy
        "pred:action:<verb>" on the same binding (for back-compat).
      - Edges carry generic "then" relations; actions are nodes, not edge labels.

Controller-only flags (never written as pred:*):
  • drive:*    — ephemeral homeostatic flags derived from Drives (e.g., drive:hunger_high)

Why constants:
  • Single source of truth, IDE autocomplete, fewer typos.
  • Easy refactors (rename once; keep legacy in CANON_SYNONYMS for back-compat).
  • Clear lexicon surface for docs/tests.

Reading & writing helpers:
  • _canon(token)                 → maps legacy → canonical (e.g., "posture:standing" → "state:posture_standing")
  • _add_pred(world, token, ...)  → adds pred:<canonical_token> (WorldGraph prefixes 'pred:')
  • _has(world, token)            → True if pred:<canonical OR legacy> exists (alias-aware)

Back-compat policy (WorldGraph only):
  • For selected tokens we tag the SAME binding with both the legacy alias and canonical tag
    (e.g., pred:posture:standing + pred:state:posture_standing) so older tools/tests still pass.

Naming rules:
  • snake_case, colon-namespaces, no spaces.
  • state:* uses noun phrases (state:posture_standing).
  • action:* uses verb phrases (action:orient_to_mom).
  • Avoid inventing new top-level families; prefer state:* or action:* and document here.

Common tokens (constants → stored token):
  • STATE_POSTURE_STANDING  → state:posture_standing    (legacy: posture:standing)
  • STATE_POSTURE_FALLEN    → state:posture_fallen      (legacy: posture:fallen)
  • STATE_RESTING           → state:resting
  • STATE_ALERT             → state:alert
  • STATE_SEEKING_MOM       → state:seeking_mom         (legacy: seeking_mom)
  • ACTION_PUSH_UP          → action:push_up
  • ACTION_EXTEND_LEGS      → action:extend_legs
  • ACTION_LOOK_AROUND      → action:look_around
  • ACTION_ORIENT_TO_MOM    → action:orient_to_mom

Usage patterns (examples):
  • Write a fact:
      b = _add_pred(world, STATE_POSTURE_STANDING, attach="latest", meta=meta)
      # In real WorldGraph, the same binding also carries the legacy alias for compatibility.

  • Check a fact (alias-aware):
      if _has(world, STATE_POSTURE_STANDING): ...

  • Add a new canonical token:
      NEW_CONST = "state:foo_bar"
      CANON_SYNONYMS.update({"legacy:foo": NEW_CONST})  # optional back-compat mapping

Agent loop note:
  • Drives produce drive:* flags (ephemeral).
  • Action selection can prefer policies linked to the largest drive deficits; the controller
    remains the safety gate (e.g., stand up if fallen), while the world stores only pred:* facts.


Action loop
-----------
-the Action Center is like a single-step orchestrator --
   -safety short-circuit, e.g., if the world shows a fallen state then immediately run StandUp
   -otherwise scan PRIMITIVES in order call trigger(world, dirves)
   -run the first policy whose trigger is True --> _run wraps execute(...) and updates the skill ledger
   -returns a status dict {"policy":"policy:<name>" | None, "status": "ok|fail|noop|error", "reward":float, "notes":str}
-the order of PRIMITIVES matters and we placed in our priority scheme:
   StandUp (safety) --> SeekNipple(hunger) --> Rest (fatigue) --> FollowMom (fallback) --> ExploreCheck (stub)
-permissive fallback (e.g., FollowMom) (i.e., a policy whose trigger(...) is basically always True or at least in most normal states)
  -the action center returns {"status":"noop"} only when no policy triggers
  -if FollowMom.trigger(...) is nearly always True, then never see a "noop" because the fallback will always fire and produce an "ok" step instead
  -if ever want occasional no-ops (i.e., do nothing controller steps) then tighten FollowMom(...) trigger (e.g., return False if tired/hungry/just acted) or
     move FollowMom even further down or add a timer/debounce so it doesn't constantly fire
-when multiple policies trigger, selection defaults to deficit scoring with legacy-order fallback
-selection defaults to deficit scoring; to integrate an external adviser, pass preferred='policy:...' (controller remains the safety gate)

"""

# --- Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List

# PyPI and Third-Party Imports
# --none at this time at program startup--

# CCA8 Module Imports
# --none at this time at program startup--

# --- Public API index and version-------------------------------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.2.0"
__all__ = [
    "Drives",
    "SkillStat",
    "skills_to_dict",
    "skills_from_dict",
    "skill_readout",
    "Primitive",
    "StandUp",
    "SeekNipple",
    "FollowMom",
    "ExploreCheck",
    "Rest",
    "PRIMITIVES",
    "action_center_step",
    "__version__",
]

# Drive thresholds
HUNGER_HIGH = 0.60
FATIGUE_HIGH = 0.70
WARMTH_COLD = 0.30


# --- Canonical tokens ---------------------------------------------------------
# Canonical tokens (second-level namespaces under pred:*)
# We treat "posture:*", "resting", "alert", "seeking_mom" as the canonical forms.
# Legacy "state:*" forms are still recognized when *reading* so older snapshots/tests work.

STATE_POSTURE_STANDING = "posture:standing"
STATE_POSTURE_FALLEN   = "posture:fallen"
STATE_RESTING          = "resting"
STATE_ALERT            = "alert"
STATE_SEEKING_MOM      = "seeking_mom"

ACTION_PUSH_UP         = "action:push_up"
ACTION_EXTEND_LEGS     = "action:extend_legs"
ACTION_LOOK_AROUND     = "action:look_around"
ACTION_ORIENT_TO_MOM   = "action:orient_to_mom"

# Back-compat synonyms we still recognize when *reading* from the graph.
# These map legacy state:* forms onto the new canonical tokens.
CANON_SYNONYMS: dict[str, str] = {}
def _canon(token: str) -> str:
    return CANON_SYNONYMS.get(token, token)


def _is_worldgraph(world) -> bool:
    """Heuristic: real WorldGraph exposes planning.
    True or False regarding if world.plan_to_predicate() exists
    """
    return hasattr(world, "plan_to_predicate") and callable(getattr(world, "plan_to_predicate"))


def _add_tag_to_binding(world, bid: str, full_tag: str) -> None:
    """Best-effort: add a tag to an existing binding (works for WorldGraph and FakeWorld).
    -will add "full_tag" to binding "bid" assuming a binding exists for "bid", and then adds "full_tag"
      to whatever binding.tags exists
    -doesn't return anything since mutates binding.tags in place
    """
    try:
        b = getattr(world, "_bindings", {}).get(bid) #if world._bindings exists look up bid
        if not b:
            return
        tags = getattr(b, "tags", None) #fetches attribute b.tags if exists, otherwise creates from "full_tag" passed into the function
        if tags is None:
            b.tags = {full_tag} #if no b.tags then we rebind the attribute here
            return
        if isinstance(tags, set):  #mutate t.tags set in place --> change will persist after the function returns
            tags.add(full_tag)
        elif isinstance(tags, list): # #mutate t.tags list in place --> change will persist after the function returns
            if full_tag not in tags:
                tags.append(full_tag)
    except Exception:
        pass


def _add_pred(world, token: str, **kwargs):
    """Wrapper to add a canonical predicate token. WorldGraph will add the 'pred:' family automatically.
    -calls in worldgraph module world.add_predicate but with token updated to any newer tokens should they existing
    """
    return world.add_predicate(_canon(token), **kwargs)


def _add_action(world, token: str, **kwargs):
    """Wrapper to add an action binding.

    On a real WorldGraph, this calls `world.add_action(...)`, which writes
    both "action:*" and legacy "pred:action:*" tags on the same binding.

    On FakeWorld (tests) or other WorldGraph-like stubs that don't yet define
    `add_action(...)`, we fall back to `_add_pred(...)`, which writes only
    "pred:action:*" (preserving older test expectations).
    """
    # Apply canonical mapping (currently only used for state:*; action:* passes through)
    tok = _canon(token)

    if _is_worldgraph(world) and hasattr(world, "add_action") and callable(getattr(world, "add_action")):
        # Real WorldGraph path: action-family binding
        return world.add_action(tok, **kwargs)

    # Fallback for FakeWorld or older stubs: treat actions as predicates
    return _add_pred(world, token, **kwargs)


# ==== Base-aware write STUB (NO-OP) =========================================
#pylint: disable=unused-argument
def _add_pred_base_aware(world, token: str, ctx, *, default_attach="latest", meta=None):
    """
    STUB: Later, if a suggested write-base exists on ctx, write unattached and
    manual-link base->new. Today this is identical to _add_pred(...).
    Note: -We already compute a "write base" suggestion via choose_contextual_base(...)
        e.g., as seen in the Instinct Step menu selection.
      -these stubs give a single place to switch from attach="latest" to
        base-anchored placement later.
      - _maybe_anchor_attach(...) and add_spatial_relation stubs are in Runner module
    """
    return _add_pred(world, token, attach=default_attach, meta=meta)
#pylint: enable=unused-argument

# -----------------------------------------------------------------------------
# Drives
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class Drives:
    """Agent internal state.

    Attributes:
        hunger: 0..1; >0.6 yields 'drive:hunger_high'.
        fatigue: 0..1; >0.7 yields 'drive:fatigue_high'.
        warmth: 0..1; <0.3 yields 'drive:cold'.
        -note slots=True therefore no other attributes can be added

    Methods:
        -note dataclass, thus e.g., aa=Drives() (default values or can specify) -> aa.hunger will be 0.7
        flags(): convert numeric drives to 'drive:*' flags (i.e., ephemeral tags) used by policy triggers.
        to_dict()/from_dict(): autosave support.
    """
    hunger: float = 0.7
    fatigue: float = 0.2
    warmth: float = 0.6


    def flags(self) -> List[str]:
        """Return ephemeral 'drive:*' flags for policy triggers (not persisted in the graph)
        -note that above in constants section: HUNGER_HIGH = 0.60, FATIGUE_HIGH = 0.70, WARMTH_COLD = 0.30
        -returns a list of drive:* flags where sensory values triggered  e.g., ["drive:hunger_high"]

        """
        tags: List[str] = []
        if self.hunger > HUNGER_HIGH:
            tags.append("drive:hunger_high")
        if self.fatigue > FATIGUE_HIGH:
            tags.append("drive:fatigue_high")
        if self.warmth < WARMTH_COLD:
            tags.append("drive:cold")
        return tags


    def predicates(self) -> List[str]:  # pragma: no cover (legacy alias)
        """DEPRECATED: use flags().
           Back-compat for older code/tests
        """
        return self.flags()


    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict of drive values for autosave/snapshots.
        """
        return {"hunger": self.hunger, "fatigue": self.fatigue, "warmth": self.warmth}


    @classmethod
    def from_dict(cls, d: dict) -> "Drives":
        """Construct a Drives from a snapshot dict (robust to missing keys)
        e.g., to_dict() → {"hunger": 0.7, "fatigue": 0.2, "warmth": 0.6}
        from_dict({"hunger": 0.7, "fatigue": 0.2, "warmth": 0.6}) -> Drive
        this classmethod returns a new instance of Drives
        actually is called from and returns to the Load Session menu option in the runner module

        """
        return cls(
            hunger=float(d.get("hunger", 0.7)),
            fatigue=float(d.get("fatigue", 0.2)),
            warmth=float(d.get("warmth", 0.6)),
        )

# -----------------------------------------------------------------------------
# Skills (tiny RL-style ledger)
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class SkillStat:
    """Simple running stats per policy
    -this is a tiny dataclass that tracks per-policy learning-like statistics
    -really scaffolding for future RL
    e.g., aa = SkillStat() #SkillStat(n=0, succ=0, q=0.0, last_reward=0.0)
          print(type(aa)) #<class 'cca8_controller.SkillStat'>
    """
    n: int = 0   #how many times this policy has been updated/attempted
    succ: int = 0  #how many of those attempts successful
    q: float = 0.0  #exponential moving average EMA of recent rewards
    last_reward: float = 0.0  #most recent reward observed for that policy

SKILLS: Dict[str, SkillStat] = {}
#module level dictionary keyed by policy name, i.e., {policy_name:SkillStat, ...}
#e.g., StandUp.name = "policy:stand_up" (defined on the primitive)
#e.g., SKILLS = {"policy:stand_up": SkillStat(n=3, succ=2, q=0.447, last_reward=1.0),...}


def update_skill(name: str, reward: float, ok: bool = True, alpha: float = 0.3) -> None:
    """Update (or create) a SkillStat:
    - n += 1; succ += 1 if ok
    - q ← (1 - alpha) * q + alpha * reward     (exponential moving average)
    - last_reward ← reward

    Notes:
        * The ledger is in-memory only (not used for selection yet).
        * Callers should pass rewards on the same scale across policies.
    Operation:
        e.g., let's assume SKILLS = {"policy:stand_up": SkillStat(n=3, succ=2, q=0.447, last_reward=1.0),...}
        thus, s= SKILLS.get(name) = SkillStat(n=3, succ=2, q=0.447, last_reward=1.0)
        if s returns as None then create instance of default SkillStat as s and then assign it to SKILLS[name]
        then we increment the counter n, i.e., how many times policy attempted or updated and possibly the succ attribute
        then we adjust the exponential moving average  and update the last_reward

    """
    s = SKILLS.get(name)
    if s is None:
        s = SkillStat()
        SKILLS[name] = s

    s.n += 1
    if ok:
        s.succ += 1
    s.q = (1 - alpha) * s.q + alpha * float(reward)
    s.last_reward = float(reward)


def reset_skills() -> None:
    """Clear the in-memory skill ledger(testing/demo convenience).
    SKILLS becomes {}
    """
    SKILLS.clear()


def skills_to_dict() -> dict:
    """Return a JSON-safe mapping of skill stats:
    { "policy:stand_up": {"n": int, "succ": int, "q": float, "last_reward": float}, ...}
    """
    return {k: asdict(v) for k, v in SKILLS.items()}


def skills_from_dict(d: dict) -> None:
    """Rebuild SKILLS dataclass values from plain dicts (robust to bad inputs).
    """
    SKILLS.clear()
    for k, v in (d or {}).items():
        try:
            SKILLS[k] = SkillStat(
                n=int(v.get("n", 0)),
                succ=int(v.get("succ", 0)),
                q=float(v.get("q", 0.0)),
                last_reward=float(v.get("last_reward", 0.0)),
            )
        except Exception:
            # Skip malformed rows rather than breaking session load.
            continue


def skill_readout() -> str:
    """Human-readable policy stats: one line per policy (n/succ/rate/q/last)
    -goes through SKILLS' stats and prints out

    """
    if not SKILLS:
        return "(no skill stats yet)"
    lines: List[str] = []
    for name in sorted(SKILLS):
        s = SKILLS[name]
        rate = (s.succ / s.n) if s.n else 0.0
        lines.append(
            f"{name}: n={s.n}, succ={s.succ}, rate={rate:.2f}, q={s.q:.2f}, last={s.last_reward:+.2f}"
        )
    return "\n".join(lines)

# -----------------------------------------------------------------------------
# Helper queries (controller-local; simple global scans)
# -----------------------------------------------------------------------------
# Note: world._bindings is an internal/private attribute of world object instance of WorldGraph, meaning it shouldn't
#   really be accessed from outside the class (or immediate subclasses), i.e., "peeking" is occurring
#   -however, these helper queries are considered a trusted-friend shortcut and we allow access rather than
#      implementing a more formal public API in WorldGraph (can be considered in the future if WorldGraph internal changes,
#      graph size exceeds 50K bindings, we introduce tag indices/aliasing that really belong inside WorldGraph)
#   -scope guard: do not access world._bindings anywhere else in the codebase

def _any_tag(world, full_tag: str) -> bool:
    """Return True if any binding carries the exact tag (e.g., 'pred:...')
    -checks to see if full_tag argument is in the set/list/tuple attributes found
    """
    try:
        for b in world._bindings.values():  # pylint: disable=protected-access
            tags = getattr(b, "tags", ())
            if isinstance(tags, (set, list, tuple)) and full_tag in tags:
                return True
    except (AttributeError, TypeError, KeyError):
        pass
    return False


def _has(world, token: str) -> bool:
    """
    Previously: True if either the canonical *or* raw token exists as a pred:* tag
    -recall from above that _canon(token: str) -> CANON_SYNONYMS.get(token, token)
    -then the argument token is fed into __any_tag(...)

    New version: Return True if any binding has tag 'pred:<token>'.
    -Thin wrapper over _any_tag(...), which is the only helper allowed
    to peek at world._bindings (and is guarded with the appropriate
    pylint pragma).

    """
    target = f"pred:{token}"
    return _any_tag(world, target)


def _any_cue_present(world) -> bool:
    """Loose cue check: True if any tag starts with 'cue:' (no proximity semantics).
    -scans through tags in world._bindings.values() to see if any starts with "cue" and
      if so returns True
    -used as a coarse perception gate to tell the controller if a cue present
    """
    try:
        for b in world._bindings.values():  # pylint: disable=protected-access
            tags = getattr(b, "tags", ())
            if not isinstance(tags, (set, list, tuple)):
                continue
            for t in tags:
                if isinstance(t, str) and t.startswith("cue:"):
                    return True
    except (AttributeError, TypeError, KeyError):
        pass
    return False


def _policy_deficit_score(name: str, drives: Drives) -> float:
    """
    priority-by-deficit approach for policies:
        Return a non-negative score reflecting how off-setpoint the relevant drive(s) are
        for a given policy. Higher score → higher priority.

    Current mapping (simple and transparent):
        - policy:seek_nipple → max(0, hunger - HUNGER_HIGH) * 1.0
        - policy:rest        → max(0, fatigue - FATIGUE_HIGH) * 0.7
        - others             → 0.0  (rely on triggers & fallback ordering)

    Rationale:
        This affects *selection among policies that already triggered*.
        Safety is handled before scoring (e.g., explicit 'fallen' → StandUp).

    -future external/LLM advisory approach for policies:
        We already support 'preferred' in action_center_step(...). To integrate an external
        agent or LLM, expose 'drives_summary(drives)' and world facts; let the agent propose
        a 'preferred' policy string. The controller remains the safety gate (e.g., fallen →
        StandUp overrides everything). See action_center_step docstring for details.
    """
    if name == "policy:seek_nipple":
        return max(0.0, float(drives.hunger) - float(HUNGER_HIGH)) * 1.0
    if name == "policy:rest":
        return max(0.0, float(drives.fatigue) - float(FATIGUE_HIGH)) * 0.7
    return 0.0


def drives_summary(drives: Drives) -> dict:
    """
    Compact snapshot of drives suitable for external advisory/LLM
    Safe to log/serialize; does not include world internals
    """
    return {"hunger": drives.hunger, "fatigue": drives.fatigue, "warmth": drives.warmth, "flags": list(drives.flags())}

# -----------------------------------------------------------------------------
# Policy base
# -----------------------------------------------------------------------------

class Primitive:
    """Abstract policy interface: implement trigger(...) and execute(...).
    -this is informally an abstract base-like class that provides the shared interface (contract) and
       shared helpers while concrete subclasses are shown below (e.g., class StandUp(Primitive), etc )
       actually provide the concrete behavior
    -note: I have decided to avoid the full richness of Python (e.g., import ABC and use the abstractmethod decorator)
            here and similar analogous coding/concpets in other places of the codebase, to keep the programming level
            and concepts reasonable (i.e., pragmatic) for future maintainers (hs -- oct '25)
    -shared interface/contract: trigger(...) and execute(...) effectively enforce that the subclass must have its own specific trigger() and execute()
            and if not, trigger() running in the base will return False or execute running in the base ill return self._fail()
            -thus enforcement occurs here which is intentionally forgiving and test-friendly
            (stricter enforcement if we raise NotImplementedError, etc or switch to abc.ABC + @abstractmethod)
    -boilerplate reduction: _success() and _fail() can be re-used by subclasses
    -controller glue: action_center_step(...) chooses a policy (safety → preferred → scoring) and calls _run(...),
             which catches exceptions and still updates SKILLS

    -when writing a new policy:
       1. set name = "policy:your_name"
       2. implement a cheap trigger(...) (reads only)
       3. implement execute(...) (write preds/edges, meta ={"policy": self.name, ...}, then call __success()/__fail() )
       4. add an instance to PRIMITIVES in the right order

    """
    #subclasses should have their own name values but if methods here run
    #as shown in docstring, set name = "policy:your_name"   e.g., "policy:stand_up"
    name: str = "policy:unknown"


    def trigger(self, world, drives: Drives) -> bool:  # pylint: disable=unused-argument
        """Return usually True if this policy should fire in a concrete subclass
        -however, in the base class, will return False
        -uses a → cheap gate; no world writes, returns True or False regarding triggering
        """
        return False


    def execute(self, world, ctx, drives: Drives) -> dict:  # pylint: disable=unused-argument
        """Return usually _success() if policy runs in a concrete subclasses
        -however, in the abstract base class, will return _fail(...)
        -in the concrete subclass execute(...) does the work, returns a normalized payload
        -perform one step; append bindings/edges and return a status dict (base = fail).
        """
        return self._fail("not implemented")


    def _success(self, reward: float, notes: str, **extra) -> dict:
        """Standard success payload + skill update; extra keys are merged (e.g., binding='b7')
        -return the status dict
        -shared helper with the subclasses
        """
        update_skill(self.name, reward, ok=True)
        payload = {"policy": self.name, "status": "ok", "reward": float(reward), "notes": notes}
        if extra:
            payload.update(extra)
        return payload


    def _fail(self, notes: str, reward: float = 0.0, **extra) -> dict:
        """Standard fail payload + skill update; extra keys are merged
        -return the status dict
        -shared helper with the subclasses
        """
        update_skill(self.name, reward, ok=False)
        payload = {"policy": self.name, "status": "fail", "reward": float(reward), "notes": notes}
        if extra:
            payload.update(extra)
        return payload


# -----------------------------------------------------------------------------
# Concrete policies
# -----------------------------------------------------------------------------

def _policy_meta(ctx, policy_name: str) -> dict:
    """Helper function that contains the common meta boilerplate used by each policy.
    Note that we now timestamp with ticks.
    """
    now = datetime.now().isoformat(timespec="seconds")
    m = {"policy": policy_name, "created_at": now, "ticks": getattr(ctx, "ticks", 0)}
    h = getattr(ctx, "tvec64", None)
    if callable(h):
        try:
            m["tvec64"] = h()
        except (AttributeError, TypeError, ValueError):
            pass
    # Epoch stamp (which boundary epoch this write belonged to)
    bno = getattr(ctx, "boundary_no", None)
    if isinstance(bno, int):
        m["epoch"] = bno
    bvh = getattr(ctx, "boundary_vhash64", None)
    if isinstance(bvh, str):
        m["epoch_vhash64"] = bvh
    return m


class StandUp(Primitive):
    """Primitive that creates a tiny posture chain and marks standing
    -see above for the division of work between the abstract base class (class Primitive) and the
       subclasses doing the concrete work such as class StandUp here, which represents the StandUp policy
    -tips in writing this and other new subclasses which are the policies of the CCA8:
       1. set name = "policy:your_name"
       2. implement a cheap trigger(...) (reads only)
       3. implement execute(...) (write preds/edges, meta ={"policy": self.name, ...}, then call __success()/__fail() )
       4. add an instance to PRIMITIVES in the right order

    Trigger:
        Fires only when the graph shows a fallen state (safety override)
        (previous code: Fires if fallen OR when hunger is high and the agent is not already upright)
        -the concept of a "cheap gate" == a fast, read-only eligibility check; lives in the trigger(...), and should:
            -do no writes to the world graph (no new nodes/edges/tags)
            -be computationally light (some flags or booleans, a few tag lookups)
            -be safe to call every tick for every policy
            -purpose is to keep Action Center snappy -- it can ask all primitives "ready?" without mutating state, then let
              the chosen policy's execute(...) do the actual writes
    Execute:
        Add predicates:
            action:push_up -> action:extend_legs -> state:posture_standing
        Add 'then' edges between them.
        Stamp meta.policy = 'policy:stand_up' on the final binding.
        Return success with reward=+1.0, notes='standing'.
    """
    #policy name
    name = "policy:stand_up"


    def trigger(self, world, drives: Drives) -> bool:
        '''
         -each subclass must have its own trigger(...); if not as seen above the
            base class Primitive's trigger() will run and return a False
         -note that the trigger() method fires only if the worldgraph shows STATE_POSTURE_FALLEN
         - _has(world, token) calls _any_tag(....) after checking CANON_SYNONYMS and
              _any_tag(world, pred) checks to see if any binding is holding pred
        -if there is a tag that the calf has fallen, then the trigger(...) returns True before any other evaluations
        -if not, then check to see if STATE_POSTURE_STANDING and will return False
        -if not, then looks at drives.flags() and if not fatige_high but if hunger_high then returns True, otherwise False

         '''
        # Safety-first: if explicitly fallen (alias or canonical), stand up.
        if _has(world, STATE_POSTURE_FALLEN) or _has(world, "posture:fallen"):
            return True
        # If already upright (alias or canonical), don't fire.
        if _has(world, STATE_POSTURE_STANDING) or _has(world, "posture:standing"):
            return False
        # Posture unknown: prefer readiness if hungry, but yield to Rest if very fatigued.
        flags = set(drives.flags())
        if "drive:fatigue_high" in flags:
            return False
        if "drive:hunger_high" in flags:
            return True
        #otherwise the policy does not trigger
        return False


    def execute(self, world, ctx, drives):
        """
        Create a short 'stand up' sequence:
          pred:action:push_up -> pred:action:extend_legs -> final standing node

        - recall that _add_pred(...) calls world.add_predicate(_canon(token), **kwargs)
        - recall that _add_tag_to_binding(....) calls tags.add(full_tag) where tags = tags from particular binding in world
        - recall that world.add_edge(...) adds an edge from binding where it is stored to specified binding
        - adds ACTION_PUSH_UP predicate, adds ACTION_EXTEND_LEGS predicate, adds "posture:standing" predicate, adds tag to that binding
            "pred:state:posture_standing", adds and edge from each predicate to the next and then returns self._success(...)
        - if these operations fail then returns self._fail(...)

        -node policy:
           -Real WorldGraph: write legacy alias pred:posture:standing (to satisfy older tests & tools),
            then also tag that SAME binding with pred:state:posture_standing.
           -FakeWorld tests: write only pred:state:posture_standing (keeps canonical-only test passing).
        """
        meta = _policy_meta(ctx, self.name)
        try:
            _add_action(world, ACTION_PUSH_UP,     attach="now",    meta=meta)
            _add_action(world, ACTION_EXTEND_LEGS, attach="latest", meta=meta)

            # Final state: canonical posture:standing predicate
            c = _add_pred(world, STATE_POSTURE_STANDING, attach="latest", meta=meta)

            return self._success(reward=1.0, notes="stood up", binding=c)
        except Exception as e:
            return self._fail(f"stand_up failed: {e}")


class SeekNipple(Primitive):
    """
    Seek the maternal nipple after safety and posture checks.

    Intent
    ------
    Escalate orientation toward the maternal stimulus and mark a "seeking" state
    when hunger is high and the agent is upright. This is a reward-seeking follow-up
    policy that assumes the safety posture is already under control.

    Triggers (read-only gates)
    --------------------------
    • hunger_high flag present (from Drives.flags())
    • upright (either canonical 'state:posture_standing' or legacy 'posture:standing')
    • not fallen (canonical or legacy)
    • not already in a 'seeking_mom' state (canonical or legacy)

    Execution (world writes)
    ------------------------
    1) Append `pred:action:orient_to_mom` (attach='now').
    2) Finalize with a "seeking" state:
       • Real WorldGraph: write legacy `pred:seeking_mom` and also tag the SAME
         binding with `pred:state:seeking_mom` for canonical reads.
       • FakeWorld tests: write only `pred:state:seeking_mom`.
    3) Connect with 'then' edge(s).
    4) Return `_success(reward=0.5, notes="seeking mom")`.

    Parameters
    ----------
    world : WorldGraph-like
        Must support `add_predicate(...)` and (on real builds) carry `_bindings`
        so helpers can tag the same binding. See `WorldGraph.add_predicate` for
        normalization and attach semantics.
    ctx : Any
        Runtime context (not used here beyond provenance).
    drives : Drives
        Provides the `flags()` signal for gating.

    Returns
    -------
    dict
        Standard controller payload: {"policy","status","reward","notes",...}.

    Side Effects
    ------------
    • Mutates the WorldGraph (adds 1–2 bindings, edges).
    • Updates the skill ledger EMA via `_success(...)`.

    Notes
    -----
    • Alias/canonical mapping is handled by controller helpers; token storage and
      normalization are handled by `WorldGraph.add_predicate(...)`.
    """
    name = "policy:seek_nipple"


    def trigger(self, world, drives: Drives) -> bool:
        """Cheap gate (no writes). See class docstring for conditions. Returns True if eligible.
        """
        flags = set(drives.flags())
        if "drive:hunger_high" not in flags:
            return False
        if not (_has(world, STATE_POSTURE_STANDING) or _has(world, "posture:standing")):
            return False
        if _has(world, STATE_POSTURE_FALLEN) or _has(world, "posture:fallen"):
            return False
        if _has(world, STATE_SEEKING_MOM) or _has(world, "seeking_mom"):
            return False
        return True


    def execute(self, world, ctx, drives: Drives) -> dict:
        """
        Append an orientation→seeking chain, stamp provenance, and return success.
        See class docstring for exact write pattern and side effects.
        """
        meta = _policy_meta(ctx, self.name)
        _add_action(world, ACTION_ORIENT_TO_MOM, attach="now", meta=meta)
        # Final state: canonical seeking_mom predicate
        b = _add_pred(world, STATE_SEEKING_MOM, attach="latest", meta=meta)
        return self._success(reward=0.5, notes="seeking mom", binding=b)


class FollowMom(Primitive):
    """
    Permissive fallback policy: keep the agent alert and scanning.

    Intent
    ------
    Provide a low-cost default when no stronger need triggers. It keeps the
    episode timeline moving and marks an "alert" state that downstream logic
    can read as a mild arousal baseline.

    Trigger
    -------
    Returns True unconditionally (permissive). If you want occasional 'noop'
    controller step from the Action Center, tighten this trigger (e.g., skip when the
    agent just acted, is very fatigued, or strong cues are present).

    Execution
    ---------
    • Append `pred:action:look_around` (attach='now').
    • Finalize with `pred:state:alert`.
    • Connect with 'then' and return `_success(reward=0.1, notes="idling/alert")`.

    Parameters
    ----------
    world : WorldGraph-like
    ctx : Any
    drives : Drives

    Returns
    -------
    dict : standard controller payload.

    Side Effects
    ------------
    • Mutates the WorldGraph (adds 2 predicates + 1 edge).
    • Updates the skill ledger EMA.

    Ordering Note
    -------------
    This primitive sits **after** Rest in `PRIMITIVES` so need-driven policies
    (fatigue/hunger) win first; its permissive nature would otherwise mask them.
    """
    name = "policy:follow_mom"


    def trigger(self, world, drives: Drives) -> bool:
        """Always True (permissive fallback). Tighten if you want occasional no-ops."""
        return True


    def execute(self, world, ctx, drives: Drives) -> dict:
        """Append look_around→alert and return success (see class docstring).
        """
        meta = _policy_meta(ctx, self.name)
        a = _add_action(world, ACTION_LOOK_AROUND, attach="now", meta=meta)
        b = _add_pred(world, STATE_ALERT, meta=meta)
        world.add_edge(a, b, "then")
        return self._success(reward=0.1, notes="idling/alert")


class ExploreCheck(Primitive):
    """
    Periodic/diagnostic exploration hook (disabled by default).

    Intent
    ------
    Reserve a slot for future environment sampling / curiosity behavior without
    committing to a design now. Useful as a placeholder in demos and tests.

    Trigger
    -------
    Returns False (off). You can convert this into a timed/stochastic gate later
    (e.g., every N autonomic ticks, or with small probability when the world is quiet).

    Execution
    ---------
    Returns `_success(reward=0.0, notes="checked")` with **no world writes**
    so that it’s safe to enable during experiments without perturbing the graph.

    Parameters
    ----------
    world : WorldGraph-like
    ctx : Any
    drives : Drives

    Returns
    -------
    dict : standard controller payload.
    """
    name = "policy:explore_check"


    def trigger(self, world, drives: Drives) -> bool:
        """Disabled stub (always False)."""
        return False


    def execute(self, world, ctx, drives: Drives) -> dict:
        """Return a success sentinel without modifying the world."""
        #meta = _policy_meta(ctx, self.name) #not used since a no op policy
        return self._success(reward=0.0, notes="checked")


class Rest(Primitive):
    """
    Reduce fatigue and assert a 'resting' state.

    Intent
    ------
    Provide a simple homeostatic recovery step when fatigue is high.

    Trigger
    -------
    `drives.fatigue > 0.8` (explicit threshold; separate from selection scoring).

    Execution
    ---------
    • Decrease `drives.fatigue` by 0.2 (clamped at 0.0).
    • Append `pred:state:resting` (attach='now').
    • Return `_success(reward=0.2, notes="resting")`.

    Parameters
    ----------
    world : WorldGraph-like
    ctx : Any
    drives : Drives
        Mutated in place (fatigue reduced) as part of the side effect.

    Returns
    -------
    dict : standard controller payload.

    Side Effects
    ------------
    • Mutates Drives (fatigue ↓) and WorldGraph (adds one predicate).
    • Updates the skill ledger EMA.

    Design Note
    -----------
    In `PRIMITIVES`, Rest is ordered **before** the permissive fallback so recovery
    can preempt idling when appropriate; the Action Center may also prefer it via
    deficit scoring when fatigue dominates.
    """
    name = "policy:rest"


    def trigger(self, world, drives: Drives) -> bool:
        """Return True when fatigue is above the hard threshold (> 0.8)."""
        return drives.fatigue > 0.8


    def execute(self, world, ctx, drives: Drives) -> dict:
        """Reduce fatigue, assert 'resting', and return success (see class docstring)."""
        drives.fatigue = max(0.0, drives.fatigue - 0.2)
        meta = _policy_meta(ctx, self.name)
        _add_pred(world, STATE_RESTING, attach="now", meta=meta)
        return self._success(reward=0.2, notes="resting")

# -----------------------------------------------------------------------------
# Primitives to be Scanned by the Action Center
# -----------------------------------------------------------------------------

# Ordered repertoire scanned by the Action Center
# Action Center behavior (single-step orchestrator):
#   1) Safety short-circuit: if the world shows 'fallen' → run StandUp immediately.
#   2) Otherwise scan PRIMITIVES in order and call trigger(world, drives) on each (cheap, read-only).
#   3) If multiple triggers are True, select by deficit score (e.g., hunger for seek, fatigue for rest),
#      with this list order as a final tiebreaker. See _policy_deficit_score(...) and the Action Center notes.
#   4) Execute the chosen policy; _run(...) ensures skill accounting on success/failure.
#
# Policy summaries (why this order):
#   • StandUp      — Safety-first posture recovery; must come first.
#   • SeekNipple   — Hunger-driven seeking; runs when upright & hungry, not fallen, not already seeking.
#   • Rest         — Homeostatic recovery when very fatigued; placed before the permissive fallback.
#   • FollowMom    — Permissive fallback (trigger is usually True); keeps the loop producing 'ok' steps
#                    instead of 'noop' when nothing else is pressing. Tighten its trigger if you want
#                    occasional no-op controller steps.
#   • ExploreCheck — Diagnostic placeholder; disabled stub for future exploration logic.
#
# **Important**
#      -When you add a new policy class, you must also instantiate it and add it to PRIMITIVES or
#        the Action Center will never consider it.
#      -The list’s order matters (used as a final tie-breaker after deficit scoring), so place your new policy where its priority makes sense.
#      -If you want the class importable from the module, add its name to __all__ too
#
PRIMITIVES: List[Primitive] = [
    StandUp(),
    SeekNipple(),
    Rest(),         # check restorative action before permissive fallback
    FollowMom(),    # permissive default should be after concrete needs
    ExploreCheck(),
]

# -----------------------------------------------------------------------------
# Action Center
# -----------------------------------------------------------------------------

def _run(policy, world, ctx, drives) -> dict:
    """
    -This is a wrapper used by action_center_step(...) to execute a policy of one of the
       subclasses above
    -The code consists of:  return policy.execute(world, ctx, drives)
       plus an exception branch in which case it will run update_skill(...) and return a dict with {policy:name, status:error, ...}
    -sample input parameter arguments, e.g. --
      policy = <cca8_controller.StandUp object at 0x0000021DC09B0890>
      world  = <cca8_world_graph.WorldGraph object at 0x0000021DC0A50C50>
      ctx =  Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0, profile='Mountain Goat', winners_k=2, hal=None, body='(none)')
      drives = Drives(hunger=0.7, fatigue=0.2, warmth=0.6)

    -therefore in this example:  return StandUp.execute(WorldGraph, Ctx, Drives)
            -StandUp.execute(self, world, ctx, drives) is shown above
            - adds ACTION_PUSH_UP predicate, adds ACTION_EXTEND_LEGS predicate, adds "posture:standing" predicate, adds tag to that binding
                  "pred:state:posture_standing", adds and edge from each predicate to the next and then returns self._success(...)
    -keeping error handling + accounting in one place lets policy classes stay small and focused on world edits, while the Action Center treats every step uniformly.

    Parameters
    ----------
    world : WorldGraph-like engine the policy may mutate (predicates/edges/tags).
    ctx   : Opaque run context passed through to policies.
    policy: Primitive instance being executed (must define `name`).
    drives: Drives; policies may read and (occasionally) mutate it.

    Returns
    -------
    dict
        Normalized controller payload, e.g.:
        {
          "policy": "policy:stand_up",
          "status": "ok" | "fail" | "error",
          "reward": float,            # 0.0 on errors, policy-defined otherwise
          "notes": str,               # human-readable summary
          ...                         # any extra keys the policy adds (e.g., binding=...)
        }

    Side Effects
    ------------
    • Mutates `world` if/when the policy performs writes.
    • Updates the skill ledger (via `_success/_fail`; on exceptions, via this wrapper).
    • May emit a brief diagnostic in error paths.

    """
    try:
        return policy.execute(world, ctx, drives)
    except Exception as e:
        update_skill(policy.name, 0.0, ok=False)
        return {"policy": policy.name, "status": "error", "reward": 0.0, "notes": f"exec error: {e}"}


def action_center_step(world, ctx, drives: Drives, preferred: str | None = None) -> dict:
    """
    Run one controller step.

    Order of operations:
        1) Safety override: if fallen, force StandUp (ignores 'preferred').
        2) If 'preferred' is provided, execute that exact policy (controller still handles errors).
        3) Otherwise: evaluate triggers; if multiple triggered, choose by drive deficit
           If all scores are zero, fall back to the legacy scan order for backward-compat.

    -sample input parameter arguments, e.g. --
      world  = <cca8_world_graph.WorldGraph object at 0x0000021DC0A50C50>
      ctx =  Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0, profile='Mountain Goat', winners_k=2, hal=None, body='(none)')
      drives = Drives(hunger=0.7, fatigue=0.2, warmth=0.6)

    -preferred trigger mechanism --
        - Provide an external agent with a small state (see drives_summary(...), and any
          whitelisted world facts). Let that agent suggest 'preferred' by name.
        - Pass preferred='policy:...' here. Safety checks still run first.
        - This preserves a single source of truth for execution while allowing richer selection
          logic without coupling the controller to any specific agent/LLM.
    """
    # (1) Safety-first: explicit fallen → StandUp
    if _has(world, STATE_POSTURE_FALLEN) or _has(world, "posture:fallen"):
        stand = None
        for p in PRIMITIVES:
            if p.name == "policy:stand_up":
                stand = p
                break
        assert stand is not None, "Action Center safety override: StandUp policy not registered"
        return _run(stand, world, ctx, drives)

    # (2) External advisory path (Option B-ready): honor exact 'preferred' if present
    #  e.g., preferred="policy:rest" as specified by the argument to the function
    if preferred:
        chosen = next((p for p in PRIMITIVES if p.name == preferred), None) #next generator value
        if chosen:
            return _run(chosen, world, ctx, drives)

    # (3) Trigger evaluation -- if multiple triggers choose by drive deficit
    triggered = []
    for policy in PRIMITIVES:
        try:
            if policy.trigger(world, drives):
                triggered.append(policy)
        except Exception:
            continue

    if not triggered:
        return {"policy": None, "status": "noop", "reward": 0.0, "notes": "no triggers matched"}

    # If exactly one triggered, no need to score.
    if len(triggered) == 1:
        return _run(triggered[0], world, ctx, drives)

    # Multiple triggered -- choose by drive deficit
    scored = [(p, _policy_deficit_score(p.name, drives)) for p in triggered]
    max_score = max(s for _, s in scored)

    if max_score > 0.0:
        # break ties by preserving PRIMITIVES stable order
        names_in_order = [p.name for p in PRIMITIVES]
        chosen = max(scored, key=lambda ps: (ps[1], -names_in_order.index(ps[0].name)))[0]
        return _run(chosen, world, ctx, drives)

    # If all scores are zero, fall back to legacy scan order (back-compat)
    for p in PRIMITIVES:
        if p in triggered:
            return _run(p, world, ctx, drives)

    # Should not reach here — invariant violation (triggered was non-empty)
    raise RuntimeError("Action Center invariant violated: no policy chosen from non-empty 'triggered' set; "
        f"triggered={[p.name for p in triggered]}, preferred={preferred}, flags={list(drives.flags())}")
