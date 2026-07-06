# -*- coding: utf-8 -*-
"""Tests for CCA8 NavMap payload helpers."""

from __future__ import annotations
import json
from types import SimpleNamespace
from cca8_navmap import (
    NAVMAP_PAYLOAD_SCHEMA_V1,
    NavMapPayloadV1,
    match_navmap_payloads_v1,
    make_navmap_payload_v1,
    navmap_residual_v1,
    navmap_payload_slots_v1,
    navmap_learning_proposal_from_match_v1,
    navmap_payload_from_env_obs_v1,
    navmap_slots_from_env_obs_v1,
    navmap_scene_body_cycle_from_env_obs_v1,
    NAVMAP_STORE_UPDATE_SCHEMA_V1,
    navmap_apply_learning_proposal_v1,
    NAVMAP_TRANSITION_SCHEMA_V1,
    make_navmap_transition_v1,
    NAVMAP_POLICY_OUTCOME_SCHEMA_V1,
    navmap_policy_outcome_from_transition_v1,
    NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1,
    navmap_observation_update_from_env_obs_v1,
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


def test_navmap_slots_from_env_obs_extracts_scene_body_predicates() -> None:
    """EnvObservation-like predicates should become the first scene_body slot map."""
    obs = SimpleNamespace(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        env_meta={"zone": "safe"},
    )

    assert navmap_slots_from_env_obs_v1(obs) == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
        "zone": "safe",
    }


def test_navmap_slots_from_env_obs_uses_metadata_fallbacks() -> None:
    """Missing predicate slots should use safe metadata fallbacks when available."""
    obs = {
        "predicates": ["resting"],
        "env_meta": {
            "mom_proximity_from_raw": "far",
            "nipple_state": "visible",
            "zone": " nursery ",
        },
    }

    assert navmap_slots_from_env_obs_v1(obs) == {
        "posture": "resting",
        "mom_distance": "far",
        "nipple_state": "found",
        "zone": "nursery",
    }


def test_navmap_payload_from_env_obs_builds_json_safe_scene_body_payload() -> None:
    """The observation extractor should build a normal NavMapPayloadV1."""
    obs = SimpleNamespace(
        predicates=["posture:fallen", "proximity:mom:far", "nipple:latched", "milk:drinking"],
        env_meta={
            "zone": "unsafe",
            "scenario_stage": "birth",
            "time_since_birth": 3,
            "position": "open_field",
        },
    )

    payload = navmap_payload_from_env_obs_v1(
        obs,
        confidence=0.6,
        source="unit_test_env_obs",
        basis={"case": "wake_up"},
    ).as_dict()

    assert payload["schema"] == NAVMAP_PAYLOAD_SCHEMA_V1
    assert payload["map_kind"] == "local_navmap"
    assert payload["modality"] == "scene_body"
    assert payload["source"] == "unit_test_env_obs"
    assert payload["confidence"] == 0.6
    assert payload["slots"] == {
        "posture": "fallen",
        "mom_distance": "far",
        "nipple_state": "latched",
        "zone": "unsafe",
    }
    assert payload["basis"]["case"] == "wake_up"
    assert payload["basis"]["payload_source"] == "navmap_payload_from_env_obs_v1"
    assert payload["basis"]["predicate_count"] == 4
    assert payload["basis"]["scenario_stage"] == "birth"
    assert payload["basis"]["time_since_birth"] == 3
    assert payload["basis"]["position"] == "open_field"
    json.dumps(payload)


def test_navmap_payload_from_env_obs_handles_empty_or_malformed_observations() -> None:
    """Invalid observations should produce an empty but valid scene_body payload."""
    empty_payload = navmap_payload_from_env_obs_v1(None).as_dict()
    malformed_payload = navmap_payload_from_env_obs_v1(
        SimpleNamespace(predicates="not-a-list", env_meta="not-a-dict")
    ).as_dict()

    assert empty_payload["slots"] == {}
    assert empty_payload["basis"]["predicate_count"] == 0
    assert malformed_payload["slots"] == {}
    assert malformed_payload["basis"]["predicate_count"] == 0


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


