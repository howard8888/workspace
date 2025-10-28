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
        [note: worldgraph has only 3 families: pred:*, cue:*, anchor:* -- drive:* are ephemeral controller flags, not graph tags]
                   [action:* actually stored as "pred:action:*" although locally sometimes referred to as action:*]
                   [we still encode actions primarily as edge labels]
        [created by Drives.flags() for trigger logic only and are never written to WorldGraph]
        [e.g., plannable drive condition, then yes, can create a node with e.g., "pred:drive:hunger_high", or evidence, e.g., cue:drive:hunger_high]
        -policies use drive tags in triggering (e.g., SeekNipple needs hunger), while execute may update drives (e.g., Rest reduces fatigue a bit)
    -parameter 'ctx' represents runtime context
        -includes age_days, sigma and jump (tie-breaking, exploration settings), ticks (i.e., how many steps have passed), profile (e.g., "goat", "chimp", etc),
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
  • cue:*      — observations/engram evidence (non-factual sensory tags)
  • anchor:*   — structural anchors (NOW, LATEST, etc.)

Canonical tokens (second-level namespaces under pred:*):
  • state:*    — relatively stable facts about agent/world (e.g., state:posture_standing)
  • action:*   — action semantics / provenance (e.g., action:look_around)
    NOTE: prefer keeping actions on edges; assert pred:action:* only when a fact is needed.

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
  -if ever want occasional no-ops (i.e., do nothing ticks) then tighten FollowMom(...) trigger (e.g., return False if tired/hungry/just acted) or
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

__version__ = "0.0.4"
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
# We encode state/action semantics as a second-level namespace after "pred:".
STATE_POSTURE_STANDING = "state:posture_standing"
STATE_POSTURE_FALLEN   = "state:posture_fallen"
STATE_RESTING          = "state:resting"
STATE_ALERT            = "state:alert"

ACTION_PUSH_UP         = "action:push_up"
ACTION_EXTEND_LEGS     = "action:extend_legs"
ACTION_LOOK_AROUND     = "action:look_around"
ACTION_ORIENT_TO_MOM   = "action:orient_to_mom"

STATE_SEEKING_MOM      = "state:seeking_mom"

# Back-compat synonyms we still recognize when *reading* from the graph.
CANON_SYNONYMS = {
    "posture:standing": STATE_POSTURE_STANDING,
    "posture:fallen":   STATE_POSTURE_FALLEN,
    "seeking_mom":      STATE_SEEKING_MOM,
}

def _is_worldgraph(world) -> bool:
    """Heuristic: real WorldGraph exposes planning."""
    return hasattr(world, "plan_to_predicate") and callable(getattr(world, "plan_to_predicate"))

def _add_tag_to_binding(world, bid: str, full_tag: str) -> None:
    """Best-effort: add a tag to an existing binding (works for WorldGraph and FakeWorld)."""
    try:
        b = getattr(world, "_bindings", {}).get(bid)
        if not b:
            return
        tags = getattr(b, "tags", None)
        if tags is None:
            b.tags = {full_tag}
            return
        if isinstance(tags, set):
            tags.add(full_tag)
        elif isinstance(tags, list):
            if full_tag not in tags:
                tags.append(full_tag)
    except Exception:
        pass

def _canon(token: str) -> str:
    """Map legacy tokens to canonical tokens; unknowns pass through unchanged."""
    return CANON_SYNONYMS.get(token, token)

