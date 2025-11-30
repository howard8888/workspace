from cca8_world_graph import WorldGraph
from cca8_run import Ctx, mini_snapshot_text, _latest_posture_binding


def _make_world_with_postures() -> WorldGraph:
    """Build a tiny world with one env-driven posture and one policy-expected posture."""
    world = WorldGraph()
    world.ensure_anchor("NOW")

    # Env-driven posture: pred:posture:fallen with source=HybridEnvironment
    world.add_predicate(
        "posture:fallen",
        attach="now",
        meta={"source": "HybridEnvironment"},
    )

    # Policy-expected posture: pred:posture:standing with policy metadata
    world.add_predicate(
        "posture:standing",
        attach="latest",
        meta={"policy": "policy:stand_up"},
    )

    return world


def test_latest_posture_binding_env_vs_policy_filters() -> None:
    """_latest_posture_binding should distinguish env vs policy sources correctly."""
    world = _make_world_with_postures()

    env_bid, env_tag, env_meta = _latest_posture_binding(world, source="HybridEnvironment")
    pol_bid, pol_tag, pol_meta = _latest_posture_binding(world, require_policy=True)

    assert env_bid is not None and env_tag == "pred:posture:fallen"
    assert isinstance(env_meta, dict) and env_meta.get("source") == "HybridEnvironment"

    assert pol_bid is not None and pol_tag == "pred:posture:standing"
    assert isinstance(pol_meta, dict) and pol_meta.get("policy") == "policy:stand_up"


def test_mini_snapshot_discrepancy_and_history_persist() -> None:
    """mini_snapshot_text should report posture discrepancies and keep a short history."""
    world = _make_world_with_postures()
    ctx = Ctx()

    # First call: we expect a discrepancy line and a hint line,
    # plus a history block with one entry.
    text1 = mini_snapshot_text(world, ctx, limit=10)
    lines1 = text1.splitlines()

    # Current discrepancy (main + explanatory hint)
    assert any(line.startswith("[discrepancy] env posture='fallen'") for line in lines1)
    assert any("often the motor system will attempt an action" in line for line in lines1)
    # History section should be present with at least one entry.
    assert any(line.startswith("[discrepancy history]") for line in lines1)
    assert sum("env posture='fallen'" in line for line in lines1) >= 2  # main line + history line

    # Now, the environment later reports standing as well.
    # This should clear the *current* discrepancy, but keep history.
    world.add_predicate(
        "posture:standing",
        attach="latest",
        meta={"source": "HybridEnvironment"},
    )

    text2 = mini_snapshot_text(world, ctx, limit=10)
    lines2 = text2.splitlines()

    # No new hint line on the second call (no *new* discrepancy).
    assert not any("often the motor system will attempt an action" in line for line in lines2)

    # History should still be printed and contain the original mismatch.
    assert any(line.startswith("[discrepancy history]") for line in lines2)
    assert any("env posture='fallen'" in line for line in lines2)
