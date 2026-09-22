"""H5 review routing, read-only inspection and explicit source/actuation limits."""

from __future__ import annotations

import ast
import builtins
import json
import random
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

import pytest

import nca8_menu
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_righting import RightingActivityV1, RightingApplicationV1, RightingContextV1, RightingIPV1
from nca8_righting_demo import (
    competing_preview_bid_v1, render_righting_preview_v1, run_righting_preview_examples_v1, run_righting_preview_review_v1,
)
from nca8_runtime import Nca8RightingPreviewSessionV1, Nca8SessionV1
from scripts.review_nca8_righting import main

ROOT = Path(__file__).resolve().parents[1]


def test_thirteen_examples_are_deterministic_without_rng_or_source_input_labels():
    before = random.getstate()
    first = run_righting_preview_examples_v1()
    second = run_righting_preview_examples_v1()
    assert len(first) == 13
    assert [item.result.as_dict() for item in first] == [item.result.as_dict() for item in second]
    assert random.getstate() == before
    for example in first:
        payload = example.result.as_dict()
        json.dumps(payload, allow_nan=False)
        assert example.name not in json.dumps(payload)
        assert payload["motor_dispatches"] == payload["target_installations"] == payload["durable_learning_updates"] == 0


def test_matched_pair_and_influence_pair_have_declared_selective_effects():
    results = run_righting_preview_examples_v1()
    good, bad = results[1].result, results[2].result
    assert good.source.motor_support.feedback == bad.source.motor_support.feedback
    assert good.navigation.application.strategy != bad.navigation.application.strategy
    on, off = results[8].result, results[9].result
    assert on.source.as_dict() == off.source.as_dict()
    assert on.navigation.selected_primitive_id == "ip:righting" and off.navigation.selected_primitive_id is None


@pytest.mark.parametrize("index", list(range(13)))
def test_rendering_does_not_recalculate_or_mutate_a_result(index):
    example = run_righting_preview_examples_v1()[index]
    before = example.result.as_dict()
    text = render_righting_preview_v1(example)
    assert text == render_righting_preview_v1(example)
    assert example.result.as_dict() == before
    assert "physical steps=0" in text
    assert "task success not established" in text
    assert "Navigation selected=" in text


