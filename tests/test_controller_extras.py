import pytest
W = pytest.importorskip("cca8_world_graph")
C = pytest.importorskip("cca8_controller")

def _quiet(w):
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")

def test_skills_roundtrip_update():
    # Run StandUp once to record a success
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    d = C.Drives(hunger=0.8)  # hungry so StandUp may fire
    res = C.action_center_step(w, ctx=None, drives=d)
    sd = C.skills_to_dict()
    assert isinstance(sd, dict)
    # Clear and rebuild
    C.skills_from_dict(sd)
    txt = C.skill_readout()
    assert "policy:" in txt

def test_action_center_safety_recovery_on_fall():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    # Emit fallen state near NOW
    fallen = w.add_predicate("state:posture_fallen", attach="now")
    d = C.Drives(hunger=0.7)
    res = C.action_center_step(w, ctx=None, drives=d)
    assert isinstance(res, dict) and res.get("policy") in {"policy:stand_up", None}
