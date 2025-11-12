# tests/test_policy_dev_gate.py
from cca8_run import Ctx, PolicyRuntime, CATALOG_GATES

def test_stand_up_unloaded_after_day3():
    ctx = Ctx(age_days=4.0)
    rt = PolicyRuntime(CATALOG_GATES)
    rt.refresh_loaded(ctx)
    assert "policy:stand_up" not in rt.list_loaded_names()
