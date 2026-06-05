# -*- coding: utf-8 -*-
"""State-integrity analysis helpers for CCA8 long-horizon experiments.

Purpose
-------
This module provides post-processing metrics for the Long-Horizon State-Integrity
Benchmark. It is deliberately read-only: it analyzes cycle records that were
already produced by the CCA8 experiment runner and returns JSON-safe summary
metrics. It does not change the controller, environment, memory system, or
action-selection behavior.

Design goals
------------
1. Keep the state-integrity paper work separate from the main CCA8 runner.
2. Make all metrics deterministic and inspectable from saved JSONL records.
3. Start with conservative metrics that can be derived from existing traces.
4. Use proxy labels for measures that are not yet backed by full pre/post slot
   logging, so the manuscript does not overclaim what the software measured.

The functions in this module are intended to be called later from ``cca8_run.py``
after each episode summary is produced.
"""

from __future__ import annotations

import json
from typing import Any


__version__ = "0.1.0"

__all__ = [
    "NEWBORN_LHSI_MILESTONE_ORDER_V1",
    "NEWBORN_LHSI_REQUIRED_PROVENANCE_FIELDS_V1",
    "summarize_newborn_state_integrity_v1",
    "render_state_integrity_summary_lines_v1",
    "render_state_integrity_event_detail_lines_v1",
    "demo_state_integrity_smoke_v1",
    "__version__",
]

NEWBORN_LHSI_MILESTONE_ORDER_V1 = [
    "stood_up",
    "reached_mom",
    "found_nipple",
    "latched_nipple",
    "milk_drinking",
    "rested",
]

NEWBORN_LHSI_REQUIRED_PROVENANCE_FIELDS_V1 = [
    "env_step",
    "scenario_stage",
    "posture",
    "mom_distance",
    "nipple_state",
    "zone",
    "policy_fired",
    "action_applied",
    "obs",
]


def _dict_or_empty_v1(value: Any) -> dict[str, Any]:
    """Return value if it is a dict, otherwise return an empty dict."""
    return value if isinstance(value, dict) else {}


def _list_or_empty_v1(value: Any) -> list[Any]:
    """Return value if it is a list, otherwise return an empty list."""
    return value if isinstance(value, list) else []


def _string_or_none_v1(value: Any) -> str | None:
    """Return a non-empty string value, otherwise None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_or_none_v1(value: Any) -> int | None:
    """Return an integer value when conversion is safe, otherwise None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    try:
        return int(value)
    except Exception:
        return None


def _float_or_none_v1(value: Any) -> float | None:
    """Return a float value when conversion is safe, otherwise None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


def _policy_from_raw_v1(raw_record: dict[str, Any]) -> str | None:
    """Return the policy/action string used for one raw cycle record.

    Existing CCA8 traces may store either ``policy_fired`` or ``action_applied``.
    The policy_fired field is preferred because it reflects the selected CCA8
    primitive. If it is absent, action_applied is used as a fallback.
    """
    if not isinstance(raw_record, dict):
        return None

    policy = _string_or_none_v1(raw_record.get("policy_fired"))
    if policy is not None:
        return policy

    return _string_or_none_v1(raw_record.get("action_applied"))


def _env_step_from_raw_v1(raw_record: dict[str, Any], fallback_index: int) -> int:
    """Return the environment step for a raw cycle record."""
    if isinstance(raw_record, dict):
        step = _int_or_none_v1(raw_record.get("env_step"))
        if step is not None:
            return int(step)
    return int(fallback_index)


def _prediction_error_count_v1(raw_record: dict[str, Any]) -> float:
    """Return a small numeric prediction-error burden from a raw cycle record.

    The existing runner stores prediction-error details in ``pred_err_v0`` when
    available. This helper sums absolute numeric values in that dict. Non-numeric
    values are ignored.
    """
    if not isinstance(raw_record, dict):
        return 0.0

    pred_err = _dict_or_empty_v1(raw_record.get("pred_err_v0"))
    total = 0.0
    for value in pred_err.values():
        num = _float_or_none_v1(value)
        if num is not None:
            total += abs(float(num))
    return float(total)


def _obs_dict_v1(raw_record: dict[str, Any]) -> dict[str, Any]:
    """Return the observation dict from one raw cycle record."""
    if not isinstance(raw_record, dict):
        return {}
    return _dict_or_empty_v1(raw_record.get("obs"))


def _obs_predicates_v1(raw_record: dict[str, Any]) -> set[str]:
    """Return normalized predicate tokens observed in one cycle.

    Tokens are returned without a leading ``pred:`` prefix so callers can compare
    both raw observation fields and predicate lists using the same strings.
    """
    obs = _obs_dict_v1(raw_record)
    preds_raw = _list_or_empty_v1(obs.get("predicates"))
    preds: set[str] = set()

    for item in preds_raw:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if not token:
            continue
        if token.startswith("pred:"):
            token = token.replace("pred:", "", 1)
        preds.add(token)

    return preds


def _events_from_raw_v1(raw_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return WorkingMap map-switch/retrieval events from one raw cycle record."""
    if not isinstance(raw_record, dict):
        return []

    wm = _dict_or_empty_v1(raw_record.get("wm"))
    mapswitch = _dict_or_empty_v1(wm.get("mapswitch"))
    raw_events = _list_or_empty_v1(mapswitch.get("events"))

    out: list[dict[str, Any]] = []
    for event in raw_events:
        if isinstance(event, dict):
            out.append(event)
    return out


