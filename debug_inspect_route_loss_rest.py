"""
used for debug purposes of cca8 code
can be customized again
previously used for route_loss program
tracing
""""


from pathlib import Path
import json

path = Path(r"testvalues\20260606_225011__newborn_long_horizon__--no_run_label_chosen--__cycle.jsonl")

rows = []
with path.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

print(f"loaded records: {len(rows)}")
print(f"path: {path}")
print()

for rec in rows:
    step = rec.get("env_step")
    if not isinstance(step, int) or step < 44:
        continue

    dbg = rec.get("policy_debug") or {}
    state = dbg.get("state") if isinstance(dbg, dict) else {}
    state = state if isinstance(state, dict) else {}

    print("-" * 100)
    print(
        f"step={step} stage={rec.get('stage')} zone={rec.get('zone')} "
        f"posture={rec.get('posture')} mom={rec.get('mom_distance')} nipple={rec.get('nipple_state')} "
        f"policy={rec.get('selected_policy')} action={rec.get('executed_action')} milestones={rec.get('milestones')}"
    )
    print(
        f"debug.stage={dbg.get('stage')} post_latch={dbg.get('post_latch_sequence')} "
        f"chosen={dbg.get('chosen')}"
    )
    print(f"debug.state={state}")
    print(f"matches_initial={dbg.get('matches_initial')}")
    print(f"matches_after_post_latch={dbg.get('matches_after_post_latch')}")
    print(f"matches_before_choice={dbg.get('matches_before_choice')}")