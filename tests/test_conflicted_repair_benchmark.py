from __future__ import annotations

import json
from pathlib import Path

import cca8_column
import cca8_controller
import cca8_run
import cca8_experiments
import pytest
from cca8_context import Ctx


@pytest.fixture(autouse=True)
def _isolate_conflicted_repair_global_state():
    """Keep publication benchmark tests from contaminating unrelated tests."""
    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()
    yield
    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()


def _run_conflicted_repair(
    tmp_path: Path,
    condition: str,
    seed: int = 955014,
    episode_index: int = 0,
    variant_mode: str = "balanced_2x2",
) -> tuple[dict, list[dict]]:
    """Run one isolated diagnostic episode and return its summary and cycles."""
    cca8_column.mem._store.clear()  # pylint: disable=protected-access
    cca8_controller.reset_skills()

    ctx = Ctx()
    cfg = ctx.experiment_cfg
    cfg.benchmark_id = "newborn_long_horizon"
    cfg.output_dir = str(tmp_path / condition)
    cfg.run_label = "conflicted_repair_test"
    cfg.newborn_stress_profile = "conflicted_repair"
    cfg.newborn_blackout_length = 7
    cfg.conflicted_repair_variant_mode = variant_mode
    cfg.conflicted_repair_conflict_probability = 0.50
    cfg.conflicted_repair_encoding_opportunities = 4
    cfg.conflicted_repair_reacquire_probability = 0.25
    cfg.conflicted_repair_reacquire_start_delay = 1
    cfg.obs_mask_prob = 0.50
    cfg.max_cycles = 60
    cfg.condition_ids = [condition]
    cfg.seed_list = [seed]

    result = cca8_run.experiment_run_one_episode_v1(
        ctx,
        condition_id=condition,
        seed=seed,
        episode_index=episode_index,
        suppress_output=True,
    )
    assert result.get("ok") is True
    cycles = [json.loads(line) for line in Path(result["cycle_json_path"]).read_text().splitlines()]
    return result["episode_record"], cycles


def _cycle_with_selected_policy(cycles: list[dict], policy: str) -> dict:
    for row in cycles:
        if row.get("selected_policy") == policy:
            return row
    raise AssertionError(f"policy never selected: {policy}")


def test_conflicted_repair_guarded_condition_repairs_and_passes(tmp_path: Path) -> None:
    episode, cycles = _run_conflicted_repair(tmp_path, "A")

    assert episode["success"] is True
    assert episode["conflicted_repair_status"] == "passed"
    assert episode["conflicted_repair_probe_count"] == 1
    assert episode["conflicted_repair_unsafe_follow_count"] == 0
    assert episode["newborn_retrieval_non_noop_count_to_completion"] >= 1
    assert episode["newborn_repair_filled_slot_total_to_completion"] >= 1
    assert episode["newborn_guarded_field_use_count_to_completion"] >= 1
    assert episode["newborn_retrieved_hint_set_count"] == 0

    probe_cycle = _cycle_with_selected_policy(cycles, "policy:probe")
    probe_state = probe_cycle["workingmap_governed_state"]
    assert probe_state["mom_distance"] == "far"
    assert probe_state["source_by_field"]["mom_distance"] == "retrieved_guarded"
    assert probe_state["route_state"] == "blocked"
    assert probe_state["source_by_field"]["route_state"] == "current_observation"
    assert "mom:proximity:mom" in probe_cycle["workingmap_mask_invalidation"]["families"]

    follow_cycle = _cycle_with_selected_policy(cycles, "policy:follow_mom")
    follow_state = follow_cycle["workingmap_governed_state"]
    assert follow_state["mom_distance"] == "far"
    assert follow_state["route_state"] == "clear"


def test_conflicted_repair_disabled_condition_times_out_with_missing_state(tmp_path: Path) -> None:
    episode, cycles = _run_conflicted_repair(tmp_path, "B")

    assert episode["success"] is False
    assert episode["conflicted_repair_status"] == "failed"
    assert episode["conflicted_repair_failure_reason"] == "missing_state_timeout"
    assert episode["conflicted_repair_probe_count"] == 1
    assert episode["newborn_retrieval_event_count_to_completion"] == 0
    assert episode["newborn_guarded_field_use_count_to_completion"] == 0
    assert not any(row.get("selected_policy") == "policy:follow_mom" for row in cycles)

    post_probe_rows = [
        row for row in cycles
        if row.get("cycle_index", -1) >= int(episode["conflicted_repair_probe_step"] or -1)
        and row.get("stage") == "first_stand"
    ]
    assert post_probe_rows
    assert all(row["workingmap_governed_state"]["mom_distance"] is None for row in post_probe_rows)


def test_conflicted_repair_replacement_condition_imports_stale_route_and_fails(tmp_path: Path) -> None:
    episode, cycles = _run_conflicted_repair(tmp_path, "C")

    assert episode["success"] is False
    assert episode["conflicted_repair_status"] == "failed"
    assert episode["conflicted_repair_failure_reason"] == "unsafe_follow_before_probe"
    assert episode["conflicted_repair_probe_count"] == 0
    assert episode["conflicted_repair_unsafe_follow_count"] == 1

    follow_cycle = _cycle_with_selected_policy(cycles, "policy:follow_mom")
    state = follow_cycle["workingmap_governed_state"]
    assert state["mom_distance"] == "far"
    assert state["route_state"] == "clear"
    retrieval = follow_cycle.get("retrieval_event") or {}
    assert (retrieval.get("load") or {}).get("mode") == "replace"


