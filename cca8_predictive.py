# -*- coding: utf-8 -*-
"""Prediction records and prediction-error helpers for CCA8.

Purpose
-------
The first predictive-feedback milestone is deliberately small and diagnostic:
make policy postcondition expectations explicit, compare those expectations with
later observations, and return JSON-safe records that can be printed, logged,
and tested without changing controller behavior.

Design stance
-------------
- Predictions are hypotheses, not confirmed WorldGraph truth.
- The natural home for predictions is WorkingMap.Scratch / Creative; this
  module only defines the record shapes and comparison helpers.
- The legacy ``pred_err_v0`` posture vector remains supported so the current
  runner, JSONL records, and state-integrity summaries keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional


__version__ = "0.1.0"
__all__ = [
    "PREDICTION_RECORD_SCHEMA_V1",
    "PREDICTION_ERROR_SCHEMA_V1",
    "PredictionRecord",
    "PredictionError",
    "make_prediction_record",
    "make_posture_prediction_record",
    "compare_prediction_to_observed",
    "compare_predicted_posture_to_observed",
    "legacy_error_vector_v0",
    "__version__",
]


PREDICTION_RECORD_SCHEMA_V1 = "prediction_record_v1"
PREDICTION_ERROR_SCHEMA_V1 = "prediction_error_v1"


def _json_safe_scalar(value: Any) -> Any:
    """Return a small JSON-safe scalar representation for metadata fields."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _json_safe_dict(value: Any) -> dict[str, Any]:
    """Return a shallow JSON-safe dict with string keys."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, Any] = {}
    for key, val in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(val, Mapping):
            out[key] = _json_safe_dict(val)
        elif isinstance(val, list):
            out[key] = [_json_safe_scalar(item) for item in val]
        else:
            out[key] = _json_safe_scalar(val)
    return out


def _slot_map(value: Any) -> dict[str, str]:
    """Return a normalized string->string slot map from a mapping-like object."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, str] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not key:
            continue
        if val is None:
            continue
        out[key] = str(val)
    return out


def _ctx_int(ctx: Any, name: str) -> Optional[int]:
    """Read an integer field from ctx if present and safe."""
    value = getattr(ctx, name, None)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


@dataclass(slots=True)
class PredictionRecord:
    """One explicit expectation about the next observed map/body state.

    A prediction record is a hypothesis emitted by a policy, route, retrieved map,
    or future lookahead process. It is intentionally not a WorldGraph fact. The
    first CCA8 use is posture-only, but the ``expected`` dict is slot-based so the
    same record can later cover SurfaceGrid, nipple state, proximity, hazard, or
    route-progress slots.

    Parameters
    ----------
    policy:
        Policy or process that produced the expectation, for example
        ``"policy:stand_up"``. Use an empty string if the predictor is unknown.
    expected:
        Slot-family map of expected values, for example ``{"posture": "standing"}``.
    source:
        Where the prediction conceptually lives. For the first milestone this is
        usually ``"WorkingMap.Scratch"``.
    controller_step / env_step:
        Optional step markers copied from the runner context and environment.
    basis:
        JSON-safe provenance such as binding id, posture tag, or payload id.
    confidence:
        Lightweight confidence scalar. It is recorded but not used for selection
        in this milestone.
    """

    policy: str
    expected: dict[str, str]
    source: str = "WorkingMap.Scratch"
    controller_step: Optional[int] = None
    env_step: Optional[int] = None
    basis: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    schema: str = PREDICTION_RECORD_SCHEMA_V1

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "policy": str(self.policy or ""),
            "source": str(self.source or ""),
            "expected": dict(self.expected),
            "controller_step": self.controller_step,
            "env_step": self.env_step,
            "basis": _json_safe_dict(self.basis),
            "confidence": float(self.confidence),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionRecord":
        """Build a PredictionRecord from a JSON-safe dict.

        Missing or malformed fields are tolerated so older traces can be read
        best-effort rather than rejected.
        """
        expected = _slot_map(data.get("expected"))
        policy = data.get("policy")
        source = data.get("source")
        confidence = data.get("confidence")
        created_at = data.get("created_at")
        schema = data.get("schema")

        if confidence is None:
            confidence_f = 1.0
        else:
            try:
                confidence_f = float(confidence)
            except Exception:
                confidence_f = 1.0

        return cls(
            policy=str(policy or ""),
            expected=expected,
            source=str(source or "WorkingMap.Scratch"),
            controller_step=_ctx_int(data, "controller_step"),
            env_step=_ctx_int(data, "env_step"),
            basis=_json_safe_dict(data.get("basis")),
            confidence=confidence_f,
            created_at=str(created_at or datetime.now().isoformat(timespec="seconds")),
            schema=str(schema or PREDICTION_RECORD_SCHEMA_V1),
        )


