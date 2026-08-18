# -*- coding: utf-8 -*-
"""Phase 4B tests for bounded maternal Sequential/Temporal compression."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
import math

import pytest

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import (
    MaternalBearingTrendV1,
    MaternalTemporalSampleV1,
    MaternalTemporalThresholdsV1,
    MaternalTemporalTrendV1,
    maternal_temporal_readout_from_samples_v1,
    maternal_temporal_shadow_observation_step_v1,
    render_maternal_temporal_shadow_lines_v1,
)
from cca8_navmap_kernel import NavMapRefV1
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap() -> Ctx:
    """Return a context with the legacy BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(
    *,
    maternal: tuple[float, float] | None,
    time_value: float,
    step_index: int,
    raw_distance: float = 999.0,
    proximity_predicate: str | None = "proximity:mom:far",
) -> EnvObservation:
    """Return one deterministic observation with explicit geometry and timing."""
    predicates = ["posture:standing"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    return EnvObservation(
        raw_sensors={"distance_to_mom": raw_distance},
        predicates=predicates,
        cues=[],
        env_meta={
            "scenario_stage": "phase4b_test",
            "time_since_birth": float(time_value),
            "step_index": int(step_index),
            "kid_position": {"x": 0.0, "y": 0.0},
            "mom_position": (
                {"x": float(maternal[0]), "y": float(maternal[1])}
                if maternal is not None
                else None
            ),
        },
    )


def _update_phase4b(ctx: Ctx, env_obs: EnvObservation) -> dict[str, object]:
    """Run the observation-side dependencies followed by Phase 4A and 4B."""
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    return maternal_temporal_shadow_observation_step_v1(ctx, env_obs)


def _sample(
    observation_no: int,
    distance: float,
    *,
    bearing: float = 0.0,
    time_value: float | None = None,
    step_index: int | None = None,
) -> MaternalTemporalSampleV1:
    """Return one pure compact sample for decoder boundary tests."""
    return MaternalTemporalSampleV1(
        observation_no=observation_no,
        source_evidence_map_ref=NavMapRefV1(f"evidence_{observation_no}", 1),
        maintained_map_ref=NavMapRefV1("maternal", observation_no),
        frame_id="self_centered_maternal_frame_v1",
        units="simulated_distance_units",
        identity_handle="maternal_individual",
        self_element_id="self_anchor",
        maternal_element_id="maternal_individual",
        step_index=step_index if step_index is not None else observation_no,
        controller_steps=observation_no,
        time_since_birth=time_value if time_value is not None else float(observation_no),
        distance=distance,
        bearing_degrees=bearing,
        valid=True,
        reason="complete_common_frame_geometry",
    )


def test_first_two_samples_are_insufficient_and_third_derives_approaching() -> None:
    """A minimum history should be required before a static trend is emitted."""
    ctx = _ctx_with_bodymap()

    first = _update_phase4b(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    second = _update_phase4b(ctx, _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1))
    third = _update_phase4b(ctx, _observation(maternal=(3.0, 0.0), time_value=2.0, step_index=2))

    assert first["status"] == "insufficient_history"
    assert second["status"] == "insufficient_history"
    assert first["readout"]["trend"] == "unknown"
    assert second["readout"]["trend"] == "unknown"
    assert third["status"] == "supported"
    assert third["readout"]["trend"] == "approaching"
    assert third["readout"]["relative_rate"] == -1.0
    assert third["readout"]["interval_source"] == "time_since_birth"
    assert third["readout"]["valid_sample_count"] == 3


def test_geometry_derived_samples_defeat_opposite_raw_and_symbolic_trends() -> None:
    """Phase 4B must use Phase 4A geometry rather than legacy/raw Mom distance."""
    ctx = _ctx_with_bodymap()

    rows = [
        _update_phase4b(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                raw_distance=raw_distance,
                proximity_predicate="proximity:mom:close",
            ),
        )
        for index, (distance, raw_distance) in enumerate(((5.0, 1.0), (4.0, 2.0), (3.0, 3.0)))
    ]

    assert rows[-1]["readout"]["trend"] == "approaching"
    samples = [frame["navmap_temporal"]["self_maternal"] for frame in ctx.seqerr_history]
    assert [sample["distance"] for sample in samples] == [5.0, 4.0, 3.0]
    assert [frame["raw"]["distance_to_mom"] for frame in ctx.seqerr_history] == [1.0, 2.0, 3.0]
    assert all(sample["source_evidence_map_ref"]["map_id"].startswith("goat_self_maternal_evidence_v2") for sample in samples)


