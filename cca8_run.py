#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
*************************************

Software was developed in a Windows environment but should run with minimal changes in a macOS or Linux environment.
Requires Python 3.11
Please contact hschneidermd [at] alum [dot] mit [dot] edu for inquiries about additional software modules, related
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
- Python 3.11.
- All CCA8 Python modules in the same repo directory, including:
  cca8_world_graph.py, cca8_controller.py, cca8_temporal.py,
  cca8_column.py, cca8_features.py, cca8_env.py, cca8_navpatch.py,
  cca8_rcos.py, cca8_rcos_experiments.py, cca8_state_integrity.py,
  cca8_teaching.py, cca8_test_fixtures.py, cca8_context.py, cca8_cli.py,
  cca8_experiments.py, cca8_openai.py, cca8_working_memory.py, cca8_profiles.py,
  cca8_guidance.py, and cca8_preflight.py.
- Standard-library imports such as argparse, json, hashlib, os, platform,
  sys, logging, math, datetime, dataclasses, typing, collections, random,
  time, subprocess, shutil, io, contextlib, copy, tempfile, webbrowser,
  xml, and ctypes are included with a normal Python installation.

Optional PyPI packages used by menu features / development workflow:
- pygount: Menu 33 lines-of-code report.
- pyvis: interactive graph export / display.
- psutil: optional richer system-memory check during preflight.
- openai: Menu 48 LLM API setup and hybrid adviser experiments.
- pytest: unit-test runner used by --preflight.
- pytest-cov: optional coverage integration for pytest.
- pylint: external lint command used during development.
- mypy: external static type checker used during development.

Recommended setup on a fresh Windows Python 3.11 environment:
    py -m pip install --upgrade openai pyvis pygount psutil pytest pytest-cov pylint mypy

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
from dataclasses import dataclass
from typing import Optional, Any, Dict, List, Callable
from collections import defaultdict
import random

# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
#import cca8_world_graph as wgmod  # modular alternative: allows swapping WorldGraph engines
import cca8_cli
import cca8_guidance
import cca8_profiles
import cca8_experiments
import cca8_openai
import cca8_working_memory
import cca8_world_graph
from cca8_controller import (
    PRIMITIVES,
    skill_readout,
    skill_q,
    update_skill,
    skills_to_dict,
    skills_from_dict,
    HUNGER_HIGH,
    FATIGUE_HIGH,
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
from cca8_temporal import TemporalContext
from cca8_column import mem as column_mem
from cca8_env import HybridEnvironment, EnvObservation, EnvConfig  # environment simulation (HybridEnvironment/EnvState/EnvObservation)
from cca8_navmap import (
    make_navmap_payload_v1,
    make_navmap_transition_v1,
    navmap_observation_update_from_env_obs_v1,
    navmap_policy_outcome_from_transition_v1,
    navmap_residual_v1,
)
from cca8_rcos import (
    SIM_ROBOT_GOAT_COMMANDS,
    SimRobotGoatHAL,
)
from cca8_context import CreativeCandidate, Ctx, ExperimentProtocolConfig
from cca8_teaching import (
    menu37_teaching_after_controller_v1,
    menu37_teaching_after_observation_v1,
    menu37_teaching_after_run_v1,
    menu37_teaching_cycle_header_v1,
    menu37_teaching_intro_v1,
)
from cca8_predictive import (
    compare_prediction_to_observed,
    legacy_error_vector_v0,
    make_posture_prediction_record,
)
import cca8_preflight  # pylint: disable=wrong-import-order

# --- Public API index, version, global variables and constants ----------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.9.0"
__all__ = [
    "main",
    "interactive_loop",
    "run_preflight_full",
    "snapshot_text",
    "prediction_feedback_summary_v1",
    "prediction_next_record_from_policy_posture_v1",
    "prediction_pending_record_from_ctx_v1",
    "prediction_compare_pending_to_observed_v1",
    "prediction_feedback_step_from_ctx_obs_v1",
    "prediction_policy_expected_slots_v1",
    "prediction_record_with_expected_slots_v1",
    "prediction_error_history_append_v1",
    "prediction_error_record_apply_to_ctx_v1",
    "render_prediction_feedback_lines_v1",
    "prediction_feedback_mini_line_v1",
    "export_snapshot",
    "world_delete_edge",
    "boot_prime_stand",
    "save_session",
    "versions_dict",
    "versions_text",
    "choose_contextual_base",
    "compute_foa",
    "candidate_anchors",
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
_open_readme_tutorial = cca8_profiles.open_readme_tutorial
print_tagging_and_policies_help = cca8_guidance.print_tagging_and_policies_help


def _profile_runtime_v1() -> ProfileRuntime:
    """Build profile-demo operations from current runner-visible dependencies."""
    return ProfileRuntime(
        world_factory=cca8_world_graph.WorldGraph,
        world_from_dict=cca8_world_graph.WorldGraph.from_dict,
        drives_factory=Drives,
        action_center_step=action_center_step,
    )


def profile_human_multi_brains(ctx: Any, world: Any) -> tuple[str, float, float, int]:
    """Run the extracted multi-brain profile scaffold through current runner dependencies."""
    return cca8_profiles.profile_human_multi_brains(ctx, world, runtime=_profile_runtime_v1())


def profile_society_multi_agents(ctx: Any) -> tuple[str, float, float, int]:
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
        hamming_hex64=_hamming_hex64,
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
#       - Ctx: mutable runtime state (soft temporal clock, ticks, age_days, controller_steps, cog_cycles, etc.).
#   • Graph / edge helpers:
#       - world_delete_edge(...), delete_edge_flow(...): engine + CLI helpers for removing edges.
#       - Spatial stubs: _maybe_anchor_attach(...), add_spatial_relation(...).
#   • Persistence & versioning:
#       - save_session(...): atomic JSON snapshot of (world, drives, skills).
#       - _module_version_and_path(...), versions_dict(), versions_text(): component versions + paths.
#   • Embodiment stub:
#       - HAL: hardware abstraction layer skeleton for future robot embodiments.
#   • Policy runtime:
#       - PolicyGate, PolicyRuntime, CATALOG_GATES: controller gate catalog and runtime gate evaluation.
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
#       - snapshot_text(...), export_snapshot(...), recent_bindings_text(...):
#           snapshot and export of the live WorldGraph, CTX, and policies.
#       - timekeeping_line(...), print_timekeeping_line(...), _snapshot_temporal_legend(...):
#           soft-clock / epoch / cosine one-line summaries and legend.
#       - drives_and_tags_text(...), skill_ledger_text(...): drives panel + skill ledger explainers.
#       - _resolve_engrams_pretty(...), _bindings_pointing_to_eid(...), _engrams_on_binding(...):
#           engram pointer inspection utilities.
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

def init_body_world() -> tuple[cca8_world_graph.WorldGraph, dict[str, str]]:
    """
    Initialize a tiny BodyMap as a separate WorldGraph instance.

    Nodes (v1.1):
      - ROOT      (anchor:BODY_ROOT) — body as a whole
      - POSTURE   (pred:posture:*)   — overall posture
      - MOM       (pred:proximity:mom:*)      — mom distance relative to body
      - NIPPLE    (pred:nipple:* / pred:milk:drinking) — nipple/latch state
      - SHELTER   (pred:proximity:shelter:*)  — shelter distance relative to body
      - CLIFF     (pred:hazard:cliff:*)       — dangerous drop proximity

    Edges (v1.1):
      BODY_ROOT --body_state-->     POSTURE
      BODY_ROOT --body_relation-->  MOM
      BODY_ROOT --body_relation-->  SHELTER
      BODY_ROOT --body_danger-->    CLIFF
      MOM       --body_part-->      NIPPLE

    Returns:
        (body_world, body_ids) where body_ids maps "root"/"posture"/"mom"/"nipple" → binding ids.
    """
    body_world = cca8_world_graph.WorldGraph()
    # We may add non-lexicon tokens later; keep tag policy permissive here.
    body_world.set_tag_policy("allow")
    body_world.set_stage("neonate")

    # Root / self node
    root_bid = body_world.ensure_anchor("BODY_ROOT")

    # Posture slot: default fallen at birth
    posture_bid = body_world.add_predicate(
        "posture:fallen",
        attach="none",
        meta={"body_slot": "posture", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        posture_bid,
        "body_state",
        meta={"created_by": "body_map_init"},
    )

    # Mom distance slot: default far
    mom_bid = body_world.add_predicate(
        "proximity:mom:far",
        attach="none",
        meta={"body_slot": "mom", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        mom_bid,
        "body_relation",
        meta={"created_by": "body_map_init"},
    )

    # Shelter distance slot: default far
    shelter_bid = body_world.add_predicate(
        "proximity:shelter:far",
        attach="none",
        meta={"body_slot": "shelter", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        shelter_bid,
        "body_relation",
        meta={"created_by": "body_map_init"},
    )

    # Cliff / dangerous drop slot: default far (no immediate hazard)
    cliff_bid = body_world.add_predicate(
        "hazard:cliff:far",
        attach="none",
        meta={"body_slot": "cliff", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        cliff_bid,
        "body_danger",
        meta={"created_by": "body_map_init"},
    )

    # Nipple slot: default hidden
    nipple_bid = body_world.add_predicate(
        "nipple:hidden",
        attach="none",
        meta={"body_slot": "nipple", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        mom_bid,
        nipple_bid,
        "body_part",
        meta={"created_by": "body_map_init"},
    )

    body_ids = {
        "root": root_bid,
        "posture": posture_bid,
        "mom": mom_bid,
        "nipple": nipple_bid,
        "shelter": shelter_bid,
        "cliff": cliff_bid,
    }

    return body_world, body_ids


# WorkingMap construction/reset and the MapSurface storage/retrieval pipeline
# live in cca8_working_memory.py; compatibility aliases are defined near
# the module-import seams above.

# Stateful MapSurface and predictive-code update helpers moved to cca8_working_memory.py (Phase 3).


def print_working_map_snapshot(ctx, *, n: int = 15, title: str = "[workingmap] snapshot") -> None:
    """Print a tail snapshot of the WorkingMap graph, showing tags + a small edge preview."""
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    def _bid_key(bid: str) -> int:
        try:
            return int(bid[1:]) if isinstance(bid, str) and bid.startswith("b") else 10**9
        except Exception:
            return 10**9

    all_ids = sorted(getattr(ww, "_bindings", {}).keys(), key=_bid_key)  # pylint: disable=protected-access
    tail = all_ids[-max(1, int(n)) :]
    print(f"{title}: last {len(tail)} binding(s) of {len(all_ids)} total")
    print(
        "  Legend: edges=wm_entity(root→entity), wm_scratch(root→scratch), wm_creative(root→creative), "
        "distance_to(self→entity), then(action chain)"
    )
    print("          tags=wm:* entity markers; pred:* belief-now; cue:* cues-now; meta.wm.pos={x,y,frame}")



    for bid in tail:
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue
        tags = ", ".join(sorted(getattr(b, "tags", []) or []))
        edges_raw = getattr(b, "edges", []) or []
        edges = [e for e in edges_raw if isinstance(e, dict)]

        preview = []
        for e in edges[:6]:
            rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if not isinstance(dst, str):
                continue
            extra = ""
            em = e.get("meta") if isinstance(e, dict) else None
            if rel == "distance_to" and isinstance(em, dict):
                meters = em.get("meters")
                dclass = em.get("class")
                if isinstance(meters, (int, float)):
                    extra += f" meters={float(meters):.2f}"
                if isinstance(dclass, str) and dclass:
                    extra += f" class={dclass}"
            preview.append(f"{rel}:{_wm_display_id(dst)} ({dst}){extra}")

        if preview:
            pv = ", ".join(preview)
            if len(edges) > 6:
                pv += f" (+{len(edges) - 6} more)"
        else:
            pv = "(none)"
        print(f"  {_wm_display_id(bid)} ({bid}): [{tags}] out={len(edges)} edges={pv}")

    try:
        if getattr(ctx, "wm_surfacegrid", None) is not None:
            print(format_surfacegrid_snapshot_v1(ctx))
    except Exception:
        pass


def print_working_map_layers(ctx, *, title: str = "[workingmap] layers") -> None:
    """Print a compact HUD of WorkingMap layers (MapSurface / Scratch / Creative).

    This is intentionally a *structural* view:
      - Which roots exist?
      - Is Creative enabled?
      - How many candidates are currently staged?

    It does not print the full graph; use print_working_map_snapshot(...) for that.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    root_bid = (anchors.get("WM_ROOT") or anchors.get("NOW"))
    scratch_bid = anchors.get("WM_SCRATCH")
    creative_bid = anchors.get("WM_CREATIVE")

    ent_map = getattr(ctx, "wm_entities", {}) or {}
    enabled = bool(getattr(ctx, "wm_creative_enabled", False))
    cands = getattr(ctx, "wm_creative_candidates", []) or []

    print(title)
    if isinstance(root_bid, str):
        print(f"  MapSurface: root={_wm_display_id(root_bid)} ({root_bid}) entities={len(ent_map)}")
    else:
        print(f"  MapSurface: root=(none) entities={len(ent_map)}")

    if isinstance(scratch_bid, str):
        print(f"  Scratch  : root={_wm_display_id(scratch_bid)} ({scratch_bid})")
    else:
        print("  Scratch  : root=(none)")

    if isinstance(creative_bid, str):
        print(f"  Creative : root={_wm_display_id(creative_bid)} ({creative_bid}) enabled={enabled} candidates={len(cands)}")
    else:
        print(f"  Creative : root=(none) enabled={enabled} candidates={len(cands)}")

    # Optional: show candidate summaries if present
    if cands:
        print("  Creative candidates: trig=Y/N (trigger satisfied or blocked); score is a display heuristic (not deficit or RL q).")
        try:
            ordered = sorted(cands, key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)
        except Exception:
            ordered = list(cands)

        for i, c in enumerate(ordered[:8], 1):
            try:
                pol = getattr(c, "policy", "(unknown)")
                score = float(getattr(c, "score", 0.0))
                notes = str(getattr(c, "notes", "") or "")

                pred = getattr(c, "predicted", None)
                trig = bool(pred.get("triggerable", False)) if isinstance(pred, dict) else False
                trig_txt = "Y" if trig else "N"

                # If the candidate is blocked, normalize the old note prefix so output is cleaner.
                if (not trig) and notes.startswith("blocked(not_triggered)"):
                    rest = notes[len("blocked(not_triggered)"):]
                    rest = rest.lstrip(" ;")
                    notes = "not_triggered" + (f"; {rest}" if rest else "")

                print(f"    {i:>2}) {pol:<18} trig={trig_txt} score={score:>6.2f}  {notes}")
            except Exception:
                print(f"    {i:>2}) {c}")


def print_working_map_entity_table(ctx, *, title: str = "[workingmap] MapSurface entity table") -> None:
    """Print a compact table of WorkingMap entities with schematic coordinates and key WM meta.

    This is intentionally a *MapSurface* view (entities + geometry), not the full binding log.
    Coordinates are stored in binding.meta['wm']['pos'] as {x,y,frame}.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    ent_map = getattr(ctx, "wm_entities", None)
    if not isinstance(ent_map, dict) or not ent_map:
        print(f"{title}: (no wm_entities; MapSurface may not be initialized yet)")
        return

    def _sort_key(item) -> tuple[int, str]:
        eid = str(item[0])
        return (0, "") if eid == "self" else (1, eid)

    print(title)
    print("  ent      node        kind      pos(x,y)         dist_m  class     seen patches             preds (short)                cues (short)")
    print("  -------  ----------  --------  --------------  ------  --------  ---- ------------------  --------------------------  ----------------")

    # Footer summary counters (NavPatch visibility; keeps logs readable during long runs)
    ent_rows = 0
    ent_with_patches = 0
    patch_refs_total = 0
    uniq_sig16: set[str] = set()
    uniq_patch_eids: set[str] = set()

    skip_meta_entities = {"scene", "wm_root", "root", "now"}

    for eid, bid in sorted(ent_map.items(), key=_sort_key):
        if not isinstance(eid, str):
            continue
        if eid.strip().lower() in skip_meta_entities:
            continue
        if not isinstance(bid, str):
            continue
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue

        tags = list(getattr(b, "tags", []) or [])
        kind = ""
        for t in tags:
            if isinstance(t, str) and t.startswith("wm:kind:"):
                kind = t.split(":", 2)[2]
                break

        meta = getattr(b, "meta", None)
        wmm = meta.get("wm", {}) if isinstance(meta, dict) else {}
        pos = wmm.get("pos", {}) if isinstance(wmm, dict) else {}

        x = pos.get("x") if isinstance(pos, dict) else None
        y = pos.get("y") if isinstance(pos, dict) else None
        frame = pos.get("frame") if isinstance(pos, dict) else None

        dist_m = wmm.get("dist_m") if isinstance(wmm, dict) else None
        dist_class = wmm.get("dist_class") if isinstance(wmm, dict) else None
        last_seen = wmm.get("last_seen_step") if isinstance(wmm, dict) else None
        patch_refs = wmm.get("patch_refs") if isinstance(wmm, dict) else None

        # Summary bookkeeping (count only rows we actually render)
        ent_rows += 1
        if isinstance(patch_refs, list) and patch_refs:
            ent_with_patches += 1
            patch_refs_total += len(patch_refs)
            for ref in patch_refs:
                if not isinstance(ref, dict):
                    continue
                s16 = ref.get("sig16")
                if isinstance(s16, str) and s16:
                    uniq_sig16.add(s16)
                peid = ref.get("engram_id")
                if isinstance(peid, str) and peid:
                    uniq_patch_eids.add(peid)

        node_disp = f"{_wm_display_id(bid)} ({bid})"

        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pos_txt = f"({float(x):6.2f},{float(y):6.2f})"
        else:
            pos_txt = "(   n/a,   n/a)"

        dist_txt = f"{float(dist_m):6.2f}" if isinstance(dist_m, (int, float)) else "  n/a "
        cls_txt = str(dist_class) if isinstance(dist_class, str) else "n/a"
        seen_txt = f"{int(last_seen):4d}" if isinstance(last_seen, int) else " n/a"
        patch_n = len(patch_refs) if isinstance(patch_refs, list) else 0
        patch_sig16 = None
        if patch_n and isinstance(patch_refs[0], dict):
            v = patch_refs[0].get("sig16")
            if isinstance(v, str) and v:
                patch_sig16 = v
        patch_txt = f"{patch_n}:{patch_sig16}" if patch_n and patch_sig16 else ("0" if patch_n == 0 else str(patch_n))
        frame_txt = str(frame) if isinstance(frame, str) else ""
        #to clear pylint #0612: Unused variable "frame_txt" will append frame to pos_txt
        if isinstance(frame, str) and frame_txt:
            pos_txt += f" [{frame}]"

        # Optional: schematic bearing/heading (degrees) from SELF to entity, based on the distorted (x,y) WM coords.
        # This is not "true physics bearing" yet — it's a consistent directional cue for debugging/map intuition.
        try:
            if eid != "self" and isinstance(x, (int, float)) and isinstance(y, (int, float)) and (float(x) != 0.0 or float(y) != 0.0):
                from math import atan2, degrees
                brg = degrees(atan2(float(y), float(x)))
                pos_txt += f" brg={brg:+.0f}°"
        except Exception:
            pass

        # Short belief summaries
        preds = sorted(t[5:] for t in tags if isinstance(t, str) and t.startswith("pred:"))
        cues  = sorted(t[4:] for t in tags if isinstance(t, str) and t.startswith("cue:"))

        pred_txt = ", ".join(preds[:3]) + (" …" if len(preds) > 3 else "")
        cue_txt  = ", ".join(cues[:2]) + (" …" if len(cues) > 2 else "")

        print(
            f"  {eid:<7}  {node_disp:<10}  {kind:<8}  {pos_txt:<14}  {dist_txt:>6}  {cls_txt:<8}  {seen_txt:>4}  "
            f"{patch_txt:<18}  {pred_txt:<26}  {cue_txt}"
        )

    if ent_rows:
        print(
            f"  [patches] ent_with={ent_with_patches}/{ent_rows} refs_total={patch_refs_total} "
            f"uniq_sig16={len(uniq_sig16)} uniq_eid={len(uniq_patch_eids)}"
        )


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


def _hamming_hex64(a: str, b: str) -> int:
    """Hamming distance between two hex strings (intended for 64-bit vhashes).
    Returns -1 on parse error. Case-insensitive; extra whitespace ignored.
    -we use for analysis of the temporal context vector
    """
    try:
        xa = int(a.strip(), 16)
        xb = int(b.strip(), 16)
        return (xa ^ xb).bit_count()
    except Exception:
        return -1


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

def _snapshot_temporal_legend() -> list[str]:
    """info about temporal timekeeping in the CCA8
    """
    return [
        "LEGEND (temporal terms):",
        "  epoch: event boundary count; increments when boundary() is taken  [src=ctx.boundary_no]",
        "  vhash64(now): 64-bit sign-bit fingerprint of the current context vector  [src=ctx.tvec64()]",
        "  epoch_vhash64: 64-bit fingerprint of the vector at the last boundary  [src=ctx.boundary_vhash64]",
        "  last_boundary_vhash64: alias of epoch_vhash64 (kept for back-compat)  [alias of epoch_vhash64]",
        "  cos_to_last_boundary: cosine(current vector, last boundary vector)  [src=ctx.cos_to_last_boundary()]",
        "  binding (== node): holds tags, pointers to engrams, and directed edges",
        "",
        "Five measures of time in the CCA8 system:",
        "  1. controller steps — one Action Center decision/execution loop   [src=ctx.controller_steps]",
        "  2. temporal drift — cos_to_last_boundary (cosine(current, last boundary))  [src=ctx.cos_to_last_boundary();"
        "     advanced by ctx.temporal.step()]",
        "  3. autonomic ticks — heartbeat for physiology/IO (robotics integration)  [src=ctx.ticks]",
        "  4. developmental age — age_days  [src=ctx.age_days]",
        "  5. cognitive cycles — full sense->process->opt. action cycle  [src=ctx.cog_cycles]"
        "  **see menu tutorials for more about these terms**",
        "",
    ]


def timekeeping_line(ctx) -> str:
    """Compact summary of the 5 time measures + cosine (robust if any piece is missing).
    """
    cs = getattr(ctx, "controller_steps", 0)
    te = getattr(ctx, "boundary_no", 0)        # temporal epochs
    at = getattr(ctx, "ticks", 0)              # autonomic ticks
    ad = getattr(ctx, "age_days", 0.0)
    cc = getattr(ctx, "cog_cycles", 0)
    try:
        c = ctx.cos_to_last_boundary()
        cos_txt = f"{c:.4f}" if isinstance(c, float) else "(n/a)"
    except Exception:
        cos_txt = "(n/a)"
    return (f"controller_steps={cs}, cos_to_last_boundary={cos_txt}, "
            f"temporal_epochs={te}, autonomic_ticks={at}, age_days={ad:.4f}, cog_cycles={cc}")


def print_timekeeping_line(ctx, prefix: str = "[time] ") -> None:
    """Console helper for menus.
    """
    try:
        print(prefix + timekeeping_line(ctx))
    except Exception:
        pass


# ==== Developer utilities: LOC, vector parsing, and loop helper ===================
def _python_loc_counts_for_file(path: str) -> dict[str, int]:
    """Return simple physical/nonblank/code-like line counts for one Python file.

    This helper intentionally measures what a human usually means by "how large is this file?"
    rather than only formal SLOC. Physical LOC includes comments, docstrings, blank lines,
    long menu text, teaching text, and explanatory scaffolding. Code-like LOC is a simple
    approximation: nonblank lines minus full-line comments. It still counts docstrings and
    multiline strings because those are important in this repo's readable, teaching-oriented style.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except Exception:
        return {"physical": 0, "nonblank": 0, "comment_only": 0, "code_like": 0}

    physical = len(lines)
    nonblank = 0
    comment_only = 0

    for line in lines:
        stripped = line.strip()
        if stripped:
            nonblank += 1
        if line.lstrip().startswith("#"):
            comment_only += 1

    code_like = max(0, nonblank - comment_only)

    return {
        "physical": int(physical),
        "nonblank": int(nonblank),
        "comment_only": int(comment_only),
        "code_like": int(code_like),
    }


def _compute_loc_by_dir(
    suffixes=(".py",),
    skip_folders=(".git", ".venv", "build", "dist", ".pytest_cache", "__pycache__"),
):
    """Compute Python line counts per top-level directory using a dependency-free scanner.

    Returns:
        rows:
            list[(topdir, files_count, physical_loc, nonblank_loc, code_like_loc, comment_only_loc)]
            sorted by physical LOC descending.

        total:
            dict with aggregate counts for the same columns.

        errtext:
            None on success. A string only if the directory walk itself fails.

    Rationale:
        The old Menu 33 path used pygount SLOC, which intentionally excludes comments,
        docstrings, and blank lines. That is useful for one purpose, but it under-reports
        the actual size/readability burden of CCA8. This local scanner reports the project
        size a human sees in an editor.
    """
    skip_set = {str(x) for x in skip_folders}
    suffix_tuple = tuple(str(x) for x in suffixes)

    counts_by_top: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "physical": 0, "nonblank": 0, "code_like": 0, "comment_only": 0}
    )

    try:
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in skip_set and not d.startswith(".")]

            for name in files:
                if not name.endswith(suffix_tuple):
                    continue

                path = os.path.join(root, name)
                rel = os.path.relpath(path, ".")
                parts = rel.split(os.sep)
                top = "." if len(parts) == 1 else parts[0]

                if top in skip_set or not top:
                    continue

                item = _python_loc_counts_for_file(path)
                counts_by_top[top]["files"] += 1
                counts_by_top[top]["physical"] += item["physical"]
                counts_by_top[top]["nonblank"] += item["nonblank"]
                counts_by_top[top]["code_like"] += item["code_like"]
                counts_by_top[top]["comment_only"] += item["comment_only"]

    except Exception as e:
        return [], {}, f"LOC scan failed: {e}"

    rows = []
    for top, item in counts_by_top.items():
        rows.append(
            (
                top,
                int(item["files"]),
                int(item["physical"]),
                int(item["nonblank"]),
                int(item["code_like"]),
                int(item["comment_only"]),
            )
        )

    rows.sort(key=lambda row: (-row[2], row[0]))

    total = {
        "files": sum(row[1] for row in rows),
        "physical": sum(row[2] for row in rows),
        "nonblank": sum(row[3] for row in rows),
        "code_like": sum(row[4] for row in rows),
        "comment_only": sum(row[5] for row in rows),
    }

    return rows, total, None


def _render_loc_by_dir_table(rows, total):
    """Pretty-print the Python LOC table. Returns a string for testability; caller prints it."""
    if not rows:
        return "No Python files (.py) found under the current directory.\n"

    totals = total if isinstance(total, dict) else {}
    name_w = max(25, max(len(str(row[0])) for row in rows))

    lines = []
    lines.append("Selection:  LOC by Directory (Python)")
    lines.append("Counts Python files per top-level folder.")
    lines.append("physical_LOC includes comments, docstrings, menu text, teaching text, and blank lines.")
    lines.append("nonblank_LOC excludes blank lines.")
    lines.append("code_like_LOC excludes blank lines and full-line comments, but still includes docstrings/multiline strings.\n")
    lines.append(
        f"{'directory'.ljust(name_w)}  {'files':>7}  {'physical_LOC':>12}  "
        f"{'nonblank_LOC':>12}  {'code_like_LOC':>13}  {'comment_LOC':>11}"
    )
    lines.append(
        f"{'-' * name_w}  {'-' * 7}  {'-' * 12}  {'-' * 12}  {'-' * 13}  {'-' * 11}"
    )

    for top, files_n, physical, nonblank, code_like, comment_only in rows:
        lines.append(
            f"{str(top).ljust(name_w)}  {files_n:7d}  {physical:12,d}  "
            f"{nonblank:12,d}  {code_like:13,d}  {comment_only:11,d}"
        )

    lines.append(
        f"{'-' * name_w}  {'-' * 7}  {'-' * 12}  {'-' * 12}  {'-' * 13}  {'-' * 11}"
    )
    lines.append(
        f"{'TOTAL'.ljust(name_w)}  {int(totals.get('files', 0)):7d}  "
        f"{int(totals.get('physical', 0)):12,d}  {int(totals.get('nonblank', 0)):12,d}  "
        f"{int(totals.get('code_like', 0)):13,d}  {int(totals.get('comment_only', 0)):11,d}\n"
    )

    return "\n".join(lines)


def _parse_vector(text: str) -> list[float]:
    """
    Parse a comma/space-separated string into a list of floats.
    Empty input → [0.0, 0.0, 0.0].
    """
    import re
    s = (text or "").strip()
    if not s:
        return [0.0, 0.0, 0.0]
    vec = []
    for tok in re.split(r"[,\s]+", s):
        if not tok:
            continue
        try:
            vec.append(float(tok))
        except ValueError:
            pass
    return vec or [0.0, 0.0, 0.0]


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


def _wm_navsummary_get_v1(ctx: Ctx | None) -> dict[str, Any]:
    """Return the current cached WM.NavSummary dict, or {} when unavailable.

    Policies should prefer this helper over directly reading MapSurface slot-families.
    That keeps the gating seam stable even if we later change how NavSummary is computed.
    """
    if ctx is None:
        return {}
    ns = getattr(ctx, "wm_navsummary", None)
    return ns if isinstance(ns, dict) else {}


def _wm_navsummary_bool_v1(ctx: Ctx | None, key: str, default: bool = False) -> bool:
    """Read a boolean-like NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    if key not in ns:
        return bool(default)
    try:
        return bool(ns.get(key))
    except Exception:
        return bool(default)


def _wm_navsummary_int_v1(ctx: Ctx | None, key: str) -> int | None:
    """Read an integer NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    try:
        v = ns.get(key)
        return int(v) if isinstance(v, int) else None
    except Exception:
        return None


def _wm_navsummary_float_v1(ctx: Ctx | None, key: str) -> float | None:
    """Read a float-like NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    try:
        v = ns.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    except Exception:
        return None
    return None


def _wm_navsummary_explain_bits_v1(ctx: Ctx | None) -> str:
    """Return a compact human-readable NavSummary excerpt for gate explanations."""
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return "navsummary=(none)"

    hazard_near = 1 if _wm_navsummary_bool_v1(ctx, "hazard_near", False) else 0
    traversable_near = 1 if _wm_navsummary_bool_v1(ctx, "traversable_near", False) else 0

    hazard_density = _wm_navsummary_float_v1(ctx, "hazard_density")
    hd_txt = f"{hazard_density:.2f}" if isinstance(hazard_density, float) else "n/a"

    corridors = _wm_navsummary_int_v1(ctx, "corridor_count")
    corr_txt = str(corridors) if isinstance(corridors, int) else "n/a"

    goal_dir = ns.get("goal_dir")
    goal_dir_txt = goal_dir if isinstance(goal_dir, str) and goal_dir else "(none)"

    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")
    safe_cost_txt = str(safe_cost) if isinstance(safe_cost, int) else "n/a"

    return (
        "navsummary("
        f"hazard_near={hazard_near}, "
        f"traversable_near={traversable_near}, "
        f"hazard_density={hd_txt}, "
        f"corridors={corr_txt}, "
        f"goal_dir={goal_dir_txt}, "
        f"safe_cost={safe_cost_txt})"
    )


def _wm_follow_mom_blocked_by_topology_v1(ctx: Ctx | None) -> bool:
    """Return True when fallback follow_mom should be suppressed by current topology.

    Conservative v1 rule:
      - If NavSummary is unavailable: do not block here.
      - If no traversable outlet is visible near SELF: block fallback movement.
      - If hazard is near AND no currently visible safe path to a goal exists: block fallback movement.

    This keeps follow_mom available as a simple default in easy scenes, while making it stop
    pretending to be a good generic fallback in locally hazardous or topology-poor scenes.
    """
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return False

    traversable_near = _wm_navsummary_bool_v1(ctx, "traversable_near", False)
    hazard_near = _wm_navsummary_bool_v1(ctx, "hazard_near", False)
    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")

    if not traversable_near:
        return True
    if hazard_near and safe_cost is None:
        return True
    return False


def _wm_probe_supported_by_topology_v1(ctx: Ctx | None) -> bool:
    """Return True when NavSummary says the local scene is topology-relevant enough to justify probing.

    Conservative v1 signal:
      - hazard_near, OR
      - hazard_density is clearly non-trivial, OR
      - no traversable local outlet and no safe path is visible.

    This keeps probe tied to hazardous/uncertain topology, not generic curiosity.
    """
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return False

    if _wm_navsummary_bool_v1(ctx, "hazard_near", False):
        return True

    hazard_density = _wm_navsummary_float_v1(ctx, "hazard_density")
    if isinstance(hazard_density, float) and hazard_density >= 0.15:
        return True

    traversable_near = _wm_navsummary_bool_v1(ctx, "traversable_near", False)
    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")
    if (not traversable_near) and safe_cost is None:
        return True

    return False


#pylint: disable=superfluous-parens
def _gate_stand_up_trigger_body_first(world, _drives: Drives, ctx) -> bool:
    """
    StandUp gate that prefers BodyMap for posture when available, falling back
    to WorldGraph near-NOW predicates otherwise.

    Trigger logic (neonate):
      • If BodyMap is fresh and posture == 'fallen'  → fire.
      • If BodyMap is fresh and posture == 'standing'→ do NOT fire.
      • Otherwise, fall back to:
            fallen  := pred:posture:fallen near NOW
            standing:= pred:posture:standing near NOW
        and fire if fallen or (stand_intent && not standing).
    """
    # BodyMap posture if available and not stale
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None

    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        fallen = has_pred_near_now(world, "posture:fallen")
        standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    return fallen or (stand_intent and not standing)


def _gate_stand_up_explain(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_stand_up_trigger_body_first.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    bp = body_posture(ctx) if ctx is not None else None
    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        fallen = has_pred_near_now(world, "posture:fallen")
        standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    return (
        f"dev_gate: age_days={getattr(ctx, 'age_days', 0.0):.2f}<=3.0, trigger: "
        f"fallen={fallen} or (stand_intent={stand_intent} and not standing={not standing}) "
        f"(hunger={hunger:.2f})"
    )


def _gate_seek_nipple_trigger_body_first(world, drives: Drives, ctx) -> bool:
    """
    SeekNipple gate that supports two paths:

      1) the original hunger-driven path, and
      2) a narrow newborn bridge path once the kid is standing and mom is already near.

    Why this change
    ---------------
    In the hardened newborn benchmark, the kid can now successfully recover posture and
    approach mom, but the default interactive run keeps hunger at 0.50. That means the
    original hunger-only gate can leave the agent stuck in:

        first_stand + mom near + nipple hidden + safe zone

    The bridge below is intentionally narrow:
      - posture must be standing,
      - the kid must not be fallen,
      - mom-distance information must actually exist,
      - mom must be near/touching,
      - nipple must not already be latched,
      - and seeking_mom must not already be active.

    This keeps the old behavior for generic cases while letting the newborn task move
    from "reached mom" into "find nipple".

    Benchmark-only strict mode
    --------------------------
    In strict newborn benchmark mode, current state still comes first. However, when
    current distance/nipple information is sparse due to blackout, we now allow the
    short-lived retrieved hint to supply that information. This is the missing bridge
    between "retrieval happened" and "retrieval changed control".
    """
    # Once latched, do not search for the nipple again. The correct next bridge
    # is suckle, then rest.
    if _newborn_post_latch_sequence_active_v1(world, ctx):
        return False
    # Prefer BodyMap posture when it is not stale; otherwise fall back to graph.
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None

    if bp is not None:
        standing = (bp == "standing")
        fallen = (bp == "fallen")
    else:
        standing = has_pred_near_now(world, "posture:standing")
        fallen = has_pred_near_now(world, "posture:fallen")

    if not standing or fallen:
        return False

    strict_current = bool(getattr(ctx, "experiment_newborn_require_current_state", False)) if ctx is not None else False
    hint = _newborn_active_retrieved_hint_v1(ctx) if strict_current else {}

    # Mom-distance check: use BodyMap first. In strict newborn experiment mode,
    # use the retrieved hint next. Only non-strict mode falls back to old graph history.
    have_distance = False
    mom_near = False

    if ctx is not None and not stale:
        md = body_mom_distance(ctx)
        if md is not None:
            have_distance = True
            mom_near = md in ("near", "touching")

    if not have_distance and strict_current:
        hm = hint.get("mom_distance")
        if isinstance(hm, str) and hm:
            have_distance = True
            mom_near = hm in ("near", "touching")

    if not have_distance and not strict_current:
        close = has_pred_near_now(world, "proximity:mom:close")
        far = has_pred_near_now(world, "proximity:mom:far")
        if close or far:
            have_distance = True
            mom_near = close

    # In the strict newborn benchmark, if distance is still unknown even after
    # consulting the retrieved hint, do not infer "mom is near enough".
    if strict_current and not have_distance:
        return False

    # If we have distance information and mom is not near, seeking is premature.
    if have_distance and not mom_near:
        return False

    # If current state or retrieved hint says we are already latched/drinking, do not seek again.
    ns = body_nipple_state(ctx) if ctx is not None and not stale else None
    if ns is None and strict_current:
        hn = hint.get("nipple_state")
        if isinstance(hn, str) and hn:
            ns = hn
    if ns == "latched":
        return False

    # If 'seeking_mom' is already active near NOW, do not duplicate the behavior.
    if has_pred_near_now(world, "seeking_mom"):
        return False

    # Original hunger-driven path.
    hunger = float(getattr(drives, "hunger", 0.0))
    if hunger > float(HUNGER_HIGH):
        return True

    # Newborn bridge path:
    # once we are upright and truly near mom, allow nipple-seeking even if hunger
    # is only moderate in the interactive demo.
    if have_distance and mom_near:
        return True

    return False


def _gate_seek_nipple_explain(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_seek_nipple_trigger_body_first.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    bp = body_posture(ctx) if ctx is not None else None
    if bp is not None:
        standing = (bp == "standing")
        fallen = (bp == "fallen")
        posture_str = bp
    else:
        standing = has_pred_near_now(world, "posture:standing")
        fallen = has_pred_near_now(world, "posture:fallen")
        posture_str = f"standing={standing}, fallen={fallen}"

    ns = body_nipple_state(ctx) if ctx is not None else None
    nipple_str = ns if ns is not None else "n/a"

    seeking = has_pred_near_now(world, "seeking_mom")
    return (
        f"dev_gate: True, trigger: posture={posture_str} "
        f"and hunger={hunger:.2f}>0.60 "
        f"and nipple_state={nipple_str} "
        f"and not seeking={not seeking} "
        f"and not fallen={not fallen}"
        f"-mem_distance={body_mom_distance(ctx)}"
    )
#pylint: enable=superfluous-parens


def _gate_rest_trigger_body_space(world, drives: Drives, ctx) -> bool:
    """
    Rest gate that supports both ordinary fatigue-driven rest and a narrow
    newborn completion bridge, while suppressing redundant rest after success.

    Why this exists
    ---------------
    In the hardened newborn benchmark, ``rest`` is the correct bridge action in
    ``first_latch``. However, once the newborn has already reached the stable
    solved end-state, repeatedly firing ``policy:rest`` adds clutter without
    helping behavior.

    Rules
    -----
    - Ordinary mode:
        fatigue > FATIGUE_HIGH or cue:drive:fatigue_high present
    - goat04 contextual mode:
        an active hawk hint may request rest even when fatigue is mild
        an active fox hint suppresses rest
    - newborn bridge:
        ``_should_force_rest_bridge_v1(...)`` may request rest in ``first_latch``
        even when fatigue is still low
    - newborn solved-state quiescence:
        ``_should_quiesce_rest_v1(...)`` suppresses rest once the newborn is
        already in stable ``stage='rest'`` with safe geometry
    - BodyMap/space veto remains in force:
        do not rest when zone == 'unsafe_cliff_near'
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_high = fatigue > float(FATIGUE_HIGH)
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])
    goat04_hint = _goat04_context_hint_active_v1(ctx)
    newborn_rest_bridge = _should_force_rest_bridge_v1(world, ctx)
    rest_quiesce = _should_quiesce_rest_v1(world, ctx)

    if goat04_hint == "fox":
        return False

    if rest_quiesce:
        return False

    # Newborn hard-mode bridge:
    # after explicit suckling has produced milk:drinking, Rest is the correct
    # task-completion action even if ordinary fatigue is not high.
    if newborn_rest_bridge:
        return True

    # goat04 hawk-context bridge or ordinary fatigue-based Rest gate.
    if not (fatigue_high or fatigue_cue or goat04_hint == "hawk"):
        return False

    try:
        if ctx is not None:
            zone = body_space_zone(ctx)
            if zone == "unsafe_cliff_near":
                return False
    except Exception:
        return True

    return True


def _gate_rest_explain_body_space(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_rest_trigger_body_space.
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])
    goat04_hint = _goat04_context_hint_active_v1(ctx)
    newborn_rest_bridge = _should_force_rest_bridge_v1(world, ctx)
    rest_quiesce = _should_quiesce_rest_v1(world, ctx)
    stage = getattr(ctx, "lt_obs_last_stage", None) if ctx is not None else None

    shelter = None
    cliff = None
    zone = "unknown"
    try:
        if ctx is not None and not bodymap_is_stale(ctx):
            shelter = body_shelter_distance(ctx)
            cliff = body_cliff_distance(ctx)
        zone = body_space_zone(ctx) if ctx is not None else "unknown"
    except Exception:
        shelter = cliff = None
        zone = "unknown"

    return (
        f"dev_gate: True, trigger: fatigue={fatigue:.2f}>{float(FATIGUE_HIGH):.2f} "
        f"or cue:drive:fatigue_high present={fatigue_cue} "
        f"or goat04_hint={goat04_hint!r} "
        f"or newborn_rest_bridge={newborn_rest_bridge} "
        f"(newborn_rest_quiesce={rest_quiesce}, stage={stage!r}, "
        f"rest_zone={zone}, shelter={shelter}, cliff={cliff})"
    )


def _follow_mom_bridge_state_v1(world, ctx) -> dict[str, Any]:
    """Return the compact body/world state used by follow_mom gating and no-match fallback.

    I keep this helper tiny and explicit because the hardened newborn benchmark now
    depends on action-driven recovery and approach behavior. The runner therefore needs
    one place that answers:

        posture?
        mom_distance?
        nipple_state?
        zone?
        bodymap fresh or stale?

    BodyMap is preferred when fresh. If it is stale or unavailable, we normally fall
    back to near-NOW WorldGraph predicates so the controller still has a conservative
    view of the current situation.

    Benchmark-only strict mode
    --------------------------
    When ctx.experiment_newborn_require_current_state is True, this helper does NOT
    reconstruct current-state values from older long-term graph predicates. It uses:

      1) fresh BodyMap/current-state values first, then
      2) the short-lived newborn retrieved hint (if active).

    That gives episodic readback a real causal role during blackout windows without
    letting older long-term graph history silently masquerade as "truth now".
    """
    stale = True
    posture = None
    mom_distance = None
    nipple_state = None
    milk_drinking = None
    zone = "unknown"

    try:
        if ctx is not None:
            stale = bodymap_is_stale(ctx)
            if not stale:
                posture = body_posture(ctx)
                mom_distance = body_mom_distance(ctx)
                nipple_state = body_nipple_state(ctx)
                try:
                    zone = body_space_zone(ctx)
                except Exception:
                    zone = "unknown"
    except Exception:
        stale = True
        posture = None
        mom_distance = None
        nipple_state = None
        zone = "unknown"

    strict_current = bool(getattr(ctx, "experiment_newborn_require_current_state", False)) if ctx is not None else False
    if strict_current:
        hint = _newborn_active_retrieved_hint_v1(ctx)

        if posture is None:
            hp = hint.get("posture")
            if isinstance(hp, str) and hp:
                posture = hp

        if mom_distance is None:
            hm = hint.get("mom_distance")
            if isinstance(hm, str) and hm:
                mom_distance = hm

        if nipple_state is None:
            hn = hint.get("nipple_state")
            if isinstance(hn, str) and hn:
                nipple_state = hn

        hm_drinking = hint.get("milk_drinking")
        if isinstance(hm_drinking, bool):
            milk_drinking = hm_drinking

        if zone in (None, "", "unknown"):
            hz = hint.get("zone")
            if isinstance(hz, str) and hz:
                zone = hz

        return {
            "bodymap_stale": bool(stale),
            "posture": posture,
            "mom_distance": mom_distance,
            "nipple_state": nipple_state,
            "milk_drinking": milk_drinking,
            "zone": zone,
        }

    if posture is None:
        if has_pred_near_now(world, "posture:fallen"):
            posture = "fallen"
        elif has_pred_near_now(world, "posture:standing"):
            posture = "standing"
        elif has_pred_near_now(world, "resting"):
            posture = "resting"

    if mom_distance is None:
        if has_pred_near_now(world, "proximity:mom:close"):
            mom_distance = "near"
        elif has_pred_near_now(world, "proximity:mom:far"):
            mom_distance = "far"

    if nipple_state is None:
        if has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking"):
            nipple_state = "latched"
        elif has_pred_near_now(world, "nipple:found"):
            nipple_state = "reachable"
        elif has_pred_near_now(world, "nipple:hidden"):
            nipple_state = "hidden"

    try:
        milk_drinking = has_pred_near_now(world, "milk:drinking")
    except Exception:
        milk_drinking = None

    return {
        "bodymap_stale": bool(stale),
        "posture": posture,
        "mom_distance": mom_distance,
        "nipple_state": nipple_state,
        "milk_drinking": milk_drinking,
        "zone": zone,
    }


def _newborn_recent_retrieval_ok_v1(ctx, *, max_age_steps: int = 3) -> bool:
    """Return True when a recent wm_mapsurface retrieval/apply event succeeded.

    Why this exists
    ---------------
    The newborn benchmark now needs a way to distinguish:

      - "I can continue because I still have fresh current evidence", from
      - "I can continue because episodic readback just restored a useful prior."

    We intentionally keep this helper tiny and benchmark-oriented.
    It inspects the latest map-switch event and treats it as "recent enough"
    only when:

      - the event exists,
      - the event reports ok=True,
      - and it occurred within ``max_age_steps`` controller steps.

    This is not a general memory-quality score. It is only a narrow bridge gate
    for Menu 49 newborn_long_horizon hardening.
    """
    if ctx is None:
        return False

    events = getattr(ctx, "wm_mapswitch_last_events", None)
    if not isinstance(events, list) or not events:
        return False

    event = events[-1]
    if not isinstance(event, dict):
        return False
    if not bool(event.get("ok")):
        return False

    try:
        event_step = int(event.get("step"))
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        return False

    age_steps = step_now - event_step
    return 0 <= age_steps <= max(1, int(max_age_steps))


def _newborn_follow_fallback_blocked_without_memory_v1(world, ctx) -> bool:
    """Return True when generic follow_mom fallback should be blocked in newborn benchmark mode.

    Why this exists
    ---------------
    The current newborn benchmark already has:
      - strict current-state use for some bridge gates,
      - a recent-retrieval check for explicit bridge continuation,
      - and real partial observability via blackout + obs masking.

    However, one important leak remains:
    the generic follow_mom fallback can still keep the task moving even when
    current evidence is sparse, simply because posture is not fallen/resting and
    topology does not veto the action.

    That makes episodic readback less important than the paper intends.

    Rule
    ----
    In newborn benchmark resume-memory mode, block the *generic* follow_mom
    fallback when all of the following are true:

      - posture is standing,
      - current local evidence is sparse/unknown (BodyMap stale or key slots missing),
      - and there was no recent successful wm_mapsurface retrieval/apply event.

    This helper does NOT replace the explicit newborn bridge:
    `_should_force_follow_mom_bridge_v1(...)` still handles the narrower case
    where the system specifically knows mom is far and wants to continue a
    post-stand approach sequence.

    This helper only stops the architecture from drifting forward on a vague
    permissive fallback during blackout-like uncertainty.
    """
    if ctx is None:
        return False

    if not bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)):
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)
    if st.get("posture") != "standing":
        return False

    bodymap_stale = bool(st.get("bodymap_stale"))
    evidence_sparse = (
        bodymap_stale
        or (st.get("mom_distance") is None)
        or (st.get("nipple_state") is None)
    )

    if not evidence_sparse:
        return False

    return not _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _should_force_follow_mom_bridge_v1(world, ctx) -> bool:
    """Return True when follow_mom should bridge post-stand recovery into mom-approach.

    Why this exists
    ---------------
    This bridge prevents the hardened newborn benchmark from stalling forever in
    ``first_stand`` after the kid has already recovered posture.

    New benchmark hardening
    -----------------------
    In ordinary mode, the bridge remains permissive once posture is standing and
    mom is still far.

    In newborn benchmark resume-memory mode, that permissive bridge is allowed to
    carry progress across a blackout only if:

      - current evidence is genuinely missing/unknown, and
      - a recent wm_mapsurface retrieval/apply event succeeded.

    This gives episodic readback a real causal role without changing ordinary
    interactive runs.
    """
    st = _follow_mom_bridge_state_v1(world, ctx)

    if st.get("posture") != "standing":
        return False

    mom_distance = st.get("mom_distance")
    if mom_distance != "far":
        return False

    nipple_state = st.get("nipple_state")
    if nipple_state == "latched":
        return False

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)) if ctx is not None else False
    if not require_resume_memory:
        return True

    bodymap_stale = bool(st.get("bodymap_stale"))
    current_evidence_missing = bodymap_stale or (mom_distance is None)

    # If current evidence is present and explicitly says "mom is far", ordinary bridge is fine.
    # We only require episodic readback when we are trying to continue through a blackout-like
    # uncertainty window.
    if not current_evidence_missing:
        return True

    return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _newborn_milk_drinking_slot_seen_v1(ctx) -> bool:
    """Return True when the current observation slot cache has recorded milk drinking.

    This is a narrow newborn benchmark helper. It does not allow latch alone to
    count as feeding. It only returns True after the long-term observation slot
    cache has actually seen the token "milk:drinking".

    Rationale:
        Under route_loss, the visible milk predicate can disappear from the near-NOW
        graph immediately after the milk-drinking milestone, while the slot cache
        still records that the milk slot reached "milk:drinking". The rest bridge
        should be allowed to use that current-state cache to complete the feeding
        sequence.
    """
    if ctx is None:
        return False

    try:
        slots = getattr(ctx, "lt_obs_slots", None)
        if not isinstance(slots, dict):
            return False

        milk_slot = slots.get("milk")
        if not isinstance(milk_slot, dict):
            return False

        return milk_slot.get("token") == "milk:drinking"
    except Exception:
        return False


def _should_force_rest_bridge_v1(world, ctx) -> bool:
    """Return True when rest should bridge the newborn from feeding into completion.

    In hard newborn mode, Rest must not skip the explicit Suckle -> milk_drinking
    seam. Once milk drinking is visible, however, Rest should be allowed even when
    ordinary fatigue is still low.
    """
    if ctx is None:
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)
    stage = getattr(ctx, "lt_obs_last_stage", None)

    try:
        route_loss_active = _newborn_stress_profile_from_ctx_v1(ctx) == "route_loss"
    except Exception:
        route_loss_active = False

    hard_newborn = bool(getattr(ctx, "experiment_newborn_require_current_state", False))
    milk_drinking_now = _newborn_milk_drinking_current_v1(world, ctx)
    feeding_now = bool(milk_drinking_now)

    # Back-compatible non-hard path: ordinary storyboard may still treat latch/first_latch
    # as feeding. Hard newborn mode must require milk_drinking first.
    if not feeding_now and not hard_newborn and not route_loss_active:
        feeding_now = stage == "first_latch"
        if not feeding_now:
            if st.get("nipple_state") == "latched":
                feeding_now = True
            else:
                try:
                    feeding_now = has_pred_near_now(world, "milk:drinking")
                except Exception:
                    feeding_now = False

    if not feeding_now:
        return False
    if st.get("posture") == "fallen":
        return False
    if st.get("mom_distance") == "far":
        return False
    if st.get("zone") == "unsafe_cliff_near":
        return False

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))
    if not require_resume_memory:
        return True

    bodymap_stale = bool(st.get("bodymap_stale"))
    evidence_sparse = bodymap_stale or (st.get("nipple_state") is None) or (st.get("mom_distance") is None)

    if route_loss_active:
        if not milk_drinking_now:
            return False
        if evidence_sparse:
            return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)
        return True

    if not evidence_sparse:
        return True

    return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _should_quiesce_rest_v1(world, ctx) -> bool:
    """Return True when newborn rest should quiesce because the solved end-state is already stable.

    Why this exists
    ---------------
    The newborn rest bridge is supposed to help the kid move from ``first_latch``
    into completion. Once the environment has already reached the solved end-state,
    repeatedly re-firing ``policy:rest`` is no longer useful. This helper therefore
    suppresses rest only when all of the following are already true:

      - the latest environment stage is ``rest``,
      - posture is resting,
      - the spatial niche is explicitly safe,
      - mom is not far,
      - and the feeding relation is still present (latched or drinking).

    This is intentionally narrower than ``_should_force_rest_bridge_v1(...)``.
    We do not use it during ``first_latch`` because the bridge is still needed there.
    """
    if ctx is None:
        return False

    stage = getattr(ctx, "lt_obs_last_stage", None)
    if stage != "rest":
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)

    resting_now = st.get("posture") == "resting"
    if not resting_now:
        try:
            resting_now = has_pred_near_now(world, "resting")
        except Exception:
            resting_now = False
    if not resting_now:
        return False

    if st.get("zone") != "safe":
        return False
    if st.get("mom_distance") == "far":
        return False

    latched_or_drinking = st.get("nipple_state") == "latched"
    if not latched_or_drinking:
        try:
            latched_or_drinking = has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking")
        except Exception:
            latched_or_drinking = False
    if not latched_or_drinking:
        return False

    return True


def _newborn_post_latch_sequence_active_v1(world, ctx) -> bool:
    """Return True when the newborn sequence has entered the post-latch feeding phase.

    This benchmark helper prevents the controller from continuing earlier search
    or locomotor policies after latch has already been reached. Once latched, the
    correct sequence is suckle, then rest. This helper is conservative and accepts
    current BodyMap state, retrieved hint state, or the benchmark stage boundary.
    """
    if ctx is None:
        return False

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        st = {}

    if st.get("posture") == "latched":
        return True

    if st.get("nipple_state") == "latched":
        return True

    if st.get("milk_drinking") is True:
        return True

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))

    if require_resume_memory and stage == "first_latch":
        return True

    if not require_resume_memory:
        try:
            return has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking")
        except Exception:
            return False

    return False


def _bodymap_slot_has_pred_v1(ctx, slot_name: str, pred_token: str) -> bool:
    """Return True if a BodyMap slot currently carries a specific pred:* tag.

    This is intentionally a tiny runner-side helper. It lets bridge gates read the
    same current-state BodyMap that policy gates already trust, without adding a
    new public controller API just for this newborn benchmark seam.
    """
    if ctx is None:
        return False

    try:
        if bodymap_is_stale(ctx):
            return False
    except Exception:
        return False

    try:
        body_world = getattr(ctx, "body_world", None)
        body_ids = getattr(ctx, "body_ids", {}) or {}
        if body_world is None or not isinstance(body_ids, dict):
            return False

        bid = body_ids.get(slot_name)
        if not isinstance(bid, str):
            return False

        binding = getattr(body_world, "_bindings", {}).get(bid)
        if binding is None:
            return False

        tags = set(getattr(binding, "tags", []) or [])
        want = pred_token if pred_token.startswith("pred:") else f"pred:{pred_token}"
        return want in tags

    except Exception:
        return False


def _newborn_graph_has_pred_anywhere_v1(graph, pred_token: str) -> bool:
    """Return True if a graph-like object currently contains a pred:* token anywhere.

    This is intentionally broader than ``has_pred_near_now``. The current newborn
    loop can execute policies in WorkingMap while long-term WorldGraph remains sparse.
    During the late feeding/rest seam, the most reliable current evidence may therefore
    live on WorkingMap's SELF entity rather than near the long-term NOW anchor.
    """
    if graph is None:
        return False

    token = str(pred_token or "").strip()
    if not token:
        return False
    if token.startswith("pred:"):
        token = token.replace("pred:", "", 1)

    want = f"pred:{token}"

    try:
        bindings = getattr(graph, "_bindings", {})
        if not isinstance(bindings, dict):
            return False

        for binding in bindings.values():
            tags = getattr(binding, "tags", None)
            if isinstance(tags, (set, list, tuple)) and want in tags:
                return True

    except Exception:
        return False

    return False


def _newborn_pred_seen_in_control_worlds_v1(world, ctx, pred_token: str) -> bool:
    """Return True if a predicate is visible in long-term, WorkingMap, MapSurface, or BodyMap."""
    token = str(pred_token or "").strip()
    if not token:
        return False
    if token.startswith("pred:"):
        token = token.replace("pred:", "", 1)

    graphs: list[Any] = [world]

    if ctx is not None:
        for attr_name in ("working_world", "map_surface_world", "body_world"):
            try:
                graph = getattr(ctx, attr_name, None)
            except Exception:
                graph = None
            if graph is not None:
                graphs.append(graph)

    for graph in graphs:
        if graph is None:
            continue

        try:
            if has_pred_near_now(graph, token, hops=6):
                return True
        except TypeError:
            try:
                if has_pred_near_now(graph, token):
                    return True
            except Exception:
                pass
        except Exception:
            pass

        if _newborn_graph_has_pred_anywhere_v1(graph, token):
            return True

    return False


def _newborn_milk_drinking_current_v1(world, ctx) -> bool:
    """Return True once the controller has agent-visible evidence of milk drinking.

    Hard newborn mode now separates:

        nipple:latched -> policy:suckle -> milk:drinking -> policy:rest

    BodyMap still stores nipple/milk state in a compact slot, and policy execution
    may write into WorkingMap first. This helper therefore checks all current
    control-visible surfaces before deciding that Suckle should stop and Rest should
    take over.
    """
    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
        if st.get("milk_drinking") is True:
            return True
    except Exception:
        pass

    if _newborn_pred_seen_in_control_worlds_v1(world, ctx, "milk:drinking"):
        return True

    try:
        if _newborn_milk_drinking_slot_seen_v1(ctx):
            return True
    except Exception:
        pass

    try:
        records = getattr(ctx, "cycle_json_records", None)
    except Exception:
        records = None

    if isinstance(records, list):
        for record in records[-12:]:
            if not isinstance(record, dict):
                continue

            obs = record.get("obs")
            obs = obs if isinstance(obs, dict) else {}

            preds = obs.get("predicates")
            if isinstance(preds, list) and "milk:drinking" in preds:
                return True

            meta = obs.get("env_meta")
            meta = meta if isinstance(meta, dict) else {}

            raw = meta.get("milestones")
            if raw is None:
                raw = meta.get("milestone")

            if raw == "milk_drinking":
                return True
            if isinstance(raw, list) and "milk_drinking" in raw:
                return True

    return False


def _should_force_newborn_rest_after_milk_v1(world, ctx) -> bool:
    """Return True when Rest should bridge milk drinking into the final resting state."""
    if ctx is None:
        return False

    if not _newborn_milk_drinking_current_v1(world, ctx):
        return False

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    # The bridge is specifically for the post-latch newborn feeding phase.
    if stage == "rest":
        return False

    if stage != "first_latch":
        try:
            st = _follow_mom_bridge_state_v1(world, ctx)
        except Exception:
            st = {}

        if st.get("posture") != "latched" and st.get("nipple_state") != "latched":
            return False

    try:
        if body_space_zone(ctx) == "unsafe_cliff_near":
            return False
    except Exception:
        pass

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
        if st.get("posture") == "fallen":
            return False
        if st.get("zone") == "unsafe_cliff_near":
            return False
    except Exception:
        pass

    return True


def _should_force_suckle_bridge_v1(world, ctx) -> bool:
    """Return True when Suckle should bridge latch into milk drinking.

    Once milk_drinking is visible anywhere in the current control surfaces, Suckle
    should stop. The next correct bridge is Rest.
    """
    if ctx is None:
        return False

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        return False

    if st.get("posture") == "fallen":
        return False

    if st.get("zone") == "unsafe_cliff_near":
        return False

    if st.get("mom_distance") == "far":
        return False

    if _newborn_milk_drinking_current_v1(world, ctx):
        return False

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    if stage == "rest":
        return False

    if stage == "first_latch":
        return True

    if st.get("posture") == "latched":
        return True

    if st.get("nipple_state") == "latched":
        return True

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))

    if require_resume_memory and stage == "first_latch":
        return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)

    if not require_resume_memory:
        try:
            return has_pred_near_now(world, "nipple:latched")
        except Exception:
            return False

    return False


def _gate_suckle_trigger_newborn_v1(world, _drives: Drives, ctx) -> bool:
    """Trigger suckling after latch and before rest."""
    return _should_force_suckle_bridge_v1(world, ctx)


def _gate_suckle_explain_newborn_v1(world, _drives: Drives, ctx) -> str:
    """Human-readable explanation matching _gate_suckle_trigger_newborn_v1."""
    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        st = {}

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    try:
        recent_retrieval = _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)
    except Exception:
        recent_retrieval = False

    return (
        "dev_gate: True, trigger: newborn_suckle_bridge="
        f"{_should_force_suckle_bridge_v1(world, ctx)} "
        f"stage={stage!r} posture={st.get('posture')!r} "
        f"mom={st.get('mom_distance')!r} nipple={st.get('nipple_state')!r} "
        f"milk_drinking={st.get('milk_drinking')!r} zone={st.get('zone')!r} "
        f"recent_retrieval={recent_retrieval}"
    )


def _gate_follow_mom_trigger_body_space(world, drives: Drives, ctx) -> bool:  # pylint: disable=unused-argument
    """FollowMom gate with goat04/context behavior and newborn post-latch discipline."""
    hint = _goat04_context_hint_active_v1(ctx)
    if hint == "hawk":
        return False
    if hint == "fox":
        return True

    st = _follow_mom_bridge_state_v1(world, ctx)
    posture = st.get("posture")

    if posture in ("fallen", "resting"):
        return False

    if _newborn_post_latch_sequence_active_v1(world, ctx):
        return False

    if _should_force_follow_mom_bridge_v1(world, ctx):
        return True

    if _newborn_follow_fallback_blocked_without_memory_v1(world, ctx):
        return False

    if posture is None:
        try:
            if has_pred_near_now(world, "resting", hops=3):
                return False
        except Exception:
            pass

    try:
        if _wm_follow_mom_blocked_by_topology_v1(ctx):
            return False
    except Exception:
        pass

    return True


def _gate_follow_mom_explain_body_space(world, drives: Drives, ctx) -> str:  # pylint: disable=unused-argument
    """
    Human-readable explanation matching _gate_follow_mom_trigger_body_space.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))
    goat04_hint = _goat04_context_hint_active_v1(ctx)

    posture = None
    zone = "unknown"
    bodymap_stale = True
    try:
        bodymap_stale = bodymap_is_stale(ctx) if ctx is not None else True
        if ctx is not None and not bodymap_stale:
            posture = body_posture(ctx)
            zone = body_space_zone(ctx)
    except Exception:
        posture = posture or "n/a"
        zone = "unknown"
        bodymap_stale = True

    rest_near_now = False
    try:
        rest_near_now = has_pred_near_now(world, "resting", hops=3)
    except Exception:
        rest_near_now = False

    topo_blocked = False
    try:
        topo_blocked = _wm_follow_mom_blocked_by_topology_v1(ctx)
    except Exception:
        topo_blocked = False

    sparse_follow_blocked = False
    try:
        sparse_follow_blocked = _newborn_follow_fallback_blocked_without_memory_v1(world, ctx)
    except Exception:
        sparse_follow_blocked = False

    return (
        "dev_gate: True, trigger: fallback=True when not fallen/resting and topology permits; "
        f"goat04_hint={goat04_hint!r} bodymap_stale={bodymap_stale} posture={posture or 'n/a'} "
        f"rest_near_now={rest_near_now} zone={zone} topology_blocked={topo_blocked} "
        f"sparse_follow_blocked={sparse_follow_blocked} "
        f"{_wm_navsummary_explain_bits_v1(ctx)} (hunger={hunger:.2f}, fatigue={fatigue:.2f})"
    )


def _gate_probe_ambiguity_trigger_body_first(world, _drives: Drives, ctx) -> bool:  # pylint: disable=unused-argument
    """
    Step 15C gate: trigger a minimal probe policy when WM.Scratch reports an ambiguous NavPatch match.

    Refactor intent
    ---------------
    This gate prefers NavSummary when it is available, but it preserves the original
    Step-15C behavior when NavSummary is absent.

    v1.1 rules
    ----------
      - Probe must be enabled.
      - WM.Scratch must currently hold at least one ambiguity key.
      - Prefer cliff ambiguity, but BodyMap cliff-near remains a fallback support signal.
      - If NavSummary is present:
          * hazard ambiguity requires topology support OR BodyMap cliff-near
          * non-hazard ambiguity requires the stronger fallback (hazard_near + topology support)
      - If NavSummary is absent:
          * preserve backward-compatible behavior: cliff ambiguity alone may trigger probe
      - Respect cooldown exactly as before.
    """
    if ctx is None:
        return False
    if not bool(getattr(ctx, "wm_probe_enabled", True)):
        return False

    keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
    if not isinstance(keys, set) or not keys:
        return False

    ents: set[str] = set()
    for k in keys:
        if not isinstance(k, str) or "|" not in k:
            continue
        ent = k.split("|", 1)[0].strip().lower()
        if ent:
            ents.add(ent)

    hazard_amb = "cliff" in ents

    hazard_near = False
    try:
        hazard_near = body_cliff_distance(ctx) == "near"
    except Exception:
        hazard_near = False

    if not (hazard_amb or hazard_near):
        return False

    ns = _wm_navsummary_get_v1(ctx)
    navsummary_present = bool(ns)

    topo_support = False
    if navsummary_present:
        try:
            topo_support = _wm_probe_supported_by_topology_v1(ctx)
        except Exception:
            topo_support = False

    # Backward-compatible Step 15C behavior:
    # if NavSummary is missing, a hazard-relevant ambiguity should still be able to trigger probe.
    if hazard_amb:
        if navsummary_present and not (topo_support or hazard_near):
            return False
    else:
        # No explicit cliff ambiguity: require stronger evidence.
        if not navsummary_present:
            return False
        if not (hazard_near and topo_support):
            return False

    # Debounce (cooldown)
    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    last = getattr(ctx, "wm_probe_last_step", None)
    last_i = int(last) if isinstance(last, int) else None

    try:
        cooldown = int(getattr(ctx, "wm_probe_cooldown_steps", 3) or 3)
    except Exception:
        cooldown = 3
    cooldown = max(0, min(50, int(cooldown)))

    if last_i is not None and cooldown > 0 and (step_now - last_i) < cooldown:
        return False

    return True


def _gate_probe_ambiguity_explain_body_first(world, _drives: Drives, ctx) -> str:  # pylint: disable=unused-argument
    """
    Human-readable explanation for the Step 15C probe gate.
    """
    if ctx is None:
        return "dev_gate: True, trigger: ctx missing"

    keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
    keys_txt = sorted(list(keys)) if isinstance(keys, set) else []

    ents: set[str] = set()
    for k in keys_txt:
        if isinstance(k, str) and "|" in k:
            ents.add(k.split("|", 1)[0].strip().lower())

    hazard_amb = "cliff" in ents

    hazard_near = False
    try:
        hazard_near = body_cliff_distance(ctx) == "near"
    except Exception:
        hazard_near = False

    ns = _wm_navsummary_get_v1(ctx)
    navsummary_present = bool(ns)

    topo_support = False
    if navsummary_present:
        try:
            topo_support = _wm_probe_supported_by_topology_v1(ctx)
        except Exception:
            topo_support = False

    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    last = getattr(ctx, "wm_probe_last_step", None)
    last_i = int(last) if isinstance(last, int) else None

    try:
        cooldown = int(getattr(ctx, "wm_probe_cooldown_steps", 3) or 3)
    except Exception:
        cooldown = 3
    cooldown = max(0, min(50, int(cooldown)))

    blocked = False
    if last_i is not None and cooldown > 0 and (step_now - last_i) < cooldown:
        blocked = True

    fallback_mode = False
    if hazard_amb and not navsummary_present:
        fallback_mode = True

    return (
        "dev_gate: True, trigger: "
        f"scratch_keys={len(keys_txt)} ents={sorted(list(ents))} "
        f"hazard_amb(cliff)={hazard_amb} hazard_near={hazard_near} "
        f"navsummary_present={navsummary_present} topo_support={topo_support} "
        f"fallback_mode={fallback_mode} "
        f"cooldown={cooldown} blocked={blocked} "
        f"(step_now={step_now}, last_probe={last_i}) {_wm_navsummary_explain_bits_v1(ctx)}"
    )


def _gate_recover_fall_trigger_body_first(world, _drives: Drives, ctx) -> bool:
    """
    RecoverFall gate that prefers BodyMap for posture when available, falling back
    to WorldGraph near-NOW predicates otherwise.

    Trigger logic:
      • If explicit fall cues are present → fire (regardless of posture).
      • If BodyMap is fresh:
            posture == 'fallen'   → fire
            posture == 'standing' → do NOT fire
            posture == 'resting'  → do NOT fire
      • Otherwise fall back to graph near-NOW: pred:posture:fallen near NOW.
    """
    # Fall cues always override
    if any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"]):
        return True

    # Prefer BodyMap when fresh
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None
    if bp is not None:
        return bp == "fallen"

    # Fallback to episode graph (legacy behavior)
    return has_pred_near_now(world, "posture:fallen")


def _gate_recover_fall_explain(world, _drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_recover_fall_trigger_body_first.
    """
    fall_cue = any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])

    bodymap_stale = True
    bp = None
    try:
        bodymap_stale = bodymap_is_stale(ctx) if ctx is not None else True
        bp = body_posture(ctx) if ctx is not None and not bodymap_stale else None
    except Exception:
        bodymap_stale = True
        bp = None

    if bp is not None:
        fallen = bp == "fallen"
    else:
        fallen = has_pred_near_now(world, "posture:fallen")

    return (
        "dev_gate: True, trigger: "
        f"fallen={fallen} (bodymap_posture={bp or 'n/a'}, bodymap_stale={bodymap_stale}) "
        f"or fall_cue={fall_cue} cues={present_cue_bids(world)}"
    )


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

_EFE_SCORES_VERSION = "efe_scores_v1"


def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _norm_deficit(val: float, thresh: float) -> float:
    """Normalize how far ABOVE a threshold we are into [0,1]."""
    try:
        v = float(val)
        t = float(thresh)
    except Exception:
        return 0.0
    if v <= t:
        return 0.0
    denom = (1.0 - t) if (1.0 - t) > 1e-9 else 1e-9
    return _clamp01((v - t) / denom)


def _norm_cold(warmth: float, cold_thresh: float = 0.30) -> float:
    """Normalize how far BELOW the cold threshold we are into [0,1]."""
    try:
        w = float(warmth)
        t = float(cold_thresh)
    except Exception:
        return 0.0
    if w >= t:
        return 0.0
    denom = t if t > 1e-9 else 1e-9
    return _clamp01((t - w) / denom)


def _efe_zone_from_ctx(ctx) -> str:
    """
    Best-effort zone label used as a safety proxy for the EFE stub.

    Preference order:
      1) BodyMap-derived zone (if available)
      2) navpatch_priors["zone"] (already JSON-safe and present in cycle logs)
      3) "unknown"
    """
    # (1) BodyMap if possible
    try:
        if ctx is not None:
            z = body_space_zone(ctx)
            if isinstance(z, str) and z:
                return z
    except Exception:
        pass

    # (2) navpatch priors bundle
    try:
        priors = getattr(ctx, "navpatch_last_priors", None)
        if isinstance(priors, dict):
            z = priors.get("zone")
            if isinstance(z, str) and z:
                return z
    except Exception:
        pass

    return "unknown"


def _efe_stage_from_ctx(ctx) -> str:
    """Stage is useful context, but we keep it optional and best-effort."""
    try:
        priors = getattr(ctx, "navpatch_last_priors", None)
        if isinstance(priors, dict):
            st = priors.get("stage")
            if isinstance(st, str) and st:
                return st
    except Exception:
        pass
    return "unknown"


def _efe_global_ambiguity_from_navpatch(ctx) -> float:
    """
    Use NavPatch matching residuals as a proxy for perceptual ambiguity.

    We treat best-match error (best['err'] in [0,1]) as a local mismatch signal.
    This is NOT yet the commit/ambiguous classification (that is Step 2); it is
    simply "how well did the patch match its nearest stored prototype?"
    """
    matches = getattr(ctx, "navpatch_last_matches", None)
    if not isinstance(matches, list) or not matches:
        return 0.0

    errs: list[float] = []
    for rec in matches:
        if not isinstance(rec, dict):
            continue
        best = rec.get("best")
        if not isinstance(best, dict):
            continue
        err = best.get("err")
        if isinstance(err, (int, float)):
            errs.append(float(err))

    if not errs:
        return 0.0
    return _clamp01(sum(errs) / max(1, len(errs)))


def _efe_risk_stub_v1(policy_name: str, *, zone: str) -> float:
    """
    Risk proxy: map coarse zone + policy semantics into a [0,1] cost.

    This is intentionally tiny and transparent. We will revise once we have
    a richer environment (goat_foraging_* tasks) and real movement policies.
    """
    base = {"unsafe_cliff_near": 0.80, "safe": 0.10, "unknown": 0.40}.get(zone, 0.40)

    # Heuristic adjustments by policy role (very small; keep readable)
    if policy_name == "policy:rest":
        base += 0.20  # resting while unsafe is a bad idea
    elif policy_name == "policy:follow_mom":
        base -= 0.20  # movement away from danger tends to reduce risk
    elif policy_name in ("policy:stand_up", "policy:recover_fall"):
        base -= 0.10  # recovery actions reduce immediate risk of being prone
    elif policy_name == "policy:seek_nipple":
        base += 0.05  # mild: attention diverted (stub)

    return _clamp01(base)


def _efe_preference_stub_v1(policy_name: str, drives: Drives, ctx, *, zone: str, amb_global: float) -> float:
    """
    Preference proxy: expected "goodness" of an action given drives + safety context.

    Returns a [0,1] value (higher is more preferred).
    """
    hunger = float(getattr(drives, "hunger", 0.0) or 0.0)
    fatigue = float(getattr(drives, "fatigue", 0.0) or 0.0)
    warmth = float(getattr(drives, "warmth", 1.0) or 1.0)

    hunger_need = _norm_deficit(hunger, float(HUNGER_HIGH))
    fatigue_need = _norm_deficit(fatigue, float(FATIGUE_HIGH))
    cold_need = _norm_cold(warmth, 0.30)

    # Safety posture signal (BodyMap-first via controller helper)
    fallen = False
    try:
        fallen = bool(_fallen_near_now(None if ctx is None else getattr(ctx, "working_world", None), ctx, max_hops=3))  # best-effort
    except Exception:
        try:
            fallen = bool(_fallen_near_now(None, ctx, max_hops=3))
        except Exception:
            fallen = False

    # Policy-specific preference
    if policy_name == "policy:seek_nipple":
        return _clamp01(1.00 * hunger_need)

    if policy_name == "policy:rest":
        return _clamp01(1.00 * fatigue_need + 0.25 * cold_need)

    if policy_name in ("policy:stand_up", "policy:recover_fall"):
        return 1.0 if fallen else 0.0

    if policy_name == "policy:follow_mom":
        # When unsafe, moving is strongly preferred; otherwise it is a mild default preference.
        return 0.60 if zone == "unsafe_cliff_near" else 0.20

    if policy_name == "policy:explore_check":
        # Epistemic-ish bias: when ambiguity is high, exploring becomes more attractive.
        return _clamp01(0.10 + 0.40 * float(amb_global))

    return 0.0


def _efe_ambiguity_stub_v1(policy_name: str, *, amb_global: float) -> float:
    """
    Ambiguity proxy: start from global perceptual ambiguity and apply tiny policy deltas.

    Lower is better (it is a cost term).
    """
    a = _clamp01(float(amb_global))

    if policy_name == "policy:explore_check":
        a -= 0.20
    elif policy_name == "policy:follow_mom":
        a -= 0.10
    elif policy_name == "policy:rest":
        a += 0.10

    return _clamp01(a)


def compute_efe_scores_stub_v1(_world, drives: Drives, ctx, candidates: list[str], *, triggered_all: list[str] | None = None) -> dict[str, Any]:
    """
    Compute a small, JSON-safe EFE-style scoring bundle for candidate policies.

    Output (JSON-safe):
      {
        "v": "efe_scores_v1",
        "enabled": true,
        "stage": "...",
        "zone": "...",
        "amb_global": 0.23,
        "weights": {"risk": 1.0, "ambiguity": 1.0, "preference": 1.0},
        "candidates": [...],
        "triggered_all": [...],          # optional
        "scores": [
            {"policy": "...", "risk": .., "ambiguity": .., "preference": .., "total": .., "rank": 1},
            ...
        ],
      }

    Convention:
      - risk/ambiguity are costs (lower is better)
      - preference is a value (higher is better)
      - total is minimized: total = w_risk*risk + w_amb*ambiguity - w_pref*preference
    """
    zone = _efe_zone_from_ctx(ctx)
    stage = _efe_stage_from_ctx(ctx)
    amb_global = _efe_global_ambiguity_from_navpatch(ctx)

    try:
        w_r = float(getattr(ctx, "efe_w_risk", 1.0))
    except Exception:
        w_r = 1.0
    try:
        w_a = float(getattr(ctx, "efe_w_ambiguity", 1.0))
    except Exception:
        w_a = 1.0
    try:
        w_p = float(getattr(ctx, "efe_w_preference", 1.0))
    except Exception:
        w_p = 1.0

    # De-dupe candidates while preserving order
    seen: set[str] = set()
    cand: list[str] = []
    for nm in candidates:
        if isinstance(nm, str) and nm and nm not in seen:
            seen.add(nm)
            cand.append(nm)

    rows: list[dict[str, Any]] = []
    for nm in cand:
        r = _efe_risk_stub_v1(nm, zone=zone)
        a = _efe_ambiguity_stub_v1(nm, amb_global=amb_global)
        p = _efe_preference_stub_v1(nm, drives, ctx, zone=zone, amb_global=amb_global)
        total = (w_r * r) + (w_a * a) - (w_p * p)

        rows.append(
            {
                "policy": nm,
                "risk": float(r),
                "ambiguity": float(a),
                "preference": float(p),
                "total": float(total),
            }
        )

    rows.sort(key=lambda d: float(d.get("total", 0.0)))
    for i, d in enumerate(rows, 1):
        d["rank"] = i

    out: dict[str, Any] = {
        "v": _EFE_SCORES_VERSION,
        "enabled": True,
        "stage": stage,
        "zone": zone,
        "amb_global": float(amb_global),
        "weights": {"risk": float(w_r), "ambiguity": float(w_a), "preference": float(w_p)},
        "candidates": list(cand),
        "scores": rows,
    }
    if isinstance(triggered_all, list):
        out["triggered_all"] = [x for x in triggered_all if isinstance(x, str)]
    return out


def _efe_render_summary_line(ctx, *, max_policies: int = 5) -> str:
    """
    Render a compact, single-line EFE summary for terminal logs.

    Only prints when ctx.efe_enabled is True. This is meant to be "one more lens"
    next to deficit/non-drive/RL notes, not a new control rule yet.
    """
    if ctx is None or not bool(getattr(ctx, "efe_enabled", False)):
        return ""

    efe = getattr(ctx, "efe_last", None)
    if not isinstance(efe, dict):
        return ""

    zone = efe.get("zone", "unknown")
    amb = efe.get("amb_global", None)
    try:
        amb_txt = f"{float(amb):.2f}"
    except Exception:
        amb_txt = "n/a"

    scores = efe.get("scores", None)
    if not isinstance(scores, list) or not scores:
        return f"[efe] zone={zone} amb={amb_txt} (no scores)\n"

    parts: list[str] = []
    lim = max(1, int(max_policies))
    for row in scores[:lim]:
        if not isinstance(row, dict):
            continue
        nm = row.get("policy")
        if not isinstance(nm, str):
            continue
        try:
            tot = float(row.get("total", 0.0))
            r = float(row.get("risk", 0.0))
            a = float(row.get("ambiguity", 0.0))
            p = float(row.get("preference", 0.0))
            parts.append(f"{nm}(G={tot:+.2f} r={r:.2f} a={a:.2f} p={p:.2f})")
        except Exception:
            parts.append(f"{nm}(G=n/a)")

    if not parts:
        return f"[efe] zone={zone} amb={amb_txt} (no scores)\n"

    if len(scores) > lim:
        parts.append("...")

    return f"[efe] zone={zone} amb={amb_txt} " + " | ".join(parts) + "\n"


@dataclass
class PolicyGate:
    """Declarative description of a controller gate used by PolicyRuntime (dev_gating,
       trigger, and optional explain)."""
    name: str
    dev_gate: Callable[[Any], bool]                      # ctx -> bool
    trigger: Callable[[Any, Any, Any], bool]             # (world, drives, ctx) -> bool
    explain: Optional[Callable[[Any, Any, Any], str]] = None


class PolicyRuntime:
    """Runtime wrapper around a gate catalog that filters by dev gating, evaluates
         triggers, and executes one step."""
    def __init__(self, catalog: List[PolicyGate]):
        """Initialize with a catalog (list of PolicyGate) and compute the 'loaded'
           subset based on ctx.dev gating."""
        self.catalog = list(catalog)
        self.loaded: List[PolicyGate] = []


    def refresh_loaded(self, ctx) -> None:
        """Recompute `self.loaded` by applying each gate's dev_gating predicate to `ctx`.
        """
        self.loaded = [p for p in self.catalog if _safe(p.dev_gate, ctx)]


    def list_loaded_names(self) -> List[str]:
        """Return names of currently loaded (dev-eligible) gates.
        """
        return [p.name for p in self.loaded]


    def consider_and_maybe_fire(
        self,
        world,
        drives,
        ctx,
        tie_break: str = "first",
        *,
        exec_world=None,
    ) -> str:  # pylint: disable=unused-argument,too-many-branches,too-many-locals
        """Evaluate triggers, choose one policy, and execute it once.

        The optional ``exec_world`` compatibility seam lets callers evaluate
        triggers on one world object but execute the chosen controller primitive
        on another. When it is omitted, execution happens on ``world`` exactly as
        before.
        """
        _ = tie_break  # compatibility seam for older call sites / docs, avoid unused-argument warning
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        triggered_all = [p.name for p in matches]

        try:
            debug_state = _follow_mom_bridge_state_v1(world, ctx)
        except Exception as e:
            debug_state = {"error": f"{e.__class__.__name__}: {e}"}
        try:
            debug_stage = getattr(ctx, "lt_obs_last_stage", None)
        except Exception:
            debug_stage = None
        try:
            debug_step = int(getattr(ctx, "controller_steps", 0) or 0)
        except Exception:
            debug_step = -1
        policy_debug: dict[str, Any] = {
            "schema": "experiment_policy_debug_v1",
            "step": int(debug_step),
            "stage": debug_stage if isinstance(debug_stage, str) else None,
            "state": dict(debug_state) if isinstance(debug_state, dict) else {},
            "matches_initial": list(triggered_all),
            "post_latch_sequence": None,
            "matches_after_post_latch": None,
            "bridge_follow_mom": None,
            "forced_follow_mom": None,
            "matches_after_bridge": None,
            "suppress_follow_mom": None,
            "matches_after_topology": None,
            "fallen_safety_filter": None,
            "matches_after_safety": None,
            "matches_before_choice": None,
            "chosen": None,
        }

        post_latch_sequence = False
        try:
            post_latch_sequence = _newborn_post_latch_sequence_active_v1(world, ctx)
        except Exception:
            post_latch_sequence = False
        policy_debug["post_latch_sequence"] = bool(post_latch_sequence)

        # Hard sequence lock: after latch, earlier locomotor/search policies should
        # not compete with the late feeding/rest sequence.
        #
        #   before milk_drinking: allow Suckle, block Rest
        #   after milk_drinking : allow Rest, block Suckle
        #
        # This prevents the failure mode where one settling Rest occurs, then the
        # selector falls back into repeated Suckle forever.
        if post_latch_sequence:
            milk_drinking_now = _newborn_milk_drinking_current_v1(world, ctx)

            blocked_post_latch = {"policy:follow_mom", "policy:seek_nipple"}
            if milk_drinking_now:
                blocked_post_latch.add("policy:suckle")
            else:
                blocked_post_latch.add("policy:rest")

            matches = [p for p in matches if p.name not in blocked_post_latch]

            if not milk_drinking_now and not any(p.name == "policy:suckle" for p in matches):
                try:
                    suckle_gate = next((p for p in self.loaded if p.name == "policy:suckle"), None)
                except Exception:
                    suckle_gate = None

                if suckle_gate is not None and _safe(suckle_gate.trigger, world, drives, ctx):
                    matches.append(suckle_gate)

            if milk_drinking_now and not any(p.name == "policy:rest" for p in matches):
                try:
                    rest_gate = next((p for p in self.loaded if p.name == "policy:rest"), None)
                except Exception:
                    rest_gate = None

                if rest_gate is not None and _safe(rest_gate.trigger, world, drives, ctx):
                    matches.append(rest_gate)

        policy_debug["matches_after_post_latch"] = [p.name for p in matches]
        forced_follow_mom = False
        bridge_follow_mom = False
        if not post_latch_sequence:
            try:
                bridge_follow_mom = _should_force_follow_mom_bridge_v1(world, ctx)
            except Exception:
                bridge_follow_mom = False

        # If follow_mom already matched because its own gate fired under the newborn bridge,
        # remember that now so the later topology suppression step does not remove it.
        if bridge_follow_mom and any(p.name == "policy:follow_mom" for p in matches):
            forced_follow_mom = True

        if not matches:
            forced = None
            if (not post_latch_sequence) and bridge_follow_mom:
                try:
                    forced = next((p for p in self.loaded if p.name == "policy:follow_mom"), None)
                except Exception:
                    forced = None

            if forced is None:
                policy_debug["bridge_follow_mom"] = bool(bridge_follow_mom)
                policy_debug["forced_follow_mom"] = bool(forced_follow_mom)
                policy_debug["matches_after_bridge"] = []
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

            matches = [forced]
            forced_follow_mom = True
        policy_debug["bridge_follow_mom"] = bool(bridge_follow_mom)
        policy_debug["forced_follow_mom"] = bool(forced_follow_mom)
        policy_debug["matches_after_bridge"] = [p.name for p in matches]

        # SurfaceGrid/NavSummary-first suppression hook:
        # block the fallback follow_mom path only when local topology says the move is
        # effectively unsafe or no visible safe outlet exists.
        try:
            suppress_follow_mom = _wm_follow_mom_blocked_by_topology_v1(ctx)
        except Exception:
            suppress_follow_mom = False

        if suppress_follow_mom and not forced_follow_mom:
            matches = [p for p in matches if p.name != "policy:follow_mom"]
            if not matches:
                policy_debug["suppress_follow_mom"] = bool(suppress_follow_mom)
                policy_debug["matches_after_topology"] = []
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

        policy_debug["suppress_follow_mom"] = bool(suppress_follow_mom)
        policy_debug["matches_after_topology"] = [p.name for p in matches]

        try:
            if ctx is not None:
                ctx.ac_triggered_policies = list(triggered_all)
        except Exception:
            pass

        try:
            if ctx is not None:
                ctx.experiment_last_llm_advice_summary = {}
        except Exception:
            pass

        # Fallen posture near NOW forces safety-only policies.
        fallen_safety_active = _fallen_near_now(world, ctx, max_hops=3)
        policy_debug["fallen_safety_filter"] = bool(fallen_safety_active)

        if fallen_safety_active:
            safety_only = {"policy:recover_fall", "policy:stand_up"}
            matches = [p for p in matches if p.name in safety_only]
            if not matches:
                policy_debug["matches_after_safety"] = []
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

        policy_debug["matches_after_safety"] = [p.name for p in matches]

        # --- EFE scoring (diagnostic only) ---
        try:
            if ctx is not None and bool(getattr(ctx, "efe_enabled", False)):
                cand_names = [p.name for p in matches]
                ctx.efe_last = compute_efe_scores_stub_v1(world, drives, ctx, cand_names, triggered_all=triggered_all)
                if isinstance(ctx.efe_last, dict):
                    ctx.efe_last_scores = list(ctx.efe_last.get("scores", []))
                else:
                    ctx.efe_last_scores = []
            else:
                if ctx is not None:
                    ctx.efe_last = {}
                    ctx.efe_last_scores = []
        except Exception:
            try:
                if ctx is not None:
                    ctx.efe_last = {"v": _EFE_SCORES_VERSION, "enabled": False, "error": "efe_compute_exception"}
                    ctx.efe_last_scores = []
            except Exception:
                pass

        # Choose by drive-deficit.
        # "deficit" here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD).
        def deficit(name: str) -> float:
            d = 0.0
            if name == "policy:seek_nipple":
                d += max(0.0, float(getattr(drives, "hunger", 0.0)) - float(HUNGER_HIGH)) * 1.0
            if name == "policy:rest":
                d += max(0.0, float(getattr(drives, "fatigue", 0.0)) - float(FATIGUE_HIGH)) * 0.7
            return d

        def stable_idx(p) -> int:
            try:
                return [q.name for q in self.catalog].index(p.name)
            except ValueError:
                return 10_000


        def non_drive_priority(name: str) -> float:
            """Tiny non-drive tie-break score.

            Used only as a SECONDARY score when drive-urgency deficits tie.

            Intent:
              - StandUp: prefer when BodyMap is fresh and posture == 'fallen'.
              - SeekNipple: once the kid is upright and genuinely near mom, prefer
                nipple-seeking over continuing to spam follow_mom.
              - Suckle: once the newborn is latched but not yet drinking, prefer
                feeding continuation over renewed search/follow actions.
              - Rest: once milk drinking has occurred, prefer resting over
                re-seeking so short blackout windows do not keep breaking latch.
              - RecoverFall: prefer when explicit fall cues are present or when
                repeated stand-up attempts are not taking effect.
            """
            if name == "policy:stand_up":
                try:
                    if ctx is not None and not bodymap_is_stale(ctx) and body_posture(ctx) == "fallen":
                        return 2.0
                except Exception:
                    pass
                return 0.0

            if name == "policy:seek_nipple":
                try:
                    if ctx is not None and not bodymap_is_stale(ctx):
                        bp = body_posture(ctx)
                        md = body_mom_distance(ctx)
                        ns = body_nipple_state(ctx)
                        zone = body_space_zone(ctx)

                        if (
                            bp == "standing"
                            and md in ("near", "touching")
                            and ns not in ("latched",)
                            and zone != "unsafe_cliff_near"
                        ):
                            return 1.5
                except Exception:
                    pass
                return 0.0

            if name == "policy:suckle":
                try:
                    if _should_force_suckle_bridge_v1(world, ctx):
                        return 4.5
                except Exception:
                    pass
                return 0.0

            if name == "policy:recover_fall":
                cue_bonus = 0.0
                try:
                    if any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"]):
                        cue_bonus = 1.0
                except Exception:
                    cue_bonus = 0.0

                streak = 0
                try:
                    hist = getattr(ctx, "posture_discrepancy_history", []) if ctx is not None else []
                    if isinstance(hist, list) and hist:
                        for entry in reversed(hist[-10:]):
                            s = str(entry)
                            if (
                                ("from policy:stand_up" in s)
                                and ("env posture=" in s and "fallen" in s)
                                and ("policy-expected posture=" in s and "standing" in s)
                            ):
                                streak += 1
                            else:
                                break
                except Exception:
                    streak = 0

                hist_bonus = 0.0
                if streak >= 2:
                    hist_bonus = min(4.0, 2.5 + 0.5 * (streak - 2))
                return cue_bonus + hist_bonus

            if name == "policy:rest":
                try:
                    if _should_force_rest_bridge_v1(world, ctx):
                        return 4.0
                except Exception:
                    pass
                return 0.0

            if name == "policy:probe":
                return 3.0

            return 0.0

        adviser_choice_name = None
        llm_pick_note = ""
        if bool(getattr(ctx, "experiment_llm_adviser_enabled", False)) and len(matches) >= 2:
            try:
                cand_info = _experiment_llm_candidate_rows_v1(
                    matches,
                    world=world,
                    drives=drives,
                    ctx=ctx,
                    deficit_fn=deficit,
                    non_drive_fn=non_drive_priority,
                    stable_idx_fn=stable_idx,
                )
                candidate_rows = cand_info.get("candidate_rows") if isinstance(cand_info, dict) else []
                adviser_summary = _run_experiment_llm_adviser_once_v1(world, drives, ctx, candidate_rows)
            except Exception as e:
                adviser_summary = {
                    "enabled": True,
                    "called": False,
                    "ok": False,
                    "why": "adviser_exception",
                    "error": f"{e.__class__.__name__}: {e}",
                }

            try:
                if ctx is not None:
                    ctx.experiment_last_llm_advice_summary = dict(adviser_summary) if isinstance(adviser_summary, dict) else {}
                    if bool(adviser_summary.get("called")):
                        ctx.experiment_llm_call_count = int(getattr(ctx, "experiment_llm_call_count", 0) or 0) + 1
                        latency_v = adviser_summary.get("latency_ms")
                        if isinstance(latency_v, (int, float)) and not isinstance(latency_v, bool):
                            ctx.experiment_llm_latency_ms_total = (
                                float(getattr(ctx, "experiment_llm_latency_ms_total", 0.0) or 0.0) + float(latency_v)
                            )
            except Exception:
                pass

            try:
                if (
                    ctx is not None
                    and bool(adviser_summary.get("called"))
                    and not bool(adviser_summary.get("ok"))
                    and not bool(getattr(ctx, "experiment_llm_first_error_printed", False))
                ):
                    detail = adviser_summary.get("error_detail")
                    detail = detail if isinstance(detail, dict) else {}

                    msg = detail.get("message") or adviser_summary.get("error") or adviser_summary.get("why")
                    param = detail.get("param")
                    code = detail.get("code")

                    summary = str(msg) if msg is not None else str(adviser_summary.get("why"))
                    if isinstance(param, str) and param:
                        summary += f" | param={param}"
                    if isinstance(code, str) and code:
                        summary += f" | code={code}"

                    print(f"[llm-adviser] first API error: {summary}")
                    ctx.experiment_llm_first_error_printed = True
                    ctx.experiment_llm_first_error_summary = summary

                    if param == "text.format.schema" or code == "invalid_json_schema":
                        ctx.experiment_llm_adviser_enabled = False
            except Exception:
                pass


            if bool(adviser_summary.get("ok")):
                rec_policy = adviser_summary.get("recommended_policy")
                if isinstance(rec_policy, str) and any(p.name == rec_policy for p in matches):
                    adviser_choice_name = rec_policy
                    conf_txt = _experiment_metric_text_v1(adviser_summary.get("confidence"))
                    lat_txt = _experiment_metric_text_v1(adviser_summary.get("latency_ms"))
                    llm_pick_note = (
                        "[llm-adviser] "
                        f"model={adviser_summary.get('model')} recommended={rec_policy} "
                        f"confidence={conf_txt} latency_ms={lat_txt} "
                        f"candidates={adviser_summary.get('candidate_policies')}"
                    )
            elif bool(adviser_summary.get("called")) or adviser_summary.get("why"):
                llm_pick_note = (
                    "[llm-adviser] fallback "
                    f"why={adviser_summary.get('why')} model={adviser_summary.get('model')} "
                    f"candidates={adviser_summary.get('candidate_policies')}"
                )


        def _run_probe_stub_v1() -> dict[str, Any]:
            """Runner-side probe execution shim.

            Why this exists
            ---------------
            The runner has a real probe gate and tests expect probe bookkeeping to change
            immediately when the probe wins. If the controller primitive catalog does not yet
            expose an executable ``policy:probe``, we still need a minimal local execution path.

            Effects
            -------
            - Save the previous grid precision
            - Raise ctx.navpatch_precision_grid to ctx.wm_probe_grid_precision
            - Stamp wm_probe_last_step / wm_probe_restore_step
            - Return a normalized controller-like payload
            """
            step_now = int(getattr(ctx, "controller_steps", 0) or 0)
            duration = int(getattr(ctx, "wm_probe_duration_steps", 2) or 2)
            duration = max(1, min(50, duration))

            prev_precision = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
            probe_precision = float(getattr(ctx, "wm_probe_grid_precision", 0.50) or 0.50)

            try:
                ctx.wm_probe_prev_navpatch_precision_grid = prev_precision
            except Exception:
                pass
            try:
                ctx.navpatch_precision_grid = probe_precision
            except Exception:
                pass
            try:
                ctx.wm_probe_last_step = step_now
                ctx.wm_probe_restore_step = step_now + duration
            except Exception:
                pass

            try:
                update_skill("policy:probe", 0.05, ok=True)
            except Exception:
                pass

            return {
                "policy": "policy:probe",
                "status": "ok",
                "reward": 0.05,
                "notes": "runner-side probe shim raised navpatch precision",
                "binding": None,
            }

        rl_pick_note = ""
        did_explore = False
        rl_exploit_kind = ""
        tie_break_label = ""
        selector_kind = "deficit"

        if isinstance(adviser_choice_name, str) and adviser_choice_name:
            chosen = next((p for p in matches if p.name == adviser_choice_name), None)
            if chosen is None:
                adviser_choice_name = None

        rl_enabled = bool(getattr(ctx, "rl_enabled", False))
        if isinstance(adviser_choice_name, str) and adviser_choice_name:
            selector_kind = "llm_adviser"
        elif rl_enabled:
            eps = getattr(ctx, "rl_epsilon", None)
            if eps is None:
                eps = getattr(ctx, "jump", 0.0)
            try:
                eps_f = float(eps)
            except Exception:
                eps_f = 0.0
            eps_f = max(0.0, min(1.0, eps_f))

            def _bump(field_name: str) -> None:
                try:
                    if ctx is not None and hasattr(ctx, field_name):
                        setattr(ctx, field_name, int(getattr(ctx, field_name, 0)) + 1)
                except Exception:
                    pass

            if eps_f > 0.0 and random.random() < eps_f:
                chosen = random.choice(matches)
                did_explore = True
                _bump("rl_explore_steps")
            else:
                rl_delta_raw = getattr(ctx, "rl_delta", 0.0)
                try:
                    rl_delta = float(rl_delta_raw)
                except (TypeError, ValueError):
                    rl_delta = 0.0
                rl_delta = max(rl_delta, 0.0)

                scored = [(p, deficit(p.name), non_drive_priority(p.name)) for p in matches]
                best_deficit = max(d for _, d, _ in scored)
                near_best = [(p, d, nd) for p, d, nd in scored if (best_deficit - d) <= rl_delta]

                if len(near_best) == 1:
                    chosen = near_best[0][0]
                    rl_exploit_kind = "deficit"
                else:
                    eps_tie = 1e-9
                    best_nd = max(nd for _, _, nd in near_best)
                    top_nd = [(p, d, nd) for p, d, nd in near_best if abs(nd - best_nd) <= eps_tie]

                    if len(top_nd) == 1:
                        chosen = top_nd[0][0]
                        rl_exploit_kind = "non_drive_tiebreak"
                    else:
                        chosen = max(
                            top_nd,
                            key=lambda t: (
                                skill_q(t[0].name, default=0.0),
                                t[1],
                                t[2],
                                -stable_idx(t[0]),
                            ),
                        )[0]
                        rl_exploit_kind = "q_soft_tiebreak"

                if len(near_best) > 1:
                    bits: list[str] = []
                    for p, d, nd in sorted(near_best, key=lambda t: (-t[1], -t[2], t[0].name)):
                        qv = skill_q(p.name, default=0.0)
                        bits.append(f"{p.name}(def={d:.3f}, nd={nd:.2f}, q={qv:+.2f})")
                    if len(bits) > 6:
                        bits = bits[:6] + ["..."]

                    chosen_q = skill_q(chosen.name, default=0.0)
                    chosen_nd = non_drive_priority(chosen.name)

                    if rl_exploit_kind == "non_drive_tiebreak":
                        rl_pick_note = (
                            "[rl-pick] chosen via non-drive tiebreak in deficit near-tie band: "
                            f"best_def={best_deficit:.3f} delta={rl_delta:.3f} "
                            f"→ {chosen.name} (nd={chosen_nd:.2f}, q={chosen_q:+.2f}) "
                            f"among [{', '.join(bits)}]"
                        )
                    elif rl_exploit_kind == "q_soft_tiebreak":
                        rl_pick_note = (
                            "[rl-pick] chosen via q-soft-tiebreak in deficit near-tie band: "
                            f"best_def={best_deficit:.3f} delta={rl_delta:.3f} "
                            f"→ {chosen.name} (q={chosen_q:+.2f}) among [{', '.join(bits)}]"
                        )

                _bump("rl_exploit_steps")
        else:
            chosen = max(matches, key=lambda p: (deficit(p.name), non_drive_priority(p.name), -stable_idx(p)))

            try:
                scored_final = [(p.name, deficit(p.name), non_drive_priority(p.name)) for p in matches]
                if scored_final:
                    eps = 1e-9
                    best_d = max(d for _, d, _ in scored_final)
                    top = [(nm, nd) for (nm, d, nd) in scored_final if abs(d - best_d) <= eps]

                    if len(top) > 1:
                        best_nd = max(nd for _, nd in top)
                        n_best_nd = sum(1 for _, nd in top if abs(nd - best_nd) <= eps)

                        if n_best_nd == 1:
                            tie_break_label = "non_drive_priority(deficit_tie)"
                        else:
                            tie_break_label = "stable_order(deficit_tie)"
            except Exception:
                tie_break_label = ""

        if not (isinstance(adviser_choice_name, str) and adviser_choice_name):
            selector_kind = "deficit"
            if rl_enabled:
                if did_explore:
                    selector_kind = "rl_explore"
                elif rl_exploit_kind == "non_drive_tiebreak":
                    selector_kind = "rl_exploit(non_drive_tiebreak)"
                elif rl_exploit_kind == "q_soft_tiebreak":
                    selector_kind = "rl_exploit(q_soft_tiebreak)"
                else:
                    selector_kind = "rl_exploit(deficit)"

        try:
            policy_debug["matches_before_choice"] = [p.name for p in matches]
            policy_debug["chosen"] = getattr(chosen, "name", None)
            _experiment_policy_debug_record_v1(ctx, policy_debug)
        except Exception:
            pass

        base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
        foa = compute_foa(world, ctx, max_hops=2)
        cands = candidate_anchors(world, ctx)
        pre_expl = chosen.explain(world, drives, ctx) if chosen.explain else "explain: (not provided)"

        try:
            exec_target = exec_world if exec_world is not None else world
            before_n = len(exec_target._bindings)

            has_real_probe = False
            if chosen.name == "policy:probe":
                try:
                    has_real_probe = any(getattr(p, "name", None) == "policy:probe" for p in PRIMITIVES)
                except Exception:
                    has_real_probe = False

            if chosen.name == "policy:probe" and not has_real_probe:
                result = _run_probe_stub_v1()
            else:
                result = action_center_step(exec_target, ctx, drives, preferred=chosen.name)

            after_n = len(exec_target._bindings)
            delta_n = after_n - before_n

            label = chosen.name
            if isinstance(result, dict):
                raw_label = result.get("policy")
                if isinstance(raw_label, str) and raw_label:
                    label = raw_label
        except Exception as e:
            return f"{chosen.name} (error: {e})"

        exec_line = ""
        if isinstance(result, dict):
            status = result.get("status")
            reward = result.get("reward")
            binding = result.get("binding")
            if status and status != "noop":
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                exec_line = f"[executed] {label} ({status}, reward={rtxt}) binding={binding}\n"

        pick_debug_line = ""
        try:
            triggered_final = [p.name for p in matches]
            trig_txt = ", ".join(triggered_all)
            final_txt = ", ".join(triggered_final)

            def _fmt_deficits(names: list[str], limit: int = 12) -> str:
                parts: list[str] = []
                lim = max(0, int(limit))
                for nm in names[:lim]:
                    try:
                        parts.append(f"{nm}:{deficit(nm):.2f}")
                    except Exception:
                        parts.append(f"{nm}:n/a")
                if len(names) > lim:
                    parts.append("...")
                return ", ".join(parts)

            def _fmt_non_drive(names: list[str], limit: int = 12) -> str:
                parts: list[str] = []
                lim = max(0, int(limit))
                for nm in names[:lim]:
                    try:
                        parts.append(f"{nm}:{non_drive_priority(nm):.2f}")
                    except Exception:
                        parts.append(f"{nm}:n/a")
                if len(names) > lim:
                    parts.append("...")
                return ", ".join(parts)

            deficits_all = _fmt_deficits(triggered_all, limit=12)
            non_drive_all = _fmt_non_drive(triggered_all, limit=12)

            pick_debug = f"[pick] best_policy={label} best_by={selector_kind}"
            if tie_break_label:
                pick_debug += f" tie_break={tie_break_label}"
            pick_debug += f" triggered=[{trig_txt}]"

            if deficits_all:
                pick_debug += f" deficits=[{deficits_all}]"

            if non_drive_all:
                pick_debug += f" non_drive=[{non_drive_all}]"

            if triggered_final != triggered_all:
                pick_debug += f" safety_filtered=[{final_txt}]"

                deficits_final = _fmt_deficits(triggered_final, limit=12)
                if deficits_final:
                    pick_debug += f" deficits_filtered=[{deficits_final}]"

                non_drive_final = _fmt_non_drive(triggered_final, limit=12)
                if non_drive_final:
                    pick_debug += f" non_drive_filtered=[{non_drive_final}]"

            if chosen.name != label:
                pick_debug += f" selected={chosen.name}"

            pick_debug_line = pick_debug + "\n"
        except Exception:
            pick_debug_line = ""

        gate_for_label = next((p for p in self.loaded if p.name == label), chosen)
        post_expl = gate_for_label.explain(exec_target, drives, ctx) if gate_for_label.explain else "explain: (not provided)"
        rl_line = (rl_pick_note + "\n") if rl_pick_note else ""
        llm_line = (llm_pick_note + "\n") if llm_pick_note else ""

        return (
            f"{label} (added {delta_n} bindings)\n"
            f"{pick_debug_line}"
            f"{llm_line}"
            f"{rl_line}"
            f"{exec_line}"
            f"pre:  {pre_expl}\n"
            f"base: {base}\n"
            f"foa:  {foa}\n"
            f"cands:{cands}\n"
            f"post: {post_expl}"
        )


def _safe(fn, *args):
    """Invoke a predicate defensively (exceptions → False).
    """
    try:
        return bool(fn(*args))
    except Exception:
        return False


CATALOG_GATES: List[PolicyGate] = [
    PolicyGate(
        name="policy:stand_up",
        # Neonatal only; later profiles/ages may choose a different gate.
        dev_gate=lambda ctx: getattr(ctx, "age_days", 0.0) <= 3.0,
        trigger=_gate_stand_up_trigger_body_first,
        explain=_gate_stand_up_explain,
    ),

    PolicyGate(
        name="policy:seek_nipple",
        dev_gate=lambda ctx: True,
        trigger=_gate_seek_nipple_trigger_body_first,
        explain=_gate_seek_nipple_explain,
    ),

    PolicyGate(
        name="policy:rest",
        dev_gate=lambda ctx: True,  # available at all stages; selection is by trigger/deficit
        trigger=_gate_rest_trigger_body_space,
        explain=_gate_rest_explain_body_space,
    ),

    PolicyGate(
        name="policy:probe",
        dev_gate=lambda ctx: True,
        trigger=_gate_probe_ambiguity_trigger_body_first,
        explain=_gate_probe_ambiguity_explain_body_first,
    ),

    PolicyGate(
        name="policy:follow_mom",
        dev_gate=lambda ctx: True,
        trigger=_gate_follow_mom_trigger_body_space,
        explain=_gate_follow_mom_explain_body_space,
    ),

    PolicyGate(
        name="policy:suckle",
        dev_gate=lambda ctx: True,
        trigger=_gate_suckle_trigger_newborn_v1,
        explain=_gate_suckle_explain_newborn_v1,
    ),

    PolicyGate(
        name="policy:recover_miss",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: has_pred_near_now(W, "nipple:missed"),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: nipple:missed near NOW={has_pred_near_now(W,'nipple:missed')}"
        ),
    ),

    PolicyGate(
        name="policy:recover_fall",
        dev_gate=lambda ctx: True,
        trigger=_gate_recover_fall_trigger_body_first,
        explain=_gate_recover_fall_explain,
    ),

]


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


# print_tagging_and_policies_help moved to cca8_profiles.py or cca8_guidance.py.

# --------------------------------------------------------------------------------------
# Profiles & tutorials: experimental profiles (dry-run) + narrative fallbacks
# --------------------------------------------------------------------------------------


# _goat_defaults moved to cca8_profiles.py or cca8_guidance.py.


# _print_goat_fallback moved to cca8_profiles.py or cca8_guidance.py.


# profile_rcos_api moved to cca8_profiles.py or cca8_guidance.py.


# profile_chimpanzee moved to cca8_profiles.py or cca8_guidance.py.


# profile_human moved to cca8_profiles.py or cca8_guidance.py.


# profile_human_multi_brains moved to cca8_profiles.py or cca8_guidance.py.


# profile_society_multi_agents moved to cca8_profiles.py or cca8_guidance.py.


# profile_multi_brains_adv_planning moved to cca8_profiles.py or cca8_guidance.py.


# profile_superhuman moved to cca8_profiles.py or cca8_guidance.py.


# _open_readme_tutorial moved to cca8_profiles.py or cca8_guidance.py.


# run_new_user_tour moved to cca8_profiles.py or cca8_guidance.py.


# --------------------------------------------------------------------------------------
# World/intro flows: profile selection, startup notices, preflight-lite
# --------------------------------------------------------------------------------------

# choose_profile moved to cca8_profiles.py or cca8_guidance.py.


def versions_dict() -> dict:
    """Collect versions/paths for CCA8 runner components and environment modules."""
    mods = [
        "cca8_world_graph",
        "cca8_controller",
        "cca8_temporal",
        "cca8_column",
        "cca8_features",
        "cca8_env",
        "cca8_experiments",
        "cca8_openai",
        "cca8_working_memory",
        "cca8_profiles",
        "cca8_guidance",
        "cca8_navpatch",
        "cca8_rcos",
        "cca8_rcos_experiments",
        "cca8_state_integrity",
        "cca8_teaching",
        "cca8_predictive",
        "cca8_test_fixtures",
    ]

    info = {
        "runner": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }

    for m in mods:
        ver, path = _module_version_and_path(m)
        key = m.replace("cca8_", "")
        info[key] = ver
        info[key + "_path"] = path

    return info


def versions_text() -> str:
    """
    Return a human-readable summary of CCA8 component versions.

    Includes the runner plus the main non-debug CCA8 modules used by the
    interactive runner, environment, memory, experiments, and test fixtures.
    """
    d = versions_dict()
    keys = (
        "runner",
        "world_graph",
        "controller",
        "temporal",
        "column",
        "features",
        "env",
        "experiments",
        "openai",
        "working_memory",
        "profiles",
        "guidance",
        "navpatch",
        "rcos",
        "rcos_experiments",
        "state_integrity",
        "teaching",
        "test_fixtures",
    )
    lines = [f"{k}: {d.get(k, 'n/a')}" for k in keys]
    return "\n".join(lines)


class TeeTextIO:
    """File-like stream that duplicates writes into multiple underlying streams.

    Purpose:
        - Keep interactive output visible in the terminal
        - Also persist the full transcript to a file (e.g., terminal.txt)
        - Avoid rewriting existing print(...) calls across the codebase

    Notes:
        - This affects *all* print() calls that ultimately write to sys.stdout/sys.stderr.
        - It is safe for interactive sessions (input() relies on stdout.flush()).
    """
    def __init__(self, *streams):
        self._streams = list(streams)

    def write(self, s: str) -> int:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self) -> None:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        try:
            return any(getattr(st, "isatty", lambda: False)() for st in self._streams)
        except Exception:
            return False

    @property
    def encoding(self) -> str:
        '''Keep downstream code happy if it queries sys.stdout.encoding
        '''
        try:
            return getattr(self._streams[0], "encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"


def install_terminal_tee(path: str = "terminal.txt", *, append: bool = True, also_stderr: bool = True) -> None:
    """Duplicate stdout (and optionally stderr) to a UTF-8 text file.

    Call this once near program start (inside main) to capture a full transcript
    of an interactive run without losing on-screen output.

    Args:
        path: Output file path (e.g., "terminal.txt").
        append: If True, append; if False, overwrite each run.
        also_stderr: If True, duplicate stderr too (tracebacks end up in the file).
    """
    if getattr(sys, "_cca8_terminal_tee_installed", False):
        return

    mode = "a" if append else "w"
    # NOTE:
    # We intentionally keep this file handle open for the full program lifetime so
    # stdout/stderr can be tee'd during interactive use. It is closed via atexit
    # in _cleanup() below. Using `with open(...)` here would close it immediately.
    f = open(path, mode, encoding="utf-8", errors="replace", buffering=1)  # pylint: disable=consider-using-with

    sys._cca8_terminal_tee_installed = True  # type: ignore[attr-defined]

    # Keep originals so we can restore them at exit.
    sys._cca8_stdout_orig = sys.stdout  # type: ignore[attr-defined]
    sys._cca8_stderr_orig = sys.stderr  # type: ignore[attr-defined]
    sys._cca8_terminal_tee_file = f     # type: ignore[attr-defined]

    sys.stdout = TeeTextIO(sys.stdout, f)
    if also_stderr:
        sys.stderr = TeeTextIO(sys.stderr, f)

    import atexit
    def _cleanup() -> None:
        # Flush tee streams first, then restore and close.
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        try:
            sys.stdout = sys._cca8_stdout_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            sys.stderr = sys._cca8_stderr_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass
    atexit.register(_cleanup)


def print_startup_notices(world) -> None:
    '''print active planner and other statuses at
    startup of the runner
    '''
    try:
        planner = str(world.get_planner()).upper()
        expl = {
            "BFS": "Breadth-First Search (unweighted shortest path by hop count)",
            "DIJKSTRA": "Dijkstra (lowest total edge weight; equals BFS when all weights=1)",
        }.get(planner)
        if expl:
            print(f"[planner] Active planner on startup: {planner} — {expl}")
        else:
            print(f"[planner] Active planner on startup: {planner}")


    except Exception as e:
        print(f"unable to retrieve which active planner is running: {e}")
        logging.error(f"Unable to retrieve startup active planner status: {e}", exc_info=True)


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

    binding_id, posture_tag, meta = _latest_posture_binding(world, require_policy=True)
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
    expected = dict(out.get("expected")) if isinstance(out.get("expected"), dict) else {}

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
        basis = dict(out.get("basis")) if isinstance(out.get("basis"), dict) else {}
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

    pred_posture = pred_error.prediction.expected.get("posture")
    if isinstance(pred_posture, str) and not pred_posture:
        pred_posture = None

    source_policy = pred_error.prediction.policy
    if isinstance(source_policy, str) and not source_policy:
        source_policy = None

    return {
        "schema": "prediction_comparison_result_v1",
        "has_prediction": True,
        "observed_slots": observed_slots,
        "error_record": error_record,
        "err_vec": err_vec,
        "pred_posture": pred_posture if isinstance(pred_posture, str) else None,
        "obs_posture": observed_slots.get("posture"),
        "source_policy": source_policy if isinstance(source_policy, str) else None,
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


def _prediction_compact_map_text_v1(value: Any) -> str:
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
        f"pred_err_v0={{{_prediction_compact_map_text_v1(s['pred_err_v0'])}}} "
        "[src=ctx.pred_err_v0_last]"
    )

    if s["has_next_prediction"]:
        lines.append(
            "  next: "
            f"policy={s['next_policy'] or '(n/a)'} "
            f"expected={{{_prediction_compact_map_text_v1(s['next_expected'])}}} "
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
            f"errors={{{_prediction_compact_map_text_v1(s['last_error_by_slot'])}}} "
            "[src=ctx.prediction_last_error_record]"
        )
        lines.append(
            "  observed: "
            f"{{{_prediction_compact_map_text_v1(s['last_observed'])}}} "
            f"expected={{{_prediction_compact_map_text_v1(s['last_expected'])}}}"
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
        next_txt = f"{s['next_policy'] or '?'} expected={{{_prediction_compact_map_text_v1(s['next_expected'])}}}"

    last_txt = "none"
    if s["has_last_error"]:
        last_txt = (
            f"matched={s['last_matched']} mismatches={s['last_mismatch_count']} "
            f"severity={s['last_severity']:.2f} errors={{{_prediction_compact_map_text_v1(s['last_error_by_slot'])}}}"
        )

    return f"[pred] status={s['status']} next={next_txt}; last={last_txt}; history_count={s['history_count']}"


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
            "safety_residual_slots": (
                list(expected.get("safety_residual_slots"))
                if isinstance(expected.get("safety_residual_slots"), list)
                else []
            ),
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


def snapshot_text(world, drives=None, ctx=None, policy_rt=None) -> str:
    """
    Render a human-readable snapshot of the runtime state.
    Each value also shows its source attribute for maintainers, e.g., "[src=ctx.ticks]".

    Sections:
    - Header/anchors: EMBODIMENT (ctx.body), NOW/LATEST from world anchors.
    - CTX (Context): agent state (profile, age_days, ticks, winners_k) +
      temporal breadcrumbs: vhash64(now)=ctx.tvec64(), epoch=ctx.boundary_no,
      epoch_vhash64=ctx.boundary_vhash64.
    - TEMPORAL: params from ctx.temporal (dim, sigma, jump), cos_to_last_boundary;
      repeats vhash64(now)/epoch/epoch_vhash64; prints a back-compat alias "vhash64:".
    - DRIVES: drives.hunger/fatigue/warmth.
    - POLICIES (executed this session): per-policy SkillStat telemetry (from skill_readout()).
    - ELIGIBLE NOW: policies with dev_gate(ctx) == True (policy_rt.list_loaded_names()).
    - BINDINGS/EDGES: symbolic nodes/links with their raw sources noted.
    - Footer: nodes/edges count summary.
    """

    def _safe(getter, default=None):
        try:
            return getter()
        except Exception:
            return default

    lines: List[str] = []
    lines.append("\n--------------------------------------------------------------------------------------")
    lines.append(f"WorldGraph snapshot at {datetime.now()}")
    lines.append("--------------------------------------------------------------------------------------")
    lines.extend(_snapshot_temporal_legend())

    # Header / anchors
    body = (getattr(ctx, "body", None)
            or getattr(getattr(ctx, "hal", None), "body", None)
            or "(none)")
    lines.append(f"EMBODIMENT: body={body}  [src=ctx.body or ctx.hal.body]")

    now_id = _anchor_id(world, "NOW")
    latest = getattr(world, "_latest_binding_id", "?")
    lines.append(f"NOW={now_id}  [src=_anchor_id('NOW')]  LATEST={latest}  [src=world._latest_binding_id]")
    origin_id = _anchor_id(world, "NOW_ORIGIN")
    lines.append(f"NOW_ORIGIN={origin_id}  [src=_anchor_id('NOW_ORIGIN')]")
    lines.append(f"NOW_LATEST={latest}  [alias for LATEST/world._latest_binding_id]")
    lines.append("")

    # CTX (Context)
    lines.append("CTX (Context):")
    lines.append("(runtime agent state (profile/age/ticks) + TemporalContext soft clock)")
    if ctx is not None:
        # Print scalar-ish fields explicitly so we can annotate their sources.
        def _add_ctx_scalar(name: str, src: str, fmt="{v}"):
            v = getattr(ctx, name, None)
            if isinstance(v, float):
                lines.append(f"  {name}: {v:.4f}  [src={src}]")
            elif v is not None:
                lines.append(f"  {name}: {fmt.format(v=v)}  [src={src}]")

        _add_ctx_scalar("age_days", "ctx.age_days", "{v:.4f}")
        _add_ctx_scalar("body", "ctx.body")
        _add_ctx_scalar("hal", "ctx.hal")
        _add_ctx_scalar("profile", "ctx.profile")
        lines.append(f"  autonomic_ticks: {getattr(ctx,'ticks',0)}  [src=ctx.ticks]")
        _add_ctx_scalar("winners_k", "ctx.winners_k")

        lines.append(
            "  counts: controller_steps="
            f"{getattr(ctx,'controller_steps',0)}, cog_cycles={getattr(ctx,'cog_cycles',0)}, "
            f"temporal_epochs={getattr(ctx,'boundary_no',0)}, autonomic_ticks={getattr(ctx,'ticks',0)}" )

        # Harmonized temporal breadcrumbs in CTX
        vhash_now = _safe(ctx.tvec64)
        lines.append(f"  vhash64(now): {vhash_now if vhash_now else '(n/a)'}  [src=ctx.tvec64()]")
        epoch_vh = getattr(ctx, "boundary_vhash64", None)
        lines.append(f"  epoch_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [src=ctx.boundary_vhash64]")
        epoch_no = getattr(ctx, "boundary_no", 0)
        lines.append(f"  epoch: {epoch_no}  [src=ctx.boundary_no]")
    else:
        lines.append("  (none)")
    lines.append("")

    # TEMPORAL
    tv = getattr(ctx, "temporal", None)
    if tv:
        lines.append("TEMPORAL:")
        dim   = getattr(tv, "dim", 0)
        sigma = getattr(tv, "sigma", 0.0)
        jump  = getattr(tv, "jump", 0.0)
        lines.append(f"  dim={dim}  [src=ctx.temporal.dim]")
        lines.append(f"  sigma={sigma:.4f}  [src=ctx.temporal.sigma]")
        lines.append(f"  jump={jump:.4f}  [src=ctx.temporal.jump]")

        c = _safe(ctx.cos_to_last_boundary)
        lines.append(
            f"  cos_to_last_boundary: {c:.4f}  [src=ctx.cos_to_last_boundary()]"
            if isinstance(c, float) else
            "  cos_to_last_boundary: (n/a)  [src=ctx.cos_to_last_boundary()]"
        )

        vhash_now = _safe(ctx.tvec64)
        if vhash_now:
            lines.append(f"  vhash64(now): {vhash_now}  [src=ctx.tvec64()]")
            # Back-compat alias for tests expecting plain 'vhash64:'
            lines.append(f"  vhash64: {vhash_now}  [alias of vhash64(now)]")
        else:
            lines.append("  vhash64(now): (n/a)  [src=ctx.tvec64()]")
            lines.append("  vhash64: (n/a)  [alias of vhash64(now)]")

        epoch_no = getattr(ctx, "boundary_no", 0)
        lines.append(f"  epoch: {epoch_no}  [src=ctx.boundary_no]")
        epoch_vh = getattr(ctx, "boundary_vhash64", None)
        if epoch_vh:
            lines.append(f"  epoch_vhash64: {epoch_vh}  [src=ctx.boundary_vhash64]")
            lines.append(f"  last_boundary_vhash64: {epoch_vh}  [alias of epoch_vhash64]")
        # One-line timekeeping summary (compact view)
        if ctx is not None:
            lines.append("TIMEKEEPING: " + timekeeping_line(ctx))

        lines.append("")
    else:
        lines.append("TEMPORAL: (none)")
        lines.append("")

    # DRIVES
    lines.append("DRIVES:")
    if drives is not None:
        try:
            lines.append(
                f"  hunger={drives.hunger:.2f}, fatigue={drives.fatigue:.2f}, warmth={drives.warmth:.2f}  "
                "[src=drives.hunger; drives.fatigue; drives.warmth]"
            )
        except Exception:
            lines.append("  (unavailable)")
    else:
        lines.append("  (none)")
    lines.append("")

    # BODY (BodyMap + near-world) one-line summary
    if ctx is not None:
        try:
            bp = body_posture(ctx)
            md = body_mom_distance(ctx)
            ns = body_nipple_state(ctx)
            # shelter/cliff may not be present on older runs; guard separately
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

            line = (
                "BODY: "
                f"posture={bp or '(n/a)'} "
                f"mom={md or '(n/a)'} "
                f"nipple={ns or '(n/a)'} "
                f"shelter={sd or '(n/a)'} "
                f"cliff={cd or '(n/a)'}"
            )
            if zone is not None:
                line += f" zone={zone}"
            lines.append(line)
        except Exception:
            # Snapshot must stay robust even if BodyMap is missing.
            lines.append("BODY: (unavailable)")
    else:
        lines.append("BODY: (ctx unavailable)")
    lines.append("")

    lines.extend(render_prediction_feedback_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_observation_update_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_expected_current_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_accepted_current_lines_v1(ctx))
    lines.append("")

    lines.extend(render_working_navmap_surface_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_transition_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_scope_frame_lines_v1(ctx))
    lines.append("")

    # POLICIES (skills readout)
    lines.append("POLICIES:\n (already run at least once, with their SkillStat statistics)  [src=skill_readout()]")
    try:
        sr = skill_readout()
        if sr.strip():
            for ln in sr.strip().splitlines():
                lines.append(f"  {ln}")
        else:
            lines.append("  (none)")
    except Exception:
        lines.append("  (unavailable)")
    lines.append("")

    # POLICY GATES (availability)
    lines.append("POLICIES ELIGIBLE (meet devpt requirements):  [src=policy_rt.list_loaded_names()]")
    try:
        names = policy_rt.list_loaded_names() if policy_rt is not None else []
        if names:
            for nm in names:
                lines.append(f"  - {nm}")
        else:
            lines.append("  (none)")
    except Exception:
        lines.append("  (unavailable)")
    lines.append("")

    # BINDINGS
    lines.append("BINDINGS:")
    for bid in _sorted_bids(world):
        b = world._bindings[bid]
        tags = ", ".join(sorted(getattr(b, "tags", [])))
        eng = getattr(b, "engrams", None)
        if isinstance(eng, dict) and eng:
            parts = []
            for slot, val in eng.items():
                eid = val.get("id") if isinstance(val, dict) else None
                parts.append(f"{slot}:{eid[:8]}…" if isinstance(eid, str) else slot)
            lines.append(f"{bid}: [{tags}] engrams=[{', '.join(parts)}]  [src=world._bindings['{bid}'].tags/engrams]")
        else:
            lines.append(f"{bid}: [{tags}]  [src=world._bindings['{bid}'].tags]")

    # PROMINENCE (top tags; runtime convenience)
    lines.append("")
    lines.append("PROMINENCE (top tags; obs>=2, sorted by act):")
    try:
        rows = world.prominence_top(n=12, sort_by="act", min_obs=2)
    except Exception:
        rows = []
    if not rows:
        lines.append("(none)")
    else:
        for tag, rec in rows:
            try:
                obs = int(rec.get("obs", 0))
            except Exception:
                obs = 0
            try:
                act = float(rec.get("act", 0.0))
            except Exception:
                act = 0.0
            last_step = rec.get("last_step")
            step_key = rec.get("step_key")
            lines.append(f"{tag}: obs={obs} act={act:.2f} last_step={last_step} [{step_key}]")

    # EDGES (collapsed duplicates)
    lines.append("")
    lines.append("EDGES:")
    from collections import Counter
    def _edge_lines_for(bid: str) -> list[str]:
        b = world._bindings[bid]
        edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                 getattr(b, "links", []) or getattr(b, "outgoing", []))
        out: list[str] = []
        if isinstance(edges, list):
            for e in edges:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    out.append(f"{bid} --{rel}--> {dst}  [src=world._bindings['{bid}'].edges]")
        return out

    all_edge_lines: list[str] = []
    for bid in _sorted_bids(world):
        all_edge_lines.extend(_edge_lines_for(bid))

    if not all_edge_lines:
        lines.append("(none)")
    else:
        for line, n in Counter(all_edge_lines).items():
            lines.append(line if n == 1 else f"{line}  ×{n}")

    # Summary footer
    edges_total = len(all_edge_lines)
    lines.append(f"Summary: nodes={len(world._bindings)} edges={edges_total}")
    lines.append("--------------------------------------------------------------------------------------\n")
    return "\n".join(lines)


def export_snapshot(world, drives=None, ctx=None, policy_rt=None,
                    path_txt="world_snapshot.txt", _path_dot=None) -> None:
    """Write a complete snapshot of bindings + edges to a text file (no DOT).
    """
    text_blob = snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt)
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(text_blob + "\n")

    path_txt_abs = os.path.abspath(path_txt)
    out_dir = os.path.dirname(path_txt_abs)
    print("Exported snapshot (text only):")
    print(f"  {path_txt_abs}")
    print(f"Directory: {out_dir}")


def recent_bindings_text(world, limit: int = 5) -> str:
    """
    Build a short, source-annotated list of the last `limit` bindings.
    For each binding, show tags, engram slots, a tiny edge preview, and key meta.
    """
    lines = []
    last_ids = _sorted_bids(world)[-limit:]
    if not last_ids:
        return "(no bindings yet)\n"

    for bid in last_ids:
        b = world._bindings.get(bid)
        # tags
        tags = ", ".join(sorted(getattr(b, "tags", []))) if b else ""
        lines.append(f"  {bid}: tags=[{tags}]  [src=world._bindings['{bid}'].tags]")

        # engrams
        eng = getattr(b, "engrams", None) if b else None
        if isinstance(eng, dict) and eng:
            parts = []
            for slot, val in eng.items():
                eid = val.get("id") if isinstance(val, dict) else None
                parts.append(f"{slot}:{(eid[:8] + '…') if isinstance(eid, str) else '(id?)'}")
            lines.append(f"      engrams=[{', '.join(parts)}]  [src=world._bindings['{bid}'].engrams]")
        else:
            lines.append(f"      engrams=(none)  [src=world._bindings['{bid}'].engrams]")

        # edges (preview up to 3)
        edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                 getattr(b, "links", []) or getattr(b, "outgoing", [])) if b else []
        if isinstance(edges, list) and edges:
            preview = []
            for e in edges[:3]:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    preview.append(f"{rel}:{dst}")
            more = f" (+{len(edges)-3} more)" if len(edges) > 3 else ""
            lines.append(
                f"      outdeg={len(edges)} preview=[{', '.join(preview)}]{more}  "
                f"[src=world._bindings['{bid}'].edges]"
            )
        else:
            lines.append(f"      outdeg=0  [src=world._bindings['{bid}'].edges]")

        # meta highlights (best-effort)
        meta = getattr(b, "meta", {}) if b else {}
        if isinstance(meta, dict) and meta:
            pol = meta.get("policy") or meta.get("created_by")
            created = meta.get("created_at") or meta.get("time") or meta.get("ts")
            extras = []
            if pol:     extras.append(f"policy={pol}")
            if created: extras.append(f"created_at={created}")
            if extras:
                lines.append(f"      meta: {' '.join(extras)}  [src=world._bindings['{bid}'].meta]")

    return "\n".join(lines) + "\n"


def prediction_observed_slots_from_env_obs_v1(env_obs: EnvObservation) -> dict[str, str]:
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


def update_body_world_from_obs(ctx, env_obs) -> None:
    """
    Update the tiny BodyMap (ctx.body_world) from an EnvObservation.

    We treat BodyMap as a structured register:
      - posture slot reflects posture:* / resting predicates
      - mom slot reflects proximity:mom:* predicates
      - nipple slot reflects nipple:* / milk:drinking predicates

    EnvObservation is observation-space; we mirror its discrete predicates here.
    """
    body_world = getattr(ctx, "body_world", None)
    body_ids = getattr(ctx, "body_ids", {}) or {}
    if body_world is None or not body_ids:
        return

    preds = set(getattr(env_obs, "predicates", []) or [])

    # --- posture slot ---
    posture_bid = body_ids.get("posture")
    if posture_bid and posture_bid in body_world._bindings:
        b = body_world._bindings[posture_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Strip old posture-like tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and (
                    t.startswith("pred:posture:")
                    or t == "pred:resting"
                    or t == "resting"
                )
            )
        }

        new_posture: str | None = None
        if "posture:standing" in preds:
            new_posture = "standing"
        elif "posture:fallen" in preds:
            new_posture = "fallen"
        elif "resting" in preds:
            new_posture = "resting"

        if new_posture == "resting":
            tags.add("pred:resting")
        elif new_posture in ("standing", "fallen"):
            tags.add(f"pred:posture:{new_posture}")

        b.tags = tags

    # --- mom-distance slot ---
    mom_bid = body_ids.get("mom")
    if mom_bid and mom_bid in body_world._bindings:
        b = body_world._bindings[mom_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old proximity tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:proximity:mom:")
            )
        }

        if "proximity:mom:close" in preds:
            tags.add("pred:proximity:mom:close")
        elif "proximity:mom:far" in preds:
            tags.add("pred:proximity:mom:far")

        b.tags = tags

    # --- shelter-distance slot ---
    shelter_bid = body_ids.get("shelter")
    if shelter_bid and shelter_bid in body_world._bindings:
        b = body_world._bindings[shelter_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old shelter proximity tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:proximity:shelter:")
            )
        }

        # Only update if the observation actually carries shelter proximity.
        if "proximity:shelter:near" in preds:
            tags.add("pred:proximity:shelter:near")
        elif "proximity:shelter:far" in preds:
            tags.add("pred:proximity:shelter:far")

        b.tags = tags

    # --- cliff / dangerous drop slot ---
    cliff_bid = body_ids.get("cliff")
    if cliff_bid and cliff_bid in body_world._bindings:
        b = body_world._bindings[cliff_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old cliff hazard tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:hazard:cliff:")
            )
        }

        # Hazard semantics: near vs far; if not present we leave previous value.
        if "hazard:cliff:near" in preds:
            tags.add("pred:hazard:cliff:near")
        elif "hazard:cliff:far" in preds:
            tags.add("pred:hazard:cliff:far")

        b.tags = tags

    # --- nipple/latch slot ---
    nipple_bid = body_ids.get("nipple")
    if nipple_bid and nipple_bid in body_world._bindings:
        b = body_world._bindings[nipple_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old nipple/milk tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and (
                    t.startswith("pred:nipple:")
                    or t == "pred:milk:drinking"
                )
            )
        }

        # Infer a simple nipple state from observation predicates
        if "nipple:latched" in preds:
            tags.add("pred:nipple:latched")
            if "milk:drinking" in preds:
                tags.add("pred:milk:drinking")
        elif "nipple:found" in preds:
            tags.add("pred:nipple:found")
        else:
            # Fallback: hidden if nothing else observed
            tags.add("pred:nipple:hidden")

        b.tags = tags

    # --- recency marker ---
    # We treat controller_steps as our integer "clock" for BodyMap staleness.
    try:
        # If controller_steps is not yet initialized, fall back to 0.
        steps = int(getattr(ctx, "controller_steps", 0))
        # Only set the attribute if it exists (Ctx defines bodymap_last_update_step).
        if hasattr(ctx, "bodymap_last_update_step"):
            ctx.bodymap_last_update_step = steps
    except Exception:
        # BodyMap bookkeeping must never break the env→body bridge.
        pass


def seqerr_update_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """
    Sequential/error v1 (stub): compute short-window temporal deltas + prediction error.

    Intent
    ------
    In CCA7, a cerebellum-inspired unit processes how sensory signals evolve over time and
    computes mismatch signals (prediction error). For CCA8 we implement a minimal, transparent
    version that:

      1) Tracks a short history window (default 4) of:
         - raw numeric channels (EnvObservation.raw_sensors)
         - discrete predicate slots (EnvObservation.predicates)

      2) Computes:
         - raw_delta: per-channel curr - prev
         - raw_err  : constant-velocity extrapolation error when we have >=3 frames:
                      pred_next = prev + (prev - prev_prev)
                      raw_err   = curr - pred_next
         - slot_changes: list of discrete slot transitions (e.g., proximity:mom:far -> close)
         - slot_stability: how many consecutive frames each slot token has remained unchanged

    Outputs (stored on ctx)
    -----------------------
      - ctx.seqerr_last: latest JSON-safe bundle
      - ctx.seqerr_history: ring buffer of last seqerr_window frames

    Optional predictive-coding seam (OFF by default)
    ------------------------------------------------
    If ctx.seqerr_attention_enabled is True, set ctx.seqerr_attention_request when a channel
    error magnitude exceeds ctx.seqerr_attention_threshold and no request is pending.

    Safety
    ------
    Must never raise exceptions to callers.
    """
    if ctx is None or env_obs is None:
        return
    if not bool(getattr(ctx, "seqerr_enabled", True)):
        return

    def _as_int(x: Any) -> int:
        try:
            return int(x)
        except Exception:
            return 0

    def _as_float(x: Any) -> float | None:
        # bool is an int subclass; treat it as non-numeric for our purposes.
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return float(x)
        try:
            return float(x)
        except Exception:
            return None

    def _slot_key(tok: str) -> str:
        tok = str(tok)
        return tok.rsplit(":", 1)[0] if ":" in tok else tok

    # ---- time/step reference (best-effort) ----
    env_meta = getattr(env_obs, "env_meta", None)
    env_meta = env_meta if isinstance(env_meta, dict) else {}
    t_now = _as_float(env_meta.get("time_since_birth"))
    step_ref = env_meta.get("step_index")
    if step_ref is None:
        step_ref = getattr(ctx, "controller_steps", 0)
    step_now = _as_int(step_ref)

    # ---- raw sensors (numeric only; JSON-safe) ----
    raw_in = getattr(env_obs, "raw_sensors", None)
    raw: dict[str, float] = {}
    if isinstance(raw_in, dict):
        for k, v in raw_in.items():
            if not isinstance(k, str) or not k:
                continue
            fv = _as_float(v)
            if fv is None:
                continue
            raw[k] = fv

    # ---- discrete slot snapshot (one token per slot family) ----
    preds_in = getattr(env_obs, "predicates", None)
    slots: dict[str, str] = {}
    if isinstance(preds_in, list):
        for p in preds_in:
            if p is None:
                continue
            tok = str(p).replace("pred:", "", 1)
            slots[_slot_key(tok)] = tok

    # ---- history ring buffer ----
    hist = getattr(ctx, "seqerr_history", None)
    if not isinstance(hist, list):
        hist = []
        try:
            ctx.seqerr_history = hist
        except Exception:
            hist = []

    frame = {"step": step_now, "t": t_now, "raw": dict(raw), "slots": dict(slots)}
    hist.append(frame)

    try:
        win = int(getattr(ctx, "seqerr_window", 4) or 4)
    except Exception:
        win = 4
    win = max(2, min(25, win))
    if len(hist) > win:
        del hist[: len(hist) - win]

    # ---- dt estimate ----
    dt = 1.0
    if len(hist) >= 2:
        t0 = hist[-2].get("t")
        t1 = hist[-1].get("t")
        if isinstance(t0, (int, float)) and isinstance(t1, (int, float)):
            d = float(t1) - float(t0)
            if d > 1e-9:
                dt = float(d)

    # ---- deltas + errors ----
    raw_delta: dict[str, float] = {}
    raw_err: dict[str, float] = {}
    slot_changes: list[dict[str, str]] = []
    slot_stability: dict[str, int] = {}

    if len(hist) >= 2:
        prev_raw = hist[-2].get("raw")
        prev_raw = prev_raw if isinstance(prev_raw, dict) else {}
        for k, v1 in raw.items():
            v0 = prev_raw.get(k)
            if isinstance(v0, (int, float)):
                raw_delta[k] = float(v1) - float(v0)

        prev_slots = hist[-2].get("slots")
        prev_slots = prev_slots if isinstance(prev_slots, dict) else {}
        for slot, tok in slots.items():
            prev_tok = prev_slots.get(slot)
            if isinstance(prev_tok, str) and prev_tok != tok:
                slot_changes.append({"slot": slot, "prev": prev_tok, "now": tok})

    if len(hist) >= 3:
        prev_raw = hist[-2].get("raw")
        prev_prev_raw = hist[-3].get("raw")
        if isinstance(prev_raw, dict) and isinstance(prev_prev_raw, dict):
            for k, v1 in raw.items():
                v0 = prev_raw.get(k)
                v_1 = prev_prev_raw.get(k)
                if isinstance(v0, (int, float)) and isinstance(v_1, (int, float)):
                    pred_next = float(v0) + (float(v0) - float(v_1))
                    raw_err[k] = float(v1) - pred_next

    for slot, tok in slots.items():
        n = 1
        for i in range(len(hist) - 2, -1, -1):
            slots_i = hist[i].get("slots")
            if not isinstance(slots_i, dict):
                break
            if slots_i.get(slot) == tok:
                n += 1
            else:
                break
        slot_stability[slot] = n

    # ---- attention suggestion (stored always; applied only when enabled) ----
    best_key: str | None = None
    best_mag = 0.0
    best_src = ""

    for k, e in raw_err.items():
        mag = abs(float(e))
        if mag > best_mag:
            best_mag = mag
            best_key = k
            best_src = "raw_err"

    if best_key is None:
        for k, d in raw_delta.items():
            mag = abs(float(d))
            if mag > best_mag:
                best_mag = mag
                best_key = k
                best_src = "raw_delta"

    attention_suggest: str | None = None
    if best_key is not None:
        if "mom" in best_key:
            attention_suggest = "mom"
        elif "temperature" in best_key:
            attention_suggest = "self:temperature"
        else:
            attention_suggest = best_key

    try:
        ctx.seqerr_last = {
            "step": int(step_now),
            "t": t_now,
            "dt": float(dt),
            "raw": dict(raw),
            "raw_delta": dict(raw_delta),
            "raw_err": dict(raw_err),
            "slots": dict(slots),
            "slot_changes": list(slot_changes),
            "slot_stability": dict(slot_stability),
            "attention_suggest": attention_suggest,
            "attention_src": best_src,
            "attention_mag": float(best_mag),
        }
    except Exception:
        pass

    try:
        if bool(getattr(ctx, "seqerr_attention_enabled", False)) and attention_suggest:
            thresh = float(getattr(ctx, "seqerr_attention_threshold", 0.25) or 0.25)
            if float(best_mag) >= thresh and getattr(ctx, "seqerr_attention_request", None) is None:
                ctx.seqerr_attention_request = attention_suggest
    except Exception:
        pass

    try:
        if bool(getattr(ctx, "seqerr_verbose", False)) and slot_changes:
            parts = []
            for c in slot_changes[:4]:
                if isinstance(c, dict):
                    parts.append(f"{c.get('slot')}:{c.get('prev')}→{c.get('now')}")
            more = " …" if len(slot_changes) > 4 else ""
            print(f"[seqerr] step={step_now} slot_changes={len(slot_changes)} [{', '.join(parts)}]{more}")
    except Exception:
        pass


def _write_spatial_scene_edges(world, ctx, env_obs, token_to_bid: Dict[str, str]) -> None: #pylint: disable=unused-argument
    """
    Write minimal scene-graph style edges for this observation.

    Today we keep this extremely conservative:

      • Only when 'resting' is present in env_obs.predicates (kid is in a relatively
        stable configuration).

      • Treat the NOW anchor as "SELF".

      • For any bindings created this step with tokens:
            proximity:mom:close
            proximity:shelter:near
            hazard:cliff:near
        we add a single edge:

            NOW --near--> <that binding>

        if such an edge does not already exist.

    The destination binding's predicate tags carry the semantics (mom vs shelter vs cliff);
    the edge label 'near' is intentionally generic to avoid label explosion.
    """
    preds = set(getattr(env_obs, "predicates", []) or [])
    # Only annotate a tiny scene when resting is present in this observation
    if "resting" not in preds:
        return

    try:
        now_id = _anchor_id(world, "NOW")
        if not now_id or now_id == "?":
            return
        src = world._bindings.get(now_id)
        if not src:
            return

        # Collect existing 'near' edges out of NOW so we don't duplicate them.
        existing: set[str] = set()
        edges_raw = (
            getattr(src, "edges", []) or
            getattr(src, "out", []) or
            getattr(src, "links", []) or
            getattr(src, "outgoing", [])
        )
        if isinstance(edges_raw, list):
            for e in edges_raw:
                if not isinstance(e, dict):
                    continue
                if e.get("label") == "near":
                    dst = (
                        e.get("to")
                        or e.get("dst")
                        or e.get("dst_id")
                        or e.get("id")
                    )
                    if isinstance(dst, str):
                        existing.add(dst)

        # Candidate tokens we know how to represent.
        candidates = [
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:near",
        ]

        for tok in candidates:
            bid = token_to_bid.get(tok)
            if not isinstance(bid, str):
                continue
            if bid in existing:
                continue  # already have NOW --near--> bid

            try:
                add_spatial_relation(
                    world,
                    src_bid=now_id,
                    rel="near",
                    dst_bid=bid,
                    meta={
                        "created_by": "scene_graph",
                        "source": "env_step",
                        "kind": "near",
                    },
                )
                existing.add(bid)
            except Exception:
                # Scene-graph sugar must never break env injection.
                continue
    except Exception:
        # Fully defensive: if anything goes wrong, just skip spatial labels.
        return


def _inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid: Dict[str, str]) -> None:  # pylint: disable=unused-argument
    """
    Minimal valence stub: when the kid is latched and mom is close in the SAME EnvObservation,
    tag the mom-proximity binding with pred:valence:like.

    Condition:
      • 'nipple:latched' ∈ env_obs.predicates
      • 'proximity:mom:close' ∈ env_obs.predicates

    Effect:
      • Find the binding we just created for 'proximity:mom:close' (via token_to_bid)
      • Add 'pred:valence:like' to its tags if not already present.

    This encodes "like mom (when close and feeding)" directly on the mom-near binding,
    ready for future planning/gating logic to read.
    """
    preds = set(getattr(env_obs, "predicates", []) or [])
    if "nipple:latched" not in preds:
        return
    if "proximity:mom:close" not in preds:
        return

    mom_bid = token_to_bid.get("proximity:mom:close")
    if not isinstance(mom_bid, str):
        return

    b = world._bindings.get(mom_bid)
    if not b:
        return

    tags = getattr(b, "tags", None)

    # Ensure tags is a mutable set
    if tags is None:
        b.tags = {"pred:valence:like"}
        return
    if isinstance(tags, list):
        tags = set(tags)
        b.tags = tags

    if "pred:valence:like" not in tags:
        tags.add("pred:valence:like")


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

def append_cycle_json_record(ctx: Ctx, record: dict[str, Any]) -> None:
    """Append a per-cycle JSON-safe record to ctx and optionally write it as JSONL.

    Design:
      - Always appends to an in-memory ring buffer (ctx.cycle_json_records).
      - If ctx.cycle_json_path is a non-empty string, appends a single JSON object per line (JSONL).
      - Never raises: logging-only on failure so the runner stays interactive.

    Notes:
      - File path is interpreted relative to the process working directory unless absolute.
      - The file is created on first successful open(..., "a", ...).
    """
    if ctx is None or not bool(getattr(ctx, "cycle_json_enabled", False)):
        return

    max_n = int(getattr(ctx, "cycle_json_max_records", 0) or 0)
    if max_n <= 0:
        max_n = 2000

    buf = getattr(ctx, "cycle_json_records", None)
    if not isinstance(buf, list):
        ctx.cycle_json_records = []
        buf = ctx.cycle_json_records
    buf.append(record)
    if len(buf) > max_n:
        del buf[:-max_n]

    path = getattr(ctx, "cycle_json_path", None)
    if not isinstance(path, str) or not path.strip():
        return

    abs_path = os.path.abspath(path)
    try:
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False)
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logging.error("[cycle_json] write failed path=%r: %s", abs_path, e, exc_info=True)
        return


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


def inject_obs_into_world(world, ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Write env observation tokens into the long-term WorldGraph with clear attach semantics.

    Modes (ctx.longterm_obs_mode):
      - "snapshot": old behavior; always write all observed predicates each tick
      - "changes" : write only when a state-slot changes, plus optional re-asserts/keyframes

    Slot definition:
      token "proximity:mom:far" -> slot "proximity:mom"
      token "resting"           -> slot "resting" (no ":")

    Keyframes (only in "changes" mode):
      - episode start (env_reset): time_since_birth <= 0.0
      - stage change (if enabled): env_meta["scenario_stage"] changed
      - zone change (if enabled): coarse safety zone flip derived from shelter/cliff predicates
      - periodic (optional): every N controller steps (period_steps > 0)
      - surprise (optional): pred_err v0 sustained mismatch (streak-based)
      - milestones (optional): env_meta milestone flags AND/OR derived predicate slot transitions
      - strong emotion/arousal (optional): env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy

    Even when we skip writing an unchanged token, token_to_bid will still map that token
    to the most recent binding id for its slot (so downstream helpers can still find it).
    """
    created_preds: list[str] = []
    created_cues: list[str] = []
    token_to_bid: dict[str, str] = {}

    # Pull env meta fields early (not masked; used for keyframe labels later).
    env_meta = getattr(env_obs, "env_meta", None) or {}
    stage = env_meta.get("scenario_stage")
    time_since_birth = env_meta.get("time_since_birth")

    # Partial observability (Phase VIII): optionally drop some observation facts before they enter memory.
    #
    # Notes:
    # - This is a PERCEPTION knob (what crosses the env→agent boundary), not a change to EnvState truth.
    # - Masking happens BEFORE BodyMap/WorkingMap/WorldGraph writes so it affects "belief-now".
    # - A small set of safety-critical predicate families is protected so zone classification remains stable.
    mask_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
    if mask_p <= 0.0:
        # If masking is off, clear the "config printed" sentinel so re-enabling prints a config line again.
        try:
            ctx.obs_mask_last_cfg_sig = None
        except Exception:
            pass
    else:
        mask_p = max(0.0, min(1.0, mask_p))
        protect_pred_prefixes = ("posture:", "hazard:cliff:", "proximity:shelter:")

        preds_in = getattr(env_obs, "predicates", None)
        cues_in = getattr(env_obs, "cues", None)

        preds = [t for t in preds_in if isinstance(t, str) and t] if isinstance(preds_in, list) else []
        cues = [t for t in cues_in if isinstance(t, str) and t] if isinstance(cues_in, list) else []

        def _strip_pred_prefix(tok: str) -> str:
            return tok[5:] if tok.startswith("pred:") else tok

        # Reproducible masking (optional):
        # If ctx.obs_mask_seed is set, use a per-step deterministic RNG. This prevents unrelated random calls
        # (e.g., RL exploration) from perturbing the observation-masking pattern.
        rng = random
        rng_mode = "global"
        seed_base = getattr(ctx, "obs_mask_seed", None)

        step_ref = env_meta.get("step_index")
        if step_ref is None:
            step_ref = getattr(ctx, "cog_cycles", None)
        if step_ref is None:
            step_ref = getattr(ctx, "controller_steps", 0)

        seed_eff: Optional[int] = None
        if seed_base is not None:
            try:
                seed_i = int(seed_base)
            except Exception:
                seed_i = None
            if seed_i is not None:
                try:
                    step_i = int(step_ref) if step_ref is not None else 0
                except Exception:
                    step_i = 0
                seed_eff = (seed_i * 1_000_003) ^ step_i
                rng = random.Random(seed_eff)
                rng_mode = "seeded"

        verbose = bool(getattr(ctx, "obs_mask_verbose", True))
        cfg_sig = f"{rng_mode}|{seed_base!r}|{mask_p:.3f}"
        if verbose and cfg_sig != getattr(ctx, "obs_mask_last_cfg_sig", None):
            try:
                ctx.obs_mask_last_cfg_sig = cfg_sig
            except Exception:
                pass
            print(
                f"[obs-mask] config mode={rng_mode} seed={seed_base!r} step_ref={step_ref!r} "
                f"p={mask_p:.2f} protected={len(protect_pred_prefixes)}"
            )

        dropped_preds = 0
        dropped_cues = 0

        preds_out: list[str] = []
        for tok in preds:
            tok_chk = _strip_pred_prefix(tok)
            if any(tok_chk.startswith(pfx) for pfx in protect_pred_prefixes):
                preds_out.append(tok)
                continue
            if rng.random() < mask_p:
                dropped_preds += 1
                continue
            preds_out.append(tok)

        # Defensive: keep at least one predicate if we had any (avoid “empty observation block” surprises).
        if (not preds_out) and preds:
            preds_out = [preds[0]]
            dropped_preds = max(0, len(preds) - 1)

        cues_out: list[str] = []
        for tok in cues:
            if rng.random() < mask_p:
                dropped_cues += 1
                continue
            cues_out.append(tok)

        # Apply the masked lists back onto the observation packet.
        try:
            setattr(env_obs, "predicates", preds_out)
            setattr(env_obs, "cues", cues_out)
        except Exception:
            pass

        # Expose masking stats for downstream gating/diagnostics (e.g., keyframe auto-retrieve).
        # This lets the keyframe pipeline know whether *this* observation lost tokens.
        try:
            if isinstance(env_meta, dict):
                env_meta["obs_mask_dropped_preds"] = int(dropped_preds)
                env_meta["obs_mask_dropped_cues"] = int(dropped_cues)
                env_meta["obs_mask_mode"] = str(rng_mode)
                env_meta["obs_mask_prob"] = float(mask_p)
        except Exception:
            pass

        if verbose and (dropped_preds or dropped_cues):
            seed_part = f" seed_eff={seed_eff}" if seed_eff is not None else ""
            print(
                f"[obs-mask] mode={rng_mode}{seed_part} step_ref={step_ref!r} "
                f"dropped preds={dropped_preds}/{len(preds)} cues={dropped_cues}/{len(cues)} p={mask_p:.2f}"
            )

    # Always keep BodyMap current (policies are BodyMap-first now).
    try:
        update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass

    # Sequential/error stub (CCA7-inspired): temporal deltas + prediction error on the sensory stream.
    # Diagnostic-first; does not affect policy selection unless you explicitly enable attention later.
    try:
        seqerr_update_from_obs(ctx, env_obs)
    except Exception:
        pass

    # Update the short-lived sensory surfaces (SurfaceGrid + MapSurface) and
    # compute a minimal prediction error signal (predictive coding v1).
    try:
        update_surface_grid_from_obs(ctx, env_obs)
    except Exception:
        pass
    try:
        update_map_surface_from_obs(ctx, env_obs)
    except Exception:
        pass
    try:
        predcode_update_from_obs(ctx, env_obs)
    except Exception:
        pass

    # NavPatch predictive matching loop (Phase X baseline; priors OFF).
    # This records traceability metadata and may store new patch engrams in Column.
    # IMPORTANT: run *before* WorkingMap injection so env_obs.nav_patches carries match/commit fields.
    # This must never break env stepping.
    try:
        navpatch_predictive_match_loop_v1(ctx, env_obs)
    except Exception:
        # Matching is diagnostic; ignore failures and keep the env loop alive.
        pass

    # Mirror into WorkingMap when enabled.
    # Keep the returned dict so callers (e.g., env-loop footer) can summarize what happened.
    working_inj = None
    try:
        if getattr(ctx, "working_enabled", False):
            working_inj = inject_obs_into_working_world(ctx, env_obs)
    except Exception:
        working_inj = None

    # Always keep BodyMap current (policies are BodyMap-first now).
    try:
        update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass

    # Read-only NavMap diagnostic bridge. This updates ctx-local candidate/history fields only.
    try:
        navmap_ctx_observation_update_step_v1(ctx, env_obs)
    except Exception:
        pass

    # Allow turning off long-term injection entirely (BodyMap/WorkingMap still update).
    if not getattr(ctx, "longterm_obs_enabled", True):
        return {
            "predicates": created_preds,
            "cues": created_cues,
            "token_to_bid": token_to_bid,
            "working": working_inj,
        }

    mode = (getattr(ctx, "longterm_obs_mode", "snapshot") or "snapshot").strip().lower()
    do_changes = mode in ("changes", "dedup", "delta", "state_changes")

    # Normalize (defensive: some probes may include prefixes already) AFTER masking.
    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "")
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    keyframe = False
    keyframe_reasons: list[str] = []
    # In "changes" mode: optionally force a one-tick snapshot at stage transitions/resets
    if do_changes:
        force_snapshot = False
        reasons: list[str] = []

        step_no = int(getattr(ctx, "controller_steps", 0) or 0)

        # ---- Coarse zone (derived from pred tokens; does NOT depend on BodyMap update ordering) ----
        zone_now = "unknown"
        shelter = None
        cliff = None
        for _tok in pred_tokens:
            if isinstance(_tok, str) and _tok.startswith("proximity:shelter:"):
                shelter = _tok.rsplit(":", 1)[-1]
            elif isinstance(_tok, str) and _tok.startswith("hazard:cliff:"):
                cliff = _tok.rsplit(":", 1)[-1]
        if cliff == "near" and shelter != "near":
            zone_now = "unsafe_cliff_near"
        elif shelter == "near" and cliff != "near":
            zone_now = "safe"

        last_zone = getattr(ctx, "lt_obs_last_zone", None)

        # Reset keyframe: env.reset() produces time_since_birth == 0.0
        if isinstance(time_since_birth, (int, float)) and float(time_since_birth) <= 0.0:
            force_snapshot = True
            reasons.append(f"env_reset(time_since_birth={float(time_since_birth):.2f})")

        # Stage-change keyframe (optional)
        last_stage = getattr(ctx, "lt_obs_last_stage", None)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True)):
            if stage is not None and last_stage is not None and stage != last_stage:
                force_snapshot = True
                reasons.append(f"stage_change {last_stage!r}→{stage!r}")

        # Zone-change keyframe (optional)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_zone_change", True)):
            if isinstance(last_zone, str) and zone_now != last_zone:
                force_snapshot = True
                reasons.append(f"zone_change {last_zone!r}→{zone_now!r}")

        # Benchmark-only newborn route-loss keyframe.
        # During route_loss, current route/task evidence is deliberately hidden,
        # so the experiment must create retrieval opportunities instead of
        # waiting for ordinary stage/zone changes.
        try:
            env_meta_for_stress = getattr(env_obs, "env_meta", None)
            env_meta_for_stress = env_meta_for_stress if isinstance(env_meta_for_stress, dict) else {}

            if bool(env_meta_for_stress.get("newborn_force_keyframe")):
                force_snapshot = True
                route_reason = env_meta_for_stress.get("newborn_blackout_reason")
                route_reason = route_reason if isinstance(route_reason, str) and route_reason else "route_loss"
                reasons.append(f"newborn_stress:{route_reason}")
        except Exception:
            pass

        # Periodic keyframe (optional; safe: evaluated only at this boundary hook)
        #
        # Two semantics:
        #   A) legacy absolute schedule: step_no % period == 0
        #   B) reset-on-any-keyframe: treat periodic as a max-gap since last keyframe
        #      (if any other keyframe happens, the periodic counter restarts).
        try:
            period = int(getattr(ctx, "longterm_obs_keyframe_period_steps", 0) or 0)
        except Exception:
            period = 0

        if period > 0 and step_no > 0:
            reset_on_any = bool(getattr(ctx, "longterm_obs_keyframe_period_reset_on_any_keyframe", False))

            hit = False
            if reset_on_any:
                last_kf = getattr(ctx, "lt_obs_last_keyframe_step", None)
                last_kf_step = int(last_kf) if isinstance(last_kf, int) else 0
                if last_kf_step > step_no:
                    # Defensive: controller_steps can be reset in some flows; treat that as a new epoch.
                    last_kf_step = 0
                hit = (step_no - last_kf_step) >= period
            else:
                hit = (step_no % period) == 0

            # Optional suppression: do not fire periodic keyframes while sleeping.
            #
            # We detect sleep state best-effort from either:
            #   A) env_meta: sleep_state/sleep_mode (str), or sleeping/dreaming (bool)
            #   B) predicate tokens: sleeping:non_dreaming / sleeping:dreaming (rem/nrem aliases allowed)
            if hit:
                sup_nd = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming", False))
                sup_dr = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_dreaming", False))

                if sup_nd or sup_dr:
                    sleep_kind: str | None = None

                    # A) env_meta string label
                    try:
                        sm = env_meta.get("sleep_state") or env_meta.get("sleep_mode") or env_meta.get("sleep")
                    except Exception:
                        sm = None

                    if isinstance(sm, str) and sm.strip():
                        s = sm.strip().lower().replace(" ", "_")
                        if s in ("dreaming", "rem", "rem_sleep", "sleep_rem"):
                            sleep_kind = "dreaming"
                        elif s in ("non_dreaming", "nondreaming", "nrem", "nrem_sleep", "sleep_nrem", "non_rem"):
                            sleep_kind = "non_dreaming"

                    # A2) env_meta boolean flags
                    if sleep_kind is None:
                        try:
                            sleeping_flag = env_meta.get("sleeping")
                            dreaming_flag = env_meta.get("dreaming")
                        except Exception:
                            sleeping_flag = None
                            dreaming_flag = None

                        if isinstance(sleeping_flag, bool) and sleeping_flag:
                            sleep_kind = "dreaming" if bool(dreaming_flag) else "non_dreaming"

                    # B) predicate tokens
                    if sleep_kind is None:
                        try:
                            toks = {t.strip().lower() for t in pred_tokens if isinstance(t, str) and t.strip()}
                        except Exception:
                            toks = set()

                        if (
                            "sleeping:dreaming" in toks
                            or "sleep:dreaming" in toks
                            or "sleeping:rem" in toks
                            or "sleep:rem" in toks
                        ):
                            sleep_kind = "dreaming"
                        elif (
                            "sleeping:non_dreaming" in toks
                            or "sleep:non_dreaming" in toks
                            or "sleeping:nrem" in toks
                            or "sleep:nrem" in toks
                        ):
                            sleep_kind = "non_dreaming"
                        elif ("sleeping" in toks) or ("sleep" in toks):
                            # If sleep is present but untyped, treat as non-dreaming by default.
                            sleep_kind = "non_dreaming"

                    if (sleep_kind == "non_dreaming") and sup_nd:
                        hit = False
                    elif (sleep_kind == "dreaming") and sup_dr:
                        hit = False

            if hit:
                # If another keyframe is already happening this tick, do NOT add a second "periodic" reason.
                # In reset-on-any-keyframe mode, the periodic counter will still be reset by that other keyframe.
                if not force_snapshot:
                    force_snapshot = True
                    reasons.append(f"periodic(step={step_no}, period={period})")

        # Surprise keyframe from pred_err v0 (optional; streak-based)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_pred_err", False)):
            pe = getattr(ctx, "pred_err_v0_last", None)
            pe_any = False
            if isinstance(pe, dict) and pe:
                try:
                    pe_any = any(int(v or 0) != 0 for v in pe.values())
                except Exception:
                    pe_any = False

            streak = int(getattr(ctx, "lt_obs_pred_err_streak", 0) or 0)
            streak = (streak + 1) if pe_any else 0
            ctx.lt_obs_pred_err_streak = streak

            try:
                min_streak = int(getattr(ctx, "longterm_obs_keyframe_pred_err_min_streak", 2) or 2)
            except Exception:
                min_streak = 2
            min_streak = max(1, min_streak)

            if pe_any and streak >= min_streak:
                force_snapshot = True
                reasons.append(f"pred_err_v0(streak={streak})")
        else:
            ctx.lt_obs_pred_err_streak = 0

        # Milestone keyframes (HAL + derived from predicate transitions). Off by default.
        #
        # Two sources:
        #   A) env_meta milestone flags (HAL/richer envs) — may be sticky and repeat across ticks → dedup.
        #   B) derived transition events from predicate slots (storyboard + early HAL) — event-based, no sticky dedup needed.
        #
        # Derived events currently recognized:
        #   - posture:fallen -> posture:standing              => stood_up
        #   - proximity:mom:* -> proximity:mom:close         => reached_mom
        #   - (first) nipple:found                           => found_nipple
        #   - (first) nipple:latched                         => latched_nipple
        #   - (first) milk:drinking                          => milk_drinking
        #   - (first) resting                                => rested
        if bool(getattr(ctx, "longterm_obs_keyframe_on_milestone", False)):
            ms_events: set[str] = set()

            # --- A) Env-supplied milestone flags (rising-edge, not episode-global sticky) ---
            #
            # Important semantic choice:
            #   We treat env-supplied milestones as "new" relative to the immediately
            #   previous observation, NOT as "seen once per episode forever".
            #
            # Why:
            #   Some scenarios intentionally reuse the same milestone label multiple times
            #   in one episode. goat_foraging_04 is the current example:
            #
            #       context:fox -> context:hawk -> context:fox -> ...
            #
            #   We want each alternation edge to be a fresh keyframe trigger, while still
            #   suppressing repeated identical labels on consecutive ticks:
            #
            #       fox, fox, fox     -> fire once on first fox tick
            #       fox -> hawk       -> fire on hawk
            #       hawk, hawk, hawk  -> fire once on first hawk tick
            #       hawk -> fox       -> fire on fox again
            #
            #   Therefore we compare CURRENT milestones against the PREVIOUS active set,
            #   then overwrite the remembered set with the current one.
            ms_raw = env_meta.get("milestones") or env_meta.get("milestone")
            ms_list: list[str] = []
            if isinstance(ms_raw, str) and ms_raw:
                ms_list = [ms_raw]
            elif isinstance(ms_raw, list):
                ms_list = [m for m in ms_raw if isinstance(m, str) and m]

            prev_raw = getattr(ctx, "lt_obs_last_milestones", None)
            prev_ms: set[str] = {x for x in prev_raw if isinstance(x, str) and x} if isinstance(prev_raw, set) else set()
            curr_ms: set[str] = {m for m in ms_list if isinstance(m, str) and m}

            new_ms = curr_ms - prev_ms
            if new_ms:
                ms_events |= new_ms

            try:
                ctx.lt_obs_last_milestones = curr_ms
            except Exception:
                pass

            # --- B) Derived milestone events (slot transitions) ---
            try:
                prev_slots = getattr(ctx, "lt_obs_slots", None)
                prev_slots = prev_slots if isinstance(prev_slots, dict) else {}

                # Build current slot->token mapping from this observation (pred_tokens has no "pred:" prefix).
                curr_by_slot: dict[str, str] = {}
                for tok in pred_tokens:
                    if not isinstance(tok, str) or not tok:
                        continue
                    slot = tok.rsplit(":", 1)[0] if ":" in tok else tok
                    if slot not in curr_by_slot:
                        curr_by_slot[slot] = tok

                def _prev_token(slot: str) -> str | None:
                    p = prev_slots.get(slot)
                    if isinstance(p, dict):
                        t = p.get("token")
                        return t if isinstance(t, str) else None
                    return None

                # posture transition
                prev_posture = _prev_token("posture")
                curr_posture = curr_by_slot.get("posture")
                if curr_posture == "posture:standing" and prev_posture != "posture:standing":
                    ms_events.add("stood_up")

                # mom proximity transition
                prev_mom = _prev_token("proximity:mom")
                curr_mom = curr_by_slot.get("proximity:mom")
                if curr_mom == "proximity:mom:close" and prev_mom != "proximity:mom:close":
                    ms_events.add("reached_mom")

                # nipple milestones
                prev_nipple = _prev_token("nipple")
                curr_nipple = curr_by_slot.get("nipple")
                if curr_nipple == "nipple:found" and prev_nipple != "nipple:found":
                    ms_events.add("found_nipple")
                if curr_nipple == "nipple:latched" and prev_nipple != "nipple:latched":
                    ms_events.add("latched_nipple")

                # milk milestone
                prev_milk = _prev_token("milk")
                curr_milk = curr_by_slot.get("milk")
                if curr_milk == "milk:drinking" and prev_milk != "milk:drinking":
                    ms_events.add("milk_drinking")

                # resting milestone
                prev_rest = _prev_token("resting")
                curr_rest = curr_by_slot.get("resting")
                if curr_rest == "resting" and prev_rest != "resting":
                    ms_events.add("rested")
            except Exception:
                # Derived milestones are strictly best-effort; never break env injection.
                pass

            if ms_events:
                force_snapshot = True
                reasons.append("milestone:" + ",".join(sorted(ms_events)))

        # Strong emotion keyframe stub (HAL / richer envs). Off by default.
        # Note: we treat hazard zone as a conservative proxy ("fear") only when env_meta doesn't supply emotion.
        if bool(getattr(ctx, "longterm_obs_keyframe_on_emotion", False)):
            label = None
            intensity = None

            emo_raw = env_meta.get("emotion") or env_meta.get("affect")
            if isinstance(emo_raw, dict):
                lab = emo_raw.get("label")
                inten = emo_raw.get("intensity")
                label = lab if isinstance(lab, str) and lab else None
                try:
                    intensity = float(inten) if inten is not None else None
                except Exception:
                    intensity = None
            elif isinstance(emo_raw, str) and emo_raw:
                label = emo_raw

            # Proxy if no explicit emotion: unsafe zone -> fear-high
            if intensity is None and label is None:
                if zone_now == "unsafe_cliff_near":
                    label = "fear"
                    intensity = 1.0

            try:
                thr = float(getattr(ctx, "longterm_obs_keyframe_emotion_threshold", 0.85) or 0.85)
            except Exception:
                thr = 0.85

            high = bool(isinstance(intensity, (int, float)) and float(intensity) >= thr)
            prev_label = getattr(ctx, "lt_obs_last_emotion_label", None)
            prev_high = bool(getattr(ctx, "lt_obs_last_emotion_high", False))

            # Rising edge: (not high) -> high, or label changes while high.
            if high and (label != prev_label or not prev_high):
                force_snapshot = True
                inten_txt = f"{float(intensity):.2f}" if isinstance(intensity, (int, float)) else "n/a"
                reasons.append(f"emotion:{label or 'n/a'}@{inten_txt}")

            try:
                ctx.lt_obs_last_emotion_label = label if isinstance(label, str) else None
                ctx.lt_obs_last_emotion_high = high
            except Exception:
                pass

        # [KEYFRAME HOOK + ORDERING INVARIANT]
        # This is the keyframe/boundary detection point for the env→memory injection path.
        # inject_obs_into_world(...) runs BEFORE policy selection (Action Center), so any keyframe-driven
        # WM↔Column pipeline that must influence *this same boundary cycle* belongs conceptually here.
        #
        # INVARIANT (keyframes):
        #   EnvObservation -> BodyMap/WorkingMap update -> (keyframe) store snapshot + pointer update ->
        #   (keyframe) optional retrieve+apply (replace or seed/merge) -> policy selection/execution.
        #
        # RESERVED FUTURE SLOT (consolidation/reconsolidation write-back):
        #   After policy selection+execution, a keyframe may also write new engrams (copy-on-write) and
        #   update WorldGraph pointers for future retrieval, without mutating the belief state already
        #   used for action selection in this cycle.  See README: "WM ⇄ Column engram pipeline".

        # REAL-EMBODIMENT KEYFRAMES (HAL / non-storyboard):
        #   In real robots there is no storyboard stage. We will therefore support additional keyframe triggers here,
        #   evaluated ONLY at this boundary hook (never mid-cycle):
        #
        #   - periodic: every N controller_steps (ctx.longterm_obs_keyframe_period_steps)
        #   - surprise: pred_err v0 sustained mismatch (ctx.pred_err_v0_last + min_streak)
        #   - context discontinuity: zone flips (zone_now derived here vs ctx.lt_obs_last_zone)
        #   - milestones: env_meta milestones and/or derived slot transitions (goal-relevant outcomes)
        #   - emotion/arousal: env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy
        #
        # TIME-BASED SAFETY:
        #   Even the periodic keyframe must be checked only at this boundary hook so we never split a cycle
        #   while intermediate planner/policy structures are half-written.

        if force_snapshot:
            old_pred_n = len(getattr(ctx, "lt_obs_slots", {}) or {})
            old_cue_n = len(getattr(ctx, "lt_obs_cues", {}) or {})

            ctx.lt_obs_slots.clear()
            try:
                ctx.lt_obs_cues.clear()
            except Exception:
                pass
            try:
                ctx.lt_obs_last_milestones = set()
            except Exception:
                pass
            if bool(getattr(ctx, "longterm_obs_keyframe_log", True)):
                why = ", ".join(reasons) if reasons else "keyframe"
                print(f"[env→world] KEYFRAME: {why} | cleared {old_pred_n} pred slot(s), {old_cue_n} cue slot(s)")
            try:
                ctx.lt_obs_last_keyframe_step = step_no
            except Exception:
                pass

        ctx.lt_obs_last_stage = stage
        ctx.lt_obs_last_zone = zone_now

        # For downstream callers (e.g., env-loop) that want a unified keyframe definition:
        keyframe = bool(force_snapshot)
        keyframe_reasons = list(reasons)


    def _slot_key(tok: str) -> str:
        return tok.rsplit(":", 1)[0] if ":" in tok else tok

    step_no = int(getattr(ctx, "controller_steps", 0) or 0)
    reassert_steps = int(getattr(ctx, "longterm_obs_reassert_steps", 0) or 0)
    verbose_skips = bool(getattr(ctx, "longterm_obs_verbose", False))

    wrote_any_pred_this_tick = False

    # Predicates: snapshot vs changes mode
    for tok in pred_tokens:
        meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}

        if not do_changes:
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
            continue

        slot = _slot_key(tok)
        prev = ctx.lt_obs_slots.get(slot)

        emit = False
        reason = ""
        if prev is None:
            emit = True
            reason = "first"
        elif prev.get("token") != tok:
            emit = True
            reason = "changed"
        else:
            # unchanged
            if 0 < reassert_steps <= (step_no - int(prev.get("last_emit_step", 0) or 0)):
                emit = True
                reason = "reassert"
            else:
                emit = False
                reason = "unchanged"
        if emit:
            meta2 = dict(meta)
            meta2["_dedup"] = reason
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta2)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            ctx.lt_obs_slots[slot] = {"token": tok, "bid": bid, "last_emit_step": step_no}
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
        else:
            prev_bid = prev.get("bid") if isinstance(prev, dict) else None
            if isinstance(prev_bid, str):
                token_to_bid[tok] = prev_bid
                try:
                    world.bump_prominence(prev_bid, tag=f"pred:{tok}", meta=meta, reason="observe")
                except Exception:
                    pass
            if verbose_skips:
                print(f"[env→world] pred:{tok} → {prev_bid} (reused; unchanged)")

    # If everything was unchanged, print one line so the user knows this is intentional.
    if do_changes and pred_tokens and not created_preds and not verbose_skips:
        print("[env→world] (long-term obs unchanged; no new pred:* bindings written)")

    # Cues:
    # Default: episodic (write each observed cue each tick).
    # Optional (changes-mode): rising-edge de-dup (emit only when absent→present), but still bump prominence every tick.
    cue_attach = "latest" if wrote_any_pred_this_tick else "now"
    dedup_cues = bool(do_changes) and bool(getattr(ctx, "longterm_obs_dedup_cues", False))
    if not dedup_cues:
        for tok in cue_tokens:
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            bid = world.add_cue(tok, attach=cue_attach, meta=meta)
            created_cues.append(tok)
            token_to_bid[tok] = bid
            print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
    else:
        cue_cache = getattr(ctx, "lt_obs_cues", None)
        if not isinstance(cue_cache, dict):
            cue_cache = {}
            try:
                ctx.lt_obs_cues = cue_cache
            except Exception:
                pass

        seen_this_step: set[str] = set()
        cues_now: set[str] = set()
        for tok in cue_tokens:
            if not isinstance(tok, str):
                continue
            if tok in seen_this_step:
                continue
            seen_this_step.add(tok)
            cues_now.add(tok)
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            prev = cue_cache.get(tok)
            was_present = bool(isinstance(prev, dict) and prev.get("present", False))
            emit = False
            reason = ""
            if not was_present:
                emit = True
                reason = "rising"
            else:
                if 0 < reassert_steps <= (step_no - int((prev or {}).get("last_emit_step", 0) or 0)):
                    emit = True
                    reason = "reassert"
                else:
                    emit = False
                    reason = "held"
            if emit:
                meta2 = dict(meta)
                meta2["_dedup"] = reason
                bid = world.add_cue(tok, attach=cue_attach, meta=meta2)
                created_cues.append(tok)
                token_to_bid[tok] = bid
                cue_cache[tok] = {"present": True, "bid": bid, "last_emit_step": step_no}
                print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
            else:
                prev_bid = prev.get("bid") if isinstance(prev, dict) else None
                if isinstance(prev_bid, str):
                    token_to_bid[tok] = prev_bid
                    try:
                        world.bump_prominence(prev_bid, tag=f"cue:{tok}", meta=meta, reason="observe")
                    except Exception:
                        pass
                if isinstance(prev, dict):
                    prev["present"] = True
                if verbose_skips:
                    print(f"[env→world] cue:{tok} → {prev_bid} (reused; held)")
        # Mark cues that were present but are absent now as not present.
        try:
            for tok, rec in list(cue_cache.items()):
                if not isinstance(rec, dict):
                    continue
                if rec.get("present", False) and tok not in cues_now:
                    rec["present"] = False
        except Exception:
            pass

    # Optional env sugar on top of tokens (must never break env stepping)
    try:
        _write_spatial_scene_edges(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    try:
        _inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    return {
        "predicates": created_preds,
        "cues": created_cues,
        "token_to_bid": token_to_bid,
        "working": working_inj,
        "keyframe": bool(keyframe),
        "keyframe_reasons": list(keyframe_reasons),
        "zone_now": getattr(ctx, "lt_obs_last_zone", None),
    }


def _wm_creative_update(policy_rt, world, drives, ctx, *, exec_world=None) -> None:

    """
    Populate the WorkingMap Creative layer with a tiny "imagination" demo (Option B Step 2).

    What this does (and does NOT do):
      - It scores a few candidate *policies* using a simple heuristic (safety first).
      - It stores the results on ctx:
          ctx.wm_creative_candidates (best-first)
          ctx.wm_creative_last_pick
      - It does NOT change which policy the controller actually executes yet.

    Candidate pool:
      - We use policy_rt.loaded (already dev-gated by profile/age via refresh_loaded(ctx)).
      - We evaluate trigger(world, drives) to see which are currently feasible.
      - We mirror the controller's safety filter: if "fallen near NOW", only StandUp/RecoverFall count as feasible.
    """
    if ctx is None:
        return

    enabled = bool(getattr(ctx, "wm_creative_enabled", False))
    if not enabled:
        try:
            ctx.wm_creative_candidates.clear()
        except Exception:
            pass
        try:
            ctx.wm_creative_last_pick = None
        except Exception:
            pass
        return

    # Clamp K to a readable small range (2–5 recommended; allow 1..5)
    try:
        k = int(getattr(ctx, "wm_creative_k", 3) or 3)
    except Exception:
        k = 3
    k = max(1, min(5, k))
    try:
        ctx.wm_creative_k = k
        # Use the same world the controller will execute into (if provided) so "triggerable" matches real executability.
        trigger_world = exec_world if exec_world is not None else world
    except Exception:
        pass

    # Read BodyMap (preferred) for cheap state signals
    posture = None
    mom = None
    nipple = None
    zone = "unknown"
    try:
        if not bodymap_is_stale(ctx):
            posture = body_posture(ctx)
            mom = body_mom_distance(ctx)
            nipple = body_nipple_state(ctx)
            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = "unknown"
    except Exception:
        zone = "unknown"

    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))

    # Which loaded policies are actually triggerable right now?
    loaded = getattr(policy_rt, "loaded", []) or []
    triggerable: set[str] = set()
    all_names: list[str] = []

    for g in loaded:
        name = getattr(g, "name", None)
        if not isinstance(name, str):
            continue
        all_names.append(name)
        ok = False
        try:
            ok = bool(g.trigger(trigger_world, drives, ctx))
        except Exception:
            ok = False
        if ok:
            triggerable.add(name)

    # Mirror safety override: if fallen near NOW, only allow posture recovery policies as feasible.
    try:
        if _fallen_near_now(trigger_world, ctx, max_hops=3):
            triggerable &= {"policy:stand_up", "policy:recover_fall"}
    except Exception:
        pass


    def _score_policy(name: str) -> tuple[float, str, dict]:
        """
        Tiny heuristic scorer.
        Returns (score, notes, predicted_dict).
        """
        score = 0.0
        notes: list[str] = []
        predicted: dict = {}

        # Safety/posture recovery first
        if name == "policy:stand_up":
            if posture == "fallen":
                score += 5.0
                notes.append("safety:fallen→stand")
                predicted["posture"] = "standing"
            elif posture == "standing":
                score -= 2.0
                notes.append("already_standing")
            else:
                score += 0.5
                notes.append("posture_unknown")

        elif name == "policy:recover_fall":
            if posture == "fallen":
                score += 4.0
                notes.append("recover:fallen→assist")
                predicted["posture"] = "standing"
            else:
                score -= 1.0
                notes.append("not_fallen")

        # Hunger / feeding
        elif name == "policy:seek_nipple":
            if hunger > HUNGER_HIGH:
                score += 3.0 * (hunger - HUNGER_HIGH)
                notes.append(f"hunger_high({hunger:.2f})")
                predicted["feeding"] = "advance"
            else:
                score -= 0.3
                notes.append(f"hunger_ok({hunger:.2f})")

            if mom in ("near", "close", "touching"):
                score += 0.6
                notes.append("mom_near")
            elif mom == "far":
                score -= 0.6
                notes.append("mom_far")

            if posture == "fallen":
                score -= 1.5
                notes.append("blocked_by_fallen")

            if nipple == "latched":
                score -= 3.0
                notes.append("already_latched")
                predicted["feeding"] = "already"

        # Fatigue / resting (with zone veto)
        elif name == "policy:rest":
            if fatigue > FATIGUE_HIGH:
                score += 3.0 * (fatigue - FATIGUE_HIGH)
                notes.append(f"fatigue_high({fatigue:.2f})")
                predicted["fatigue"] = "down"
            else:
                score -= 0.2
                notes.append(f"fatigue_ok({fatigue:.2f})")

            if zone == "safe":
                score += 0.6
                notes.append("zone_safe")
            if zone == "unsafe_cliff_near":
                score -= 2.5
                notes.append("zone_unsafe_veto")

        # Movement / geometry change
        elif name == "policy:follow_mom":
            score += 0.2
            notes.append("move/fallback")
            if zone == "unsafe_cliff_near":
                score += 1.6
                notes.append("escape_cliff")
                predicted["zone"] = "safer"
            if mom == "far":
                score += 0.4
                notes.append("mom_far")
            if nipple == "latched":
                score -= 0.2
                notes.append("already_nursing")

        # Default: keep neutral
        else:
            score += 0.0

        return score, "; ".join(notes), predicted

    # Build candidates for all loaded policies, but sort triggerable ones first.
    cands: list[CreativeCandidate] = []
    for name in all_names:
        sc, note, pred = _score_policy(name)
        trig = name in triggerable
        pred = dict(pred or {})
        pred["triggerable"] = trig
        if not trig:
            note = "blocked(not_triggered)" + (f"; {note}" if note else "")
        cands.append(CreativeCandidate(policy=name, score=float(sc), notes=note, predicted=pred))

    trig_cands = [c for c in cands if bool(getattr(c, "predicted", {}).get("triggerable", False))]
    blk_cands  = [c for c in cands if not bool(getattr(c, "predicted", {}).get("triggerable", False))]

    trig_cands.sort(key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)
    blk_cands.sort(key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)

    out = trig_cands[:k]
    if len(out) < k:
        out += blk_cands[: (k - len(out))]

    try:
        ctx.wm_creative_candidates.clear()
        ctx.wm_creative_candidates.extend(out)
    except Exception:
        pass

    try:
        ctx.wm_creative_last_pick = out[0] if out else None
    except Exception:
        pass


def print_env_loop_tag_legend_once(ctx: Ctx) -> None:
    """Print a compact legend for console prefixes (once per session).

    We keep the run output readable for new users, but avoid re-printing the
    legend every time menu 35/37 is used.
    """
    if ctx is None:
        return
    if ctx.env_loop_legend_printed:
        return
    ctx.env_loop_legend_printed = True

    print("\nLegend (console tags):")
    print("  [env-loop]      closed-loop driver (one cognitive cycle = env update → policy select → policy act)")
    print("  [env]           environment events (reset/step; with HAL ON, this would be real sensor I/O)")
    print("  [env→working]   EnvObservation → WorkingMap (fast scratch / map surface)")
    print("  [env→world]     EnvObservation → WorldGraph (long-term episode index)")
    print("  [env→controller] Action Center output (policy selection + execution)")
    print("  [wm<->col]      WorkingMap ⇄ Column keyframe pipeline (store snapshot → retrieve candidates → apply/merge priors)")
    print("  [pred_err]      prediction error v0 (expected vs observed); gates auto-retrieve and shapes policy value via penalty on streaks")
    print("  [gate:<p>]      gating explanation for policy <p>")
    print("  [pick]          which policy was selected this cycle")
    print("  [executed]      policy execution result (effects show up in the NEXT cycle's observation)")
    print("  [maps]          selection_on=map used to score; execute_on=map used to run actions")
    print("  [obs-mask]      partial-observability masking (token drops) when enabled")
    print("")


def _quiet_solved_rest_tail_v1(
    curr_state,
    zone: str | None,
    action_applied_this_step: str | None,
    next_action_for_env: str | None,
) -> bool:
    """Return True when the newborn episode is already in a stable solved rest tail.

    This helper is intentionally cosmetic-only. It does not alter controller or
    environment behavior. It simply identifies the late solved state where
    repeating the same explanatory prose and the same SurfaceGrid ASCII map each
    cycle adds noise but little new information.

    We call the rest tail "quiet" only when all of these are already true:
      - scenario_stage == "rest"
      - kid_posture == "resting"
      - mom_distance == "touching"
      - nipple_state == "latched"
      - zone == "safe"
      - no action was applied this step
      - no next action is queued for the next environment step

    The first transition into rest is therefore still explained normally. Only
    the later steady-state tail becomes quieter.
    """
    if curr_state is None or zone != "safe":
        return False

    try:
        stage = getattr(curr_state, "scenario_stage", None)
        posture = getattr(curr_state, "kid_posture", None)
        mom_distance = getattr(curr_state, "mom_distance", None)
        nipple_state = getattr(curr_state, "nipple_state", None)
    except Exception:
        return False

    if stage != "rest":
        return False
    if posture != "resting":
        return False
    if mom_distance != "touching":
        return False
    if nipple_state != "latched":
        return False

    if isinstance(action_applied_this_step, str) and action_applied_this_step:
        return False
    if isinstance(next_action_for_env, str) and next_action_for_env:
        return False

    return True


def _print_cog_cycle_footer(*,
                            ctx: "Ctx",
                            drives,
                            env_obs,
                            prev_state,
                            curr_state,
                            env_step: int | None,
                            zone: str | None,
                            inj: dict[str, Any] | None,
                            fired_txt: str | None,
                            col_store_txt: str | None,
                            col_retrieve_txt: str | None,
                            col_apply_txt: str | None,
                            action_applied_this_step: str | None,
                            next_action_for_env: str | None,
                            cycle_no: int,
                            cycle_total: int) -> None:
    """
    Print a compact, end-of-cycle footer intended for fast human scanning.

    Intent
    ------
    Menu 37 (closed-loop env↔controller runs) produces many diagnostic lines. This footer is the
    "cheap digest" line-set that lets a maintainer quickly see what happened in *this* cognitive
    cycle in terms of the architecture:

      inputs → MapSurface deltas → Scratch writes → WorldGraph writes → Column ops → action

    The footer is intentionally pragmatic and will evolve as Phase IX/robotics/HAL integration evolves.
    Treat it as a reading aid, not a stable API.

    Notes
    -----
    - "MapSurface deltas" are derived from EnvState diffs (authoritative simulator truth). MapSurface is
      driven by EnvObservation, so EnvState changes correspond to slot-family changes (posture, proximity,
      hazard, nipple, etc.).
    - "Scratch writes" are summarized from the policy runtime's returned text (added bindings, executed line).
    - Column ops are summarized from the wm<->col store/retrieve/apply block when it ran this cycle.
    """
    if not bool(getattr(ctx, "env_loop_cycle_summary", True)):
        return

    try:
        max_items = int(getattr(ctx, "env_loop_cycle_summary_max_items", 6) or 6)
    except Exception:
        max_items = 6

    def _sf(x) -> str:
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "n/a"

    def _fmt_items(items, *, prefix: str = "", limit: int = 6) -> str:
        if not items:
            return "(none)"
        out = []
        for it in items:
            if isinstance(it, str) and it:
                out.append(f"{prefix}{it}")
        if not out:
            return "(none)"
        if len(out) <= limit:
            return ", ".join(out)
        head = ", ".join(out[:limit])
        return f"{head}, +{len(out) - limit} more"


    def _get_state_attr(st, name: str):
        try:
            return getattr(st, name, None)
        except Exception:
            return None


    def _obs_write_strings(raw: Any) -> list[str]:
        """Return non-empty strings from common JSON-safe obs-write shapes.

        The EnvObservation injection path has evolved over time. Most runs provide
        lists such as ["posture:fallen"], but some diagnostic paths may provide a
        dict such as token_to_bid. This helper keeps the footer defensive without
        changing the underlying memory write behavior.
        """
        if isinstance(raw, str):
            return [raw] if raw else []

        raw_iter: Any
        if isinstance(raw, dict):
            raw_iter = raw.keys()
        elif isinstance(raw, (list, tuple, set)):
            raw_iter = raw
        else:
            return []

        out: list[str] = []
        for item in raw_iter:
            if isinstance(item, str) and item:
                out.append(item)
            elif isinstance(item, dict):
                for key in ("token", "tag", "name"):
                    val = item.get(key)
                    if isinstance(val, str) and val:
                        out.append(val)
                        break
        return out


    def _clean_obs_family_token(tok: str, *, family: str) -> str | None:
        """Normalize one pred/cue token for footer display.

        Returned tokens are prefix-free because the footer later adds the display
        prefix itself via _fmt_items(..., prefix="pred:"/"cue:").
        """
        text = str(tok or "").strip()
        if not text:
            return None

        own_prefix = f"{family}:"
        if text.startswith(own_prefix):
            return text[len(own_prefix):]

        if text.startswith("pred:") or text.startswith("cue:"):
            return None

        return text


    def _dedup_obs_tokens(items: list[str]) -> list[str]:
        """De-duplicate footer tokens while preserving their original order."""
        out: list[str] = []
        seen: set[str] = set()

        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)

        return out


    def _obs_write_family_values(src: dict[str, Any], keys: tuple[str, ...], *, family: str) -> list[str]:
        """Return obs-write values from the first matching schema key."""
        for key in keys:
            out: list[str] = []
            for item in _obs_write_strings(src.get(key)):
                tok = _clean_obs_family_token(item, family=family)
                if tok:
                    out.append(tok)

            if out:
                return _dedup_obs_tokens(out)

        return []


    def _looks_like_pred_token(tok: str) -> bool:
        """Classify unprefixed token_to_bid fallback keys that are clearly predicates."""
        text = str(tok or "").strip()
        return (
            text.startswith("posture:")
            or text.startswith("proximity:")
            or text.startswith("hazard:")
            or text.startswith("nipple:")
            or text.startswith("milk:")
            or text in ("resting", "alert", "seeking_mom")
        )


    def _surface_deltas(ps, cs) -> list[str]:
        # These correspond to the newborn-goat "big slots" that map cleanly onto MapSurface slot-families.
        fields = [
            ("posture", "kid_posture"),
            ("mom", "mom_distance"),
            ("shelter", "shelter_distance"),
            ("cliff", "cliff_distance"),
            ("nipple", "nipple_state"),
        ]
        out: list[str] = []
        for label, attr in fields:
            a = _get_state_attr(ps, attr) if ps is not None else None
            b = _get_state_attr(cs, attr) if cs is not None else None
            if ps is None:
                out.append(f"{label}={b}")
            else:
                if a != b:
                    out.append(f"{label} {a}→{b}")
        return out

    def _parse_fired(txt: str | None) -> dict[str, Any]:
        # fired text is produced by PolicyRuntime.consider_and_maybe_fire(...).
        out: dict[str, Any] = {"policy": None, "added": None, "reward": None, "sel_on": None, "exec_on": None}
        if not (isinstance(txt, str) and txt.strip()):
            return out
        import re  # local import (matches existing style in this file)
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if not lines:
            return out

        # First line: "policy:xyz (added N bindings)"
        first = lines[0]
        parts = first.split()
        if parts and parts[0].startswith("policy:"):
            out["policy"] = parts[0]
        m = re.search(r"added\s+(\d+)\s+bindings", first)
        if m:
            try:
                out["added"] = int(m.group(1))
            except Exception:
                out["added"] = None

        for ln in lines:
            if ln.startswith("[executed]"):
                # Example: [executed] policy:follow_mom (ok, reward=+0.10) binding=w38 (b38)
                m2 = re.search(r"reward=([+\-]?\d+(?:\.\d+)?)", ln)
                if m2:
                    try:
                        out["reward"] = float(m2.group(1))
                    except Exception:
                        out["reward"] = None
            if ln.startswith("[maps]"):
                # Example: [maps] selection_on=WG execute_on=WM
                if "selection_on=" in ln:
                    try:
                        out["sel_on"] = ln.split("selection_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
                if "execute_on=" in ln:
                    try:
                        out["exec_on"] = ln.split("execute_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
        return out

    # Keyframe indicator: best-effort. (Keyframe reasons still appear in the KEYFRAME log line above.)
    is_kf = False
    try:
        is_kf = (getattr(ctx, "lt_obs_last_keyframe_step", None) == getattr(ctx, "controller_steps", None))
    except Exception:
        is_kf = False

    st_stage = _get_state_attr(curr_state, "scenario_stage")
    st_post  = _get_state_attr(curr_state, "kid_posture")
    st_mom   = _get_state_attr(curr_state, "mom_distance")
    st_nip   = _get_state_attr(curr_state, "nipple_state")

    dr_h = _sf(getattr(drives, "hunger", None))
    dr_f = _sf(getattr(drives, "fatigue", None))
    dr_w = _sf(getattr(drives, "warmth", None))

    # WG write summary (env injection)
    wg_preds: list[str] = []
    wg_cues: list[str] = []
    wg_keyframe = False
    wg_reason_txt = ""

    if isinstance(inj, dict):
        wg_preds = _obs_write_family_values(
            inj,
            (
                "predicates",
                "preds",
                "created_preds",
                "created_predicates",
                "written_predicates",
                "predicates_written",
                "preds_written",
            ),
            family="pred",
        )
        wg_cues = _obs_write_family_values(
            inj,
            (
                "cues",
                "created_cues",
                "written_cues",
                "cues_written",
            ),
            family="cue",
        )

        # Fallback for obs_write schemas that expose only token_to_bid.
        # Unprefixed fallback keys are only treated as predicates when they are from
        # known state-slot families, so we do not accidentally label arbitrary cue text.
        if not (wg_preds or wg_cues):
            token_to_bid = inj.get("token_to_bid")
            if isinstance(token_to_bid, dict):
                pred_fallback: list[str] = []
                cue_fallback: list[str] = []

                for raw_key in token_to_bid.keys():
                    if not isinstance(raw_key, str) or not raw_key:
                        continue

                    key = raw_key.strip()
                    if key.startswith("cue:"):
                        tok = _clean_obs_family_token(key, family="cue")
                        if tok:
                            cue_fallback.append(tok)
                    elif key.startswith("pred:"):
                        tok = _clean_obs_family_token(key, family="pred")
                        if tok:
                            pred_fallback.append(tok)
                    elif _looks_like_pred_token(key):
                        pred_fallback.append(key)

                wg_preds = _dedup_obs_tokens(pred_fallback)
                wg_cues = _dedup_obs_tokens(cue_fallback)

        wg_keyframe = bool(inj.get("keyframe"))

        reason_items = _obs_write_strings(
            inj.get("keyframe_reasons")
            or inj.get("keyframe_reason")
            or inj.get("reasons")
        )
        reason_items = _dedup_obs_tokens(reason_items)
        if reason_items:
            wg_reason_txt = " reason=" + _fmt_items(reason_items, prefix="", limit=3)

    # EnvObservation input summary (what crossed the env→agent boundary this tick)
    obs_preds: list[str] = []
    obs_cues: list[str] = []
    obs_drop_p = 0
    obs_drop_c = 0
    if env_obs is not None:
        try:
            pr = getattr(env_obs, "predicates", None)
            if isinstance(pr, list):
                obs_preds = [str(x).replace("pred:", "", 1) for x in pr if isinstance(x, str) and x]
        except Exception:
            obs_preds = []

        try:
            cr = getattr(env_obs, "cues", None)
            if isinstance(cr, list):
                obs_cues = [str(x).replace("cue:", "", 1) for x in cr if isinstance(x, str) and x]
        except Exception:
            obs_cues = []

        try:
            em = getattr(env_obs, "env_meta", None)
            if isinstance(em, dict):
                obs_drop_p = int(em.get("obs_mask_dropped_preds", 0) or 0)
                obs_drop_c = int(em.get("obs_mask_dropped_cues", 0) or 0)
        except Exception:
            obs_drop_p = 0
            obs_drop_c = 0

    fired_info = _parse_fired(fired_txt)

    # ---- line 1: inputs
    kf_txt = "KF" if is_kf else "--"
    step_txt = str(env_step) if isinstance(env_step, int) else "?"
    zone_txt = zone if isinstance(zone, str) else "?"

    mask_txt = ""
    if (obs_drop_p or obs_drop_c) and (obs_drop_p >= 0 and obs_drop_c >= 0):
        mask_txt = f" mask_drop(p={obs_drop_p} c={obs_drop_c})"

    print(
        f"[cycle] IN   {kf_txt} cycle={cycle_no}/{cycle_total} env_step={step_txt} "
        f"stage={st_stage} posture={st_post} mom={st_mom} nipple={st_nip} zone={zone_txt} "
        f"drives(h={dr_h} f={dr_f} w={dr_w}) applied_action={action_applied_this_step!r} "
        f"obs(p={len(obs_preds)} c={len(obs_cues)}){mask_txt}"
    )

    # ---- line 1b: observation detail (preds/cues + navpatch summary)
    patches_in = getattr(env_obs, "nav_patches", None) or []
    patch_n = len(patches_in) if isinstance(patches_in, list) else 0
    uniq_sig16: set[str] = set()
    patch_ids: set[str] = set()

    if patch_n:
        for p in patches_in:
            if not isinstance(p, dict):
                continue

            try:
                uniq_sig16.add(navpatch_payload_sig_v1(p)[:16])
            except Exception:
                pass

            role = p.get("role") if isinstance(p.get("role"), str) else ""
            local_id = p.get("local_id") if isinstance(p.get("local_id"), str) else ""
            entity_id = p.get("entity_id") if isinstance(p.get("entity_id"), str) else ""

            key = ""
            if role and local_id:
                key = f"{role}|{local_id}"
            elif role and entity_id:
                key = f"{role}|{entity_id}"
            elif entity_id and local_id:
                key = f"{entity_id}|{local_id}"
            elif role:
                key = role
            elif local_id:
                key = local_id
            elif entity_id:
                key = entity_id

            if key:
                patch_ids.add(key)

    ids_txt = ""
    if patch_ids:
        ids = sorted(patch_ids)
        show_n = 4
        shown = ids[:show_n]
        more = len(ids) - len(shown)

        ids_body = ", ".join(shown)
        if more > 0:
            ids_body = ids_body + f", +{more} more"

        ids_txt = f" ids=[{ids_body}]"

    nav_txt = f"nav_patches={patch_n} uniq_sig16={len(uniq_sig16)}{ids_txt}"

    obs_note_txt = ""
    try:
        obs_pred_set = {str(x) for x in obs_preds if isinstance(x, str) and x}
        if (
            isinstance(st_post, str)
            and st_post == "latched"
            and "posture:standing" in obs_pred_set
            and "nipple:latched" in obs_pred_set
            and "milk:drinking" in obs_pred_set
        ):
            obs_note_txt = (
                " | note: in this early CCA8, env_posture='latched' is encoded perceptually as "
                "posture:standing + nipple:latched + milk:drinking"
            )
    except Exception:
        obs_note_txt = ""

    if obs_preds or obs_cues or patch_n:
        pred_txt = _fmt_items(obs_preds, prefix="", limit=max_items) if obs_preds else "(none)"
        cue_txt = _fmt_items(obs_cues, prefix="", limit=max_items) if obs_cues else "(none)"
        print(f"[cycle] OBS  preds: {pred_txt} | cues: {cue_txt} | {nav_txt}{obs_note_txt}")

    # ---- line 2: WorkingMap summary (surface deltas + scratch writes)
    deltas = _surface_deltas(prev_state, curr_state)
    delta_txt = _fmt_items(deltas, prefix="", limit=max_items) if deltas else "(no surface slot change)"
    pol = fired_info.get("policy") or next_action_for_env
    added = fired_info.get("added")
    exec_on = fired_info.get("exec_on")
    scratch_txt = "(no policy fired)"
    if isinstance(pol, str) and pol:
        if isinstance(added, int):
            scratch_txt = f"{pol} +{added} binding(s)"
        else:
            scratch_txt = f"{pol}"
        if exec_on:
            scratch_txt += f" (exec_on={exec_on})"
    print(f"[cycle] WM   surfaceΔ: {delta_txt} | scratch: {scratch_txt}")
    # [cycle] ZM — Zoom transitions (Phase X Step 15B)
    # We only print on transition ticks (zoom_down / zoom_up) so logs stay readable.
    try:
        z_events = getattr(ctx, "wm_zoom_last_events", None)
        if isinstance(z_events, list) and z_events:
            ev0 = z_events[0] if isinstance(z_events[0], dict) else {}
            kind = ev0.get("kind") if isinstance(ev0.get("kind"), str) else "zoom"
            reason = ev0.get("reason") if isinstance(ev0.get("reason"), str) else ""
            ents = ev0.get("ambiguous_entities") if isinstance(ev0.get("ambiguous_entities"), list) else []
            ent_txt = _fmt_items(ents, prefix="", limit=3) if ents else "(none)"
            amb_n = ev0.get("ambiguous_n")
            try:
                amb_n = int(amb_n) if amb_n is not None else None
            except Exception:
                amb_n = None
            amb_txt = f" amb={amb_n}" if isinstance(amb_n, int) else ""
            rz = f" reason={reason}" if reason else ""
            print(f"[cycle] ZM   {kind}{rz}{amb_txt} ents={ent_txt}")
    except Exception:
        pass

    # [cycle] MS — Map-switch events (P3.11)
    try:
        ms_events = getattr(ctx, "wm_mapswitch_last_events", None)
        if isinstance(ms_events, list) and ms_events:
            ev0 = ms_events[-1] if isinstance(ms_events[-1], dict) else {}
            line = format_mapswitch_event_line_v1(ev0)
            if line and line != "(none)":
                print(f"[cycle] MS   {line}")
    except Exception:
        pass


    # [cycle] SG — SurfaceGrid HUD (Phase X Step 12)
    if bool(getattr(ctx, "wm_surfacegrid_enabled", False)):
        sg_sig16 = getattr(ctx, "wm_surfacegrid_sig16", None)
        sg_sig16 = sg_sig16 if isinstance(sg_sig16, str) and sg_sig16 else "(none)"
        try:
            sg_ms = float(getattr(ctx, "wm_surfacegrid_compose_ms", 0.0) or 0.0)
        except Exception:
            sg_ms = 0.0

        reasons = getattr(ctx, "wm_surfacegrid_dirty_reasons", None)
        reasons = reasons if isinstance(reasons, list) else []

        reason_items = [str(r) for r in reasons[:3] if isinstance(r, str) and r]
        if reason_items == ["cache_hit"]:
            reason_txt = ""
        else:
            reason_txt = ",".join(reason_items)
            reason_txt = f" ({reason_txt})" if reason_txt else ""

        print(f"[cycle] SG   surfacegrid_sig16={sg_sig16} compose_ms={sg_ms:.2f}{reason_txt}")

        # ASCII map dump:
        # Optional ASCII map dump using the same changed-vs-unchanged logic as
        # the older [surfacegrid] snapshot path.
        if bool(getattr(ctx, "wm_surfacegrid_verbose", False)):
            legend_txt = (
                "@=self &=self+mom M=mom S=shelter C=cliff G=goal "
                "#=hazard X=blocked *=other  (dense: .=traversable; sparse: space=unknown/trav)"
            )
            sg = getattr(ctx, "wm_surfacegrid", None)
            print(
                _surfacegrid_ascii_terminal_block_v1(
                    ctx,
                    sg,
                    sig16=sg_sig16,
                    line_prefix="[cycle] SG   ",
                    title=f"WM.SurfaceGrid (sig16={sg_sig16})",
                    legend=legend_txt,
                )
            )

    # [cycle] NS — NavSummary HUD (Phase X P1.4)
    try:
        if bool(getattr(ctx, "wm_navsummary_enabled", False)):
            ns = getattr(ctx, "wm_navsummary", None)
            if isinstance(ns, dict) and ns:
                print(f"[cycle] NS   {format_navsummary_line_v1(ns)}")
    except Exception:
        pass

    # ---- line 3: WorldGraph writes this tick
    wg_txt = f"preds+{len(wg_preds)} cues+{len(wg_cues)}"
    if wg_keyframe:
        wg_txt += " keyframe=Y"

    wg_pred_txt = _fmt_items(wg_preds, prefix="pred:", limit=max_items)
    wg_cue_txt = _fmt_items(wg_cues, prefix="cue:", limit=max_items)
    print(f"[cycle] WG   wrote {wg_txt}{wg_reason_txt} | {wg_pred_txt} | {wg_cue_txt}")

    # ---- line 4: Column ops (only meaningful on keyframes)
    if col_store_txt or col_retrieve_txt or col_apply_txt:
        cs = col_store_txt or "store: (n/a)"
        cr = col_retrieve_txt or "retrieve: (n/a)"
        ca = col_apply_txt or "apply: (n/a)"
        print(f"[cycle] COL  {cs} | {cr} | {ca}")
    else:
        print("[cycle] COL  (no wm<->col ops this cycle)")

    # ---- line 5: action recap
    r = fired_info.get("reward")
    rtxt = f"{r:+.2f}" if isinstance(r, (int, float)) else "n/a"
    print(f"[cycle] ACT  executed={pol!r} reward={rtxt} next_action={next_action_for_env!r}")


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
    Run N closed-loop steps between the HybridEnvironment and the CCA8 brain
    in a condensed, explanatory way.

    Each step:
      - advances controller_steps and the temporal soft clock (no autonomic ticks here),
      - calls env.reset() once (if this is the first ever env step for this episode),
        or env.step(last_policy_action, ctx) on later steps,
      - injects EnvObservation into the WorldGraph via inject_obs_into_world(...),
      - runs one controller step via PolicyRuntime.consider_and_maybe_fire(...),
      - remembers the last fired policy name in ctx.env_last_action so the next
        env.step(...) can react to it.

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
    print("  1) Advance controller_steps and the temporal soft clock (one drift),")
    print("  2) Call env.reset() (first time) or env.step(last policy action),")
    print("  3) Inject EnvObservation into the WorldGraph as pred:/cue: facts,")
    print("  4) Run ONE controller step (Action Center) and store the last policy name.\n")

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

        # 1) Timekeeping for this controller loop (soft clock only)
        try:
            ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
        except Exception:
            pass
        if getattr(ctx, "temporal", None):
            ctx.temporal.step()

        prev_state = None
        action_for_env: str | None = None

        # 2) Environment evolution (reset once, then step with last action)
        if not getattr(ctx, "env_episode_started", False):
            env_obs, env_info = env.reset()
            _phase7_reset_run_state() # phase7 s/w devpt: clear any previous run state on env reset
            ctx.env_episode_started = True
            ctx.env_last_action = None
            ctx.navmap_pending_action_v1 = None
            ctx.navmap_pending_reward_v1 = 0.0
            ctx.navmap_last_payload_v1 = None
            ctx.navmap_last_expected_current_payload_v1 = None
            ctx.navmap_last_expected_current_comparison_v1 = None
            ctx.navmap_last_accepted_current_v1 = None
            step_idx = env_info.get("step_index", 0)
            print(
                f"[env] Reset env scenario: "
                f"episode_index={env_info.get('episode_index')} "
                f"scenario={env_info.get('scenario_name')}"
            )
        else:
            # Snapshot previous EnvState so we can explain posture/nipple/zone changes.
            try:
                prev_state = env.state.copy()
            except Exception:
                prev_state = None

            action_for_env = ctx.env_last_action
            env_obs, _env_reward, _env_done, env_info = env.step(
                action=action_for_env,
                ctx=ctx,
            )
            ctx.env_last_action = None
            ctx.navmap_pending_action_v1 = action_for_env if isinstance(action_for_env, str) else None
            try:
                ctx.navmap_pending_reward_v1 = float(_env_reward)
            except (TypeError, ValueError):
                ctx.navmap_pending_reward_v1 = 0.0
            st = env.state
            step_idx = env_info.get("step_index")
            ctx_txt = ""
            try:
                c_label = getattr(st, "context_label", None)
                if isinstance(c_label, str) and c_label:
                    ctx_txt = f" context={c_label}"
            except Exception:
                ctx_txt = ""
            print(
                f"[env] env_step={step_idx} (since reset) "
                f"stage={st.scenario_stage} posture={st.kid_posture} "
                f"mom_distance={st.mom_distance} nipple_state={st.nipple_state}{ctx_txt} "
                f"action={action_for_env!r}"
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
                and isinstance(action_for_env, str)
                and action_for_env
                and isinstance(obs_posture, str)
                and isinstance(pred_posture, str)
            ):
                # 1) Append a standardized discrepancy entry (so RecoverFall can see streaks in menu 37)
                entry = (
                    f"[discrepancy] env posture={obs_posture!r} "
                    f"vs policy-expected posture={pred_posture!r} from {action_for_env}"
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
                                (f"from {action_for_env}" in s)
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
                    update_skill(action_for_env, shaping_reward, ok=False)
                    try:
                        q_now = float(skill_q(action_for_env))
                    except Exception:
                        q_now = 0.0
                    print(
                        f"[pred_err] shaping: policy={action_for_env} reward={shaping_reward:+.2f} "
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

        try:
            policy_rt.refresh_loaded(ctx)

            if bool(getattr(ctx, "phase7_working_first", False)):
                if getattr(ctx, "working_world", None) is None:
                    ctx.working_world = init_working_world()
                exec_world = ctx.working_world
            _wm_creative_update(policy_rt, world, drives, ctx, exec_world=exec_world)
            fired = policy_rt.consider_and_maybe_fire(world, drives, ctx, exec_world=exec_world)

            fired_txt = fired if isinstance(fired, str) else None

            if fired != "no_match":
                print(f"[env→controller] {fired}")

                # Extract clean "policy:..." for env.step(...) on the next loop.
                if isinstance(fired, str):
                    first_token = fired.split()[0]
                    if isinstance(first_token, str) and first_token.startswith("policy:"):
                        ctx.env_last_action = first_token
                        policy_name = first_token
                    else:
                        ctx.env_last_action = None
                else:
                    ctx.env_last_action = None
            else:
                ctx.env_last_action = None
        except Exception as e:
            print(f"[env→controller] controller step error: {e}")
            ctx.env_last_action = None

        if teaching_mode:
            print(menu37_teaching_after_controller_v1())
            print()

        # --- Capture NEXT-step prediction (Scratch postcondition), v1 record; v0 posture fields kept for compatibility ---
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
                    source="WorkingMap.Scratch" if exec_world is not world else "WorldGraph.policy_trace",
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

        # start/extend run for the policy we just chose (applied on the NEXT env step)
        if _phase7_enabled():
            token_to_bid = {}
            if isinstance(obs_write, dict):
                raw_map = obs_write.get("token_to_bid")
                if isinstance(raw_map, dict):
                    token_to_bid = raw_map

            state_bid = _phase7_pick_state_bid(token_to_bid)
            _phase7_start_or_extend_run(world, state_bid, policy_name, env_step=step_idx)

        # Short summary for this step + posture/nipple/zone explanations
        try:
            st = env.state
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
                f"[env-loop] summary cognitive_cycle={i+1}/{n_steps} env_step={step_idx} stage={st.scenario_stage} "
                f"env_posture={st.kid_posture} bm_posture={bm_posture or st.kid_posture} "
                f"mom={st.mom_distance} nipple={st.nipple_state} last_policy={policy_name!r}"
            )
            if expected_posture is not None:
                line += f" expected_posture={expected_posture}"
            if zone is not None:
                line += f" zone={zone}"
            print(line)

            if expected_posture is not None and str(expected_posture) != str(st.kid_posture):
                print("[env-loop] note: expected_posture is a Scratch postcondition (hypothesis); env_posture is storyboard truth this tick.")

            quiet_rest_tail = _quiet_solved_rest_tail_v1(
                st,
                zone,
                action_for_env,
                getattr(ctx, "env_last_action", None),
            )

            if not quiet_rest_tail:
                # Explain why posture ended up as it is at this step.
                try:
                    posture_expl = _explain_posture_change(prev_state, st, action_for_env)
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
                    nipple_expl = _explain_nipple_change(prev_state, st, action_for_env)
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
                    action_applied_this_step=action_for_env,
                    next_action_for_env=getattr(ctx, "env_last_action", None),
                    cycle_no=i + 1,
                    cycle_total=n_steps,
                )
            except Exception:
                pass
        except Exception:
            pass

        # Per-cycle JSON record (Phase X scaffolding): replayable debug trace.
        # This is OFF by default; enable by setting ctx.cycle_json_enabled=True and (optionally)
        # ctx.cycle_json_path="cycle_log.jsonl".
        try:
            if bool(getattr(ctx, "cycle_json_enabled", False)):
                st = env.state
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
                    "scenario_stage": getattr(st, "scenario_stage", None),
                    "posture": getattr(st, "kid_posture", None),
                    "mom_distance": getattr(st, "mom_distance", None),
                    "nipple_state": getattr(st, "nipple_state", None),
                    "zone": zone_now,
                    "action_applied": action_for_env,
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

    print("\n[env-loop] Closed-loop cognitive cycle complete. "
          "You can inspect details via Snapshot or the mini-snapshot that follows.")
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


def _latest_posture_binding(world, *, source: Optional[str] = None, require_policy: bool = False):
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
    try:
        bids = _sorted_bids(world)
    except Exception:
        return None, None, None

    for bid in reversed(bids):
        b = world._bindings.get(bid)
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


def mini_snapshot_text(world, ctx=None, limit: int = 50) -> str:
    """
    Compact mini-snapshot: one timekeeping line + a short list of recent bindings
    with their outgoing edges.

    Intentionally omits [src=...] annotations so readers see only the conceptual
    structure (bindings/tags/edges) without internal implementation details.
    """
    lines: list[str] = []

    # Timekeeping line (if ctx is available)
    if ctx is not None:
        try:
            lines.append("[time] " + timekeeping_line(ctx))
        except Exception:
            lines.append("[time] (unavailable)")
    else:
        lines.append("[time] (ctx unavailable)")

    try:
        lines.append(prediction_feedback_mini_line_v1(ctx))
    except Exception:
        lines.append("[pred] (unavailable)")

    try:
        lines.append(navmap_observation_update_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap] (unavailable)")

    try:
        lines.append(navmap_expected_current_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-expected] (unavailable)")

    try:
        lines.append(navmap_accepted_current_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-accepted] (unavailable)")

    try:
        lines.append(working_navmap_surface_mini_line_v1(ctx))
    except Exception:
        lines.append("[working-navmap] (unavailable)")

    try:
        lines.append(navmap_transition_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-transition] (unavailable)")

    try:
        lines.append(navmap_scope_mini_line_v1(ctx))
    except Exception:
        lines.append(f"{NAVMAP_SCOPE_MARKER_V1} [navmap-scope] (unavailable)")

    # Compact world view: last `limit` bindings with their outgoing edges
    try:
        bids = _sorted_bids(world)
    except Exception:
        bids = []

    if not bids:
        lines.append("[world] no bindings yet")
        return "\n".join(lines)

    n = min(limit, len(bids))
    lines.append(f"[world] last {n} binding(s):")
    for bid in bids[-n:]:
        b = world._bindings.get(bid)
        tags = ", ".join(sorted(getattr(b, "tags", []))) if b else ""
        lines.append(f"  {bid}: [{tags}]")

        # Robust edge extraction with explicit typing (for mypy)
        edges: list[dict[str, Any]] = []
        if b is not None:
            edges_raw = (
                getattr(b, "edges", []) or
                getattr(b, "out", []) or
                getattr(b, "links", []) or
                getattr(b, "outgoing", [])
            )
            if isinstance(edges_raw, list):
                edges = [e for e in edges_raw if isinstance(e, dict)]

        if edges:
            parts: list[str] = []
            for e in edges:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    parts.append(f"{rel}:{dst}")
            if parts:
                lines.append(f"      edges: {', '.join(parts)}")
            else:
                lines.append("      edges: (none)")
        else:
            lines.append("      edges: (none)")

    # Optional posture discrepancy note (env vs policy-expected posture).
    # This is a *display-only* diagnostic: we do NOT create any bindings.
    history_entry: Optional[str] = None
    try:
        env_bid, env_posture, _ = _latest_posture_binding(
            world, source="HybridEnvironment"
        )
        pol_bid, pol_posture, pol_meta = _latest_posture_binding(
            world, require_policy=True
        )

        if env_bid and pol_bid and env_posture and pol_posture and env_posture != pol_posture:
            def _posture_suffix(tag: str) -> str:
                parts = tag.split(":", 2)
                return parts[-1] if parts else tag

            env_state = _posture_suffix(env_posture)
            pol_state = _posture_suffix(pol_posture)
            pol_name = pol_meta.get("policy") if isinstance(pol_meta, dict) else None

            if pol_name:
                msg_main = (
                    f"[discrepancy] env posture={env_state!r} at {env_bid} "
                    f"vs policy-expected posture={pol_state!r} from {pol_name} at {pol_bid}"
                )
            else:
                msg_main = (
                    f"[discrepancy] env posture={env_state!r} at {env_bid} "
                    f"vs policy-expected posture={pol_state!r} at {pol_bid}"
                )

            msg_hint = (
                "[discrepancy] note: a mismatch can be normal right after reset (env has not yet applied the last action); "
                "persistent mismatches across steps suggest failed execution or storyboard veto."
            )

            lines.append(msg_main)
            lines.append(msg_hint)
            history_entry = msg_main

    except Exception:
        # Snapshot must never crash the runner.
        pass

    # Maintain and print discrepancy history (last ~50 events), if ctx supports it.
    try:
        if ctx is not None and hasattr(ctx, "posture_discrepancy_history"):
            hist: list[str] = getattr(ctx, "posture_discrepancy_history", [])
            # Append the newest entry if it exists and is not a duplicate of the last one
            if history_entry:
                if not hist or hist[-1] != history_entry:
                    hist.append(history_entry)
                    if len(hist) > 50:
                        del hist[:-50]
                ctx.posture_discrepancy_history = hist  # in case it was missing before

            if hist:
                lines.append("")
                lines.append("[discrepancy history] recent posture discrepancies (most recent last):")
                for h in hist:
                    lines.append("  " + h)
    except Exception:
        # Again, history bookkeeping must never crash the runner.
        pass

    return "\n".join(lines)


def print_mini_snapshot(world, ctx=None, limit: int = 50) -> None:
    """Print the compact mini-snapshot (safe to call from menu flow).
    """
    try:
        print("Values of time measures, nodes and links at this point:")
        print(mini_snapshot_text(world, ctx, limit))
    except Exception:
        pass



def drives_and_tags_text(drives) -> str:
    """
    Human-readable drives panel with source annotations and a concise explainer.
    """
    lines = []
    lines.append("Raw drives (0..1). Policies can read raw values or threshold flags.")
    lines.append(
        f"  hunger={drives.hunger:.2f}  [src=drives.hunger]  "
        f"HUNGER_HIGH={HUNGER_HIGH:.2f}  [src=cca8_controller.HUNGER_HIGH]"
    )
    lines.append(
        f"  fatigue={drives.fatigue:.2f}  [src=drives.fatigue]  "
        f"FATIGUE_HIGH={FATIGUE_HIGH:.2f}  [src=cca8_controller.FATIGUE_HIGH]"
    )
    lines.append(
        f"  warmth={drives.warmth:.2f}  [src=drives.warmth]  "
        f"rule:cold if warmth<0.30  [src=_drive_tags (derived)]"
    )

    # Compute the tags + show where they came from (flags/predicates/derived)
    if hasattr(drives, "flags") and callable(getattr(drives, "flags")):
        tag_source = "drives.flags()"
    elif hasattr(drives, "predicates") and callable(getattr(drives, "predicates")):
        tag_source = "drives.predicates()"
    else:
        tag_source = "derived thresholds (hunger>0.60, fatigue>0.70, warmth<0.30)"

    tags = _drive_tags(drives)
    lines.append(
        "Drive tags: " +
        (", ".join(tags) if tags else "(none)") +
        f"  [src=_drive_tags → {tag_source}]"
    )

    lines.append("")
    lines.append("Where these live:")
    lines.append("  - Drives object: cca8_controller.Drives  [src=cca8_controller.Drives]")
    lines.append("  - Updated by: autonomic ticks, policies, or direct code.")
    lines.append("  - Drive tags here are ephemeral (not persisted unless you choose to).")

    # === Integrated ~10-line explainer ===
    lines.append("")
    lines.append("Drive flags = thresholds from raw drives (e.g., hunger>=HUNGER_HIGH")
    lines.append("  → drive:hunger_high). They are ephemeral and usually NOT written")
    lines.append("  to the graph; used to gate/weight policies.")
    lines.append("House style: use pred:drive:* only when you want a planner goal")
    lines.append("  (e.g., pred:drive:warm_enough). Otherwise treat thresholds as")
    lines.append("  evidence in triggers (conceptually cue:drive:*).")
    lines.append("Combine flags with sensory cues (e.g., cue:silhouette:mom) in")
    lines.append("  policy.trigger(...). Example: hunger>=HUNGER_HIGH AND cue:nipple:found.")
    lines.append("Priority variant: cues gate; hunger over threshold scales reward/urgency.")
    lines.append("We compute flags on-the-fly each controller step or autonomic tick; persist them only for demos/debug.")
    lines.append("Sources: raw=drives.*, thresholds=HUNGER_HIGH/FATIGUE_HIGH (controller).")

    return "\n".join(lines) + "\n"


def skill_ledger_text(example_policy: str = "policy:stand_up") -> str:
    """
    Human-readable explainer for the Skill Ledger with a concrete example and sources.
    """
    from math import isfinite
    lines = []
    lines.append("The Skill Ledger is per-policy runtime telemetry (RL-flavored):")
    lines.append("  n=executions, succ=successes, rate=succ/n, q=mean reward, last=last reward.")
    lines.append("  Used as a quick controller health check and for tuning/diagnostics.")
    lines.append("Sources: live in-memory ledger → cca8_controller.SKILLS;")
    lines.append("         programmatic snapshot → cca8_controller.skills_to_dict();")
    lines.append("         human-readable lines  → cca8_controller.skill_readout().")
    lines.append("")

    # Example row (policy:stand_up) pulled from skills_to_dict(), with fallbacks
    try:
        d = skills_to_dict() or {}
    except Exception:
        d = {}
    row = d.get(example_policy, {}) if isinstance(d, dict) else {}

    def _get(dd, *keys, default=None):
        for k in keys:
            if isinstance(dd, dict) and k in dd:
                return dd[k]
        return default

    n     = _get(row, "n", "runs", "count", default=0) or 0
    succ  = _get(row, "succ", "successes", "ok", default=0) or 0
    rate  = _get(row, "rate", default=(succ / n if n else None))
    q     = _get(row, "q", "mean_reward", "avg", default=None)
    last  = _get(row, "last", "last_reward", default=None)

    def _fmt(x, nd=2, plus=False):
        if x is None:
            return "n/a"
        try:
            val = float(x)
            if not isfinite(val):
                return "n/a"
            s = f"{val:+.{nd}f}" if plus else f"{val:.{nd}f}"
            return s
        except Exception:
            return str(x)

    lines.append(f"Example ({example_policy}): "
                 f"n={n}, succ={succ}, rate={_fmt(rate)}, q={_fmt(q)}, last={_fmt(last, plus=True)}  "
                 f"[src=skills_to_dict()['{example_policy}']]")
    lines.append("")
    lines.append("Interpretation: higher n builds confidence; rate≈1.0 means it rarely fails;")
    lines.append("q tracks average reward quality; last is the most recent reward sample.")
    return "\n".join(lines) + "\n"


def skills_hud_text(ctx: Optional[Ctx] = None, *, top_n: int = 8) -> str:
    """
    Compact HUD for learned policy values (SkillStat.q).

    - Sorts policies by q (EMA reward) descending.
    - Shows basic counts: n, succ-rate, q, last_reward.
    - If ctx is provided, also prints RL settings + explore/exploit counters.

    This is intentionally a *read-only* helper (no world writes).
    """
    try:
        raw = skills_to_dict() or {}
    except Exception:
        raw = {}

    try:
        delta = float(getattr(ctx, "rl_delta", 0.0))
    except Exception:
        delta = 0.0
    delta = max(delta, 0.0)

    rows: list[tuple[str, int, int, float, float]] = []
    for name, stat in raw.items():
        if not isinstance(name, str) or not isinstance(stat, dict):
            continue
        try:
            n = int(stat.get("n", 0) or 0)
            succ = int(stat.get("succ", 0) or 0)
            q = float(stat.get("q", 0.0) or 0.0)
            last = float(stat.get("last_reward", 0.0) or 0.0)
        except Exception:
            continue
        if n <= 0:
            continue
        rows.append((name, n, succ, q, last))

    if not rows:
        return "(no skill stats yet)"

    # Sort: high q first, then higher n, then name for stability
    rows.sort(key=lambda t: (-t[3], -t[1], t[0]))

    lines: list[str] = []

    if ctx is not None:
        enabled = bool(getattr(ctx, "rl_enabled", False))
        eps_raw = getattr(ctx, "rl_epsilon", None)
        try:
            eff_eps = float(eps_raw) if eps_raw is not None else float(getattr(ctx, "jump", 0.0))
        except (TypeError, ValueError):
            eff_eps = float(getattr(ctx, "jump", 0.0))

        explore = int(getattr(ctx, "rl_explore_steps", 0) or 0)
        exploit = int(getattr(ctx, "rl_exploit_steps", 0) or 0)
        total = explore + exploit
        explore_rate = (explore / total) if total else 0.0

        lines.append(
            "RL: "
            f"enabled={enabled} "
            f"epsilon={eff_eps:.3f} "
            f"delta={delta:.3f} "
            f"(explore={explore}, exploit={exploit}, explore_rate={explore_rate:.2f})"
        )

    show_n = min(top_n, len(rows))
    lines.append(f"Skill HUD (top {show_n} by q=EMA reward):")

    for i, (name, n, succ, q, last) in enumerate(rows[:show_n], start=1):
        rate = (succ / n) if n else 0.0
        lines.append(
            f"  {i:2d}) {name:<18}  n={n:3d}  rate={rate:.2f}  q={q:+.2f}  last={last:+.2f}"
        )

    return "\n".join(lines)


def _io_banner(args, loaded_path: str | None, loaded_ok: bool) -> None:
    """Explain how load/autosave will behave for this run.
    """
    ap = (args.autosave or "").strip() if hasattr(args, "autosave") else ""
    lp = (loaded_path or "").strip() if loaded_path else ""
    def _same(a, b):  # robust path compare
        try: return os.path.abspath(a) == os.path.abspath(b)
        except Exception: return a == b

    if loaded_ok and ap and _same(ap, lp):
        print(f"[io] Loaded '{lp}'. Autosave ON to the same file — state will be saved in-place after each action. "
              f"(the file is fully rewritten on each autosave).")
    elif loaded_ok and ap and not _same(ap, lp):
        print(f"[io] Loaded '{lp}'. Autosave ON to '{ap}' — new steps will be written to the autosave file; "
              f"the original load file remains unchanged.")
    elif loaded_ok and not ap:
        print(f"[io] Loaded '{lp}'. Autosave OFF")
        print("[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>.")
    elif (not loaded_ok) and ap:
        print(f"[io] Started a NEW session. Autosave ON to '{ap}'.")
    else:
        print("[io] Started a NEW session. Autosave OFF — use menu selection Save Session or relaunch with --autosave <path>.")


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



def _sim_robot_goat_value_text_v1(value: Any) -> str:
    """Return a compact terminal-safe text form for the RCOS sandbox menu."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _sim_robot_goat_obs_lines_v1(obs: EnvObservation) -> list[str]:
    """Return a compact human-readable summary of one SimRobotGoat observation.

    This is a runner-only presentation helper. It does not interpret or mutate the
    simulated robot world. All state-transition logic remains in cca8_rcos.py.
    """
    raw = obs.raw_sensors if isinstance(obs.raw_sensors, dict) else {}
    meta = obs.env_meta if isinstance(obs.env_meta, dict) else {}

    pos = meta.get("position") if isinstance(meta.get("position"), dict) else {}
    goal = meta.get("goal") if isinstance(meta.get("goal"), dict) else {}
    milestones = meta.get("milestones") if isinstance(meta.get("milestones"), list) else []

    x_val = pos.get("x", raw.get("x"))
    y_val = pos.get("y", raw.get("y"))
    gx_val = goal.get("x")
    gy_val = goal.get("y")

    return [
        "[rcos] observation",
        (
            f"  position=({_sim_robot_goat_value_text_v1(x_val)}, {_sim_robot_goat_value_text_v1(y_val)}) "
            f"heading={_sim_robot_goat_value_text_v1(raw.get('heading', meta.get('heading')))} "
            f"battery={_sim_robot_goat_value_text_v1(raw.get('battery'))} "
            f"fatigue={_sim_robot_goat_value_text_v1(raw.get('fatigue'))}"
        ),
        (
            f"  goal=({_sim_robot_goat_value_text_v1(gx_val)}, {_sim_robot_goat_value_text_v1(gy_val)}) "
            f"hazard_near={_sim_robot_goat_value_text_v1(raw.get('hazard_near'))} "
            f"at_target={_sim_robot_goat_value_text_v1(raw.get('at_target'))} "
            f"at_dock={_sim_robot_goat_value_text_v1(raw.get('at_dock'))}"
        ),
        f"  predicates={list(obs.predicates or [])}",
        f"  cues={list(obs.cues or [])}",
        (
            f"  step_index={_sim_robot_goat_value_text_v1(meta.get('step_index'))} "
            f"milestones={milestones}"
        ),
    ]


def _sim_robot_goat_status_lines_v1(status: dict[str, Any]) -> list[str]:
    """Return a compact status block for the runner-side SimRobotGoat sandbox menu.

    This helper exists so the menu branch stays readable and the formatting logic is
    centralized in one small place.
    """
    state = status.get("state") if isinstance(status.get("state"), dict) else {}
    summary = status.get("summary") if isinstance(status.get("summary"), dict) else {}
    milestones = status.get("milestones") if isinstance(status.get("milestones"), list) else []

    return [
        "[rcos] status",
        (
            f"  done={_sim_robot_goat_value_text_v1(status.get('done'))} "
            f"hal_estopped={_sim_robot_goat_value_text_v1(status.get('hal_estopped'))} "
            f"success={_sim_robot_goat_value_text_v1(summary.get('success'))} "
            f"done_reason={_sim_robot_goat_value_text_v1(summary.get('done_reason'))}"
        ),
        (
            f"  milestone_score={_sim_robot_goat_value_text_v1(summary.get('milestone_score'))} "
            f"steps={_sim_robot_goat_value_text_v1(summary.get('steps'))}"
        ),
        (
            f"  posture={_sim_robot_goat_value_text_v1(state.get('posture'))} "
            f"heading={_sim_robot_goat_value_text_v1(state.get('heading'))} "
            f"position=({_sim_robot_goat_value_text_v1(state.get('x'))}, "
            f"{_sim_robot_goat_value_text_v1(state.get('y'))})"
        ),
        (
            f"  battery={_sim_robot_goat_value_text_v1(state.get('battery'))} "
            f"fatigue={_sim_robot_goat_value_text_v1(state.get('fatigue'))} "
            f"step_index={_sim_robot_goat_value_text_v1(state.get('step_index'))}"
        ),
        (
            f"  milestones={milestones} "
            f"falls={_sim_robot_goat_value_text_v1(summary.get('falls'))} "
            f"safety_violations={_sim_robot_goat_value_text_v1(summary.get('safety_violations'))} "
            f"loops={_sim_robot_goat_value_text_v1(summary.get('repeated_action_loop_count'))}"
        ),
        (
            f"  target_inspected={_sim_robot_goat_value_text_v1(summary.get('target_inspected'))} "
            f"at_dock={_sim_robot_goat_value_text_v1(summary.get('at_dock'))} "
            f"returned_to_dock={_sim_robot_goat_value_text_v1(summary.get('returned_to_dock'))} "
            f"final_posture={_sim_robot_goat_value_text_v1(summary.get('final_posture'))}"
        ),
    ]


def _sim_robot_goat_ack_lines_v1(ack: Any) -> list[str]:
    """Return a compact acknowledgement block for one SimRobotGoat command."""
    data: dict[str, Any]

    if isinstance(ack, dict):
        data = dict(ack)
    elif hasattr(ack, "to_dict") and callable(getattr(ack, "to_dict")):
        try:
            data = dict(ack.to_dict())
        except Exception:
            data = {"note": str(ack)}
    else:
        data = {"note": str(ack)}

    new_milestones = data.get("new_milestones")
    if not isinstance(new_milestones, list):
        new_milestones = []

    return [
        "[rcos] ack",
        (
            f"  command={_sim_robot_goat_value_text_v1(data.get('command'))} "
            f"ok={_sim_robot_goat_value_text_v1(data.get('ok'))} "
            f"status={_sim_robot_goat_value_text_v1(data.get('status'))} "
            f"changed={_sim_robot_goat_value_text_v1(data.get('changed'))} "
            f"reward={_sim_robot_goat_value_text_v1(data.get('reward'))}"
        ),
        f"  note={_sim_robot_goat_value_text_v1(data.get('note'))}",
        f"  new_milestones={new_milestones}",
    ]


def sim_robot_goat_menu_50_interactive(sim_hal: Optional[SimRobotGoatHAL]) -> SimRobotGoatHAL:
    """Interactive Stage-1 RCOS sandbox menu for SimRobotGoat.

    Design intent
    -------------
    This is intentionally a thin runner wrapper only. All robot/world logic remains
    inside cca8_rcos.py. The runner is responsible only for terminal I/O, command
    selection, and compact status rendering.
    """
    hal = sim_hal if isinstance(sim_hal, SimRobotGoatHAL) else SimRobotGoatHAL()

    if getattr(getattr(hal, "env", None), "state", None) is None:
        obs = hal.reset()
        print("\n[rcos] Initialized SimRobotGoat sandbox.")
        for line in _sim_robot_goat_obs_lines_v1(obs):
            print(line)
        print()
        for line in _sim_robot_goat_status_lines_v1(hal.status()):
            print(line)
        print()
        print(hal.env.render_ascii())

    while True:
        print("\nSelection: SimRobotGoat RCOS sandbox")
        print("  1) Reset episode")
        print("  2) Show ASCII map")
        print("  3) Show status / summary")
        print("  4) Sense current observation")
        print("  5) Step one Stage-1 command")
        print("  6) HAL emergency stop")
        print("  Enter) Return to main menu")

        choice = input("\nChoose [1,2,3,4,5,6, Enter]: ").strip().lower()

        if choice == "":
            print("[rcos] Returning to main menu.")
            return hal

        if choice in ("1", "reset", "r"):
            raw_seed = input("\nReset seed (blank = keep current deterministic stream): ").strip()
            seed_value: Optional[int] = None

            if raw_seed:
                try:
                    seed_value = int(raw_seed)
                except ValueError:
                    print("[rcos] Invalid seed. Please enter an integer or leave blank.")
                    continue

            obs = hal.reset(seed=seed_value)
            print("\n[rcos] Episode reset.")
            for line in _sim_robot_goat_obs_lines_v1(obs):
                print(line)
            print()
            for line in _sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            print()
            print(hal.env.render_ascii())
            continue

        if choice in ("2", "map", "ascii", "render"):
            print("\n[rcos] ASCII map")
            print(hal.env.render_ascii())
            continue

        if choice in ("3", "status", "summary"):
            print()
            for line in _sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            continue

        if choice in ("4", "sense", "obs", "observe"):
            obs = hal.sense()
            print()
            for line in _sim_robot_goat_obs_lines_v1(obs):
                print(line)
            continue

        if choice in ("5", "step", "command", "act"):
            print("\n[rcos] Available Stage-1 commands:")
            for idx, command_name in enumerate(SIM_ROBOT_GOAT_COMMANDS, start=1):
                print(f"  {idx}) {command_name}")

            raw_command = input("\nCommand number or name (blank = cancel): ").strip().lower()
            if not raw_command:
                print("[rcos] Command step cancelled.")
                continue

            command = raw_command
            if raw_command.isdigit():
                cmd_index = int(raw_command)
                if 1 <= cmd_index <= len(SIM_ROBOT_GOAT_COMMANDS):
                    command = SIM_ROBOT_GOAT_COMMANDS[cmd_index - 1]
                else:
                    print("[rcos] Invalid command number.")
                    continue

            ack = hal.act(command)
            print()
            for line in _sim_robot_goat_ack_lines_v1(ack):
                print(line)

            obs = hal.sense()
            print()
            for line in _sim_robot_goat_obs_lines_v1(obs):
                print(line)

            print()
            for line in _sim_robot_goat_status_lines_v1(hal.status()):
                print(line)

            print()
            print(hal.env.render_ascii())
            continue

        if choice in ("6", "estop", "stop", "emergency"):
            hal.emergency_stop()
            print("\n[rcos] HAL emergency stop latched. Use reset to clear it.")
            for line in _sim_robot_goat_status_lines_v1(hal.status()):
                print(line)
            continue

        print(f"[rcos] Unknown selection: {choice!r}")


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

    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)
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

    ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump) # temporal soft clock (added)
    ctx.tvec_last_boundary = ctx.temporal.vector()  # seed “last boundary”
    try:
        ctx.boundary_vhash64 = ctx.tvec64()
    except Exception:
        ctx.boundary_vhash64 = None

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
        name, sigma, jump, k = profile_rcos_api(ctx)
    elif args.profile:
        if args.profile == "goat":
            name, sigma, jump, k = _goat_defaults()
        elif args.profile == "chimp":
            name, sigma, jump, k = profile_chimpanzee(ctx)
        elif args.profile == "human":
            name, sigma, jump, k = profile_human(ctx)
        else:
            name, sigma, jump, k = profile_superhuman(ctx)
    else:
        profile = choose_profile(ctx, world)
        name = profile["name"]
        sigma = profile["ctx_sigma"]
        jump = profile["ctx_jump"]
        k = profile["winners_k"]

    ctx.profile = name
    ctx.sigma = sigma
    ctx.jump = jump
    ctx.winners_k = k
    print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})")
    print(
        "  sigma/jump = TemporalContext drift/jump noise scales; "
        "k = reserved top-k winners knob (future WTA selection).\n"
    )

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
    print_startup_notices(world)
    print("[profile] Hardwired memory pipeline: phase7 daily-driver (no options menu needed).")

    run_preflight_lite_maybe()  # optional preflight-lite
    pretty_scroll = True        #to see changes before terminal menu scrolls over screen

    # Interactive menu loop  >>>>>>>>>>>>>>>>>>>
    while True:
        try:
            print(f"\n{cca8_cli.MAIN_MENU_HEADER}")

            if pretty_scroll:
                temp = input(
                    "\nPress ENTER to continue and display the CCA8 Main Menu "
                    "\n(Type * then Enter to disable these pauses for the session) "
                )
                if temp == "*":
                    pretty_scroll = False

            choice = input(cca8_cli.MAIN_MENU_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return


        ckey = choice.strip().lower()

        # If it's not a pure number, try word/prefix routing first
        if not ckey.isdigit():
            # A successful route returns a displayed menu number; ambiguous prefixes return candidate aliases.
            routed, matches = cca8_cli.route_menu_alias(ckey)
            if routed is not None:
                if pretty_scroll:
                    print(f"[text input menu selection successfully matched: '{ckey}' → {routed}]")
                choice = routed
            else:
                if len(matches) > 1:
                    print(f"[help] Ambiguous input '{ckey}'. "
                          f"Try one of: {', '.join(sorted(matches)[:6])}"
                          f"{'...' if len(matches) > 6 else ''}")
                    continue #ambiguous entry thus restart while loop above for new input

        ckey = choice.strip().lower() #ensure any present or future routed value is in correct form
        routed = cca8_cli.route_menu_number(ckey)
        if pretty_scroll and ckey != routed:
            print(
                "[[menu numbering auto-compatibility] processed input entry "
                f"routed to old value: {ckey} → {routed}]\n"
            )
        choice = routed

        #FIRST MENU SELECTION CODE BLOCK.... WITHIN interactive menu while loop >>>>>> of interactive_menu()
        #----Menu Selection Code Block------------------------
        if choice == "1":
            # World stats
            now_id = _anchor_id(world, "NOW")
            print("Selection:  World Graph Statistics\n")
            print('''
The CCA8 architecture holds symbolic declarative memory (i.e., episodic and semantic memory) in the WorldGraph.

There are bindings (i.e., nodes) in the WorldGraph, each of which holds directed edges to other bindings (i.e., nodes),
 concise semantic and episodic information, metadata, and pointers to engrams in the cortical-like Columns which
 is the rich store of knowledge.
e.g., 'b1' means binding 1, 'b2' means binding 2, and so on

As mentioned, the bindings (i.e., nodes) are linked to each other by directed edges.
An 'anchor' is a binding which we use to start the WorldGraph as well as a starting point somewhere in the middle
  of the graph. Symbolic procedural knowledge is held in the Policies which currently are held in the
  Controller Module.
A policy (i.e., same as primitive in the CCA8 published papers) is a simple set of conditional actions.
In order to execute, a policy must be loaded (e.g., meets development requirements) and then it must be triggered.

Note we are showing the symbolic statistics here. The distributed, rich information of the CCA8, i.e., its engrams,
  are held in the Columns.\n
Below we show some general WorldGraph and Policy statistics. See Snapshot and other menu selections for more details
  on the system.

            ''')
            print(f"Bindings: {len(world._bindings)}  Anchors: NOW={now_id}  Latest: {world._latest_binding_id}")
            try:
                print(f"Policies loaded: {len(POLICY_RT.loaded)} -> {', '.join(POLICY_RT.list_loaded_names()) or '(none)'}")
            except Exception:
                pass
            print_timekeeping_line(ctx)
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
            # Show last 5 bindings
            print("Selection:  Recent Bindings\n")
            print("Shows the 5 most recent bindings (bN). For each: tags and any engram slots attached.")
            print(" 'outdeg' is the number of outgoing edges, e.g., outdeg=2 means there are 2 outgoing edges")
            print(" 'preview' is a short sample of up to 3 these outgoing edges")
            print("     e.g., outdeg=2 preview=[initiate_stand:b2, then:b3]")
            print("     -this means 2 outgoing edges, 1 edge goes to b2 with action label 'initiate_stand', 1 edge ")
            print("          goes to b3 with action label 'then'")
            print("Tip: use 'Inspect binding details' for full meta/edges on a specific id.\n")

            print(recent_bindings_text(world, limit=5))
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
            print("Runs pytest (unit tests framework) and coverage, then a series of whole-flow custom tests.\n")

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
                ticks = meta.get("ticks")
                epoch = meta.get("epoch")
                bits: list[str] = []
                if policy:
                    bits.append(f"policy={policy}")
                if creator:
                    bits.append(f"created_by={creator}")
                if created_at:
                    bits.append(f"created_at={created_at}")
                if isinstance(ticks, int):
                    bits.append(f"ticks={ticks}")
                if isinstance(epoch, int):
                    bits.append(f"epoch={epoch}")
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
            print('''
Adds cue:<channel>:<token> (evidence, not a goal) at NOW and may nudge a policy.
  e.g., vision:silhouette:mom, sound:bleat:mom, scent:milk

This menu selection asks you for the channel and then the token, and writes the resulting cue,
  e.g., "cue:vision:silhouette:mom", to a new binding attached to NOW.
A controller step==Action Center step will run and if any policies are capable of triggering,
  the best one will be chosen and will execute.
In addition to triggering and executing a policy (if possible) the controller step will also:
  controller_steps ++,  temporal_drift ++  (no effect on autonomic ticks, cognitive cycles, age_days)

Consider the example where the Mountain Goat calf has just been born and stands up.
At this point these bindings, drives, and timekeeping exist:
b1: [anchor:NOW] -> b2: [pred:stand] -> b3: [pred:action:push_up] -> b4: [pred:action:extend_legs]
    -> b5: [pred:posture:standing, pred:posture:standing]
hunger=0.70, fatigue=0.20, warmth=0.60
controller_steps=1, cog_cycles=1, temporal_epochs=1, autonomic_ticks=0,  age_days: 0.0000, cos_to_last_boundary: 1.0000
These policies are eligible:  policy:stand_up, policy:seek_nipple, policy:rest, policy:suckle,
       policy:recover_miss, policy:recover_fall

Now add a sensory cue -- bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
 e.g., "cue:vision:silhouette:mom" and we see a message added to b6
 note: "attach=now" means add link from NOW->new node
Now a controller step will run -- fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
We see in the message displayed that policy seek_nipple executed and added 2 bindings.
"pre" explains why it triggered including the cue provided by new binding b6; "post" shows still triggerable after
  after policy executed; base suggestion, focus of attention and candidates for linking (see Instinct Step or README).

If we look at Snapshot we now see:
-Timekeeping (controller_steps ++,  temporal_drift ++ ):
  controller_steps=2, cog_cycles=1, temporal_epochs=1, autonomic_ticks=0, cos_to_last_boundary: 0.9857,  age_days: 0.0000
-New binding b6  [cue:vision:silhouette:mom]
-SkillStats -- new "policy:seek_nipple" statistics  ("policy:stand_up" ran before during the Instinct Step)
-New bindings created by "policy:seek_nipple" : b7: [pred:action:orient_to_mom],
    b8: [pred:seeking_mom, pred:seeking_mom]
(Note: If we run this Menu Step in a newborn calf then policy:stand_up will run since it is executionable with
 or without a cue and will have priority.)

            ''')

            ch = input("Channel (vision/scent/touch/sound): ").strip().lower()
            tok = input("Cue token (e.g., silhouette:mom): ").strip()
            if ch and tok:
                cue_token = f"{ch}:{tok}"
                bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
                print(f"Added sensory cue: cue:{cue_token} as {bid}")
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
                if fired != "no_match":
                    print(fired)
                try:
                    ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
                except Exception:
                    pass
                if getattr(ctx, "temporal", None):
                    ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
                    print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "12":
            # Instinct step
            print("Selection:  Instinct Step\n")
            # Quick explainer for the user before the step runs
            print('''
Purpose:
  • Run ONE controller step ("instinct step") which will:
   i.   Advance the soft temporal clock (temporal drift) (no autonomic tick or age_days change)
   ii.  Propose a write-base (base_suggestion): NEAREST_PRED(targets), then HERE, then NOW
   iii. Build a small FOA (focus-of-attention): union of small neighborhoods around NOW, LATEST, cues
   iv.  Evaluate loaded policies and execute the first that triggers (safety-first)
   v.   If the controller wrote new facts, then boundary jump (epoch++)

Let's consider an example. Consider the Mountain Goat simulation at its start, just after
    the goat calf is born.

There is by default a binding b1 with the tag "anchor:NOW" and the default bootup routines
    will create a binding b2 with the tag "pred:stand" and a link from b1 to b2 -- this all exists.
Ok... then we run an "instinct step".

i.  -there is a small drift of the context vector via ctx.temporal.step()
     (this may not matter if a policy writes a new event and there is a temporal jump later)

ii. -the Action Center has to decide where to link new bindings to -- base_suggestions provides suggestions
    -base_suggestion = choose_contextual_base(..., targets=['posture:standing', 'stand'])
    -it first looks for NEAREST_PRED(target) and success since b2 meets the target specified
    -thus, base_suggestion = binding b2 is recommended as the "write base", i.e. to link to
    -the suggestion is not used since that link already exists
    -base_suggestions can be used at different times to control write placement

iii. -FOA focus of attention -- a small set of nearby nodes around NOW/LATEST, cues (for lightweight planning)
     -NOW will also point to the new state binding created


iv. -policy:stand_up when considered can be triggered since age_days is <3.0 and stand near NOW is True
    -thus, policy:stand_up runs and as creates one mor more new nodes/edges (e.g., b5), and
            bindings b2 through b5 are linked

v.  -a new event occurred, thus there is a temporal jump, with epoch++

    ''')

            # Count one controller step
            try:
                ctx.controller_steps += 1
            except Exception:
                pass


            before_n = len(world._bindings)

            # [TEMPORAL] drift once per instinct step
            if ctx.temporal:
                ctx.temporal.step()

            # --- context (for teaching / debugging) ---
            base  = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
            foa   = compute_foa(world, ctx, max_hops=2)
            cands = candidate_anchors(world, ctx)

            # annotate anchors for readability: b1(NOW), ?(HERE), etc.
            now_id  = _anchor_id(world, "NOW")
            here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
            def _ann(bid: str) -> str:
                if bid == now_id:  return f"{bid}(NOW)"
                if here_id and bid == here_id: return f"{bid}(HERE)"
                return f"{bid}"

            print(f"[instinct] base_suggestion={base}, anchors={[ _ann(x) for x in cands ]}, foa_size={foa['size']}")
            print("Note: A base_suggestion is a proposal for where to attach writes this step. It is not a policy pick.")
            print("      Anchors give us a write base (where to attach new preds/edges). Where we attach the ")
            print("         new fact matters for searching paths and planning later.")
            print(f"[context] write-base: {_fmt_base(base)}")
            print(f"[context] anchors: {', '.join(_ann(x) for x in cands)}")
            print(f"[context] foa: size={foa['size']} (ids near NOW/LATEST + cues)")
            print("Note: write-base is where we’ll attach any new facts/edges this step (keeps the episode local and readable).")
            print("      anchors are candidate start points the system considers for local searches/attachment.")
            print("      foa is the current 'focus of attention' neighborhood size used for light-weight planning.")

            result = action_center_step(world, ctx, drives)
            after_n  = len(world._bindings)  #  measure write delta for this path

            # NOTE (Phase VIII terminology alignment):
            # - ctx.controller_steps counts every Action Center evaluation/execution loop.
            # - ctx.cog_cycles is reserved for CLOSED-LOOP env↔controller iterations (menu 35/37),
            #   i.e., EnvObservation → internal update → policy select/execute → action feedback to env.
            # Therefore: Instinct Step does not increment ctx.cog_cycles.

            # Explicit summary of what executed
            if isinstance(result, dict):
                policy  = result.get("policy")
                status  = result.get("status")
                reward  = result.get("reward")
                binding = result.get("binding")
                if policy and status:
                    rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                    print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                else:
                    print("Action Center:", result)
            else:
                print("Action Center:", result)

            # Move NOW anchor to the latest stable binding when we wrote new facts
            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n:
                new_bid = result.get("binding")
                if isinstance(new_bid, str):
                    try:
                        world.set_now(new_bid, tag=True, clean_previous=True)
                    except Exception:
                        # If anything goes wrong, ignore and keep the old NOW
                        pass

            # WHY: show a human explanation tied to the executed policy
            label = result.get("policy") if isinstance(result, dict) and "policy" in result else "(controller)"
            gate  = next((p for p in POLICY_RT.loaded if p.name == label), None)
            explainer: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
            if explainer is not None:
                try:
                    why = explainer(world, drives, ctx)
                    print(f"[why {label}] {why}")
                except Exception:
                    pass

            # delta and autosave
            if after_n == before_n:
                print("(no new bindings/edges created this step)")
            else:
                print(f"(graph updated: bindings {before_n} -> {after_n})")

            # [TEMPORAL] boundary when the controller actually wrote
            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n and ctx.temporal:
                new_v = ctx.temporal.boundary()
                ctx.tvec_last_boundary = list(new_v)
                # epoch++
                ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                try:
                    ctx.boundary_vhash64 = ctx.tvec64()
                except Exception:
                    ctx.boundary_vhash64 = None
                print("[temporal] a new event occurred, thus not just a drift in the context vector but ")
                print("     instead a jump to mark a temporal boundary (cos reset to ~1.000)")
                print(f"[temporal] boundary==event changes -> event/boundary/epoch={ctx.boundary_no}")
                print(f"     last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            # [TEMPORAL] optional τ-cut (e.g., τ=0.90)
            if ctx.temporal and ctx.tvec_last_boundary:
                v_now = ctx.temporal.vector()
                cos_now = sum(a*b for a,b in zip(v_now, ctx.tvec_last_boundary))
                if cos_now < 0.90:
                    new_v = ctx.temporal.boundary()
                    ctx.tvec_last_boundary = list(new_v)
                    # epoch++
                    ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                    try:
                        ctx.boundary_vhash64 = ctx.tvec64()
                    except Exception:
                        ctx.boundary_vhash64 = None
                    print(f"[temporal] boundary: cos_to_last_boundary {cos_now:.3f} < 0.90")
                    print(f"[temporal] boundary -> epoch (event changes) ={ctx.boundary_no} ")
                    print(f"     last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "13":
            # Skill Ledger
            print("Selection: Skill Ledger\n")
            print(skill_ledger_text("policy:stand_up"))
            print("Full ledger:  [src=cca8_controller.skill_readout()]")
            print(skill_readout())
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "14":
            # Autonomic tick
            print("Selection: Autonomic Tick")
            print('''

The autonomic tick is like a fixed-rate heartbeat in the background, particularly important for hardware and robotics.
(To learn more about the different time systems in the architecture see the Snapshot or Instinct Step menu selections.)

The result of this menu autonomic tick may cause (if conditions exist):
  i.   increment ticks, age_days, temporal drift, fatigue
  ii.  emit rising-edge interoceptive cues
  iii. recompute which policies are unlocked at this age/stage via dev_gate(ctx) before evaluating triggers
  iv.  try one controller step (Action Center): collect triggered policies, apply safety override if needed,
  tie-break by priority, and execute one policy (same engine as Instinct Step, just less verbose here)

Consider this example -- the Mountain Goat calf has just been born.
At this time by default (note -- this might change with future software updates):
- default -- binding b1 with the tag "anchor:NOW", b2 with tag "pred:stand", link b1--> b2
- controller_steps=0, cog_cycles=0, temporal_epochs=0, autonomic_ticks=0, age_days: 0.0000
- hunger=0.70, fatigue=0.20, warmth=0.60  [src=drives.hunger; drives.fatigue; drives.warmth]

Ok... then we run this menu "autonomic tick" (and look at Snapshot display also):
i.   ticks -> 1, age_day -> .01, cosine -> .98, fatigue -> .21

ii.  HUNGER_HIGH = 0.60 (Controller Module), thus hunger drive at 0.70 will trigger and thus
 be present now and thus written to WorldGraph as an interoceptive cue --
 b1: [anchor:NOW], b2: [pred:stand], b3 LATEST: [cue:drive:hunger_high], with b2-->b3 now also

iii. POLICY_RT.refresh_loaded(ctx) causes the Action Center to recompute and rebuild the set of
stage-appropriate policies (via dev_gate(ctx)) so only developmentally unlocked policies can trigger
-- these are loaded and are ready for step iv

iv.  try one controller step to react if anything is now actionable:
        fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx); if fired != "no_match": print(fired)
        (similar to Instinct Step menu but less verbose and instead more runtime version: refresh-->triggers-->pick--execute)
   -looks at all the loaded policies re trigger(world, drives, ctx)
      e.g., policy:stand_up wants nearby pred:stand, that you are not already standing, and young age
   -choose best candidate triggered policy and call policy's execute(...)
      e.g., policy:stand_up (added 3 bindings)
            b4: [pred:action:push_up], b5: [pred:action:extend_legs], b6: [pred:posture:standing, pred:posture:standing]
   -the extra lines below: base is the same as Instinct Step base suggestion, and again for humans not passed into action_center step;
   foa seeds foa with LATEST and NOW, adds cue nodes, union of neighborhoods with max_hops of 2; cands are candidate anchors which could be
   potential start anchors for planning/attachement

Fixed-rate heartbeat: fatigue↑, autonomic_ticks/age_days advance, temporal drift here (with optional boundary).
Often followed by a controller check to see if any policy should act, gather triggered policies, apply safety override,
pick by priority, and execute one policy (similar to menu Instinct Step but less verbose)

            ''')
            drives.fatigue = min(1.0, drives.fatigue + 0.01) #ceiling clamp, never exceed 1.0
            # advance developmental clock
            try:
                ctx.ticks = getattr(ctx, "ticks", 0) + 1
                ctx.age_days = getattr(ctx, "age_days", 0.0) + 0.01   # tune step as like
                if ctx.temporal:
                    ctx.temporal.step()
                world.set_stage_from_ctx(ctx)           # keep the stage in sync as age changes
                print(f"Autonomic: fatigue +0.01 | ticks={ctx.ticks} age_days={ctx.age_days:.2f}")

                # Interoception: write cues only on threshold rising-edges to avoid clutter
                started = _emit_interoceptive_cues(world, drives, ctx, attach="latest")
                if started:
                    print("[autonomic] interoceptive cues asserted: " + ", ".join(f"cue:{s}" for s in sorted(started)))

                # [TEMPORAL] optional τ-cut
                if ctx.temporal:
                    # Initialize boundary state once, on first tick with a temporal context
                    if getattr(ctx, "tvec_last_boundary", None) is None:
                        ctx.tvec_last_boundary = list(ctx.temporal.vector())
                        ctx.boundary_no = getattr(ctx, "boundary_no", 0)
                        try:
                            ctx.boundary_vhash64 = ctx.tvec64()
                        except Exception:
                            ctx.boundary_vhash64 = None

                    v_now = ctx.temporal.vector()
                    cos_now = sum(a * b for a, b in zip(v_now, ctx.tvec_last_boundary))

                    if cos_now < 0.90:
                        new_v = ctx.temporal.boundary()  # re-seed & renormalize
                        ctx.tvec_last_boundary = list(new_v)
                        ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                        try:
                            ctx.boundary_vhash64 = ctx.tvec64()
                        except Exception:
                            ctx.boundary_vhash64 = None
                        print(f"[temporal] τ-cut: cos_to_last_boundary={cos_now:.3f} < 0.90 → epoch={ctx.boundary_no}, last_boundary_vhash64={ctx.boundary_vhash64}")
                        print("[temporal] note: writes after this boundary belong to the NEW epoch.")

                    print_timekeeping_line(ctx)
            except Exception as e:
                print(f"Autonomic: fatigue +0.01 (exception: {type(e).__name__}: {e})")

            # Refresh availability and consider firing regardless
            POLICY_RT.refresh_loaded(ctx)
            #rebuilds the set of eligible policies by applying each gate's dev_gate(ctx) to the current context
            #  e.g., age-->stage, etc  -- only those that pass are "loaded"=="eligible" for triggering
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            # Controller step bookkeeping for this path:
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            #if getattr(ctx, "temporal", None):  #already did a temporal drift above, so don't run here (same code as pasted in for few blocks of code)
            #   ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
            # Note: we do NOT increment cog_cycles here by design.
            # Autonomic Tick is physiology + one controller step; cycles are counted only in Instinct Step (see comment there).


            #runs the Action Center once:
            # -collects policies whose trigger(world, drives, ctx) is True, i.e., eligible policy that has triggered
            # -safety override -- e.g., if posture:fallen is near NOW then restricts policy to only policy:recover_fall, policy:stand_up
            # -tie-break/priority -- computes a simple drive-deficit score (e.g., hunger for policy:seek_nipple, etc) and picks the max policy
            # -executes the chosen policy via action_center_step(...) and returns a human-readable summary
            if fired != "no_match":
                print(fired)
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
        elif choice == "17":
            # Display snapshot
            print("Selection:  Snapshot (WorldGraph + CTX + Policies)\n")
            print("A full, human-readable dump. The LEGEND explains some of the terms.")
            print("Note: Various tutorials and the README/Compendium file can help you understand the terms and functionality better.")
            print("Note: At the end of the snapshot you have the option to generate an interactive HTML graph of WorldGraph.\n")

            print(snapshot_text(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT))

            # Optional: generate an interactive Pyvis HTML view
            try:
                yn = input("Generate interactive graph (Pyvis HTML)? [y/N]: ").strip().lower()
            except Exception:
                yn = "n"
            if yn in ("y", "yes"):
                default_path = "world_graph.html"
                try:
                    path = input(f"Save HTML to (default: {default_path}): ").strip() or default_path
                except Exception:
                    path = default_path
                try:
                    out = world.to_pyvis_html(path_html=path, label_mode="id+first_pred", show_edge_labels=True, physics=True)
                    print(f"Interactive graph written to: {out}")
                    try:
                        open_now = input("Open in your default browser now? [y/N]: ").strip().lower()
                    except Exception:
                        open_now = "n"
                    if open_now in ("y", "yes"):
                        try:
                            import webbrowser # use the top-level 'sys','os'
                            if sys.platform.startswith("win"):
                                os.startfile(out)  # type: ignore[attr-defined]
                            elif sys.platform == "darwin":
                                os.system(f'open "{out}"')
                            else:
                                webbrowser.open(f"file://{out}")
                            print("(opened in your browser)")
                        except Exception as e:
                            print(f"[warn] Could not open automatically: {e}")
                except Exception as e:
                    print(f"[warn] Could not generate Pyvis HTML: {e}")
                    print("       Tip: install with  pip install pyvis")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "18":
            # Simulate a fall event and try a recovery attempt immediately
            print("Selection: Simulate a fall event\n")
            print('''
Summary: -Creates posture:fallen and relabels the linking edge to 'fall', then attempts recovery.
         -Use this to demo safety gates (recover_fall / stand_up).

--background primer and terminology--
Controller steps  — one Action Center decision/execution loop (aka “instinct step”).
 -a loop in the runner that evaluates policies once and may write to the WorldGraph.
 -if that step wrote new facts, we mark a  temporal boundary (epoch++) .
 -With regards to its effects on timekeeping,  when a Controller Step occurs :
     i)  controller_steps : ++ once per controller step
     ii)  temporal drift : ++ (one soft-clock drift) per controller step
     iii)  autonomic ticks : no direct change (may increase but independent heartbeat-like clock)
     iv)  developmental age : no direct change (may increase but must be calculated elsewhere)
     v)   cognitive cycles : ++ if there is a write to the graph (nb. need to change in the future)
           Note: we do NOT increment cog_cycles here by design.
           This menu is 'event injector + one controller step'; cognitive cycles are counted only in Instinct Step.


 -With regards to terminology and operations that affect controller steps:
  “Action Center”  = the engine (`PolicyRuntime`).
  “Controller step”  = one invocation of that engine.
  “Instinct step”  = diagnostics +  one controller step .
  “Autonomic tick”  = physiology +  one controller step .
  ----

Consider the example where the Mountain Goat calf has just been born.
Thus, by default there will be b1 NOW --> b2 pred:stand
Note: "pred:stand" is not a state but an intent (if standing we would say,
   e.g., "pred:posture:standing" or legacy alias pred:posture:standing")
As shown below, this menu item creates a new binding b3 with "posture:fallen"
(it does it via world.add_predicate with attach="latest", i.e., link to b2).
The previous LATEST → fallen edge is relabeled to 'fall' for semantic readability.
It then calls a controller step. As shown above, this will cause the Action Center to
  evaluate policies via PolicyRuntime.consider_and_maybe_fire(...) --> since there is
  "posture:fallen" the safety override restricts candidate policies to {recover_fall, stand_up}
  and given that equally priority/deficit, stand_up is earlier and will be triggered.
The base suggestion, focus of attention, and candidates for binding are discussed in Instinct Step
  as well as in the README.md. They are largely diagnostic. Similarly the 'post' message simply re-evalutes
  the gate/trigger after execution; it's normal that it can still read True.
However the line "policy:stand_up (added 3 bindings)" tells us that the policy executed and added
3 bindings.
If we go to Snapshot we see:
    b1: [anchor:NOW]  [src=world._bindings['b1'].tags]
    b2: [pred:stand]  [src=world._bindings['b2'].tags]
    b3: [pred:posture:fallen]  [src=world._bindings['b3'].tags]
    b4: [pred:action:push_up]  [src=world._bindings['b4'].tags]
    b5: [pred:action:extend_legs]  [src=world._bindings['b5'].tags]
    b6: [pred:posture:standing, pred:posture:standing]  [src=world._bindings['b6'].tags]
Bindings b4, b5 and b6 were added and various actions occurred (or is being executed now). We see
   that at b6 there is the predicate "pred:posture:standing".
Also, of interest with regard to timekeeping:
   controller_steps=1, cog_cycles=0, temporal_epochs=0, autonomic_ticks=0, vhash64()==epoch_vhash64, age_days =0.000

            ''')

            prev_latest = world._latest_binding_id
            # Create a 'fallen' state as a new binding attached to latest
            fallen_bid = world.add_predicate(
                "posture:fallen",
                attach="latest",
                meta={"event": "fall", "added_by": "user"}
            )
            # Relabel the auto 'then' edge from the previous latest → fallen as 'fall'
            try:
                if prev_latest:
                    # Remove any auto edge regardless of label, then add a semantic one
                    try:
                        world_delete_edge(world, prev_latest, fallen_bid, None)
                    except NameError:
                        pass
                    world.add_edge(prev_latest, fallen_bid, "fall")
            except Exception as e:
                print(f"[fall] relabel note: {e}")

            print(f"Simulated fall as {fallen_bid}")

            # Refresh and consider policies now; recovery gate will nudge Action Center
            POLICY_RT.refresh_loaded(ctx)
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(fired)
            # Controller step bookkeeping for this path:
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            if getattr(ctx, "temporal", None):
                ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
                print_timekeeping_line(ctx)

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        #elif "19"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        #elif "20"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        #elif "21"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        elif choice == "22":
            # Export and display interactive graph (Pyvis HTML) with options
            print("Selection: Export and display interactive graph (Pyvis HTML) with options")
            print('''

Export and display graph of nodes and links with more options (Pyvis HTML)
Note: the graph opened in your web browser is interactive -- even if you don't show
       edge labels to save space, put the mouse on them and the labels appear
Note: the graph HTML file will be saved in your current directory\n
— Edge labels: draw text on the links, e.g.,'then' or 'initiate_stand'
    On = label printed on the arrow (and still a tooltip). Off = only tooltip.
    -->Recommend Y on small graphs, n on larger ones to reduce clutter
— Node label mode:
    'id'           → show binding ids only (e.g., b5)
    'first_pred'   → show first pred:* token (e.g., stand, nurse)
    'id+first_pred'→ show both (two-line label)
     -->Recommend id+first_pred if enough space
— Physics: enable force-directed layout; turn off for very large graphs.
      (We model the graph as a physical system and then try to achieve a minimal
       energy state by simulating the movement of the nodes into this minimal state. The result is a
       graph which many people find easier to read. This option uses Barnes-Hut physics which is an
       algorithm originally for the N-body problem in astrophysics and which speeds up the layout calculations.
       Nonetheless, for very large graphs may not be computationally feasible.
      -->Recommend physics ON unless issues with very large graphs

            ''')
            # Collect options
            try:
                label_mode = input("Node label mode [id / first_pred / id+first_pred] (default: id+first_pred): ").strip().lower()
            except Exception:
                label_mode = ""
            if label_mode not in {"id", "first_pred", "id+first_pred"}:
                label_mode = "id+first_pred"

            try:
                el = input("Show edge labels on links? [Y/n]: ").strip().lower()
            except Exception:
                el = ""
            show_edge_labels = not (el in {"n", "no", "0"})

            try:
                ph = input("Enable physics (force-directed layout)? [Y/n]: ").strip().lower()
            except Exception:
                ph = ""
            physics = not (ph in {"n", "no", "0"})

            default_path = "world_graph.html"
            try:
                path = input(f"Save HTML to (default: {default_path}): ").strip() or default_path
            except Exception:
                path = default_path

            try:
                out = world.to_pyvis_html(
                    path_html=path,
                    label_mode=label_mode,
                    show_edge_labels=show_edge_labels,
                    physics=physics
                )
                print(f"Interactive graph written to: {out}")
                try:
                    open_now = input("Open in your default browser now? [y/N]: ").strip().lower()
                except Exception:
                    open_now = "n"
                if open_now in ("y", "yes"):
                    try:
                        import webbrowser # use the top-level 'sys', 'os'
                        if sys.platform.startswith("win"):
                            os.startfile(out)  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            os.system(f'open "{out}"')
                        else:
                            webbrowser.open(f"file://{out}")
                        print("(opened in your browser)")
                    except Exception as e:
                        print(f"[warn] Could not open automatically: {e}")
            except Exception as e:
                print(f"[warn] Could not generate Pyvis HTML: {e}")
                print("       Tip: install with  pip install pyvis")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "23":
            # Understanding bindings/edges/predicates/cues/anchors/policies (terminal help)
            print("Selection: Understanding bindings, edges, predicates, cues, anchors, policies")
            print_tagging_and_policies_help(POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "24":
            # Capture scene → emit cue/predicate + tiny engram (signal bridge demo)
            print("Selection: Capture scene\n")
            print('''
Capture scene -- creates a binding, stores an engram of some scene in one of the columns,
  and then stores a pointer to that engram in the binding.

-the user is prompted to enter channel, token, family, attach (NOW->new, advance LATEST; oldLATEST -> new, advance LATEST;
   "none" -- create node unlinked, can manually add edges later) and a tiny scene vector(e.g., ".5,.5,.5")
-there is a temporal boundary jump so that the new engram starts a fresh epoch
   e.g., [temporal] boundary (pre-capture) → epoch=1 last_boundary_vhash64=23636ff46c39b1c5 (cos≈1.000)
-time attributes are passed in creating the engram
-then -- bid, eid = world.capture_scene(channel, token, vec, attach=attach, family=family, attrs=attrs)
-this creates a new binding --  b3 with tag cue:vision:silhouette:mom and attached engram id=80ac0bc7b6624b538db354c9d5aa4a17
-as noted it creates a tiny engram in one of the Columns, and stamps it with the time from attrs  e.g., time on engram: ticks....
-it then writes a pointer on the binding so that the binding points to the engram
     -e.g.,  b3.engrams["column01"] = 80ac0....
     -sets bN.engrams["column01"] = <eid>
-it then returns the binding id bid and the engram id eid
-then there is a controller==Action Center step -- in the example with a newborn calf the gate and trigger conditions for
    policy:stand_up are met, and this policy is executed

  - When attach='latest' (default in base-aware mode), this menu now consults a write-base suggestion:
      base = NEAREST_PRED(pred=posture:standing/stand) near NOW → binding bN
    and uses base-aware attach semantics so the captured scene anchors under a meaningful posture node
    instead of blindly hanging off whatever LATEST happens to be.

  - Brief tutorial on how to think of the terms above and below at this point in the software development:
    NOW_ORIGIN anchor -- episode root binding, i.e., a stable 'start' marker, but not used much otherwise at this time
    HERE anchor -- stub right now, in future use for 'where the body is in space' (vs NOW 'where we are in time')
    LATEST -- a pointer, really _latest_binding_id, i.e., the last binding we created
    NOW anchor -- after execution of a policy NOW is usually moved to latest binding of event, but tiny events and cue might not move NOW
               -- used as default start for planning/search, time anchor, center of focus of attention FOA region
    attach = 'latest' -- flag indicating that new binding for predicate/engram/etc should be linked to the latest binding
    attach = 'now' -- flag indicating the new binding for predicate/engram/etc should be linked to the NOW anchor binding
    base -- 'where should this new binding be linked in the graph so that the episode stays tidy and meaningful?'
    base_suggestion -- system saying 'given the current situation (NOW + FOA) the best node to attach new nodes to is this binding'
    choose_contextual_base(...) -- computes base_suggestion starting from NOW, within small radius of nodes looks for binding with
        specified target predicate, if found returns, e.g., {'base':'NEAREST_PRED', 'pred':'posture:standing', 'bid':'b5'},
        but if not found returns, e.g., {'base':'HERE', 'bid':'?'}, i.e., strategy of HERE rather than nearest predicate and if can't
        use HERE then will use NOW/LATEST
    base-aware logic  -- if attach='latest' and last node was a cue or some dev_gate, etc, the new predicate/scene
        binding would normally link to those, even though they really belong under another node, then attach='effective_attach'=='none',
        and have NEAREST_PRED base, then _attach_via_base(...) links under NEAREST_PRED base



            ''')

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

            # Treat capture as a new event (pre-capture boundary) so time attrs reflect a new epoch
            if ctx.temporal:
                new_v = ctx.temporal.boundary()
                ctx.tvec_last_boundary = list(new_v)
                ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                try:
                    ctx.boundary_vhash64 = ctx.tvec64()
                except Exception:
                    ctx.boundary_vhash64 = None
                print(f"[temporal] boundary (pre-capture) → epoch={ctx.boundary_no} last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            # Pass time attrs when creating an engram
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
                        print(f"[bridge] time on engram: ticks={attrs.get('ticks')} "
                              f"tvec64={attrs.get('tvec64')} epoch={attrs.get('epoch')} "
                              f"epoch_vhash64={attrs.get('epoch_vhash64')}")
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

                # Optional: one controller step (Action Center) after capture
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
            # Temporal probe (harmonized with Snapshot naming)
            print("Selection:  Temporal Probe\n")
            print("Shows the temporal soft clock using the same names as Snapshot,")
            print("with source attributes for each value.\n")

            # Epoch + hashes (same names as Snapshot)
            epoch = getattr(ctx, "boundary_no", 0)
            vhash_now = ctx.tvec64() if hasattr(ctx, "tvec64") else None
            epoch_vh  = getattr(ctx, "boundary_vhash64", None)

            print(f"  vhash64(now): {vhash_now if vhash_now else '(n/a)'}  [src=ctx.tvec64()]")
            print(f"  vhash64: {vhash_now if vhash_now else '(n/a)'}  [alias of vhash64(now)]")
            print(f"  epoch: {epoch}  [src=ctx.boundary_no]")
            print(f"  epoch_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [src=ctx.boundary_vhash64]")
            print(f"  last_boundary_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [alias of epoch_vhash64]")

            # Cosine to last boundary (same name as Snapshot)
            cos = None
            try:
                cos = ctx.cos_to_last_boundary()
            except Exception:
                cos = None
            if isinstance(cos, float):
                print(f"  cos_to_last_boundary: {cos:.4f}  [src=ctx.cos_to_last_boundary()]")
            else:
                print("  cos_to_last_boundary: (n/a)  [src=ctx.cos_to_last_boundary()]")

            # Hamming distance between hashes (0..64), optional
            if vhash_now and epoch_vh:
                try:
                    h = _hamming_hex64(vhash_now, epoch_vh)
                    if h >= 0:
                        print(f"  hamming(vhash64,epoch_vhash64): {h} bits (0..64)  [src=_hamming_hex64]")
                except Exception:
                    pass

            # Temporal parameters (same keys as Snapshot)
            tv = getattr(ctx, "temporal", None)
            if tv:
                dim   = getattr(tv, "dim", 0)
                sigma = getattr(tv, "sigma", 0.0)
                jump  = getattr(tv, "jump", 0.0)
                print(f"  dim={dim}  [src=ctx.temporal.dim]")
                print(f"  sigma={sigma:.4f}  [src=ctx.temporal.sigma]")
                print(f"  jump={jump:.4f}  [src=ctx.temporal.jump]")

            # Status derived from cosine, same thresholds as elsewhere
            if isinstance(cos, float):
                if cos >= 0.99:
                    status = "ON-EVENT BOUNDARY"
                elif cos < 0.90:
                    status = "EVENT BOUNDARY-SOON"
                else:
                    status = "DRIFTING slowly forward in time"
                print(f"  status={status}  [derived from cos_to_last_boundary]")

            print_timekeeping_line(ctx)

            # Explanation (matches Snapshot nomenclature)
            print("\nExplanation:")
            print("  The temporal soft clock keeps two fingerprints of a unit vector:")
            print("    • vhash64(now) — current context vector fingerprint  [src=ctx.tvec64()]")
            print("    • epoch_vhash64 — fingerprint captured at the last boundary  [src=ctx.boundary_vhash64]")
            print("  Between boundaries the vector DRIFTS a little each drift step (sigma). When a new")
            print("  event occurs, boundary() applies a larger JUMP (jump), we record epoch_vhash64")
            print("  to the new value, and vhash64(now) equals it immediately after.")
            print("  Elapsed-within-epoch can be estimated by comparing now vs boundary:")
            print("    • cos_to_last_boundary ≈ 1.000 at a boundary and decreases with drift;")
            print("    • Hamming(vhash64(now), epoch_vhash64) counts bit flips (0..64).")

            # Small legend (matches Snapshot legend terms)
            print("\nLegend:")
            print("  epoch = event boundary count; increments when boundary() is taken")
            print("  vhash64(now) = fingerprint of current temporal vector")
            print("  epoch_vhash64 = fingerprint at last boundary (alias: last_boundary_vhash64)")

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
                    ticks = attrs.get("ticks")
                    tvec  = attrs.get("tvec64")
                    epoch = attrs.get("epoch")
                    evh   = attrs.get("epoch_vhash64")
                    print(f"  time attrs: ticks={ticks} tvec64={tvec} epoch={epoch} epoch_vhash64={evh}")

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
            # List all engrams by scanning bindings; dedupe by id
            print("Selection: List all engrams")
            print('''
This selection will list all engrams stored by scanning the bindings.
Any duplicated engram ID's in different bindings will not be shown twice.
EID -- the engram id (32 hex characters)
src -- the source binding==node where the pointer is stored
       note: this is the first binding found that points to that EID but de-duplicated by EID
ticks, epoch -- when the engram was created, actually the value of these counters when it was captured
tvec64 -- human readable 64-bit fingerprint of the temporal vector ctx.tvec64 when the engram was captured
payload --  info from the payload's metadata TensorPayload holds data:list[float] and on serialization write contiguous float32's
  -shape=(3,) -- 1-D vector of 3 elements
  -kind=scene -- kind of field, not numeric dtype; "scene" kind comes from the payload's metadata
  -fmt=tensor/list-f32  -- TensorPayload holds data:list[float] and on serialization writes contiguous float32's
name -- engram name  e.g., scene:vision:silhouette:mom

Note: the Column record stores {"id", "name", "payload", "meta"}; receives the time attrs + "created_at"
Note: the binding keeps the pointer engrams["column01"] = {"id":EID, "act":1.0}

            ''')

            seen: set[str] = set() #useful to annotate containers created empty so mypy finds unambiguous
            any_found = False  #type is obvious from the literal, so don't type in cases like this
            printed_header = False
            for bid in _sorted_bids(world):  #[b1, b2,...]
                eids = _engrams_on_binding(world, bid)  #[] if no engram, or if engram, e.g., ['15da3c55f02c4f7db6cf657367fc8e49']
                for eid in eids:
                    if eid in seen:
                        continue
                    seen.add(eid)
                    any_found = True
                    # Best-effort fetch of Column record for summary
                    rec = None
                    try:
                        rec = world.get_engram(engram_id=eid)
                        #e.g.,  {'id': '15da3c55f02c4f7db6cf657367fc8e49', 'name': 'scene:vision:silhouette:mom',
                        #  'payload': TensorPayload(data=[0.0, 0.0, 0.0], shape=(3,), kind='scene', fmt='tensor/list-f32'),
                        #  'meta': {'name': 'scene:vision:silhouette:mom', 'links': ['cue:vision:silhouette:mom'],
                        #  'attrs': {'ticks': 0, 'tvec64': '7ffe462732f60bd9', 'epoch': 1, epoch_vhash64': '7ffe462732f60bd9', 'column': 'column01'},
                        #  'created_at': '2025-11-16T10:46:50'}, 'v': '1'}
                    except Exception:
                        rec = None
                    ticks = epoch = tvec = evh = shape = dtype = None
                    if isinstance(rec, dict):
                        meta = rec.get("meta", {})
                        attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                        if isinstance(attrs, dict):
                            ticks = attrs.get("ticks")
                            tvec  = attrs.get("tvec64")
                            epoch = attrs.get("epoch")
                            evh   = attrs.get("epoch_vhash64")

                        payload = rec.get("payload")
                        if isinstance(payload, dict):
                            shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                            dtype = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                        else:
                            shape = rec.get("shape"); dtype = rec.get("kind") or rec.get("type")

                        payload = rec.get("payload")
                        if isinstance(payload, dict):
                            shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                            dtype = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                        elif hasattr(payload, "meta"):  # e.g., TensorPayload object
                            try:
                                pmeta = payload.meta()  # {'kind','fmt','shape','len'}
                                shape = pmeta.get("shape")
                                dtype = pmeta.get("kind")
                            except Exception:
                                shape = dtype = None
                        else:
                            shape = rec.get("shape")
                            dtype = rec.get("kind") or rec.get("type")
                    name = (rec.get("name") or "") if isinstance(rec, dict) else ""

                    if not printed_header:
                        print("Engrams in the system:\n")
                        printed_header = True

                    fmt = (payload.meta().get("fmt") if hasattr(payload, "meta")
                           else (payload.get("fmt") if isinstance(payload, dict) else None))
                    print(f"EID={eid}  src={bid}  ticks={ticks} epoch={epoch} tvec64={tvec} "
                          f"payload(shape={shape}, kind={dtype}{', fmt='+fmt if fmt else ''})"
                          f"{'  name='+name if name else ''}")
            if not any_found:
                print("no engrams were found")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection  Code Block------------------------
        elif choice == "29":
            # Search engrams
            print("Selection:  Search Engrams\n")
            print("Search referenced engrams by name substring (case-insensitive) and/or epoch.\n"
                  "Optional filters: channel substring (e.g., 'vision'), payload kind (e.g., 'scene'), "
                  "and EID prefix.\n"
                  "Note: 'Name' is not bid but the given by the tag, e.g.,name=scene:vision:silhouette:mom ")

            # --- inputs (all optional except 'q' which can be blank) ---
            try:
                q = input("Name contains (substring, blank=any): ").strip()
            except Exception:
                q = ""
            try:
                e_in = input("Epoch equals (blank=any): ").strip()
                epoch = int(e_in) if e_in else None
            except Exception:
                epoch = None
            try:
                chan = input("Channel contains (e.g., vision, blank=any): ").strip().lower()
            except Exception:
                chan = ""
            try:
                kid = input("Payload kind equals (e.g., scene, blank=any): ").strip().lower()
            except Exception:
                kid = ""
            try:
                eid_prefix = input("EID starts with (hex prefix, blank=any): ").strip().lower()
            except Exception:
                eid_prefix = ""

            # --- scan pointers on bindings, de-dupe by EID ---
            seen = set()
            found: list[tuple[str, str, str, dict]] = []  # (eid, src_bid, name, attrs)

            for bid, b in world._bindings.items():
                eng = getattr(b, "engrams", None)
                if not isinstance(eng, dict):
                    continue
                for _slot, val in eng.items():
                    if not (isinstance(val, dict) and "id" in val):
                        continue
                    eid = val["id"]
                    if eid in seen:
                        continue
                    seen.add(eid)

                    # fetch column record
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue

                    name = rec.get("name") or ""
                    meta = rec.get("meta", {})
                    attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}

                    # ---- filters ----
                    if eid_prefix and not eid.lower().startswith(eid_prefix):
                        continue
                    if q and q.lower() not in name.lower():
                        continue
                    if chan and chan not in name.lower():
                        continue
                    if epoch is not None:
                        ep = attrs.get("epoch")
                        if not (isinstance(ep, int) and ep == epoch):
                            continue
                    if kid:
                        # 'kind' comes from payload metadata
                        pl = rec.get("payload")
                        kind = None
                        if hasattr(pl, "meta"):
                            try:
                                kind = pl.meta().get("kind")
                            except Exception:
                                kind = None
                        elif isinstance(pl, dict):
                            kind = pl.get("kind") or (pl.get("meta", {}) or {}).get("kind")
                        if (kind or "").lower() != kid:
                            continue

                    found.append((eid, bid, name, attrs))

            # --- print results (epoch desc, then name, then eid) ---
            if not found:
                print("\n(no matches)")
            else:
                print("\nThe following matches were found:\n")
                def _sort_key(t):
                    eid, _bid, name, attrs = t
                    ep = attrs.get("epoch")
                    # sort by epoch desc (ints first), then name, then eid
                    ep_key = -ep if isinstance(ep, int) else float("inf")
                    return (ep_key, name or "", eid)

                for eid, bid, name, attrs in sorted(found, key=_sort_key):
                    print(f"EID={eid}  src={bid}  name={name}  epoch={attrs.get('epoch')}  tvec64={attrs.get('tvec64')}")

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
            print("""What is a cognitive cycle?
--------------------------

A cognitive cycle is one complete perceive-update-decide-act loop between an agent
(for example, a goat, chimpanzee, human, or robot) and its environment.

The agent's brain or control system is simulated using the CCA8 cognitive architecture.
CCA8 receives evidence from the environment, updates its internal state, selects an action,
and then begins the cycle again.

At a high level, this cycle will:

  1) --> Let the simulated or real environment report what the agent is sensing now -->
  2) Convert that evidence into current internal maps and compare it with what was expected -->
  3) Record any mismatch as a prediction-error or residual signal -->
  4) Let the Action Center select a behavior, called a policy, for the next cycle --> REPEAT

  Note: In the CCA literature, "Navigation Module" means "Action Center," and
  "Primitive" means "Policy."

Predictions help CCA8 interpret noisy or incomplete sensory evidence. When the
incoming pattern closely matches a known NavMap, CCA8 may treat it as the same
map with updated details. However, strong, persistent, or safety-critical
differences must not be forced to conform to the prediction; they may trigger
an alternative or new NavMap interpretation.

The environment is stepped using the action selected during the previous cycle. The new
observation is then processed, and CCA8 selects the action to be used during the next cycle.
""")
            input("Press Enter to continue reading...\n\n")

            print("""To make it easier to read the information about the cog cycle, note this
key being used:
        [teach]       explanation for the human reader
        [env...]      information from the simulated (or real) environment
        [navmap...]   map-processing diagnostics
        [controller]  policy-selection or action information
        [cycle]       compact end-of-cycle summary

In the CCA literature, 'controller'===Navigation Module -- this is where the mechanics of
the 'policy'==='primitive' acts on the Working Navigation Map.

The term 'cycle' refers to a 'cognitive cycle' of information going through the CCA8-generated
architecture, i.e., sensory, processing and output, and then another cognitive cycle starts.

***Tip: If this is the first time you are seeing this architecture, you should make some pen and
paper notes to become familiar with and consolidate the basic terms and functioning of the
architecture. Consider reading some of the literature on the subject as well.***

During the first cycle, there may be no previous action or prediction, so some diagnostic
fields may say "missing" or "incomplete." This is normal.\n""")
            input("Press Enter to continue reading...\n\n")

            print("""Optional discussion about matching navigation maps:
-If you have read some of the literature on the Cognitive Causal Architecture then you are aware it
uses NavMaps (i.e., map-like basic data structures) in its core processing. Sensory information (as
well as intermediate results) are mapped onto NavMaps and a new sensory NavMap is matched against
stored NavMaps. There are three types of matches that occur:
Very close match
    → interpret the observation using an existing NavMap
    e.g., sensory image of tree will be matched to other pre-existing trees usually; the small differences among
    the leaves and branches will be ignored (although if many such sensory inputs there is finer assortment of
    NavMaps stored on the subject).
Clearly poor match
    → treat it as novel and form a new NavMap candidate
    e.g., have never seen an automobile before -- a new NavMap will be created; it will not be forced matched as
    a type of tree, for example.
Middle region
    → preserve uncertainty and gather more evidence
    e.g., sensory image of a large bushy shrub -- do we just perceive it as a tree perhaps under different lighting
    or different angles, or is it a totally different match and we should create a new NavMap for it?

There is ongoing development of the CCA8's NavMap learning and context-management system. With regard to matching:
    -close and unambiguous  → reuse/update an existing NavMap
    -close but ambiguous    → preserve several hypotheses or inspect further
    -poor match             → create a new NavMap candidate
    -safety-critical contradiction → immediately reconsider the current context

Optional discussion: Current threshold cutoff values:
    -exact content signature
        → reuse_exact
    -best score >= 0.85
    -and best - second >= 0.05
        → commit to the best existing interpretation
    -best score >= 0.85
    -but best - second < 0.05
        → ambiguous
    -best score < 0.85
        → unknown / novel

***The output below may scroll down quickly. After computations are completed and terminal output has stopped,
   SCROLL upward to be able to read all the text.***\n""")
            input("Press Enter to begin the cognitive cycle...")
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
  1) Advance controller_steps and the temporal soft clock once,
  2) STEP the newborn-goat environment using the last policy action (if any),
  3) Inject the resulting EnvObservation into the WorldGraph as pred:/cue: facts,
  4) Run ONE controller step (Action Center) and remember the last fired policy.

Menu 35 runs one cycle in verbose teaching mode.
Menu 37 runs the compact multi-cycle timeline.
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
            print("(terminology: hud==heads-up-display; n==number times policy executed; rate==% times we counted policy as successful;")
            print("  last==reward value that policy received the last time it executed; q==learned value estimate;")
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

This baseline demo disables observation masking and route-loss stress. Menu 49 remains the
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
            # Configure episode starting state (drives + age_days)
            print("Selection: Configure episode starting state (drives + age_days)\n")
            print("(For development work, it is useful to adjust starting state attributes and see the")
            print("  effect on program behavior.)\n")

            # Read current values defensively
            try:
                current_hunger = float(getattr(drives, "hunger", 0.0))
            except Exception:
                current_hunger = 0.0
            try:
                current_fatigue = float(getattr(drives, "fatigue", 0.0))
            except Exception:
                current_fatigue = 0.0
            try:
                current_warmth = float(getattr(drives, "warmth", 0.0))
            except Exception:
                current_warmth = 0.0
            try:
                current_age = float(getattr(ctx, "age_days", 0.0) or 0.0)
            except Exception:
                current_age = 0.0

            # Partial observability knob (obs masking)
            try:
                cur_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
            except Exception:
                cur_p = 0.0
            try:
                cur_seed = getattr(ctx, "obs_mask_seed", None)
            except Exception:
                cur_seed = None
            cur_mode = "seeded" if cur_seed is not None else "global"
            try:
                cur_verbose = bool(getattr(ctx, "obs_mask_verbose", True))
            except Exception:
                cur_verbose = True

            print()
            print(
                "Partial observability (obs masking): "
                f"obs_mask_prob={cur_p:.2f} mode={cur_mode} obs_mask_seed={cur_seed!r} verbose={cur_verbose}"
            )
            print("  obs_mask_prob:")
            print("    0.00 = fully observed (default)")
            print("    0.10–0.30 = mild partial observability (good starting range)")
            print("  obs_mask_seed:")
            print("    None = stochastic masking (uses global RNG)")
            print("    int  = reproducible masking (seeded per env step; independent of RL randomness)")
            print("  Protected (never dropped): posture:* , hazard:cliff:* , proximity:shelter:*")

            s = input("Set obs_mask_prob in [0..1] (blank=keep current): ").strip()
            if s:
                try:
                    v = float(s)
                    v = max(0.0, min(1.0, v))
                    ctx.obs_mask_prob = v
                    try:
                        ctx.obs_mask_last_cfg_sig = None
                    except Exception:
                        pass
                    print(f"(updated) obs_mask_prob={ctx.obs_mask_prob:.2f}")
                except ValueError:
                    print("(warn) invalid obs_mask_prob; keeping current value.")

            s = input("Set obs_mask_seed (blank=keep; 'none'/'off'=disable; int=enable): ").strip().lower()
            if s:
                if s in ("none", "off", "disable", "disabled"):
                    ctx.obs_mask_seed = None
                    try:
                        ctx.obs_mask_last_cfg_sig = None
                    except Exception:
                        pass
                    print("(updated) obs_mask_seed=None (stochastic/global RNG)")
                else:
                    try:
                        ctx.obs_mask_seed = int(float(s))
                        try:
                            ctx.obs_mask_last_cfg_sig = None
                        except Exception:
                            pass
                        print(f"(updated) obs_mask_seed={ctx.obs_mask_seed} (reproducible)")
                    except ValueError:
                        print("(warn) invalid obs_mask_seed; keeping current value.")

            rawv = input("obs-mask verbose logs? [Enter=toggle | on | off]: ").strip().lower()
            if rawv in ("on", "true", "1", "yes", "y"):
                ctx.obs_mask_verbose = True
            elif rawv in ("off", "false", "0", "no", "n"):
                ctx.obs_mask_verbose = False
            elif rawv == "":
                ctx.obs_mask_verbose = not bool(getattr(ctx, "obs_mask_verbose", True))
            print(f"(now) obs_mask_verbose={bool(getattr(ctx, 'obs_mask_verbose', True))}")

            # WM<->Column auto-retrieve enable + mode toggle
            # WorkingMap↔Column auto-retrieve controls (keyframes)
            # - merge   = conservative prior (fills missing slot families only; does NOT inject cue:* into belief-now)
            # - replace = strong prior (clears + rebuilds MapSurface from the snapshot; useful for debug)
            try:
                ar_enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False))
            except Exception:
                ar_enabled = False
            try:
                ar_mode = str(getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
            except Exception:
                ar_mode = "merge"
            if ar_mode == "r":
                ar_mode = "replace"
            if ar_mode not in ("merge", "replace"):
                ar_mode = "merge"
            print()
            print(f"WM<->Column auto-retrieve (keyframes): enabled={ar_enabled} mode={ar_mode}")
            print("  merge   = conservative prior fill (no overwrite; no cue leakage)")
            print("  replace = rebuild MapSurface from engram snapshot (debug/strong prior)")

            s = input("Set auto-retrieve enabled? [Enter=keep | t=toggle | on | off]: ").strip().lower()
            if s:
                if s in ("t", "toggle"):
                    ar_enabled = not ar_enabled
                elif s in ("on", "true", "1", "yes", "y"):
                    ar_enabled = True
                elif s in ("off", "false", "0", "no", "n", "disable", "disabled"):
                    ar_enabled = False
                else:
                    print("(warn) invalid input; keeping current enabled setting.")
            try:
                ctx.wm_mapsurface_autoretrieve_enabled = ar_enabled
            except Exception:
                pass
            s = input("Set auto-retrieve mode? [Enter=keep | t=toggle | merge | replace]: ").strip().lower()
            if s:
                if s in ("t", "toggle"):
                    ar_mode = "replace" if ar_mode == "merge" else "merge"
                elif s in ("merge", "m"):
                    ar_mode = "merge"
                elif s in ("replace", "r"):
                    ar_mode = "replace"
                else:
                    print("(warn) invalid mode; keeping current mode.")
            try:
                ctx.wm_mapsurface_autoretrieve_mode = ar_mode
            except Exception:
                pass
            print(f"(now) wm_mapsurface_autoretrieve_enabled={ar_enabled} wm_mapsurface_autoretrieve_mode={ar_mode}")

            print("Current values:")
            print(f"  hunger   = {current_hunger:.2f}")
            print(f"  fatigue  = {current_fatigue:.2f}")
            print(f"  warmth   = {current_warmth:.2f}")
            print(f"  age_days = {current_age:.2f}")
            print("\nEnter new values or press Enter to keep the current value.")
            print("Drives are clamped to the range [0.0, 1.0]. age_days must be ≥ 0.\n")

            def _prompt_float(
                label: str,
                cur: float,
                low: float | None = None,
                high: float | None = None,
            ) -> float:
                """Prompt for a float with optional clamping; blank keeps current."""
                try:
                    raw = input(f"{label} (current={cur:.2f}): ").strip()
                except Exception:
                    return cur
                if not raw:
                    return cur
                try:
                    val = float(raw)
                except Exception:
                    print(f"  [warn] Could not parse {label!r}; keeping previous value.")
                    return cur
                if low is not None and val < low:
                    print(f"  [warn] {label} below minimum {low:.2f}; clamping.")
                    val = low
                if high is not None and val > high:
                    print(f"  [warn] {label} above maximum {high:.2f}; clamping.")
                    val = high
                return val

            # Update drives in-place (these are the same objects used by env-loop)
            new_hunger = _prompt_float("hunger", current_hunger, 0.0, 1.0)
            new_fatigue = _prompt_float("fatigue", current_fatigue, 0.0, 1.0)
            new_warmth = _prompt_float("warmth", current_warmth, 0.0, 1.0)

            try:
                drives.hunger = new_hunger
            except Exception:
                pass
            try:
                drives.fatigue = new_fatigue
            except Exception:
                pass
            try:
                drives.warmth = new_warmth
            except Exception:
                pass

            # Update age_days (non-negative float)
            try:
                raw_age = input(f"age_days (current={current_age:.2f}): ").strip()
            except Exception:
                raw_age = ""
            if raw_age:
                try:
                    val = float(raw_age)
                    if val < 0.0:
                        print("  [warn] age_days below 0.0; clamping to 0.0.")
                        val = 0.0
                    ctx.age_days = val
                except Exception:
                    print("  [warn] Could not parse age_days; keeping previous value.")
            else:
                # Ensure ctx.age_days is at least present
                try:
                    ctx.age_days = current_age
                except Exception:
                    pass

            print("\n[config] Updated episode starting state:")
            print(
                f"  hunger={getattr(drives, 'hunger', new_hunger):.2f} "
                f"fatigue={getattr(drives, 'fatigue', new_fatigue):.2f} "
                f"warmth={getattr(drives, 'warmth', new_warmth):.2f} "
                f"age_days={getattr(ctx, 'age_days', current_age):.2f}"
            )
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "41":
            print("Menu 41 retired. Memory pipeline is hardwired (Phase VII daily-driver).")
            # If later we decide for this menu selection to be interactive again, we should also update the
            #   unreachable “Current settings / presets” prints so they display zone/pred_err/milestone/emotion
            #   keyframe knobs (not just stage).
            print("""[guide] This menu is the main "knobs and buttons" reference card for CCA8 experiments.

NOTE (current runner behavior)
------------------------------
Menu 41 is currently "reference-only":
- The Phase VII daily-driver memory pipeline is hardwired at startup (see apply_hardwired_profile_phase7).
- This menu prints a cheat sheet and returns to the main menu (it does not run an interactive edit flow right now).

Mental model you should have to understand these settings
---------------------------------------------------------

At runtime it helps to keep FOUR memory structures in mind:

1) BodyMap (ctx.body_world)
   - Tiny, safety-critical belief-now register (posture, mom distance, nipple/milk, shelter/cliff).
   - Updated on every EnvObservation tick; read by gates and tie-break logic.

2) WorkingMap (ctx.working_world)
   - Short-term working memory with three layers:
     - MapSurface (WM_ROOT + entity nodes): stable, overwrite-by-slot-family belief table.
     - Scratch (WM_SCRATCH): policy action chains + predicted postconditions (hypotheses).
     - Creative (WM_CREATIVE): counterfactual rollouts (future; inspect-only scaffolding today).
   - By default this is NOT a dense tick-log: MapSurface updates entity nodes in place.
     (Optional: ctx.working_trace=True appends a legacy per-tick trace for debugging.)

3) WorldGraph (world)
   - Durable long-term episode index that persists (autosave / save session).
   - Receives EnvObservation injection (subject to the "long-term env obs" knobs).
   - Receives policy writes unless Phase VII working_first is enabled (then policies execute into WorkingMap).

4) Columns / Engrams (cca8_column.mem)
   - Heavy payload store (append-only / immutable records).
   - WorldGraph/WorkingMap bindings hold only pointers (binding.engrams["column01"]["id"]=...).

Fixed dataflow (env → agent boundary)
-------------------------------------
EnvObservation → BodyMap update (always) → WorkingMap mirror (if enabled) → WorldGraph injection (if enabled)

Keyframes are decided at the env→memory boundary hook (inject_obs_into_world) BEFORE policy selection.

Cue-slot de-duplication (long-term)
-----------------------------------
In changes-mode we can de-duplicate repeated cue tokens:
- rising edge (absent→present) writes a cue:* binding
- held cues do not create new bindings; they bump prominence on the last cue binding
- if a cue disappears and later reappears, a new cue:* binding is written again

Long-term EnvObservation → WorldGraph injection
-----------------------------------------------
longterm_obs_enabled (bool)
  ON  : write env predicates/cues to WorldGraph (subject to mode settings)
  OFF : skip long-term WorldGraph writes (BodyMap still updates; WorkingMap still mirrors if enabled)

longterm_obs_mode ("snapshot" vs "changes")
  snapshot : write every observed predicate each tick (dense; old behavior)
  changes  : treat predicates as state-slots (posture, proximity:mom, hazard:cliff, ...)
             write only when a slot changes (plus optional re-asserts/keyframes)

longterm_obs_reassert_steps (int)
  In changes mode: re-emit an unchanged slot after N controller steps (a "re-observation" cadence).

longterm_obs_dedup_cues (bool)
  In changes mode: write cue:* only on rising-edge (absent→present); held cues bump prominence instead.

longterm_obs_verbose (bool)
  In changes mode: print verbose per-slot reuse lines when slots are unchanged (can be noisy).

Keyframes (episode boundaries)
------------------------------
In changes mode we maintain per-slot caches (ctx.lt_obs_slots and ctx.lt_obs_cues).
A keyframe clears those caches so the current state is written again as a clean boundary snapshot.

Keyframe triggers (Phase IX; evaluated ONLY at the env→memory boundary hook):
  - env_reset: time_since_birth <= 0.0
  - stage_change: scenario_stage changed (longterm_obs_keyframe_on_stage_change)
  - zone_change: coarse safety zone flip (longterm_obs_keyframe_on_zone_change)
  - periodic: every N controller steps (longterm_obs_keyframe_period_steps)
  - surprise: pred_err v0 sustained mismatch (longterm_obs_keyframe_on_pred_err + min_streak)
  - milestones: env_meta milestones and/or derived slot transitions (longterm_obs_keyframe_on_milestone)
  - emotion/arousal: env_meta emotion/affect (rising-edge into "high") with threshold
                     (longterm_obs_keyframe_on_emotion + emotion_threshold)

Keyframe semantics (what "happens at a boundary"):
  - clear long-term slot caches (so the next observation writes as "first" for each slot)
  - (if Phase VII WM<->Column pipeline is enabled) boundary store/retrieve/apply can run:
        store snapshot → optional retrieve candidates → apply priors (replace or seed/merge)
    Reserved future: post-execution write-back / reconsolidation slot.

Manual keyframe (without env.reset):
  - clearing ctx.lt_obs_slots (and ctx.lt_obs_cues) forces the next env observation to be treated as "first".

Phase VII memory pipeline knobs (WorkingMap-first + run compression)
--------------------------------------------------------------------
phase7_working_first (bool)
  OFF: policies write into WorldGraph (action/preds accumulate there)
  ON : policies execute into WorkingMap.Scratch; WorldGraph stays sparse (env keyframes + pointers + runs)

phase7_run_compress (bool)
  If ON: long-term WorldGraph action logging collapses repeated identical policies into one "run" node:
    state → action(run_len=3) → state
  A boundary (stage/posture/nipple/zone signature change) or policy change closes the run.

phase7_move_longterm_now_to_env (bool)
  OFF: long-term NOW moves only when new bindings are written (or at keyframes)
  ON : long-term NOW is actively moved to the current env state binding each step (debug-friendly)

RL policy selection (epsilon-greedy among triggered candidates)
--------------------------------------------------------------
rl_enabled (bool)
  OFF: deterministic winner: deficit → non-drive tie-break → stable order
  ON : epsilon-greedy: explore with probability epsilon; otherwise exploit:
       deficit near-tie band (rl_delta) → non-drive tie-break → learned q → stable order

rl_epsilon (float|None)
  Exploration probability in [0..1]. If None, we use ctx.jump as a convenience default.

rl_delta (float)
  Defines the deficit near-tie band within which q is allowed to decide among candidates.

(For full examples and the authoritative contract, see README.md: keyframes, WM<->Column pipeline, and cognitive cycles.)
""")

            # Control panel: RL policy selection + WorkingMap + long-term WorldGraph obs injection
            print("Selection: Control Panel (RL policy selection + memory knobs)\n")
            #print("""[guide] This menu is the main "knobs and buttons" control panel for CCA8 experiments.



            loop_helper(args.autosave, world, drives, ctx)
            continue
            #pylint: disable=unreachable

            # Ensure WorkingMap exists
            if getattr(ctx, "working_world", None) is None:
                ctx.working_world = init_working_world()
            ww = ctx.working_world

            # --- Current RL settings ---
            enabled_now = bool(getattr(ctx, "rl_enabled", False))
            eps_now = getattr(ctx, "rl_epsilon", None)
            try:
                jump_now = float(getattr(ctx, "jump", 0.0))
            except Exception:
                jump_now = 0.0
            try:
                eff_eps = float(eps_now) if eps_now is not None else jump_now
            except Exception:
                eff_eps = jump_now
            try:
                delta_now = float(getattr(ctx, "rl_delta", 0.0))
            except Exception:
                delta_now = 0.0
            delta_now = max(delta_now, 0.0)
            explore_steps = int(getattr(ctx, "rl_explore_steps", 0) or 0)
            exploit_steps = int(getattr(ctx, "rl_exploit_steps", 0) or 0)

            # --- Current memory settings ---
            world_mode = world.get_memory_mode() if hasattr(world, "get_memory_mode") else "episodic"
            wm_enabled = bool(getattr(ctx, "working_enabled", False))
            wm_verbose = bool(getattr(ctx, "working_verbose", False))
            wm_max = int(getattr(ctx, "working_max_bindings", 0) or 0)
            wm_count = len(getattr(ww, "_bindings", {}))  # pylint: disable=protected-access

            lt_enabled = bool(getattr(ctx, "longterm_obs_enabled", True))
            lt_mode = str(getattr(ctx, "longterm_obs_mode", "snapshot"))
            lt_reassert = int(getattr(ctx, "longterm_obs_reassert_steps", 0) or 0)
            lt_keyframe = bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True))
            lt_verbose = bool(getattr(ctx, "longterm_obs_verbose", False))

            print("Current settings:")
            print(f"  phase7 s/w dev't: working_first={bool(getattr(ctx,'phase7_working_first',False))} run_compress={bool(getattr(ctx,'phase7_run_compress',False))} run_verbose={bool(getattr(ctx,'phase7_run_verbose',False))} move_NOW_to_env={bool(getattr(ctx,'phase7_move_longterm_now_to_env',False))}")
            print(f"  RL: enabled={enabled_now} epsilon={eps_now!r} effective={eff_eps:.3f} delta={delta_now:.3f} (explore={explore_steps}, exploit={exploit_steps})")
            print(f"  WorkingMap: enabled={wm_enabled} verbose={wm_verbose} max_bindings={wm_max} bindings={wm_count}")
            print(f"  WorldGraph: memory_mode={world_mode}")
            print(f"  Long-term env obs: enabled={lt_enabled} mode={lt_mode} reassert_steps={lt_reassert} keyframe_on_stage={lt_keyframe} verbose={lt_verbose}")
            print()

            # Quick exit if user just wants to view status
            edit = input("Adjust settings now? [y/N]: ").strip().lower()
            if edit not in ("y", "yes"):
                loop_helper(args.autosave, world, drives, ctx)
                continue

            # ---- Presets (quick tuning of long-term env obs) ----
            print("\nPresets (long-term env obs):")
            print("  bio    = changes + keyframes + reassert=25 (periodic re-observation)")
            print("  sparse = changes + keyframes + reassert=0  (minimal long-term growth)")
            print("  debug  = snapshot + verbose (write every env pred each tick)")
            preset = input("Preset? [Enter=skip | bio | sparse | debug]: ").strip().lower()
            if preset in ("bio", "biological"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "changes"
                ctx.longterm_obs_reassert_steps = 25
                ctx.longterm_obs_keyframe_on_stage_change = False
                ctx.longterm_obs_verbose = False
            elif preset in ("sparse", "minimal"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "changes"
                ctx.longterm_obs_reassert_steps = 0
                ctx.longterm_obs_keyframe_on_stage_change = False
                ctx.longterm_obs_verbose = False
            elif preset in ("debug", "trace"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "snapshot"
                ctx.longterm_obs_reassert_steps = 0
                ctx.longterm_obs_keyframe_on_stage_change = True
                ctx.longterm_obs_verbose = True

            # ---- RL controls ----
            print("\nRL policy selection:")
            raw = input("RL enabled? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                enabled_new = True
            elif raw in ("off", "false", "0", "no", "n"):
                enabled_new = False
            elif raw == "":
                enabled_new = not enabled_now
            else:
                enabled_new = enabled_now

            eps_new = eps_now
            if enabled_new:
                raw_eps = input(f"rl_epsilon (0..1 or 'none'; current={eps_now!r}, effective={eff_eps:.3f}; Enter=keep): ").strip().lower()
                if raw_eps == "":
                    eps_new = eps_now
                elif raw_eps in ("none", "null"):
                    eps_new = None
                else:
                    try:
                        v = float(raw_eps)
                        v = max(v, 0.0)
                        v = min(v, 1.0)
                        eps_new = v
                    except ValueError:
                        eps_new = eps_now

                raw_delta = input(f"rl_delta (>=0; current={delta_now:.3f}; Enter=keep): ").strip().lower()
                if raw_delta != "":
                    try:
                        v = float(raw_delta)
                        v = max(v, 0.0)
                        ctx.rl_delta = v
                    except ValueError:
                        pass

            ctx.rl_enabled = enabled_new
            ctx.rl_epsilon = eps_new

            # ---- WorkingMap controls ----
            print("\nWorkingMap (short-term raw trace):")
            raw = input("WorkingMap capture? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.working_enabled = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.working_enabled = False
            elif raw == "":
                ctx.working_enabled = not bool(getattr(ctx, "working_enabled", False))

            rawv = input("WorkingMap verbose? [Enter=toggle | on | off]: ").strip().lower()
            if rawv in ("on", "true", "1", "yes", "y"):
                ctx.working_verbose = True
            elif rawv in ("off", "false", "0", "no", "n"):
                ctx.working_verbose = False
            elif rawv == "":
                ctx.working_verbose = not bool(getattr(ctx, "working_verbose", False))

            rawm = input(f"WorkingMap max_bindings (current={wm_max}; Enter=keep): ").strip()
            if rawm:
                try:
                    ctx.working_max_bindings = max(0, int(float(rawm)))
                except ValueError:
                    print("  (ignored: could not parse max_bindings)")

             # ---- phase7 s/w devp't scaffolding memory pipeline knobs ----
            print("\nphase7 s/w devp't memory pipeline (experimental):")
            raw = input("working_first (execute policies in WorkingMap)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_working_first = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_working_first = False
            elif raw == "":
                ctx.phase7_working_first = not bool(getattr(ctx, "phase7_working_first", False))

            raw = input("run_compress (compress repeated policy actions in long-term WorldGraph)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_run_compress = True
                # If we are compressing actions, it's usually because we want long-term WorldGraph sparse.
                ctx.phase7_working_first = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_run_compress = False
            elif raw == "":
                ctx.phase7_run_compress = not bool(getattr(ctx, "phase7_run_compress", False))
                if bool(getattr(ctx, "phase7_run_compress", False)):
                    ctx.phase7_working_first = True

            raw = input("run_verbose (print run-compression debug lines)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_run_verbose = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_run_verbose = False
            elif raw == "":
                ctx.phase7_run_verbose = not bool(getattr(ctx, "phase7_run_verbose", False))

            raw = input("move_longterm_NOW_to_env (move long-term NOW to env state each step)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_move_longterm_now_to_env = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_move_longterm_now_to_env = False
            elif raw == "":
                ctx.phase7_move_longterm_now_to_env = not bool(getattr(ctx, "phase7_move_longterm_now_to_env", False))

            # ---- WorldGraph memory_mode ----
            if hasattr(world, "set_memory_mode") and hasattr(world, "get_memory_mode"):
                print("\nWorldGraph memory_mode:")
                print("  episodic = every add creates a new binding (dense trace)")
                print("  semantic = reuse identical pred/cue bindings (less clutter; experimental)")
                raw_mode = input(f"memory_mode (current={world.get_memory_mode()}; Enter=keep): ").strip().lower()
                if raw_mode in ("episodic", "semantic"):
                    world.set_memory_mode(raw_mode)

            # ---- Long-term env observation injection knobs ----
            print("\nLong-term EnvObservation → WorldGraph injection:")
            raw_lt = input("Enabled? [Enter=toggle | on | off]: ").strip().lower()
            if raw_lt in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_enabled = True
            elif raw_lt in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_enabled = False
            elif raw_lt == "":
                ctx.longterm_obs_enabled = not bool(getattr(ctx, "longterm_obs_enabled", True))

            print("Mode options:")
            print("  changes  = write only when a state slot changes (dedup env preds)")
            print("  snapshot = write every observed pred each tick (old behavior)")
            raw_ltm = input(f"mode (current={getattr(ctx,'longterm_obs_mode','snapshot')}; Enter=keep): ").strip().lower()
            if raw_ltm in ("changes", "snapshot"):
                ctx.longterm_obs_mode = raw_ltm

            raw_rs = input(f"reassert_steps (current={getattr(ctx,'longterm_obs_reassert_steps',0)}; Enter=keep): ").strip()
            if raw_rs:
                try:
                    ctx.longterm_obs_reassert_steps = max(0, int(float(raw_rs)))
                except ValueError:
                    print("  (ignored: could not parse reassert steps)")

            raw_kf = input("keyframe_on_stage_change? [Enter=toggle | on | off]: ").strip().lower()
            if raw_kf in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_keyframe_on_stage_change = False
            elif raw_kf in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_keyframe_on_stage_change = False
            elif raw_kf == "":
                #ctx.longterm_obs_keyframe_on_stage_change = not bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True))
                ctx.longterm_obs_keyframe_on_stage_change = False

            raw_lv = input("longterm_obs_verbose (show reuse lines)? [Enter=toggle | on | off]: ").strip().lower()
            if raw_lv in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_verbose = True
            elif raw_lv in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_verbose = False
            elif raw_lv == "":
                ctx.longterm_obs_verbose = not bool(getattr(ctx, "longterm_obs_verbose", False))

            # ---- Optional clears ----
            rawc = input("\nClear WorkingMap now? [y/N]: ").strip().lower()
            if rawc in ("y", "yes"):
                reset_working_world(ctx)

            raw_slot = input("Clear long-term slot cache now? (next env obs treated as 'first') [y/N]: ").strip().lower()
            if raw_slot in ("y", "yes"):
                try:
                    ctx.lt_obs_slots.clear()
                    ctx.lt_obs_last_stage = None
                except Exception:
                    pass

            # Re-prune after changes
            _prune_working_world(ctx)

            # ---- Print updated settings ----
            try:
                jump_now = float(getattr(ctx, "jump", 0.0))
            except Exception:
                jump_now = 0.0
            eps_now2 = getattr(ctx, "rl_epsilon", None)
            try:
                eff_eps2 = float(eps_now2) if eps_now2 is not None else jump_now
            except Exception:
                eff_eps2 = jump_now
            try:
                delta_now2 = float(getattr(ctx, "rl_delta", 0.0))
            except Exception:
                delta_now2 = 0.0

            world_mode2 = world.get_memory_mode() if hasattr(world, "get_memory_mode") else "episodic"
            ww_count2 = len(getattr(ctx.working_world, "_bindings", {}))  # pylint: disable=protected-access

            print("\nUpdated settings:")
            print(f"  RL: enabled={bool(getattr(ctx,'rl_enabled',False))} epsilon={getattr(ctx,'rl_epsilon',None)!r} effective={eff_eps2:.3f} delta={max(0.0, float(delta_now2)):.3f}")
            print(f"  WorkingMap: enabled={bool(getattr(ctx,'working_enabled',False))} verbose={bool(getattr(ctx,'working_verbose',False))} max_bindings={int(getattr(ctx,'working_max_bindings',0) or 0)} bindings={ww_count2}")
            print(f"  WorldGraph: memory_mode={world_mode2}")
            print(f"  Long-term env obs: enabled={bool(getattr(ctx,'longterm_obs_enabled',True))} mode={getattr(ctx,'longterm_obs_mode','snapshot')} reassert_steps={int(getattr(ctx,'longterm_obs_reassert_steps',0) or 0)} keyframe_on_stage={bool(getattr(ctx,'longterm_obs_keyframe_on_stage_change',True))} verbose={bool(getattr(ctx,'longterm_obs_verbose',False))}")

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
                print("  - next menu 35/37 call will start a fresh goat_foraging_04 episode")
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

            rawc = input("\nClear WorkingMap now? [y/N]: ").strip().lower()
            if rawc in ("y", "yes"):
                reset_working_world(ctx)
                print("(WorkingMap cleared.)")

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
                print("Tip: run menu 44 (manual store) or run menu 37 until a stage/zone boundary occurs.")
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

            print("\nTip: paste an engram id into menu 27 to inspect payload/meta.")
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
                print("Tip: run menu 37 to auto-store keyframes, or menu 44 to store manually.")
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
                print("Tip: run appropriate menu item (43 currently) to inspect; then run one env step to let observation correct the prior.")
            else:
                print(f"[wm-retrieve] replaced WorkingMap from engram={raw[:8]}…: entities={out.get('entities')} relations={out.get('relations')}")
                print("Tip: run appropriate menu item (43 currently) now to inspect the loaded MapSurface; next env step may overwrite parts of it.")

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
            # Show drives (raw + tags), robust across Drives variants
            print("Selection: Drives & Drive Tags\n")
            print("Shows raw drive values and threshold flags with their sources.\n")
            print(drives_and_tags_text(drives))
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
        elif choice.lower() == "t":
            # Help and Tutorial selection that opens project documentation
            print("Selection:  Help -- System Docs and Tutorial\n")

            print("\nTutorial options:")
            print("  1) README/compendium System Documentation")
            print("  2) Console Tour (pending)")
            print("  [Enter] Cancel")
            try:
                pick = input("Choose: ").strip()
            except Exception:
                pick = ""
            #pylint:disable=no-else-continue
            if pick == "1":
                comp = os.path.join(os.getcwd(), "README.md")
                print(f"Tutorial file (README.md which acts as an all-in-one compendium): {comp}")
                if os.path.exists(comp):
                    try:
                        if sys.platform.startswith("win"):
                            os.startfile(comp)  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            os.system(f'open "{comp}"')
                        else:
                            os.system(f'xdg-open "{comp}"')
                        print("Opened the README.md/compendium in your default viewer.")
                    except Exception as e:
                        print(f"[warn] Could not open automatically: {e}")
                        print("Please open the file manually in your editor.")
                else:
                    print("README.md not found in the current folder. Copy it here to open directly.")
                continue
            elif pick == "2":
                print("Console tour is pending; please use the README/compendium for now.")
                continue
            else:
                print("(cancelled)")
                continue
        #pylint:enable=no-else-continue
        #no loop_helper(...) -- tutorial/help returns to main menu

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
    #p.add_argument("--write-artifacts", action="store_true", help="Write preflight artifacts to disk")
    p.add_argument("--load", help="Load session from JSON file")
    p.add_argument("--save", help="Save session to JSON file on exit")
    p.add_argument("--autosave", help="Autosave session to JSON file after each action")

    try:
        args = p.parse_args(argv)
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
        comps = [  # (label, version, path)
            ("cca8_run.py", __version__, os.path.abspath(__file__)),
        ]
        for name in [
            "cca8_world_graph",
            "cca8_controller",
            "cca8_temporal",
            "cca8_column",
            "cca8_features",
            "cca8_env",
            "cca8_profiles",
            "cca8_guidance",
            "cca8_navpatch",
            "cca8_rcos",
            "cca8_rcos_experiments",
            "cca8_state_integrity",
            "cca8_teaching",
            "cca8_predictive",
            "cca8_test_fixtures",
        ]:
            ver, path = _module_version_and_path(name)
            comps.append((name, ver, path))

        print("CCA8 Components:")
        for label, ver, path in comps:
            print(f"  - {label} v{ver} ({path})")

        # additionally show primitive count if the controller is importable
        try:
            print(f"\n    [controller primitives: {len(PRIMITIVES)}]")
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
