import random
import importlib

import cca8_world_graph as wgmod
from cca8_temporal import TemporalContext
from cca8_features import TensorPayload, FactMeta, time_attrs_from_ctx
import cca8_run as runmod

def test_engram_carries_runner_time_attrs():
    random.seed(123)
    world = wgmod.WorldGraph()

    # minimal ctx with soft clock
    ctx = runmod.Ctx()
    ctx.temporal = TemporalContext(dim=32, sigma=0.015, jump=0.20)
    ctx.tvec_last_boundary = ctx.temporal.vector()  # seed
    # Optionally drift once to make the hash less trivial
    ctx.temporal.step()

    # build payload + attrs from ctx
    vec = [0.1, 0.2, 0.3]
    payload = TensorPayload(data=vec, shape=(len(vec),))
    attrs = time_attrs_from_ctx(ctx)

    # use the world bridge (pred or cue—either is fine)
    bid, eid = world.capture_scene("vision", "silhouette:mom", vec, attach="now", family="cue", attrs=attrs)
    rec = world.get_engram(engram_id=eid)

    assert "meta" in rec and isinstance(rec["meta"], dict)
    meta = rec["meta"]
    # attrs are nested inside FactMeta.as_dict()
    mattrs = meta.get("attrs", {})
    assert mattrs.get("ticks") == getattr(ctx, "ticks", 0)
    assert mattrs.get("tvec64") == ctx.tvec64()
