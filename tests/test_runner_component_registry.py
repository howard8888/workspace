# -*- coding: utf-8 -*-
"""Tests for the canonical CCA8 component registry and ``--about`` report."""

from __future__ import annotations

import pytest

import cca8_run

# These tests intentionally verify the runner's private component registry.
# pylint: disable=protected-access

REQUIRED_COMPONENTS: dict[str, str] = {
    "context": "cca8_context",
    "cli": "cca8_cli",
    "preflight": "cca8_preflight",
    "experiments": "cca8_experiments",
    "openai": "cca8_openai",
    "working_memory": "cca8_working_memory",
    "profiles": "cca8_profiles",
    "guidance": "cca8_guidance",
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
    "wnm_runtime": "cca8_wnm_runtime",
    "standup_compare": "cca8_standup_compare",
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
