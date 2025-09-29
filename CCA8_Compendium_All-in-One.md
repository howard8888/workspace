# CCA8 Compendium (All-in-One)

*A living document that captures the design, rationale, and practical know-how for the CCA8 simulation.*  
**Audience:** future software maintainers, new collaborators, persons with an interest in the project.  
**Tone:** mostly technical, with tutorial-style sections so it’s readable without “tribal knowledge.”



**Summary Overview:**

The CCA8 (Causal Cognitive Architecture version 8) is a cognitive architecture that simulates the mammalian brain based on the assumption that the declarative data is largely stored in spatial navigation maps. Simulations can be run virtually but there are hooks, i.e., an interace module, for it to control an actual robotic embodiment.



****Planned versions: ****

CCA8   Simulation of a mountain goat through the lifescycle

CCA9  Simulation of a chimpanzee through the lifecycle

CCA10 Simulation of a human through the lifecycle



<img title="" src="file:///C:/Users/howar/OneDrive/Desktop/3day_old_mountain_goat.jpg" alt="3day_old_mountain_goat" data-align="center" style="zoom:150%;">

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


Awesome prompt. I read both attachments and did a quick literature sweep on Oak/STOMP so we can connect the dots to CCA8.

---

## What Sutton’s “Alberta Plan” and **Oak** are proposing (in a nutshell)

* **Agent framing:** All learning is grounded in three time-series—observation, action, reward—continuously, with **temporal uniformity** (no special “training phases”). The agent plans and learns on *every* step under compute constraints. 

* **Base agent:** perception → reactive policies (+ value functions) → transition model → planning, all updating continually. 

* **Roadmap → Oak:** they propose a sequence that culminates in **Oak** (Step 11). The **STOMP progression** builds temporally-abstract competence:
  **S**ubtasks → **T**emporal-option (**O**ption) → **M**odel of that option → **P**lanning with the option model; Oak **adds feedback** that continuously ranks and *replaces* features, subtasks, options, and option models (i.e., continual structure learning). 

* **Option Keyboard:** a way to *compose* options—think linear combinations of skills in pseudo-reward space—to synthesize new skills instantly. ([arXiv][1])

* **Reward-respecting subtasks (RRS):** define subtasks that **use the original reward** plus a feature-based bonus at **option termination**; the resulting options are much more useful for planning than many previous discovery methods. ([arXiv][2])

Overall: Oak + STOMP is a coherent plan for **continual, options-based, model-based RL** that constantly **creates/uses/retires** abstractions (features, options, models) under compute limits. 

---

## Internet sources you can skim (good signal)

* **Alberta Plan** (arXiv PDF; Step 11 describes Oak): ([arXiv][3])
* **RRS** (arXiv + journal): ([arXiv][2])
* **Option Keyboard** (NeurIPS & arXiv): ([NeurIPS Papers][4])
* Talks where Sutton walks through Oak and related planning choices: ([YouTube][5])

---

## What I think (brief critique)

* The **discipline of temporal uniformity** and the insistence on **options + planning** every step is exactly what long-lived agents need.
* **RRS** is the missing piece that ties option discovery to **what planning cares about** (reward at termination), and *that’s* why it tends to produce useful abstractions.
* The **Option Keyboard** answers the “how to combine skills *now*” question; it’s practical and plays nicely with RRS.
* Open challenges (they acknowledge these): learned perception that supports options and models, search-control under compute budgets, and **multi-agent** signals (social reward, cooperation/competition). 

This all lines up well with where we’re steering CCA8.

---

## Your ToM paper and how it plugs in

Your AGI-2025 chapter argues ToM should be treated as a **behavior-directing mechanism**, not just a benchmark trick. You operationalize a **Goal Module** that balances energy (AM) versus a social/ToM drive (T), producing an **Out** signal that biases primitives; in simulation it yields large survival gains (≈97 vs 6 cycles). 

> Your intuition that **ToM is a “reward-like” signal over the lifespan** fits Alberta Plan mechanics perfectly if we treat it as a **cumulant/bonus** used in **reward-respecting subtasks** and as a **GVF** to predict and plan with. 

Concretely:

* Treat **ToM-Out** (from your Goal Module) as a **termination bonus** in RRS.
* Track **GVFs** that predict social outcomes (e.g., acceptance/rejection, donation reciprocity, deception penalties). (This mirrors Horde-style many-predictions, and Oak’s continual learning vibe.) ([AI University of Basel][6])

---

## How to incorporate Oak/STOMP into **CCA8** (minimal invasive roadmap)

Below is a pragmatic adaptation that maps Sutton’s terms onto our current code (predicates/bindings/edges + policies). Each step is implementable without overhauling the system.

### Mapping

| Alberta Plan                          | CCA8 today                                                               | CCA8 addition                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Feature** (state signal)            | Predicates like `vision:mom:close`, `state:posture_standing`, drive tags | Keep using predicates as “features”; add tiny **feature ranking** (count use in successful plans)        |
| **Subtask** (target feature w/ bonus) | “Plan to predicate” (BFS)                                                | Define **Subtask** = `target_predicate` + **termination bonus function** (e.g., ToM-Out or energy delta) |
| **Option** (policy+termination)       | Policies (StandUp, SeekNipple…)                                          | Wrap policies as **Options** with clear termination predicates; add simple **option registry**           |
| **Option Model** (S’, R)              | N/A yet                                                                  | For each option, store **macro-edge**: (source→termination) with **expected steps** and **bonus reward** |
| **Planning**                          | BFS over micro edges                                                     | Allow BFS to traverse **macro-edges** (option-edges) too; later: prioritize by expected bonus            |
| **Option Keyboard**                   | N/A yet                                                                  | Allow linear blend of options by **weights**; for now, pick argmax(weight×Q_est) per tick                |

