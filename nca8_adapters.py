#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment boundary and observation firewall for the new CCA8 runtime.

Purpose
-------
The Architecture-v09.3 runtime may share the established physical-world
simulation, but it must not import legacy cognitive conclusions or read the
environment's God's-eye ``EnvState``.  This module is the only initial
``nca8_*`` module allowed to import :mod:`cca8_env`.

It performs three jobs:

* construct a private ``HybridEnvironment`` for each new-runtime session;
* expose reset plus explicit task-action advancement through the shared physical boundary;
* convert ``EnvObservation`` into a defensively copied, recursively immutable,
  positively whitelisted observation packet.

Unknown outer fields are discarded. The P15-1E-A support packet is stricter:
unknown fields inside ``raw_sensors["posture_support_v1"]`` reject that packet
atomically, with a bounded diagnostic reason and no new behavioral authority.
In particular, scenario stage, milestone lists,
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
from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from cca8_navpatch import CELL_BLOCKED, CELL_GOAL, CELL_HAZARD, CELL_TRAVERSABLE, CELL_UNKNOWN

from nca8_visual import VisualDetectionV1, VisualObservationV1
from nca8_maps import SupportObservationV1
from nca8_primitives import TaskActionKindV1, TaskActionV1

__version__ = "0.5.0"
__all__ = [
    "NCA8_SCAFFOLD_LEDGER_V1",
    "Nca8EnvironmentBridgeV1",
    "Nca8EnvironmentResetV1",
    "Nca8EnvironmentStepV1",
    "Nca8EnvironmentAdvanceV1",
    "Nca8ObservationV1",
    "Nca8ScaffoldLedgerEntryV1",
    "adapt_env_observation_v1",
    "admit_visual_surface_v1",
    "environment_token_for_task_action_v1",
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
        first_phase="1A transport; 1B/1C timing and transport only",
        replacement_target="modality-specific sensory services",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.raw_sensors.posture_support_v1",
        cognitive_meaning="bounded supplied support measurements; read-only, not action authority",
        first_phase="P15-1E-A injected observations and owning-sensory configuration",
        replacement_target="P16-1E-C trajectory/source refresh, then P16-1F/1G tested behavioral use",
        status="opt-in P16-1E-B support_dynamics_v1 world producer or synthetic fixture; read-only consumer",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.predicates[posture:fallen|posture:standing]",
        cognitive_meaning="pre-recognized posture configuration selecting canonical SELF-ground geometry",
        first_phase="1C body-sensory interpretation and POSTURE-SUPPORT NavMapState update",
        replacement_target="vestibular/proprioceptive/contact matching in the owning body-sensory circuit",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.predicates[other allowed tokens]",
        cognitive_meaning="selected interpreted perception tokens not yet given NCA8 cognitive authority",
        first_phase="1A transport; 1B/1C timing and transport only",
        replacement_target="owning sensory and association circuit derivation",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.cues",
        cognitive_meaning="selected salient sensory cues",
        first_phase="1A transport; 1B timing only; later sensory/association use",
        replacement_target="local sensory matching and activation",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="EnvObservation.nav_patches/surface_grid",
        cognitive_meaning="bounded current geometry without goal/stage labels",
        first_phase="1A transport; 1B/1C timing and transport only",
        replacement_target="new sensory and NavMap-state contracts",
        status="temporary explicit scaffold",
    ),
    Nca8ScaffoldLedgerEntryV1(
        source_field="env_meta.lower_motor_feedback_v1",
        cognitive_meaning="compact support, slip, progress, and error feedback",
        first_phase="1A transport; 1B timing only; later BodyMap/outcome use",
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
    """Return the positive metadata whitelist for the initial NCA8 runtime."""
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


def _adapt_support_observation_v1(raw_sensors: Mapping[str, Any]) -> tuple[SupportObservationV1 | None, str | None]:
    """Parse only ``EnvObservation.raw_sensors['posture_support_v1']``.

    An absent packet returns (None, None). A present malformed packet is rejected
    atomically with a bounded reason, without echoing its values. Unknown keys
    reject the whole packet, unlike the outer legacy whitelist's discard rule.
    Header fields are mandatory; omitted optional measurements become None.
    This adapter performs no pose, trajectory, outcome, or action inference.
    """
    if "posture_support_v1" not in raw_sensors:
        return None, None
    packet = raw_sensors["posture_support_v1"]
    allowed = {
        "schema", "sample_id", "event_cycle", "frame_id",
        "body_ground_angle_degrees", "useful_loading", "destabilization", "lateral_contact",
    }
    required = {"schema", "sample_id", "event_cycle", "frame_id"}
    if not isinstance(packet, Mapping):
        return None, "invalid_support_packet"
    if len(packet) > len(allowed) or any(key not in allowed for key in packet):
        return None, "unknown_support_fields"
    if not required.issubset(packet) or packet["schema"] != "posture_support_v1":
        return None, "invalid_support_header"
    try:
        sample = SupportObservationV1(
            sample_id=packet["sample_id"],
            event_cycle=packet["event_cycle"],
            frame_id=packet["frame_id"],
            body_ground_angle_degrees=packet.get("body_ground_angle_degrees"),
            useful_loading=packet.get("useful_loading"),
            destabilization=packet.get("destabilization"),
            lateral_contact=packet.get("lateral_contact"),
        )
    except (TypeError, ValueError, OverflowError):
        return None, "invalid_support_values"
    return sample, None


@dataclass(frozen=True, slots=True)
class Nca8ObservationV1:
    """Recursively immutable agent-visible packet owned by the new runtime.

    The record contains only copied whitelist products.  It retains no reference
    to the source ``EnvObservation`` and offers ``as_dict`` only as a newly
    allocated diagnostic/export view. Phase 1C posture tokens retain A0 authority.
    P15-1E-A also admits one typed support packet (or a bounded rejection reason)
    for an opt-in read-only consumer. It is not added to the generic raw channels.
    """

    raw_sensors: Mapping[str, Any]
    predicates: tuple[str, ...]
    cues: tuple[str, ...]
    nav_patches: tuple[Mapping[str, Any], ...]
    env_meta: Mapping[str, Any]
    surface_grid: Mapping[str, Any]
    support_observation: SupportObservationV1 | None = None
    support_observation_error: str | None = None

    @property
    def step_index(self) -> int | None:
        """Return the whitelisted observation step index when present."""
        value = self.env_meta.get("step_index")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def as_dict(self) -> dict[str, Any]:
        """Return a newly allocated JSON-safe diagnostic representation."""
        out = {
            "raw_sensors": _thaw_json_v1(self.raw_sensors),
            "predicates": list(self.predicates),
            "cues": list(self.cues),
            "nav_patches": [_thaw_json_v1(patch) for patch in self.nav_patches],
            "env_meta": _thaw_json_v1(self.env_meta),
            "surface_grid": _thaw_json_v1(self.surface_grid),
        }
        if self.support_observation is not None or self.support_observation_error is not None:
            out["support_observation"] = self.support_observation.as_dict() if self.support_observation is not None else None
            out["support_observation_error"] = self.support_observation_error
        return out

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

    support_observation, support_error = _adapt_support_observation_v1(raw_source)

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
        support_observation=support_observation,
        support_observation_error=support_error,
    )


