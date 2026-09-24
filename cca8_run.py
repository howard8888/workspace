#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
*************************************

Software was developed in a Windows environment but should run with minimal changes in a macOS or Linux environment.
Requires Python 3.13
Please contact __  for inquiries about additional software modules, related
 materials, or ongoing development.

*************************************

CCA8 World Runner, i.e. the module that runs the CCA8 project

This script is the interactive and CLI entry point for the CCA8 simulation.
It provides an interactive banner + profile selector, wires the world graph
and a sample cortical column, offers HAL (embodiment) stubs, and exposes
preflight checks (lite at startup; full on demand).

The program is run at the command line interface:
        python cca8_run.py [FLAGS]

        e.g., > python cca8_run.py
        e.g., > python cca8_run.py --about
        e.g., > python cca8_run.py --preflight
        e.g., > python cca8_run.py --rcos-api

Key ideas for readers and new collaborators
------------------------------------------
- **Predicate**: a symbolic fact token (e.g., "posture:standing").
- **Binding**: a node instance carrying a predicate tag (`pred:<token>`) plus meta/engrams.
- **Edge**: a directed link between bindings with a label (often "then") for **weak causality**.
- **WorldGraph**: the small, fast *episode index* (~5% information). Rich content goes in engrams.
- **Policy (primitive)**: behavior object with `trigger(world, drives)` and `execute(world, ctx, drives)`.
  The Action Center scans the ordered list of policies and runs the first that triggers (one "controller step").
- **Autosave/Load**: JSON snapshot with `world`, `drives`, `skills`, plus a `saved_at` timestamp.

This runner presents an interactive menu for inspecting the world, planning, adding predicates,
emitting sensory cues, and running the Action Center ("Instinct step"). It also supports
non-interactive utility flags for scripting, like `--about`, `--version`.


Requirements
------------

Core runtime:
- Python 3.13.
- All CCA8 Python modules in the same repo directory, including:
  cca8_world_graph.py, cca8_controller.py,
  cca8_column.py, cca8_features.py, cca8_env.py, cca8_navpatch.py,
  cca8_rcos.py, cca8_rcos_experiments.py, cca8_state_integrity.py,
  cca8_teaching.py, cca8_test_fixtures.py, cca8_context.py, cca8_cli.py,
  cca8_experiments.py, cca8_openai.py, cca8_working_memory.py, cca8_profiles.py,
  cca8_guidance.py, cca8_predictive.py, cca8_navmap_runtime.py, cca8_maternal_geometry.py,
  cca8_maternal_temporal.py, cca8_maternal_continuity.py, cca8_followmom_compare.py,
  cca8_followmom_advisory.py, cca8_followmom_authority.py, cca8_feeding.py, cca8_terrain.py,
  cca8_live_dynamics.py, cca8_navmap_memory.py, cca8_wnm_runtime.py,
  cca8_cognitive_scope.py, cca8_cognitive_scope_menu.py, cca8_reporting.py,
  cca8_observation_runtime.py, cca8_policy_runtime.py, cca8_main_menu.py,
  cca8_session_menu.py, cca8_rcos_menu.py, and cca8_preflight.py.
- Standard-library imports such as argparse, json, hashlib, os, platform,
  sys, logging, math, datetime, dataclasses, typing, collections, random,
  time, subprocess, shutil, io, contextlib, copy, tempfile, webbrowser,
  xml, and ctypes are included with a normal Python installation.

Optional PyPI packages used by menu features / development workflow:
- pygount: Main Menu #12 lines-of-code report.
- pyvis: interactive graph export / display.
- psutil: optional richer system-memory check during preflight.
- openai: Main Menu #10 LLM setup and hybrid adviser experiments.
- pytest: unit-test runner used by --preflight.
- pytest-cov / Coverage.py: optional coverage tooling used only when explicitly requested with --preflight --coverage.
- pylint: external lint command used during development.
- mypy: external static type checker used during development.

Recommended setup on a fresh Windows Python 3.13 environment:
       py -m pip install --upgrade openai pyvis pygount psutil pytest pylint mypy

For a more standard repo layout, keep the same package list in requirements.txt
at the repo root and install with:
    py -m pip install -r requirements.txt

"""

# --- Pragmas and Imports -------------------------------------------------------------

# Style:Display notes:
#  -assume Windows default 120 column x 30+ line terminal display for displayed messages; translates well to macOS and Linux
#  -Main Menu limit to 80 column display but all other messages assume 120 columns
#  -code lines and docstrings -- try to respect 120 columns but ok to go over, generally try to keep under 200 columns
#  -ANSI colors ok but do not rely on them alone
#  -alert user visually if a task will take longer than 2 seconds
#  -if an error message can occur, then the user should see a human-readable, readily comprehensible error message

# pylint: disable=protected-access
#   we treat the cca8_runner module as a trusted friend module and thus silence warnings for acces to _objects
# pylint: disable=import-outside-toplevel
#   a number of the imports in profile/preflight stubs are by design and leave for now
# pylint: disable=duplicate-code
#   while there may be some (tiny) amount of duplicated code, it is not worth refactoring it into a common module, increases complexity

# Standard Library Imports
from __future__ import annotations
import argparse
import json
import os
import platform
import sys
import logging
from datetime import datetime
from typing import Optional, Any, Dict, List, Callable

# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
#import cca8_world_graph as wgmod  # modular alternative: allows swapping WorldGraph engines
import cca8_cli
import cca8_controller
import cca8_guidance
import cca8_profiles
import cca8_experiments
import cca8_openai
import cca8_predictive
import cca8_working_memory
import cca8_navmap
import cca8_navmap_runtime
import cca8_followmom_advisory
import cca8_followmom_authority
import cca8_followmom_compare
import cca8_feeding
import cca8_terrain
import cca8_live_dynamics
import cca8_main_menu
import cca8_navmap_memory
import cca8_wnm_runtime
import cca8_cognitive_scope
import cca8_cognitive_scope_menu
import cca8_cognitive_injection
import cca8_maternal_continuity
import cca8_maternal_geometry
import cca8_maternal_temporal
import cca8_standup_compare
import cca8_reporting
import cca8_observation_runtime
import cca8_policy_runtime
import cca8_preflight
import cca8_rcos_menu
import cca8_session_menu
import cca8_world_graph
from cca8_controller import (
    PRIMITIVES,
    skill_q,
    update_skill,
    skills_to_dict,
    skills_from_dict,
    Drives,
    action_center_step,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    bodymap_is_stale,
    body_cliff_distance,
    body_space_zone,
    _fallen_near_now,
    __version__ as controller_version,
)
from cca8_controller import body_shelter_distance  # pylint: disable=unused-import
from cca8_controller import body_cliff_is_near     # pylint: disable=unused-import
from cca8_controller import body_shelter_is_near   # pylint: disable=unused-import
from cca8_column import mem as column_mem
from cca8_env import HybridEnvironment, EnvObservation, EnvConfig  # environment simulation (HybridEnvironment/EnvState/EnvObservation)
from cca8_rcos import SimRobotGoatHAL
from cca8_context import CreativeCandidate, Ctx, ExperimentProtocolConfig  # pylint: disable=unused-import
from cca8_teaching import (
    menu37_teaching_after_controller_v1,
    menu37_teaching_after_observation_v1,
    menu37_teaching_after_run_v1,
    menu37_teaching_cycle_header_v1,
    menu37_teaching_intro_v1,
)
# Predictive-feedback implementations live in cca8_predictive. Importing the public API here preserves
# historical ``from cca8_run import ...`` callers while keeping the runner focused on orchestration.
from cca8_predictive import (
    latest_posture_binding_v1 as _latest_posture_binding,
    prediction_compare_pending_to_observed_v1,
    prediction_error_history_append_v1,
    prediction_error_record_apply_to_ctx_v1,
    prediction_feedback_mini_line_v1,
    prediction_feedback_step_from_ctx_obs_v1,
    prediction_feedback_summary_v1,
    prediction_next_record_from_policy_posture_v1,
    prediction_observed_slots_from_env_obs_v1,
    prediction_pending_record_from_ctx_v1,
    prediction_policy_expected_slots_v1,
    prediction_record_with_expected_slots_v1,
    prediction_source_for_execution_target_v1,
    render_prediction_feedback_lines_v1,
)

# Private prediction compatibility alias retained for historical runner imports.
_prediction_compact_map_text_v1 = cca8_predictive.compact_slot_map_text_v1

# --- NavMap runtime compatibility seam ------------------------------------------
# Pure NavMap schemas/operators remain in cca8_navmap. Runtime registers,
# expected/accepted-current processing, transitions, policy-outcome indexing,
# reporting, and the Oscilloscope now live in cca8_navmap_runtime. Historical
# cca8_run names remain direct aliases so downstream imports keep working.
make_navmap_payload_v1 = cca8_navmap.make_navmap_payload_v1
make_navmap_transition_v1 = cca8_navmap.make_navmap_transition_v1
navmap_observation_update_from_env_obs_v1 = cca8_navmap.navmap_observation_update_from_env_obs_v1
navmap_policy_outcome_from_transition_v1 = cca8_navmap.navmap_policy_outcome_from_transition_v1
navmap_residual_v1 = cca8_navmap.navmap_residual_v1

NAVMAP_SCOPE_MARKER_V1 = cca8_navmap_runtime.NAVMAP_SCOPE_MARKER_V1
NAVMAP_SCOPE_PROBES_V1 = cca8_navmap_runtime.NAVMAP_SCOPE_PROBES_V1
navmap_observation_update_summary_v1 = cca8_navmap_runtime.navmap_observation_update_summary_v1
render_navmap_observation_update_lines_v1 = cca8_navmap_runtime.render_navmap_observation_update_lines_v1
navmap_observation_update_mini_line_v1 = cca8_navmap_runtime.navmap_observation_update_mini_line_v1
navmap_observation_update_history_append_v1 = cca8_navmap_runtime.navmap_observation_update_history_append_v1
navmap_expected_current_summary_v1 = cca8_navmap_runtime.navmap_expected_current_summary_v1
render_navmap_expected_current_lines_v1 = cca8_navmap_runtime.render_navmap_expected_current_lines_v1
navmap_expected_current_mini_line_v1 = cca8_navmap_runtime.navmap_expected_current_mini_line_v1
navmap_expected_current_history_append_v1 = cca8_navmap_runtime.navmap_expected_current_history_append_v1
navmap_accepted_current_history_append_v1 = cca8_navmap_runtime.navmap_accepted_current_history_append_v1
navmap_accepted_current_from_comparison_v1 = cca8_navmap_runtime.navmap_accepted_current_from_comparison_v1
navmap_accepted_current_summary_v1 = cca8_navmap_runtime.navmap_accepted_current_summary_v1
render_navmap_accepted_current_lines_v1 = cca8_navmap_runtime.render_navmap_accepted_current_lines_v1
navmap_accepted_current_mini_line_v1 = cca8_navmap_runtime.navmap_accepted_current_mini_line_v1
working_navmap_surface_history_append_v1 = cca8_navmap_runtime.working_navmap_surface_history_append_v1
working_navmap_surface_from_accepted_current_v1 = cca8_navmap_runtime.working_navmap_surface_from_accepted_current_v1
working_navmap_surface_summary_v1 = cca8_navmap_runtime.working_navmap_surface_summary_v1
render_working_navmap_surface_lines_v1 = cca8_navmap_runtime.render_working_navmap_surface_lines_v1
working_navmap_surface_mini_line_v1 = cca8_navmap_runtime.working_navmap_surface_mini_line_v1
navmap_expected_current_payload_from_ctx_v1 = cca8_navmap_runtime.navmap_expected_current_payload_from_ctx_v1
navmap_expected_current_comparison_step_v1 = cca8_navmap_runtime.navmap_expected_current_comparison_step_v1
navmap_transition_summary_v1 = cca8_navmap_runtime.navmap_transition_summary_v1
render_navmap_transition_lines_v1 = cca8_navmap_runtime.render_navmap_transition_lines_v1
navmap_transition_mini_line_v1 = cca8_navmap_runtime.navmap_transition_mini_line_v1
navmap_scope_frame_v1 = cca8_navmap_runtime.navmap_scope_frame_v1
navmap_scope_frame_is_complete_v1 = cca8_navmap_runtime.navmap_scope_frame_is_complete_v1
navmap_scope_missing_probe_reasons_v1 = cca8_navmap_runtime.navmap_scope_missing_probe_reasons_v1
render_navmap_scope_frame_lines_v1 = cca8_navmap_runtime.render_navmap_scope_frame_lines_v1
render_navmap_scope_legend_lines_v1 = cca8_navmap_runtime.render_navmap_scope_legend_lines_v1
navmap_scope_mini_line_v1 = cca8_navmap_runtime.navmap_scope_mini_line_v1
navmap_transition_history_append_v1 = cca8_navmap_runtime.navmap_transition_history_append_v1
navmap_policy_outcome_index_update_v1 = cca8_navmap_runtime.navmap_policy_outcome_index_update_v1
navmap_ctx_observation_update_step_v1 = cca8_navmap_runtime.navmap_ctx_observation_update_step_v1
navmap_ctx_transition_from_payloads_v1 = cca8_navmap_runtime.navmap_ctx_transition_from_payloads_v1

# --- Phase 4A maternal geometry compatibility seam -----------------------------
# The SELF-maternal common-frame shadow is runtime-visible and traceable, but it
# remains non-authoritative for FollowMom in this slice.
maternal_geometry_shadow_summary_v1 = cca8_maternal_geometry.maternal_geometry_shadow_summary_v1
render_maternal_geometry_shadow_lines_v1 = cca8_maternal_geometry.render_maternal_geometry_shadow_lines_v1

# --- Phase 4B maternal temporal compatibility seam -----------------------------
# The bounded Sequential/Temporal shadow reads Phase 4A geometry-derived
# distance/bearing samples and remains non-authoritative for FollowMom.
maternal_temporal_shadow_summary_v1 = cca8_maternal_temporal.maternal_temporal_shadow_summary_v1
render_maternal_temporal_shadow_lines_v1 = cca8_maternal_temporal.render_maternal_temporal_shadow_lines_v1

# --- Phase 4C maternal continuity/localization compatibility seam -------------
# The shadow separates maternal identity/role persistence from observability,
# exact localization, uncertainty, and active-track status. It remains unable
# to alter FollowMom, BodyMap, PolicyRuntime, or protected safety.
maternal_continuity_shadow_summary_v1 = cca8_maternal_continuity.maternal_continuity_shadow_summary_v1
render_maternal_continuity_shadow_lines_v1 = cca8_maternal_continuity.render_maternal_continuity_shadow_lines_v1

# --- Phase 4D FollowMom compare compatibility seam -----------------------------
# The map path independently evaluates FollowMom applicability and compact
# expected relation outcomes. Legacy PolicyRuntime/controller selection and
# execution remain authoritative throughout this phase.
followmom_compare_selection_step_v1 = cca8_followmom_compare.followmom_compare_selection_step_v1
followmom_compare_summary_v1 = cca8_followmom_compare.followmom_compare_summary_v1
render_followmom_compare_lines_v1 = cca8_followmom_compare.render_followmom_compare_lines_v1

# --- Phase 4E-A FollowMom advisory compatibility seam --------------------------
# Advice distinguishes initial recruitment from supported continuation, but it
# cannot alter the legacy candidate set, selected primitive, action, or safety.
followmom_advisory_selection_step_v1 = cca8_followmom_advisory.followmom_advisory_selection_step_v1
followmom_advisory_summary_v1 = cca8_followmom_advisory.followmom_advisory_summary_v1
render_followmom_advisory_lines_v1 = cca8_followmom_advisory.render_followmom_advisory_lines_v1

# --- Phase 4E-B/4F FollowMom authority compatibility seam ----------------------
# Exact current identity-supported maternal evidence may control the bounded
# FollowMom gate. Default mode makes that WNM/NavMap path the normal cognitive
# source while protected legacy vetoes, explicit compatibility forces, and
# complete legacy fallback remain available.
followmom_authority_mode_v1 = cca8_followmom_authority.followmom_authority_mode_v1
followmom_authority_trigger_value_v1 = cca8_followmom_authority.followmom_authority_trigger_value_v1
followmom_authority_legacy_bridge_allowed_v1 = cca8_followmom_authority.followmom_authority_legacy_bridge_allowed_v1
followmom_authority_selection_step_v1 = cca8_followmom_authority.followmom_authority_selection_step_v1
followmom_authority_summary_v1 = cca8_followmom_authority.followmom_authority_summary_v1
followmom_authority_explain_v1 = cca8_followmom_authority.followmom_authority_explain_v1
render_followmom_authority_lines_v1 = cca8_followmom_authority.render_followmom_authority_lines_v1

# --- Phase 5 feeding / single-operative-WNM compatibility seam ----------------
# The Phase 4 SELF-maternal map becomes the coarse overview for one genuine
# overview -> maternal-body -> nipple-mouth -> return round-trip. Exactly one
# map is operative; ready maps retain no equal authority. SeekNipple and Suckle
# selection remain in PolicyRuntime while their expectations become map-native.
feeding_reset_v1 = cca8_feeding.feeding_reset_v1
feeding_selection_step_v1 = cca8_feeding.feeding_selection_step_v1
feeding_operative_readout_v1 = cca8_feeding.feeding_operative_readout_v1
feeding_milk_evidence_v1 = cca8_feeding.feeding_milk_evidence_v1
feeding_latch_evidence_v1 = cca8_feeding.feeding_latch_evidence_v1
feeding_summary_v1 = cca8_feeding.feeding_summary_v1
render_feeding_lines_v1 = cca8_feeding.render_feeding_lines_v1

# --- Phase 6 terrain / lateral route-sheet WNM compatibility seam ------------
# Two overlapping route sheets can become operative through explicit SELF and
# shared-landmark correspondence. The WNM-derived grid remains dual-run and
# its policy readout may only add a conservative safety veto.
terrain_reset_v1 = cca8_terrain.terrain_reset_v1
terrain_wnm_observation_step_v1 = cca8_terrain.terrain_wnm_observation_step_v1
terrain_policy_readout_v1 = cca8_terrain.terrain_policy_readout_v1
terrain_motion_veto_v1 = cca8_terrain.terrain_motion_veto_v1
terrain_safe_to_rest_v1 = cca8_terrain.terrain_safe_to_rest_v1
terrain_cliff_near_v1 = cca8_terrain.terrain_cliff_near_v1
terrain_route_clear_v1 = cca8_terrain.terrain_route_clear_v1
terrain_summary_v1 = cca8_terrain.terrain_summary_v1
render_terrain_lines_v1 = cca8_terrain.render_terrain_lines_v1

# --- Phase 7 generalized temporal binding / live-dynamics seam ---------------
# Compact typed samples reuse the existing bounded Sequential/Error window.
# Dynamic envelopes remain EXPECTED, structured residuals remain source-linked,
# and lower-controller feedback contains no detailed movement trajectory.
live_dynamics_reset_v1 = cca8_live_dynamics.live_dynamics_reset_v1
live_dynamics_observation_step_v1 = cca8_live_dynamics.live_dynamics_observation_step_v1
live_dynamics_overlay_v1 = cca8_live_dynamics.live_dynamics_overlay_v1
live_dynamics_summary_v1 = cca8_live_dynamics.live_dynamics_summary_v1
render_live_dynamics_lines_v1 = cca8_live_dynamics.render_live_dynamics_lines_v1

# --- Phase 8 long-term NavMap memory and sparse retrieval seam ----------------
# Immutable map payloads live in Columns; lightweight ctx-local index rows
# support bounded candidate-reference activation and selective reinstatement.
# Retrieval does not grant present truth or operative authority.
navmap_memory_request_strategic_retrieval_v1 = (
    cca8_navmap_memory.navmap_memory_request_strategic_retrieval_v1
)
navmap_memory_retrieve_v1 = cca8_navmap_memory.navmap_memory_retrieve_v1
navmap_memory_replay_eligible_refs_v1 = cca8_navmap_memory.navmap_memory_replay_eligible_refs_v1
navmap_memory_reset_episode_v1 = cca8_navmap_memory.navmap_memory_reset_episode_v1
navmap_memory_summary_v1 = cca8_navmap_memory.navmap_memory_summary_v1
render_navmap_memory_lines_v1 = cca8_navmap_memory.render_navmap_memory_lines_v1

wnm_operative_map_v1 = cca8_wnm_runtime.wnm_operative_map_v1
wnm_ready_maps_v1 = cca8_wnm_runtime.wnm_ready_maps_v1
wnm_admit_ready_map_v1 = cca8_wnm_runtime.wnm_admit_ready_map_v1
wnm_commit_transition_v1 = cca8_wnm_runtime.wnm_commit_transition_v1
wnm_return_to_ref_v1 = cca8_wnm_runtime.wnm_return_to_ref_v1
wnm_summary_v1 = cca8_wnm_runtime.wnm_summary_v1
render_wnm_lines_v1 = cca8_wnm_runtime.render_wnm_lines_v1

# --- Phase 3A/3B/3C/3D StandUp authority compatibility seam -------------------
# The map-native query, expected-successor, advisory, and authority records live
# in their own module. Phase 3D makes the validated WNM/NavMap query the default
# StandUp cognitive source; explicit guarded/legacy modes remain available.
# PolicyRuntime/controller execution and protected BodyMap safety remain intact.
standup_compare_selection_step_v1 = cca8_standup_compare.standup_compare_selection_step_v1
standup_compare_summary_v1 = cca8_standup_compare.standup_compare_summary_v1
render_standup_compare_lines_v1 = cca8_standup_compare.render_standup_compare_lines_v1
standup_advisory_selection_step_v1 = cca8_standup_compare.standup_advisory_selection_step_v1
standup_advisory_summary_v1 = cca8_standup_compare.standup_advisory_summary_v1
render_standup_advisory_lines_v1 = cca8_standup_compare.render_standup_advisory_lines_v1
standup_authority_mode_v1 = cca8_standup_compare.standup_authority_mode_v1
standup_guarded_selection_step_v1 = cca8_standup_compare.standup_guarded_selection_step_v1
standup_guarded_summary_v1 = cca8_standup_compare.standup_guarded_summary_v1
standup_authority_summary_v1 = cca8_standup_compare.standup_authority_summary_v1
render_standup_guarded_lines_v1 = cca8_standup_compare.render_standup_guarded_lines_v1
render_standup_authority_lines_v1 = cca8_standup_compare.render_standup_authority_lines_v1

# Private aliases preserve existing maintainer/test access during the extraction.
_navmap_safe_dict_v1 = cca8_navmap_runtime._navmap_safe_dict_v1
_navmap_safe_list_count_v1 = cca8_navmap_runtime._navmap_safe_list_count_v1
_navmap_safe_int_v1 = cca8_navmap_runtime._navmap_safe_int_v1
_navmap_safe_float_or_none_v1 = cca8_navmap_runtime._navmap_safe_float_or_none_v1
_navmap_slots_from_payload_dict_v1 = cca8_navmap_runtime._navmap_slots_from_payload_dict_v1
_navmap_transition_slot_change_text_v1 = cca8_navmap_runtime._navmap_transition_slot_change_text_v1
_navmap_compact_list_text_v1 = cca8_navmap_runtime._navmap_compact_list_text_v1
_navmap_scope_compact_missing_text_v1 = cca8_navmap_runtime._navmap_scope_compact_missing_text_v1
_navmap_scope_probe_status_text_v1 = cca8_navmap_runtime._navmap_scope_probe_status_text_v1
_navmap_slot_signature_from_slots_v1 = cca8_navmap_runtime._navmap_slot_signature_from_slots_v1
_navmap_policy_index_row_for_action_v1 = cca8_navmap_runtime._navmap_policy_index_row_for_action_v1
_navmap_expected_current_safety_slots_v1 = cca8_navmap_runtime._navmap_expected_current_safety_slots_v1
_navmap_expected_current_evidence_override_slots_v1 = cca8_navmap_runtime._navmap_expected_current_evidence_override_slots_v1
_navmap_accepted_current_label_v1 = cca8_navmap_runtime._navmap_accepted_current_label_v1

# --- Runtime reporting compatibility seam --------------------------------------
# Dynamic snapshots, terminal HUDs, cycle-footer reporting, transcript teeing,
# and small developer utilities now live in cca8_reporting. Historical runner
# names remain direct aliases so menus, tests, and downstream imports continue
# to use the same surface.
TeeTextIO = cca8_reporting.TeeTextIO
install_terminal_tee = cca8_reporting.install_terminal_tee
print_startup_notices = cca8_reporting.print_startup_notices
print_working_map_snapshot = cca8_reporting.print_working_map_snapshot
print_working_map_layers = cca8_reporting.print_working_map_layers
print_working_map_entity_table = cca8_reporting.print_working_map_entity_table
_snapshot_timekeeping_legend = cca8_reporting._snapshot_timekeeping_legend
timekeeping_line = cca8_reporting.timekeeping_line
timekeeping_status_text_v1 = cca8_reporting.timekeeping_status_text_v1
print_timekeeping_line = cca8_reporting.print_timekeeping_line
_python_loc_counts_for_file = cca8_reporting._python_loc_counts_for_file
_compute_loc_by_dir = cca8_reporting._compute_loc_by_dir
_render_loc_by_dir_table = cca8_reporting._render_loc_by_dir_table
_parse_vector = cca8_reporting._parse_vector
snapshot_text = cca8_reporting.snapshot_text
export_snapshot = cca8_reporting.export_snapshot
architecture_status_text_v1 = cca8_reporting.architecture_status_text_v1
recent_bindings_text = cca8_reporting.recent_bindings_text
print_env_loop_tag_legend_once = cca8_reporting.print_env_loop_tag_legend_once
_quiet_solved_rest_tail_v1 = cca8_reporting._quiet_solved_rest_tail_v1
_print_cog_cycle_footer = cca8_reporting._print_cog_cycle_footer
mini_snapshot_text = cca8_reporting.mini_snapshot_text
print_mini_snapshot = cca8_reporting.print_mini_snapshot
drives_and_tags_text = cca8_reporting.drives_and_tags_text
skill_ledger_text = cca8_reporting.skill_ledger_text
skills_hud_text = cca8_reporting.skills_hud_text
_io_banner = cca8_reporting._io_banner


def _surfacegrid_ascii_terminal_block_v1(
    ctx: Ctx,
    sg,
    *,
    sig16: str,
    line_prefix: str = "",
    title: Optional[str] = None,
    legend: Optional[str] = None,
) -> str:
    """Render a SurfaceGrid block through runner-visible formatting hooks."""
    return cca8_working_memory._surfacegrid_ascii_terminal_block_v1(
        ctx,
        sg,
        sig16=sig16,
        line_prefix=line_prefix,
        title=title,
        legend=legend,
        ascii_text_fn=_surfacegrid_ascii_text_v1,
        format_map_fn=format_surfacegrid_ascii_map_v1,
    )


# --- Observation-ingestion compatibility seam ---------------------------------
# BodyMap construction, sequential/error processing, observation masking,
# keyframe detection, short-lived map handoffs, sparse WorldGraph writes, and
# cycle JSON logging now live in cca8_observation_runtime. Runtime-sensitive
# callbacks resolve through the runner at call time to preserve historical
# monkeypatch and preflight seams.
ObservationRuntime = cca8_observation_runtime.ObservationRuntime
init_body_world = cca8_observation_runtime.init_body_world
update_body_world_from_obs = cca8_observation_runtime.update_body_world_from_obs
seqerr_update_from_obs = cca8_observation_runtime.seqerr_update_from_obs
_inject_simple_valence_like_mom = cca8_observation_runtime._inject_simple_valence_like_mom
append_cycle_json_record = cca8_observation_runtime.append_cycle_json_record


def _write_spatial_scene_edges(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    token_to_bid: Dict[str, str],
) -> None:
    """Write extracted spatial observation edges through runner graph helpers."""
    cca8_observation_runtime._write_spatial_scene_edges(
        world,
        ctx,
        env_obs,
        token_to_bid,
        anchor_id_fn=_anchor_id,
        add_spatial_relation_fn=add_spatial_relation,
    )


def _observation_runtime_v1() -> ObservationRuntime:
    """Build the runner-to-observation-ingestion callback bridge."""
    return ObservationRuntime(
        newborn_stress_profile_from_ctx=_newborn_stress_profile_from_ctx_v1,
        newborn_conflicted_repair_status=_newborn_conflicted_repair_status_v1,
        update_body_world_from_obs=update_body_world_from_obs,
        seqerr_update_from_obs=seqerr_update_from_obs,
        update_surface_grid_from_obs=update_surface_grid_from_obs,
        update_map_surface_from_obs=update_map_surface_from_obs,
        predcode_update_from_obs=predcode_update_from_obs,
        navpatch_predictive_match_loop=navpatch_predictive_match_loop_v1,
        inject_obs_into_working_world=inject_obs_into_working_world,
        navmap_ctx_observation_update_step=navmap_ctx_observation_update_step_v1,
        write_spatial_scene_edges=_write_spatial_scene_edges,
        inject_simple_valence_like_mom=_inject_simple_valence_like_mom,
    )


def inject_obs_into_world(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
) -> dict[str, Any]:
    """Run the extracted observation-ingestion pipeline through runner hooks."""
    return cca8_observation_runtime.inject_obs_into_world(
        world,
        ctx,
        env_obs,
        runtime=_observation_runtime_v1(),
    )


# --- Policy-runtime compatibility seam ----------------------------------------
# Gate logic, newborn control bridges, EFE diagnostics, PolicyGate/PolicyRuntime,
# the gate catalog, and Creative candidate scoring now live in
# cca8_policy_runtime. The hook bundle stores lambdas that resolve runner names
# at call time, preserving historical monkeypatch and preflight seams without a
# circular import.
PolicyRuntimeHooks = cca8_policy_runtime.PolicyRuntimeHooks


# The lambdas are intentional: each resolves the current runner name when called,
# preserving historical monkeypatch seams rather than freezing function objects.
# pylint: disable=unnecessary-lambda
def _policy_runtime_hooks_v1() -> PolicyRuntimeHooks:
    """Build the runner-to-policy-runtime dependency bridge."""
    return PolicyRuntimeHooks(
        bodymap_is_stale=lambda *args, **kwargs: bodymap_is_stale(*args, **kwargs),
        body_posture=lambda *args, **kwargs: body_posture(*args, **kwargs),
        body_mom_distance=lambda *args, **kwargs: body_mom_distance(*args, **kwargs),
        body_nipple_state=lambda *args, **kwargs: body_nipple_state(*args, **kwargs),
        body_shelter_distance=lambda *args, **kwargs: body_shelter_distance(*args, **kwargs),
        body_cliff_distance=lambda *args, **kwargs: body_cliff_distance(*args, **kwargs),
        body_space_zone=lambda *args, **kwargs: body_space_zone(*args, **kwargs),
        fallen_near_now=lambda *args, **kwargs: _fallen_near_now(*args, **kwargs),
        has_pred_near_now=lambda *args, **kwargs: has_pred_near_now(*args, **kwargs),
        any_cue_tokens_present=lambda *args, **kwargs: any_cue_tokens_present(*args, **kwargs),
        present_cue_bids=lambda *args, **kwargs: present_cue_bids(*args, **kwargs),
        newborn_active_retrieved_hint=lambda *args, **kwargs: _newborn_active_retrieved_hint_v1(
            *args, **kwargs
        ),
        newborn_stress_profile_from_ctx=lambda *args, **kwargs: _newborn_stress_profile_from_ctx_v1(
            *args, **kwargs
        ),
        goat04_context_hint_active=lambda *args, **kwargs: _goat04_context_hint_active_v1(*args, **kwargs),
        experiment_policy_debug_record=lambda *args, **kwargs: _experiment_policy_debug_record_v1(
            *args, **kwargs
        ),
        experiment_llm_candidate_rows=lambda *args, **kwargs: _experiment_llm_candidate_rows_v1(
            *args, **kwargs
        ),
        run_experiment_llm_adviser_once=lambda *args, **kwargs: _run_experiment_llm_adviser_once_v1(
            *args, **kwargs
        ),
        experiment_metric_text=lambda *args, **kwargs: _experiment_metric_text_v1(*args, **kwargs),
        choose_contextual_base=lambda *args, **kwargs: choose_contextual_base(*args, **kwargs),
        compute_foa=lambda *args, **kwargs: compute_foa(*args, **kwargs),
        candidate_anchors=lambda *args, **kwargs: candidate_anchors(*args, **kwargs),
        action_center_step=lambda *args, **kwargs: action_center_step(*args, **kwargs),
        skill_q=lambda *args, **kwargs: skill_q(*args, **kwargs),
        update_skill=lambda *args, **kwargs: update_skill(*args, **kwargs),
        register_policy_scratch_chain=lambda *args, **kwargs: (
            cca8_working_memory.register_policy_scratch_chain_v1(*args, **kwargs)
        ),
        policy_primitives=lambda: PRIMITIVES,
        standup_guarded_trigger=lambda *args, **kwargs: (
            cca8_standup_compare.standup_guarded_trigger_value_v1(*args, **kwargs)
        ),
        standup_guarded_safety_active=lambda *args, **kwargs: (
            cca8_standup_compare.standup_guarded_safety_active_v1(*args, **kwargs)
        ),
        standup_guarded_explain=lambda *args, **kwargs: (
            cca8_standup_compare.standup_guarded_explain_v1(*args, **kwargs)
        ),
        followmom_authority_trigger=lambda *args, **kwargs: (
            cca8_followmom_authority.followmom_authority_trigger_value_v1(*args, **kwargs)
        ),
        followmom_authority_explain=lambda *args, **kwargs: (
            cca8_followmom_authority.followmom_authority_explain_v1(*args, **kwargs)
        ),
        followmom_authority_legacy_bridge_allowed=lambda *args, **kwargs: (
            cca8_followmom_authority.followmom_authority_legacy_bridge_allowed_v1(*args, **kwargs)
        ),
    )


# pylint: enable=unnecessary-lambda
cca8_policy_runtime.configure_policy_runtime_hooks(_policy_runtime_hooks_v1())

PolicyGate = cca8_policy_runtime.PolicyGate
PolicyRuntime = cca8_policy_runtime.PolicyRuntime
CATALOG_GATES = cca8_policy_runtime.CATALOG_GATES

_wm_navsummary_get_v1 = cca8_policy_runtime._wm_navsummary_get_v1
_wm_navsummary_bool_v1 = cca8_policy_runtime._wm_navsummary_bool_v1
_wm_navsummary_int_v1 = cca8_policy_runtime._wm_navsummary_int_v1
_wm_navsummary_float_v1 = cca8_policy_runtime._wm_navsummary_float_v1
_wm_navsummary_explain_bits_v1 = cca8_policy_runtime._wm_navsummary_explain_bits_v1
_wm_follow_mom_blocked_by_topology_v1 = cca8_policy_runtime._wm_follow_mom_blocked_by_topology_v1
_wm_probe_supported_by_topology_v1 = cca8_policy_runtime._wm_probe_supported_by_topology_v1
_gate_stand_up_trigger_body_first = cca8_policy_runtime._gate_stand_up_trigger_body_first
_gate_stand_up_explain = cca8_policy_runtime._gate_stand_up_explain
_gate_seek_nipple_trigger_body_first = cca8_policy_runtime._gate_seek_nipple_trigger_body_first
_gate_seek_nipple_explain = cca8_policy_runtime._gate_seek_nipple_explain
_gate_rest_trigger_body_space = cca8_policy_runtime._gate_rest_trigger_body_space
_gate_rest_explain_body_space = cca8_policy_runtime._gate_rest_explain_body_space
_record_newborn_guarded_field_use_v1 = cca8_policy_runtime._record_newborn_guarded_field_use_v1
_newborn_workingmap_state_v1 = cca8_policy_runtime._newborn_workingmap_state_v1
_follow_mom_bridge_state_v1 = cca8_policy_runtime._follow_mom_bridge_state_v1
_newborn_conflicted_repair_status_v1 = cca8_policy_runtime._newborn_conflicted_repair_status_v1
_newborn_conflicted_repair_gate_state_v1 = cca8_policy_runtime._newborn_conflicted_repair_gate_state_v1
_newborn_recent_retrieval_ok_v1 = cca8_policy_runtime._newborn_recent_retrieval_ok_v1
_newborn_follow_fallback_blocked_without_memory_v1 = (
    cca8_policy_runtime._newborn_follow_fallback_blocked_without_memory_v1
)
_should_force_follow_mom_bridge_v1 = cca8_policy_runtime._should_force_follow_mom_bridge_v1
_newborn_milk_drinking_slot_seen_v1 = cca8_policy_runtime._newborn_milk_drinking_slot_seen_v1
_should_force_rest_bridge_v1 = cca8_policy_runtime._should_force_rest_bridge_v1
_should_quiesce_rest_v1 = cca8_policy_runtime._should_quiesce_rest_v1
_newborn_post_latch_sequence_active_v1 = cca8_policy_runtime._newborn_post_latch_sequence_active_v1
_bodymap_slot_has_pred_v1 = cca8_policy_runtime._bodymap_slot_has_pred_v1
_newborn_graph_has_pred_anywhere_v1 = cca8_policy_runtime._newborn_graph_has_pred_anywhere_v1
_newborn_pred_seen_in_control_worlds_v1 = cca8_policy_runtime._newborn_pred_seen_in_control_worlds_v1
_newborn_milk_drinking_current_v1 = cca8_policy_runtime._newborn_milk_drinking_current_v1
_should_force_newborn_rest_after_milk_v1 = cca8_policy_runtime._should_force_newborn_rest_after_milk_v1
_should_force_suckle_bridge_v1 = cca8_policy_runtime._should_force_suckle_bridge_v1
_gate_suckle_trigger_newborn_v1 = cca8_policy_runtime._gate_suckle_trigger_newborn_v1
_gate_suckle_explain_newborn_v1 = cca8_policy_runtime._gate_suckle_explain_newborn_v1
_gate_follow_mom_trigger_body_space = cca8_policy_runtime._gate_follow_mom_trigger_body_space
_gate_follow_mom_explain_body_space = cca8_policy_runtime._gate_follow_mom_explain_body_space
_gate_probe_ambiguity_trigger_body_first = cca8_policy_runtime._gate_probe_ambiguity_trigger_body_first
_gate_probe_ambiguity_explain_body_first = cca8_policy_runtime._gate_probe_ambiguity_explain_body_first
_gate_recover_fall_trigger_body_first = cca8_policy_runtime._gate_recover_fall_trigger_body_first
_gate_recover_fall_explain = cca8_policy_runtime._gate_recover_fall_explain
_EFE_SCORES_VERSION = cca8_policy_runtime._EFE_SCORES_VERSION
_clamp01 = cca8_policy_runtime._clamp01
_norm_deficit = cca8_policy_runtime._norm_deficit
_norm_cold = cca8_policy_runtime._norm_cold
_efe_zone_from_ctx = cca8_policy_runtime._efe_zone_from_ctx
_efe_stage_from_ctx = cca8_policy_runtime._efe_stage_from_ctx
_efe_global_ambiguity_from_navpatch = cca8_policy_runtime._efe_global_ambiguity_from_navpatch
_efe_risk_stub_v1 = cca8_policy_runtime._efe_risk_stub_v1
_efe_preference_stub_v1 = cca8_policy_runtime._efe_preference_stub_v1
_efe_ambiguity_stub_v1 = cca8_policy_runtime._efe_ambiguity_stub_v1
compute_efe_scores_stub_v1 = cca8_policy_runtime.compute_efe_scores_stub_v1
_efe_render_summary_line = cca8_policy_runtime._efe_render_summary_line
_safe = cca8_policy_runtime._safe
_wm_creative_update = cca8_policy_runtime._wm_creative_update


# --- Public API index, version, global variables and constants ----------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.30.39"
__all__ = [
    "main",
    "interactive_loop",
    "run_preflight_full",
    "snapshot_text",
    "architecture_status_text_v1",
    "print_architecture_overview_v1",
    "prediction_feedback_summary_v1",
    "prediction_next_record_from_policy_posture_v1",
    "prediction_source_for_execution_target_v1",
    "prediction_pending_record_from_ctx_v1",
    "prediction_compare_pending_to_observed_v1",
    "prediction_feedback_step_from_ctx_obs_v1",
    "prediction_policy_expected_slots_v1",
    "prediction_record_with_expected_slots_v1",
    "prediction_error_history_append_v1",
    "prediction_error_record_apply_to_ctx_v1",
    "render_prediction_feedback_lines_v1",
    "prediction_feedback_mini_line_v1",
    "prediction_observed_slots_from_env_obs_v1",
    "export_snapshot",
    "world_delete_edge",
    "boot_prime_stand",
    "save_session",
    "versions_dict",
    "versions_text",
    "choose_contextual_base",
    "compute_foa",
    "candidate_anchors",
    "register_policy_scratch_chain_v1",
    "__version__",
    "Ctx",
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
    "maternal_geometry_shadow_summary_v1",
    "render_maternal_geometry_shadow_lines_v1",
    "maternal_temporal_shadow_summary_v1",
    "render_maternal_temporal_shadow_lines_v1",
    "maternal_continuity_shadow_summary_v1",
    "render_maternal_continuity_shadow_lines_v1",
    "followmom_compare_selection_step_v1",
    "followmom_compare_summary_v1",
    "render_followmom_compare_lines_v1",
    "followmom_advisory_selection_step_v1",
    "followmom_advisory_summary_v1",
    "render_followmom_advisory_lines_v1",
    "followmom_authority_mode_v1",
    "followmom_authority_trigger_value_v1",
    "followmom_authority_legacy_bridge_allowed_v1",
    "followmom_authority_selection_step_v1",
    "followmom_authority_summary_v1",
    "followmom_authority_explain_v1",
    "render_followmom_authority_lines_v1",
    "feeding_reset_v1",
    "feeding_selection_step_v1",
    "feeding_operative_readout_v1",
    "feeding_milk_evidence_v1",
    "feeding_latch_evidence_v1",
    "feeding_summary_v1",
    "render_feeding_lines_v1",
    "terrain_reset_v1",
    "terrain_wnm_observation_step_v1",
    "terrain_policy_readout_v1",
    "terrain_motion_veto_v1",
    "terrain_safe_to_rest_v1",
    "terrain_cliff_near_v1",
    "terrain_route_clear_v1",
    "terrain_summary_v1",
    "render_terrain_lines_v1",
    "live_dynamics_reset_v1",
    "live_dynamics_observation_step_v1",
    "live_dynamics_overlay_v1",
    "live_dynamics_summary_v1",
    "render_live_dynamics_lines_v1",
    "navmap_memory_request_strategic_retrieval_v1",
    "navmap_memory_retrieve_v1",
    "navmap_memory_replay_eligible_refs_v1",
    "navmap_memory_reset_episode_v1",
    "navmap_memory_summary_v1",
    "render_navmap_memory_lines_v1",
    "wnm_operative_map_v1",
    "wnm_ready_maps_v1",
    "wnm_admit_ready_map_v1",
    "wnm_commit_transition_v1",
    "wnm_return_to_ref_v1",
    "wnm_summary_v1",
    "render_wnm_lines_v1",
    "standup_compare_selection_step_v1",
    "standup_compare_summary_v1",
    "render_standup_compare_lines_v1",
    "standup_advisory_selection_step_v1",
    "standup_advisory_summary_v1",
    "render_standup_advisory_lines_v1",
    "standup_authority_mode_v1",
    "standup_guarded_selection_step_v1",
    "standup_guarded_summary_v1",
    "standup_authority_summary_v1",
    "render_standup_guarded_lines_v1",
    "render_standup_authority_lines_v1",
    "HAL",
    "PolicyRuntime",
    "run_autonomous_newborn_survival_demo_v1",
    "render_autonomous_newborn_survival_demo_lines_v1",
    "ExperimentConditionDef",
    "ExperimentBenchmarkDef",
    "ExperimentProtocolConfig",
    "experiment_normalize_protocol_v1",
    "experiment_make_run_id_v1",
    "experiment_jsonl_paths_v1",
    "experiment_prepare_logging_v1",
    "append_experiment_jsonl_record_v1",
    "experiment_write_episode_record_v1",
    "experiment_build_cycle_record_stub_v1",
    "experiment_build_episode_record_stub_v1",
    "experiment_make_sandbox_runtime_v1",
    "experiment_configure_benchmark_runtime_v1",
    "experiment_apply_condition_runtime_v1",
    "experiment_run_one_episode_v1",
    "experiment_run_condition_batch_v1",
    "render_experiment_batch_summary_lines_v1",
    "render_experiment_protocol_summary_v1",
    "OpenAIRuntime",
    "build_cca8_llm_state_summary_v1",
    "openai_menu_48_interactive",
    "ProfileOperations",
    "ProfileRuntime",
    "TutorialRuntime",
]

NON_WIN_LINUX = False  #set if non-Win, non-macOS, non-Linux/like OS
PLACEHOLDER_EMBODIMENT = '0.0.0 : none specified'
# Compatibility aliases for callers that historically accessed CLI constants
# and the logo function through cca8_run.
TECH_MANUAL = cca8_cli.TECH_MANUAL
ASCII_LOGOS = cca8_cli.ASCII_LOGOS
print_ascii_logo = cca8_cli.print_ascii_logo


# --- Profiles and explanatory guidance compatibility seam ---------------------------
# Startup profile selection/narratives live in cca8_profiles.  Static help and
# the hands-on new-user tour live in cca8_guidance.  Runner-visible wrappers
# preserve historical imports and resolve callbacks at call time.
ProfileRuntime = cca8_profiles.ProfileRuntime
ProfileOperations = cca8_profiles.ProfileOperations
TutorialRuntime = cca8_guidance.TutorialRuntime

_goat_defaults = cca8_profiles._goat_defaults
_print_goat_fallback = cca8_profiles._print_goat_fallback
profile_rcos_api = cca8_profiles.profile_rcos_api
profile_chimpanzee = cca8_profiles.profile_chimpanzee
profile_human = cca8_profiles.profile_human
profile_multi_brains_adv_planning = cca8_profiles.profile_multi_brains_adv_planning
profile_superhuman = cca8_profiles.profile_superhuman
profile_cca11_governed_cognitive_plurality = cca8_profiles.profile_cca11_governed_cognitive_plurality
profile_cca12_governed_pod = cca8_profiles.profile_cca12_governed_pod
_open_readme_tutorial = cca8_profiles.open_readme_tutorial
print_tagging_and_policies_help = cca8_guidance.print_tagging_and_policies_help
print_architecture_overview_v1 = cca8_guidance.print_architecture_overview_v1


def _profile_runtime_v1() -> ProfileRuntime:
    """Build profile-demo operations from current runner-visible dependencies."""
    return ProfileRuntime(
        world_factory=cca8_world_graph.WorldGraph,
        world_from_dict=cca8_world_graph.WorldGraph.from_dict,
        drives_factory=Drives,
        action_center_step=action_center_step,
    )


def profile_human_multi_brains(ctx: Any, world: Any) -> tuple[str, int]:
    """Run the extracted multi-brain profile scaffold through current runner dependencies."""
    return cca8_profiles.profile_human_multi_brains(ctx, world, runtime=_profile_runtime_v1())


def profile_society_multi_agents(ctx: Any) -> tuple[str, int]:
    """Run the extracted society profile scaffold through current runner dependencies."""
    return cca8_profiles.profile_society_multi_agents(ctx, runtime=_profile_runtime_v1())


def _profile_operations_v1() -> ProfileOperations:
    """Build profile-selection callbacks from the runner compatibility surface."""
    return ProfileOperations(
        open_tutorial=_open_readme_tutorial,
        chimpanzee=profile_chimpanzee,
        human=profile_human,
        human_multi_brains=profile_human_multi_brains,
        society_multi_agents=profile_society_multi_agents,
        multi_brains_adv_planning=profile_multi_brains_adv_planning,
        superhuman=profile_superhuman,
        cca11=profile_cca11_governed_cognitive_plurality,
        cca12=profile_cca12_governed_pod,
    )


def choose_profile(ctx: Any, world: Any) -> dict[str, Any]:
    """Prompt through the extracted profile chooser using current runner callbacks."""
    return cca8_profiles.choose_profile(ctx, world, operations=_profile_operations_v1())


def _tutorial_binding_engrams_v1(world: Any, bid: str) -> Any:
    """Return one binding's engram map for the extracted tutorial bridge."""
    try:
        binding = world._bindings.get(bid)
    except Exception:
        return None
    return getattr(binding, "engrams", None) if binding is not None else None


