"""Focused regression tests for WorldGraph cycle-report accounting."""

from __future__ import annotations

from types import SimpleNamespace

import cca8_reporting
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation


_OBS_PREDICATES = [
    "posture:fallen",
    "proximity:mom:far",
    "proximity:shelter:far",
    "hazard:cliff:far",
]


def _worldgraph_line(capsys, *, written: list[str], keyframe: bool = False) -> str:
    """Render one footer and return only its WorldGraph accounting line."""
    ctx = Ctx()
    ctx.env_loop_cycle_summary = True
    ctx.wm_surfacegrid_enabled = False
    ctx.wm_navsummary_enabled = False
    ctx.controller_steps = 1
    if keyframe:
        ctx.lt_obs_last_keyframe_step = 1

    state = SimpleNamespace(
        scenario_stage="birth",
        kid_posture="fallen",
        mom_distance="far",
        nipple_state="hidden",
    )
    observation = EnvObservation(predicates=list(_OBS_PREDICATES), cues=[], env_meta={})
    token_to_bid = {token: f"b{index}" for index, token in enumerate(_OBS_PREDICATES, start=1)}
    injection = {
        "predicates": list(written),
        "cues": [],
        "token_to_bid": token_to_bid,
        "keyframe": keyframe,
        "keyframe_reasons": ["env_reset"] if keyframe else [],
    }

    cca8_reporting._print_cog_cycle_footer(  # pylint: disable=protected-access
        ctx=ctx,
        drives=Drives(hunger=0.5, fatigue=0.3, warmth=0.6),
        env_obs=observation,
        prev_state=None,
        curr_state=state,
        env_step=0,
        zone="unknown",
        inj=injection,
        fired_txt=None,
        col_store_txt=None,
        col_retrieve_txt=None,
        col_apply_txt=None,
        action_applied_this_step=None,
        next_action_for_env=None,
        cycle_no=1,
        cycle_total=1,
    )

    lines = capsys.readouterr().out.splitlines()
    return next(line for line in lines if line.startswith("[cycle] WG"))


def test_worldgraph_footer_distinguishes_initial_observation_from_four_new_writes(capsys) -> None:
    """The reset cycle should report four observed and four persisted predicates."""
    line = _worldgraph_line(capsys, written=_OBS_PREDICATES, keyframe=True)

    assert "observed preds=4 cues=0" in line
    assert "persisted_new preds=4 cues=0 keyframe=Y" in line
    assert "pred:posture:fallen" in line


def test_worldgraph_footer_reports_zero_new_writes_for_unchanged_observation(capsys) -> None:
    """Reused token_to_bid references must not masquerade as new persistent writes."""
    line = _worldgraph_line(capsys, written=[])

    assert "observed preds=4 cues=0" in line
    assert "persisted_new preds=0 cues=0" in line
    assert line.endswith("| (none) | (none)")


def test_worldgraph_footer_reports_only_one_changed_predicate_as_persisted(capsys) -> None:
    """A single slot change should persist one predicate while observing all four."""
    line = _worldgraph_line(capsys, written=["hazard:cliff:near"])

    assert "observed preds=4 cues=0" in line
    assert "persisted_new preds=1 cues=0" in line
    assert "pred:hazard:cliff:near" in line
    assert "pred:posture:fallen" not in line


def test_worldgraph_footer_retains_token_to_bid_fallback_for_legacy_schema(capsys) -> None:
    """Older injection schemas without explicit write lists should remain readable."""
    ctx = Ctx()
    ctx.env_loop_cycle_summary = True
    ctx.wm_surfacegrid_enabled = False
    ctx.wm_navsummary_enabled = False
    state = SimpleNamespace(
        scenario_stage="birth",
        kid_posture="fallen",
        mom_distance="far",
        nipple_state="hidden",
    )
    observation = EnvObservation(predicates=list(_OBS_PREDICATES), cues=[], env_meta={})

    cca8_reporting._print_cog_cycle_footer(  # pylint: disable=protected-access
        ctx=ctx,
        drives=Drives(),
        env_obs=observation,
        prev_state=None,
        curr_state=state,
        env_step=0,
        zone="unknown",
        inj={"token_to_bid": {token: f"b{index}" for index, token in enumerate(_OBS_PREDICATES, start=1)}},
        fired_txt=None,
        col_store_txt=None,
        col_retrieve_txt=None,
        col_apply_txt=None,
        action_applied_this_step=None,
        next_action_for_env=None,
        cycle_no=1,
        cycle_total=1,
    )

    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("[cycle] WG"))
    assert "persisted_new preds=4 cues=0" in line