def test_increasing_geometry_derives_receding() -> None:
    """Increasing SELF-maternal distance should decode as receding."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((2.0, 2.5, 3.0)):
        row = _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    assert row["status"] == "supported"
    assert row["readout"]["trend"] == "receding"
    assert row["readout"]["relative_rate"] == 0.5


def test_small_distance_variation_derives_stable() -> None:
    """Changes inside the explicit tolerance should decode as stable."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((3.0, 3.02, 3.04)):
        row = _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    assert row["status"] == "supported"
    assert row["readout"]["trend"] == "stable"
    assert math.isclose(row["readout"]["relative_rate"], 0.02)


def test_bearing_wraparound_derives_counterclockwise_without_false_large_jump() -> None:
    """A 350→0→10 degree sequence should unwrap to a small positive rotation."""
    ctx = _ctx_with_bodymap()
    for index, degrees in enumerate((350.0, 0.0, 10.0)):
        radians = math.radians(degrees)
        maternal = (2.0 * math.cos(radians), 2.0 * math.sin(radians))
        row = _update_phase4b(
            ctx,
            _observation(maternal=maternal, time_value=float(index), step_index=index),
        )

    readout = row["readout"]
    assert readout["trend"] == "stable"
    assert readout["bearing_trend"] == "counterclockwise"
    assert math.isclose(readout["bearing_delta_degrees"], 20.0, abs_tol=1e-9)
    assert math.isclose(readout["bearing_rate_degrees"], 10.0, abs_tol=1e-9)


def test_hysteresis_preserves_approaching_through_mild_slowing_then_releases() -> None:
    """The smaller exit threshold should prevent trend chatter near zero."""
    ctx = _ctx_with_bodymap()
    ctx.seqerr_window = 3
    rows = []
    for index, distance in enumerate((5.0, 4.9, 4.8, 4.84, 4.94)):
        rows.append(
            _update_phase4b(
                ctx,
                _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
            )
        )

    assert rows[2]["readout"]["trend"] == "approaching"
    assert math.isclose(rows[3]["readout"]["relative_rate"], -0.03, abs_tol=1e-12)
    assert rows[3]["readout"]["trend"] == "approaching"
    assert rows[4]["readout"]["trend"] == "receding"


def test_exact_entry_threshold_tie_resolves_deterministically_to_stable() -> None:
    """An exact entry-boundary rate should not depend on insertion or float ordering."""
    thresholds = MaternalTemporalThresholdsV1(
        minimum_valid_samples=3,
        stable_rate_tolerance=1.0,
        hysteresis_rate=0.0,
        stable_bearing_rate_tolerance=2.0,
        bearing_hysteresis_rate=0.0,
        minimum_elapsed_time=1e-9,
    )

    readout = maternal_temporal_readout_from_samples_v1(
        (_sample(1, 5.0), _sample(2, 4.0), _sample(3, 3.0)),
        thresholds=thresholds,
        window_capacity=3,
    )

    assert readout.relative_rate == -1.0
    assert readout.trend is MaternalTemporalTrendV1.STABLE


def test_equal_time_and_step_values_fall_back_to_existing_observation_counter() -> None:
    """Non-advancing environment timing should use Phase 4A observation order, not a new clock."""
    ctx = _ctx_with_bodymap()
    for distance in (5.0, 4.0, 3.0):
        row = _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=0.0, step_index=0),
        )

    assert row["readout"]["interval_source"] == "observation_no"
    assert row["readout"]["elapsed_time"] == 2.0
    assert row["readout"]["trend"] == "approaching"


def test_irregular_explicit_dt_produces_rate_from_elapsed_time_not_sample_count() -> None:
    """Uneven observation spacing should still derive the correct physical rate."""
    ctx = _ctx_with_bodymap()
    observations = (
        (10.0, 0.0, 0),
        (8.0, 1.0, 1),
        (4.0, 3.0, 2),
    )
    for distance, time_value, step_index in observations:
        row = _update_phase4b(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=time_value,
                step_index=step_index,
            ),
        )

    assert row["readout"]["interval_source"] == "time_since_birth"
    assert row["readout"]["elapsed_time"] == 3.0
    assert row["readout"]["relative_rate"] == -2.0
    assert row["readout"]["rate_uncertainty"] == 0.0


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (("identity_handle", "different_individual"), ("frame_id", "incompatible_frame")),
)
def test_identity_or_frame_change_resets_temporal_support(
    changed_field: str,
    changed_value: str,
) -> None:
    """Temporal samples cannot be silently combined across identity or frame changes."""
    thresholds = MaternalTemporalThresholdsV1(
        minimum_valid_samples=3,
        stable_rate_tolerance=0.05,
        hysteresis_rate=0.02,
        stable_bearing_rate_tolerance=2.0,
        bearing_hysteresis_rate=1.0,
        minimum_elapsed_time=1e-9,
    )
    third = replace(_sample(3, 3.0), **{changed_field: changed_value})

    readout = maternal_temporal_readout_from_samples_v1(
        (_sample(1, 5.0), _sample(2, 4.0), third),
        thresholds=thresholds,
        window_capacity=4,
    )

    assert readout.valid is False
    assert readout.trend is MaternalTemporalTrendV1.UNKNOWN
    assert readout.support_status == "insufficient_history"
    assert readout.valid_sample_count == 1