def _tutorial_runtime_v1() -> TutorialRuntime:
    """Build tutorial operations from the runner compatibility surface."""
    return TutorialRuntime(
        snapshot_text=snapshot_text,
        sorted_bids=_sorted_bids,
        engrams_on_binding=_engrams_on_binding,
        binding_engrams=_tutorial_binding_engrams_v1,
        action_center_step=action_center_step,
    )


def run_new_user_tour(
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    autosave_cb: Optional[Callable[[], None]] = None,
) -> None:
    """Run the extracted new-user tour through current runner callbacks."""
    cca8_guidance.run_new_user_tour(
        world,
        drives,
        ctx,
        policy_rt,
        autosave_cb,
        runtime=_tutorial_runtime_v1(),
    )


# --- OpenAI / LLM compatibility seam ---------------------------------------------
# The implementation lives in cca8_openai. Runner-visible names remain available
# so existing imports, preflight hooks, experiment callbacks, and focused tests
# continue to work.
OpenAIRuntime = cca8_openai.OpenAIRuntime
OpenAIAdvancedMenuOperations = cca8_openai.OpenAIAdvancedMenuOperations
OpenAIMenuOperations = cca8_openai.OpenAIMenuOperations

OPENAI_REASONING_EFFORT_OPTIONS = cca8_openai.OPENAI_REASONING_EFFORT_OPTIONS
OPENAI_ADVANCED_ENV_NAMES = cca8_openai.OPENAI_ADVANCED_ENV_NAMES

_save_openai_api_key_windows_user_env = cca8_openai._save_openai_api_key_windows_user_env
_openai_sdk_version_text = cca8_openai._openai_sdk_version_text
_openai_default_model_name = cca8_openai._openai_default_model_name
_save_cca8_openai_model_windows_user_env = cca8_openai._save_cca8_openai_model_windows_user_env
_save_windows_user_env = cca8_openai._save_windows_user_env
_delete_windows_user_env = cca8_openai._delete_windows_user_env
_openai_temperature_value = cca8_openai._openai_temperature_value
_openai_top_p_value = cca8_openai._openai_top_p_value
_openai_max_output_tokens_value = cca8_openai._openai_max_output_tokens_value
_openai_reasoning_effort_value = cca8_openai._openai_reasoning_effort_value
_openai_advanced_settings_snapshot = cca8_openai._openai_advanced_settings_snapshot
_openai_advanced_settings_one_line = cca8_openai._openai_advanced_settings_one_line
_openai_response_request_options_v1 = cca8_openai._openai_response_request_options_v1
_openai_quiet_http_loggers_v1 = cca8_openai._openai_quiet_http_loggers_v1
_openai_sanitize_adviser_request_options_v1 = cca8_openai._openai_sanitize_adviser_request_options_v1
_openai_api_error_detail_v1 = cca8_openai._openai_api_error_detail_v1
_openai_response_text_best_effort = cca8_openai._openai_response_text_best_effort
_set_openai_advanced_env = cca8_openai._set_openai_advanced_env

configure_openai_temperature_interactive = cca8_openai.configure_openai_temperature_interactive
configure_openai_top_p_interactive = cca8_openai.configure_openai_top_p_interactive
configure_openai_max_output_tokens_interactive = cca8_openai.configure_openai_max_output_tokens_interactive
configure_openai_reasoning_effort_interactive = cca8_openai.configure_openai_reasoning_effort_interactive
clear_openai_advanced_settings_interactive = cca8_openai.clear_openai_advanced_settings_interactive
print_openai_install_help = cca8_openai.print_openai_install_help
configure_openai_api_key_interactive = cca8_openai.configure_openai_api_key_interactive
configure_openai_model_interactive = cca8_openai.configure_openai_model_interactive
run_openai_smoke_test_interactive = cca8_openai.run_openai_smoke_test_interactive
_cca8_llm_state_reply_schema_v1 = cca8_openai._cca8_llm_state_reply_schema_v1
_cca8_llm_state_reply_prompt_v1 = cca8_openai._cca8_llm_state_reply_prompt_v1
_short_json_sig16_v1 = cca8_openai._short_json_sig16_v1
_llm_eval_response_usage_v1 = cca8_openai._llm_eval_response_usage_v1
_append_jsonl_record_v1 = cca8_openai._append_jsonl_record_v1
_run_openai_structured_state_eval_once_v1 = cca8_openai._run_openai_structured_state_eval_once_v1
_llm_eval_result_one_line_v1 = cca8_openai._llm_eval_result_one_line_v1
_print_llm_eval_summary_v1 = cca8_openai._print_llm_eval_summary_v1


def _openai_runtime_v1() -> cca8_openai.OpenAIRuntime:
    """Build the current runner-to-OpenAI state-summary callback bridge."""
    return OpenAIRuntime(
        timekeeping_line=timekeeping_line,
        anchor_id=_anchor_id,
        sorted_bids=_sorted_bids,
    )


def build_cca8_llm_state_summary_v1(world: Any, drives: Any, ctx: Any) -> dict[str, Any]:
    """Build the extracted OpenAI state summary through current runner helpers."""
    return cca8_openai.build_cca8_llm_state_summary_v1(
        world,
        drives,
        ctx,
        runtime=_openai_runtime_v1(),
    )


def _openai_advanced_menu_operations_v1() -> cca8_openai.OpenAIAdvancedMenuOperations:
    """Build advanced Menu 48 operations from runner-visible callables."""
    return OpenAIAdvancedMenuOperations(
        configure_temperature=configure_openai_temperature_interactive,
        configure_top_p=configure_openai_top_p_interactive,
        configure_max_output_tokens=configure_openai_max_output_tokens_interactive,
        configure_reasoning_effort=configure_openai_reasoning_effort_interactive,
        clear_settings=clear_openai_advanced_settings_interactive,
    )


def openai_advanced_settings_menu_interactive() -> None:
    """Open the extracted advanced-settings submenu through runner-visible callables."""
    cca8_openai.openai_advanced_settings_menu_interactive(
        _openai_advanced_menu_operations_v1(),
    )


def run_cca8_llm_eval_harness_interactive(world: Any, drives: Any, ctx: Any) -> None:
    """Run the extracted LLM evaluation harness through current runner helpers."""
    cca8_openai.run_cca8_llm_eval_harness_interactive(
        world,
        drives,
        ctx,
        runtime=_openai_runtime_v1(),
    )


def run_cca8_llm_state_summary_demo_interactive(world: Any, drives: Any, ctx: Any) -> None:
    """Run the extracted CCA8-to-LLM demo through current runner helpers."""
    cca8_openai.run_cca8_llm_state_summary_demo_interactive(
        world,
        drives,
        ctx,
        runtime=_openai_runtime_v1(),
    )


def _openai_menu_operations_v1() -> cca8_openai.OpenAIMenuOperations:
    """Build Menu 48 operations from the runner-visible compatibility surface."""
    return OpenAIMenuOperations(
        sdk_version_text=_openai_sdk_version_text,
        default_model_name=_openai_default_model_name,
        advanced_settings_one_line=_openai_advanced_settings_one_line,
        configure_api_key=configure_openai_api_key_interactive,
        configure_model=configure_openai_model_interactive,
        run_smoke_test=run_openai_smoke_test_interactive,
        print_install_help=print_openai_install_help,
        run_state_summary_demo=run_cca8_llm_state_summary_demo_interactive,
        open_advanced_settings=openai_advanced_settings_menu_interactive,
        run_eval_harness=run_cca8_llm_eval_harness_interactive,
    )


def openai_menu_48_interactive(world: Any, drives: Any, ctx: Any) -> None:
    """Open the extracted Menu 48 flow through runner-visible operations."""
    cca8_openai.openai_menu_48_interactive(
        world,
        drives,
        ctx,
        _openai_menu_operations_v1(),
    )


# --- Working memory compatibility seam -------------------------------------------
# Phase-1 WorkingMap construction and MapSurface storage/retrieval implementations
# live in cca8_working_memory. Historical runner names remain available so tests,
# experiments, and downstream tools continue to work unchanged.
init_working_world = cca8_working_memory.init_working_world
reset_working_world = cca8_working_memory.reset_working_world
register_policy_scratch_chain_v1 = cca8_working_memory.register_policy_scratch_chain_v1
serialize_mapsurface_v1 = cca8_working_memory.serialize_mapsurface_v1
mapsurface_payload_sig_v1 = cca8_working_memory.mapsurface_payload_sig_v1
_SALIENT_PRED_PREFIXES = cca8_working_memory._SALIENT_PRED_PREFIXES
_SALIENT_PRED_EXACT = cca8_working_memory._SALIENT_PRED_EXACT
mapsurface_salience_v1 = cca8_working_memory.mapsurface_salience_v1
current_mapsurface_salience_v1 = cca8_working_memory.current_mapsurface_salience_v1
store_mapsurface_snapshot_v1 = cca8_working_memory.store_mapsurface_snapshot_v1
_wm_entity_anchor_name = cca8_working_memory._wm_entity_anchor_name
_wm_tagset_of = cca8_working_memory._wm_tagset_of
_wm_upsert_edge = cca8_working_memory._wm_upsert_edge
_rec_stage_zone = cca8_working_memory._rec_stage_zone
_wm_snapshot_pointer_bids = cca8_working_memory._wm_snapshot_pointer_bids
_wm_pointer_engram_id = cca8_working_memory._wm_pointer_engram_id
_iter_newest_wm_mapsurface_recs = cca8_working_memory._iter_newest_wm_mapsurface_recs
pick_best_wm_mapsurface_rec = cca8_working_memory.pick_best_wm_mapsurface_rec
load_mapsurface_payload_v1_into_workingmap = cca8_working_memory.load_mapsurface_payload_v1_into_workingmap
merge_mapsurface_payload_v1_into_workingmap = cca8_working_memory.merge_mapsurface_payload_v1_into_workingmap
_wm_count_cue_tags_v1 = cca8_working_memory._wm_count_cue_tags_v1
_wm_mapswitch_candidate_view_v1 = cca8_working_memory._wm_mapswitch_candidate_view_v1
_wm_mapswitch_ranked_view_v1 = cca8_working_memory._wm_mapswitch_ranked_view_v1
_wm_log_mapswitch_event_v1 = cca8_working_memory._wm_log_mapswitch_event_v1
format_mapswitch_event_line_v1 = cca8_working_memory.format_mapswitch_event_line_v1
load_wm_mapsurface_engram_into_workingmap_mode = cca8_working_memory.load_wm_mapsurface_engram_into_workingmap_mode
load_wm_mapsurface_engram_into_workingmap = cca8_working_memory.load_wm_mapsurface_engram_into_workingmap

# Phase-2 pure helpers are direct aliases. Runtime-sensitive helpers below are
# thin wrappers so existing runner monkeypatch seams continue to resolve at call time.
_navpatch_core_v1 = cca8_working_memory._navpatch_core_v1
navpatch_payload_sig_v1 = cca8_working_memory.navpatch_payload_sig_v1
_wm_surfacegrid_priority_v1 = cca8_working_memory._wm_surfacegrid_priority_v1
_wm_focus_token_from_obs_token_v1 = cca8_working_memory._wm_focus_token_from_obs_token_v1
wm_salience_force_focus_token_v1 = cca8_working_memory.wm_salience_force_focus_token_v1
_wm_salience_candidate_tokens_v1 = cca8_working_memory._wm_salience_candidate_tokens_v1
_wm_blank_grid_cells_v1 = cca8_working_memory._wm_blank_grid_cells_v1
_wm_set_grid_cell_v1 = cca8_working_memory._wm_set_grid_cell_v1
_wm_paint_diamond_v1 = cca8_working_memory._wm_paint_diamond_v1
_wm_env_position_v1 = cca8_working_memory._wm_env_position_v1
_wm_relative_direction_cell_v1 = cca8_working_memory._wm_relative_direction_cell_v1
_wm_default_navpatches_from_obs_v1 = cca8_working_memory._wm_default_navpatches_from_obs_v1
_wm_patch_center_xy_v1 = cca8_working_memory._wm_patch_center_xy_v1
_wm_patch_index_v1 = cca8_working_memory._wm_patch_index_v1
_wm_surfacegrid_mark_char_v1 = cca8_working_memory._wm_surfacegrid_mark_char_v1
_wm_place_overlay_char_v1 = cca8_working_memory._wm_place_overlay_char_v1
_navpatch_tag_jaccard = cca8_working_memory._navpatch_tag_jaccard
_navpatch_extent_sim = cca8_working_memory._navpatch_extent_sim
navpatch_similarity_v1 = cca8_working_memory.navpatch_similarity_v1
navpatch_candidate_prior_bias_v1 = cca8_working_memory.navpatch_candidate_prior_bias_v1
wm_apply_grid_slot_families_to_mapsurface_v1 = cca8_working_memory.wm_apply_grid_slot_families_to_mapsurface_v1
_wm_dir8_v1 = cca8_working_memory._wm_dir8_v1
_wm_surfacegrid_local_points_v1 = cca8_working_memory._wm_surfacegrid_local_points_v1
_wm_surfacegrid_corridor_count_v1 = cca8_working_memory._wm_surfacegrid_corridor_count_v1
_wm_surfacegrid_shortest_safe_path_cost_v1 = cca8_working_memory._wm_surfacegrid_shortest_safe_path_cost_v1
compute_navsummary_v1 = cca8_working_memory.compute_navsummary_v1
format_navsummary_line_v1 = cca8_working_memory.format_navsummary_line_v1
_wm_entity_pos_xy_v1 = cca8_working_memory._wm_entity_pos_xy_v1
_wm_entity_kind_v1 = cca8_working_memory._wm_entity_kind_v1
_wm_entity_dist_class_v1 = cca8_working_memory._wm_entity_dist_class_v1
_wm_pos_to_grid_cell_v1 = cca8_working_memory._wm_pos_to_grid_cell_v1
_wm_surfacegrid_window_anchor_v2 = cca8_working_memory._wm_surfacegrid_window_anchor_v2
_wm_surfacegrid_scene_fingerprint_v2 = cca8_working_memory._wm_surfacegrid_scene_fingerprint_v2
_wm_surfacegrid_dirty_reasons_v2 = cca8_working_memory._wm_surfacegrid_dirty_reasons_v2
_surfacegrid_ascii_lines_v1 = cca8_working_memory._surfacegrid_ascii_lines_v1
_wm_entity_mark_char_v1 = cca8_working_memory._wm_entity_mark_char_v1
_wm_display_focus_entities_v1 = cca8_working_memory._wm_display_focus_entities_v1
render_surfacegrid_ascii_with_salience_v1 = cca8_working_memory.render_surfacegrid_ascii_with_salience_v1
format_surfacegrid_ascii_map_v1 = cca8_working_memory.format_surfacegrid_ascii_map_v1
_surfacegrid_ascii_text_v1 = cca8_working_memory._surfacegrid_ascii_text_v1
_surfacegrid_terminal_block_key_v1 = cca8_working_memory._surfacegrid_terminal_block_key_v1
format_surfacegrid_snapshot_v1 = cca8_working_memory.format_surfacegrid_snapshot_v1
wm_salience_force_focus_entity_v1 = cca8_working_memory.wm_salience_force_focus_entity_v1
_wm_salience_ambiguous_entities_v1 = cca8_working_memory._wm_salience_ambiguous_entities_v1


