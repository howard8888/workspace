# -*- coding: utf-8 -*-
"""
Phase X: per-cycle JSON record tests.

We test the helper directly (fast, deterministic). If the helper writes JSONL to disk
when ctx.cycle_json_path is set, this test also validates that behavior.
"""

from __future__ import annotations

import json
import inspect

import cca8_run


def test_append_cycle_json_record_appends_to_ctx() -> None:
    ctx = cca8_run.Ctx()
    ctx.cycle_json_enabled = True

    assert ctx.cycle_json_records == []

    cca8_run.append_cycle_json_record(ctx, {"i": 1, "msg": "hello"})
    assert len(ctx.cycle_json_records) == 1
    assert ctx.cycle_json_records[0]["i"] == 1


def test_append_cycle_json_record_writes_jsonl_when_enabled(tmp_path) -> None:
    ctx = cca8_run.Ctx()
    ctx.cycle_json_enabled = True

    out_path = tmp_path / "cycle.jsonl"
    ctx.cycle_json_path = str(out_path)

    cca8_run.append_cycle_json_record(ctx, {"i": 1})
    cca8_run.append_cycle_json_record(ctx, {"i": 2})

    # If your build doesn't implement on-disk JSONL yet, this assertion will fail,
    # which is a useful signal to either (a) implement it, or (b) remove the feature flag.
    assert out_path.exists()

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["i"] == 1
    assert json.loads(lines[1])["i"] == 2

    # Bonus sanity: ensure the helper actually references cycle_json_path in code.
    src = inspect.getsource(cca8_run.append_cycle_json_record)
    assert "cycle_json_path" in src
