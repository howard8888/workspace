# -*- coding: utf-8 -*-
"""Compatibility tests for Phase 1 of the CCA8 working-memory extraction."""

from __future__ import annotations

from typing import Any

import pytest

import cca8_run
import cca8_working_memory

# This white-box compatibility test intentionally exercises runner-private aliases.
# pylint: disable=protected-access


def test_runner_phase1_aliases_resolve_to_working_memory_module() -> None:
    """Historical runner names should point to the extracted implementations."""
    assert cca8_run.init_working_world is cca8_working_memory.init_working_world
    assert cca8_run.reset_working_world is cca8_working_memory.reset_working_world
    assert cca8_run.serialize_mapsurface_v1 is cca8_working_memory.serialize_mapsurface_v1
    assert cca8_run.store_mapsurface_snapshot_v1 is cca8_working_memory.store_mapsurface_snapshot_v1
    assert cca8_run.pick_best_wm_mapsurface_rec is cca8_working_memory.pick_best_wm_mapsurface_rec
    assert (
        cca8_run.load_mapsurface_payload_v1_into_workingmap
        is cca8_working_memory.load_mapsurface_payload_v1_into_workingmap
    )
    assert (
        cca8_run.merge_mapsurface_payload_v1_into_workingmap
        is cca8_working_memory.merge_mapsurface_payload_v1_into_workingmap
    )
    assert cca8_run.format_mapswitch_event_line_v1 is cca8_working_memory.format_mapswitch_event_line_v1


def test_working_memory_module_owns_phase1_implementation_without_runner_import() -> None:
    """The extracted subsystem should be independently importable and one-way."""
    assert "cca8_run" not in cca8_working_memory.__dict__
    assert cca8_working_memory.serialize_mapsurface_v1.__module__ == "cca8_working_memory"
    assert cca8_working_memory.pick_best_wm_mapsurface_rec.__module__ == "cca8_working_memory"
    assert cca8_working_memory.load_wm_mapsurface_engram_into_workingmap_mode.__module__ == "cca8_working_memory"


def test_direct_working_memory_round_trip_preserves_entities_and_relations() -> None:
    """Direct module users should be able to reconstruct and serialize a MapSurface."""
    ctx = cca8_run.Ctx()
    ctx.working_world = cca8_working_memory.init_working_world()

    payload = {
        "schema": "wm_mapsurface_v1",
        "entities": [
            {
                "eid": "self",
                "kind": "agent",
                "pos": {"x": 0.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": 0.0,
                "dist_class": "self",
                "preds": ["posture:standing"],
                "cues": [],
            },
            {
                "eid": "mom",
                "kind": "agent",
                "pos": {"x": 1.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": 1.0,
                "dist_class": "near",
                "preds": ["proximity:mom:near"],
                "cues": ["vision:silhouette:mom"],
            },
        ],
        "relations": [
            {
                "rel": "distance_to",
                "src": "self",
                "dst": "mom",
                "meters": 1.0,
                "class": "near",
                "frame": "wm_schematic_v1",
            }
        ],
    }

    loaded = cca8_working_memory.load_mapsurface_payload_v1_into_workingmap(
        ctx,
        payload,
        replace=True,
        reason="compat_round_trip",
    )
    serialized = cca8_working_memory.serialize_mapsurface_v1(ctx)

    assert loaded == {"ok": True, "entities": 2, "relations": 1}
    assert serialized["schema"] == "wm_mapsurface_v1"
    assert {row["eid"] for row in serialized["entities"]} == {"self", "mom"}
    assert serialized["relations"] == payload["relations"]


def test_runner_autoretrieve_resolves_runner_visible_hooks_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runner-owned orchestration should retain its historical monkeypatch seams."""
    calls: dict[str, Any] = {}

    def fake_picker(**kwargs: Any) -> dict[str, Any]:
        calls["picker"] = kwargs
        return {
            "ok": True,
            "source": "compat",
            "match": "stage+zone",
            "ranked": [{"engram_id": "compat-engram", "score": 1.0}],
        }

    def fake_loader(_ctx: Any, engram_id: str, *, mode: str = "replace") -> dict[str, Any]:
        calls["loader"] = {"engram_id": engram_id, "mode": mode}
        return {
            "ok": True,
            "mode": mode,
            "engram_id": engram_id,
            "cue_tag_delta": 0,
            "merge_guardrail_ok": True,
        }

    monkeypatch.setattr(cca8_run, "pick_best_wm_mapsurface_rec", fake_picker)
    monkeypatch.setattr(cca8_run, "load_wm_mapsurface_engram_into_workingmap_mode", fake_loader)

    ctx = cca8_run.Ctx()
    ctx.working_world = cca8_run.init_working_world()
    ctx.wm_mapsurface_autoretrieve_enabled = True

    out = cca8_run.maybe_autoretrieve_mapsurface_on_keyframe(
        object(),
        ctx,
        stage="rest",
        zone="safe",
        reason="compat_test",
        mode="merge",
        log=False,
    )

    assert out["ok"] is True
    assert out["engram_id"] == "compat-engram"
    assert calls["picker"]["stage"] == "rest"
    assert calls["loader"] == {"engram_id": "compat-engram", "mode": "merge"}


def test_working_memory_version_appears_in_runner_report() -> None:
    """Version diagnostics should include the new production module."""
    versions = cca8_run.versions_dict()

    assert versions["working_memory"] == cca8_working_memory.__version__
    assert versions["working_memory_path"].endswith("cca8_working_memory.py")
