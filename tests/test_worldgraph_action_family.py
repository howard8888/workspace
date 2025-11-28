import cca8_world_graph as wgmod


def _edges_from(world, bid: str):
    """Helper: return list of dst ids from binding.bid's outgoing edges."""
    b = world._bindings.get(bid)
    if not b:
        return []
    edges = (
        getattr(b, "edges", []) or
        getattr(b, "out", []) or
        getattr(b, "links", []) or
        getattr(b, "outgoing", [])
    )
    out = []
    if isinstance(edges, list):
        for e in edges:
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if dst:
                out.append(dst)
    return out


def test_add_action_creates_action_tag_only():
    """WorldGraph.add_action should create a binding tagged only with action:*, not pred:action:*.
    """
    w = wgmod.WorldGraph()
    w.set_tag_policy("allow")
    w.ensure_anchor("NOW")

    bid = w.add_action("action:push_up", attach="none")
    b = w._bindings[bid]
    tags = getattr(b, "tags", set()) or set()

    # canonical action tag present
    assert "action:push_up" in tags

    # no legacy pred:action:* tags
    assert not any(isinstance(t, str) and t.startswith("pred:action:") for t in tags)


def test_add_action_attach_now_and_latest():
    """attach='now' should create NOW→action, attach='latest' should chain from previous latest.
    """
    w = wgmod.WorldGraph()
    w.set_tag_policy("allow")
    now = w.ensure_anchor("NOW")

    # First action: attach="now" → NOW --then--> a
    a = w.add_action("push_up", attach="now")
    assert w._latest_binding_id == a

    out_from_now = _edges_from(w, now)
    assert a in out_from_now, "NOW should have an edge to first action when attach='now'"

    # Second action: attach="latest" → a --then--> b
    b = w.add_action("extend_legs", attach="latest")
    assert w._latest_binding_id == b

    out_from_a = _edges_from(w, a)
    assert b in out_from_a, "First action should have an edge to second action when attach='latest'"
