"""Bounded string-only wrapping reuse; every existing exhaustive trace case stays.

Reference functions below are the pre-optimization algorithms, not calls back
into the changed helpers. No wall-clock assertion makes slower CI machines fail.
The original 318 prefix/suffix render calls remain in test_nca8_trace_flow.py.
"""
from __future__ import annotations

import random
import textwrap

import pytest

from nca8_runtime import Nca8SessionV1
import nca8_trace as trace


def original_ascii(text):
    return "".join(character if " " <= character <= "~" else ascii(character)[1:-1] for character in text)


def original_wrap(text, width, *, indent=""):
    return textwrap.wrap(original_ascii(text), width=width, initial_indent=indent, subsequent_indent=indent,
                         break_long_words=True, break_on_hyphens=False) or [indent]


@pytest.mark.parametrize("text", ["", "plain ASCII 'quotes' \\", " \t\n\r\x00\x1f\x7f", "maternal → support ≥ 0.5", "雪 🐐 é",
                                  "\ud800\udfff", "".join(chr(code) for code in range(256)), "a" * 513])
def test_ascii_fast_path_is_exact_original_character_conversion(text):
    assert trace._flow_ascii_v1(text) == original_ascii(text)


@pytest.mark.parametrize("text", ["", "a", "ordinary short words to wrap with context", "a-b-c " * 40, "z" * 510, "X" * 514, "\t→\n" * 20])
@pytest.mark.parametrize("width,indent", [(1, ""), (60, "  "), (96, "    "), (140, ""), (141, ""), (96, " " * 33)])
def test_cached_and_uncached_wrapping_match_original(text, width, indent):
    trace._flow_wrap_cached_v1.cache_clear()
    expected = original_wrap(text, width, indent=indent)
    assert trace._flow_wrap_v1(text, width, indent=indent) == expected
    assert trace._flow_wrap_v1(text, width, indent=indent) == expected


def test_repeated_formatting_reuses_work_but_returns_an_independent_list():
    trace._flow_wrap_cached_v1.cache_clear()
    first = trace._flow_wrap_v1("same text and width", 96, indent="  ")
    first[0] = "tampered"
    second = trace._flow_wrap_v1("same text and width", 96, indent="  ")
    assert second == ["  same text and width"] and first is not second
    info = trace._flow_wrap_cached_v1.cache_info()
    assert info.hits == 1 and info.misses == 1 and info.currsize == 1


def test_cache_is_finite_and_eviction_cannot_change_output():
    trace._flow_wrap_cached_v1.cache_clear()
    expected = trace._flow_wrap_v1("first formatting input", 96)
    for index in range(1100):
        trace._flow_wrap_v1(f"unique formatting input {index}", 96)
    info = trace._flow_wrap_cached_v1.cache_info()
    assert info.maxsize == info.currsize == 1024
    assert trace._flow_wrap_v1("first formatting input", 96) == expected


@pytest.mark.parametrize("text,width,indent", [("x" * 513, 96, ""), ("x", 141, ""), ("x", 96, " " * 33), ("→" * 100, 96, "")])
def test_unbounded_input_sizes_bypass_cache(text, width, indent):
    trace._flow_wrap_cached_v1.cache_clear()
    assert trace._flow_wrap_v1(text, width, indent=indent) == original_wrap(text, width, indent=indent)
    assert trace._flow_wrap_cached_v1.cache_info().currsize == 0


@pytest.mark.parametrize("width", [0, -1])
def test_invalid_width_preserves_original_failure(width):
    with pytest.raises(ValueError):
        original_wrap("text", width)
    with pytest.raises(ValueError):
        trace._flow_wrap_v1("text", width)


@pytest.mark.parametrize("width", [60, 96, 140])
def test_whole_and_partial_trace_output_matches_uncached_original_with_cold_warm_and_eviction(monkeypatch, width):
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    events = session.trace_snapshot()
    state = random.getstate()
    for subset in (events, events[:23], events[27:], events[57:93]):
        trace._flow_wrap_cached_v1.cache_clear()
        cold = trace.render_flow_trace_lines_v1(subset, width=width, include_details=False)
        assert trace.render_flow_trace_lines_v1(subset, width=width, include_details=False) == cold
        for index in range(1100):
            trace._flow_wrap_v1(f"eviction pressure {index}", 60)
        assert trace.render_flow_trace_lines_v1(subset, width=width, include_details=False) == cold
        with monkeypatch.context() as isolated:
            isolated.setattr(trace, "_flow_wrap_v1", original_wrap)
            assert trace.render_flow_trace_lines_v1(subset, width=width, include_details=False) == cold
    assert session.trace_snapshot() == events and random.getstate() == state
