# -*- coding: utf-8 -*-
"""Regression test for the isolated autonomous newborn survival demo helper."""

from __future__ import annotations

from cca8_run import (
    render_autonomous_newborn_survival_demo_lines_v1,
    run_autonomous_newborn_survival_demo_v1,
)


def test_autonomous_newborn_survival_demo_helper_completes() -> None:
    """The menu-facing demo helper should complete the baseline hard newborn ladder."""
    result = run_autonomous_newborn_survival_demo_v1(max_cycles=60, show_timeline=False)

    assert result["ok"], result
    assert result["success"], "\n".join(render_autonomous_newborn_survival_demo_lines_v1(result))
    assert result["final_state"]["stage"] == "rest"
    assert result["final_state"]["posture"] == "resting"
    assert result["final_state"]["nipple_state"] == "latched"
    assert result["final_state"]["milk_ticks"] >= 3
    assert result["policy_counts"].get("policy:suckle", 0) > 0
    assert result["final_state"]["suckle_ticks"] >= 3
    assert result["policy_counts"].get("policy:rest", 0) >= 2