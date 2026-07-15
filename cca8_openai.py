#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI/LLM integration, evaluation, and Menu 48 subsystem for CCA8.

Purpose
-------
This module owns CCA8's OpenAI-facing functionality: environment-variable
configuration, Responses API request settings, error/usage normalization,
state-summary construction, structured evaluation helpers, live smoke tests,
and the complete Menu 48 terminal flow.

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. Three tiny runner-owned graph and
timekeeping helpers are supplied through :class:`OpenAIRuntime`. Menu callables
may be supplied through immutable operation tables so ``cca8_run`` can retain
its historical names and call-time monkeypatch seams without creating a
circular import.

Network behavior
----------------
Importing this module never performs a network request and does not require the
``openai`` package. The SDK is imported only inside live smoke/demo/evaluation
functions. Pure configuration and response-normalization helpers remain usable
without the optional dependency.
"""

from __future__ import annotations

# The extracted menu/evaluation flow intentionally preserves the runner's
# defensive and terminal-oriented structure.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=import-outside-toplevel
# pylint: disable=protected-access
# pylint: disable=too-many-lines
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

import hashlib
import json
import logging
import os
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, DefaultDict, Optional

from cca8_controller import (
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_space_zone,
    bodymap_is_stale,
)

__version__ = "0.1.0"


@dataclass(frozen=True, slots=True)
class OpenAIRuntime:  # pylint: disable=too-few-public-methods
    """Runner-owned lookup helpers used by CCA8 state-summary construction.

    The OpenAI subsystem needs only three operations that remain naturally
    runner-owned: the human-readable timekeeping line, anchor lookup, and
    numerically sorted binding ids. Supplying them explicitly keeps this module
    import-safe and preserves replacement hooks used by tests and downstream
    tools.
    """

    timekeeping_line: Callable[[Any], str]
    anchor_id: Callable[[Any, str], str]
    sorted_bids: Callable[[Any], list[str]]


@dataclass(frozen=True, slots=True)
class OpenAIAdvancedMenuOperations:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Callables used by the extracted advanced-settings submenu."""

    configure_temperature: Callable[[], None]
    configure_top_p: Callable[[], None]
    configure_max_output_tokens: Callable[[], None]
    configure_reasoning_effort: Callable[[], None]
    clear_settings: Callable[[], None]


@dataclass(frozen=True, slots=True)
class OpenAIMenuOperations:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-visible operations used by the extracted Menu 48 flow."""

    sdk_version_text: Callable[[], str]
    default_model_name: Callable[[], str]
    advanced_settings_one_line: Callable[[], str]
    configure_api_key: Callable[[], None]
    configure_model: Callable[[], None]
    run_smoke_test: Callable[[], None]
    print_install_help: Callable[[], None]
    run_state_summary_demo: Callable[[Any, Any, Any], None]
    open_advanced_settings: Callable[[], None]
    run_eval_harness: Callable[[Any, Any, Any], None]


__all__ = [
    "OpenAIRuntime",
    "OpenAIAdvancedMenuOperations",
    "OpenAIMenuOperations",
    "OPENAI_REASONING_EFFORT_OPTIONS",
    "OPENAI_ADVANCED_ENV_NAMES",
    "build_cca8_llm_state_summary_v1",
    "configure_openai_api_key_interactive",
    "configure_openai_model_interactive",
    "configure_openai_temperature_interactive",
    "configure_openai_top_p_interactive",
    "configure_openai_max_output_tokens_interactive",
    "configure_openai_reasoning_effort_interactive",
    "clear_openai_advanced_settings_interactive",
    "openai_advanced_settings_menu_interactive",
    "print_openai_install_help",
    "run_openai_smoke_test_interactive",
    "run_cca8_llm_eval_harness_interactive",
    "run_cca8_llm_state_summary_demo_interactive",
    "openai_menu_48_interactive",
    "__version__",
]


def _fallback_timekeeping_line(ctx: Any) -> str:
    """Return a compact timekeeping line when no runner runtime is supplied."""
    controller_steps = int(getattr(ctx, "controller_steps", 0) or 0)
    boundary_no = int(getattr(ctx, "boundary_no", 0) or 0)
    ticks = int(getattr(ctx, "ticks", 0) or 0)
    age_days = float(getattr(ctx, "age_days", 0.0) or 0.0)
    cog_cycles = int(getattr(ctx, "cog_cycles", 0) or 0)

    try:
        cosine = ctx.cos_to_last_boundary()
        cosine_text = f"{cosine:.4f}" if isinstance(cosine, float) else "(n/a)"
    except Exception:
        cosine_text = "(n/a)"

    return (
        f"controller_steps={controller_steps}, cos_to_last_boundary={cosine_text}, "
        f"temporal_epochs={boundary_no}, autonomic_ticks={ticks}, "
        f"age_days={age_days:.4f}, cog_cycles={cog_cycles}"
    )


def _world_snapshot_v1(world: Any) -> dict[str, Any]:
    """Return a public JSON-safe WorldGraph snapshot, or an empty dict.

    The OpenAI subsystem is intentionally outside the small set of trusted
    modules allowed to inspect WorldGraph internals. Reading through the public
    ``to_dict()`` interface keeps this module independent of private storage
    details while preserving the historical read-only state-summary behavior.
    """
    try:
        to_dict = getattr(world, "to_dict", None)
        snapshot = to_dict() if callable(to_dict) else {}
    except Exception:
        return {}

    return snapshot if isinstance(snapshot, dict) else {}


def _fallback_anchor_id(world: Any, name: str = "NOW") -> str:
    """Return an anchor binding id without depending on the runner module."""
    snapshot = _world_snapshot_v1(world)
    anchors = snapshot.get("anchors")
    if isinstance(anchors, dict):
        bid = anchors.get(name)
        if isinstance(bid, str) and bid:
            return bid

    wanted = f"anchor:{name}"
    bindings = snapshot.get("bindings")
    if isinstance(bindings, dict):
        for bid, binding in bindings.items():
            if not isinstance(binding, dict):
                continue
            tags = binding.get("tags") or []
            if wanted in tags:
                return str(bid)

    return "?"


def _fallback_sorted_bids(world: Any) -> list[str]:
    """Return binding ids in the runner's numeric-first display order."""
    snapshot = _world_snapshot_v1(world)
    bindings = snapshot.get("bindings")
    ids = list(bindings.keys()) if isinstance(bindings, dict) else []

    def sort_key(bid: Any) -> tuple[int, int | str]:
        text = str(bid)
        if text.startswith("b") and text[1:].isdigit():
            return (0, int(text[1:]))
        return (1, text)

    return [str(item) for item in sorted(ids, key=sort_key)]


def _default_openai_runtime() -> OpenAIRuntime:
    """Build the standalone fallback runtime for direct module callers."""
    return OpenAIRuntime(
        timekeeping_line=_fallback_timekeeping_line,
        anchor_id=_fallback_anchor_id,
        sorted_bids=_fallback_sorted_bids,
    )


def _openai_response_text_best_effort(response: Any) -> str:
    """Extract plain text from an OpenAI Responses API object as defensively as possible.

    Purpose / intent
    ----------------
    Menu 48 and preflight both care about a very small question: did the model return a short text reply?
    Newer SDKs usually expose ``response.output_text`` directly, but we also walk the structured
    ``response.output[*].content[*].text`` shape as a fallback so the preflight stays robust across small SDK
    response-shape differences.

    Parameters
    ----------
    response:
        The object returned by ``client.responses.create(...)``.

    Returns
    -------
    str
        Stripped text if we can find it, otherwise an empty string.

    Notes
    -----
    This helper is intentionally read-only and best-effort. It should never raise. Preflight must remain
    informative even when the SDK shape changes or a mocked response object is incomplete.
    """
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    try:
        output = getattr(response, "output", None)
        if isinstance(output, list):
            pieces: list[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for part in content:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str) and part_text:
                        pieces.append(part_text)
            if pieces:
                return "".join(pieces).strip()
    except Exception:
        pass

    return ""


