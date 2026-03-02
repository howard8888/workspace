# -*- coding: utf-8 -*-
"""
CCA8 Environment module (EnvState, EnvObservation, HybridEnvironment)


High-level overview
-------------------

The CCA8 cognitive architecture simulates a mammalian brain that can control
either a **virtual body** or a **robotic body**. Until CCA8 is attached to a
real robot, it needs a **simulated world** to live in.

This module provides that world == "environment":

- The core CCA8 modules simulate the **brain + body** (agent / embodiment).
- The Environment module simulates the **external world**: ground, 3D space,
  time, the mother goat nearby, rocks, weather, etc.
- HybridEnvironment and its backends advance a **world state** (EnvState).
- PerceptionAdapter converts EnvState into **EnvObservation** (what the agent
  senses each tick).
- CCA8 sends actions back to HybridEnvironment, which updates EnvState; the
  next EnvObservation reflects the consequences of those actions
  (e.g. the kid tries to stand and gravity pulls it down).

Terminology note
----------------
Here, “environment” always means the agent’s **task/world environment** in the
RL/robotics sense (the world the agent acts in), not ecological politics,
climate, or OS/runtime “environment variables”.


Purpose
-------
Provide a small, well-defined seam between the external environment and the
CCA8 cognitive architecture.

Key concepts (matching the README terminology):
- EnvState        : canonical "God's-eye" environment state. Not visible to CCA8.
- EnvObservation  : one-tick sensory/perceptual packet that CCA8 receives.
- HybridEnvironment: orchestrator that owns EnvState and coordinates backends.
- FsmBackend      : finite-state / scripted environment backend (skeleton).
- PerceptionAdapter: converts EnvState -> EnvObservation.

CCA8 should depend only on:
    HybridEnvironment.reset(...) / step(...)
    EnvObservation structure
and its own WorldGraph. EnvState and backends remain environment-side.


-------------------------------------------------------------------------------
Mental model
-------------------------------------------------------------------------------

HybridEnvironment is effectively the "main loop" for the environment simulation
subsystem. It is not the program's global main(), but it plays a similar role
inside the world: it is the one place that:

    - holds the current EnvState
    - calls the backends in the right order each tick
    - calls PerceptionAdapter to turn the new EnvState into an EnvObservation
    - hands that EnvObservation back to the CCA8 agent

HybridEnvironment, of course, functions within the main() loop of the CCA8
simulation system, e.g. (pseudocode):

    def main():
        env = HybridEnvironment(...)              # build an environment
        num_episodes = 1

        for episode in range(num_episodes):       # iterate over episodes
            obs, info = env.reset(...)            # reset env; get first obs
            ctx = CCA8.make_initial_ctx(...)      # CCA8 / WorldGraph init
            done = False

            # iterate over time steps within that episode
            while not done:
                # CCA8 chooses an action from current observation + internal state
                action = CCA8.choose_action(obs, ctx)

                # HybridEnvironment advances the world one tick
                obs, reward, done, info = env.step(action, ctx)

                # CCA8 ingests the new observation and reward
                # (updates WorldGraph, Columns, ctx, etc.)
                ctx = CCA8.ingest_observation(obs, reward, done, info, ctx)

-------------------------------------------------------------------------------
RL semantics
-------------------------------------------------------------------------------

Classic RL environment responsibilities:

    1. Take an action from the agent.
    2. Update the world state.
    3. Return a new observation, a reward (scalar), and a `done` flag indicating
       whether the episode has terminated.

The agent uses the reward signal to learn which actions are good or bad.
The `done` flag captures *episodic termination* (reaching a terminal state in
an episodic MDP). In code, this is modeled as:

    - when `done` becomes True, we stop calling env.step(...)
    - we then call env.reset(...) to start a new episode

Gym/Gymnasium use this same contract: `obs, reward, done, info = env.step(...)`.

In this module:

    - HybridEnvironment currently only has the *shape* of an RL environment.
      Reward is hard-coded to 0.0 and done=False (no termination yet).
    - A future MdpBackend will fill in the meaning of reward and done.
      That is where "what counts as success/failure" lives.
    - Learning happens in the agent (CCA8), not in HybridEnvironment.

Design stance (at time of writing):

    - Backends (FSM, Physics, Robot, LLM, ...) update EnvState and their own
      internal bookkeeping.
    - MdpBackend (future) looks at (old_state, action, new_state) and decides:
        * how much reward to assign, and
        * whether this episode is done.
    - HybridEnvironment simply calls these pieces and returns
      (EnvObservation, reward, done, info) to the agent.

This keeps "task definition" (success/failure) in one place (MdpBackend) and
lets RL-style agents plug into HybridEnvironment without changing the CCA8 core.

"""

# --- Pragmas and Imports -------------------------------------------------------------

from __future__ import annotations

#pylint pragmas...
#

# Standard Library Imports
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
from cca8_navpatch import GRID_ENCODING_V1, CELL_UNKNOWN, CELL_TRAVERSABLE, CELL_HAZARD, CELL_GOAL


# --- Public API index, version, global variables and constants ----------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.2.1"
__all__ = [
    "EnvState",
    "EnvObservation",
    "EnvConfig",
    "FsmBackend",
    "PerceptionAdapter",
    "HybridEnvironment",
]

# Global constants

ENV_LOGOS = {
    "badge": r"""
+------------------------------------------------------------+
|  C C A 8  ENV —  Environment Module                        |
+------------------------------------------------------------+""",
    "goat_world": r"""

      N
     / \\
    / | \\
  W ----+---- E
    \\ | /
     \\ /
      S
""".strip("\n"),
}


# ---------------------------------------------------------------------------
# EnvState: canonical environment state
# ---------------------------------------------------------------------------

