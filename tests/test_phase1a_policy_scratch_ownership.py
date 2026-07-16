# -*- coding: utf-8 -*-
"""Phase 1A tests for explicit policy-chain Scratch ownership and authority."""

from __future__ import annotations

import cca8_run
import cca8_working_memory
from cca8_column import mem as column_mem
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation
from cca8_world_graph import Edge, WorldGraph

# These focused architecture tests intentionally inspect WorkingMap internals.
# pylint: disable=protected-access,too-many-locals,too-many-statements


def _edge_rows(world: WorldGraph, src: str, label: str, dst: str) -> list[Edge]:
    """Return matching outgoing edge rows from one binding."""
    binding = world._bindings[src]
    return [
        edge
        for edge in binding.edges
        if edge.get("label") == label and edge.get("to") == dst
    ]


def _fallen_selection_world() -> WorldGraph:
    """Return a minimal long-term world that selects the StandUp policy."""
    world = WorldGraph()
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")
    world.add_predicate("posture:fallen", attach="now", meta={"source": "observed"})
    return world


def _working_ctx_with_fallen_evidence() -> Ctx:
    """Return a context whose WorkingMap has the normal MapSurface layer roots."""
    ctx = Ctx()
    ctx.cog_cycles = 7
    ctx.controller_steps = 11
    ctx.working_world = cca8_run.init_working_world()
    cca8_run.inject_obs_into_working_world(
        ctx,
        EnvObservation(predicates=["posture:fallen"], cues=[], env_meta={"scenario_stage": "struggle"}),
    )
    return ctx


def test_policy_scratch_chain_is_owned_without_replacing_wm_root_edge() -> None:
    """StandUp should keep the legacy root edge and gain one Scratch ownership edge."""
    ctx = _working_ctx_with_fallen_evidence()
    working_world = ctx.working_world
    assert working_world is not None

    selection_world = _fallen_selection_world()
    selection_count_before = len(selection_world._bindings)
    column_count_before = column_mem.count()
    before_binding_ids = set(working_world._bindings)

    runtime = cca8_run.PolicyRuntime(cca8_run.CATALOG_GATES)
    runtime.refresh_loaded(ctx)
    fired = runtime.consider_and_maybe_fire(
        selection_world,
        Drives(hunger=0.7, fatigue=0.2, warmth=0.6),
        ctx,
        exec_world=working_world,
    )

    assert fired.startswith("policy:stand_up (added 3 bindings)")
    assert len(selection_world._bindings) == selection_count_before
    assert column_mem.count() == column_count_before

    policy_ids = [
        bid
        for bid, binding in working_world._bindings.items()
        if binding.meta.get("policy") == "policy:stand_up"
    ]
    assert len(policy_ids) == 3

    chain_head = next(
        bid
        for bid in policy_ids
        if "action:push_up" in working_world._bindings[bid].tags
    )
    chain_tail = next(
        bid
        for bid in policy_ids
        if "pred:posture:standing" in working_world._bindings[bid].tags
    )

    root_bid = working_world._anchors["WM_ROOT"]
    scratch_bid = working_world._anchors["WM_SCRATCH"]

    # Compatibility decision: keep the original WM_ROOT -> policy chain edge.
    assert len(_edge_rows(working_world, root_bid, "then", chain_head)) == 1
    ownership_edges = _edge_rows(working_world, scratch_bid, "wm_scratch_item", chain_head)
    assert len(ownership_edges) == 1

    owner_meta = ownership_edges[0]["meta"]
    assert owner_meta["schema"] == "wm_policy_scratch_owner_v1"
    assert owner_meta["scratch_id"] == f"scratch:{chain_head}"
    assert owner_meta["owner"] == "WM_SCRATCH"
    assert owner_meta["kind"] == "policy_chain"
    assert owner_meta["created_cycle"] == 7
    assert owner_meta["created_controller_step"] == 11
    assert owner_meta["status"] == "unconfirmed"
    assert owner_meta["chain_head"] == chain_head
    assert owner_meta["chain_tail"] == chain_tail
    assert owner_meta["cleanup_policy"] == "retain_until_explicit_cleanup"
    assert owner_meta["source"] == "expected"
    assert owner_meta["source_primitive"] == "policy:stand_up"
    assert owner_meta["source_authority"] == "low"
    assert owner_meta["safety_weight"] == "normal"

    head_binding = working_world._bindings[chain_head]
    head_meta = head_binding.meta
    assert head_meta["scratch_id"] == f"scratch:{chain_head}"
    assert head_meta["owner"] == "WM_SCRATCH"
    assert head_meta["workspace_layer"] == "scratch"
    assert head_meta["kind"] == "policy_action"
    assert head_meta["status"] == "executed"
    assert head_meta["source_primitive"] == "policy:stand_up"
    assert "wm:scratch_item" in head_binding.tags
    assert "wm:scratch:policy_chain" in head_binding.tags

    tail_binding = working_world._bindings[chain_tail]
    tail_meta = tail_binding.meta
    assert tail_meta["owner"] == "WM_SCRATCH"
    assert tail_meta["workspace_layer"] == "scratch"
    assert tail_meta["kind"] == "expected_terminal"
    assert tail_meta["layer"] == "expected"
    assert tail_meta["source"] == "expected"
    assert tail_meta["source_authority"] == "low"
    assert tail_meta["authority"] == "expected"
    assert tail_meta["status"] == "unconfirmed"
    assert tail_meta["confirmation"] == "unconfirmed"
    assert tail_meta["safety_weight"] == "normal"
    assert "wm:expected" in tail_binding.tags
    assert "wm:unconfirmed" in tail_binding.tags

    # The observed MapSurface posture remains evidence and is not relabeled by registration.
    self_bid = ctx.wm_entities["self"]
    observed_binding = working_world._bindings[self_bid]
    assert "pred:posture:fallen" in observed_binding.tags
    assert observed_binding.meta.get("owner") != "WM_SCRATCH"
    assert observed_binding.meta.get("source") != "expected"

    # Re-registering the same binding delta is idempotent.
    summary = cca8_working_memory.register_policy_scratch_chain_v1(
        ctx,
        working_world,
        before_binding_ids=before_binding_ids,
        policy_name="policy:stand_up",
        policy_result={"policy": "policy:stand_up", "status": "ok", "binding": chain_tail},
    )
    assert summary["registered"] is True
    assert summary["expected_terminal"] == chain_tail
    assert len(_edge_rows(working_world, scratch_bid, "wm_scratch_item", chain_head)) == 1


