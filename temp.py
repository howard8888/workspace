
# --- WorldGraph and Engram Helpers ------------------------------------------------       
        
def _resolve_engrams_pretty(world, bid: str) -> None:
    b = world._bindings.get(bid)
    if not b:
        print("Unknown binding id.")
        return
    eng = getattr(b, "engrams", None)
    if not isinstance(eng, dict) or not eng:
        print("Engrams: (none)")
        return
    print("Engrams on", bid)
    for slot, val in sorted(eng.items()):
        eid = val.get("id") if isinstance(val, dict) else None
        ok = False
        try:
            rec = world.get_engram(engram_id=eid) if isinstance(eid, str) else None
            ok = bool(rec and isinstance(rec, dict) and rec.get("id") == eid)
        except Exception:
            ok = False
        status = "OK" if ok else "(dangling)"
        short = (eid[:8] + "…") if isinstance(eid, str) else "(id?)"
        print(f"  {slot}: {short}  {status}")