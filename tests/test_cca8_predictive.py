# -*- coding: utf-8 -*-
"""Tests for the CCA8 predictive-feedback record helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from cca8_predictive import (
    PredictionError,
    PredictionRecord,
    compare_predicted_posture_to_observed,
    compare_prediction_to_observed,
    legacy_error_vector_v0,
    make_posture_prediction_record,
)


@dataclass
class DummyCtx:
    """Tiny context stub used to avoid importing the full runner."""

    controller_steps: int = 12


def test_posture_prediction_match_is_json_safe() -> None:
    """A standing prediction followed by standing observation should have zero posture error."""
    ctx = DummyCtx(controller_steps=7)
    record = make_posture_prediction_record(
        "policy:stand_up",
        "standing",
        ctx=ctx,
        basis={"binding_id": "b42", "posture_tag": "pred:posture:standing"},
        env_step=3,
    )

    error = compare_prediction_to_observed(record, {"posture": "standing"}, ctx=ctx, env_step=4)

    assert error.matched is True
    assert error.mismatch_count == 0
    assert error.severity == 0.0
    assert error.error_by_slot == {"posture": 0}
    assert legacy_error_vector_v0(error) == {"posture": 0}
    json.dumps(error.as_dict())


def test_posture_prediction_mismatch_round_trips_from_dict() -> None:
    """A standing prediction followed by fallen observation should round-trip as a mismatch."""
    original = compare_predicted_posture_to_observed(
        "standing",
        "fallen",
        policy="policy:stand_up",
        env_step=5,
    )
    payload = original.as_dict()
    restored = PredictionError.from_dict(payload)

    assert restored.matched is False
    assert restored.mismatch_count == 1
    assert restored.error_by_slot == {"posture": 1}
    assert restored.observed == {"posture": "fallen"}
    assert restored.prediction.policy == "policy:stand_up"
    assert restored.prediction.expected == {"posture": "standing"}
    assert legacy_error_vector_v0(payload) == {"posture": 1}


def test_prediction_record_from_dict_tolerates_missing_fields() -> None:
    """Older or partial traces should still produce a usable record object."""
    record = PredictionRecord.from_dict({"expected": {"posture": "standing"}})
    error = compare_prediction_to_observed(record, {})

    assert record.policy == ""
    assert record.source == "WorkingMap.Scratch"
    assert error.error_by_slot == {"posture": 1}