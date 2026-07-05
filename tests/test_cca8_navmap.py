# -*- coding: utf-8 -*-
"""Tests for CCA8 NavMap payload helpers."""

from __future__ import annotations

import json

from cca8_navmap import (
    NAVMAP_PAYLOAD_SCHEMA_V1,
    NavMapPayloadV1,
    match_navmap_payloads_v1,
    make_navmap_payload_v1,
    navmap_residual_v1,
    navmap_payload_slots_v1,
    navmap_learning_proposal_from_match_v1,
)


def test_navmap_payload_creates_valid_json_safe_payload() -> None:
    """The first NavMap payload should be a small JSON-safe scene/body map."""
    payload = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        confidence=0.75,
        source="unit_test",
        basis={
            "env_step": 5,
            "policy": "policy:seek_nipple",
            "tags": ["posture:standing", "nipple:found"],
            "nested": {"ok": True},
        },
    )

    data = payload.as_dict()

    assert data["schema"] == NAVMAP_PAYLOAD_SCHEMA_V1
    assert data["map_kind"] == "local_navmap"
    assert data["modality"] == "scene_body"
    assert data["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
        "zone": "safe",
    }
    assert data["confidence"] == 0.75
    assert data["source"] == "unit_test"
    assert data["basis"]["env_step"] == 5
    assert isinstance(data["created_at"], str) and data["created_at"]
    json.dumps(data)


def test_navmap_payload_normalizes_slot_keys_values_and_headers() -> None:
    """Slot keys, slot values, map kind, and modality should become stable tokens."""
    payload = make_navmap_payload_v1(
        {
            " Posture ": " Standing ",
            "Mom Distance": " Near Mom ",
            "NIPPLE_STATE": " Found ",
            "Zone": " Safe ",
        },
        map_kind=" Local NavMap ",
        modality=" Scene Body ",
    )

    assert payload.as_dict()["map_kind"] == "local_navmap"
    assert payload.as_dict()["modality"] == "scene_body"
    assert payload.as_dict()["slots"] == {
        "posture": "standing",
        "mom_distance": "near_mom",
        "nipple_state": "found",
        "zone": "safe",
    }


def test_navmap_payload_handles_malformed_slot_input_safely() -> None:
    """Malformed slot input should not crash or create odd nested slot values."""
    empty_payload = make_navmap_payload_v1("not-a-dict")  # type: ignore[arg-type]
    mixed_payload = make_navmap_payload_v1(
        {
            "": "empty_key",
            "zone": None,
            "nested": {"bad": "value"},
            "list_value": ["bad"],
            3: "bad_key",
            "step": 12,
        }  # type: ignore[dict-item]
    )

    assert empty_payload.as_dict()["slots"] == {}
    assert mixed_payload.as_dict()["slots"] == {"step": "12"}


def test_navmap_payload_preserves_source_basis_and_confidence() -> None:
    """Provenance fields should survive normalization without changing the slot map."""
    payload = make_navmap_payload_v1(
        {"posture": "standing"},
        confidence="0.42",  # type: ignore[arg-type]
        source="WorkingMap.Scratch",
        basis={
            "binding_id": "b12",
            "policy": "policy:stand_up",
            "steps": (1, 2, 3),
            "nested": {"source": "unit_test"},
        },
    )

    data = payload.as_dict()

    assert data["confidence"] == 0.42
    assert data["source"] == "WorkingMap.Scratch"
    assert data["basis"] == {
        "binding_id": "b12",
        "policy": "policy:stand_up",
        "steps": [1, 2, 3],
        "nested": {"source": "unit_test"},
    }


def test_navmap_payload_does_not_mutate_caller_provided_dicts() -> None:
    """Payload construction and slot extraction should copy caller-owned mappings."""
    slots = {" Posture ": " Standing "}
    basis = {"nested": {"step": 1}, "tags": ["raw"]}

    payload = make_navmap_payload_v1(slots, basis=basis)
    data = payload.as_dict()
    extracted = navmap_payload_slots_v1(payload)

    data["slots"]["posture"] = "fallen"
    extracted["posture"] = "fallen"
    payload.basis["nested"]["step"] = 2

    assert slots == {" Posture ": " Standing "}
    assert basis == {"nested": {"step": 1}, "tags": ["raw"]}
    assert payload.as_dict()["slots"] == {"posture": "standing"}