def _save_openai_api_key_windows_user_env(api_key: str) -> tuple[bool, str]:
    """Persist OPENAI_API_KEY for future Windows cmd.exe sessions using setx.

    Important:
        - setx affects future shells, not the current process.
        - We also set os.environ in the current process so the key works immediately inside this run.
    """
    try:
        result = subprocess.run(
            ["setx", "OPENAI_API_KEY", api_key],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
    except Exception as e:
        return False, f"Could not run setx: {e}"

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip() or f"setx failed with exit code {result.returncode}"
        return False, msg

    msg = (result.stdout or "").strip() or "OPENAI_API_KEY saved with setx."
    return True, msg


def _openai_sdk_version_text() -> str:
    """Return installed openai SDK version text, or '(not installed)'."""
    try:
        import openai  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
        return str(getattr(openai, "__version__", "(unknown)"))
    except Exception:
        return "(not installed)"


def _openai_default_model_name() -> str:
    """Return the default model name used by CCA8 menu 48 smoke tests.

    This is a CCA8 runner setting, not an OpenAI SDK requirement.
    """
    model_name = os.environ.get("CCA8_OPENAI_MODEL", "").strip()
    return model_name or "gpt-5.4"


def _save_cca8_openai_model_windows_user_env(model_name: str) -> tuple[bool, str]:
    """Persist CCA8_OPENAI_MODEL for future Windows cmd.exe sessions using setx."""
    try:
        result = subprocess.run(
            ["setx", "CCA8_OPENAI_MODEL", model_name],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
    except Exception as e:
        return False, f"Could not run setx: {e}"

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip() or f"setx failed with exit code {result.returncode}"
        return False, msg

    msg = (result.stdout or "").strip() or "CCA8_OPENAI_MODEL saved with setx."
    return True, msg


OPENAI_REASONING_EFFORT_OPTIONS = ("none", "minimal", "low", "medium", "high", "xhigh")
OPENAI_ADVANCED_ENV_NAMES = (
    "CCA8_OPENAI_TEMPERATURE",
    "CCA8_OPENAI_TOP_P",
    "CCA8_OPENAI_MAX_OUTPUT_TOKENS",
    "CCA8_OPENAI_REASONING_EFFORT",
)


def _save_windows_user_env(name: str, value: str) -> tuple[bool, str]:
    """Persist one user environment variable for future Windows cmd.exe sessions using setx.

    This is used for non-secret Menu 48 tuning knobs. The current process must still update
    os.environ separately because setx only affects future shells.
    """
    try:
        result = subprocess.run(
            ["setx", name, value],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
    except Exception as e:
        return False, f"Could not run setx: {e}"

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip() or f"setx failed with exit code {result.returncode}"
        return False, msg

    msg = (result.stdout or "").strip() or f"{name} saved with setx."
    return True, msg


def _delete_windows_user_env(name: str) -> tuple[bool, str]:
    """Delete one user environment variable for future Windows cmd.exe sessions.

    We delete from HKCU\\Environment so a reset-to-default in Menu 48 really clears the saved
    value for future cmd.exe shells instead of merely setting a blank string.
    """
    try:
        result = subprocess.run(
            ["reg", "delete", r"HKCU\Environment", "/v", name, "/f"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
    except Exception as e:
        return False, f"Could not run reg delete: {e}"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode == 0:
        return True, stdout or f"{name} removed from HKCU\\Environment."

    lower = (stdout + "\n" + stderr).lower()
    if "unable to find" in lower or "cannot find" in lower:
        return True, f"{name} was not present in HKCU\\Environment."

    msg = stderr or stdout or f"reg delete failed with exit code {result.returncode}"
    return False, msg


def _openai_temperature_value() -> Optional[float]:
    """Return Menu 48 temperature override if present and valid, else None."""
    raw = os.environ.get("CCA8_OPENAI_TEMPERATURE", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not 0.0 <= value <= 2.0:
        return None
    return value


def _openai_top_p_value() -> Optional[float]:
    """Return Menu 48 top_p override if present and valid, else None."""
    raw = os.environ.get("CCA8_OPENAI_TOP_P", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not 0.0 < value <= 1.0:
        return None
    return value


def _openai_max_output_tokens_value() -> Optional[int]:
    """Return Menu 48 max_output_tokens override if present and valid, else None."""
    raw = os.environ.get("CCA8_OPENAI_MAX_OUTPUT_TOKENS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _openai_reasoning_effort_value() -> Optional[str]:
    """Return Menu 48 reasoning-effort override if present and valid, else None."""
    raw = os.environ.get("CCA8_OPENAI_REASONING_EFFORT", "").strip().lower()
    if not raw:
        return None
    if raw not in OPENAI_REASONING_EFFORT_OPTIONS:
        return None
    return raw


def _openai_advanced_settings_snapshot() -> dict[str, Any]:
    """Return the parsed advanced Menu 48 request settings.

    These settings are intentionally request-focused rather than architecture-focused. They
    already map onto the current Responses API path used by both the smoke test and demo,
    so they are immediately testable while still being useful for future experiments.
    """
    return {
        "temperature": _openai_temperature_value(),
        "top_p": _openai_top_p_value(),
        "max_output_tokens": _openai_max_output_tokens_value(),
        "reasoning_effort": _openai_reasoning_effort_value(),
    }


def _openai_advanced_settings_one_line() -> str:
    """Return one compact human-readable summary of active advanced settings."""
    settings = _openai_advanced_settings_snapshot()
    parts: list[str] = []

    temp = settings.get("temperature")
    if isinstance(temp, float):
        parts.append(f"temperature={temp:.3f}")

    top_p = settings.get("top_p")
    if isinstance(top_p, float):
        parts.append(f"top_p={top_p:.3f}")

    mot = settings.get("max_output_tokens")
    if isinstance(mot, int):
        parts.append(f"max_output_tokens={mot}")

    effort = settings.get("reasoning_effort")
    if isinstance(effort, str) and effort:
        parts.append(f"reasoning_effort={effort}")

    return ", ".join(parts) if parts else "(defaults)"


def _openai_response_request_options_v1() -> dict[str, Any]:
    """Return optional Responses API kwargs derived from Menu 48 advanced settings."""
    settings = _openai_advanced_settings_snapshot()
    opts: dict[str, Any] = {}

    temp = settings.get("temperature")
    if isinstance(temp, float):
        opts["temperature"] = temp

    top_p = settings.get("top_p")
    if isinstance(top_p, float):
        opts["top_p"] = top_p

    mot = settings.get("max_output_tokens")
    if isinstance(mot, int):
        opts["max_output_tokens"] = mot

    effort = settings.get("reasoning_effort")
    if isinstance(effort, str) and effort:
        opts["reasoning"] = {"effort": effort}

    return opts


def _openai_quiet_http_loggers_v1() -> None:
    """Lower transport/client loggers to WARNING so experiment runs do not flood the terminal.

    The runner uses root logging at INFO level. That is fine for CCA8 itself, but it also allows
    httpx/openai transport logs to print one line per request. During submenu 20/21 runs this can
    dominate the terminal and make the experiment look "slow" even when the real problem is simply
    repeated request rejection. This helper quiets only the noisy transport/client loggers.
    """
    for name in ("httpx", "httpcore", "openai", "openai._base_client"):
        try:
            logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass


def _openai_sanitize_adviser_request_options_v1(request_opts: dict[str, Any] | None) -> dict[str, Any]:
    """Return conservative Responses API kwargs for bounded adviser calls.

    Design choice
    -------------
    The submenu-48 advanced settings are useful for interactive demos and smoke tests, but the
    bounded adviser path is different:
      - it is schema-first,
      - it is called many times,
      - and we want maximum stability, not tunability.

    Therefore, for adviser calls I keep only `max_output_tokens` and drop the menu-level sampling /
    tuning knobs. That is the safest first step when the current issue is repeated HTTP 400 errors.
    Once the adviser path is stable, we can selectively reintroduce other options later.
    """
    out: dict[str, Any] = {}
    if isinstance(request_opts, dict):
        mot = request_opts.get("max_output_tokens")
        if isinstance(mot, int) and mot > 0:
            out["max_output_tokens"] = mot
    return out


def _openai_api_error_detail_v1(exc: Any) -> dict[str, Any]:
    """Extract a compact JSON-safe detail bundle from an OpenAI SDK exception.

    Purpose
    -------
    `str(e)` is often too vague for debugging repeated adviser failures. When the SDK gives us an
    HTTP response body, I try to pull out the API message, offending param, and code so the runner
    can print one helpful line instead of a wall of transport logs.
    """
    out: dict[str, Any] = {
        "message": str(exc),
        "status_code": getattr(exc, "status_code", None),
        "param": None,
        "code": None,
        "payload": None,
        "body_text": None,
    }

    response = getattr(exc, "response", None)
    if response is None:
        return out

    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        err = payload.get("error")
        err = err if isinstance(err, dict) else {}

        msg = err.get("message")
        if isinstance(msg, str) and msg:
            out["message"] = msg

        param = err.get("param")
        if isinstance(param, str) and param:
            out["param"] = param

        code = err.get("code")
        if isinstance(code, str) and code:
            out["code"] = code

        out["payload"] = payload
        return out

    try:
        text = response.text
    except Exception:
        text = None

    if isinstance(text, str) and text.strip():
        out["body_text"] = text[:500]

    return out


def _set_openai_advanced_env(name: str, value: Optional[str]) -> None:
    """Set or clear one Menu 48 advanced environment variable.

    The current process is always updated immediately. On Windows, we also persist the change for
    future cmd.exe sessions. On non-Windows platforms we keep the current process updated and print
    a small reminder about shell startup files.
    """
    if value is None:
        os.environ.pop(name, None)
        print(f"[llm-adv] Cleared {name} in the current process.")

        if os.name == "nt":
            ok, msg = _delete_windows_user_env(name)
            if ok:
                print(f"[llm-adv] Cleared {name} for future Windows cmd.exe sessions.")
                print(f"[llm-adv] reg: {msg}")
                print("[llm-adv] Note: a NEW cmd.exe window will see the cleared value automatically.")
            else:
                print(f"[llm-adv] Warning: {name} was cleared for this run, but persistence failed.")
                print(f"[llm-adv] reg error: {msg}")
        else:
            print(f"[llm-adv] Non-Windows OS detected; {name} was cleared only for this current process.")
            print(f"[llm-adv] Remove {name} from your shell startup file too if you saved it there manually.")
        return

    os.environ[name] = value
    print(f"[llm-adv] Loaded {name} into current process: {value}")

    if os.name == "nt":
        ok, msg = _save_windows_user_env(name, value)
        if ok:
            print(f"[llm-adv] Saved {name} for future Windows cmd.exe sessions.")
            print(f"[llm-adv] setx: {msg}")
            print("[llm-adv] Note: a NEW cmd.exe window will see the saved value automatically.")
        else:
            print(f"[llm-adv] Warning: {name} was loaded for this run, but persistence failed.")
            print(f"[llm-adv] setx error: {msg}")
    else:
        print(f"[llm-adv] Non-Windows OS detected; {name} was saved only for this current process.")
        print(f"[llm-adv] Add {name} to your shell startup file if you want persistence.")


def configure_openai_temperature_interactive() -> None:
    """Configure Menu 48 temperature override for future smoke tests and demos."""
    print("\nSelection: Configure OpenAI / LLM temperature override")
    print("  - Responses API range is 0.0 to 2.0.")
    print("  - Lower values are usually more focused / repeatable.")
    print("  - Blank input cancels without changing anything.")
    print("  - Type DEFAULT to clear this override and use the API/model default.\n")

    current = _openai_temperature_value()
    print(f"[llm-adv] Current temperature override: {current if current is not None else '(default)'}")

    raw = input("\nEnter temperature [0.0..2.0] (blank=cancel, DEFAULT=clear): ").strip()
    if not raw:
        print("[llm-adv] Cancelled. No changes made.")
        return

    if raw.lower() == "default":
        _set_openai_advanced_env("CCA8_OPENAI_TEMPERATURE", None)
        return

    try:
        value = float(raw)
    except ValueError:
        print("[llm-adv] Invalid temperature. Please enter a numeric value such as 0.2 or 1.0.")
        return

    if not 0.0 <= value <= 2.0:
        print("[llm-adv] Temperature must be between 0.0 and 2.0.")
        return

    _set_openai_advanced_env("CCA8_OPENAI_TEMPERATURE", str(value))


def configure_openai_top_p_interactive() -> None:
    """Configure Menu 48 top_p override for future smoke tests and demos."""
    print("\nSelection: Configure OpenAI / LLM top_p override")
    print("  - Responses API range is >0.0 and <=1.0.")
    print("  - This is an alternative to broad temperature changes.")
    print("  - Blank input cancels without changing anything.")
    print("  - Type DEFAULT to clear this override and use the API/model default.\n")

    current = _openai_top_p_value()
    print(f"[llm-adv] Current top_p override: {current if current is not None else '(default)'}")

    raw = input("\nEnter top_p (>0.0 and <=1.0) (blank=cancel, DEFAULT=clear): ").strip()
    if not raw:
        print("[llm-adv] Cancelled. No changes made.")
        return

    if raw.lower() == "default":
        _set_openai_advanced_env("CCA8_OPENAI_TOP_P", None)
        return

    try:
        value = float(raw)
    except ValueError:
        print("[llm-adv] Invalid top_p. Please enter a numeric value such as 0.3 or 1.0.")
        return

    if not 0.0 < value <= 1.0:
        print("[llm-adv] top_p must be >0.0 and <=1.0.")
        return

    _set_openai_advanced_env("CCA8_OPENAI_TOP_P", str(value))


def configure_openai_max_output_tokens_interactive() -> None:
    """Configure Menu 48 max_output_tokens override for future smoke tests and demos."""
    print("\nSelection: Configure OpenAI / LLM max_output_tokens override")
    print("  - This caps total generated response tokens, including reasoning tokens.")
    print("  - Blank input cancels without changing anything.")
    print("  - Type DEFAULT to clear this override and use the API/model default.\n")

    current = _openai_max_output_tokens_value()
    print(f"[llm-adv] Current max_output_tokens override: {current if current is not None else '(default)'}")

    raw = input("\nEnter max_output_tokens (>0) (blank=cancel, DEFAULT=clear): ").strip()
    if not raw:
        print("[llm-adv] Cancelled. No changes made.")
        return

    if raw.lower() == "default":
        _set_openai_advanced_env("CCA8_OPENAI_MAX_OUTPUT_TOKENS", None)
        return

    try:
        value = int(raw)
    except ValueError:
        print("[llm-adv] Invalid max_output_tokens. Please enter an integer such as 120 or 400.")
        return

    if value <= 0:
        print("[llm-adv] max_output_tokens must be greater than zero.")
        return

    _set_openai_advanced_env("CCA8_OPENAI_MAX_OUTPUT_TOKENS", str(value))


def configure_openai_reasoning_effort_interactive() -> None:
    """Configure Menu 48 reasoning-effort override for gpt-5 / o-series style models."""
    print("\nSelection: Configure OpenAI / LLM reasoning effort override")
    print("  - Typical values: none, minimal, low, medium, high, xhigh.")
    print("  - Model support varies; unsupported values will be rejected by the API.")
    print("  - Blank input cancels without changing anything.")
    print("  - Type DEFAULT to clear this override and use the API/model default.\n")

    current = _openai_reasoning_effort_value()
    print(f"[llm-adv] Current reasoning_effort override: {current if current is not None else '(default)'}")

    raw = input("\nEnter reasoning_effort (blank=cancel, DEFAULT=clear): ").strip().lower()
    if not raw:
        print("[llm-adv] Cancelled. No changes made.")
        return

    if raw == "default":
        _set_openai_advanced_env("CCA8_OPENAI_REASONING_EFFORT", None)
        return

    if raw not in OPENAI_REASONING_EFFORT_OPTIONS:
        opts = ", ".join(OPENAI_REASONING_EFFORT_OPTIONS)
        print(f"[llm-adv] Invalid reasoning_effort. Choose one of: {opts}")
        return

    _set_openai_advanced_env("CCA8_OPENAI_REASONING_EFFORT", raw)


def clear_openai_advanced_settings_interactive() -> None:
    """Clear all Menu 48 advanced request settings back to defaults."""
    print("\nSelection: Clear all OpenAI / LLM advanced settings")
    print("  - This removes all Menu 48 request overrides and returns to defaults.")
    print("  - Blank input cancels. Type YES to continue.\n")

    confirm = input("Type YES to clear all advanced settings: ").strip()
    if confirm != "YES":
        print("[llm-adv] Cancelled. No changes made.")
        return

    for name in OPENAI_ADVANCED_ENV_NAMES:
        _set_openai_advanced_env(name, None)


def openai_advanced_settings_menu_interactive(
    operations: OpenAIAdvancedMenuOperations | None = None,
) -> None:
    """Submenu for advanced Menu 48 request knobs that already map to the current API path."""
    active_operations = operations or _default_openai_advanced_menu_operations()
    while True:
        print("\nSelection: OpenAI / LLM advanced request settings")
        print("  These settings apply to Menu 48 requests sent by the smoke test and CCA8 demo.")
        print(f"  Current active overrides: {_openai_advanced_settings_one_line()}")
        print("\n  1) Configure temperature")
        print("  2) Configure top_p")
        print("  3) Configure max_output_tokens")
        print("  4) Configure reasoning_effort")
        print("  5) Clear all advanced settings back to defaults")
        print("  Enter) Return to the Menu 48 screen")

        choice = input("\nChoose [1,2,3,4,5, Enter]: ").strip().lower()

        if choice == "":
            print("[llm-adv] Returning to the Menu 48 screen.")
            return
        if choice in ("1", "temp", "temperature"):
            active_operations.configure_temperature()
            continue
        if choice in ("2", "top", "top_p", "topp"):
            active_operations.configure_top_p()
            continue
        if choice in ("3", "tokens", "max", "max_output_tokens"):
            active_operations.configure_max_output_tokens()
            continue
        if choice in ("4", "reason", "reasoning", "effort", "reasoning_effort"):
            active_operations.configure_reasoning_effort()
            continue
        if choice in ("5", "clear", "reset", "defaults"):
            active_operations.clear_settings()
            continue

        print(f"[llm-adv] Unknown selection: {choice!r}")


def print_openai_install_help() -> None:
    """Print concise OpenAI / LLM API installation help."""
    print("\n[llm-help] OpenAI / LLM API setup")
    print("  1. Install the Python SDK into this SAME Python environment:")
    print("       python -m pip install --upgrade openai")
    print("  2. Verify which version this interpreter sees:")
    print('       python -c "import openai; print(openai.__version__)"')
    print("  3. Save your API key in menu 48, or otherwise set OPENAI_API_KEY in the environment.")
    print("  4. Optionally set a default smoke-test model in menu 48.")
    print("     - CCA8 stores this in CCA8_OPENAI_MODEL.")
    print("     - If unset, CCA8 defaults to gpt-5.4.")
    print("  5. Run the smoke test from menu 48 to verify:")
    print("       - the SDK imports correctly,")
    print("       - OPENAI_API_KEY is present,")
    print("       - the configured model name is being used, and")
    print("       - an actual API call succeeds.")
    print("  Notes:")
    print("       - Use 'python -m pip ...' so pip targets the same interpreter running CCA8.")
    print("       - On Windows, setx affects future cmd.exe windows, not the current one.")
    print("       - This menu also sets os.environ in the current CCA8 run, so testing can work immediately.")
    print("       - You need both a valid API key and API billing/credits for live calls.\n")


def configure_openai_api_key_interactive() -> None:
    """Interactively collect and save OPENAI_API_KEY for the current run and future Windows shells.

    House style / UX:
        - The user can see what they typed.
        - We do not print the full key back afterward.
        - Blank input cancels.
    """
    print("\nSelection: Configure OpenAI / LLM API key")
    print("  - Paste your OpenAI API key when prompted.")
    print("  - The key will be visible while typing.")
    print("  - Blank input cancels without changing anything.")
    print("  - In this current CCA8 run, the key is loaded into os.environ immediately,")
    print("    so you can test it right away without restarting CCA8.")
    print("  - On Windows, CCA8 also saves the key for future cmd.exe sessions with setx.")
    print("    Important: already-open terminals or IDE shells may still keep the old key")
    print("    until you close them and open a fresh terminal window.")
    print("  - On non-Windows systems, the key still works immediately in this current run,")
    print("    but persistence is usually manual via your shell startup file.\n")

    existing = os.environ.get("OPENAI_API_KEY", "").strip()
    if existing:
        print(f"[llm] OPENAI_API_KEY already present in current process (length={len(existing)}).")
    else:
        print("[llm] OPENAI_API_KEY is not currently set in this process.")

    api_key = input("\nPaste OpenAI API key (blank = cancel): ").strip()
    if not api_key:
        print("[llm] Cancelled. No changes made.")
        return

    os.environ["OPENAI_API_KEY"] = api_key
    print(f"[llm] Loaded OPENAI_API_KEY into current process (length={len(api_key)}).")

    if os.name == "nt":
        ok, msg = _save_openai_api_key_windows_user_env(api_key)
        if ok:
            print("[llm] Saved OPENAI_API_KEY for future Windows cmd.exe sessions.")
            print(f"[llm] setx: {msg}")
            print("[llm] Note: a NEW cmd.exe window will see the saved key automatically.")
        else:
            print("[llm] Warning: key loaded for this current run, but persistence failed.")
            print(f"[llm] setx error: {msg}")
    else:
        print("[llm] Non-Windows OS detected; key saved only for this current process.")
        print("[llm] This means the current CCA8 run can use it immediately.")
        print("[llm] For future terminal sessions, add OPENAI_API_KEY to your shell startup file")
        print("[llm] such as ~/.bashrc, ~/.zshrc, or the startup file used by your shell.")


def configure_openai_model_interactive() -> None:
    """Interactively collect and save the default model name used by menu 48 smoke tests."""
    print("\nSelection: Configure OpenAI / LLM default model")
    print("  - This sets the default model used by CCA8 menu 48 smoke tests.")
    print("  - Blank input cancels without changing anything.")
    print("  - Examples: gpt-5.4, gpt-5.4-mini, gpt-5.4-nano\n")

    current_model = _openai_default_model_name()
    print(f"[llm-model] Current default model: {current_model}")

    model_name = input("\nEnter model name (blank = cancel): ").strip()
    if not model_name:
        print("[llm-model] Cancelled. No changes made.")
        return

    os.environ["CCA8_OPENAI_MODEL"] = model_name
    print(f"[llm-model] Loaded CCA8_OPENAI_MODEL into current process: {model_name}")

    if os.name == "nt":
        ok, msg = _save_cca8_openai_model_windows_user_env(model_name)
        if ok:
            print("[llm-model] Saved CCA8_OPENAI_MODEL for future Windows cmd.exe sessions.")
            print(f"[llm-model] setx: {msg}")
            print("[llm-model] Note: a NEW cmd.exe window will see the saved model automatically.")
        else:
            print("[llm-model] Warning: model loaded for this current run, but persistence failed.")
            print(f"[llm-model] setx error: {msg}")
    else:
        print("[llm-model] Non-Windows OS detected; model saved only for this current process.")
        print("[llm-model] Add CCA8_OPENAI_MODEL to your shell startup file if you want persistence.")


def run_openai_smoke_test_interactive() -> None:
    """Test whether the OpenAI SDK imports and whether the current API key actually works.

    This folds the old standalone openai_smoke_test.py logic into menu 48 so users
    do not need to manage a separate file.
    """
    print("\n[llm-test] OpenAI SDK / API smoke test")
    print("[llm-test] This checks:")
    print("           1) whether the openai package imports,")
    print("           2) whether OPENAI_API_KEY is present,")
    print("           3) which model CCA8 will use, and")
    print("           4) whether a real API call succeeds.\n")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model_name = _openai_default_model_name()
    request_opts = _openai_response_request_options_v1()

    print(f"[llm-test] OPENAI_API_KEY present: {'yes' if api_key else 'no'}")
    if api_key:
        print(f"[llm-test] OPENAI_API_KEY length: {len(api_key)}")
    print(f"[llm-test] model: {model_name}")
    print(f"[llm-test] advanced settings: {_openai_advanced_settings_one_line()}")

    try:
        import openai  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
        from openai import OpenAI  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
    except Exception as e:
        print("[llm-test] OpenAI Python SDK is not available in this Python environment.")
        print("[llm-test] Install or upgrade it with:")
        print("           python -m pip install --upgrade openai")
        print(f"[llm-test] Import error: {e}")
        return

    sdk_ver = str(getattr(openai, "__version__", "(unknown)"))
    print(f"[llm-test] openai SDK version: {sdk_ver}")

    if not api_key:
        print("[llm-test] OPENAI_API_KEY is missing.")
        print("[llm-test] Use menu 48 to save the key, then run this test again.")
        return

    print("[llm-test] Sending a tiny test request...")

    try:
        client = OpenAI()
        response = client.responses.create(
            model=model_name,
            input="Reply with exactly: CCA8 smoke test ok.",
            **request_opts,
        )
        reply = getattr(response, "output_text", None)
        print("\n[llm-test] API call succeeded.")
        print("[llm-test] Model reply:")
        print(reply if isinstance(reply, str) and reply.strip() else "(no output_text returned)")
        return

    except openai.AuthenticationError as e:  #pylint: disable=unused-variable
        print("\n[llm-test] Authentication error.")
        print("[llm-test] The SDK imported correctly, but the API key was rejected.")
        #print(f"[llm-test] Details: {e}")
        print("[llm-demo] Details were redacted to avoid echoing API-key text into terminal output.")
        return

    except openai.RateLimitError as e:
        print("\n[llm-test] Rate-limit / quota / billing error.")
        print("[llm-test] The key was recognized, but the request could not proceed.")
        print(f"[llm-test] Details: {e}")
        return

    except openai.APIConnectionError as e:
        print("\n[llm-test] Connection error.")
        print("[llm-test] The SDK and key look present, but the network call failed.")
        print(f"[llm-test] Details: {e}")
        return

    except openai.APIStatusError as e:
        status_code = getattr(e, "status_code", "(unknown)")
        print(f"\n[llm-test] API status error (HTTP {status_code}).")
        print(f"[llm-test] Details: {e}")
        return

    except Exception as e:
        print("\n[llm-test] Unexpected error during smoke test.")
        print(f"[llm-test] Details: {e}")
        return


def build_cca8_llm_state_summary_v1(
    world: Any,
    drives: Any,
    ctx: Any,
    *,
    runtime: OpenAIRuntime | None = None,
) -> dict[str, Any]:
    """Build a tiny JSON-safe summary of the current CCA8 state.

    Purpose
    -------
    This is the first real CCA8 -> LLM bridge. I keep it deliberately small,
    stable, and readable so:
      - the prompt stays cheap,
      - the returned interpretation is easy to inspect,
      - and we do not accidentally turn the LLM into the controller.

    This is a read-only summary. It does NOT modify CCA8 state.

    The optional runtime supplies the three tiny runner-owned lookup helpers.
    Direct module callers may omit it and use the module fallbacks.
    """
    active_runtime = runtime or _default_openai_runtime()
    out: dict[str, Any] = {
        "schema": "cca8_llm_state_summary_v1",
        "profile": getattr(ctx, "profile", None),
        "age_days": float(getattr(ctx, "age_days", 0.0) or 0.0),
        "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
        "cog_cycles": int(getattr(ctx, "cog_cycles", 0) or 0),
        "autonomic_ticks": int(getattr(ctx, "ticks", 0) or 0),
        "timekeeping": None,
        "body": {
            "bodymap_stale": True,
            "posture": None,
            "mom_distance": None,
            "nipple_state": None,
            "zone": None,
        },
        "drives": {
            "hunger": None,
            "fatigue": None,
            "warmth": None,
        },
        "graph": {
            "now_bid": None,
            "latest_bid": None,
            "node_count": 0,
            "edge_count": 0,
        },
        "working_map": {
            "enabled": bool(getattr(ctx, "working_enabled", False)),
            "binding_count": 0,
        },
        "navsummary": {},
        "recent_bindings": [],
    }

    try:
        out["timekeeping"] = active_runtime.timekeeping_line(ctx)
    except Exception:
        out["timekeeping"] = None

    try:
        out["body"]["bodymap_stale"] = bool(bodymap_is_stale(ctx))
    except Exception:
        out["body"]["bodymap_stale"] = True

    try:
        out["body"]["posture"] = body_posture(ctx)
    except Exception:
        pass

    try:
        out["body"]["mom_distance"] = body_mom_distance(ctx)
    except Exception:
        pass

    try:
        out["body"]["nipple_state"] = body_nipple_state(ctx)
    except Exception:
        pass

    try:
        out["body"]["zone"] = body_space_zone(ctx)
    except Exception:
        pass

    try:
        out["drives"]["hunger"] = round(float(getattr(drives, "hunger", 0.0) or 0.0), 3)
        out["drives"]["fatigue"] = round(float(getattr(drives, "fatigue", 0.0) or 0.0), 3)
        out["drives"]["warmth"] = round(float(getattr(drives, "warmth", 0.0) or 0.0), 3)
    except Exception:
        pass

    try:
        out["graph"]["now_bid"] = active_runtime.anchor_id(world, "NOW")
    except Exception:
        pass

    world_snapshot = _world_snapshot_v1(world)
    bindings_snapshot = world_snapshot.get("bindings")
    bindings_snapshot = bindings_snapshot if isinstance(bindings_snapshot, dict) else {}

    try:
        out["graph"]["latest_bid"] = world_snapshot.get("latest")
    except Exception:
        pass

    try:
        out["graph"]["node_count"] = len(bindings_snapshot)

        edge_count = 0
        for binding_snapshot in bindings_snapshot.values():
            if not isinstance(binding_snapshot, dict):
                continue
            edges = binding_snapshot.get("edges", []) or []
            if isinstance(edges, list):
                edge_count += len(edges)
        out["graph"]["edge_count"] = edge_count
    except Exception:
        pass

    try:
        ww = getattr(ctx, "working_world", None)
        if ww is not None:
            working_snapshot = _world_snapshot_v1(ww)
            working_bindings = working_snapshot.get("bindings")
            if isinstance(working_bindings, dict):
                out["working_map"]["binding_count"] = len(working_bindings)
    except Exception:
        pass

    try:
        ns = getattr(ctx, "wm_navsummary", None)
        if isinstance(ns, dict) and ns:
            keep = (
                "hazard_near",
                "hazard_density",
                "traversable_near",
                "traversable_density",
                "corridor_count",
                "goal_present",
                "goal_dir",
                "goal_distance_l1",
                "shortest_safe_path_cost",
            )
            out["navsummary"] = {k: ns.get(k) for k in keep if k in ns}
    except Exception:
        pass

    try:
        recent: list[dict[str, Any]] = []
        for bid in active_runtime.sorted_bids(world)[-4:]:
            binding_snapshot = bindings_snapshot.get(bid)
            if not isinstance(binding_snapshot, dict):
                continue

            tags = [t for t in (binding_snapshot.get("tags", []) or []) if isinstance(t, str)]
            edges = binding_snapshot.get("edges", []) or []
            out_degree = len(edges) if isinstance(edges, list) else 0

            recent.append(
                {
                    "bid": bid,
                    "tags": sorted(tags)[:8],
                    "out_degree": out_degree,
                }
            )

        out["recent_bindings"] = recent
    except Exception:
        pass

    return out


def _cca8_llm_state_reply_schema_v1() -> dict[str, Any]:
    """Return the strict structured-reply schema used by Menu 48 state-summary requests.

    I keep this in one helper so the normal demo and the batch evaluation harness use the
    exact same output contract. That makes later comparisons more meaningful because any
    differences are coming from model behavior or request settings, not from two slightly
    different prompt/schema definitions drifting apart over time.
    """
    return {
        "type": "object",
        "properties": {
            "scene_label": {"type": "string"},
            "current_task": {"type": "string"},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "advice": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["scene_label", "current_task", "risk_flags", "advice", "confidence"],
        "additionalProperties": False,
    }


def _cca8_llm_state_reply_prompt_v1(state_summary: dict[str, Any]) -> str:
    """Return the conservative prompt used by the Menu 48 demo and evaluation harness."""
    return (
        "You are helping interpret a tiny CCA8 cognitive-architecture runtime snapshot. "
        "Be conservative. Use only the supplied JSON summary. "
        "Do not invent hidden sensors, hidden goals, or hidden world state. "
        "Return only a JSON object matching the required schema.\n\n"
        "CCA8 STATE SUMMARY JSON:\n"
        f"{json.dumps(state_summary, ensure_ascii=False)}"
    )


def _short_json_sig16_v1(obj: Any) -> str:
    """Return a short stable signature for a JSON-safe object."""
    try:
        blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        blob = json.dumps(str(obj), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _llm_eval_response_usage_v1(response: Any) -> dict[str, Optional[int]]:
    """Extract a compact token-usage summary from a Responses API object.

    I keep this defensive because SDK response objects can grow new fields over time, and I
    do not want the evaluation harness itself to fail merely because one usage subfield is
    absent for a given model or SDK version.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
        }

    output_details = getattr(usage, "output_tokens_details", None)
    reasoning_tokens = getattr(output_details, "reasoning_tokens", None) if output_details is not None else None

    return {
        "input_tokens": int(usage.input_tokens) if getattr(usage, "input_tokens", None) is not None else None,
        "output_tokens": int(usage.output_tokens) if getattr(usage, "output_tokens", None) is not None else None,
        "reasoning_tokens": int(reasoning_tokens) if reasoning_tokens is not None else None,
        "total_tokens": int(usage.total_tokens) if getattr(usage, "total_tokens", None) is not None else None,
    }


def _append_jsonl_record_v1(path: str, record: dict[str, Any]) -> tuple[bool, str]:
    """Append one JSON-safe record to a JSONL file."""
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _run_openai_structured_state_eval_once_v1(*, model_name: str, prompt: str,
                                              schema: dict[str, Any], request_opts: dict[str, Any]) -> dict[str, Any]:
    """Run one structured Menu 48 state-summary request and return a JSON-safe result bundle."""
    try:
        import openai  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
        from openai import OpenAI  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
    except Exception as e:
        return {
            "ok": False,
            "error_type": "sdk_import_error",
            "error": str(e),
            "model": model_name,
        }

    t0 = time.time()
    try:
        client = OpenAI()
        response = client.responses.create(
            model=model_name,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "cca8_state_reply_v1",
                    "strict": True,
                    "schema": schema,
                }
            },
            **request_opts,
        )
        duration_ms = int((time.time() - t0) * 1000.0)

        raw = getattr(response, "output_text", None)
        if not isinstance(raw, str) or not raw.strip():
            return {
                "ok": False,
                "error_type": "no_output_text",
                "error": "Responses API returned no output_text.",
                "model": model_name,
                "duration_ms": duration_ms,
                "response_id": getattr(response, "id", None),
                "status": getattr(response, "status", None),
                "usage": _llm_eval_response_usage_v1(response),
                "sdk_version": str(getattr(openai, "__version__", "(unknown)")),
            }

        try:
            reply = json.loads(raw)
        except Exception as e:
            return {
                "ok": False,
                "error_type": "json_parse_error",
                "error": str(e),
                "raw_text": raw,
                "model": model_name,
                "duration_ms": duration_ms,
                "response_id": getattr(response, "id", None),
                "status": getattr(response, "status", None),
                "usage": _llm_eval_response_usage_v1(response),
                "sdk_version": str(getattr(openai, "__version__", "(unknown)")),
            }

        return {
            "ok": True,
            "model": model_name,
            "duration_ms": duration_ms,
            "response_id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "usage": _llm_eval_response_usage_v1(response),
            "reply": reply,
            "reply_sig16": _short_json_sig16_v1(reply),
            "sdk_version": str(getattr(openai, "__version__", "(unknown)")),
        }

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000.0)
        error_name = e.__class__.__name__.lower()
        if "authentication" in error_name:
            error_type = "authentication_error"
        elif "ratelimit" in error_name or "rate_limit" in error_name:
            error_type = "rate_limit_error"
        elif "connection" in error_name:
            error_type = "api_connection_error"
        elif "status" in error_name:
            error_type = "api_status_error"
        else:
            error_type = "unexpected_error"
        return {
            "ok": False,
            "error_type": error_type,
            "error": str(e),
            "model": model_name,
            "duration_ms": duration_ms,
        }


def _llm_eval_result_one_line_v1(result: dict[str, Any]) -> str:
    """Render one compact evaluation-harness result line for the terminal."""
    model = str(result.get("model", "(unknown)"))
    duration_ms = result.get("duration_ms")
    duration_txt = f"{int(duration_ms)}ms" if isinstance(duration_ms, int) else "n/a"

    if bool(result.get("ok")):
        reply_raw = result.get("reply")
        reply: dict[str, Any] = reply_raw if isinstance(reply_raw, dict) else {}
        scene = str(reply.get("scene_label", ""))[:60]
        confidence: Any = reply.get("confidence")
        try:
            confidence_txt = f"{float(confidence):.2f}"
        except Exception:
            confidence_txt = "n/a"
        sig16 = result.get("reply_sig16")
        sig16_txt = str(sig16) if isinstance(sig16, str) and sig16 else "(none)"
        return f"ok model={model} dur={duration_txt} conf={confidence_txt} sig={sig16_txt} scene={scene!r}"

    error_type = str(result.get("error_type", "error"))
    msg = str(result.get("error", ""))[:72]
    return f"error model={model} dur={duration_txt} type={error_type} msg={msg!r}"


def _print_llm_eval_summary_v1(records: list[dict[str, Any]]) -> None:
    """Print a compact grouped summary after a Menu 48 evaluation-harness batch."""
    if not records:
        print("\n[llm-eval] No records to summarize.")
        return

    by_model: DefaultDict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        model = str(rec.get("model", "(unknown)"))
        by_model[model].append(rec)

    print("\n[llm-eval] Batch summary")
    for model in sorted(by_model):
        rows = by_model[model]
        ok_rows = [row for row in rows if bool(row.get("ok"))]
        err_rows = [row for row in rows if not bool(row.get("ok"))]

        durations: list[int] = []
        for row in rows:
            duration_value = row.get("duration_ms")
            if isinstance(duration_value, int):
                durations.append(duration_value)
        avg_duration = (sum(durations) / len(durations)) if durations else None

        confidences: list[float] = []
        scene_counts: DefaultDict[str, int] = defaultdict(int)
        risk_counts: DefaultDict[str, int] = defaultdict(int)
        reply_sigs: set[str] = set()
        error_counts: DefaultDict[str, int] = defaultdict(int)

        for row in ok_rows:
            reply_raw = row.get("reply")
            reply: dict[str, Any] = reply_raw if isinstance(reply_raw, dict) else {}

            confidence: Any = reply.get("confidence")
            try:
                confidences.append(float(confidence))
            except Exception:
                pass

            scene = reply.get("scene_label")
            if isinstance(scene, str) and scene:
                scene_counts[scene] += 1

            risks = reply.get("risk_flags")
            if isinstance(risks, list):
                for item in risks:
                    if isinstance(item, str) and item:
                        risk_counts[item] += 1

            sig16 = row.get("reply_sig16")
            if isinstance(sig16, str) and sig16:
                reply_sigs.add(sig16)

        for row in err_rows:
            error_counts[str(row.get("error_type", "error"))] += 1

        avg_confidence = (sum(confidences) / len(confidences)) if confidences else None
        top_scenes = sorted(scene_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        top_risks = sorted(risk_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        top_errors = sorted(error_counts.items(), key=lambda item: (-item[1], item[0]))[:5]

        avg_duration_txt = f"{avg_duration:.0f}ms" if isinstance(avg_duration, float) else "n/a"
        avg_confidence_txt = f"{avg_confidence:.2f}" if isinstance(avg_confidence, float) else "n/a"

        print(f"\n  model={model}")
        print(
            f"    runs={len(rows)} ok={len(ok_rows)} error={len(err_rows)} "
            f"avg_dur={avg_duration_txt} avg_conf={avg_confidence_txt} unique_replies={len(reply_sigs)}"
        )

        if top_scenes:
            scene_txt = "; ".join(f"{name} x{count}" for name, count in top_scenes)
            print(f"    top scene_label: {scene_txt}")
        if top_risks:
            risk_txt = ", ".join(f"{name} x{count}" for name, count in top_risks)
            print(f"    top risk_flags : {risk_txt}")
        if top_errors:
            error_txt = ", ".join(f"{name} x{count}" for name, count in top_errors)
            print(f"    errors         : {error_txt}")


def run_cca8_llm_eval_harness_interactive(
    world: Any,
    drives: Any,
    ctx: Any,
    *,
    runtime: OpenAIRuntime | None = None,
) -> None:
    """Run a small Menu 48 evaluation harness over the current CCA8 state summary.

    This harness exists to make the Menu 48 bridge useful for real experimentation rather
    than only a one-off demo. It sends the SAME outgoing CCA8 summary repeatedly, records
    structured replies, and optionally saves a JSONL log that can be inspected later.
    """
    active_runtime = runtime or _default_openai_runtime()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model_name = _openai_default_model_name()
    request_opts = _openai_response_request_options_v1()

    print("\nSelection: CCA8 -> LLM evaluation harness")
    print("  Purpose: prove that CCA8 can package a selected internal state summary, send it to the LLM,")
    print("           receive structured replies back, and compare those replies across repeated runs.")
    print("  This harness reuses the SAME outgoing CCA8 state packet each time, so differences mainly")
    print("           reflect model/settings behavior rather than changes inside CCA8 itself.")
    print("  It is read-only: useful for comparison, logging, and future LLM experiments.")
    print("  It does NOT yet make the LLM control map switching, planning, or write-back into CCA8.\n")
    print(f"[llm-eval] OPENAI_API_KEY present: {'yes' if api_key else 'no'}")
    if api_key:
        print(f"[llm-eval] OPENAI_API_KEY length: {len(api_key)}")
    print(f"[llm-eval] default model: {model_name}")
    print(f"[llm-eval] advanced settings: {_openai_advanced_settings_one_line()}")

    if not api_key:
        print("\n[llm-eval] OPENAI_API_KEY is not set in this process.")
        print("[llm-eval] Use Menu 48 option 1 first, then rerun this harness.")
        return

    state_summary = build_cca8_llm_state_summary_v1(world, drives, ctx, runtime=active_runtime)
    schema = _cca8_llm_state_reply_schema_v1()
    prompt = _cca8_llm_state_reply_prompt_v1(state_summary)
    state_sig16 = _short_json_sig16_v1(state_summary)

    print("\n[llm-eval] Outgoing CCA8 state summary (same packet reused for all runs):")
    print(json.dumps(state_summary, indent=2, ensure_ascii=False))

    raw_models = input("\nModels to evaluate (comma-separated, blank=current default model): ").strip()
    models = [item.strip() for item in raw_models.split(",") if item.strip()] if raw_models else [model_name]

    raw_trials = input("Trials per model (blank=3): ").strip()
    if not raw_trials:
        trials_per_model = 3
    else:
        try:
            trials_per_model = int(raw_trials)
        except ValueError:
            print("[llm-eval] Invalid integer for trials per model.")
            return
        if not 1 <= trials_per_model <= 20:
            print("[llm-eval] Trials per model must be between 1 and 20.")
            return

    default_path = f"llm_eval_menu48_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    raw_path = input(f"JSONL output path (blank={default_path}, NONE=no file): ").strip()
    if not raw_path:
        jsonl_path: Optional[str] = default_path
    elif raw_path.lower() == "none":
        jsonl_path = None
    else:
        jsonl_path = raw_path

    eval_id = f"menu48_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    header = {
        "schema": "cca8_llm_eval_header_v1",
        "eval_id": eval_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "menu": 48,
        "state_summary_sig16": state_sig16,
        "state_summary": state_summary,
        "prompt": prompt,
        "reply_schema": schema,
        "advanced_settings": dict(request_opts),
        "models": list(models),
        "trials_per_model": int(trials_per_model),
        "sdk_version": _openai_sdk_version_text(),
    }

    jsonl_ok = True
    if isinstance(jsonl_path, str):
        ok, msg = _append_jsonl_record_v1(jsonl_path, header)
        if not ok:
            jsonl_ok = False
            print(f"[llm-eval] Warning: could not write JSONL header to {jsonl_path!r}: {msg}")

    print("\n[llm-eval] Running batch...")
    print(
        f"[llm-eval] eval_id={eval_id} state_sig={state_sig16} models={models} "
        f"trials_per_model={trials_per_model}"
    )

    records: list[dict[str, Any]] = []
    run_no = 0
    total_runs = len(models) * trials_per_model

    for model in models:
        for trial_no in range(1, trials_per_model + 1):
            run_no += 1
            print(f"\n[llm-eval] run {run_no}/{total_runs}: model={model} trial={trial_no}/{trials_per_model}")
            result = _run_openai_structured_state_eval_once_v1(
                model_name=model,
                prompt=prompt,
                schema=schema,
                request_opts=request_opts,
            )
            records.append(result)
            print("  " + _llm_eval_result_one_line_v1(result))

            if isinstance(jsonl_path, str) and jsonl_ok:
                record = {
                    "schema": "cca8_llm_eval_record_v1",
                    "eval_id": eval_id,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "state_summary_sig16": state_sig16,
                    "model": model,
                    "trial_no": trial_no,
                    "advanced_settings": dict(request_opts),
                    "result": result,
                }
                ok, msg = _append_jsonl_record_v1(jsonl_path, record)
                if not ok:
                    jsonl_ok = False
                    print(f"[llm-eval] Warning: JSONL append failed for {jsonl_path!r}: {msg}")

    _print_llm_eval_summary_v1(records)

    if isinstance(jsonl_path, str) and jsonl_ok:
        print(f"\n[llm-eval] JSONL saved to: {jsonl_path}")
    elif isinstance(jsonl_path, str):
        print("\n[llm-eval] Batch completed, but JSONL output stopped after a write failure.")
    else:
        print("\n[llm-eval] Batch completed without JSONL file output.")


def run_cca8_llm_state_summary_demo_interactive(
    world: Any,
    drives: Any,
    ctx: Any,
    *,
    runtime: OpenAIRuntime | None = None,
) -> None:
    """Run the first real CCA8 -> LLM demo.

    This sends a tiny CCA8-generated state summary to the current OpenAI model,
    asks for a short structured interpretation, and prints the result cleanly.

    Important:
      - read-only demo
      - no write-back into CCA8
      - conservative / inspectable / easy to debug
    """
    active_runtime = runtime or _default_openai_runtime()
    print("\n[llm-demo] First CCA8 -> LLM state-summary demo")
    print("[llm-demo] This sends a small CCA8-generated JSON summary to the model.")
    print("[llm-demo] The model returns a structured JSON interpretation.\n")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model_name = _openai_default_model_name()
    request_opts = _openai_response_request_options_v1()

    print(f"[llm-demo] OPENAI_API_KEY present: {'yes' if api_key else 'no'}")
    if api_key:
        print(f"[llm-demo] OPENAI_API_KEY length: {len(api_key)}")
    print(f"[llm-demo] model: {model_name}")
    print(f"[llm-demo] advanced settings: {_openai_advanced_settings_one_line()}")

    try:
        import openai  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
        from openai import OpenAI  # type: ignore[import-not-found]  # pylint: disable=import-error,import-outside-toplevel
    except Exception as e:
        print("[llm-demo] OpenAI Python SDK is not available in this Python environment.")
        print("[llm-demo] Install or upgrade it with:")
        print("           python -m pip install --upgrade openai")
        print(f"[llm-demo] Import error: {e}")
        return

    sdk_ver = str(getattr(openai, "__version__", "(unknown)"))
    print(f"[llm-demo] openai SDK version: {sdk_ver}")

    if not api_key:
        print("[llm-demo] OPENAI_API_KEY is missing.")
        print("[llm-demo] Use menu 48 to save the key, then run this demo again.")
        return

    state_summary = build_cca8_llm_state_summary_v1(world, drives, ctx, runtime=active_runtime)

    print("\n[llm-demo] Outgoing CCA8 state summary:")
    print(json.dumps(state_summary, indent=2, ensure_ascii=False))

    schema = _cca8_llm_state_reply_schema_v1()
    prompt = _cca8_llm_state_reply_prompt_v1(state_summary)

    print("\n[llm-demo] SENDING STRUCTURED REQUEST TO THE LLM...")

    try:
        client = OpenAI()
        response = client.responses.create(
            model=model_name,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "cca8_state_reply_v1",
                    "strict": True,
                    "schema": schema,
                }
            },
            **request_opts,
        )

        raw = getattr(response, "output_text", None)
        if not isinstance(raw, str) or not raw.strip():
            print("[llm-demo] API call succeeded, but no output_text was returned.")
            return

        try:
            reply = json.loads(raw)
        except Exception as e:
            print("[llm-demo] The API call succeeded, but the reply was not valid JSON.")
            print(f"[llm-demo] JSON parse error: {e}")
            print("[llm-demo] Raw reply:")
            print(raw)
            return

        print("\n[llm-demo] STRUCTURED REPLY FROM THE LLM:")
        print(f"  scene_label : {reply.get('scene_label')}")
        print(f"  current_task: {reply.get('current_task')}")
        print("  risk_flags  :")
        risks = reply.get("risk_flags")
        if isinstance(risks, list) and risks:
            for item in risks:
                print(f"    - {item}")
        else:
            print("    (none)")
        print(f"  advice      : {reply.get('advice')}")

        conf = reply.get("confidence")
        if isinstance(conf, (int, float)):
            print(f"  confidence  : {float(conf):.2f}")
        else:
            print(f"  confidence  : {conf}")
        return

    except openai.AuthenticationError as e:  # pylint: disable=unused-variable
        print("\n[llm-demo] Authentication error.")
        print("[llm-demo] The SDK imported correctly, but the API key was rejected.")
        print("[llm-demo] Details were redacted to avoid echoing API-key text into terminal output.")
        return

    except openai.RateLimitError as e:
        print("\n[llm-demo] Rate-limit / quota / billing error.")
        print("[llm-demo] The key was recognized, but the request could not proceed.")
        print(f"[llm-demo] Details: {e}")
        return

    except openai.APIConnectionError as e:
        print("\n[llm-demo] Connection error.")
        print("[llm-demo] The SDK and key look present, but the network call failed.")
        print(f"[llm-demo] Details: {e}")
        return

    except openai.APIStatusError as e:
        status_code = getattr(e, "status_code", "(unknown)")
        print(f"\n[llm-demo] API status error (HTTP {status_code}).")
        print(f"[llm-demo] Details: {e}")
        return

    except Exception as e:
        print("\n[llm-demo] Unexpected error during the CCA8 -> LLM demo.")
        print(f"[llm-demo] Details: {e}")
        return


def openai_menu_48_interactive(
    world: Any,
    drives: Any,
    ctx: Any,
    operations: OpenAIMenuOperations | None = None,
) -> None:
    """Menu #48: one place for OpenAI / LLM setup, demos, help, smoke testing, and evals."""
    active_operations = operations or _default_openai_menu_operations()
    while True:
        existing = os.environ.get("OPENAI_API_KEY", "").strip()
        sdk_ver = active_operations.sdk_version_text()
        model_name = active_operations.default_model_name()

        print("\nSelection: OpenAI / LLM API setup, model selection, help, smoke test, and CCA8 demo")
        print(f"  Current SDK version seen by this interpreter: {sdk_ver}")
        print(f"  Current default model for smoke test / demo: {model_name}")
        print(f"  OPENAI_API_KEY present in this process: {'yes' if existing else 'no'}")
        if existing:
            print(f"  OPENAI_API_KEY length: {len(existing)}")
        print(f"  Advanced request overrides: {active_operations.advanced_settings_one_line()}")

        print("\n  1) Configure / update OPENAI_API_KEY")
        print("  2) Configure / update default OpenAI model")
        print("  3) Run OpenAI SDK / API smoke test")
        print("  4) Show install/help text")
        print("  5) Run first CCA8 -> LLM state-summary demo")
        print("  6) Advanced request settings")
        print("  7) Run evaluation harness (batch compare + JSONL log)")
        print("  Enter) Return to main menu")

        choice = input("\nChoose [1,2,3,4,5,6,7, Enter]: ").strip().lower()

        if choice == "":
            print("[llm] Returning to main menu.")
            return
        if choice in ("1", "c", "config", "configure", "key", "apikey"):
            active_operations.configure_api_key()
            continue
        if choice in ("2", "m", "model", "llmmodel"):
            active_operations.configure_model()
            continue
        if choice in ("3", "t", "test", "smoke", "smoketest"):
            active_operations.run_smoke_test()
            continue
        if choice in ("4", "h", "help", "install", "sdk", "pip"):
            active_operations.print_install_help()
            continue
        if choice in ("5", "demo", "cca8", "state", "summary"):
            active_operations.run_state_summary_demo(world, drives, ctx)
            continue
        if choice in ("6", "advanced", "adv", "knobs", "settings"):
            active_operations.open_advanced_settings()
            continue
        if choice in ("7", "eval", "evaluate", "harness", "batch"):
            active_operations.run_eval_harness(world, drives, ctx)
            continue

        print(f"[llm] Unknown selection: {choice!r}")



def _default_openai_advanced_menu_operations() -> OpenAIAdvancedMenuOperations:
    """Build advanced-settings operations for direct module callers."""
    return OpenAIAdvancedMenuOperations(
        configure_temperature=configure_openai_temperature_interactive,
        configure_top_p=configure_openai_top_p_interactive,
        configure_max_output_tokens=configure_openai_max_output_tokens_interactive,
        configure_reasoning_effort=configure_openai_reasoning_effort_interactive,
        clear_settings=clear_openai_advanced_settings_interactive,
    )


def _default_openai_menu_operations() -> OpenAIMenuOperations:
    """Build Menu 48 operations for direct module callers."""
    runtime = _default_openai_runtime()

    def run_demo(world: Any, drives: Any, ctx: Any) -> None:
        run_cca8_llm_state_summary_demo_interactive(world, drives, ctx, runtime=runtime)

    def run_eval(world: Any, drives: Any, ctx: Any) -> None:
        run_cca8_llm_eval_harness_interactive(world, drives, ctx, runtime=runtime)

    return OpenAIMenuOperations(
        sdk_version_text=_openai_sdk_version_text,
        default_model_name=_openai_default_model_name,
        advanced_settings_one_line=_openai_advanced_settings_one_line,
        configure_api_key=configure_openai_api_key_interactive,
        configure_model=configure_openai_model_interactive,
        run_smoke_test=run_openai_smoke_test_interactive,
        print_install_help=print_openai_install_help,
        run_state_summary_demo=run_demo,
        open_advanced_settings=openai_advanced_settings_menu_interactive,
        run_eval_harness=run_eval,
    )
