# tests/test_runner_sorted_bids_numeric.py
import cca8_world_graph as wg
from cca8_run import _sorted_bids

def test_sorted_bids_numeric_then_alpha():
    w = wg.WorldGraph()
    now = w.ensure_anchor("NOW")     # 'b1'
    a = w.add_predicate("pred:A", attach="now")      # 'b2'
    b = w.add_predicate("pred:B", attach="latest")   # 'b3'
    # World keys are b1,b2,b3,…; verify numeric sort (regardless of insertion)
    ids = _sorted_bids(w)
    assert ids[:3] == ["b1", "b2", "b3"]
