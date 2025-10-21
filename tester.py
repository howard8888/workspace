import cca8_world_graph as W
w = W.WorldGraph(); w.ensure_anchor("NOW")
print(w.check_invariants(raise_on_error=False))