@dataclass
class EnvState:
    """
    Canonical environment state ("God's-eye" view).

    This is *not* the agent's belief. It lives entirely on the environment side
    and is manipulated only by environment backends.

    The fields describe the current geometry and situation of the world in a
    compact, domain-specific way:

      - kid_posture, mom_distance, shelter_distance, cliff_distance,
        nipple_state, scenario_stage describe discrete aspects of the scene.
      - kid_position, mom_position are low-dimensional coordinates used for
        approximate distances and simple spatial reasoning.
      - kid_fatigue, kid_temperature, time_since_birth and step_index track
        slow, continuous dynamics and episode progress.

    Here we treat this structure as the "geometry" of the environment:
    the spatial configuration of kid, mom, cliff and shelter, and simple
    safety-related relationships such as "near"/"far" or "unsafe"/"safe".

    When the goat chooses an action that moves its body (for example, a future
    `walk_toward_shelter` policy), the environment backend updates the relevant
    fields in EnvState:

      - positions and derived distances (kid_position, mom_position,
        mom_distance, shelter_distance, cliff_distance),
      - optionally, symbolic region labels (e.g. a future `position` field such
        as "cliff_edge", "open_field", "shelter_area"),
      - optionally, coarse safety labels derived from those (e.g. a future
        `zone` field such as "unsafe", "neutral", "safe").

    Those changes are then turned into an EnvObservation, mirrored into the
    BodyMap, and written into WorldGraph predicates. In that sense, the goat's
    own actions directly change the environment geometry: by walking away from
    the cliff and toward shelter, EnvState moves from an unsafe to a safer
    configuration, and the rest of CCA8 sees and remembers that change.
    """

    # Discrete state
    kid_posture: str = "fallen"          # "fallen", "standing", "latched", "resting"
    mom_distance: str = "far"            # "far", "near", "touching"
    shelter_distance: str = "far"        # "far", "near", "touching" (relative to shelter)
    cliff_distance: str = "far"          # "far", "near"            (dangerous drop proximity)
    nipple_state: str = "hidden"         # "hidden", "visible", "reachable", "latched"
    scenario_stage: str = "birth"        # "birth", "struggle", "first_stand", "first_latch", "rest"

    # Continuous-ish state
    kid_position: Tuple[float, float] = (0.0, 0.0)
    mom_position: Tuple[float, float] = (1.0, 0.0)
    kid_fatigue: float = 0.2             # 0..1
    kid_temperature: float = 0.6         # 0..1
    time_since_birth: float = 0.0        # seconds (or ticks, as long as consistent)

    # Bookkeeping
    step_index: int = 0                  # environment steps in this episode

    # Symbolic spatial overlay for geometry / safety
    position: str = "cliff_edge"         # symbolic location name
    zone: str = "unsafe"                 # safety zone classification

    def update_zone_from_position(self) -> None:
        """Update safety zone label from the current symbolic position."""
        mapping = {
            "cliff_edge": "unsafe",
            "open_field": "neutral",
            "shelter_area": "safe",
        }
        self.zone = mapping.get(self.position, "neutral")

    def copy(self) -> "EnvState":
        """Return a shallow copy (explicit, so call sites stay readable)."""
        return EnvState(
            kid_posture=self.kid_posture,
            mom_distance=self.mom_distance,
            shelter_distance=self.shelter_distance,
            cliff_distance=self.cliff_distance,
            nipple_state=self.nipple_state,
            scenario_stage=self.scenario_stage,
            kid_position=self.kid_position,
            mom_position=self.mom_position,
            kid_fatigue=self.kid_fatigue,
            kid_temperature=self.kid_temperature,
            time_since_birth=self.time_since_birth,
            step_index=self.step_index,
            position=self.position,
            zone=self.zone,
        )

# ---------------------------------------------------------------------------
# EnvObservation: what CCA8 sees each tick
# ---------------------------------------------------------------------------

@dataclass
class EnvObservation:
    """
    One-tick observation packet that the agent receives.

    This matches the structure described in the README:

      - raw_sensors : numeric/tensor-like channels (distances, images, IMU, ...)
      - predicates  : discrete tokens suitable for insertion into WorldGraph
      - cues        : tokens routed into Features/Columns
      - nav_patches : processed local navigation map fragments (NavPatch v0; JSON-safe dicts)
      - env_meta    : lightweight metadata (episode id, uncertainties, etc.)
      - surface_grid: local spatial / affordance "surface" representation

    Note: these are *observations*, not beliefs. WorldGraph+Columns are where
    CCA8 turns observations into internal state and memory.
    """

    raw_sensors: Dict[str, Any] = field(default_factory=dict)
    predicates: List[str] = field(default_factory=list)
    cues: List[str] = field(default_factory=list)
    nav_patches: List[Dict[str, Any]] = field(default_factory=list)
    env_meta: Dict[str, Any] = field(default_factory=dict)
    surface_grid: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# EnvConfig: scenario / backend selection
# ---------------------------------------------------------------------------

@dataclass
class EnvConfig:
    """
    Environment configuration / scenario description.

    For now this is intentionally small. We can extend it with:
      - richer scenario descriptors,
      - initial conditions,
      - parameters for noise, thresholds, etc.
    """
    scenario_name: str = "newborn_goat_first_hour"
    dt: float = 1.0                # simulated time per environment step (seconds)
    use_fsm: bool = True
    use_physics: bool = False
    use_robot: bool = False
    use_llm: bool = False
    use_mdp: bool = False
    # future: seed: Optional[int] = None
    # future: initial_state overrides


# ---------------------------------------------------------------------------
# Backend skeletons
# ---------------------------------------------------------------------------

