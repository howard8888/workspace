# tests/test_policy_rest.py
import pytest
import cca8_world_graph as wg
from cca8_controller import Drives
from cca8_run import Ctx, PolicyRuntime, CATALOG_GATES


def _has_pred(world, token):
    full = token if token.startswith("pred:") else f"pred:{token}"
    return any(full in (getattr(b, "tags", []) or []) for b in world._bindings.values())


def test_rest_triggers_and_reduces_fatigue():
    world = wg.WorldGraph(); world.ensure_anchor("NOW")
    d = Drives(fatigue=0.86)  # above FATIGUE_HIGH=0.70
    ctx = Ctx()

    rt = PolicyRuntime(CATALOG_GATES)
    rt.refresh_loaded(ctx)

    # Identify which gates trigger at this fatigue
    matches = [p for p in rt.loaded if p.trigger(world, d, ctx)]
    names = {p.name for p in matches}
    # Only rest should be eligible in this scenario (no posture, no cues)
    assert "policy:rest" in names
    assert "policy:stand_up" not in names
    assert "policy:seek_nipple" not in names

    # Simulate a controller step via the core Action Center
    from cca8_controller import action_center_step
    res = action_center_step(world, ctx, d)
    assert res["policy"] == "policy:rest"

    # Rest reduces fatigue by 0.2 (clamped at 0)
    assert d.fatigue == pytest.approx(0.66, abs=1e-9)
    # Canonical resting predicate should be present (state:resting is legacy)
    assert _has_pred(world, "resting") or _has_pred(world, "state:resting")
   
    
    
    
    
    
    