def test_action_only_policy_chain_does_not_gain_expected_terminal_authority() -> None:
    """An action-only policy trace should be owned by Scratch without a false state claim."""
    ctx = Ctx()
    ctx.cog_cycles = 3
    ctx.controller_steps = 5
    ctx.working_world = cca8_run.init_working_world()
    working_world = ctx.working_world

    root_bid = working_world.ensure_anchor("WM_ROOT")
    working_world.set_now(root_bid, tag=True, clean_previous=True)
    scratch_bid = working_world.ensure_anchor("WM_SCRATCH")
    cca8_working_memory._wm_tagset_of(working_world, scratch_bid).add("wm:scratch")
    cca8_working_memory._wm_upsert_edge(working_world, root_bid, scratch_bid, "wm_scratch")

    before_binding_ids = set(working_world._bindings)
    action_bid = working_world.add_action(
        "suckle",
        attach="now",
        meta={"policy": "policy:suckle"},
    )

    summary = cca8_working_memory.register_policy_scratch_chain_v1(
        ctx,
        working_world,
        before_binding_ids=before_binding_ids,
        policy_name="policy:suckle",
        policy_result={"policy": "policy:suckle", "status": "ok", "binding": action_bid},
    )

    assert summary["registered"] is True
    assert summary["expected_terminal"] is None
    action_binding = working_world._bindings[action_bid]
    assert action_binding.meta["kind"] == "policy_action"
    assert action_binding.meta["status"] == "executed"
    assert action_binding.meta.get("authority") != "expected"
    assert "wm:expected" not in action_binding.tags

    ownership_edges = _edge_rows(working_world, scratch_bid, "wm_scratch_item", action_bid)
    assert len(ownership_edges) == 1
    assert "source" not in ownership_edges[0]["meta"]
    assert len(_edge_rows(working_world, root_bid, "then", action_bid)) == 1


def test_policy_execution_on_worldgraph_does_not_create_scratch_ownership() -> None:
    """Default execution should remain a WorldGraph policy trace, not WorkingMap Scratch."""
    ctx = Ctx()
    ctx.working_world = cca8_run.init_working_world()
    working_ids_before = set(ctx.working_world._bindings)

    world = _fallen_selection_world()
    runtime = cca8_run.PolicyRuntime(cca8_run.CATALOG_GATES)
    runtime.refresh_loaded(ctx)
    fired = runtime.consider_and_maybe_fire(world, Drives(), ctx)

    assert fired.startswith("policy:stand_up (added 3 bindings)")
    assert "WM_SCRATCH" not in world._anchors
    assert all(binding.meta.get("owner") != "WM_SCRATCH" for binding in world._bindings.values())
    assert set(ctx.working_world._bindings) == working_ids_before


def test_prediction_source_uses_actual_execution_target() -> None:
    """An omitted execution override must not be mislabeled as WorkingMap Scratch."""
    ctx = Ctx()
    ctx.working_world = cca8_run.init_working_world()
    world = WorldGraph()

    assert (
        cca8_run.prediction_source_for_execution_target_v1(ctx, world, exec_world=ctx.working_world)
        == "WorkingMap.Scratch"
    )
    assert cca8_run.prediction_source_for_execution_target_v1(ctx, world) == "WorldGraph.policy_trace"
    assert (
        cca8_run.prediction_source_for_execution_target_v1(ctx, world, exec_world=world)
        == "WorldGraph.policy_trace"
    )


def test_runner_exposes_the_working_memory_registration_helper() -> None:
    """The historical runner facade should expose the Working Memory-owned helper."""
    assert cca8_run.register_policy_scratch_chain_v1 is cca8_working_memory.register_policy_scratch_chain_v1