def test_navmap_scene_body_cycle_keeps_exact_candidate_match() -> None:
    """A full observation cycle should keep an exact matching candidate."""
    obs = SimpleNamespace(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        env_meta={"zone": "safe", "scenario_stage": "wake"},
    )
    candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        basis={"label": "mom_near"},
    )

    cycle = navmap_scene_body_cycle_from_env_obs_v1(obs, [candidate], basis={"case": "cycle_exact"}).as_dict()

    assert cycle["schema"] == "navmap_cycle_v1"
    assert cycle["candidate_count"] == 1
    assert cycle["matched"] is True
    assert cycle["action"] == "keep_candidate"
    assert cycle["current_payload"]["basis"]["case"] == "cycle_exact"
    assert cycle["current_payload"]["basis"]["scenario_stage"] == "wake"
    assert cycle["match"]["score"] == 1.0
    assert cycle["proposal"]["reason"] == "exact_match"


def test_navmap_scene_body_cycle_updates_partial_candidate_match() -> None:
    """A full observation cycle should propose updating a partial candidate match."""
    obs = SimpleNamespace(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        env_meta={"zone": "safe"},
    )
    candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "far", "terrain": "flat"},
        confidence=0.2,
        basis={"label": "field_without_mom"},
    )

    cycle = navmap_scene_body_cycle_from_env_obs_v1(obs, [candidate], confidence=0.9).as_dict()

    assert cycle["candidate_count"] == 1
    assert cycle["matched"] is True
    assert cycle["action"] == "update_candidate"
    assert cycle["match"]["score"] == 0.2
    assert cycle["proposal"]["proposed_payload"]["confidence"] == 0.9
    assert cycle["proposal"]["proposed_payload"]["source"] == "NavMapCandidate.Update"
    assert cycle["proposal"]["proposed_payload"]["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
        "terrain": "flat",
        "nipple_state": "found",
        "zone": "safe",
    }


def test_navmap_scene_body_cycle_creates_candidate_when_no_match_is_accepted() -> None:
    """A full observation cycle should propose a new candidate when matching fails."""
    obs = SimpleNamespace(
        predicates=["posture:fallen", "proximity:mom:far"],
        env_meta={"zone": "unsafe"},
    )
    candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near", "zone": "safe"},
        basis={"label": "wrong_context"},
    )

    cycle = navmap_scene_body_cycle_from_env_obs_v1(obs, [candidate], min_score=0.75, confidence=0.5).as_dict()

    assert cycle["candidate_count"] == 1
    assert cycle["matched"] is False
    assert cycle["action"] == "create_candidate"
    assert cycle["match"]["reason"] == "below_threshold"
    assert cycle["proposal"]["proposed_payload"]["source"] == "NavMapCandidate.New"
    assert cycle["proposal"]["proposed_payload"]["confidence"] == 0.5
    assert cycle["proposal"]["proposed_payload"]["slots"] == {
        "posture": "fallen",
        "mom_distance": "far",
        "zone": "unsafe",
    }


def test_navmap_scene_body_cycle_handles_no_candidates() -> None:
    """A full observation cycle should still return a valid proposal with no candidates."""
    obs = SimpleNamespace(predicates=["posture:standing"], env_meta={})

    cycle = navmap_scene_body_cycle_from_env_obs_v1(obs, []).as_dict()

    assert cycle["candidate_count"] == 0
    assert cycle["matched"] is False
    assert cycle["action"] == "create_candidate"
    assert cycle["match"]["reason"] == "no_candidates"
    assert cycle["proposal"]["proposed_payload"]["slots"] == {"posture": "standing"}


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


def test_navmap_apply_learning_proposal_keeps_candidate_store_on_exact_match() -> None:
    """An exact match should leave the candidate list unchanged."""
    current = make_navmap_payload_v1({"posture": "standing", "mom_distance": "near"})
    candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near"},
        basis={"label": "mom_near"},
    )
    proposal = navmap_learning_proposal_from_match_v1(match_navmap_payloads_v1(current, [candidate]))

    update = navmap_apply_learning_proposal_v1([candidate], proposal).as_dict()

    assert update["schema"] == NAVMAP_STORE_UPDATE_SCHEMA_V1
    assert update["action"] == "keep_candidate"
    assert update["changed"] is False
    assert update["reason"] == "kept_existing_candidate"
    assert update["candidate_index"] == 0
    assert update["before_count"] == 1
    assert update["after_count"] == 1
    assert update["candidates"] == [candidate.as_dict()]


