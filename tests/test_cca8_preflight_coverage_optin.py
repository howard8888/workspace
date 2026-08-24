# -*- coding: utf-8 -*-
"""Tests for opt-in pure-Python coverage behavior in CCA8 preflight."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import cca8_preflight


def _set_fake_distributions(
    monkeypatch: pytest.MonkeyPatch,
    *,
    coverage_files: list[str],
    pytest_cov_installed: bool = True,
) -> None:
    """Provide deterministic package metadata without importing Coverage.py."""

    def fake_distribution(name: str):
        if name == "coverage":
            return SimpleNamespace(files=list(coverage_files))
        if name == "pytest-cov" and pytest_cov_installed:
            return SimpleNamespace(files=[])
        raise cca8_preflight.importlib_metadata.PackageNotFoundError(name)

    monkeypatch.setattr(
        cca8_preflight.importlib_metadata,
        "distribution",
        fake_distribution,
    )


def test_coverage_is_not_requested_by_default() -> None:
    """Missing coverage flag must preserve the coverage-free preflight default."""
    assert cca8_preflight._coverage_requested(SimpleNamespace()) is False


def test_coverage_flag_explicitly_enables_request() -> None:
    """The explicit coverage flag should be the only normal opt-in path."""
    assert cca8_preflight._coverage_requested(SimpleNamespace(coverage=True)) is True


def test_native_coverage_tracer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """CCA8 must refuse coverage before a native tracer can be imported."""
    _set_fake_distributions(
        monkeypatch,
        coverage_files=[
            "coverage/__init__.py",
            "coverage/tracer.cp313-win_amd64.pyd",
        ],
    )

    ready, message = cca8_preflight._coverage_preflight_status()

    assert ready is False
    assert "native Coverage tracer" in message


def test_pure_python_coverage_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pure-Python Coverage.py plus pytest-cov should satisfy the opt-in contract."""
    _set_fake_distributions(
        monkeypatch,
        coverage_files=[
            "coverage/__init__.py",
            "coverage/py.typed",
        ],
    )

    ready, message = cca8_preflight._coverage_preflight_status()

    assert ready is True
    assert "pure-Python" in message


def test_missing_pytest_cov_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit coverage should fail clearly when its pytest plugin is absent."""
    _set_fake_distributions(
        monkeypatch,
        coverage_files=["coverage/__init__.py"],
        pytest_cov_installed=False,
    )

    ready, message = cca8_preflight._coverage_preflight_status()

    assert ready is False
    assert "pytest-cov is not installed" in message


def test_default_pytest_args_contain_no_coverage_options() -> None:
    """Normal preflight must explicitly prevent pytest-cov from loading."""
    args = cca8_preflight._build_pytest_args(
        coverage_enabled=False,
        coveragerc_exists=True,
    )

    assert not any(arg.startswith("--cov") for arg in args)
    assert "-p" in args
    assert args[args.index("-p") + 1] == "no:pytest_cov"


def test_opt_in_pytest_args_use_xml_without_terminal_coverage_table() -> None:
    """Explicit coverage should retain the XML artifact without the verbose table."""
    args = cca8_preflight._build_pytest_args(
        coverage_enabled=True,
        coveragerc_exists=True,
    )

    cov_pairs = list(zip(args, args[1:]))
    assert ("--cov", "cca8_run") in cov_pairs
    assert "--cov-config" in args
    assert "--cov-report=xml:.coverage/coverage.xml" in args
    assert "--cov-report=term-missing" not in args