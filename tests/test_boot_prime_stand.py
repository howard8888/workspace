# tests/test_boot_prime_stand.py
import cca8_world_graph
from cca8_run import Ctx, boot_prime_stand

def test_boot_prime_seeds_stand_reachable_from_now():
    # Fresh world with NOW
    w = cca8_world_graph.WorldGraph()
    w.ensure_anchor("NOW")

    # Neonate context so the boot step is eligible
    ctx = Ctx()
    ctx.age_days = 0.0

    # Seed "stand" near NOW if needed
    boot_prime_stand(w, ctx)

    # There should be a (short) path from NOW to 'stand'
    src = w.ensure_anchor("NOW")
    path = w.plan_to_predicate(src, "stand")  # accepts "stand" or "pred:stand"
    assert path, "Expected a path from NOW to 'stand' after boot_prime_stand()"
    assert len(path) >= 1  # usually 1–2 hops depending on prior state
