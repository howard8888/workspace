# -*- coding: utf-8 -*-
"""Focused tests for the consolidated Superintelligence publication workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cca8_context import Ctx, ExperimentProtocolConfig
import cca8_experiments
from cca8_publication_analysis import exact_paired_binary_p_v1, wilson_interval_v1
from cca8_publication_integrity import (
    source_tree_manifest_v1,
    verify_checksums_v1,
    write_checksum_text_v1,
    write_json_exclusive_v1,
)
from cca8_publication_lhsi_sensitivity import DEFAULT_SPEC, compute_lhsi_v1, sensitivity_specs_v1
from cca8_publication_protocol import (
    CONDITIONS,
    FROZEN_PROTOCOL,
    PROFILES,
    PROTOCOL_VERSION,
    build_manifest_v1,
    protocol_metadata_v1,
    schedule_for_episode_v1,
    schedule_from_seed_v1,
    sha256_hex,
    validate_manifest_v1,
    write_manifest_exclusive_v1,
)
from cca8_publication_worker import _normalize_episode


def test_frozen_protocol_has_expected_scale_and_guardrails() -> None:
    assert (FROZEN_PROTOCOL.python_major, FROZEN_PROTOCOL.python_minor) == (3, 11)
    assert FROZEN_PROTOCOL.matched_seed_count == 100
    assert FROZEN_PROTOCOL.total_publication_episodes == 600
    assert PROFILES == ("baseline", "conflicted_repair")
    assert CONDITIONS == ("A", "B", "C")
    assert FROZEN_PROTOCOL.direct_retrieved_hint_enabled is False
    assert FROZEN_PROTOCOL.llm_or_external_api_enabled is False
    assert FROZEN_PROTOCOL.fresh_process_per_episode is True


def test_protocol_metadata_preserves_five_primary_hypotheses() -> None:
    metadata = protocol_metadata_v1()
    assert metadata["protocol_version"] == PROTOCOL_VERSION
    assert len(metadata["primary_hypotheses"]) == 5
    assert metadata["frozen_protocol"]["ordinary_observation_mask_probability"] == 0.5


def test_schedule_is_deterministic_and_condition_independent() -> None:
    first = schedule_for_episode_v1("focused-test-nonce", 7)
    second = schedule_for_episode_v1("focused-test-nonce", 7)
    assert first == second
    assert first["schedule_hash"] == sha256_hex(
        {key: value for key, value in first.items() if key != "schedule_hash"}
    )
    assert "condition" not in first


def test_external_schedule_reproduces_core_stochastic_streams() -> None:
    seed = 232111339
    episode_index = 1
    expected = schedule_from_seed_v1(seed, episode_index)
    ctx = Ctx()
    ctx.obs_mask_seed = seed
    ctx.experiment_episode_index = episode_index
    ctx.experiment_cfg = ExperimentProtocolConfig(
        obs_mask_prob=0.5,
        newborn_blackout_length=7,
        conflicted_repair_variant_mode="stochastic_v3",
        conflicted_repair_conflict_probability=0.5,
        conflicted_repair_encoding_opportunities=4,
        conflicted_repair_reacquire_probability=0.25,
        conflicted_repair_reacquire_start_delay=1,
    )
    actual = cca8_experiments._newborn_conflicted_repair_assignment_v1(ctx)  # pylint: disable=protected-access
    assert actual["conflict_draw"] == expected["route_change_draw"]
    assert actual["conflict_present"] == expected["route_changed"]
    assert actual["encoding_draws"] == expected["encoding_draws"]
    assert actual["memory_available"] == expected["memory_usable"]
    assert actual["reacquire_draws"] == expected["reacquisition_draws"]


def test_holdout_manifest_requires_exactly_100_matched_seeds() -> None:
    with pytest.raises(ValueError):
        build_manifest_v1(master_nonce="x", seed_count=99, manifest_kind="holdout")
    manifest = build_manifest_v1(master_nonce="x", seed_count=100, manifest_kind="holdout")
    assert validate_manifest_v1(manifest)["ok"] is True
    assert len({entry["episode_seed"] for entry in manifest["entries"]}) == 100


def test_manifest_validation_detects_schedule_tampering() -> None:
    manifest = build_manifest_v1(master_nonce="x", seed_count=3, manifest_kind="development")
    manifest["entries"][0]["route_changed"] = not manifest["entries"][0]["route_changed"]
    result = validate_manifest_v1(manifest)
    assert result["ok"] is False
    assert any(error.startswith("schedule_mismatch") for error in result["errors"])


def test_manifest_writer_refuses_overwrite(tmp_path: Path) -> None:
    manifest = build_manifest_v1(master_nonce="x", seed_count=1, manifest_kind="development")
    target = tmp_path / "manifest.json"
    write_manifest_exclusive_v1(target, manifest)
    with pytest.raises(FileExistsError):
        write_manifest_exclusive_v1(target, manifest)


def test_json_writer_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "record.json"
    write_json_exclusive_v1(target, {"ok": True})
    with pytest.raises(FileExistsError):
        write_json_exclusive_v1(target, {"ok": True})


def test_source_manifest_excludes_caches_and_its_own_manifest(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "publication_source_manifest.json").write_text("{}\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"ignored")
    manifest = source_tree_manifest_v1(tmp_path)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == ["module.py"]


def test_output_checksums_round_trip_and_detect_change(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    write_checksum_text_v1(tmp_path)
    assert verify_checksums_v1(tmp_path)["ok"] is True
    (tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")
    assert verify_checksums_v1(tmp_path)["ok"] is False


def test_worker_normalization_maps_core_fields_and_precompletion_details(tmp_path: Path) -> None:
    cycles = [
        {
            "cycle_index": 0,
            "workingmap_mask_invalidation": {
                "invalidated_family_count": 1,
                "families": ["mom:proximity:mom"],
            },
            "retrieval_event": {
                "ok": True,
                "step": 1,
                "reason": "test",
                "mode": "merge",
                "chosen_seed": {"engram_id": "abc"},
                "load": {
                    "mode": "merge",
                    "filled_slots": 1,
                    "added_entities": 0,
                    "added_edges": 1,
                    "filled_metadata": 0,
                    "repaired_families": ["mom:proximity:mom"],
                    "added_edge_targets": ["mom"],
                },
            },
        }
    ]
    schedule = schedule_from_seed_v1(123, 0)
    job = {"profile": "conflicted_repair", "condition": "A", "schedule": schedule}
    episode = {
        "condition": "A",
        "time_to_rested": 1.0,
        "newborn_retrieval_non_noop_count_to_completion": 1,
        "newborn_guarded_field_use_count_to_completion": 2,
        "newborn_guarded_field_use_events_to_completion": [],
        "newborn_retrieval_event_count_to_completion": 1,
        "newborn_retrieval_replace_count_to_completion": 0,
        "newborn_retrieved_hint_used_step_count": 0,
        "conflicted_repair_status": "passed",
        "conflicted_repair_probe_count": 1,
        "conflicted_repair_unsafe_follow_count": 0,
        "conflicted_repair_reacquired": False,
        "llm_call_count": 0,
    }
    normalized = _normalize_episode(episode, job=job, cycle_rows=cycles)
    assert normalized["publication_guarded_repair_count_pre_completion"] == 1
    assert normalized["publication_invalidation_count_pre_completion"] == 1
    assert normalized["publication_repaired_families_pre_completion"] == ["mom:proximity:mom"]
    assert normalized["publication_repaired_relations_pre_completion"] == ["self->mom:distance_to"]
    assert normalized["publication_resolution_count_pre_completion"] == 1


def test_exact_paired_binary_test_known_values() -> None:
    assert exact_paired_binary_p_v1(0, 0) == 1.0
    assert exact_paired_binary_p_v1(1, 0) == 1.0
    assert exact_paired_binary_p_v1(10, 0) == pytest.approx(2.0 / 1024.0)


def test_wilson_interval_is_bounded_and_contains_observed_proportion() -> None:
    low, high = wilson_interval_v1(74, 100)
    assert 0.0 <= low <= 0.74 <= high <= 1.0


def test_default_lhsi_reproduction_and_prespecified_sensitivity_family() -> None:
    row = {
        "milestone_score": 1.0,
        "lhsi_wrong_stage_action_count": 1,
        "lhsi_current_state_overwrite_proxy_count": 0,
        "lhsi_stale_memory_intrusion_proxy_count": 1,
        "lhsi_repeated_action_loop_count": 0,
        "lhsi_provenance_complete_cycle_rate": 0.80,
    }
    score, components = compute_lhsi_v1(row, DEFAULT_SPEC)
    assert score == pytest.approx(0.91)
    assert components["total_penalty"] == pytest.approx(0.09)
    specs = sensitivity_specs_v1()
    assert len(specs) >= 15
    assert len({spec.name for spec in specs}) == len(specs)
