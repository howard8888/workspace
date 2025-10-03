# # CCA8 (v0.7.x) — Project Compendium (Canonical README)

**Entry point:** `cca8_run.py`  
**Repo:** `github.com/howard8888/workspace`

**Quickstart:**

1) `py -3.11 -m venv .venv && .\.venv\Scripts\activate && python -V`
2) `python cca8_run.py --about`
3) `python cca8_run.py --autosave session.json`  (or `--load session.json`)

**CCA8 Python Modules:**`cca8_run.py, cca8_world_graph.py, cca8_column.py, cca8_controller.py, cca8_features.py, cca8_temporal.py` 

**Purpose of Program:** Simulation of the brain of a mountain goat through the lifecycle with hooks for robotic embodiment

**Newborn mountain goat demo (fast path):**  
Menu → `3` add `stand`; `4` connect NOW→stand (`stand_up`); then add and connect  
`mom:close` (`approach`) → `nipple:found` (`search`) → `nipple:latched` (`latch`) → `milk:drinking` (`suckle`);  
verify with `5` plan NOW → `milk:drinking`.  
**Glossary:** predicates, bindings, edges, policies, drives (hunger/warmth/fatigue), and search knobs (`k`, `sigma`, `jump`).







# CCA8 Compendium (All-in-One)

*A living document that captures the design, rationale, and practical know-how for the CCA8 simulation.*  
**Audience:** future software maintainers, new collaborators, persons with an interest in the project.  
**Tone:** mostly technical, with tutorial-style sections so it’s readable without “tribal knowledge.”



**Summary Overview:**

The CCA8 (Causal Cognitive Architecture version 8) is a cognitive architecture that simulates the mammalian brain based on the assumption that the declarative data is largely stored in spatial navigation maps. Simulations can be run virtually but there are hooks, i.e., an interface module, for it to control an actual robotic embodiment. The CCA8 is the simulation of the brain of a mountain goat through the lifecycle with hooks for robotic embodiment.







<img title="" src="3day_old_mountain_goat.jpg" alt="3-day-old mountain goat" style="zoom:200%;">

