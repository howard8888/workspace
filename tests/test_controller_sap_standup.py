import cca8_world_graph as wgmod
from cca8_controller import Drives
from cca8_controller import StandUp  # Concrete policy


class DummyCtx:
    """Minimal ctx surrogate for StandUp._policy_meta."""
    def __init__(self):
        self.ticks = 0
        self.boundary_no = 0
        self.boundary_vhash64 = None

    def tvec64(self):
        # simple deterministic fingerprint; StandUp only cares that this is callable
        return "0000000000000000"


def _tags_of(world, token_prefix: str):
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if isinstance(t, str) and t.startswith(token_prefix):
                out.append((bid, t))
    return out


def test_standup_creates_sap_chain_no_legacy_tags():
    """StandUp should build a clean S–A–P chain with posture:fallen/standing and action:* nodes, no state: or pred:action:* tags."""
    world = wgmod.WorldGraph()
    world.set_tag_policy("allow")
    now = world.ensure_anchor("NOW")

    # Seed posture:fallen attached to NOW, similar to boot_prime_stand
    fallen_bid = world.add_predicate("posture:fallen", attach="now")

    drives = Drives()
    ctx = DummyCtx()

    pol = StandUp()
    assert pol.trigger(world, drives), "StandUp should trigger when posture:fallen is near NOW"

    before = len(world._bindings)
    res = pol.execute(world, ctx, drives)
    after = len(world._bindings)

    assert res["status"] == "ok"
    assert after > before

    # Check posture predicates
    preds = _tags_of(world, "pred:posture:")
    pred_tokens = {t for _, t in preds}
    assert "pred:posture:fallen" in pred_tokens
    assert "pred:posture:standing" in pred_tokens

    # Check action nodes
    actions = _tags_of(world, "action:")
    action_tokens = {t for _, t in actions}
    assert "action:push_up" in action_tokens
    assert "action:extend_legs" in action_tokens

    # No legacy state:* or pred:action:*
    assert not any("state:" in t for _, t in preds)
    assert not any(
        isinstance(t, str) and t.startswith("state:")
        for _, b in world._bindings.items()
        for t in getattr(b, "tags", [])
    )
    assert not any(
        isinstance(t, str) and t.startswith("pred:action:")
        for _, b in world._bindings.items()
        for t in getattr(b, "tags", [])
    )

    # Optional: sanity on edges — fallen/posture should be reachable to standing in ≤3 hops
    start = now  # start from NOW cluster, which includes posture:fallen
    goal_bids = [bid for bid, t in preds if t == "pred:posture:standing"]
    assert goal_bids, "Expected at least one posture:standing binding"
    goal = goal_bids[0]

    from collections import deque

    q = deque([start])
    seen = {start}
    found = False
    while q:
        u = q.popleft()
        if u == goal:
            found = True
            break
        edges = getattr(world._bindings[u], "edges", []) or []
        for e in edges:
            v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if v and v not in seen:
                seen.add(v)
                q.append(v)

    assert found, "There should be a path from posture:fallen to posture:standing after StandUp.execute"
