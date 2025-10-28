# -*- coding: utf-8 -*-
import cca8_controller as ctrl

# Minimal stand-ins so we don't depend on the full WorldGraph here.
class Binding:
    def __init__(self, bid: str, token: str, meta=None):
        self.id = bid
        self.tags = {f"pred:{token}"}
        self.meta = dict(meta or {})

class FakeWorld:
    def __init__(self):
        self._bindings = {}
        self._id = 0
    def _next(self) -> str:
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

def _upright(world: FakeWorld):
    # Seed upright state using the legacy alias (controller is alias-aware).
    world.add_predicate("posture:standing")


def test_scoring_prefers_seek_when_hunger_deficit_dominates():
    """
    When both SeekNipple and Rest triggers are true, the controller should pick
    the policy with the larger deficit score. Here, hunger deficit dominates.
    """
    w = FakeWorld()
    _upright(w)
    d = ctrl.Drives()
    # Make BOTH triggers true:
    #   - SeekNipple: hunger > HUNGER_HIGH
    #   - Rest: fatigue > FATIGUE_HIGH
    d.hunger  = 0.85  # deficit ~ 0.85 - HUNGER_HIGH (typically 0.25 if H=0.6)
    d.fatigue = 0.85  # deficit ~ 0.05 -> weighted 0.035 if F=0.8 and weight=0.7
    res = ctrl.action_center_step(w, DummyCtx(), d)
    assert res["policy"] == "policy:seek_nipple"


def test_scoring_prefers_rest_when_fatigue_deficit_dominates():
    """
    When fatigue deficit (weighted by 0.7) exceeds hunger's, choose Rest.
    """
    w = FakeWorld()
    _upright(w)
    d = ctrl.Drives()
    # Hunger only barely above threshold; fatigue far above threshold.
    d.hunger  = ctrl.HUNGER_HIGH + 0.05
    d.fatigue = 1.00  # strong deficit vs FATIGUE_HIGH
    res = ctrl.action_center_step(w, DummyCtx(), d)
    assert res["policy"] == "policy:rest"


def test_scoring_tie_breaker_uses_primitives_order_on_equal_scores():
    """
    If both trigger AND their weighted deficits are equal, tie-breaker should
    prefer the earlier policy in PRIMITIVES (stable order).
    We enforce equal score by matching deficits:
        hunger_deficit == 0.7 * fatigue_deficit
    """
    w = FakeWorld()
    _upright(w)
    d = ctrl.Drives()

    # Choose a convenient fatigue deficit and compute matching hunger deficit.
    fatigue_def = 0.20
    hunger_def  = 0.7 * fatigue_def  # equal weighted score

    d.fatigue = ctrl.FATIGUE_HIGH + fatigue_def
    d.hunger  = ctrl.HUNGER_HIGH  + hunger_def

    # Both triggers true by construction.
    res = ctrl.action_center_step(w, DummyCtx(), d)

    names_in_order = [p.name for p in ctrl.PRIMITIVES]
    idx_seek = names_in_order.index("policy:seek_nipple")
    idx_rest = names_in_order.index("policy:rest")
    expected = "policy:seek_nipple" if idx_seek < idx_rest else "policy:rest"
    assert res["policy"] == expected