def test_menu_and_script_use_identical_shared_review_output(monkeypatch, capsys):
    output = StringIO()
    with redirect_stdout(output):
        assert main() == 0
    responses = iter(("7", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    assert output.getvalue() in capsys.readouterr().out


def test_opening_menu_does_not_run_preview_or_create_a_session(monkeypatch):
    def prohibited(*_args, **_kwargs):
        raise AssertionError("menu opening performed work")

    monkeypatch.setattr(nca8_menu, "run_righting_preview_review_v1", prohibited)
    monkeypatch.setattr(nca8_menu, "Nca8SessionV1", prohibited)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None


def test_h5_menu_keeps_existing_a0_session_unchanged(monkeypatch):
    retained = Nca8SessionV1()
    before = retained.status()
    trace = retained.trace_snapshot()
    responses = iter(("7", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(retained) is retained
    assert retained.status() == before and retained.trace_snapshot() == trace


def test_h4_menu_route_is_still_a_separate_unchanged_call(monkeypatch):
    calls = []
    monkeypatch.setattr(nca8_menu, "run_sensorimotor_review_menu_v1", lambda: calls.append("h4"))
    monkeypatch.setattr(nca8_menu, "run_righting_preview_review_v1", lambda: calls.append("h5"))
    responses = iter(("6", "7", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    assert calls == ["h4", "h5"]


def test_permanent_script_works_outside_repository_without_writing_files(tmp_path):
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/review_nca8_righting.py")],
                               cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "RIGHTING PREVIEW CHECKS COMPLETE" in completed.stdout
    assert "H6 integration and 1G outcomes remain open" in completed.stdout
    assert list(tmp_path.iterdir()) == []


def test_review_does_not_require_any_removed_phase_markdown(monkeypatch):
    original = Path.read_text

    def forbid_phase_notes(path, *args, **kwargs):
        assert not (path.suffix == ".md" and path.name.startswith("P18"))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", forbid_phase_notes)
    run_righting_preview_review_v1()


def test_task_computation_does_not_import_physics_controller_or_evaluator():
    tree = ast.parse((ROOT / "nca8_righting.py").read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not ({"cca8_support_world", "cca8_env", "nca8_sensorimotor", "nca8_sensorimotor_demo"} & modules)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"step_motor", "step", "milestones", "scenario_stage", "state", "_state"}


def test_source_influence_has_a_real_owner_and_consumer_not_only_a_printed_field(monkeypatch):
    calls = []
    original = nca8_menu.run_righting_preview_review_v1  # No execution from importing the menu.
    assert callable(original)
    stream = MotorStreamRefV1("fixture:influence", 1)
    owner = Nca8RightingPreviewSessionV1(stream)
    request_owner = owner.sensory.retain_motor_context

    def capture(*args, **kwargs):
        calls.append(args)
        return request_owner(*args, **kwargs)

    monkeypatch.setattr(owner.sensory, "retain_motor_context", capture)
    packet = MotorFeedbackV1(stream, 1, 0, 0, 30, 0.4, True, 0.5, 0.3)
    owner.preview(packet, cutoff_tick=0)
    result = owner.preview(packet, cutoff_tick=1, competing_bids=(competing_preview_bid_v1(2),))
    assert len(calls) == 2 and result.persistence_rank == 20
    assert result.attention.disposition.value == "maintain"


@pytest.mark.parametrize("invalid", [1, 0, "yes", None])
def test_invalid_enable_flag_does_not_create_a_cognitive_actor(invalid):
    with pytest.raises(TypeError):
        RightingIPV1(enabled=invalid)


@pytest.mark.parametrize("context_id", ["", " padded", "padded ", "a\nb", "a" * 81, 0, None])
def test_context_identity_is_bounded_explicit_printable_text(context_id):
    with pytest.raises((ValueError, TypeError)):
        RightingContextV1(context_id)


@pytest.mark.parametrize("kind", ["mobility", 1, None])
def test_context_requires_explicit_activity_vocabulary(kind):
    with pytest.raises(TypeError):
        RightingContextV1("fixture", kind)


def test_wrong_generation_or_source_cannot_borrow_a_live_task():
    examples = run_righting_preview_examples_v1()
    result = examples[0].result
    primitive = RightingIPV1()
    primitive.prepare_opportunity(cycle_id=1, at_tick=0, context=RightingContextV1())
    wnm = result.navigation.wnm
    applicability = primitive.evaluate_applicability(wnm, cycle_id=1)
    primitive.apply(wnm, applicability, cycle_id=1)
    primitive.prepare_opportunity(cycle_id=2, at_tick=4, context=RightingContextV1())
    from nca8_maps import DurableNavMapRefV1
    source = replace(result.source.motor_support, evidence=None, previous=None, source_map_ref=DurableNavMapRefV1("other", 1),
                     applied_cycle=2, cutoff_tick=4)
    assert primitive.source_status(source) == "current_source_unavailable"


def test_current_prospective_values_are_never_installed_as_current_source_facts():
    result = run_righting_preview_examples_v1()[1].result
    actual = result.source.motor_support.feedback
    app = result.navigation.application
    assert isinstance(app, RightingApplicationV1)
    assert actual.body_tilt_degrees == 30 and actual.useful_loading == 0.5
    assert app.projection.predicted_tilt == 21
    assert app.projection.predicted_loading > actual.useful_loading
    assert app.projection.basis.feedback is actual
    assert not app.projection.as_dict()["executed_obligation"]


def test_registry_lists_real_production_modules_without_changing_host_behavior_count():
    import cca8_run
    import nca8_righting
    import nca8_righting_demo
    import nca8_maps
    import nca8_sensory
    import nca8_prediction
    import nca8_executive
    import nca8_runtime
    assert cca8_run.__version__ == "0.30.32"
    assert nca8_righting.__version__ == "0.4.0" and nca8_righting_demo.__version__ == "0.1.1"
    assert nca8_maps.__version__ == "0.3.0" and nca8_executive.__version__ == "0.7.0"
    assert nca8_sensory.__version__ == "0.6.0"
    assert nca8_prediction.__version__ == "0.6.0" and nca8_runtime.__version__ == "0.17.0"
    assert nca8_menu.__version__ == "0.25.0"
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["nca8_righting"] == "nca8_righting" and registry["nca8_righting_demo"] == "nca8_righting_demo"
    assert len(cca8_run._cca8_component_rows()) == 99 and len(cca8_run.PRIMITIVES) == 8
