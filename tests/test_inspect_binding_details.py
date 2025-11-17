# -*- coding: utf-8 -*-
"""
Tests for the Inspect Binding Details menu (menu #20 / legacy #10).

These tests don't drive the interactive loop directly (which is input/print-based),
but they verify that the *world state* created by build_demo_world_for_inspect()
has the structure that menu #20 is supposed to reveal:

- Anchors (NOW/HERE) with correct tags and degrees.
- Predicates with expected meta / provenance.
- Engram attachments and edge degrees for a "rest" node.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pytest

from cca8_world_graph import WorldGraph
from cca8_test_worlds import build_demo_world_for_inspect


def _incoming_edges(world: WorldGraph, target_bid: str) -> list[tuple[str, str]]:
    """
    Utility used only in tests: return (src_id, label) for all edges whose
    destination is target_bid.
    """
    incoming: list[tuple[str, str]] = []
    for src_id, b in world._bindings.items():
        for e in getattr(b, "edges", []):
            if e.get("to") == target_bid:
                incoming.append((src_id, e.get("label", "")))
    return incoming


def _outgoing_edges(world: WorldGraph, src_bid: str) -> list[tuple[str, str]]:
    """
    Utility used only in tests: return (dst_id, label) for all outgoing edges
    from src_bid.
    """
    b = world._bindings[src_bid]
    out: list[tuple[str, str]] = []
    for e in getattr(b, "edges", []):
        out.append((e.get("to"), e.get("label", "")))
    return out


def test_demo_world_now_anchor_shape() -> None:
    """
    The NOW anchor in the demo world should look like what Inspect Binding Details
    will display as a simple anchor with one outgoing edge and no incoming edges.
    """
    world, ids = build_demo_world_for_inspect()
    now_id = ids["NOW"]
    stand_id = ids["stand"]

    assert now_id in world._bindings
    now_binding = world._bindings[now_id]

    # Tags: should contain exactly one anchor tag for NOW
    assert any(t == "anchor:NOW" for t in now_binding.tags)

    # Outgoing: NOW --initiate_stand--> stand
    outgoing = _outgoing_edges(world, now_id)
    assert (stand_id, "initiate_stand") in outgoing

    # No incoming edges to NOW in this demo world
    incoming = _incoming_edges(world, now_id)
    assert incoming == []


def test_demo_world_rest_binding_provenance_and_engrams() -> None:
    """
    The 'rest' binding in the demo world is designed to exercise provenance +
    engram display in Inspect Binding Details.

    It should have:
      - pred:state:resting tag (or equivalent)
      - a meta dict with policy/created_by/created_at/ticks/epoch
      - one engram under column01 with the expected id
      - two incoming edges (from stand and fallen), and no outgoing edges
    """
    world, ids = build_demo_world_for_inspect()
    rest_id = ids["rest"]
    stand_id = ids["stand"]
    fallen_id = ids["fallen"]

    assert rest_id in world._bindings
    rest_binding = world._bindings[rest_id]

    # Tag sanity: something like "pred:state:resting" should be present
    assert any("resting" in t for t in rest_binding.tags), rest_binding.tags

    # Provenance keys used by menu #20's Provenance: line
    meta = rest_binding.meta
    assert meta.get("policy") == "Rest"
    assert meta.get("created_by") == "unit_test" or "demo_world"
    assert meta.get("created_at") == "2025-01-01T00:00:00"
    assert meta.get("ticks") == 42
    assert meta.get("epoch") == 3

    # Engram: we expect a pointer in column01
    assert isinstance(rest_binding.engrams, dict)
    assert "column01" in rest_binding.engrams
    slot_payload = rest_binding.engrams["column01"]
    assert slot_payload.get("id") == "ENG_demo_rest"
    # act should be a float around 0.8
    assert pytest.approx(slot_payload.get("act"), rel=1e-6) == 0.8

    # Edges: two incoming (from stand and fallen), none outgoing
    incoming = _incoming_edges(world, rest_id)
    labels = {(src, lbl) for src, lbl in incoming}
    assert (stand_id, "then") in labels
    assert (fallen_id, "recovered_to") in labels

    outgoing = _outgoing_edges(world, rest_id)
    assert outgoing == []
