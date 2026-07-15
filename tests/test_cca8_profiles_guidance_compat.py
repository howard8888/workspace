# -*- coding: utf-8 -*-
"""Compatibility tests for the CCA8 profile and guidance extraction."""

from __future__ import annotations

import builtins
from types import SimpleNamespace
import pytest

# These white-box compatibility tests intentionally inspect runner-private
# bridge factories and replace runner-visible callbacks.
# pylint: disable=protected-access

import cca8_guidance
import cca8_profiles
import cca8_run


def test_profile_and_guidance_modules_are_one_way() -> None:
    """The extracted presentation modules must not import the interactive runner."""
    assert "cca8_run" not in cca8_profiles.__dict__
    assert "cca8_run" not in cca8_guidance.__dict__


def test_runner_profile_compatibility_surface_points_to_extracted_owners() -> None:
    """Pure profile/help names remain available from the historical runner module."""
    assert cca8_run.profile_chimpanzee is cca8_profiles.profile_chimpanzee
    assert cca8_run.profile_human is cca8_profiles.profile_human
    assert cca8_run.profile_superhuman is cca8_profiles.profile_superhuman
    assert cca8_run.print_tagging_and_policies_help is cca8_guidance.print_tagging_and_policies_help
    assert cca8_run.choose_profile.__module__ == "cca8_run"
    assert cca8_profiles.choose_profile.__module__ == "cca8_profiles"
    assert cca8_guidance.run_new_user_tour.__module__ == "cca8_guidance"


def test_profile_chooser_keeps_mountain_goat_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pressing Enter should retain the historical Mountain Goat defaults."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    ctx = cca8_run.Ctx()

    result = cca8_run.choose_profile(ctx, cca8_run.cca8_world_graph.WorldGraph())

    assert result == {
        "name": "Mountain Goat",
        "ctx_sigma": 0.015,
        "ctx_jump": 0.2,
        "winners_k": 2,
    }
    assert ctx.profile == "Mountain Goat"


def test_profile_chooser_resolves_runner_callbacks_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replacing a runner-visible profile should affect the extracted chooser immediately."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "2")
    monkeypatch.setattr(
        cca8_run,
        "profile_chimpanzee",
        lambda _ctx: ("Compatibility Chimp", 0.11, 0.22, 7),
    )
    ctx = cca8_run.Ctx()

    result = cca8_run.choose_profile(ctx, cca8_run.cca8_world_graph.WorldGraph())

    assert result["name"] == "Compatibility Chimp"
    assert result["ctx_sigma"] == pytest.approx(0.11)
    assert result["ctx_jump"] == pytest.approx(0.22)
    assert result["winners_k"] == 7
    assert ctx.profile == "Compatibility Chimp"


def test_profile_runtime_resolves_current_runner_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run profiles receive the runner's current controller callback."""
    def sentinel(*_args: object, **_kwargs: object) -> dict[str, str]:
        return {"status": "sentinel"}

    monkeypatch.setattr(cca8_run, "action_center_step", sentinel)

    runtime = cca8_run._profile_runtime_v1()

    assert runtime.action_center_step is sentinel


def test_tagging_help_is_rendered_by_extracted_guidance(capsys: pytest.CaptureFixture[str]) -> None:
    """Menu-1 explanatory text should preserve its key architecture sections."""
    cca8_run.print_tagging_and_policies_help(
        SimpleNamespace(list_loaded_names=lambda: ["policy:test"]),
    )

    output = capsys.readouterr().out
    assert "Understanding Bindings" in output
    assert "Policies currently loaded" in output
    assert "policy:test" in output
    assert "WorldGraph" in output


def test_tour_wrapper_uses_current_runner_snapshot_callback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The runner wrapper should resolve its snapshot callback at call time."""
    monkeypatch.setattr(cca8_run, "snapshot_text", lambda *_args, **_kwargs: "PROFILE_GUIDANCE_SENTINEL")
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "*")

    cca8_run.run_new_user_tour(
        object(),
        object(),
        SimpleNamespace(),
        SimpleNamespace(loaded=[]),
    )

    output = capsys.readouterr().out
    assert "CCA8 Quick Tour" in output
    assert "PROFILE_GUIDANCE_SENTINEL" in output


def test_profile_and_guidance_versions_appear_in_runner_report() -> None:
    """The normal component report should include both extracted modules."""
    versions = cca8_run.versions_dict()

    assert versions["profiles"] == cca8_profiles.__version__
    assert versions["guidance"] == cca8_guidance.__version__
