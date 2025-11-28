# -*- coding: utf-8 -*-
"""
Small helper module for building deterministic test worlds.
This "Test Worlds" module help to build ahead a test world for you to experiment with.

These helpers are intended for:
- Unit tests (pytest) exercising WorldGraph and menu 20 / inspect-binding.
- Manual experiments in a REPL.

They are deliberately tiny so you can see the whole layout at a glance.
"""

from __future__ import annotations

from typing import Dict, Tuple
from cca8_world_graph import WorldGraph


__version__ = "0.1.0"
__all__ = ["__version__"]


def build_demo_world_for_inspect() -> Tuple[WorldGraph, Dict[str, str]]:
    """
    Build a small, deterministic WorldGraph for inspection / graph tests.

    Layout (ids are deterministic but we also return them in a dict):

      Anchors
      -------
      - NOW : "current time" anchor
      - HERE: "current location" anchor (left disconnected on purpose)

      Predicates / cues
      -----------------
      - stand      : pred:stand
      - fallen     : pred:posture:fallen
      - cue_mom    : pred:vision:silhouette:mom (used like a cue)
      - rest       : pred:state:resting (example of policy-created binding)

      Edges (roughly)
      ----------------
      - NOW  --initiate_stand--> stand        (boot-time link)
      - NOW  --then-->            fallen      (second boot-time link)
      - cue_mom --supports-->     stand       (cue supports standing)
      - stand   --then-->         rest        (after standing, agent can rest)
      - fallen  --recovered_to--> rest        (after a fall, agent recovers to rest)

      Provenance / engrams
      ---------------------
      - stand, fallen, cue_mom:
            meta["boot"] = "test_world", meta["added_by"] = "system"
      - rest:
            meta contains policy / created_by / created_at / ticks / epoch
            and one engram pointer in column01 with a demo id.

    Returns
    -------
    world : WorldGraph
        The populated world instance.
    ids : dict[str, str]
        Mapping of human-friendly keys -> binding ids, e.g. ids["NOW"], ids["stand"].
    """
    world = WorldGraph()

    # Anchors
    now_id = world.ensure_anchor("NOW")
    here_id = world.ensure_anchor("HERE")  # intentionally left with no edges

    # Boot-time predicates
    boot_meta = {"boot": "test_world", "added_by": "system"}

    b_stand = world.add_predicate("stand", attach=None, meta=boot_meta)
    b_fallen = world.add_predicate("posture:fallen", attach=None, meta=boot_meta)
    b_cue_mom = world.add_predicate("vision:silhouette:mom", attach="now", meta=boot_meta)

    # Boot-time edges from NOW
    world.add_edge(now_id, b_stand, "initiate_stand", meta={"boot": "test_world"})
    world.add_edge(now_id, b_fallen, "then", meta={"boot": "test_world"})

    # Cue influences standing
    world.add_edge(b_cue_mom, b_stand, "supports", meta={"created_by": "test_world"})

    # Runtime "rest" predicate with richer provenance
    rest_meta = {
        "policy": "Rest",
        "created_by": "demo_world",
        "created_at": "2025-01-01T00:00:00",
        "ticks": 42,
        "epoch": 3,
    }
    b_rest = world.add_predicate("state:resting", attach="latest", meta=rest_meta)

    # Attach a demo engram pointer (OK if column storage doesn't know this id yet)
    world.attach_engram(
        b_rest,
        column="column01",
        engram_id="ENG_demo_rest",
        act=0.8,
        extra_meta={"note": "demo"},
    )

    # Connect rest into the episode flow
    world.add_edge(b_stand, b_rest, "then", meta={"created_by": "unit_test"})
    world.add_edge(b_fallen, b_rest, "recovered_to", meta={"created_by": "unit_test"})

    ids: Dict[str, str] = {
        "NOW": now_id,
        "HERE": here_id,
        "stand": b_stand,
        "fallen": b_fallen,
        "cue_mom": b_cue_mom,
        "rest": b_rest,
    }
    return world, ids