class FsmBackend:
    """
    Finite-state / scripted environment backend.

    Responsibility
    --------------
    Maintain high-level "story" logic for the newborn-goat vignette
    (birth → struggle → stand → latch → rest) and update discrete EnvState
    fields each step given the last action and ctx.

    Design notes
    ------------
    - This is intentionally tiny and hand-scripted: it is a *storyboard*, not
      a physics engine.
    - It uses EnvState.scenario_stage as a coarse phase label:
        "birth" -> "struggle" -> "first_stand" -> "first_latch" -> "rest".
    - Transitions are primarily time-based (EnvState.step_index), but we
      optionally react to simple action names such as "policy:stand_up" and
      "policy:seek_nipple" when present.
    - Physiology fields (kid_fatigue, kid_temperature) receive very small,
      purely cosmetic drifts so PerceptionAdapter has something to report.
    - When the CCA8 is operating in the real world then the real world provides
      the inputs, not a storyboard, to the CCA8. The storyboard is largely for
      development.
    """

    name: str = "fsm"

    # Simple thresholds in *steps* for software changes; HybridEnvironment bumps
    # EnvState.step_index and time_since_birth before calling this backend.
    _BIRTH_TO_STRUGGLE: int = 3
    _STRUGGLE_MOM_NEAR: int = 5
    _AUTO_STAND_UP: int = 8
    _AUTO_NIPPLE_REACHABLE: int = 11
    _AUTO_LATCH: int = 13
    _AUTO_REST: int = 16


    def _update_spatial_label(self, state: EnvState) -> None:
        """
        Coarse spatial geometry helper.

        Keep EnvState.position/zone aligned with a simple spatial story:

          - Early phases ('birth', 'struggle', 'first_stand') treat `position`
            as a symbolic overlay that movement policies may update
            (e.g. policy:follow_mom can move
               cliff_edge → open_field → shelter_area).

          - Later phases ('first_latch', 'rest') always snap to 'shelter_area',
            since the kid is assumed to be nursing/resting in a sheltered niche.

          - If `position` is unknown, fall back to a stage-based default.
        """
        stage = state.scenario_stage

        # Later storyboard phases live in the shelter regardless of prior movement.
        if stage in ("first_latch", "rest"):
            state.position = "shelter_area"

        # For earlier phases, only fill in a default if nothing meaningful is set.
        elif state.position not in ("cliff_edge", "open_field", "shelter_area"):
            if stage == "birth":
                # Neutral ground before any struggle near the cliff.
                state.position = "open_field"
            elif stage in ("struggle", "first_stand"):
                # Default to exposed terrain until movement policies change it.
                state.position = "cliff_edge"
            else:
                # Unknown future stages: choose a neutral default.
                state.position = "open_field"

        # Always recompute coarse safety label from the current symbolic position.
        state.update_zone_from_position()


    def reset( #pylint: disable=unused-argument
        self, env_state: EnvState, config: EnvConfig) -> EnvState:
        """
        Prepare env_state for a new episode under the given scenario.

        For now we recognise only "newborn_goat_first_hour". If some other
        scenario_name is used, we leave the defaults as-is.

        This method is explicit (even though EnvState has matching defaults)
        so that the newborn-goat initial conditions are easy to inspect.
        """
        if config.scenario_name == "newborn_goat_first_hour":
            env_state.kid_posture = "fallen"
            env_state.mom_distance = "far"
            env_state.nipple_state = "hidden"
            env_state.scenario_stage = "birth"

            env_state.kid_position = (0.0, 0.0)
            env_state.mom_position = (1.0, 0.0)

            env_state.kid_fatigue = 0.2
            env_state.kid_temperature = 0.6
            env_state.time_since_birth = 0.0
            env_state.step_index = 0

            env_state.shelter_distance = "far"
            env_state.cliff_distance   = "far"
            self._update_spatial_label(env_state) #initialize coarse geometry / zone.
        return env_state


    def step( #pylint: disable=unused-argument
        self, env_state: EnvState, action: Optional[str], ctx: Any) -> EnvState:
        """
        Advance env_state one tick given the agent's last action and context.

        Args
        ----
        env_state
            Current EnvState (will be updated and returned; we treat EnvState
            as the canonical world, not the agent's belief).

        action
            Agent's chosen action for this tick (e.g., "policy:stand_up").
            For v0, this can be a small string; later it may be a richer
            action object. This storyboard uses a couple of simple hooks:
                - "policy:stand_up"   → accelerates standing.
                - "policy:seek_nipple"→ accelerates nipple reach / latch.

        ctx
            CCA8 context object (TemporalContext, ticks, age_days, etc.).
            Currently unused here; kept for future coupling.

        Returns
        -------
        EnvState
            Updated EnvState after applying the newborn-goat storyboard logic.

        Notes
        -----
        - This method is *idempotent per step*: it mutates env_state in place
          and returns it (HybridEnvironment also stores it as self._state).
        - Time bookkeeping (step_index, time_since_birth) is maintained by
          HybridEnvironment before calling this backend.
        """
        state = env_state  # alias for readability
        stage = state.scenario_stage
        steps = state.step_index


        def _has_action(prefix: str) -> bool:
            """Return True if the action string starts with the given prefix."""
            return isinstance(action, str) and action.startswith(prefix)

        # -------------------------------
        # Stage: birth → struggle
        # -------------------------------
        if stage == "birth":
            # At birth: fallen, mom far, nipple hidden. We mostly let time pass.
            state.kid_posture = "fallen"
            state.mom_distance = "far"
            state.nipple_state = "hidden"
            # Environment geometry: no shelter or cliff immediately nearby.
            state.shelter_distance = "far"
            state.cliff_distance = "far"

            if steps >= self._BIRTH_TO_STRUGGLE:
                state.scenario_stage = "struggle"
                # Small fatigue bump to suggest the calf is working.
                state.kid_fatigue = min(1.0, state.kid_fatigue + 0.02)

        # -------------------------------
        # Stage: struggle
        # -------------------------------
        elif stage == "struggle":
            # The kid is on the ground, flailing a bit; mom gradually comes closer.
            state.kid_posture = "fallen"

            # Geometric intuition: the kid is on a more exposed patch, with a drop
            # somewhere nearby. Shelter is still far.
            state.shelter_distance = "far"
            state.cliff_distance = "near"

            # After a few steps, bring mom from far -> near.
            if steps >= self._STRUGGLE_MOM_NEAR and state.mom_distance == "far":
                state.mom_distance = "near"
                # Move mom closer along the x-axis (purely illustrative).
                state.mom_position = (0.7, state.mom_position[1])

            stood_up = _has_action("policy:stand_up") or _has_action("policy:recover_fall") or (steps >= self._AUTO_STAND_UP)
            if stood_up:
                state.kid_posture = "standing"
                state.scenario_stage = "first_stand"

        # -------------------------------
        # Stage: first_stand
        # -------------------------------
        elif stage == "first_stand":
            # Ensure upright posture and a near mom.
            state.kid_posture = "standing"
            if state.mom_distance == "far":
                state.mom_distance = "near"
                state.mom_position = (0.5, state.mom_position[1])

            # Still somewhat exposed: cliff remains near; shelter is not yet reached.
            state.shelter_distance = "far"
            state.cliff_distance = "near"

            # Step 1: nipple becomes reachable (found).
            if state.nipple_state in ("hidden", "visible"):
                if _has_action("policy:seek_nipple") or steps >= self._AUTO_NIPPLE_REACHABLE:
                    state.nipple_state = "reachable"

            # Step 2: latch, once nipple is reachable.
            if state.nipple_state == "reachable":
                if _has_action("policy:seek_nipple") or steps >= self._AUTO_LATCH:
                    state.nipple_state = "latched"
                    state.kid_posture = "latched"
                    state.scenario_stage = "first_latch"

        # -------------------------------
        # Stage: first_latch
        # -------------------------------
        elif stage == "first_latch":
            # Latched and effectively drinking.
            state.kid_posture = "latched"
            state.nipple_state = "latched"
            state.mom_distance = "near"

            # Interpretation: the kid has shifted into a safer, more sheltered niche.
            state.shelter_distance = "near"
            state.cliff_distance = "far"

            # After a short while, transition to a resting state.
            if steps >= self._AUTO_REST:
                state.scenario_stage = "rest"
                state.kid_posture = "resting"
                state.mom_distance = "touching"
                # You may imagine the kid curled up against mom.
                state.mom_position = (state.kid_position[0], state.kid_position[1])

        # -------------------------------
        # Stage: rest
        # -------------------------------
        elif stage == "rest":
            # Keep a simple, stable resting configuration.
            state.kid_posture = "resting"
            state.mom_distance = "touching"
            # We keep nipple_state as "latched" to indicate ongoing access to milk.
            if state.nipple_state == "hidden":
                state.nipple_state = "latched"

            # Resting near shelter; cliff is far.
            state.shelter_distance = "near"
            state.cliff_distance = "far"

        # ------------------------------------------------------------------
        # Interpret 'policy:follow_mom' as a small move toward shelter.
        #
        # Geometry ladder:
        #   cliff_edge  --follow_mom-->  open_field  --follow_mom-->  shelter_area
        #
        # This only runs in 'struggle' / 'first_stand' so we do not interfere with
        # the birth setup or the later nursing/resting configuration.
        # ------------------------------------------------------------------
        if _has_action("policy:follow_mom") and state.scenario_stage in ("struggle", "first_stand"):
            if state.position == "cliff_edge":
                # Step 1: move off the exposed cliff edge onto more neutral terrain.
                state.position = "open_field"
                state.cliff_distance = "far"
                # shelter_distance stays as-is (usually 'far' at this point).
            elif state.position == "open_field":
                # Step 2: move from neutral ground into a more sheltered niche.
                state.position = "shelter_area"
                state.shelter_distance = "near"
                state.cliff_distance = "far"
            # If already in 'shelter_area', we leave geometry unchanged.

        # ------------------------------------------------------------------
        # Simple physiology drifts (fatigue, temperature)
        # ------------------------------------------------------------------
        # Fatigue:
        if state.kid_posture == "fallen":
            state.kid_fatigue = min(1.0, state.kid_fatigue + 0.02)
        elif state.kid_posture in ("standing", "latched"):
            # Standing / nursing still costs some effort.
            state.kid_fatigue = min(1.0, state.kid_fatigue + 0.01)
        elif state.kid_posture == "resting":
            state.kid_fatigue = max(0.0, state.kid_fatigue - 0.02)

        # Temperature:
        if stage in ("birth", "struggle") and state.kid_posture == "fallen":
            # Slight cooling while on the ground early on.
            state.kid_temperature = max(0.0, state.kid_temperature - 0.005)
        elif stage in ("first_latch", "rest"):
            # Warmth from mom and milk.
            state.kid_temperature = min(1.0, state.kid_temperature + 0.005)

        self._update_spatial_label(state) #keep symbolic position / zone in sync with storyboard
        return state