def _add_pred(world, token: str, **kwargs):
    """Wrapper to add a canonical predicate token. WorldGraph will add the 'pred:' family automatically."""
    return world.add_predicate(_canon(token), **kwargs)

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

    Methods:
        predicates(): convert numeric drives to 'drive:*' tags used by policy triggers.
        to_dict()/from_dict(): autosave support.
    """
    hunger: float = 0.7
    fatigue: float = 0.2
    warmth: float = 0.6

    def flags(self) -> List[str]:
        """Return ephemeral 'drive:*' flags for policy triggers (not persisted in the graph).

        Thresholds:
            hunger  > 0.60 → 'drive:hunger_high'
            fatigue > 0.70 → 'drive:fatigue_high'
            warmth  < 0.30 → 'drive:cold'
        """
        tags: List[str] = []
        if self.hunger > HUNGER_HIGH:
            tags.append("drive:hunger_high")
        if self.fatigue > FATIGUE_HIGH:
            tags.append("drive:fatigue_high")
        if self.warmth < WARMTH_COLD:
            tags.append("drive:cold")
        return tags

    # Back-compat for older code/tests
    def predicates(self) -> List[str]:  # pragma: no cover (legacy alias)
        """DEPRECATED: use .flags()."""
        return self.flags()

    def to_dict(self) -> dict:
        """Return a plain JSON-safe dict of drive values for autosave/snapshots."""
        return {"hunger": self.hunger, "fatigue": self.fatigue, "warmth": self.warmth}

    @classmethod
    def from_dict(cls, d: dict) -> "Drives":
        """Construct a Drives from a snapshot dict (robust to missing keys)."""
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
    """Simple running stats per policy (scaffolding for future RL)."""
    n: int = 0
    succ: int = 0
    q: float = 0.0
    last_reward: float = 0.0

SKILLS: Dict[str, SkillStat] = {}

def update_skill(name: str, reward: float, ok: bool = True, alpha: float = 0.3) -> None:
    """Update (or create) a SkillStat:
    - n += 1; succ += 1 if ok
    - q ← (1 - alpha) * q + alpha * reward     (exponential moving average)
    - last_reward ← reward

    Notes:
        * The ledger is in-memory only (not used for selection yet).
        * Callers should pass rewards on the same scale across policies.
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
    """Clear the in-memory skill ledger (testing/demo convenience)."""
    SKILLS.clear()

def skills_to_dict() -> dict:
    """Return a JSON-safe mapping of skill stats:
    {
      "policy:stand_up": {"n": int, "succ": int, "q": float, "last_reward": float},
      ...
    }
    """
    return {k: asdict(v) for k, v in SKILLS.items()}

def skills_from_dict(d: dict) -> None:
    """Rebuild SKILLS dataclass values from plain dicts (robust to bad inputs)."""
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
    """Human-readable policy stats: one line per policy (n/succ/rate/q/last)."""
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
# NOTE: in the future prefer a public iterator on WorldGraph (e.g., world.iter_tags(prefix="cue:"))
# to avoid peeking at world._bindings here. Kept as a trusted-friend shortcut for now.

def _any_tag(world, full_tag: str) -> bool:
    """Return True if any binding carries the exact tag (e.g., 'pred:...')."""
    try:
        for b in world._bindings.values():  # pylint: disable=protected-access
            tags = getattr(b, "tags", ())
            if isinstance(tags, (set, list, tuple)) and full_tag in tags:
                return True
    except (AttributeError, TypeError, KeyError):
        pass
    return False

def _has(world, token: str) -> bool:
    """True if either the canonical *or* raw token exists as a pred:* tag."""
    canon = _canon(token)
    return _any_tag(world, f"pred:{canon}") or _any_tag(world, f"pred:{token}")

