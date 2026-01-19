# -*- coding: utf-8 -*-
"""
Unit tests for the WorkingMap.MapSurface memory pipeline (Option B).

What I am testing here (the invariants that are easy to regress later):
  1) WM -> Column: storing a MapSurface snapshot creates BOTH:
       - a Column engram record (name="wm_mapsurface")
       - a thin WorldGraph pointer binding tagged cue:wm:mapsurface_snapshot with binding.engrams["column01"]["id"]
  2) Retrieval uses WorldGraph pointers (not only column scans) when pointers exist.
  3) Merge/seed is conservative:
       - never overwrites an existing slot-family (e.g., hazard:cliff:* already set)
       - does NOT inject cue:* tags (cues mean "present now"); cues must stay as prior_cues in meta
  4) Ranking: higher salience overlap beats recency when multiple candidates match the same (stage, zone).
"""

from __future__ import annotations

import cca8_world_graph
from cca8_column import mem as column_mem

from cca8_run import (
    Ctx,
    init_body_world,
    update_body_world_from_obs,
    load_mapsurface_payload_v1_into_workingmap,
    merge_mapsurface_payload_v1_into_workingmap,
    store_mapsurface_snapshot_v1,
    _iter_newest_wm_mapsurface_recs,
    pick_best_wm_mapsurface_rec,
)


class _ObsStub:
    """Minimal EnvObservation-ish stub: only .predicates is required for BodyMap update."""
    def __init__(self, predicates: list[str]):
        self.predicates = predicates


def setup_function(_fn) -> None:
    # ColumnMemory is in-RAM for this process; clear between tests so IDs/results are deterministic.
    column_mem._store.clear()  # pylint: disable=protected-access


def teardown_function(_fn) -> None:
    column_mem._store.clear()  # pylint: disable=protected-access


def _make_world() -> cca8_world_graph.WorldGraph:
    w = cca8_world_graph.WorldGraph()
    w.set_tag_policy("allow")     # avoid lexicon warnings during tests
    w.set_stage("neonate")
    w.ensure_anchor("NOW")
    return w


def _make_ctx(*, stage: str = "rest", zone: str = "safe") -> Ctx:
    """
    Build a minimal ctx with a fresh BodyMap so body_space_zone(ctx) works in store_mapsurface_snapshot_v1.
    zone ∈ {"safe","unsafe_cliff_near"} is produced by (shelter, cliff) distances.
    """
    ctx = Ctx()
    ctx.controller_steps = 1
    ctx.lt_obs_last_stage = stage

    ctx.body_world, ctx.body_ids = init_body_world()

    if zone == "unsafe_cliff_near":
        preds = [
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:far",
            "hazard:cliff:near",
        ]
    else:
        preds = [
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ]

    update_body_world_from_obs(ctx, _ObsStub(preds))
    return ctx


