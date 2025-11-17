# tests/test_runner_resolve_engrams_pretty.py
import io, sys
import cca8_world_graph as wg
from cca8_run import _resolve_engrams_pretty

def _cap(fn, *args, **kwargs):
    buf, old = io.StringIO(), sys.stdout
    try:
        sys.stdout = buf
        fn(*args, **kwargs)
        return buf.getvalue()
    finally:
        sys.stdout = old

def test_resolve_engrams_pretty_ok_and_dangling():
    w = wg.WorldGraph(); w.ensure_anchor("NOW")
    # OK pointer
    bid_ok, eid = w.capture_scene("vision", "silhouette:mom", [0.1,0.2,0.3], attach="now", family="cue")
    out_ok = _cap(_resolve_engrams_pretty, w, bid_ok)
    assert "Engrams on" in out_ok and "OK" in out_ok

    # Dangling pointer (fake id)
    bid = w.add_predicate("pred:X", attach="latest")
    b = w._bindings[bid]
    b.engrams = {"column09": {"id": "a"*32, "act": 1.0}}
    out_bad = _cap(_resolve_engrams_pretty, w, bid)
    assert "(dangling)" in out_bad
