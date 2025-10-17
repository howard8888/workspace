# # CCA8 (v0.7.x) — Project Compendium (Canonical README)

**1 minute summary:**

This single document is the canonical “compendium” for the Causal Cognitive Architecture 8 (CCA8).It serves as: README, user guide, architecture notes, design decisions, and maintainer reference.

Entry point: `cca8_run.py`Primary modules: `cca8_run.py`, `cca8_world_graph.py`, `cca8_controller.py`, `cca8_column.py`, `cca8_features.py`, `cca8_temporal.py`



**5 minute summary:**

**Entry point:** `cca8_run.py`  
**Repo:** `github.com/howard8888/workspace`

**Quickstart:**

1) `py -3.11 -m venv .venv && .\.venv\Scripts\activate && python -V`
2) `python cca8_run.py --about`
3) `python cca8_run.py --autosave session.json`  (or `--load session.json`)

**CCA8 Python Modules:**`cca8_run.py, cca8_world_graph.py, cca8_column.py, cca8_controller.py, cca8_features.py, cca8_temporal.py` 

**Purpose of Program:** Simulation of the brain of a mountain goat through the lifecycle with hooks for robotic embodiment

**Newborn mountain goat demo (fast path):**  
Menu →  add `stand`; connect NOW→stand (`stand_up`); then add and connect  
`mom:close` (`approach`) → `nipple:found` (`search`) → `nipple:latched` (`latch`) → `milk:drinking` (`suckle`);  
verify with  plan NOW → `milk:drinking`.  
**Glossary:** predicates, bindings, edges, policies, drives (hunger/warmth/fatigue), and search knobs (`k`, `sigma`, `jump`).





***Q&A to help you learn this section***

Q: What’s the entry point and the minimal way to see something run?   
A: Run `cca8_run.py` from a Python 3.11 venv. Use `--about` to confirm the install and `--autosave session.json` to start an interactive run that continuously writes your progress.

Q: Which modules should I know by name on day one?   
A: `cca8_run.py` (runner/CLI), `cca8_world_graph.py` (WorldGraph + planner), `cca8_controller.py` (drives/policies), and the engram/feature/time helpers: `cca8_column.py`, `cca8_features.py`, `cca8_temporal.py`.

Q: Is there a “fast path” demo to sanity-check planning?   
A: Yes—add `stand`, connect `NOW→stand`, then add and connect `mom:close → nipple:found → nipple:latched → milk:drinking`, and plan to `milk:drinking`.

Q: Where will this README send me if I get lost?   
A: Use the Table of Contents to jump to Architecture, Planner Contract, or Tutorial sections; this single file is the canonical compendium.



# CCA8 Compendium (All-in-One)

*A living document that captures the design, rationale, and practical know-how for the CCA8 simulation.*  
**Audience:** future software maintainers, new collaborators, persons with an interest in the project.  
**Tone:** mostly technical, with tutorial-style sections so it’s readable without “tribal knowledge.”



<img title="Mountain Goat Calf" src="./calf_goat.jpg" alt="" style="zoom:200%;">

****Planned versions: ****

CCA8 Simulation of a mountain goat through the lifecycle

CCA9 Simulation of a chimpanzee through the lifecycle

CCA10 Simulation of a human through the lifecycle

***Q&A to help you learn this section***

