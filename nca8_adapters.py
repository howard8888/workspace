#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment boundary and observation firewall for the new CCA8 runtime.

Purpose
-------
The Architecture-v09.3 runtime may share the established physical-world
simulation, but it must not import legacy cognitive conclusions or read the
environment's God's-eye ``EnvState``.  This module is the only Phase-1A
``nca8_*`` module allowed to import :mod:`cca8_env`.

It performs three jobs:

* construct a private ``HybridEnvironment`` for each new-runtime session;
* expose only ``reset`` and explicit null-action advancement to Phase 1A;
* convert ``EnvObservation`` into a defensively copied, recursively immutable,
  positively whitelisted observation packet.

Unknown fields are discarded.  In particular, scenario stage, milestone lists,
position/zone labels, goal/stage NavPatch tags, feeding progress counters,
benchmark answers, scores, and environment state are not available to the new
runtime through this boundary.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeAlias

from cca8_env import EnvConfig, EnvObservation, HybridEnvironment
from cca8_navpatch import CELL_BLOCKED, CELL_GOAL, CELL_HAZARD, CELL_TRAVERSABLE, CELL_UNKNOWN

__version__ = "0.1.0"
__all__ = [
    "NCA8_SCAFFOLD_LEDGER_V1",
    "Nca8EnvironmentBridgeV1",
    "Nca8EnvironmentResetV1",
    "Nca8EnvironmentStepV1",
    "Nca8ObservationV1",
    "Nca8ScaffoldLedgerEntryV1",
    "adapt_env_observation_v1",
    "create_environment_bridge_v1",
    "__version__",
]

JsonScalarV1: TypeAlias = str | int | float | bool | None

_MAX_NAV_PATCHES = 8
_MAX_GRID_CELLS = 4096
_MAX_SURFACE_ITEMS = 32
_MAX_TOKEN_COUNT = 64

_ALLOWED_GEOMETRY_CELLS = frozenset({CELL_UNKNOWN, CELL_TRAVERSABLE, CELL_HAZARD, CELL_BLOCKED})
_ALLOWED_SURFACE_KINDS = frozenset({"ego_anchor", "social", "hazard", "feeding", "landmark", "object"})

_ALLOWED_RAW_SENSOR_KEYS = frozenset(
    {
        "distance_to_mom",
        "kid_temperature",
        "mom_dx",
        "mom_dy",
    }
)

_ALLOWED_PREDICATES = frozenset(
    {
        "posture:fallen",
        "posture:standing",
        "resting",
        "proximity:mom:close",
        "proximity:mom:far",
        "proximity:shelter:near",
        "proximity:shelter:far",
        "hazard:cliff:near",
        "hazard:cliff:far",
        "nipple:found",
        "nipple:latched",
        "milk:drinking",
    }
)

_ALLOWED_CUES = frozenset(
    {
        "vision:silhouette:mom",
        "drive:cold_skin",
    }
)

_ALLOWED_NAVPATCH_TEXT_FIELDS = (
    "schema",
    "local_id",
    "entity_id",
    "role",
    "frame",
    "grid_encoding_v",
)

_ALLOWED_LOWER_MOTOR_TEXT_FIELDS = (
    "schema",
    "source_ref",
    "action_applied",
    "phase",
    "error_code",
)

_ALLOWED_LOWER_MOTOR_BOOLEAN_FIELDS = (
    "support_contact",
    "slip_detected",
    "detailed_movement_delegated",
    "lower_motor_trajectory_present",
    "actuator_commands_present",
)


@dataclass(frozen=True, slots=True)
class Nca8ScaffoldLedgerEntryV1:
    """Document one explicitly permitted perception scaffold at the firewall."""

    source_field: str
    cognitive_meaning: str
    first_phase: str
    replacement_target: str
    status: str