def test_navmap_payload_from_dict_round_trips_payload_like_dicts() -> None:
    """The dataclass constructor should tolerate dict payloads from traces."""
    original = make_navmap_payload_v1(
        {"posture": "standing", "zone": "safe"},
        confidence=0.9,
        source="fixture",
        basis={"case": "round_trip"},
    ).as_dict()

    restored = NavMapPayloadV1.from_dict(original)

    assert restored.as_dict()["schema"] == NAVMAP_PAYLOAD_SCHEMA_V1
    assert restored.as_dict()["slots"] == {"posture": "standing", "zone": "safe"}
    assert restored.as_dict()["confidence"] == 0.9
    assert restored.as_dict()["source"] == "fixture"
    assert restored.as_dict()["basis"] == {"case": "round_trip"}
    assert navmap_payload_slots_v1(restored.as_dict()) == {"posture": "standing", "zone": "safe"}


def test_navmap_residual_reports_matched_mismatched_missing_and_novel_slots() -> None:
    """Residuals should expose the slot differences left over after map matching."""
    current = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "found",
            "zone": "safe",
        }
    )
    candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "terrain": "flat",
        }
    )

    residual = navmap_residual_v1(current, candidate)
    data = residual.as_dict()

    assert data["schema"] == "navmap_residual_v1"
    assert data["matched_slots"] == {"nipple_state": "found", "posture": "standing"}
    assert data["mismatched_slots"] == {"mom_distance": {"current": "far", "candidate": "near"}}
    assert data["missing_slots"] == {"terrain": "flat"}
    assert data["novel_slots"] == {"zone": "safe"}
    assert data["score"] == 0.4
    assert data["current_coverage"] == 0.5
    assert data["candidate_coverage"] == 0.5
    assert data["residual_count"] == 3
    assert data["exact_match"] is False


def test_match_navmap_payloads_selects_best_candidate_by_slot_overlap() -> None:
    """The matcher should choose the closest stored/active map candidate."""
    current = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        basis={"case": "current_scene"},
    )
    field_candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "far",
            "zone": "unsafe",
        },
        basis={"label": "field_without_mom"},
    )
    mom_candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        basis={"label": "mom_near"},
    )

    match = match_navmap_payloads_v1(current, [field_candidate, mom_candidate])
    data = match.as_dict()

    assert data["schema"] == "navmap_match_v1"
    assert data["candidate_index"] == 1
    assert data["matched"] is True
    assert data["reason"] == "matched"
    assert data["score"] == 1.0
    assert data["candidate"]["basis"] == {"label": "mom_near"}
    assert data["residual"]["exact_match"] is True
    assert data["residual"]["residual_count"] == 0


def test_match_navmap_payloads_respects_threshold_and_handles_no_candidates() -> None:
    """Low scoring or absent candidates should not become accepted matches."""
    current = make_navmap_payload_v1({"posture": "standing", "mom_distance": "near"})
    weak_candidate = make_navmap_payload_v1({"posture": "standing", "mom_distance": "far"})

    weak_match = match_navmap_payloads_v1(current, [weak_candidate], min_score=0.75)
    empty_match = match_navmap_payloads_v1(current, [])

    assert weak_match.as_dict()["matched"] is False
    assert weak_match.as_dict()["reason"] == "below_threshold"
    assert weak_match.as_dict()["score"] == 0.5
    assert empty_match.as_dict()["matched"] is False
    assert empty_match.as_dict()["reason"] == "no_candidates"
    assert empty_match.as_dict()["candidate"] == {}
    assert empty_match.as_dict()["residual"]["novel_slots"] == {
        "mom_distance": "near",
        "posture": "standing",
    }


