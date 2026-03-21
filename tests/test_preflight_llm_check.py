# -*- coding: utf-8 -*-
"""
Unit tests for the preflight LLM operational smoke-test helper.

These tests do not make live network calls. They verify only the local control flow:
skip when unconfigured, pass on a mocked success, and fail on a mocked runtime error.
"""

from __future__ import annotations

import sys
import types

import pytest

import cca8_run


class _FakeAuthenticationError(Exception):
    """Fake OpenAI auth error for unit testing."""


class _FakeAPIConnectionError(Exception):
    """Fake OpenAI connection error for unit testing."""


class _FakeAPIStatusError(Exception):
    """Fake OpenAI API status error for unit testing."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeResponse:
    """Minimal fake Responses API object with the field our helper prefers first."""

    def __init__(self, text: str) -> None:
        self.output_text = text


class _FakeResponsesOK:
    """Fake responses endpoint that returns the expected smoke-test token."""

    def create(self, **_kwargs):
        return _FakeResponse("CCA8_LLM_SMOKE_TEST_OK")


class _FakeResponsesFail:
    """Fake responses endpoint that raises a generic runtime failure."""

    def create(self, **_kwargs):
        raise RuntimeError("boom")


class _FakeClientOK:
    """Fake OpenAI client whose responses endpoint succeeds."""

    def __init__(self, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.responses = _FakeResponsesOK()


class _FakeClientFail:
    """Fake OpenAI client whose responses endpoint fails."""

    def __init__(self, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.responses = _FakeResponsesFail()


def _install_fake_openai(monkeypatch: pytest.MonkeyPatch, client_cls) -> None:
    """Install a tiny fake 'openai' module into sys.modules for one test."""
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = client_cls
    fake_openai.AuthenticationError = _FakeAuthenticationError
    fake_openai.APIConnectionError = _FakeAPIConnectionError
    fake_openai.APIStatusError = _FakeAPIStatusError
    monkeypatch.setitem(sys.modules, "openai", fake_openai)


def test_run_llm_operational_preflight_check_skips_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """No API key should produce a clean skip, not a failure."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = cca8_run.run_llm_operational_preflight_check(timeout_seconds=0.1)

    assert result["status"] == "skip"
    assert "OPENAI_API_KEY" in str(result["detail"])


def test_run_llm_operational_preflight_check_passes_with_mocked_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mocked successful client should produce a pass result."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(cca8_run, "_openai_default_model_name", lambda: "fake-model")
    monkeypatch.setattr(cca8_run, "_openai_response_request_options_v1", lambda: {})
    _install_fake_openai(monkeypatch, _FakeClientOK)

    result = cca8_run.run_llm_operational_preflight_check(timeout_seconds=0.1)

    assert result["status"] == "pass"
    assert result["model"] == "fake-model"


def test_run_llm_operational_preflight_check_fails_on_mocked_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured client that raises unexpectedly should produce a fail result."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(cca8_run, "_openai_default_model_name", lambda: "fake-model")
    monkeypatch.setattr(cca8_run, "_openai_response_request_options_v1", lambda: {})
    _install_fake_openai(monkeypatch, _FakeClientFail)

    result = cca8_run.run_llm_operational_preflight_check(timeout_seconds=0.1)

    assert result["status"] == "fail"
    assert "RuntimeError" in str(result["detail"])