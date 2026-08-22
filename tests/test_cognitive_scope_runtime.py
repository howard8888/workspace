"""Focused tests for Main Menu #3 cognitive storage oscilloscope phase 1."""

from __future__ import annotations

import json

import cca8_cli
import cca8_cognitive_scope
import cca8_controller
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
    """The terminal UI should expose compact, raw, drill-down, and history views."""
    ctx = Ctx()
    snapshot = _capture_once(ctx)

    compact = "\n".join(cca8_cognitive_scope.render_cognitive_scope_compact_snapshot_lines_v1(snapshot))
    raw = "\n".join(cca8_cognitive_scope.render_cognitive_scope_snapshot_lines_v1(snapshot))
    detail = "\n".join(cca8_cognitive_scope.render_cognitive_scope_port_detail_lines_v1(snapshot, "DP13"))
    history = "\n".join(cca8_cognitive_scope.render_cognitive_scope_trace_index_lines_v1(ctx))

    assert "COMPACT SIGNAL PATH" in compact
    assert "DP00 WORLD" in compact
    assert "DP18 LEARNING" in compact
    assert "full stored signal is available by DP drill-down" in compact
    assert "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- SNAPSHOT" in raw
    assert "DP00  External World / Body" in raw
    assert "DP18  Learning / Revision / Memory Writeback" in raw
    assert "DIAGNOSTIC-POINT DETAIL" in detail
    assert "DP13  Policy / Primitive Selection + Arbitration" in detail
    assert "DP12  Drives" not in detail
    assert "RETAINED SNAPSHOTS" in history
    assert "snapshot=1 cycle=0" in history
    assert "Cognitive Storage Oscilloscope / System Inspector" in cca8_cli.MAIN_MENU_PROMPT
    assert cca8_cli.route_menu_alias("oscilloscope")[0] == "3"
    assert dict(cca8_run._CCA8_COMPONENT_REGISTRY)["cognitive_scope"] == "cca8_cognitive_scope"


def test_compact_front_panel_summarizes_large_ports_without_dumping_nested_payloads() -> None:
    """The default scope view should remain readable while preserving raw drill-down data."""
    ctx = Ctx()
    snapshot = _capture_once(ctx)
    by_id = {row["port_id"]: row for row in snapshot["ports"]}

    by_id["DP05"]["signal_status"] = "active"
    by_id["DP05"]["signal"] = {
        "event_history_count": 4,
        "maternal_temporal": {"trend": "stable"},
        "live_dynamics_state": {
            "materiality": {"material_change_recommended": False},
            "overlays": {
                "self_maternal": {"distance_trend": "stable"},
                "self_route": {"motion_direction": "west"},
                "lower_motor": {"phase_detail": "interrupted"},
            },
        },
    }
    by_id["DP08"]["signal_status"] = "active"
    by_id["DP08"]["signal"] = {
        "candidate_count": 6,
        "candidate_refs": [{"large": "payload"}],
        "winner_ref": {"map_id": "goat_self_maternal_v2", "revision": 1},
        "retrieval_status": "authority_rejected",
        "full_payload_scan": False,
    }
    by_id["DP09"]["signal_status"] = "active"
    by_id["DP09"]["signal"] = {
        "engram_count": 13,
        "reinstatement_count": 3,
        "reinstatements": [
            {"status": "reinstated_but_conflicts_with_current_evidence"},
            {"status": "reinstated_but_conflicts_with_current_evidence"},
            {"status": "reinstated", "reason": "exact_structural_match", "match_result": {"status": "exact"}},
        ],
        "last_consolidation": {"consolidated": True},
    }
    by_id["DP13"]["signal_status"] = "active"
    by_id["DP13"]["signal"] = {
        "triggered": ["policy:stand_up", "policy:recover_fall"],
        "chosen": "policy:stand_up",
        "selection_reason": "rl_exploit(non_drive_tiebreak)",
        "protected_safety_filter": True,
        "authority_source": "protected_bodymap_safety",
    }
    by_id["DP17"]["signal_status"] = "active"
    by_id["DP17"]["signal"] = {
        "prediction_error": {
            "matched": False,
            "severity": 1.0,
            "error_by_slot": {"posture": 1},
            "prediction": {"policy": "policy:stand_up", "expected": {"posture": "standing"}},
            "observed": {"posture": "fallen"},
        }
    }

    compact_lines = cca8_cognitive_scope.render_cognitive_scope_compact_snapshot_lines_v1(snapshot)
    compact = "\n".join(compact_lines)

    assert sum(line.startswith("DP") for line in compact_lines) == 19
    assert "DP05 TEMPORAL" in compact
    assert "maternal=stable | route=west | motor=interrupted" in compact
    assert "DP08 MEMORY IDX" in compact
    assert "candidates=6 | winner=goat_self_maternal_v2@r1" in compact
    assert "DP09 COLUMNS" in compact
    assert "reinstated=3 | exact=1 | conflicts=2" in compact
    assert "DP13 POLICY" in compact
    assert "chosen=stand_up | reason=non_drive_tiebreak" in compact
    assert "DP17 OUTCOME" in compact
    assert "posture=standing->fallen" in compact
    assert "candidate_refs" not in compact
    assert "reinstatements" not in compact

    detail = "\n".join(cca8_cognitive_scope.render_cognitive_scope_port_detail_lines_v1(snapshot, "9"))
    assert "DP09  Columns / Rich NavMap Reinstatement" in detail
    assert '"reinstatements"' in detail
    assert "DP08  Sparse Memory Activation" not in detail


