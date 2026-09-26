#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the coherent architecture explanation and system-status panels."""

from __future__ import annotations

from cca8_column import ColumnMemory
from cca8_context import Ctx
from cca8_features import TensorPayload
from cca8_guidance import architecture_overview_text_v1
from cca8_reporting import architecture_status_text_v1
from cca8_world_graph import WorldGraph


class _PolicyRuntimeStub:
    """Small deterministic legacy-policy registry for the status panel."""

    def list_loaded_names(self) -> list[str]:
        """Return a stable pair of currently loaded legacy-policy names."""
        return ["policy:stand_up", "policy:follow_mom"]


def test_architecture_overview_states_the_current_map_first_contract() -> None:
    """The terminal overview should teach the current architecture rather than the legacy graph-first model."""
    text = architecture_overview_text_v1()

    assert "map-first cognitive architecture" in text
    assert "the SAME Selected NM serves in the WNM role" in text
    assert "WorldGraph" in text
    assert "WorldIndex holds sparse bindings" in text
    assert "Columns" in text
    assert "actual NM-owning hosts" in text
    assert "internal handoff precede cognitive-cycle closure" in text
    assert "host/default runtime retains PolicyRuntime, WorldGraph, Columns, WorkingMap" in text
    assert "symbolic declarative memory" not in text


def test_architecture_status_panel_is_coherent_and_read_only() -> None:
    """The status view should distinguish WNM, Columns, sparse retrieval, and WorldGraph without mutation."""
    world = WorldGraph()
    world.set_tag_policy("allow")
    now_id = world.ensure_anchor("NOW")
    current_id = world.add_predicate("posture:standing", attach="now")
    column_memory = ColumnMemory(name="test_column")
    engram_id = column_memory.assert_fact(
        "test:scene",
        TensorPayload(data=[0.25, 0.75], shape=(2,)),
    )
    world.attach_engram(current_id, column="test_column", engram_id=engram_id)
    world.attach_engram(now_id, column="test_column", engram_id="missing-engram")
    ctx = Ctx()

    world_before = world.to_dict()
    column_ids_before = column_memory.list_ids()
    text = architecture_status_text_v1(world, ctx, column_memory, _PolicyRuntimeStub())

    assert "CURRENT COGNITION" in text
    assert "Operative WNM" in text
    assert "LONG-TERM RICH CONTENT" in text
    assert "Columns: total engrams=1" in text
    assert "SPARSE MEMORY ACTIVATION" in text
    assert "ctx-local sparse reference/token index scaffold" in text
    assert "WORLDGRAPH" in text
    assert "sparse episode/retrieval/index structure plus legacy symbolic compatibility content" in text
    assert "Column pointers=2 unique_engram_ids=2 dangling=1" in text
    assert "loaded=2 -> policy:stand_up, policy:follow_mom" in text
    assert "retrieval supplies candidates, not present-world authority" in text
    assert world.to_dict() == world_before
    assert column_memory.list_ids() == column_ids_before


def test_v102_overview_separates_functional_parts_legacy_names_and_implemented_scope() -> None:
    """New labels must not silently turn a compatibility store or an experiment into the full target."""
    text = " ".join(architecture_overview_text_v1().split())
    for expected in (
        "Attention Module", "Executive Navigation Module (ExecNav)", "Instinctive Procedure System",
        "Predicted NavMap (PNM)", "BodyMap Module", "Sensorimotor Primitive (SMP) retains Primitive",
        "Sequential Expectation and Correction Module (SEC)", "WorldIndex Module",
        "zero-or-one WNM role", "not a detached second map or a guarantee of current truth",
        "WorldGraph is a Python/API name", "P16-2C-N", "separately selected Rest",
        "not a central learner or the sole time of plasticity", "not establish general LP acquisition",
    ):
        assert expected in text
    assert "sparse WorldGraph memory activation" not in text
    assert "Exactly one NavMap has detailed accepted-current cognitive authority" not in text
    assert "Sensorimotor Procedure" not in text
