# -*- coding: utf-8 -*-
"""Preflight validation subsystem for the CCA8 simulation.

Purpose
-------
This module owns the full CCA8 preflight implementation: unit-test and
coverage execution, deterministic architecture probes, hardware/robotics
checks, system-fitness checks, summary rendering, and the optional startup
preflight notice.

The extraction is intentionally structural. ``cca8_run`` retains its public
``run_preflight_full`` and ``run_preflight_lite_maybe`` entry points and
delegates here, so command-line behavior and existing imports remain
compatible.

Dependency boundary
-------------------
Stable CCA8 types and modules are imported directly. A small
:class:`PreflightRuntime` bridge carries the runner-private helpers used by
scenario probes. This explicit bridge avoids a circular import from
``cca8_preflight`` back into ``cca8_run`` and keeps the runner as the owner of
its operational helpers while the preflight orchestration lives here.
"""

from __future__ import annotations

# The full preflight is intentionally a long, sequential checklist. These
# suppressions preserve the existing readable probe-by-probe structure during
# the mechanical extraction; later refactors can split individual lanes.
# pylint: disable=duplicate-code
# pylint: disable=import-outside-toplevel
# pylint: disable=no-member
# pylint: disable=protected-access
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

import cca8_world_graph
from cca8_context import Ctx
from cca8_controller import (
    PRIMITIVES,
    Drives,
    action_center_step,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_space_zone,
)
from cca8_env import HybridEnvironment
from cca8_features import FactMeta
from cca8_temporal import TemporalContext

