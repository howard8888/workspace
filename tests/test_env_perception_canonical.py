from cca8_env import EnvState, PerceptionAdapter, EnvConfig, HybridEnvironment


def test_perception_adapter_uses_canonical_posture_tokens():
    """PerceptionAdapter.observe should emit canonical posture/resting predicates, not legacy state:* tokens."""
    # Construct a few EnvState variants and check predicates
    adapter = PerceptionAdapter()

    # 1) Standing
    es = EnvState(
        kid_posture="standing",
        kid_position=(0.0, 0.0),
        mom_position=(0.5, 0.0),
        mom_distance="near",
        nipple_state="hidden",
        kid_temperature=0.5,
        time_since_birth=10.0,
    )
    obs = adapter.observe(es)
    assert "posture:standing" in obs.predicates
    assert not any(p.startswith("state:") for p in obs.predicates)

    # 2) Fallen
    es.kid_posture = "fallen"
    obs = adapter.observe(es)
    assert "posture:fallen" in obs.predicates
    assert not any(p.startswith("state:") for p in obs.predicates)

    # 3) Resting
    es.kid_posture = "resting"
    obs = adapter.observe(es)
    assert "resting" in obs.predicates
    assert not any(p.startswith("state:") for p in obs.predicates)
