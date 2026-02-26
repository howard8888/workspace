# -*- coding: utf-8 -*-
"""
Phase X Step 15C tests: minimal probe/inspect policy driven by WM.Scratch ambiguity.

We verify:
  1) Step 15A writes an ambiguity key into ctx.wm_scratch_navpatch_last_keys.
  2) The runner gate triggers policy:probe (and it beats the permissive fallback).
  3) policy:probe temporarily boosts ctx.navpatch_precision_grid and sets restore bookkeeping.
  4) navpatch_predictive_match_loop_v1 auto-restores the previous precision value after the window expires.
"""

from __future__ import annotations

import pytest

import cca8_world_graph
from cca8_controller import Drives
from cca8_run import (
    CATALOG_GATES,
    Ctx,
    PolicyRuntime,
    inject_obs_into_working_world,
    navpatch_predictive_match_loop_v1,
)


class _ObsStub:  # pylint: disable=too-few-public-methods
    def __init__(self, *, predicates=None, cues=None, nav_patches=None):
        self.predicates = list(predicates or [])
        self.cues = list(cues or [])
        self.nav_patches = list(nav_patches or [])
        self.raw_sensors = {}
        self.env_meta = {}


def _ambiguous_patch(*, entity_id="cliff", local_id="p_cliff"):
    # Keep this minimal: Step 15A only needs match.commit == "ambiguous" and (entity_id, local_id).
    return {
        "entity_id": entity_id,
        "local_id": local_id,
        "role": "hazard",
        "frame": "wm_schematic_v1",
        "sig16": "deadbeefdeadbeef",
        "tags": ["hazard:cliff", "cliff:near", "shelter:far"],
        "match": {
            "commit": "ambiguous",
            "decision": "new_near_match",
            "decision_note": "ambiguous_low_margin",
            "margin": 0.02,
            "best": {"engram_id": "e1", "score": 0.90},
            "top_k": [
                {"engram_id": "e1", "score": 0.90},
                {"engram_id": "e2", "score": 0.88},
            ],
        },
    }


def test_step15c_probe_policy_fires_and_restores_precision():
    ctx = Ctx()
    ctx.controller_steps = 10

    # Keep the test focused: we only need WorkingMap injection to create WM.Scratch ambiguity keys.
    ctx.working_enabled = True
    ctx.navpatch_enabled = True
    ctx.navpatch_store_to_column = False
    ctx.wm_surfacegrid_enabled = False
    ctx.wm_salience_enabled = False

    # Ensure the pre-probe precision is a known baseline.
    ctx.navpatch_precision_grid = 0.0

    obs = _ObsStub(predicates=["posture:standing"], cues=[], nav_patches=[_ambiguous_patch()])
    inject_obs_into_working_world(ctx, obs)

    assert isinstance(ctx.wm_scratch_navpatch_last_keys, set)
    assert ctx.wm_scratch_navpatch_last_keys, "precondition: Step 15A should have created scratch keys"

    # Build a small long-term WorldGraph that is NOT fallen (otherwise safety override blocks probe).
    world = cca8_world_graph.WorldGraph()
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")
    world.add_predicate("posture:standing", attach="now", meta={"test": True})

    drives = Drives(hunger=0.10, fatigue=0.10, warmth=0.60)

    rt = PolicyRuntime(CATALOG_GATES)
    rt.refresh_loaded(ctx)
    fired_txt = rt.consider_and_maybe_fire(world, drives, ctx)

    assert isinstance(fired_txt, str)
    assert fired_txt.startswith("policy:probe"), fired_txt

    # Probe should boost grid precision and set restore bookkeeping.
    assert pytest.approx(ctx.navpatch_precision_grid, rel=1e-6) == float(ctx.wm_probe_grid_precision)
    assert ctx.wm_probe_last_step == 10
    assert ctx.wm_probe_restore_step == 12

    # Before restore_step: still boosted.
    ctx.controller_steps = 11
    navpatch_predictive_match_loop_v1(ctx, _ObsStub(nav_patches=[]))
    assert pytest.approx(ctx.navpatch_precision_grid, rel=1e-6) == float(ctx.wm_probe_grid_precision)

    # At restore_step: restored to baseline.
    ctx.controller_steps = 12
    navpatch_predictive_match_loop_v1(ctx, _ObsStub(nav_patches=[]))
    assert pytest.approx(ctx.navpatch_precision_grid, rel=1e-6) == 0.0
    assert ctx.wm_probe_restore_step is None