def test_navmap_apply_learning_proposal_updates_candidate_store_entry() -> None:
    """A residual update should replace the matched candidate with the proposal."""
    current = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        confidence=0.9,
    )
    candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "far", "terrain": "flat"},
        confidence=0.4,
        basis={"label": "field_without_mom"},
    )
    proposal = navmap_learning_proposal_from_match_v1(match_navmap_payloads_v1(current, [candidate])).as_dict()

    update = navmap_apply_learning_proposal_v1([candidate.as_dict()], proposal).as_dict()

    assert update["action"] == "update_candidate"
    assert update["changed"] is True
    assert update["reason"] == "updated_candidate"
    assert update["candidate_index"] == 0
    assert update["before_count"] == 1
    assert update["after_count"] == 1
    assert update["candidates"][0]["source"] == "NavMapCandidate.Update"
    assert update["candidates"][0]["confidence"] == 0.9
    assert update["candidates"][0]["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
        "terrain": "flat",
        "nipple_state": "found",
        "zone": "safe",
    }
    assert update["candidates"][0]["basis"]["proposal_action"] == "update_candidate"


def test_navmap_apply_learning_proposal_appends_new_candidate_and_caps_store() -> None:
    """A create proposal should append the new candidate and keep the newest maps."""
    current = make_navmap_payload_v1(
        {"posture": "fallen", "mom_distance": "far", "zone": "unsafe"},
        confidence=0.6,
        basis={"case": "new_scene"},
    )
    old_candidate = make_navmap_payload_v1({"posture": "resting"}, basis={"label": "old"})
    weak_candidate = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near", "zone": "safe"},
        basis={"label": "weak"},
    )
    match = match_navmap_payloads_v1(current, [weak_candidate], min_score=0.75)
    proposal = navmap_learning_proposal_from_match_v1(match)

    update = navmap_apply_learning_proposal_v1(
        [old_candidate, weak_candidate],
        proposal,
        max_candidates=2,
    ).as_dict()

    assert update["action"] == "create_candidate"
    assert update["changed"] is True
    assert update["reason"] == "created_candidate_capped"
    assert update["candidate_index"] == 1
    assert update["before_count"] == 2
    assert update["after_count"] == 2
    assert update["candidates"][0]["basis"] == {"label": "weak"}
    assert update["candidates"][1]["source"] == "NavMapCandidate.New"
    assert update["candidates"][1]["slots"] == {
        "posture": "fallen",
        "mom_distance": "far",
        "zone": "unsafe",
    }
    assert update["candidates"][1]["basis"]["proposal_action"] == "create_candidate"


def test_navmap_apply_learning_proposal_ignores_invalid_inputs() -> None:
    """Invalid proposals should preserve the normalized candidate list."""
    candidate = make_navmap_payload_v1({"posture": "standing"}, basis={"label": "known"})
    original = [candidate.as_dict()]

    update = navmap_apply_learning_proposal_v1(original, "not-a-proposal").as_dict()  # type: ignore[arg-type]

    assert update["action"] == "ignore"
    assert update["changed"] is False
    assert update["reason"] == "invalid_proposal"
    assert update["before_count"] == 1
    assert update["after_count"] == 1
    assert update["candidates"] == [candidate.as_dict()]
    assert original == [candidate.as_dict()]

def test_navmap_transition_records_action_conditioned_map_change() -> None:
    """A transition should capture before-map, action, after-map, and slot changes."""
    before_payload = make_navmap_payload_v1(
        {"posture": "fallen", "mom_distance": "near"},
        basis={"case": "before_stand"},
    )
    after_payload = make_navmap_payload_v1(
        {"posture": "standing", "mom_distance": "near"},
        basis={"case": "after_stand"},
    )

    transition = make_navmap_transition_v1(
        before_payload,
        after_payload,
        action=" Policy:Stand Up ",
        reward=1.0,
        drive_delta={" fatigue ": "0.1", "hunger": "-0.05"},
        basis={"env_step": 3},
    ).as_dict()

    assert transition["schema"] == NAVMAP_TRANSITION_SCHEMA_V1
    assert transition["action"] == "policy:stand_up"
    assert transition["reward"] == 1.0
    assert transition["drive_delta"] == {"fatigue": 0.1, "hunger": -0.05}
    assert transition["changed"] is True
    assert transition["changed_slots"] == 1
    assert transition["residual"]["matched_slots"] == {"mom_distance": "near"}
    assert transition["residual"]["mismatched_slots"] == {
        "posture": {"current": "standing", "candidate": "fallen"}
    }
    assert transition["basis"]["transition_source"] == "make_navmap_transition_v1"


