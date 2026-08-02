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
    assert (
        cca8_run.profile_cca11_governed_cognitive_plurality
        is cca8_profiles.profile_cca11_governed_cognitive_plurality
    )
    assert cca8_run.profile_cca12_governed_pod is cca8_profiles.profile_cca12_governed_pod
    assert cca8_run.print_tagging_and_policies_help is cca8_guidance.print_tagging_and_policies_help
    assert cca8_run.choose_profile.__module__ == "cca8_run"
    assert cca8_profiles.choose_profile.__module__ == "cca8_profiles"
    assert cca8_guidance.run_new_user_tour.__module__ == "cca8_guidance"


def test_startup_header_advertises_cca11_and_cca12(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first runner screen should advertise both long-range research profiles."""
    cca8_run.print_header("HAL TEST", "BODY TEST")

    output = capsys.readouterr().out
    assert "8. CCA11: one coherent superhuman mind with governed cognitive plurality" in output
    assert "9. CCA12: governed pod of complete CCA11 cognitive architectures" in output


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


def test_profile_chooser_prompt_advertises_profiles_one_through_nine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interactive prompt should make the two future research profiles discoverable."""
    prompts: list[str] = []

    def choose_default(prompt: str = "") -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(builtins, "input", choose_default)
    ctx = cca8_run.Ctx()

    cca8_run.choose_profile(ctx, cca8_run.cca8_world_graph.WorldGraph())

    assert prompts
    assert "1–9" in prompts[0]


def test_profile_chooser_routes_cca11_through_runner_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choice 8 should preserve the runner's call-time callback seam."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "8")
    monkeypatch.setattr(
        cca8_run,
        "profile_cca11_governed_cognitive_plurality",
        lambda _ctx: ("Compatibility CCA11", 0.31, 0.41, 11),
    )
    ctx = cca8_run.Ctx()

    result = cca8_run.choose_profile(ctx, cca8_run.cca8_world_graph.WorldGraph())

    assert result == {
        "name": "Compatibility CCA11",
        "ctx_sigma": pytest.approx(0.31),
        "ctx_jump": pytest.approx(0.41),
        "winners_k": 11,
    }
    assert ctx.profile == "Compatibility CCA11"


def test_profile_chooser_routes_cca12_through_runner_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choice 9 should preserve the runner's call-time callback seam."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "9")
    monkeypatch.setattr(
        cca8_run,
        "profile_cca12_governed_pod",
        lambda _ctx: ("Compatibility CCA12", 0.32, 0.42, 12),
    )
    ctx = cca8_run.Ctx()

    result = cca8_run.choose_profile(ctx, cca8_run.cca8_world_graph.WorldGraph())

    assert result == {
        "name": "Compatibility CCA12",
        "ctx_sigma": pytest.approx(0.32),
        "ctx_jump": pytest.approx(0.42),
        "winners_k": 12,
    }
    assert ctx.profile == "Compatibility CCA12"


def test_future_profile_narratives_preserve_governed_authority_distinction(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The profile text should retain the core CCA11-versus-CCA12 design distinction."""
    cca11 = cca8_profiles.profile_cca11_governed_cognitive_plurality(SimpleNamespace())
    cca11_output = capsys.readouterr().out

    cca12 = cca8_profiles.profile_cca12_governed_pod(SimpleNamespace())
    cca12_output = capsys.readouterr().out

    assert cca11 == ("Mountain Goat", 0.015, 0.2, 2)
    assert cca12 == ("Mountain Goat", 0.015, 0.2, 2)
    assert "one persistent self" in cca11_output
    assert "constitutional society of cognitive processes" in cca11_output
    assert "Agreement is not the objective" in cca11_output
    assert "many CCA11 selves operating under one governed mission" in cca12_output
    assert "Mission Charter" in cca12_output
    assert "society of complete minds" in cca12_output


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
