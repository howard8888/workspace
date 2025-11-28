# -*- coding: utf-8 -*-
from datetime import datetime
import cca8_controller as ctrl

class Binding:
    def __init__(self, bid: str, token: str, meta=None):
        self.id = bid
        self.tags = {f"pred:{token}"}
        self.meta = dict(meta or {})

class FakeWorld:
    def __init__(self):
        self._bindings = {}
        self._id = 0
    def _next(self):
        self._id += 1
        return f"b{self._id}"
    def add_predicate(self, token: str, attach: str = "now", meta=None):
        bid = self._next()
        self._bindings[bid] = Binding(bid, token, meta)
        return bid
    def add_edge(self, src, dst, label="then", meta=None):
        return (src, dst, label, meta or {})

class DummyCtx:
    age_days = 1.0

def _has_tag(world, token):
    want = f"pred:{token}"
    return any(want in b.tags for b in world._bindings.values())

def test_standup_writes_canonical_state_tag():
    world = FakeWorld()
    d = ctrl.Drives()
    ctx = DummyCtx()
    pol = ctrl.StandUp()
    assert pol.trigger(world, d)
    res = pol.execute(world, ctx, d)
    assert res["status"] == "ok"
    assert res["policy"] == "policy:stand_up"
    # Canonical posture token should be present.
    assert _has_tag(world, ctrl.STATE_POSTURE_STANDING)
    # In FakeWorld we do not write any legacy alias; only the canonical posture:standing is present.
    # (Any state:posture_standing tag, if written, would only appear in a real WorldGraph instance.)


def test_preferred_policy_executes_selected():
    world = FakeWorld()
    d = ctrl.Drives(); d.fatigue = 0.9
    ctx = DummyCtx()
    res = ctrl.action_center_step(world, ctx, d, preferred="policy:rest")
    assert res["policy"] == "policy:rest"
    assert _has_tag(world, ctrl.STATE_RESTING)

def test_seeknipple_uses_state_token():
    world = FakeWorld()
    d = ctrl.Drives(); d.hunger = 0.9
    ctx = DummyCtx()
    world.add_predicate(ctrl.STATE_POSTURE_STANDING)  # standing
    pol = ctrl.SeekNipple()
    assert pol.trigger(world, d)
    res = pol.execute(world, ctx, d)
    assert res["status"] == "ok"
    # Canonical seeking_mom token should be present.
    assert _has_tag(world, ctrl.STATE_SEEKING_MOM)

