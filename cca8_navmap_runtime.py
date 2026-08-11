# -*- coding: utf-8 -*-
"""Runner-facing NavMap runtime integration and diagnostic reporting for CCA8.

Purpose
-------
This module owns the ctx-local NavMap runtime bridge that was historically
embedded in ``cca8_run.py``. It coordinates the existing pure NavMap schemas and
operators with CCA8 runtime registers for:

- observation-update candidate storage and bounded histories
- expected-current construction and residual comparison
- conservative accepted-current selection
- the diagnostic Working Navigation Map surface bridge
- action-conditioned transitions and policy-outcome indexing
- terminal summaries, mini-lines, and the NavMap Oscilloscope

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. It depends only on stable CCA8 data
records and helper modules. ``cca8_run`` re-exports the historical names as
compatibility aliases, keeping imports and current tests unchanged while the
runner remains focused on orchestration.

Authority boundary
------------------
The extracted path remains diagnostic and behavior-preserving. Accepted-current
continues to prefer direct observed evidence; the Working Navigation Map surface
record does not write WorldGraph truth, Columns, BodyMap, or policy-selection
state. Moving this code changes ownership, not cognitive authority.
"""

from __future__ import annotations

# The extracted runtime preserves the intentionally defensive implementation
# that previously lived in cca8_run.py.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements

from datetime import datetime
from typing import Any, Optional

from cca8_context import Ctx
from cca8_env import EnvObservation
from cca8_navmap import (
    make_navmap_payload_v1,
    make_navmap_transition_v1,
    navmap_observation_update_from_env_obs_v1,
    navmap_policy_outcome_from_transition_v1,
    navmap_residual_v1,
)
from cca8_predictive import (
    compact_slot_map_text_v1 as _prediction_compact_map_text_v1,
    prediction_policy_expected_slots_v1,
)


__version__ = "0.1.0"
__all__ = [
    "NAVMAP_SCOPE_MARKER_V1",
    "NAVMAP_SCOPE_PROBES_V1",
    "navmap_observation_update_summary_v1",
    "render_navmap_observation_update_lines_v1",
    "navmap_observation_update_mini_line_v1",
    "navmap_observation_update_history_append_v1",
    "navmap_expected_current_summary_v1",
    "render_navmap_expected_current_lines_v1",
    "navmap_expected_current_mini_line_v1",
    "navmap_expected_current_history_append_v1",
    "navmap_accepted_current_history_append_v1",
    "navmap_accepted_current_from_comparison_v1",
    "navmap_accepted_current_summary_v1",
    "render_navmap_accepted_current_lines_v1",
    "navmap_accepted_current_mini_line_v1",
    "working_navmap_surface_history_append_v1",
    "working_navmap_surface_from_accepted_current_v1",
    "working_navmap_surface_summary_v1",
    "render_working_navmap_surface_lines_v1",
    "working_navmap_surface_mini_line_v1",
    "navmap_expected_current_payload_from_ctx_v1",
    "navmap_expected_current_comparison_step_v1",
    "navmap_transition_summary_v1",
    "render_navmap_transition_lines_v1",
    "navmap_transition_mini_line_v1",
    "navmap_scope_frame_v1",
    "navmap_scope_frame_is_complete_v1",
    "navmap_scope_missing_probe_reasons_v1",
    "render_navmap_scope_frame_lines_v1",
    "render_navmap_scope_legend_lines_v1",
    "navmap_scope_mini_line_v1",
    "navmap_transition_history_append_v1",
    "navmap_policy_outcome_index_update_v1",
    "navmap_ctx_observation_update_step_v1",
    "navmap_ctx_transition_from_payloads_v1",
    "__version__",
]


def _navmap_safe_dict_v1(value: Any) -> dict[str, Any]:
    """Return a shallow dict only when value is a dict."""
    return dict(value) if isinstance(value, dict) else {}


def _navmap_safe_list_count_v1(value: Any) -> int:
    """Return the length of a list-like diagnostic buffer."""
    return len(value) if isinstance(value, list) else 0


