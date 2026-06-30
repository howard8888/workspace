# -*- coding: utf-8 -*-
"""Tests for CCA8 predictive-feedback record helpers."""

from __future__ import annotations

from types import SimpleNamespace

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