def test_disabled_condition_can_recover_from_current_reobservation(tmp_path: Path) -> None:
    # Cell 1: route conflict is present, but current mother-distance evidence
    # reappears before the deadline. Condition B should probe and then succeed
    # without episodic readback.
    episode, cycles = _run_conflicted_repair(tmp_path, "B", episode_index=1)

    assert episode["conflicted_repair_variant"] == "conflict_reacquire"
    assert episode["conflicted_repair_reacquisition_available"] is True
    assert episode["success"] is True
    assert episode["conflicted_repair_status"] == "passed"
    assert episode["conflicted_repair_probe_count"] == 1
    assert episode["newborn_retrieval_event_count_to_completion"] == 0
    assert any(row.get("selected_policy") == "policy:follow_mom" for row in cycles)


def test_replacement_condition_can_succeed_when_memory_is_not_stale(tmp_path: Path) -> None:
    # Cell 2: mother distance remains missing, but the current route remains
    # clear. Replacement restores a useful state without importing a conflict.
    episode, cycles = _run_conflicted_repair(tmp_path, "C", episode_index=2)

    assert episode["conflicted_repair_variant"] == "no_conflict_persistent"
    assert episode["conflicted_repair_conflict_present"] is False
    assert episode["success"] is True
    assert episode["conflicted_repair_status"] == "passed"
    assert episode["conflicted_repair_unsafe_follow_count"] == 0
    follow_cycle = _cycle_with_selected_policy(cycles, "policy:follow_mom")
    state = follow_cycle["workingmap_governed_state"]
    assert state["mom_distance"] == "far"
    assert state["route_state"] == "clear"


def test_factorial_assignment_is_matched_and_balanced_by_episode_index(tmp_path: Path) -> None:
    expected = {
        0: "conflict_persistent",
        1: "conflict_reacquire",
        2: "no_conflict_persistent",
        3: "no_conflict_reacquire",
    }
    for episode_index, variant in expected.items():
        rows = [
            _run_conflicted_repair(tmp_path, condition, episode_index=episode_index)[0]
            for condition in ("A", "B", "C")
        ]
        assert {row["conflicted_repair_variant"] for row in rows} == {variant}


def test_stochastic_schedule_is_reproducible_and_matched_across_conditions(
    tmp_path: Path,
) -> None:
    rows = [
        _run_conflicted_repair(
            tmp_path,
            condition,
            seed=540916,
            episode_index=7,
            variant_mode="stochastic_v3",
        )[0]
        for condition in ("A", "B", "C")
    ]

    matched_fields = (
        "conflicted_repair_schedule_mode",
        "conflicted_repair_variant",
        "conflicted_repair_conflict_present",
        "conflicted_repair_conflict_draw",
        "conflicted_repair_memory_available",
        "conflicted_repair_encoding_opportunities",
        "conflicted_repair_encoding_successes",
        "conflicted_repair_encoding_draws",
        "conflicted_repair_reacquire_offsets",
        "conflicted_repair_reacquire_draws",
    )
    for field in matched_fields:
        assert len({json.dumps(row[field], sort_keys=True) for row in rows}) == 1

    assert rows[0]["conflicted_repair_schedule_mode"] == "stochastic_v3"
    assert rows[0]["conflicted_repair_encoding_opportunities"] == 4
    assert len(rows[0]["conflicted_repair_encoding_draws"]) == 4
    assert len(rows[0]["conflicted_repair_reacquire_draws"]) == 6


def test_stochastic_schedule_varies_across_matched_seeds() -> None:
    schedules: list[tuple[bool, bool, tuple[int, ...]]] = []
    for seed in range(101, 141):
        ctx = Ctx()
        cfg = ctx.experiment_cfg
        cfg.newborn_blackout_length = 7
        cfg.obs_mask_prob = 0.50
        cfg.conflicted_repair_variant_mode = "stochastic_v3"
        cfg.conflicted_repair_conflict_probability = 0.50
        cfg.conflicted_repair_encoding_opportunities = 4
        cfg.conflicted_repair_reacquire_probability = 0.25
        cfg.conflicted_repair_reacquire_start_delay = 1
        ctx.obs_mask_seed = seed
        ctx.experiment_episode_index = seed - 101
        assignment = cca8_experiments._newborn_conflicted_repair_assignment_v1(ctx)  # pylint: disable=protected-access
        schedules.append(
            (
                bool(assignment["conflict_present"]),
                bool(assignment["memory_available"]),
                tuple(int(value) for value in assignment["reacquire_offsets"]),
            )
        )

    assert {conflict for conflict, _, _ in schedules} == {False, True}
    assert {memory for _, memory, _ in schedules} == {False, True}
    assert any(offsets for _, _, offsets in schedules)
    assert any(not offsets for _, _, offsets in schedules)
    assert len(set(schedules)) >= 6
