# -*- coding: utf-8 -*-
"""Compatibility tests for the extracted NavMap runtime subsystem."""

from __future__ import annotations

import cca8_navmap_runtime
import cca8_run

# The compatibility contract intentionally verifies historical private aliases.
# pylint: disable=protected-access

PUBLIC_RUNTIME_NAMES = (
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
)


def test_runner_reexports_navmap_runtime_and_registers_component() -> None:
    """Historical runner imports should resolve directly to the extracted module."""
    for name in PUBLIC_RUNTIME_NAMES:
        assert getattr(cca8_run, name) is getattr(cca8_navmap_runtime, name)

    assert cca8_run.NAVMAP_SCOPE_MARKER_V1 == cca8_navmap_runtime.NAVMAP_SCOPE_MARKER_V1
    assert cca8_run._navmap_safe_dict_v1 is cca8_navmap_runtime._navmap_safe_dict_v1
    assert cca8_run._navmap_slot_signature_from_slots_v1 is cca8_navmap_runtime._navmap_slot_signature_from_slots_v1

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["navmap_runtime"] == "cca8_navmap_runtime"
