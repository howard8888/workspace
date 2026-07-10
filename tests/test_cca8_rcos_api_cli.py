"""CLI/profile contract tests for the planned RCOS API startup mode."""

import cca8_run


def test_profile_rcos_api_prints_explanation_and_falls_back_to_goat(capsys) -> None:
    """The RCOS API placeholder should be explicit and return runnable goat defaults."""
    result = cca8_run.profile_rcos_api(cca8_run.Ctx())
    output = capsys.readouterr().out

    assert result == ("Mountain Goat", 0.015, 0.2, 2)
    assert "Robotic Cognitive Operating System (RCOS)" in output
    assert "an RCOS API configuration is not available" in output
    assert "Profile will be set to mountain goat-like brain simulation" in output


def test_main_accepts_rcos_api_and_routes_to_interactive_loop(monkeypatch) -> None:
    """--rcos-api should parse cleanly and reach the ordinary interactive runner."""
    seen: dict[str, object] = {}

    monkeypatch.setattr(cca8_run, "install_terminal_tee", lambda *args, **kwargs: None)

    def fake_interactive_loop(args) -> None:
        seen["rcos_api"] = args.rcos_api
        seen["profile"] = args.profile

    monkeypatch.setattr(cca8_run, "interactive_loop", fake_interactive_loop)

    assert cca8_run.main(["--rcos-api", "--no-intro"]) == 0
    assert seen == {"rcos_api": True, "profile": None}


def test_main_rejects_removed_demo_world_and_conflicting_startup_modes() -> None:
    """The retired flag should fail, and RCOS/profile startup modes should be exclusive."""
    assert cca8_run.main(["--demo-world"]) == 2
    assert cca8_run.main(["--rcos-api", "--profile", "human"]) == 2