Q: How will concepts carry forward?  A: As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. The chimpanzee has the main structures of the mountain goat (some differences nonetheless in these "same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.



---

**Summary Overview:**

The CCA8 (Causal Cognitive Architecture version 8) is a cognitive architecture that simulates the mammalian brain based on the assumption that the declarative data is largely stored in spatial navigation maps. Simulations can be run virtually but there are hooks, i.e., an interface module, for it to control an actual robotic embodiment. The CCA8 is the simulation of the brain of a mountain goat through the lifecycle with hooks for robotic embodiment.



**What CCA8 is (two-minute orientation):**

CCA8 is a small, inspectable simulation of early mammalian cognition. It models a newborn mountain goat’s first minutes and extends toward richer lifelog episodes. The core idea is to separate:

* a **fast symbolic index** of experience (the WorldGraph), and
* **rich engrams** (perceptual/temporal detail) that live outside the graph in “columns.”

The symbolic graph is not a full knowledge base. Its job is to index “what led to what” as simple, directed edges between small records called bindings. Planning is then just graph search over these edges.

Design decision (formerly ADR-0001): We intentionally use a small episode graph with weak causality. Each edge means “this tended to follow that” rather than a logical implication. This keeps recall and planning fast and transparent; deeper causal reasoning can be layered on later.



***Q&A to help you learn this section***

Q: What exactly is a “binding”? A: A node that carries tags (at least one `pred:*`), optional engram pointers, and meta (e.g., provenance).

Q: What does the graph represent day-to-day? A: Small, directed steps an agent experienced (“this led to that”), not a full world model.

*Q: Why BFS and not Dijkstra/A*? A: Edges are unweighted; BFS guarantees fewest hops and is simpler to reason about. You can layer heuristics later if weights appear.

Q: Are cycles allowed? A: Yes; the planner uses visited-on-enqueue to avoid re-enqueuing discovered nodes.



**Quickstart:**

1. Create a virtual environment (Windows):
      py -3.11 -m venv .venv && .\.venv\Scripts\activate
   Verify:
      python -V

2. Run the program banner:
      python cca8_run.py --about

3. Start an interactive session with autosave enabled:
      python cca8_run.py --autosave session.json
   At any time you can load a prior session:
      python cca8_run.py --load session.json

Tip: The session file is a plain JSON snapshot that includes the WorldGraph, drives, simple policy telemetry, and small bits of context. See “Persistence” below for the exact shape.



**Q&A to help you learn this section**

Q: Where does `--autosave` write and what’s in the file?   
A: It writes a JSON snapshot in your working directory containing world (bindings/edges), drives, skills, and a timestamp.

Q: How do I resume the same run later?   
A: Launch with `--load session.json`; the runner restores the world and advances the id counter to avoid collisions.

Q: What if I want a fresh run but keep history?   
A: Use a new autosave filename or copy the old snapshot aside and start with `--autosave new_session.json`.

Q: Any one-shot CLI for planning without entering the menu?   
A: Use `--plan <pred:token>` on the command line.



**Concepts you’ll see in the UI:**

**Binding** (node). A tiny record that carries tags (at least one `pred:*`), optional engrams, and meta. Bindings act like episode index cards.

**Edge**. A directed link with a small label, often `"then"`. Edges record that one binding led to another during an episode.

**WorldGraph**. The directed graph of bindings and edges. It has a start anchor called NOW and uses breadth‑first search (BFS) to find routes from NOW to a goal predicate.

**Drive**. A motive with a scalar level (e.g., hunger, fatigue, warmth). Drives can publish “drive tags” into the context to make policies easy to trigger.

**Policy**. A small routine with `trigger()` and `execute()`. The Action Center scans policies in priority order, picks the first that triggers, and executes it once. Execution typically creates a new binding and connects it to whatever was most recent.

**Provenance**. A policy stamps its name into the `meta` of any binding it creates. This makes behavior audit trails easy to read.

Design decision (formerly ADR-0002): We use drives + policies instead of a heavy rule engine. Behavior for a newborn unfolds well as short triggered routines (“stand up if you are not already standing,” “seek nipple if hungry”). Guards inside `trigger()` prevent refiring when a state is already true.



***Q&A to help you learn this section***

Q: Binding vs. Predicate vs. Anchor—what’s the difference?   
A: A **predicate** is a token (`pred:…`); a **binding** is the node that carries it (plus meta/engrams); an **anchor** (e.g., NOW) is a special binding used as a planning start.

Q: Where do I see who created a node?   
A: In `meta.policy`—policies stamp their names when they create bindings.

Q: What are drive tags?   
A: Derived tags like `drive:hunger_high` that make policy triggers straightforward.

Q: Can I inspect an engram from the UI?   
A: Yes—use the binding inspection flow to see engram pointers and meta.



**The WorldGraph in detail**

**Nodes (Bindings):**

A binding carries:

* `tags`: a list of strings. One is always a predicate like `pred:stand` or `pred:nurse`. Optional tags include anchors (`anchor:NOW`) or cues (`cue:scent:milk`).
* `engrams`: optional pointers to richer content, e.g., `{"column01": {"id": "...", "act": 1.0}}`.
* `meta`: provenance and light context (policy name that created it, timestamps, etc.).

Bindings live in an index by id (`b1`, `b2`, …). The id is what edges point to.



**Edges (Links):**

Edges live in a simple adjacency list: `src_id -> [{ "to": dst_id, "label": "then", "meta": {...}}, ...]`.

Design decision (ADR-0001 folded in): We keep edges small and directed; multiple distinct edges between the same nodes are allowed if their labels differ (e.g., “then”, “causes”); dedup is left to the caller and the UI can warn on duplication.



**Anchors:**

The graph maintains special anchor bindings such as NOW (the current temporal anchor). The UI prints NOW and LATEST to orient you while you explore or plan.



**Planning:**

Planning is BFS (breadth first search) from a start binding (usually NOW) to any binding that has a goal tag (e.g., `pred:nurse`). We search over the adjacency list and keep a parent map to reconstruct the shortest path in edges. Because edges are unweighted, BFS is sufficient and guarantees fewest hops.

Design decision (was ADR-0004, runner UX): The CLI provides a one‑shot plan with `--plan <token>` and a menu item to plan interactively from NOW. For clarity, plans are shown both as raw ids and as a “pretty path” where each id is printed with its first `pred:*` tag. The HTML graph export can make these paths visible at a glance.

We decided not use a library to implement the WorldGraph but instead have coded it entirely in Python within the program because:

1. The symbolic WorldGraph only holds about 5% of the information of the CCA8 cognitive architecture. The rich store of information is in the engrams to which the WorldGraph must link. This was difficult to do with SciPy sparse or retworkx/igraph. 

2. For development scale simulations the Python code should run fast enough. For larger simulations (e.g., a billion nodes) the WorldGraph and BFS will, of course, need more scalable representations.

3. Note that we are using deques in our Python code which unlike the O(n) behavior of lists, gives O(1) behavior for popleft() -- manipulation of the WorldGraph appears quick enough for small to medium simulations.



##### Indexing & goal resolution (how the planner finds a match)

The planner checks each popped node’s tags for a goal predicate (`pred:<token>`). Implementations may also keep a tiny tag→binding index to accelerate goal detection on large runs. Either way, a match is defined as “any binding whose `tags` contains the requested goal token.” If multiple candidates exist, BFS guarantees the first one popped is on a shortest-hop path from the start. This makes planning both predictable and easy to reason about in logs and demos.

##### Edge-label conventions (house style)

Use `"then"` for episode flow. Reserve domain labels when they clarify intent:

* **`approach`**: locomote toward a target (`stand → mom:close`).

* **`search`**: information-seeking (`mom:close → nipple:found`).

* **`latch`**: discrete state change with contact.

* **`suckle`**: sustained action with reward.  
  You can add richer domain labels over time; keep them short and consistent so paths remain readable.

##### Consistency invariants (quick checklist)

* Every binding has a unique `id` (`bN`), and **anchors** (e.g., `NOW`) map to real binding ids.

* Edges are **directed**; the adjacency lives on the **source** binding’s `edges[]`.

* A binding without edges is a valid **sink**.

* The first `pred:*` tag is used as the default UI label; if absent, the `id` is shown.

* Snapshots must restore `latest`, anchor ids, and advance the internal `bN` counter beyond any loaded ids.

##### Scale & performance notes

For development scale (up to hundreds of thousands of bindings), the dict-of-lists adjacency plus a `deque` frontier is fast and transparent. If the graph grows toward tens of millions of edges, swap the backend (e.g., CSR or a KV store) behind the same interface without changing runner semantics or user-facing behavior.



***Q&A to help you learn this section***

Q: How are edges stored?   
A: On the source binding in an adjacency list: each edge is `{to, label, meta}`.

Q: Do we dedupe edges?   
A: The design allows multiple edges; the UI warns if you add an identical labeled edge so you can skip duplicates.

Q: What labels should I use?   
A: `"then"` for episode flow; you can add others like `approach`, `search`, `latch`, `suckle` to clarify intent.

Q: How does NOW behave?   
A: It’s a named binding used as the plan start and orientation point in the runner and visualizations.

Q: Why a deque?   
A: O(1) `popleft()` for BFS frontiers (lists would be O(n) for `pop(0)`).



**Drives, Policies, and the Action Center:**

The controller tracks simple drives (hunger, fatigue, warmth). Policies consume those signals and look for tags in the WorldGraph or context to decide whether to act. The Action Center asks policies in a fixed order “are you ready? ” and executes the first one that returns true.

Example (stand up):

* Trigger: standing is not already true; body is not severely fatigued.
* Execute: create a `pred:stand` binding; connect from LATEST (or NOW) with label `initiate_stand`, then follow‑on edges `then` into chronological progression.

Design decision (ADR-0002 folded in): Policies are intentionally small and readable. We avoid global planning for every step to keep the code explainable and the UI responsive. Guards in `trigger()` prevent repeated firing (e.g., don’t stand up twice if standing exists).

Design decision (ADR-0008 folded in): If a drive source cannot publish tag predicates for some reason, the system should continue running; policies degrade gracefully by relying on tags already in the graph.



***Q&A to help you learn this section***
Q: How is an action chosen each tick?   
A: The Action Center scans policies in a fixed order and runs the first whose `trigger()` returns True given current drives/tags.

Q: What prevents re-firing the same action?   
A: Guards in `trigger()` (e.g., StandUp checks that standing isn’t already true).

Q: What does a policy return?   
A: A small status dict (policy name, ok/fail/noop, reward, notes) and it stamps provenance on any binding it creates.

Q: What if drive predicates aren’t available?   
A: Policies degrade gracefully by relying on existing graph tags; the system keeps running.





**Persistence (snapshots):**

A session snapshot is a JSON file that contains: the world graph (bindings + edges + internal counters), drives, minimal skill telemetry, and small context items. Saving is atomic; loading restores indices and advances the id counter so new bindings don’t collide with old ids.

Design decision (ADR-0003 folded in): We use human‑readable JSON for portability and easy field debugging. A binary format would be smaller but harder to inspect. The JSON structure is stable enough to be versioned if we add fields later.

Design decision (ADR-0005 folded in): A runner‑level “Reset” is preferable to ad‑hoc deletes when starting a clean demo—this guarantees counters and anchors are consistent.

***Q&A to help you learn this section***

Q: What exactly is persisted?   
A: Bindings, edges, anchors, id counters, drives, and simple skill telemetry, plus `saved_at`.

Q: Are saves safe against partial writes?   
A: Yes—snapshots are written via atomic replace.

Q: After load, why don’t my new nodes collide with old ids?   
A: The loader restores and **advances** the internal id counter.

Q: Binary vs JSON?   
A: JSON keeps sessions portable and debuggable; binary would be smaller but opaque.





**Runner, menus, and CLI:**

You can explore the graph via an interactive menu. Relevant items:

* Display snapshot (prints bindings, edges, drives; optionally exports an interactive graph).
* Add predicate (creates a node with a `pred:*` tag; you can attach it to NOW or LATEST to auto‑link chronology).
* Connect two bindings (adds a directed edge; the UI warns if the same labeled edge already exists).
* Plan from NOW to a predicate (prints ids and a pretty path).

Design decision (ADR-0004 folded in): The runner offers a quick‑exit `--plan <token>` flag when you only need to compute a plan once and exit. The menu shows a short “drives” view because drives are central to policy triggers.

Design decision (ADR-0007 folded in): Attachment semantics are explicit and lowercase: `attach="now"`, `attach="latest"`, or `"none"`. This removes ambiguity when auto‑wiring the newest binding into the episode chain.

***Q&A to help you learn this section***

Q: What are the most useful menu items while learning?   
A: Display snapshot, Add predicate, Connect two bindings, Plan from NOW, and the interactive graph export.

Q: Is there a quick way to visualize the graph?   
A: Yes—export an interactive HTML graph from the menu; labels can show `id`, `first_pred`, or both.

Q: Why does the menu warn about duplicate edges?   
A: To avoid clutter when auto-attach already created the same `(src, label, dst)` relation.

Q: Can I skip the menu and just plan?   
A: Use `--plan pred:<token>` from the CLI for a one-shot plan.





## Table of Contents

1. [Executive Overview](#executive-overview)  
2. [Theory Primer](#theory-primer)  
3. [Architecture](#architecture)  
4. [Key Data Structures (Schemas)](#key-data-structures-schemas)  
5. [Action Selection: Drives, Policies, Action Center](#action-selection-drives-policies-action-center)  
6. [Planner Contract](#planner-contract)  
7. [Persistence: Autosave/Load](#persistence-autosaveload)  
8. [Tutorial: Newborn Mountain Goat — First Minutes](#tutorial-newborn-mountain-goat--first-minutes)  
9. [How-To Guides](#how-to-guides)  
10. [Traceability-Lite (Requirements ↔ Code)](#traceability-lite-requirements--code)  
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

***Q&A to help you learn this section***

Q: Why keep the symbolic graph small?  A: For fast indexing/planning; heavy content lives in engrams.

Q: Which primitives form “standing”?  A: action:push_up, action:extend_legs, state:posture_standing.

Q: Where is provenance stored?  A: binding.meta.policy = "policy:<name>".
Q: What’s the planner algorithm?  A: BFS from NOW to the first pred:<token> match.



***Q&A to help you learn the above sections:***

Q: What’s the key separation in CCA8?  A: A compact symbolic episode index** (WorldGraph) for fast lookup/plan, and rich engrams** outside the graph for heavyweight content.

Q: Are edges logical implications?  A: No—edges encode weak, episode-level causality** (“then”), good for action and recall without heavy inference.

Q: Why not store everything in the graph? A: Keeping symbols small avoids brittleness and keeps planning fast; the heavy 95% lives in engrams referenced by bindings.

Q: How does this help planning? A: BFS over a sparse adjacency list gives shortest-hop paths quickly; the graph is shaped for that.

---

## Theory Primer

- **Weak causality:** Mammalian episodes often encode **soft** chains (“this happened, then that”), sufficient for immediate action without formal causal inference. In CCA8, edges labeled `"then"` capture this episode flow.
- **Two-store economy:** Keep the **symbolic graph small** (~5%): tags & edges for **recall and planning**. Keep the **heavy content** (~95%) in engrams (features, traces, sensory payloads). This avoids the brittleness of “all knowledge in a graph.”
- **From pre-causal to causal:** The symbolic skeleton is compatible with later, stronger causal reasoning layered above (e.g., annotating edges with conditions, failure modes, or learned utilities).
  
  

***Q&A to help you learn this section***

Q: Define “weak causality.” A: Soft episode links (“then”) without asserting logical necessity.

Q: Why engrams vs symbols?  A: Symbols = fast index; engrams = heavy content → avoids brittle all-graph designs.

Q: Can we add stronger causal reasoning later?  A: Yes, layered above (edge annotations, utilities).

---

## Architecture

### Modules (lean overview)

- **`cca8_world_graph.py`** — Directed episode graph (bindings, edges, anchors), plus a BFS planner. Serialization via `to_dict()` / `from_dict()`.
- **`cca8_controller.py`** — Drives (hunger, fatigue, warmth), primitive policies (e.g., `StandUp`), Action Center loop, and a small skill ledger (n, succ, q, last_reward).
- **`cca8_run.py`** — CLI & interactive runner: banner/profile, menu actions (inspect, plan, add predicate, instincts), autosave/load, `--plan` flag, `[D] Show drives`.
- **`cca8_column.py`** — Engram provider (stubs now): bindings may reference column content via small pointers.
- **`cca8_features.py`** — Feature helpers for engrams (schemas/utilities).
- **`cca8_temporal.py`** — Timestamps and simple period/year tagging (used in binding meta).
  
  

***Q&A to help you learn this section***

Q: Which module stores nodes/edges?  A: cca8_world_graph.py.

Q: Which runs instincts?  A: cca8_controller.py (policies + Action Center).

Q: Which shows the menu & autosave/load?  A: cca8_run.py.

Q: Where do engrams live?  A: cca8_column.py, referenced by bindings’ engrams.



### Data flow (a tick)

1. Action Center computes active **drive tags**.  
2. Scans **policies** in order; first `trigger()` that returns True **fires**.  
3. `execute()` appends a **small chain** of predicates + edges to the WorldGraph, stamps `meta.policy`, returns a status dict, and updates the skill ledger.  
4. Planner (on demand) runs BFS from **NOW** to a target `pred:<token>`.  

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



##### Policy ordering & fairness

Policies are evaluated in a fixed order to keep behavior explainable. If two policies could fire on the same tick, the one earlier in the list wins that tick; the other will get a chance later if its trigger remains true. For fairness in long runs, you can:

* periodically rotate policy order, or

* add light inhibition windows (e.g., “don’t refire within N ticks”).

##### Designing good `trigger()` guards

Good triggers are **narrow and testable**:

* Test for **absence** of the goal state (`not standing yet`).

* Include **drive thresholds** when appropriate (`hunger_high`).

* Prefer **explicit tags** or **anchors** over ad-hoc string checks.  
  This makes behavior auditable: anyone can read a binding’s tags/drives and understand why a policy did or did not fire.

##### Example sketch: SeekNipple

* **Trigger:** `drive:hunger_high` and no `pred:nipple:latched`.

* **Execute:** add `pred:nipple:found`, connect from the current state with `search`, optionally emit a cue tag (`cue:scent:milk`) when present.

* **Provenance:** stamp `meta.policy = "policy:seek_nipple"` on any new binding.

Q&A to help you learn this section

Q: Two methods every policy must have?  A: trigger, execute.

Q: What prevents “re-standing”?  A: Guard in StandUp.trigger() that checks for pred:state:posture_standing.

Q: What does a policy return?  A: A status dict (policy, status, reward, notes).

Q: What does the skill ledger track?  A: Counts, success rate, running q, last reward.

---

##### Planner Contract

- **Goal:** Find a path from anchor **NOW** to the **first** binding carrying `pred:<token>`.
- **Algorithm:** **BFS** (O(|V|+|E|)) over edges.  
- **Returns:** List of binding ids (`["b1", "b9", "b12", ...]`) or `None` if not found.
- **When paths don’t exist:** Either you haven’t created the predicate yet (e.g., no instinct tick) or it’s disconnected.
  
  

##### Stop conditions & correctness

Two equivalent conventions exist:

* **Stop-on-pop (default):** return when a goal binding is **popped** from the frontier.

* **Stop-on-discovery:** return as soon as a goal binding is **enqueued**.  
  Both yield shortest paths in unweighted graphs; stop-on-pop tends to produce cleaner logs because the pop order matches the BFS layers.

##### Frontier semantics (one line mental model)

The frontier is the **FIFO queue of discovered-but-not-expanded nodes**. A node is marked “discovered” at **enqueue time**; never enqueue a discovered node again. This invariant prevents cycles from causing duplicates.

##### Path presentation

For humans, show both ids and predicates:  
`b3[born] --then--> b4[wobble] --then--> b5[stand] --then--> b6[nurse]`.  
For programs, keep returning the id list (stable, parseable, compact).



***Q&A to help you learn this section***

Q: Where does planning start?  A: Anchor NOW.

Q: How is the goal detected?  A: First binding whose tags contain pred:<token>.

Q: Complexity?  A: O(|V|+|E|) BFS.
Q: Why might a path be missing?  A: Predicate not created yet or the graph is disconnected.

---

## Persistence: Autosave/Load

- Snapshot file (JSON) includes:
  
  ```jsonc
  {"saved_at": "...", "world": {...}, "drives": {...}, "skills": {...}}
  ```

- **Autosave:** `--autosave session.json` writes after each completed action (atomic replace). Overwrites prior file if same name.

- **Load:** `--load session.json` restores world/drives/skills; id counter advances to avoid `bNN` collisions.

- **Fresh start:** Use a new filename, delete/rename old file, or load a non-existent file (runner continues with a fresh session and starts saving after first action).

##### Atomic writes & recovery

Snapshots are written via **atomic replace**: write to a temp file in the same directory and rename over the old snapshot. If a crash occurs mid-write, the old file remains intact. On load:

1. Parse JSON safely; if it fails, print a clear error with the path and keep the process alive so the user can save to a new file.

2. Validate minimal invariants (`anchors`, `latest`, `bN` shape). If any are missing, reconstruct conservative defaults and continue (prefer a live session to a hard fail).

##### Versioning the shape

Include a small `{"version": "0.7.x"}` under `world`. If you add fields later, bump this string and keep best-effort compatibility in `from_dict()`—log a one-liner describing any defaulted fields so users know what changed.



***Q&A to help you learn this section***

Q: What does autosave write?  A: {saved_at, world, drives, skills}.

Q: How do we avoid id collisions after load?  A: from_dict() advances the internal bNN counter.

Q: Missing --load file?  A: Continue fresh; file created on first autosave.
Q: Why atomic replace on save?  A: Prevents partial/corrupt snapshots.

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
   
   

***Q&A to help you learn this section***

Q: Which menu option creates “standing”?  A: 12 Instinct step.

Q: How do you view provenance?  A: 10 Inspect the binding → meta.policy.

Q: How to list recent nodes?  A: 7 Show last 5 bindings.
Q: How to verify a path exists?  A: 5 Plan from NOW to state:posture_standing.

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



##### Export an interactive graph with readable labels

From the main menu choose **22) Export interactive graph (Pyvis HTML)**, then:

* **Node label mode** → `id+first_pred` (shows both `bN` and the first predicate).

* **Edge labels** → `Y` for small graphs; `n` for big graphs to reduce clutter.

* **Physics** → `Y` unless the graph is very large.  
  Open the saved HTML in your browser and hover nodes/edges for tooltips; the NOW anchor is highlighted to orient you.

### Delete a mistaken edge

If you accidentally created a duplicate or wrong link:

1. Note `src_id` and `dst_id` from the snapshot view.

2. Use the “edge delete” helper (if present in `tools/`) or manually edit the snapshot JSON (`edges[]` on the source binding), then **Load** that edited snapshot.

3. Re-export the graph to confirm the fix.



***Q&A to help you learn this section***

Q: Resume + autosave same file?  A: --load session.json --autosave session.json.

Q: Start fresh but keep old?  A: Autosave to a new filename.

Q: One-shot planning?  A: --load session.json --plan state:posture_standing.

Q: Reset?  A: Press R (with autosave set).

---

## Data schemas (for contributors)

This section documents the canonical in-memory shapes and their JSON snapshot equivalents. The goal is that a maintainer can read the structures, eyeball a saved session, and reconstruct what happened without digging into code.

### World snapshot (top level)

A saved session is a single JSON object that bundles the world, drives, skills, and a timestamp:
    {
      "saved_at": "2025-10-16T12:34:56.789012",
      "world": {
        "version": "0.7.x",
        "next_id": 7,
        "latest": "b6",
        "anchors": { "NOW": "b1" },
        "bindings": {
          "b1": { "...binding object..." },
          "b2": { "...binding object..." }
        }
      },
      "drives": { "hunger": 0.70, "fatigue": 0.20, "warmth": 0.60 },
      "skills": {
        "policy:stand_up": { "n": 3, "succ": 3, "q": 0.58, "last_reward": 1.0 }
      }
    }

**Invariants (top level):**

* `next_id` is the next numeric suffix to allocate (`b{next_id}`), advanced on load to avoid collisions.

* `latest` is the most recently created binding id (used for default attachments).

* `anchors` is a small map of named anchors (e.g., `NOW`, `HERE`) to binding ids.

### Binding (node)

Bindings are the atomic “episode cards” in the graph.
    {
      "id": "b42",
      "tags": [
        "pred:state:posture_standing",
        "cue:silhouette:mom"
      ],
      "edges": [
        { "to": "b43", "label": "then", "meta": { "created_by": "policy:stand_up" } }
      ],
      "meta": { "policy": "policy:stand_up", "t": 123.4 },
      "engrams": { "column01": { "id": "9d46...", "act": 1.0 } }
    }

**Invariants (binding):**

* `id` is a string of the form `b<num>`, unique within the world.

* `tags` is a list of strings; at least one tag for a “stateful” node should be a `pred:*` token (e.g., `pred:stand`).

* `meta.policy` records provenance (which policy created the node); `meta` can hold timestamps or light context.

* `engrams` holds **pointers** to rich content (stored outside the WorldGraph).

### Edge (directed link)

Edges are stored **on the source binding** in its `edges[]` list, forming a classic adjacency list.
    { "to": "b43", "label": "then", "meta": {} }

**Conventions (edge):**

* `to` is the destination binding id.

* `label` is a short relation name. Use `"then"` for episode flow; feel free to add domain labels (e.g., `approach`, `search`, `latch`, `suckle`) when helpful.

* Multiple edges between the same pair are allowed if labels differ; the UI warns when you attempt to add an identical `(src, label, dst)` edge.

### Anchors

Anchors are just bindings with special meaning, referenced in `world.anchors`. Many anchor bindings also carry a tag like `anchor:NOW` for visibility in UIs. Planning typically starts from the `NOW` anchor.

### Drives (controller)

    { "hunger": 0.70, "fatigue": 0.20, "warmth": 0.60 }

The controller may derive helper tags (e.g., `drive:hunger_high`) for policy triggers. If those tags aren’t available, policies should degrade gracefully by using graph state alone.

### Skill ledger (per policy)

A lightweight, per-policy roll-up to support introspection and future learning hooks:
    "policy:stand_up": { "n": 3, "succ": 3, "q": 0.58, "last_reward": 1.0 }

Field meanings are intentionally minimal: total runs `n`, number succeeded `succ`, an optional running quality estimate `q`, and the last reward.

### Contracts & loader behavior

* **Serialization:** `WorldGraph.to_dict()` emits `version`, `next_id`, `latest`, `anchors`, and `bindings`.

* **Deserialization:** `WorldGraph.from_dict()` restores the structures and **advances** the internal id counter beyond any loaded ids.

* **Sinks:** a binding without `edges` is a valid sink.

* **Labels & pretty print:** when displaying paths or graphs, the first `pred:*` tag is used as a human label if present; otherwise the id is shown.



#### Why edges live on the source binding (design rationale)

Storing edges on the source binding gives:

* **O(1) neighbor iteration** for BFS (no global lookups needed).

* **Locality of reasoning:** everything needed to “expand” a node is on that node.

* **Simple persistence:** the snapshot is a direct dump of each binding’s edges.  
  The trade-off is that reverse lookups (who points _to_ `bK`?) require scanning or a small auxiliary index; in practice we only need forward edges for planning.



***Q&A to help you learn this section***

Q: What’s inside a Binding?  A: id, tags, edges[], meta, engrams.

Q: How are edges stored?  A: On the source binding as {"to", "label", "meta"}.

Q: One drive:* tag example?  A: drive:hunger_high (hunger > 0.6).

Q: A skill stat besides n?  A: succ, q, or last_reward.

Q: Where do edges live relative to nodes?  A: On the source binding, inside its `edges[]` list. That’s the adjacency list the planner traverses.

Q: Are duplicate edges allowed? A: The structure allows them, but the UI warns when an identical `(src, label, dst)` already exists so you can skip duplicates.

Q: Which tag shows as the node label in UIs? A: The first `pred:*` tag if present; otherwise the binding id.

Q: How does the loader avoid `bNN` collisions after a load? A: It advances `next_id` past the highest numeric suffix seen in `bindings`.

Q: Do I need to add an edge for a terminal node? A: No. A binding with an empty (or missing) `edges` list is a valid sink.

Q: What makes a predicate “atomic”?A: It’s a single namespaced token (`pred:…`) carried by a binding; we don’t decompose it further inside the graph.

Q: One concrete example of provenance?A: `meta.policy = "policy:stand_up"` on the standing binding created by the StandUp policy.

Q: What is the “skill ledger”?A: Lightweight per-policy stats (counts, success, running q, last reward) to support analytics or future RL.

* * *



## Planner contract (for maintainers)

Input:

* `start_id`: usually the NOW anchor.
* `goal_token`: a predicate token like `pred:nurse`.

Output:

* Path as a list of ids, or `None` if unreachable.

Rules:

* BFS over `edges` with visited‑on‑enqueue.
* Parent map records the first discoverer.
* Stop‑on‑pop or stop‑on‑discovery are both acceptable (we currently stop‑on‑pop).
* The pretty printer reconstructs `id[label] --edge--> id[label]` for readability.
  
  

***Q&A to help you learn this section***

Q: Start node for plans?   
A: The NOW anchor (binding id) unless explicitly overridden.

Q: Stop condition?   
A: When the planner pops a binding whose tags include the target `pred:<token>`.

Q: Visited bookkeeping?   
A: Visited-on-enqueue with a parent map to reconstruct the shortest path.

Q: Can we switch to weighted search later?   
A: Yes—swap BFS with Dijkstra/A* once edges carry costs/heuristics or... consider library component.

* * *

## Persistence contract

* `WorldGraph.to_dict()` produces a serializable shape with bindings, their edges, anchors, and the next id counter.
* `WorldGraph.from_dict()` restores the same and advances the counter past any loaded ids so new bindings don’t collide.
* The runner writes snapshots atomically and includes minor controller and skill state for debugging.

Design decision (ADR-0003 folded in): We chose JSON over a binary format to keep field debugging simple and to make saved sessions portable across machines and Python versions.



***Q&A to help you learn this section***

Q: What are the versioning expectations of the JSON shape?   
A: Keep it stable; if fields change, bump a version field and handle compatibility in `from_dict()`.

Q: Does loading mutate counters?   
A: Yes—counters advance so newly created bindings get fresh ids.

Q: What else does the runner persist beyond the world?   
A: Drives and small controller telemetry to aid debugging.



## Traceability (requirements to code)

A traceability‑lite table maps major requirements to the modules and functions that satisfy them. Keep this short and keep it close to code names so a maintainer can jump straight into the right file. Examples:

* REQ‑PLAN‑01: BFS finds a shortest path in edges.Satisfied by `WorldGraph.plan_to_predicate` (BFS), `pretty_path` (display).

* REQ‑POL‑02: Policies run in priority order with small guards.Satisfied by `cca8_controller.ActionCenter`, policy `trigger()` guards, and provenance in `meta`.

* REQ‑PERS‑03: Loading a snapshot advances the id counter.Satisfied by `WorldGraph.from_dict`.

You can expand this list as the codebase grows.
Note -- Currently halted as much work.. but to consider implementing again in the future...

***Q&A to help you learn this section***

Q: Does it seem silly having these Q&A for section barely used.  A: No... as forms part of scaffolding of multi-purpose README/compedium document.

**Q: How do I keep requirements and code in sync?   
A: Add a short REQ row and tag the relevant functions/classes with the REQ id in comments.

**Q: Where should new ADRs go now that decisions are in-line?   
A: Summarize in the section where the topic appears and, if large, put the full ADR under `docs/adr/` with a link.

**Q: What belongs in a REQ vs. ADR?   
A: REQ = behavior the system must provide; ADR = why a design choice was made among alternatives. 

* * *

## Roadmap

* Enrich engrams and column providers; add minimal perception‑to‑predicate pipelines.
* Add “landmarks” and heuristics for long‑distance plans (A* when we add weights).
* Optional database or CSR backend if the graph grows beyond memory.
* Exporters: NetworkX/GraphML for interoperability; continue shipping the Pyvis HTML for quick, zero‑install visualization.

***Q&A to help you learn this section***

Q: Does it seem silly having these Q&A for section barely used. A: No... as forms part of scaffolding of multi-purpose README/compedium document.

* * *

### 

## Debugging Tips (traceback, pdb, VS Code)

- **traceback:** In `except Exception:` add `traceback.print_exc()` to print a full stack. Use when a loader/snapshot fails.  
- **pdb:** Drop `breakpoint()` in code or run `python -m pdb cca8_run.py --load ...`. Commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p`/`pp` (print), `b` (breakpoint), `where`.  
- **VS Code debugger:** Create `.vscode/launch.json` with args, set breakpoints in the gutter, F5 to start. Great for multi-file stepping.
* Tracebacks: the runner keeps exceptions readable; copy the stack into an issue if you see unexpected behavior.
* `pdb`: insert `import pdb; pdb.set_trace()` where needed to inspect bindings and edges.
* VS Code: run `cca8_run.py` with the debugger and place breakpoints in `plan_to_predicate()` or policy `trigger()`/`execute()`.
  
  

A common pitfall is duplicate edges when both auto‑attach and a manual connect create the same relation. The UI warns when you try to add a duplicate; you can also inspect the `edges` list on a binding directly in the debugger.

#### Playbook: “No path found”

1. **Verify the predicate exists** (snapshot shows a binding with that `pred:*`).

2. **Check connectivity** (ensure there’s a forward chain of edges from NOW to that binding).

3. **Look for reversed edges** (common error: added `B→A` instead of `A→B`).

4. **Confirm the goal token** (exact `pred:<token>` string; avoid typos/extra spaces).

5. **Inspect layers** (use the interactive graph; the missing hop will be visually obvious).

#### Playbook: “Repeated standing”

1. Confirm `StandUp.trigger()` checks for an existing standing predicate.

2. Verify policy order (another policy shouldn’t insert a second standing node as a side effect).

3. Grep recent bindings for `meta.policy` to see who created duplicates.



***Q&A to help you learn this section***

Q: Quick way to print a stack?  A: traceback.print_exc() in except.

Q: Start debugger from CLI?  A: python -m pdb cca8_run.py --load ....

Q: Persistent breakpoint in code?  A: breakpoint() (Python 3.7+).

Q: IDE workflow?  A: VS Code launch config + gutter breakpoints.

---

## FAQ / Pitfalls

- **“No path found to state:posture_standing”** — You planned before creating the state. Run one instinct tick (menu **12**) first or `--load` a session that already has it.
- **Repeated “standing” nodes** — Tightened `StandUp.trigger()` prevents refiring when a standing binding exists. If you see repeats, ensure you’re on the updated controller.
- **Autosave overwrote my old run** — Use a new filename for autosave (e.g., `--autosave session_YYYYMMDD.json`) or keep read-only load + new autosave path.
- **Loading says file not found** — We continue with a fresh session; the file will be created on your first autosave event.
  
  

***Q&A to help you learn this section***

Q: Why “No path found …” on a new session?  A: You planned before adding the predicate; run one instinct tick.

Q: Why duplicate “standing” nodes?  A: Old controller; update to guarded StandUp.trigger().

Q: How to keep an old snapshot?  A: Autosave to a new filename.
Q: Is load failure fatal?  A: No; runner continues with a fresh session.

---

## Architecture Decision Records (ADRs)

### ADR-0001 —

Note -- ADR's are paused at present. Instead new material is integrated directly into the code and documented directly in the body of this document. ADR's are planned to restart once the project reaches a higher level of maturation.





* * *

## 

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



***Q&A to help you learn this section***

Q: Binding vs Predicate?  A: Binding = node container; Predicate = symbolic fact carried by the binding.

Q: Edge label semantics today?  A: "then" = weak episode causality.

Q: Engram?  A: Pointer to heavy content (outside the graph).

Q: Provenance?  A: meta.policy records which policy created the node.

---

*End of compendium. Keep this single file updated. If size ever becomes unwieldy, we can split into a `docs/` tree while preserving the same section structure.*

## Session Notes (Living Log)

### 

- - 

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
