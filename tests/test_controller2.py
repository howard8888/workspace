from cca8_world_graph import WorldGraph
from cca8_controller import Drives, action_center_step, skill_readout
from cca8_run import Ctx

def test_safety_override_standup_and_skill_ledger():
    w = WorldGraph(); w.ensure_anchor("NOW")
    w.add_predicate("state:posture_fallen", attach="latest")
    ctx = Ctx()
    d = Drives()
    res = action_center_step(w, ctx, d)
    assert isinstance(res, dict) and res.get("policy") == "policy:stand_up" and res.get("status") == "ok"
    # ledger registered at least one entry
    assert "policy:stand_up" in skill_readout()

def test_preferred_rest_decreases_fatigue():
    w = WorldGraph(); w.ensure_anchor("NOW")
    ctx = Ctx()
    d = Drives(hunger=0.3, fatigue=0.9, warmth=0.6)
    res = action_center_step(w, ctx, d, preferred="policy:rest")
    assert res.get("policy") == "policy:rest" and res.get("status") == "ok"
    assert d.fatigue <= 0.7  # dropped by 0.2 in Rest.execute
