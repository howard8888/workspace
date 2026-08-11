# -*- coding: utf-8 -*-
"""Prediction records and prediction-error helpers for CCA8.

Purpose
-------
The predictive-feedback subsystem is deliberately small and diagnostic:
make policy postcondition expectations explicit, compare those expectations with
later observations, maintain bounded runtime registers, and return JSON-safe
records that can be printed, logged, and tested without changing controller
behavior.

Design stance
-------------
- Predictions are hypotheses, not confirmed WorldGraph truth.
- The natural home for predictions is WorkingMap.Scratch / Creative; this
  module defines record shapes, comparison helpers, and bounded diagnostic
  runtime helpers.
- The legacy ``pred_err_v0`` posture vector remains supported so the current
  runner, JSONL records, and state-integrity summaries keep working.
- Runner-facing helpers live here rather than in ``cca8_run.py``; the runner
  re-exports their names for backward-compatible imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional


__version__ = "0.2.0"
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
    "latest_posture_binding_v1",
    "prediction_observed_slots_from_env_obs_v1",
    "prediction_error_history_append_v1",
    "prediction_error_record_apply_to_ctx_v1",
    "prediction_source_for_execution_target_v1",
    "prediction_next_record_from_policy_posture_v1",
    "prediction_pending_record_from_ctx_v1",
    "prediction_policy_expected_slots_v1",
    "prediction_record_with_expected_slots_v1",
    "prediction_compare_pending_to_observed_v1",
    "prediction_feedback_step_from_ctx_obs_v1",
    "compact_slot_map_text_v1",
    "prediction_feedback_summary_v1",
    "render_prediction_feedback_lines_v1",
    "prediction_feedback_mini_line_v1",
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


# -----------------------------------------------------------------------------
# Runner-facing predictive-feedback runtime helpers
# -----------------------------------------------------------------------------

def _sorted_binding_ids_v1(world: Any) -> list[str]:
    """Return binding ids in the runner's stable numeric-then-text order.

    This local helper keeps prediction capture independent of ``cca8_run.py``.
    It intentionally mirrors the runner's historical ``_sorted_bids`` ordering:
    ``b2`` precedes ``b10``, while non-numeric ids sort after numeric ids.
    """
    bindings = getattr(world, "_bindings", None)
    if not isinstance(bindings, Mapping):
        return []

    binding_ids = [binding_id for binding_id in bindings if isinstance(binding_id, str)]
    if len(binding_ids) != len(bindings):
        return []

    def key_fn(binding_id: str) -> tuple[int, int, str]:
        if binding_id.startswith("b") and binding_id[1:].isdigit():
            return (0, int(binding_id[1:]), "")
        return (1, 0, binding_id)

    return sorted(binding_ids, key=key_fn)


def latest_posture_binding_v1(
    world: Any,
    *,
    source: Optional[str] = None,
    require_policy: bool = False,
) -> tuple[Optional[str], Optional[str], Optional[dict[str, Any]]]:
    """
    Helper for mini-snapshots: find the most recent pred:posture:* binding.

    Args:
        source: if given, require binding.meta['source'] == source
                (e.g., 'HybridEnvironment' for env-driven facts).
        require_policy: if True, require binding.meta['policy'] to exist
                (policy-written expected posture).

    Returns:
        (bid, posture_tag, meta) or (None, None, None).
    """
    bindings = getattr(world, "_bindings", None)
    if not isinstance(bindings, Mapping):
        return None, None, None

    try:
        bids = _sorted_binding_ids_v1(world)
    except Exception:
        return None, None, None

    for bid in reversed(bids):
        b = bindings.get(bid)
        if not b:
            continue

        tags = getattr(b, "tags", None)
        if not tags:
            continue

        posture_tag = None
        for t in tags:
            if isinstance(t, str) and t.startswith("pred:posture:"):
                posture_tag = t
                break
        if not posture_tag:
            continue

        meta = getattr(b, "meta", None)

        if source is not None:
            if not isinstance(meta, dict) or meta.get("source") != source:
                continue

        if require_policy:
            if not isinstance(meta, dict) or "policy" not in meta:
                continue

        return bid, posture_tag, meta

    return None, None, None


def prediction_observed_slots_from_env_obs_v1(env_obs: Any) -> dict[str, str]:
    """Return the tiny observed slot map used by prediction-error records.

    The prediction layer should compare hypotheses against an agent-facing
    observation packet, not against a confirmed long-term WorldGraph fact. This
    helper extracts the first small map vocabulary that Step 3 cares about:

      - posture
      - mom_distance
      - nipple_state
      - zone

    Missing slots are left absent. A missing observed slot counts as a mismatch
    only when the prediction explicitly expected that slot.
    """
    if env_obs is None:
        return {}

    preds_raw = getattr(env_obs, "predicates", []) or []
    preds = {str(item).strip() for item in preds_raw if isinstance(item, str) and item.strip()}

    out: dict[str, str] = {}

    if "posture:standing" in preds:
        out["posture"] = "standing"
    elif "posture:fallen" in preds:
        out["posture"] = "fallen"
    elif "resting" in preds:
        out["posture"] = "resting"

    if "proximity:mom:close" in preds:
        out["mom_distance"] = "near"
    elif "proximity:mom:far" in preds:
        out["mom_distance"] = "far"

    if "nipple:latched" in preds:
        out["nipple_state"] = "latched"
    elif "nipple:found" in preds:
        out["nipple_state"] = "found"
    elif "nipple:hidden" in preds:
        out["nipple_state"] = "hidden"

    meta = getattr(env_obs, "env_meta", {}) or {}
    if isinstance(meta, dict):
        zone_val = meta.get("zone")
        if isinstance(zone_val, str) and zone_val.strip():
            out["zone"] = zone_val.strip()

        if "mom_distance" not in out:
            mom_val = meta.get("mom_proximity_from_raw")
            if isinstance(mom_val, str) and mom_val.strip() in ("near", "far"):
                out["mom_distance"] = mom_val.strip()
    return out


def _prediction_safe_dict_v1(value: Any) -> dict[str, Any]:
    """Return a shallow dict only when value is a dict.

    Prediction feedback records are deliberately stored on ctx as JSON-safe dicts.
    This helper keeps the readout layer defensive: malformed or missing values
    become an empty dict instead of crashing snapshot/mini-snapshot rendering.
    """
    return dict(value) if isinstance(value, dict) else {}


def _prediction_safe_history_count_v1(value: Any) -> int:
    """Return the number of stored prediction-error history rows."""
    return len(value) if isinstance(value, list) else 0


def prediction_error_history_append_v1(ctx: Any, error_record: Any, *, limit: int = 50) -> int:
    """Append one prediction-error record to the bounded history buffer.

    Prediction-error history is a diagnostic/scratch trace, not long-term memory.
    This helper centralizes the small ring-buffer rule that was previously inline
    in the environment loop:

      - tolerate a missing or malformed existing history by starting a new list
      - append only JSON-like dict records
      - keep only the newest ``limit`` records

    The function returns the resulting history count. It does not update policy
    choice, skill values, WorldGraph facts, or prediction comparison results.
    """
    if ctx is None or not isinstance(error_record, dict):
        return 0

    hist = getattr(ctx, "prediction_error_history", [])
    if not isinstance(hist, list):
        hist = []

    try:
        cap = int(limit)
    except Exception:
        cap = 50
    cap = max(1, cap)

    hist.append(dict(error_record))
    if len(hist) > cap:
        del hist[:-cap]

    ctx.prediction_error_history = hist
    return len(hist)


def prediction_error_record_apply_to_ctx_v1(ctx: Any, error_record: Any, *, limit: int = 50) -> dict[str, int]:
    """Store one prediction-error record in the runner's diagnostic registers.

    This helper centralizes the write-back part of the predictive-feedback
    display path. It accepts either a ``PredictionError``-like object with
    ``as_dict()`` or an already JSON-safe dict, updates the legacy v0 vector,
    stores the v1 error record, and appends the bounded diagnostic history.

    The function does not update policy choice, skill values, WorldGraph facts,
    BodyMap state, or action selection. It only preserves the existing display
    and JSON-cycle bookkeeping behavior in one testable place.
    """
    if ctx is None:
        return {}

    as_dict = getattr(error_record, "as_dict", None)
    if callable(as_dict):
        try:
            payload = as_dict()
        except Exception:
            return {}
    elif isinstance(error_record, dict):
        payload = dict(error_record)
    else:
        return {}

    if not isinstance(payload, dict) or not payload:
        return {}

    err_vec = legacy_error_vector_v0(payload)
    ctx.pred_err_v0_last = dict(err_vec)
    ctx.prediction_last_error_record = dict(payload)

    try:
        prediction_error_history_append_v1(ctx, payload, limit=limit)
    except Exception:
        pass

    return dict(err_vec)


def prediction_source_for_execution_target_v1(
    ctx: Any,
    selection_world: Any,
    *,
    exec_world: Any = None,
) -> str:
    """Return the prediction-source label for the world that actually executed a policy.

    ``exec_world=None`` means execution occurred on ``selection_world``. This explicit
    resolution avoids labeling legacy WorldGraph execution as WorkingMap Scratch merely
    because ``None is not selection_world``. The helper is read-only and does not change
    prediction records, policy behavior, or either world.
    """
    actual_target = exec_world if exec_world is not None else selection_world
    active_working_world = getattr(ctx, "working_world", None) if ctx is not None else None
    if active_working_world is not None and actual_target is active_working_world:
        return "WorkingMap.Scratch"
    return "WorldGraph.policy_trace"


def prediction_next_record_from_policy_posture_v1(
    ctx: Any,
    world: Any,
    policy_name: Any,
    *,
    env_step: Optional[int] = None,
    source: str = "WorkingMap.Scratch",
) -> dict[str, Any]:
    """Return a next-step prediction record from the latest policy posture binding.

    This helper formalizes the runner boundary where a policy-written posture
    postcondition becomes a prediction hypothesis. It is intentionally read-only:
    it scans the supplied world, creates a JSON-safe prediction record if the
    latest policy posture binding belongs to ``policy_name``, and returns ``{}``
    when no valid match exists.

    The function does not update ctx, write memory, compare observations, or
    change policy selection. The caller remains responsible for assigning
    ``ctx.pred_next_posture`` and ``ctx.prediction_next_record``. When safe
    policy-level slot expectations exist, they are added without overwriting the
    explicitly captured posture postcondition.
    """
    if not isinstance(policy_name, str) or not policy_name:
        return {}
    if world is None:
        return {}

    binding_id, posture_tag, meta = latest_posture_binding_v1(world, require_policy=True)
    if not isinstance(posture_tag, str) or not posture_tag.startswith("pred:posture:"):
        return {}
    if not isinstance(meta, dict) or meta.get("policy") != policy_name:
        return {}

    expected_posture = posture_tag.split(":")[-1].strip()
    if not expected_posture:
        return {}

    pred_record = make_posture_prediction_record(
        policy_name,
        expected_posture,
        ctx=ctx,
        source=source,
        basis={
            "binding_id": binding_id,
            "posture_tag": posture_tag,
            "meta_policy": meta.get("policy"),
        },
        env_step=env_step,
    )
    policy_slots = prediction_policy_expected_slots_v1(policy_name, expected_posture=expected_posture)
    return prediction_record_with_expected_slots_v1(pred_record.as_dict(), policy_slots)


def prediction_pending_record_from_ctx_v1(ctx: Any, *, env_step: Optional[int] = None) -> dict[str, Any]:
    """Return the pending prediction record that should be compared this tick.

    The environment loop currently stores next-step predictions in two forms:

      - the formal v1 record at ``ctx.prediction_next_record``
      - the older posture-only fields ``ctx.pred_next_posture`` / ``ctx.pred_next_policy``

    This read-only helper preserves that compatibility rule while making the
    comparison boundary testable. A non-empty dict in ``prediction_next_record``
    wins. Otherwise the legacy posture fields are converted into the same
    JSON-safe ``PredictionRecord`` shape used by the v1 path and enriched with
    safe policy-level slot expectations when available. No policy choice,
    memory write, WorldGraph fact, or prediction history is changed here.
    """
    prediction_raw = getattr(ctx, "prediction_next_record", {})
    if isinstance(prediction_raw, dict) and prediction_raw:
        return dict(prediction_raw)

    pred_old = getattr(ctx, "pred_next_posture", None)
    src_old = getattr(ctx, "pred_next_policy", None)
    if isinstance(pred_old, str) and pred_old:
        legacy_record = make_posture_prediction_record(
            str(src_old or ""),
            pred_old,
            ctx=ctx,
            source="legacy:pred_next_posture",
            env_step=env_step,
        ).as_dict()
        policy_slots = prediction_policy_expected_slots_v1(str(src_old or ""), expected_posture=pred_old)
        return prediction_record_with_expected_slots_v1(legacy_record, policy_slots)

    return {}


def prediction_policy_expected_slots_v1(policy_name: Any, *, expected_posture: Any = None) -> dict[str, str]:
    """Return the first tiny map-slot expectations associated with a policy.

    This helper is deliberately conservative and not yet wired into live control.
    It gives CCA8 a tested place to name policy-level hypotheses beyond posture,
    while preserving the rule that predictions are hypotheses, not WorldGraph
    facts. Explicitly supplied posture wins over policy defaults.
    """
    out: dict[str, str] = {}

    if isinstance(expected_posture, str) and expected_posture.strip():
        out["posture"] = expected_posture.strip()

    if not isinstance(policy_name, str) or not policy_name:
        return out

    if policy_name in ("policy:stand_up", "policy:recover_fall"):
        out.setdefault("posture", "standing")
    elif policy_name == "policy:rest":
        out.setdefault("posture", "resting")
    elif policy_name == "policy:seek_nipple":
        out.setdefault("mom_distance", "near")
        out.setdefault("nipple_state", "found")
    elif policy_name == "policy:suckle":
        out.setdefault("nipple_state", "latched")

    return out


def prediction_record_with_expected_slots_v1(
    prediction_record: Any,
    expected_slots: Any,
    *,
    source: str = "policy_expected_slots_v1",
) -> dict[str, Any]:
    """Return a prediction record copy enriched with additional expected slots.

    Existing expected slots are preserved. This lets an explicit captured
    postcondition, such as ``posture=standing``, remain authoritative while
    future map-slot expectations can be added around it. The original record is
    not mutated.
    """
    if not isinstance(prediction_record, dict) or not prediction_record:
        return {}

    out = dict(prediction_record)

    expected_raw = out.get("expected")
    expected = dict(expected_raw) if isinstance(expected_raw, dict) else {}

    added: list[str] = []
    if isinstance(expected_slots, dict):
        for key, value in expected_slots.items():
            if not isinstance(key, str) or not key:
                continue
            if value is None:
                continue
            if key not in expected:
                expected[key] = str(value)
                added.append(key)

    out["expected"] = expected
    if added:
        basis_raw = out.get("basis")
        basis = dict(basis_raw) if isinstance(basis_raw, dict) else {}
        basis["slot_expectation_source"] = str(source or "policy_expected_slots_v1")
        basis["slot_expectation_added"] = sorted(added)
        out["basis"] = basis

    return out


def prediction_compare_pending_to_observed_v1(
    ctx: Any,
    prediction_raw: Any,
    env_obs: Any,
    *,
    env_step: Optional[int] = None,
) -> dict[str, Any]:
    """Compare one pending prediction record to one EnvObservation-like object.

    This read-only helper is the middle of the predictive-feedback diagnostic
    chain. It accepts the pending prediction record selected by
    ``prediction_pending_record_from_ctx_v1()``, extracts the observed slots
    from the current observation, and returns a JSON-safe comparison summary.

    The function deliberately does not write to ``ctx``, append history, update
    the skill ledger, write WorldGraph facts, or change action selection. The
    caller remains responsible for applying the returned ``error_record`` with
    ``prediction_error_record_apply_to_ctx_v1()``.
    """
    empty_result: dict[str, Any] = {
        "schema": "prediction_comparison_result_v1",
        "has_prediction": False,
        "observed_slots": {},
        "error_record": {},
        "err_vec": {},
        "pred_posture": None,
        "obs_posture": None,
        "source_policy": None,
        "matched": None,
    }

    if not isinstance(prediction_raw, dict) or not prediction_raw:
        return empty_result

    observed_slots = prediction_observed_slots_from_env_obs_v1(env_obs)
    pred_error = compare_prediction_to_observed(
        prediction_raw,
        observed_slots,
        ctx=ctx,
        env_step=env_step,
    )
    error_record = pred_error.as_dict()
    err_vec = legacy_error_vector_v0(error_record)

    pred_posture_raw = pred_error.prediction.expected.get("posture")
    pred_posture: Optional[str] = (
        pred_posture_raw
        if isinstance(pred_posture_raw, str) and pred_posture_raw
        else None
    )

    source_policy_raw = pred_error.prediction.policy
    source_policy: Optional[str] = source_policy_raw if source_policy_raw else None

    return {
        "schema": "prediction_comparison_result_v1",
        "has_prediction": True,
        "observed_slots": observed_slots,
        "error_record": error_record,
        "err_vec": err_vec,
        "pred_posture": pred_posture,
        "obs_posture": observed_slots.get("posture"),
        "source_policy": source_policy,
        "matched": pred_error.matched,
    }


def prediction_feedback_step_from_ctx_obs_v1(
    ctx: Any,
    env_obs: Any,
    *,
    env_step: Optional[int] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Run one diagnostic predictive-feedback step for the current observation.

    This is the runner-level bridge for the first predictive-coding milestone:

      pending prediction -> observed slots -> comparison -> diagnostic ctx write-back

    It intentionally remains a display/logging operation. It does not change
    policy selection, skill values, BodyMap state, WorldGraph facts, or action
    selection. When no pending prediction exists, the current error registers
    are cleared while the bounded history is left intact.
    """
    prediction_raw = prediction_pending_record_from_ctx_v1(ctx, env_step=env_step)
    comparison = prediction_compare_pending_to_observed_v1(
        ctx,
        prediction_raw,
        env_obs,
        env_step=env_step,
    )

    if comparison.get("has_prediction") is not True:
        if ctx is not None:
            ctx.pred_err_v0_last = {}
            ctx.prediction_last_error_record = {}
        return {
            "schema": "prediction_feedback_step_v1",
            "status": "idle",
            "has_prediction": False,
            "applied": False,
            "err_vec": {},
            "pred_posture": None,
            "obs_posture": None,
            "source_policy": None,
            "matched": None,
            "comparison": comparison,
        }

    err_vec = prediction_error_record_apply_to_ctx_v1(
        ctx,
        comparison.get("error_record", {}),
        limit=limit,
    )
    pred_raw = comparison.get("pred_posture")
    obs_raw = comparison.get("obs_posture")
    src_raw = comparison.get("source_policy")

    return {
        "schema": "prediction_feedback_step_v1",
        "status": "compared",
        "has_prediction": True,
        "applied": bool(ctx is not None and isinstance(comparison.get("error_record"), dict)),
        "err_vec": err_vec,
        "pred_posture": pred_raw if isinstance(pred_raw, str) and pred_raw else None,
        "obs_posture": obs_raw if isinstance(obs_raw, str) and obs_raw else None,
        "source_policy": src_raw if isinstance(src_raw, str) and src_raw else None,
        "matched": comparison.get("matched"),
        "comparison": comparison,
    }


