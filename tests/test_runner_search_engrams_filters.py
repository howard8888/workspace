# tests/test_runner_search_engrams_filters.py
import cca8_world_graph as wg
from cca8_features import time_attrs_from_ctx
from cca8_run import Ctx, _engrams_on_binding

def _capture(w, ctx, name_tok, epoch_bump=False):
    if epoch_bump and ctx.temporal:
        new_v = ctx.temporal.boundary()
        ctx.tvec_last_boundary = list(new_v)
        ctx.boundary_no += 1
        ctx.boundary_vhash64 = ctx.tvec64()
    attrs = time_attrs_from_ctx(ctx)
    bid, eid = w.capture_scene("vision", name_tok, [0.0,0.0,0.0], attach="now", family="cue", attrs=attrs)
    return bid, eid

def test_search_like_filters_locally():
    w = wg.WorldGraph(); w.ensure_anchor("NOW")
    ctx = Ctx(); from cca8_temporal import TemporalContext
    ctx.temporal = TemporalContext(dim=8, sigma=0.01, jump=0.2)
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.boundary_vhash64 = ctx.tvec64()

    b1, e1 = _capture(w, ctx, "silhouette:mom", epoch_bump=True)   # epoch 1
    b2, e2 = _capture(w, ctx, "silhouette:tree", epoch_bump=True)  # epoch 2

    # emulate the runner’s scan+filters:
    seen, matches = set(), []
    for bid, b in w._bindings.items():
        eng = getattr(b, "engrams", None)
        if isinstance(eng, dict):
            for v in eng.values():
                eid = v.get("id") if isinstance(v, dict) else None
                if isinstance(eid, str) and eid not in seen:
                    seen.add(eid)
                    rec = w.get_engram(engram_id=eid)
                    name = rec.get("name", "")
                    attrs = rec.get("meta", {}).get("attrs", {})
                    # filters: substring, epoch exact, kind=scene, eid prefix
                    if "silhouette" in name and attrs.get("epoch") in {1,2}:
                        pl = rec.get("payload")
                        kind = getattr(pl, "meta", lambda: {})().get("kind") if hasattr(pl,"meta") \
                               else (pl.get("kind") if isinstance(pl, dict) else None)
                        if kind == "scene" and eid.startswith(eid[:2]):  # trivial prefix sanity
                            matches.append((eid, bid, name, attrs.get("epoch")))
    assert set(m[0] for m in matches) == {e1, e2}
