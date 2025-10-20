import pytest

W = pytest.importorskip("cca8_world_graph", reason="cca8_world_graph module not found")
C = pytest.importorskip("cca8_controller", reason="cca8_controller module not found")


def _world_and_drives():
    g = W.WorldGraph()
    if hasattr(g, "set_tag_policy"):
        g.set_tag_policy("allow")
    g.ensure_anchor("NOW")
    d = C.Drives(hunger=0.7, fatigue=0.2, warmth=0.6)  # defaults are fine; hunger>0.6
    return g, d


def test_drives_predicates_thresholds():
    """Verify derived drive:* tags from thresholds."""
    d = C.Drives(hunger=0.61, fatigue=0.71, warmth=0.25)
    tags = set(d.predicates())
    assert "drive:hunger_high" in tags
    assert "drive:fatigue_high" in tags
    assert "drive:cold" in tags


def test_action_center_fires_standup_when_hungry_and_not_upright():
    """
    With hunger high and not already upright, StandUp should fire first,
    adding 'posture:standing' and returning status ok.
    """
    g, d = _world_and_drives()
    res = C.action_center_step(g, ctx=None, drives=d)
    assert res["policy"] == "policy:stand_up"
    assert res["status"] == "ok"
    # Confirm standing predicate recorded
    assert any("pred:posture:standing" in b.tags for b in g._bindings.values())


def test_action_center_seeks_nipple_when_already_standing_and_hungry():
    """
    If already upright + hunger high, SeekNipple should fire (comes after StandUp).
    """
    g, d = _world_and_drives()
    # Pre-mark upright so StandUp.trigger() returns False
    g.add_predicate("posture:standing", attach="now")
    res = C.action_center_step(g, ctx=None, drives=d)
    assert res["policy"] == "policy:seek_nipple"
    assert res["status"] == "ok"
    # Should have created seeking predicate
    assert any("pred:seeking_mom" in b.tags for b in g._bindings.values())
