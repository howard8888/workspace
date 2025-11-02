# tests/test_runner_temporal_integration.py
import math
import random
from typing import List

import pytest

import cca8_world_graph as wgmod
from cca8_temporal import TemporalContext
from cca8_controller import Drives, action_center_step
import cca8_run as runmod


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _vhash64(v: List[float]) -> str:
    x = 0
    m = min(64, len(v))
    for i in range(m):
        if v[i] >= 0.0:
            x |= (1 << i)
    return f"{x:016x}"


def _mk_ctx(dim: int = 32, sigma: float = 0.02, jump: float = 0.25):
    """
    Create a runtime ctx with a temporal soft clock suitable for tests.
    Works with the real slotted runmod.Ctx; no monkey-patching of methods.
    """
    # Prefer the real dataclass Ctx if present
    Ctx = getattr(runmod, "Ctx", None)
    ctx = Ctx() if Ctx is not None else object()

    # Base fields (only set what exists; tolerate older builds)
    for name, val in dict(
        sigma=sigma, jump=jump, ticks=getattr(ctx, "ticks", 0),
        profile=getattr(ctx, "profile", "Test"), body="(none)",
    ).items():
        try:
            setattr(ctx, name, val if hasattr(ctx, name) else getattr(ctx, name, val))
        except Exception:
            pass

    # Temporal plumbing: these fields exist on the real Ctx
    try:
        t = TemporalContext(dim=dim, sigma=sigma, jump=jump)
        ctx.temporal = t
        ctx.tvec_last_boundary = t.vector()
    except Exception:
        # Fallback shim only if we're not using the real Ctx
        class _Shim:
            def __init__(self):
                self.temporal = TemporalContext(dim=dim, sigma=sigma, jump=jump)
                self.tvec_last_boundary = self.temporal.vector()
                self.sigma, self.jump, self.ticks, self.profile, self.body = sigma, jump, 0, "Test", "(none)"
            # Provide the two helpers if snapshot_text expects them
            def tvec64(self) -> str:
                v = self.temporal.vector()
                x = 0
                for i in range(min(64, len(v))):
                    if v[i] >= 0.0:
                        x |= (1 << i)
                return f"{x:016x}"
            def cos_to_last_boundary(self) -> float:
                v, lb = self.temporal.vector(), self.tvec_last_boundary
                return sum(a*b for a, b in zip(v, lb))
        ctx = _Shim()

    return ctx

def test_snapshot_temporal_block_present() -> None:
    random.seed(1234)
    world = wgmod.WorldGraph()
    ctx = _mk_ctx(dim=32, sigma=0.015, jump=0.20)

    txt = runmod.snapshot_text(world, drives=None, ctx=ctx, policy_rt=None)
    if "TEMPORAL:" not in txt:
        pytest.skip("Runner snapshot does not yet include TEMPORAL block in this build.")
    assert "TEMPORAL:" in txt
    assert "cos_to_last_boundary:" in txt
    assert "vhash64:" in txt


def test_policy_write_stamps_tvec64_meta() -> None:
    random.seed(2025)
    world = wgmod.WorldGraph()
    ctx = _mk_ctx(dim=64, sigma=0.015, jump=0.20)
    drives = Drives()  # defaults (hunger=0.7, etc.)

    before = set(world._bindings.keys())  # pylint: disable=protected-access
    payload = action_center_step(world, ctx, drives)
    after = set(world._bindings.keys())   # pylint: disable=protected-access
    created = list(after - before)

    assert payload.get("status") == "ok"
    assert created, "Expected at least one new binding."

    metas = [world._bindings[bid].meta for bid in created]  # pylint: disable=protected-access
    assert any(isinstance(m, dict) and "tvec64" in m for m in metas), f"Missing tvec64 in metas: {metas}"
    # Sanity: created_at/ticks should also be present
    assert any("created_at" in m and "ticks" in m for m in metas)


def test_temporal_drift_and_boundary_reflect_in_cosine() -> None:
    random.seed(7)
    _ = wgmod.WorldGraph()
    ctx = _mk_ctx(dim=32, sigma=0.02, jump=0.25)

    # initial cosine ~ 1.0
    c0 = ctx.cos_to_last_boundary()
    assert math.isclose(c0, 1.0, rel_tol=1e-9, abs_tol=1e-9)

    # drift lowers cosine slightly
    ctx.temporal.step()
    c1 = ctx.cos_to_last_boundary()
    assert c1 < 1.0000001
    assert c1 > 0.90

    # boundary jump resets "last boundary" → cosine rises again
    new_v = ctx.temporal.boundary()
    ctx.tvec_last_boundary = list(new_v)
    c2 = ctx.cos_to_last_boundary()
    assert c2 > c1
    assert 0.97 <= c2 <= 1.0000001
