"""Compatibility checks for the extracted CCA8 policy-runtime subsystem."""

from __future__ import annotations

import ast
import inspect

import cca8_policy_runtime
import cca8_run
from cca8_controller import Drives


def test_runner_policy_runtime_compatibility(monkeypatch) -> None:
    """Preserve runner imports, live monkeypatch seams, registration, and one-way imports."""
    assert cca8_run.PolicyRuntimeHooks is cca8_policy_runtime.PolicyRuntimeHooks
    assert cca8_run.PolicyGate is cca8_policy_runtime.PolicyGate
    assert cca8_run.PolicyRuntime is cca8_policy_runtime.PolicyRuntime
    assert cca8_run.CATALOG_GATES is cca8_policy_runtime.CATALOG_GATES

    direct_aliases = (
        "_gate_stand_up_trigger_body_first",
        "_gate_seek_nipple_trigger_body_first",
        "_gate_rest_trigger_body_space",
        "_gate_probe_ambiguity_trigger_body_first",
        "_gate_follow_mom_trigger_body_space",
        "_gate_suckle_trigger_newborn_v1",
        "_gate_recover_fall_trigger_body_first",
        "_newborn_workingmap_state_v1",
        "_follow_mom_bridge_state_v1",
        "_newborn_recent_retrieval_ok_v1",
        "compute_efe_scores_stub_v1",
        "_wm_creative_update",
    )
    for name in direct_aliases:
        assert getattr(cca8_run, name) is getattr(cca8_policy_runtime, name)

    # The installed hook bundle stores runner-resolving lambdas rather than
    # frozen function objects, so focused monkeypatches must remain visible.
    ctx = cca8_run.Ctx()
    drives = Drives()
    monkeypatch.setattr(cca8_run, "bodymap_is_stale", lambda _ctx: False)
    monkeypatch.setattr(cca8_run, "body_posture", lambda _ctx: "fallen")
    monkeypatch.setattr(cca8_run, "has_pred_near_now", lambda *_args, **_kwargs: False)
    assert cca8_run._gate_stand_up_trigger_body_first(None, drives, ctx) is True

    assert ("policy_runtime", "cca8_policy_runtime") in cca8_run._CCA8_COMPONENT_REGISTRY

    source = inspect.getsource(cca8_policy_runtime)
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "cca8_run" not in imported_modules