NCA8_SCAFFOLD_LEDGER_V1: tuple[Nca8ScaffoldLedgerEntryV1, ...] = (
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.raw_sensors",
        cognitive_meaning="bounded numeric receptor-like channels",
        first_phase="1A transport only; first interpreted use in 1C",
        replacement_target="modality-specific sensory services",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.predicates",
        cognitive_meaning="selected interpreted perception tokens",
        first_phase="1A transport only; first map-state use in 1C",
        replacement_target="owned sensory/NavMap-state derivation",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.cues",
        cognitive_meaning="selected salient sensory cues",
        first_phase="1A transport only; later sensory/association use",
        replacement_target="local sensory matching and activation",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.nav_patches/surface_grid",
        cognitive_meaning="bounded current geometry without goal/stage labels",
        first_phase="1A transport only; first decoded map use in 1C",
        replacement_target="new sensory and NavMap-state contracts",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="env_meta.lower_motor_feedback_v1",
        cognitive_meaning="compact support, slip, progress, and error feedback",
        first_phase="1A transport only; later BodyMap/outcome use",
        replacement_target="HAL/lower-action status contract",
        status="temporary explicit scaffold",
    ),
)


def _finite_number(value: Any) -> int | float | None:
    """Return one finite non-Boolean number, otherwise ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _safe_text(value: Any, *, maximum: int = 160) -> str | None:
    """Return a bounded string, otherwise ``None``."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        return None
    return normalized


def _freeze_json_v1(value: Any) -> Any:
    """Recursively copy and freeze one already-sanitized JSON-like value.

    Mappings become read-only ``mappingproxy`` objects and sequences become
    tuples.  Unsupported values raise ``TypeError`` so a future adapter change
    cannot silently smuggle an opaque environment object through the boundary.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not valid observation values")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json_v1(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_v1(item) for item in value)
    raise TypeError(f"unsupported observation value type: {type(value).__name__}")


def _thaw_json_v1(value: Any) -> Any:
    """Return a newly allocated JSON-safe form of one frozen value."""
    if isinstance(value, Mapping):
        return {str(key): _thaw_json_v1(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_v1(item) for item in value]
    return value


def _safe_token_tuple(values: Any, allowed: frozenset[str]) -> tuple[str, ...]:
    """Return unique allowed tokens in source order with a hard count bound."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return ()
    retained: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if len(retained) >= _MAX_TOKEN_COUNT:
            break
        token = _safe_text(raw)
        if token is None or token not in allowed or token in seen:
            continue
        seen.add(token)
        retained.append(token)
    return tuple(retained)


def _sanitize_point_v1(value: Any, *, allow_entity: bool = True) -> dict[str, Any] | None:
    """Return one bounded two-dimensional point/relative-position dictionary."""
    if not isinstance(value, Mapping):
        return None
    out: dict[str, Any] = {}
    if allow_entity:
        entity = _safe_text(value.get("entity"), maximum=80)
        if entity is not None:
            out["entity"] = entity
    for key in ("x", "y", "dx", "dy", "dist"):
        number = _finite_number(value.get(key))
        if number is not None:
            out[key] = number
    return out or None


def _sanitize_extent_v1(value: Any) -> dict[str, Any] | None:
    """Return a validated axis-aligned NavPatch extent."""
    if not isinstance(value, Mapping):
        return None
    extent_type = _safe_text(value.get("type"), maximum=40)
    if extent_type != "aabb":
        return None
    out: dict[str, Any] = {"type": extent_type}
    for key in ("x0", "y0", "x1", "y1"):
        number = _finite_number(value.get(key))
        if number is None:
            return None
        out[key] = number
    return out


