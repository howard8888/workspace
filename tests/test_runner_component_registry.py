# -*- coding: utf-8 -*-
"""Tests for the canonical CCA8 component registry and ``--about`` report."""

from __future__ import annotations

import pytest

import cca8_run

# These tests intentionally verify the runner's private component registry.
# pylint: disable=protected-access

REQUIRED_COMPONENTS: dict[str, str] = {
    "motor_contracts": "cca8_motor_contracts",
    "context": "cca8_context",
    "cli": "cca8_cli",
    "preflight": "cca8_preflight",
    "experiments": "cca8_experiments",
    "openai": "cca8_openai",
    "working_memory": "cca8_working_memory",
    "profiles": "cca8_profiles",
    "guidance": "cca8_guidance",
    "main_menu": "cca8_main_menu",
    "navmap": "cca8_navmap",
    "navmap_kernel": "cca8_navmap_kernel",
    "navmap_shadow": "cca8_navmap_shadow",
    "maternal_geometry": "cca8_maternal_geometry",
    "maternal_temporal": "cca8_maternal_temporal",
    "maternal_continuity": "cca8_maternal_continuity",
    "followmom_compare": "cca8_followmom_compare",
    "followmom_advisory": "cca8_followmom_advisory",
    "followmom_authority": "cca8_followmom_authority",
    "feeding": "cca8_feeding",
    "terrain": "cca8_terrain",
    "live_dynamics": "cca8_live_dynamics",
    "navmap_memory": "cca8_navmap_memory",
    "wnm_runtime": "cca8_wnm_runtime",
    "cognitive_scope": "cca8_cognitive_scope",
    "cognitive_scope_menu": "cca8_cognitive_scope_menu",
    "cognitive_injection": "cca8_cognitive_injection",
    "standup_compare": "cca8_standup_compare",
    "rcos_menu": "cca8_rcos_menu",
    "session_menu": "cca8_session_menu",
    "nca8_adapters": "nca8_adapters",
    "nca8_body": "nca8_body",
    "nca8_body_targets": "nca8_body_targets",
    "nca8_contracts": "nca8_contracts",
    "nca8_followmom": "nca8_followmom",
    "nca8_followmom_demo": "nca8_followmom_demo",
    "nca8_maternal": "nca8_maternal",
    "nca8_hierarchy": "nca8_hierarchy",
    "nca8_hierarchy_demo": "nca8_hierarchy_demo",
    "nca8_hierarchy_qualification": "nca8_hierarchy_qualification",
    "nca8_learning": "nca8_learning",
    "nca8_learning_demo": "nca8_learning_demo",
    "nca8_learning_registry": "nca8_learning_registry",
    "nca8_visual": "nca8_visual",
    "nca8_visual_demo": "nca8_visual_demo",
    "nca8_outcomes": "nca8_outcomes",
    "nca8_outcomes_demo": "nca8_outcomes_demo",
    "nca8_righting": "nca8_righting",
    "nca8_righting_demo": "nca8_righting_demo",
    "nca8_sensorimotor": "nca8_sensorimotor",
    "nca8_sensorimotor_demo": "nca8_sensorimotor_demo",
    "nca8_sensorimotor_contracts": "nca8_sensorimotor_contracts",
    "nca8_executive": "nca8_executive",
    "nca8_maps": "nca8_maps",
    "nca8_menu": "nca8_menu",
    "nca8_prediction": "nca8_prediction",
    "nca8_primitives": "nca8_primitives",
    "nca8_runtime": "nca8_runtime",
    "nca8_scheduler": "nca8_scheduler",
    "nca8_sensory": "nca8_sensory",
    "nca8_trace": "nca8_trace",
}


def test_component_registry_contains_previously_omitted_modules() -> None:
    """The canonical registry should include all recently extracted components."""
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)

    for key, module_name in REQUIRED_COMPONENTS.items():
        assert registry[key] == module_name


def test_versions_dict_and_text_follow_component_registry() -> None:
    """Structured and text version reports should expose the same components."""
    versions = cca8_run.versions_dict()
    text = cca8_run.versions_text()

    assert versions["runner"] == cca8_run.__version__
    assert f"runner: {cca8_run.__version__}" in text

    for key, _module_name in cca8_run._CCA8_COMPONENT_REGISTRY:
        assert key in versions
        assert versions[f"{key}_path"]
        assert f"{key}: {versions[key]}" in text


def test_about_reports_runner_and_every_registered_component(capsys: pytest.CaptureFixture[str]) -> None:
    """The command-line report should be generated from the canonical registry."""
    assert cca8_run.main(["--about"]) == 0

    output = capsys.readouterr().out
    component_rows = cca8_run._cca8_component_rows()

    assert "CCA8 Components:" in output
    assert f"[components listed: {len(component_rows)}]" in output
    assert "  - cca8_run.py v" in output
    assert f"[registered behavioral primitives: {len(cca8_run.PRIMITIVES)}]" in output

    for _key, module_name in cca8_run._CCA8_COMPONENT_REGISTRY:
        assert f"  - {module_name} v" in output