def admit_visual_surface_v1(
    observation: Nca8ObservationV1 | None, *, stream: MotorStreamRefV1, sample_id: int,
    event_tick: int, available_tick: int,
) -> VisualObservationV1 | None:
    """Decode a narrow, opt-in horizontal visual scene from admitted geometry.

    First use adapt_env_observation_v1; this function accepts neither EnvState nor
    raw environment observations. It consumes only surface_grid schema/frame,
    anchor x/y, and objects/landmarks entity/kind/x/y. It ignores cues, predicates,
    affordances, proximity flags, preferred focus, priority hints and task labels.
    Entity strings are opaque supplied region handles, never maternal identities.

    The named scene_xy: frame explicitly denotes right-handed horizontal metre
    coordinates. The old frame='body' and dx/dy products are NOT reinterpreted as
    allocentric x/y. Partial coordinates remain unknown. The outer transport must
    supply original sample/event/availability; step_index must match event_tick.
    No missing clock, sample, heading or geometry is inferred. None or an absent
    surface is missing input; a valid empty surface is a distinct acquisition.
    Oversized/duplicate/malformed retained contributions reject the whole packet.
    """
    if observation is None:
        return None
    if not isinstance(observation, Nca8ObservationV1):
        raise TypeError("visual admission requires the already whitelisted observation")
    surface = observation.surface_grid
    if not surface or surface == {"objects": (), "landmarks": (), "affordances": {}}:
        # The retained whitelist normalizes a supplied empty surface to these keys.
        return None
    if surface.get("schema") != "surface_grid_v1":
        raise ValueError("visual preview requires the declared surface_grid_v1 schema")
    frame = surface.get("frame")
    if not isinstance(frame, str):
        raise ValueError("visual scene needs an explicit frame")
    if observation.step_index != event_tick or isinstance(event_tick, bool):
        raise ValueError("visual event must equal the observation's original step_index")

    def point(value: object) -> NavPointV1 | None:
        """Decode one complete x/y pair; never backfill one absent coordinate."""
        if not isinstance(value, Mapping):
            return None
        x, y = value.get("x"), value.get("y")
        if x is None or y is None:
            return None
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError("visual coordinates must be numeric or unknown")
        return NavPointV1(x, y)

    detections: list[VisualDetectionV1] = []
    for channel in ("objects", "landmarks"):
        items = surface.get(channel, ())
        if not isinstance(items, (tuple, list)) or len(items) + len(detections) > 8:
            raise ValueError("the visual profile admits at most eight regions, without silent truncation")
        for item in items:
            if not isinstance(item, Mapping):
                raise TypeError("visual region must be an admitted mapping")
            region_id = item.get("entity")
            descriptor = item.get("kind")
            if not isinstance(region_id, str) or (descriptor is not None and not isinstance(descriptor, str)):
                raise ValueError("visual region requires an opaque handle and optional category")
            detections.append(VisualDetectionV1(region_id, descriptor, point(item)))
    return VisualObservationV1(stream, sample_id, event_tick, available_tick, frame, point(surface.get("anchor")), tuple(detections))