def _sanitize_navpatch_v1(value: Any) -> dict[str, Any] | None:
    """Return one geometry-only NavPatch with stage/goal tags removed."""
    if not isinstance(value, Mapping):
        return None

    out: dict[str, Any] = {}
    for key in _ALLOWED_NAVPATCH_TEXT_FIELDS:
        text = _safe_text(value.get(key), maximum=100)
        if text is not None:
            out[key] = text

    width = _finite_number(value.get("grid_w"))
    height = _finite_number(value.get("grid_h"))
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        return None
    if width * height > _MAX_GRID_CELLS:
        return None

    raw_cells = value.get("grid_cells")
    if not isinstance(raw_cells, Sequence) or isinstance(raw_cells, (str, bytes, bytearray)):
        return None
    if len(raw_cells) != width * height:
        return None

    cells: list[int] = []
    for raw_cell in raw_cells:
        if isinstance(raw_cell, bool) or not isinstance(raw_cell, int):
            return None
        # The legacy environment marks shelter with CELL_GOAL.  NCA8 may receive
        # geometry, but the environment may not nominate the agent's cognitive
        # goal.  Preserve that cell only as ordinary traversable space.
        sanitized_cell = CELL_TRAVERSABLE if raw_cell == CELL_GOAL else raw_cell
        if sanitized_cell not in _ALLOWED_GEOMETRY_CELLS:
            return None
        cells.append(sanitized_cell)

    out["grid_w"] = width
    out["grid_h"] = height
    out["grid_cells"] = cells

    extent = _sanitize_extent_v1(value.get("extent"))
    if extent is not None:
        out["extent"] = extent

    raw_obs = value.get("obs")
    if isinstance(raw_obs, Mapping):
        obs_out: dict[str, Any] = {}
        source = _safe_text(raw_obs.get("source"), maximum=120)
        step_index = _finite_number(raw_obs.get("step_index"))
        blackout = raw_obs.get("blackout")
        focus = _safe_text(raw_obs.get("focus"), maximum=80)
        if source is not None:
            obs_out["source"] = source
        if isinstance(step_index, int):
            obs_out["step_index"] = step_index
        if isinstance(blackout, bool):
            obs_out["blackout"] = blackout
        if focus is not None:
            obs_out["focus"] = focus
        if obs_out:
            out["obs"] = obs_out

    return out


def _sanitize_surface_item_v1(value: Any) -> dict[str, Any] | None:
    """Return one bounded object/landmark item from the agent-visible surface grid."""
    if not isinstance(value, Mapping):
        return None
    out: dict[str, Any] = {}
    for key in ("token", "entity"):
        text = _safe_text(value.get(key), maximum=80)
        if text is not None:
            out[key] = text
    kind = _safe_text(value.get("kind"), maximum=80)
    if kind in _ALLOWED_SURFACE_KINDS:
        out["kind"] = kind
    for key in ("x", "y", "dx", "dy", "dist"):
        number = _finite_number(value.get(key))
        if number is not None:
            out[key] = number
    priority = _finite_number(value.get("priority_hint"))
    if isinstance(priority, int):
        out["priority_hint"] = priority
    focused = value.get("focused")
    if isinstance(focused, bool):
        out["focused"] = focused
    return out or None


def _sanitize_surface_grid_v1(value: Any) -> dict[str, Any]:
    """Return safe current geometry while discarding region position/zone labels."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, Any] = {}
    for key in ("schema", "frame"):
        text = _safe_text(value.get(key), maximum=100)
        if text is not None:
            out[key] = text

    for key in ("anchor", "center"):
        point = _sanitize_point_v1(value.get(key))
        if point is not None:
            out[key] = point

    for key in ("objects", "landmarks"):
        raw_items = value.get(key)
        items: list[dict[str, Any]] = []
        if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes, bytearray)):
            for raw_item in raw_items[:_MAX_SURFACE_ITEMS]:
                item = _sanitize_surface_item_v1(raw_item)
                if item is not None:
                    items.append(item)
        out[key] = items

    raw_affordances = value.get("affordances")
    affordances: dict[str, bool] = {}
    if isinstance(raw_affordances, Mapping):
        for key in ("cliff_near", "shelter_near", "mom_near"):
            item = raw_affordances.get(key)
            if isinstance(item, bool):
                affordances[key] = item
    out["affordances"] = affordances

    return out


def _sanitize_lower_motor_feedback_v1(value: Any) -> dict[str, Any] | None:
    """Return compact lower-action feedback without hidden trajectory/state data."""
    if not isinstance(value, Mapping):
        return None
    out: dict[str, Any] = {}
    for key in _ALLOWED_LOWER_MOTOR_TEXT_FIELDS:
        text = _safe_text(value.get(key), maximum=160)
        if text is not None:
            out[key] = text
    for key in _ALLOWED_LOWER_MOTOR_BOOLEAN_FIELDS:
        item = value.get(key)
        if isinstance(item, bool):
            out[key] = item
    for key in ("quality", "progress"):
        number = _finite_number(value.get(key))
        if number is not None:
            out[key] = number
    return out or None


def _sanitize_env_meta_v1(value: Any) -> dict[str, Any]:
    """Return the positive metadata whitelist for Phase 1A."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, Any] = {}
    for key in ("time_since_birth", "step_index", "obs_mask_dropped_preds", "obs_mask_dropped_cues"):
        number = _finite_number(value.get(key))
        if number is not None:
            out[key] = number

    for key in ("newborn_obs_blackout",):
        item = value.get(key)
        if isinstance(item, bool):
            out[key] = item

    for key in ("newborn_obs_blackout_kind", "mom_proximity_from_raw"):
        text = _safe_text(value.get(key), maximum=100)
        if text is not None:
            out[key] = text

    lower_feedback = _sanitize_lower_motor_feedback_v1(value.get("lower_motor_feedback_v1"))
    if lower_feedback is not None:
        out["lower_motor_feedback_v1"] = lower_feedback

    return out


