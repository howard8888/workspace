"""Compatibility checks for the runner observation-ingestion extraction."""

from __future__ import annotations

from typing import Any

import cca8_observation_runtime
import cca8_run
from cca8_env import EnvObservation


def test_runner_observation_runtime_compatibility_surface(monkeypatch: Any) -> None:
    """Historical runner names should resolve through the extracted subsystem."""
    direct_aliases = (
        "ObservationRuntime",
        "init_body_world",
        "update_body_world_from_obs",
        "seqerr_update_from_obs",
        "_inject_simple_valence_like_mom",
        "append_cycle_json_record",
    )

    for name in direct_aliases:
        assert getattr(cca8_run, name) is getattr(cca8_observation_runtime, name)

    # These two functions remain runner wrappers because they resolve runner
    # callbacks at call time rather than importing cca8_run from the subsystem.
    assert cca8_run.inject_obs_into_world is not cca8_observation_runtime.inject_obs_into_world
    assert cca8_run._write_spatial_scene_edges is not cca8_observation_runtime._write_spatial_scene_edges

    runtime = cca8_run._observation_runtime_v1()
    assert runtime.update_body_world_from_obs is cca8_run.update_body_world_from_obs
    assert runtime.seqerr_update_from_obs is cca8_run.seqerr_update_from_obs
    assert runtime.navpatch_predictive_match_loop is cca8_run.navpatch_predictive_match_loop_v1
    assert runtime.inject_obs_into_working_world is cca8_run.inject_obs_into_working_world
    assert runtime.navmap_ctx_observation_update_step is cca8_run.navmap_ctx_observation_update_step_v1
    assert runtime.write_spatial_scene_edges is cca8_run._write_spatial_scene_edges
    assert runtime.inject_simple_valence_like_mom is cca8_run._inject_simple_valence_like_mom

    captured: dict[str, Any] = {}

    def _fake_inject(
        world: Any,
        ctx: Any,
        env_obs: EnvObservation,
        *,
        runtime: cca8_observation_runtime.ObservationRuntime,
    ) -> dict[str, Any]:
        captured["world"] = world
        captured["ctx"] = ctx
        captured["env_obs"] = env_obs
        captured["runtime"] = runtime
        return {"delegated": True}

    monkeypatch.setattr(cca8_observation_runtime, "inject_obs_into_world", _fake_inject)

    world = object()
    ctx = cca8_run.Ctx()
    obs = EnvObservation(predicates=[], cues=[], env_meta={})
    assert cca8_run.inject_obs_into_world(world, ctx, obs) == {"delegated": True}
    assert captured["world"] is world
    assert captured["ctx"] is ctx
    assert captured["env_obs"] is obs
    assert isinstance(captured["runtime"], cca8_observation_runtime.ObservationRuntime)

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["observation_runtime"] == "cca8_observation_runtime"
    assert "cca8_run" not in cca8_observation_runtime.__dict__
