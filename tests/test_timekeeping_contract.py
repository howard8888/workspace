"""Unit-level contract tests for the simplified CCA8 time model."""

from __future__ import annotations

from types import SimpleNamespace

from cca8_column import ColumnMemory
from cca8_context import Ctx
from cca8_features import FactMeta, TensorPayload, time_attrs_from_ctx
from cca8_reporting import timekeeping_line, timekeeping_status_text_v1


def _payload() -> TensorPayload:
    return TensorPayload(data=[0.0], shape=(1,), kind="test")


def test_ctx_default_timekeeping_is_explicit_and_interpretable() -> None:
    """A fresh context should expose only the supported cognitive counters."""
    ctx = Ctx()

    assert ctx.cog_cycles == 0
    assert ctx.controller_steps == 0
    assert ctx.ticks == 0
    assert ctx.age_days == 0.0
    assert ctx.rl_epsilon == 0.2


def test_time_attrs_ignores_missing_or_malformed_values() -> None:
    """Metadata extraction should be defensive without inventing values."""
    ctx = SimpleNamespace(cog_cycles="bad", controller_steps=2, ticks=None, age_days=1.5)

    assert time_attrs_from_ctx(ctx) == {"controller_step": 2, "age_days": 1.5}


def test_factmeta_preserves_existing_attrs_while_adding_counters() -> None:
    """Explicit timing metadata should merge without discarding source provenance."""
    ctx = SimpleNamespace(cog_cycles=6, controller_steps=7, ticks=8, age_days=0.9)

    fact = FactMeta(name="demo", attrs={"source": "sensor"}).with_time(ctx)

    assert fact.as_dict()["attrs"] == {
        "source": "sensor",
        "cognitive_cycle": 6,
        "controller_step": 7,
        "autonomic_tick": 8,
        "age_days": 0.9,
    }


def test_column_search_filters_by_cognitive_cycle() -> None:
    """Column lookup should use the canonical cognitive-cycle metadata field."""
    column = ColumnMemory(name="test")
    first = column.assert_fact("first", _payload(), FactMeta(name="first", attrs={"cognitive_cycle": 2}))
    second = column.assert_fact("second", _payload(), FactMeta(name="second", attrs={"cognitive_cycle": 3}))

    assert [row["id"] for row in column.find(cognitive_cycle=2)] == [first]
    assert [row["id"] for row in column.find(cognitive_cycle=3)] == [second]


def test_timekeeping_line_has_one_unambiguous_counter_set() -> None:
    """The compact HUD should omit the retired vector and event-epoch clock."""
    ctx = SimpleNamespace(cog_cycles=4, controller_steps=5, ticks=6, age_days=0.125)

    assert timekeeping_line(ctx) == (
        "cognitive_cycles=4, controller_steps=5, autonomic_ticks=6, age_days=0.1250"
    )


def test_timekeeping_status_panel_reports_all_named_domains_without_mutation() -> None:
    """The inspector should show current values from each owner without advancing any clock."""
    pending_observation = SimpleNamespace(env_meta={"step_index": 13, "time_since_birth": 6.5})
    ctx = SimpleNamespace(
        cog_cycles=8,
        controller_steps=11,
        ticks=3,
        age_days=0.25,
        env_pending_observation=pending_observation,
        env_last_action="policy:follow_mom",
    )
    env = SimpleNamespace(
        state=SimpleNamespace(step_index=13, time_since_birth=6.5),
        config=SimpleNamespace(dt=0.5),
        episode_index=2,
    )
    ctx_before = dict(vars(ctx))
    env_state_before = dict(vars(env.state))

    text = timekeeping_status_text_v1(ctx, env)

    assert "CCA8 EXPLICIT TIMEKEEPING / ORDERING" in text
    assert "cognitive_cycles=8" in text
    assert "controller_steps=11" in text
    assert "autonomic_ticks=3" in text
    assert "age_days=0.2500" in text
    assert "episode_index: 2" in text
    assert "environment_step: 13" in text
    assert "environment_time: 6.5000" in text
    assert "dt_per_transition: 0.5000" in text
    assert "buffered_next_observation_step: 13" in text
    assert "buffered_next_observation_time: 6.5000" in text
    assert "last_dispatched_action: policy:follow_mom" in text
    assert "domain temporal cognition" in text
    assert "tvec64" not in text
    assert "cos_to_last_boundary" not in text
    assert vars(ctx) == ctx_before
    assert vars(env.state) == env_state_before
