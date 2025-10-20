import json
import os
import pytest

W = pytest.importorskip("cca8_world_graph", reason="cca8_world_graph module not found")
R = pytest.importorskip("cca8_run", reason="cca8_run module not found")
C = pytest.importorskip("cca8_controller", reason="cca8_controller module not found")


def _quiet(world):
    """Silence lexicon warnings for ad-hoc tokens during tests."""
    if hasattr(world, "set_tag_policy"):
        try:
            world.set_tag_policy("allow")
        except Exception:
            pass


def _build_demo_world():
    """
    Build a small graph with:
      NOW -> A -> B -> goal   (default weights = 1)
      NOW -[5]-> X -[1]-> goal
    And add a tiny engram/meta to exercise serialization.
    """
    g = W.WorldGraph()
    _quiet(g)
    start = g.ensure_anchor("NOW")

    a = g.add_predicate("A", attach="now")          # NOW -> A
    b = g.add_predicate("B", attach="latest")       # A   -> B
    goal = g.add_predicate("goal", attach="latest") # B   -> goal

    x = g.add_predicate("X", attach=None)           # no auto-link
    g.add_edge(start, x, "then", meta={"weight": 5})
    g.add_edge(x, goal, "then", meta={"weight": 1})

    # Add a tiny engram & meta to ensure those fields survive round-trip
    g._bindings[a].engrams["column01"] = {"id": "eng1", "act": 0.7}
    g._bindings[a].meta["note"] = "testmeta"
    return g, start, goal, {"A": a, "B": b, "goal": goal, "X": x}


def test_worldgraph_roundtrip_to_dict_from_dict_generates_same_structure():
    g, start, goal, ids = _build_demo_world()

    # Serialize → dict
    payload = g.to_dict()
    assert "bindings" in payload and "anchors" in payload and "latest" in payload

    # Deserialize → new world
    g2 = W.WorldGraph.from_dict(payload)

    # Anchors preserved
    assert g2._anchors == g._anchors

    # Binding id set preserved
    assert set(g2._bindings.keys()) == set(g._bindings.keys())

    # Tags & a specific edge meta survived
    a = ids["A"]
    x = ids["X"]
    assert g2._bindings[a].tags == g._bindings[a].tags
    assert g2._bindings[a].meta.get("note") == "testmeta"
    assert g2._bindings[a].engrams.get("column01", {}).get("id") == "eng1"

    # Check the weighted edge NOW -> X exists with weight=5
    now = g2._anchors["NOW"]
    outs = [e for e in g2._bindings[now].edges if e.get("to") == x]
    assert outs, "NOW -> X edge missing after round-trip"
    assert outs[0].get("meta", {}).get("weight") == 5

    # Ensure planning still works after round-trip
    path = g2.plan_to_predicate(start, "goal")
    assert path and path[0] == start and path[-1] == goal

    # Optional: ensure new ids won’t collide after from_dict()
    before_ids = set(g2._bindings.keys())
    new_id = g2.add_predicate("C", attach="latest")
    assert new_id not in before_ids, "from_dict() should advance id counter to avoid collisions"


def test_save_session_roundtrip_and_schema(tmp_path):
    g, start, goal, ids = _build_demo_world()
    drives = C.Drives(hunger=0.8, fatigue=0.2, warmth=0.6)

    out = tmp_path / "session.json"
    ts = R.save_session(str(out), g, drives)

    # File exists and tmp file cleaned up
    assert out.exists(), "session.json not written"
    assert not (tmp_path / "session.json.tmp").exists(), "temp file should be replaced atomically"

    # JSON schema sanity
    blob = json.loads(out.read_text(encoding="utf-8"))
    for k in ("saved_at", "world", "drives", "skills", "app_version", "platform"):
        assert k in blob
    assert isinstance(blob["world"], dict) and isinstance(blob["drives"], dict)
    assert isinstance(blob["skills"], dict)
    assert isinstance(blob["saved_at"], str)
    assert blob["app_version"].startswith(f"cca8_run/{R.__version__}")

    # Rehydrate
    g2 = W.WorldGraph.from_dict(blob["world"])
    d2 = C.Drives.from_dict(blob["drives"])

    # Planning still works; drives preserved
    path = g2.plan_to_predicate(start, "goal")
    assert path and path[-1] == ids["goal"]
    assert pytest.approx(d2.hunger, rel=0, abs=1e-9) == 0.8
    assert pytest.approx(d2.fatigue, rel=0, abs=1e-9) == 0.2
    assert pytest.approx(d2.warmth,  rel=0, abs=1e-9) == 0.6

    # Timestamp round-trip matches what save_session returned
    assert blob["saved_at"] == ts