def test_navmap_transition_accepts_payload_like_dicts_and_stays_json_safe() -> None:
    """Transition creation should tolerate raw slot dicts and payload-like dicts."""
    before_payload = {" Posture ": "Resting", "Zone": "safe"}
    after_payload = make_navmap_payload_v1(
        {"posture": "standing", "zone": "safe", "mom_distance": "near"},
        source="unit_test_after",
    ).as_dict()

    transition = make_navmap_transition_v1(
        before_payload,
        after_payload,
        action="policy:orient_to_mom",
        reward="0.25",  # type: ignore[arg-type]
        basis={"tags": ("wake", "orient"), "nested": {"ok": True}},
    ).as_dict()

    assert transition["before_payload"]["slots"] == {"posture": "resting", "zone": "safe"}
    assert transition["after_payload"]["slots"] == {
        "posture": "standing",
        "zone": "safe",
        "mom_distance": "near",
    }
    assert transition["reward"] == 0.25
    assert transition["residual"]["matched_slots"] == {"zone": "safe"}
    assert transition["residual"]["novel_slots"] == {"mom_distance": "near"}
    assert transition["basis"]["tags"] == ["wake", "orient"]
    json.dumps(transition)


def test_navmap_transition_handles_malformed_inputs_safely() -> None:
    """Invalid transition inputs should produce an inert JSON-safe transition."""
    transition = make_navmap_transition_v1(
        "bad-before",  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        action=" ",
        reward=float("nan"),
        drive_delta={"hunger": "bad", "warmth": float("inf"), "fatigue": 0.2},
        basis="bad-basis",  # type: ignore[arg-type]
    ).as_dict()

    assert transition["action"] == ""
    assert transition["reward"] == 0.0
    assert transition["drive_delta"] == {"fatigue": 0.2}
    assert transition["changed"] is False
    assert transition["changed_slots"] == 0
    assert transition["before_payload"]["slots"] == {}
    assert transition["after_payload"]["slots"] == {}
    assert transition["residual"]["residual_count"] == 0
    assert transition["basis"] == {"transition_source": "make_navmap_transition_v1"}

def test_navmap_policy_outcome_from_transition_records_successful_action_sample() -> None:
    """A positive transition should become a policy-outcome learning sample."""
    before_payload = make_navmap_payload_v1({"posture": "fallen", "mom_distance": "near"})
    after_payload = make_navmap_payload_v1({"posture": "standing", "mom_distance": "near"})
    transition = make_navmap_transition_v1(
        before_payload,
        after_payload,
        action="policy:stand_up",
        reward=1.0,
        drive_delta={"fatigue": 0.1},
        basis={"env_step": 7},
    )

    outcome = navmap_policy_outcome_from_transition_v1(
        transition,
        confidence=0.8,
        basis={"case": "stand_learning"},
    ).as_dict()

    assert outcome["schema"] == NAVMAP_POLICY_OUTCOME_SCHEMA_V1
    assert outcome["action"] == "policy:stand_up"
    assert outcome["context_slots"] == {"posture": "fallen", "mom_distance": "near"}
    assert outcome["expected_slots"] == {"posture": "standing", "mom_distance": "near"}
    assert outcome["slot_changes"] == {
        "posture": {"before": "fallen", "after": "standing"}
    }
    assert outcome["reward"] == 1.0
    assert outcome["drive_delta"] == {"fatigue": 0.1}
    assert outcome["success"] is True
    assert outcome["confidence"] == 0.8
    assert outcome["sample_count"] == 1
    assert outcome["context_signature"] == "mom_distance=near|posture=fallen"
    assert outcome["policy_key"] == "mom_distance=near|posture=fallen::policy:stand_up"
    assert outcome["basis"]["env_step"] == 7
    assert outcome["basis"]["case"] == "stand_learning"
    assert outcome["basis"]["outcome_source"] == "navmap_policy_outcome_from_transition_v1"
    assert outcome["basis"]["transition_changed_slots"] == 1


def test_navmap_policy_outcome_from_transition_dict_respects_success_threshold() -> None:
    """Outcome creation should accept transition dicts and use the threshold."""
    transition = make_navmap_transition_v1(
        {"posture": "standing", "mom_distance": "near"},
        {"posture": "standing", "mom_distance": "near", "nipple_state": "found"},
        action="policy:seek_nipple",
        reward=0.2,
    ).as_dict()

    outcome = navmap_policy_outcome_from_transition_v1(
        transition,
        success_threshold=0.5,
    ).as_dict()

    assert outcome["action"] == "policy:seek_nipple"
    assert outcome["success"] is False
    assert outcome["reward"] == 0.2
    assert outcome["sample_count"] == 1
    assert outcome["slot_changes"] == {
        "nipple_state": {"before": "", "after": "found"}
    }
    assert outcome["policy_key"] == "mom_distance=near|posture=standing::policy:seek_nipple"
    json.dumps(outcome)