@dataclass(frozen=True, slots=True)
class Nca8ObservationV1:
    """Recursively immutable agent-visible packet owned by the new runtime.

    The record contains only copied whitelist products.  It retains no reference
    to the source ``EnvObservation`` and offers ``as_dict`` only as a newly
    allocated diagnostic/export view.  Phase 1A transports and summarizes this
    packet but does not yet interpret it as cognition.
    """

    raw_sensors: Mapping[str, Any]
    predicates: tuple[str, ...]
    cues: tuple[str, ...]
    nav_patches: tuple[Mapping[str, Any], ...]
    env_meta: Mapping[str, Any]
    surface_grid: Mapping[str, Any]

    @property
    def step_index(self) -> int | None:
        """Return the whitelisted observation step index when present."""
        value = self.env_meta.get("step_index")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def as_dict(self) -> dict[str, Any]:
        """Return a newly allocated JSON-safe diagnostic representation."""
        return {
            "raw_sensors": _thaw_json_v1(self.raw_sensors),
            "predicates": list(self.predicates),
            "cues": list(self.cues),
            "nav_patches": [_thaw_json_v1(patch) for patch in self.nav_patches],
            "env_meta": _thaw_json_v1(self.env_meta),
            "surface_grid": _thaw_json_v1(self.surface_grid),
        }

    def compact_summary(self) -> dict[str, JsonScalarV1]:
        """Return bounded scalar counts suitable for the engineering trace."""
        return {
            "step_index": self.step_index,
            "raw_sensor_count": len(self.raw_sensors),
            "predicate_count": len(self.predicates),
            "cue_count": len(self.cues),
            "nav_patch_count": len(self.nav_patches),
        }


def adapt_env_observation_v1(observation: EnvObservation) -> Nca8ObservationV1:
    """Convert one environment observation through the positive whitelist.

    No fallback copies unknown fields.  A future environment field therefore
    remains unavailable to ``nca8`` until this function and its leakage tests are
    deliberately amended.
    """
    raw_out: dict[str, int | float] = {}
    raw_source = observation.raw_sensors if isinstance(observation.raw_sensors, Mapping) else {}
    for key in sorted(_ALLOWED_RAW_SENSOR_KEYS):
        number = _finite_number(raw_source.get(key))
        if number is not None:
            raw_out[key] = number

    predicates = _safe_token_tuple(observation.predicates, _ALLOWED_PREDICATES)
    cues = _safe_token_tuple(observation.cues, _ALLOWED_CUES)

    nav_patches: list[Mapping[str, Any]] = []
    raw_patches = observation.nav_patches
    if isinstance(raw_patches, Sequence) and not isinstance(raw_patches, (str, bytes, bytearray)):
        for raw_patch in raw_patches[:_MAX_NAV_PATCHES]:
            patch = _sanitize_navpatch_v1(raw_patch)
            if patch is not None:
                nav_patches.append(_freeze_json_v1(patch))

    env_meta = _sanitize_env_meta_v1(observation.env_meta)
    surface_grid = _sanitize_surface_grid_v1(observation.surface_grid)

    return Nca8ObservationV1(
        raw_sensors=_freeze_json_v1(raw_out),
        predicates=predicates,
        cues=cues,
        nav_patches=tuple(nav_patches),
        env_meta=_freeze_json_v1(env_meta),
        surface_grid=_freeze_json_v1(surface_grid),
    )