def test_match_navmap_payloads_filters_modalities_by_default() -> None:
    """A scene_body current map should not directly match a visual-only candidate."""
    current = make_navmap_payload_v1({"posture": "standing"}, modality="scene_body")
    visual_candidate = make_navmap_payload_v1({"posture": "standing"}, modality="visual")

    filtered = match_navmap_payloads_v1(current, [visual_candidate])
    unfiltered = match_navmap_payloads_v1(current, [visual_candidate], same_modality_only=False)

    assert filtered.as_dict()["matched"] is False
    assert filtered.as_dict()["reason"] == "no_candidates"
    assert unfiltered.as_dict()["matched"] is True
    assert unfiltered.as_dict()["candidate"]["modality"] == "visual"


def test_navmap_learning_proposal_keeps_exact_candidate_match() -> None:
    """An exact match should propose keeping the matched candidate unchanged."""
    current = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near"},
        basis={"case": "current"},
    )
    candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near"},
        basis={"label": "mom_near"},
    )

    match = match_navmap_payloads_v1(current, [candidate])
    proposal = navmap_learning_proposal_from_match_v1(match).as_dict()

    assert proposal["schema"] == "navmap_learning_proposal_v1"
    assert proposal["action"] == "keep_candidate"
    assert proposal["accepted_match"] is True
    assert proposal["reason"] == "exact_match"
    assert proposal["candidate_index"] == 0
    assert proposal["proposed_payload"] == proposal["candidate"]
    assert proposal["proposed_payload"]["basis"] == {"label": "mom_near"}


def test_navmap_learning_proposal_updates_partial_candidate_match() -> None:
    """A partial accepted match should overlay current slots onto the candidate map."""
    current = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        confidence=0.8,
        basis={"case": "current_scene"},
    )
    candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "far",
            "terrain": "flat",
        },
        confidence=0.4,
        basis={"label": "field_without_mom"},
    )

    match = match_navmap_payloads_v1(current, [candidate])
    proposal = navmap_learning_proposal_from_match_v1(match).as_dict()

    assert proposal["action"] == "update_candidate"
    assert proposal["accepted_match"] is True
    assert proposal["reason"] == "residual_update"
    assert proposal["score"] == 0.2
    assert proposal["proposed_payload"]["source"] == "NavMapCandidate.Update"
    assert proposal["proposed_payload"]["confidence"] == 0.8
    assert proposal["proposed_payload"]["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
        "terrain": "flat",
        "nipple_state": "found",
        "zone": "safe",
    }
    assert proposal["proposed_payload"]["basis"]["label"] == "field_without_mom"
    assert proposal["proposed_payload"]["basis"]["proposal_action"] == "update_candidate"
    assert proposal["proposed_payload"]["basis"]["residual_count"] == 4


def test_navmap_learning_proposal_creates_candidate_when_no_match_is_accepted() -> None:
    """A rejected match should propose a new candidate built from the current map."""
    current = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near"},
        confidence=0.7,
        basis={"case": "new_scene"},
    )
    candidate = make_navmap_payload_v1({"posture": "fallen", "mom_distance": "far"})

    match = match_navmap_payloads_v1(current, [candidate], min_score=0.75)
    proposal = navmap_learning_proposal_from_match_v1(match).as_dict()

    assert proposal["action"] == "create_candidate"
    assert proposal["accepted_match"] is False
    assert proposal["reason"] == "below_threshold"
    assert proposal["candidate_index"] == 0
    assert proposal["proposed_payload"]["source"] == "NavMapCandidate.New"
    assert proposal["proposed_payload"]["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
    }
    assert proposal["proposed_payload"]["confidence"] == 0.7
    assert proposal["proposed_payload"]["basis"]["case"] == "new_scene"
    assert proposal["proposed_payload"]["basis"]["proposal_action"] == "create_candidate"


def test_navmap_learning_proposal_ignores_invalid_match_inputs() -> None:
    """Invalid match objects should produce an inert proposal instead of raising."""
    proposal = navmap_learning_proposal_from_match_v1("not-a-match").as_dict()  # type: ignore[arg-type]

    assert proposal["action"] == "ignore"
    assert proposal["accepted_match"] is False
    assert proposal["reason"] == "invalid_match"
    assert proposal["proposed_payload"] == {}