**AI-rendered video of robotic embodiment + CCA8 :** [Robotic mountain goat (Sora)](https://sora.chatgpt.com/g/gen_01k6jsgnqcfnm83vprbxb1jq73)
Note: If viewer won't open the video link, then copy this URL:  https://sora.chatgpt.com/g/gen_01k6jsgnqcfnm83vprbxb1jq73

****Planned versions: ****

CCA8 Simulation of a mountain goat through the lifecycle

CCA9 Simulation of a chimpanzee through the lifecycle

CCA10 Simulation of a human through the lifecycle

---

## Table of Contents

1. [Executive Overview](#executive-overview)  
2. [Theory Primer](#theory-primer)  
3. [Architecture](#architecture)  
4. [Key Data Structures (Schemas)](#key-data-structures-schemas)  
5. [Action Selection: Drives, Policies, Action Center](#action-selection-drives-policies-action-center)  
6. [Planner Contract](#planner-contract)  
7. [Persistence: Autosave/Load](#persistence-autosaveload)  
8. [Tutorial: Newborn Mountain Goat — First Minutes](#tutorial-newborn-mountain-goat--first-minutes)  
9. [How-To Guides](#howto-guides)  
10. [Traceability-Lite (Requirements ↔ Code)](#traceabilitylite-requirements--code)  
11. [Architecture Decision Records (ADRs)](#architecture-decision-records-adrs)  
12. [Debugging Tips (traceback, pdb, VS Code)](#debugging-tips-traceback-pdb-vs-code)  
13. [FAQ / Pitfalls](#faq--pitfalls)  
14. [Glossary](#glossary)

---

## Executive Overview

CCA8 aims to simulate early mammalian cognition with a **small symbolic episode index** (the *WorldGraph*) coordinating **rich engrams** (perceptual/temporal content) in a column provider. Symbols are used for **fast indexing & planning**, not as a full knowledge store.

**Core mental model:**

- **Predicate** — a symbolic fact token (e.g., `state:posture_standing`). Atomic.  
- **Binding** — a node instance that *carries* one or more tags, including `pred:<token>`, plus `meta` and optional `engrams`.  
- **Edge** — a directed link between bindings with a label (often `"then"`) representing **weak, episode-level causality** (“in this run, this led to that”).  
- **WorldGraph** — the directed graph composed of these bindings and edges; supports **BFS planning**.  
- **Policy (primitive)** — an instinctive behavior with `trigger()` + `execute()`. The **Action Center** scans policies in order and runs the first whose trigger matches current **drive** tags (hunger/fatigue/warmth).  
- **Provenance** — when a policy creates a new binding, its name is stamped into `binding.meta["policy"]`.  
- **Autosave/Load** — a JSON snapshot persists (world, drives, skills) with `saved_at`, written via atomic replace.
  
  
  
  

Newborn Mountain Goat: stand → mom → nipple → drink (5-step demo)
=================================================================

This minimal demo creates a linear episode chain and verifies that planning finds it.

1) Start or resume

------------------

`python cca8_run.py --autosave session.json`

Pick **Profile 1: Mountain Goat** when prompted.

2) Note IDs you’ll need

-----------------------

* **World stats** (menu `1`) → find the **NOW** anchor’s binding ID (e.g., `b0`).

* **Show last 5 bindings** (menu `7`) anytime to grab the newest IDs you create.
3) (Optional) Prime drives and cues

-----------------------------------

* `14` Autonomic tick once or twice; then `D` Show drives (aim for `drive:hunger_high`).

* `11` Add sensory cue a few times:
  
  * `vision` → `silhouette:mom`
  
  * `smell` → `milk:scent`
  
  * `sound` → `bleat:mom`
4) Create milestones (add predicates), then wire edges

------------------------------------------------------

**A. Stand first**

1. `3` Add predicate → `stand` → note ID, e.g., `b2`.

2. `4` Connect two bindings:
   
   * Source: `<NOW_id>` (e.g., `b0`)
   
   * Destination: `<stand_id>` (e.g., `b2`)
   
   * Relation: `stand_up`

**B. Approach mom**

1. `3` Add predicate → `mom:close` → note ID, e.g., `b3`.

2. `4` Connect:
   
   * Source: `<stand_id>` (e.g., `b2`)
   
   * Destination: `<mom_id>` (e.g., `b3`)
   
   * Relation: `approach`

**C. Find nipple**

1. `3` Add predicate → `nipple:found` → ID `b4`.

2. `4` Connect `b3 → b4` with relation `search`.

**D. Latch**

1. `3` Add predicate → `nipple:latched` → ID `b5`.

2. `4` Connect `b4 → b5` with relation `latch`.

**E. Drink**

1. `3` Add predicate → `milk:drinking` → ID `b6`.

2. `4` Connect `b5 → b6` with relation `suckle`.

_(Tip: use `7` Show last 5 bindings as you go to copy the exact IDs.)_

5) Verify with planning

-----------------------

* `5` Plan from NOW → `<predicate>`

* Target: `milk:drinking`

* Expect a path like: NOW (b0) → stand (b2) → mom:close (b3) → nipple:found (b4) → nipple:latched (b5) → milk:drinking (b6)
6) (Optional) Inspect memory

----------------------------

* `7` Show last 5 bindings → copy the ID for `nipple:latched`.

* `6` Resolve engrams on a binding → paste that ID to see its engram/meta.
7) Save/Load

------------

* You started with `--autosave session.json`.

* You can also press `S` to save or relaunch later with `--load session.json`.

* 

Executive Overview — Mini-tutorial (Q&A)

Q: Why keep the symbolic graph small? A: For fast indexing/planning; heavy content lives in engrams.

Q: Which primitives form “standing”? A: action:push_up, action:extend_legs, state:posture_standing.

Q: Where is provenance stored? A: binding.meta.policy = "policy:<name>".
Q: What’s the planner algorithm? A: BFS from NOW to the first pred:<token> match.









---

## Theory Primer

- **Weak causality:** Mammalian episodes often encode **soft** chains (“this happened, then that”), sufficient for immediate action without formal causal inference. In CCA8, edges labeled `"then"` capture this episode flow.
- **Two-store economy:** Keep the **symbolic graph small** (~5%): tags & edges for **recall and planning**. Keep the **heavy content** (~95%) in engrams (features, traces, sensory payloads). This avoids the brittleness of “all knowledge in a graph.”
- **From pre-causal to causal:** The symbolic skeleton is compatible with later, stronger causal reasoning layered above (e.g., annotating edges with conditions, failure modes, or learned utilities).

Theory Primer — Mini-tutorial (Q&A)

Q: Define “weak causality.” A: Soft episode links (“then”) without asserting logical necessity.

Q: Why engrams vs symbols? A: Symbols = fast index; engrams = heavy content → avoids brittle all-graph designs.

Q: Can we add stronger causal reasoning later? A: Yes, layered above (edge annotations, utilities).

---

## Architecture

### Modules (lean overview)

- **`cca8_world_graph.py`** — Directed episode graph (bindings, edges, anchors), plus a BFS planner. Serialization via `to_dict()` / `from_dict()`.
- **`cca8_controller.py`** — Drives (hunger, fatigue, warmth), primitive policies (e.g., `StandUp`), Action Center loop, and a small skill ledger (n, succ, q, last_reward).
- **`cca8_run.py`** — CLI & interactive runner: banner/profile, menu actions (inspect, plan, add predicate, instincts), autosave/load, `--plan` flag, `[D] Show drives`.
- **`cca8_column.py`** — Engram provider (stubs now): bindings may reference column content via small pointers.
- **`cca8_features.py`** — Feature helpers for engrams (schemas/utilities).
- **`cca8_temporal.py`** — Timestamps and simple period/year tagging (used in binding meta).

Architecture — Mini-tutorial (Q&A)

Q: Which module stores nodes/edges? A: cca8_world_graph.py.

Q: Which runs instincts? A: cca8_controller.py (policies + Action Center).

Q: Which shows the menu & autosave/load? A: cca8_run.py.

Q: Where do engrams live? A: cca8_column.py, referenced by bindings’ engrams.



### Data flow (a tick)

1. Action Center computes active **drive tags**.  
2. Scans **policies** in order; first `trigger()` that returns True **fires**.  
3. `execute()` appends a **small chain** of predicates + edges to the WorldGraph, stamps `meta.policy`, returns a status dict, and updates the skill ledger.  
4. Planner (on demand) runs BFS from **NOW** to a target `pred:<token>`.  

---

## Key Data Structures (Schemas)

### Binding (node)

```jsonc
{
  "id": "b152",
  "tags": ["pred:state:posture_standing", "anchor:NOW? (for anchors)"],
  "edges": [{"to": "b153", "label": "then", "meta": {}}],
  "meta": {"policy": "policy:stand_up", "created_at": "2025-09-28T11:17:00"},
  "engrams": {}
}
```

- `pred:<token>` is **atomic** (don’t split `state`/`posture_standing` into separate nodes in this design).
- `meta.policy` records **provenance** (which policy created this binding).

### Edge

```jsonc
{"to": "b153", "label": "then", "meta": {}}
```

- Directed; label often `"then"`. Represents **episode-level** causation (not logical necessity).

### Drives (controller)

```jsonc
{"hunger": 0.7, "fatigue": 0.2, "warmth": 0.6}
```

- Derived tags (typical thresholds):  
  - `hunger > 0.6` → `drive:hunger_high`  
  - `fatigue > 0.7` → `drive:fatigue_high`  
  - `warmth < 0.3` → `drive:cold`

### Skill ledger (per policy; scaffolding for RL)

```jsonc
"policy:stand_up": {"n": 3, "succ": 3, "q": 0.58, "last_reward": 1.0}
```

Key Data Structures (Schemas) — Mini-tutorial (Q&A)

Q: What’s inside a Binding? A: id, tags, edges[], meta, engrams.

Q: How are edges stored? A: On the source binding as {"to", "label", "meta"}.

Q: One drive:* tag example? A: drive:hunger_high (hunger > 0.6).

Q: A skill stat besides n? A: succ, q, or last_reward.

---

## Action Selection: Drives, Policies, Action Center

- **Policies** are small classes with:
  - `trigger(world, drives) -> bool`  
  - `execute(world, ctx, drives) -> {"policy", "status", "reward", "notes"}`
- **Ordered list** `PRIMITIVES = [StandUp(), SeekNipple(), FollowMom(), ExploreCheck(), Rest(), ...]`.  
- **Action Center** runs the **first** policy whose `trigger` is True.  
- **StandUp guard:** `StandUp.trigger()` checks for an existing `pred:state:posture_standing` to avoid “re-standing” every tick.

**Status dict convention:**  
`{"policy": "policy:<name>" | None, "status": "ok|fail|noop|error", "reward": float, "notes": str}`

Action Selection: Drives, Policies, Action Center — Mini-tutorial (Q&A)

Q: Two methods every policy must have? A: trigger, execute.

Q: What prevents “re-standing”? A: Guard in StandUp.trigger() that checks for pred:state:posture_standing.

Q: What does a policy return? A: A status dict (policy, status, reward, notes).

Q: What does the skill ledger track? A: Counts, success rate, running q, last reward.

---

## Planner Contract

- **Goal:** Find a path from anchor **NOW** to the **first** binding carrying `pred:<token>`.
- **Algorithm:** **BFS** (O(|V|+|E|)) over edges.  
- **Returns:** List of binding ids (`["b1", "b9", "b12", ...]`) or `None` if not found.
- **When paths don’t exist:** Either you haven’t created the predicate yet (e.g., no instinct tick) or it’s disconnected.

Planner Contract — Mini-tutorial (Q&A)

Q: Where does planning start? A: Anchor NOW.

Q: How is the goal detected? A: First binding whose tags contain pred:<token>.

Q: Complexity? A: O(|V|+|E|) BFS.
Q: Why might a path be missing? A: Predicate not created yet or the graph is disconnected.

---

## Persistence: Autosave/Load

- Snapshot file (JSON) includes:
  
  ```jsonc
  {"saved_at": "...", "world": {...}, "drives": {...}, "skills": {...}}
  ```

- **Autosave:** `--autosave session.json` writes after each completed action (atomic replace). Overwrites prior file if same name.

- **Load:** `--load session.json` restores world/drives/skills; id counter advances to avoid `bNN` collisions.

- **Fresh start:** Use a new filename, delete/rename old file, or load a non-existent file (runner continues with a fresh session and starts saving after first action).

Persistence: Autosave/Load — Mini-tutorial (Q&A)

Q: What does autosave write? A: {saved_at, world, drives, skills}.

Q: How do we avoid id collisions after load? A: from_dict() advances the internal bNN counter.

Q: Missing --load file? A: Continue fresh; file created on first autosave.
Q: Why atomic replace on save? A: Prevents partial/corrupt snapshots.

---

## Tutorial: Newborn Mountain Goat — First Minutes

> Goal: watch bindings/edges form as the neonate stands.

1. **Start fresh**  
   
   ```bash
   cca8_run.py --autosave session.json
   ```
   
   Choose **1 = Mountain Goat**.

2. **Run one instinct tick**  
   Menu → **12**  
   Output: `{'policy': 'policy:stand_up', 'status': 'ok', 'reward': 1.0, 'notes': 'standing'}`  
   Internals: creates a mini chain:  
   `action:push_up → action:extend_legs → state:posture_standing`

3. **Inspect the newest bindings**  
   Menu → **7** (Show last 5 bindings). Note the id of the standing node.

4. **Inspect details**  
   Menu → **10** → paste the standing binding id. See `tags` (with `pred:state:posture_standing`) and `meta.policy = "policy:stand_up"`.

5. **Plan**  
   Menu → **5** → enter `state:posture_standing`. You should see a short path from `NOW` to the standing binding.

6. **(Later) Resume and one-shot plan**  
   
   ```bash
   cca8_run.py --load session.json --plan state:posture_standing
   ```

Tutorial: Newborn Mountain Goat — Mini-tutorial (Q&A)

Q: Which menu option creates “standing”? A: 12 Instinct step.

Q: How do you view provenance? A: 10 Inspect the binding → meta.policy.

Q: How to list recent nodes? A: 7 Show last 5 bindings.
Q: How to verify a path exists? A: 5 Plan from NOW to state:posture_standing.

---

## How-To Guides

### Resume + keep autosaving

```
cca8_run.py --load session.json --autosave session.json
```

### Start fresh but keep old snapshot

```
cca8_run.py --load session.json --autosave session_NEXT.json
```

### One-shot planning (no menu)

```
cca8_run.py --load session.json --plan state:posture_standing
```

### Add a sensory cue

Menu → **11** → channel `vision`, cue `mom:close` → creates `pred:vision:mom:close` (depending on your input normalization).

### Show drives (raw + tags)

Menu → **D** → prints numeric drives and active `drive:*` tags (robust even if `Drives.predicates()` isn’t available).

How-To Guides — Mini-tutorial (Q&A)

Q: Resume + autosave same file? A: --load session.json --autosave session.json.

Q: Start fresh but keep old? A: Autosave to a new filename.

Q: One-shot planning? A: --load session.json --plan state:posture_standing.

Q: Reset? A: Press R (with autosave set).

---

## Traceability-Lite (Requirements ↔ Code)

| ID           | Requirement (short)                                                 | Rationale / ADR | Code anchor(s)                                                       |
| ------------ | ------------------------------------------------------------------- | --------------- | -------------------------------------------------------------------- |
| REQ-PRED-01  | Predicates are **atomic** tokens.                                   | ADR-0001        | `WorldGraph.add_predicate`, planner target matching (`pred:<token>`) |
| REQ-BIND-02  | Each predicate lives in a **Binding** with `meta` and `engrams`.    | ADR-0001        | `Binding` dataclass (`cca8_world_graph.py`)                          |
| REQ-EDGE-03  | Edges express **episode** causality (`"then"`).                     | ADR-0001        | `WorldGraph.add_edge`, planner BFS                                   |
| REQ-PLAN-04  | Planner is **BFS** from `NOW` to first match.                       | ADR-0001        | `WorldGraph.plan_to_predicate`                                       |
| REQ-DRV-05   | Drives derive `drive:*` tags from thresholds.                       | ADR-0002        | `Drives.predicates()` (or runner fallback `_drive_tags`)             |
| REQ-POL-06   | Policies are ordered; Action Center runs **first match**.           | ADR-0002        | `PRIMITIVES`, `action_center_step`                                   |
| REQ-PROV-07  | New bindings made by a policy **stamp provenance** (`meta.policy`). | ADR-0002        | Each policy `execute()` (e.g., `StandUp`)                            |
| REQ-GUARD-08 | `StandUp` **won’t refire** if already standing.                     | ADR-0002        | `StandUp.trigger()` guard                                            |
| REQ-PERS-09  | Snapshot includes `world`, `drives`, `skills`, **atomic replace**.  | ADR-0003        | `save_session`, `WorldGraph.to_dict/from_dict`, `skills_*`           |
| REQ-LOAD-10  | `from_dict` **advances id counter** to avoid `bNN` collisions.      | ADR-0003        | `WorldGraph.from_dict`                                               |
| REQ-RUN-11   | Runner offers **one-shot planning** via `--plan`.                   | ADR-0004        | `interactive_loop` (plan quick-exit)                                 |
| REQ-UX-12    | Runner exposes **[D] Show drives**.                                 | ADR-0004        | Menu & branch in `cca8_run.py`                                       |

> **Note:** Tag these IDs in code comments where relevant (e.g., `# REQ-PLAN-04`).

Traceability-Lite — Mini-tutorial (Q&A)

Q: What does REQ-PRED-01 assert? A: Predicates are atomic tokens.

Q: Which REQ maps to --plan? A: REQ-RUN-11.

Q: Which REQ captures Reset? A: REQ-RESET-13.
Q: Where do you tag code with REQ IDs? A: Comments/docstrings near relevant functions.

---

## Architecture Decision Records (ADRs)

### ADR-0001 — Episode Graph & Weak Causality *(Accepted — 2025-09-28)*

**Context:** We want fast recall/planning without forcing all knowledge into a brittle graph.  
**Decision:** Use a **small WorldGraph** with **bindings** (carrying `pred:<token>`) and **edges** labeled `"then"`. Planner uses BFS from `NOW` to target `pred:<token>`.  
**Alternatives:** Logic network with heavy axioms; full causal graphs for everything.  
**Consequences:** Fast and explainable. True causal reasoning can be layered later.

### ADR-0002 — Drives & Policies (Action Center) *(Accepted — 2025-09-28)*

**Context:** Newborn behavior unfolds as short, triggered routines.  
**Decision:** Policies with `trigger` + `execute`, scanned in fixed order; `meta.policy` records provenance. Added guard so `StandUp` won’t re-fire once standing exists.  
**Alternatives:** Rule engine; global planner-first.  
**Consequences:** Simple to reason about; requires small guards to avoid repeats.

### ADR-0003 — Persistence via JSON Snapshots *(Accepted — 2025-09-28)*

**Decision:** Autosave/load single JSON snapshot with atomic replace. Rehydrate with `from_dict()`, **advance id counter** to avoid collisions.  
**Alternatives:** DB/WAL — defer until scale requires.  
**Consequences:** Human-inspectable, easy to back up/branch.

### ADR-0004 — Runner UX: `--plan` & `[D] Show drives` *(Accepted — 2025-09-28)*

**Decision:** Add quick scripts UX (`--plan`) and diagnostic UX (`[D]`) to accelerate iteration.  
**Consequences:** Easier CI/testing hooks and field debugging.

ADRs — Mini-tutorial (Q&A)

Q: Why ADR-0001 vs full causal graphs? A: Speed + simplicity; causal layers can be added later.

Q: What did ADR-0007 change? A: attach strictly "now"|"latest"|"none" (lowercase).

Q: ADR-0008’s benefit? A: Robustness when Drives.predicates() is absent.

Q: Which ADR introduced Reset? A: ADR-0005.

---

## Debugging Tips (traceback, pdb, VS Code)

- **traceback:** In `except Exception:` add `traceback.print_exc()` to print a full stack. Use when a loader/snapshot fails.  
- **pdb:** Drop `breakpoint()` in code or run `python -m pdb cca8_run.py --load ...`. Commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p`/`pp` (print), `b` (breakpoint), `where`.  
- **VS Code debugger:** Create `.vscode/launch.json` with args, set breakpoints in the gutter, F5 to start. Great for multi-file stepping.

Debugging Tips — Mini-tutorial (Q&A)

Q: Quick way to print a stack? A: traceback.print_exc() in except.

Q: Start debugger from CLI? A: python -m pdb cca8_run.py --load ....

Q: Persistent breakpoint in code? A: breakpoint() (Python 3.7+).

Q: IDE workflow? A: VS Code launch config + gutter breakpoints.

---

## FAQ / Pitfalls

- **“No path found to state:posture_standing”** — You planned before creating the state. Run one instinct tick (menu **12**) first or `--load` a session that already has it.
- **Repeated “standing” nodes** — Tightened `StandUp.trigger()` prevents refiring when a standing binding exists. If you see repeats, ensure you’re on the updated controller.
- **Autosave overwrote my old run** — Use a new filename for autosave (e.g., `--autosave session_YYYYMMDD.json`) or keep read-only load + new autosave path.
- **Loading says file not found** — We continue with a fresh session; the file will be created on your first autosave event.

FAQ / Pitfalls — Mini-tutorial (Q&A)

Q: Why “No path found …” on a new session? A: You planned before adding the predicate; run one instinct tick.

Q: Why duplicate “standing” nodes? A: Old controller; update to guarded StandUp.trigger().

Q: How to keep an old snapshot? A: Autosave to a new filename.
Q: Is load failure fatal? A: No; runner continues with a fresh session.

---

## Glossary

- **Predicate** — symbolic fact token (atomic).  
- **Binding** — node that carries predicate tag(s) and holds meta/engrams/edges.  
- **Edge** — directed relation labeled `"then"`, encoding episode flow.  
- **WorldGraph** — the episode index graph.  
- **Policy** — primitive behavior with `trigger` + `execute`.  
- **Action Center** — ordered scan of policies; runs first match per tick.  
- **Drives** — homeostatic variables (hunger/fatigue/warmth) that generate drive tags for triggers.  
- **Engram** — pointer to heavy content (features/sensory/temporal traces) stored outside the graph.  
- **Provenance** — `meta.policy` stamp recording which policy created a binding.
  
  

**Predicate (tag)**  
Namespaced symbolic token (string) carried by a binding, e.g., `pred:stand`, `pred:mom:close`, `pred:milk:drinking`. A binding can carry multiple predicates.

**Binding (node / episode)**  
A time-slice container that holds: predicate tags, lightweight `meta`, and **pointers** to rich engrams (not the engrams themselves).

**Edge (directed link)**  
A directed connection `src → dst` with optional relation label (e.g., `approach`, `search`, `latch`, `suckle`). Think temporal/causal adjacency.

**Anchors**  
Special bindings (e.g., `NOW`). Use **World stats** to find the actual binding ID (e.g., `NOW=b0`).

**WorldGraph**  
Holds bindings + edges and fast tag→binding indexes for planning and lookup (~the compact symbolic 5%).

**Engram (rich memory)**  
Large payloads stored outside the graph and referenced by pointers from bindings (~the rich 95%). Resolved via the column provider.

**Column provider**  
`cca8_column.py` resolves binding→engrams and manages simple engram CRUD for demos.

**Policy**  
Trigger (conditions on predicates/drives/sensory cues) + primitive (callable). Lives in code (`cca8_controller.py`), not in the graph.

**Drives**  
Scalar homeostatic variables (0–1): `hunger`, `warmth`, `fatigue`. When crossing thresholds, the runner emits drive tags like `drive:hunger_high`.

**Search knobs**

* `k`: branch cap during expansion (smaller = decisive, larger = broader).

* `sigma`: small Gaussian jitter to break ties/avoid stagnation.

* `jump`: ε-exploration probability to occasionally take a random plausible move.

**Cues & ticks**

* **Sensory cue** adds transient evidence (vision/smell/sound/touch).

* **Autonomic tick** updates drives (e.g., hunger rises) and can emit drive tags.

**Instinct step**  
One step chosen by the controller using policies + drives + cues. You can accept/reject proposals.

**Planning**  
BFS-style search from the `NOW` anchor to any binding carrying a target predicate (`pred:<name>`), traversing directed edges.



Glossary — Mini-tutorial (Q&A)

Q: Binding vs Predicate? A: Binding = node container; Predicate = symbolic fact carried by the binding.

Q: Edge label semantics today? A: "then" = weak episode causality.

Q: Engram? A: Pointer to heavy content (outside the graph).

Q: Provenance? A: meta.policy records which policy created the node.

---

*End of compendium. Keep this single file updated. If size ever becomes unwieldy, we can split into a `docs/` tree while preserving the same section structure.*

## Session Notes (Living Log)

### 2025-09-28 (America/Toronto)

- **Autosave/Load best practices**  
  
  - Fresh run + autosave overwrites any existing file with the same name *after the first action* completes.  
    Use a new filename (e.g., `--autosave session_2025-09-28.json`) if you want to preserve older snapshots.  
  - To resume and keep autosaving to the same file: `--load session.json --autosave session.json`.  
  - To resume but checkpoint to a new file: `--load session.json --autosave session_NEXT.json`.  
  - A missing `--load` file isn’t fatal; the runner starts fresh and will create it on the first autosave.

- **One‑shot planning (`--plan`)**  
  
  - Runs **before** any instincts. In a brand‑new session, the goal predicate likely doesn’t exist yet, so you may see *“No path found”*.  
    Create it first (e.g., one Instinct step) or load a saved session that has it, then `--plan state:posture_standing` will print the path and exit.

- **Runner UX additions**  
  
  - `[D] Show drives (raw + tags)` prints `hunger/fatigue/warmth` and active `drive:*` tags.  
  - The runner computes drive tags even if `Drives.predicates()` isn’t available (robust fallback).

- **Controller behavior**  
  
  - `StandUp.trigger()` now guards against refiring if a binding carrying `pred:state:posture_standing` already exists.  
  - Policy executions stamp provenance into `binding.meta.policy` for traceability.

- **Docs strategy**  
  
  - Code docstrings stay **tight** (contracts + invariants).  
  - This compendium holds the *why*, tutorials, ADRs, and traceability‑lite.
    
    

## Tiny Command Vocabulary

Say these during a chat and I will update this compendium accordingly:

- **“log this …”** → Append a dated entry under *Session Notes* summarizing the decision/insight.  
- **“new ADR: <title> …”** → Create a new ADR block (ID, status, context, decision, consequences) and link it in Traceability‑Lite.  
- **“update ADR-0002 …”** → Amend the specified ADR with new nuance and update cross‑links.  
- **“add REQ: <short requirement> …”** → Add a row to the Traceability‑Lite table with a new REQ ID and suggested code anchors to tag.  
- **“promote note to ADR …”** → Convert a *Session Note* item into a formal ADR entry.
  
  

## Work in Progress

--

--

---

# Updates in v0.7.9 — Policies, `ctx`, and Menu Reference (2025-10-03)

## Two‑Gate Policies (Availability vs. Execution)

CCA8 now treats policies with **two gates**:

- **Developmental availability (load gate):** a policy exists in code but is only **loaded** when developmental criteria in `ctx` are met (e.g., age/profile/milestones). The **World stats** menu shows how many policies are currently **loaded** (available).  
- **Execution (fire gate):** whenever an **event** occurs (e.g., you add a **sensory cue** with menu **11** or run an **autonomic tick** with menu **14**), all *loaded* policies are considered. For now we use a simple **first‑match** rule (ties can become scoring later). If a policy fires, its primitive writes bindings/edges and stamps provenance in `binding.meta.policy`.

**Where you can see it:**

- **World stats (1):** `Policies loaded: …`  
- **Export snapshot (16):** `POLICY_GATES_LOADED` plus the skill readout under `POLICIES:`  
- **Console prints:** after events, you’ll see `Policy executed: policy:<name> -> {...status...}`

**Examples of gates in the default catalog** (intent only—actual triggers live in code):
- `policy:stand_up` — available from birth; executes when `pred:stand` is reachable near NOW.  
- `policy:seek_mom` — available from birth; executes when hunger is high and relevant cues exist (e.g., `vision:silhouette:mom`, `smell:milk:scent`, `sound:bleat:mom`).  
- `policy:suckle` — available from birth; executes when `pred:mom:close` is near NOW.  
- `policy:recover_miss` — available from birth; executes when `pred:nipple:missed` is near NOW.

> **Provenance:** Any binding written by a policy records `meta.policy = "policy:<name>"` so you can trace who created it.

## `ctx` (Context) — What it is and how it evolves

`ctx` holds lightweight, session‑level context used by policy gates and planning knobs. Current fields include:

- `sigma`, `jump`, and `k` (from profile selection)  
- `age_days` (float) and `ticks` (int) — **incremented on menu 14** (autonomic tick)  
- (optionally) `profile` name

**Where to see it:** export with menu **16**; the TXT includes a **CTX** section showing these values. `age_days`/`ticks` advance each time you run **14**.

> We keep `ctx` intentionally small; richer context belongs in bindings’ `meta`/engrams.

## Menu Reference (v0.7.9)

**1) World stats** — counts + `NOW=<id>`, latest binding id, **Policies loaded** list.  
**2) List predicates** — `pred:token -> bIDs` mapping for quick paper copies.  
**3) Add predicate** — creates `pred:<token>` on a new binding, **attaching to `latest`** by default (adds a `then` edge). Relabel edges with **15+4** if you want semantic labels.  
**4) Connect two bindings** — `src -> dst` with a relation label (e.g., `approach`, `search`, `latch`, `suckle`).  
**5) Plan from NOW → <predicate>** — BFS to the first binding carrying `pred:<token>`.  
**6) Resolve engrams on a binding** — dereference rich payloads for a given binding.  
**7) Show last 5 bindings** — quick tail (ids + primary tags).  
**8) Quit** — exit (saves if you used `--save`).  
**9) Run preflight now** — full preflight (debugging).  
**10) Inspect binding details** — tags/meta + outgoing edges for a binding.  
**11) Add sensory cue** — creates cue predicates (e.g., `pred:vision:silhouette:mom`). **Triggers policy consideration**.  
**12) Instinct step (Action Center)** — run the ordered policy scan once; prints the policy’s status dict.  
**13) Show skill stats** — per‑policy usage (`n`, `succ`, `rate`, `q`, `last`).  
**14) Autonomic tick** — updates drives, **advances `ctx.ticks`/`ctx.age_days`**, **considers policies**.  
**15) Delete edge (source, destn, relation)** — remove stray/shortcut edges cleanly.  
**16) Export snapshot (bindings + edges + ctx + policies)** — writes `world_snapshot.txt` & `.dot` with **absolute paths**.  
**[S] Save**, **[L] Load**, **[D] Show drives**, **[R] Reset**, **[T] Tutorial** (opens `README.md`).

### Practical tips
- If a **plan** skips steps, check NOW’s edges (`10`) and remove shortcuts with **15**.  
- When adding a **branch** from a non‑latest node, add the node, delete the auto `then` from latest (**15**), then wire the intended source with **4**.  
- Keep **semantic edge labels** (`approach`, `search`, `latch`, `suckle`) for readable traces.

---