def test_navmap_policy_outcome_from_transition_handles_malformed_inputs() -> None:
    """Invalid transition inputs should produce an inert policy-outcome record."""
    outcome = navmap_policy_outcome_from_transition_v1(
        "not-a-transition",  # type: ignore[arg-type]
        confidence=0.9,
        basis={"case": "bad_input"},
    ).as_dict()

    assert outcome["action"] == ""
    assert outcome["context_slots"] == {}
    assert outcome["expected_slots"] == {}
    assert outcome["slot_changes"] == {}
    assert outcome["success"] is False
    assert outcome["confidence"] == 0.0
    assert outcome["sample_count"] == 0
    assert outcome["context_signature"] == ""
    assert outcome["policy_key"] == ""
    assert outcome["basis"]["case"] == "bad_input"
    assert outcome["basis"]["outcome_source"] == "navmap_policy_outcome_from_transition_v1"
    
def test_navmap_observation_update_keeps_exact_candidate_store() -> None:
    """A full pure observation update should keep an exact candidate unchanged."""
    obs = SimpleNamespace(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        env_meta={"zone": "safe"},
    )
    candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        basis={"label": "mom_near"},
    )

    update = navmap_observation_update_from_env_obs_v1(obs, [candidate]).as_dict()

    assert update["schema"] == NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1
    assert update["action"] == "keep_candidate"
    assert update["matched"] is True
    assert update["changed"] is False
    assert update["candidate_count_before"] == 1
    assert update["candidate_count_after"] == 1
    assert update["current_payload"]["slots"] == candidate.as_dict()["slots"]
    assert update["cycle"]["proposal"]["reason"] == "exact_match"
    assert update["store_update"]["candidates"] == [candidate.as_dict()]


def test_navmap_observation_update_creates_candidate_when_store_is_empty() -> None:
    """An observation with no candidates should create the first candidate payload."""
    obs = SimpleNamespace(
        predicates=["posture:fallen", "proximity:mom:far"],
        env_meta={"zone": "unsafe"},
    )

    update = navmap_observation_update_from_env_obs_v1(
        obs,
        [],
        confidence=0.6,
        basis={"case": "first_scene"},
    ).as_dict()

    assert update["action"] == "create_candidate"
    assert update["matched"] is False
    assert update["changed"] is True
    assert update["candidate_count_before"] == 0
    assert update["candidate_count_after"] == 1
    assert update["cycle"]["match"]["reason"] == "no_candidates"
    assert update["store_update"]["reason"] == "created_candidate"
    assert update["store_update"]["candidates"][0]["source"] == "NavMapCandidate.New"
    assert update["store_update"]["candidates"][0]["confidence"] == 0.6
    assert update["store_update"]["candidates"][0]["slots"] == {
        "posture": "fallen",
        "mom_distance": "far",
        "zone": "unsafe",
    }
    assert update["current_payload"]["basis"]["case"] == "first_scene"


def test_navmap_observation_update_updates_partial_candidate_store_entry() -> None:
    """A full pure observation update should materialize partial-match updates."""
    obs = SimpleNamespace(
        predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        env_meta={"zone": "safe"},
    )
    candidate = make_navmap_payload_v1(
        {
            "posture": "standing",
            "mom_distance": "far",
            "terrain": "flat",
        },
        confidence=0.2,
        basis={"label": "field_without_mom"},
    )

    update = navmap_observation_update_from_env_obs_v1(
        obs,
        [candidate.as_dict()],
        confidence=0.9,
    ).as_dict()

    assert update["action"] == "update_candidate"
    assert update["matched"] is True
    assert update["changed"] is True
    assert update["candidate_count_before"] == 1
    assert update["candidate_count_after"] == 1
    assert update["cycle"]["match"]["score"] == 0.2
    assert update["store_update"]["reason"] == "updated_candidate"
    assert update["store_update"]["candidates"][0]["source"] == "NavMapCandidate.Update"
    assert update["store_update"]["candidates"][0]["slots"] == {
        "posture": "standing",
        "mom_distance": "near",
        "terrain": "flat",
        "nipple_state": "found",
        "zone": "safe",
    }
