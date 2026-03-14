from __future__ import annotations

import cca8_world_graph
from cca8_column import mem as column_mem
from cca8_features import FactMeta
from cca8_run import (
    Ctx,
    format_mapswitch_event_line_v1,
    init_working_world,
    load_mapsurface_payload_v1_into_workingmap,
    maybe_autoretrieve_mapsurface_on_keyframe,
)


_TEST_STAGE = "__mapswitch_test_stage_v1__"
_TEST_ZONE = "__mapswitch_test_zone_v1__"


def _mapsurface_payload(*, mom_near: bool, cue_name: str) -> dict:
    """Build a tiny wm_mapsurface_v1 payload for retrieval tests."""
    mom_pred = "proximity:mom:near" if mom_near else "proximity:mom:far"
    dist_m = 1.0 if mom_near else 4.0
    dist_class = "near" if mom_near else "far"

    return {
        "schema": "wm_mapsurface_v1",
        "entities": [
            {
                "eid": "self",
                "kind": "self",
                "preds": ["posture:standing"],
                "cues": [],
                "pos": {"x": 0.0, "y": 0.0, "frame": "wm_schematic_v1"},
            },
            {
                "eid": "mom",
                "kind": "social",
                "preds": [mom_pred],
                "cues": [cue_name],
                "pos": {"x": 1.0, "y": 0.0, "frame": "wm_schematic_v1"},
                "dist_m": dist_m,
                "dist_class": dist_class,
            },
        ],
        "relations": [
            {
                "src": "self",
                "dst": "mom",
                "rel": "distance_to",
                "meters": dist_m,
                "class": dist_class,
                "frame": "wm_schematic_v1",
            }
        ],
    }


def _store_mapsurface_record(payload: dict, *, stage: str, zone: str, salient_preds: list[str], salient_cues: list[str]) -> str:
    """Store one wm_mapsurface record with deterministic retrieval attrs."""
    fm = FactMeta(
        name="wm_mapsurface",
        links=[],
        attrs={
            "stage": stage,
            "zone": zone,
            "sig": f"sig_{stage}_{zone}_{len(salient_preds)}_{len(salient_cues)}",
            "salience_sig": f"sal_{stage}_{zone}_{len(salient_preds)}_{len(salient_cues)}",
            "salient_preds": list(salient_preds),
            "salient_cues": list(salient_cues),
        },
    )
    return column_mem.assert_fact("wm_mapsurface", payload, fm)


def test_mapswitch_event_logging_records_candidates_choice_and_guardrail() -> None:
    """Auto-retrieve should log candidates, chosen seed, exclusion drop reason, and cue guardrail status."""
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.wm_mapsurface_autoretrieve_enabled = True
    ctx.wm_mapswitch_history_limit = 10

    long_world = cca8_world_graph.WorldGraph()
    long_world.set_tag_policy("allow")
    long_world.ensure_anchor("NOW")

    # Current WM salience prefers the "mom near" candidate.
    cur_payload = _mapsurface_payload(mom_near=True, cue_name="silhouette:mom")
    load_mapsurface_payload_v1_into_workingmap(ctx, cur_payload, replace=True, reason="test_current_seed")

    eids: list[str] = []
    try:
        eid_best = _store_mapsurface_record(
            _mapsurface_payload(mom_near=True, cue_name="silhouette:mom"),
            stage=_TEST_STAGE,
            zone=_TEST_ZONE,
            salient_preds=["proximity:mom:near"],
            salient_cues=["silhouette:mom"],
        )
        eids.append(eid_best)

        eid_other = _store_mapsurface_record(
            _mapsurface_payload(mom_near=False, cue_name="odor:hay"),
            stage=_TEST_STAGE,
            zone=_TEST_ZONE,
            salient_preds=["proximity:mom:far"],
            salient_cues=["odor:hay"],
        )
        eids.append(eid_other)

        out = maybe_autoretrieve_mapsurface_on_keyframe(
            long_world,
            ctx,
            stage=_TEST_STAGE,
            zone=_TEST_ZONE,
            exclude_engram_id=eid_best,
            reason="auto_test_boundary",
            mode="merge",
            top_k=5,
            log=False,
        )

        assert out["ok"] is True
        event = out.get("event")
        assert isinstance(event, dict)
        assert event["schema"] == "wm_mapswitch_event_v1"
        assert event["candidate_count"] == 2
        assert event["drop_reason"] == "excluded_current_snapshot"

        chosen = event.get("chosen_seed")
        assert isinstance(chosen, dict)
        assert chosen["engram_id"] == eid_other
        assert event["chosen_rank"] == 2

        load = event.get("load")
        assert isinstance(load, dict)
        assert load["mode"] == "merge"
        assert load["merge_guardrail_ok"] is True
        assert load["cue_tag_delta"] == 0

        assert isinstance(ctx.wm_mapswitch_last_events, list) and ctx.wm_mapswitch_last_events
        assert ctx.wm_mapswitch_last_events[-1]["chosen_seed"]["engram_id"] == eid_other

        line = format_mapswitch_event_line_v1(event)
        assert "ok" in line
        assert "cand_n=2" in line
        assert "drop=excluded_current_snapshot" in line
        assert "cue_guard=ok" in line
    finally:
        for eid in eids:
            try:
                column_mem.delete(eid)
            except Exception:
                pass


def test_mapswitch_event_logging_records_no_candidate_noop() -> None:
    """When no matching wm_mapsurface records exist, the no-op should still be logged as an event."""
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.wm_mapsurface_autoretrieve_enabled = True

    long_world = cca8_world_graph.WorldGraph()
    long_world.set_tag_policy("allow")
    long_world.ensure_anchor("NOW")

    out = maybe_autoretrieve_mapsurface_on_keyframe(
        long_world,
        ctx,
        stage="__mapswitch_none_stage__",
        zone="__mapswitch_none_zone__",
        exclude_engram_id=None,
        reason="auto_test_none",
        mode="merge",
        top_k=5,
        log=False,
    )

    assert out["ok"] is False
    assert out["why"] == "no_candidates"

    event = out.get("event")
    assert isinstance(event, dict)
    assert event["schema"] == "wm_mapswitch_event_v1"
    assert event["ok"] is False
    assert event["why"] == "no_candidates"
    assert event["candidate_count"] == 0
    assert event["chosen_seed"] is None
    assert event["drop_reason"] == "no_candidates"

    line = format_mapswitch_event_line_v1(event)
    assert "skip" in line
    assert "why=no_candidates" in line
    assert "cand_n=0" in line
