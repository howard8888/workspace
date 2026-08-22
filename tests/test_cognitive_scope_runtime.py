"""Focused tests for Main Menu #3 cognitive storage oscilloscope phase 1."""

from __future__ import annotations

import json

import cca8_cli
import cca8_cognitive_scope
import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import HybridEnvironment
from cca8_world_graph import WorldGraph


class _PolicyRuntimeStub:
    """Minimal no-policy runtime for deterministic scope-capture tests."""

    def __init__(self) -> None:
        self.loaded: list[object] = []

    def refresh_loaded(self, ctx: Ctx) -> None:  # pylint: disable=unused-argument
        """Keep the loaded policy set empty."""
        self.loaded = []

    def list_loaded_names(self) -> list[str]:
        """Return the empty deterministic policy-name set."""
        return []

    def consider_and_maybe_fire(
        self,
        world: WorldGraph,
        drives: Drives,
        ctx: Ctx,
        tie_break: str = "first",
        exec_world: WorldGraph | None = None,
    ) -> str:
        """Return no match without changing the tested architecture."""
        del world, drives, ctx, tie_break, exec_world
        return "no_match"


def _capture_once(ctx: Ctx, *, env: HybridEnvironment | None = None) -> dict[str, object]:
    """Capture one direct scope snapshot with a real environment observation."""
    active_env = env or HybridEnvironment()
    obs, info = active_env.reset()
    return cca8_cognitive_scope.capture_cognitive_scope_snapshot_v1(
        ctx,
        env=active_env,
        env_obs=obs,
        world=WorldGraph(),
        drives=Drives(),
        policy_rt=_PolicyRuntimeStub(),
        selected_policy=None,
        action_applied=None,
        env_step=info.get("step_index"),
    )


def test_port_registry_has_external_reference_plus_eighteen_service_points() -> None:
    """The v03 schematic should map DP00 plus DP01-DP18 exactly once."""
    ports = cca8_cognitive_scope.COGNITIVE_SCOPE_PORTS_V1

    assert len(ports) == 19
    assert [port.port_id for port in ports] == [f"DP{index:02d}" for index in range(19)]
    assert ports[0].name == "External World / Body"
    assert ports[-1].name == "Learning / Revision / Memory Writeback"


def test_capture_is_json_safe_bounded_and_honest_about_collapsed_stages() -> None:
    """One capture should retain a JSON-safe circuit snapshot without inventing modules."""
    ctx = Ctx()
    snapshot = _capture_once(ctx)

    assert snapshot["schema"] == "cognitive_scope_snapshot_v1"
    assert snapshot["external_reference_port_count"] == 1
    assert snapshot["cognitive_service_point_count"] == 18
    assert snapshot["port_count"] == 19
    assert len(snapshot["ports"]) == 19
    assert len(ctx.cognitive_scope_trace_v1) == 1
    assert ctx.cognitive_scope_last_capture_v1 is snapshot

    by_id = {row["port_id"]: row for row in snapshot["ports"]}
    assert by_id["DP00"]["signal_status"] == "active"
    assert by_id["DP01"]["signal_status"] == "active"
    assert by_id["DP02"]["implementation"] == "collapsed"
    assert "no fabricated intermediate value" in by_id["DP02"]["note"]
    assert by_id["DP11"]["authority"] == "accepted_current"
    assert snapshot["sampling_model"] == "end_of_cycle_stable_register_snapshot_v1"
    assert snapshot["port_samples_are_exact_stage_timestamps"] is False
    assert snapshot["trace_is_cognitive_memory"] is False
    assert snapshot["measurement_only"] is True
    assert snapshot["injection_enabled"] is False

    json.dumps(snapshot, allow_nan=False)


