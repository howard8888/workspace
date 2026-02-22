"""Unit tests for Phase X per-cycle JSONL logging.

These tests are intentionally narrow and pragmatic:

- Ensure the env-loop appends *exactly one* JSON record per closed-loop step.
  (We previously had a regression where record construction was duplicated.)

- Ensure the JSON record field `efe_scores` is always a list, even if upstream
  scaffolding accidentally leaves ctx.efe_last_scores in a non-list shape.

Pytest import-mode can vary between environments. To keep these tests robust when
run from the repo root or via preflight helpers, we explicitly ensure the repo
root is on sys.path.
"""

from __future__ import annotations

import os
import sys


# Ensure repo root is importable even under pytest --import-mode=importlib.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class _PolicyRuntimeStub:
    """Minimal PolicyRuntime stub for env-loop tests.

    We want the closed-loop step to execute without writing to the WorldGraph via
    controller policies. Returning "no_match" keeps the environment moving while
    preserving test determinism.
    """

    def __init__(self) -> None:
        self.loaded = []

    def refresh_loaded(self, ctx) -> None:  # pylint: disable=unused-argument
        self.loaded = []

    def consider_and_maybe_fire(self, world, drives, ctx, tie_break: str = "first", exec_world=None) -> str:  # noqa: D401
        return "no_match"


def test_cycle_json_record_is_single_and_efe_scores_is_list() -> None:
    """One env step should produce exactly one JSON record with list-valued efe_scores."""

    # pylint: disable=import-outside-toplevel
    from cca8_env import HybridEnvironment
    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives
    from cca8_run import Ctx, run_env_closed_loop_steps

    env = HybridEnvironment()
    world = WorldGraph()
    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)

    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)

    # Keep this test focused on JSON record plumbing.
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    ctx.env_loop_cycle_summary = False
    ctx.working_enabled = False
    ctx.wm_creative_enabled = False

    # Simulate a buggy upstream assignment; the record builder must coerce.
    ctx.efe_last_scores = {"oops": 1}

    run_env_closed_loop_steps(env, world, drives, ctx, _PolicyRuntimeStub(), n_steps=1)

    assert len(ctx.cycle_json_records) == 1
    rec = ctx.cycle_json_records[0]
    assert isinstance(rec.get("efe_scores"), list)