def _payload_mapsurface(*, cliff: str, mom_cue: bool, self_preds: list[str]) -> dict:
    """
    Construct a wm_mapsurface_v1-like payload for loader tests.
    This is intentionally small and JSON-safe.
    """
    mom_cues = ["vision:silhouette:mom"] if mom_cue else []
    return {
        "schema": "wm_mapsurface_v1",
        "header": {"schema": "wm_mapsurface_v1"},
        "entities": [
            {
                "eid": "self",
                "kind": "agent",
                "pos": {"x": 0.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": 0.0,
                "dist_class": "self",
                "last_seen_step": 0,
                "preds": list(self_preds),
                "cues": [],
            },
            {
                "eid": "cliff",
                "kind": "hazard",
                "pos": {"x": 5.0, "y": 1.0, "frame": "wm_schematic_v1"},
                "dist_m": 5.0,
                "dist_class": "far" if cliff.endswith(":far") else "near",
                "last_seen_step": 0,
                "preds": [cliff],
                "cues": [],
            },
            {
                "eid": "mom",
                "kind": "agent",
                "pos": {"x": 1.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": 1.0,
                "dist_class": "close",
                "last_seen_step": 0,
                "preds": ["proximity:mom:close"],
                "cues": mom_cues,
            },
            {
                "eid": "shelter",
                "kind": "shelter",
                "pos": {"x": 2.0, "y": -1.0, "frame": "wm_schematic_v1"},
                "dist_m": 1.2,
                "dist_class": "near",
                "last_seen_step": 0,
                "preds": ["proximity:shelter:near"],
                "cues": [],
            },
        ],
        "relations": [
            {"rel": "distance_to", "src": "self", "dst": "mom", "meters": 1.0, "class": "close", "frame": "wm_schematic_v1"},
            {"rel": "distance_to", "src": "self", "dst": "shelter", "meters": 1.2, "class": "near", "frame": "wm_schematic_v1"},
            {"rel": "distance_to", "src": "self", "dst": "cliff", "meters": 5.0, "class": "far", "frame": "wm_schematic_v1"},
        ],
    }


def test_store_creates_pointer_and_engram_and_world_pointer_source() -> None:
    world = _make_world()
    ctx = _make_ctx(stage="rest", zone="safe")

    payload = _payload_mapsurface(
        cliff="hazard:cliff:far",
        mom_cue=True,
        self_preds=["resting", "posture:standing", "nipple:latched", "milk:drinking"],
    )
    load_mapsurface_payload_v1_into_workingmap(ctx, payload, replace=True, reason="pytest_seed")

    info = store_mapsurface_snapshot_v1(world, ctx, reason="pytest_store", attach="now", quiet=True)
    assert info.get("stored") is True
    bid = info["bid"]
    eid = info["engram_id"]

    # Column record exists
    rec = column_mem.try_get(eid)
    assert isinstance(rec, dict)
    assert rec.get("name") == "wm_mapsurface"

    # Pointer binding exists and carries engram pointer
    b = world._bindings.get(bid)
    assert b is not None
    assert "cue:wm:mapsurface_snapshot" in (getattr(b, "tags", set()) or set())
    assert isinstance(getattr(b, "engrams", None), dict)
    assert b.engrams["column01"]["id"] == eid  # type: ignore[index]

    # Retrieval helper should prefer world pointers when available
    recs, src = _iter_newest_wm_mapsurface_recs(long_world=world, limit=50)
    assert src == "world_pointers"
    assert recs and recs[0].get("id") == eid


def test_merge_does_not_inject_cue_tags_and_does_not_overwrite_slot_family() -> None:
    ctx = _make_ctx(stage="rest", zone="safe")

    # Current WM says cliff FAR and mom has NO cue tag.
    cur = _payload_mapsurface(
        cliff="hazard:cliff:far",
        mom_cue=False,
        self_preds=["resting", "posture:standing"],
    )
    load_mapsurface_payload_v1_into_workingmap(ctx, cur, replace=True, reason="pytest_cur")

    mom_bid = ctx.wm_entities["mom"]
    cliff_bid = ctx.wm_entities["cliff"]

    mom_tags_before = set(ctx.working_world._bindings[mom_bid].tags)  # pylint: disable=protected-access
    cliff_tags_before = set(ctx.working_world._bindings[cliff_bid].tags)  # pylint: disable=protected-access
    assert "cue:vision:silhouette:mom" not in mom_tags_before
    assert "pred:hazard:cliff:far" in cliff_tags_before

    # Prior engram says cliff NEAR and includes a mom cue.
    prior = _payload_mapsurface(
        cliff="hazard:cliff:near",
        mom_cue=True,
        self_preds=["resting", "posture:standing"],
    )
    out = merge_mapsurface_payload_v1_into_workingmap(ctx, prior, reason="pytest_merge")
    assert out.get("ok") is True

    # Merge must NOT inject cue:* tags.
    mom_tags_after = set(ctx.working_world._bindings[mom_bid].tags)  # pylint: disable=protected-access
    assert "cue:vision:silhouette:mom" not in mom_tags_after
    assert mom_tags_after.issuperset(mom_tags_before)

    # Merge must NOT overwrite an existing slot-family (hazard:cliff).
    cliff_tags_after = set(ctx.working_world._bindings[cliff_bid].tags)  # pylint: disable=protected-access
    assert "pred:hazard:cliff:far" in cliff_tags_after
    assert "pred:hazard:cliff:near" not in cliff_tags_after


def test_picker_prefers_higher_overlap_over_newer_when_stage_zone_match() -> None:
    world = _make_world()
    ctx = _make_ctx(stage="rest", zone="safe")

    # A (older) has richer salient preds.
    a = _payload_mapsurface(
        cliff="hazard:cliff:far",
        mom_cue=True,
        self_preds=["resting", "posture:standing", "nipple:latched", "milk:drinking"],
    )
    load_mapsurface_payload_v1_into_workingmap(ctx, a, replace=True, reason="pytest_A")
    ida = store_mapsurface_snapshot_v1(world, ctx, reason="A", attach="now", quiet=True)["engram_id"]

    # B (newer) is missing nipple/milk preds (lower salience overlap).
    b = _payload_mapsurface(
        cliff="hazard:cliff:far",
        mom_cue=True,
        self_preds=["resting", "posture:standing"],
    )
    load_mapsurface_payload_v1_into_workingmap(ctx, b, replace=True, reason="pytest_B")
    _idb = store_mapsurface_snapshot_v1(world, ctx, reason="B", attach="now", quiet=True)["engram_id"]

    # Current WM resembles A; picker should choose A even though B is newer.
    load_mapsurface_payload_v1_into_workingmap(ctx, a, replace=True, reason="pytest_wantA")
    info = pick_best_wm_mapsurface_rec(stage="rest", zone="safe", ctx=ctx, long_world=world, allow_fallback=True, top_k=5)

    assert info.get("ok") is True
    rec = info.get("rec")
    assert isinstance(rec, dict)
    assert rec.get("id") == ida
    assert info.get("source") == "world_pointers"


def test_autoretrieve_skips_excluded_engram_id_and_merges_prior():
    import cca8_world_graph
    from cca8_column import mem as column_mem
    from cca8_run import (
        Ctx,
        init_body_world,
        init_working_world,
        update_body_world_from_obs,
        inject_obs_into_working_world,
        store_mapsurface_snapshot_v1,
        maybe_autoretrieve_mapsurface_on_keyframe,
    )

    # Keep this test isolated
    column_mem._store.clear()

    world = cca8_world_graph.WorldGraph()
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")

    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.working_world = init_working_world()
    ctx.working_enabled = True
    ctx.working_mapsurface = True
    ctx.wm_mapsurface_autoretrieve_enabled = True
    ctx.wm_mapsurface_autoretrieve_verbose = False

    class _Obs:  # minimal EnvObservation-like stub
        def __init__(self, predicates, cues=None, env_meta=None):
            self.predicates = predicates
            self.cues = cues or []
            self.env_meta = env_meta or {}
            self.raw_sensors = {}

    preds = [
        "resting",
        "proximity:mom:close",
        "proximity:shelter:near",
        "hazard:cliff:far",
        "nipple:latched",
        "milk:drinking",
    ]
    cues = ["vision:silhouette:mom"]
    obs = _Obs(preds, cues, {"scenario_stage": "rest"})

    # Make stage/zone available for storage + retrieval
    ctx.lt_obs_last_stage = "rest"
    update_body_world_from_obs(ctx, obs)
    inject_obs_into_working_world(ctx, obs)

    # Snapshot #1 (baseline)
    s1 = store_mapsurface_snapshot_v1(world, ctx, reason="t1", attach="now", force=True, quiet=True)
    assert s1.get("stored")
    eid1 = s1.get("engram_id")
    assert isinstance(eid1, str) and eid1

    # Modify WM slightly to make a distinct snapshot (#2)
    self_bid = ctx.wm_entities.get("self")
    assert isinstance(self_bid, str)
    bself = ctx.working_world._bindings.get(self_bid)  # pylint: disable=protected-access
    tags = getattr(bself, "tags", None)
    assert isinstance(tags, set)
    tags.add("pred:alert")  # salient exact token; changes sig + salience

    s2 = store_mapsurface_snapshot_v1(world, ctx, reason="t2", attach="now", force=True, quiet=True)
    assert s2.get("stored")
    eid2 = s2.get("engram_id")
    assert isinstance(eid2, str) and eid2 and eid2 != eid1

    # Auto-retrieve should skip excluded eid2 and pick eid1
    out = maybe_autoretrieve_mapsurface_on_keyframe(
        world,
        ctx,
        stage="rest",
        zone="safe",
        exclude_engram_id=eid2,
        reason="test_autoretrieve",
        top_k=5,
    )
    assert out.get("ok") is True
    assert out.get("engram_id") == eid1