@dataclass(frozen=True, slots=True)
class Nca8EnvironmentResetV1:
    """Result of resetting one private new-runtime environment episode."""

    observation: Nca8ObservationV1
    episode_index: int
    scenario_name: str


@dataclass(frozen=True, slots=True)
class Nca8EnvironmentStepV1:
    """Result of applying Phase 1A's explicit null action to the environment."""

    observation: Nca8ObservationV1
    reward: float
    done: bool
    episode_index: int
    step_index: int


class Nca8EnvironmentBridgeV1:  # pylint: disable=too-few-public-methods
    """Own one private ``HybridEnvironment`` behind a narrow physical boundary.

    The bridge deliberately exposes no ``state`` property and no generic method
    for reading arbitrary environment attributes.  The new runtime receives only
    whitelisted observations plus small environment protocol results.
    """

    def __init__(self, *, scenario_name: str = "newborn_goat_first_hour") -> None:
        normalized_scenario = _safe_text(scenario_name, maximum=120)
        if normalized_scenario is None:
            raise ValueError("scenario_name must be a non-empty bounded string")
        self._scenario_name = normalized_scenario
        self._environment = HybridEnvironment(config=EnvConfig(scenario_name=normalized_scenario))

    @property
    def episode_index(self) -> int:
        """Return the public environment episode counter for diagnostics."""
        return int(self._environment.episode_index)

    def reset(self, *, seed: int | None = None) -> Nca8EnvironmentResetV1:
        """Reset the private episode and return only its whitelisted observation."""
        observation, info = self._environment.reset(seed=seed)
        raw_episode = info.get("episode_index") if isinstance(info, Mapping) else None
        episode_index = raw_episode if isinstance(raw_episode, int) and not isinstance(raw_episode, bool) else self.episode_index
        raw_scenario = info.get("scenario_name") if isinstance(info, Mapping) else None
        scenario_name = _safe_text(raw_scenario, maximum=120) or self._scenario_name
        return Nca8EnvironmentResetV1(
            observation=adapt_env_observation_v1(observation),
            episode_index=episode_index,
            scenario_name=scenario_name,
        )

    def apply_no_action(self) -> Nca8EnvironmentStepV1:
        """Advance the private environment with an explicit null task output.

        Phase 1A has no Attention, WNM, Navigation, primitive, PNM, BodyMap
        cognition, SEC, or WorldIndex.  Passing ``None`` is therefore the only
        honest environment action at this stage.
        """
        observation, reward, done, info = self._environment.apply_action(None, ctx=None)
        raw_episode = info.get("episode_index") if isinstance(info, Mapping) else None
        raw_step = info.get("step_index") if isinstance(info, Mapping) else None
        episode_index = raw_episode if isinstance(raw_episode, int) and not isinstance(raw_episode, bool) else self.episode_index
        step_index = raw_step if isinstance(raw_step, int) and not isinstance(raw_step, bool) else -1
        return Nca8EnvironmentStepV1(
            observation=adapt_env_observation_v1(observation),
            reward=float(reward),
            done=bool(done),
            episode_index=episode_index,
            step_index=step_index,
        )


def create_environment_bridge_v1(
    *,
    scenario_name: str = "newborn_goat_first_hour",
) -> Nca8EnvironmentBridgeV1:
    """Construct one new, unshared environment boundary for an ``nca8`` session."""
    return Nca8EnvironmentBridgeV1(scenario_name=scenario_name)