_TASK_ACTION_TO_ENVIRONMENT_TOKEN_V1: dict[TaskActionKindV1, str | None] = {
    TaskActionKindV1.STAND_UP: "policy:stand_up",
    TaskActionKindV1.NO_ACTION: None,
}


def environment_token_for_task_action_v1(task_action: TaskActionV1 | None) -> str | None:
    """Map one internal task action onto the shared physical-world vocabulary.

    The environment token is a compatibility seam only.  NCA8 cognition never
    treats ``policy:stand_up`` as its primitive or internal action identity.
    """
    if task_action is None:
        return None
    if not isinstance(task_action, TaskActionV1):
        raise TypeError("task_action must be a TaskActionV1 or None")
    try:
        return _TASK_ACTION_TO_ENVIRONMENT_TOKEN_V1[task_action.kind]
    except KeyError as exc:  # pragma: no cover - enum additions require an explicit adapter update
        raise ValueError(f"unsupported NCA8 task action kind: {task_action.kind.value}") from exc


@dataclass(frozen=True, slots=True)
class Nca8EnvironmentResetV1:
    """Result of resetting one private new-runtime environment episode."""

    observation: Nca8ObservationV1
    episode_index: int
    scenario_name: str


@dataclass(frozen=True, slots=True)
class Nca8EnvironmentStepV1:
    """Result of applying one explicit NCA8 task output to the private world."""

    observation: Nca8ObservationV1
    reward: float
    done: bool
    episode_index: int
    step_index: int
    environment_action: str | None