def _navmap_safe_int_v1(value: Any, default: int = 0) -> int:
    """Return an int for ordinary scalar values, excluding bools."""
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _navmap_safe_float_or_none_v1(value: Any) -> Optional[float]:
    """Return a float for ordinary scalar values, or None when unavailable."""
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def navmap_observation_update_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only summary of the runner's last scene_body NavMap update."""
    base: dict[str, Any] = {
        "schema": "navmap_observation_update_summary_v1",
        "status": "idle",
        "has_last_update": False,
        "action": None,
        "matched": None,
        "changed": None,
        "candidate_count_before": 0,
        "candidate_count_after": 0,
        "candidate_store_count": 0,
        "history_count": 0,
        "candidate_index": None,
        "match_score": None,
        "residual_count": 0,
        "slot_count": 0,
        "slots": {},
        "created_at": None,
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    base["candidate_store_count"] = _navmap_safe_list_count_v1(
        getattr(ctx, "navmap_scene_body_candidates_v1", [])
    )
    base["history_count"] = _navmap_safe_list_count_v1(
        getattr(ctx, "navmap_observation_update_history_v1", [])
    )

    update = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_observation_update_v1", {}))
    if not update:
        return base

    current_payload = _navmap_safe_dict_v1(update.get("current_payload"))
    slots_raw = _navmap_safe_dict_v1(current_payload.get("slots"))
    slots = {str(key): value for key, value in slots_raw.items() if isinstance(key, str)}

    cycle = _navmap_safe_dict_v1(update.get("cycle"))
    match = _navmap_safe_dict_v1(cycle.get("match"))
    proposal = _navmap_safe_dict_v1(cycle.get("proposal"))
    residual = _navmap_safe_dict_v1(proposal.get("residual"))
    if not residual:
        residual = _navmap_safe_dict_v1(match.get("residual"))
    store_update = _navmap_safe_dict_v1(update.get("store_update"))

    action_raw = update.get("action") or store_update.get("action") or cycle.get("action")
    candidate_index_raw = store_update.get("candidate_index")
    if candidate_index_raw is None:
        candidate_index_raw = proposal.get("candidate_index")
    if candidate_index_raw is None:
        candidate_index_raw = match.get("candidate_index")

    out = dict(base)
    out.update(
        {
            "status": "active",
            "has_last_update": True,
            "action": action_raw if isinstance(action_raw, str) and action_raw else None,
            "matched": update.get("matched") if isinstance(update.get("matched"), bool) else None,
            "changed": update.get("changed") if isinstance(update.get("changed"), bool) else None,
            "candidate_count_before": _navmap_safe_int_v1(
                update.get("candidate_count_before"),
                _navmap_safe_int_v1(store_update.get("before_count"), 0),
            ),
            "candidate_count_after": _navmap_safe_int_v1(
                update.get("candidate_count_after"),
                _navmap_safe_int_v1(store_update.get("after_count"), 0),
            ),
            "candidate_index": _navmap_safe_int_v1(candidate_index_raw, -1),
            "match_score": _navmap_safe_float_or_none_v1(match.get("score")),
            "residual_count": _navmap_safe_int_v1(residual.get("residual_count"), 0),
            "slot_count": len(slots),
            "slots": slots,
            "created_at": update.get("created_at") if isinstance(update.get("created_at"), str) else None,
        }
    )
    if out["candidate_index"] < 0:
        out["candidate_index"] = None
    return out


def render_navmap_observation_update_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for the runner's scene_body NavMap diagnostic."""
    s = navmap_observation_update_summary_v1(ctx)
    lines: list[str] = ["NAVMAP OBSERVATION UPDATE:"]

    if s["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if not s["has_last_update"]:
        lines.append(
            "  status=idle "
            f"candidate_store_count={s['candidate_store_count']} "
            f"history_count={s['history_count']} "
            "[src=ctx.navmap_last_observation_update_v1]"
        )
        return lines

    score = s["match_score"]
    score_txt = f"{score:.2f}" if isinstance(score, float) else "n/a"
    lines.append(
        "  "
        f"status={s['status']} "
        f"action={s['action'] or '(n/a)'} "
        f"matched={s['matched']} "
        f"changed={s['changed']} "
        f"residual_count={s['residual_count']} "
        f"match_score={score_txt} "
        "[src=ctx.navmap_last_observation_update_v1]"
    )
    lines.append(
        "  "
        f"candidates={s['candidate_count_before']}->{s['candidate_count_after']} "
        f"store_count={s['candidate_store_count']} "
        f"history_count={s['history_count']} "
        f"candidate_index={s['candidate_index']}"
    )
    lines.append(
        "  "
        f"current_slots={{{_prediction_compact_map_text_v1(s['slots'])}}} "
        f"slot_count={s['slot_count']}"
    )
    return lines


def navmap_observation_update_mini_line_v1(ctx: Any) -> str:
    """Return a one-line NavMap readout for mini-snapshots."""
    s = navmap_observation_update_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[navmap] ctx unavailable"

    if not s["has_last_update"]:
        return (
            "[navmap] status=idle "
            f"store_count={s['candidate_store_count']} history_count={s['history_count']}"
        )

    return (
        "[navmap] "
        f"action={s['action'] or '(n/a)'} "
        f"matched={s['matched']} changed={s['changed']} "
        f"residuals={s['residual_count']} slots={{{_prediction_compact_map_text_v1(s['slots'])}}} "
        f"candidates={s['candidate_count_before']}->{s['candidate_count_after']} "
        f"history_count={s['history_count']}"
    )


def _navmap_slots_from_payload_dict_v1(payload: Any) -> dict[str, Any]:
    """Return a shallow slot map from a JSON-safe NavMap payload dict."""
    payload_dict = _navmap_safe_dict_v1(payload)
    slots = _navmap_safe_dict_v1(payload_dict.get("slots"))
    return {str(key): value for key, value in slots.items() if isinstance(key, str)}


def _navmap_transition_slot_change_text_v1(slot_changes: Any) -> str:
    """Return compact text for a NavMap policy-outcome slot-change map."""
    if not isinstance(slot_changes, dict) or not slot_changes:
        return "(none)"

    parts: list[str] = []
    for key in sorted(slot_changes):
        if not isinstance(key, str):
            continue
        val = slot_changes.get(key)
        if isinstance(val, dict):
            before = val.get("before", "")
            after = val.get("after", "")
            parts.append(f"{key}:{before}->{after}")
        else:
            parts.append(f"{key}:{val}")
    return ", ".join(parts) if parts else "(none)"


def _navmap_compact_list_text_v1(value: Any) -> str:
    """Return compact text for a small diagnostic list."""
    if not isinstance(value, list) or not value:
        return "(none)"

    parts: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            parts.append(text)
    return ", ".join(parts) if parts else "(none)"


def navmap_expected_current_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only summary of expected-current NavMap predictive diagnostics."""
    base: dict[str, Any] = {
        "schema": "navmap_expected_current_summary_v1",
        "status": "idle",
        "has_last_comparison": False,
        "action": None,
        "reason": None,
        "residual_count": 0,
        "exact_match": None,
        "context_shift_recommended": False,
        "context_break_recommended": False,
        "history_count": 0,
        "expected_slots": {},
        "observed_slots": {},
        "evidence_override_slots": {},
        "safety_residual_slots": [],
        "created_at": None,
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    base["history_count"] = _navmap_safe_list_count_v1(
        getattr(ctx, "navmap_expected_current_history_v1", [])
    )

    comparison = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_expected_current_comparison_v1", {}))
    if not comparison:
        return base

    expected_payload = _navmap_safe_dict_v1(comparison.get("expected_payload"))
    observed_payload = _navmap_safe_dict_v1(comparison.get("observed_payload"))
    safety_slots_raw = comparison.get("safety_residual_slots")
    safety_slots = [str(item) for item in safety_slots_raw if isinstance(item, str)] if isinstance(
        safety_slots_raw, list
    ) else []

    status_raw = comparison.get("status")
    action_raw = comparison.get("action")
    reason_raw = comparison.get("reason")
    created_at_raw = comparison.get("created_at")
    exact_raw = comparison.get("exact_match")
    context_shift_raw = comparison.get("context_shift_recommended")
    context_break_raw = comparison.get("context_break_recommended")

    out = dict(base)
    out.update(
        {
            "status": status_raw if isinstance(status_raw, str) and status_raw else "active",
            "has_last_comparison": True,
            "action": action_raw if isinstance(action_raw, str) and action_raw else None,
            "reason": reason_raw if isinstance(reason_raw, str) and reason_raw else None,
            "residual_count": _navmap_safe_int_v1(comparison.get("residual_count"), 0),
            "exact_match": exact_raw if isinstance(exact_raw, bool) else None,
            "context_shift_recommended": (
                context_shift_raw if isinstance(context_shift_raw, bool) else False
            ),
            "context_break_recommended": (
                context_break_raw if isinstance(context_break_raw, bool) else False
            ),
            "expected_slots": _navmap_slots_from_payload_dict_v1(expected_payload),
            "observed_slots": _navmap_slots_from_payload_dict_v1(observed_payload),
            "evidence_override_slots": _navmap_safe_dict_v1(comparison.get("evidence_override_slots")),
            "safety_residual_slots": safety_slots,
            "created_at": created_at_raw if isinstance(created_at_raw, str) and created_at_raw else None,
        }
    )
    return out


def render_navmap_expected_current_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for expected-current NavMap predictive diagnostics."""
    s = navmap_expected_current_summary_v1(ctx)
    lines: list[str] = ["NAVMAP EXPECTED-CURRENT:"]

    if s["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if not s["has_last_comparison"]:
        lines.append(
            "  status=idle "
            f"history_count={s['history_count']} "
            "[src=ctx.navmap_last_expected_current_comparison_v1]"
        )
        return lines

    lines.append(
        "  "
        f"status={s['status']} "
        f"action={s['action'] or '(none)'} "
        f"residual_count={s['residual_count']} "
        f"exact_match={s['exact_match']} "
        f"context_shift={s['context_shift_recommended']} "
        f"context_break={s['context_break_recommended']} "
        "[src=ctx.navmap_last_expected_current_comparison_v1]"
    )
    lines.append(
        "  "
        f"expected={{{_prediction_compact_map_text_v1(s['expected_slots'])}}} "
        f"observed={{{_prediction_compact_map_text_v1(s['observed_slots'])}}}"
    )
    lines.append(
        "  "
        f"evidence_override={{{_prediction_compact_map_text_v1(s['evidence_override_slots'])}}} "
        f"safety_slots={{{_navmap_compact_list_text_v1(s['safety_residual_slots'])}}} "
        f"history_count={s['history_count']} "
        f"reason={s['reason'] or '(n/a)'}"
    )
    return lines


def navmap_expected_current_mini_line_v1(ctx: Any) -> str:
    """Return a one-line expected-current NavMap readout for mini-snapshots."""
    s = navmap_expected_current_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[navmap-expected] ctx unavailable"

    if not s["has_last_comparison"]:
        return f"[navmap-expected] status=idle history_count={s['history_count']}"

    return (
        "[navmap-expected] "
        f"status={s['status']} "
        f"action={s['action'] or '(none)'} "
        f"residuals={s['residual_count']} "
        f"shift={s['context_shift_recommended']} "
        f"break={s['context_break_recommended']} "
        f"expected={{{_prediction_compact_map_text_v1(s['expected_slots'])}}} "
        f"observed={{{_prediction_compact_map_text_v1(s['observed_slots'])}}} "
        f"overrides={{{_prediction_compact_map_text_v1(s['evidence_override_slots'])}}} "
        f"history_count={s['history_count']}"
    )


def navmap_accepted_current_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only summary of the accepted-current NavMap diagnostic.

    Accepted-current is the conservative handoff point between residual checking
    and the future WorkingMap bridge. This summary intentionally reads only the
    existing ctx register written by ``navmap_accepted_current_from_comparison_v1``.
    It does not run a new comparison, mutate ctx, append history, or write memory.
    """
    base: dict[str, Any] = {
        "schema": "navmap_accepted_current_summary_v1",
        "status": "idle",
        "has_last_accepted_current": False,
        "acceptance": None,
        "action": None,
        "comparison_status": None,
        "comparison_reason": None,
        "residual_count": 0,
        "exact_match": None,
        "context_shift_recommended": False,
        "context_break_recommended": False,
        "history_count": 0,
        "accepted_slots": {},
        "observed_slots": {},
        "expected_slots": {},
        "evidence_override_slots": {},
        "safety_residual_slots": [],
        "created_at": None,
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    base["history_count"] = _navmap_safe_list_count_v1(
        getattr(ctx, "navmap_accepted_current_history_v1", [])
    )

    record = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_accepted_current_v1", {}))
    if not record:
        return base

    accepted_payload = _navmap_safe_dict_v1(record.get("accepted_payload"))
    expected_payload = _navmap_safe_dict_v1(record.get("expected_payload"))
    accepted_slots = _navmap_slots_from_payload_dict_v1(accepted_payload)
    observed_slots = _navmap_safe_dict_v1(record.get("observed_slots"))
    expected_slots = _navmap_safe_dict_v1(record.get("expected_slots"))
    if not observed_slots:
        observed_slots = dict(accepted_slots)
    if not accepted_slots:
        accepted_slots = dict(observed_slots)
    if not expected_slots:
        expected_slots = _navmap_slots_from_payload_dict_v1(expected_payload)

    safety_slots_raw = record.get("safety_residual_slots")
    safety_slots = [str(item) for item in safety_slots_raw if isinstance(item, str)] if isinstance(
        safety_slots_raw, list
    ) else []

    acceptance_raw = record.get("acceptance")
    action_raw = record.get("action")
    status_raw = record.get("comparison_status")
    reason_raw = record.get("comparison_reason")
    created_at_raw = record.get("created_at")
    exact_raw = record.get("exact_match")
    context_shift_raw = record.get("context_shift_recommended")
    context_break_raw = record.get("context_break_recommended")

    out = dict(base)
    out.update(
        {
            "status": "active",
            "has_last_accepted_current": True,
            "acceptance": acceptance_raw if isinstance(acceptance_raw, str) and acceptance_raw else None,
            "action": action_raw if isinstance(action_raw, str) and action_raw else None,
            "comparison_status": status_raw if isinstance(status_raw, str) and status_raw else None,
            "comparison_reason": reason_raw if isinstance(reason_raw, str) and reason_raw else None,
            "residual_count": _navmap_safe_int_v1(record.get("residual_count"), 0),
            "exact_match": exact_raw if isinstance(exact_raw, bool) else None,
            "context_shift_recommended": context_shift_raw if isinstance(context_shift_raw, bool) else False,
            "context_break_recommended": context_break_raw if isinstance(context_break_raw, bool) else False,
            "accepted_slots": accepted_slots,
            "observed_slots": observed_slots,
            "expected_slots": expected_slots,
            "evidence_override_slots": _navmap_safe_dict_v1(record.get("evidence_override_slots")),
            "safety_residual_slots": safety_slots,
            "created_at": created_at_raw if isinstance(created_at_raw, str) and created_at_raw else None,
        }
    )
    return out


def render_navmap_accepted_current_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for accepted-current NavMap diagnostics."""
    s = navmap_accepted_current_summary_v1(ctx)
    lines: list[str] = ["NAVMAP ACCEPTED-CURRENT:"]

    if s["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if not s["has_last_accepted_current"]:
        lines.append(
            "  status=idle "
            f"history_count={s['history_count']} "
            "[src=ctx.navmap_last_accepted_current_v1]"
        )
        return lines

    lines.append(
        "  "
        f"status={s['status']} "
        f"acceptance={s['acceptance'] or '(none)'} "
        f"action={s['action'] or '(none)'} "
        f"residual_count={s['residual_count']} "
        f"exact_match={s['exact_match']} "
        f"context_shift={s['context_shift_recommended']} "
        f"context_break={s['context_break_recommended']} "
        "[src=ctx.navmap_last_accepted_current_v1]"
    )
    lines.append(
        "  "
        f"accepted={{{_prediction_compact_map_text_v1(s['accepted_slots'])}}} "
        f"expected={{{_prediction_compact_map_text_v1(s['expected_slots'])}}} "
        f"observed={{{_prediction_compact_map_text_v1(s['observed_slots'])}}}"
    )
    lines.append(
        "  "
        f"evidence_override={{{_prediction_compact_map_text_v1(s['evidence_override_slots'])}}} "
        f"safety_slots={{{_navmap_compact_list_text_v1(s['safety_residual_slots'])}}} "
        f"history_count={s['history_count']} "
        f"comparison_status={s['comparison_status'] or '(n/a)'} "
        f"reason={s['comparison_reason'] or '(n/a)'}"
    )
    return lines


def navmap_accepted_current_mini_line_v1(ctx: Any) -> str:
    """Return a one-line accepted-current NavMap readout for mini-snapshots."""
    s = navmap_accepted_current_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[navmap-accepted] ctx unavailable"

    if not s["has_last_accepted_current"]:
        return f"[navmap-accepted] status=idle history_count={s['history_count']}"

    return (
        "[navmap-accepted] "
        f"acceptance={s['acceptance'] or '(none)'} "
        f"action={s['action'] or '(none)'} "
        f"residuals={s['residual_count']} "
        f"shift={s['context_shift_recommended']} "
        f"break={s['context_break_recommended']} "
        f"accepted={{{_prediction_compact_map_text_v1(s['accepted_slots'])}}} "
        f"overrides={{{_prediction_compact_map_text_v1(s['evidence_override_slots'])}}} "
        f"history_count={s['history_count']}"
    )


def working_navmap_surface_history_append_v1(
    history: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return a bounded Working NavMap surface history without mutating inputs."""
    return navmap_observation_update_history_append_v1(history, record, limit=limit)


def working_navmap_surface_from_accepted_current_v1(ctx: Any, accepted_record: dict[str, Any]) -> dict[str, Any]:
    """Copy accepted-current into a ctx-local Working NavMap surface register.

    This is the first explicit handoff seam from the NavMap predictive path toward
    a future WorkingMap / Navigation Module surface. It is deliberately diagnostic-only:
    it copies the existing accepted-current payload into ``ctx.working_navmap_surface_v1``
    and appends a bounded ctx-local history. It does not write WorldGraph facts,
    write Column engrams, alter ``ctx.working_world``, update BodyMap, choose policies,
    or change the accepted-current semantics.
    """
    if ctx is None or not isinstance(accepted_record, dict) or not accepted_record:
        return {}

    accepted_payload = _navmap_safe_dict_v1(accepted_record.get("accepted_payload"))
    if not accepted_payload:
        return {}

    slots = _navmap_slots_from_payload_dict_v1(accepted_payload)
    if not slots:
        slots = _navmap_safe_dict_v1(accepted_record.get("observed_slots"))

    created_at_raw = accepted_record.get("created_at")
    acceptance_raw = accepted_record.get("acceptance")
    action_raw = accepted_record.get("action")

    record = {
        "schema": "working_navmap_surface_v1",
        "status": "active",
        "surface_kind": "scene_body",
        "bridge_role": "accepted_current_to_workingmap_candidate",
        "source_register": "ctx.navmap_last_accepted_current_v1",
        "writes_enabled": False,
        "used_for_policy_selection": False,
        "used_for_worldgraph_truth": False,
        "used_for_column_write": False,
        "acceptance": acceptance_raw if isinstance(acceptance_raw, str) and acceptance_raw else None,
        "action": action_raw if isinstance(action_raw, str) and action_raw else None,
        "accepted_payload": dict(accepted_payload),
        "slots": dict(slots),
        "slot_signature": _navmap_slot_signature_from_slots_v1(slots),
        "residual_count": _navmap_safe_int_v1(accepted_record.get("residual_count"), 0),
        "context_shift_recommended": bool(accepted_record.get("context_shift_recommended")),
        "context_break_recommended": bool(accepted_record.get("context_break_recommended")),
        "evidence_override_slots": _navmap_safe_dict_v1(accepted_record.get("evidence_override_slots")),
        "created_at": created_at_raw if isinstance(created_at_raw, str) and created_at_raw else datetime.now().isoformat(),
    }

    try:
        ctx.working_navmap_surface_v1 = dict(record)

        history_limit = _navmap_safe_int_v1(getattr(ctx, "working_navmap_surface_history_limit_v1", 25), 25)
        if history_limit <= 0:
            history_limit = 25
        ctx.working_navmap_surface_history_v1 = working_navmap_surface_history_append_v1(
            getattr(ctx, "working_navmap_surface_history_v1", []),
            record,
            limit=history_limit,
        )
    except Exception:
        return {}

    return record


def working_navmap_surface_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only summary of the diagnostic Working NavMap surface bridge."""
    base: dict[str, Any] = {
        "schema": "working_navmap_surface_summary_v1",
        "status": "idle",
        "has_surface": False,
        "surface_kind": None,
        "bridge_role": None,
        "source_register": None,
        "acceptance": None,
        "action": None,
        "residual_count": 0,
        "context_shift_recommended": False,
        "context_break_recommended": False,
        "writes_enabled": False,
        "used_for_policy_selection": False,
        "used_for_worldgraph_truth": False,
        "used_for_column_write": False,
        "history_count": 0,
        "slot_count": 0,
        "slot_signature": "",
        "slots": {},
        "evidence_override_slots": {},
        "created_at": None,
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    base["history_count"] = _navmap_safe_list_count_v1(getattr(ctx, "working_navmap_surface_history_v1", []))

    record = _navmap_safe_dict_v1(getattr(ctx, "working_navmap_surface_v1", {}))
    if not record:
        return base

    slots = _navmap_safe_dict_v1(record.get("slots"))
    if not slots:
        slots = _navmap_slots_from_payload_dict_v1(record.get("accepted_payload"))

    out = dict(base)
    out.update(
        {
            "status": "active",
            "has_surface": True,
            "surface_kind": record.get("surface_kind") if isinstance(record.get("surface_kind"), str) else None,
            "bridge_role": record.get("bridge_role") if isinstance(record.get("bridge_role"), str) else None,
            "source_register": record.get("source_register") if isinstance(record.get("source_register"), str) else None,
            "acceptance": record.get("acceptance") if isinstance(record.get("acceptance"), str) else None,
            "action": record.get("action") if isinstance(record.get("action"), str) else None,
            "residual_count": _navmap_safe_int_v1(record.get("residual_count"), 0),
            "context_shift_recommended": bool(record.get("context_shift_recommended")),
            "context_break_recommended": bool(record.get("context_break_recommended")),
            "writes_enabled": bool(record.get("writes_enabled")),
            "used_for_policy_selection": bool(record.get("used_for_policy_selection")),
            "used_for_worldgraph_truth": bool(record.get("used_for_worldgraph_truth")),
            "used_for_column_write": bool(record.get("used_for_column_write")),
            "slot_count": len(slots),
            "slot_signature": str(record.get("slot_signature") or ""),
            "slots": slots,
            "evidence_override_slots": _navmap_safe_dict_v1(record.get("evidence_override_slots")),
            "created_at": record.get("created_at") if isinstance(record.get("created_at"), str) else None,
        }
    )
    return out


def render_working_navmap_surface_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for the diagnostic Working NavMap surface bridge."""
    s = working_navmap_surface_summary_v1(ctx)
    lines: list[str] = ["WORKING NAVMAP SURFACE:"]

    if s["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if not s["has_surface"]:
        lines.append(
            "  status=idle "
            f"history_count={s['history_count']} "
            "[src=ctx.working_navmap_surface_v1]"
        )
        lines.append("  note=diagnostic-only bridge; waiting for accepted-current NavMap")
        return lines

    lines.append(
        "  "
        f"status={s['status']} "
        f"kind={s['surface_kind'] or '(none)'} "
        f"role={s['bridge_role'] or '(none)'} "
        f"acceptance={s['acceptance'] or '(none)'} "
        f"action={s['action'] or '(none)'} "
        f"residual_count={s['residual_count']} "
        "[src=ctx.working_navmap_surface_v1]"
    )
    lines.append(
        "  "
        f"slots={{{_prediction_compact_map_text_v1(s['slots'])}}} "
        f"slot_count={s['slot_count']} "
        f"signature={s['slot_signature'] or '(none)'}"
    )
    lines.append(
        "  "
        f"overrides={{{_prediction_compact_map_text_v1(s['evidence_override_slots'])}}} "
        f"shift={s['context_shift_recommended']} "
        f"break={s['context_break_recommended']} "
        f"history_count={s['history_count']}"
    )
    lines.append(
        "  "
        f"used_for_policy_selection={s['used_for_policy_selection']} "
        f"worldgraph_truth={s['used_for_worldgraph_truth']} "
        f"column_write={s['used_for_column_write']} "
        f"writes_enabled={s['writes_enabled']}"
    )
    return lines


def working_navmap_surface_mini_line_v1(ctx: Any) -> str:
    """Return a one-line Working NavMap surface bridge readout for mini-snapshots."""
    s = working_navmap_surface_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[working-navmap] ctx unavailable"

    if not s["has_surface"]:
        return f"[working-navmap] status=idle history_count={s['history_count']}"

    return (
        "[working-navmap] "
        f"role={s['bridge_role'] or '(none)'} "
        f"acceptance={s['acceptance'] or '(none)'} "
        f"action={s['action'] or '(none)'} "
        f"residuals={s['residual_count']} "
        f"slots={{{_prediction_compact_map_text_v1(s['slots'])}}} "
        f"policy_used={s['used_for_policy_selection']} "
        f"writes={s['writes_enabled']} "
        f"history_count={s['history_count']}"
    )


def navmap_transition_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only summary of the runner's last action-conditioned NavMap transition."""
    base: dict[str, Any] = {
        "schema": "navmap_transition_summary_v1",
        "status": "idle",
        "has_last_transition": False,
        "action": None,
        "reward": 0.0,
        "changed": None,
        "changed_slots": 0,
        "transition_history_count": 0,
        "policy_outcome_history_count": 0,
        "policy_outcome_index_count": 0,
        "indexed_sample_count": 0,
        "indexed_success_rate": 0.0,
        "indexed_mean_reward": 0.0,
        "before_slots": {},
        "after_slots": {},
        "slot_changes": {},
        "success": None,
        "confidence": None,
        "policy_key": None,
        "context_signature": None,
        "created_at": None,
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    base["transition_history_count"] = _navmap_safe_list_count_v1(getattr(ctx, "navmap_transition_history_v1", []))
    base["policy_outcome_history_count"] = _navmap_safe_list_count_v1(getattr(ctx, "navmap_policy_outcome_history_v1", []))
    raw_index = getattr(ctx, "navmap_policy_outcome_index_v1", {})
    base["policy_outcome_index_count"] = len(raw_index) if isinstance(raw_index, dict) else 0

    transition = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_transition_v1", {}))
    if not transition:
        return base

    outcome = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_policy_outcome_v1", {}))
    index_row = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_policy_outcome_index_row_v1", {}))
    action_raw = transition.get("action")
    changed_raw = transition.get("changed")
    success_raw = outcome.get("success")
    created_at_raw = transition.get("created_at")

    out = dict(base)
    out.update(
        {
            "status": "active",
            "has_last_transition": True,
            "action": action_raw if isinstance(action_raw, str) and action_raw else None,
            "reward": _navmap_safe_float_or_none_v1(transition.get("reward")) or 0.0,
            "changed": changed_raw if isinstance(changed_raw, bool) else None,
            "changed_slots": _navmap_safe_int_v1(transition.get("changed_slots"), 0),
            "indexed_sample_count": _navmap_safe_int_v1(index_row.get("sample_count"), 0),
            "indexed_success_rate": _navmap_safe_float_or_none_v1(index_row.get("success_rate")) or 0.0,
            "indexed_mean_reward": _navmap_safe_float_or_none_v1(index_row.get("mean_reward")) or 0.0,
            "before_slots": _navmap_slots_from_payload_dict_v1(transition.get("before_payload")),
            "after_slots": _navmap_slots_from_payload_dict_v1(transition.get("after_payload")),
            "slot_changes": _navmap_safe_dict_v1(outcome.get("slot_changes")),
            "success": success_raw if isinstance(success_raw, bool) else None,
            "confidence": _navmap_safe_float_or_none_v1(outcome.get("confidence")),
            "policy_key": outcome.get("policy_key") if isinstance(outcome.get("policy_key"), str) else None,
            "context_signature": (
                outcome.get("context_signature") if isinstance(outcome.get("context_signature"), str) else None
            ),
            "created_at": created_at_raw if isinstance(created_at_raw, str) and created_at_raw else None,
        }
    )
    return out


def render_navmap_transition_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable lines for the runner's action-conditioned NavMap transition."""
    s = navmap_transition_summary_v1(ctx)
    lines: list[str] = ["NAVMAP TRANSITION:"]

    if s["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if not s["has_last_transition"]:
        lines.append(
            "  status=idle "
            f"transition_history_count={s['transition_history_count']} "
            f"policy_outcome_history_count={s['policy_outcome_history_count']} "
            "[src=ctx.navmap_last_transition_v1]"
        )
        return lines

    confidence = s["confidence"]
    confidence_txt = f"{confidence:.2f}" if isinstance(confidence, float) else "n/a"
    lines.append(
        "  "
        f"status={s['status']} "
        f"action={s['action'] or '(none)'} "
        f"reward={s['reward']:.2f} "
        f"changed={s['changed']} "
        f"changed_slots={s['changed_slots']} "
        f"success={s['success']} "
        f"confidence={confidence_txt} "
        "[src=ctx.navmap_last_transition_v1]"
    )
    lines.append(
        "  "
        f"before={{{_prediction_compact_map_text_v1(s['before_slots'])}}} "
        f"after={{{_prediction_compact_map_text_v1(s['after_slots'])}}}"
    )
    lines.append(
        "  "
        f"slot_changes={{{_navmap_transition_slot_change_text_v1(s['slot_changes'])}}} "
        f"transition_history_count={s['transition_history_count']} "
        f"policy_outcome_history_count={s['policy_outcome_history_count']} "
        f"index_count={s['policy_outcome_index_count']} "
        f"indexed_samples={s['indexed_sample_count']} "
        f"indexed_success_rate={s['indexed_success_rate']:.2f} "
        f"indexed_mean_reward={s['indexed_mean_reward']:.2f}"
    )
    return lines


def navmap_transition_mini_line_v1(ctx: Any) -> str:
    """Return a one-line NavMap transition readout for mini-snapshots."""
    s = navmap_transition_summary_v1(ctx)

    if s["status"] == "ctx_unavailable":
        return "[navmap-transition] ctx unavailable"

    if not s["has_last_transition"]:
        return (
            "[navmap-transition] status=idle "
            f"history_count={s['transition_history_count']} "
            f"outcome_count={s['policy_outcome_history_count']}"
        )

    return (
        "[navmap-transition] "
        f"action={s['action'] or '(none)'} "
        f"reward={s['reward']:.2f} "
        f"changed_slots={s['changed_slots']} "
        f"success={s['success']} "
        f"before={{{_prediction_compact_map_text_v1(s['before_slots'])}}} "
        f"after={{{_prediction_compact_map_text_v1(s['after_slots'])}}} "
        f"history_count={s['transition_history_count']} "
        f"indexed_samples={s['indexed_sample_count']}"
    )


NAVMAP_SCOPE_MARKER_V1 = "(~~)"

NAVMAP_SCOPE_PROBES_V1 = (
    ("evidence", "has_evidence", "waiting for EnvObservation-derived evidence map"),
    ("expected", "has_expected", "first cycle or no selected-primitive prior yet"),
    ("residual", "has_residual", "waiting for expected-current vs evidence comparison"),
    ("accepted", "has_accepted", "waiting for accepted-current map diagnostic"),
    ("transition", "has_transition", "needs previous map + action + current map"),
    ("outcome", "has_policy_outcome", "needs transition policy-outcome sample/index row"),
)


def navmap_scope_missing_probe_reasons_v1(frame: dict[str, Any]) -> dict[str, str]:
    """Return a probe-name -> reason map for missing NavMap Oscilloscope probes.

    The oscilloscope is a read-only instrument. This helper inspects one already-built
    frame and explains why the six-probe signal path is incomplete. It does not read
    ctx directly, mutate runtime state, run new matching, append history, or write memory.
    """
    if not isinstance(frame, dict):
        return {name: reason for name, _key, reason in NAVMAP_SCOPE_PROBES_V1}

    reasons: dict[str, str] = {}
    for name, key, reason in NAVMAP_SCOPE_PROBES_V1:
        if not bool(frame.get(key)):
            reasons[name] = reason
    return reasons


def navmap_scope_frame_is_complete_v1(frame: dict[str, Any]) -> bool:
    """Return True when all six NavMap Oscilloscope probes are present.

    Complete means the current frame contains evidence, expected-current, residual,
    accepted-current, transition, and policy-outcome/index signals. This is a
    display/readiness check only; it does not imply the map is correct or safe.
    """
    if not isinstance(frame, dict):
        return False
    return not navmap_scope_missing_probe_reasons_v1(frame)


def _navmap_scope_compact_missing_text_v1(value: Any) -> str:
    """Return compact missing-probe text for terminal display."""
    if not isinstance(value, dict) or not value:
        return "(none)"
    return ",".join(str(key) for key in sorted(value))


def navmap_scope_frame_v1(ctx: Any) -> dict[str, Any]:
    """Return a read-only NavMap Oscilloscope frame over the current ctx registers.

    This is intentionally high-impedance test equipment: it reads existing NavMap
    diagnostic registers and formats a single signal-path frame. It does not run
    NavMap matching, mutate ctx, write memory, choose policies, or append history.
    """
    base: dict[str, Any] = {
        "schema": "navmap_scope_frame_v1",
        "status": "idle",
        "has_evidence": False,
        "has_expected": False,
        "has_residual": False,
        "has_accepted": False,
        "has_transition": False,
        "has_policy_outcome": False,
        "complete": False,
        "missing_probe_count": 6,
        "missing_probe_reasons": {},
        "evidence_action": None,
        "evidence_slots": {},
        "expected_action": None,
        "expected_slots": {},
        "observed_slots": {},
        "residual_count": 0,
        "exact_match": None,
        "context_shift_recommended": False,
        "context_break_recommended": False,
        "evidence_override_slots": {},
        "safety_residual_slots": [],
        "acceptance": None,
        "accepted_slots": {},
        "transition_action": None,
        "transition_reward": 0.0,
        "transition_before_slots": {},
        "transition_after_slots": {},
        "transition_changed_slots": 0,
        "policy_success": None,
        "policy_confidence": None,
        "policy_key": None,
        "indexed_sample_count": 0,
        "indexed_success_rate": 0.0,
        "indexed_mean_reward": 0.0,
        "probe_order": [
            "evidence",
            "expected",
            "residual",
            "accepted",
            "transition",
            "policy_outcome",
        ],
    }

    if ctx is None:
        out = dict(base)
        out["status"] = "ctx_unavailable"
        return out

    observation = navmap_observation_update_summary_v1(ctx)
    expected = navmap_expected_current_summary_v1(ctx)
    transition = navmap_transition_summary_v1(ctx)
    accepted = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_accepted_current_v1", {}))

    accepted_payload = _navmap_safe_dict_v1(accepted.get("accepted_payload"))
    accepted_slots = _navmap_slots_from_payload_dict_v1(accepted_payload)
    if not accepted_slots:
        accepted_slots = _navmap_safe_dict_v1(accepted.get("observed_slots"))

    observed_slots = _navmap_safe_dict_v1(expected.get("observed_slots"))
    if not observed_slots:
        observed_slots = _navmap_safe_dict_v1(observation.get("slots"))

    has_evidence = bool(observation.get("has_last_update"))
    has_expected = bool(expected.get("expected_slots"))
    has_residual = bool(expected.get("has_last_comparison"))
    has_accepted = bool(accepted)
    has_transition = bool(transition.get("has_last_transition"))
    has_policy_outcome = bool(transition.get("success") is not None or transition.get("indexed_sample_count"))

    safety_residual_slots_raw = expected.get("safety_residual_slots")
    safety_residual_slots = (
        list(safety_residual_slots_raw)
        if isinstance(safety_residual_slots_raw, list)
        else []
    )

    out = dict(base)
    out.update(
        {
            "status": "active" if any(
                [has_evidence, has_expected, has_residual, has_accepted, has_transition, has_policy_outcome]
            ) else "idle",
            "has_evidence": has_evidence,
            "has_expected": has_expected,
            "has_residual": has_residual,
            "has_accepted": has_accepted,
            "has_transition": has_transition,
            "has_policy_outcome": has_policy_outcome,
            "evidence_action": observation.get("action") if isinstance(observation.get("action"), str) else None,
            "evidence_slots": _navmap_safe_dict_v1(observation.get("slots")),
            "expected_action": expected.get("action") if isinstance(expected.get("action"), str) else None,
            "expected_slots": _navmap_safe_dict_v1(expected.get("expected_slots")),
            "observed_slots": observed_slots,
            "residual_count": _navmap_safe_int_v1(expected.get("residual_count"), 0),
            "exact_match": expected.get("exact_match") if isinstance(expected.get("exact_match"), bool) else None,
            "context_shift_recommended": bool(expected.get("context_shift_recommended")),
            "context_break_recommended": bool(expected.get("context_break_recommended")),
            "evidence_override_slots": _navmap_safe_dict_v1(expected.get("evidence_override_slots")),
            "safety_residual_slots": safety_residual_slots,
            "acceptance": accepted.get("acceptance") if isinstance(accepted.get("acceptance"), str) else None,
            "accepted_slots": accepted_slots,
            "transition_action": transition.get("action") if isinstance(transition.get("action"), str) else None,
            "transition_reward": _navmap_safe_float_or_none_v1(transition.get("reward")) or 0.0,
            "transition_before_slots": _navmap_safe_dict_v1(transition.get("before_slots")),
            "transition_after_slots": _navmap_safe_dict_v1(transition.get("after_slots")),
            "transition_changed_slots": _navmap_safe_int_v1(transition.get("changed_slots"), 0),
            "policy_success": transition.get("success") if isinstance(transition.get("success"), bool) else None,
            "policy_confidence": _navmap_safe_float_or_none_v1(transition.get("confidence")),
            "policy_key": transition.get("policy_key") if isinstance(transition.get("policy_key"), str) else None,
            "indexed_sample_count": _navmap_safe_int_v1(transition.get("indexed_sample_count"), 0),
            "indexed_success_rate": _navmap_safe_float_or_none_v1(
                transition.get("indexed_success_rate")
            ) or 0.0,
            "indexed_mean_reward": _navmap_safe_float_or_none_v1(transition.get("indexed_mean_reward")) or 0.0,
        }
    )

    missing_reasons = navmap_scope_missing_probe_reasons_v1(out)
    out["missing_probe_reasons"] = missing_reasons
    out["missing_probe_count"] = len(missing_reasons)
    out["complete"] = not missing_reasons
    return out


def _navmap_scope_probe_status_text_v1(frame: dict[str, Any]) -> str:
    """Return compact on/off probe status text for a NavMap Oscilloscope frame."""
    parts = [f"{name}={'on' if frame.get(key) else 'off'}" for name, key, _reason in NAVMAP_SCOPE_PROBES_V1]
    return ", ".join(parts)


def render_navmap_scope_legend_lines_v1() -> list[str]:
    """Return a compact teaching legend for NavMap Oscilloscope output."""
    return [
        f"{NAVMAP_SCOPE_MARKER_V1} NAVMAP OSCILLOSCOPE LEGEND:",
        "  evidence  = EnvObservation-derived NavMap; the current sensory/body evidence packet.",
        "  expected  = context/policy prior; what the previous map and selected primitive predicted.",
        "  residual  = slot-level difference between expected map and evidence map.",
        "  accepted  = current accepted map; evidence remains authoritative in this diagnostic slice.",
        "  transition= previous accepted map + action + current accepted map.",
        "  outcome   = ctx-local policy-outcome sample/index evidence for that map/action path.",
        "  complete  = all six probes are on; incomplete usually means first-cycle warm-up or no action yet.",
        "  missing   = compact list of probes not yet present in the current signal path.",
        "  shift/break: shift suggests context update; break marks safety/context-breaking evidence.",
    ]


def render_navmap_scope_frame_lines_v1(ctx: Any) -> list[str]:
    """Return human-readable NavMap Oscilloscope lines for the current ctx registers."""
    frame = navmap_scope_frame_v1(ctx)
    lines: list[str] = [f"{NAVMAP_SCOPE_MARKER_V1} NAVMAP OSCILLOSCOPE:"]

    if frame["status"] == "ctx_unavailable":
        lines.append("  status=ctx_unavailable")
        return lines

    if frame["status"] == "idle":
        lines.append("  status=idle probes=all_off [src=ctx.navmap_* diagnostic registers]")
        lines.append("  legend: run menu 35 or 37 to put evidence/expectation/residual signals on the scope.")
        return lines

    confidence = frame["policy_confidence"]
    confidence_txt = f"{confidence:.2f}" if isinstance(confidence, float) else "n/a"
    lines.append(
        "  "
        f"status={frame['status']} complete={frame['complete']} "
        f"missing={_navmap_scope_compact_missing_text_v1(frame['missing_probe_reasons'])} "
        f"probes={_navmap_scope_probe_status_text_v1(frame)} "
        "[src=ctx.navmap_* diagnostic registers]"
    )
    if frame["missing_probe_reasons"]:
        lines.append("  missing reasons:")
        for probe_name, reason in frame["missing_probe_reasons"].items():
            lines.append(f"    - {probe_name}: {reason}")
    lines.append("  legend: evidence=input map; expected=prior; residual=difference; accepted=current map")
    lines.append(
        "  "
        f"1 evidence  : action={frame['evidence_action'] or '(n/a)'} "
        f"slots={{{_prediction_compact_map_text_v1(frame['evidence_slots'])}}}"
    )
    lines.append(
        "  "
        f"2 expected  : action={frame['expected_action'] or '(none)'} "
        f"slots={{{_prediction_compact_map_text_v1(frame['expected_slots'])}}}"
    )
    lines.append(
        "  "
        f"3 residual  : count={frame['residual_count']} exact={frame['exact_match']} "
        f"shift={frame['context_shift_recommended']} break={frame['context_break_recommended']} "
        f"overrides={{{_prediction_compact_map_text_v1(frame['evidence_override_slots'])}}} "
        f"safety={{{_navmap_compact_list_text_v1(frame['safety_residual_slots'])}}}"
    )
    lines.append(
        "  "
        f"4 accepted  : acceptance={frame['acceptance'] or '(none)'} "
        f"slots={{{_prediction_compact_map_text_v1(frame['accepted_slots'])}}}"
    )
    lines.append(
        "  "
        f"5 transition: before={{{_prediction_compact_map_text_v1(frame['transition_before_slots'])}}} "
        f"action={frame['transition_action'] or '(none)'} "
        f"after={{{_prediction_compact_map_text_v1(frame['transition_after_slots'])}}} "
        f"reward={frame['transition_reward']:.2f} changed_slots={frame['transition_changed_slots']}"
    )
    lines.append(
        "  "
        f"6 outcome   : success={frame['policy_success']} confidence={confidence_txt} "
        f"indexed_samples={frame['indexed_sample_count']} "
        f"indexed_success_rate={frame['indexed_success_rate']:.2f} "
        f"indexed_mean_reward={frame['indexed_mean_reward']:.2f}"
    )
    return lines


def navmap_scope_mini_line_v1(ctx: Any) -> str:
    """Return a one-line NavMap Oscilloscope readout for mini-snapshots."""
    frame = navmap_scope_frame_v1(ctx)

    if frame["status"] == "ctx_unavailable":
        return f"{NAVMAP_SCOPE_MARKER_V1} [navmap-scope] ctx unavailable"

    if frame["status"] == "idle":
        return f"{NAVMAP_SCOPE_MARKER_V1} [navmap-scope] status=idle probes=all_off"

    return (
        f"{NAVMAP_SCOPE_MARKER_V1} [navmap-scope] "
        f"complete={frame['complete']} "
        f"missing={_navmap_scope_compact_missing_text_v1(frame['missing_probe_reasons'])} "
        f"acceptance={frame['acceptance'] or '(none)'} "
        f"residuals={frame['residual_count']} "
        f"shift={frame['context_shift_recommended']} "
        f"break={frame['context_break_recommended']} "
        f"accepted={{{_prediction_compact_map_text_v1(frame['accepted_slots'])}}} "
        f"action={frame['transition_action'] or frame['expected_action'] or '(none)'} "
        f"outcome_samples={frame['indexed_sample_count']}"
    )


def navmap_observation_update_history_append_v1(
    history: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return a bounded NavMap observation-update history without mutating inputs.

    Parameters
    ----------
    history:
        Existing JSON-safe history records. Malformed rows are ignored so a bad
        caller-owned list cannot poison ctx history.

    record:
        The newest JSON-safe NavMapObservationUpdateV1 dictionary to append. If
        it is empty, the returned list is just the bounded clean history.

    limit:
        Maximum number of records to keep. Non-positive or malformed values are
        treated as 25.

    Returns
    -------
    list[dict[str, Any]]
        Newest-bounded history, preserving order from older to newer records.
    """
    try:
        max_len = int(limit)
    except (TypeError, ValueError):
        max_len = 25
    if max_len <= 0:
        max_len = 25

    clean_history: list[dict[str, Any]] = []
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                clean_history.append(dict(item))

    if isinstance(record, dict) and record:
        clean_history.append(dict(record))

    if len(clean_history) > max_len:
        return clean_history[-max_len:]
    return clean_history


def navmap_transition_history_append_v1(
    history: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return a bounded NavMap transition history without mutating inputs."""
    return navmap_observation_update_history_append_v1(history, record, limit=limit)


def navmap_policy_outcome_index_update_v1(ctx: Ctx, outcome: dict[str, Any]) -> dict[str, Any]:
    """Update the ctx-local NavMap policy-outcome index with one outcome sample.

    The index is the first runner-side table for the CCA8 idea:

      in this map context, this action has produced this next map/outcome.

    It is diagnostic-only. It does not alter policy choice, skill values, WorldGraph
    facts, Column engrams, or controller gates.
    """
    if ctx is None or not isinstance(outcome, dict) or not outcome:
        return {}

    policy_key_raw = outcome.get("policy_key")
    policy_key = policy_key_raw if isinstance(policy_key_raw, str) and policy_key_raw else ""
    if not policy_key:
        context_sig = outcome.get("context_signature")
        action_raw = outcome.get("action")
        action = action_raw if isinstance(action_raw, str) and action_raw else ""
        if isinstance(context_sig, str) and context_sig and action:
            policy_key = f"{context_sig}::{action}"
        elif action:
            policy_key = action
        elif isinstance(context_sig, str) and context_sig:
            policy_key = context_sig
    if not policy_key:
        return {}

    raw_index = getattr(ctx, "navmap_policy_outcome_index_v1", {})
    index = {str(key): dict(val) for key, val in raw_index.items() if isinstance(key, str) and isinstance(val, dict)}
    old = dict(index.get(policy_key, {}))

    old_n = _navmap_safe_int_v1(old.get("sample_count"), 0)
    old_success = _navmap_safe_int_v1(old.get("success_count"), 0)
    old_reward_total = _navmap_safe_float_or_none_v1(old.get("reward_total")) or 0.0
    old_conf_total = _navmap_safe_float_or_none_v1(old.get("confidence_total")) or 0.0

    reward = _navmap_safe_float_or_none_v1(outcome.get("reward")) or 0.0
    confidence = _navmap_safe_float_or_none_v1(outcome.get("confidence")) or 0.0
    success = bool(outcome.get("success")) if isinstance(outcome.get("success"), bool) else False

    sample_count = old_n + 1
    success_count = old_success + (1 if success else 0)
    reward_total = old_reward_total + reward
    confidence_total = old_conf_total + confidence

    action_out = outcome.get("action") if isinstance(outcome.get("action"), str) else None
    context_sig_out = outcome.get("context_signature") if isinstance(outcome.get("context_signature"), str) else None
    created_at_raw = outcome.get("created_at")

    row = {
        "schema": "navmap_policy_outcome_index_row_v1",
        "policy_key": policy_key,
        "action": action_out,
        "context_signature": context_sig_out,
        "sample_count": int(sample_count),
        "success_count": int(success_count),
        "success_rate": float(success_count / sample_count) if sample_count > 0 else 0.0,
        "reward_total": float(reward_total),
        "mean_reward": float(reward_total / sample_count) if sample_count > 0 else 0.0,
        "confidence_total": float(confidence_total),
        "mean_confidence": float(confidence_total / sample_count) if sample_count > 0 else 0.0,
        "last_reward": float(reward),
        "last_success": bool(success),
        "context_slots": _navmap_safe_dict_v1(outcome.get("context_slots")),
        "expected_slots": _navmap_safe_dict_v1(outcome.get("expected_slots")),
        "slot_changes": _navmap_safe_dict_v1(outcome.get("slot_changes")),
        "updated_at": created_at_raw if isinstance(created_at_raw, str) and created_at_raw else datetime.now().isoformat(),
    }

    if policy_key in index:
        del index[policy_key]
    index[policy_key] = dict(row)

    index_limit = _navmap_safe_int_v1(getattr(ctx, "navmap_policy_outcome_index_limit_v1", 100), 100)
    if index_limit <= 0:
        index_limit = 100
    while len(index) > index_limit:
        oldest_key = next(iter(index))
        del index[oldest_key]

    ctx.navmap_policy_outcome_index_v1 = index
    ctx.navmap_last_policy_outcome_index_row_v1 = dict(row)
    return row


def navmap_expected_current_history_append_v1(
    history: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return a bounded expected-current NavMap diagnostic history without mutating inputs."""
    return navmap_observation_update_history_append_v1(history, record, limit=limit)


def navmap_accepted_current_history_append_v1(
    history: list[dict[str, Any]],
    record: dict[str, Any],
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return a bounded accepted-current NavMap diagnostic history without mutating inputs."""
    return navmap_observation_update_history_append_v1(history, record, limit=limit)


def _navmap_slot_signature_from_slots_v1(slots: Any) -> str:
    """Return a stable context signature from a slot map."""
    slot_map = _navmap_safe_dict_v1(slots)
    clean: dict[str, str] = {}
    for key, value in slot_map.items():
        if not isinstance(key, str) or value is None:
            continue
        clean_key = key.strip()
        clean_value = str(value).strip().lower()
        if clean_key and clean_value:
            clean[clean_key] = clean_value
    return "|".join(f"{key}={clean[key]}" for key in sorted(clean))


def _navmap_policy_index_row_for_action_v1(ctx: Ctx, action: str, context_slots: dict[str, Any]) -> dict[str, Any]:
    """Return the exact ctx-local policy-outcome index row for context/action, if present."""
    if ctx is None or not isinstance(action, str) or not action:
        return {}

    context_signature = _navmap_slot_signature_from_slots_v1(context_slots)
    policy_key = f"{context_signature}::{action}" if context_signature else action

    raw_index = getattr(ctx, "navmap_policy_outcome_index_v1", {})
    if not isinstance(raw_index, dict):
        return {}

    row = raw_index.get(policy_key)
    return dict(row) if isinstance(row, dict) else {}


def navmap_expected_current_payload_from_ctx_v1(ctx: Ctx) -> dict[str, Any]:
    """Build the ctx-local expected-current scene_body NavMap diagnostic.

    This is the first explicit top-down prior surface for the runner's NavMap
    path. It combines previous scene_body continuity with the selected primitive:

      previous scene_body map + pending primitive/action -> expected current map

    This helper is goat-level, short-horizon, and behavior-preserving. It does
    not simulate alternative policies, choose actions, write WorldGraph facts,
    write Column engrams, update BodyMap, or alter policy selection.
    """
    if ctx is None:
        return {}

    previous_payload = _navmap_safe_dict_v1(getattr(ctx, "navmap_last_payload_v1", {}))
    previous_slots = _navmap_slots_from_payload_dict_v1(previous_payload)

    action_raw = getattr(ctx, "navmap_pending_action_v1", None)
    action = action_raw if isinstance(action_raw, str) and action_raw else ""

    expected_slots: dict[str, Any] = dict(previous_slots)
    sources: list[str] = []
    if previous_slots:
        sources.append("previous_payload_continuity")

    learned_row = _navmap_policy_index_row_for_action_v1(ctx, action, previous_slots)
    learned_expected = _navmap_safe_dict_v1(learned_row.get("expected_slots"))
    if learned_expected:
        expected_slots.update(learned_expected)
        sources.append("policy_outcome_index_expected_slots")
    else:
        policy_defaults = prediction_policy_expected_slots_v1(action)
        if policy_defaults:
            expected_slots.update(policy_defaults)
            sources.append("policy_default_expected_slots")

    if not expected_slots:
        ctx.navmap_last_expected_current_payload_v1 = None
        return {}

    basis = {
        "diagnostic_source": "cca8_run.navmap_expected_current_payload_from_ctx_v1",
        "action": action or None,
        "sources": list(sources),
        "context_signature": _navmap_slot_signature_from_slots_v1(previous_slots),
        "controller_steps": getattr(ctx, "controller_steps", None),
        "ticks": getattr(ctx, "ticks", None),
        "profile": getattr(ctx, "profile", None),
    }
    if learned_row:
        basis["learned_policy_key"] = learned_row.get("policy_key")
        basis["learned_sample_count"] = learned_row.get("sample_count")

    payload = make_navmap_payload_v1(
        expected_slots,
        confidence=0.60 if sources else 0.25,
        source="ctx_expected_current_v1",
        basis=basis,
    )
    payload_dict = payload.as_dict()
    ctx.navmap_last_expected_current_payload_v1 = dict(payload_dict)
    return payload_dict


def _navmap_expected_current_safety_slots_v1(residual: dict[str, Any]) -> list[str]:
    """Return safety-relevant residual slot names for expected-vs-evidence comparison."""
    safety_slot_names = {"zone", "space_zone", "hazard", "cliff_distance", "cliff_state", "shelter_distance"}
    out: set[str] = set()
    for field_name in ("mismatched_slots", "missing_slots", "novel_slots"):
        values = residual.get(field_name)
        if not isinstance(values, dict):
            continue
        for key in values:
            if isinstance(key, str) and key in safety_slot_names:
                out.add(key)
    return sorted(out)


def _navmap_expected_current_evidence_override_slots_v1(residual: dict[str, Any]) -> dict[str, Any]:
    """Return observed evidence slots that directly override or extend expectation."""
    out: dict[str, Any] = {}

    mismatched = residual.get("mismatched_slots")
    if isinstance(mismatched, dict):
        for key, value in mismatched.items():
            if isinstance(key, str) and isinstance(value, dict) and "current" in value:
                out[key] = value.get("current")

    novel = residual.get("novel_slots")
    if isinstance(novel, dict):
        for key, value in novel.items():
            if isinstance(key, str):
                out[key] = value

    return out


def _navmap_accepted_current_label_v1(comparison: dict[str, Any]) -> str:
    """Return the accepted-current diagnostic label for a comparison record."""
    status = comparison.get("status")
    if status == "no_expectation":
        return "evidence_only"
    if comparison.get("context_break_recommended") is True:
        return "context_break"
    if comparison.get("context_shift_recommended") is True:
        return "context_shift"
    if comparison.get("exact_match") is True:
        return "confirmed"
    if _navmap_safe_int_v1(comparison.get("residual_count"), 0) > 0:
        return "adjusted_by_evidence"
    return "confirmed"


def navmap_accepted_current_from_comparison_v1(ctx: Ctx, comparison: dict[str, Any]) -> dict[str, Any]:
    """Store the ctx-local accepted-current NavMap after prior-vs-evidence comparison.

    This is the first explicit acceptance surface for the NavMap predictive path.
    It is deliberately conservative: the accepted current payload is the observed
    evidence payload. Expected/prior payloads can be confirmed, adjusted, shifted,
    or broken by evidence, but they do not overwrite direct observation here.
    """
    if ctx is None or not isinstance(comparison, dict) or not comparison:
        return {}

    observed_payload = _navmap_safe_dict_v1(comparison.get("observed_payload"))
    if not observed_payload:
        return {}

    expected_payload = _navmap_safe_dict_v1(comparison.get("expected_payload"))
    safety_raw = comparison.get("safety_residual_slots")
    safety_slots = [str(item) for item in safety_raw if isinstance(item, str)] if isinstance(safety_raw, list) else []

    action_raw = comparison.get("action")
    status_raw = comparison.get("status")
    reason_raw = comparison.get("reason")
    created_at_raw = comparison.get("created_at")

    record = {
        "schema": "navmap_accepted_current_v1",
        "acceptance": _navmap_accepted_current_label_v1(comparison),
        "comparison_status": status_raw if isinstance(status_raw, str) and status_raw else None,
        "comparison_reason": reason_raw if isinstance(reason_raw, str) and reason_raw else None,
        "action": action_raw if isinstance(action_raw, str) and action_raw else None,
        "accepted_payload": dict(observed_payload),
        "expected_payload": dict(expected_payload),
        "observed_slots": _navmap_slots_from_payload_dict_v1(observed_payload),
        "expected_slots": _navmap_slots_from_payload_dict_v1(expected_payload),
        "residual_count": _navmap_safe_int_v1(comparison.get("residual_count"), 0),
        "exact_match": comparison.get("exact_match") if isinstance(comparison.get("exact_match"), bool) else None,
        "context_shift_recommended": bool(comparison.get("context_shift_recommended")),
        "context_break_recommended": bool(comparison.get("context_break_recommended")),
        "evidence_override_slots": _navmap_safe_dict_v1(comparison.get("evidence_override_slots")),
        "safety_residual_slots": safety_slots,
        "created_at": (
            created_at_raw if isinstance(created_at_raw, str) and created_at_raw else datetime.now().isoformat()
        ),
    }

    ctx.navmap_last_accepted_current_v1 = dict(record)

    history_limit = _navmap_safe_int_v1(getattr(ctx, "navmap_accepted_current_history_limit_v1", 25), 25)
    if history_limit <= 0:
        history_limit = 25
    ctx.navmap_accepted_current_history_v1 = navmap_accepted_current_history_append_v1(
        getattr(ctx, "navmap_accepted_current_history_v1", []),
        record,
        limit=history_limit,
    )
    working_navmap_surface_from_accepted_current_v1(ctx, record)
    return record


def navmap_expected_current_comparison_step_v1(ctx: Ctx, observed_payload: dict[str, Any]) -> dict[str, Any]:
    """Compare the expected current NavMap prior with the observed evidence NavMap.

    This helper makes the first explicit predictive-coding-style runner diagnostic:

      context / previous map / selected primitive -> expected current map
      EnvObservation-derived payload             -> observed evidence map
      expected current map vs evidence map       -> predictive residual

    It records ctx-local diagnostics only. Strong evidence is never overwritten;
    conflicts are reported as residuals and evidence_override_slots.
    """
    if ctx is None:
        return {}
    observed = _navmap_safe_dict_v1(observed_payload)
    if not observed:
        return {}

    expected = navmap_expected_current_payload_from_ctx_v1(ctx)

    action_raw = getattr(ctx, "navmap_pending_action_v1", None)
    action = action_raw if isinstance(action_raw, str) and action_raw else None
    comparison: dict[str, Any]
    if not expected:
        comparison = {
            "schema": "navmap_expected_current_comparison_v1",
            "status": "no_expectation",
            "reason": "no_previous_payload_or_policy_expectation",
            "action": action,
            "expected_payload": {},
            "observed_payload": dict(observed),
            "residual": {},
            "residual_count": 0,
            "exact_match": False,
            "context_shift_recommended": False,
            "context_break_recommended": False,
            "safety_residual_slots": [],
            "evidence_override_slots": {},
            "created_at": datetime.now().isoformat(),
        }
    else:
        residual_obj = navmap_residual_v1(observed, expected)
        residual = residual_obj.as_dict()
        safety_slots = _navmap_expected_current_safety_slots_v1(residual)
        override_slots = _navmap_expected_current_evidence_override_slots_v1(residual)
        residual_count = _navmap_safe_int_v1(residual.get("residual_count"), 0)

        observed_slots = _navmap_slots_from_payload_dict_v1(observed)
        expected_slots = _navmap_slots_from_payload_dict_v1(expected)
        observed_zone = str(observed_slots.get("zone", "") or "").strip().lower()
        expected_zone = str(expected_slots.get("zone", "") or "").strip().lower()
        context_break = bool(observed_zone in {"unsafe", "hazard", "cliff", "danger"} and observed_zone != expected_zone)

        threshold = _navmap_safe_int_v1(getattr(ctx, "navmap_expected_current_context_shift_threshold_v1", 3), 3)
        if threshold <= 0:
            threshold = 3
        context_shift = bool(residual_count >= threshold or safety_slots)

        comparison = {
            "schema": "navmap_expected_current_comparison_v1",
            "status": "active",
            "reason": "compared_expected_current_to_observed_current",
            "action": action,
            "expected_payload": dict(expected),
            "observed_payload": dict(observed),
            "residual": residual,
            "residual_count": int(residual_count),
            "exact_match": bool(residual.get("exact_match")),
            "context_shift_recommended": bool(context_shift),
            "context_break_recommended": bool(context_break),
            "safety_residual_slots": list(safety_slots),
            "evidence_override_slots": dict(override_slots),
            "created_at": datetime.now().isoformat(),
        }

    ctx.navmap_last_expected_current_comparison_v1 = dict(comparison)

    history_limit = _navmap_safe_int_v1(getattr(ctx, "navmap_expected_current_history_limit_v1", 25), 25)
    if history_limit <= 0:
        history_limit = 25
    ctx.navmap_expected_current_history_v1 = navmap_expected_current_history_append_v1(
        getattr(ctx, "navmap_expected_current_history_v1", []),
        comparison,
        limit=history_limit,
    )
    navmap_accepted_current_from_comparison_v1(ctx, comparison)
    return comparison


def navmap_ctx_transition_from_payloads_v1(
    ctx: Ctx,
    before_payload: dict[str, Any],
    after_payload: dict[str, Any],
) -> dict[str, Any]:
    """Store one ctx-local action-conditioned NavMap transition diagnostic.

    This helper is the runner bridge for primitive causal learning:

      previous scene_body map + action applied by the environment + current scene_body map
      -> NavMapTransitionV1
      -> optional NavMapPolicyOutcomeV1 sample

    It is deliberately diagnostic-only. It does not write WorldGraph facts, Column
    engrams, controller state, skill values, or policy-selection inputs.
    """
    if ctx is None:
        return {}
    if not isinstance(before_payload, dict) or not before_payload:
        return {}
    if not isinstance(after_payload, dict) or not after_payload:
        return {}

    action_raw = getattr(ctx, "navmap_pending_action_v1", None)
    action = action_raw if isinstance(action_raw, str) and action_raw else ""

    try:
        reward = float(getattr(ctx, "navmap_pending_reward_v1", 0.0) or 0.0)
    except (TypeError, ValueError):
        reward = 0.0

    basis = {
        "diagnostic_source": "cca8_run.navmap_ctx_transition_from_payloads_v1",
        "controller_steps": getattr(ctx, "controller_steps", None),
        "ticks": getattr(ctx, "ticks", None),
        "profile": getattr(ctx, "profile", None),
    }

    transition = make_navmap_transition_v1(
        before_payload,
        after_payload,
        action=action,
        reward=reward,
        drive_delta={},
        basis=basis,
    )
    transition_dict = transition.as_dict()
    ctx.navmap_last_transition_v1 = dict(transition_dict)

    transition_limit = _navmap_safe_int_v1(
        getattr(ctx, "navmap_transition_history_limit_v1", 25),
        25,
    )
    if transition_limit <= 0:
        transition_limit = 25
    ctx.navmap_transition_history_v1 = navmap_transition_history_append_v1(
        getattr(ctx, "navmap_transition_history_v1", []),
        transition_dict,
        limit=transition_limit,
    )

    if action:
        outcome = navmap_policy_outcome_from_transition_v1(
            transition,
            success_threshold=0.0,
            confidence=1.0,
            basis={"diagnostic_source": "cca8_run.navmap_ctx_transition_from_payloads_v1"},
        )
        outcome_dict = outcome.as_dict()
        ctx.navmap_last_policy_outcome_v1 = dict(outcome_dict)
        navmap_policy_outcome_index_update_v1(ctx, outcome_dict)

        outcome_limit = _navmap_safe_int_v1(
            getattr(ctx, "navmap_policy_outcome_history_limit_v1", 25),
            25,
        )
        if outcome_limit <= 0:
            outcome_limit = 25
        ctx.navmap_policy_outcome_history_v1 = navmap_transition_history_append_v1(
            getattr(ctx, "navmap_policy_outcome_history_v1", []),
            outcome_dict,
            limit=outcome_limit,
        )
    else:
        ctx.navmap_last_policy_outcome_v1 = None
        ctx.navmap_last_policy_outcome_index_row_v1 = None

    return transition_dict


def navmap_ctx_observation_update_step_v1(ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Run one read-only scene_body NavMap diagnostic update and store it on ctx.

    This is the first runtime bridge from EnvObservation into the NavMap helper
    module. It deliberately does not write WorldGraph facts, Column engrams, or
    controller/policy selection state. The only effects are ctx-local diagnostic
    fields:

      - ctx.navmap_scene_body_candidates_v1
      - ctx.navmap_last_observation_update_v1
      - ctx.navmap_observation_update_history_v1

    The candidate pool is a small in-memory diagnostic store. It is updated with
    the pure candidate list returned by cca8_navmap.navmap_observation_update_from_env_obs_v1.
    """
    if ctx is None or env_obs is None:
        return {}

    candidate_store = getattr(ctx, "navmap_scene_body_candidates_v1", [])
    if not isinstance(candidate_store, list):
        candidate_store = []

    try:
        max_candidates = int(getattr(ctx, "navmap_scene_body_max_candidates_v1", 25) or 25)
    except (TypeError, ValueError):
        max_candidates = 25
    if max_candidates <= 0:
        max_candidates = 25

    basis = {
        "diagnostic_source": "cca8_run.navmap_ctx_observation_update_step_v1",
        "controller_steps": getattr(ctx, "controller_steps", None),
        "ticks": getattr(ctx, "ticks", None),
        "profile": getattr(ctx, "profile", None),
    }

    update = navmap_observation_update_from_env_obs_v1(
        env_obs,
        candidate_store,
        basis=basis,
        max_candidates=max_candidates,
    )
    update_dict = update.as_dict()

    store_update = update_dict.get("store_update", {})
    new_candidates = store_update.get("candidates") if isinstance(store_update, dict) else None
    if isinstance(new_candidates, list):
        ctx.navmap_scene_body_candidates_v1 = [dict(item) for item in new_candidates if isinstance(item, dict)]
    else:
        ctx.navmap_scene_body_candidates_v1 = []

    ctx.navmap_last_observation_update_v1 = dict(update_dict)

    try:
        history_limit = int(getattr(ctx, "navmap_observation_update_history_limit_v1", 25) or 25)
    except (TypeError, ValueError):
        history_limit = 25
    ctx.navmap_observation_update_history_v1 = navmap_observation_update_history_append_v1(
        getattr(ctx, "navmap_observation_update_history_v1", []),
        update_dict,
        limit=history_limit,
    )

    current_payload = update_dict.get("current_payload")
    current_payload_dict = dict(current_payload) if isinstance(current_payload, dict) else {}
    previous_payload = getattr(ctx, "navmap_last_payload_v1", None)
    previous_payload_dict = dict(previous_payload) if isinstance(previous_payload, dict) else {}

    if current_payload_dict:
        navmap_expected_current_comparison_step_v1(ctx, current_payload_dict)
    else:
        ctx.navmap_last_expected_current_payload_v1 = None
        ctx.navmap_last_expected_current_comparison_v1 = None
        ctx.navmap_last_accepted_current_v1 = None
        ctx.working_navmap_surface_v1 = None

    if previous_payload_dict and current_payload_dict:
        navmap_ctx_transition_from_payloads_v1(ctx, previous_payload_dict, current_payload_dict)
    else:
        ctx.navmap_last_transition_v1 = None
        ctx.navmap_last_policy_outcome_v1 = None
        ctx.navmap_last_policy_outcome_index_row_v1 = None

    ctx.navmap_last_payload_v1 = dict(current_payload_dict) if current_payload_dict else None
    ctx.navmap_pending_action_v1 = None
    ctx.navmap_pending_reward_v1 = 0.0
    return update_dict
