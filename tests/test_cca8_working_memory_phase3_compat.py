# -*- coding: utf-8 -*-
"""Compatibility tests for Working Memory refactor Phase 3."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import cca8_run
import cca8_working_memory
from cca8_context import Ctx
from cca8_env import EnvObservation

# This white-box compatibility test intentionally exercises runner-private aliases.
# pylint: disable=protected-access


def test_runner_phase3_aliases_and_implementation_ownership() -> None:
    """Pure Phase-3 helpers should alias the extracted module; orchestration should live there."""
    assert cca8_run.init_map_surface_world is cca8_working_memory.init_map_surface_world
    assert cca8_run.update_surface_grid_from_obs is cca8_working_memory.update_surface_grid_from_obs
    assert cca8_run.update_map_surface_from_obs is cca8_working_memory.update_map_surface_from_obs
    assert cca8_run.predcode_update_from_obs is cca8_working_memory.predcode_update_from_obs
    assert cca8_run._wm_display_id is cca8_working_memory._wm_display_id
    assert cca8_run._prune_working_world is cca8_working_memory._prune_working_world
    assert cca8_working_memory.inject_obs_into_working_world.__module__ == "cca8_working_memory"
    assert cca8_working_memory.maybe_autoretrieve_mapsurface_on_keyframe.__module__ == "cca8_working_memory"


def test_working_memory_phase3_remains_one_way_and_reports_version() -> None:
    """The completed working-memory extraction should not import the interactive runner."""
    assert "cca8_run" not in cca8_working_memory.__dict__
    assert cca8_working_memory.__version__ == "0.3.0"


def test_direct_phase3_observation_injection_updates_mapsurface_and_navsummary() -> None:
    """Direct module users should be able to execute the complete live WorkingMap pipeline."""
    ctx = Ctx()
    ctx.working_world = cca8_working_memory.init_working_world()
    ctx.working_enabled = True
    ctx.working_mapsurface = True
    ctx.navpatch_enabled = True
    ctx.wm_surfacegrid_enabled = True
    ctx.wm_navsummary_enabled = True

    obs = EnvObservation(
        predicates=[
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ],
        cues=["vision:silhouette:mom"],
        env_meta={"scenario_stage": "first_stand"},
        raw_sensors={},
    )

    result = cca8_working_memory.inject_obs_into_working_world(ctx, obs)

    assert result["predicates"] == list(obs.predicates)
    assert result["cues"] == list(obs.cues)
    assert {"self", "mom", "shelter", "cliff"}.issubset(ctx.wm_entities)
    assert isinstance(ctx.wm_navsummary, dict)
    assert "hazard_near" in ctx.wm_navsummary


def test_runner_phase3_injection_resolves_current_init_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner wrapper should resolve its WorkingMap factory at call time."""
    calls: list[str] = []

    def fake_init_working_world() -> Any:
        """Record the call while returning a real isolated WorkingMap."""
        calls.append("init")
        return cca8_working_memory.init_working_world()

    monkeypatch.setattr(cca8_run, "init_working_world", fake_init_working_world)

    ctx = Ctx()
    ctx.working_world = None
    ctx.working_mapsurface = False
    result = cca8_run.inject_obs_into_working_world(
        ctx,
        EnvObservation(predicates=["posture:standing"], cues=[]),
    )

    assert calls == ["init"]
    assert result["predicates"] == ["posture:standing"]
    assert ctx.working_world is not None


def test_runner_goat04_wrapper_resolves_current_storage_and_zone_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contextual switching should use runner-visible storage and BodyMap hooks."""
    calls: dict[str, Any] = {}

    def fake_zone(_ctx: Ctx) -> str:
        """Return a deterministic zone for the wrapper seam."""
        calls["zone"] = True
        return "safe"

    def fake_store(_world: Any, _ctx: Ctx, **kwargs: Any) -> dict[str, Any]:
        """Record one contextual seed write without touching Column memory."""
        calls["store"] = kwargs
        return {"stored": True, "sig": "a" * 64, "engram_id": "phase3-goat04-engram"}

    monkeypatch.setattr(cca8_run, "body_space_zone", fake_zone)
    monkeypatch.setattr(cca8_run, "store_mapsurface_snapshot_v1", fake_store)

    ctx = Ctx()
    obs = EnvObservation(
        predicates=[],
        cues=[],
        env_meta={"scenario_stage": "goat_foraging_04_scan", "milestones": ["context:fox"]},
    )

    result = cca8_run.maybe_goat04_context_mapswitch_on_keyframe_v1(object(), ctx, obs)

    assert result["handled"] is True
    assert "store goat04:fox" in str(result["store"])
    assert calls["zone"] is True
    assert calls["store"]["reason"] == "goat04_seed:fox"


def test_runner_newborn_hint_wrapper_uses_current_column_object(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner's retrieved-hint wrapper should read from its current Column object."""
    record = {
        "payload": {
            "header": {
                "body": {
                    "posture": "standing",
                    "mom_distance": "near",
                    "nipple_state": "reachable",
                    "zone": "safe",
                }
            },
            "entities": [],
        }
    }
    fake_column = SimpleNamespace(try_get=lambda _engram_id: record)
    monkeypatch.setattr(cca8_run, "column_mem", fake_column)

    ctx = Ctx()
    hint = cca8_run._set_newborn_retrieved_hint_from_engram_v1(ctx, "phase3-hint", ttl_steps=2)

    assert hint["posture"] == "standing"
    assert hint["mom_distance"] == "near"
    assert ctx.experiment_newborn_retrieved_hint_source == "phase3-hint"