def test_current_missing_geometry_yields_unknown_and_breaks_contiguous_history() -> None:
    """A missing current position must not bridge a temporal trend across the gap."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    missing = _update_phase4b(
        ctx,
        _observation(
            maternal=None,
            time_value=3.0,
            step_index=3,
            proximity_predicate=None,
        ),
    )
    returning = _update_phase4b(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=4.0, step_index=4),
    )

    assert missing["status"] == "unknown"
    assert missing["readout"]["trend"] == "unknown"
    assert missing["readout"]["support_status"] == "current_geometry_unknown"
    assert returning["status"] == "insufficient_history"
    assert returning["readout"]["valid_sample_count"] == 1


def test_phase4b_reuses_bounded_seqerr_window_without_storing_full_navmaps() -> None:
    """The temporal window should stay bounded and carry compact JSON-safe samples only."""
    ctx = _ctx_with_bodymap()
    ctx.seqerr_window = 3
    for index, distance in enumerate((6.0, 5.0, 4.0, 3.0, 2.0)):
        _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    assert len(ctx.seqerr_history) == 3
    assert not hasattr(ctx, "navmap_maternal_temporal_samples")
    for frame in ctx.seqerr_history:
        sample = frame["navmap_temporal"]["self_maternal"]
        assert sample["contains_full_navmap"] is False
        assert "elements" not in sample
        assert "relations" not in sample
        assert "links" not in sample
    json.dumps(ctx.seqerr_history, allow_nan=False, sort_keys=True)


def test_phase4b_does_not_create_or_mutate_immutable_navmaps() -> None:
    """Temporal decoding should leave the completed Phase 4A map revision untouched."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    maternal_map = ctx.navmap_maternal_map
    root_view = ctx.navmap_maternal_root_view
    maternal_bytes = maternal_map.to_bytes() if maternal_map is not None else b""
    root_bytes = root_view.to_bytes() if root_view is not None else b""

    row = maternal_temporal_shadow_observation_step_v1(ctx, env_obs)

    assert row["creates_immutable_navmap_revision"] is False
    assert ctx.navmap_maternal_map is maternal_map
    assert ctx.navmap_maternal_root_view is root_view
    assert ctx.navmap_maternal_map is not None
    assert ctx.navmap_maternal_root_view is not None
    assert ctx.navmap_maternal_map.to_bytes() == maternal_bytes
    assert ctx.navmap_maternal_root_view.to_bytes() == root_bytes


def test_bodymap_and_followmom_authority_remain_unchanged() -> None:
    """The Phase 4B shadow must not alter BodyMap or gain behavioral authority."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(
        maternal=(5.0, 0.0),
        time_value=0.0,
        step_index=0,
        proximity_predicate="proximity:mom:close",
    )
    update_body_world_from_obs(ctx, env_obs)
    mom_id = ctx.body_ids["mom"]
    before_tags = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)

    row = maternal_temporal_shadow_observation_step_v1(ctx, env_obs)

    after_tags = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags
    assert row["authority"] == "shadow_only"
    assert row["follow_mom_authority"] == "legacy_bodymap_policy_runtime"
    assert row["map_can_trigger_follow_mom"] is False
    assert row["map_can_advise_follow_mom"] is False


def test_phase4a_trace_remains_unchanged_by_phase4b() -> None:
    """Phase 4B should consume Phase 4A output without rewriting its trace."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(4.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    phase4a_before = json.loads(json.dumps(ctx.navmap_maternal_last_update))

    maternal_temporal_shadow_observation_step_v1(ctx, env_obs)

    assert ctx.navmap_maternal_last_update == phase4a_before