@dataclass(slots=True)
class PredictionError:
    """Comparison between a PredictionRecord and the observed map/body state.

    ``error_by_slot`` is intentionally integer-valued for compatibility with the
    existing ``pred_err_v0`` convention: 0 means matched, 1 means mismatched or
    missing. The richer record carries the observed values, mismatch count, and
    provenance so later code can add graded confidence/value updates without
    changing the basic trace format.
    """

    prediction: PredictionRecord
    observed: dict[str, str]
    error_by_slot: dict[str, int]
    controller_step: Optional[int] = None
    env_step: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    schema: str = PREDICTION_ERROR_SCHEMA_V1

    @property
    def mismatch_count(self) -> int:
        """Number of non-zero slot errors."""
        return sum(1 for val in self.error_by_slot.values() if int(val) != 0)

    @property
    def matched(self) -> bool:
        """True if all expected slots matched observed values."""
        return self.mismatch_count == 0

    @property
    def severity(self) -> float:
        """Simple severity score for the first milestone."""
        return float(self.mismatch_count)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "prediction": self.prediction.as_dict(),
            "observed": dict(self.observed),
            "error_by_slot": dict(self.error_by_slot),
            "matched": bool(self.matched),
            "mismatch_count": int(self.mismatch_count),
            "severity": float(self.severity),
            "controller_step": self.controller_step,
            "env_step": self.env_step,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionError":
        """Build a PredictionError from a JSON-safe dict."""
        pred_raw = data.get("prediction")
        if isinstance(pred_raw, Mapping):
            prediction = PredictionRecord.from_dict(pred_raw)
        else:
            prediction = PredictionRecord(policy="", expected={})

        err_raw = data.get("error_by_slot")
        err_map: dict[str, int] = {}
        if isinstance(err_raw, Mapping):
            for key, val in err_raw.items():
                if not isinstance(key, str):
                    continue
                try:
                    err_map[key] = int(val)
                except Exception:
                    err_map[key] = 1

        created_at = data.get("created_at")
        schema = data.get("schema")

        return cls(
            prediction=prediction,
            observed=_slot_map(data.get("observed")),
            error_by_slot=err_map,
            controller_step=_ctx_int(data, "controller_step"),
            env_step=_ctx_int(data, "env_step"),
            created_at=str(created_at or datetime.now().isoformat(timespec="seconds")),
            schema=str(schema or PREDICTION_ERROR_SCHEMA_V1),
        )


def make_prediction_record(
    policy: str,
    expected: Mapping[str, Any],
    *,
    ctx: Any = None,
    source: str = "WorkingMap.Scratch",
    basis: Optional[Mapping[str, Any]] = None,
    env_step: Optional[int] = None,
    confidence: float = 1.0,
) -> PredictionRecord:
    """Create a PredictionRecord with optional timing copied from ctx.

    This helper keeps runner code short and makes tests independent of the large
    ``Ctx`` class. The returned object is still a normal dataclass and can be
    converted to a dict with ``as_dict()``.
    """
    return PredictionRecord(
        policy=str(policy or ""),
        expected=_slot_map(expected),
        source=str(source or "WorkingMap.Scratch"),
        controller_step=_ctx_int(ctx, "controller_steps"),
        env_step=env_step,
        basis=_json_safe_dict(basis or {}),
        confidence=float(confidence),
    )


def make_posture_prediction_record(
    policy: str,
    posture: str,
    *,
    ctx: Any = None,
    source: str = "WorkingMap.Scratch",
    basis: Optional[Mapping[str, Any]] = None,
    env_step: Optional[int] = None,
    confidence: float = 1.0,
) -> PredictionRecord:
    """Convenience constructor for the first posture-only prediction milestone."""
    return make_prediction_record(
        policy,
        {"posture": str(posture or "")},
        ctx=ctx,
        source=source,
        basis=basis,
        env_step=env_step,
        confidence=confidence,
    )


def compare_prediction_to_observed(
    prediction: PredictionRecord | Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    ctx: Any = None,
    env_step: Optional[int] = None,
) -> PredictionError:
    """Compare expected slot values with observed slot values.

    Expected slots drive the comparison. A missing observed slot counts as a
    mismatch for that expected slot. Extra observed slots are retained in the
    record but do not contribute to the v0 error vector.
    """
    if isinstance(prediction, PredictionRecord):
        pred = prediction
    elif isinstance(prediction, Mapping):
        pred = PredictionRecord.from_dict(prediction)
    else:
        pred = PredictionRecord(policy="", expected={})

    observed_slots = _slot_map(observed)
    errors: dict[str, int] = {}
    for slot, expected_value in pred.expected.items():
        observed_value = observed_slots.get(slot)
        errors[slot] = 0 if observed_value == expected_value else 1

    return PredictionError(
        prediction=pred,
        observed=observed_slots,
        error_by_slot=errors,
        controller_step=_ctx_int(ctx, "controller_steps"),
        env_step=env_step,
    )


def compare_predicted_posture_to_observed(
    predicted_posture: str,
    observed_posture: str,
    *,
    policy: str = "",
    ctx: Any = None,
    source: str = "WorkingMap.Scratch",
    basis: Optional[Mapping[str, Any]] = None,
    env_step: Optional[int] = None,
) -> PredictionError:
    """Compatibility helper for the existing posture-only prediction-error path."""
    record = make_posture_prediction_record(
        policy,
        predicted_posture,
        ctx=ctx,
        source=source,
        basis=basis,
        env_step=env_step,
    )
    return compare_prediction_to_observed(record, {"posture": observed_posture}, ctx=ctx, env_step=env_step)


def legacy_error_vector_v0(error: PredictionError | Mapping[str, Any]) -> dict[str, int]:
    """Return the legacy integer error vector used by existing CCA8 traces.

    This is mainly ``{"posture": 0|1}`` in the first milestone, but it is kept
    generic so future slot families can reuse the same migration bridge.
    """
    if isinstance(error, PredictionError):
        return dict(error.error_by_slot)

    if isinstance(error, Mapping):
        raw = error.get("error_by_slot")
        out: dict[str, int] = {}
        if isinstance(raw, Mapping):
            for key, val in raw.items():
                if not isinstance(key, str):
                    continue
                try:
                    out[key] = int(val)
                except Exception:
                    out[key] = 1
        return out

    return {}
