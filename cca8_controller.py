# -*- coding: utf-8 -*-
"""
CCA8 Controller: drives, primitives ("policies"), and action center.

Concepts
--------
- Drives: numeric homeostatic values (hunger, fatigue, warmth) → derive 'drive:*' tags.
- Policy (primitive): behavior object with `trigger(world, drives)` and `execute(world, ctx, drives)`.
  When executed, a policy appends a *small chain* of predicates/edges to the WorldGraph and returns
  a status dict: {"policy": "policy:<name>", "status": "ok|fail|noop|error", "reward": float, "notes": str}.
- Provenance: bindings created by a policy stamp meta.policy = "policy:<name>".
  "provenance" means when a primitive/policy fires and creates bindings or links we stamp metadata
   eg, "created_by: policy:<name>", timestamp, tag "policy:stand_up", "note: 'standing'"
   thus effective means recording origin so later debugging/credit assignment skill ledger,RL is explainable
   -state predicates, e.g., state:posture_standing, assert something about the agent or world that reasoner can use as facts
   -provenance tags, e.g., policy:stand_up, assert who/what produced this binding/edge rather than something you plan for, it already occurred
   -despite the same effect predicate being produced there could have been two different policies creating it, provenance tags help figure out which one
- Skill ledger: tiny RL-style counters (n, succ, q, last_reward) per policy; not used for selection yet.

Action loop
-----------
`action_center_step(world, ctx, drives)` scans PRIMITIVES in order and runs the *first* whose trigger is true.
A permissive fallback (e.g., FollowMom) prevents 'noop' unless you tighten its trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List



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

    def predicates(self) -> List[str]:
        tags: List[str] = []
        if self.hunger > HUNGER_HIGH:
            tags.append("drive:hunger_high")
        if self.fatigue > FATIGUE_HIGH:
            tags.append("drive:fatigue_high")
        if self.warmth < WARMTH_COLD:
            tags.append("drive:cold")
        return tags

    def to_dict(self) -> dict:
        return {"hunger": self.hunger, "fatigue": self.fatigue, "warmth": self.warmth}


    @classmethod
    def from_dict(cls, d: dict) -> "Drives":
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
    # get-or-create (more readable than setdefault)
    s = SKILLS.get(name)
    if s is None:
        s = SkillStat()
        SKILLS[name] = s

    s.n += 1
    if ok:
        s.succ += 1
    # simple exponential average for q
    s.q = (1 - alpha) * s.q + alpha * float(reward)
    s.last_reward = float(reward)


def skills_to_dict() -> dict:
    """    
    Converts each SkillStat dataclass to a built-in mapping (i.e., plain dict with field names as keys)
       via dataclasses.asdict(), so the result is detached (editing it will not mutate the original SKILLS)
    Returns:
        dict[str, dict[str, float|int]]

    e.g. SKILLS is: {'policy:stand_up': SkillStat(n=1, succ=1, q=0.3, last_reward=1.0)}
    output is: {'policy:stand_up': {'n': 1, 'succ': 1, 'q': 0.3, 'last_reward': 1.0}}   
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

def _any_tag(world, full_tag: str) -> bool:
    """Return True if any binding carries the exact 'pred:...' tag."""
    try:
        for b in world._bindings.values():
            if full_tag in getattr(b, "tags", []):
                return True
    except Exception:
        pass
    return False

def _has(world, token: str) -> bool:
    """Convenience: token like 'state:posture_fallen' → checks 'pred:<token>' anywhere."""
    return _any_tag(world, f"pred:{token}")

def _any_cue_present(world) -> bool:
    """Loose cue check: any vision/smell/sound cue is present (no proximity test here)."""
    try:
        for b in world._bindings.values():
            for t in getattr(b, "tags", []):
                if isinstance(t, str) and (
                    t.startswith("pred:vision:") or t.startswith("pred:smell:") or t.startswith("pred:sound:")
                ):
                    return True
    except Exception:
        pass
    return False


# -----------------------------------------------------------------------------
# Policy base
# -----------------------------------------------------------------------------