class PerceptionAdapter: #pylint: disable=too-few-public-methods
    """
    Adapter converting EnvState -> EnvObservation.

    This is the "sensor interface":

      - decides which pieces of EnvState are observable,
      - turns them into predicates / cues / raw channels,
      - does *not* store memory or update WorldGraph (CCA8 handles that).

    Design notes:

      - Tokens emitted here should align with the current neonate vocabulary
        (TagLexicon.BASE) for the "neonate" stage, e.g.:

          * posture:standing, posture:fallen
          * proximity:mom:close, proximity:mom:far
          * nipple:found, nipple:latched, milk:drinking
          * cues like vision:silhouette:mom, drive:hunger_high (if ever used)
    """

    def __init__(self) -> None:
        # We may parameterize thresholds later (e.g., near/far distance).
        self._near_threshold: float = 1.0


    def observe(self, env_state: EnvState, ctx: Any | None = None) -> EnvObservation:
        """
        Build an EnvObservation from the current EnvState.

        In addition to predicates/cues, we also emit a minimal NavPatch grid payload
        (grid_v1) so the Phase X SurfaceGrid pipeline has an end-to-end input stream.

        Notes:
            - This is a storyboard stub. In a real robot backend, these grids would
              come from perception + mapping (depth/LiDAR/costmap/terrain classifiers).
            - The grid is JSON-safe and deterministic; it is *not* a belief store.
        """
        raw: Dict[str, Any] = {}
        preds: List[str] = []
        cues: List[str] = []
        meta: Dict[str, Any] = {}

        # --- raw channels ---
        dx = env_state.mom_position[0] - env_state.kid_position[0]
        dy = env_state.mom_position[1] - env_state.kid_position[1]
        dist = (dx * dx + dy * dy) ** 0.5
        raw["distance_to_mom"] = dist
        raw["kid_temperature"] = env_state.kid_temperature

        # --- posture predicates ---
        if env_state.kid_posture == "standing":
            preds.append("posture:standing")
        elif env_state.kid_posture == "fallen":
            preds.append("posture:fallen")
        elif env_state.kid_posture == "latched":
            preds.append("posture:standing")
        elif env_state.kid_posture == "resting":
            preds.append("resting")

        # --- proximity predicates ---
        if env_state.mom_distance in ("near", "touching"):
            preds.append("proximity:mom:close")
        elif env_state.mom_distance == "far":
            preds.append("proximity:mom:far")

        if env_state.shelter_distance in ("near", "touching"):
            preds.append("proximity:shelter:near")
        elif env_state.shelter_distance == "far":
            preds.append("proximity:shelter:far")

        # --- hazard predicates ---
        if env_state.cliff_distance == "near":
            preds.append("hazard:cliff:near")
        elif env_state.cliff_distance == "far":
            preds.append("hazard:cliff:far")

        # --- feeding predicates ---
        if env_state.nipple_state in ("visible", "reachable"):
            preds.append("nipple:found")
        elif env_state.nipple_state == "latched":
            preds.append("nipple:latched")
            preds.append("milk:drinking")

        # --- simple cues ---
        if env_state.mom_distance in ("near", "touching"):
            cues.append("vision:silhouette:mom")
        if env_state.kid_temperature < 0.35:
            cues.append("drive:cold_skin")

        # --- meta ---
        meta["time_since_birth"] = env_state.time_since_birth
        meta["scenario_stage"] = env_state.scenario_stage
        meta["zone"] = env_state.zone
        meta["position"] = env_state.position

        # Use self._near_threshold so it’s not “dead configuration”.
        meta["mom_proximity_from_raw"] = "near" if dist <= float(self._near_threshold) else "far"

        # Predictive-coding / attention hook: top-down focus request (optional).
        focus: str | None = None
        try:
            if ctx is not None:
                focus = getattr(ctx, "percept_focus", None)
                focus = str(focus) if focus is not None else None
        except Exception:
            focus = None
        if focus is not None:
            meta["percept_focus"] = focus
            if focus in ("mom", "vision", "proximity:mom"):
                raw["mom_dx"] = dx
                raw["mom_dy"] = dy

        # --- SurfaceGrid (local spatial/affordance surface; JSON-safe) ---
        # This is intentionally small: it is a *perception product* that can be scanned
        # quickly and can later become a real robot costmap/heightmap/etc.
        cliff_near = bool(env_state.cliff_distance == "near")
        shelter_near = bool(env_state.shelter_distance in ("near", "touching"))
        mom_near = bool(env_state.mom_distance in ("near", "touching"))

        surface_grid: Dict[str, Any] = {
            "frame": "body",
            "center": {"entity": "kid", "x": 0.0, "y": 0.0},
            "objects": [{"entity": "mom", "dx": float(dx), "dy": float(dy), "dist": float(dist)}],
            "affordances": {"cliff_near": cliff_near, "shelter_near": shelter_near, "mom_near": mom_near},
            "region": {"position": str(env_state.position), "zone": str(env_state.zone)},
        }
        if focus is not None:
            surface_grid["attention"] = {"focus": focus}

        # --- NavPatch grid payload (grid_v1) ---
        nav_patches = self._stub_navpatch_grid_v1(env_state, focus=focus)

        return EnvObservation(
            raw_sensors=raw,
            predicates=preds,
            cues=cues,
            nav_patches=nav_patches,
            env_meta=meta,
            surface_grid=surface_grid,
        )


    def _stub_navpatch_grid_v1(self, env_state: EnvState, *, focus: str | None = None) -> List[Dict[str, Any]]:
        """Return a minimal grid_v1 NavPatch list derived from EnvState (storybook stub).

        Contract
        --------
        Unit test expects:
          - obs.nav_patches is a non-empty list
          - each patch uses grid_v1 fields and passes navpatch_grid_errors_v1()

        Design
        ------
        - Deterministic
        - JSON-safe
        - Simple semantics: unknown border, traversable interior, optional hazard cluster, optional goal cell.
        """
        w = 16
        h = 16
        n = w * h

        # Unknown everywhere, then carve a traversable interior (uses CELL_UNKNOWN intentionally).
        cells = [CELL_UNKNOWN] * n
        for y in range(1, h - 1):
            base = y * w
            for x in range(1, w - 1):
                cells[base + x] = CELL_TRAVERSABLE

        cx = w // 2
        cy = h // 2

        # Hazard cluster when cliff is near.
        if env_state.cliff_distance == "near":
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    x = cx + ox
                    y = cy + oy
                    if 0 < x < (w - 1) and 0 < y < (h - 1):
                        cells[y * w + x] = CELL_HAZARD

        # Goal cell when shelter is near.
        if env_state.shelter_distance in ("near", "touching"):
            gx = min(w - 2, cx + 3)
            gy = cy
            if 0 < gx < (w - 1) and 0 < gy < (h - 1):
                cells[gy * w + gx] = CELL_GOAL

        zone = getattr(env_state, "zone", None) or "unknown"
        stage = getattr(env_state, "scenario_stage", None) or "unknown"

        obs: Dict[str, Any] = {
            "source": "PerceptionAdapter.observe",
            "step_index": int(getattr(env_state, "step_index", 0) or 0),
        }
        if focus is not None:
            obs["focus"] = str(focus)

        tags = [f"zone:{zone}", f"stage:{stage}"]
        if focus is not None:
            tags.append(f"focus:{focus}")

        patch = {
            "schema": "navpatch_v1",
            "local_id": "p_scene",  # volatile
            "entity_id": "scene",
            "role": "scene",
            "frame": "ego_schematic_v1",
            "grid_encoding_v": GRID_ENCODING_V1,
            "grid_w": w,
            "grid_h": h,
            "grid_cells": cells,
            "tags": tags,
            "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
            "layers": {},  # volatile
            "obs": obs,  # volatile
        }

        return [patch]


    def _stub_nav_patches(self, env_state: EnvState) -> List[Dict[str, Any]]:
        """Return a minimal list of NavPatch-like dicts derived from EnvState.

        Purpose
        -------
        The newborn-goat storyboard is not yet a full navigation environment. However, we still want
        an *intermediate representation* that looks like the eventual NavPatch stream so we can:

          1) test JSON-safe patch schemas end-to-end,
          2) run a simple prototype matching loop against Column memory,
          3) log top-K candidate matches for interpretability and future learning.

        Design
        ------
        - The dict schema is intentionally small and JSON-safe.
        - We avoid any heavy geometry (images, point clouds) in this stub.
        - The agent-side code computes patch signatures and matching; this function only emits patches.

        Schema (v0)
        -----------
        Each patch is a dict with keys:

          v      : str, version label ("navpatch_v1")
          id     : str, short patch id within the observation (e.g., "p_zone")
          kind   : str, coarse patch family ("zone" | "hazard" | "affordance" | ...)
          tags   : list[str], human-readable tags (order is not significant)
          geom   : dict[str, Any], small structured features used for matching (JSON-safe)
          meta   : dict[str, Any], volatile tick info (NOT part of signature)

        Returns
        -------
        list[dict[str, Any]]
            Patch list for this observation tick.
        """
        zone = getattr(env_state, "zone", None) or "unknown"
        cliff = getattr(env_state, "cliff_distance", None) or "unknown"
        shelter = getattr(env_state, "shelter_distance", None) or "unknown"

        # The 'zone' patch is a coarse summary used for future route/context selection.
        p_zone = {
            "v": "navpatch_v1",
            "id": "p_zone",
            "kind": "zone",
            "tags": [f"zone:{zone}"],
            "geom": {
                "zone": zone,
                "position": getattr(env_state, "position", None) or "unknown",
                "cliff_distance": cliff,
                "shelter_distance": shelter,
            },
            "meta": {
                "source": "PerceptionAdapter",
                "step_index": int(getattr(env_state, "step_index", 0) or 0),
            },
        }

        # The 'cliff hazard' patch is the first concrete hazard-like patch in the storyboard.
        p_cliff = {
            "v": "navpatch_v1",
            "id": "p_cliff",
            "kind": "hazard",
            "tags": ["hazard:cliff", f"cliff:{cliff}", f"shelter:{shelter}"],
            "geom": {
                "cliff_distance": cliff,
                "shelter_distance": shelter,
                "zone": zone,
            },
            "meta": {
                "source": "PerceptionAdapter",
                "step_index": int(getattr(env_state, "step_index", 0) or 0),
            },
        }

        return [p_zone, p_cliff]


