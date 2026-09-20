#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dependency and observation-leakage firewall tests for flat ``nca8_*`` modules."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from cca8_env import EnvObservation
from nca8_adapters import adapt_env_observation_v1

ROOT = Path(__file__).resolve().parents[1]
NCA8_FILES = tuple(sorted(ROOT.glob("nca8_*.py")))

_ALLOWED_CCA8_IMPORTS: dict[str, frozenset[str]] = {
    "nca8_adapters.py": frozenset({"cca8_env", "cca8_navpatch"}),
    "nca8_body.py": frozenset({"cca8_motor_contracts"}),
    "nca8_body_targets.py": frozenset({"cca8_motor_contracts"}),
    "nca8_contracts.py": frozenset(),
    "nca8_executive.py": frozenset(),
    "nca8_handoff.py": frozenset({"cca8_motor_contracts"}),
    "nca8_hierarchy.py": frozenset({"cca8_motor_contracts", "cca8_support_world"}),
    "nca8_hierarchy_demo.py": frozenset({"cca8_cli", "cca8_motor_contracts", "cca8_support_world"}),
    "nca8_hierarchy_qualification.py": frozenset({"cca8_cli", "cca8_motor_contracts", "cca8_support_world"}),
    "nca8_learning.py": frozenset({"cca8_motor_contracts"}),
    "nca8_learning_demo.py": frozenset({"cca8_cli", "cca8_motor_contracts", "cca8_support_world"}),
    "nca8_learning_registry.py": frozenset(),
    "nca8_maps.py": frozenset({"cca8_navmap_kernel", "cca8_motor_contracts"}),
    "nca8_menu.py": frozenset({"cca8_cli"}),
    "nca8_outcome_attention.py": frozenset({"cca8_motor_contracts"}),
    "nca8_outcome_attention_demo.py": frozenset({"cca8_cli", "cca8_motor_contracts", "cca8_support_world"}),
    "nca8_outcomes.py": frozenset({"cca8_motor_contracts"}),
    "nca8_outcomes_demo.py": frozenset({"cca8_cli", "cca8_support_world"}),
    "nca8_prediction.py": frozenset(),
    "nca8_primitives.py": frozenset(),
    "nca8_righting.py": frozenset({"cca8_motor_contracts"}),
    "nca8_righting_demo.py": frozenset({"cca8_motor_contracts"}),
    "nca8_runtime.py": frozenset({"cca8_motor_contracts"}),
    "nca8_scheduler.py": frozenset(),
    "nca8_sensorimotor.py": frozenset({"cca8_motor_contracts"}),
    "nca8_sensorimotor_demo.py": frozenset({"cca8_cli", "cca8_motor_contracts", "cca8_support_world"}),
    "nca8_sensorimotor_contracts.py": frozenset({"cca8_motor_contracts"}),
    "nca8_sensory.py": frozenset({"cca8_motor_contracts"}),
    "nca8_support_dynamics.py": frozenset(),
    "nca8_trace.py": frozenset(),
}

_FORBIDDEN_LEGACY_COGNITION = frozenset(
    {
        "cca8_context",
        "cca8_controller",
        "cca8_policy_runtime",
        "cca8_working_memory",
        "cca8_world_graph",
        "cca8_observation_runtime",
        "cca8_navmap_runtime",
        "cca8_navmap_shadow",
        "cca8_wnm_runtime",
        "cca8_predictive",
        "cca8_maternal_geometry",
        "cca8_maternal_temporal",
        "cca8_maternal_continuity",
        "cca8_followmom_compare",
        "cca8_followmom_advisory",
        "cca8_followmom_authority",
        "cca8_feeding",
        "cca8_terrain",
        "cca8_live_dynamics",
        "cca8_navmap_memory",
        "cca8_run",
    }
)