def test_port_normalization_and_lookup_accept_human_friendly_identifiers() -> None:
    """The drill-down prompt should accept DP13, dp13, and 13 equivalently."""
    snapshot = _capture_once(Ctx())

    assert cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1("DP13") == "DP13"
    assert cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1("dp13") == "DP13"
    assert cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1("13") == "DP13"
    assert cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1("19") is None
    assert cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1("policy") is None
    assert cca8_cognitive_scope.cognitive_scope_find_port_v1(snapshot, "13")["port_id"] == "DP13"


def test_scope_menu_defaults_to_compact_view_and_supports_dp_drilldown(monkeypatch, capsys) -> None:
    """Main Menu #3 should show the front panel first and open only the requested port."""
    ctx = Ctx()
    _capture_once(ctx)
    answers = iter(["1", "DP13", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    cca8_run._cognitive_scope_menu_v1(
        HybridEnvironment(),
        WorldGraph(),
        Drives(),
        ctx,
        _PolicyRuntimeStub(),
    )
    output = capsys.readouterr().out

    assert "SYSTEM INSPECTOR -- PHASE 1B" in output
    assert "COMPACT SIGNAL PATH" in output
    assert "DP00 WORLD" in output
    assert "DIAGNOSTIC-POINT DETAIL" in output
    assert "DP13  Policy / Primitive Selection + Arbitration" in output
    assert "DP12  Drives / Goal / Emotion / Development" not in output


def test_dp13_exposes_arbitration_reason_scores_and_trigger_authority() -> None:
    """DP13 should show why a primitive won and which trigger authority supplied it."""
    ctx = Ctx()
    ctx.ac_triggered_policies = ["policy:stand_up", "policy:recover_fall"]
    ctx.experiment_policy_debug_last = {
        "matches_initial": ["policy:stand_up", "policy:recover_fall"],
        "matches_after_safety": ["policy:stand_up", "policy:recover_fall"],
        "matches_before_choice": ["policy:stand_up", "policy:recover_fall"],
        "chosen": "policy:stand_up",
        "selector_kind": "rl_exploit(non_drive_tiebreak)",
        "selection_reason": "rl_exploit(non_drive_tiebreak)",
        "tie_break_label": None,
        "score_rows": [
            {"policy": "policy:stand_up", "deficit": 0.0, "non_drive": 2.0, "q": 0.52},
            {"policy": "policy:recover_fall", "deficit": 0.0, "non_drive": 0.0, "q": 0.24},
        ],
        "winner_scores": {"policy": "policy:stand_up", "deficit": 0.0, "non_drive": 2.0, "q": 0.52},
        "fallen_safety_filter": True,
        "legacy_fallen_safety_filter": True,
        "guarded_map_fallen_safety_filter": False,
        "selected_trigger_authority_source": "protected_bodymap_safety",
        "selected_trigger_authority_reason": "fresh_bodymap_fallen_protected_safety",
    }

    snapshot = cca8_cognitive_scope.build_cognitive_scope_snapshot_v1(
        ctx,
        env=HybridEnvironment(),
        env_obs=None,
        world=WorldGraph(),
        drives=Drives(),
        policy_rt=_PolicyRuntimeStub(),
        selected_policy="policy:stand_up",
        action_applied=None,
        env_step=None,
    )

    by_id = {row["port_id"]: row for row in snapshot["ports"]}
    signal = by_id["DP13"]["signal"]
    assert signal["chosen"] == "policy:stand_up"
    assert signal["selector_kind"] == "rl_exploit(non_drive_tiebreak)"
    assert signal["selection_reason"] == "rl_exploit(non_drive_tiebreak)"
    assert signal["winner_scores"]["non_drive"] == 2.0
    assert signal["protected_safety_filter"] is True
    assert signal["authority_source"] == "protected_bodymap_safety"
    assert signal["authority_reason"] == "fresh_bodymap_fallen_protected_safety"


def test_dp18_and_compact_view_separate_executions_from_learning_updates() -> None:
    """The cognitive DSO should expose the skill-ledger count split without changing q learning."""
    cca8_controller.reset_skills()
    try:
        for _ in range(4):
            cca8_controller.update_skill("policy:stand_up", 1.0, ok=True)
        cca8_controller.update_skill("policy:stand_up", -0.15, ok=False, execution=False)

        ctx = Ctx()
        ctx.navmap_last_policy_outcome_v1 = {"action": "policy:stand_up"}
        snapshot = cca8_cognitive_scope.build_cognitive_scope_snapshot_v1(
            ctx,
            env=HybridEnvironment(),
            env_obs=None,
            world=WorldGraph(),
            drives=Drives(),
            policy_rt=_PolicyRuntimeStub(),
            selected_policy="policy:stand_up",
            action_applied="policy:stand_up",
            env_step=4,
        )

        by_id = {row["port_id"]: row for row in snapshot["ports"]}
        stand_up = by_id["DP18"]["signal"]["skill_stats"]["policy:stand_up"]
        assert stand_up["execution_count"] == 4
        assert stand_up["learning_update_count"] == 5
        assert stand_up["success_count"] == 4

        compact = "\n".join(cca8_cognitive_scope.render_cognitive_scope_compact_snapshot_lines_v1(snapshot))
        assert "DP18 LEARNING" in compact
        assert "last=stand_up exec=4 updates=5" in compact
    finally:
        cca8_controller.reset_skills()


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