def store_navpatch_engram_v1(ctx: Ctx, patch: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Store one NavPatch through the current runner-visible Column instance."""
    return cca8_working_memory.store_navpatch_engram_v1(
        ctx,
        patch,
        reason=reason,
        column_memory=column_mem,
    )


def navpatch_priors_bundle_v1(ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Build NavPatch priors through the current runner BodyMap lookup."""
    return cca8_working_memory.navpatch_priors_bundle_v1(
        ctx,
        env_obs,
        body_space_zone_fn=body_space_zone,
    )


def navpatch_predictive_match_loop_v1(ctx: Ctx, env_obs: EnvObservation) -> list[dict[str, Any]]:
    """Run extracted NavPatch matching through current runner dependency seams."""
    return cca8_working_memory.navpatch_predictive_match_loop_v1(
        ctx,
        env_obs,
        column_memory=column_mem,
        store_navpatch_fn=store_navpatch_engram_v1,
        body_space_zone_fn=body_space_zone,
    )


# _surfacegrid_ascii_terminal_block_v1 moved to cca8_reporting.py.


def _wm_guess_inspected_entity_v1(ctx: Ctx) -> str | None:
    """Resolve a probe target through current runner BodyMap helpers."""
    return cca8_working_memory._wm_guess_inspected_entity_v1(
        ctx,
        body_cliff_distance_fn=body_cliff_distance,
        body_mom_distance_fn=body_mom_distance,
    )


def wm_salience_tick_v1(
    ctx: Ctx,
    ww,
    *,
    changed_entities: set[str],
    new_cue_entities: set[str],
    ambiguous_entities: set[str],
) -> dict[str, Any]:
    """Update extracted salience through current runner BodyMap helpers."""
    return cca8_working_memory.wm_salience_tick_v1(
        ctx,
        ww,
        changed_entities=changed_entities,
        new_cue_entities=new_cue_entities,
        ambiguous_entities=ambiguous_entities,
        body_cliff_distance_fn=body_cliff_distance,
        body_mom_distance_fn=body_mom_distance,
        body_shelter_distance_fn=body_shelter_distance,
    )


# --- Working memory Phase-3 compatibility seam ------------------------------------
# Live observation injection, stateful MapSurface updates, contextual retrieval,
# benchmark map switching, and retrieved-state hints now live in
# cca8_working_memory. Runtime-sensitive wrappers resolve runner-visible hooks at
# call time so existing tests and downstream tools retain their monkeypatch seams.
init_map_surface_world = cca8_working_memory.init_map_surface_world
_slot_key_from_token = cca8_working_memory._slot_key_from_token
update_surface_grid_from_obs = cca8_working_memory.update_surface_grid_from_obs
update_map_surface_from_obs = cca8_working_memory.update_map_surface_from_obs
predcode_update_from_obs = cca8_working_memory.predcode_update_from_obs
_wm_display_id = cca8_working_memory._wm_display_id
_prune_working_world = cca8_working_memory._prune_working_world
_goat04_context_milestone_label_v1 = cca8_working_memory._goat04_context_milestone_label_v1
_newborn_b2_seed_label_v1 = cca8_working_memory._newborn_b2_seed_label_v1
_newborn_controller_step_int_v1 = cca8_working_memory._newborn_controller_step_int_v1
_append_newborn_retrieved_hint_event_v1 = cca8_working_memory._append_newborn_retrieved_hint_event_v1
_note_newborn_retrieved_hint_returned_v1 = cca8_working_memory._note_newborn_retrieved_hint_returned_v1
_newborn_retrieved_hint_debug_from_ctx_v1 = cca8_working_memory._newborn_retrieved_hint_debug_from_ctx_v1
_clear_newborn_retrieved_hint_v1 = cca8_working_memory._clear_newborn_retrieved_hint_v1
_newborn_active_retrieved_hint_v1 = cca8_working_memory._newborn_active_retrieved_hint_v1
_decode_newborn_hint_from_mapsurface_record_v1 = cca8_working_memory._decode_newborn_hint_from_mapsurface_record_v1


def _set_newborn_retrieved_hint_from_engram_v1(
    ctx: Ctx | None,
    engram_id: str,
    *,
    ttl_steps: int = 3,
) -> dict[str, Any]:
    """Decode a newborn retrieved-state hint through the current Column object."""
    return cca8_working_memory._set_newborn_retrieved_hint_from_engram_v1(
        ctx,
        engram_id,
        ttl_steps=ttl_steps,
        column_memory=column_mem,
    )


def should_autoretrieve_mapsurface(
    ctx: Ctx,
    env_obs: EnvObservation | None,
    *,
    stage: str | None,
    zone: str | None,
    stage_changed: bool,
    zone_changed: bool,
    forced_keyframe: bool = False,
    boundary_reason: str | None = None,
) -> dict[str, Any]:
    """Evaluate the extracted retrieval guard through the current BodyMap helper."""
    return cca8_working_memory.should_autoretrieve_mapsurface(
        ctx,
        env_obs,
        stage=stage,
        zone=zone,
        stage_changed=stage_changed,
        zone_changed=zone_changed,
        forced_keyframe=forced_keyframe,
        boundary_reason=boundary_reason,
        bodymap_is_stale_fn=bodymap_is_stale,
    )


def maybe_autoretrieve_mapsurface_on_keyframe(
    world: Any,
    ctx: Ctx,
    *,
    stage: str | None,
    zone: str | None,
    exclude_engram_id: str | None = None,
    reason: str = "auto_keyframe",
    mode: str | None = None,
    top_k: int | None = None,
    max_scan: int = 500,
    log: bool | None = None,
) -> dict[str, Any]:
    """Run extracted MapSurface retrieval through runner-visible storage hooks."""
    return cca8_working_memory.maybe_autoretrieve_mapsurface_on_keyframe(
        world,
        ctx,
        stage=stage,
        zone=zone,
        exclude_engram_id=exclude_engram_id,
        reason=reason,
        mode=mode,
        top_k=top_k,
        max_scan=max_scan,
        log=log,
        pick_best_fn=pick_best_wm_mapsurface_rec,
        load_engram_fn=load_wm_mapsurface_engram_into_workingmap_mode,
        log_event_fn=_wm_log_mapswitch_event_v1,
        format_event_fn=format_mapswitch_event_line_v1,
    )


def maybe_goat04_context_mapswitch_on_keyframe_v1(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
) -> dict[str, Any]:
    """Run extracted goat04 map switching through current runner hooks."""
    return cca8_working_memory.maybe_goat04_context_mapswitch_on_keyframe_v1(
        world,
        ctx,
        env_obs,
        body_space_zone_fn=body_space_zone,
        store_snapshot_fn=store_mapsurface_snapshot_v1,
        autoretrieve_fn=maybe_autoretrieve_mapsurface_on_keyframe,
    )


def maybe_newborn_b2_mapswitch_on_keyframe_v1(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
) -> dict[str, Any]:
    """Run extracted newborn-B2 map switching through current runner hooks."""
    return cca8_working_memory.maybe_newborn_b2_mapswitch_on_keyframe_v1(
        world,
        ctx,
        env_obs,
        body_space_zone_fn=body_space_zone,
        store_snapshot_fn=store_mapsurface_snapshot_v1,
        autoretrieve_fn=maybe_autoretrieve_mapsurface_on_keyframe,
        set_retrieved_hint_fn=_set_newborn_retrieved_hint_from_engram_v1,
        clear_retrieved_hint_fn=_clear_newborn_retrieved_hint_v1,
    )


def inject_obs_into_working_world(ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Mirror one observation through the extracted WorkingMap implementation."""
    return cca8_working_memory.inject_obs_into_working_world(
        ctx,
        env_obs,
        init_working_world_fn=init_working_world,
        display_id_fn=_wm_display_id,
        store_navpatch_fn=store_navpatch_engram_v1,
        salience_tick_fn=wm_salience_tick_v1,
        body_cliff_distance_fn=body_cliff_distance,
        prune_working_world_fn=_prune_working_world,
    )


# --- Runtime Context (ENGINE↔CLI seam) ---------------------------------------------



# Compatibility aliases and wrappers preserve the historical ``cca8_run``
# experiment surface while the complete experiment subsystem lives in
# ``cca8_experiments``. Runtime callbacks are resolved at call time below.
ExperimentConditionDef = cca8_experiments.ExperimentConditionDef
ExperimentBenchmarkDef = cca8_experiments.ExperimentBenchmarkDef

_experiment_policy_debug_record_v1 = cca8_experiments._experiment_policy_debug_record_v1
experiment_action_vocab_v1 = cca8_experiments.experiment_action_vocab_v1
experiment_condition_catalog_v1 = cca8_experiments.experiment_condition_catalog_v1
experiment_benchmark_catalog_v1 = cca8_experiments.experiment_benchmark_catalog_v1

NEWBORN_STRESS_PROFILES_V1 = cca8_experiments.NEWBORN_STRESS_PROFILES_V1
NEWBORN_STRESS_DROP_PRED_PREFIXES_V1 = cca8_experiments.NEWBORN_STRESS_DROP_PRED_PREFIXES_V1
NEWBORN_STRESS_DROP_CUE_PREFIXES_V1 = cca8_experiments.NEWBORN_STRESS_DROP_CUE_PREFIXES_V1
NEWBORN_ROUTE_LOSS_DROP_PRED_PREFIXES_V1 = cca8_experiments.NEWBORN_ROUTE_LOSS_DROP_PRED_PREFIXES_V1
NEWBORN_ROUTE_LOSS_DROP_CUE_PREFIXES_V1 = cca8_experiments.NEWBORN_ROUTE_LOSS_DROP_CUE_PREFIXES_V1
NEWBORN_ROUTE_LOSS_RAW_SENSOR_KEY_INFIXES_V1 = cca8_experiments.NEWBORN_ROUTE_LOSS_RAW_SENSOR_KEY_INFIXES_V1
NEWBORN_ROUTE_LOSS_META_PROTECTED_KEYS_V1 = cca8_experiments.NEWBORN_ROUTE_LOSS_META_PROTECTED_KEYS_V1

_newborn_route_loss_drop_predicates_v1 = cca8_experiments._newborn_route_loss_drop_predicates_v1
_newborn_route_loss_drop_cues_v1 = cca8_experiments._newborn_route_loss_drop_cues_v1
_newborn_route_loss_drop_raw_sensors_v1 = cca8_experiments._newborn_route_loss_drop_raw_sensors_v1
_newborn_route_loss_mask_env_meta_v1 = cca8_experiments._newborn_route_loss_mask_env_meta_v1
_newborn_route_loss_drop_nav_fields_v1 = cca8_experiments._newborn_route_loss_drop_nav_fields_v1
_newborn_effective_blackout_length_v1 = cca8_experiments._newborn_effective_blackout_length_v1
_newborn_stress_profile_from_ctx_v1 = cca8_experiments._newborn_stress_profile_from_ctx_v1
_newborn_blackout_length_from_ctx_v1 = cca8_experiments._newborn_blackout_length_from_ctx_v1
_newborn_stress_env_meta_v1 = cca8_experiments._newborn_stress_env_meta_v1
_newborn_stress_milestones_from_obs_v1 = cca8_experiments._newborn_stress_milestones_from_obs_v1
_newborn_stress_drop_predicates_v1 = cca8_experiments._newborn_stress_drop_predicates_v1
_newborn_stress_drop_cues_v1 = cca8_experiments._newborn_stress_drop_cues_v1
_newborn_stress_schedule_blackout_v1 = cca8_experiments._newborn_stress_schedule_blackout_v1
apply_newborn_experiment_stress_v1 = cca8_experiments.apply_newborn_experiment_stress_v1

reset_experiment_protocol_v1 = cca8_experiments.reset_experiment_protocol_v1
render_experiment_conditions_table_v1 = cca8_experiments.render_experiment_conditions_table_v1
render_experiment_benchmarks_table_v1 = cca8_experiments.render_experiment_benchmarks_table_v1
render_experiment_jsonl_schema_summary_v1 = cca8_experiments.render_experiment_jsonl_schema_summary_v1
render_experiment_protocol_summary_v1 = cca8_experiments.render_experiment_protocol_summary_v1
_experiment_safe_token_v1 = cca8_experiments._experiment_safe_token_v1
experiment_parse_condition_ids_v1 = cca8_experiments.experiment_parse_condition_ids_v1
experiment_parse_seed_list_v1 = cca8_experiments.experiment_parse_seed_list_v1
experiment_normalize_protocol_v1 = cca8_experiments.experiment_normalize_protocol_v1
experiment_make_run_id_v1 = cca8_experiments.experiment_make_run_id_v1
append_experiment_jsonl_record_v1 = cca8_experiments.append_experiment_jsonl_record_v1
_experiment_write_json_file_v1 = cca8_experiments._experiment_write_json_file_v1
_experiment_protocol_snapshot_v1 = cca8_experiments._experiment_protocol_snapshot_v1
_experiment_collect_repeated_bundle_rows_v1 = cca8_experiments._experiment_collect_repeated_bundle_rows_v1
experiment_write_episode_record_v1 = cca8_experiments.experiment_write_episode_record_v1


def experiment_jsonl_paths_v1(ctx: Ctx, *, run_id: str | None = None) -> dict[str, Any]:
    """Return experiment JSONL paths while preserving runner monkeypatch seams."""
    return cca8_experiments.experiment_jsonl_paths_v1(
        ctx,
        run_id=run_id,
        run_id_factory=experiment_make_run_id_v1,
    )


def _experiment_write_repeated_result_bundle_v1(
    ctx: Ctx,
    repeated_result: dict[str, Any],
    *,
    bundle_label: str,
) -> dict[str, Any]:
    """Write a repeated-result bundle through the extracted experiment module."""
    return cca8_experiments._experiment_write_repeated_result_bundle_v1(
        ctx,
        repeated_result,
        bundle_label=bundle_label,
        run_id_factory=experiment_make_run_id_v1,
    )


def experiment_prepare_logging_v1(ctx: Ctx, *, reset_buffers: bool = True) -> dict[str, Any]:
    """Prepare experiment logging while using the runner-visible run-id helper."""
    return cca8_experiments.experiment_prepare_logging_v1(
        ctx,
        reset_buffers=reset_buffers,
        run_id_factory=experiment_make_run_id_v1,
    )


def experiment_build_cycle_record_stub_v1(
    ctx: Ctx,
    *,
    experiment_id: str | None = None,
    condition_id: str = "A",
    seed: int = 11,
    episode_index: int = 0,
    cycle_index: int = 0,
) -> dict[str, Any]:
    """Build a cycle record while preserving runner-visible dependency hooks."""
    return cca8_experiments.experiment_build_cycle_record_stub_v1(
        ctx,
        experiment_id=experiment_id,
        condition_id=condition_id,
        seed=seed,
        episode_index=episode_index,
        cycle_index=cycle_index,
        run_id_factory=experiment_make_run_id_v1,
        body_space_zone_fn=body_space_zone,
    )


def experiment_build_episode_record_stub_v1(
    ctx: Ctx,
    *,
    experiment_id: str | None = None,
    condition_id: str = "A",
    seed: int = 11,
    episode_index: int = 0,
) -> dict[str, Any]:
    """Build an episode record while preserving the runner run-id hook."""
    return cca8_experiments.experiment_build_episode_record_stub_v1(
        ctx,
        experiment_id=experiment_id,
        condition_id=condition_id,
        seed=seed,
        episode_index=episode_index,
        run_id_factory=experiment_make_run_id_v1,
    )


# --- Experiment execution compatibility bridge -----------------------------------

ExperimentRuntime = cca8_experiments.ExperimentRuntime
ExperimentMenuOperations = cca8_experiments.ExperimentMenuOperations


def _experiment_runtime_v1() -> ExperimentRuntime:
    """Build the current runner-to-experiment callback bridge.

    Callbacks are resolved each time rather than cached. This preserves the
    historical monkeypatch seams used by tests and keeps ``cca8_experiments``
    independent of the interactive runner.
    """
    return ExperimentRuntime(
        world_factory=cca8_world_graph.WorldGraph,
        policy_runtime_factory=lambda: PolicyRuntime(CATALOG_GATES),
        init_body_world=init_body_world,
        init_working_world=init_working_world,
        reset_working_world=reset_working_world,
        apply_hardwired_profile=apply_hardwired_profile_phase7,
        configure_goat_foraging=configure_goat_foraging_04_eval_v1,
        run_closed_loop=run_env_closed_loop_steps,
        build_llm_state_summary=build_cca8_llm_state_summary_v1,
        newborn_retrieved_hint_debug=_newborn_retrieved_hint_debug_from_ctx_v1,
        run_id_factory=experiment_make_run_id_v1,
        openai_default_model_name=_openai_default_model_name,
        openai_response_request_options=_openai_response_request_options_v1,
        openai_sanitize_adviser_request_options=_openai_sanitize_adviser_request_options_v1,
        openai_quiet_http_loggers=_openai_quiet_http_loggers_v1,
        openai_response_text=_openai_response_text_best_effort,
        openai_api_error_detail=_openai_api_error_detail_v1,
        llm_response_usage=_llm_eval_response_usage_v1,
    )


def _experiment_menu_operations_v1() -> ExperimentMenuOperations:
    """Build Menu 49 operations from the runner-visible compatibility surface."""
    return ExperimentMenuOperations(
        make_run_id=experiment_make_run_id_v1,
        prepare_logging=experiment_prepare_logging_v1,
        build_cycle_record=experiment_build_cycle_record_stub_v1,
        build_episode_record=experiment_build_episode_record_stub_v1,
        run_one_episode=experiment_run_one_episode_v1,
        run_condition_batch=experiment_run_condition_batch_v1,
        run_repeated_abc=experiment_run_repeated_random_abc_v1,
        run_repeated_ae=experiment_run_repeated_random_ae_v1,
        write_repeated_bundle=_experiment_write_repeated_result_bundle_v1,
    )


def experiment_make_sandbox_runtime_v1() -> dict[str, Any]:
    """Build one isolated experiment runtime through the extracted subsystem."""
    return cca8_experiments.experiment_make_sandbox_runtime_v1(_experiment_runtime_v1())


def experiment_configure_benchmark_runtime_v1(
    world: Any,
    drives: Drives,
    ctx: Ctx,
    env: HybridEnvironment,
    benchmark_id: str,
) -> dict[str, Any]:
    """Configure a sandbox benchmark while preserving the runner API."""
    return cca8_experiments.experiment_configure_benchmark_runtime_v1(
        world,
        drives,
        ctx,
        env,
        benchmark_id,
        runtime=_experiment_runtime_v1(),
    )


experiment_apply_condition_runtime_v1 = cca8_experiments.experiment_apply_condition_runtime_v1
_experiment_llm_candidate_rows_v1 = cca8_experiments._experiment_llm_candidate_rows_v1
_experiment_llm_adviser_reply_schema_v1 = cca8_experiments._experiment_llm_adviser_reply_schema_v1
_experiment_llm_adviser_prompt_v1 = cca8_experiments._experiment_llm_adviser_prompt_v1
_experiment_extract_generic_milestones_v1 = cca8_experiments._experiment_extract_generic_milestones_v1
_experiment_summarize_newborn_b2_v1 = cca8_experiments._experiment_summarize_newborn_b2_v1
_newborn_retrieval_debug_from_raw_records_v1 = cca8_experiments._newborn_retrieval_debug_from_raw_records_v1
_newborn_stress_debug_from_raw_records_v1 = cca8_experiments._newborn_stress_debug_from_raw_records_v1
_goat04_oracle_from_raw_record_v1 = cca8_experiments._goat04_oracle_from_raw_record_v1
_goat04_seed_context_by_engram_v1 = cca8_experiments._goat04_seed_context_by_engram_v1
_goat04_retrieved_context_from_event_v1 = cca8_experiments._goat04_retrieved_context_from_event_v1
_goat04_context_hint_active_v1 = cca8_experiments._goat04_context_hint_active_v1
_goat04_update_control_hint_v1 = cca8_experiments._goat04_update_control_hint_v1
_experiment_transform_generic_cycle_records_v1 = cca8_experiments._experiment_transform_generic_cycle_records_v1


def _run_experiment_llm_adviser_once_v1(
    world: Any,
    drives: Drives,
    ctx: Ctx,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run the extracted bounded adviser using current runner callbacks."""
    return cca8_experiments._run_experiment_llm_adviser_once_v1(
        world,
        drives,
        ctx,
        candidate_rows,
        runtime=_experiment_runtime_v1(),
    )


def _experiment_summarize_generic_episode_v1(
    ctx: Ctx,
    *,
    experiment_id: str,
    condition_id: str,
    seed: int,
    episode_index: int,
    raw_records: list[dict[str, Any]],
    latency_ms_total: float,
) -> dict[str, Any]:
    """Summarize one episode through the extracted experiment subsystem."""
    return cca8_experiments._experiment_summarize_generic_episode_v1(
        ctx,
        runtime=_experiment_runtime_v1(),
        experiment_id=experiment_id,
        condition_id=condition_id,
        seed=seed,
        episode_index=episode_index,
        raw_records=raw_records,
        latency_ms_total=latency_ms_total,
    )


def experiment_run_one_episode_v1(
    protocol_ctx: Ctx,
    *,
    condition_id: str | None = None,
    seed: int | None = None,
    episode_index: int = 0,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run one isolated experiment episode through the extracted subsystem."""
    return cca8_experiments.experiment_run_one_episode_v1(
        protocol_ctx,
        runtime=_experiment_runtime_v1(),
        condition_id=condition_id,
        seed=seed,
        episode_index=episode_index,
        suppress_output=suppress_output,
    )


AUTONOMOUS_NEWBORN_SURVIVAL_MILESTONES_V1 = cca8_experiments.AUTONOMOUS_NEWBORN_SURVIVAL_MILESTONES_V1
_autonomous_newborn_demo_final_state_v1 = cca8_experiments._autonomous_newborn_demo_final_state_v1
_autonomous_newborn_demo_policy_counts_v1 = cca8_experiments._autonomous_newborn_demo_policy_counts_v1
_autonomous_newborn_demo_policy_counts_from_stdout_v1 = cca8_experiments._autonomous_newborn_demo_policy_counts_from_stdout_v1
_autonomous_newborn_demo_counts_text_v1 = cca8_experiments._autonomous_newborn_demo_counts_text_v1


def run_autonomous_newborn_survival_demo_v1(
    max_cycles: int = 60,
    *,
    show_timeline: bool = True,
) -> dict[str, Any]:
    """Run the isolated newborn demo through the extracted subsystem."""
    return cca8_experiments.run_autonomous_newborn_survival_demo_v1(
        max_cycles=max_cycles,
        show_timeline=show_timeline,
        runtime=_experiment_runtime_v1(),
    )


render_autonomous_newborn_survival_demo_lines_v1 = cca8_experiments.render_autonomous_newborn_survival_demo_lines_v1
render_experiment_logging_status_v1 = cca8_experiments.render_experiment_logging_status_v1
_experiment_metric_text_v1 = cca8_experiments._experiment_metric_text_v1
render_experiment_episode_summary_lines_v1 = cca8_experiments.render_experiment_episode_summary_lines_v1
_experiment_mean_v1 = cca8_experiments._experiment_mean_v1
_EXPERIMENT_TCRIT_CACHE_V1 = cca8_experiments._EXPERIMENT_TCRIT_CACHE_V1
_experiment_numeric_values_v1 = cca8_experiments._experiment_numeric_values_v1
_experiment_sample_sd_v1 = cca8_experiments._experiment_sample_sd_v1
_student_t_pdf_v1 = cca8_experiments._student_t_pdf_v1
_student_t_cdf_v1 = cca8_experiments._student_t_cdf_v1
_student_t_critical_two_sided_v1 = cca8_experiments._student_t_critical_two_sided_v1
_experiment_descriptive_stats_v1 = cca8_experiments._experiment_descriptive_stats_v1
_experiment_paired_diff_stats_v1 = cca8_experiments._experiment_paired_diff_stats_v1
_experiment_ci_text_v1 = cca8_experiments._experiment_ci_text_v1
_experiment_p_text_v1 = cca8_experiments._experiment_p_text_v1
_experiment_repeat_metric_label_v1 = cca8_experiments._experiment_repeat_metric_label_v1
render_experiment_repeat_stats_lines_v1 = cca8_experiments.render_experiment_repeat_stats_lines_v1


def experiment_run_condition_batch_v1(
    protocol_ctx: Ctx,
    *,
    condition_ids: list[str] | None = None,
    seed_list: list[int] | None = None,
    episodes_per_seed: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run a condition batch while preserving the runner episode hook."""
    return cca8_experiments.experiment_run_condition_batch_v1(
        protocol_ctx,
        runtime=_experiment_runtime_v1(),
        run_one_episode_fn=experiment_run_one_episode_v1,
        condition_ids=condition_ids,
        seed_list=seed_list,
        episodes_per_seed=episodes_per_seed,
        suppress_output=suppress_output,
    )


render_experiment_batch_summary_lines_v1 = cca8_experiments.render_experiment_batch_summary_lines_v1
_experiment_repeat_metric_keys_v1 = cca8_experiments._experiment_repeat_metric_keys_v1
_experiment_random_seed_list_v1 = cca8_experiments._experiment_random_seed_list_v1
_render_experiment_repeat_condition_line_v1 = cca8_experiments._render_experiment_repeat_condition_line_v1


def experiment_run_repeated_selected_vs_a_v1(
    protocol_ctx: Ctx,
    *,
    condition_ids: list[str] | None = None,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run selected repeated comparisons while preserving the runner batch hook."""
    return cca8_experiments.experiment_run_repeated_selected_vs_a_v1(
        protocol_ctx,
        runtime=_experiment_runtime_v1(),
        run_condition_batch_fn=experiment_run_condition_batch_v1,
        condition_ids=condition_ids,
        repeats=repeats,
        seeds_per_repeat=seeds_per_repeat,
        suppress_output=suppress_output,
    )


def experiment_run_repeated_random_abc_v1(
    protocol_ctx: Ctx,
    *,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run repeated A/B/C comparisons through the extracted subsystem."""
    return cca8_experiments.experiment_run_repeated_random_abc_v1(
        protocol_ctx,
        runtime=_experiment_runtime_v1(),
        run_condition_batch_fn=experiment_run_condition_batch_v1,
        repeats=repeats,
        seeds_per_repeat=seeds_per_repeat,
        suppress_output=suppress_output,
    )


def experiment_run_repeated_random_ae_v1(
    protocol_ctx: Ctx,
    *,
    repeats: int = 20,
    seeds_per_repeat: int | None = None,
    suppress_output: bool = True,
) -> dict[str, Any]:
    """Run repeated A/E comparisons through the extracted subsystem."""
    return cca8_experiments.experiment_run_repeated_random_ae_v1(
        protocol_ctx,
        runtime=_experiment_runtime_v1(),
        run_condition_batch_fn=experiment_run_condition_batch_v1,
        repeats=repeats,
        seeds_per_repeat=seeds_per_repeat,
        suppress_output=suppress_output,
    )


def experiments_menu_49_interactive(ctx: Ctx) -> None:
    """Open the extracted Menu 49 flow through runner-visible operations."""
    cca8_experiments.experiments_menu_49_interactive(
        ctx,
        _experiment_menu_operations_v1(),
    )




# Module layout / roadmap
# -----------------------
# ENGINE (import-safe, no direct user I/O) – reusable from tests or other front-ends:
#   • Runtime context:
#       - Ctx: mutable runtime state (explicit cycle/step/tick counters, developmental age, etc.).
#   • Graph / edge helpers:
#       - world_delete_edge(...), delete_edge_flow(...): engine + CLI helpers for removing edges.
#       - Spatial stubs: _maybe_anchor_attach(...), add_spatial_relation(...).
#   • Persistence & versioning:
#       - save_session(...): atomic JSON snapshot of (world, drives, skills).
#       - _module_version_and_path(...), versions_dict(), versions_text(): component versions + paths.
#   • Embodiment stub:
#       - HAL: hardware abstraction layer skeleton for future robot embodiments.
#   • Policy runtime subsystem:
#       - policy gates, newborn control bridges, EFE diagnostics, PolicyGate, PolicyRuntime, CATALOG_GATES,
#         and WorkingMap Creative candidate scoring live in cca8_policy_runtime.py.
#       - runner dependencies are supplied through an explicit hook bundle; historical names remain available here.
#       - boot_prime_stand(...): boot-time seeding of a “stand” intent reachable from NOW.
#   • Tagging / help text:
#       - print_tagging_and_policies_help(...): console explainer for bindings, edges, tags, and policies.
#   • Profiles & tutorials:
#       - profile narratives/scaffolds and choose_profile(...) live in cca8_profiles.py.
#       - explanatory tagging help and run_new_user_tour(...) live in cca8_guidance.py.
#       - runner callbacks are supplied through explicit compatibility bridges.
#   • Experiment subsystem:
#       - protocol, stressors, execution, scoring, statistics, rendering, and Menu 49 live in cca8_experiments.py.
#       - runner-private policy/loop operations and runner-visible OpenAI hooks use explicit callback bridges.
#   • NavMap runtime subsystem:
#       - expected/accepted-current processing, transitions, policy-outcome indexing, and Oscilloscope reporting
#         live in cca8_navmap_runtime.py; pure schemas/operators remain in cca8_navmap.py.
#   • Runtime reporting subsystem:
#       - full/mini snapshots, WorkingMap displays, time/drive/skill HUDs, cycle footers, transcript teeing,
#         and developer-facing LOC utilities live in cca8_reporting.py.
#   • Observation runtime subsystem:
#       - BodyMap construction/update, sequential/error processing, observation masking, keyframe detection,
#         short-lived map handoffs, sparse WorldGraph writes, and cycle JSON logging live in
#         cca8_observation_runtime.py.
#   • Working memory subsystem:
#       - WorkingMap construction/reset, MapSurface serialization/storage/ranking, NavPatch matching, Scratch/zoom/probe,
#         salience, SurfaceGrid, grid predicates, NavSummary, and map-switch records live in cca8_working_memory.py.
#       - live observation injection and contextual auto-retrieval now live in cca8_working_memory.py.
#   • OpenAI / LLM integration:
#       - API configuration, structured evaluation, state summaries, and Menu 48 live in cca8_openai.py.
#       - runner graph/time lookups are supplied through an explicit callback bridge.
#   • Preflight:
#       - run_preflight_full(...): full pytest + probes + hardware checks.
#       - run_preflight_lite_maybe(): optional startup “lite” preflight banner.
#   • WorldGraph helpers for the runner:
#       - _anchor_id(...), _sorted_bids(...): anchor and binding id helpers.
#       - _resolve_engrams_pretty(...), _bindings_pointing_to_eid(...), _engrams_on_binding(...):
#           engram pointer inspection utilities.
#       - reporting/snapshot implementations live in cca8_reporting.py and remain available here
#         through compatibility aliases.
#   • Planning / FOA / contextual helpers:
#       - _neighbors(...), _bfs_reachable(...), *_with_pred/cue(...): small graph utilities.
#       - _first_binding_with_pred(...), choose_contextual_base(...): write-base suggestions.
#       - present_cue_bids(...), neighbors_k(...), compute_foa(...), candidate_anchors(...):
#           focus-of-attention and candidate anchor selection.
#
# CLI (printing/input; menus; argparse) – terminal user experience:
#   • interactive_loop(args): main menu + per-selection code blocks.
#   • main(argv): argument parsing, logging, one-shot flags (about/version/preflight), and then interactive_loop.
#   • if __name__ == "__main__": sys.exit(main()): standard Python script entry point.


# --- Graph edge deletion helpers (engine-level, import-safe) -----------------

# BodyMap construction moved to cca8_observation_runtime.py.


# WorkingMap construction/reset and the MapSurface storage/retrieval pipeline
# live in cca8_working_memory.py; compatibility aliases are defined near
# the module-import seams above.

# Stateful MapSurface and predictive-code update helpers moved to cca8_working_memory.py (Phase 3).


# print_working_map_snapshot moved to cca8_reporting.py.


# print_working_map_layers moved to cca8_reporting.py.


# print_working_map_entity_table moved to cca8_reporting.py.


# MapSurface serialization, salience, and Column storage moved to
# cca8_working_memory.py (Working Memory refactor Phase 1).

# -----------------------------------------------------------------------------
# NavPatch v1 helpers (Phase X; NavPatch plan v5)
# -----------------------------------------------------------------------------

# _navpatch_core_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# navpatch_payload_sig_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# store_navpatch_engram_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# MapSurface reconstruction, ranking, merge/replace loading, and map-switch
# event helpers moved to cca8_working_memory.py.

# Contextual MapSurface retrieval policy and benchmark map switching moved to cca8_working_memory.py (Phase 3).

# _wm_surfacegrid_priority_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_focus_token_from_obs_token_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# wm_salience_force_focus_token_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_salience_candidate_tokens_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_blank_grid_cells_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


#pylint: disable-next=too-many-positional-arguments
# _wm_set_grid_cell_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


#pylint: disable-next=too-many-positional-arguments
# _wm_paint_diamond_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_env_position_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_relative_direction_cell_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_default_navpatches_from_obs_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_patch_center_xy_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_patch_index_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_mark_char_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_place_overlay_char_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


def _edge_get_dst(edge: Dict[str, Any]) -> str | None:
    return edge.get("dst") or edge.get("to") or edge.get("dst_id") or edge.get("id")


def _edge_get_rel(edge: Dict[str, Any]) -> str | None:
    return edge.get("rel") or edge.get("label") or edge.get("relation")


def _rm_from_list(lst: List[Dict[str, Any]], dst: str, rel: str | None) -> int:
    before = len(lst)
    def match(e: Dict[str, Any]) -> bool:
        if _edge_get_dst(e) != dst:
            return False
        return (rel is None) or (_edge_get_rel(e) == rel)
    lst[:] = [e for e in lst if not match(e)]
    return before - len(lst)


def world_delete_edge(world: Any, src: str, dst: str, rel: str | None) -> int:
    """
    Remove edges matching (src -> dst [rel]) from the in-memory WorldGraph.

    Supports per-binding edges like:
        world._bindings[src].edges == [{'label': 'then', 'to': 'b3'}, ...]
    and also optional global world.edges layouts.

    Returns number of removed edges.
    """
    removed = 0

    # Per-binding adjacency: world._bindings[src]
    bindings = getattr(world, "_bindings", None) or getattr(world, "bindings", None) or getattr(world, "nodes", None)
    if isinstance(bindings, dict) and src in bindings:
        node = bindings[src]
        # node may be an object with attribute 'edges' or a dict with key 'edges'
        edges_list = getattr(node, "edges", None) if hasattr(node, "edges") else (node.get("edges") if isinstance(node, dict) else None)
        if isinstance(edges_list, list):
            removed += _rm_from_list(edges_list, dst, rel)
        # Also check common alternative keys
        for key in ("out", "links", "outgoing"):
            alt = getattr(node, key, None) if hasattr(node, key) else (node.get(key) if isinstance(node, dict) else None)
            if isinstance(alt, list):
                removed += _rm_from_list(alt, dst, rel)

    # Global edge list: world.edges = [{src,dst,rel}, ...]
    gl = getattr(world, "edges", None)
    if isinstance(gl, list):
        before = len(gl)
        def match_gl(e: Dict[str, Any]) -> bool:
            s = e.get("src") or e.get("from") or e.get("src_id")
            d = _edge_get_dst(e)
            r = _edge_get_rel(e)
            if s != src or d != dst:
                return False
            return (rel is None) or (r == rel)
        gl[:] = [e for e in gl if not match_gl(e)]
        removed += before - len(gl)
    elif isinstance(gl, dict) and src in gl:
        lst = gl.get(src)
        if isinstance(lst, list):
            removed += _rm_from_list(lst, dst, rel)
    return removed


# --- CLI flow: delete edge (menu 24) ---------------------------------------------
# CLI helper that wraps world_delete_edge() and engine-level delete_edge(), plus autosave.

def delete_edge_flow(world: Any, autosave_cb=None) -> None:
    """delete edge

    """
    #messages and input values
    print("Delete edge (src -> dst [relation])")
    print("src -- enter the source binding, e.g., b1")
    print("dst -- enter the destination binding, e.g., b5")
    print("[relation] -- if multiple links between the two bindings you can optionally specify which one to delete")
    print("           -- you need to specify the exact label, not a substring\n")
    src = input("Source binding id (e.g., b1): ").strip()
    dst = input("Dest binding id (e.g., b5): ").strip()
    rel = input("Relation label (optional; blank = ANY): ").strip() or None

    #removal of link
    removed = 0
    for method in ("remove_edge", "delete_edge"):  #remove_edge() is an old alias for delete_edge, both here for compatibility
        if hasattr(world, method): #does the world object have this method?
            try:
                removed = getattr(world, method)(src, dst, rel) #fetches the bound method and calls it
                break
            except Exception:
                removed = 0 #any error then we will try world_delete_edge(...)
    if removed == 0: #if neither of remove_edge() nor delete_edge() existed/worked
        removed = world_delete_edge(world, src, dst, rel)

    #print message and autosave file
    print(f"Removed {removed} edge(s) {src} -> {dst}{(' (rel='+rel+')' if rel else '')}")
    if autosave_cb:
        try:
            autosave_cb()
        except Exception:
            pass


# ==== Spatial anchoring stubs (NO-OP placeholders for future attach semantics) ====

def _maybe_anchor_attach(default_attach: str, base: dict | None) -> str:
    """
    Base-aware attach helper: adjust the attach mode based on a suggested write-base.

    Today we keep the behavior very conservative:

      • If base is a NEAREST_PRED suggestion with a concrete 'bid' and the caller
        would have used attach="latest", we return "none". This signals that the
        caller should create the new binding unattached and then explicitly add
        base['bid'] --then--> new in a single, readable place.

      • In all other cases we simply return default_attach unchanged.

    This keeps the core WorldGraph attach semantics simple (now/latest/none) while
    giving us a single knob to turn write placement from naive 'LATEST' to
    base-anchored placement as the architecture evolves.

    Note: -We already compute a "write base" suggestion via choose_contextual_base(...)
            e.g., as seen in the Instinct Step menu selection.
          -These helpers (together with _add_pred_base_aware(...) in the Controller)
            provide a single choke point for future base-aware write semantics.
    Note: Nov 2025 -- pylint:disable=unused-argument removed as stub now filled in
    """
    if not isinstance(base, dict):
        return default_attach
    kind = base.get("base")
    bid = base.get("bid")
    if kind == "NEAREST_PRED" and isinstance(bid, str) and bid and default_attach == "latest":
        # Create the node unattached; the caller will add base['bid'] --then--> new.
        return "none"
    return default_attach


def _attach_via_base(world, base: dict | None, new_bid: str, *, rel: str = "then", meta: dict | None = None) -> None:
    """
    Attach a newly-created binding under the suggested base, when appropriate.

    This is intended to be used together with _maybe_anchor_attach(...):

      • The caller first chooses a base via choose_contextual_base(...),
        then calls _maybe_anchor_attach(default_attach, base) to decide the
        attach mode to pass into world.add_predicate/add_cue/etc.

      • If _maybe_anchor_attach(...) returned "none" for a NEAREST_PRED base,
        the caller can then invoke _attach_via_base(...) to add an explicit
        base['bid'] --rel--> new_bid edge for readability.

    For now we only attach for NEAREST_PRED suggestions; HERE/NOW bases are
    left to the default attach semantics to avoid duplicating edges.
    """
    if not isinstance(base, dict):
        return
    kind = base.get("base")
    base_bid = base.get("bid")
    if kind != "NEAREST_PRED" or not isinstance(base_bid, str) or not base_bid:
        return
    try:
        if base_bid not in world._bindings or new_bid not in world._bindings:
            return
    except Exception:
        return
    edge_meta = meta or {
        "created_by": "base_attach",
        "base_kind": kind,
        "base_pred": base.get("pred"),
    }
    try:
        world.add_edge(base_bid, new_bid, rel, meta=edge_meta)
        try:
            print(f"[base] attached {new_bid} under base {base_bid} via {rel} ({_fmt_base(base)})")
        except Exception:
            # Printing is purely diagnostic; ignore errors here.
            pass
    except Exception as e:
        try:
            print(f"[base] error while attaching {new_bid} under {base_bid}: {e}")
        except Exception:
            pass


# Minimal vocabulary for spatial edge labels in WorldGraph.
SPATIAL_REL_LABELS = {"near", "inside", "supports"}
def add_spatial_relation(world, src_bid: str, rel: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Sugar for scene-graph style relations (near, inside, supports).

    Today this is just an alias of world.add_edge(...). The 'rel' string is not
    strictly enforced here, but callers are encouraged to stick to the small,
    explicit vocabulary in SPATIAL_REL_LABELS to avoid label explosion.
    """
    world.add_edge(src_bid, dst_bid, rel, meta or {})


def add_spatial_inside(world, src_bid: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Stub helper for 'inside' spatial relation.

    Intended future use:
      SELF --inside--> SHELTER when the agent is resting in a sheltered niche.

    Currently unused; provided as a clearly named wrapper so future code can
    call it and we keep the label semantics centralized.
    """
    add_spatial_relation(world, src_bid, "inside", dst_bid, meta)


def add_spatial_supports(world, src_bid: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Stub helper for 'supports' spatial relation.

    Intended future use:
      ROCK --supports--> SELF when a particular surface is bearing the body,
      or SHELTER_FLOOR --supports--> SELF, etc.

    Currently unused; provided as a stub for future development.
    """
    add_spatial_relation(world, src_bid, "supports", dst_bid, meta)



# --------------------------------------------------------------------------------------
# Persistence: atomic JSON autosave (world, drives, skills)
# --------------------------------------------------------------------------------------

def save_session(path: str, world, drives) -> str:
    """Serialize (world, drives, skills) to JSON and atomically write to disk.

    Returns:
        The ISO timestamp used as 'saved_at' in the file.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    data = {
        "saved_at": ts,
        "world": world.to_dict(),
        "drives": drives.to_dict(),
        "skills": skills_to_dict(),
        "app_version": f"cca8_run/{__version__}",
        "platform": platform.platform(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return ts


def _module_version_and_path(modname: str) -> tuple[str, str]:
    """Return (version_string, path) for a module name, safely.
    - If module can't be imported → ('-- unavailable (i.e.,not found)', '<name>.py')
    - If no __version__ on module → ('n/a', path)
    """
    try:
        import importlib
        m = importlib.import_module(modname)
    except Exception:
        return "-- unavailable (i.e., not found)", f"{modname}.py"
    ver = getattr(m, "__version__", None)
    ver_str = str(ver) if ver is not None else "n/a"
    path = getattr(m, "__file__", f"{modname}.py")
    return ver_str, path


# --------------------------------------------------------------------------------------
# Embodiment / HAL skeleton (no real robotics yet)
# --------------------------------------------------------------------------------------

class HAL:
    """Hardware abstraction layer (HAL) skeleton for future usage
    """
    def __init__(self, body: str | None = None):
        # future usage: load body profile (motor map), open serial/network, etc.
        self.body = body or "(none)"
        # future usage: load body profile (motor map), open serial/network, etc.


    # Actuators
    def push_up(self):
        """Raise chest (stub)."""
        return False


    def extend_legs(self):
        """Extend legs (stub)."""
        return False


    def orient_to_mom(self):
        """Rotate toward maternal stimulus (stub)."""
        return False


    # Sensors
    def sense_vision_mom(self):
        """Return True if mother's silhouette is detected (stub)."""
        return False


    def sense_vestibular_fall(self):
        """Return True if fall is detected (stub)."""
        return False


# --------------------------------------------------------------------------------------
# Policy runtime: gates, Action Center, and console helpers
# --------------------------------------------------------------------------------------


# _hamming_hex64 moved to cca8_reporting.py.


def _fmt_base(d: dict) -> str:
    """helper to print base suggestion info,
    particularly during snapshot displays

    e.g., print(f"[context] write-base: {_fmt_base(base)}")
    """
    if not isinstance(d, dict):
        return str(d)
    kind = d.get("base")
    bid  = d.get("bid")
    if kind == "NEAREST_PRED":
        p = d.get("pred")
        return f"NEAREST_PRED(pred={p}) -> {bid}"
    elif kind:
        return f"{kind} -> {bid}"
    return str(d)


def print_header(hal_str: str = "HAL: off (no embodiment)", body_str: str = "Body: (none)") -> None:
    """Print the startup banner through the extracted CLI presentation module.

    The wrapper preserves the historical ``cca8_run.print_header`` call
    signature while supplying the runner version and current runner-visible logo
    callback to ``cca8_cli``.
    """
    cca8_cli.print_header(
        hal_str,
        body_str,
        runner_version=__version__,
        technical_manual=TECH_MANUAL,
        logo_printer=print_ascii_logo,
    )


def _readme_compendium_path_v1() -> str:
    """Return README.md beside the active runner through the guidance module."""
    return cca8_guidance.readme_compendium_path_v1(__file__)


def _print_brief_overview_of_key_concepts_v1(policy_rt: Any) -> None:
    """Compatibility wrapper for the concise map-first architecture overview."""
    print("Selection: Explanation of the Architecture")
    print(cca8_cli.MENU_RESPONSE_DIVIDER)
    print()
    print_architecture_overview_v1(policy_rt)


def _open_readme_compendium_v1() -> None:
    """Compatibility wrapper for opening the README/compendium."""
    cca8_guidance.open_readme_compendium_v1(_readme_compendium_path_v1())


def _architecture_explanation_menu_v1(policy_rt: Any) -> None:
    """Open Main Menu #3 through the extracted architecture-guidance flow."""
    runtime = cca8_guidance.ArchitectureMenuRuntimeV1(
        overview_printer=print_architecture_overview_v1,
        tagging_printer=print_tagging_and_policies_help,
        readme_path=_readme_compendium_path_v1(),
        divider=cca8_cli.MENU_RESPONSE_DIVIDER,
    )
    cca8_guidance.architecture_explanation_menu_v1(policy_rt, runtime)


def _help_menu_v1(policy_rt: Any) -> None:
    """Compatibility wrapper for the architecture-explanation menu."""
    _architecture_explanation_menu_v1(policy_rt)


_watch_cognition_menu_v1 = cca8_cli.watch_cognition_menu_v1


# --- WorldGraph snapshot + engram helpers (runner-facing) ------------------------


def _resolve_engrams_pretty(world, bid: str) -> None:
    """used with resolve engrams menu selection
    -from bid gets column01: {"id": eid, "act": 1.0}
    -prints these out as, e.g., Engrams on b3; column01: 34c406dd…  OK
    """

    b = world._bindings.get(bid)
    # e.g., Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={}, engrams={'column01': {'id': '302ca8b28d0c4e03b501c2d1d23ffa76', 'act': 1.0}})
    # -world is the live WorldGraph instance created at runner start inside interactive_loop
    if not b:
        print("Unknown binding id.")
        return
    eng = getattr(b, "engrams", None)
    # e.g., {'column01': {'id': '34c406dd346f4a6fb8bd356d01da9f79', 'act': 1.0}}
    #  -{"id": eid, "act": 1.0} (id = engram id, act = activation weight)
    if not isinstance(eng, dict) or not eng:
        print("Engrams: (none)")
        return
    print("Engrams on", bid)

    for slot, val in sorted(eng.items()):
        eid = val.get("id") if isinstance(val, dict) else None
        ok = False
        try:
            rec = world.get_engram(engram_id=eid) if isinstance(eid, str) else None
            ok = bool(rec and isinstance(rec, dict) and rec.get("id") == eid)
        except Exception:
            ok = False
        status = "OK" if ok else "(dangling)"
        short = (eid[:8] + "…") if isinstance(eid, str) else "(id?)"
        print(f"  {slot}: {short}  {status}")


def _bindings_pointing_to_eid(world, eid: str):
    """allows inspect engrams to tell which bindings
    reference the eid
    """
    refs = []
    for bid, b in world._bindings.items():
        eng = getattr(b, "engrams", None)
        if isinstance(eng, dict):
            for slot, val in eng.items():
                if isinstance(val, dict) and val.get("id") == eid:
                    refs.append((bid, slot))
    return refs


# ==== Temporal / timekeeping legend and one-line summary helpers ==================

# _snapshot_temporal_legend moved to cca8_reporting.py.


# timekeeping_line moved to cca8_reporting.py.


# print_timekeeping_line moved to cca8_reporting.py.


# ==== Developer utilities: LOC, vector parsing, and loop helper ===================
# _python_loc_counts_for_file moved to cca8_reporting.py.


# _compute_loc_by_dir moved to cca8_reporting.py.


# _render_loc_by_dir_table moved to cca8_reporting.py.


# _parse_vector moved to cca8_reporting.py.


def loop_helper(autosave_from_args: Optional[str], world, drives, ctx=None, time_limited: bool = False):
    """
    Operations to run at the end of each menu branch before looping again.
    Currently: autosave (if enabled), optional mini-snapshot, visual spacer.
    Mini-snapshot -- print a compact binding/edge list plus one line of timekeeping values
    Future: time-limited bypasses for real-world ops.
    """
    if time_limited:
        return #from the loop_helper (not menu loop), i.e., just return without doing anything
    if autosave_from_args:
        save_session(autosave_from_args, world, drives)
        # Quiet by default; uncomment for debugging:
        # print(f"[autosaved {ts}] {autosave_from_args}")
    try:
        if ctx is not None and getattr(ctx, "mini_snapshot", False):
            print()
            print_mini_snapshot(world, ctx, limit=50)
    except Exception:
        pass
    print("\n-----\n") #visual spacer before menu prints again
    #this is usually the end of the elif branch of a menu selection block
    #thus, control now falls to the bottom of the while loop and then back to top where while True starts its next iteration




_open_worldgraph_pyvis_flow_v1 = cca8_cognitive_scope_menu.open_worldgraph_pyvis_flow_v1
_show_architecture_status_v1 = cca8_cognitive_scope_menu.show_architecture_status_v1
_show_recent_bindings_v1 = cca8_cognitive_scope_menu.show_recent_bindings_v1
_show_drives_v1 = cca8_cognitive_scope_menu.show_drives_v1
_show_timekeeping_status_v1 = cca8_cognitive_scope_menu.show_timekeeping_status_v1
_show_skill_telemetry_v1 = cca8_cognitive_scope_menu.show_skill_telemetry_v1
_cognitive_scope_live_snapshot_v1 = cca8_cognitive_scope_menu.cognitive_scope_live_snapshot_v1
_cognitive_scope_prompt_port_detail_v1 = cca8_cognitive_scope_menu.cognitive_scope_prompt_port_detail_v1
_cognitive_scope_show_compact_snapshot_v1 = cca8_cognitive_scope_menu.cognitive_scope_show_compact_snapshot_v1


def _cognitive_scope_injection_runtime_v1() -> cca8_cognitive_injection.CognitiveInjectionRuntimeV1:
    """Return the runner-owned callback bundle for disposable DP01 injection."""
    return cca8_cognitive_injection.CognitiveInjectionRuntimeV1(
        policy_runtime_factory=lambda: PolicyRuntime(CATALOG_GATES),
        run_closed_loop_steps=run_env_closed_loop_steps,
        skill_store=cca8_controller.SKILLS,
        column_memory=column_mem,
    )


def _cognitive_scope_injection_flow_v1(ctx: Any) -> None:
    """Compatibility wrapper for the extracted DP01 sandbox menu flow."""
    cca8_cognitive_scope_menu.cognitive_scope_injection_flow_v1(
        ctx,
        _cognitive_scope_injection_runtime_v1(),
        show_compact_snapshot=_cognitive_scope_show_compact_snapshot_v1,
    )


def _cognitive_scope_menu_runtime_v1() -> cca8_cognitive_scope_menu.CognitiveScopeMenuRuntimeV1:
    """Build Main Menu #2 callbacks from current runner-visible helpers."""
    return cca8_cognitive_scope_menu.CognitiveScopeMenuRuntimeV1(
        show_architecture_status=_show_architecture_status_v1,
        show_recent_bindings=_show_recent_bindings_v1,
        show_drives=_show_drives_v1,
        show_timekeeping_status=_show_timekeeping_status_v1,
        show_skill_telemetry=_show_skill_telemetry_v1,
        open_worldgraph_pyvis=_open_worldgraph_pyvis_flow_v1,
        run_injection_flow=_cognitive_scope_injection_flow_v1,
        build_live_snapshot=_cognitive_scope_live_snapshot_v1,
        show_compact_snapshot=_cognitive_scope_show_compact_snapshot_v1,
        legacy_snapshot_text=snapshot_text,
    )


def _cognitive_scope_menu_v1(env: Any, world: Any, drives: Any, ctx: Any, policy_rt: Any) -> str | None:
    """Open the inspector and return an optional established read-only handler."""
    return cca8_cognitive_scope_menu.cognitive_scope_menu_v1(
        env,
        world,
        drives,
        ctx,
        policy_rt,
        runtime=_cognitive_scope_menu_runtime_v1(),
    )


def _drive_tags(drives) -> list[str]:
    """Robustly compute drive:* tags even if Drives.flags()/predicates() is missing.

    If the Drives class has .flags() use that; fallback to .predicates(); else derive
    by thresholds: hunger>0.6 → drive:hunger_high; fatigue>0.7 → drive:fatigue_high; warmth<0.3 → drive:cold.
    """
    # Prefer the new API
    if hasattr(drives, "flags") and callable(getattr(drives, "flags")):
        try:
            tags = list(drives.flags())
            return [t for t in tags if isinstance(t, str)]
        except Exception:
            pass

    # Back-compat
    if hasattr(drives, "predicates") and callable(getattr(drives, "predicates")):
        try:
            tags = list(drives.predicates())
            return [t for t in tags if isinstance(t, str)]
        except Exception:
            pass

    # Last-resort derived flags
    tags = []
    try:
        if getattr(drives, "hunger", 0.0) > 0.6:
            tags.append("drive:hunger_high")
        if getattr(drives, "fatigue", 0.0) > 0.7:
            tags.append("drive:fatigue_high")
        if getattr(drives, "warmth", 1.0) < 0.3:
            tags.append("drive:cold")
    except Exception:
        pass
    return tags


def _emit_interoceptive_cues(world, drives, ctx, attach: str = "latest") -> set[str]:
    """
    Emit `cue:drive:*` on rising-edge transitions (e.g., hunger crosses HUNGER_HIGH).
    Returns the set of flags that started this tick, e.g., {"drive:hunger_high"}.
    House style: treat drive thresholds as *evidence* (cue:*), not planner goals.
    """
    try:
        flags_now: set[str] = set(_drive_tags(drives))         # e.g., {"drive:hunger_high", "drive:fatigue_high"}
        flags_prev: set[str] = getattr(ctx, "last_drive_flags", set()) or set()
        started = flags_now - flags_prev #perhaps, e.g., {"drive:hunger_high"}
        for f in sorted(started):
            # world.add_cue normalizes to tag "cue:<token>"
            world.add_cue(f, attach=attach, meta={"created_by": "autonomic", "ticks": getattr(ctx, "ticks", 0)})
            #e.g., creates a new binding whose tag will inlcude f, perhaps e.g., "cue:drive:hunger_high"
        ctx.last_drive_flags = flags_now
        #return rising-edge drive thresholds that occurred here, e.g., "drive:hunger_high"
        #remember... cues can function as policy triggers focus of attention, but we *do not* write all the sensory cues streaming
        #  into the architecture -- we capture some of this as engrams; again, cues are part of a lightweight symbolic layer
        return started
    except Exception:
        return set()


def _normalize_pred(tok: str) -> str:
    """Ensure a token is 'pred:<x>' form (idempotent).
    """
    return tok if tok.startswith("pred:") else f"pred:{tok}"


def _neighbors(world, bid: str) -> List[str]:
    """Return outgoing neighbor ids from a binding, being tolerant of alternative edge
         layouts ('edges'/'out'/'links')."""
    b = world._bindings.get(bid)
    if not b:
        return []
    edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
    out = []
    if isinstance(edges, list):
        for e in edges:
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if dst:
                out.append(dst)
    return out


def _engrams_on_binding(world, bid: str) -> list[str]:
    """Return engram ids attached to a binding (via binding.engrams).
    -in world instance of class World -- self._bindings={}, i.e., in the instance world, world_bindings.keys() is a

    """
    b = world._bindings.get(bid)
    #-nodes in world instance of WorldGraph are dataclass Binding
    #-fields of dataclass Binding -- id, tags {set}, edges [list of TypedDict Edges {to:___, label:___, meta:___}, {}...], meta {dict}, engrams {dict}
    #-b=Binding below is an instance of dataclass Binding corresponding to, e.g., node b3
    #   nb. Python objects don't have an intrinsic 'instance name' -- just have variables point at them
    # e.g., b= Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={},
    #          engrams={'column01': {'id': '9e48b29cb0614f71b8435e4cab01082a', 'act': 1.0}})
    if not b:
        return []
    eng = getattr(b, "engrams", None) or {}
    # e.g., eng = {'column01': {'id': '9e48b29cb0614f71b8435e4cab01082a', 'act': 1.0}}
    out: list[str] = []
    if isinstance(eng, dict):
        for v in eng.values():
            if isinstance(v, dict):
                eid = v.get("id")
                #e.g., eid = 9e48b29cb0614f71b8435e4cab01082a
                if isinstance(eid, str):
                    out.append(eid)
    return out


def _bfs_reachable(world, src: str, dst: str, max_hops: int = 3) -> bool:
    """Light BFS reachability within `max_hops` hops; early exit on first match.
    """
    from collections import deque
    if src == dst:
        return True
    q, seen, depth = deque([src]), {src}, {src: 0}
    while q:
        u = q.popleft()
        if depth[u] >= max_hops:
            continue
        for v in _neighbors(world, u):
            if v in seen:
                continue
            if v == dst:
                return True
            seen.add(v)
            depth[v] = depth[u] + 1
            q.append(v)
    return False


def _bindings_with_pred(world, token: str) -> List[str]:
    """Return binding ids whose tags contain pred:<token> (exact match)."""
    want = _normalize_pred(token)
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out


def _bindings_with_cue(world, token: str) -> List[str]:
    """Return binding ids whose tags contain cue:<token> (exact match)."""
    want = f"cue:{token}"
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out


def any_cue_tokens_present(world, tokens: List[str]) -> bool:
    """Return True if **any** `cue:<token>` exists anywhere in the graph.
    """
    return any(bool(_bindings_with_cue(world, tok)) for tok in tokens)


def has_pred_near_now(world, token: str, hops: int = 3) -> bool:
    """Return True if any pred:<token> is reachable from NOW in ≤ `hops` edges."""
    now_id = _anchor_id(world, "NOW")
    for bid in _bindings_with_pred(world, token):
        if _bfs_reachable(world, now_id, bid, max_hops=hops):
            return True
    return False


def any_pred_present(world, tokens: List[str]) -> bool:
    """Return True if any pred:<token> in `tokens` exists anywhere in the graph."""
    return any(bool(_bindings_with_pred(world, tok)) for tok in tokens)


def neighbors_near_self(world) -> List[str]:
    """
    Return binding ids that are directly connected from NOW via a 'near' edge.

        NOW --near--> bN

    This queries the main WorldGraph (episode index), not the BodyMap. It is
    purely descriptive sugar over the scene-graph edges written by
    _write_spatial_scene_edges(...).
    """
    now_id = _anchor_id(world, "NOW")
    if not now_id or now_id == "?" or now_id not in world._bindings:
        return []

    b = world._bindings.get(now_id)
    if not b:
        return []

    edges_raw = (
        getattr(b, "edges", []) or
        getattr(b, "out", []) or
        getattr(b, "links", []) or
        getattr(b, "outgoing", [])
    )

    out: list[str] = []
    if isinstance(edges_raw, list):
        for e in edges_raw:
            if not isinstance(e, dict):
                continue
            rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
            if rel != "near":
                continue
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if isinstance(dst, str) and dst in world._bindings:
                out.append(dst)

    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for bid in out:
        if bid not in seen:
            seen.add(bid)
            uniq.append(bid)
    return uniq


def resting_scenes_in_shelter(world) -> Dict[str, Any]:
    """
    Query helper for the current episode around NOW:

    Returns a dict with:
      {
        "rest_near_now": bool,           # pred:resting reachable from NOW within a small radius
        "shelter_near_now": bool,        # NOW --near--> binding(s) with pred:proximity:shelter:near
        "shelter_bids": list[str],       # those shelter-near binding ids
        "hazard_cliff_far_near_now": bool,  # pred:hazard:cliff:far reachable from NOW
      }

    This is intentionally simple and descriptive. It does NOT alter the world
    or planner; it just inspects the structure produced by the env loop and
    scene-graph writer.

    Typical use:
      - Ask "are we in a 'resting in shelter, cliff far' configuration now?"
      - That is approximately when:
          rest_near_now
          and shelter_near_now
          and hazard_cliff_far_near_now
    """
    now_id = _anchor_id(world, "NOW")
    if not now_id or now_id == "?" or now_id not in world._bindings:
        return {
            "rest_near_now": False,
            "shelter_near_now": False,
            "shelter_bids": [],
            "hazard_cliff_far_near_now": False,
        }

    # 1) Is there any 'resting' predicate reachable from NOW within a few hops?
    rest_near_now = has_pred_near_now(world, "resting", hops=3)

    # 2) Which neighbors via NOW --near--> are shelter-near bindings?
    near_ids = neighbors_near_self(world)
    shelter_bids: list[str] = []
    for bid in near_ids:
        b = world._bindings.get(bid)
        if not b:
            continue
        tags = getattr(b, "tags", []) or []
        if any(isinstance(t, str) and t == "pred:proximity:shelter:near" for t in tags):
            shelter_bids.append(bid)

    shelter_near_now = bool(shelter_bids)

    # 3) Is there any 'hazard:cliff:far' near NOW?
    hazard_cliff_far_near_now = has_pred_near_now(world, "hazard:cliff:far", hops=3)

    return {
        "rest_near_now": rest_near_now,
        "shelter_near_now": shelter_near_now,
        "shelter_bids": shelter_bids,
        "hazard_cliff_far_near_now": hazard_cliff_far_near_now,
    }


# Policy gates, NavSummary gate helpers, and newborn control bridges moved to cca8_policy_runtime.py.


def apply_hardwired_profile_phase7(ctx: "Ctx", world) -> None:
    """Hardwire the Phase VII daily-driver memory pipeline.

    Intent:
      - WorkingMap: dense workspace (env mirroring always on; policy execution writes can live here)
      - WorldGraph: sparse long-term index (env obs in changes mode + keyframes + cue dedup + run-compressed actions)
      - RL: off by default (deterministic selection while we validate memory mechanics)

    This replaces the need for Menu 41 in normal use.
    """
    if ctx is None or world is None:
        return

    # --- RL: enabled (deterministic by default) ---
    # turning RL ON, but keeping exploration essentially OFF (epsilon=0.05) so behavior stays reproducible.
    # You still get q-based tie-break behavior when it applies.
    try:
        ctx.rl_enabled = True
        ctx.rl_epsilon = 0.05  # % explore, i.e., the amount of randomness
        ctx.rl_delta = 0.0     # q used only for exact deficit ties (safe default)
        ctx.rl_explore_steps = 0
        ctx.rl_exploit_steps = 0
    except Exception:
        pass

    # --- WorkingMap: on (trace/workspace) ---
    try:
        ctx.working_enabled = True
        ctx.working_verbose = True
        ctx.working_max_bindings = 250
        if hasattr(ctx, "working_move_now"):
            ctx.working_move_now = True
    except Exception:
        pass

    # --- Phase VII: motor runs + (optionally) working-first execution ---
    try:
        ctx.phase7_working_first = True
        ctx.phase7_run_compress = True
        ctx.phase7_run_verbose = False
        ctx.phase7_move_longterm_now_to_env = True
    except Exception:
        pass

    # --- MapSurface auto-retrieve at keyframes (safe default = merge) ---
    try:
        ctx.wm_mapsurface_autoretrieve_enabled = True
        ctx.wm_mapsurface_autoretrieve_mode = "merge"
        ctx.wm_mapsurface_autoretrieve_top_k = 5
        ctx.wm_mapsurface_autoretrieve_verbose = True
    except Exception:
        pass

    # --- WorldGraph memory mode: keep literal time semantics for long-term writes ---
    try:
        if hasattr(world, "set_memory_mode"):
            world.set_memory_mode("episodic")
    except Exception:
        pass

    # --- Long-term EnvObservation injection: sparse + keyframes + cue dedup ---
    try:
        ctx.longterm_obs_enabled = True
        ctx.longterm_obs_mode = "changes"
        ctx.longterm_obs_reassert_steps = 0

        # IMPORTANT:
        # The Phase VII hardwired profile enables the memory pipeline, but it must NOT override
        # keyframe trigger knobs (stage/zone/periodic/pred_err/milestone/emotion). Those are
        # experiment settings on Ctx and should remain under direct user control.

        ctx.longterm_obs_verbose = False
    except Exception:
        pass


    # Low-noise, useful log
    try:
        if hasattr(ctx, "longterm_obs_keyframe_log"):
            ctx.longterm_obs_keyframe_log = True
    except Exception:
        pass

    # Cue dedup (presence/rising-edge)
    try:
        if hasattr(ctx, "longterm_obs_dedup_cues"):
            ctx.longterm_obs_dedup_cues = True
    except Exception:
        pass

    # Clear long-term slot caches (dedup bookkeeping) so the next env obs is a clean "first".
    try:
        ctx.lt_obs_slots.clear()
    except Exception:
        pass
    try:
        if hasattr(ctx, "lt_obs_cues"):
            ctx.lt_obs_cues.clear()
    except Exception:
        pass
    try:
        ctx.lt_obs_last_stage = None
    except Exception:
        pass

    # Clear any open run-compression state (defensive; safe no-op if fields not present)
    try:
        if hasattr(ctx, "run_open"):
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
    except Exception:
        pass


# -----------------------------------------------------------------------------
# EFE policy scoring (Phase X 2.2b): diagnostic stub (no selection changes)
# -----------------------------------------------------------------------------
# EFE scoring, PolicyGate, PolicyRuntime, and the gate catalog moved to cca8_policy_runtime.py.


def _first_binding_with_pred(world, token: str) -> str | None:
    """Return the first binding id that carries pred:<token>, else None."""
    want = token if token.startswith("pred:") else f"pred:{token}"
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                return bid
    return None


def boot_prime_stand(world, ctx) -> None:
    """
    At birth (age_days == 0), seed a simple initial posture state for the kid:

    - Ensure there is a `posture:fallen` predicate reachable from NOW.
    - If not present, create it attached to NOW.
    - Use generic 'then' as the edge label (no special 'initiate_*' action label).

    Idempotent and safe to call on a fresh session.
    """
    # Only at birth
    try:
        if float(getattr(ctx, "age_days", 0.0)) != 0.0:
            return
    except Exception:
        return

    now_id = _anchor_id(world, "NOW")

    # Look for an existing fallen-posture predicate
    fallen_bid = _first_binding_with_pred(world, "posture:fallen")
    if fallen_bid:
        # If NOW can't reach it in 1 hop, add a 'then' edge
        if not _bfs_reachable(world, now_id, fallen_bid, max_hops=1):
            try:
                world.add_edge(now_id, fallen_bid, "then")
                print(f"[boot] Linked {now_id} --then--> {fallen_bid} (posture:fallen)")
            except Exception as e:
                print(f"[boot] Could not link NOW->posture:fallen: {e}")
        return

    # Otherwise, create a new fallen-posture binding attached to NOW
    try:
        fallen_bid = world.add_predicate(
            "posture:fallen",
            attach="now",
            meta={"boot": "init", "added_by": "system"},
        )
        print(f"[boot] Seeded posture:fallen as {fallen_bid} (birth-state binding; anchor:NOW → pred:posture:fallen)")
    except Exception as e:
        print(f"[boot] Could not seed posture:fallen: {e}")


# Profile/tutorial implementations were extracted to cca8_profiles.py and cca8_guidance.py.
# The former per-helper relocation placeholders are consolidated here; no implementation is removed.


# --------------------------------------------------------------------------------------
# World/intro flows: profile selection, startup notices, preflight-lite
# --------------------------------------------------------------------------------------

# choose_profile moved to cca8_profiles.py or cca8_guidance.py.


_CCA8_COMPONENT_REGISTRY: tuple[tuple[str, str], ...] = (
    ("world_graph", "cca8_world_graph"),
    ("controller", "cca8_controller"),
    ("column", "cca8_column"),
    ("features", "cca8_features"),
    ("env", "cca8_env"),
    ("support_world", "cca8_support_world"),
    ("motor_contracts", "cca8_motor_contracts"),
    ("context", "cca8_context"),
    ("cli", "cca8_cli"),
    ("preflight", "cca8_preflight"),
    ("experiments", "cca8_experiments"),
    ("openai", "cca8_openai"),
    ("working_memory", "cca8_working_memory"),
    ("profiles", "cca8_profiles"),
    ("guidance", "cca8_guidance"),
    ("navmap", "cca8_navmap"),
    ("navmap_kernel", "cca8_navmap_kernel"),
    ("navmap_shadow", "cca8_navmap_shadow"),
    ("navmap_runtime", "cca8_navmap_runtime"),
    ("maternal_geometry", "cca8_maternal_geometry"),
    ("maternal_temporal", "cca8_maternal_temporal"),
    ("maternal_continuity", "cca8_maternal_continuity"),
    ("followmom_compare", "cca8_followmom_compare"),
    ("followmom_advisory", "cca8_followmom_advisory"),
    ("followmom_authority", "cca8_followmom_authority"),
    ("feeding", "cca8_feeding"),
    ("terrain", "cca8_terrain"),
    ("live_dynamics", "cca8_live_dynamics"),
    ("main_menu", "cca8_main_menu"),
    ("navmap_memory", "cca8_navmap_memory"),
    ("wnm_runtime", "cca8_wnm_runtime"),
    ("cognitive_scope", "cca8_cognitive_scope"),
    ("cognitive_scope_menu", "cca8_cognitive_scope_menu"),
    ("cognitive_injection", "cca8_cognitive_injection"),
    ("standup_compare", "cca8_standup_compare"),
    ("reporting", "cca8_reporting"),
    ("observation_runtime", "cca8_observation_runtime"),
    ("policy_runtime", "cca8_policy_runtime"),
    ("navpatch", "cca8_navpatch"),
    ("rcos", "cca8_rcos"),
    ("rcos_menu", "cca8_rcos_menu"),
    ("rcos_experiments", "cca8_rcos_experiments"),
    ("state_integrity", "cca8_state_integrity"),
    ("session_menu", "cca8_session_menu"),
    ("teaching", "cca8_teaching"),
    ("predictive", "cca8_predictive"),
    ("test_fixtures", "cca8_test_fixtures"),
    ("nca8_adapters", "nca8_adapters"),
    ("nca8_body", "nca8_body"),
    ("nca8_body_targets", "nca8_body_targets"),
    ("nca8_contracts", "nca8_contracts"),
    ("nca8_righting", "nca8_righting"),
    ("nca8_righting_demo", "nca8_righting_demo"),
    ("nca8_sensorimotor", "nca8_sensorimotor"),
    ("nca8_sensorimotor_contracts", "nca8_sensorimotor_contracts"),
    ("nca8_sensorimotor_demo", "nca8_sensorimotor_demo"),
    ("nca8_executive", "nca8_executive"),
    ("nca8_handoff", "nca8_handoff"),
    ("nca8_hierarchy", "nca8_hierarchy"),
    ("nca8_hierarchy_demo", "nca8_hierarchy_demo"),
    ("nca8_hierarchy_qualification", "nca8_hierarchy_qualification"),
    ("nca8_learning", "nca8_learning"),
    ("nca8_learning_demo", "nca8_learning_demo"),
    ("nca8_learning_registry", "nca8_learning_registry"),
    ("nca8_outcome_attention", "nca8_outcome_attention"),
    ("nca8_outcome_attention_demo", "nca8_outcome_attention_demo"),
    ("nca8_outcomes", "nca8_outcomes"),
    ("nca8_outcomes_demo", "nca8_outcomes_demo"),
    ("nca8_support_dynamics", "nca8_support_dynamics"),
    ("nca8_maps", "nca8_maps"),
    ("nca8_menu", "nca8_menu"),
    ("nca8_prediction", "nca8_prediction"),
    ("nca8_primitives", "nca8_primitives"),
    ("nca8_runtime", "nca8_runtime"),
    ("nca8_scheduler", "nca8_scheduler"),
    ("nca8_sensory", "nca8_sensory"),
    ("nca8_trace", "nca8_trace"),
    ("nca8_maternal", "nca8_maternal"),
    ("nca8_maternal_outcomes", "nca8_maternal_outcomes"),
    ("nca8_maternal_attention", "nca8_maternal_attention"),
    ("nca8_maternal_attention_demo", "nca8_maternal_attention_demo"),
    ("nca8_maternal_learning", "nca8_maternal_learning"),
    ("nca8_maternal_learning_demo", "nca8_maternal_learning_demo"),
    ("nca8_followmom", "nca8_followmom"),
    ("nca8_followmom_demo", "nca8_followmom_demo"),
    ("nca8_followmom_qualification", "nca8_followmom_qualification"),
    ("nca8_feeding", "nca8_feeding"),
    ("nca8_feeding_demo", "nca8_feeding_demo"),
    ("nca8_oral_demo", "nca8_oral_demo"),
    ("nca8_oral_seal_demo", "nca8_oral_seal_demo"),
    ("nca8_oral_extraction_demo", "nca8_oral_extraction_demo"),
    ("nca8_suckle", "nca8_suckle"),
    ("nca8_suckle_demo", "nca8_suckle_demo"),
    ("nca8_suckle_outcomes", "nca8_suckle_outcomes"),
    ("nca8_suckle_outcomes_demo", "nca8_suckle_outcomes_demo"),
    ("nca8_suckle_attention", "nca8_suckle_attention"),
    ("nca8_suckle_attention_demo", "nca8_suckle_attention_demo"),
    ("nca8_suckle_learning", "nca8_suckle_learning"),
    ("nca8_suckle_learning_demo", "nca8_suckle_learning_demo"),
    ("nca8_seek_nipple", "nca8_seek_nipple"),
    ("nca8_seek_nipple_demo", "nca8_seek_nipple_demo"),
    ("nca8_seek_attention", "nca8_seek_attention"),
    ("nca8_seek_attention_demo", "nca8_seek_attention_demo"),
    ("nca8_seek_learning", "nca8_seek_learning"),
    ("nca8_seek_learning_demo", "nca8_seek_learning_demo"),
    ("nca8_seek_outcomes", "nca8_seek_outcomes"),
    ("nca8_seek_outcomes_demo", "nca8_seek_outcomes_demo"),
    ("nca8_stand_follow_demo", "nca8_stand_follow_demo"),
    ("nca8_translation", "nca8_translation"),
    ("nca8_translation_demo", "nca8_translation_demo"),
    ("nca8_visual", "nca8_visual"),
    ("nca8_visual_demo", "nca8_visual_demo"),
)


def _cca8_component_rows() -> list[tuple[str, str, str]]:
    """Return canonical ``(label, version, path)`` rows for CCA8 diagnostics.

    The registry above is the single source of truth for ``versions_dict()``,
    ``versions_text()``, and the ``--about`` command. New production modules
    should be added there once so every component report stays synchronized.
    """
    rows = [("cca8_run.py", __version__, os.path.abspath(__file__))]
    for _key, module_name in _CCA8_COMPONENT_REGISTRY:
        version, path = _module_version_and_path(module_name)
        rows.append((module_name, version, path))
    return rows


def versions_dict() -> dict:
    """Collect versions and paths for the canonical CCA8 component registry."""
    info = {
        "runner": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }

    for key, module_name in _CCA8_COMPONENT_REGISTRY:
        version, path = _module_version_and_path(module_name)
        info[key] = version
        info[key + "_path"] = path

    return info


def versions_text() -> str:
    """Return a human-readable summary of every registered CCA8 component."""
    versions = versions_dict()
    lines = [f"runner: {versions.get('runner', 'n/a')}"]
    for key, _module_name in _CCA8_COMPONENT_REGISTRY:
        lines.append(f"{key}: {versions.get(key, 'n/a')}")
    return "\n".join(lines)


# TeeTextIO moved to cca8_reporting.py.


# install_terminal_tee moved to cca8_reporting.py.


# print_startup_notices moved to cca8_reporting.py.


# OpenAI response parsing is implemented in cca8_openai and aliased near the runtime seam.



def run_llm_operational_preflight_check(timeout_seconds: float = 20.0) -> dict[str, Any]:
    """Run the extracted LLM preflight check through runner-owned OpenAI helpers.

    This compatibility wrapper preserves ``cca8_run.run_llm_operational_preflight_check``
    and deliberately resolves the runner helpers at call time so tests and local
    experiments can continue to monkeypatch them.
    """
    return cca8_preflight.run_llm_operational_preflight_check(
        timeout_seconds,
        default_model_name=_openai_default_model_name,
        response_request_options=_openai_response_request_options_v1,
        response_text=_openai_response_text_best_effort,
    )


def _make_preflight_runtime() -> cca8_preflight.PreflightRuntime:
    """Build the explicit runner-to-preflight dependency bridge.

    The bridge is constructed only when a full preflight starts. This avoids a
    circular import and ensures the extracted preflight receives the current
    runner functions, including any replacements installed by focused tests.
    """
    return cca8_preflight.PreflightRuntime(
        policy_runtime_factory=PolicyRuntime,
        catalog_gates=CATALOG_GATES,
        anchor_id=_anchor_id,
        resolve_engrams_pretty=_resolve_engrams_pretty,
        init_body_world=init_body_world,
        save_session=save_session,
        timekeeping_line=timekeeping_line,
        ensure_now_origin=ensure_now_origin,
        update_body_world_from_obs=update_body_world_from_obs,
        seek_nipple_gate=_gate_seek_nipple_trigger_body_first,
        rest_gate=_gate_rest_trigger_body_space,
        inject_obs_into_world=inject_obs_into_world,
        resting_scenes_in_shelter=resting_scenes_in_shelter,
        print_ascii_logo=print_ascii_logo,
        llm_operational_check=run_llm_operational_preflight_check,
        non_win_linux=NON_WIN_LINUX,
        placeholder_embodiment=PLACEHOLDER_EMBODIMENT,
    )


def run_preflight_full(args: Any) -> int:
    """Run the full extracted preflight while preserving the runner public API."""
    return cca8_preflight.run_preflight_full(args, _make_preflight_runtime())


def run_preflight_lite_maybe() -> None:
    """Run the extracted optional startup preflight notice."""
    cca8_preflight.run_preflight_lite_maybe()



def _anchor_id(world, name="NOW") -> str:
    """Return the binding id for anchor:<name>, scanning internals or tags; '?' if not found."""
    # Try a direct lookup if available
    try:
        if hasattr(world, "_anchors") and isinstance(world._anchors, dict):
            bid = world._anchors.get(name)
            if bid:
                return bid
    except Exception:
        pass
    # Fallback: scan tags
    for bid, b in world._bindings.items():
        if any(t == f"anchor:{name}" for t in getattr(b, "tags", [])):
            return bid
    return "?"


def _sorted_bids(world) -> list[str]:
    """Return binding ids sorted numerically (b1, b2, ...), with non-numeric ids last.
    -in class World self._bindings={}, i.e., in the instance world, world_bindings.keys() is a
    dict_keys view of all the keys  e.g., dict_keys(['b1', 'b2', 'b3', 'b4'.....])
    nb. Python 3.7+ dicts preserve insertion order, so that is what will be obtained before sorting
    """

    def key_fn(bid: str):
        """
        -strip out the 'b' for sorting bindings, and alphabetical bindings, e.g., NOW,
            sort after the 'b' numerical ones
        -in Python the key= value can be any comparable object, including tuples
        -thus, (0,n) where 'n' is from bn will be sorted ahead of (1, abc) where abc is an alpha binding, e.g., "NOW"
        """
        if bid.startswith("b") and bid[1:].isdigit():
            return (0, int(bid[1:]))   # group 0: numeric, sorted by number
        return (1, bid)                # group 1: non-numeric, sorted by string
    return sorted(world._bindings.keys(), key=key_fn)


# NavMap diagnostic summaries, terminal renderers, and Oscilloscope reporting
# moved to cca8_navmap_runtime.py; compatibility aliases are defined near the imports.



# snapshot_text moved to cca8_reporting.py.


# export_snapshot moved to cca8_reporting.py.


# recent_bindings_text moved to cca8_reporting.py.


# EnvObservation -> BodyMap updates moved to cca8_observation_runtime.py.


# Sequential/error observation processing moved to cca8_observation_runtime.py.


# Spatial observation-edge writing moved to cca8_observation_runtime.py.


# Observation valence tagging moved to cca8_observation_runtime.py.


# WorkingMap pruning moved to cca8_working_memory.py (Phase 3).

# -----------------------------------------------------------------------------
# NavPatch (Phase X): predictive matching loop (priors OFF baseline)
# -----------------------------------------------------------------------------

# _navpatch_tag_jaccard moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _navpatch_extent_sim moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# navpatch_similarity_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# navpatch_priors_bundle_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# navpatch_candidate_prior_bias_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# navpatch_predictive_match_loop_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# -----------------------------------------------------------------------------
# Per-cycle JSON record helper (Phase X)
# -----------------------------------------------------------------------------

# Per-cycle JSON/JSONL storage moved to cca8_observation_runtime.py.


# wm_apply_grid_slot_families_to_mapsurface_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_dir8_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_local_points_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_corridor_count_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_shortest_safe_path_cost_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# compute_navsummary_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# format_navsummary_line_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_entity_pos_xy_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_entity_kind_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_entity_dist_class_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_pos_to_grid_cell_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_window_anchor_v2 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_scene_fingerprint_v2 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_surfacegrid_dirty_reasons_v2 moved to cca8_working_memory.py (Working Memory refactor Phase 2).

# _surfacegrid_ascii_lines_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_entity_mark_char_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_display_focus_entities_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# render_surfacegrid_ascii_with_salience_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# format_surfacegrid_ascii_map_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _surfacegrid_ascii_text_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _surfacegrid_terminal_block_key_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _surfacegrid_ascii_terminal_block_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# format_surfacegrid_snapshot_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# wm_salience_force_focus_entity_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_guess_inspected_entity_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# _wm_salience_ambiguous_entities_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# wm_salience_tick_v1 moved to cca8_working_memory.py (Working Memory refactor Phase 2).


# Live EnvObservation -> WorkingMap injection moved to cca8_working_memory.py (Phase 3).


# NavMap ctx integration, accepted-current, transition, and policy-outcome runtime
# moved to cca8_navmap_runtime.py; compatibility aliases are defined near the imports.



# EnvObservation ingestion and sparse WorldGraph writes moved to cca8_observation_runtime.py.


# WorkingMap Creative policy-candidate scoring moved to cca8_policy_runtime.py.


# print_env_loop_tag_legend_once moved to cca8_reporting.py.


# _quiet_solved_rest_tail_v1 moved to cca8_reporting.py.


# _print_cog_cycle_footer moved to cca8_reporting.py.


def configure_goat_foraging_04_eval_v1(world, drives, ctx: Ctx, env: HybridEnvironment) -> None:
    """Configure the contextual map-switch evaluation scenario (goat_foraging_04).

    Intent
    ------
    This helper prepares a repeatable evaluation run that pressures the WorkingMap↔Column
    read path without changing the core controller. The scenario keeps coarse geometry mostly
    fixed while alternating context cues (fox vs hawk), so retrieval must rely on stored
    MapSurface context rather than gross topology alone.

    What this sets
    --------------
    - env scenario: ``goat_foraging_04``
    - Phase VII memory pipeline: enabled via apply_hardwired_profile_phase7(...)
    - keyframe trigger emphasis: milestone-driven rather than stage/zone-driven
    - episode bookkeeping: force the next env-loop tick to call env.reset(...)
    """
    if ctx is None or env is None:
        return

    try:
        apply_hardwired_profile_phase7(ctx, world)
    except Exception:
        pass

    # This evaluation wants milestone-forced keyframes under a constant stage/zone.
    try:
        ctx.longterm_obs_keyframe_on_stage_change = False
        ctx.longterm_obs_keyframe_on_zone_change = False
        ctx.longterm_obs_keyframe_on_milestone = True
    except Exception:
        pass

    # Conservative retrieve knobs.
    try:
        ctx.wm_mapsurface_autoretrieve_enabled = True
        ctx.wm_mapsurface_autoretrieve_mode = "merge"
        ctx.wm_mapsurface_autoretrieve_top_k = 5
        ctx.wm_mapsurface_autoretrieve_verbose = True
    except Exception:
        pass

    try:
        env.config = EnvConfig(scenario_name="goat_foraging_04", dt=getattr(env.config, "dt", 1.0))
    except Exception:
        try:
            env.config.scenario_name = "goat_foraging_04"
        except Exception:
            pass

    try:
        ctx.env_episode_started = False
        ctx.env_last_action = None
        ctx.env_pending_observation = None
        ctx.env_pending_info = {}
        ctx.env_pending_reward = 0.0
        ctx.env_pending_done = False
        ctx.env_pending_previous_state = None
        ctx.navmap_pending_action_v1 = None
        ctx.navmap_pending_reward_v1 = 0.0
    except Exception:
        pass

    # Keep drives mild so the controller mostly behaves as a permissive background process.
    try:
        drives.hunger = 0.30
        drives.fatigue = 0.20
        drives.warmth = 0.60
    except Exception:
        pass

    # Fresh WorkingMap is helpful for readability; the long-term WorldGraph is intentionally preserved.
    try:
        reset_working_world(ctx)
    except Exception:
        pass

    try:
        ctx.wm_goat04_seeded_contexts.clear()
        ctx.wm_goat04_seed_engram_by_context.clear()
        ctx.goat04_control_context = None
        ctx.goat04_control_source = None
        ctx.goat04_control_until_step = -1
        ctx.wm_mapswitch_last_events = []
    except Exception:
        pass

    # Clear prior run-compression state and recent auto-retrieve note.
    try:
        ctx.run_open = False
        ctx.run_policy = None
        ctx.run_action_bid = None
        ctx.run_len = 0
        ctx.run_start_env_step = None
        ctx.run_last_env_step = None
        ctx.wm_mapsurface_last_autoretrieve_engram_id = None
        ctx.wm_mapsurface_last_autoretrieve_reason = None
    except Exception:
        pass


#pylint: disable-next=too-many-positional-arguments
def run_env_closed_loop_steps(env, world, drives, ctx, policy_rt, n_steps: int, *, teaching_mode: bool = False) -> None:
    """
    Run N closed-loop cognitive cycles between the environment and CCA8.

    Canonical cycle contract
    ------------------------
    ``CognitiveCycle_n`` consumes ``Observation_n``, performs the current
    sensory/map/policy processing, produces ``Action_n`` (or an explicit null
    action), and dispatches that output before the cycle closes. The environment
    transition returns ``Observation_(n+1)``, which is buffered at the I/O seam
    and is not cognitively processed until ``CognitiveCycle_(n+1)``.

    Each cycle therefore:
      - advances the explicit controller-step count (no autonomic tick here),
      - consumes env.reset() output once or the observation buffered by the prior cycle,
      - injects that EnvObservation into the current CCA8 sensory/map path,
      - runs one controller step via PolicyRuntime.consider_and_maybe_fire(...),
      - dispatches the selected task-level output with env.apply_action(...), and
      - buffers the resulting later observation for the next cognitive cycle.

    This version also prints short explanation lines for:
      - posture (why we are fallen / standing / latched / resting),
      - nipple_state (hidden → reachable → latched → resting),
      - zone (why we are 'unknown' vs 'unsafe_cliff_near' vs 'safe').
    """


    def _coarse_zone_from_env(state) -> str | None:
        """Approximate the BodyMap's zone from EnvState distances.

        This mirrors cca8_controller.body_space_zone:

          - 'unsafe_cliff_near' if cliff is 'near' and shelter is not 'near'.
          - 'safe' if shelter is 'near' and cliff is not 'near'.
          - 'unknown' otherwise (including None / inconsistent / partial info).
        """
        if state is None:
            return None
        try:
            cliff = getattr(state, "cliff_distance", None)
            shelter = getattr(state, "shelter_distance", None)
        except Exception:
            return None

        if cliff is None and shelter is None:
            return "unknown"
        if cliff == "near" and shelter != "near":
            return "unsafe_cliff_near"
        if shelter == "near" and cliff != "near":
            return "safe"
        return "unknown"

    # phase7 is one of the s/w devp't phases, need some scaffolding to converted memory pipeline to
    #    sensory input -> recognition -> inject into Working Mem,BodyMap -> details to Work Mem -> consolidate to WorldGraph

    def _phase7_enabled() -> bool:
        return bool(getattr(ctx, "phase7_run_compress", False))


    def _phase7_dbg(msg: str) -> None:
        if bool(getattr(ctx, "phase7_run_verbose", False)):
            try:
                print(msg)
            except Exception:
                pass


    def _phase7_pick_state_bid(token_to_bid: dict) -> str | None:
        """Pick a representative 'state' binding id for run start/end edges.

        Preference order:
          1) resting (stable episode marker)
          2) posture:standing / posture:fallen
          3) nipple:latched / milk:drinking (feeding milestones)
          4) any last-seen token bid as a fallback
        """
        if not isinstance(token_to_bid, dict):
            return None
        for tok in ("resting", "posture:standing", "posture:fallen", "nipple:latched", "milk:drinking"):
            bid = token_to_bid.get(tok)
            if isinstance(bid, str):
                return bid
        try:
            vals = list(token_to_bid.values())
            for bid in reversed(vals):
                if isinstance(bid, str):
                    return bid
        except Exception:
            pass
        return None


    def _phase7_close_run(long_world, *, reason: str) -> None:
        """Close the currently-open run (if any) and clear ctx run state."""
        if ctx is None or not _phase7_enabled():
            return
        if not bool(getattr(ctx, "run_open", False)):
            return

        run_bid = getattr(ctx, "run_action_bid", None)
        if isinstance(run_bid, str):
            try:
                b = long_world._bindings.get(run_bid)
                if b is not None and isinstance(getattr(b, "meta", None), dict):
                    b.meta["run_open"] = False
                    b.meta["run_closed_reason"] = reason
            except Exception:
                pass

        # Clear ctx run state
        try:
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
        except Exception:
            pass

        _phase7_dbg(f"[phase7-run] close reason={reason}")


    def _phase7_update_open_run_end(long_world, state_bid: str | None, *, env_step: int | None) -> None:
        """Update the open run's end-state edge to point at `state_bid` (one edge, overwritten)."""
        if ctx is None or not _phase7_enabled():
            return
        if not bool(getattr(ctx, "run_open", False)):
            return

        run_bid = getattr(ctx, "run_action_bid", None)
        if not (isinstance(run_bid, str) and isinstance(state_bid, str)):
            return

        # Identify prior end bid (stored in run.meta)
        old_end = None
        try:
            b = long_world._bindings.get(run_bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                old_end = b.meta.get("run_end_bid")
        except Exception:
            old_end = None

        # Remove old end-edge if it existed and changed
        if isinstance(old_end, str) and old_end != state_bid:
            try:
                long_world.delete_edge(run_bid, old_end, label=None)
            except Exception:
                pass

        # Add/update current end-edge (avoid duplicates)
        try:
            need_edge = True
            b = long_world._bindings.get(run_bid)
            if b is not None:
                for e in getattr(b, "edges", []) or []:
                    if isinstance(e, dict) and e.get("to") == state_bid:
                        need_edge = False
                        break
            if need_edge:
                long_world.add_edge(run_bid, state_bid, "then", meta={"phase7": "run_end", "env_step": env_step})
        except Exception:
            pass

        # Update meta
        try:
            b = long_world._bindings.get(run_bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                b.meta["run_end_bid"] = state_bid
                b.meta["run_last_env_step"] = env_step
                b.meta["run_open"] = True
        except Exception:
            pass


    def _phase7_start_or_extend_run(long_world, state_bid: str | None, policy: str | None, *, env_step: int | None) -> None:
        """Start a new run node (action) or extend the existing run if the policy repeats."""
        if ctx is None or not _phase7_enabled():
            return
        if not (isinstance(policy, str) and policy.startswith("policy:")):
            return
        if not isinstance(state_bid, str):
            return

        # Extend in-place when policy repeats and run is still open
        if bool(getattr(ctx, "run_open", False)) and getattr(ctx, "run_policy", None) == policy:
            try:
                ctx.run_len = int(getattr(ctx, "run_len", 0) or 0) + 1
            except Exception:
                ctx.run_len = 1
            ctx.run_last_env_step = env_step

            run_bid = getattr(ctx, "run_action_bid", None)
            if isinstance(run_bid, str):
                try:
                    b = long_world._bindings.get(run_bid)
                    if b is not None and isinstance(getattr(b, "meta", None), dict):
                        b.meta["run_len"] = int(getattr(ctx, "run_len", 1))
                        b.meta["run_last_env_step"] = env_step
                        b.meta["run_open"] = True
                except Exception:
                    pass

            _phase7_dbg(f"[phase7-run] extend {policy} len={int(getattr(ctx, 'run_len', 1))}")
            return

        # Otherwise, close the previous run (if any) and start a new one
        if bool(getattr(ctx, "run_open", False)):
            _phase7_close_run(long_world, reason="policy_change")

        token = policy.split(":", 1)[1]
        meta = {
            "phase7": "run_start",
            "policy": policy,
            "run_open": True,
            "run_len": 1,
            "run_start_env_step": env_step,
            "run_last_env_step": env_step,
        }

        try:
            run_bid = long_world.add_action(token, attach="none", meta=meta)
        except Exception:
            return

        # Connect state → run (stable episode locality)
        try:
            long_world.add_edge(state_bid, run_bid, "then", meta={"phase7": "run_start", "policy": policy, "env_step": env_step})
        except Exception:
            pass

        try:
            ctx.run_open = True
            ctx.run_policy = policy
            ctx.run_action_bid = run_bid
            ctx.run_len = 1
            ctx.run_start_env_step = env_step
            ctx.run_last_env_step = env_step
        except Exception:
            pass

        _phase7_dbg(f"[phase7-run] start {policy} run_bid={run_bid} from={state_bid} env_step={env_step}")


    def _phase7_reset_run_state() -> None:
        """Clear ctx run state (used on env.reset())."""
        if ctx is None:
            return
        try:
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
        except Exception:
            pass


    def _explain_zone_change(prev_state, curr_state, zone: str | None, ctx) -> str | None: #pylint: disable=unused-argument
        """Human-readable explanation for why the coarse zone is what it is this step."""
        if zone is None:
            return None

        # Try to reconstruct the previous zone from EnvState distances.
        prev_zone = _coarse_zone_from_env(prev_state)

        # 'unknown' zone: either BodyMap is stale or geometry is ambiguous/incomplete.
        if zone == "unknown":
            stale = False
            try:
                if ctx is None or bodymap_is_stale(ctx):
                    stale = True
            except Exception:
                # If anything goes wrong, just treat as possibly stale.
                stale = False

            if stale:
                return (
                    "zone is 'unknown' because the BodyMap is stale or unavailable; "
                    "we do not yet trust shelter/cliff slots for spatial gating."
                )
            if prev_zone and prev_zone != "unknown":
                return (
                    f"zone changed {prev_zone!r}→'unknown'; cliff/shelter geometry is now in a "
                    "combination we do not classify (e.g., both near) or partially known, so "
                    "we treat it conservatively."
                )
            return (
                "zone is 'unknown'; either the environment has not yet established clear "
                "cliff/shelter distances or they are in a combination we do not classify, "
                "so gates treat it conservatively."
            )

        # Unsafe near a cliff.
        if zone == "unsafe_cliff_near":
            if prev_zone and prev_zone != zone:
                return (
                    f"zone changed {prev_zone!r}→'unsafe_cliff_near'; BodyMap now sees the cliff "
                    "near while shelter is not near, so this geometry is treated as unsafe for "
                    "resting."
                )
            return (
                "zone is 'unsafe_cliff_near'; BodyMap sees a nearby cliff but no nearby shelter, "
                "so resting policies are gated off in this configuration."
            )

        # Safe in a sheltered niche.
        if zone == "safe":
            if prev_zone and prev_zone != zone:
                return (
                    f"zone changed {prev_zone!r}→'safe'; cliff is no longer near and shelter is "
                    "near, so the kid is now in a sheltered niche where resting/feeding are "
                    "allowed."
                )
            return (
                "zone is 'safe'; BodyMap sees shelter near and no nearby cliff, so this is a "
                "sheltered niche suitable for resting and feeding."
            )

        # Any other zone label (future extensions).
        if prev_zone and prev_zone != zone:
            return (
                f"zone changed {prev_zone!r}→{zone!r}; this label is not yet given a detailed "
                "explanation in the newborn-goat storyboard."
            )
        return f"zone is {zone!r}; this label currently has no more detailed explanation."


    def _explain_nipple_change(prev_state, curr_state, action_for_env: str | None) -> str | None:
        """Human-readable explanation for why nipple_state is what it is this step."""
        if curr_state is None:
            return None

        n = curr_state.nipple_state
        s = curr_state.scenario_stage

        if prev_state is None:
            # First tick after reset: describe the starting feeding milestone.
            if n == "hidden":
                return (
                    "initial storyboard setup: nipple_state='hidden' in stage "
                    f"{s!r}; the kid has not yet found or reached the nipple."
                )
            return (
                f"initial storyboard setup: nipple_state={n!r} in stage={s!r} "
                "(start-of-episode feeding configuration)."
            )

        prev_n = prev_state.nipple_state
        prev_s = prev_state.scenario_stage

        # No nipple_state change this tick
        if n == prev_n:
            if n == "hidden":
                return (
                    "nipple remains hidden; the storyboard has not yet made it "
                    "reachable (or visible) to the kid in this stage."
                )
            if n in ("visible", "reachable"):
                return (
                    f"nipple_state remains {n!r}; the nipple is available but "
                    "has not yet latched this step."
                )
            if n == "latched":
                if prev_s != s and s == "rest":
                    return (
                        "stage advanced from 'first_latch' to 'rest' while the "
                        "nipple remains latched; the kid is effectively resting "
                        "with ongoing access to milk."
                    )
                return (
                    "nipple remains latched; the kid continues feeding at the "
                    "maternal nipple this step."
                )
            return (
                f"nipple_state remains {n!r}; no storyboard transition affecting "
                "feeding milestones this step."
            )

        # Nipple milestone changed this tick
        if prev_n in ("hidden", "visible") and n == "reachable":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple changed hidden→reachable, helped by a seek_nipple "
                    "action; the kid has oriented enough that the nipple is now "
                    "within reach."
                )
            return (
                "nipple changed hidden→reachable as the storyboard crossed its "
                f"\"nipple reachable\" threshold in stage {s!r}."
            )

        if prev_n in ("hidden", "visible") and n == "latched":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple jumped hidden→latched under seek_nipple; the kid "
                    "found and latched onto the nipple in one scripted step."
                )
            return (
                "nipple jumped hidden→latched directly by storyboard timing; "
                "this compresses 'found' and 'latched' into a single episode step."
            )

        if prev_n == "reachable" and n == "latched":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple changed reachable→latched under seek_nipple; the kid "
                    "successfully latched after having the nipple within reach."
                )
            return (
                "nipple changed reachable→latched as the storyboard hit its "
                "\"auto latch\" threshold; milk:drinking now begins."
            )

        # Any other transition (rare in the newborn storyboard)
        return (
            f"nipple_state changed {prev_n!r}→{n!r} as the storyboard moved "
            f"{prev_s!r}→{s!r} this step."
        )


    def _explain_posture_change(prev_state, curr_state, action_for_env: str | None) -> str | None:
        """Human-readable explanation for why posture is what it is this step."""
        if curr_state is None:
            return None

        p = curr_state.kid_posture
        s = curr_state.scenario_stage

        if prev_state is None:
            # First tick after reset: just describe the initial storyboard setup.
            return (
                f"initial storyboard setup: stage={s!r} starts with posture={p!r} "
                "(newborn begins life on the ground)."
            )

        prev_p = prev_state.kid_posture
        prev_s = prev_state.scenario_stage

        # No posture change this tick
        if p == prev_p:
            if p == "fallen":
                if action_for_env == "policy:stand_up":
                    return (
                        "stand_up was requested this tick, but the newborn is still "
                        f"kept fallen by the storyboard (stage={s!r}); standing will "
                        "only appear once the stand-up transition threshold is reached."
                    )
                return (
                    f"storyboard keeps the kid posture={p!r} in stage={s!r}; no successful "
                    "standing transition yet."
                )
            return f"posture remains {p!r}; no storyboard transition affecting posture this step."

        # Posture changed
        if prev_p == "fallen" and p == "standing":
            if action_for_env == "policy:stand_up":
                return (
                    "stand_up action applied by the environment: posture changed "
                    f"fallen→standing as the storyboard moved {prev_s!r}→{s!r}."
                )
            return (
                f"storyboard crossed its stand-up threshold: posture changed "
                f"fallen→standing as stage moved {prev_s!r}→{s!r}."
            )

        if prev_p == "standing" and p == "latched":
            return (
                "nipple became reachable and then latched in the storyboard; "
                "the kid switches from upright to 'latched' while feeding."
            )

        if prev_p == "latched" and p == "resting":
            return (
                "after some time latched and feeding, the storyboard advanced to 'rest'; "
                "the kid is now resting curled up against mom in a sheltered niche."
            )

        # Fallback for any other transitions.
        return (
            f"posture changed {prev_p!r}→{p!r} as the storyboard moved "
            f"{prev_s!r}→{s!r} this step."
        )

    if n_steps <= 0:
        print("[env-loop] N must be ≥ 1; nothing to do.")
        return
    if teaching_mode:
        print()
        print(menu37_teaching_intro_v1())
        print("\n".join(render_navmap_scope_legend_lines_v1()))
        print()

    print_env_loop_tag_legend_once(ctx)
    print(f"[env-loop] Running {n_steps} closed-loop cognitive cycle(s) (env↔controller).")
    print("[env-loop] Each cognitive cycle will:")
    print("  1) Advance controller_steps for this Action Center invocation,")
    print("  2) Consume one current EnvObservation (reset output or the prior transition's result),")
    print("  3) Process that observation through BodyMap / WNM / memory / policy selection,")
    print("  4) Produce and dispatch this cycle's action, including an explicit null action, and")
    print("  5) Buffer the resulting later observation for the next cognitive cycle.\n")

    if not getattr(ctx, "env_episode_started", False):
        print("[env-loop] Note: this episode has not started yet; the first cognitive cycle will call env.reset().")
        print("[env-loop]       (With HAL ON, this is where we'd sample the first real sensor snapshot.)")

    # Start each env-loop run with a clean SG display cache so the first map
    # of the run is shown in full once, and later identical maps can collapse
    # to the short unchanged marker.
    try:
        ctx.wm_surfacegrid_last_printed_ascii = None
        ctx.wm_surfacegrid_last_printed_block = None
    except Exception:
        pass

    for i in range(n_steps):
        print(f"\n[env-loop] Cognitive Cycle {i+1}/{n_steps}")
        if teaching_mode:
            print(menu37_teaching_cycle_header_v1(i + 1, n_steps))
            print()
        # Per-cycle capture for the footer summary (reset each cycle).
        fired_txt = None
        inj = None
        col_store_txt = None
        col_retrieve_txt = None
        col_apply_txt = None
        try:
            ctx.wm_mapswitch_last_events = []
        except Exception:
            pass

        # Count one CLOSED-LOOP cognitive cycle (env↔controller iteration).
        try:
            ctx.cog_cycles = getattr(ctx, "cog_cycles", 0) + 1
        except Exception:
            pass

        # 1) Explicit ordering for this Action Center invocation.
        try:
            ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
        except Exception:
            pass

        prev_state = None
        input_state = None
        input_from_reset = False
        prior_action_for_input: str | None = None
        input_reward = 0.0

        # 2) Consume exactly one current observation.
        #
        # The first cycle consumes env.reset() output. Later cycles consume the
        # observation produced and buffered when the preceding cognitive cycle
        # dispatched its own output. No environment action is applied here.
        if not getattr(ctx, "env_episode_started", False):
            env_obs, env_info = env.reset()
            input_from_reset = True
            _phase7_reset_run_state()  # phase7 s/w devpt: clear any previous run state on env reset
            ctx.env_episode_started = True
            ctx.env_last_action = None
            ctx.env_pending_observation = None
            ctx.env_pending_info = {}
            ctx.env_pending_reward = 0.0
            ctx.env_pending_done = False
            ctx.env_pending_previous_state = None
            ctx.navmap_pending_action_v1 = None
            ctx.navmap_pending_reward_v1 = 0.0
            ctx.navmap_last_payload_v1 = None
            ctx.navmap_last_expected_current_payload_v1 = None
            ctx.navmap_last_expected_current_comparison_v1 = None
            ctx.navmap_last_accepted_current_v1 = None
            feeding_reset_v1(ctx)
            terrain_reset_v1(ctx)
            live_dynamics_reset_v1(ctx)
            navmap_memory_reset_episode_v1(ctx)
            step_idx = env_info.get("step_index", 0)
            print(
                f"[env] Reset env scenario: "
                f"episode_index={env_info.get('episode_index')} "
                f"scenario={env_info.get('scenario_name')}"
            )
        else:
            prior_raw = getattr(ctx, "env_last_action", None)
            prior_action_for_input = prior_raw if isinstance(prior_raw, str) and prior_raw else None
            prev_state = getattr(ctx, "env_pending_previous_state", None)

            pending_obs = getattr(ctx, "env_pending_observation", None)
            pending_info = getattr(ctx, "env_pending_info", None)
            if pending_obs is not None:
                env_obs = pending_obs
                env_info = dict(pending_info) if isinstance(pending_info, dict) else {}
            else:
                # Compatibility fallback for a context created before the
                # explicit transition buffer existed, or manually reset by a test.
                env_obs = env.observe(ctx=ctx)
                env_info = {
                    "episode_index": getattr(env, "episode_index", None),
                    "step_index": getattr(env, "episode_steps", None),
                }

            try:
                input_reward = float(getattr(ctx, "env_pending_reward", 0.0) or 0.0)
            except (TypeError, ValueError):
                input_reward = 0.0

            ctx.env_pending_observation = None
            ctx.env_pending_info = {}
            ctx.env_pending_reward = 0.0
            ctx.env_pending_done = False
            ctx.env_pending_previous_state = None

            ctx.navmap_pending_action_v1 = prior_action_for_input
            ctx.navmap_pending_reward_v1 = input_reward
            step_idx = env_info.get("step_index")

        try:
            input_state = env.state.copy()
        except Exception:
            input_state = getattr(env, "state", None)

        if not input_from_reset:
            st = input_state
            ctx_txt = ""
            try:
                c_label = getattr(st, "context_label", None)
                if isinstance(c_label, str) and c_label:
                    ctx_txt = f" context={c_label}"
            except Exception:
                ctx_txt = ""
            print(
                f"[env] input env_step={step_idx} (since reset) "
                f"stage={getattr(st, 'scenario_stage', None)} posture={getattr(st, 'kid_posture', None)} "
                f"mom_distance={getattr(st, 'mom_distance', None)} "
                f"nipple_state={getattr(st, 'nipple_state', None)}{ctx_txt} "
                f"prior_action={prior_action_for_input!r}"
            )

        # --- Prediction error v1 record + legacy v0 vector (display/log only) ---
        # Compare last cycle's predicted postcondition (hypothesis) vs this cycle's observed env posture.
        # The rich record stays JSON-safe in ctx.prediction_last_error_record; pred_err_v0_last remains
        # the compatibility vector used by existing retrieval/keyframe/state-integrity code.
        pred_posture: str | None = None
        obs_posture: str | None = None
        err_vec: dict[str, int] = {}
        src_txt = "(n/a)"

        try:
            feedback_step = prediction_feedback_step_from_ctx_obs_v1(
                ctx,
                env_obs,
                env_step=step_idx if isinstance(step_idx, int) else None,
                limit=50,
            )
            err_vec = dict(feedback_step.get("err_vec", {}) or {})

            if feedback_step.get("has_prediction") is True:
                pred_raw = feedback_step.get("pred_posture")
                pred_posture = pred_raw if isinstance(pred_raw, str) and pred_raw else None
                obs_raw = feedback_step.get("obs_posture")
                obs_posture = obs_raw if isinstance(obs_raw, str) and obs_raw else None
                src = feedback_step.get("source_policy")
                src_txt = src if isinstance(src, str) and src else "(n/a)"
                matched = feedback_step.get("matched")

                print(
                    f"[pred_err] v1 err={err_vec} pred_posture={pred_posture} obs_posture={obs_posture} "
                    f"from={src_txt} matched={matched}"
                )
            else:
                err_vec = {}

        except Exception:
            # If anything goes wrong, keep the signal empty rather than crashing the env-loop.
            err_vec = {}
            ctx.pred_err_v0_last = {}
            ctx.prediction_last_error_record = {}

        # ----------------------------------------------------------------------------------
        # [pred_err] shaping penalty (extinction pressure when postconditions fail)
        #
        # Goal:
        #   If a policy repeatedly predicts a postcondition (v0: posture) and the next env
        #   observation contradicts it, apply a small negative reward shaping update to that
        #   policy's skill ledger entry.
        #
        # Design notes:
        #   - We ignore the very first mismatch after reset-like transitions by requiring
        #     a short mismatch streak (>=2) before applying the penalty.
        #   - We ALSO append a standardized entry into ctx.posture_discrepancy_history so
        #     existing non-drive tie-break logic (RecoverFall's discrepancy bonus) can use it
        #     during menu 37 (which otherwise doesn't build history via mini-snapshots).
        #
        # Knobs (optional; safe defaults if absent):
        #   ctx.pred_err_shaping_enabled : bool   (default True)
        #   ctx.pred_err_shaping_penalty : float  (default 0.15)
        # ----------------------------------------------------------------------------------
        try:
            shaping_enabled = bool(getattr(ctx, "pred_err_shaping_enabled", True))
        except Exception:
            shaping_enabled = True

        try:
            pen_mag = float(getattr(ctx, "pred_err_shaping_penalty", 0.15) or 0.15)
        except Exception:
            pen_mag = 0.15

        try:
            # v0 is posture-only today; treat any non-zero as a mismatch.
            v0_posture_err = 0
            if isinstance(err_vec, dict):
                try:
                    v0_posture_err = int(err_vec.get("posture", 0) or 0)
                except Exception:
                    v0_posture_err = 0

            if (    # pylint: disable=too-many-boolean-expressions
                shaping_enabled
                and v0_posture_err != 0
                and isinstance(prior_action_for_input, str)
                and prior_action_for_input
                and isinstance(obs_posture, str)
                and isinstance(pred_posture, str)
            ):
                # 1) Append a standardized discrepancy entry (so RecoverFall can see streaks in menu 37)
                entry = (
                    f"[discrepancy] env posture={obs_posture!r} "
                    f"vs policy-expected posture={pred_posture!r} from {prior_action_for_input}"
                )
                try:
                    hist = getattr(ctx, "posture_discrepancy_history", [])
                    if not isinstance(hist, list):
                        hist = []

                    # Important: we want repeated mismatches to accumulate so streak>=2 can trigger shaping.
                    hist.append(entry)
                    if len(hist) > 50:
                        del hist[:-50]

                    ctx.posture_discrepancy_history = hist
                except Exception:
                    pass

                # 2) Compute a short mismatch streak over the newest entries
                streak = 0
                try:
                    hist2 = getattr(ctx, "posture_discrepancy_history", [])
                    if isinstance(hist2, list) and hist2:
                        for h in reversed(hist2[-10:]):
                            s = str(h)
                            if (
                                (f"from {prior_action_for_input}" in s)
                                and ("env posture=" in s and obs_posture in s)
                                and ("policy-expected posture=" in s and pred_posture in s)
                            ):
                                streak += 1
                            else:
                                break
                except Exception:
                    streak = 0

                # 3) Apply shaping only after the streak threshold (ignore first mismatch)
                if streak >= 2:
                    shaping_reward = -abs(pen_mag) * float(v0_posture_err)
                    update_skill(prior_action_for_input, shaping_reward, ok=False, execution=False)
                    try:
                        q_now = float(skill_q(prior_action_for_input))
                    except Exception:
                        q_now = 0.0
                    print(
                        f"[pred_err] shaping: policy={prior_action_for_input} reward={shaping_reward:+.2f} "
                        f"(streak={streak}) q={q_now:+.2f}"
                    )
        except Exception:
            # Shaping must never crash the env-loop.
            pass

        # 3) EnvObservation → WorldGraph + BodyMap
        # Benchmark-only stressors modify the agent-visible observation packet,
        # not hidden environment truth.
        try:
            env_obs = apply_newborn_experiment_stress_v1(ctx, env_obs)
        except Exception:
            pass

        obs_write = inject_obs_into_world(world, ctx, env_obs)
        if teaching_mode:
            print(menu37_teaching_after_observation_v1())
            print()

        # goat_foraging_04 contextual evaluation:
        #   - first fox milestone  -> store fox seed
        #   - first hawk milestone -> store hawk seed
        #   - later alternating milestones -> retrieve/apply
        #
        # In this latest runner there is no generic wm_auto_store block here anymore,
        # so we hook the evaluation directly into the live env→memory handoff.
        try:
            goat04_stage = None
            meta_goat = getattr(env_obs, "env_meta", None)
            meta_goat = meta_goat if isinstance(meta_goat, dict) else {}
            goat04_stage = meta_goat.get("scenario_stage")

            goat04_kf = bool(isinstance(obs_write, dict) and obs_write.get("keyframe"))
        except Exception:
            goat04_stage = None
            goat04_kf = False

        if goat04_stage == "goat_foraging_04_scan" and goat04_kf:
            try:
                goat04_ops = maybe_goat04_context_mapswitch_on_keyframe_v1(world, ctx, env_obs)
                if isinstance(goat04_ops, dict):
                    if isinstance(goat04_ops.get("store"), str):
                        col_store_txt = goat04_ops.get("store")
                    if isinstance(goat04_ops.get("retrieve"), str):
                        col_retrieve_txt = goat04_ops.get("retrieve")
                    if isinstance(goat04_ops.get("apply"), str):
                        col_apply_txt = goat04_ops.get("apply")
            except Exception as e:
                print(f"[wm<->col] goat04 context mapswitch error: {e}")
                col_retrieve_txt = f"retrieve goat04 error:{e}"
                col_apply_txt = "apply no-op (error)"

        # newborn_long_horizon benchmark evaluation:
        #   - first stood_up / reached_mom / latched_nipple / rested milestones -> store seeds
        #   - later newborn keyframes -> retrieve/apply
        try:
            newborn_kf = bool(isinstance(obs_write, dict) and obs_write.get("keyframe"))
        except Exception:
            newborn_kf = False

        if bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)) and newborn_kf:
            try:
                newborn_ops = maybe_newborn_b2_mapswitch_on_keyframe_v1(world, ctx, env_obs)
                if isinstance(newborn_ops, dict):
                    if isinstance(newborn_ops.get("store"), str):
                        col_store_txt = newborn_ops.get("store")
                    if isinstance(newborn_ops.get("retrieve"), str):
                        col_retrieve_txt = newborn_ops.get("retrieve")
                    if isinstance(newborn_ops.get("apply"), str):
                        col_apply_txt = newborn_ops.get("apply")
            except Exception as e:
                print(f"[wm<->col] newborn B2 mapswitch error: {e}")
                col_retrieve_txt = f"retrieve newborn_b2 error:{e}"
                col_apply_txt = "apply no-op (error)"

        # goat04 retrieval → control bridge:
        # update a short-lived context hint after any goat04 mapswitch event so the
        # controller can express contextual switching rather than only logging retrieval.
        try:
            goat04_hint_info = _goat04_update_control_hint_v1(ctx)
            if bool(goat04_hint_info.get("updated")):
                active = goat04_hint_info.get("active")
                if isinstance(active, str) and active:
                    print(
                        f"[goat04] control_hint context={active} source={goat04_hint_info.get('source')} "
                        f"until_step={goat04_hint_info.get('until_step')}"
                    )
                else:
                    print("[goat04] control_hint cleared")
        except Exception:
            pass

        try:
            if getattr(ctx, "wm_surfacegrid_enabled", False):
                print(format_surfacegrid_snapshot_v1(ctx))
        except Exception:
            pass

        # 4) Controller response
        exec_world = None
        policy_name = None
        legacy_standup_gate_triggered: Optional[bool] = None
        legacy_followmom_gate_triggered: Optional[bool] = None
        legacy_followmom_effective_candidate: Optional[bool] = None
        active_followmom_effective_candidate: Optional[bool] = None

        try:
            policy_rt.refresh_loaded(ctx)

            if bool(getattr(ctx, "phase7_working_first", False)):
                if getattr(ctx, "working_world", None) is None:
                    ctx.working_world = init_working_world()
                exec_world = ctx.working_world
            _wm_creative_update(policy_rt, world, drives, ctx, exec_world=exec_world)
            fired = policy_rt.consider_and_maybe_fire(world, drives, ctx, exec_world=exec_world)

            # PolicyRuntime exposes both the historical FollowMom gate/candidate
            # and the active Phase 4F gate/candidate. Phase 4D continues to record
            # the historical values so its differential remains meaningful after
            # default authority promotion.
            policy_debug = getattr(ctx, "experiment_policy_debug_last", None)
            matches_initial = policy_debug.get("matches_initial") if isinstance(policy_debug, dict) else None
            legacy_followmom_gate_value = (
                policy_debug.get("followmom_legacy_gate_triggered")
                if isinstance(policy_debug, dict)
                else None
            )
            if isinstance(legacy_followmom_gate_value, bool):
                legacy_followmom_gate_triggered = legacy_followmom_gate_value
            elif isinstance(matches_initial, list):
                legacy_followmom_gate_triggered = "policy:follow_mom" in matches_initial
            matches_before_choice = (
                policy_debug.get("matches_before_choice")
                if isinstance(policy_debug, dict)
                else None
            )
            legacy_followmom_candidate_value = (
                policy_debug.get("followmom_legacy_effective_candidate")
                if isinstance(policy_debug, dict)
                else None
            )
            if isinstance(legacy_followmom_candidate_value, bool):
                legacy_followmom_effective_candidate = legacy_followmom_candidate_value
            elif isinstance(matches_before_choice, list):
                legacy_followmom_effective_candidate = "policy:follow_mom" in matches_before_choice
            active_followmom_candidate_value = (
                policy_debug.get("followmom_active_effective_candidate")
                if isinstance(policy_debug, dict)
                else None
            )
            if isinstance(active_followmom_candidate_value, bool):
                active_followmom_effective_candidate = active_followmom_candidate_value
            elif isinstance(matches_before_choice, list):
                active_followmom_effective_candidate = "policy:follow_mom" in matches_before_choice

            # PolicyRuntime records both the active trigger set and, in Phase
            # 3C/3D map-authority modes, the independent legacy trigger inside
            # the authority decision. Prefer the latter for the Phase 3A
            # differential so comparison remains truly legacy after promotion.
            guarded_summary = standup_authority_summary_v1(ctx)
            guarded_decision = guarded_summary.get("decision") if isinstance(guarded_summary, dict) else None
            legacy_from_guard = (
                guarded_decision.get("legacy_gate_triggered")
                if isinstance(guarded_decision, dict)
                else None
            )
            if isinstance(legacy_from_guard, bool):
                legacy_standup_gate_triggered = legacy_from_guard
            elif isinstance(matches_initial, list):
                legacy_standup_gate_triggered = "policy:stand_up" in matches_initial

            fired_txt = fired if isinstance(fired, str) else None

            if fired != "no_match":
                print(f"[env→controller] {fired}")

                # Extract the task-level output produced by this cognitive cycle.
                if isinstance(fired, str):
                    first_token = fired.split()[0]
                    if isinstance(first_token, str) and first_token.startswith("policy:"):
                        policy_name = first_token
        except Exception as e:
            print(f"[env→controller] controller step error: {e}")

        # Phase 4D FollowMom compare instrumentation. This post-selection call
        # records the original legacy gate, the effective post-filter candidate,
        # and the controller winner. It may arm an expected relation for later
        # evidence, but it cannot change the action already selected internally.
        followmom_compare_selection_updated = False
        try:
            followmom_compare_selection_step_v1(
                ctx,
                legacy_gate_triggered=legacy_followmom_gate_triggered,
                legacy_effective_candidate=legacy_followmom_effective_candidate,
                selected_policy=policy_name,
            )
            followmom_compare_selection_updated = True
        except Exception as exc:
            ctx.navmap_followmom_compare_last_update = {
                "schema": "followmom_compare_summary_v1",
                "phase": "4D",
                "status": "error",
                "authority": "compare_only",
                "follow_mom_authority": "legacy_bodymap_policy_runtime",
                "legacy_executes": True,
                "map_can_override": False,
                "map_can_trigger_follow_mom": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

        # Phase 4E-A refreshes non-binding advice after the real legacy candidate
        # set and winner are known. The selected policy before and after this call
        # is necessarily identical; protected filters remain outside map advice.
        if followmom_compare_selection_updated:
            try:
                followmom_advisory_selection_step_v1(ctx)
            except Exception as exc:
                ctx.navmap_followmom_advisory = None
                ctx.navmap_followmom_advisory_last_update = {
                    "schema": "followmom_advisory_summary_v1",
                    "phase": "4E-A",
                    "status": "error",
                    "authority": "advisory_only",
                    "follow_mom_authority": "legacy_bodymap_policy_runtime",
                    "legacy_executes": True,
                    "map_can_override": False,
                    "protected_safety_can_be_overridden": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        else:
            ctx.navmap_followmom_advisory = None
            ctx.navmap_followmom_advisory_last_update = {
                "schema": "followmom_advisory_summary_v1",
                "phase": "4E-A",
                "status": "dependency_error",
                "authority": "advisory_only",
                "follow_mom_authority": "legacy_bodymap_policy_runtime",
                "legacy_executes": True,
                "map_can_override": False,
                "protected_safety_can_be_overridden": False,
                "reason": "phase4d_compare_selection_update_failed",
            }

        # Phase 4E-B/4F finalizes the already-selected FollowMom authority
        # lifecycle. It records the actual global-arbitration winner and, when
        # map-authorized FollowMom was selected, arms the existing compact
        # expected-versus-observed relation. This call cannot change the winner.
        if followmom_compare_selection_updated:
            try:
                followmom_authority_selection_step_v1(
                    ctx,
                    active_effective_candidate=active_followmom_effective_candidate,
                    selected_policy=policy_name,
                )
            except Exception as exc:
                mode = followmom_authority_mode_v1(ctx).value
                ctx.navmap_followmom_authority_last_update = {
                    "schema": "followmom_authority_summary_v1",
                    "phase": "4F" if mode == "default" else "4E-B",
                    "status": "error",
                    "authority": "default_followmom" if mode == "default" else "guarded_followmom",
                    "authority_mode": mode,
                    "default_authority_active": mode == "default",
                    "protected_safety_can_be_overridden": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        elif followmom_authority_mode_v1(ctx).value != "legacy":
            mode = followmom_authority_mode_v1(ctx).value
            ctx.navmap_followmom_authority_last_update = {
                "schema": "followmom_authority_summary_v1",
                "phase": "4F" if mode == "default" else "4E-B",
                "status": "dependency_error",
                "authority": "default_followmom" if mode == "default" else "guarded_followmom",
                "authority_mode": mode,
                "default_authority_active": mode == "default",
                "protected_safety_can_be_overridden": False,
                "reason": "phase4d_compare_selection_update_failed",
            }

        # Phase 5 observes the already-selected primitive. It may atomically
        # zoom the feeding-domain WNM and arm a compact map-native expectation
        # for SeekNipple/Suckle, but it cannot change the global winner.
        try:
            feeding_selection_step_v1(
                ctx,
                selected_policy=policy_name,
            )
        except Exception as exc:
            ctx.feeding_last_update_v1 = {
                "schema": "feeding_summary_v1",
                "phase": "5",
                "status": "error",
                "authority": "single_operative_wnm_feeding_domain",
                "single_operative_wnm": True,
                "protected_safety_can_be_overridden": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

        # Phase 3A/3B/3C/3D instrumentation. Phase 3A retains an independent
        # legacy differential, Phase 3B emits non-binding advice, and Phase 3C/3D
        # records which trigger source actually fed PolicyRuntime. None
        # of these post-selection calls may alter the selected winner.
        compare_selection_updated = False
        try:
            standup_compare_selection_step_v1(
                ctx,
                legacy_gate_triggered=legacy_standup_gate_triggered,
                selected_policy=policy_name,
            )
            compare_selection_updated = True
        except Exception as exc:
            ctx.navmap_standup_compare_last_update = {
                "schema": "standup_compare_summary_v1",
                "phase": "3A",
                "status": "error",
                "authority": "compare_only",
                "legacy_executes": True,
                "map_can_override": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

        if compare_selection_updated:
            try:
                standup_advisory_selection_step_v1(ctx)
            except Exception as exc:
                ctx.navmap_standup_advisory_last_update = {
                    "schema": "standup_advisory_summary_v1",
                    "phase": "3B",
                    "status": "error",
                    "authority": "advisory_only",
                    "legacy_executes": True,
                    "map_can_override": False,
                    "protected_safety_can_be_overridden": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

        try:
            standup_guarded_selection_step_v1(
                ctx,
                selected_policy=policy_name,
            )
        except Exception as exc:
            authority_mode = standup_authority_mode_v1(ctx)
            default_mode = authority_mode.value == "default"
            ctx.navmap_standup_guarded_last_update = {
                "schema": "standup_guarded_summary_v1",
                "phase": "3D" if default_mode else "3C",
                "status": "error",
                "authority": "default_standup" if default_mode else "guarded_standup",
                "authority_level": "default" if default_mode else "guarded",
                "authority_mode": authority_mode.value,
                "default_authority_active": default_mode,
                "feature_flag_enabled": authority_mode.value == "guarded",
                "protected_safety_can_be_overridden": False,
                "legacy_retired": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

        # --- Capture later-evidence prediction (Scratch postcondition), v1 record; v0 posture fields kept for compatibility ---
        try:
            ctx.pred_next_policy = policy_name if isinstance(policy_name, str) and policy_name else None
            ctx.pred_next_posture = None
            ctx.prediction_next_record = {}

            if isinstance(ctx.pred_next_policy, str):
                w_scan = exec_world if exec_world is not None else world
                pred_record = prediction_next_record_from_policy_posture_v1(
                    ctx,
                    w_scan,
                    ctx.pred_next_policy,
                    env_step=step_idx if isinstance(step_idx, int) else None,
                    source=prediction_source_for_execution_target_v1(ctx, world, exec_world=exec_world),
                )
                if pred_record:
                    expected_slots = pred_record.get("expected")
                    if isinstance(expected_slots, dict):
                        expected_posture = expected_slots.get("posture")
                        if isinstance(expected_posture, str) and expected_posture:
                            ctx.pred_next_posture = expected_posture
                    ctx.prediction_next_record = pred_record
        except Exception:
            try:
                ctx.prediction_next_record = {}
            except Exception:
                pass

        cycle_output_action = policy_name if isinstance(policy_name, str) and policy_name else None

        # Start/extend a task-level run for the output generated from this
        # current observation. This is internal expectation/progress bookkeeping,
        # so it is completed before the output crosses the lower-controller seam.
        if _phase7_enabled():
            token_to_bid = {}
            if isinstance(obs_write, dict):
                raw_map = obs_write.get("token_to_bid")
                if isinstance(raw_map, dict):
                    token_to_bid = raw_map

            state_bid = _phase7_pick_state_bid(token_to_bid)
            _phase7_start_or_extend_run(world, state_bid, cycle_output_action, env_step=step_idx)

        # 5) Dispatch this cognitive cycle's output before the cycle closes.
        #
        # ``None`` is an explicit null task-level output. The simulator still
        # advances one physical/environment transition so a later observation is
        # available, just as lower body/world dynamics continue when the animal
        # issues no new locomotor command.
        action_dispatched: str | None = None
        dispatch_succeeded = False
        output_env_step: int | None = None
        next_env_obs = None
        next_env_reward = 0.0
        next_env_done = False
        next_env_info: dict[str, Any] = {}

        try:
            next_env_obs, next_env_reward, next_env_done, next_env_info = env.apply_action(
                action=cycle_output_action,
                ctx=ctx,
            )
            dispatch_succeeded = True
            action_dispatched = cycle_output_action
            if isinstance(next_env_info, dict):
                next_step_raw = next_env_info.get("step_index")
                if isinstance(next_step_raw, int):
                    output_env_step = next_step_raw
        except Exception as exc:
            print(f"[controller→env] dispatch error: {type(exc).__name__}: {exc}")
            try:
                next_env_obs = env.observe(ctx=ctx)
                output_env_step = int(getattr(env, "episode_steps", 0) or 0)
                next_env_info = {
                    "episode_index": getattr(env, "episode_index", None),
                    "step_index": output_env_step,
                    "dispatch_error": type(exc).__name__,
                }
            except Exception:
                next_env_obs = None
                next_env_info = {"dispatch_error": type(exc).__name__}

        ctx.env_last_action = action_dispatched
        ctx.env_pending_observation = next_env_obs
        ctx.env_pending_info = dict(next_env_info) if isinstance(next_env_info, dict) else {}
        try:
            ctx.env_pending_reward = float(next_env_reward)
        except (TypeError, ValueError):
            ctx.env_pending_reward = 0.0
        ctx.env_pending_done = bool(next_env_done)
        try:
            ctx.env_pending_previous_state = input_state.copy() if input_state is not None else None
        except Exception:
            ctx.env_pending_previous_state = input_state

        # The pending action/reward describe the transition whose observation is
        # buffered above. NavMap runtime will consume and clear them only when that
        # later observation enters the next cognitive cycle.
        ctx.navmap_pending_action_v1 = action_dispatched
        ctx.navmap_pending_reward_v1 = ctx.env_pending_reward

        output_label = cycle_output_action if cycle_output_action is not None else "NO_ACTION"
        buffered_text = "buffered" if next_env_obs is not None else "unavailable"
        print(
            f"[controller→env] cycle_output={output_label!r} "
            f"dispatched_in_cognitive_cycle={getattr(ctx, 'cog_cycles', None)} "
            f"transition_env_step={output_env_step} next_observation={buffered_text}"
        )

        if teaching_mode:
            print(menu37_teaching_after_controller_v1())
            print()

        # Short summary for this step + posture/nipple/zone explanations
        try:
            st = input_state
            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None

            # Clarify: env_* is storyboard truth; bm_* is the agent’s current belief cache (BodyMap).
            try:
                stale = bodymap_is_stale(ctx)
            except Exception:
                stale = False

            try:
                bm_posture = body_posture(ctx) if not stale else None
            except Exception:
                bm_posture = None

            # Expected posture: Scratch postcondition written by the last executed policy (if any).
            expected_posture = None
            if isinstance(policy_name, str) and policy_name:
                for w in (getattr(ctx, "working_world", None), world):
                    if w is None:
                        continue
                    _bid, posture_tag, meta = _latest_posture_binding(w, require_policy=True)
                    if posture_tag and isinstance(meta, dict) and meta.get("policy") == policy_name:
                        expected_posture = posture_tag.split(":")[-1]
                        break

            line = (
                f"[env-loop] summary cognitive_cycle={i+1}/{n_steps} input_env_step={step_idx} stage={st.scenario_stage} "
                f"env_posture={st.kid_posture} bm_posture={bm_posture or st.kid_posture} "
                f"mom={st.mom_distance} nipple={st.nipple_state} cycle_output={cycle_output_action!r}"
            )
            if expected_posture is not None:
                line += f" expected_posture={expected_posture}"
            if zone is not None:
                line += f" zone={zone}"
            print(line)

            if expected_posture is not None and str(expected_posture) != str(st.kid_posture):
                print(
                    "[env-loop] note: expected_posture is a Scratch postcondition for later evidence; "
                    "the input env_posture remains the current cycle's observed truth."
                )

            quiet_rest_tail = _quiet_solved_rest_tail_v1(
                st,
                zone,
                prior_action_for_input,
                cycle_output_action,
            )

            if not quiet_rest_tail:
                # Explain why posture ended up as it is at this step.
                try:
                    posture_expl = _explain_posture_change(prev_state, st, prior_action_for_input)
                    if posture_expl:
                        print(f"[env-loop] explain posture: {posture_expl}")

                    if isinstance(getattr(st, "kid_posture", None), str) and st.kid_posture == "latched":
                        print(
                            "[env-loop] explain perception: in this early CCA8, the storyboard state "
                            "'latched' is represented perceptually as posture:standing + nipple:latched + milk:drinking."
                        )
                except Exception:
                    pass

                # Explain why nipple_state ended up as it is at this step.
                try:
                    nipple_expl = _explain_nipple_change(prev_state, st, prior_action_for_input)
                    if nipple_expl:
                        print(f"[env-loop] explain nipple: {nipple_expl}")
                except Exception:
                    pass

                # Explain why zone ended up as it is at this step.
                try:
                    zone_expl = _explain_zone_change(prev_state, st, zone, ctx)
                    if zone_expl:
                        print(f"[env-loop] explain zone: {zone_expl}")
                except Exception:
                    pass

            # End-of-cycle footer: compact digest for fast scanning (Phase IX).
            try:
                _print_cog_cycle_footer(
                    ctx=ctx,
                    drives=drives,
                    env_obs=env_obs,
                    prev_state=prev_state,
                    curr_state=st,
                    env_step=step_idx,
                    zone=zone,
                    inj=obs_write if isinstance(obs_write, dict) else None,
                    fired_txt=fired_txt if isinstance(fired_txt, str) else None,
                    col_store_txt=col_store_txt,
                    col_retrieve_txt=col_retrieve_txt,
                    col_apply_txt=col_apply_txt,
                    prior_action_for_input=prior_action_for_input,
                    cycle_output_action=cycle_output_action,
                    action_dispatched=action_dispatched,
                    dispatch_succeeded=dispatch_succeeded,
                    output_env_step=output_env_step,
                    next_observation_buffered=next_env_obs is not None,
                    cycle_no=i + 1,
                    cycle_total=n_steps,
                )
            except Exception:
                pass
        except Exception:
            pass

        # Cognitive storage oscilloscope: retain one bounded, read-only
        # architectural snapshot for every closed-loop cognitive cycle.
        try:
            cca8_cognitive_scope.capture_cognitive_scope_snapshot_v1(
                ctx,
                env=env,
                env_obs=env_obs,
                world=world,
                drives=drives,
                policy_rt=policy_rt,
                selected_policy=policy_name if isinstance(policy_name, str) else None,
                action_applied=action_dispatched if isinstance(action_dispatched, str) else None,
                env_step=step_idx if isinstance(step_idx, int) else None,
                external_state=input_state,
                prior_action_for_input=prior_action_for_input,
                dispatch_succeeded=dispatch_succeeded,
                output_env_step=output_env_step,
                capture_kind="cognitive_cycle",
            )
        except Exception as exc:
            logging.error("[cognitive_scope] capture failed: %s", exc, exc_info=True)

        # Per-cycle JSON record (Phase X scaffolding): replayable debug trace.
        # This is OFF by default; enable by setting ctx.cycle_json_enabled=True and (optionally)
        # ctx.cycle_json_path="cycle_log.jsonl".
        try:
            if bool(getattr(ctx, "cycle_json_enabled", False)):
                st = input_state
                try:
                    zone_now = body_space_zone(ctx)
                except Exception:
                    zone_now = None

                # Robustify a few fields so JSON dumping never surprises us.
                policy_fired_val = policy_name if isinstance(policy_name, str) else None

                efe_last = getattr(ctx, "efe_last", None)
                if not isinstance(efe_last, dict):
                    efe_last = {}

                efe_scores = getattr(ctx, "efe_last_scores", None)
                if not isinstance(efe_scores, list):
                    efe_scores = []

                navpatch_priors = getattr(ctx, "navpatch_last_priors", None)
                if not isinstance(navpatch_priors, dict):
                    navpatch_priors = {}

                llm_advice_summary = getattr(ctx, "experiment_last_llm_advice_summary", None)
                if not isinstance(llm_advice_summary, dict):
                    llm_advice_summary = {}

                rec = {
                    "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
                    "env_step": env_info.get("step_index") if isinstance(env_info, dict) else None,
                    "input_env_step": env_info.get("step_index") if isinstance(env_info, dict) else None,
                    "output_env_step": output_env_step,
                    "scenario_stage": getattr(st, "scenario_stage", None),
                    "posture": getattr(st, "kid_posture", None),
                    "mom_distance": getattr(st, "mom_distance", None),
                    "nipple_state": getattr(st, "nipple_state", None),
                    "zone": zone_now,
                    "prior_action_for_input": prior_action_for_input,
                    "cycle_output_action": cycle_output_action,
                    "action_dispatched": action_dispatched,
                    "dispatch_succeeded": dispatch_succeeded,
                    "next_observation_buffered": next_env_obs is not None,
                    # Compatibility alias retained for existing trace readers.
                    "action_applied": action_dispatched,
                    "policy_fired": policy_fired_val,
                    "policy_debug": dict(getattr(ctx, "experiment_policy_debug_last", {}) or {}),
                    "llm_advice_summary": dict(llm_advice_summary),
                    "obs": {
                        "predicates": list(getattr(env_obs, "predicates", []) or []),
                        "cues": list(getattr(env_obs, "cues", []) or []),
                        "nav_patches": list(getattr(env_obs, "nav_patches", []) or []),
                        "env_meta": dict(getattr(env_obs, "env_meta", {}) or {}),
                    },
                    "wg_wrote": {
                        "predicates": list((inj or {}).get("predicates", []) or []),
                        "cues": list((inj or {}).get("cues", []) or []),
                    },
                    "navpatch_matches": list(getattr(ctx, "navpatch_last_matches", []) or []),
                    "navpatch_priors": navpatch_priors,
                    "efe": efe_last,
                    "efe_scores": efe_scores,
                    "drives": {
                        "hunger": float(getattr(drives, "hunger", 0.0) or 0.0),
                        "fatigue": float(getattr(drives, "fatigue", 0.0) or 0.0),
                        "warmth": float(getattr(drives, "warmth", 0.0) or 0.0),
                    },
                    "pred_err_v0": dict(getattr(ctx, "pred_err_v0_last", {}) or {}),
                    "prediction_next_record": dict(getattr(ctx, "prediction_next_record", {}) or {}),
                    "prediction_last_error_record": dict(getattr(ctx, "prediction_last_error_record", {}) or {}),

                    # Back-compatible aliases for older trace readers.
                    "prediction_next": dict(getattr(ctx, "prediction_next_record", {}) or {}),
                    "prediction_error": dict(getattr(ctx, "prediction_last_error_record", {}) or {}),
                    "prediction_feedback": prediction_feedback_summary_v1(ctx),
                    "maternal_geometry_shadow": maternal_geometry_shadow_summary_v1(ctx),
                    "maternal_temporal_shadow": maternal_temporal_shadow_summary_v1(ctx),
                    "maternal_continuity_shadow": maternal_continuity_shadow_summary_v1(ctx),
                    "followmom_compare": followmom_compare_summary_v1(ctx),
                    "followmom_advisory": followmom_advisory_summary_v1(ctx),
                    "followmom_authority": followmom_authority_summary_v1(ctx),
                    "feeding": feeding_summary_v1(ctx),
                    "terrain": terrain_summary_v1(ctx),
                    "live_dynamics": live_dynamics_summary_v1(ctx),
                    "navmap_memory": navmap_memory_summary_v1(ctx),
                    "wnm": wnm_summary_v1(ctx),
                    "standup_advisory": standup_advisory_summary_v1(ctx),
                    "standup_authority": standup_authority_summary_v1(ctx),
                    "standup_guarded": standup_guarded_summary_v1(ctx),
                }
                try:
                    if getattr(st, "scenario_stage", None) == "goat_foraging_04_scan":
                        goat04_oracle = {
                            "true_context": getattr(st, "context_label", None),
                            "expected_policy": getattr(st, "goat04_oracle_expected_policy", None),
                            "switch_step": int(getattr(st, "goat04_oracle_switch_step", -1) or -1),
                            "response_deadline_step": int(
                                getattr(st, "goat04_oracle_response_deadline_step", -1) or -1
                            ),
                        }

                        sw = goat04_oracle["switch_step"]
                        dl = goat04_oracle["response_deadline_step"]
                        env_step_now = rec.get("env_step")

                        goat04_oracle["switch_event"] = bool(
                            isinstance(env_step_now, int) and sw >= 0 and env_step_now == sw
                        )
                        goat04_oracle["response_window_open"] = bool(
                            isinstance(env_step_now, int) and sw >= 0 and dl >= sw and sw <= env_step_now <= dl #pylint: disable=chained-comparison
                        )

                        rec["oracle"] = {"goat04": goat04_oracle}
                except Exception:
                    pass

                # --- Step 14.5: include WM salience in the per-cycle JSON record (trace hook) ---
                try:
                    wm = rec.get("wm")
                    if not isinstance(wm, dict):
                        wm = {}
                        rec["wm"] = wm

                    wm["salience"] = {
                        "focus_entities": list(getattr(ctx, "wm_salience_focus_entities", []) or []),
                        "events": list(getattr(ctx, "wm_salience_last_events", []) or []),
                    }

                    wm["navsummary"] = dict(getattr(ctx, "wm_navsummary", {}) or {})

                    #working_info = (inj or {}).get("working") if isinstance(inj, dict) else None
                    #working_info = working_info if isinstance(working_info, dict) else {}
                    working_raw: Any = (
                        (inj or {}).get("working") if isinstance(inj, dict) else None
                    )
                    working_info: dict[str, Any] = (
                        working_raw if isinstance(working_raw, dict) else {}
                    )

                    invalidation = working_info.get("mask_invalidation")
                    if not isinstance(invalidation, dict):
                        invalidation = dict(getattr(ctx, "wm_mask_invalidation_last", {}) or {})
                    wm["mask_invalidation"] = dict(invalidation)
                    wm["newborn_governed_state"] = _newborn_workingmap_state_v1(ctx)

                    # --- Step 15B: include WM zoom state/events (trace hook) ---
                    try:
                        z_state = getattr(ctx, "wm_zoom_state", "up")
                        z_state = str(z_state).strip().lower() if isinstance(z_state, str) else "up"
                        if z_state not in ("up", "down"):
                            z_state = "up"

                        keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
                        active_keys = sorted(list(keys)) if isinstance(keys, set) else []

                        wm["zoom"] = {
                            "state": z_state,
                            "active_keys": active_keys,
                            "events": list(getattr(ctx, "wm_zoom_last_events", []) or []),
                        }

                        wm["mapswitch"] = {"events": list(getattr(ctx, "wm_mapswitch_last_events", []) or [])}

                    except Exception:
                        pass
                except Exception:
                    pass

                append_cycle_json_record(ctx, rec)
        except Exception as e:
            logging.error("[cycle_json] record build/append failed: %s", e, exc_info=True)

    print(
        "\n[env-loop] Closed-loop cognitive cycle complete. "
        "Inspect the retained signal path with Main Menu #2 Cognitive Storage Oscilloscope."
    )
    if teaching_mode:
        print()
        print(menu37_teaching_after_run_v1())

    try:
        if getattr(ctx, "working_enabled", False):
            print()
            print_working_map_entity_table(ctx, title="[workingmap] MapSurface entity table")
            print()
            print_working_map_snapshot(ctx, n=250, title="[workingmap] auto snapshot (last 250)")
    except Exception:
        pass


# mini_snapshot_text moved to cca8_reporting.py.


# print_mini_snapshot moved to cca8_reporting.py.



# drives_and_tags_text moved to cca8_reporting.py.


# skill_ledger_text moved to cca8_reporting.py.


# skills_hud_text moved to cca8_reporting.py.


# _io_banner moved to cca8_reporting.py.


# ---------- Contextual base selection (skeleton) ----------
def _nearest_binding_with_pred(world, token: str, from_bid: str, max_hops: int = 3) -> str | None:
    """Return the first binding matching pred:<token> found by BFS from `from_bid` within `max_hops`."""
    want = token if token.startswith("pred:") else f"pred:{token}"
    # BFS with early exit that returns the first binding matching the predicate
    from collections import deque
    q, seen, depth = deque([from_bid]), {from_bid}, {from_bid: 0}
    while q:
        u = q.popleft()
        b = world._bindings.get(u)
        if b and any(t == want for t in getattr(b, "tags", [])):
            return u
        if depth[u] >= max_hops:
            continue
        edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
        if isinstance(edges, list):
            for e in edges:
                v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if v and v not in seen:
                    seen.add(v); depth[v] = depth[u] + 1; q.append(v)
    return None


def choose_contextual_base(world, ctx, targets: list[str] | None = None) -> dict: # pylint: disable=unused-argument
    """
    Skeleton: pick where a primitive *should* anchor writes.
    Order: nearest target predicate -> HERE (if exists) -> NOW.
    We only *suggest* the base here; controller may ignore it today.
    """
    targets = targets or ["posture:standing", "stand"]
    now_id  = _anchor_id(world, "NOW")
    here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
    # try each target nearest to NOW
    for tok in targets:
        bid = _nearest_binding_with_pred(world, tok, from_bid=now_id, max_hops=3)
        if bid:
            return {"base": "NEAREST_PRED", "pred": tok, "bid": bid}
    if here_id:
        return {"base": "HERE", "bid": here_id}
    return {"base": "NOW", "bid": now_id}


# ---------- FOA (Focus of Attention), NOW skeleton ----------
def present_cue_bids(world) -> list[str]:
    """Return binding ids that carry any `cue:*` tag (unordered)
    """
    bids = []
    for bid, b in world._bindings.items():
        ts = getattr(b, "tags", [])
        if any(isinstance(t, str) and t.startswith("cue:") for t in ts):
            bids.append(bid)
    return bids


def neighbors_k(world, start_bid: str, max_hops: int = 2) -> set[str]:
    """Return the set of nodes within `max_hops` hops of `start_bid` (inclusive).
    """
    from collections import deque
    out = set()
    q = deque([(start_bid, 0)])
    seen = {start_bid}
    while q:
        u, d = q.popleft()
        out.add(u)
        if d >= max_hops:
            continue
        b = world._bindings.get(u)
        edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
        if isinstance(edges, list):
            for e in edges:
                v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if v and v not in seen:
                    seen.add(v); q.append((v, d+1))
    return out


def compute_foa(world, ctx, max_hops: int = 2) -> dict: # pylint: disable=unused-argument
    """
    Skeleton FOA window: union of neighborhoods around LATEST and NOW, plus cue nodes.
    Later we can weight by drives/costs and restrict size aggressively.
    """
    now_id   = _anchor_id(world, "NOW")
    latest   = world._latest_binding_id
    seeds    = [x for x in [latest, now_id] if x]
    seeds   += present_cue_bids(world)
    # dedupe seeds while preserving original order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in seeds:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    seeds = uniq
    foa_ids  = set()
    for s in seeds:
        foa_ids |= neighbors_k(world, s, max_hops=max_hops)
    return {"seeds": seeds, "size": len(foa_ids), "ids": foa_ids}


def ensure_now_origin(world):
    """
    to set NOW_ORIGIN once
    """
    origin_id = _anchor_id(world, "NOW")
    if origin_id and origin_id != "?":
        # Set in anchors map if available
        if hasattr(world, "_anchors") and isinstance(world._anchors, dict):
            world._anchors["NOW_ORIGIN"] = origin_id
        # Also tag the binding
        b = world._bindings.get(origin_id)
        if b is not None:
            tags = getattr(b, "tags", None)
            if tags is None:
                b.tags = set()
                tags = b.tags
            # robust: handle set or list
            try:
                tags.add("anchor:NOW_ORIGIN")
            except AttributeError:
                if "anchor:NOW_ORIGIN" not in tags:
                    tags.append("anchor:NOW_ORIGIN")


# ---------- Multi-anchor candidates (skeleton) ----------
def candidate_anchors(world, ctx) -> list[str]:  # pylint: disable=unused-argument
    """
    Skeleton list of candidate start anchors for planning/search.
    Later we’ll run K parallel searches from these.
    """
    now_id   = _anchor_id(world, "NOW")
    here_id  = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
    picks    = [now_id]
    if here_id and here_id not in picks: picks.append(here_id)
    for tok in ("posture:standing", "stand", "mom:close"):
        bid = _nearest_binding_with_pred(world, tok, from_bid=now_id, max_hops=3)
        if bid and bid not in picks:
            picks.append(bid)
    return [p for p in picks if p]


# ---------- LLM API password, billing, mgmt ----------
# OpenAI/LLM configuration, API helpers, evaluation, and Menu 48 live in cca8_openai.py.



_sim_robot_goat_value_text_v1 = cca8_rcos_menu.sim_robot_goat_value_text_v1
_sim_robot_goat_obs_lines_v1 = cca8_rcos_menu.sim_robot_goat_obs_lines_v1
_sim_robot_goat_status_lines_v1 = cca8_rcos_menu.sim_robot_goat_status_lines_v1
_sim_robot_goat_ack_lines_v1 = cca8_rcos_menu.sim_robot_goat_ack_lines_v1
sim_robot_goat_menu_50_interactive = cca8_rcos_menu.sim_robot_goat_menu_50_interactive


# --------------------------------------------------------------------------------------
# Interactive loop
# --------------------------------------------------------------------------------------

def interactive_loop(args: argparse.Namespace) -> None:
    """Main interactive loop.
    """

    # Build initial world/drives fresh
    world = cca8_world_graph.WorldGraph()
    #drives = Drives()  #Drives(hunger=0.7, fatigue=0.2, warmth=0.6) at time of writing comment
    #drives.fatigue = 0.85 #for devp't testing --> Drives(hunger=0.7, fatigue=0.85, warmth=0.6)
    #drives = Drives(hunger=0.5, fatigue=0.9, warmth=0.6)  #for rest gate to see hazard versus shelter
    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)  # moderate fatigue so fallback 'follow_mom' can win

    ctx = Ctx(age_days=0.0, ticks=0)
    # Phase X (NavPatch) defaults: enable in the interactive runner.
    # Unit tests or external callers can keep this OFF unless they explicitly opt in.
    ctx.navpatch_enabled = True
    # Phase X: per-cycle JSON trace (JSONL) logging (optional)
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = "cycle_log.jsonl"   # set to None for in-memory only
    ctx.cycle_json_max_records = 2000         # ring buffer size

    ctx.efe_enabled = True
    ctx.efe_verbose = False  # keep noise low; the env-loop will still print one [efe] line per step
    ctx.efe_w_risk = 1.0
    ctx.efe_w_ambiguity = 1.0
    ctx.efe_w_preference = 1.0

    # Phase X ergonomics:
    # - keep the SurfaceGrid HUD visible in env-loop runs,
    # - but let the shared SG helper collapse identical maps to the short
    #   "unchanged" marker instead of forcing a full redraw every cycle.
    ctx.wm_surfacegrid_verbose = True
    ctx.wm_surfacegrid_ascii_each_tick = False

    env = HybridEnvironment()     # Environment simulation: newborn-goat scenario (HybridEnvironment)
    ctx.body_world, ctx.body_ids = init_body_world() # initialize tiny BodyMap (body_world) as a separate WorldGraph instance
    ctx.working_world = init_working_world()

    # Stage-1 RCOS sandbox handle (lazy-init from menu 50 so we do not touch normal CCA8 flows unless requested).
    sim_robot_goat_hal: Optional[SimRobotGoatHAL] = None

    # Architecture-v09.3 experimental runtime handle.  Keep this typed as Any so the normal legacy runner can start
    # without importing any nca8 module; the explicit Watch Cognition submenu constructs the session lazily.
    nca8_session: Optional[Any] = None

    POLICY_RT = PolicyRuntime(CATALOG_GATES)
    POLICY_RT.refresh_loaded(ctx)
    loaded_ok = False
    loaded_src = None

    # Main-menu presentation and deterministic routing live in cca8_cli.

    # Attempt to load a prior session if requested
    if args.load:
        try:
            with open(args.load, "r", encoding="utf-8") as f:
                blob = json.load(f)

            new_world  = cca8_world_graph.WorldGraph.from_dict(blob.get("world", {}))
            try:
                new_drives = Drives.from_dict(blob.get("drives", {}))
            except Exception as e:
                print(f"[warn] --load: invalid drives in {args.load}: {e}; using defaults.")
                new_drives = Drives()

            skills_from_dict(blob.get("skills", {}))
            world, drives = new_world, new_drives
            loaded_ok = True
            loaded_src = args.load

            print(f"Loaded {args.load} (saved_at={blob.get('saved_at','?')})")
            print("A previously saved simulation session is being continued here.\n")

        except FileNotFoundError:
            print(f"The file {args.load} could not be found. The simulation will run as a new one.\n")
        except json.JSONDecodeError as e:
            print(f"[warn] --load: invalid JSON in {args.load}: {e}")
            print("The simulation will run as a new one.\n")
        except (PermissionError, OSError) as e:
            print(f"[warn] --load: could not read {args.load}: {e}")
            print("The simulation will run as a new one.\n")
        except Exception as e:
            print(f"The file was found but there was a problem reading it: {args.load}: {e}")
            print("The simulation will run as a new one.\n")

    # Banner & profile selection
    if not args.no_intro:
        print_header(args.hal_status_str, args.body_status_str)
    if getattr(args, "rcos_api", False):
        name, k = profile_rcos_api(ctx)
    elif args.profile:
        if args.profile == "goat":
            name, k = _goat_defaults()
        elif args.profile == "chimp":
            name, k = profile_chimpanzee(ctx)
        elif args.profile == "human":
            name, k = profile_human(ctx)
        else:
            name, k = profile_superhuman(ctx)
    else:
        profile = choose_profile(ctx, world)
        name = profile["name"]
        k = profile["winners_k"]

    ctx.profile = name
    ctx.winners_k = k
    print(f"Profile set: {name} (k={k})")
    print("  k = reserved top-k winners knob (future WTA selection).\n")

    POLICY_RT.refresh_loaded(ctx)

    world.set_stage_from_ctx(ctx)        # derive 'neonate'/'infant' from ctx.age_days
    world.set_tag_policy("warn")         # or "strict" once you’re ready

    # HAL instantiation (although already set in class Ctx, but can modify here)
    ctx.hal  = None
    ctx.body = "(none)"
    if getattr(args, "hal", False):
        hal = HAL(args.body)
        ctx.hal  = hal  #store HAL on ctx so that other primitives can see it
        ctx.body = hal.body

    # Ensure NOW anchor exists for the episode (so attachments from "now" resolve)
    world.ensure_anchor("NOW")
    # Seed the newborn Mountain Goat's default stand-up intent.
    boot_prime_stand(world, ctx)
    # Pin NOW_ORIGIN to this initial NOW (episode root)
    ensure_now_origin(world)
    # Startup notices (print here so they appear as part of the session boot block).
    # This keeps the output grouped: [io] → [boot] → [planner]/[profile] → [preflight-lite].
    apply_hardwired_profile_phase7(ctx, world)
    #print_startup_notices(world)

    #run_preflight_lite_maybe()  # optional preflight-lite
    pretty_scroll = False       # compatibility-routing messages remain quiet by default
    main_menu_continue_pending = False

    # Interactive menu loop  >>>>>>>>>>>>>>>>>>>
    while True:
        try:
            if main_menu_continue_pending:
                if not cca8_cli.wait_for_main_menu_continue_v1():
                    print("\nGoodbye.")
                    return
                main_menu_continue_pending = False
                print()

            print(f"\n{cca8_cli.MAIN_MENU_HEADER}")
            choice = input(cca8_cli.MAIN_MENU_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return


        ckey = choice.strip().lower()
        alias_route_message: str | None = None

        # If it's not a pure number, try word/prefix routing first.
        if not ckey.isdigit():
            # A successful route returns a displayed menu number; ambiguous prefixes return candidate aliases.
            routed, matches = cca8_cli.route_menu_alias(ckey)
            if routed is not None:
                if pretty_scroll:
                    alias_route_message = f"[text input menu selection successfully matched: '{ckey}' → {routed}]"
                choice = routed
            else:
                if len(matches) > 1:
                    print(f"[help] Ambiguous input '{ckey}'. "
                          f"Try one of: {', '.join(sorted(matches)[:6])}"
                          f"{'...' if len(matches) > 6 else ''}")
                    continue #ambiguous entry thus restart while loop above for new input

        # Print the displayed selection before translating it to the historical
        # internal handler key. This gives every long menu response a stable,
        # easy-to-find marker when scrolling backward through terminal output.
        displayed_choice = choice.strip().lower()
        print()
        print(cca8_cli.menu_selection_banner(displayed_choice), end="")
        print()
        if alias_route_message is not None:
            print(alias_route_message)

        # Any Main Menu selection that eventually returns here should pause once
        # before the front page is redrawn. Quit exits the loop, so it never
        # consumes this pending pause.
        main_menu_continue_pending = True

        ckey = displayed_choice #ensure any present or future routed value is in correct form
        routed = cca8_cli.route_menu_number(ckey)
        if (
            pretty_scroll
            and ckey != routed
            and routed not in cca8_main_menu.SEMANTIC_TOP_LEVEL_CHOICES_V1
        ):
            print(
                "[[menu numbering auto-compatibility] processed input entry "
                f"routed to old value: {ckey} → {routed}]\n"
            )
        choice = routed

        main_menu_runtime = cca8_main_menu.MainMenuRuntimeV1(
            watch_menu=_watch_cognition_menu_v1,
            scope_menu=lambda: _cognitive_scope_menu_v1(env, world, drives, ctx, POLICY_RT),
            architecture_menu=lambda: _architecture_explanation_menu_v1(POLICY_RT),
            versions_text=versions_text,
        )
        resolved_choice = cca8_main_menu.resolve_top_level_choice_v1(
            choice,
            runtime=main_menu_runtime,
            loaded_path=loaded_src,
            autosave_path=getattr(args, "autosave", None),
            exit_save_path=getattr(args, "save", None),
        )
        if resolved_choice is None:
            continue
        choice = resolved_choice

        if choice == "nca8-runtime":
            # Import only after explicit user selection.  No legacy world, drives, Ctx, PolicyRuntime, or autosave
            # object is passed into the new runtime; this is the composition-root firewall between the two brains.
            try:
                from nca8_menu import run_nca8_experimental_menu_v1
                nca8_session = run_nca8_experimental_menu_v1(nca8_session)
            except Exception as exc:
                print(f"[nca8:error] experimental runtime unavailable: {type(exc).__name__}: {exc}")
            continue

        if choice == "configure-runtime":
            cca8_session_menu.runtime_configuration_menu_v1(drives, ctx)
            loop_helper(args.autosave, world, drives, ctx)
            continue
        if choice == "clear-working-map":
            cleared = cca8_main_menu.clear_working_map_interactive_v1(ctx, reset_working_map=reset_working_world)
            if cleared:
                loop_helper(args.autosave, world, drives, ctx)
            continue

        #FIRST MENU SELECTION CODE BLOCK.... WITHIN interactive menu while loop >>>>>> of interactive_menu()
        #----Menu Selection Code Block------------------------
        if choice == "1":
            # Legacy Main Menu #4 compatibility route: architecture/memory status.
            print("Selection: Architecture / Memory Status\n")
            _show_architecture_status_v1(world, ctx, POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "2":
            # List predicates
            print("Selection:  List Predicates\n")
            print('''
This selection will gather all the predicate tokens, i.e., "pred:*" , and show which bindings bN
  store teach token.

Note that in the current WorldGraph planner, the target is always a predicate. Cues, on the other hand, are
  not used a planning targets but indirectly they can still influence planning via policies.
  (essentially, only pred:* is used as a goal condition)

You can filter results by entering the string of the desired token, or even a partial substring of it, and
   the code will automatically find the bindings.
            ''')
            #flt is the substring of the predicate token to search for, if flt="" then we simply list all predicate tokens
            try:
                flt = input("Optional filter (substring in token, blank=all): ").strip().lower()
            except Exception:
                flt = ""
            idx: Dict[str, List[str]] = {}
            total_tags = 0
            for bid, b in world._bindings.items():
                #world._bindings is a dict and thus .items() returning (bid=key, b=value) pairs
                #  bid=key -- e.g., "b5"
                #  b=value -- a dataclass Binding instance representing one node
                #  i.e., iterate over, e.g., {"b1": Binding(id="b1", tags={...}, edges=[...], meta={...}, engrams={...}), "b2": Binding(...),  ...}
                #  dataclass Binding defined in WorldGraph -- id str, (tags), [Edge], {meta}, {engrams}
                #cca8_world_graph.class WorldGraph:  def __init__(self): self._bindings: {str, Binding} = {}
                for t in getattr(b, "tags", []):
                    #t gets that node's tags  e.g., for bid="b2", t= "tags={'pred:stand'}, edges=[], meta={'boot': 'init', 'added_by': 'system'}, engrams={})"
                    if isinstance(t, str) and t.startswith("pred:"):
                        key = t.replace("pred:", "", 1)  # strip 'pred:' e.g., in above example key = "pred"
                        if flt and flt not in key.lower(): #if substring, check if matches, else try next value
                            continue
                        idx.setdefault(key, []).append(bid)
                        total_tags += 1
                        #e.g., total_tags = 1, idx = {'stand':[b2']} <-- will list later by predicate
            if not idx:
                if flt:
                    print(f"(no predicates matched filter substring {flt!r})")
                else:
                    print("(no predicates to list yet)")
            else:
                #e.g., idx = {'stand':[b2']}
                def _bid_sort(bid: str) -> tuple[int, str]:
                    # group 0: numeric ids (b1, b2, ...), sorted by number with zero-padding
                    # group 1: non-numeric ids (e.g., 'NOW'), sorted lexicographically
                    if len(bid) > 1 and bid[1:].isdigit():
                        return (0, f"{int(bid[1:]):09d}")
                    return (1, bid)
                for key in sorted(idx.keys()):
                    bids = sorted(idx[key], key=_bid_sort)
                    print(f"  {key:<30} -> {', '.join(bids)}")
                print(
                    f"\nSummary: {len(idx)} unique predicate token(s), "
                    f"{total_tags} predicate tag(s) across {len(world._bindings)} binding(s)."
                )
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "3":
            # Selection:  Add Predicate
            # input predicate token, attach and meta for the new binding
            print("Selection: Add Predicate\n")
            print("""
Creates a new binding which will be tagged with "pred:<token>"
'Attach' value will effect where this new binding is linked in the episode:
  now    → NOW -> new, new becomes LATEST
  latest → LATEST -> new, new becomes LATEST (default)
  none   → create unlinked node (no automatic edge)\n
Examples: posture:standing, nipple:latched, etc.  Lexicon may warn in strict modes.\n

Please enter the predicate token
  e.g., vision:silhouette:mom
  don't enter, e.g., 'pred:vision:silhouette:mom' -- just enter the token portion of the predicate
  nb. no default value for predicate -- if you just click ENTER for predicate with no input, return to menu
  nb. however, there is a default value of 'latest' for attachment option
""")

            token = input("\nEnter predicate token (e.g., vision:silhouette:mom)   ").strip()
            if not token:
                print("No token entered -- no default values -- return back to menu....")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            attach = input("Attach [now/latest/none] (default: latest): ").strip().lower() or "latest"
            if attach not in ("now", "latest", "none"):
                print("[info] unknown attach; defaulting to 'latest'")
                attach = "latest"

            meta = {
                "added_by": "user",
                "created_by": "menu:add_predicate",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }

            # Decide on a contextual write base for this manual predicate add.
            base = None
            effective_attach = attach
            if attach == "latest":
                base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
                effective_attach = _maybe_anchor_attach(attach, base)
                # Brief explanation for users seeing base-aware behavior for the first time.
                print(f"[base] write-base suggestion for this add_predicate: {_fmt_base(base)}")
                if effective_attach == "none" and isinstance(base, dict) and base.get("base") == "NEAREST_PRED":
                    print("[base] base-aware attach: new binding will be created unattached, then "
                          "linked from the suggested NEAREST_PRED base instead of plain 'LATEST'.")
            else:
                print("[base] write-base suggestion skipped: attach mode is not 'latest' (user-specified).")

            # Create the new predicate binding and apply base-aware semantics if requested.
            try:
                before = len(world._bindings)
                bid = world.add_predicate(token, attach=effective_attach, meta=meta)
                after = len(world._bindings)
                print(f"Added binding {bid} with pred:{token} (attach={effective_attach})")

                # If we used a NEAREST_PRED base and suppressed auto-attach, add base->new edge explicitly.
                if isinstance(base, dict) and base.get("base") == "NEAREST_PRED" and effective_attach == "none":
                    _attach_via_base(
                        world,
                        base,
                        bid,
                        rel="then",
                        meta={
                            "created_by": "base_attach:menu:add_predicate",
                            "base_kind": base.get("base"),
                            "base_pred": base.get("pred"),
                        },
                    )

                # Small confirmation of attach semantics when we can cheaply infer the source for attach="now".
                if after > before:
                    src = None
                    if effective_attach == "now":
                        src = _anchor_id(world, "NOW")
                    if src and src in world._bindings:
                        edges = getattr(world._bindings[src], "edges", []) or []
                        def _dst(e):  # tolerant of edge layouts
                            return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                        def _rel(e):
                            return e.get("label") or e.get("rel") or e.get("relation") or "then"
                        rels = [_rel(e) for e in edges if _dst(e) == bid]
                        if rels:
                            print(f"[attach] {src} --{rels[0]}--> {bid}")
            except ValueError as e:
                print(f"[guard] add_predicate rejected token {token!r}: {e}")
            except Exception as e:
                print(f"[error] add_predicate failed: {e}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "4":
            # Connect two bindings (with duplicate warning)
            # Input bindings and edge label
            print("Selection:  Connect Bindings\n")

            print("Adds a directed edge src --label--> dst (default label: 'then'). Duplicate edges are skipped.")
            print("Use labels for readability ('fall', 'latch', 'approach'); planner today follows structure, not labels.\n")
            print('Do not use quotes, e.g., enter: fall not:"fall" unless you want quotes in the stored label')
            print('Similarly, do not use quotes for the bid, e.g., enter: b14, not "b14"\n')

            src = input("Enter the source binding id (bid) (e.g., b12) NO QUOTES :").strip()
            dst = input("Enter the destination binding id (bid) (e.g., b14) NO QUOTES : ").strip()
            if not src or not dst:
                print("Source or destination bindings entered are missing -- return back to menu....")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            label = input('Edge relation label (default via ENTER is "then") NO QUOTES : ').strip() or "then"
            try:
                b = world._bindings.get(src)
                if not b:
                    print("Invalid id: unknown source binding bid -- return back to menu....")
                elif dst not in world._bindings:
                    print("Invalid id: unknown destination binding bid -- return back to menu....")
                else:
                    edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                             getattr(b, "links", []) or getattr(b, "outgoing", []))
                    def _rel(e):  # normalize edge label
                        return e.get("label") or e.get("rel") or e.get("relation") or "then"
                    def _dst(e):  # normalize edge dst
                        return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    duplicate = any((_dst(e) == dst) and (_rel(e) == label) for e in edges)
                    if duplicate:
                        print(f"[info] Edge already exists: {src} --{label}--> {dst} (skipping)")
                    else:
                        meta = {
                            "created_by": "menu:connect",
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        }
                        #adds a directed edge from source bid to destination bid with label input, meta input
                        world.add_edge(src, dst, label, meta=meta)
                        print(f"Linked {src} --{label}--> {dst}")
            except KeyError as e:
                print("Invalid id:", e)
            except ValueError as e:
                print(f"[guard] {e}")
            except Exception as e:
                print(f"[error] add_edge failed: {e}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "5":
            # Plan from NOW -> <predicate>
            current_planner = getattr(world, "get_planner", lambda: "bfs")()
            print("Selection:  Plan to Predicate\n")
            print("""
Note the use of S-A-S segments in learning and planning within the architecture:
S-A-S  State-Action-State which we consider in the CCA8 as Predicate-Action-Predicate (since we
    avoid the brain labeling things as 'states', something scientists do more so than brains)
Conceptually it is the pattern:
   [what the world/agent is like] --> [what the agent does] --> [what the world/agent is like after]
S = predicate binding, e.g., pred:posture:standing")
A = action binding, e.g., pred:action:push_up or action:push_up (depends on version)
e.g., posture:fallen --> push_up, extend_legs --> posture:standing
A whole episode becomes a chain of S-A-S segments. This becomes a natural unit for learning and planning, i.e.,
  'if I'm in predicate S want predicate S', then what action chain A should I consider?'

Note the use of the anchor bindings NOW, NOW_ORIGIN, and LATEST in WorldGraph:
NOW_ORIGIN --   where NOW was when the session (or episode) began
                birth / episode root; stable, episode-level anchor
                world._anchors["NOW_ORIGIN"]
                should not move once set (unless deliberately start a new episode)
                #todo -- add an explicit 'start new episode' and reset NOW_ORIGIN to a new binding
NOW --  where the agent is now in the map
        world._anchors["NOW"]
        e.g., start at birth/fallen → StandUp moves NOW to standing → SeekNipple moves NOW to seeking_mom, etc.
        good for local FOA and 'what should I do from here?'
        a moving, local-state anchor
LATEST --   the most recently created binding by any operation
            world._latest_binding_id
            useful in debugging and FOA
            note that not semantically 'the agent’s current state' -- for example, can create a cue or perhaps an
                engram binding that’s not the stable state of the body
            note that we do not tag the latest binding each time with anchor:LATEST as it would move on every single
                write, i.e., end up spamming tags and making graph harder to read, and this is not necessary as
                it is always available via world._latest_binding_id, and only printed in the header

You will be asked to choose the determination of a path from NOW or from a node of your choosing, to a
    predicate of your choosing  -- be aware of what the default 'NOW' actually represents.

            """)

            print(f"Current planner strategy: {current_planner.upper()}")
            if current_planner == "dijkstra":
                print("Dijkstra search from anchor:NOW to a binding with pred:<token>.")
                print("With all edges currently weight=1, this is effectively the same path as BFS.\n")
            else:
                print("BFS from anchor:NOW to a binding with pred:<token>. Prints raw id path and a pretty path.\n")

            token = input("Target predicate (e.g., posture:standing): ").strip()
            if not token:
                loop_helper(args.autosave, world, drives, ctx)
                continue
            # convenience: allow posture:standing → posture:standing, etc.
            if ":" not in token and "_" in token:
                parts = token.split("_", 1)
                if len(parts) == 2:
                    token = f"{parts[0]}:{parts[1]}"

            # allow planning from any binding, default NOW; special token ORIGIN → NOW_ORIGIN
            try:
                start_bid = input("Start from binding id (blank = NOW, ORIGIN = NOW_ORIGIN): ").strip()
            except Exception:
                start_bid = ""
            if start_bid:
                key = start_bid.lower()
                if key in ("origin", "now_origin"):
                    src_id = _anchor_id(world, "NOW_ORIGIN")
                    if src_id == "?":
                        print("[info] NOW_ORIGIN not set; falling back to NOW.")
                        src_id = world.ensure_anchor("NOW")
                elif start_bid in world._bindings:
                    src_id = start_bid
                else:
                    print(f"[info] Unknown binding id {start_bid!r}; falling back to NOW.")
                    src_id = world.ensure_anchor("NOW")
            else:
                src_id = world.ensure_anchor("NOW")

            path = world.plan_to_predicate(src_id, token)
            if path:
                print("\nPath (ids):", " -> ".join(path))
                try:
                    pretty = world.pretty_path(
                        path,
                        node_mode="id+pred",       # try 'pred' if prefer only tokens
                        show_edge_labels=True,
                        annotate_anchors=True
                    )
                    print("Pretty printing of path:\n", pretty)
                except Exception as e:
                    print(f"(pretty-path error: {e})")

                def _typed_label(bid: str) -> str:
                    """
                    Typed view: show each node with its primary role (anchor/pred/action/cue)
                    """
                    b = world._bindings.get(bid)
                    if not b:
                        return bid
                    tags = getattr(b, "tags", []) or []

                    goal_pred_full = f"pred:{token}"
                    if any(isinstance(t, str) and (t in (goal_pred_full, token)) for t in tags):
                        return token

                    for t in tags:
                        if isinstance(t, str) and t.startswith("anchor:"):
                            return t
                    for t in tags:
                        if isinstance(t, str) and t.startswith("action:"):
                            return t
                    for t in tags:
                        if isinstance(t, str) and t.startswith("pred:"):
                            return t[5:]
                    for t in tags:
                        if isinstance(t, str) and t.startswith("cue:"):
                            return t
                    return "(no-tags)"

                # Reverse typed view: from goal back to start (useful for "backwards" intuition).
                rev_parts: list[str] = []
                rev_path = list(reversed(path))
                for i, bid in enumerate(rev_path):
                    rev_parts.append(f"[{bid}:{_typed_label(bid)}]")
                    if i + 1 < len(rev_path):
                        rev_parts.append(" -> ")
                print("Reverse typed path:", "".join(rev_parts))

                # Forward typed view: from start to goal
                typed_parts: list[str] = []
                for i, bid in enumerate(path):
                    typed_parts.append(f"[{bid}:{_typed_label(bid)}]")
                    if i + 1 < len(path):
                        typed_parts.append(" -> ")
                print("Typed path:", "".join(typed_parts))
            else:
                print("No path found.")
            loop_helper(args.autosave, world, drives, ctx)

        #----Menu Selection Code Block------------------------
        elif choice == "6":
            print("Selection:  Resolve Engrams\n")
            print('''
Shows engram slots on a binding.
Note: For payload/meta details use menu selection "Inspect engram by id"

-a "slot name" is the key used in a binding's engrams dict to label a particular engram pointer
     e.g, b3: [cue:vision:silhouette:mom] engrams={'column01': {'id': 'b3001752abc946769b8c182f38cf0232', 'act': 1.0}}
       -- 'column01' is the slot name, i.e., binding.engrams['column01'] = {id:eid, act:1.0, ...} where id = engram id,
              act = activation weight
       -- 'b3001752a…' is the human-readable summary of that pointer== eid
-system defaults with a single column in RAM    mem =ColumnMemory(name='column01')  but can set up for multiple columns

            ''')
            bid = input("Binding id to resolve engrams: ").strip()
            #user input is the bid
            if not bid:
                print("No id entered.")
            else:
                _resolve_engrams_pretty(world, bid)
                #from bid gets column01: {"id": eid, "act": 1.0}
                #prints these out as, e.g., Engrams on b3; column01: 34c406dd…  OK
                b = world._bindings.get(bid)
                #e.g. Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={}, engrams={'column01': {'id': '05a6dfba0e7b4aef8ca116485efc5ad8', 'act': 1.0}})
                if b and getattr(b, "engrams", None):
                    print("Raw pointers:", b.engrams)

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "7":
            # Legacy Main Menu #5 compatibility route.
            print("Selection: Recent WorldGraph Bindings\n")
            _show_recent_bindings_v1(world, limit=5)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "8":
            # Quit
            print("Selection:  Quit\n")
            print("Exits the simulation. If you launched with --save, a final save occurs on exit.\n")
            print("Goodbye.")
            if args.save:
                save_session(args.save, world, drives)
            #return from main() which will then immediately exedcute return 0
            #after main() is: if __name__ == "__main__": sys.exit(main()) --> sys.exit(0) thus occurs
            return


        #----Menu Selection Code Block------------------------
        elif choice == "9":
            # Run preflight now
            print("Selection:  Preflight\n")
            print("Runs pytest and the full CCA8 validation wall. Coverage is optional and disabled by default.\n")

            #rc = run_preflight_full(args)
            run_preflight_full(args)
            # no autosave or mini-snapshot after preflight; just return to menu.
            # loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "10":
            # Inspect binding details and user input (accepts a single id, or ALL/* to dump everything)
            print("Selection:  Inspect Binding Details")
            print('''

-Enter a binding id (bid) (e.g., 'b3') or 'ALL' (or '*').
     Note: not case sensitive -- e.g., 'B3' or 'b3' treated the same
     Note: if case-sensitivity exists in your WorldGraph labeling, then comment out case insensitivity line of code

-This selection will then display the binding's tags, meta, engrams,
   and its outgoing and incoming edges.
-Note that you can inspect provenance, meta.policy/created_by/boot, attached engrams,
   and graph degree on one or more bindings.
   Note: each binding has a meta dictionary that stores provenance, i.e., a record of where and when this binding comes
   Note: from a binding created by a policy at runtime might have key:value pair inside of meta dict
   Note: a typical Provenance summary is, e.g., meta.policy, meta.created_by, meta.boot, meta.ticks, etc.

-Internally the code block calls _print_one(bid) and prints out the information about that binding
-if "ALL" chosen then _sorted_bids(world) returns the WorldGraph's bid's in sorted order, e.g., (b1, b2, ...)
    and loop through bid's with a _print_one(bid) for each one

            ''')
            bid = input("Binding id to inspect (or 'ALL'/ENTER): ").strip().lower() #case insensitive
            #bid = input("Binding id to inspect (or 'ALL'): ").strip() #case sensitive
            print("\n Binding details for the requested binding(s):\n")

            # Inspect binding internal helper functions
            def _edge_rel(e: dict) -> str:
                return e.get("label") or e.get("rel") or e.get("relation") or "then"


            def _edge_dst(e: dict) -> str | None:
                return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")


            def _families_from_tags(tags) -> list[str]:
                fams: list[str] = []
                tags = tags or []
                if any(isinstance(t, str) and t.startswith("anchor:") for t in tags):
                    fams.append("anchor")
                if any(isinstance(t, str) and t.startswith("pred:") for t in tags):
                    fams.append("pred")
                if any(isinstance(t, str) and t.startswith("action:") for t in tags):
                    fams.append("action")
                if any(isinstance(t, str) and t.startswith("cue:") for t in tags):
                    fams.append("cue")
                return fams


            def _anchors_from_tags(tags) -> list[str]:
                out: list[str] = []
                for t in tags or []:
                    if isinstance(t, str) and t.startswith("anchor:"):
                        out.append(t.split(":", 1)[1])
                return out


            def _provenance_summary(meta: dict) -> str | None:
                if not isinstance(meta, dict) or not meta:
                    return None
                policy = meta.get("policy")
                creator = meta.get("created_by") or meta.get("boot") or meta.get("added_by")
                created_at = meta.get("created_at") or meta.get("time") or meta.get("ts")
                cognitive_cycle = meta.get("cognitive_cycle")
                controller_step = meta.get("controller_step")
                autonomic_tick = meta.get("autonomic_tick")
                age_days = meta.get("age_days")
                bits: list[str] = []
                if policy:
                    bits.append(f"policy={policy}")
                if creator:
                    bits.append(f"created_by={creator}")
                if created_at:
                    bits.append(f"created_at={created_at}")
                if isinstance(cognitive_cycle, int):
                    bits.append(f"cognitive_cycle={cognitive_cycle}")
                if isinstance(controller_step, int):
                    bits.append(f"controller_step={controller_step}")
                if isinstance(autonomic_tick, int):
                    bits.append(f"autonomic_tick={autonomic_tick}")
                if isinstance(age_days, (int, float)):
                    bits.append(f"age_days={float(age_days):.4f}")
                return ", ".join(bits) if bits else None


            def _engrams_pretty(_bid: str, b) -> None:
                eng = getattr(b, "engrams", None) or {}
                if not isinstance(eng, dict) or not eng:
                    print("Engrams: (none)")
                    return
                print("Engrams:")
                for slot, val in sorted(eng.items()):
                    if isinstance(val, dict):
                        eid = val.get("id")
                        act = val.get("act")
                    else:
                        eid = None
                        act = None
                    status = ""
                    short = "(id?)"
                    if isinstance(eid, str):
                        short = eid[:8] + "…"
                        try:
                            rec = world.get_engram(engram_id=eid)
                            ok = bool(rec and isinstance(rec, dict) and rec.get("id") == eid)
                            status = "OK" if ok else "(dangling)"
                        except Exception:
                            status = "(error)"
                    act_txt = f" act={act:.3f}" if isinstance(act, (int, float)) else ""
                    print(f"  {slot}: {short}{act_txt} {status}".rstrip())


            def _incoming_edges_for(_bid: str) -> list[tuple[str, str]]:
                inc: list[tuple[str, str]] = []
                for src_id, other in world._bindings.items():
                    edges = (getattr(other, "edges", []) or getattr(other, "out", []) or
                             getattr(other, "links", []) or getattr(other, "outgoing", []))
                    if not isinstance(edges, list):
                        continue
                    for e in edges:
                        dst = _edge_dst(e)
                        if dst == _bid:
                            inc.append((src_id, _edge_rel(e)))
                return inc


            def _outgoing_edges_for(b) -> list[tuple[str, str]]:
                edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                         getattr(b, "links", []) or getattr(b, "outgoing", []))
                out: list[tuple[str, str]] = []
                if isinstance(edges, list):
                    for e in edges:
                        dst = _edge_dst(e)
                        if dst:
                            out.append((dst, _edge_rel(e)))
                return out


            def _print_one(_bid: str) -> None:
                b = world._bindings.get(_bid)
                if not b:
                    print(f"Unknown binding id: {_bid}")
                    print("Returning to main menu....\n")
                    return

                tags = sorted(getattr(b, "tags", []))
                families = _families_from_tags(tags)
                anchors = _anchors_from_tags(tags)

                print(f"ID: {_bid}")
                if families or anchors:
                    kind_parts: list[str] = []
                    if families:
                        kind_parts.append("kind=" + "/".join(families))
                    if anchors:
                        kind_parts.append("anchor=" + ",".join(anchors))
                    print("Role:", "; ".join(kind_parts))
                print("Tags:", ", ".join(tags) if tags else "(none)")

                meta = getattr(b, "meta", {})
                print("Meta:", json.dumps(meta if isinstance(meta, dict) else {}, indent=2))
                prov = _provenance_summary(meta if isinstance(meta, dict) else {})
                if prov:
                    print("Provenance:", prov)

                _engrams_pretty(_bid, b)

                # Edges
                outgoing = _outgoing_edges_for(b)
                incoming = _incoming_edges_for(_bid)
                print(f"Degree: out={len(outgoing)} in={len(incoming)}")

                if outgoing:
                    print("Outgoing edges:")
                    for dst, rel in outgoing:
                        print(f"  {_bid} --{rel}--> {dst}")
                else:
                    print("Outgoing edges: (none)")

                if incoming:
                    print("Incoming edges:")
                    for src, rel in incoming:
                        print(f"  {src} --{rel}--> {_bid}")
                else:
                    print("Incoming edges: (none)")

                print("\n", "-" * 28, "\n")


            from collections import deque
            def _concept_neighborhood_layers(start_bid: str, max_hops: int = 2) -> dict[int, list[str]]:
                """
                Return a dict {distance: [binding ids]} for nodes reachable from start_bid
                within `max_hops` hops (outgoing edges only).
                distance=0 contains start_bid itself.
                """
                layers: dict[int, list[str]] = {0: [start_bid]}
                seen: set[str] = {start_bid}
                q = deque([(start_bid, 0)])

                while q:
                    u, d = q.popleft()
                    if d >= max_hops:
                        continue
                    b = world._bindings.get(u)
                    if not b:
                        continue
                    edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                             getattr(b, "links", []) or getattr(b, "outgoing", []))
                    if not isinstance(edges, list):
                        continue
                    for e in edges:
                        v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                        if not v or v in seen or v not in world._bindings:
                            continue
                        seen.add(v)
                        layers.setdefault(d+1, []).append(v)
                        q.append((v, d+1))
                return layers


            def _print_neighborhood(start_bid: str, max_hops: int = 2) -> None:
                if start_bid not in world._bindings:
                    print(f"(neighborhood) Unknown start binding {start_bid!r}")
                    return
                layers = _concept_neighborhood_layers(start_bid, max_hops=max_hops)
                print(f"\nConcept neighborhood around {start_bid} (max_hops={max_hops}):")
                for dist in sorted(layers.keys()):
                    print(f"  distance {dist}:")
                    for nid in layers[dist]:
                        nb = world._bindings.get(nid)
                        tags = ", ".join(sorted(getattr(nb, 'tags', []))) if nb else ""
                        print(f"    {nid}: [{tags}]")
                print()


            #main code of the Inspect Binding code block
            if bid in ("all", "*", ""):
                for _bid in _sorted_bids(world):
                    _print_one(_bid)
            else:
                _print_one(bid)
                # Optional: concept neighborhood around this binding
                try:
                    ans = input("Show concept neighborhood around this binding? [y/N]: ").strip().lower()
                except Exception:
                    ans = ""
                if ans in ("y", "yes"):
                    try:
                        htxt = input("Max hops (default 2): ").strip()
                        max_hops = int(htxt) if htxt.isdigit() else 2
                    except Exception:
                        max_hops = 2
                    _print_neighborhood(bid, max_hops=max_hops)

            #code block complete and return back to main menu
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "11":
            # Add sensory cue
            print("Selection:  Input Sensory Cue")
            print(r"""
Adds one cue:<channel>:<token> binding at NOW, then runs one Action Center invocation.

Timekeeping for this manual flow is explicit:
  - controller_steps increments once before policy selection/execution;
  - cognitive cycles do not increment because no full EnvObservation-to-output loop runs;
  - autonomic ticks and developmental age do not change.

Examples include cue:vision:silhouette:mom, cue:scent:milk, and cue:sound:bleat:mom.
""")

            ch = input("Channel (vision/scent/touch/sound): ").strip().lower()
            tok = input("Cue token (e.g., silhouette:mom): ").strip()
            if ch and tok:
                cue_token = f"{ch}:{tok}"
                bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
                print(f"Added sensory cue: cue:{cue_token} as {bid}")
                try:
                    ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
                except Exception:
                    pass
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
                if fired != "no_match":
                    print(fired)
                print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "12":
            # Instinct step
            print("Selection:  Instinct Step\n")
            print(r"""
Run one manual Action Center invocation.

This operation:
  1. increments controller_steps once;
  2. proposes a context-sensitive write base;
  3. builds a small focus-of-attention neighborhood;
  4. evaluates the currently loaded primitives and executes one winner, when applicable;
  5. reports any graph change and the explicit runtime counters.

It does not increment cognitive_cycles because it is not a complete
EnvObservation -> processing -> output cognitive cycle. It also does not change
autonomic_ticks or developmental age.
""")

            try:
                ctx.controller_steps += 1
            except Exception:
                pass

            before_n = len(world._bindings)

            # --- context (for teaching / debugging) ---
            base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
            foa = compute_foa(world, ctx, max_hops=2)
            cands = candidate_anchors(world, ctx)

            # Annotate anchors for readability: b1(NOW), ?(HERE), etc.
            now_id = _anchor_id(world, "NOW")
            here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None

            def _ann(bid: str) -> str:
                if bid == now_id:
                    return f"{bid}(NOW)"
                if here_id and bid == here_id:
                    return f"{bid}(HERE)"
                return f"{bid}"

            print(f"[instinct] base_suggestion={base}, anchors={[_ann(x) for x in cands]}, foa_size={foa['size']}")
            print("Note: A base_suggestion proposes where to attach writes; it is not a policy selection.")
            print(f"[context] write-base: {_fmt_base(base)}")
            print(f"[context] anchors: {', '.join(_ann(x) for x in cands)}")
            print(f"[context] foa: size={foa['size']} (ids near NOW/LATEST + cues)")

            result = action_center_step(world, ctx, drives)
            after_n = len(world._bindings)

            # controller_steps counts this Action Center invocation. cognitive_cycles
            # remains reserved for complete environment-to-output cycles (menus 35/37).
            if isinstance(result, dict):
                policy = result.get("policy")
                status = result.get("status")
                reward = result.get("reward")
                binding = result.get("binding")
                if policy and status:
                    rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                    print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                else:
                    print("Action Center:", result)
            else:
                print("Action Center:", result)

            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n:
                new_bid = result.get("binding")
                if isinstance(new_bid, str):
                    try:
                        world.set_now(new_bid, tag=True, clean_previous=True)
                    except Exception:
                        pass

            label = result.get("policy") if isinstance(result, dict) and "policy" in result else "(controller)"
            gate = next((policy for policy in POLICY_RT.loaded if policy.name == label), None)
            explainer: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
            if explainer is not None:
                try:
                    why = explainer(world, drives, ctx)
                    print(f"[why {label}] {why}")
                except Exception:
                    pass

            if after_n == before_n:
                print("(no new bindings/edges created this step)")
            else:
                print(f"(graph updated: bindings {before_n} -> {after_n})")

            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "13":
            # Legacy Main Menu #7 compatibility route.
            print("Selection: Primitive Skill Telemetry\n")
            _show_skill_telemetry_v1(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "14":
            # Autonomic tick
            print("Selection: Autonomic Tick")
            print(r"""
The autonomic tick is an independent physiology/IO heartbeat. This menu action:
  1. increments autonomic_ticks and developmental age;
  2. updates the small fatigue model;
  3. emits any rising-edge interoceptive cues;
  4. refreshes developmentally available policies;
  5. performs one Action Center invocation, incrementing controller_steps once.

It does not increment cognitive_cycles because no complete sensory-input to
same-cycle-output environment loop runs here.
""")
            drives.fatigue = min(1.0, drives.fatigue + 0.01)
            try:
                ctx.ticks = getattr(ctx, "ticks", 0) + 1
                ctx.age_days = getattr(ctx, "age_days", 0.0) + 0.01
                world.set_stage_from_ctx(ctx)
                print(f"Autonomic: fatigue +0.01 | ticks={ctx.ticks} age_days={ctx.age_days:.2f}")

                started = _emit_interoceptive_cues(world, drives, ctx, attach="latest")
                if started:
                    print("[autonomic] interoceptive cues asserted: " + ", ".join(f"cue:{item}" for item in sorted(started)))
            except Exception as exc:
                print(f"Autonomic: fatigue +0.01 (exception: {type(exc).__name__}: {exc})")

            POLICY_RT.refresh_loaded(ctx)
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(fired)
            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "15":
            # Delete edge and autosave (if --autosave is active)
            print("Selection:  Delete Edge\n")
            print("Removes edge(s) matching src --> dst [relation]. Leave relation blank to remove any label.\n")
            #function contains inputs, logic,messages, autosave
            delete_edge_flow(world, autosave_cb=lambda: loop_helper(args.autosave, world, drives, ctx))
            #does not call loop_helper(...) since delete_edge_flow(...) does much of the same, including optional autosave

        #----Menu Selection Code Block------------------------
        elif choice == "16":
            # Export snapshot
            print("Selection:  Export Snapshot (Text)\n")
            print("Writes the same snapshot you see on-screen to world_snapshot.txt for sharing/debugging.\n")

            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice in ("scope", "17"):
            # Cognitive storage oscilloscope / system inspector.
            print("Selection: CCA8 Cognitive Storage Oscilloscope / System Inspector\n")
            _cognitive_scope_menu_v1(env, world, drives, ctx, POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "18":
            # Simulate a fall event and try a recovery attempt immediately.
            print("Selection: Simulate a fall event\n")
            print(r"""
Creates a current posture:fallen event, relabels the transition into that
binding as fall, and performs one safety-oriented Action Center invocation.

Timekeeping is explicit: controller_steps increments once before policy
selection. cognitive_cycles, autonomic_ticks, and age_days do not change.
""")

            prev_latest = world._latest_binding_id
            fallen_bid = world.add_predicate(
                "posture:fallen",
                attach="latest",
                meta={"event": "fall", "added_by": "user"},
            )
            try:
                if prev_latest:
                    world_delete_edge(world, prev_latest, fallen_bid, None)
                    world.add_edge(prev_latest, fallen_bid, "fall")
            except Exception as exc:
                print(f"[fall] relabel note: {exc}")

            print(f"Simulated fall as {fallen_bid}")
            POLICY_RT.refresh_loaded(ctx)
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(fired)
            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "22":
            # Historical direct Pyvis route; the interaction flow now lives with the Oscilloscope menu.
            print("Selection: Export and display interactive graph (Pyvis HTML) with options")
            _open_worldgraph_pyvis_flow_v1(world)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "24":
            # Capture scene -> emit cue/predicate + tiny engram (signal bridge demo)
            print("Selection: Capture scene\n")
            print(r"""
Capture one small sensory payload in Column memory and attach its engram pointer
to a new WorldGraph binding.

The engram records directly interpretable provenance:
  cognitive_cycle, controller_step, autonomic_tick, age_days, and created_at.
No stochastic temporal vector or synthetic event epoch is created.

When attach=latest, the menu can still use a context-sensitive write-base
suggestion so the new binding is linked under a meaningful nearby predicate.
""")

            try:
                channel = input("Channel [vision/scent/sound/touch] (default: vision): ").strip().lower() or "vision"
                token   = input("Token   (e.g., silhouette:mom) (default: silhouette:mom): ").strip() or "silhouette:mom"
                family  = input("Family  [cue/pred] (default: cue): ").strip().lower() or "cue"
                attach  = input("Attach  [now/latest/none] (default: now): ").strip().lower() or "now"
                vtext   = input("Vector  (comma/space floats; default: 0.0,0.0,0.0): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n(cancelled)")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            if family not in ("cue", "pred"):
                print("[info] unknown family; defaulting to 'cue'")
                family = "cue"
            if attach not in ("now", "latest", "none"):
                print("[info] unknown attach; defaulting to 'now'")
                attach = "now"

            vec = _parse_vector(vtext)

            # decide on a contextual write base for this capture_scene.
            base = None
            effective_attach = attach
            if attach == "latest":
                base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
                effective_attach = _maybe_anchor_attach(attach, base)
                print(f"[base] write-base suggestion for this capture_scene: {_fmt_base(base)}")
                if effective_attach == "none" and isinstance(base, dict) and base.get("base") == "NEAREST_PRED":
                    print("[base] base-aware capture_scene: new binding will be created unattached, then "
                          "anchored under the suggested NEAREST_PRED base instead of plain 'LATEST'.")
            else:
                print("[base] write-base suggestion skipped for capture_scene: attach mode is not 'latest' (user-specified).")

            # Pass explicit runtime-ordering metadata when creating the engram.
            from cca8_features import time_attrs_from_ctx
            attrs = time_attrs_from_ctx(ctx)
            bid, eid = world.capture_scene(channel, token, vec, attach=effective_attach, family=family, attrs=attrs)

            try:
                print(f"[bridge] created binding {bid} with tag "
                      f"{family}:{channel}:{token} and attached engram id={eid}")

                # If we used a NEAREST_PRED base and suppressed auto-attach, anchor this scene under the base now.
                if isinstance(base, dict) and base.get("base") == "NEAREST_PRED" and effective_attach == "none":
                    _attach_via_base(
                        world,
                        base,
                        bid,
                        rel="then",
                        meta={
                            "created_by": "base_attach:menu:capture_scene",
                            "base_kind": base.get("base"),
                            "base_pred": base.get("pred"),
                        },
                    )

                # Fetch and summarize the engram record (robust to different shapes)
                try:
                    rec = world.get_engram(engram_id=eid)
                    meta = rec.get("meta", {})
                    attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                    if attrs:
                        print(
                            "[bridge] time on engram: "
                            f"cognitive_cycle={attrs.get('cognitive_cycle')} "
                            f"controller_step={attrs.get('controller_step')} "
                            f"autonomic_tick={attrs.get('autonomic_tick')} "
                            f"age_days={attrs.get('age_days')}"
                        )
                    rid   = rec.get("id", eid)
                    payload = rec.get("payload") if isinstance(rec, dict) else None
                    if isinstance(payload, dict):
                        kind  = payload.get("kind") or payload.get("meta", {}).get("kind")
                        shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                    else:
                        kind  = rec.get("kind")
                        shape = rec.get("shape")
                    print(f"[bridge] column record ok: id={rid} kind={kind} shape={shape} "
                          f"keys={list(rec.keys()) if isinstance(rec, dict) else type(rec)}")
                except Exception as e:
                    print(f"[warn] could not retrieve engram record: {e}")

                # Print the actual slot and ids we just attached
                slot = None
                try:
                    b = world._bindings.get(bid)
                    eng = getattr(b, "engrams", None)
                    if isinstance(eng, dict):
                        for s, v in eng.items():
                            if isinstance(v, dict) and v.get("id") == eid:
                                slot = s
                                break
                except Exception:
                    slot = None
                if slot:
                    print(f'[bridge] attached pointer: {bid}.engrams["{slot}"] = {eid}')
                else:
                    slots = ", ".join(eng.keys()) if isinstance(eng, dict) else "(none)"
                    print(f'[bridge] {bid} engrams now include [{slots}] (attached id={eid})')

                # Optional: one controller step (Action Center) after capture.
                try:
                    ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
                except Exception:
                    pass
                try:
                    res = action_center_step(world, ctx, drives)
                    if isinstance(res, dict):
                        if res.get("status") != "noop":
                            policy  = res.get("policy")
                            status  = res.get("status")
                            reward  = res.get("reward")
                            binding = res.get("binding")
                            rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                            print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                            gate = next((p for p in POLICY_RT.loaded if p.name == policy), None)
                            explain_fn: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
                            if explain_fn is not None:
                                try:
                                    why = explain_fn(world, drives, ctx)
                                    print(f"[why {policy}] {why}")
                                except Exception:
                                    pass
                    else:
                        print("Action Center:", res)
                except Exception as e:
                    print(f"[warn] controller step errored: {e}")
            except Exception as e:
                print(f"[warn] capture_scene flow failed: {e}")

            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "25":
            # Planner strategy toggle
            print("Selection: Planner Strategy Toggle")
            try:
                current = getattr(world, "get_planner", lambda: "bfs")()
            except Exception:
                current = "bfs"
            print(f"\nCurrent planner: {current.upper()}  (BFS = fewest hops; Dijkstra = lowest total edge weight)")
            print("Note: Edge weights are read from edge.meta keys: 'weight' → 'cost' → 'distance' → 'duration_s' (default 1.0).")
            try:
                sel = input("Choose planner: [b]fs / [d]ijkstra / [Enter]=keep → ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sel = ""
            if sel.startswith("b"):
                world.set_planner("bfs")
                print("Planner set to BFS (unweighted shortest path by hops).")
            elif sel.startswith("d"):
                world.set_planner("dijkstra")
                print("Planner set to Dijkstra (weighted; defaults to 1 per edge when unspecified).")
            else:
                print("Planner unchanged.")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "26":
            # Historical Main Menu #8 compatibility route.
            print("Selection: Timekeeping Status\n")
            _show_timekeeping_status_v1(env, ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "27":
            # Inspect engram by id OR by binding id
            print("Selection: Inspect engram by id or by binding id")
            print('''
From the eid (engram id) or bid (binding id) this selection will display
the human-readable portions of the engram record.

            ''')
            try:
                key = input("Engram id OR Binding id: ").strip()
            except Exception:
                key = ""
            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            # Resolve binding → engram(s) if the user passed bN
            eid = key
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives, ctx)
                    continue
                if len(eids) > 1:
                    print(f"Binding {key} has multiple engrams:")
                    for i, ee in enumerate(eids, 1):
                        print(f"  {i}) {ee}")
                    try:
                        sel = input("Pick one [number]: ").strip()
                        idx = int(sel) - 1
                        eid = eids[idx]
                    except Exception:
                        print("Cancelled.")
                        loop_helper(args.autosave, world, drives, ctx)
                        continue
                else:
                    eid = eids[0]
            #at this point have eid, e.g., "9a55787783bc44fb9f5d3f5a49ec7b5d"

            rec = None
            try:
                rec = world.get_engram(engram_id=eid)
                #e.g., {'id': '9a55787783bc44fb9f5d3f5a49ec7b5d', 'name': 'scene:vision:silhouette:mom', 'payload': TensorPayload(......
            except Exception:
                rec = None
            if not rec:
                print(f"Engram not found: {eid}")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            refs = _bindings_pointing_to_eid(world, eid)
            if refs:
                print("  referenced by:", ", ".join(f"{bid}.{slot}" for bid, slot in refs))
            try:
                kind = rec.get("kind") or rec.get("type") or "(unknown)"
                print(f"Engram: {eid}")
                print(f"  kind: {kind}")
                #e.g., Engram: 9a55787783bc44fb9f5d3f5a49ec7b5d  \\ kind: (unknown)

                meta = rec.get("meta", {}) if isinstance(rec, dict) else {}
                print("  meta:", json.dumps(meta, indent=2))

                attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                if isinstance(attrs, dict) and attrs:
                    print(
                        "  time attrs: "
                        f"cognitive_cycle={attrs.get('cognitive_cycle')} "
                        f"controller_step={attrs.get('controller_step')} "
                        f"autonomic_tick={attrs.get('autonomic_tick')} "
                        f"age_days={attrs.get('age_days')}"
                    )

                payload = rec.get("payload") or rec.get("data") or rec.get("value")
                if isinstance(payload, dict):
                    shape  = payload.get("shape") or payload.get("meta", {}).get("shape")
                    dtype  = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                    nbytes = payload.get("nbytes")
                    if nbytes is None and "bytes" in payload and isinstance(payload["bytes"], (bytes, bytearray, str)):
                        try: nbytes = len(payload["bytes"])
                        except Exception: nbytes = None
                    if shape or dtype or nbytes is not None:
                        print(f"  payload: shape={shape} dtype={dtype} nbytes={nbytes}")
                    else:
                        print("  payload:", json.dumps(payload, indent=2))
                elif isinstance(payload, (bytes, bytearray)):
                    print(f"  payload: <{len(payload)} bytes>")
                else:
                    print("  payload: (none)" if payload is None else f"  payload: {payload}")
            except Exception as e:
                print(f"(error printing engram {eid}): {e!r}")
            print("-" * 78)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "28":
            # List all engrams by scanning bindings; de-duplicate by id.
            print("Selection: List all engrams")
            print(r"""
Lists each referenced Column engram once. Runtime provenance is shown as
cognitive-cycle, controller-step, autonomic-tick, and developmental-age values.
""")

            seen: set[str] = set()
            any_found = False
            for bid in _sorted_bids(world):
                for eid in _engrams_on_binding(world, bid):
                    if eid in seen:
                        continue
                    seen.add(eid)
                    any_found = True
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        rec = None

                    attrs = {}
                    shape = None
                    kind = None
                    fmt = None
                    name = ""
                    if isinstance(rec, dict):
                        name = str(rec.get("name") or "")
                        meta = rec.get("meta", {})
                        raw_attrs: Any = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                        attrs = raw_attrs if isinstance(raw_attrs, dict) else {}
                        payload = rec.get("payload")
                        if hasattr(payload, "meta"):
                            try:
                                payload_meta = payload.meta()
                                shape = payload_meta.get("shape")
                                kind = payload_meta.get("kind")
                                fmt = payload_meta.get("fmt")
                            except Exception:
                                pass
                        elif isinstance(payload, dict):
                            payload_meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
                            shape = payload.get("shape") or payload_meta.get("shape")
                            kind = payload.get("kind") or payload.get("dtype") or payload_meta.get("kind")
                            fmt = payload.get("fmt") or payload_meta.get("fmt")

                    print(
                        f"EID={eid} src={bid} cognitive_cycle={attrs.get('cognitive_cycle')} "
                        f"controller_step={attrs.get('controller_step')} "
                        f"autonomic_tick={attrs.get('autonomic_tick')} age_days={attrs.get('age_days')} "
                        f"payload(shape={shape}, kind={kind}{', fmt=' + str(fmt) if fmt else ''})"
                        f"{' name=' + name if name else ''}"
                    )
            if not any_found:
                print("no engrams were found")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "29":
            # Search engrams.
            print("Selection: Search Engrams\n")
            print(
                "Search referenced engrams by name substring and/or cognitive-cycle number. "
                "Optional filters include channel, payload kind, and EID prefix.\n"
            )

            try:
                query = input("Name contains (substring, blank=any): ").strip()
            except Exception:
                query = ""
            try:
                cycle_text = input("Cognitive cycle equals (blank=any): ").strip()
                cognitive_cycle = int(cycle_text) if cycle_text else None
            except Exception:
                cognitive_cycle = None
            try:
                channel = input("Channel contains (e.g., vision, blank=any): ").strip().lower()
            except Exception:
                channel = ""
            try:
                payload_kind = input("Payload kind equals (e.g., scene, blank=any): ").strip().lower()
            except Exception:
                payload_kind = ""
            try:
                eid_prefix = input("EID starts with (hex prefix, blank=any): ").strip().lower()
            except Exception:
                eid_prefix = ""

            seen = set()
            found: list[tuple[str, str, str, dict[str, Any]]] = []
            for bid, binding in world._bindings.items():
                engrams = getattr(binding, "engrams", None)
                if not isinstance(engrams, dict):
                    continue
                for value in engrams.values():
                    if not (isinstance(value, dict) and isinstance(value.get("id"), str)):
                        continue
                    eid = value["id"]
                    if eid in seen:
                        continue
                    seen.add(eid)
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue

                    name = str(rec.get("name") or "")
                    meta = rec.get("meta", {})
                    raw_attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                    attrs = raw_attrs if isinstance(raw_attrs, dict) else {}

                    if eid_prefix and not eid.lower().startswith(eid_prefix):
                        continue
                    if query and query.lower() not in name.lower():
                        continue
                    if channel and channel not in name.lower():
                        continue
                    if cognitive_cycle is not None and attrs.get("cognitive_cycle") != cognitive_cycle:
                        continue
                    if payload_kind:
                        payload = rec.get("payload")
                        kind = None
                        if hasattr(payload, "meta"):
                            try:
                                kind = payload.meta().get("kind")
                            except Exception:
                                kind = None
                        elif isinstance(payload, dict):
                            payload_meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
                            kind = payload.get("kind") or payload_meta.get("kind")
                        if str(kind or "").lower() != payload_kind:
                            continue

                    found.append((eid, bid, name, attrs))

            if not found:
                print("\n(no matches)")
            else:
                print("\nThe following matches were found:\n")

                def _sort_key(item: tuple[str, str, str, dict[str, Any]]) -> tuple[float, str, str]:
                    eid, _bid, name, attrs = item
                    cycle = attrs.get("cognitive_cycle")
                    cycle_key = -float(cycle) if isinstance(cycle, int) else float("inf")
                    return (cycle_key, name, eid)

                for eid, bid, name, attrs in sorted(found, key=_sort_key):
                    print(
                        f"EID={eid} src={bid} name={name} "
                        f"cognitive_cycle={attrs.get('cognitive_cycle')} "
                        f"controller_step={attrs.get('controller_step')} "
                        f"autonomic_tick={attrs.get('autonomic_tick')}"
                    )

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "30":
            # Delete engram by id OR by binding id; also prune any binding pointers to it
            print("Selection: Delete engram\n")
            print('''
Deletes engrams by bid (binding id) or by eid (engram id).
Every binding pointer that references this eid will be pruned.
-deletes the Column record via column.mem.delete(eid)
-then prunes every binding pointer that referenced that eid

            ''')
            key = input("Engram id OR Binding id to delete: ").strip()
            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives, ctx); continue

            # Resolve binding → engram id(s) if needed
            targets = []
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives, ctx); continue
                if len(eids) > 1:
                    print(f"Binding {key} has multiple engrams:")
                    for i, ee in enumerate(eids, 1):
                        print(f"  {i}) {ee}")
                    try:
                        pick = int(input("Pick one [number]: ").strip()) - 1
                        targets = [eids[pick]]
                    except Exception:
                        print("(cancelled)")
                        loop_helper(args.autosave, world, drives, ctx); continue
                else:
                    targets = [eids[0]]
            else:
                targets = [key]

            print("WARNING: this will delete the engram record from column memory,")
            print("and will also prune any binding pointers that reference it.")
            if input("Type DELETE to confirm: ").strip() != "DELETE":
                print("(cancelled)")
                loop_helper(args.autosave, world, drives, ctx); continue

            deleted_any = False
            for eid in targets:
                ok = False
                try:
                    ok = column_mem.delete(eid)
                except Exception as e:
                    print(f"(error) {e}")
                # prune pointers regardless — harmless if not present
                pruned = 0
                for bid, b in world._bindings.items():
                    eng = getattr(b, "engrams", None)
                    if not isinstance(eng, dict):
                        continue
                    for slot, val in list(eng.items()):
                        if isinstance(val, dict) and val.get("id") == eid:
                            try:
                                del eng[slot]
                                pruned += 1
                            except Exception:
                                pass
                print(("Deleted" if ok else "Engram not found or not deleted") + f". Pruned {pruned} pointer(s).")
                deleted_any = deleted_any or ok

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "31":
            # Attach an existing engram id to a binding (creates/overwrites a slot)
            print("Selection: Attach an existing engram id to a binding (creates/overwrites a slot) ")
            print('''

Attach an existing engram id (eid) to a binding id (bid).
-this will create a new slot for that eid or overwrite an existing slot with same eid
-multiple slots and engram pointers possible, of course, on a given binding
-it is possible to create dangling pointers that point to non-existing engrams that
   you entered, but they can be removed via the Delete menu option

            ''')

            bid = input("Binding id: ").strip()
            if not (bid.lower().startswith("b") and bid[1:].isdigit()):
                print("Please enter a binding id like b3.")
                loop_helper(args.autosave, world, drives, ctx); continue
            eid = input("Engram id to attach: ").strip()
            if not eid:
                print("No engram id provided.")
                loop_helper(args.autosave, world, drives, ctx); continue

            # Choose slot (column name)
            slot = input("Column slot name (default: column01): ").strip() or "column01"

            # Existence check is optional; we’ll warn but still allow.
            try:
                _ = world.get_engram(engram_id=eid)
                exists = True
            except Exception:
                exists = False
            if not exists:
                print("(warn) engram id not found in column memory; attaching pointer anyway.")

            b = world._bindings.get(bid)
            if not b:
                print(f"Unknown binding id: {bid}")
                loop_helper(args.autosave, world, drives, ctx); continue
            if getattr(b, "engrams", None) is None or not isinstance(b.engrams, dict):
                b.engrams = {}
            b.engrams[slot] = {"id": eid, "act": 1.0}
            print(f"Attached engram {eid} to {bid} as {slot}.")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        #elif "32"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        elif choice == "33":
            print("Selection:  LOC by Directory (Python)")
            print("\nPrints Python line counts by top-level directory")
            print("-physical_LOC counts all lines in .py files, including comments, docstrings, menu text, and blanks")
            print("-nonblank_LOC excludes blank lines")
            print("-code_like_LOC excludes blank lines and full-line comments, but still includes docstrings/multiline strings")
            print("-will not count code in .bak files, configuration files, typedown docs, etc.")
            print("-will search through current working directory and all of its subdirectories")
            print("-'tests' is the subdirectory of pytest unit tests")
            print("\nPlease wait.... searching through directories and counting Python lines....\n")

            rows, total, err = _compute_loc_by_dir()
            if err:
                print(err)  # pragma: no cover
            else:
                print(_render_loc_by_dir_table(rows, total))  # pragma: no cover
            # also show the .py files in the *current* working directory (not subdirectories)
            try:
                entries = os.listdir(".")
                py_files = [
                    name for name in entries
                    if name.endswith(".py") and os.path.isfile(name)
                ]
                if py_files:
                    py_files_sorted = sorted(py_files)
                    print("\nThe following Python .py files are in the current working directory:")
                    print("  " + ", ".join(py_files_sorted))
                else:
                    print("\nNo Python .py files were found in the current working directory.")
            except Exception as e:
                print(f"\n[warn] Could not list .py files in current directory: {e}")
            #does not call loop_helper(...) since no autosave here, it is a read-only menu selection


        #----Menu Selection Code Block------------------------
        elif choice == "35":
            # Verbose teaching mode: one closed-loop cycle using the same engine as Menu 37.
            print("Selection: Run 1 Cognitive Cycle (verbose teaching mode)\n")
            print("""What is a cognitive cycle? (page 1 of 4)
-----------------------------------------

A cognitive cycle ("cog cycle", "cycle") is one complete
perceive-update-decide-act loop between an agent (for example, a goat,
chimpanzee, human, or robot) and its environment.

(Technical note: CCA8 cognitive cycles are recurrently linked, i.e., results of
earlier computations may feed into later computations. Also, not every cognitive
cycle necessarily produces an external action.

In CCA8, "update" is a first-class cognitive step. Observations do not simply
pass downstream toward action selection -- they revise a persistent internal
model of the world. This update is broader than conventional robotic state
estimation and also extends beyond the primarily predictive world models
commonly discussed in AI. It maintains identity, evidence status, uncertainty,
continuity, relationships, and other cognitively meaningful structure.)\n""")
            input("Press Enter for page 2 of 4...\n\n")

            print("""How CCA8 implements the cycle (page 2 of 4)
--------------------------------------------

The agent's brain or control system is represented by the CCA8 cognitive
architecture. CCA8 receives evidence from the environment ("perceive"), updates
its internal representations of SELF and the world ("update"), selects an
appropriate response ("decide"), and dispatches that result ("act"). The result
may be an external action, an internal feedback result for later reprocessing,
or an explicit null external output. CCA8 then begins the next cognitive cycle.

CCA8 is map-first. Its internal model is organized primarily through Navigation
Maps ("NavMaps"). A NavMap is more than a geometric map -- it can represent SELF
and other entities, their locations and relationships, identity and continuity,
evidence status, and uncertainty. New evidence updates these representations,
which then inform subsequent cognition and behavior.

At a high level, one cognitive cycle will:
  1) --> Let the simulated environment (or the real world in robotics)
          report what the agent is sensing now -->
  2) Update internal NavMaps using that evidence and compare the resulting
        state with what was expected -->
  3) Record any mismatch as a prediction-error or residual signal -->
  4) Select a behavioral primitive, let the Navigation Module apply it to the
        current Working Navigation Map, and dispatch the resulting action,
        feedback, or null external output -->
     REPEAT

Action_n is selected and dispatched during Cognitive Cycle_n. Its consequences
are observed later as part of Observation_(n+1).\n""")
            input("Press Enter for page 3 of 4...\n\n")

            print("""How to read this terminal output, i.e., demonstration (page 3 of 4)
--------------------------------------------------------------------

This demonstration uses short bracketed labels:

        [teach]       explanation for the human reader
        [env...]      evidence or events from the simulated environment
        [navmap...]   NavMap update, matching, or comparison diagnostics
        [controller]  primitive/policy-selection or action information
        [cycle]       compact end-of-cycle summary

These labels organize terminal output. They are to help you understand what is
happening. They are not supposed to be names of separate CCA8 modules.

Terminology Note
----------------
In the published CCA literature, primitive-selection machinery chooses a
Working Primitive, and the Navigation Module applies it to the current Working
Navigation Map. In the current Python implementation, the corresponding runtime
behavior is often called a "policy," and the selection/dispatch machinery is
often called the "Action Center." The [controller] label covers diagnostics from
this path but note that "controller" is not the published name of a separate CCA module.

During the first cycle there may be no previous action, expectation, or outcome,
so some fields may say "missing" or "incomplete." This is normal.

On a first run, you should follow:
    observation -> NavMap update -> primitive/policy -> dispatched result
                -> later outcome

At each stage you should ask:
  1) What information exists?
  2) Which structure currently has authority?
  3) What caused the next computation or action?\n""")
            input("Press Enter for page 4 of 4...\n\n")

            print("""Optional detail: How NavMaps are matched (page 4 of 4)
-------------------------------------------------------

Incoming sensory evidence and cognitively meaningful intermediate results are
represented in map-like form and compared with stored NavMaps. Matching is not
simply yes/no:
  - close and unambiguous --> reuse and update an existing NavMap
  - close but ambiguous   --> preserve several hypotheses or inspect further
  - clearly poor match    --> create a new NavMap candidate
  - safety-critical contradiction
                           --> immediately reconsider the current context

For example, another view of a familiar tree may update an existing tree
NavMap. A never-before-seen automobile may require a new candidate. A large
bushy shrub may remain ambiguous until more evidence is available.

Predictions can help CCA8 interpret noisy or incomplete evidence. However,
strong, persistent, or safety-critical differences must not be forced to fit an
expectation, but they may instead trigger an alternative or new NavMap
interpretation.

In this demonstration, cutoffs for similarity scores obtained between
incoming and stored NavMap fragments:
  - exact content signature
        --> reuse_exact
  - best score >= 0.85 and lead over second-best >= 0.05
        --> commit to the best existing interpretation
  - best score >= 0.85 and lead over second-best < 0.05
        --> ambiguous
  - best score < 0.85
        --> unknown / novel
Here, "lead" means the best score minus the second-best score. These cutoffs are
arbitrary implementation defaults, not universal cognitive constants.

***The output below may scroll quickly. After it stops, SCROLL upward to read
   the complete cognitive-cycle trace.***\n""")
            input("Press Enter to begin the demonstration cognitive cycle...")
            print('\n\nSTART COGNITIVE CYCLE')
            print('=====================\n')

            try:
                run_env_closed_loop_steps(
                    env,
                    world,
                    drives,
                    ctx,
                    POLICY_RT,
                    1,
                    teaching_mode=True,
                )
            except Exception as e:
                print(f"[env-loop] error while running 1 verbose closed-loop step: {e}")

            loop_helper(args.autosave, world, drives, ctx)

        #----Menu Selection Code Block------------------------
        elif choice == "36":
            # Toggle mini-snapshot on/off
            ctx.mini_snapshot = not getattr(ctx, "mini_snapshot", False)
            state = "ON" if ctx.mini_snapshot else "OFF"
            print(f"Selection: Toggle ON/OFF mini-snapshot switch to a new position of: {state}")
            print("(if ON: will print a mini-snapshot after running the code of most menu selections, including this one)")
            print("(if OFF: will not print a mini-snapshot after each menu selection)\n")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "37":
            # Multi-step environment closed-loop run
            print("Selection: Run n Cognitive Cycles (closed-loop timeline)\n")
            print("""This selection runs several consecutive closed-loop cognitive cycles between the
HybridEnvironment (newborn-goat world) and the CCA8 brain.

For each cognitive cycle we will:
  1) Advance controller_steps for this Action Center invocation,
  2) Consume one current EnvObservation (reset output or a buffered later observation),
  3) Process that observation through BodyMap, WNM, memory, and policy selection,
  4) Produce and dispatch Action_n (or an explicit null output) during CognitiveCycle_n,
  5) Buffer Observation_(n+1) for processing in the next cognitive cycle.

Main Menu #1 option 1 runs one cycle in verbose teaching mode.
Main Menu #1 option 2 runs the compact multi-cycle timeline.
""")
            print("[policy-selection] Candidates = dev_gate passes AND trigger(...) returns True.")
            print("[policy-selection] Winner = highest deficit → non_drive → (RL: q | non-RL: stable order).")
            print("[policy-selection] RL adds exploration: epsilon picks a random candidate; otherwise we exploit the winner logic above.\n")

            # Ask the user for n
            try:
                n_text = input("How many closed-loop cognitive cycle(s) would you like to run? [default: 5]: ").strip()
            except Exception:
                n_text = ""
            try:
                n_steps = int(n_text) if n_text else 5
            except ValueError:
                n_steps = 5

            if n_steps <= 0:
                print("[env-loop] N must be ≥ 1; nothing to do.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            run_env_closed_loop_steps(env, world, drives, ctx, POLICY_RT, n_steps)

            print()
            print("\n[skills-hud] Learned policy values after env-loop:")
            print("(terminology: hud==heads-up-display; exec==actual primitive executions; updates==all q/EMA learning updates;")
            print("  rate==successful executions / executions; last_exec==latest execution reward;")
            print("  last_update==latest reward sample, including prediction-error shaping; q==learned value estimate;")
            print("  EMA==exponential moving average of rewards; q_new = (1-alpha_smoothing_factor)*q_old + alpha*reward (alpha ~0.3))")
            print("(if RL=enabled, epsilon is theoretical % times to choose randomly, 'explore_rate' is measured % of random choices;")
            print("   delta=0 then q used only for exact ties otherwise deficit values within delta range are considered tied and q used to decide)")
            print("NOTE: deficit here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD) (amount ABOVE threshold, not a negative deficit).")
            print("Policies without a drive-urgency term score 0.00 and will tie-break by stable policy order (or RL tie-break, if enabled)")

            print(skills_hud_text(ctx, top_n=8))
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "51":
            # Isolated autonomous newborn survival demo
            print("Selection: Autonomous newborn survival demo\n")
            print("""This runs an isolated hard-mode newborn-goat sandbox.

It does NOT mutate the current interactive WorldGraph/session.
It reuses the same closed-loop engine as Menu 37, but with a fresh sandbox runtime.

Goal:
    fallen -> stand -> follow mom -> find/latch nipple -> suckle -> milk drinking -> rest

This baseline demo disables observation masking and route-loss stress. Main Menu #8 remains the
right place for harder A/B/C stress tests.
""")

            try:
                raw_cycles = input("Max cognitive cycles [default: 60]: ").strip()
            except Exception:
                raw_cycles = ""

            try:
                max_cycles = int(raw_cycles) if raw_cycles else 60
            except Exception:
                max_cycles = 60
            max_cycles = max(1, min(500, max_cycles))

            try:
                raw_show = input("Print full cycle timeline? [Y/n]: ").strip().lower()
            except Exception:
                raw_show = ""
            show_timeline = raw_show not in ("n", "no")

            result = run_autonomous_newborn_survival_demo_v1(
                max_cycles=max_cycles,
                show_timeline=show_timeline,
            )

            print()
            for line in render_autonomous_newborn_survival_demo_lines_v1(result):
                print(line)

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "38":
            # Inspect BodyMap summary
            print("Selection:  BodyMap Inspect\n")
            print("Shows a one-line summary derived from body_* helpers plus zone classification.\n")

            if ctx is None:
                print("Ctx is not available.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            try:
                bp = body_posture(ctx)
                md = body_mom_distance(ctx)
                ns = body_nipple_state(ctx)
                try:
                    sd = body_shelter_distance(ctx)
                except Exception:
                    sd = None
                try:
                    cd = body_cliff_distance(ctx)
                except Exception:
                    cd = None

                try:
                    zone = body_space_zone(ctx)
                except Exception:
                    zone = None

                print("BodyMap one-line summary:")
                line = (
                    f"  posture={bp or '(n/a)'} "
                    f"mom={md or '(n/a)'} "
                    f"nipple={ns or '(n/a)'} "
                    f"shelter={sd or '(n/a)'} "
                    f"cliff={cd or '(n/a)'}"
                )
                if zone is not None:
                    line += f"  zone={zone}"
                print(line)
            except Exception as e:
                print(f"[bodymap] inspect error: {e}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "39":
            # Spatial scene demo: what is NOW near + resting-in-shelter?
            print("Selection:  Spatial Scene Demo\n")
            print("Shows which bindings are NOW-near and whether we are in a 'resting in shelter, cliff far' scene.\n")

            # Part 1: what is NOW near?
            try:
                near_ids = neighbors_near_self(world)
                if not near_ids:
                    print("NOW-near neighbors: (none)")
                else:
                    print("NOW-near neighbors:")
                    for bid in near_ids:
                        b = world._bindings.get(bid)
                        tags = ", ".join(sorted(getattr(b, "tags", []) or [])) if b else ""
                        print(f"  {bid}: [{tags}]")
                print()
            except Exception as e:
                print(f"[spatial] neighbors_near_self error: {e}\n")

            # Part 2: are we resting in shelter with cliff far?
            try:
                summary = resting_scenes_in_shelter(world)
                print("Resting-in-shelter scene summary (around NOW):")
                print(f"  rest_near_now:             {summary.get('rest_near_now')}")
                print(f"  shelter_near_now:          {summary.get('shelter_near_now')}")
                print(f"  hazard_cliff_far_near_now: {summary.get('hazard_cliff_far_near_now')}")
                sbids = summary.get("shelter_bids") or []
                if sbids:
                    print("  shelter_bids (NOW --near--> ...):")
                    for bid in sbids:
                        b = world._bindings.get(bid)
                        tags = ", ".join(sorted(getattr(b, 'tags', []) or [])) if b else ""
                        print(f"    {bid}: [{tags}]")
                else:
                    print("  shelter_bids: (none)")
            except Exception as e:
                print(f"[spatial] resting_scenes_in_shelter error: {e}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "40":
            cca8_session_menu.configure_episode_starting_state_v1(drives, ctx)
            loop_helper(args.autosave, world, drives, ctx)

        #----Menu Selection Code Block------------------------
        elif choice == "41":
            cca8_session_menu.show_retired_memory_pipeline_guide_v1()
            loop_helper(args.autosave, world, drives, ctx)

        #----Menu Selection Code Block------------------------
        elif choice == "42":
            print("Selection: Configure goat_foraging_04 contextual map-switch evaluation\n")
            print("This configures a repeatable evaluation run where the coarse geometry stays simple")
            print("but the context alternates (fox ↔ hawk), so WorkingMap↔Column retrieval must")
            print("switch on contextual cues rather than gross terrain alone.\n")

            try:
                configure_goat_foraging_04_eval_v1(world, drives, ctx, env)
                print("Configured goat_foraging_04.")
                print("  - env.config.scenario_name = 'goat_foraging_04'")
                print("  - milestone-driven keyframes ON")
                print("  - WorkingMap/Column auto-retrieve ON (merge mode)")
                print("  - the next Main Menu #1 option 1/2 run will start a fresh goat_foraging_04 episode")
            except Exception as e:
                print(f"[goat04] configuration error: {e}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "43":
            print("Selection: WorkingMap snapshot\n")

            if getattr(ctx, "working_world", None) is None:
                ctx.working_world = init_working_world()

            raw_n = input("Show last N bindings (default=15): ").strip()
            n = 15
            if raw_n:
                try:
                    n = max(1, int(float(raw_n)))
                except ValueError:
                    pass

            print_working_map_layers(ctx)
            print()
            print_working_map_entity_table(ctx)
            print()
            print_working_map_snapshot(ctx, n=n)

            # Dump MapSurface (MapEngram payload v1) — this is the exact snapshot we will later store into Column memory.
            try:
                payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)
                txt = json.dumps(payload, indent=2, ensure_ascii=False)
                print()
                print("[workingmap] MapSurface payload (wm_mapsurface_v1; JSON-safe)")
                print(txt)
            except Exception as e:
                print()
                print(f"[workingmap] MapSurface payload dump failed: {e}")

            print("\n[workingmap] Read-only view. To clear WorkingMap, use Main Menu #6 -> Clear the current WorkingMap.")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "44":
            #  Store WorkingMap MapSurface snapshot (Column + WG pointer)
            print("Selection: Store WorkingMap MapSurface snapshot (Column + WG pointer)\n")
            info = store_mapsurface_snapshot_v1(world, ctx, reason="manual_menu44", attach="now", force=False, quiet=False)
            if info.get("stored"):
                print(f"OK: stored. sig={info.get('sig','')[:16]} bid={info.get('bid')} engram_id={info.get('engram_id','')}")
            else:
                print(f"SKIP: {info.get('why','(no reason)')}. sig={info.get('sig','')[:16]}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "45":
            print("Selection: List recent wm_mapsurface engrams (Column)\n")

            raw_n = input("How many recent MapSurface engrams? (default=10): ").strip()
            n = 10
            if raw_n:
                try:
                    n = max(1, int(float(raw_n)))
                except ValueError:
                    pass

            # Traverse column memory from newest to oldest; filter by record name.
            rows = []
            try:
                ids = list(column_mem.list_ids())
                for eid in reversed(ids):
                    rec = column_mem.try_get(eid)
                    if not isinstance(rec, dict):
                        continue
                    if rec.get("name") != "wm_mapsurface":
                        continue
                    rows.append(rec)
                    if len(rows) >= n:
                        break
            except Exception:
                rows = []

            if not rows:
                print("(none) No wm_mapsurface engrams found in column memory yet.")
                print("Tip: use Main Menu #6 to store a MapSurface, or Main Menu #1 option 2 to reach a stage/zone boundary.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            print(f"Recent wm_mapsurface engrams (newest first; n={len(rows)}):")
            for i, rec in enumerate(rows, start=1):
                eid = str(rec.get("id", ""))
                meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
                attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}

                created_at = meta.get("created_at") or "(n/a)"
                stage = attrs.get("stage") or "(n/a)"
                zone  = attrs.get("zone") or "(n/a)"
                sig   = attrs.get("sig") or ""
                sal = attrs.get("salience_sig") or ""
                sal_txt = f" sal={str(sal)[:12]}" if sal else ""

                links = meta.get("links")
                src = links[0] if isinstance(links, list) and links else None
                src_txt = f" src={src}" if isinstance(src, str) else ""
                sig_txt = f" sig={str(sig)[:12]}" if sig else ""

                print(f"  {i:2d}) {eid[:8]}… created={created_at} stage={stage} zone={zone}{sig_txt}{src_txt} {sal_txt}")

            print("\nTip: use Main Menu #2 -> Memory Stores & WorldGraph State -> Inspect one engram.")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "46":
            print("Selection: Pick best wm_mapsurface engram for current stage/zone (read-only)\n")

            stage = getattr(ctx, "lt_obs_last_stage", None)
            stage = stage if isinstance(stage, str) else None

            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None
            zone = zone if isinstance(zone, str) else None

            raw_k = input("Show top K candidates (default=5): ").strip()
            k = 5
            if raw_k:
                try:
                    k = max(1, int(float(raw_k)))
                except Exception:
                    k = 5

            print(f"[wm-retrieve] want stage={stage!r} zone={zone!r} (top_k={k})")
            info = pick_best_wm_mapsurface_rec(stage=stage, zone=zone, ctx=ctx, long_world=world, allow_fallback=True, top_k=k)

            if not info.get("ok"):
                print("(none) No wm_mapsurface engrams found for retrieval.")
                print("Tip: use Main Menu #1 option 2 to auto-store keyframes, or Main Menu #6 to store manually.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            print(f"[wm-retrieve] candidate_source={info.get('source')} match_tier={info.get('match')}")
            print(
                f"[wm-retrieve] want_sal={str(info.get('want_salience_sig') or '')[:12]} "
                f"want_pred_n={info.get('want_pred_n')} want_cue_n={info.get('want_cue_n')}"
            )

            ranked = info.get("ranked", [])
            if isinstance(ranked, list) and ranked:
                print("\nTop candidates (winner marked with '*'):")
                for i, c in enumerate(ranked, start=1):
                    if not isinstance(c, dict):
                        continue
                    star = "*" if i == 1 else " "
                    eid = str(c.get("engram_id", ""))
                    created = c.get("created_at") or "(n/a)"
                    st = c.get("stage") or "(n/a)"
                    zn = c.get("zone") or "(n/a)"
                    src = c.get("src")
                    src_txt = f" src={src}" if isinstance(src, str) else ""
                    sig = str(c.get("sig") or "")[:12]
                    sal = str(c.get("salience_sig") or "")[:12]
                    score = float(c.get("score", 0.0) or 0.0)
                    op = int(c.get("overlap_preds", 0) or 0)
                    oc = int(c.get("overlap_cues", 0) or 0)
                    print(
                        f" {star}{i:2d}) {eid[:8]}… score={score:6.1f} op={op:2d} oc={oc:2d} "
                        f"stage={st} zone={zn} sig={sig} sal={sal} created={created}{src_txt}"
                    )

            # Winner summary (same info as before)
            rec = info.get("rec")
            rec = rec if isinstance(rec, dict) else None
            if rec is not None:
                eid = str(rec.get("id", ""))
                meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
                attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}
                created_at = meta.get("created_at") or "(n/a)"
                links = meta.get("links")
                src = links[0] if isinstance(links, list) and links else None

                print("\n[wm-retrieve] winner:")
                print(f"  engram={eid[:8]}… created_at={created_at} stage={attrs.get('stage')!r} zone={attrs.get('zone')!r}")
                if isinstance(src, str):
                    print(f"  src(binding)={src}")
                print(
                    f"  score={info.get('score')} "
                    f"overlap_preds={info.get('overlap_preds')}/{info.get('want_pred_n')} "
                    f"overlap_cues={info.get('overlap_cues')}/{info.get('want_cue_n')}"
                )

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "47":
            print("Selection: Load wm_mapsurface engram into WorkingMap (replace OR merge/seed)\n")

            raw = input("Engram id to load (blank = pick best for current stage/zone): ").strip()
            if not raw:
                stage = getattr(ctx, "lt_obs_last_stage", None)
                stage = stage if isinstance(stage, str) else None
                try:
                    zone = body_space_zone(ctx)
                except Exception:
                    zone = None
                zone = zone if isinstance(zone, str) else None

                info = pick_best_wm_mapsurface_rec(stage=stage, zone=zone, ctx=ctx, long_world=world, allow_fallback=True, top_k=5)
                rec = info.get("rec")
                rec = rec if isinstance(rec, dict) else None
                if not (info.get("ok") and rec):
                    print("(none) No wm_mapsurface engrams available to load.")
                    loop_helper(args.autosave, world, drives, ctx)
                    continue
                raw = str(rec.get("id", "")).strip()

            mode_txt = input("Load mode: [R]eplace / [M]erge-seed (default R): ").strip().lower()
            mode = "merge" if mode_txt.startswith("m") else "replace"

            out = load_wm_mapsurface_engram_into_workingmap_mode(ctx, raw, mode=mode)
            if not out.get("ok"):
                print(f"(failed) load: {out.get('why','unknown')}")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            if out.get("mode") == "merge":
                guard_ok = out.get("merge_guardrail_ok")
                cue_delta = out.get("cue_tag_delta")
                if guard_ok is True:
                    guard_txt = " cue_guard=ok"
                elif guard_ok is False:
                    try:
                        d_i = int(cue_delta) if cue_delta is not None else None
                    except Exception:
                        d_i = None
                    if isinstance(d_i, int):
                        guard_txt = f" cue_guard=leak(+{d_i})"
                    else:
                        guard_txt = " cue_guard=leak"
                else:
                    guard_txt = ""

                print(
                    f"[wm-retrieve] merged engram={raw[:8]}… into WorkingMap: "
                    f"added_entities={out.get('added_entities')} filled_slots={out.get('filled_slots')} "
                    f"added_edges={out.get('added_edges')} stored_prior_cues={out.get('stored_prior_cues')}"
                    f"{guard_txt}"
                )
                print("Tip: use Main Menu #2 -> Current Cognition & Control State -> WorkingMap to inspect; then run one environment step.")
            else:
                print(f"[wm-retrieve] replaced WorkingMap from engram={raw[:8]}…: entities={out.get('entities')} relations={out.get('relations')}")
                print("Tip: use Main Menu #2 -> Current Cognition & Control State -> WorkingMap to inspect the loaded MapSurface.")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "k":
            # OpenAI / LLM setup + first CCA8 demo
            print("Selection: OpenAI / LLM API setup + first CCA8 demo\n")
            openai_menu_48_interactive(world, drives, ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "49":
            # Experiments / Benchmarks (protocol scaffolding only in patch 1)
            experiments_menu_49_interactive(ctx)
            print("Selection: xperiments / Benchmarks\n")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "50":
            # SimRobotGoat RCOS sandbox
            print("Selection: RCOS sandbox\n")
            sim_robot_goat_hal = sim_robot_goat_menu_50_interactive(sim_robot_goat_hal)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "s":
            # Save session
            print("Selection:  Save Session\n")
            print('''
This "save session" is a manual one-shot snapshot, i.e., you are saving the session to
  a .json file you specify.

It saves the world, drives and skill data of the session to the JSON file.
-writes world.to_dict(), drives.to_dict(), skills_to_dict() along with a timestamp and version

This menu selection does not change args.autosave or anything about autosave behavior.

It is useful to checkpoint your development progress in running a simulation -- you can save the
  current session to disk at a moment you choose. Even if you have --autosave session.json option
  already set (which indeed provides robust, frequent autosaves) this manual one-shot
  save session is useful to checkpoint your simulation run at a certain point where autosave
  has not occurred at that moment yet, or if you want a save to a different file location without
  changing your autosave setup.


Brief Recap of --autosave session.json (i.e., NOT this current menu selection)
-------------------------------------------------------------------------------
-the flag "--autosave" should work with Windows, Linux and macOS since we use the argparse library,
    with the OS just passing the flag as text to Python and Python handling the rest
>python cca8_run.py --autosave session.json
    -see on display: "[io] Started a NEW session. Autosave ON to 'session.json'."
    -new empty WorldGraph and Drives are created
    -after most menu actions, loop_helper(args.autosave, world, drives, ctx) calls
      save_session("session.json", world, drives)
    -the session.json is fully rewritten each time, i.e., a current state snapshot is written
    -if you crash or ctl-C you can later restart from session.json using --load
    -reset menu option only works if --autosave was used, in which case it will delete the current
      autosave file and reinitialize a fresh one
-if "--autosave mysession.json"is being used, you really don't need this menu option "save session"
    unless special case such as obtaining specific checkpoint, writing to a different file, etc.
-note: file saving is via JSON so .json file extension should be used, but any extension will actually work as long
    as the file is json format and load in using the same file extension name
-IMPORTANT - note that each time an "autosave session.json" occurs the contents of the "session.json" file are
  not appended with new information, but overwritten, i.e., the old "session.json" file is effectively deleted


Brief Recap of --load session.json (i.e., NOT this current menu selection)
--------------------------------------------------------------------------
-the flag "--load" should work with Windows, Linux and macOS since we use the argparse library,
  with the OS just passing the flag as text to Python and Python handling the rest
>python cca8_run.py --load session.json
    -see on display:
        "[io] Loaded 'session1.json'. Autosave OFF"
        "[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>."
    -it reads session1.json (world, drives, skills) and reconstructs that state
    -no autosave is automatically active unless you also specify --autosave file_to_save.json
    -after loading a saved file, you can modify it in memory -- it will not be written back, i.e., saved,
        unless you specifically used a --save session.json flag or else use this menu selection "Save Session"
-make changes and select: "Save session"  --> newer_session.json
-then quit
-then load session1.json and examine, then quit; then load newer_session.json -- changes in appropriate json files

>python cca8_run.py --load nonexistent.json
    -see on display: "[io] Started a NEW session. Autosave OFF — use menu selection Save Session"
                               "or relaunch with --autosave <path>."
-can load a session while in the middle of another one; if no one-shot save or autosave then lose that session
    -in middle of a session and then menu select "Load Session"
    -will see on the display:
        "Loads a prior JSON snapshot (world, drives, skills). The new state replaces the current one."
        "Load from file: session1.json"
        "Loaded session1.json (saved_at=2025-11-20T05:35:45)"
        "[io] Loaded 'session1.json'. Autosave OFF"
        "[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>."


Brief Recap of Using Both Together (i.e., NOT this current menu selection)
--------------------------------------------------------------------------
>python cca8_run.py --load session2.json --autosave session2.json
    -effectively load from session.json and keep autosaving back to same file session.json
    -if session2.json does not exist yet you will see on the display:
            "[io] Started a NEW session. Autosave ON to 'session2.json'."
    -if session2.json exists from saving a previous time, you will see on the display:
            "[io] Loaded 'session2.json'. Autosave ON to the same file — state will be saved in-place "
            "  after each action. (the file is fully rewritten on each autosave)."

>python cca8_run.py --load session2.json --autosave new_session5.json
    -effectively start from this saved snapshot but then autosave new work to another file new_session5.json
    -see on display:
        "[io] Loaded 'session2.json'. Autosave ON to 'new_session5.json' — new steps will be written to the autosave file;"
           "the original load file remains unchanged."
-continue with this example; quit and then restart as:
>python cca8_run.py --autosave new_session5.json --load session2.json
    -order of --autosave and --load does not matter
    -new_session5.json is not a new file but an existing one, thus will be overwritten
    -see on display:
        "[io] Loaded 'session2.json'. Autosave ON to 'new_session5.json' — new steps will be written to the autosave file;"
           "the original load file remains unchanged."


Brief Recap of this current Menu Selection: "Save Session"
----------------------------------------------------------
-Again, this current menu selection "save session" is a manual one-shot snapshot, i.e., you are
    saving the session to a .json file you specify.

            ''')

            path = input("Save to file (e.g., session.json): ").strip()
            #input file name to pass to save_session(...)
            if path:
                ts = save_session(path, world, drives)
                #inside save_session(...):
                #with open(tmp, "w", encoding="utf-8") as f:
                #        json.dump(data, f, indent=2, ensure_ascii=False)
                #-ts is datetime.now()
                #-data =dict {ts, world.to_dict(), drives.to_dict(), skills_to_dict(), version, platform}
                #-note: don't write "open(path, "w"...)" since "w" will truncate the existing file to length 0 and then start writing
                #       thus write to a temporary file, make sure no crashes, and then os.replace(tmp, path)
                print(f"Saved to {path} at {ts}")


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "l":
            # Load session
            print("Selection: Load Session\n")
            print('''
[Note: If you don't have knowledge of what --load, --autosave, Load, Save selections do, then see
  Menu Selection "Save Session" or else see README.md Documentation for a quick recap of these. ]

This "load session" is a manual one-shot load snapshot, i.e., you are retrieving the
  session from a .json file you specify. It will overwrite whatever current session you are running.

"Load Session" does not automatically write back to the file -- it just loads it.

-prompted for a filename and path
-opens and parses the JSON
-reconstructs a fresh WorldGraph and Drives from the blob via WorldGraph.from_dict(...), Drives.from_dict(...)
-restores the skills ledger via skills_from_dict(...)
-replaces the current simulation state with the loaded one -- whatever was in memory is discarded
-no autosave is triggered immediately since don't want to overwrite a file as soon as it is loaded
-next menu actions will autosave as usual if --autosave option, otherwise can use Save Session for one-shot save

            ''')

            print("Loads a prior JSON snapshot (world, drives, skills).")
            print("The current simulation in memory will be discarded so make sure it is being autosaved or else manually")
            print("  save it, if you want to preserve the current program state.\n")
            path = input("Load from file (ENTER to exit back to the menu): ").strip()
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        blob = json.load(f)
                    print(f"Loaded {path} (saved_at={blob.get('saved_at','?')})")
                    new_world  = cca8_world_graph.WorldGraph.from_dict(blob.get("world", {}))
                    new_drives = Drives.from_dict(blob.get("drives", {}))
                    skills_from_dict(blob.get("skills", {}))
                    world, drives = new_world, new_drives
                    loaded_ok = True
                    loaded_src = path
                    _io_banner(args, loaded_src, loaded_ok)
                except Exception as e:
                    print(f"[warn] could not load {path}: {e}")
            #does not call loop_helper(...) since you might not want to overwrite a file immediately after loading it


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "d":
            # Legacy Main Menu #6 compatibility route.
            print("Selection: Drives / Internal Control State\n")
            _show_drives_v1(drives)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "r":
            # Reset current saved session: explicit confirmation
            print("Selection: Reset current save session")
            print('''
This menu selection code will reset the current autosave-backed up session
 -Note that --autosave must be used (or else code will alert you to this and exit back to the menu)
This selection will delete the autosave file (if it still exists) and re-initialize new but empty WorldGraph,
  drives and skill ledger in memory.
-world = cca8_world_graph.WorldGraph()
-drives = Drives()
-skills_from_dict({}) #clear skill ledger

What has happened is the current world has been replaced with a brand-new empty WorldGraph (and fresh drives and
  skill ledger).
There will be a NOW anchore in the new WorldGraph.
Note that args.autosave is unchanged -- autosave's will still occur at the same path cca8_run.py was launched with.
However, VERY IMPORTANT, note that the autosave session.json file will be deleted as part of this reset.
By contrast, if you simply exit and later restart with >python cca8_run.py --autosave session.json, the existing file
 is not deleted; it remains on disk until the first autosave of the new run, at which point its contents
 are overwritten with the fresh session.
            ''')

            if not args.autosave:
                print("No current saved json file to reset (you did not launch with --autosave <path>).")
                print("Returning back to menu....")
            else:
                path = os.path.abspath(args.autosave)
                cwd  = os.path.abspath(os.getcwd())
                print("\n[RESET] This will:")
                print("  -Delete the autosave file shown below (if it exists), and")
                print("  -Re-initialize an empty world, drives, and skill ledger in memory.\n")
                print(f"Autosave file: {path}")
                if not path.startswith(cwd):
                    print(f"[CAUTION] The file is outside the current directory: {cwd}")
                try:
                    reply = input("Type DELETE in uppercase to confirm, or press Enter to cancel: ").strip()
                except Exception:
                    reply = ""
                if reply == "DELETE":
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                            print(f"\n1. Deleted {path}.")
                        else:
                            print(f"1. Hmmm... no file at {path} (nothing to delete).")
                    except Exception as e:
                        print(f"[warn] Could not delete {path}: {e}")
                    # Reinitialize episode state
                    world = cca8_world_graph.WorldGraph()
                    drives = Drives()
                    skills_from_dict({})  # clear skill ledger
                    world.ensure_anchor("NOW")
                    print("2. Initialized a fresh episode in memory -- fresh WorldGraph, drives and skill ledger.")
                    print("   -this is in memory now but after your next action, it will be autosaved")
                else:
                    print("Reset cancelled (nothing deleted)")
                    print("Returning back to menu....")
            continue   # back to menu
            #no loop_helper(...) -- it's a brand new WorldGraph created; autosaves will occur after next action


        #----Menu Selection Code Block------------------------
        elif choice.lower() in ("t", "architecture"):
            # Architecture explanation and documentation submenu.
            _architecture_explanation_menu_v1(POLICY_RT)
            continue
        #no loop_helper(...) -- explanatory material returns directly to the main menu

        #----Menu Selection Code Block------------------------
            ##END OF MENU SELECTION BLOCKS

    # interactive_loop(...): while loop:  END <<<<<<<<<<<<<<<<<<<  back to while loop


# --------------------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """
    Command-line entry point for the CCA8 runner.

    Responsibilities
    ----------------
    - Configure logging (file + console).
    - Parse CLI flags (about/version/load/save/autosave/preflight/profile/rcos-api/hal/body/…).
    - Handle one-shot modes:
         --version / --about → print version/component info and exit.
         --preflight         → run full unit tests + preflight probes and exit.
    - For interactive mode:
         Normalize HAL/body flags into human-readable status strings.
         Call interactive_loop(args), which runs the menu-driven CCA8 simulation.

    Args:
        argv: Optional list of CLI arguments (defaults to sys.argv[1:] when None).

    Returns:
        0 on normal success, or a non-zero exit code (e.g., preflight failures).
    """

    # set up logging (one-time)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler("cca8_run.log", encoding="utf-8"),
                      logging.StreamHandler()] )
    logging.info("cca8_run start v%s python=%s platform=%s",
                 __version__, sys.version.split()[0], platform.platform())

    try:
        _openai_quiet_http_loggers_v1()
    except Exception:
        pass

    ##argparse and processing of certain flags here
    # argparse flags
    p = argparse.ArgumentParser(prog="cca8_run.py")
    p.add_argument("--about", action="store_true", help="Print version and component info")
    p.add_argument("--version", action="store_true", help="Print just the runner (i.e., main entry program module) version")
    p.add_argument("--hal", action="store_true", help="Enable HAL embodiment stub (if available)")
    p.add_argument("--body", help="Body/robot, profile to use with HAL, e.g., 'hapty'")
    #p.add_argument("--period", type=int, default=None, help="Optional period (for tagging)")
    #p.add_argument("--year", type=int, default=None, help="Optional year (for tagging)")
    p.add_argument("--no-intro", action="store_true", help="Skip the intro banner")
    startup_mode = p.add_mutually_exclusive_group()
    startup_mode.add_argument(
        "--profile",
        choices=["goat", "chimp", "human", "super"],
        help=(
            "Select a startup profile without prompting"
        ),
    )
    startup_mode.add_argument(
        "--rcos-api",
        action="store_true",
        help="Use CCA8 as RCOS (Robot Cognitive Operationg System)",
    )
    p.add_argument("--preflight", action="store_true", help="Run full unit tests and preflight and exit")
    p.add_argument(
        "--coverage",
        action="store_true",
        help="Enable optional pure-Python coverage for a full preflight run (default: off)",
    )
    p.add_argument(
        "--timing", action="store_true",
        help="Report preflight phase times and the 20 slowest pytest phases >= 0.5 s (requires --preflight)",
    )
    #p.add_argument("--write-artifacts", action="store_true", help="Write preflight artifacts to disk")
    p.add_argument("--load", help="Load session from JSON file")
    p.add_argument("--save", help="Save session to JSON file on exit")
    p.add_argument("--autosave", help="Autosave session to JSON file after each action")

    try:
        args = p.parse_args(argv)
        if args.timing and not args.preflight:
            p.error("--timing requires --preflight")
    except SystemExit as e:
        code = getattr(e, "code", 0)
        return 2 if code else 0  # pylint: disable=using-constant-test

    # process embodiment flags and continue with code
    try:
        if args.hal:
            args.hal_status_str = "ON (however, a full R-HAL has not been implemented\n     at this time, thus software will run without consideration of the robotic embodiment)"
        else:
            args.hal_status_str = "OFF (runs without consideration of the robotic embodiment)"
        body = (args.body or "").strip()
        if body == "hapty":
            body = "0.1.1 hapty"
        args.body_status_str = f"{body if body else PLACEHOLDER_EMBODIMENT}"
    except Exception as e:
        args.hal_status_str  = f"error in flag {e} -- HAL: off (software will run without consideration of  robotic embodiment)"
        args.body_status_str = f"error in flag {e} -- Body: (none)"

    # process version flag and return
    if args.version:
        print(__version__)
        return 0

    # process about flag and return
    if args.about:
        component_rows = _cca8_component_rows()

        print("CCA8 Components:")
        print(f"    [components listed: {len(component_rows)}]")
        for label, version, path in component_rows:
            print(f"  - {label} v{version} ({path})")

        # Additionally show the number of behavioral primitives registered
        # with the controller for action selection.
        try:
            print(f"\n    [registered behavioral primitives: {len(PRIMITIVES)}]")
        except Exception:
            pass

        return 0

    # process preflight flag and return
    if args.preflight:
        rc = run_preflight_full(args)
        return rc

    # mirror terminal output to terminal.txt, overwriting the previous session each time
    # set append=True to not overwrite each session
    # comment out the line below if you don't want this feature
    install_terminal_tee("terminal.txt", append=False, also_stderr=True)

    ##main operations of program via interactive_loop()
    interactive_loop(args); return 0

# --------------------------------------------------------------------------------------
# __main__
# --------------------------------------------------------------------------------------
# Standard Python entry point:
# When this file is executed as a script (e.g., `python cca8_run.py`),
# run main(...) and propagate its return code as the process exit status.
if __name__ == "__main__":
    sys.exit(main())
