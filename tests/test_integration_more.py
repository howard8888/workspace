import json
import importlib
from typing import List

import pytest

import cca8_world_graph as wgmod
from cca8_controller import Drives, action_center_step
import cca8_run as runmod


def _has_tag(world: wgmod.WorldGraph, tag: str) -> bool:
    for b in world._bindings.values():  # pylint: disable=protected-access
        ts = getattr(b, "tags", set())
        if tag in ts:
            return True
    return False


def test_add_predicate_attach_now_forwards_meta_and_edge():
    world = wgmod.WorldGraph()
    meta = {"policy": "policy:test", "created_at": "2025-01-01T00:00:00"}
    bid = world.add_predicate("state:resting", attach="now", meta=meta)
    now_id = world.ensure_anchor("NOW")
    edges = [e for e in world._bindings[now_id].edges if e.get("to") == bid]  # pylint: disable=protected-access
    assert edges, "Expected an auto edge from NOW to the new binding"
    e = edges[0]
    assert e.get("label") == "then"
    assert isinstance(e.get("meta"), dict) and e["meta"].get("policy") == "policy:test"


def test_add_predicate_attach_latest_links_previous_latest():
    world = wgmod.WorldGraph()
    meta = {"who": "tester"}
    a = world.add_predicate("state:posture_standing", attach="now", meta=meta)
    b = world.add_predicate("state:alert", attach="latest", meta=meta)
    edges = [e for e in world._bindings[a].edges if e.get("to") == b]  # pylint: disable=protected-access
    assert edges, "Expected an auto edge from previous latest to the new binding"
    assert edges[0].get("label") == "then"
    assert isinstance(edges[0].get("meta"), dict) and edges[0]["meta"].get("who") == "tester"


def test_set_now_moves_anchor_tag_and_pointer():
    world = wgmod.WorldGraph()
    a = world.add_predicate("state:posture_standing", attach="now")
    b = world.add_predicate("state:alert", attach="latest")
    world.ensure_anchor("NOW")
    world.set_now(b, tag=True, clean_previous=True)
    assert world.ensure_anchor("NOW") == b
    assert "anchor:NOW" not in world._bindings[a].tags  # pylint: disable=protected-access
    assert "anchor:NOW" in world._bindings[b].tags      # pylint: disable=protected-access


def test_plan_to_predicate_bfs_from_now():
    world = wgmod.WorldGraph()
    _ = world.add_predicate("state:posture_standing", attach="now")
    t2 = world.add_predicate("state:resting", attach="latest")
    src = world.ensure_anchor("NOW")
    path = world.plan_to_predicate(src, "state:resting")
    assert path and path[0] == src and path[-1] == t2


def test_world_to_dict_from_dict_roundtrip_preserves_edges_and_meta():
    world = wgmod.WorldGraph()
    m = {"policy": "policy:test", "created_at": "2025-01-01T00:00:00"}
    a = world.add_predicate("state:posture_standing", attach="now", meta=m)
    b = world.add_predicate("state:alert", attach="latest", meta=m)

    # explicit action edge with meta
    world.add_edge(b, a, "look_around", meta={"k": "v"})

    # round-trip
    snap = world.to_dict()
    restored = wgmod.WorldGraph.from_dict(snap)

    # anchors + latest preserved
    assert restored._anchors["NOW"] == world._anchors["NOW"]                      # pylint: disable=protected-access
    assert restored._latest_binding_id == world._latest_binding_id                # pylint: disable=protected-access

    # tags + action label preserved
    assert _has_tag(restored, "pred:state:alert")
    assert "look_around" in restored.list_actions(include_then=True)


def test_runner_world_delete_edge_helper_removes_per_binding_edges():
    world = wgmod.WorldGraph()
    a = world.add_predicate("state:posture_standing", attach="now")
    b = world.add_predicate("state:resting", attach="latest")
    now_id = world.ensure_anchor("NOW")
    assert any(e.get("to") == a for e in world._bindings[now_id].edges)          # pylint: disable=protected-access
    assert any(e.get("to") == b for e in world._bindings[a].edges)               # pylint: disable=protected-access
    removed = runmod.world_delete_edge(world, a, b, "then")
    assert removed >= 1
    assert not any(e.get("to") == b for e in world._bindings[a].edges)           # pylint: disable=protected-access


def test_controller_action_center_safety_override_triggers_standup():
    world = wgmod.WorldGraph()
    world.add_predicate("state:posture_fallen", attach="now")
    drives = Drives()
    ctx = getattr(runmod, "Ctx", None)()
    payload = action_center_step(world, ctx, drives)
    assert payload.get("policy") == "policy:stand_up"
    assert _has_tag(world, "pred:state:posture_standing") or _has_tag(world, "pred:posture:standing")


def test_controller_seeking_when_upright_and_hungry():
    world = wgmod.WorldGraph()
    world.add_predicate("state:posture_standing", attach="now")
    drives = Drives()  # hunger=0.7 by default
    ctx = getattr(runmod, "Ctx", None)()
    payload = action_center_step(world, ctx, drives)
    assert payload.get("policy") == "policy:seek_nipple"
    assert _has_tag(world, "pred:state:seeking_mom") or _has_tag(world, "pred:seeking_mom")


def test_runner_save_session_writes_json(tmp_path):
    world = wgmod.WorldGraph()
    drives = Drives()
    ctx = getattr(runmod, "Ctx", None)()
    action_center_step(world, ctx, drives)  # populate skill ledger
    path = tmp_path / "session.json"
    ts = runmod.save_session(str(path), world, drives)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(ts, str) and ts
    assert "saved_at" in data and "world" in data and "drives" in data and "skills" in data
    assert isinstance(data["skills"], dict) and data["skills"]
