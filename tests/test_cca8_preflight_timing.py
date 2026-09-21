"""Optional preflight phase/duration diagnostics without a second pytest execution.

The unit-dispatch integration fixtures substitute pytest.main and the optional
external LLM check. They execute the normal remaining preflight/reporting code in
an isolated temporary directory; they do not recursively run the real test suite
or claim the missing temporary accessory files passed architectural probes.
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

import pytest

import cca8_preflight
import cca8_run


@pytest.mark.parametrize("coverage", [False, True])
@pytest.mark.parametrize("config", [False, True])
def test_timing_only_adds_duration_reporting_to_unchanged_selection_and_coverage(coverage, config):
    plain = cca8_preflight._build_pytest_args(coverage_enabled=coverage, coveragerc_exists=config)
    timed = cca8_preflight._build_pytest_args(coverage_enabled=coverage, coveragerc_exists=config, timing_enabled=True)
    assert [arg for arg in timed if not arg.startswith("--durations")] == plain
    assert timed.count("tests") == 1 and timed[-1] == "tests"
    assert "--durations=20" in timed and "--durations-min=0.5" in timed
    assert "--junitxml=.coverage/junit.xml" in timed
    assert not any(arg.startswith("--durations") for arg in plain)
    assert ("no:pytest_cov" in timed) is not coverage


@pytest.mark.parametrize("options,timing,coverage", [(["--preflight"], False, False),
    (["--preflight", "--timing"], True, False), (["--preflight", "--timing", "--coverage"], True, True)])
def test_cli_passes_independent_optional_flags_once(monkeypatch, options, timing, coverage):
    calls = []
    monkeypatch.setattr(cca8_run, "run_preflight_full", lambda args: calls.append(args) or 0)
    assert cca8_run.main(options) == 0
    assert len(calls) == 1 and calls[0].timing is timing and calls[0].coverage is coverage


@pytest.mark.parametrize("options", [["--timing"], ["--timing", "--about"], ["--timing", "--coverage"]])
def test_timing_without_preflight_rejected_without_interactive_or_test_work(monkeypatch, capsys, options):
    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid timing usage must not invoke preflight or the interactive loop")
    monkeypatch.setattr(cca8_run, "run_preflight_full", forbidden)
    monkeypatch.setattr(cca8_run, "interactive_loop", forbidden)
    assert cca8_run.main(options) == 2
    assert "--timing requires --preflight" in capsys.readouterr().err


@pytest.mark.parametrize("exit_code", [0, 1, "exception"])
def test_timing_preserves_test_dispatch_failure_and_summary_semantics(tmp_path, exit_code):
    """Isolate actual probe side effects from this process's unrelated unit tests."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "tests").mkdir()
    program = r"""
import contextlib, io, json, sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import pytest
import cca8_preflight
import cca8_run
exit_code = json.loads(sys.argv[2])
captured = []
with patch.object(cca8_preflight, "run_preflight_full", lambda args, runtime: captured.append(runtime) or 0):
    cca8_run.run_preflight_full(SimpleNamespace())
runtime = replace(captured[0], llm_operational_check=lambda _timeout: {"status": "skip", "reason": "test fixture"})
calls = []
def fake_pytest(args):
    calls.append(list(args))
    failure = 1 if exit_code else 0
    Path(".coverage/junit.xml").write_text(
        f'<testsuite tests="3" failures="{failure}" errors="0" skipped="0"/>', encoding="utf-8")
    if exit_code == "exception":
        raise RuntimeError("deliberate unit dispatch fixture failure")
    return exit_code
runs = []
with patch.object(pytest, "main", fake_pytest):
    for args in (SimpleNamespace(hal=False, body=""), SimpleNamespace(hal=False, body="", timing=True)):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cca8_preflight.run_preflight_full(args, runtime)
        runs.append([code, output.getvalue()])
print(json.dumps({"runs": runs, "calls": calls}))
"""
    completed = subprocess.run([sys.executable, "-c", program, str(root), json.dumps(exit_code)], cwd=tmp_path,
                               capture_output=True, text=True, check=True, timeout=30)
    data = json.loads(completed.stdout)
    (rc_plain, plain), (rc_timed, timed) = data["runs"]
    calls = data["calls"]
    assert len(calls) == 2  # One unit dispatch per requested preflight; no recursive suite run.
    assert rc_plain == rc_timed
    assert not any(arg.startswith("--durations") for arg in calls[0])
    assert "--durations=20" in calls[1]
    assert "[preflight timing]" not in plain
    for label in ("unit tests (including collection/reporting)", "architecture/scenario probes", "hardware/robotics checks",
                  "system-fitness assessments", "total (including preflight overhead)"):
        line, = [line for line in timed.splitlines() if line.startswith(f"[preflight timing] {label}:")]
        assert float(line.rsplit(":", 1)[1].strip().split()[0]) >= 0.0
    expected = "unit_tests=3/3" if exit_code == 0 else "unit_tests=2/3"
    assert expected in plain and expected in timed
    if exit_code:
        assert rc_timed != 0 and "RESULT: FAIL" in timed
        assert "pytest run error" in timed if exit_code == "exception" else "test run reported failures" in timed


def test_help_exposes_timing_without_running_preflight(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs): pytest.fail("help must not run preflight")
    monkeypatch.setattr(cca8_run, "run_preflight_full", forbidden)
    assert cca8_run.main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "--timing" in output and "--preflight" in output
