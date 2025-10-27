# tests/test_controller.py
import pytest

from cca8_world_graph import WorldGraph
from cca8_controller import (
    Drives,
    action_center_step,
    SKILLS,
    skills_to_dict,
    update_skill,
)

# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def fresh_skills():
    """Keep the global SKILLS ledger isolated per test."""
    SKILLS.clear()
    yield
    SKILLS.clear()

@pytest.fixture()
def world():
    g = WorldGraph()
    g.set_tag_policy("allow")  # silence lexicon checks in tests
    g.ensure_anchor("NOW")
    return g


# ---------- tests ----------

def test_drives_predicates_thresholds():
    """Strict thresholds: >0.60, >0.70, <0.30."""
    d = Drives(hunger=0.61, fatigue=0.71, warmth=0.29)
    tags = set(d.predicates())
    assert {"drive:hunger_high", "drive:fatigue_high", "drive:cold"} <= tags

    # boundaries do NOT trigger
    d2 = Drives(hunger=0.60, fatigue=0.70, warmth=0.30)
    assert d2.predicates() == []


def test_action_center_standup_then_seek(world):
    """Hungry neonate: StandUp first; with standing recorded, SeekNipple next."""
    d = Drives(hunger=0.95, fatigue=0.2, warmth=0.6)

    s1 = action_center_step(world, ctx=None, drives=d)
    assert s1["policy"] == "policy:stand_up"

    s2 = action_center_step(world, ctx=None, drives=d)
    assert s2["policy"] == "policy:seek_nipple"


def test_action_center_fallen_short_circuit(world):
    """If fallen is present, StandUp short-circuits regardless of hunger."""
    world.add_predicate("posture:fallen", attach="now")
    d = Drives(hunger=0.1, fatigue=0.1, warmth=0.6)
    s = action_center_step(world, ctx=None, drives=d)
    assert s["policy"] == "policy:stand_up"


def test_skills_update_and_dump():
    """Ledger increments n/succ; q is an EMA; last_reward tracks the latest."""
    update_skill("policy:example", reward=0.5, ok=True)   # q = 0.3*0.5 = 0.15
    update_skill("policy:example", reward=0.0, ok=False)  # q = 0.7*0.15 + 0.3*0 = 0.105

    dump = skills_to_dict()
    assert "policy:example" in dump
    row = dump["policy:example"]

    assert row["n"] == 2
    assert row["succ"] == 1
    assert row["last_reward"] == pytest.approx(0.0, rel=1e-9)
    assert row["q"] == pytest.approx(0.105, rel=1e-9)


def test_standup_returns_binding_extra():
    """StandUp returns a payload with 'binding' that matches the final standing node."""
    g = WorldGraph()
    g.set_tag_policy("allow")
    now = g.ensure_anchor("NOW")

    g.add_predicate("posture:fallen", attach="now")
    res = action_center_step(g, ctx=None, drives=Drives(hunger=0.0, fatigue=0.0, warmth=0.6))

    assert res["policy"] == "policy:stand_up"
    assert res["status"] == "ok"
    assert "binding" in res and isinstance(res["binding"], str)

    bid = res["binding"]
    path = g.plan_to_predicate(now, "posture:standing")
    assert path is not None and path[-1] == bid
