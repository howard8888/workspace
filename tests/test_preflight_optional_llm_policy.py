# -*- coding: utf-8 -*-
"""Tests for the non-blocking optional-LLM policy in full preflight."""

from __future__ import annotations

import sys
import types

import pytest

# This white-box test intentionally verifies one private aggregation-policy helper.
# pylint: disable=protected-access

import cca8_preflight


class _FakeAuthenticationError(Exception):
    """Fake OpenAI authentication error for redaction testing."""


class _FakeResponsesAuthFailure:  # pylint: disable=too-few-public-methods
    """Fake Responses endpoint that rejects the supplied key."""

    def create(self, **_kwargs) -> None:
        """Raise the fake authentication error for every request."""
        raise _FakeAuthenticationError("sensitive-key-fragment")


class _FakeClientAuthFailure:  # pylint: disable=too-few-public-methods
    """Fake OpenAI client whose Responses endpoint rejects authentication."""

    def __init__(self, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.responses = _FakeResponsesAuthFailure()


def test_optional_llm_assessment_keeps_success_as_pass() -> None:
    """A successful live LLM probe should remain a Part-4 pass."""
    severity, message = cca8_preflight._classify_llm_preflight_assessment(
        {
            "status": "pass",
            "summary": "LLM smoke test passed",
            "detail": "live API call returned the expected reply",
            "model": "fake-model",
        }
    )

    assert severity == "pass"
    assert "fake-model" in message


def test_optional_llm_assessment_downgrades_unavailability_to_warning() -> None:
    """Missing or unusable optional OpenAI access should not block the full preflight."""
    for status in ("skip", "fail"):
        severity, message = cca8_preflight._classify_llm_preflight_assessment(
            {
                "status": status,
                "summary": "LLM smoke test unavailable",
                "detail": "OPENAI_API_KEY missing or invalid",
                "model": "fake-model",
            }
        )

        assert severity == "warning"
        assert "core CCA8 preflight continues" in message


def test_authentication_detail_does_not_echo_sdk_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """An authentication warning should not repeat a key fragment supplied by the SDK."""
    fake_openai = types.ModuleType("openai")
    setattr(fake_openai, "OpenAI", _FakeClientAuthFailure)
    setattr(fake_openai, "AuthenticationError", _FakeAuthenticationError)
    setattr(fake_openai, "APIConnectionError", RuntimeError)
    setattr(fake_openai, "APIStatusError", RuntimeError)

    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    result = cca8_preflight.run_llm_operational_preflight_check(
        timeout_seconds=0.1,
        default_model_name=lambda: "fake-model",
        response_request_options=lambda: {},
        response_text=lambda _response: "",
    )

    assert result["status"] == "fail"
    assert "OPENAI_API_KEY was rejected" in str(result["detail"])
    assert "sensitive-key-fragment" not in str(result["detail"])