# ---------------------------------------------------------------------------
# HybridEnvironment: orchestrator
# ---------------------------------------------------------------------------

class HybridEnvironment:
    """
    HybridEnvironment orchestrates EnvState and backends and exposes a Gym-like API:

        obs, info = env.reset(seed, config)
        obs, reward, done, info = env.step(action, ctx)

    CCA8 sees only EnvObservation, reward, done, and info. EnvState and the
    backends live entirely on the environment side.

    HybridEnvironment is effectively the 'main loop' for the environment simulation subsystem.
    It is not the program's global main(), but it plays a similar role inside the world -- it is one place that:
        -holds the current EnvState
        -calls the backends in the right order each tick
        -call PerceptionAdapter to turn the new EnvState into an EnvObservation
        -hands that EnvObservation back to the CCA8

    Effectively the HybridEnvironment main()-like action controls the whole simulation loop.
    --> It controls how the world evolves each step.

    HybridEnvironment, of course, functions within the main() loop of the CCA8 simulation system:

    main():
        env=HybridEnvironment(...)  #build an environment
        num_episodes = 1

        for episode in range(num_episodes):  #iterate over episodes
            obs, info = env.reset(...)  #reset the environment to get the first obs
            ctx = CCA8.make_initial_ctx(...)  #and other CCA8/ WorldGraph init
            done=False

            while not done:  #iterate over time steps within that episode until done=True
                action = CCA8.choose_action(obs, ctx)  #CCA8 chooses an actin based on current obsv'n, internal state
                obs, reward, done, info = env.step(action, ctx)  #HybridEnvironment advances on tick
                CCA8.ingest_observation(obs, reward, done, info)  #CCA8 ingets the new observations and reward
                                                                  #CCA8 updates WorldGraph, Columns, etc

    HybridEnvironment owns the 'master copy' of EnvState (self._state)
    Each step it:
    1.updates basic bookeeping(step count, time since birth)
    2. hands current EnvState to backends "Given this state and the agent's action, how should the world change?"
    3. accepts the updated EnvState back
    4. finally, hands that EnvState to PerceptionAdapter, which returns EnvObservation

    Reinforcement Learning in HybridEnvironment class
    -HybridEnvironment currently only has the shape of an RL environment (todo at time of writing)
    -(todo) MdpBackend will fill in the meaning of reward and done <-- actual RL logic lives here
    -the learning actually happens in the agent (i.e., CCA), not in HybridEnvironment
    -complex subject -- learning in the environment -- don't want rules of physics to learn and change, although
        it is fine for the environment to learn how to present scenarios at a meta level, e.g., a curriculum
        generator and/or scenario sampler (lives in EnvConfig generator); however, the environment does adapt
        its parameters to the agent -- indeed backends update EnvState
    -current design approach with respect to environment "learning":
        -the world physics/rules adapt and learn <-- do not want laws of the world to change as a function of the
            agent's skills
        -environment learns how to present scenarios at a meta level <-- more reasonable and useful
            -lives in the Scenario/ EnvConfig generator -- chooses parameters for next Envconfig
            -curriculum generator -- makes tasks gradually harder as CCA8 gets better or focuses on
            failure cases
            -scenario sampler that uses performance history to pick which episodes to generate next
        -normal actions can change the environment -- normal causal effects are indeed the reason for the
            EnvState and the backends
            -CCA8 sends an action to env.step(action, ctx) and backends update EnvState, e.g., posture goes
            from "fallen" to "standing" if the "StandUp" policy succeeds
            --> act on the world does change EnvState -- but this is not environment learning but just dynamics
        -treating other agents more complex, e.g., how to treat the mother goat
        -can treat the mother as part of the environment, i.e., non-learning agent, e.g., if newborn near but
            struggling, mother position can adjust to make suckling easier
        -can treat the mother and other goats as a multi-agent scenario, but each would have its own Controller,
            WorldGraph, policy/drives -- it would be them learning, not the environment
        -in summary:
            -core backends (FSM, Physics, Robot) -- implement fixed dynamics for a given episode (laws+script),
                they don't learn in RL sense during the episode
            -task/MDP logic (MdpBackend) -- defines reward and done; might be tuned offline but not agent-adaptive
            -scenario/curriculum layer -- outside HybridEnvironment; can learn over episodes
            -other agents -- early modeled as part of envrt dynamics, later can model as explicit agents

    -in classic RL an environment does 3 things:
        1. takes an action from an agent
        2. updates the world state
        3. returns a new observation, a reward (number), a done flag (whether episode finished or not)
    -essentially the agent uses the reward signal to learn which actions are good and which are bad

    -the "done" flag is often not discussed in introductory classical RL, however, classical RL does in fact
        distinguish episodic tasks (i.e., the interactions occurs in episodes -- start in some initial state,
        take actions, get rewards, eventually reach a terminal state, then the evnr't resets) versus
        continuing tasks
        -in episodic case of classical RL the episode ends at some T terminal time, and in the code this is
        modeled as "we reached terminal state, we are returning a done=True signal, stop this episode
        and call reset(...) before continuing"
        -in Gymnaisum software there is a terminated signal and a truncated signal (we cut off the episode early),
            but at the time of writing we model both with done=True
        -when done=Tue, the outer loop in the prototype code shown above stops calling env.step(...) and isntead
            calls env.reset(...) for a new episode
        -note that even without RL the done=True signal is useful to provide natural episode boundaries

    -HybridEnvironment look exactly like this, as noted above:
        obs, info = env.reset(...)
        obs, reward, done, info = env.step(action, ctx)
    -again, it is important to note that the agent is where the learning is occuring, while the environment's role
        is to provide the reward/done signals in a standard learning way so that a learning algorithm in the
        CCA8 could use them
    (todo: RL learning can occur in the environment, particularly if agents, but even without agents
        there will be situations where learning should occur; but this is for future devp't work)
    -simplified way to think of the above -- HybridEnvironment calls backends to get EnvState_t to EnvState_{t+1},
        it then asks MdpBackend: " Given we went from old_state to new_state with this action, how much reward
        should I assign, and is the episode over?"
    -for example, consider the newborn goat, if nipple_state becomes "latched" then we could assign, e.g., +1 reward;
        give a small positive reward each step while "milk:drinking"; -1 negative reward is "kid_temperature" too low;
        set done=True once the goat has latched and then rested for 5 minutes
    -essentially MdpBackend in our simple usage case (at time of writing) gives what counts as a success or failure
        in the world of the newborn goat, while HybridEnvironment's role is just to call it and pass the reward/done
        back to the agent, i.e., the CCA8

    -while in the future the environment should become more sophisticated with learning on its own (although perhaps
        we are able to make the transition to the real physical world early enough) (although.... for multi-agents and
        certain aspects of the world it would be nice and probably necessary to simulate them), at the time of
        writing, note that we have intentionally separated RL learning to occur in the agent (i.e., CCA8) -- it
        sees (obs, reward, done), it adjusts its policy (i.e., how to choose actions) based on those signals, versus
        HybridEnvironment+backends which keep track of EnvState (i.e., the simulated world), provide EnvObservation,
        provide reward and done (via MdpBackend) -- at the time writing, learning is not occuring in HybridEnvironment
    -HybridEnvironment supports RL in terms of letting an RL agent plug into it and learn from it with the standard
        reset/step -> (obs, reward, done, info) language
    -in the future even with multiple backend's available, it might be conceptually better for only MdpBackend to
        compute reward/done, i.e., one place in the coding owns these signals, and reward/done are essentially
        about the taks, not the physics, not the script, not the robot hardware, or other information the other
        backend's will provide; while multiple backend's could compute these signals there will an issue in
        managing conflicting signals (doable in future -- have other backend's annotate EnvState with task-relevant
        signals (e.g., "energy_used") and MdpBackend uses those fields to compute a single scalar reward and a single
        done flag)
    -at the time of writing (Nov 2025), backends (e.g., FSM, Physics, Robot, LLM) only update EnvState and their own
        internal bookkeeping <--> MdpBackend loos at (old_state, action, new_state_) and decides how much reward to
        assign and whether this episode is done

    """

    def __init__(
        self,
        config: Optional[EnvConfig] = None,
        *,
        fsm_backend: Optional[FsmBackend] = None,
        perception: Optional[PerceptionAdapter] = None,
    ) -> None:
        self.config: EnvConfig = config or EnvConfig()
        self._fsm: FsmBackend = fsm_backend or FsmBackend()
        self._perception: PerceptionAdapter = perception or PerceptionAdapter()

        self._state: EnvState = EnvState()
        self._episode_index: int = 0
        self._episode_steps: int = 0

        # future: physics_backend, robot_backend, llm_backend, mdp_backend

    # ----- Public API -----
    def reset(#pylint: disable=unused-argument
        self,
        seed: Optional[int] = None,
        config: Optional[EnvConfig] = None,
    ) -> Tuple[EnvObservation, Dict[str, Any]]:
        """
        Start a new episode.

        Args:
            seed:
                Optional random seed for backends (ignored for now). Later, we
                may pass this into backends for reproducible randomization.

            config:
                Optional new EnvConfig; if provided, replaces the current one.

        Returns:
            (EnvObservation, info) for the first tick (before any agent action).

        Conceptual steps (as used in pseudocode):

            obs, info = env.reset(seed, config)

                - updates EnvConfig if provided,
                - creates a fresh EnvState,
                - lets FsmBackend adjust that initial state for the scenario,
                - calls PerceptionAdapter to build the first EnvObservation,
                - returns that obs up to CCA8.

        Effectively, reset(...) sets up state, lets backends configure it, and
        produces the first observation of the episode.
        """

        if config is not None:
            self.config = config

        self._episode_index += 1
        self._episode_steps = 0

        # For now we ignore seed; backends can adopt it later if needed.

        # Fresh canonical state, then let the FSM backend adjust it for the scenario.
        self._state = EnvState()
        self._state = self._fsm.reset(self._state, self.config)

        obs = self._perception.observe(self._state, ctx=None)
        info = {
            "episode_index": self._episode_index,
            "scenario_name": self.config.scenario_name,
            # NOTE: do not rely on internal EnvState here from CCA8 – this dict is
            # intended for logging/debugging, not as a second observation channel.
        }
        return obs, info


    def step(
        self,
        action: Optional[str],
        ctx: Any,
    ) -> Tuple[EnvObservation, float, bool, Dict[str, Any]]:
        """
        Advance the environment by one tick given the agent's last action.

        Args:
            action:
                A structured representation of what CCA8 decided. Today this can
                be a policy name or a small string; later this may be a richer
                action object.

            ctx:
                The CCA8 context object (TemporalContext, ticks, age_days, etc.).

        Returns:
            (obs, reward, done, info)

                - obs    : EnvObservation for this new state.
                - reward : RL-style scalar signal (0.0 for now; MdpBackend will
                           own this later).
                - done   : True if episode terminated (always False in skeleton).
                - info   : small dict for logging/debugging (episode/step indices).

        Conceptual steps:

            obs, reward, done, info = env.step(action, ctx)

            1. Time bookkeeping:
               - increment episode_steps
               - update EnvState.step_index
               - advance EnvState.time_since_birth by config.dt

            2. Let backends update EnvState (FSM today; physics/robot/LLM later).

            3. Compute reward/done via MdpBackend (future; reward=0.0, done=False
               for v0).

            4. Produce observation via PerceptionAdapter.

            5. Build info dict (logging/debug).

            6. Return (obs, reward, done, info).
        """

        self._episode_steps += 1

        # Advance simple time bookkeeping
        self._state.step_index = self._episode_steps
        self._state.time_since_birth += self.config.dt

        # Let the FSM backend update discrete state. Future backends (physics,
        # robot, LLM) will also be invoked here with clear field-ownership rules.
        if self.config.use_fsm:
            self._state = self._fsm.step(self._state, action, ctx)

        # For v0, we have no MdpBackend yet: reward=0.0, done=False.
        reward: float = 0.0
        done: bool = False

        obs = self._perception.observe(self._state, ctx=ctx)
        info = {
            "episode_index": self._episode_index,
            "step_index": self._episode_steps,
        }
        return obs, reward, done, info


    # ----- Introspection helpers (optional) -----

    @property
    def state(self) -> EnvState:
        """
        Return the current EnvState.

        NOTE:
            This is exposed for debugging / unit tests. CCA8 should not use
            this in normal operation; it should rely solely on EnvObservation.
        """
        return self._state

    @property
    def episode_index(self) -> int:
        """
        info = {"episode_index": self._episode_index, ...}
        """
        return self._episode_index

    @property
    def episode_steps(self) -> int:
        """
        self._state.step_index = self._episode_steps
        """
        return self._episode_steps


