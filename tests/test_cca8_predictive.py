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