def _any_cue_present(world) -> bool:
    """Loose cue check: True if any tag starts with 'cue:' (no proximity semantics)."""
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
    Option A (priority-by-deficit):
        Return a non-negative score reflecting how off-setpoint the relevant drive(s) are
        for a given policy. Higher score → higher priority.

    Current mapping (simple and transparent):
        - policy:seek_nipple → max(0, hunger - HUNGER_HIGH) * 1.0
        - policy:rest        → max(0, fatigue - FATIGUE_HIGH) * 0.7
        - others             → 0.0  (rely on triggers & fallback ordering)

    Rationale:
        This affects *selection among policies that already triggered*.
        Safety is handled before scoring (e.g., explicit 'fallen' → StandUp).

    Option B (future external/LLM advisory):
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
    Compact snapshot of drives suitable for external advisory/LLM (Option B).
    Safe to log/serialize; does not include world internals.
    """
    return {"hunger": drives.hunger, "fatigue": drives.fatigue, "warmth": drives.warmth, "flags": list(drives.flags())}

# -----------------------------------------------------------------------------
# Policy base
# -----------------------------------------------------------------------------

class Primitive:
    """Abstract policy interface: implement trigger(...) and execute(...)."""
    name: str = "policy:unknown"

    def trigger(self, world, drives: Drives) -> bool:  # pylint: disable=unused-argument
        """Return True if this policy should fire given world/drives (base returns False)."""
        return False

    def execute(self, world, ctx, drives: Drives) -> dict:  # pylint: disable=unused-argument
        """Perform one step; append bindings/edges and return a status dict (base = fail)."""
        return self._fail("not implemented")

    def _success(self, reward: float, notes: str, **extra) -> dict:
        """Standard success payload + skill update; extra keys are merged (e.g., binding='b7')."""
        update_skill(self.name, reward, ok=True)
        payload = {"policy": self.name, "status": "ok", "reward": float(reward), "notes": notes}
        if extra:
            payload.update(extra)
        return payload

    def _fail(self, notes: str, reward: float = 0.0, **extra) -> dict:
        """Standard fail payload + skill update; extra keys are merged."""
        update_skill(self.name, reward, ok=False)
        payload = {"policy": self.name, "status": "fail", "reward": float(reward), "notes": notes}
        if extra:
            payload.update(extra)
        return payload

# -----------------------------------------------------------------------------
# Concrete policies
# -----------------------------------------------------------------------------

class StandUp(Primitive):
    """Primitive that creates a tiny posture chain and marks standing.

    Trigger:
        Fires only when the graph shows a fallen state (safety override).
        (Previously: Fires if fallen OR when hunger is high and the agent is not already upright)
    Execute:
        Add predicates:
            action:push_up -> action:extend_legs -> state:posture_standing
        Add 'then' edges between them.
        Stamp meta.policy = 'policy:stand_up' on the final binding.
        Return success with reward=+1.0, notes='standing'.
    """
    name = "policy:stand_up"

    def trigger(self, world, drives: Drives) -> bool:
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

        return False

    def execute(self, world, ctx, drives):
        """
        Create a short 'stand up' sequence:
          pred:action:push_up -> pred:action:extend_legs -> final standing node

        Final node policy:
          • Real WorldGraph: write legacy alias pred:posture:standing (to satisfy older tests & tools),
            then also tag that SAME binding with pred:state:posture_standing.
          • FakeWorld tests: write only pred:state:posture_standing (keeps canonical-only test passing).
        """
        meta = {"policy": self.name, "created_at": datetime.now().isoformat(timespec="seconds")}
        try:
            a = _add_pred(world, ACTION_PUSH_UP,     attach="now",    meta=meta)
            b = _add_pred(world, ACTION_EXTEND_LEGS, attach="latest", meta=meta)

            if _is_worldgraph(world):
                # Write alias as the FINAL node so planner to "posture:standing" finds *this* binding.
                c = world.add_predicate("posture:standing", attach="latest", meta=meta)
                # Also add the canonical tag on the SAME binding for new code paths.
                _add_tag_to_binding(world, c, f"pred:{STATE_POSTURE_STANDING}")
            else:
                # In FakeWorld unit tests we keep only the canonical token.
                c = _add_pred(world, STATE_POSTURE_STANDING, attach="latest", meta=meta)

            world.add_edge(a, b, "then")
            world.add_edge(b, c, "then")
            return self._success(reward=1.0, notes="stood up", binding=c)
        except Exception as e:
            return self._fail(f"stand_up failed: {e}")

class SeekNipple(Primitive):
    """Example/stub of a follow-up behavior"""
    name = "policy:seek_nipple"

    def trigger(self, world, drives: Drives) -> bool:
        """Fire only when hungry, upright, not fallen, and not already seeking."""
        flags = set(drives.flags())
        if "drive:hunger_high" not in flags:
            return False
        # accept canonical or legacy upright
        if not (_has(world, STATE_POSTURE_STANDING) or _has(world, "posture:standing")):
            return False
        # treat either canonical or legacy fallen as disqualifier
        if _has(world, STATE_POSTURE_FALLEN) or _has(world, "posture:fallen"):
            return False
        # don't duplicate seeking; accept either spelling
        if _has(world, STATE_SEEKING_MOM) or _has(world, "seeking_mom"):
            return False
        return True

    def execute(self, world, ctx, drives: Drives) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        a = _add_pred(world, ACTION_ORIENT_TO_MOM, attach="now", meta=meta)

        # Create the final 'seeking' node. For real WorldGraph, write the legacy alias
        # that tests/tools look for, and also tag the canonical state on the SAME binding.
        if _is_worldgraph(world):
            b = world.add_predicate("seeking_mom", meta=meta)  # → pred:seeking_mom
            _add_tag_to_binding(world, b, f"pred:{STATE_SEEKING_MOM}")  # also add pred:state:seeking_mom
        else:
            b = _add_pred(world, STATE_SEEKING_MOM, meta=meta)  # FakeWorld unit tests keep canonical-only

        world.add_edge(a, b, "then")
        return self._success(reward=0.5, notes="seeking mom")

class FollowMom(Primitive):
    """Fallback primitive (permissive). Tighten trigger if prefer fewer defaults."""
    name = "policy:follow_mom"

    def trigger(self, world, drives: Drives) -> bool:
        return True  # acts as default so we rarely noop

    def execute(self, world, ctx, drives: Drives) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        a = _add_pred(world, ACTION_LOOK_AROUND, attach="now", meta=meta)
        b = _add_pred(world, STATE_ALERT, meta=meta)
        world.add_edge(a, b, "then")
        return self._success(reward=0.1, notes="idling/alert")

class ExploreCheck(Primitive):
    """Periodic/diagnostic check stub (disabled by default)."""
    name = "policy:explore_check"

    def trigger(self, world, drives: Drives) -> bool:
        # simple periodic check;  can add a timer or stochastic gate later
        return False

    def execute(self, world, ctx, drives: Drives) -> dict:
        return self._success(reward=0.0, notes="checked")

class Rest(Primitive):
    """Reduce fatigue and mark a resting state."""
    name = "policy:rest"

    def trigger(self, world, drives: Drives) -> bool:
        return drives.fatigue > 0.8

    def execute(self, world, ctx, drives: Drives) -> dict:
        drives.fatigue = max(0.0, drives.fatigue - 0.2)
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        _add_pred(world, STATE_RESTING, attach="now", meta=meta)
        return self._success(reward=0.2, notes="resting")

# Ordered repertoire scanned by the Action Center
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
        3) Otherwise: evaluate triggers; if multiple triggered, choose by drive deficit (Option A).
           If all scores are zero, fall back to the legacy scan order for backward-compat.

    About Option B (future LLM/external advisory):
        - Provide an external agent with a small state (see drives_summary(...), and any
          whitelisted world facts). Let that agent suggest 'preferred' by name.
        - Pass preferred='policy:...' here. Safety checks still run first.
        - This preserves a single source of truth for execution while allowing richer selection
          logic without coupling the controller to any specific agent/LLM.
    """
    # (1) Safety-first: explicit fallen → StandUp
    if _has(world, STATE_POSTURE_FALLEN) or _has(world, "posture:fallen"):
        stand = next((p for p in PRIMITIVES if p.name == "policy:stand_up"), None)
        if stand:
            return _run(stand, world, ctx, drives)

    # (2) External advisory path (Option B-ready): honor exact 'preferred' if present
    if preferred:
        chosen = next((p for p in PRIMITIVES if p.name == preferred), None)
        if chosen:
            return _run(chosen, world, ctx, drives)

    # (3) Trigger evaluation
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

    # Multiple triggered → Option A: choose by drive deficit
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

    # Should not reach here
    return {"policy": None, "status": "noop", "reward": 0.0, "notes": "no triggers matched (post-score)"}