# ---------------------------------------------------------------------------
# Tiny debug driver (manual storyboard inspection)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Display message
    print('\n', ENV_LOGOS["badge"])
    print('\n', ENV_LOGOS["goat_world"], '\n')

    # Simple manual run to inspect the newborn-goat storyboard without CCA8.
    env = HybridEnvironment()
    dbg_obs, dbg_info = env.reset()

    print("=== HybridEnvironment debug: newborn_goat_first_hour ===")
    print(
        f"episode_index={dbg_info.get('episode_index')}, "
        f"scenario={dbg_info.get('scenario_name')}"
    )
    print(" step  stage          posture   mom_dist  nipple     temp  fatigue  predicates")

    max_steps = 20
    for _ in range(max_steps):
        # For now we don't drive any real actions; we just let the storyboard run.
        dbg_action = None
        dbg_ctx = None

        dbg_obs, dbg_reward, dbg_done, dbg_info = env.step(dbg_action, dbg_ctx)
        dbg_state = env.state

        print(
            f"{dbg_info.get('step_index', -1):4d}  "
            f"{dbg_state.scenario_stage:12s}  "
            f"{dbg_state.kid_posture:8s}  "
            f"{dbg_state.mom_distance:8s}  "
            f"{dbg_state.nipple_state:9s}  "
            f"{dbg_state.kid_temperature:5.2f}  "
            f"{dbg_state.kid_fatigue:7.2f}  "
            f"{','.join(dbg_obs.predicates)}"
        )

        if dbg_done:
            break
