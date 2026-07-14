# -*- coding: utf-8 -*-
"""Compatibility tests for the runtime-context module extraction."""

import cca8_context
import cca8_run


def test_runner_reexports_extracted_context_types() -> None:
    """Legacy runner imports should resolve to the authoritative context types."""
    assert cca8_run.Ctx is cca8_context.Ctx
    assert cca8_run.CreativeCandidate is cca8_context.CreativeCandidate
    assert cca8_run.ExperimentProtocolConfig is cca8_context.ExperimentProtocolConfig


def test_ctx_counter_reset_methods_preserve_behavior() -> None:
    """The extracted context should preserve its existing counter helpers."""
    ctx = cca8_run.Ctx(controller_steps=7, cog_cycles=5)

    ctx.reset_controller_steps()
    ctx.reset_cog_cycles()

    assert ctx.controller_steps == 0
    assert ctx.cog_cycles == 0
