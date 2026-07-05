# -*- coding: utf-8 -*-
"""Tests for CCA8 predictive-feedback record helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from cca8_predictive import (
    compare_prediction_to_observed,
    legacy_error_vector_v0,
    make_prediction_record,
    make_posture_prediction_record,
)


def test_posture_prediction_produces_legacy_vector_and_v1_error_record() -> None:
    """A posture mismatch should still feed pred_err_v0 and the richer v1 record."""
    ctx = SimpleNamespace(controller_steps=7)
    record = make_posture_prediction_record(
        "policy:stand_up",
        "standing",
        ctx=ctx,
        source="WorkingMap.Scratch",
        basis={"binding_id": "b9", "posture_tag": "pred:posture:standing"},
        env_step=3,
    )

    error = compare_prediction_to_observed(record, {"posture": "fallen"}, ctx=ctx, env_step=4)
    payload = error.as_dict()

    assert legacy_error_vector_v0(error) == {"posture": 1}
    assert payload["schema"] == "prediction_error_v1"
    assert payload["prediction"]["policy"] == "policy:stand_up"
    assert payload["prediction"]["expected"] == {"posture": "standing"}
    assert payload["observed"] == {"posture": "fallen"}
    assert payload["error_by_slot"] == {"posture": 1}
    assert payload["matched"] is False
    assert payload["mismatch_count"] == 1
    assert payload["severity"] == 1.0


def test_prediction_comparison_handles_small_map_slot_record() -> None:
    """The comparison helper should already support the first tiny map-slot vocabulary."""
    ctx = SimpleNamespace(controller_steps=12)
    record = make_prediction_record(
        "policy:seek_nipple",
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        ctx=ctx,
        source="WorkingMap.Scratch",
        basis={"reason": "unit_test"},
        env_step=5,
    )

    error = compare_prediction_to_observed(
        record,
        {
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "found",
            "zone": "unsafe",
        },
        ctx=ctx,
        env_step=6,
    )

    assert error.error_by_slot == {
        "posture": 0,
        "mom_distance": 1,
        "nipple_state": 0,
        "zone": 1,
    }
    assert legacy_error_vector_v0(error) == error.error_by_slot
    assert error.matched is False
    assert error.mismatch_count == 2
    assert error.severity == 2.0


def _env_obs_stub(predicates: list[str], env_meta: dict[str, Any] | None = None) -> Any:
    """Return a tiny EnvObservation-like object for runner helper tests."""
    return SimpleNamespace(predicates=predicates, env_meta=env_meta or {})


def test_prediction_observed_slots_extracts_direct_predicates_and_zone() -> None:
    """Observed-slot extraction should convert direct EnvObservation predicates."""
    from cca8_run import prediction_observed_slots_from_env_obs_v1

    obs = _env_obs_stub(
        ["posture:standing", "proximity:mom:close", "nipple:found"],
        {"zone": "safe"},
    )

    assert prediction_observed_slots_from_env_obs_v1(obs) == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
        "zone": "safe",
    }


def test_prediction_observed_slots_extracts_alternate_predicates() -> None:
    """Observed-slot extraction should cover the other first-milepost values."""
    from cca8_run import prediction_observed_slots_from_env_obs_v1

    obs = _env_obs_stub(
        ["posture:fallen", "proximity:mom:far", "nipple:latched"],
        {},
    )

    assert prediction_observed_slots_from_env_obs_v1(obs) == {
        "posture": "fallen",
        "mom_distance": "far",
        "nipple_state": "latched",
    }


def test_prediction_observed_slots_uses_raw_mom_proximity_fallback() -> None:
    """The raw mom-proximity fallback should fill only a missing mom slot."""
    from cca8_run import prediction_observed_slots_from_env_obs_v1

    fallback_obs = _env_obs_stub(
        ["nipple:hidden"],
        {"zone": " nursery ", "mom_proximity_from_raw": "far"},
    )
    direct_obs = _env_obs_stub(
        ["proximity:mom:close"],
        {"mom_proximity_from_raw": "far"},
    )

    assert prediction_observed_slots_from_env_obs_v1(fallback_obs) == {
        "mom_distance": "far",
        "nipple_state": "hidden",
        "zone": "nursery",
    }
    assert prediction_observed_slots_from_env_obs_v1(direct_obs) == {
        "mom_distance": "near",
    }


def test_prediction_next_record_from_policy_posture_builds_matching_record() -> None:
    """The runner helper should convert a policy-written posture binding into a prediction record."""
    from cca8_run import prediction_next_record_from_policy_posture_v1

    ctx = SimpleNamespace(controller_steps=21)
    world = SimpleNamespace(
        _bindings={
            "b1": SimpleNamespace(
                tags={"pred:posture:fallen"},
                meta={"policy": "policy:recover_fall"},
            ),
            "b2": SimpleNamespace(
                tags={"pred:posture:standing"},
                meta={"policy": "policy:stand_up"},
            ),
        }
    )

    record = prediction_next_record_from_policy_posture_v1(
        ctx,
        world,
        "policy:stand_up",
        env_step=8,
        source="WorkingMap.Scratch",
    )

    assert record["schema"] == "prediction_record_v1"
    assert record["policy"] == "policy:stand_up"
    assert record["source"] == "WorkingMap.Scratch"
    assert record["expected"] == {"posture": "standing"}
    assert record["controller_step"] == 21
    assert record["env_step"] == 8
    assert record["basis"] == {
        "binding_id": "b2",
        "posture_tag": "pred:posture:standing",
        "meta_policy": "policy:stand_up",
    }


def test_prediction_next_record_from_policy_posture_enriches_policy_slots_when_available() -> None:
    """Policy-level map-slot expectations should enrich captured posture records."""
    from cca8_run import prediction_next_record_from_policy_posture_v1

    ctx = SimpleNamespace(controller_steps=24)
    world = SimpleNamespace(
        _bindings={
            "b1": SimpleNamespace(
                tags={"pred:posture:standing"},
                meta={"policy": "policy:seek_nipple"},
            ),
        }
    )

    record = prediction_next_record_from_policy_posture_v1(
        ctx,
        world,
        "policy:seek_nipple",
        env_step=30,
        source="WorkingMap.Scratch",
    )

    assert record["schema"] == "prediction_record_v1"
    assert record["policy"] == "policy:seek_nipple"
    assert record["expected"] == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
    }
    assert record["basis"]["binding_id"] == "b1"
    assert record["basis"]["slot_expectation_source"] == "policy_expected_slots_v1"
    assert record["basis"]["slot_expectation_added"] == ["mom_distance", "nipple_state"]


def test_prediction_next_record_from_policy_posture_requires_latest_matching_policy() -> None:
    """The capture helper should preserve the current latest-binding policy check."""
    from cca8_run import prediction_next_record_from_policy_posture_v1

    ctx = SimpleNamespace(controller_steps=22)
    world = SimpleNamespace(
        _bindings={
            "b1": SimpleNamespace(
                tags={"pred:posture:standing"},
                meta={"policy": "policy:stand_up"},
            ),
            "b2": SimpleNamespace(
                tags={"pred:posture:fallen"},
                meta={"policy": "policy:recover_fall"},
            ),
        }
    )

    assert prediction_next_record_from_policy_posture_v1(ctx, world, "policy:stand_up", env_step=9) == {}


def test_prediction_next_record_from_policy_posture_ignores_invalid_inputs() -> None:
    """Invalid predictor inputs should produce no next prediction record."""
    from cca8_run import prediction_next_record_from_policy_posture_v1

    ctx = SimpleNamespace(controller_steps=23)
    world = SimpleNamespace(
        _bindings={
            "b1": SimpleNamespace(
                tags={"pred:posture:standing"},
                meta={"policy": "policy:stand_up"},
            ),
        }
    )

    assert prediction_next_record_from_policy_posture_v1(ctx, world, "", env_step=10) == {}
    assert prediction_next_record_from_policy_posture_v1(ctx, None, "policy:stand_up", env_step=10) == {}


def test_prediction_pending_record_from_ctx_prefers_existing_v1_record() -> None:
    """Pending-record resolution should use the formal v1 record when present."""
    from cca8_run import prediction_pending_record_from_ctx_v1

    existing = make_prediction_record(
        "policy:seek_nipple",
        {"posture": "standing", "mom_distance": "near"},
        source="WorkingMap.Scratch",
        env_step=11,
    ).as_dict()
    ctx = SimpleNamespace(
        prediction_next_record=existing,
        pred_next_posture="fallen",
        pred_next_policy="policy:recover_fall",
        controller_steps=31,
    )

    record = prediction_pending_record_from_ctx_v1(ctx, env_step=12)

    assert record == existing
    assert record["policy"] == "policy:seek_nipple"
    assert record["expected"] == {"posture": "standing", "mom_distance": "near"}
    assert record["source"] == "WorkingMap.Scratch"


def test_prediction_pending_record_from_ctx_builds_legacy_posture_record() -> None:
    """The old posture-only pending fields should still become a v1 prediction record."""
    from cca8_run import prediction_pending_record_from_ctx_v1

    ctx = SimpleNamespace(
        prediction_next_record={},
        pred_next_posture="standing",
        pred_next_policy="policy:stand_up",
        controller_steps=32,
    )

    record = prediction_pending_record_from_ctx_v1(ctx, env_step=13)

    assert record["schema"] == "prediction_record_v1"
    assert record["policy"] == "policy:stand_up"
    assert record["expected"] == {"posture": "standing"}
    assert record["source"] == "legacy:pred_next_posture"
    assert record["controller_step"] == 32
    assert record["env_step"] == 13


def test_prediction_pending_record_from_ctx_enriches_legacy_policy_slots() -> None:
    """Legacy pending posture should also receive safe policy-level expected slots."""
    from cca8_run import prediction_pending_record_from_ctx_v1

    ctx = SimpleNamespace(
        prediction_next_record={},
        pred_next_posture="standing",
        pred_next_policy="policy:seek_nipple",
        controller_steps=34,
    )

    record = prediction_pending_record_from_ctx_v1(ctx, env_step=31)

    assert record["schema"] == "prediction_record_v1"
    assert record["policy"] == "policy:seek_nipple"
    assert record["source"] == "legacy:pred_next_posture"
    assert record["expected"] == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
    }
    assert record["basis"]["slot_expectation_source"] == "policy_expected_slots_v1"
    assert record["basis"]["slot_expectation_added"] == ["mom_distance", "nipple_state"]


def test_prediction_pending_record_from_ctx_returns_empty_without_pending_prediction() -> None:
    """No v1 record and no legacy posture prediction should resolve to no pending prediction."""
    from cca8_run import prediction_pending_record_from_ctx_v1

    ctx = SimpleNamespace(
        prediction_next_record={},
        pred_next_posture=None,
        pred_next_policy=None,
    )

    assert prediction_pending_record_from_ctx_v1(ctx, env_step=14) == {}
    assert prediction_pending_record_from_ctx_v1(None, env_step=14) == {}


def test_prediction_pending_record_from_ctx_handles_malformed_next_record() -> None:
    """Malformed v1 storage should not crash pending-record resolution."""
    from cca8_run import prediction_pending_record_from_ctx_v1

    ctx = SimpleNamespace(
        prediction_next_record="not-a-dict",
        pred_next_posture="standing",
        pred_next_policy="policy:stand_up",
        controller_steps=33,
    )
    empty_ctx = SimpleNamespace(
        prediction_next_record=["not", "a", "dict"],
        pred_next_posture="",
        pred_next_policy="policy:stand_up",
    )

    record = prediction_pending_record_from_ctx_v1(ctx, env_step=15)

    assert record["policy"] == "policy:stand_up"
    assert record["expected"] == {"posture": "standing"}
    assert record["source"] == "legacy:pred_next_posture"
    assert prediction_pending_record_from_ctx_v1(empty_ctx, env_step=15) == {}


def test_prediction_policy_expected_slots_covers_first_goat_policy_hypotheses() -> None:
    """Policy-level expectations should expose the first tiny map-slot vocabulary."""
    from cca8_run import prediction_policy_expected_slots_v1

    assert prediction_policy_expected_slots_v1("policy:stand_up") == {"posture": "standing"}
    assert prediction_policy_expected_slots_v1("policy:recover_fall") == {"posture": "standing"}
    assert prediction_policy_expected_slots_v1("policy:rest") == {"posture": "resting"}
    assert prediction_policy_expected_slots_v1("policy:suckle") == {"nipple_state": "latched"}
    assert prediction_policy_expected_slots_v1("policy:seek_nipple") == {
        "mom_distance": "near",
        "nipple_state": "found",
    }
    assert prediction_policy_expected_slots_v1("policy:stand_up", expected_posture="fallen") == {
        "posture": "fallen",
    }
    assert prediction_policy_expected_slots_v1("", expected_posture="standing") == {"posture": "standing"}
    assert prediction_policy_expected_slots_v1(None) == {}


def test_prediction_record_with_expected_slots_merges_without_overwriting_existing_slots() -> None:
    """Additional map-slot expectations should not overwrite captured postconditions."""
    from cca8_run import prediction_record_with_expected_slots_v1

    record = make_posture_prediction_record(
        "policy:seek_nipple",
        "standing",
        source="WorkingMap.Scratch",
        basis={"binding_id": "b12"},
        env_step=28,
    ).as_dict()

    merged = prediction_record_with_expected_slots_v1(
        record,
        {
            "posture": "fallen",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": None,
        },
    )

    assert record["expected"] == {"posture": "standing"}
    assert merged["expected"] == {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "found",
    }
    assert merged["basis"]["binding_id"] == "b12"
    assert merged["basis"]["slot_expectation_source"] == "policy_expected_slots_v1"
    assert merged["basis"]["slot_expectation_added"] == ["mom_distance", "nipple_state"]


def test_prediction_record_with_expected_slots_handles_invalid_inputs() -> None:
    """Invalid enrichment inputs should produce stable, non-mutating results."""
    from cca8_run import prediction_record_with_expected_slots_v1

    record = make_prediction_record(
        "policy:stand_up",
        {"posture": "standing"},
        source="WorkingMap.Scratch",
        env_step=29,
    ).as_dict()

    assert prediction_record_with_expected_slots_v1(None, {"posture": "standing"}) == {}
    assert prediction_record_with_expected_slots_v1(record, "not-a-dict") == record
    assert record["expected"] == {"posture": "standing"}


def test_prediction_compare_pending_to_observed_reports_mismatch_summary() -> None:
    """The comparison helper should summarize a pending prediction vs observed slots."""
    from cca8_run import prediction_compare_pending_to_observed_v1

    prediction = make_prediction_record(
        "policy:seek_nipple",
        {
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "found",
            "zone": "safe",
        },
        source="WorkingMap.Scratch",
        env_step=16,
    ).as_dict()
    obs = _env_obs_stub(
        ["posture:fallen", "proximity:mom:far", "nipple:found"],
        {"zone": "unsafe"},
    )
    ctx = SimpleNamespace(
        controller_steps=41,
        pred_err_v0_last={"old": 1},
        prediction_last_error_record={"schema": "old"},
        prediction_error_history=[{"schema": "old"}],
    )

    result = prediction_compare_pending_to_observed_v1(ctx, prediction, obs, env_step=17)

    assert result["schema"] == "prediction_comparison_result_v1"
    assert result["has_prediction"] is True
    assert result["err_vec"] == {"posture": 1, "mom_distance": 1, "nipple_state": 0, "zone": 1}
    assert result["pred_posture"] == "standing"
    assert result["obs_posture"] == "fallen"
    assert result["source_policy"] == "policy:seek_nipple"
    assert result["matched"] is False
    assert result["error_record"]["mismatch_count"] == 3
    assert ctx.pred_err_v0_last == {"old": 1}


def test_prediction_compare_pending_to_observed_reports_matched_summary() -> None:
    """The comparison helper should report matched=True when observed slots agree."""
    from cca8_run import prediction_compare_pending_to_observed_v1

    prediction = make_prediction_record(
        "policy:stand_up",
        {"posture": "standing", "mom_distance": "near"},
        source="WorkingMap.Scratch",
        env_step=18,
    ).as_dict()
    obs = _env_obs_stub(["posture:standing", "proximity:mom:close"], {})

    result = prediction_compare_pending_to_observed_v1(None, prediction, obs, env_step=19)

    assert result["has_prediction"] is True
    assert result["err_vec"] == {"posture": 0, "mom_distance": 0}
    assert result["matched"] is True
    assert result["error_record"]["severity"] == 0.0


def test_prediction_compare_pending_to_observed_returns_empty_without_pending_prediction() -> None:
    """No valid pending prediction should produce an inert comparison result."""
    from cca8_run import prediction_compare_pending_to_observed_v1

    obs = _env_obs_stub(["posture:standing"], {})

    empty_result = prediction_compare_pending_to_observed_v1(None, {}, obs, env_step=20)
    malformed_result = prediction_compare_pending_to_observed_v1(None, "not-a-dict", obs, env_step=20)

    assert empty_result == malformed_result
    assert empty_result["schema"] == "prediction_comparison_result_v1"
    assert empty_result["has_prediction"] is False
    assert empty_result["error_record"] == {}
    assert empty_result["err_vec"] == {}
    assert empty_result["matched"] is None


def test_prediction_feedback_step_from_ctx_obs_applies_v1_pending_record() -> None:
    """The feedback-step helper should resolve, compare, apply, and return print fields."""
    from cca8_run import prediction_feedback_step_from_ctx_obs_v1

    pending = make_prediction_record(
        "policy:seek_nipple",
        {"posture": "standing", "mom_distance": "near"},
        source="WorkingMap.Scratch",
        env_step=24,
    ).as_dict()
    ctx = SimpleNamespace(
        prediction_next_record=pending,
        pred_next_posture=None,
        pred_next_policy=None,
        pred_err_v0_last={},
        prediction_last_error_record={},
        prediction_error_history=[],
        controller_steps=51,
    )
    obs = _env_obs_stub(["posture:fallen", "proximity:mom:far"], {})

    result = prediction_feedback_step_from_ctx_obs_v1(ctx, obs, env_step=25, limit=50)

    assert result["schema"] == "prediction_feedback_step_v1"
    assert result["status"] == "compared"
    assert result["has_prediction"] is True
    assert result["applied"] is True
    assert result["err_vec"] == {"posture": 1, "mom_distance": 1}
    assert result["pred_posture"] == "standing"
    assert result["obs_posture"] == "fallen"
    assert result["source_policy"] == "policy:seek_nipple"
    assert result["matched"] is False
    assert ctx.pred_err_v0_last == {"posture": 1, "mom_distance": 1}
    assert ctx.prediction_last_error_record["mismatch_count"] == 2
    assert ctx.prediction_error_history == [ctx.prediction_last_error_record]


def test_prediction_feedback_step_from_ctx_obs_uses_legacy_pending_posture() -> None:
    """The feedback-step helper should preserve the legacy pred_next_posture fallback."""
    from cca8_run import prediction_feedback_step_from_ctx_obs_v1

    ctx = SimpleNamespace(
        prediction_next_record={},
        pred_next_posture="standing",
        pred_next_policy="policy:stand_up",
        pred_err_v0_last={},
        prediction_last_error_record={},
        prediction_error_history=[],
        controller_steps=52,
    )
    obs = _env_obs_stub(["posture:standing"], {})

    result = prediction_feedback_step_from_ctx_obs_v1(ctx, obs, env_step=26, limit=50)

    assert result["status"] == "compared"
    assert result["err_vec"] == {"posture": 0}
    assert result["pred_posture"] == "standing"
    assert result["obs_posture"] == "standing"
    assert result["source_policy"] == "policy:stand_up"
    assert result["matched"] is True
    assert ctx.pred_err_v0_last == {"posture": 0}
    assert ctx.prediction_last_error_record["matched"] is True
    assert len(ctx.prediction_error_history) == 1


def test_prediction_feedback_step_from_ctx_obs_clears_current_error_without_pending_prediction() -> None:
    """No pending prediction should clear current diagnostic registers but keep history."""
    from cca8_run import prediction_feedback_step_from_ctx_obs_v1

    old_history = [{"schema": "prediction_error_v1", "seq": 1}]
    ctx = SimpleNamespace(
        prediction_next_record={},
        pred_next_posture=None,
        pred_next_policy=None,
        pred_err_v0_last={"posture": 1},
        prediction_last_error_record={"schema": "old"},
        prediction_error_history=list(old_history),
    )
    obs = _env_obs_stub(["posture:standing"], {})

    result = prediction_feedback_step_from_ctx_obs_v1(ctx, obs, env_step=27, limit=50)

    assert result["schema"] == "prediction_feedback_step_v1"
    assert result["status"] == "idle"
    assert result["has_prediction"] is False
    assert result["applied"] is False
    assert result["err_vec"] == {}
    assert ctx.pred_err_v0_last == {}
    assert ctx.prediction_last_error_record == {}
    assert ctx.prediction_error_history == old_history


def test_prediction_error_history_append_recovers_and_caps_to_newest_records() -> None:
    """Prediction-error history should remain a bounded diagnostic trace."""
    from cca8_run import prediction_error_history_append_v1

    ctx = SimpleNamespace(prediction_error_history="not-a-list")

    assert prediction_error_history_append_v1(ctx, {"schema": "prediction_error_v1", "seq": 0}, limit=50) == 1
    assert ctx.prediction_error_history == [{"schema": "prediction_error_v1", "seq": 0}]

    count = 0
    for seq in range(1, 56):
        count = prediction_error_history_append_v1(ctx, {"schema": "prediction_error_v1", "seq": seq}, limit=50)

    assert count == 50
    assert len(ctx.prediction_error_history) == 50
    assert ctx.prediction_error_history[0]["seq"] == 6
    assert ctx.prediction_error_history[-1]["seq"] == 55
    assert prediction_error_history_append_v1(None, {"schema": "prediction_error_v1"}, limit=50) == 0


def test_prediction_error_record_apply_to_ctx_stores_legacy_and_history() -> None:
    """The apply helper should update all diagnostic registers from a PredictionError object."""
    from cca8_run import prediction_error_record_apply_to_ctx_v1

    prediction = make_prediction_record(
        "policy:stand_up",
        {"posture": "standing"},
        source="WorkingMap.Scratch",
        env_step=20,
    )
    error = compare_prediction_to_observed(prediction, {"posture": "fallen"}, env_step=21)
    ctx = SimpleNamespace(
        pred_err_v0_last={},
        prediction_last_error_record={},
        prediction_error_history=[],
    )

    err_vec = prediction_error_record_apply_to_ctx_v1(ctx, error, limit=50)

    assert err_vec == {"posture": 1}
    assert ctx.pred_err_v0_last == {"posture": 1}
    assert ctx.prediction_last_error_record["schema"] == "prediction_error_v1"
    assert ctx.prediction_last_error_record["prediction"]["policy"] == "policy:stand_up"
    assert ctx.prediction_last_error_record["observed"] == {"posture": "fallen"}
    assert ctx.prediction_error_history == [ctx.prediction_last_error_record]


def test_prediction_error_record_apply_to_ctx_accepts_dict_payload() -> None:
    """The apply helper should also accept the JSON-safe dict form."""
    from cca8_run import prediction_error_record_apply_to_ctx_v1

    prediction = make_prediction_record(
        "policy:seek_nipple",
        {"posture": "standing", "mom_distance": "near"},
        source="WorkingMap.Scratch",
        env_step=22,
    ).as_dict()
    error_record = compare_prediction_to_observed(
        prediction,
        {"posture": "standing", "mom_distance": "far"},
        env_step=23,
    ).as_dict()
    ctx = SimpleNamespace(
        pred_err_v0_last={},
        prediction_last_error_record={},
        prediction_error_history=[],
    )

    err_vec = prediction_error_record_apply_to_ctx_v1(ctx, error_record, limit=50)

    assert err_vec == {"posture": 0, "mom_distance": 1}
    assert ctx.pred_err_v0_last == {"posture": 0, "mom_distance": 1}
    assert ctx.prediction_last_error_record == error_record
    assert ctx.prediction_error_history == [error_record]


def test_prediction_error_record_apply_to_ctx_ignores_invalid_inputs() -> None:
    """Invalid apply-helper inputs should leave the diagnostic registers unchanged."""
    from cca8_run import prediction_error_record_apply_to_ctx_v1

    ctx = SimpleNamespace(
        pred_err_v0_last={"posture": 1},
        prediction_last_error_record={"schema": "old"},
        prediction_error_history=[{"schema": "old"}],
    )

    assert prediction_error_record_apply_to_ctx_v1(None, {"schema": "prediction_error_v1"}) == {}
    assert prediction_error_record_apply_to_ctx_v1(ctx, "not-an-error-record") == {}
    assert ctx.pred_err_v0_last == {"posture": 1}
    assert ctx.prediction_last_error_record == {"schema": "old"}
    assert ctx.prediction_error_history == [{"schema": "old"}]


def test_prediction_feedback_summary_empty_ctx_is_stable() -> None:
    """The read-only feedback register should be stable before any prediction exists."""
    from cca8_run import prediction_feedback_mini_line_v1, prediction_feedback_summary_v1

    ctx = SimpleNamespace(
        prediction_next_record={},
        prediction_last_error_record={},
        prediction_error_history=[],
        pred_err_v0_last={},
    )

    summary = prediction_feedback_summary_v1(ctx)

    assert summary["schema"] == "prediction_feedback_summary_v1"
    assert summary["status"] == "idle"
    assert summary["has_next_prediction"] is False
    assert summary["has_last_error"] is False
    assert summary["history_count"] == 0
    assert summary["pred_err_v0"] == {}
    assert summary["last_mismatch_count"] == 0
    assert summary["last_severity"] == 0.0
    assert prediction_feedback_mini_line_v1(ctx) == (
        "[pred] status=idle next=none; last=none; history_count=0"
    )


def test_prediction_feedback_summary_reports_active_error_record() -> None:
    """The feedback register should summarize next prediction and last error records."""
    from cca8_run import render_prediction_feedback_lines_v1, prediction_feedback_mini_line_v1, prediction_feedback_summary_v1

    next_record = make_prediction_record(
        "policy:seek_nipple",
        {"posture": "standing", "mom_distance": "near"},
        source="WorkingMap.Scratch",
        env_step=5,
    ).as_dict()
    error = compare_prediction_to_observed(
        next_record,
        {"posture": "standing", "mom_distance": "far"},
        env_step=6,
    )
    error_record = error.as_dict()

    ctx = SimpleNamespace(
        prediction_next_record=next_record,
        prediction_last_error_record=error_record,
        prediction_error_history=[error_record],
        pred_err_v0_last={"posture": 0, "mom_distance": 1},
    )

    summary = prediction_feedback_summary_v1(ctx)
    lines = render_prediction_feedback_lines_v1(ctx)
    mini = prediction_feedback_mini_line_v1(ctx)

    assert summary["status"] == "active"
    assert summary["has_next_prediction"] is True
    assert summary["has_last_error"] is True
    assert summary["history_count"] == 1
    assert summary["next_policy"] == "policy:seek_nipple"
    assert summary["next_expected"] == {"posture": "standing", "mom_distance": "near"}
    assert summary["last_matched"] is False
    assert summary["last_mismatch_count"] == 1
    assert summary["last_severity"] == 1.0
    assert summary["last_error_by_slot"] == {"posture": 0, "mom_distance": 1}
    assert any("PREDICTION FEEDBACK:" in line for line in lines)
    assert any("mismatch_count=1" in line for line in lines)
    assert "status=active" in mini
    assert "history_count=1" in mini
