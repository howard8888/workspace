#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the menu-module extraction from ``cca8_run.py``."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

import cca8_cli
import cca8_cognitive_scope_menu
import cca8_rcos_menu
import cca8_run
import cca8_session_menu
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_rcos import SimRobotGoatHAL


def test_runner_remains_below_eight_thousand_physical_lines() -> None:
    """Preserve the explicit maintainability milestone achieved by this refactor."""
    source_path = Path(cca8_run.__file__).resolve()
    physical_line_count = len(source_path.read_text(encoding="utf-8").splitlines())

    assert physical_line_count < 8_000


def test_runner_reexports_focused_menu_helpers() -> None:
    """Historical runner helper names should remain available after extraction."""
    assert cca8_run._watch_cognition_menu_v1 is cca8_cli.watch_cognition_menu_v1
    assert cca8_run._sim_robot_goat_obs_lines_v1 is cca8_rcos_menu.sim_robot_goat_obs_lines_v1
    assert cca8_run._sim_robot_goat_status_lines_v1 is cca8_rcos_menu.sim_robot_goat_status_lines_v1
    assert cca8_run._cognitive_scope_live_snapshot_v1 is cca8_cognitive_scope_menu.cognitive_scope_live_snapshot_v1


def test_episode_starting_state_menu_updates_and_clamps_explicit_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Menu 40 should retain its bounded editing behavior in the extracted module."""
    responses = iter(
        (
            "1.4",      # obs_mask_prob -> clamp 1.0
            "123",      # deterministic mask seed
            "",         # historical blank-means-toggle verbose behavior
            "on",       # auto-retrieve enabled
            "replace",  # auto-retrieve mode
            "-0.2",     # hunger -> clamp 0.0
            "1.4",      # fatigue -> clamp 1.0
            "0.4",      # warmth
            "-2",       # age_days -> clamp 0.0
        )
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)
    ctx = Ctx()
    ctx.obs_mask_verbose = True

    cca8_session_menu.configure_episode_starting_state_v1(drives, ctx)

    assert ctx.obs_mask_prob == 1.0
    assert ctx.obs_mask_seed == 123
    assert ctx.obs_mask_verbose is False
    assert ctx.wm_mapsurface_autoretrieve_enabled is True
    assert ctx.wm_mapsurface_autoretrieve_mode == "replace"
    assert drives.hunger == 0.0
    assert drives.fatigue == 1.0
    assert drives.warmth == 0.4
    assert ctx.age_days == 0.0


def test_retired_memory_guide_is_reference_only() -> None:
    """The extracted Menu 41 text should not pretend that the dead editor still runs."""
    text = cca8_session_menu.retired_memory_pipeline_guide_text_v1()

    assert 'currently "reference-only"' in text
    assert "does not run an interactive edit flow" in text
    assert "rl_enabled" in text
    assert "longterm_obs_enabled" in text


def test_rcos_menu_renderers_operate_without_runner_state() -> None:
    """Menu 50 presentation should use only the HAL observation/status contracts."""
    hal = SimRobotGoatHAL()
    observation = hal.reset(seed=7)

    observation_text = "\n".join(cca8_rcos_menu.sim_robot_goat_obs_lines_v1(observation))
    status_text = "\n".join(cca8_rcos_menu.sim_robot_goat_status_lines_v1(hal.status()))

    assert "[rcos] observation" in observation_text
    assert "predicates=" in observation_text
    assert "[rcos] status" in status_text
    assert "milestone_score=" in status_text