def test_trace_uses_monotonic_numbers_and_drops_only_oldest_rows() -> None:
    """The storage scope should retain only its configured finite number of cycles."""
    ctx = Ctx()
    ctx.cognitive_scope_capacity_v1 = 2
    env = HybridEnvironment()

    first = _capture_once(ctx, env=env)
    second = _capture_once(ctx, env=env)
    third = _capture_once(ctx, env=env)

    assert first["snapshot_no"] == 1
    assert second["snapshot_no"] == 2
    assert third["snapshot_no"] == 3
    assert [row["snapshot_no"] for row in ctx.cognitive_scope_trace_v1] == [2, 3]
    summary = cca8_cognitive_scope.cognitive_scope_trace_summary_v1(ctx)
    assert summary["retained_count"] == 2
    assert summary["total_capture_count"] == 3
    assert summary["oldest_snapshot_no"] == 2
    assert summary["latest_snapshot_no"] == 3

    assert cca8_cognitive_scope.cognitive_scope_clear_v1(ctx) == 2
    assert ctx.cognitive_scope_trace_v1 == []
    assert ctx.cognitive_scope_snapshot_no_v1 == 3


def test_closed_loop_records_one_scope_snapshot_per_cognitive_cycle(
    capsys,
) -> None:
    """Menu 35/37's shared loop should feed every completed cycle into the scope."""
    ctx = Ctx()
    ctx.env_loop_cycle_summary = False
    ctx.working_enabled = False
    ctx.wm_creative_enabled = False

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        WorldGraph(),
        Drives(),
        ctx,
        _PolicyRuntimeStub(),
        n_steps=3,
    )
    capsys.readouterr()

    assert ctx.cog_cycles == 3
    assert len(ctx.cognitive_scope_trace_v1) == 3
    assert [row["cognitive_cycle"] for row in ctx.cognitive_scope_trace_v1] == [1, 2, 3]
    assert all(row["capture_kind"] == "cognitive_cycle" for row in ctx.cognitive_scope_trace_v1)
    assert all(len(row["ports"]) == 19 for row in ctx.cognitive_scope_trace_v1)


def test_scope_renderers_and_main_menu_expose_the_new_instrument() -> None:
    """The terminal UI should expose readable snapshot and history displays."""
    ctx = Ctx()
    snapshot = _capture_once(ctx)

    rendered = "\n".join(cca8_cognitive_scope.render_cognitive_scope_snapshot_lines_v1(snapshot))
    history = "\n".join(cca8_cognitive_scope.render_cognitive_scope_trace_index_lines_v1(ctx))

    assert "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- SNAPSHOT" in rendered
    assert "DP00  External World / Body" in rendered
    assert "DP18  Learning / Revision / Memory Writeback" in rendered
    assert "DP01-DP18 are the eighteen cognitive/architectural service points" in rendered
    assert "latest stable register at cycle end" in rendered
    assert "RETAINED SNAPSHOTS" in history
    assert "snapshot=1 cycle=0" in history
    assert "Cognitive Storage Oscilloscope / System Inspector" in cca8_cli.MAIN_MENU_PROMPT
    assert cca8_cli.route_menu_alias("oscilloscope")[0] == "3"
    assert dict(cca8_run._CCA8_COMPONENT_REGISTRY)["cognitive_scope"] == "cca8_cognitive_scope"


def test_lower_motor_port_distinguishes_current_selection_from_prior_applied_action() -> None:
    """DP15 must not mislabel the normal one-cycle action pipeline as a handoff fault."""
    ctx = Ctx()
    env = HybridEnvironment()
    env.reset()
    env.step("policy:stand_up", ctx)

    snapshot = cca8_cognitive_scope.build_cognitive_scope_snapshot_v1(
        ctx,
        env=env,
        env_obs=None,
        world=WorldGraph(),
        drives=Drives(),
        policy_rt=_PolicyRuntimeStub(),
        selected_policy="policy:recover_fall",
        action_applied="policy:stand_up",
        env_step=1,
    )

    by_id = {row["port_id"]: row for row in snapshot["ports"]}
    signal = by_id["DP15"]["signal"]
    assert signal["selected_task_action"] == "policy:recover_fall"
    assert signal["action_applied_this_environment_step"] == "policy:stand_up"
    assert signal["pipeline_relation"] == "selected_current_cycle_is_applied_on_next_environment_step"
    assert signal["handoff_ack_mismatch"] is False