### Phase 1 — **RRS with ToM**

1. **Subtasks registry** (runner):

   ```text
   Subtask(name, target_predicate, termination_bonus_fn)
   ```

   * Examples:

     * `sub:stand` → `state:posture_standing`, bonus `+0.1`
     * `sub:social_accept` → `vision:mom:close`, bonus = **ToM-Out** (your Eq. (2)) at termination. 

2. **Wrap policies as options** (controller):
   Each policy gets `termination_predicate` and we log the **observed termination bonus** when it ends.

3. **Option model as macro-edge** (world):
   When an option ends, add a **macro-edge** `b_start --option:<name>--> b_term` with `meta={"bonus": bonus, "steps": k}`. Planner can now consider either micro “then” edges or macro option-edges.

4. **Average reward signal** (runner/controller):
   Maintain a lightweight **avg_reward** estimate (differential if you like). Use `(environmental reward + termination bonus)` as the combined signal for skill stats. This is consistent with RRS. ([arXiv][2])

### Phase 2 — **Option Keyboard (minimal)**

* Provide an API: `execute_keyboard(weights: dict[option->w])`.
  First cut: pick the option with highest `w × Q_est(option)` from our skill ledger, execute it; later, try short sequential blends. ([arXiv][1])

### Phase 3 — **Continual structure (Oak-like feedback)**

* After N ticks, **rank features** (predicates) by how often they appear in *successful* plans or option terminations with positive bonus.
* Replace the lowest-ranked subtask with a new one built from a recently frequent predicate (“feature → new Subtask” = the **S→T** of STOMP).
* Garbage-collect stale options/models whose macro-edges were never used by the planner (Oak’s replacement loop). 

This gives us a live, small-data Oak prototype *inside* CCA8 without a heavy rewrite.

---

## ToM as a **reward signal** (your question)

* In Sutton’s setting, reward is a special scalar. Your **ToM-Out** can be treated as a **cumulant** and/or **termination bonus**—that’s precisely what RRS prescribes: keep original reward, **plus** a termination bonus tied to the *feature you care about*. ([arXiv][2])
* Practically: your **Goal Module** can keep producing **Out** every tick; for RRS, we read its value **at option termination** and log it in the option model’s meta. This integrates your lifelong ToM pressure directly into planning and option choice. 

---

## What to implement next (surgical changes)

1. **Types**

   * `Subtask`: name, `target_predicate`, `bonus_fn(binding, drives, world)->float`
   * `Option`: name, `policy_ref`, `termination_predicate`

2. **Controller**

   * On policy end, detect `termination_predicate`; compute `bonus = bonus_fn(...)` (e.g., ToM-Out); update skill stats with `reward + bonus`.

3. **WorldGraph**

   * `add_option_edge(src, dst, option_name, meta={"bonus":..., "steps":...})`
   * BFS: allow traversing `label.startswith("option:")` edges; later add a “prefer high bonus” tiebreak.

4. **Runner**

   * Registry & simple CLI hooks to list/add/remove subtasks & options (for us to iterate).
   * Keep **avg_reward** updated (even if just a moving average).

If you want, I can draft the exact code diffs for (1)–(3) tailored to our files.

---

### Citations used above

* Sutton et al., **Alberta Plan / Oak / STOMP** (arXiv) and base-agent vision. 
* Your AGI-2025 **ToM** chapter (Goal Module equations, survival results, role of ToM as behavioral driver). 
* **Reward-Respecting Subtasks** (RRS) concept and motivation. ([arXiv][2])
* **Option Keyboard** (compose skills via pseudo-reward combinations). ([arXiv][1])
* Additional pointers to Sutton/Oak talks and overviews. ([arXiv][3])

If you’re happy with this plan, I’ll produce a first pass of “Subtasks + Option models + ToM-bonus” as small patches to `cca8_controller.py` and `cca8_world_graph.py`, keeping everything else intact.

[1]: https://arxiv.org/abs/2106.13105?utm_source=chatgpt.com "The Option Keyboard: Combining Skills in Reinforcement Learning"
[2]: https://arxiv.org/abs/2202.03466?utm_source=chatgpt.com "Reward-Respecting Subtasks for Model-Based Reinforcement Learning"
[3]: https://arxiv.org/pdf/2208.11173?utm_source=chatgpt.com "arXiv:2208.11173v3 [cs.AI] 21 Mar 2023"
[4]: https://papers.neurips.cc/paper/9463-the-option-keyboard-combining-skills-in-reinforcement-learning.pdf?utm_source=chatgpt.com "The Option Keyboard: Combining Skills in Reinforcement ..."
[5]: https://www.youtube.com/watch?v=gEbbGyNkR2U&utm_source=chatgpt.com "Rich Sutton, The OaK Architecture: A Vision of ..."
[6]: https://ai.dmi.unibas.ch/research/reading_group/sutton-et-al-arxiv2022.pdf?utm_source=chatgpt.com "arXiv:2208.11173v2 [cs.AI] 6 Oct 2022"