def _newborn_retrieval_events_from_raw_v1(raw_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return newborn-specific retrieval events from one raw cycle record."""
    out: list[dict[str, Any]] = []
    for event in _events_from_raw_v1(raw_record):
        reason = event.get("reason")
        if isinstance(reason, str) and reason.startswith("newborn_b2:"):
            out.append(event)
    return out


def _milestone_events_from_raw_v1(raw_record: dict[str, Any]) -> set[str]:
    """Infer newborn milestone events visible in one raw cycle record.

    This mirrors the existing newborn summary logic in ``cca8_run.py`` while
    keeping the analysis layer independent. It uses both explicit observation
    predicates and convenience fields already present in raw cycle records.
    """
    if not isinstance(raw_record, dict):
        return set()

    preds = _obs_predicates_v1(raw_record)

    posture = _string_or_none_v1(raw_record.get("posture"))
    mom_distance = _string_or_none_v1(raw_record.get("mom_distance"))
    nipple_state = _string_or_none_v1(raw_record.get("nipple_state"))
    zone = _string_or_none_v1(raw_record.get("zone"))

    events: set[str] = set()

    if posture in ("standing", "latched", "resting") or "posture:standing" in preds:
        events.add("stood_up")

    if mom_distance in ("near", "touching") or "proximity:mom:close" in preds:
        events.add("reached_mom")

    if nipple_state in ("visible", "reachable", "latched") or "nipple:found" in preds:
        events.add("found_nipple")

    if nipple_state == "latched" or "nipple:latched" in preds:
        events.add("latched_nipple")

    if "milk:drinking" in preds:
        events.add("milk_drinking")

    if (posture == "resting" or "resting" in preds) and zone == "safe":
        events.add("rested")

    return events


def _milestone_state_before_each_cycle_v1(raw_records: list[dict[str, Any]]) -> list[dict[str, bool]]:
    """Return ordered milestone state before each cycle is interpreted.

    The state advances only in the declared milestone order. This prevents later
    evidence from granting skipped milestones out of order.
    """
    state = {name: False for name in NEWBORN_LHSI_MILESTONE_ORDER_V1}
    out: list[dict[str, bool]] = []
    next_index = 0

    for raw in raw_records:
        out.append(dict(state))

        events = _milestone_events_from_raw_v1(raw)
        while next_index < len(NEWBORN_LHSI_MILESTONE_ORDER_V1):
            name = NEWBORN_LHSI_MILESTONE_ORDER_V1[next_index]
            if name not in events:
                break
            state[name] = True
            next_index += 1

    return out


def _milestone_summary_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return milestone vector, milestone steps, score, and success."""
    state = {name: False for name in NEWBORN_LHSI_MILESTONE_ORDER_V1}
    steps: dict[str, int | None] = {name: None for name in NEWBORN_LHSI_MILESTONE_ORDER_V1}
    next_index = 0

    for index, raw in enumerate(raw_records):
        events = _milestone_events_from_raw_v1(raw)
        while next_index < len(NEWBORN_LHSI_MILESTONE_ORDER_V1):
            name = NEWBORN_LHSI_MILESTONE_ORDER_V1[next_index]
            if name not in events:
                break

            state[name] = True
            steps[name] = _env_step_from_raw_v1(raw, index)
            next_index += 1

    achieved = sum(1 for name in NEWBORN_LHSI_MILESTONE_ORDER_V1 if state[name])
    score = achieved / float(len(NEWBORN_LHSI_MILESTONE_ORDER_V1))

    return {
        "milestone_vector": state,
        "milestone_steps": steps,
        "milestone_score": float(score),
        "success": bool(achieved == len(NEWBORN_LHSI_MILESTONE_ORDER_V1)),
    }


def _completion_cutoff_index_v1(raw_records: list[dict[str, Any]]) -> int | None:
    """Return the first cycle index where the ordered newborn milestone sequence completes.

    This defines the active task horizon for LHSI scoring. If the agent reaches
    final rest at cycle N, later controller behavior is post-completion behavior
    and should not inflate wrong-stage, loop, stale-memory, or dissociation metrics.

    Returns None when the episode never completes the ordered milestone sequence.
    """
    state = {name: False for name in NEWBORN_LHSI_MILESTONE_ORDER_V1}
    next_index = 0

    for index, raw in enumerate(raw_records):
        events = _milestone_events_from_raw_v1(raw)
        while next_index < len(NEWBORN_LHSI_MILESTONE_ORDER_V1):
            name = NEWBORN_LHSI_MILESTONE_ORDER_V1[next_index]
            if name not in events:
                break

            state[name] = True
            next_index += 1

        if next_index >= len(NEWBORN_LHSI_MILESTONE_ORDER_V1):
            return int(index)

    return None


def _cycle_advances_ordered_milestone_v1(
    events: set[str],
    prior_milestones: dict[str, bool],
) -> bool:
    """Return True when this cycle advances at least one not-yet-achieved milestone.

    LHSI wrong-stage scoring should be conservative around transition cycles.
    The raw trace records the policy and the resulting observed state in one
    cycle-level row, so a cycle that first achieves a milestone can otherwise
    look like a policy/state mismatch. We therefore do not count wrong-stage
    actions on cycles that visibly advance the ordered task.
    """
    if not isinstance(events, set) or not isinstance(prior_milestones, dict):
        return False

    for name in NEWBORN_LHSI_MILESTONE_ORDER_V1:
        if not bool(prior_milestones.get(name)) and name in events:
            return True

    return False


def _wrong_stage_reason_v1(
    raw_record: dict[str, Any],
    prior_milestones: dict[str, bool],
    current_events: set[str] | None = None,
) -> str | None:
    """Return a conservative wrong-stage label for one cycle, or None.

    The classifier intentionally flags only clear stage/action mismatches. Current
    observed state is treated as more authoritative than cumulative milestone
    history. This matters because the newborn task can regress locally, for
    example if a latch is lost after a previous latch milestone.
    """
    if not isinstance(raw_record, dict) or not isinstance(prior_milestones, dict):
        return None

    policy = _policy_from_raw_v1(raw_record)
    if policy is None:
        return None

    events = current_events if isinstance(current_events, set) else set()

    posture = _string_or_none_v1(raw_record.get("posture"))
    mom_distance = _string_or_none_v1(raw_record.get("mom_distance"))
    nipple_state = _string_or_none_v1(raw_record.get("nipple_state"))
    zone = _string_or_none_v1(raw_record.get("zone"))

    stood = bool(prior_milestones.get("stood_up"))
    reached = bool(prior_milestones.get("reached_mom"))
    found = bool(prior_milestones.get("found_nipple"))
    rested = bool(prior_milestones.get("rested"))

    current_latched = nipple_state == "latched" or "latched_nipple" in events
    current_drinking = "milk_drinking" in events
    current_resting_safe = "rested" in events or (posture == "resting" and zone == "safe")

    if rested and policy not in ("policy:rest", "policy:explore_check", "policy:probe"):
        return "action_after_final_rest"

    if posture == "fallen" and policy in ("policy:seek_nipple", "policy:suckle", "policy:rest"):
        return "feeding_or_rest_action_while_fallen"

    if policy == "policy:seek_nipple":
        if not stood and posture not in ("standing", "latched", "resting"):
            return "seek_before_standing"
        if not reached and mom_distance not in ("near", "touching"):
            return "seek_before_reaching_mom"
        if current_latched or current_drinking:
            return "seek_while_currently_latched_or_drinking"

    if policy == "policy:suckle":
        if not current_latched:
            return "suckle_before_current_latch"
        if posture == "fallen":
            return "suckle_while_fallen"

    if policy == "policy:rest":
        if not current_drinking and not current_resting_safe:
            return "rest_before_current_drinking"
        if zone not in (None, "safe", "unknown"):
            return "rest_before_safe_zone"

    if policy in ("policy:stand_up", "policy:recover_fall"):
        if stood and posture in ("standing", "latched", "resting"):
            return "posture_recovery_after_upright"

    if policy == "policy:follow_mom":
        if current_latched or current_drinking:
            return "follow_while_currently_latched_or_drinking"

    if found and not reached:
        return "milestone_order_incoherence"

    return None


def _wrong_stage_events_v1(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return conservative wrong-stage action events for the episode."""
    prior_states = _milestone_state_before_each_cycle_v1(raw_records)
    out: list[dict[str, Any]] = []

    for index, raw in enumerate(raw_records):
        prior = prior_states[index] if index < len(prior_states) else {}
        events = _milestone_events_from_raw_v1(raw)
        if _cycle_advances_ordered_milestone_v1(events, prior):
            continue
        reason = _wrong_stage_reason_v1(raw, prior, current_events=events)
        if reason is None:
            continue

        out.append(
            {
                "cycle_index": int(index),
                "env_step": _env_step_from_raw_v1(raw, index),
                "policy": _policy_from_raw_v1(raw),
                "reason": reason,
                "stage": _string_or_none_v1(raw.get("scenario_stage")) if isinstance(raw, dict) else None,
                "posture": _string_or_none_v1(raw.get("posture")) if isinstance(raw, dict) else None,
                "mom_distance": _string_or_none_v1(raw.get("mom_distance")) if isinstance(raw, dict) else None,
                "nipple_state": _string_or_none_v1(raw.get("nipple_state")) if isinstance(raw, dict) else None,
                "zone": _string_or_none_v1(raw.get("zone")) if isinstance(raw, dict) else None,
            }
        )

    return out


def _repeated_action_loop_events_v1(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return repeated-action loop events that occur without milestone progress.

    A loop event is counted when the same policy fires at least three cycles in a
    row and the current cycle does not add a new milestone event. This is a
    conservative trajectory-quality signal, not a claim about permanent failure.
    """
    out: list[dict[str, Any]] = []
    last_policy: str | None = None
    streak = 0

    for index, raw in enumerate(raw_records):
        policy = _policy_from_raw_v1(raw)
        events = _milestone_events_from_raw_v1(raw)

        if policy is not None and policy == last_policy:
            streak += 1
        else:
            last_policy = policy
            streak = 1 if policy is not None else 0

        if policy is not None and streak >= 3 and not events:
            out.append(
                {
                    "cycle_index": int(index),
                    "env_step": _env_step_from_raw_v1(raw, index),
                    "policy": policy,
                    "streak": int(streak),
                }
            )

    return out


def _retrieval_summary_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return retrieval and state-governance proxy metrics.

    Retrieval attempts are separated from effective retrievals. This matters for
    LHSI scoring because a merge retrieval can legitimately be a no-op when the
    current WorkingMap already has the relevant state. Stale-memory intrusion and
    retrieval-action dissociation should be evaluated only after retrievals that
    actually changed or filled state.
    """
    retrieval_event_count = 0
    retrieval_ok_count = 0
    retrieval_non_noop_count = 0
    retrieval_merge_noop_count = 0
    retrieval_replace_count = 0
    current_state_overwrite_proxy_count = 0

    retrieval_steps: list[int] = []
    retrieval_non_noop_steps: list[int] = []
    retrieval_cycle_indices: list[int] = []
    retrieval_non_noop_cycle_indices: list[int] = []
    retrieval_modes_by_cycle: dict[int, str] = {}

    for index, raw in enumerate(raw_records):
        events = _newborn_retrieval_events_from_raw_v1(raw)
        if not events:
            continue

        for event in events:
            step_value = _env_step_from_raw_v1(raw, index)

            retrieval_event_count += 1
            retrieval_cycle_indices.append(int(index))
            retrieval_steps.append(step_value)

            if bool(event.get("ok")):
                retrieval_ok_count += 1

            load = _dict_or_empty_v1(event.get("load"))
            mode = str(load.get("mode") or "").strip().lower()
            retrieval_modes_by_cycle[index] = mode or "merge"

            non_noop = False

            if mode == "replace":
                retrieval_replace_count += 1
                ent_n = _int_or_none_v1(load.get("entities")) or 0
                rel_n = _int_or_none_v1(load.get("relations")) or 0
                if ent_n > 0 or rel_n > 0:
                    non_noop = True
                    current_state_overwrite_proxy_count += 1
            else:
                added_entities = _int_or_none_v1(load.get("added_entities")) or 0
                filled_slots = _int_or_none_v1(load.get("filled_slots")) or 0
                added_edges = _int_or_none_v1(load.get("added_edges")) or 0
                stored_prior_cues = _int_or_none_v1(load.get("stored_prior_cues")) or 0

                if added_entities > 0 or filled_slots > 0 or added_edges > 0 or stored_prior_cues > 0:
                    non_noop = True
                else:
                    retrieval_merge_noop_count += 1

            if non_noop:
                retrieval_non_noop_count += 1

                if int(index) not in retrieval_non_noop_cycle_indices:
                    retrieval_non_noop_cycle_indices.append(int(index))

                if step_value not in retrieval_non_noop_steps:
                    retrieval_non_noop_steps.append(step_value)

    return {
        "retrieval_event_count": int(retrieval_event_count),
        "retrieval_ok_count": int(retrieval_ok_count),
        "retrieval_non_noop_count": int(retrieval_non_noop_count),
        "retrieval_merge_noop_count": int(retrieval_merge_noop_count),
        "retrieval_replace_count": int(retrieval_replace_count),
        "current_state_overwrite_proxy_count": int(current_state_overwrite_proxy_count),
        "retrieval_followup_basis_count": int(len(retrieval_non_noop_cycle_indices)),
        "retrieval_steps": retrieval_steps[:24],
        "retrieval_non_noop_steps": retrieval_non_noop_steps[:24],
        "retrieval_cycle_indices": retrieval_cycle_indices,
        "retrieval_non_noop_cycle_indices": retrieval_non_noop_cycle_indices,
        "retrieval_modes_by_cycle": retrieval_modes_by_cycle,
    }


def _retrieval_followup_proxy_events_v1(
    raw_records: list[dict[str, Any]],
    retrieval_cycle_indices: list[int],
    wrong_stage_events: list[dict[str, Any]],
    *,
    window: int,
) -> dict[str, Any]:
    """Return retrieval follow-up proxy events.

    This helper looks for wrong-stage actions or prediction-error burden shortly
    after a retrieval event. It is a conservative proxy for retrieval-action
    dissociation or stale-memory intrusion until full slot-level pre/post logs
    are available.
    """
    window_i = max(1, int(window))
    wrong_by_cycle: dict[int, list[dict[str, Any]]] = {}

    for event in wrong_stage_events:
        cycle = _int_or_none_v1(event.get("cycle_index"))
        if cycle is None:
            continue
        wrong_by_cycle.setdefault(int(cycle), []).append(event)

    dissociation_events: list[dict[str, Any]] = []
    stale_proxy_events: list[dict[str, Any]] = []

    for retrieval_cycle in retrieval_cycle_indices:
        start = int(retrieval_cycle)
        end = min(len(raw_records) - 1, start + window_i)

        wrong_hits: list[dict[str, Any]] = []
        pred_error_after = 0.0

        for cycle in range(start, end + 1):
            wrong_hits.extend(wrong_by_cycle.get(cycle, []))
            if 0 <= cycle < len(raw_records):
                pred_error_after += _prediction_error_count_v1(raw_records[cycle])

        if wrong_hits:
            first = wrong_hits[0]
            dissociation_events.append(
                {
                    "retrieval_cycle_index": int(start),
                    "first_wrong_cycle_index": int(first.get("cycle_index", start)),
                    "first_wrong_reason": first.get("reason"),
                }
            )
            stale_proxy_events.append(
                {
                    "retrieval_cycle_index": int(start),
                    "why": "wrong_stage_after_retrieval",
                    "first_wrong_reason": first.get("reason"),
                }
            )
        elif pred_error_after > 0.0:
            stale_proxy_events.append(
                {
                    "retrieval_cycle_index": int(start),
                    "why": "prediction_error_after_retrieval",
                    "pred_error_after": float(pred_error_after),
                }
            )

    return {
        "retrieval_action_dissociation_proxy_count": int(len(dissociation_events)),
        "stale_memory_intrusion_proxy_count": int(len(stale_proxy_events)),
        "retrieval_action_dissociation_proxy_events": dissociation_events[:24],
        "stale_memory_intrusion_proxy_events": stale_proxy_events[:24],
    }


def _provenance_summary_v1(raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return cycle-level provenance completeness metrics."""
    total = len(raw_records)
    if total <= 0:
        return {
            "provenance_cycle_count": 0,
            "provenance_complete_cycle_count": 0,
            "provenance_complete_cycle_rate": None,
            "provenance_missing_field_counts": {},
        }

    complete = 0
    missing_counts: dict[str, int] = {name: 0 for name in NEWBORN_LHSI_REQUIRED_PROVENANCE_FIELDS_V1}

    for raw in raw_records:
        if not isinstance(raw, dict):
            for name in NEWBORN_LHSI_REQUIRED_PROVENANCE_FIELDS_V1:
                missing_counts[name] += 1
            continue

        missing_this_cycle = False
        for name in NEWBORN_LHSI_REQUIRED_PROVENANCE_FIELDS_V1:
            value = raw.get(name)

            if name in ("policy_fired", "action_applied"):
                if _policy_from_raw_v1(raw) is not None:
                    continue

            if value is None:
                missing_counts[name] += 1
                missing_this_cycle = True
                continue

            if name == "obs" and not isinstance(value, dict):
                missing_counts[name] += 1
                missing_this_cycle = True

        if not missing_this_cycle:
            complete += 1

    return {
        "provenance_cycle_count": int(total),
        "provenance_complete_cycle_count": int(complete),
        "provenance_complete_cycle_rate": float(complete) / float(total),
        "provenance_missing_field_counts": missing_counts,
    }


def _state_integrity_score_v1(  #pylint: disable=too-many-positional-arguments
    milestone_score: float,
    wrong_stage_count: int,
    overwrite_proxy_count: int,
    stale_proxy_count: int,
    loop_count: int,
    provenance_rate: float | None,
) -> float:
    """Return a transparent secondary state-integrity score.

    The score is intentionally simple and bounded. Component metrics should
    still be reported separately in the manuscript. This score is useful for
    quick terminal comparison, not as the sole endpoint.
    """
    base = max(0.0, min(1.0, float(milestone_score)))

    penalty = 0.0
    penalty += min(0.25, 0.03 * max(0, int(wrong_stage_count)))
    penalty += min(0.25, 0.04 * max(0, int(overwrite_proxy_count)))
    penalty += min(0.20, 0.04 * max(0, int(stale_proxy_count)))
    penalty += min(0.15, 0.02 * max(0, int(loop_count)))

    if provenance_rate is None:
        penalty += 0.05
    else:
        penalty += min(0.10, 0.10 * max(0.0, 1.0 - float(provenance_rate)))

    return round(max(0.0, base - penalty), 6)


def summarize_newborn_state_integrity_v1(
    raw_records: list[dict[str, Any]],
    *,
    followup_window: int = 2,
) -> dict[str, Any]:
    """Summarize Long-Horizon State-Integrity metrics for one newborn episode.

    Parameters
    ----------
    raw_records:
        Raw cycle records from one CCA8 episode, usually
        ``ctx.cycle_json_records`` from the experiment sandbox.

    followup_window:
        Number of cycles after a retrieval event used for retrieval follow-up
        proxy metrics. The default of 2 keeps the metric local and conservative.

    Returns
    -------
    dict
        JSON-safe state-integrity summary. Metrics with ``_proxy`` in the name
        are derived proxies, not full slot-level overwrite/staleness audits.
    """
    records_all = raw_records if isinstance(raw_records, list) else []
    completion_cutoff_index = _completion_cutoff_index_v1(records_all)

    if completion_cutoff_index is not None:
        records = records_all[: completion_cutoff_index + 1]
    else:
        records = records_all

    milestone = _milestone_summary_v1(records)
    wrong_events = _wrong_stage_events_v1(records)
    loop_events = _repeated_action_loop_events_v1(records)
    retrieval = _retrieval_summary_v1(records)
    followup = _retrieval_followup_proxy_events_v1(
        records,
        list(retrieval.get("retrieval_non_noop_cycle_indices", []) or []),
        wrong_events,
        window=int(followup_window),
    )
    provenance = _provenance_summary_v1(records)

    pred_error_total = 0.0
    for raw in records:
        pred_error_total += _prediction_error_count_v1(raw)

    provenance_rate = provenance.get("provenance_complete_cycle_rate")
    score = _state_integrity_score_v1(
        milestone_score=float(milestone.get("milestone_score", 0.0) or 0.0),
        wrong_stage_count=len(wrong_events),
        overwrite_proxy_count=int(retrieval.get("current_state_overwrite_proxy_count", 0) or 0),
        stale_proxy_count=int(followup.get("stale_memory_intrusion_proxy_count", 0) or 0),
        loop_count=len(loop_events),
        provenance_rate=float(provenance_rate) if isinstance(provenance_rate, (int, float)) else None,
    )

    completion_cutoff_env_step = None
    if completion_cutoff_index is not None and 0 <= completion_cutoff_index < len(records_all):
        completion_cutoff_env_step = _env_step_from_raw_v1(records_all[completion_cutoff_index], completion_cutoff_index)

    out: dict[str, Any] = {
        "schema": "newborn_state_integrity_summary_v1",
        "raw_cycle_count": int(len(records_all)),
        "active_cycle_count": int(len(records)),
        "active_horizon_applied": bool(completion_cutoff_index is not None),
        "completion_cutoff_cycle_index": completion_cutoff_index,
        "completion_cutoff_env_step": completion_cutoff_env_step,
        "state_integrity_score": float(score),
        "wrong_stage_action_count": int(len(wrong_events)),
        "wrong_stage_action_events": wrong_events[:24],
        "repeated_action_loop_count_lhsi": int(len(loop_events)),
        "repeated_action_loop_events": loop_events[:24],
        "cumulative_prediction_error_lhsi": float(pred_error_total),
    }

    out.update(milestone)
    out.update(retrieval)
    out.update(followup)
    out.update(provenance)

    out.pop("retrieval_cycle_indices", None)
    out.pop("retrieval_non_noop_cycle_indices", None)
    out.pop("retrieval_modes_by_cycle", None)

    return out


def _metric_text_v1(value: Any) -> str:
    """Return a compact human-readable value for terminal summaries."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=isinstance(value, dict))
        except Exception:
            return str(value)
    return str(value)


def render_state_integrity_summary_lines_v1(summary: dict[str, Any]) -> list[str]:
    """Return compact terminal lines for one state-integrity summary. """
    if not isinstance(summary, dict):
        return ["[lhsi] state integrity summary: (invalid)"]

    return [
        f"[lhsi] cycles              : {_metric_text_v1(summary.get('raw_cycle_count'))}",
        f"[lhsi] active_cycles       : {_metric_text_v1(summary.get('active_cycle_count'))}",
        f"[lhsi] success             : {_metric_text_v1(summary.get('success'))}",
        f"[lhsi] milestone_score     : {_metric_text_v1(summary.get('milestone_score'))}",
        f"[lhsi] state_score         : {_metric_text_v1(summary.get('state_integrity_score'))}",
        f"[lhsi] wrong_stage         : {_metric_text_v1(summary.get('wrong_stage_action_count'))}",
        f"[lhsi] repeated_loops      : {_metric_text_v1(summary.get('repeated_action_loop_count_lhsi'))}",
        f"[lhsi] retrieval_events    : {_metric_text_v1(summary.get('retrieval_event_count'))}",
        f"[lhsi] retrieval_nonnoop   : {_metric_text_v1(summary.get('retrieval_non_noop_count'))}",
        f"[lhsi] replace_retrievals  : {_metric_text_v1(summary.get('retrieval_replace_count'))}",
        f"[lhsi] overwrite_proxy     : {_metric_text_v1(summary.get('current_state_overwrite_proxy_count'))}",
        f"[lhsi] stale_proxy         : {_metric_text_v1(summary.get('stale_memory_intrusion_proxy_count'))}",
        f"[lhsi] retr_act_dissoc     : {_metric_text_v1(summary.get('retrieval_action_dissociation_proxy_count'))}",
        f"[lhsi] pred_error          : {_metric_text_v1(summary.get('cumulative_prediction_error_lhsi'))}",
        f"[lhsi] provenance_rate     : {_metric_text_v1(summary.get('provenance_complete_cycle_rate'))}",
    ]

def _short_event_value_v1(value: Any, *, max_len: int = 48) -> str:
    """Return a compact one-line event value for terminal display."""
    if value is None:
        return "(none)"
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max(1, max_len - 1)] + "…"


def _event_list_v1(summary: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return a bounded list of event dicts from a state-integrity summary."""
    raw = summary.get(key) if isinstance(summary, dict) else None
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def render_state_integrity_event_detail_lines_v1(
    summary: dict[str, Any],
    *,
    max_events: int = 3,
    prefix: str = "[lhsi-detail]",
) -> list[str]:
    """Return compact event-detail lines for inspecting one LHSI episode.

    Purpose
    -------
    This renderer is for debugging and metric validation. It shows the first few
    wrong-stage, stale-memory-proxy, retrieval-action-dissociation-proxy, and
    repeated-loop events so the caller can decide whether the proxy classifiers
    are meaningful or too strict.

    It does not compute new metrics and does not change controller behavior.
    """
    if not isinstance(summary, dict):
        return [f"{prefix} detail             : (invalid summary)"]

    try:
        limit = int(max_events)
    except Exception:
        limit = 3
    limit = max(0, min(12, limit))

    wrong_events = _event_list_v1(summary, "wrong_stage_action_events")
    stale_events = _event_list_v1(summary, "stale_memory_intrusion_proxy_events")
    dissoc_events = _event_list_v1(summary, "retrieval_action_dissociation_proxy_events")
    loop_events = _event_list_v1(summary, "repeated_action_loop_events")

    wrong_count = summary.get("wrong_stage_action_count", len(wrong_events))
    stale_count = summary.get("stale_memory_intrusion_proxy_count", len(stale_events))
    dissoc_count = summary.get("retrieval_action_dissociation_proxy_count", len(dissoc_events))
    loop_count = summary.get("repeated_action_loop_count_lhsi", len(loop_events))

    counts = (
        f"wrong={_short_event_value_v1(wrong_count)} "
        f"stale_proxy={_short_event_value_v1(stale_count)} "
        f"dissoc_proxy={_short_event_value_v1(dissoc_count)} "
        f"loops={_short_event_value_v1(loop_count)}"
    )
    active_txt = (
        f"active_cycles={_short_event_value_v1(summary.get('active_cycle_count'))}/"
        f"{_short_event_value_v1(summary.get('raw_cycle_count'))} "
        f"cutoff_step={_short_event_value_v1(summary.get('completion_cutoff_env_step'))}"
    )
    lines = [f"{prefix} lhsi_detail       : {counts}; {active_txt}; showing first {limit} per class"]

    if limit <= 0:
        return lines

    for index, event in enumerate(wrong_events[:limit], start=1):
        lines.append(
            f"{prefix} wrong[{index}]          : step={_short_event_value_v1(event.get('env_step'))} "
            f"policy={_short_event_value_v1(event.get('policy'))} "
            f"reason={_short_event_value_v1(event.get('reason'))} "
            f"stage={_short_event_value_v1(event.get('stage'))} "
            f"posture={_short_event_value_v1(event.get('posture'))} "
            f"mom={_short_event_value_v1(event.get('mom_distance'))} "
            f"nipple={_short_event_value_v1(event.get('nipple_state'))} "
            f"zone={_short_event_value_v1(event.get('zone'))}"
        )

    for index, event in enumerate(stale_events[:limit], start=1):
        lines.append(
            f"{prefix} stale[{index}]          : retrieval_cycle={_short_event_value_v1(event.get('retrieval_cycle_index'))} "
            f"why={_short_event_value_v1(event.get('why'))} "
            f"first_wrong={_short_event_value_v1(event.get('first_wrong_reason'))} "
            f"pred_error_after={_short_event_value_v1(event.get('pred_error_after'))}"
        )

    for index, event in enumerate(dissoc_events[:limit], start=1):
        lines.append(
            f"{prefix} dissoc[{index}]         : retrieval_cycle={_short_event_value_v1(event.get('retrieval_cycle_index'))} "
            f"first_wrong_cycle={_short_event_value_v1(event.get('first_wrong_cycle_index'))} "
            f"first_wrong={_short_event_value_v1(event.get('first_wrong_reason'))}"
        )

    for index, event in enumerate(loop_events[:limit], start=1):
        lines.append(
            f"{prefix} loop[{index}]           : step={_short_event_value_v1(event.get('env_step'))} "
            f"policy={_short_event_value_v1(event.get('policy'))} "
            f"streak={_short_event_value_v1(event.get('streak'))}"
        )

    if len(lines) == 1:
        lines.append(f"{prefix} lhsi_detail       : no detail events recorded")

    return lines


def demo_state_integrity_smoke_v1() -> dict[str, Any]:
    """Run a tiny built-in smoke test and return the resulting summary.

    This is not a scientific benchmark. It exists so the module can be tested
    immediately after being copied into the CCA8 folder:

        python cca8_state_integrity.py
    """
    raw_records = [
        {
            "env_step": 0,
            "scenario_stage": "birth",
            "posture": "fallen",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "zone": "unsafe",
            "policy_fired": "policy:stand_up",
            "action_applied": "policy:stand_up",
            "obs": {"predicates": ["posture:fallen"]},
            "wm": {"mapswitch": {"events": []}},
            "pred_err_v0": {},
        },
        {
            "env_step": 1,
            "scenario_stage": "first_stand",
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "zone": "unsafe",
            "policy_fired": "policy:seek_nipple",
            "action_applied": "policy:seek_nipple",
            "obs": {"predicates": ["posture:standing"]},
            "wm": {"mapswitch": {"events": []}},
            "pred_err_v0": {"posture": 0},
        },
        {
            "env_step": 2,
            "scenario_stage": "first_stand",
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "visible",
            "zone": "neutral",
            "policy_fired": "policy:follow_mom",
            "action_applied": "policy:follow_mom",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:found"]},
            "wm": {
                "mapswitch": {
                    "events": [
                        {
                            "reason": "newborn_b2:resume_after_blackout",
                            "ok": True,
                            "load": {
                                "mode": "merge",
                                "added_entities": 0,
                                "filled_slots": 1,
                                "added_edges": 0,
                                "stored_prior_cues": 0,
                            },
                        }
                    ]
                }
            },
            "pred_err_v0": {},
        },
        {
            "env_step": 3,
            "scenario_stage": "first_latch",
            "posture": "latched",
            "mom_distance": "near",
            "nipple_state": "latched",
            "zone": "safe",
            "policy_fired": "policy:suckle",
            "action_applied": "policy:suckle",
            "obs": {
                "predicates": [
                    "posture:standing",
                    "proximity:mom:close",
                    "nipple:found",
                    "nipple:latched",
                    "milk:drinking",
                ]
            },
            "wm": {"mapswitch": {"events": []}},
            "pred_err_v0": {},
        },
        {
            "env_step": 4,
            "scenario_stage": "rest",
            "posture": "resting",
            "mom_distance": "near",
            "nipple_state": "latched",
            "zone": "safe",
            "policy_fired": "policy:rest",
            "action_applied": "policy:rest",
            "obs": {
                "predicates": [
                    "posture:standing",
                    "proximity:mom:close",
                    "nipple:found",
                    "nipple:latched",
                    "milk:drinking",
                    "resting",
                ]
            },
            "wm": {"mapswitch": {"events": []}},
            "pred_err_v0": {},
        },
    ]

    return summarize_newborn_state_integrity_v1(raw_records)


if __name__ == "__main__":
    result = demo_state_integrity_smoke_v1()
    print("CCA8 Long-Horizon State-Integrity smoke test")
    for line in render_state_integrity_summary_lines_v1(result):
        print(line)
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))