def _import_roots_v1(tree: ast.AST) -> set[str]:
    """Return absolute top-level import roots from one parsed module."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_flat_nca8_module_set_is_explicit_and_complete() -> None:
    """The manifest includes called boundary and owner-local support services, not future brain modules."""
    assert tuple(path.name for path in NCA8_FILES) == (
        "nca8_adapters.py",
        "nca8_body.py",
        "nca8_body_targets.py",
        "nca8_contracts.py",
        "nca8_executive.py",
        "nca8_handoff.py",
        "nca8_hierarchy.py",
        "nca8_hierarchy_demo.py",
        "nca8_hierarchy_qualification.py",
        "nca8_learning.py",
        "nca8_learning_demo.py",
        "nca8_learning_registry.py",
        "nca8_maps.py",
        "nca8_menu.py",
        "nca8_outcome_attention.py",
        "nca8_outcome_attention_demo.py",
        "nca8_outcomes.py",
        "nca8_outcomes_demo.py",
        "nca8_prediction.py",
        "nca8_primitives.py",
        "nca8_righting.py",
        "nca8_righting_demo.py",
        "nca8_runtime.py",
        "nca8_scheduler.py",
        "nca8_sensorimotor.py",
        "nca8_sensorimotor_contracts.py",
        "nca8_sensorimotor_demo.py",
        "nca8_sensory.py",
        "nca8_support_dynamics.py",
        "nca8_trace.py",
    )


def test_ast_import_firewall_blocks_legacy_cognitive_authority() -> None:
    """Every NCA8 module should have an auditable, narrow CCA8 import allowance."""
    assert set(_ALLOWED_CCA8_IMPORTS) == {path.name for path in NCA8_FILES}

    for path in NCA8_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        roots = _import_roots_v1(tree)
        cca8_roots = {root for root in roots if root.startswith("cca8_")}
        assert not (cca8_roots & _FORBIDDEN_LEGACY_COGNITION), path.name
        assert cca8_roots == set(_ALLOWED_CCA8_IMPORTS[path.name]), path.name


def test_nca8_code_never_reads_environment_state_or_private_state() -> None:
    """The God's-eye environment state must remain inaccessible to the new brain."""
    for path in NCA8_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"state", "_state"}, f"{path.name}:{node.lineno}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    assert node.args[1].value not in {"state", "_state"}, f"{path.name}:{node.lineno}"


def test_nca8_cognition_never_reads_hidden_stage_milestone_or_oracle_fields() -> None:
    """Phase-1C cognition may read filtered posture tokens, not task answers or stage labels."""
    forbidden = {
        "scenario_stage",
        "milestones",
        "oracle_policy",
        "final_score",
        "hidden_benchmark_context",
        "search_progress",
        "suckle_progress",
        "milk_progress",
    }
    cognitive_files = tuple(
        path for path in NCA8_FILES if path.name not in {"nca8_adapters.py", "nca8_menu.py"}
    )

    for path in cognitive_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden, f"{path.name}:{node.lineno}"
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                assert node.slice.value not in forbidden, f"{path.name}:{node.lineno}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    assert node.args[1].value not in forbidden, f"{path.name}:{node.lineno}"