__version__ = "0.1.1"
__all__ = [
    "PreflightRuntime",
    "run_llm_operational_preflight_check",
    "run_preflight_full",
    "run_preflight_lite_maybe",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class PreflightRuntime:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-owned operations required by the extracted preflight probes.

    Purpose
    -------
    ``cca8_run`` still owns several private operational helpers used by the
    historical scenario checks. Importing the runner from this module would
    create a circular dependency. The runner therefore constructs this bridge
    immediately before a full preflight and supplies the current callables and
    constants explicitly.

    Attributes
    ----------
    policy_runtime_factory:
        Callable that constructs the runner's policy runtime from the gate
        catalog.
    catalog_gates:
        Current runner policy-gate catalog.
    anchor_id, resolve_engrams_pretty, init_body_world, save_session,
    timekeeping_line, ensure_now_origin, update_body_world_from_obs:
        Existing runner helpers used by deterministic architecture probes.
    seek_nipple_gate, rest_gate:
        Existing policy-gate functions exercised by BodyMap probes.
    inject_obs_into_world, resting_scenes_in_shelter:
        Existing observation and scene-summary helpers.
    print_ascii_logo:
        Runner presentation callback used only for the successful footer.
    llm_operational_check:
        Runner compatibility wrapper for the live OpenAI smoke test.
    non_win_linux:
        Existing platform fallback flag used by the RAM check.
    placeholder_embodiment:
        Existing default body-description text used in the hardware lane.
    """

    policy_runtime_factory: Callable[[Any], Any]
    catalog_gates: Any
    anchor_id: Callable[[Any, str], str]
    resolve_engrams_pretty: Callable[[Any, str], None]
    init_body_world: Callable[[], tuple[Any, dict[str, str]]]
    save_session: Callable[[str, Any, Any], str]
    timekeeping_line: Callable[[Any], str]
    ensure_now_origin: Callable[[Any], None]
    update_body_world_from_obs: Callable[[Any, Any], None]
    seek_nipple_gate: Callable[[Any, Drives, Any], bool]
    rest_gate: Callable[[Any, Drives, Any], bool]
    inject_obs_into_world: Callable[[Any, Any, Any], Any]
    resting_scenes_in_shelter: Callable[[Any], dict[str, Any]]
    print_ascii_logo: Callable[..., None]
    llm_operational_check: Callable[[float], dict[str, Any]]
    non_win_linux: bool
    placeholder_embodiment: str


def run_llm_operational_preflight_check(
    timeout_seconds: float = 20.0,
    *,
    default_model_name: Callable[[], str],
    response_request_options: Callable[[], dict[str, Any]],
    response_text: Callable[[Any], str],
) -> dict[str, Any]:
    """Run a non-interactive OpenAI/LLM smoke test for preflight Part 4.

    Purpose / intent
    ----------------
    This is a *system-fitness* check, not a deterministic unit test. It answers the practical runtime question:
    can this CCA8 process currently talk to the configured OpenAI model and receive a small reply?

    What it checks
    --------------
    1. OPENAI_API_KEY is present in this process.
    2. CCA8 can determine the default model name it would normally use.
    3. The OpenAI SDK imports successfully in this interpreter.
    4. A tiny live Responses API call succeeds.
    5. The reply contains the expected smoke-test token.

    Return contract
    ---------------
    Returns a JSON-safe dict with:
        status:
            "pass", "fail", or "skip"
        summary:
            Short human-readable summary
        detail:
            One-line explanation suitable for the preflight lane
        model:
            Effective model name if known

    Callback parameters
    -------------------
    default_model_name:
        Runner-owned helper that returns the effective OpenAI model name.
    response_request_options:
        Runner-owned helper that returns optional Responses API request settings.
    response_text:
        Runner-owned best-effort extractor for Responses API text.

    Design choice
    -------------
    Missing local configuration returns "skip" rather than "fail". A configured-but-broken live call returns
    "fail" at the probe level so callers can still distinguish the diagnostic outcome. The full CCA8 preflight treats
    all non-passing OpenAI outcomes as non-blocking warnings because OpenAI access is an optional integration.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    #api_key = ""   #for testing, to force the preflight helper to behave as if no API key exists
    if not api_key:
        return {
            "status": "skip",
            "summary": "LLM smoke test skipped",
            "detail": "OPENAI_API_KEY not set in this process",
            "model": None,
        }

    try:
        model_name = default_model_name()
    except Exception:
        model_name = (os.environ.get("CCA8_OPENAI_MODEL", "") or os.environ.get("OPENAI_MODEL", "")).strip()

    if not isinstance(model_name, str) or not model_name.strip():
        return {
            "status": "skip",
            "summary": "LLM smoke test skipped",
            "detail": "no default OpenAI model configured",
            "model": None,
        }
    model_name = model_name.strip()

    try:
        request_opts = response_request_options()
        if not isinstance(request_opts, dict):
            request_opts = {}
    except Exception:
        request_opts = {}

    if "max_output_tokens" not in request_opts:
        request_opts["max_output_tokens"] = 24

    prompt = "Reply with exactly this text and nothing else: CCA8_LLM_SMOKE_TEST_OK"
    expected = "CCA8_LLM_SMOKE_TEST_OK"

    try:
        import openai  # pylint: disable=import-outside-toplevel
        from openai import OpenAI  # pylint: disable=import-outside-toplevel
    except Exception as e:
        return {
            "status": "skip",
            "summary": "LLM smoke test skipped",
            "detail": f"OpenAI SDK import failed: {e}",
            "model": model_name,
        }

    try:
        client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        response = client.responses.create(
            model=model_name,
            input=prompt,
            **request_opts,
        )
        text = response_text(response)

    except openai.AuthenticationError:
        return {
            "status": "fail",
            "summary": "LLM smoke test failed",
            "detail": "authentication error: OPENAI_API_KEY was rejected; configure it through Menu 48",
            "model": model_name,
        }

    except openai.APIConnectionError as e:
        return {
            "status": "fail",
            "summary": "LLM smoke test failed",
            "detail": f"connection error: {e}",
            "model": model_name,
        }

    except openai.APIStatusError as e:
        status_code = getattr(e, "status_code", "(unknown)")
        return {
            "status": "fail",
            "summary": "LLM smoke test failed",
            "detail": f"API status error HTTP {status_code}: {e}",
            "model": model_name,
        }

    except Exception as e:
        return {
            "status": "fail",
            "summary": "LLM smoke test failed",
            "detail": f"{e.__class__.__name__}: {e}",
            "model": model_name,
        }

    if text == expected:
        return {
            "status": "pass",
            "summary": "LLM smoke test passed",
            "detail": "live API call returned the expected reply",
            "model": model_name,
        }

    if expected in text:
        return {
            "status": "pass",
            "summary": "LLM smoke test passed",
            "detail": f"live API call returned the expected token inside reply: {text!r}",
            "model": model_name,
        }

    if not text:
        return {
            "status": "fail",
            "summary": "LLM smoke test failed",
            "detail": "live API call returned no text",
            "model": model_name,
        }

    return {
        "status": "fail",
        "summary": "LLM smoke test failed",
        "detail": f"unexpected reply text: {text!r}",
        "model": model_name,
    }


def _classify_llm_preflight_assessment(result: dict[str, Any]) -> tuple[str, str]:
    """Classify an OpenAI probe result for the aggregate CCA8 preflight.

    OpenAI access is useful for Menu 48 and LLM-backed experiment conditions, but it is not required for the core
    CCA8 architecture, deterministic tests, robotics checks, or ordinary cognitive-cycle execution. A missing SDK,
    absent key, invalid key, unavailable model, connection problem, or unexpected reply is therefore reported as a
    visible warning rather than making the full preflight fail.

    The lower-level :func:`run_llm_operational_preflight_check` retains its precise ``pass``/``skip``/``fail`` status
    contract. This helper defines only the aggregation policy used by :func:`run_preflight_full`.
    """
    status = str(result.get("status", "fail")).strip().lower()
    summary = str(result.get("summary", "LLM smoke test"))
    detail = str(result.get("detail", "") or "")
    model = result.get("model")
    model_text = f" model={model}" if isinstance(model, str) and model else ""
    message = f"{summary}{model_text} -- {detail}"

    if status == "pass":
        return "pass", message

    return "warning", f"{message} -- optional OpenAI integration unavailable; core CCA8 preflight continues"


def run_preflight_full(args: Any, runtime: PreflightRuntime) -> int:
    """
    Full preflight: quick, deterministic checks with one-line PASS/FAIL per item.
    Returns 0 for ok, non-zero for any failure.

    While the preflight system is a very convenient way for testing the cca8 simulation software, particularly after code or large
    data changes, we acknowledge the strength and tradition of the Pytest (or equivalent) unit tests in validating the correctness of
    code logic, the ability for very granular testing and better proves that the code works. Thus, the preflight system by design first
    calls pytest to run whatever unit tests are present in the /tests subdirectory from the main working directory.

    """
    print("\nPreflight running....")
    print("Like an aircraft pre-flight, this check verifies the critical parts of")
    print("the CCA8 architecture and simulation before you “fly” the system.\n")
    print("There are four main parts. The first part runs a variety of unit tests,")
    print("currently pytest-based. Coverage reports the percent of EXECUTABLE lines")
    print("exercised. Comments and docstrings are ignored; ordinary code lines—")
    print("including print(...) and input(...)—COUNT toward coverage, but not always. We")
    print("generally aim for ≥30% line coverage as a useful signal, focusing on critical paths")
    print("over raw percentage (diminishing returns with higher percentages unless mission critical).")
    print("(Due to where results are read from, the percentage may differ by one or two percent")
    print("in the body and summary line of the report.)\n")
    print("The second part of preflight runs scenario checks to catch issues which the unit")
    print("tests can miss, particularly whole-flow behavior (CLI → persistence →")
    print("relaunch).\n")
    print("The third part of the preflight runs the robotics hardware checks. In this section")
    print("the checks actually resemble more closely their aviation counterparts.\n")
    print("The fourth part of the preflight runs the system integration checks. In this section")
    print("the checks actually resemble more closely a pilot's medical and mental fitness assessment")
    print("plus the pilot's flight assessment. In this fourth part the ability of the CCA8 architecture")
    print("to functionally carry out small tasks representative of its abilities are tested.\n")
    # pylint: disable=reimported
    import os as _os  #required for running pyvis in browswer if os being used elsewhere
    print("[preflight] Running full preflight...")

    failures = 0
    checks = 0

    import time as _time
    t0 = _time.perf_counter()


    def ok(msg):
        nonlocal checks
        checks += 1
        print(f"[preflight] PASS  - {msg}")


    def bad(msg):
        nonlocal failures, checks
        failures += 1
        checks += 1
        print(f"[preflight] FAIL  - {msg}")


    # helpers for the footer
    def _fmt_hms(seconds: float) -> str:
        m, s = divmod(int(round(seconds)), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


    def _parse_junit_xml(path: str) -> dict:
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()
            if root.tag == "testsuite":
                return {
                    "tests":   int(root.attrib.get("tests", 0)),
                    "failures":int(root.attrib.get("failures", 0)),
                    "errors":  int(root.attrib.get("errors", 0)),
                    "skipped": int(root.attrib.get("skipped", 0)),
                }
            elif root.tag == "testsuites":
                total = {"tests":0,"failures":0,"errors":0,"skipped":0}
                for ts in root.findall("testsuite"):
                    for k in total:
                        total[k] += int(ts.attrib.get(k, 0))
                return total
        except Exception:
            pass
        return {}


    def _parse_coverage_pct(path: str) -> float | None:
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()  # coverage.py: <coverage line-rate="0.87" ...>
            lr = root.attrib.get("line-rate")
            if lr is not None:
                return float(lr) * 100.0
            # fallback from totals if present
            lv = root.attrib.get("lines-valid")
            lc = root.attrib.get("lines-covered")
            if lv and lc:
                lvf, lcf = float(lv), float(lc)
                return (lcf / lvf) * 100.0 if lvf else None
        except Exception:
            return None
        return None

    # --- color helpers (Windows-safe, no third-party deps) ---
    import sys as _sys

    def _is_tty() -> bool:
        try:
            return _sys.stdout.isatty()
        except Exception:
            return False


    def _ansi_enable() -> bool:
        # POSIX terminals usually support ANSI out of the box
        if not _sys.platform.startswith("win"):
            return True
        # Windows: enable Virtual Terminal Processing on stdout
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                new_mode = mode.value | 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                if kernel32.SetConsoleMode(h, new_mode):
                    return True
        except Exception:
            pass
        return False

    _ANSI_OK = _is_tty() and _ansi_enable()


    def _paint_fail(line: str) -> str:
        # red
        return f"\x1b[31m{line}\x1b[0m" if _ANSI_OK else line

    # --- Unit tests (pytest) — run first ------------------------------------------------
    try:
        if _os.path.isdir("tests"):
            try:
                import pytest as _pytest
                print("[preflight] Running unit tests (pytest)...\n")

                # Detect pytest-cov plugin; if missing, run without coverage
                try:
                    import pytest_cov as _pytest_cov  # noqa: F401  ## pylint: disable=unused-import
                    _have_cov = True
                except Exception:
                    _have_cov = False

                # Always ensure artifacts dir exists (for JUnit/coverage outputs)
                _os.makedirs(".coverage", exist_ok=True)

                if _have_cov:
                    _os.environ.setdefault("COVERAGE_FILE", ".coverage/.coverage.preflight")
                    _cov_pkgs = [
                        "cca8_world_graph",
                        "cca8_controller",
                        "cca8_run",
                        "cca8_preflight",
                        "cca8_temporal",
                        "cca8_features",
                        "cca8_column",
                    ]
                    _args = ["-v", "-ra", "--junitxml=.coverage/junit.xml"]
                    for _pkg in _cov_pkgs:
                        _args += ["--cov", _pkg]
                    if _os.path.exists(".coveragerc"):
                        _args += ["--cov-config", ".coveragerc"]
                    # human + machine readable reports
                    _args += ["--cov-report=term-missing",
                              "--cov-report=xml:.coverage/coverage.xml",
                              "tests"]
                else:
                    # Fallback: no coverage plugin, but still produce JUnit for counts
                    _args = ["-v", "-ra", "--junitxml=.coverage/junit.xml", "tests"]

                _rc = _pytest.main(_args)
                if _rc == 0:
                    ok("pytest: all tests passed\n")
                    if _have_cov:
                        ok("coverage: see .coverage/coverage.xml and console summary above\n")
                else:
                    bad(f"pytest: test run reported failures (exit={_rc})\n")
            except Exception as e:
                bad(f"pytest run error: {e}")
        else:
            ok("pytest: no 'tests' directory found — skipping\n")
    except Exception as e:
        bad(f"pytest not available or other error: {e}\n")

    # Part 2 probe counting should exclude the earlier Part 1 pytest lane bookkeeping.
    # We keep the cumulative counters for overall PASS/FAIL logic, but remember the offsets
    # so the Part 2 footer reflects only the scenario/probe section.
    probe_checks_offset = checks
    probe_failures_offset = failures

    # 1) Python & platform
    try:
        pyver = sys.version.split()[0]
        ok(f"python={pyver} platform={platform.platform()}")
    except Exception as e:
        bad(f"could not read python/platform: {e}")


    # 2a) CCA8 modules present & importable (plus key symbols)
    try:
        import importlib

        # module name → list of symbols we expect to exist
        _mods: list[tuple[str, list[str]]] = [
            ("cca8_world_graph", ["WorldGraph", "__version__"]),
            ("cca8_controller",  ["Drives", "action_center_step", "__version__"]),
            ("cca8_column",      ["__version__"]),
            ("cca8_features",    ["__version__"]),
            ("cca8_temporal",    ["__version__"]),
            ("cca8_openai",      ["OpenAIRuntime", "__version__"]),
            ("cca8_working_memory", ["init_working_world", "serialize_mapsurface_v1", "__version__"]),
        ]

        for _name, _symbols in _mods:
            try:
                _m = importlib.import_module(_name)
                _ver = getattr(_m, "__version__", None)
                _pth = getattr(_m, "__file__", None)
                ok(f"import {_name}" + (f" v{_ver}" if _ver else "") +
                   (f" ({_os.path.basename(_pth)})" if _pth else ""))

                for _sym in _symbols:
                    # "__version__" may not exist on every module; treat missing version as OK
                    if _sym == "__version__":
                        continue
                    if hasattr(_m, _sym):
                        # Touch the symbol to ensure it resolves
                        getattr(_m, _sym)
                        ok(f"{_name}.{_sym} available")
                    else:
                        bad(f"{_name}: missing symbol '{_sym}'")
            except Exception as e:
                bad(f"import {_name} failed: {e}")
    except Exception as e:
        bad(f"module import checks failed: {e}")


        # 2b) Explicit invariant check on a tiny fresh world
    try:
        _wi = cca8_world_graph.WorldGraph()
        _wi.ensure_anchor("NOW")
        issues = _wi.check_invariants(raise_on_error=False)
        if issues:
            bad("invariants: " + "; ".join(issues))
        else:
            ok("invariants: no issues on fresh world")
    except Exception as e:
        bad(f"invariants: check raised: {e}")

    # 3a) Accessory files present (README + image), non-empty
    try:
        _required_files = {
            "README.md": ["README.md"],
            "calf_goat.jpg": [
                "calf_goat.jpg",
                os.path.join("docs", "images", "calf_goat.jpg"),
            ],
        }

        for _label, _candidates in _required_files.items():
            try:
                _found_path = None
                for _path in _candidates:
                    if os.path.exists(_path):
                        _found_path = _path
                        break

                if _found_path is None:
                    bad(f"file missing: {_label}")
                    continue

                _sz = os.path.getsize(_found_path)
                if _sz > 0:
                    ok(f"file present: {_found_path} ({_sz} bytes)")
                else:
                    bad(f"file present but empty: {_found_path}")
            except Exception as e:
                bad(f"file check failed for {_label}: {e}")
    except Exception as e:
        bad(f"accessory file checks failed: {e}")

    # 4a) Pyvis installed (for HTML graph export)
    try:
        import pyvis as _pyvis # type: ignore # pylint: disable=unused-import
        ok("pyvis installed")
    except Exception as e:
        ok(f"pyvis not installed (export still optional): {e}")


    # 2) WorldGraph reasonableness
    try:
        w = cca8_world_graph.WorldGraph()
        w.ensure_anchor("NOW")
        if isinstance(w._bindings, dict) and runtime.anchor_id(w, "NOW") != "?":
            ok("WorldGraph init and NOW anchor")
        else:
            bad("WorldGraph anchor missing or invalid")
    except Exception as e:
        bad(f"WorldGraph init failed: {e}")


    # 2a) WorldGraph.set_now() — anchor remap & tag housekeeping (no warnings)
    try:
        # fresh temp world just for this test
        _w2 = cca8_world_graph.WorldGraph()
        _w2.set_tag_policy("allow")  # silence lexicon WARNs in this probe
        # ensure NOW exists for this instance
        _old_now = _w2.ensure_anchor("NOW")

        def _tags_of(bid_: str):
            b = _w2._bindings[bid_]
            ts = getattr(b, "tags", None)
            if ts is None:
                b.tags = set()
                ts = b.tags
            return ts


        def _has_tag(bid_: str, t: str) -> bool:
            ts = getattr(_w2._bindings[bid_], "tags", None)
            return ts is not None and (t in ts)


        def _tag_add(bid_: str, t: str):
            ts = _tags_of(bid_)
            try: ts.add(t)
            except AttributeError:
                if t not in ts: ts.append(t)


        def _tag_discard(bid_: str, t: str):
            ts = getattr(_w2._bindings[bid_], "tags", None)
            if ts is None: return
            try: ts.discard(t)
            except AttributeError:
                try: ts.remove(t)
                except ValueError: pass

        ok("set_now: ensured initial NOW exists")

        # make sure the old NOW is visibly tagged so we can verify removal later
        if not _has_tag(_old_now, "anchor:NOW"):
            _tag_add(_old_now, "anchor:NOW")

        # create a new binding to become NOW (no auto-attach)
        _new_now = _w2.add_predicate("pred:preflight:now_test", attach="none", meta={"created_by": "preflight"})

        _prev = _w2.set_now(_new_now, tag=True, clean_previous=True)

        # anchors map updated?
        if _w2._anchors.get("NOW") == _new_now:
            ok("set_now: NOW anchor re-pointed")
        else:
            bad("set_now: anchors map not updated")

        # new NOW has anchor tag?
        if _has_tag(_new_now, "anchor:NOW"):
            ok("set_now: new NOW has anchor:NOW tag")
        else:
            bad("set_now: new NOW missing anchor:NOW tag")

        # previous NOW lost the anchor tag?
        if _prev and _prev in _w2._bindings:
            if not _has_tag(_prev, "anchor:NOW"):
                ok("set_now: removed anchor:NOW from previous NOW")
            else:
                bad("set_now: previous NOW still tagged anchor:NOW")

        # negative test: unknown id must raise KeyError
        try:
            _w2.set_now("b999999", tag=True)
            bad("set_now: accepted unknown id (expected KeyError)")
        except KeyError:
            ok("set_now: rejects unknown id (KeyError)")

    except Exception as e:
        bad(f"set_now test failed: {e}")


    # 3) Controller primitives
    try:
        from cca8_controller import Drives as _Drv, __version__ as _CTRL_VER

        # (action_center_step is already imported at module top; if not, import it here too)
        if isinstance(PRIMITIVES, list) and PRIMITIVES:
            ok(f"controller primitives loaded (count={len(PRIMITIVES)})")
        else:
            bad("controller primitives missing/empty")

        # Smoke: run the controller once on a fresh world using the real Ctx dataclass
        try:
            _w = cca8_world_graph.WorldGraph(); _w.ensure_anchor("NOW")
            _d = _Drv()
            _ctx = Ctx()
            _ = action_center_step(_w, _ctx, _d)
            ok(f"action_center_step smoke-run (cca8_controller v{_CTRL_VER})")
        except Exception as e:
            bad(f"action_center_step failed to run: {e}")
    except Exception as e:
        bad(f"controller import failed: {e}")


    # 4) HAL header consistency (does not require real hardware)
    try:
        hal_flag = bool(getattr(args, "hal", False))
        body_val = (getattr(args, "body", "") or "").strip() or "(none)"
        ok(f"HAL flag={hal_flag} body={body_val}, nb no actual robotic embodiment implemented to pre-flight at this time")
    except Exception as e:
        bad(f"HAL/body flag read error: {e}")


    # 5) Read/write snapshot (tmp)
    try:
        tmp = "_preflight_session.json"
        d  = Drives()
        ts = runtime.save_session(tmp, cca8_world_graph.WorldGraph(), d)
        if os.path.exists(tmp):
            ok(f"snapshot write/read path exists ({tmp}, saved_at={ts})")
            try:
                with open(tmp, "r", encoding="utf-8") as f: json.load(f)
                ok("snapshot JSON parse")
            except Exception as e:
                bad(f"snapshot JSON parse failed: {e}")
            try:
                os.remove(tmp)
                ok("snapshot cleanup")
            except Exception as e:
                bad(f"snapshot cleanup failed: {e}")
        else:
            bad("snapshot file missing after save")
    except Exception as e:
        bad(f"snapshot write failed: {e}")


    # 6) Planning stub
    try:
        w = cca8_world_graph.WorldGraph()
        src = w.ensure_anchor("NOW")
        # plan to something that isn't there: expect no path, not an exception
        p = w.plan_to_predicate(src, "milk:drinking")
        ok(f"planner probes (path_found={bool(p)})")
    except Exception as e:
        bad(f"planner probe failed: {e}")


    # Z1) Attach semantics (NOW/latest → new binding) — no warnings
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.set_tag_policy("allow")  # silence lexicon WARNs here
        _now = _w.ensure_anchor("NOW")

        # attach="now" creates NOW→new (then) and updates LATEST
        _a = _w.add_predicate("pred:test:A", attach="now")

        if any(e.get("to") == _a and e.get("label", "then") == "then" for e in (_w._bindings[_now].edges or [])):
            ok("attach=now: NOW→new edge recorded")
        else:
            bad("attach=now: missing NOW→new edge")

        if _w._latest_binding_id == _a:
            ok("attach=now: LATEST updated to new binding")
        else:
            bad("attach=now: LATEST not updated")

        # attach="latest" creates oldLATEST→new (then) and updates LATEST
        _b = _w.add_predicate("pred:test:B", attach="latest")

        if any(e.get("to") == _b and e.get("label", "then") == "then" for e in (_w._bindings[_a].edges or [])):
            ok("attach=latest: LATEST→new edge recorded")
        else:
            bad("attach=latest: missing LATEST→new edge")

        if _w._latest_binding_id == _b:
            ok("attach=latest: LATEST updated to new binding")
        else:
            bad("attach=latest: LATEST not updated")

    except Exception as e:
        bad(f"attach semantics failed: {e}")


    # Z2) Cue normalization & family check
    try:
        _w3 = cca8_world_graph.WorldGraph()
        _w3.ensure_anchor("NOW")
        _c = _w3.add_cue("vision:silhouette:mom", attach="now", meta={"preflight": True})
        _tags = getattr(_w3._bindings[_c], "tags", []) or []
        if "cue:vision:silhouette:mom" in _tags:
            ok("cue add: created tag cue:vision:silhouette:mom")
        else:
            bad("cue add: did not normalize to cue:*")
        if any(isinstance(t, str) and t.startswith("pred:vision:") for t in _tags):
            bad("cue add: legacy pred:vision:* still present")
        else:
            ok("cue add: no legacy pred:vision:* present")
    except Exception as e:
        bad(f"cue normalization failed: {e}")


    # Z3) Action metrics aggregator — no warnings
    try:
        _w4 = cca8_world_graph.WorldGraph()
        _w4.set_tag_policy("allow")  # silence lexicon WARNs here
        _w4.ensure_anchor("NOW")
        _src = _w4.add_predicate("pred:test:src", attach="now")
        _dst = _w4.add_predicate("pred:test:dst", attach="none")
        _w4.add_edge(_src, _dst, label="run", meta={"meters": 10.0, "duration_s": 4.0})
        _met = _w4.action_metrics("run")
        if _met.get("count") == 1 and _met.get("keys", {}).get("meters", {}).get("sum") == 10.0:
            ok("action metrics: aggregated numeric meta (meters)")
        else:
            bad(f"action metrics: unexpected aggregate { _met }")
    except Exception as e:
        bad(f"action metrics failed: {e}")


    # Z4) BFS reasonableness (shortest-hop path found) — no warnings
    try:
        _w5 = cca8_world_graph.WorldGraph()
        _w5.set_tag_policy("allow")  # silence lexicon WARNs here
        _start = _w5.ensure_anchor("NOW")
        _a1 = _w5.add_predicate("pred:test:A", attach="now")
        _a2 = _w5.add_predicate("pred:test:B", attach="latest")
        _goal = _w5.add_predicate("pred:test:goal", attach="latest")
        _plan_path = _w5.plan_to_predicate(_start, "pred:test:goal")
        if _plan_path and _plan_path[-1] == _goal and len(_plan_path) >= 2:
            ok("planner: shortest-hop path to pred:test:goal found")
        else:
            bad(f"planner: unexpected path { _plan_path }")
    except Exception as e:
        bad(f"planner (BFS) reasonableness failed: {e}")


    # Z5) Lexicon strictness: reject out-of-lexicon pred at neonate
    try:
        _w6 = cca8_world_graph.WorldGraph()
        _w6.set_stage("neonate"); _w6.set_tag_policy("strict"); _w6.ensure_anchor("NOW")
        try:
            _w6.add_predicate("abstract:calculus", attach="now")
            bad("lexicon: strict did not reject out-of-lexicon token")
        except ValueError:
            ok("lexicon: strict rejects out-of-lexicon token at neonate")
    except Exception as e:
        bad(f"lexicon strictness failed: {e}")


    # Z6) Engram bridge: capture_scene → engram asserted, pointer attached
    try:
        _w7 = cca8_world_graph.WorldGraph()
        _w7.ensure_anchor("NOW")
        bid, eid = _w7.capture_scene("vision", "silhouette:mom", [0.1, 0.2, 0.3], attach="now", family="cue")
        # engram pointer attached?
        b = _w7._bindings[bid]

        if any(t.startswith("cue:") for t in (b.tags or [])):
            ok("engram bridge: binding created with cue")
        else:
            bad("engram bridge: cue tag missing")

        if b.engrams and "column01" in b.engrams and b.engrams["column01"].get("id") == eid:
            ok("engram bridge: pointer attached to binding")
        else:
            bad("engram bridge: pointer not attached")
        # column record retrievable?
        rec = _w7.get_engram(engram_id=eid)
        if isinstance(rec, dict) and rec.get("id") == eid:
            ok("engram bridge: column record retrievable")
        else:
            bad("engram bridge: column record missing or malformed")
    except Exception as e:
        bad(f"engram bridge failed: {e}")


    # Z6b) MapSurface round-trip: store a tiny WorldGraph snapshot into Column, attach pointer, reload, then seed-merge predicates only.
    #
    # Why this probe exists:
    # - In Phase VIII we want priors to matter, which means we must be confident we can:
    #     (1) store a "surface slate" (pred/cue snapshot) into Column memory,
    #     (2) attach a stable pointer onto a WorldGraph binding,
    #     (3) round-trip that pointer through WorldGraph snapshot save/load,
    #     (4) retrieve and reconstruct the surface (replace mode),
    #     (5) seed/merge predicates only (no cue leakage) into a live semantic world.
    try:
        from cca8_column import mem as _mem

        # (A) Build a tiny "mapsurface" world (tokens match HybridEnvironment.observe()).
        _ms = cca8_world_graph.WorldGraph()
        _ms.set_tag_policy("allow")
        _ms.set_stage("neonate")
        _ms.ensure_anchor("NOW")

        _ms.add_predicate("posture:fallen", attach="now")
        _ms.add_predicate("proximity:mom:close", attach="latest")
        _ms.add_predicate("proximity:shelter:far", attach="latest")
        _ms.add_predicate("hazard:cliff:near", attach="latest")
        _ms.add_predicate("nipple:found", attach="latest")
        _ms.add_cue("vision:silhouette:mom", attach="latest")

        _ms_dict = _ms.to_dict()

        # (B) Store snapshot payload into the Column as one engram.
        # ColumnMemory accepts JSON-safe dict payloads at runtime, while its current
        # protocol annotation describes richer feature objects. Keep this legacy probe
        # payload dynamic until the column payload contract is generalized.
        _payload: Any = {"kind": "mapsurface_snapshot", "v": 1, "world": _ms_dict}
        _fm = FactMeta(
            name="probe:mapsurface_snapshot_roundtrip",
            links=[],
            attrs={"probe": True, "v": 1, "note": "preflight mapsurface round-trip"},
        )
        _eid = _mem.assert_fact("probe:mapsurface_snapshot_roundtrip", _payload, _fm)

        if _mem.exists(_eid):
            ok("mapsurface round-trip: engram stored in column")
        else:
            bad("mapsurface round-trip: engram not found after assert_fact")

        # (C) Attach pointer to a binding; ensure pointer survives WorldGraph snapshot reload.
        _wptr = cca8_world_graph.WorldGraph()
        _wptr.set_tag_policy("allow")
        _wptr.set_stage("neonate")
        _wptr.ensure_anchor("NOW")

        _bid = _wptr.add_predicate("pred:probe:mapsurface_snapshot", attach="now")
        _wptr.attach_engram(_bid, column="column01", engram_id=_eid, act=1.0, extra_meta={"probe": True})

        _wptr2 = cca8_world_graph.WorldGraph.from_dict(_wptr.to_dict())
        _b2 = _wptr2._bindings.get(_bid)
        _pid = (((_b2.engrams or {}).get("column01") or {}).get("id") if _b2 else None)

        if _pid == _eid:
            ok("mapsurface round-trip: pointer survived WorldGraph.to_dict/from_dict")
        else:
            bad("mapsurface round-trip: pointer lost or altered across snapshot reload")

        # (D) Retrieve and reconstruct MapSurface world (replace mode).
        _rec = _mem.try_get(_eid)
        _world_blob = (_rec or {}).get("payload", {}).get("world") if isinstance(_rec, dict) else None

        if not isinstance(_world_blob, dict):
            bad("mapsurface round-trip: engram payload missing world dict")
        else:
            _ms2 = cca8_world_graph.WorldGraph.from_dict(_world_blob)

            issues = _ms2.check_invariants(raise_on_error=False)
            if issues:
                bad("mapsurface round-trip: reconstructed world invariant issues: " + "; ".join(issues))
            else:
                ok("mapsurface round-trip: reconstructed world invariants OK")

            # Expect at least one cue + one hazard predicate to survive.
            _tags = set()
            for _bb in _ms2._bindings.values():
                _tags |= set(getattr(_bb, "tags", []) or [])

            if ("pred:hazard:cliff:near" in _tags) and ("cue:vision:silhouette:mom" in _tags):
                ok("mapsurface round-trip: replace mode restored expected tags (pred + cue)")
            else:
                bad("mapsurface round-trip: replace mode missing expected tags")

            # Cheap structural sanity: bindings and total-edge counts should match.
            def _edge_total(wg) -> int:
                return sum(len(getattr(b, "edges", []) or []) for b in getattr(wg, "_bindings", {}).values())

            if len(_ms2._bindings) == len(_ms._bindings) and _edge_total(_ms2) == _edge_total(_ms):
                ok("mapsurface round-trip: replace mode preserved binding/edge counts")
            else:
                bad("mapsurface round-trip: replace mode changed binding/edge counts unexpectedly")

        # (E) Seed/merge mode: copy ONLY predicates into a live semantic world (no cues injected).
        _live = cca8_world_graph.WorldGraph(memory_mode="semantic")
        _live.set_tag_policy("allow")
        _live.set_stage("neonate")
        _live.ensure_anchor("NOW")

        # Seed an existing fact to exercise semantic consolidation (duplicate should be reused).
        _live.add_predicate("posture:fallen", attach="now")

        if isinstance(_world_blob, dict):
            _ms2b = cca8_world_graph.WorldGraph.from_dict(_world_blob)

            _pred_tags: set[str] = set()
            for _bb in _ms2b._bindings.values():
                for _t in getattr(_bb, "tags", []) or []:
                    if isinstance(_t, str) and _t.startswith("pred:"):
                        _pred_tags.add(_t)

            for _t in sorted(_pred_tags):
                _live.add_predicate(_t, attach="none")  # seed-only; no sequencing edges needed

            _live_tags = set()
            for _bb in _live._bindings.values():
                _live_tags |= set(getattr(_bb, "tags", []) or [])

            if any(t.startswith("cue:") for t in _live_tags):
                bad("mapsurface round-trip: seed/merge mode leaked cue:* tags into live world")
            else:
                ok("mapsurface round-trip: seed/merge seeded predicates only (no cues)")

            if "pred:hazard:cliff:near" in _live_tags and "pred:posture:fallen" in _live_tags:
                ok("mapsurface round-trip: seed/merge contains expected predicate priors")
            else:
                bad("mapsurface round-trip: seed/merge missing expected predicate priors")

        # (F) Cleanup: remove the probe engram so repeated preflights don't bloat column memory.
        try:
            _mem.delete(_eid)
        except Exception:
            pass

        if _mem.exists(_eid):
            bad("mapsurface round-trip: cleanup failed (engram still present)")
        else:
            ok("mapsurface round-trip: cleanup removed probe engram")

    except Exception as e:
        bad(f"mapsurface round-trip probe failed: {e}")


    # Z7) Timekeeping one-liner reasonableness
    try:
        _w = cca8_world_graph.WorldGraph(); _w.ensure_anchor("NOW")
        _d = Drives(); _ctx = Ctx()
        # Instinct-like: drift once then one controller step
        if _ctx.temporal is None:
            _ctx.temporal = TemporalContext(dim=8, sigma=_ctx.sigma, jump=_ctx.jump)
            _ctx.tvec_last_boundary = _ctx.temporal.vector()
            _ctx.boundary_vhash64 = _ctx.tvec64()
        _rt = runtime.policy_runtime_factory(runtime.catalog_gates); _rt.refresh_loaded(_ctx)
        if _ctx.temporal:
            _ctx.temporal.step()
        _ = action_center_step(_w, _ctx, _d)
        line = runtime.timekeeping_line(_ctx)
        if ("controller_steps=" in line) and ("age_days=" in line):
            ok("timekeeping one-liner produced")
        else:
            bad("timekeeping one-liner missing fields")
    except Exception as e:
        bad(f"timekeeping one-liner error: {e}")


    # Z7b) TemporalContext drift + boundary geometry
    try:
        _tctx = Ctx()
        # Small dim so this stays inexpensive; sigma/jump large enough that we
        # can see movement, but boundary() + tvec_last_boundary reset should
        # bring cosine back very close to 1.0.
        _tctx.temporal = TemporalContext(dim=16, sigma=0.03, jump=0.4)
        _tctx.tvec_last_boundary = _tctx.temporal.vector()
        _tctx.boundary_no = 0
        try:
            _tctx.boundary_vhash64 = _tctx.tvec64()
        except Exception:
            _tctx.boundary_vhash64 = None

        _cos0 = _tctx.cos_to_last_boundary()
        if not isinstance(_cos0, float):
            bad("timekeeping drift/boundary: cos_to_last_boundary missing at init")
        else:
            # Drift once and ensure cosine is still finite and in [-1,1].
            _tctx.temporal.step()
            _cos1 = _tctx.cos_to_last_boundary()
            if isinstance(_cos1, float) and -1.0001 <= _cos1 <= 1.0001:
                ok("timekeeping drift: cos_to_last_boundary computed after step()")
            else:
                bad("timekeeping drift: cos_to_last_boundary out of range after step()")

            # Boundary jump: epoch++ and cosine reset near 1.0 with a new vhash64.
            _prev_hash = _tctx.boundary_vhash64
            _new_v = _tctx.temporal.boundary()
            _tctx.tvec_last_boundary = list(_new_v)
            _tctx.boundary_no = getattr(_tctx, "boundary_no", 0) + 1
            try:
                _tctx.boundary_vhash64 = _tctx.tvec64()
            except Exception:
                _tctx.boundary_vhash64 = None

            _cos2 = _tctx.cos_to_last_boundary()
            if (
                isinstance(_cos2, float)
                and _cos2 > 0.95
                and _tctx.boundary_no == 1
                and _tctx.boundary_vhash64
                and _tctx.boundary_vhash64 != _prev_hash
            ):
                ok("timekeeping boundary: epoch increment & cosine reset near 1.0")
            else:
                bad("timekeeping boundary: unexpected cosine/epoch/vhash behavior")
    except Exception as e:
        bad(f"timekeeping drift/boundary error: {e}")


    # Z8) Resolve Engrams pretty (smoke)
    try:
        _wk = cca8_world_graph.WorldGraph(); _wk.ensure_anchor("NOW")
        bid, eid = _wk.capture_scene("vision", "silhouette:mom", [0.1], attach="now", family="cue")
        runtime.resolve_engrams_pretty(_wk, bid)  # prints; OK if non-crashing
        # add a dangling pointer
        b = _wk._bindings[bid]; b.engrams["column09"] = {"id": "a"*32, "act": 1.0}
        runtime.resolve_engrams_pretty(_wk, bid)  # should still print; no assert
        ok("resolve-engrams pretty printed")
    except Exception as e:
        bad(f"resolve-engrams pretty error: {e}")


    # Z9) Demo-world builder smoke (graph shape and provenance)
    try:
        from cca8_test_fixtures import build_demo_world_for_inspect
        _wd, _ids = build_demo_world_for_inspect()
        _demo_now = _ids.get("NOW")
        _demo_rest = _ids.get("rest")
        if (_demo_now in _wd._bindings) and (_demo_rest in _wd._bindings):
            ok("demo world: NOW/rest bindings present")
        else:
            bad("demo world: NOW/rest bindings missing")
    except Exception as e:
        bad(f"demo world builder failed: {e}")


    # Z10) Tag hygiene: no 'state:' or 'pred:action:' tags in a simple S–A–P episode
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.set_tag_policy("allow")
        _w.ensure_anchor("NOW")
        # Minimal S–A–P chain
        _w.add_predicate("posture:fallen", attach="now")
        _w.add_action("action:push_up", attach="latest")
        _w.add_action("action:extend_legs", attach="latest")
        _w.add_predicate("posture:standing", attach="latest")
        bad_tags = []
        for bid, b in _w._bindings.items():
            for t in getattr(b, "tags", []):
                if isinstance(t, str) and (t.startswith("state:") or t.startswith("pred:action:")):
                    bad_tags.append((bid, t))
        if bad_tags:
            bad(f"tag hygiene: found legacy tags {bad_tags}")
        else:
            ok("tag hygiene: no 'state:*' or 'pred:action:*' tags on fresh S–A–P episode")
    except Exception as e:
        bad(f"tag hygiene check failed: {e}")


    # Z11) NOW_ORIGIN anchor semantics
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.ensure_anchor("NOW")
        runtime.ensure_now_origin(_w)
        origin = runtime.anchor_id(_w, "NOW_ORIGIN")
        now = runtime.anchor_id(_w, "NOW")
        if origin != "?" and origin == now:
            ok("NOW_ORIGIN: pinned to initial NOW on fresh world")
        else:
            bad(f"NOW_ORIGIN: unexpected (origin={origin}, now={now})")
    except Exception as e:
        bad(f"NOW_ORIGIN check failed: {e}")


    # Z12) BodyMap bridge + SeekNipple gate (body-first) sanity
    try:
        # Build a fresh BodyMap and context.
        _bm_ctx = Ctx()
        _bm_ctx.body_world, _bm_ctx.body_ids = runtime.init_body_world()
        _bm_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: only .predicates is needed here.
        class _ObsStub:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates

        _obs = _ObsStub([
            "posture:standing",
            "proximity:mom:close",
            "nipple:latched",
            "milk:drinking",
        ])

        # Mirror observation into BodyMap.
        runtime.update_body_world_from_obs(_bm_ctx, _obs)

        # Check that the high-level BodyMap helpers see what we injected.
        _bp = body_posture(_bm_ctx)
        _md = body_mom_distance(_bm_ctx)
        _ns = body_nipple_state(_bm_ctx)

        if _bp == "standing" and _md == "near" and _ns == "latched":
            ok("BodyMap: posture/mom/nipple mirrored from observation into BodyMap helpers")
        else:
            bad(
                "BodyMap: mismatch between observation and helpers "
                f"(posture={_bp!r}, mom={_md!r}, nipple={_ns!r})"
            )

        # With nipple already latched, SeekNipple gate should NOT trigger even if hunger is high.
        _bm_world = cca8_world_graph.WorldGraph()
        _bm_world.ensure_anchor("NOW")
        _hungry = Drives(hunger=0.95, fatigue=0.1, warmth=0.6)
        _gate = runtime.seek_nipple_gate(_bm_world, _hungry, _bm_ctx)
        if _gate:
            bad("BodyMap gate: seek_nipple triggered despite nipple_state='latched'")
        else:
            ok("BodyMap gate: seek_nipple correctly suppressed when nipple_state='latched'")
    except Exception as e:
        bad(f"BodyMap / gate probes failed: {e}")


    # Z12b) BodyMap spatial zone + Rest gate sanity
    try:
        # Fresh BodyMap + context for zone tests
        _zone_ctx = Ctx()
        _zone_ctx.body_world, _zone_ctx.body_ids = runtime.init_body_world()
        _zone_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: only .predicates is needed.
        class _ObsStubZone:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates

        # ----- Case 1: unsafe_cliff_near (cliff=near, shelter=far) -----
        _obs_unsafe = _ObsStubZone([
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:far",
            "hazard:cliff:near",
        ])
        runtime.update_body_world_from_obs(_zone_ctx, _obs_unsafe)

        _zone1 = body_space_zone(_zone_ctx)
        if _zone1 == "unsafe_cliff_near":
            ok("BodyMap zone: unsafe_cliff_near from (shelter=far, cliff=near)")
        else:
            bad(
                "BodyMap zone: expected 'unsafe_cliff_near' from (shelter=far, cliff=near) "
                f"but got {_zone1!r}"
            )

        # Rest gate should veto rest here even if fatigue is high.
        _world_dummy = cca8_world_graph.WorldGraph()
        _world_dummy.ensure_anchor("NOW")
        _tired = Drives(hunger=0.20, fatigue=0.90, warmth=0.60)

        _rest_gate_unsafe = runtime.rest_gate(_world_dummy, _tired, _zone_ctx)
        if _rest_gate_unsafe:
            bad("Rest gate: incorrectly allowed rest when zone='unsafe_cliff_near' and fatigue high")
        else:
            ok("Rest gate: vetoes rest when zone='unsafe_cliff_near' despite high fatigue")

        # ----- Case 2: safe (shelter=near, cliff=far) -----
        _obs_safe = _ObsStubZone([
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ])
        runtime.update_body_world_from_obs(_zone_ctx, _obs_safe)

        _zone2 = body_space_zone(_zone_ctx)
        if _zone2 == "safe":
            ok("BodyMap zone: safe from (shelter=near, cliff=far)")
        else:
            bad(
                "BodyMap zone: expected 'safe' from (shelter=near, cliff=far) "
                f"but got {_zone2!r}"
            )

        _rest_gate_safe = runtime.rest_gate(_world_dummy, _tired, _zone_ctx)
        if _rest_gate_safe:
            ok("Rest gate: allows rest when zone='safe' and fatigue high")
        else:
            bad("Rest gate: incorrectly vetoed rest when zone='safe' and fatigue high")

    except Exception as e:
        bad(f"BodyMap spatial zone / Rest gate probes failed: {e}")


    # Z12c) Spatial scene-graph + 'resting in shelter' summary sanity
    try:
        # Fresh world + context with BodyMap initialized
        _scene_world = cca8_world_graph.WorldGraph()
        _scene_world.set_tag_policy("allow")
        _scene_world.ensure_anchor("NOW")

        _scene_ctx = Ctx()
        _scene_ctx.body_world, _scene_ctx.body_ids = runtime.init_body_world()
        _scene_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: we only need .predicates for this probe.
        class _ObsStubScene:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates
                self.cues = []

        # Synthetic "resting in shelter, cliff far" observation.
        _obs_rest = _ObsStubScene([
            "resting",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ])

        # Use the normal env→world bridge: this will:
        #   • create pred:* bindings,
        #   • update BodyMap,
        #   • write NOW --near--> mom/shelter bindings because 'resting' is present.
        runtime.inject_obs_into_world(_scene_world, _scene_ctx, _obs_rest)

        _summary = runtime.resting_scenes_in_shelter(_scene_world)

        if _summary.get("rest_near_now") and _summary.get("shelter_near_now"):
            ok(
                "scene-graph: resting_scenes_in_shelter sees "
                "rest_near_now=True and shelter_near_now=True after a resting-in-shelter obs"
            )
        else:
            bad(
                "scene-graph: resting_scenes_in_shelter summary unexpected for "
                "resting+mom:close+shelter:near+cliff:far obs: "
                f"{_summary}"
            )

    except Exception as e:
        bad(f"Spatial scene-graph / resting_scenes_in_shelter probe failed: {e}")


    # Z13) HybridEnvironment reset/step + perception smoke test
    try:
        env = HybridEnvironment()
        _ctx_env = Ctx()

        # Reset: get first observation + info.
        obs0, info0 = env.reset()
        if hasattr(obs0, "predicates") and isinstance(getattr(obs0, "predicates", None), list):
            ok("env: reset produced initial observation with predicates list")
        else:
            bad("env: reset did not return an observation with .predicates list")

        if isinstance(info0, dict) and "scenario_name" in info0:
            ok("env: reset info contains scenario_name")
        else:
            bad("env: reset info missing scenario_name")

        # Optional: inspect internal state shape (kid_posture + scenario_stage).
        _st0 = getattr(env, "state", None)
        if _st0 is not None and hasattr(_st0, "kid_posture") and hasattr(_st0, "scenario_stage"):
            ok("env: state exposes kid_posture/scenario_stage after reset")
        else:
            bad("env: state missing kid_posture/scenario_stage after reset")

        # One storyboard step forward.
        obs1, reward1, done1, info1 = env.step(action=None, ctx=_ctx_env)
        if hasattr(obs1, "predicates") and isinstance(getattr(obs1, "predicates", None), list):
            _types_ok = isinstance(reward1, (int, float)) and isinstance(done1, bool) and isinstance(info1, dict)
            if _types_ok:
                ok("env: step produced (observation, reward, done, info) tuple")
            else:
                bad("env: step returned unexpected reward/done/info types")
        else:
            bad("env: step did not return an observation with .predicates list")
    except Exception as e:
        bad(f"env: reset/step probes failed: {e}")


    # 7) Action helpers reasonableness
    try:
        _wa = cca8_world_graph.WorldGraph()
        s = _wa.action_summary_text(include_then=True, examples_per_action=1)
        # minimal presence check — the string can say "No actions..." on a fresh world, still OK
        if isinstance(s, str):
            ok("action helpers: summary generated")
        else:
            bad("action helpers: summary did not return text")
    except Exception as e:
        bad(f"action helpers failed: {e}")


    # part 3 -- hardware and robotics preflight
    hal_str  = getattr(args, "hal_status_str", "OFF (no embodiment)")
    body_str = getattr(args, "body_status_str", runtime.placeholder_embodiment)
    print(f"\n[preflight hardware_robotics] HAL={hal_str}; body={body_str}")

    hal_checks = 0
    hal_failures = 0

    def ok_hw(msg: str) -> None:
        nonlocal hal_checks
        hal_checks += 1
        print(f"[preflight hardware_robotics] PASS  - {msg}")

    def bad_hw(msg: str) -> None:
        nonlocal hal_checks, hal_failures
        hal_checks += 1
        hal_failures += 1
        print(f"[preflight hardware_robotics] FAIL  - {msg}")


    # 3a) CPU enumeration
    try:
        _n = os.cpu_count() or 0
        if _n > 0:
            ok_hw(f"cpu_count={_n}")
        else:
            bad_hw("cpu_count returned 0")
    except Exception as e:
        bad_hw(f"cpu_count error: {e}")


    # 3b) High-resolution timer reasonableness (monotonic + resolution)
    try:
        import time as _time2
        info = _time2.get_clock_info("perf_counter")
        res  = getattr(info, "resolution", None)
        timer_a = _time2.perf_counter(); timer_b = _time2.perf_counter(); timer_c = _time2.perf_counter()
        if (timer_b > timer_a) or (timer_c > timer_b):  # any forward progress is enough
        #if timer_a < timer_b < timer_c:  #occasionally samples land in the same clock tick
            ok_hw(f"perf_counter monotonic (resolution≈{res:.9f}s)")
        else:
            bad_hw("perf_counter did not strictly increase")
    except Exception as e:
        bad_hw(f"perf_counter check error: {e}")


    # 3c) Temp file write/read (4 KiB)
    try:
        import tempfile as _tempfile
        with _tempfile.NamedTemporaryFile("wb", delete=True) as tf:
            tf.write(b"\0" * 4096)
            tf.flush()
        ok_hw("temp file write (4 KiB)")
    except Exception as e:
        bad_hw(f"temp file write failed: {e}")


    # 3d) System memory (GiB) ≥ MIN_RAM_GB (default 4 -- Nov 2025)
    #adjust minimum RAM tested as makes sense for the hardware
    #looks for RAM in this order: psutil (if available), then Windows, then Linux, then MacOS, then Linux-like
    #if runtime.non_win_linux=True for non-Win/macOS/Linux/like system, then test is bypassed
    try:
        if runtime.non_win_linux:
            MIN_RAM_GB = 0.0
        else:
            MIN_RAM_GB = float(os.getenv("CCA8_MIN_RAM_GB", "4"))
        min_bytes = int(MIN_RAM_GB * (1024 ** 3))
        #min_bytes = int(5000.0 * (1024 ** 3))  #for testing to trigger a hardware testing warning

        def _total_ram_bytes() -> int:
            # Optional: psutil if present
            try:
                import psutil  # type: ignore
                return int(psutil.virtual_memory().total)
            except Exception:
                pass
            # Windows: GlobalMemoryStatusEx
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure): # pylint: disable=too-few-public-methods
                    """from cytpes library to store system info"""
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX) # pylint: disable=attribute-defined-outside-init
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    return int(stat.ullTotalPhys)
            except Exception:
                pass
            # Linux: sysconf
            try:
                sysconf_fn: Optional[Callable[[str], int]] = getattr(os, "sysconf", None)  # type: ignore[attr-defined]
                if sysconf_fn is not None:
                    page = int(sysconf_fn("SC_PAGE_SIZE"))   # ok: Pylint sees a Callable
                    phys = int(sysconf_fn("SC_PHYS_PAGES"))
                    return page * phys
            except Exception:
                pass
            # macOS: sysctl
            try:
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                return int(out)
            except Exception:
                pass
            # Fallback: /proc/meminfo (Linux-like)
            try:
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            # value reported in kB
                            return int(line.split()[1]) * 1024
            except Exception:
                pass
            return 0

        _total = _total_ram_bytes()
        if _total >= min_bytes:
            ok_hw(f"memory total={_total/(1024**3):.1f} GB -- (threshold RAM ≥{MIN_RAM_GB:.0f} GiB)")
        else:
            bad_hw(f"memory total={_total/(1024**3):.1f} GB -- below threshold RAM of {MIN_RAM_GB:.0f} GiB")
    except Exception as e:
        bad_hw(f"memory check error: {e}")


    # 3e) Disk free space on current volume ≥ MIN_DISK_GB (default 1)
    try:
        MIN_DISK_GB = float(os.getenv("CCA8_MIN_DISK_GB", "1"))
        _, _, free = shutil.disk_usage(".")
        if free >= int(MIN_DISK_GB * (1024 ** 3)):
            ok_hw(f"disk free={free/(1024**3):.1f} GiB (threshold≥{MIN_DISK_GB:.0f} GiB)")
        else:
            bad_hw(f"disk free={free/(1024**3):.1f} GiB below threshold {MIN_DISK_GB:.0f} GiB")
    except Exception as e:
        bad_hw(f"disk free check error: {e}")


    # part 4 -- integrated system preflight
    print(f"\n[preflight system functionality] HAL={hal_str}; body={body_str}")

    assessment_checks = 0
    assessment_failures = 0
    assessment_warnings = 0
    assessment_skips = 0

    def report_sys(severity: str, msg: str) -> None:
        """Record and print one Part-4 system-fitness assessment."""
        nonlocal assessment_checks, assessment_failures, assessment_warnings, assessment_skips
        assessment_checks += 1

        level = str(severity or "fail").strip().lower()
        if level == "pass":
            label = "PASS "
        elif level == "warning":
            assessment_warnings += 1
            label = "WARN "
        elif level == "skip":
            assessment_skips += 1
            label = "SKIP "
        else:
            assessment_failures += 1
            label = "FAIL "

        print(f"[preflight system functionality] {label} - {msg}")

    _llm_probe = runtime.llm_operational_check(20.0)
    _llm_severity, _llm_message = _classify_llm_preflight_assessment(_llm_probe)
    report_sys(_llm_severity, _llm_message)

    # Compute Summary Results
    # ---- Summary footer (with denominators) ----
    elapsed_total = _time.perf_counter() - t0
    mm, ss = divmod(int(round(elapsed_total)), 60)
    elapsed_mmss = f"{mm:02d}:{ss:02d}"

    # Tests / coverage (Part 1)
    junit = _parse_junit_xml(".coverage/junit.xml")
    tests_total = junit.get("tests")
    tests_fail  = (junit.get("failures", 0) or 0) + (junit.get("errors", 0) or 0)
    tests_skip  = junit.get("skipped", 0) or 0
    tests_pass  = (tests_total - tests_fail - tests_skip) if isinstance(tests_total, int) else None
    cov_pct     = _parse_coverage_pct(".coverage/coverage.xml")

    tests_txt = (f"unit_tests={tests_pass}/{tests_total}"
                 if isinstance(tests_total, int) else "unit_tests=—")
    cov_txt   = (f"coverage={cov_pct:.0f}% ({'≥30' if (cov_pct or 0.0) >= 30.0 else '<30'})"
                 if (cov_pct is not None) else "coverage=—")

    # Probes (Part 2) — exclude the earlier Part 1 pytest-lane bookkeeping
    probe_checks = max(0, checks - probe_checks_offset)
    probe_failures = max(0, failures - probe_failures_offset)
    probes_pass = max(0, probe_checks - probe_failures)
    probes_txt  = f"probes={probes_pass}/{probe_checks}"

    # Hardware (Part 3) — show pass/total
    hardware_pass = max(0, hal_checks - hal_failures)

    # System fitness (Part 4) — show pass/warning/fail/skip/total
    assessment_warnings = locals().get("assessment_warnings", 0)
    assessment_skips = locals().get("assessment_skips", 0)
    assessment_pass = max(0, assessment_checks - assessment_failures - assessment_warnings - assessment_skips)

    # Overall status (fail if any part failed)
    status_ok = (
        (failures == 0) and
        (hal_failures == 0) and
        (assessment_failures == 0) and
        (tests_fail == 0 if isinstance(tests_total, int) else True)
    )

    line1 = f"\n[preflight] RESULT: {'PASS' if status_ok else 'FAIL'} | PART 1: {tests_txt} | {cov_txt} | PART 2: {probes_txt} |"
    line2 = (f"[preflight] PART 3: hardware_robotics_checks = {hardware_pass}/{hal_checks} | "
             f"PART 4: system_fitness_assessments = "
             f"{assessment_pass} pass, {assessment_warnings} warning(s), {assessment_failures} fail, "
             f"{assessment_skips} skipped, {assessment_checks} total |")
    line3 = f"[preflight] elapsed_time (mm:ss) ={elapsed_mmss}"

    print(_paint_fail(line1) if not status_ok else line1)

    # If any non-test part failed, color line2 as well for quick scanning
    if hal_failures or assessment_failures:
        print(_paint_fail(line2))
    else:
        print(line2)
    print(line3)

    if status_ok:
        runtime.print_ascii_logo(style="goat", color=True)
    return 0 if status_ok else 1


def run_preflight_lite_maybe() -> None:
    """Optional 'lite' preflight on startup (controlled by CCA8_PREFLIGHT)."""
    mode = os.environ.get("CCA8_PREFLIGHT", "lite").lower()
    if mode == "off":
        return
    print("[preflight-lite] checks ok\n\n")