@dataclass(frozen=True, slots=True)
class Nca8EnvironmentAdvanceV1:
    """World-side receipt before input admission; never a cognitive observation.

    Reward and done belong only to the outer evaluator/runner. The raw packet
    stays privately in the bridge until admission. Identity of this receipt,
    rather than its printable fields, controls the one permitted admission.
    """

    reward: float
    done: bool
    episode_index: int
    step_index: int
    environment_action: str | None


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
        self._pending_advance: Nca8EnvironmentAdvanceV1 | None = None
        self._pending_raw_observation: object = None
        self._boundary_faulted = False
        self._advancing = False

    @property
    def episode_index(self) -> int:
        """Return the public environment episode counter for diagnostics."""
        return int(self._environment.episode_index)

    def reset(self, *, seed: int | None = None) -> Nca8EnvironmentResetV1:
        """Explicitly reset the world and admit its initial packet, or remain stopped.

        Reset invalidates a pending world receipt before touching the backend.
        A failed reset cannot make an old packet admissible. Reentrant reset
        during world execution/admission is rejected, rather than changing the
        world underneath an outstanding operation.
        """
        if self._advancing:
            raise RuntimeError("cannot reset during world execution or input admission")
        self._pending_advance = None
        self._pending_raw_observation = None
        self._boundary_faulted = True
        self._advancing = True
        try:
            observation, info = self._environment.reset(seed=seed)
            if not isinstance(observation, EnvObservation):
                raise TypeError("world reset returned a missing or malformed EnvObservation")
            raw_episode = info.get("episode_index") if isinstance(info, Mapping) else None
            episode_index = raw_episode if isinstance(raw_episode, int) and not isinstance(raw_episode, bool) else self.episode_index
            raw_scenario = info.get("scenario_name") if isinstance(info, Mapping) else None
            scenario_name = _safe_text(raw_scenario, maximum=120) or self._scenario_name
            admitted = adapt_env_observation_v1(observation)
            result = Nca8EnvironmentResetV1(
                observation=admitted, episode_index=episode_index, scenario_name=scenario_name,
            )
            self._boundary_faulted = False
            return result
        finally:
            self._advancing = False

    def advance_task_action(self, task_action: TaskActionV1 | None) -> Nca8EnvironmentAdvanceV1:
        """Advance the private world once without admitting its resulting observation.

        The outer serialized driver calls this only after internal cycle closure
        and one-time handoff consumption. None means a null time step, not a
        fabricated movement. The raw returned packet remains private here.

        An exception may follow a physical side effect. Latch the bridge stopped
        until reset and never retry automatically. A returned receipt confirms
        that the call returned, not that the task succeeded. A second advance
        before the first packet's admission is rejected without another step.
        """
        if self._boundary_faulted or self._advancing:
            raise RuntimeError("environment boundary requires reset or is already advancing")
        if self._pending_advance is not None:
            raise RuntimeError("the previous world result still requires input admission")
        environment_action = environment_token_for_task_action_v1(task_action)
        self._advancing = True
        try:
            observation, reward, done, info = self._environment.apply_action(environment_action, ctx=None)
            raw_episode = info.get("episode_index") if isinstance(info, Mapping) else None
            raw_step = info.get("step_index") if isinstance(info, Mapping) else None
            episode_index = (
                raw_episode
                if isinstance(raw_episode, int) and not isinstance(raw_episode, bool)
                else self.episode_index
            )
            step_index = raw_step if isinstance(raw_step, int) and not isinstance(raw_step, bool) else -1
            advance = Nca8EnvironmentAdvanceV1(
                reward=float(reward), done=bool(done), episode_index=episode_index,
                step_index=step_index, environment_action=environment_action,
            )
            self._pending_raw_observation = observation
            self._pending_advance = advance
            return advance
        except BaseException:
            self._boundary_faulted = True
            raise
        finally:
            self._advancing = False

    def admit_observation(self, advance: Nca8EnvironmentAdvanceV1) -> Nca8EnvironmentStepV1:
        """Admit/detach the exact pending world packet once through the existing whitelist.

        This input-boundary operation never advances time. A lost or malformed
        outer packet stops the bridge; it is not replaced with the previous
        observation. Invalid optional support content retains the existing
        packet-level rejection reason and does not acquire behavioral authority.
        Foreign, copied or already consumed receipts are rejected before reading
        a packet. Raw EnvObservation never leaves this bridge.
        """
        if self._boundary_faulted or self._advancing:
            raise RuntimeError("environment boundary requires reset or is already busy")
        if advance is not self._pending_advance or not isinstance(advance, Nca8EnvironmentAdvanceV1):
            raise RuntimeError("foreign, stale or copied world receipt")
        raw = self._pending_raw_observation
        self._pending_raw_observation = None
        self._pending_advance = None
        self._advancing = True
        try:
            if not isinstance(raw, EnvObservation):
                raise TypeError("world step returned a missing or malformed EnvObservation")
            observation = adapt_env_observation_v1(raw)
            return Nca8EnvironmentStepV1(
                observation=observation, reward=advance.reward, done=advance.done,
                episode_index=advance.episode_index, step_index=advance.step_index,
                environment_action=advance.environment_action,
            )
        except BaseException:
            self._boundary_faulted = True
            raise
        finally:
            self._advancing = False

    def apply_task_action(self, task_action: TaskActionV1 | None) -> Nca8EnvironmentStepV1:
        """Compatibility outer service: world advancement followed by separate admission.

        NCA8's core never calls this method. The P16-1R-B runner uses the two
        explicit operations to trace their actual domain boundaries. This helper
        retains the old return type for isolated adapter clients, with the same
        no-retry/fault behavior. It performs no task selection or safety rescue.
        """
        return self.admit_observation(self.advance_task_action(task_action))

    def apply_no_action(self) -> Nca8EnvironmentStepV1:
        """Compatibility helper that advances the world with no task action."""
        return self.apply_task_action(None)



def create_environment_bridge_v1(
    *,
    scenario_name: str = "newborn_goat_first_hour",
) -> Nca8EnvironmentBridgeV1:
    """Construct one new, unshared environment boundary for an ``nca8`` session."""
    return Nca8EnvironmentBridgeV1(scenario_name=scenario_name)