class Primitive:
    name: str = "policy:unknown"

    def trigger(self, world, drives: Drives) -> bool:
        return False

    def execute(self, world, ctx, drives: Drives) -> dict:
        return self._fail("not implemented")

    # helpers to standardize return + skill update
    def _success(self, reward: float, notes: str) -> dict:
        update_skill(self.name, reward, ok=True)
        return {"policy": self.name, "status": "ok", "reward": float(reward), "notes": notes}

    def _fail(self, notes: str, reward: float = 0.0) -> dict:
        update_skill(self.name, reward, ok=False)
        return {"policy": self.name, "status": "fail", "reward": float(reward), "notes": notes}


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
        if _has(world, "state:posture_fallen"):
            return True

        # Otherwise require hunger_high (toy heuristic)
        if "drive:hunger_high" not in set(drives.predicates()):
            return False

        # Guard: if already upright now (historically recorded), skip
        # (This is a coarse global check; runner guards the near-NOW case.)
        if _has(world, "state:posture_standing"):
            return False

        return True

    def execute(self, world, ctx, drives: Drives) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        meta_common = {"policy": self.name, "created_at": now}

        b_push  = world.add_predicate("action:push_up",    attach="now", meta=meta_common)
        b_ext   = world.add_predicate("action:extend_legs",               meta=meta_common)
        b_stand = world.add_predicate("state:posture_standing",           meta=meta_common)

        world.add_edge(b_push, b_ext, "then")
        world.add_edge(b_ext, b_stand, "then")

        # simple fatigue bump to show side-effect
        drives.fatigue = min(1.0, drives.fatigue + 0.05)
        return self._success(reward=1.0, notes="standing")


class SeekNipple(Primitive):
    """Example/stub of a follow-up behavior; you can flesh this out later."""
    name = "policy:seek_nipple"


    def trigger(self, world, drives: Drives) -> bool:
        tags = set(drives.predicates())
        if "drive:hunger_high" not in tags:
            return False

        # must be upright
        if not _has(world, "state:posture_standing"):
            return False

        # do NOT seek while fallen; recover first
        if _has(world, "state:posture_fallen"):
            return False

        # prevent repeats if already in a seeking state
        if _has(world, "state:seeking_mom"):
            return False

        # require at least one sensory cue (vision/smell/sound)
        if not _any_cue_present(world):
            return False

        return True


    def execute(self, world, ctx, drives: Drives) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        a = world.add_predicate("action:orient_to_mom", attach="now", meta=meta)
        b = world.add_predicate("state:seeking_mom",                 meta=meta)
        world.add_edge(a, b, "then")
        return self._success(reward=0.5, notes="seeking mom")


class FollowMom(Primitive):
    """Fallback primitive (permissive). Tighten trigger if you prefer fewer defaults."""
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
    name = "policy:explore_check"

    def trigger(self, world, drives: Drives) -> bool:
        # simple periodic check; you can add a timer or stochastic gate later
        return False

    def execute(self, world, ctx, drives: Drives) -> dict:
        return self._success(reward=0.0, notes="checked")


class Rest(Primitive):
    name = "policy:rest"

    def trigger(self, world, drives: Drives) -> bool:
        return drives.fatigue > 0.8

    def execute(self, world, ctx, drives: Drives) -> dict:
        drives.fatigue = max(0.0, drives.fatigue - 0.2)
        now = datetime.now().isoformat(timespec="seconds")
        meta = {"policy": self.name, "created_at": now}
        a = world.add_predicate("state:resting", attach="now", meta=meta)
        return self._success(reward=0.2, notes="resting")


# Ordered repertoire scanned by the Action Center
PRIMITIVES: List[Primitive] = [
    StandUp(),
    SeekNipple(),
    FollowMom(),
    ExploreCheck(),
    Rest(),
]


# -----------------------------------------------------------------------------
# Action Center
# -----------------------------------------------------------------------------

def _run(policy):
    try:
        return policy.execute(world, ctx, drives)
    except Exception as e:
        update_skill(policy.name, 0.0, ok=False)
        return {"policy": policy.name, "status": "error", "reward": 0.0, "notes": f"exec error: {e}"}

def action_center_step(world, ctx, drives: Drives) -> dict:
    """Scan PRIMITIVES in order; run the first policy whose trigger returns True.
 
    Returns a status dict:
        {
          "policy": "policy:<name>" | None,
          "status": "ok" | "fail" | "noop" | "error",
          "reward": float,
          "notes": str
        }
    Side effects:
        - Appends new bindings/edges to world.
        - Adjusts drives (e.g., fatigue).
        - Updates SKILLS ledger.
    """
    # ---- SAFETY-FIRST SHORT-CIRCUIT ----
    if _has(world, "state:posture_fallen"):
        # run stand_up immediately
        for policy in PRIMITIVES:
            if policy.name == "policy:stand_up":
                try:
                    return _run(policy)
                except Exception as e:
                    update_skill(policy.name, 0.0, ok=False)
                    return {"policy": policy.name, "status": "error", "reward": 0.0, "notes": f"exec error: {e}"}
    # ------------------------------------
    
    for policy in PRIMITIVES:
        try:
            if policy.trigger(world, drives):
                try:
                    return _run(policy)
                except Exception as e:
                    update_skill(policy.name, 0.0, ok=False)
                    return {"policy": policy.name, "status": "error", "reward": 0.0, "notes": f"exec error: {e}"}
        except Exception:
            # bad trigger shouldn't kill the loop; try next policy
            continue
    return {"policy": None, "status": "noop", "reward": 0.0, "notes": "no triggers matched"}