def test_sensory_map_and_attention_code_contain_no_standup_task_shortcut() -> None:
    """StandUp domain knowledge must stay out of sensory maps and generic Attention."""
    representation_files = (
        ROOT / "nca8_executive.py",
        ROOT / "nca8_maps.py",
        ROOT / "nca8_sensory.py",
    )

    for path in representation_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring_nodes: set[int] = set()
        for owner in ast.walk(tree):
            if isinstance(owner, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if owner.body and isinstance(owner.body[0], ast.Expr):
                    value = owner.body[0].value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        docstring_nodes.add(id(value))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert "stand_up" not in node.id.lower(), f"{path.name}:{node.lineno}"
            if isinstance(node, ast.Attribute):
                assert "stand_up" not in node.attr.lower(), f"{path.name}:{node.lineno}"
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_nodes:
                assert "stand_up" not in node.value.lower(), f"{path.name}:{node.lineno}"
                assert "policy:stand_up" not in node.value.lower(), f"{path.name}:{node.lineno}"


def test_importing_legacy_runner_does_not_import_nca8_runtime_modules() -> None:
    """Normal legacy startup must not eagerly load or construct the second brain."""
    command = (
        "import json, sys; import cca8_run; "
        "print(json.dumps(sorted(name for name in sys.modules if name.startswith('nca8_'))))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert json.loads(completed.stdout.strip()) == []


def _malicious_observation_v1() -> EnvObservation:
    """Return an observation containing allowed evidence plus nested oracle traps."""
    return EnvObservation(
        raw_sensors={
            "distance_to_mom": 1.25,
            "kid_temperature": 0.61,
            "oracle_policy": "policy:stand_up",
        },
        predicates=["posture:fallen", "oracle:next_action"],
        cues=["vision:silhouette:mom", "stage:rest"],
        nav_patches=[
            {
                "schema": "navpatch_v1",
                "local_id": "p_scene",
                "entity_id": "scene",
                "role": "scene",
                "frame": "ego_schematic_v1",
                "grid_encoding_v": "grid_v1",
                "grid_w": 2,
                "grid_h": 2,
                "grid_cells": [0, 3, 1, 0],
                "tags": ["stage:rest", "goal:nipple", "oracle:stand_up"],
                "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
                "obs": {"source": "test", "step_index": 7, "oracle_policy": "policy:stand_up"},
                "secret": {"final_score": 99},
            }
        ],
        env_meta={
            "time_since_birth": 7.0,
            "step_index": 7,
            "scenario_stage": "rest",
            "milestones": ["stood_up", "rested"],
            "position": "shelter_area",
            "zone": "safe",
            "oracle_policy": "policy:stand_up",
            "final_score": 99,
            "hidden_benchmark_context": "answer",
            "terrain_geometry_v1": {"stage": "rest", "position_label": "shelter_area"},
            "feeding_geometry_v1": {
                "search_progress": 1.0,
                "suckle_progress": 1.0,
                "milk_progress": 1.0,
            },
            "lower_motor_feedback_v1": {
                "schema": "lower_motor_feedback_v1",
                "source_ref": "test:step:7",
                "quality": 0.85,
                "action_applied": "policy:stand_up",
                "support_contact": True,
                "slip_detected": False,
                "progress": 1.0,
                "phase": "completed",
                "error_code": None,
                "oracle_policy": "policy:stand_up",
            },
        },
        surface_grid={
            "schema": "surface_grid_v1",
            "frame": "body",
            "anchor": {"entity": "kid", "x": 0.0, "y": 0.0},
            "center": {"entity": "kid", "x": 0.0, "y": 0.0},
            "objects": [{"entity": "mom", "dx": 1.0, "dy": 0.0, "dist": 1.0}],
            "landmarks": [
                {"token": "mom", "entity": "mom", "kind": "social", "dist": 1.0},
                {"token": "shelter", "entity": "shelter", "kind": "goal", "dist": 1.0},
            ],
            "affordances": {"cliff_near": False, "shelter_near": True, "mom_near": True},
            "region": {"position": "shelter_area", "zone": "safe"},
            "focus_candidates": ["mom"],
            "oracle_policy": "policy:stand_up",
        },
    )


def test_observation_adapter_uses_recursive_positive_whitelists() -> None:
    """Top-level and nested hidden task answers should not survive adaptation."""
    safe = adapt_env_observation_v1(_malicious_observation_v1())
    payload = safe.as_dict()
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["raw_sensors"] == {"distance_to_mom": 1.25, "kid_temperature": 0.61}
    assert payload["predicates"] == ["posture:fallen"]
    assert payload["cues"] == ["vision:silhouette:mom"]
    assert "tags" not in payload["nav_patches"][0]
    assert "secret" not in payload["nav_patches"][0]
    assert payload["nav_patches"][0]["grid_cells"] == [0, 1, 1, 0]
    assert "oracle_policy" not in payload["nav_patches"][0]["obs"]
    assert "region" not in payload["surface_grid"]
    assert "oracle_policy" not in payload["surface_grid"]
    assert "kind" not in payload["surface_grid"]["landmarks"][1]
    assert "focus_candidates" not in payload["surface_grid"]

    for forbidden_key in (
        "scenario_stage",
        "milestones",
        "position_label",
        "hidden_benchmark_context",
        "final_score",
        "feeding_geometry_v1",
        "terrain_geometry_v1",
        "search_progress",
        "suckle_progress",
        "milk_progress",
        "goal:nipple",
        "stage:rest",
        "oracle:stand_up",
    ):
        assert forbidden_key not in rendered


def test_adapted_observation_is_detached_and_recursively_read_only() -> None:
    """The source packet cannot mutate the observation owned by the new session."""
    source = _malicious_observation_v1()
    safe = adapt_env_observation_v1(source)
    before = safe.as_dict()

    source.raw_sensors["distance_to_mom"] = 999.0
    source.nav_patches[0]["grid_cells"][0] = 99
    source.surface_grid["objects"][0]["dist"] = 999.0

    assert safe.as_dict() == before
    with pytest.raises(TypeError):
        safe.raw_sensors["distance_to_mom"] = 2.0  # type: ignore[index]


def test_adapted_observation_export_is_json_safe() -> None:
    """The immutable internal packet should still provide a plain diagnostic export."""
    payload: dict[str, Any] = adapt_env_observation_v1(_malicious_observation_v1()).as_dict()

    encoded = json.dumps(payload, sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["env_meta"]["step_index"] == 7
    assert decoded["surface_grid"]["affordances"]["mom_near"] is True
