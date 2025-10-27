# -*- coding: utf-8 -*-
"""
CCA8 Controller: drives, primitives ("policies"), and action center.

Concepts
--------
- Drives: numeric homeostatic values (hunger, fatigue, warmth) → derive 'drive:*' tags.
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

Action loop
-----------
-the Action Center is like a single-step orchestrator --
   -safety short-circuit, e.g., if the world shows a fallen state then immediately run StandUp
   -otherwise scan PRIMITIVES in order call trigger(world, dirves)
   -run the first policy whose trigger is True --> _run wraps execute(...) and updates the skill ledger
   -returns a status dict {"policy":"policy:<name>" | None, "status": "ok|fail|noop|error", "reward":float, "notes":str}
-the order of PRIMITIVES matters and we placed in our priority scheme:
   StandUp (safety) --> SeekNipple(hunger) --> Rest (fatigue) --> FollowMom (fallback) --> ExploreCheck (stub)
A permissive fallback (e.g., FollowMom) (i.e., a policy whose trigger(...) is basically always True or at least in most normal states)
  -the action center returns {"status":"noop"} only when no policy triggers
  -if FollowMom.trigger(...) is nearly always True, then never see a "noop" because the fallback will always fire and produce an "ok" step instead
  -if ever want occasional no-ops (i.e., do nothing ticks) then tighten FollowMom(...) trigger (e.g., return False if tired/hungry/just acted) or
     move FollowMom even further down or add a timer/debounce so it doesn't constantly fire

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

__version__ = "0.0.3"
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
    """Convenience: token like 'state:posture_fallen' → checks 'pred:<token>' anywhere."""
    return _any_tag(world, f"pred:{token}")

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
        Fires if fallen OR when hunger is high and the agent is not already upright
    Execute:
        Add predicates:
            action:push_up -> action:extend_legs -> state:posture_standing
        Add 'then' edges between them.
        Stamp meta.policy = 'policy:stand_up' on the final binding.
        Return success with reward=+1.0, notes='standing'.
    """
    name = "policy:stand_up"

    def trigger(self, world, drives: Drives) -> bool:
        # Safety-first: if fallen, allow stand-up regardless of historical standing
        if _has(world, "state:posture_fallen") or _has(world, "posture:fallen"):
            return True

        # Otherwise require hunger_high (toy heuristic)
        if "drive:hunger_high" not in set(drives.flags()):
            return False

        # Guard: if already upright now (historically recorded), skip
        # (This is a coarse global check; runner guards the near-NOW case.)
        if _has(world, "state:posture_standing") or _has(world, "posture:standing"):
            return False
        return True

    def execute(self, world, ctx, drives):
        """
        Create a short 'stand up' sequence and finish at the canonical state:
        pred:posture:standing

        Meta:
            binding.meta = {"policy": "policy:stand_up", "created_at": "<ISO time>"}
            edge.meta    = same dict if you choose to add one on edges later.
        """
        meta = {"policy": self.name, "created_at": datetime.now().isoformat(timespec="seconds")}
        try:
            world.add_predicate("action:push_up",     attach="now",    meta=meta)
            world.add_predicate("action:extend_legs", attach="latest", meta=meta)
            b_stand = world.add_predicate("posture:standing", attach="latest", meta=meta)
            return self._success(reward=1.0, notes="stood up", binding=b_stand)
        except Exception as e:
            return self._fail(notes=f"exec error: {e}")

class SeekNipple(Primitive):
    """Example/stub of a follow-up behavior"""
    name = "policy:seek_nipple"

    def trigger(self, world, drives: Drives) -> bool:
        """
        Fire only when hungry, upright, not fallen, and not already seeking.
        Accept both legacy and canonical posture tags for backward compatibility.
        """
        flags = set(drives.flags())
        if "drive:hunger_high" not in flags:
            return False

        # must be upright (accept old or canonical form)
        if not (_has(world, "state:posture_standing") or _has(world, "posture:standing")):
            return False

        # do NOT seek while fallen; recover first (accept old or canonical form)
        if _has(world, "state:posture_fallen") or _has(world, "posture:fallen"):
            return False

        # avoid re-firing if already seeking (accept old or canonical form)
        if _has(world, "state:seeking_mom") or _has(world, "seeking_mom"):
            return False

        return True

    def execute(self, world, ctx, drives: Drives) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        a = world.add_predicate("action:orient_to_mom", attach="now", meta=meta)
        b = world.add_predicate("seeking_mom",                 meta=meta)
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
        a = world.add_predicate("action:look_around", attach="now", meta=meta)
        b = world.add_predicate("state:alert",                     meta=meta)
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
        world.add_predicate("state:resting", attach="now", meta=meta)  # (no assignment)
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


def action_center_step(world, ctx, drives: Drives) -> dict:
    """Scan PRIMITIVES in order; run the first policy whose trigger returns True.

    Returns:
        {"policy": "policy:<name>"|None, "status": "ok|fail|noop|error", "reward": float, "notes": str}
    Side effects:
        - Appends new bindings/edges to world.
        - May adjust drives (e.g., fatigue).
        - Updates SKILLS ledger.
    """
    # Safety-first: if fallen, run StandUp immediately
    if _has(world, "state:posture_fallen") or _has(world, "posture:fallen"):
        stand = next((p for p in PRIMITIVES if p.name == "policy:stand_up"), None)
        if stand:
            return _run(stand, world, ctx, drives)

    # Normal scan
    for policy in PRIMITIVES:
        try:
            if policy.trigger(world, drives):
                return _run(policy, world, ctx, drives)
        except Exception:
            # A bad trigger shouldn't kill the loop; try next policy.
            continue

    return {"policy": None, "status": "noop", "reward": 0.0, "notes": "no triggers matched"}
