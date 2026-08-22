"""Focused tests for the CCA8 same-cycle action-dispatch contract."""

from __future__ import annotations

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives, body_posture
from cca8_env import HybridEnvironment
from cca8_world_graph import WorldGraph


class _FixedPolicyRuntime:
    """Return one configurable policy result without adding unrelated writes."""

    def __init__(self, result: str) -> None:
        self.result = result
        self.loaded: list[object] = []

    def refresh_loaded(self, ctx: Ctx) -> None:  # pylint: disable=unused-argument
        """Keep the deterministic test runtime free of loaded policy objects."""
        self.loaded = []

    def list_loaded_names(self) -> list[str]:
        """Return the empty deterministic loaded-policy set."""
        return []

    def consider_and_maybe_fire(
        self,
        world: WorldGraph,
        drives: Drives,
        ctx: Ctx,
        tie_break: str = "first",
        exec_world: WorldGraph | None = None,
    ) -> str:
        """Return the configured result without mutating CCA8 state."""
        del world, drives, ctx, tie_break, exec_world
        return self.result


class _ImmediateStandEnvironment(HybridEnvironment):
    """Test environment whose stand command changes posture in one transition."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatched_actions: list[str | None] = []

    def apply_action(self, action: str | None, ctx: object):
        """Record the handoff and expose a visibly changed later observation."""
        self.dispatched_actions.append(action)
        _obs, reward, done, info = super().apply_action(action, ctx)
        if action == "policy:stand_up":
            self._state.kid_posture = "standing"  # pylint: disable=protected-access
        return self.observe(ctx=ctx), reward, done, info


def _ctx() -> Ctx:
    """Return a quiet context while retaining BodyMap and cognitive-scope state."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()
    ctx.env_loop_cycle_summary = False
    ctx.working_enabled = False
    ctx.wm_creative_enabled = False
    return ctx


def test_action_is_selected_and_dispatched_before_its_cognitive_cycle_closes(capsys) -> None:
    """Action_1 should cross the environment boundary during CognitiveCycle_1."""
    ctx = _ctx()
    env = _ImmediateStandEnvironment()
    runtime = _FixedPolicyRuntime("policy:stand_up")

    cca8_run.run_env_closed_loop_steps(env, WorldGraph(), Drives(), ctx, runtime, n_steps=1)
    capsys.readouterr()

    assert ctx.cog_cycles == 1
    assert env.dispatched_actions == ["policy:stand_up"]
    assert env.episode_steps == 1
    assert ctx.env_last_action == "policy:stand_up"
    assert ctx.env_pending_observation is not None
    assert ctx.env_pending_info["step_index"] == 1

    snapshot = ctx.cognitive_scope_trace_v1[-1]
    assert snapshot["cycle_input_environment_step"] == 0
    assert snapshot["cycle_output_action"] == "policy:stand_up"
    assert snapshot["action_dispatched"] == "policy:stand_up"
    assert snapshot["dispatch_succeeded"] is True
    assert snapshot["next_observation_environment_step"] == 1


def test_action_consequence_is_buffered_until_the_next_cognitive_cycle(capsys) -> None:
    """Observation_2 may exist physically after cycle 1 but enters cognition only in cycle 2."""
    ctx = _ctx()
    env = _ImmediateStandEnvironment()
    runtime = _FixedPolicyRuntime("policy:stand_up")
    world = WorldGraph()

    cca8_run.run_env_closed_loop_steps(env, world, Drives(), ctx, runtime, n_steps=1)
    capsys.readouterr()

    assert env.state.kid_posture == "standing"
    assert body_posture(ctx) == "fallen"
    pending = ctx.env_pending_observation
    assert pending is not None
    assert "posture:standing" in pending.predicates

    runtime.result = "no_match"
    cca8_run.run_env_closed_loop_steps(env, world, Drives(), ctx, runtime, n_steps=1)
    capsys.readouterr()

    assert body_posture(ctx) == "standing"
    assert env.dispatched_actions == ["policy:stand_up", None]
    snapshot = ctx.cognitive_scope_trace_v1[-1]
    assert snapshot["cycle_input_environment_step"] == 1
    assert snapshot["prior_action_for_input"] == "policy:stand_up"
    assert snapshot["cycle_output_action"] is None
    assert snapshot["dispatch_succeeded"] is True
    assert snapshot["next_observation_environment_step"] == 2


def test_no_policy_match_is_an_explicit_null_output_that_still_advances_the_world(capsys) -> None:
    """A null task command should complete the output phase rather than omit it."""
    ctx = _ctx()
    env = _ImmediateStandEnvironment()

    cca8_run.run_env_closed_loop_steps(
        env,
        WorldGraph(),
        Drives(),
        ctx,
        _FixedPolicyRuntime("no_match"),
        n_steps=1,
    )
    capsys.readouterr()

    assert env.dispatched_actions == [None]
    assert env.episode_steps == 1
    assert ctx.env_pending_observation is not None
    snapshot = ctx.cognitive_scope_trace_v1[-1]
    assert snapshot["cycle_output_action"] is None
    assert snapshot["action_dispatched"] is None
    assert snapshot["dispatch_succeeded"] is True
    dp15 = next(row for row in snapshot["ports"] if row["port_id"] == "DP15")
    assert dp15["signal"]["output_kind"] == "null_action"
    assert dp15["signal"]["pipeline_relation"] == "selected_and_dispatched_within_same_cognitive_cycle"