def test_disabled_phase4b_path_has_no_temporal_side_effects() -> None:
    """The dedicated Phase 4B flag should disable temporal shadow construction."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_maternal_temporal_shadow_enabled = False

    row = maternal_temporal_shadow_observation_step_v1(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )

    assert row["status"] == "disabled"
    assert ctx.navmap_maternal_temporal_state is None
    assert ctx.navmap_maternal_temporal_last_update is None
    assert ctx.navmap_maternal_temporal_history == []


def test_disabled_sequential_unit_prevents_phase4b_window_updates() -> None:
    """Phase 4B should respect the existing Sequential/Error enable switch."""
    ctx = _ctx_with_bodymap()
    ctx.seqerr_enabled = False
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)

    row = maternal_temporal_shadow_observation_step_v1(ctx, env_obs)

    assert row["status"] == "sequential_unit_disabled"
    assert ctx.seqerr_history == []
    assert ctx.navmap_maternal_temporal_state is None


def test_geometry_dependency_is_explicit_when_phase4a_has_not_run() -> None:
    """Phase 4B should not fabricate temporal samples without Phase 4A geometry."""
    ctx = _ctx_with_bodymap()

    row = maternal_temporal_shadow_observation_step_v1(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )

    assert row["status"] == "geometry_unavailable"
    assert row["reason"] == "phase4a_geometry_state_unavailable"
    assert ctx.seqerr_history == []


def test_phase4b_trace_history_is_bounded_and_json_safe() -> None:
    """Diagnostic summaries should be bounded independently from the sample window."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_maternal_temporal_history_limit = 2
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    assert len(ctx.navmap_maternal_temporal_history) == 2
    json.dumps(ctx.navmap_maternal_temporal_history, allow_nan=False, sort_keys=True)
    assert ctx.navmap_maternal_temporal_history[-1]["readout"]["trend"] == "approaching"


def test_records_are_immutable_and_json_safe() -> None:
    """The public sample/readout contract should remain immutable and serializable."""
    sample = _sample(1, 3.0)
    thresholds = MaternalTemporalThresholdsV1(
        minimum_valid_samples=3,
        stable_rate_tolerance=0.05,
        hysteresis_rate=0.02,
        stable_bearing_rate_tolerance=2.0,
        bearing_hysteresis_rate=1.0,
        minimum_elapsed_time=1e-9,
    )

    with pytest.raises(FrozenInstanceError):
        sample.distance = 9.0  # type: ignore[misc]
    json.dumps(sample.as_dict(), allow_nan=False, sort_keys=True)
    json.dumps(thresholds.as_dict(), allow_nan=False, sort_keys=True)


def test_renderer_exposes_shared_window_static_readout_and_authority_boundary() -> None:
    """The human trace should show compression rather than a NavMap movie."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4b(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    text = "\n".join(render_maternal_temporal_shadow_lines_v1(ctx))

    assert "MATERNAL TEMPORAL PHASE 4B SHADOW:" in text
    assert "trend=approaching" in text
    assert "rate=-1.000" in text
    assert "shared_seqerr_window=True" in text
    assert "stores_full_navmaps=False" in text
    assert "creates_navmap_revision=False" in text
    assert "follow_mom_authority=legacy_bodymap_policy_runtime" in text


def test_live_observation_runtime_populates_phase4b_without_changing_v1_return() -> None:
    """The existing NavMap observation callback should run Phase 4B after Phase 4A."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)

    v1_update = navmap_ctx_observation_update_step_v1(ctx, env_obs)

    assert v1_update["schema"] == "navmap_observation_update_v1"
    assert ctx.navmap_maternal_temporal_last_update is not None
    assert ctx.navmap_maternal_temporal_last_update["phase"] == "4B"
    assert ctx.navmap_maternal_temporal_last_update["status"] == "insufficient_history"
    assert ctx.navmap_maternal_temporal_last_update["sample"]["distance"] == 3.0


def test_cycle_json_exposes_phase4b_maternal_temporal_shadow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should expose the Phase 4B shadow."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    world = WorldGraph()
    world.ensure_anchor("NOW")

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    assert ctx.cycle_json_records
    summary = ctx.cycle_json_records[-1]["maternal_temporal_shadow"]
    assert summary["schema"] == "maternal_temporal_shadow_summary_v1"
    assert summary["phase"] == "4B"
    assert summary["authority"] == "shadow_only"
    assert summary["map_can_trigger_follow_mom"] is False
    assert summary["sample"]["contains_full_navmap"] is False


def test_phase4b_context_defaults_are_bounded_and_non_authoritative() -> None:
    """The context should expose explicit bounded Phase 4B configuration."""
    ctx = Ctx()

    assert ctx.navmap_maternal_temporal_shadow_enabled is True
    assert ctx.navmap_maternal_temporal_minimum_valid_samples == 3
    assert 0.0 <= ctx.navmap_maternal_temporal_hysteresis_rate <= ctx.navmap_maternal_temporal_stable_rate_tolerance
    assert ctx.navmap_maternal_temporal_state is None
    assert ctx.navmap_maternal_temporal_history == []


def test_bearing_enum_is_explicitly_distinct_from_distance_trend() -> None:
    """Angular and radial temporal interpretations should remain separate types."""
    assert MaternalTemporalTrendV1.APPROACHING.value == "approaching"
    assert MaternalBearingTrendV1.COUNTERCLOCKWISE.value == "counterclockwise"
    assert MaternalTemporalTrendV1.STABLE.value == MaternalBearingTrendV1.STABLE.value
    assert MaternalTemporalTrendV1 is not MaternalBearingTrendV1
