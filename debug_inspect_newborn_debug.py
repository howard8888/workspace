'''
utility program to find jsonl files
useful to help with debugging
needs to be customized for particular work
otherwise functional
'''


from pathlib import Path
import json

path = Path(r"testvalues\20260606_215437__newborn_long_horizon__--no_run_label_chosen--__cycle.jsonl")

interesting_policies = {"policy:follow_mom", "policy:suckle", "policy:rest", "policy:seek_nipple"}
interesting_stages = {"first_latch", "rest"}

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
    stage = rec.get("stage")
    policy = rec.get("selected_policy")
    action = rec.get("executed_action")
    dbg = rec.get("policy_debug") or {}

    if (
        isinstance(step, int)
        and step >= 20
        and (policy in interesting_policies or stage in interesting_stages)
    ):
        print("-" * 100)
        print(
            f"step={step} stage={stage} posture={rec.get('posture')} "
            f"mom={rec.get('mom_distance')} nipple={rec.get('nipple_state')} "
            f"zone={rec.get('zone')} policy={policy} action={action}"
        )

        if not dbg:
            print("policy_debug: MISSING")
            continue

        print(f"debug.step={dbg.get('step')} debug.stage={dbg.get('stage')}")
        print(f"debug.state={dbg.get('state')}")
        print(f"post_latch_sequence={dbg.get('post_latch_sequence')}")
        print(f"matches_initial={dbg.get('matches_initial')}")
        print(f"matches_after_post_latch={dbg.get('matches_after_post_latch')}")
        print(f"bridge_follow_mom={dbg.get('bridge_follow_mom')} forced_follow_mom={dbg.get('forced_follow_mom')}")
        print(f"matches_after_bridge={dbg.get('matches_after_bridge')}")
        print(f"suppress_follow_mom={dbg.get('suppress_follow_mom')}")
        print(f"matches_after_topology={dbg.get('matches_after_topology')}")
        print(f"fallen_safety_filter={dbg.get('fallen_safety_filter')}")
        print(f"matches_after_safety={dbg.get('matches_after_safety')}")
        print(f"matches_before_choice={dbg.get('matches_before_choice')}")
        print(f"chosen={dbg.get('chosen')}")