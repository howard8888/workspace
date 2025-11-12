# tests/test_world_attach_semantics.py
import cca8_world_graph as wg

def _first_out(world, src):
    b = world._bindings[src]; edges = getattr(b, "edges", []) or []
    return edges[0]["to"] if edges else None, edges[0].get("label","then") if edges else None

def test_attach_now_and_latest():
    w = wg.WorldGraph()
    now = w.ensure_anchor("NOW")

    a = w.add_predicate("pred:test:A", attach="now")     # NOW -> a
    dst, lab = _first_out(w, now)
    assert dst == a and lab == "then"
    assert w._latest_binding_id == a

    b = w.add_predicate("pred:test:B", attach="latest")  # a -> b
    dst2, lab2 = _first_out(w, a)
    assert dst2 == b and lab2 == "then"
    assert w._latest_binding_id == b