def compact_slot_map_text_v1(value: Any) -> str:
    """Return a stable compact rendering of a small slot/error map."""
    if not isinstance(value, dict) or not value:
        return "(none)"

    parts: list[str] = []
    for key in sorted(value.keys()):
        if not isinstance(key, str):
            continue
        parts.append(f"{key}={value.get(key)}")

    return ", ".join(parts) if parts else "(none)"


def prediction_feedback_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return the read-only predictive-feedback register summary.

    This is a diagnostic/status view over fields already stored on ``Ctx``:
    ``prediction_next_record``, ``prediction_last_error_record``,
    ``prediction_error_history``, and ``pred_err_v0_last``. It does not compute a
    new prediction, compare observations, write memory, change policy selection,
    or update the skill ledger.
    """
    if ctx is None:
        return {
            "schema": "prediction_feedback_summary_v1",
            "status": "ctx_unavailable",
            "has_next_prediction": False,
            "has_last_error": False,
            "history_count": 0,
            "pred_err_v0": {},
            "next_policy": None,
            "next_expected": {},
            "next_source": None,
            "next_controller_step": None,
            "next_env_step": None,
            "last_policy": None,
            "last_expected": {},
            "last_observed": {},
            "last_error_by_slot": {},
            "last_matched": None,
            "last_mismatch_count": 0,
            "last_severity": 0.0,
            "last_controller_step": None,
            "last_env_step": None,
        }

    next_record = _prediction_safe_dict_v1(getattr(ctx, "prediction_next_record", {}))
    last_error = _prediction_safe_dict_v1(getattr(ctx, "prediction_last_error_record", {}))
    pred_err_v0 = _prediction_safe_dict_v1(getattr(ctx, "pred_err_v0_last", {}))
    history_count = _prediction_safe_history_count_v1(getattr(ctx, "prediction_error_history", []))

    next_expected = _prediction_safe_dict_v1(next_record.get("expected"))

    pred_block = _prediction_safe_dict_v1(last_error.get("prediction"))
    last_expected = _prediction_safe_dict_v1(pred_block.get("expected"))
    last_observed = _prediction_safe_dict_v1(last_error.get("observed"))
    last_error_by_slot = _prediction_safe_dict_v1(last_error.get("error_by_slot"))

    mismatch_raw = last_error.get("mismatch_count", 0)
    try:
        mismatch_count = int(mismatch_raw)
    except Exception:
        mismatch_count = 0

    severity_raw = last_error.get("severity", float(mismatch_count))
    try:
        severity = float(severity_raw)
    except Exception:
        severity = float(mismatch_count)

    matched_raw = last_error.get("matched")
    matched = matched_raw if isinstance(matched_raw, bool) else None

    status = "idle"
    if next_record or last_error or history_count or pred_err_v0:
        status = "active"

    return {
        "schema": "prediction_feedback_summary_v1",
        "status": status,
        "has_next_prediction": bool(next_record),
        "has_last_error": bool(last_error),
        "history_count": int(history_count),
        "pred_err_v0": pred_err_v0,
        "next_policy": next_record.get("policy") if isinstance(next_record.get("policy"), str) else None,
        "next_expected": next_expected,
        "next_source": next_record.get("source") if isinstance(next_record.get("source"), str) else None,
        "next_controller_step": next_record.get("controller_step"),
        "next_env_step": next_record.get("env_step"),
        "last_policy": pred_block.get("policy") if isinstance(pred_block.get("policy"), str) else None,
        "last_expected": last_expected,
        "last_observed": last_observed,
        "last_error_by_slot": last_error_by_slot,
        "last_matched": matched,
        "last_mismatch_count": int(mismatch_count),
        "last_severity": float(severity),
        "last_controller_step": last_error.get("controller_step"),
        "last_env_step": last_error.get("env_step"),
    }


def render_prediction_feedback_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for the predictive-feedback register."""
    s = prediction_feedback_summary_v1(ctx)
    lines: list[str] = []

    lines.append("PREDICTION FEEDBACK:")
    lines.append(
        "  "
        f"status={s['status']} "
        f"history_count={s['history_count']} "
        f"pred_err_v0={{{compact_slot_map_text_v1(s['pred_err_v0'])}}} "
        "[src=ctx.pred_err_v0_last]"
    )

    if s["has_next_prediction"]:
        lines.append(
            "  next: "
            f"policy={s['next_policy'] or '(n/a)'} "
            f"expected={{{compact_slot_map_text_v1(s['next_expected'])}}} "
            f"source={s['next_source'] or '(n/a)'} "
            f"controller_step={s['next_controller_step']} env_step={s['next_env_step']} "
            "[src=ctx.prediction_next_record]"
        )
    else:
        lines.append("  next: (none)  [src=ctx.prediction_next_record]")

    if s["has_last_error"]:
        lines.append(
            "  last_error: "
            f"policy={s['last_policy'] or '(n/a)'} "
            f"matched={s['last_matched']} "
            f"mismatch_count={s['last_mismatch_count']} "
            f"severity={s['last_severity']:.2f} "
            f"errors={{{compact_slot_map_text_v1(s['last_error_by_slot'])}}} "
            "[src=ctx.prediction_last_error_record]"
        )
        lines.append(
            "  observed: "
            f"{{{compact_slot_map_text_v1(s['last_observed'])}}} "
            f"expected={{{compact_slot_map_text_v1(s['last_expected'])}}}"
        )
    else:
        lines.append("  last_error: (none)  [src=ctx.prediction_last_error_record]")

    return lines


def prediction_feedback_mini_line_v1(ctx: Any) -> str:
    """Return a one-line predictive-feedback readout for mini-snapshots."""
    s = prediction_feedback_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[pred] ctx unavailable"

    next_txt = "none"
    if s["has_next_prediction"]:
        next_txt = f"{s['next_policy'] or '?'} expected={{{compact_slot_map_text_v1(s['next_expected'])}}}"

    last_txt = "none"
    if s["has_last_error"]:
        last_txt = (
            f"matched={s['last_matched']} mismatches={s['last_mismatch_count']} "
            f"severity={s['last_severity']:.2f} errors={{{compact_slot_map_text_v1(s['last_error_by_slot'])}}}"
        )

    return f"[pred] status={s['status']} next={next_txt}; last={last_txt}; history_count={s['history_count']}"
