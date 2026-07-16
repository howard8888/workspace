# -*- coding: utf-8 -*-
"""Compatibility tests for Working Memory refactor Phase 2."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import cca8_run
import cca8_working_memory
from cca8_context import Ctx
from cca8_env import EnvObservation, EnvState, PerceptionAdapter


def test_runner_phase2_pure_aliases_resolve_to_working_memory_module() -> None:
    """Pure NavPatch, SurfaceGrid, and NavSummary names should remain import-compatible."""
    assert cca8_run.navpatch_payload_sig_v1 is cca8_working_memory.navpatch_payload_sig_v1
    assert cca8_run.navpatch_similarity_v1 is cca8_working_memory.navpatch_similarity_v1
    assert cca8_run.compute_navsummary_v1 is cca8_working_memory.compute_navsummary_v1
    assert cca8_run.format_navsummary_line_v1 is cca8_working_memory.format_navsummary_line_v1
    assert cca8_run.render_surfacegrid_ascii_with_salience_v1 is cca8_working_memory.render_surfacegrid_ascii_with_salience_v1


def test_working_memory_module_owns_phase2_without_runner_import() -> None:
    """Phase-2 implementations should remain one-way after later extraction phases."""
    assert "cca8_run" not in cca8_working_memory.__dict__
    assert cca8_working_memory.__version__ == "0.3.1"
    assert cca8_working_memory.navpatch_predictive_match_loop_v1.__module__ == "cca8_working_memory"
    assert cca8_working_memory.update_working_navpatch_scratch_zoom_v1.__module__ == "cca8_working_memory"
    assert cca8_working_memory.update_working_salience_surfacegrid_v1.__module__ == "cca8_working_memory"


def test_runner_navpatch_store_wrapper_resolves_current_column_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner wrapper should pass its current Column object into the extracted store helper."""
    calls: list[tuple[str, dict[str, Any], Any]] = []

    def fake_assert_fact(name: str, payload: dict[str, Any], meta: Any) -> str:
        """Record one fake Column write and return a deterministic engram id."""
        calls.append((name, payload, meta))
        return "phase2-navpatch-engram"

    monkeypatch.setattr(cca8_run, "column_mem", SimpleNamespace(assert_fact=fake_assert_fact))

    ctx = Ctx()
    patch = {
        "schema": "navpatch_v1",
        "local_id": "scene",
        "entity_id": "self",
        "role": "scene",
        "frame": "ego",
        "tags": ["terrain:open"],
    }

    result = cca8_run.store_navpatch_engram_v1(ctx, patch, reason="phase2_test")

    assert result["stored"] is True
    assert result["engram_id"] == "phase2-navpatch-engram"
    assert calls and calls[0][0] == "navpatch"
    assert calls[0][1] is patch


def test_runner_navpatch_priors_wrapper_resolves_current_body_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner wrapper should resolve its BodyMap-zone helper at call time."""
    def fake_body_space_zone(_ctx: Ctx) -> str:
        """Return the unsafe zone that activates the hazard prior."""
        return "unsafe_cliff_near"

    monkeypatch.setattr(cca8_run, "body_space_zone", fake_body_space_zone)

    ctx = Ctx()
    ctx.navpatch_priors_hazard_bias = 0.25
    obs = EnvObservation(env_meta={"scenario_stage": "birth"})

    priors = cca8_run.navpatch_priors_bundle_v1(ctx, obs)

    assert priors["zone"] == "unsafe_cliff_near"
    assert priors["hazard_bias"] == pytest.approx(0.25)


def test_direct_phase2_surfacegrid_pipeline_builds_navsummary() -> None:
    """Direct callers should be able to compose a SurfaceGrid and NavSummary without the runner."""
    ctx = Ctx()
    ctx.working_world = cca8_working_memory.init_working_world()

    state = EnvState(
        kid_posture="standing",
        mom_distance="near",
        shelter_distance="near",
        cliff_distance="near",
        nipple_state="reachable",
        scenario_stage="first_stand",
        position="shelter_area",
        kid_position=(1.6, 0.0),
        mom_position=(1.95, 0.0),
    )
    state.update_zone_from_position()
    obs = PerceptionAdapter().observe(state)

    result = cca8_working_memory.update_working_salience_surfacegrid_v1(
        ctx,
        obs,
        ctx.working_world,
        changed_entities=set(),
        new_cue_entities=set(),
    )

    assert ctx.wm_surfacegrid is not None
    assert isinstance(ctx.wm_surfacegrid_sig16, str) and len(ctx.wm_surfacegrid_sig16) == 16
    assert result["surfacegrid_sig16"] == ctx.wm_surfacegrid_sig16
    assert result["navsummary"]["schema"] == "wm_navsummary_v1"
    assert result["navsummary"]["hazard_near"] is True
