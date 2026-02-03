# -*- coding: utf-8 -*-
"""
Unit tests for the MapSurface auto-retrieve guard hook.

We keep these tests intentionally small:
- They validate the decision logic and stable output keys.
- They do NOT require HybridEnvironment or Column memory.
"""

from __future__ import annotations

from cca8_run import Ctx, should_autoretrieve_mapsurface


class _ObsStub:
    """Minimal EnvObservation-ish stub for guard tests."""
    def __init__(self, predicates=None, cues=None):
        self.predicates = list(predicates or [])
        self.cues = list(cues or [])


def test_guard_disabled_returns_disabled():
    ctx = Ctx()
    ctx.wm_mapsurface_autoretrieve_enabled = False

    out = should_autoretrieve_mapsurface(
        ctx,
        _ObsStub(predicates=["posture:standing"], cues=["vision:silhouette:mom"]),
        stage="rest",
        zone="safe",
        stage_changed=True,
        zone_changed=False,
        boundary_reason="auto_boundary_stage:foo->bar",
    )

    assert out["ok"] is False
    assert out["why"] == "disabled"
    assert "mode" in out and "top_k" in out and "verbose" in out and "diag" in out


def test_guard_not_boundary_returns_not_boundary_even_if_enabled():
    ctx = Ctx()
    ctx.wm_mapsurface_autoretrieve_enabled = True

    out = should_autoretrieve_mapsurface(
        ctx,
        _ObsStub(predicates=["posture:standing"]),
        stage="rest",
        zone="safe",
        stage_changed=False,
        zone_changed=False,
        boundary_reason="no_boundary",
    )

    assert out["ok"] is False
    assert out["why"] == "not_boundary"



def test_guard_enabled_boundary_allows_and_normalizes_mode_and_topk():
    ctx = Ctx()
    ctx.wm_mapsurface_autoretrieve_enabled = True
    ctx.wm_mapsurface_autoretrieve_mode = "REPLACE"
    ctx.wm_mapsurface_autoretrieve_top_k = 999  # should clamp to 10

    # Minimal gating: ensure the guard has a reason to attempt retrieval at this boundary.
    # v0 pred error is the simplest stable trigger for "need_priors".
    ctx.pred_err_v0_last = {"posture": 1}

    out = should_autoretrieve_mapsurface(
        ctx,
        _ObsStub(predicates=["posture:standing", "hazard:cliff:far"]),
        stage="first_stand",
        zone="safe",
        stage_changed=False,
        zone_changed=True,
        boundary_reason="auto_boundary_zone:safe->unsafe_cliff_near",
    )

    assert out["ok"] is True
    assert out["why"] == "enabled_boundary_pred_err"
    assert out["mode"] == "replace"
    assert out["top_k"] == 10
