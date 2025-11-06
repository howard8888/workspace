# # CCA8  — Project Compendium (README)

# CCA8 Compendium (All-in-One)

The CCA8 Compendium is an all-in-one ongoing document that captures the design, rationale, and practical know-how for the CCA8 simulation project. It is intended to function as a user manual how to use the software as well as provide technical details to persons with an interest in the project.

**1 minute summary:**

The CCA8 Project is the simulation of the brain of a mountain goat through the lifecycle with hooks for different robotic embodiments. 

Scaffolding in place (partially operational) for simulation of a chimpanzee-like brain, human-like brain, human-like brain with five brains operating in parallel in the same agent, human-like brain with multiple agents interacting, human-like brain with five brains operating in parallel with combinatorial planning ability.

This single document is the canonical “compendium” for the Causal Cognitive Architecture 8 (CCA8).It serves as: README, user guide, architecture notes, design decisions, and maintainer reference.

Entry point: `cca8_run.py`Primary modules: `cca8_run.py`, `cca8_world_graph.py`, `cca8_controller.py`, `cca8_column.py`, `cca8_features.py`, `cca8_temporal.py`



<img title="Mountain Goat Calf" src="calf_goat.jpg" alt="loading-ag-2696" style="zoom:200%;">

*Adult Mountain Goat with recently born Calf (walking within minutes
of birth, and by one week can climb most places its mother can)*

**CCA8** Simulation of a mountain goat through the lifecycle 
**CCA8b** Simulation of a mountain goat-like brain with 5 brains within the same agent
**CCA8c** Simulation of multiple agents with goat-like brains able to interact
**CCA8d** Simulation of a mountain goat-like brain with 5 brains within the same agent with combinatorial planning
**CCA9** Simulation of a chimpanzee through the lifecycle
**CCA10** Simulation of a human through the lifecycle
*See **References** Section for published peer reviewed articles on the **CCA7** and earlier versions*





**5 minute summary:**

**Entry point:** `cca8_run.py`  
**Repo:** `github.com/howard8888/workspace`

**Quickstart:**

1) `py -3.11 -m venv .venv && .\.venv\Scripts\activate && python -V`
2) `python cca8_run.py --about`
3) `python cca8_run.py --autosave session.json`  (or `--load session.json`)

**CCA8 Python Modules:**`cca8_run.py, cca8_world_graph.py, cca8_column.py, cca8_controller.py, cca8_features.py, cca8_temporal.py` 

**Purpose of Program:** Simulation of the brain of a mountain goat through the lifecycle with hooks for different robotic embodiments.

Scaffolding in place (partially operational) for simulation of a chimpanzee-like brain, human-like brain, human-like brain with five brains operating in parallel in the same agent, human-like brain with multiple agents interacting, human-like brain with five brains operating in parallel with combinatorial planning ability.

**Newborn mountain goat demo (fast path):**  
Menu →  add `stand`, connect NOW→stand (`stand_up`), then add and connect  
`mom:close` (`approach`) → `nipple:found` (`search`) → `nipple:latched` (`latch`) → `milk:drinking` (`suckle`),  
verify with  plan NOW → `milk:drinking`.  
**Glossary:** predicates, bindings, edges, policies, drives (hunger/warmth/fatigue), and search knobs (`k`, `sigma`, `jump`).

---



## Table of Contents

- [Executive Overview](#executive-overview)
- [Opening screen (banner) explained](#opening-screen-banner-explained)
- [Profiles (1–7): overview and implementation notes](#profiles-17-overview-and-implementation-notes)
- [The WorldGraph in detail](#the-worldgraph-in-detail)
- [Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)](#tagging-standard-bindings-predicates-cues-anchors-actions-provenance--engrams)
- [Restricted Lexicon (Developmental Vocabulary)](#restricted-lexicon-developmental-vocabulary)
- [Signal Bridge (WorldGraph ↔ Engrams)](#signal-bridge-worldgraph--engrams)
- [Architecture](#architecture)
  - [Modules (lean overview)](#modules-lean-overview)
  - [Data flow (a tick)](#data-flow-a-tick)
- [Action Selection: Drives, Policies, Action Center](#action-selection-drives-policies-action-center)
- [Planner Contract](#planner-contract)
- [Planner: BFS vs Dijkstra (weighted edges)](#planner-bfs-vs-dijkstra-weighted-edges)
- [Persistence: Autosave/Load](#persistence-autosaveload)
- [Runner, menus, and CLI](#runner-menus-and-cli)
- [Logging & Unit Tests](#logging--unit-tests)
- [How-To Guides](#how-to-guides)
- [Data schemas (for contributors)](#data-schemas-for-contributors)
- [Traceability (requirements to code)](#traceability-requirements-to-code)
- [Roadmap](#roadmap)
- [Debugging Tips (traceback, pdb, VS Code)](#debugging-tips-traceback-pdb-vs-code)
- [FAQ / Pitfalls](#faq--pitfalls)
- [Glossary](#glossary)
- [References](#references)
- [Session Notes (Living Log)](#session-notes-living-log)
- [Work in Progress](#work-in-progress)

<!-- Optional tutorial entries; include if you want them surfaced from the top -->

- [Tutorial on WorldGraph, Bindings, Edges, Tags and Concepts](#tutorial-on-worldgraph-bindings-edges-tags-and-concepts)
- [Tutorial on WorldGraph Technical Features](#tutorial-on-worldgraph-technical-features)
- [Tutorial on Breadth-First Search (BFS) Used by the CCA8 Fast Index](#tutorial-on-breadth-first-search-bfs-used-by-the-cca8-fast-index)
- [Tutorial on Main (Runner) Module Technical Features](#tutorial-on-main-runner-module-technical-features)
- [Tutorial on Controller Module Technical Features](#tutorial-on-controller-module-technical-features)
- [Tutorial on Temporal Module Technical Features](#tutorial-on-temporal-module-technical-features)
- [Tutorial on Features Module Technical Features](#tutorial-on-features-module-technical-features)
- [Tutorial on Column Module Technical Features](#tutorial-on-column-module-technical-features)
- [Planner contract (for maintainers)](#planner-contract-for-maintainers)
- [Persistence contract](#persistence-contract)
  
  
  
  

**Summary Overview:**

The CCA8 (Causal Cognitive Architecture version 8) is a cognitive architecture that simulates the mammalian brain based on the assumption that the declarative data is largely stored in spatial navigation maps. Simulations can be run virtually but there are hooks, i.e., an interface module, for it to control an actual robotic embodiment. The CCA8 is the simulation of the brain of a mountain goat through the lifecycle with hooks for robotic embodiment.



**What CCA8 is (two-minute orientation):**

CCA8 is a small, inspectable simulation of early mammalian cognition. It models a newborn mountain goat’s first minutes and extends toward richer lifelog episodes. The core idea is to separate:

* a **fast symbolic index** of experience (the WorldGraph), and
* **rich engrams** (perceptual/temporal detail) that live outside the graph in “columns.”

The symbolic graph is not a full knowledge base. Its job is to index “what led to what” as simple, directed edges between small records called bindings. Planning is then just graph search over these edges.

Design decision (formerly ADR-0001): We intentionally use a small episode graph with weak causality. Each edge means “this tended to follow that” rather than a logical implication. This keeps recall and planning fast and transparent, deeper causal reasoning can be layered on later.



***Q&A to help you learn this section***

Q: What exactly is a “binding”? A: A node that carries tags (at least one `pred:*`), optional engram pointers, and meta (e.g., provenance).

Q: What does the graph represent day-to-day? A: Small, directed steps an agent experienced (“this led to that”), not a full world model.

*Q: Why BFS and not Dijkstra/A*? A: Edges are unweighted, BFS guarantees fewest hops and is simpler to reason about. You can layer heuristics later if weights appear.

Q: Are cycles allowed? A: Yes, the planner uses visited-on-enqueue to avoid re-enqueuing discovered nodes.



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
A: Launch with `--load session.json`, the runner restores the world and advances the id counter to avoid collisions.

Q: What if I want a fresh run but keep history?   
A: Use a new autosave filename or copy the old snapshot aside and start with `--autosave new_session.json`.

Q: Any one-shot CLI for planning without entering the menu?   
A: Use `--plan <pred:token>` on the command line.



**Concepts you’ll see in the UI:**

**Binding** (node). A tiny record that carries tags (at least one `pred:*`), optional engrams, and meta. Bindings act like episode index cards.

**Edge**. A directed link with a small label, often `"then"`. Edges record that one binding led to another during an episode.

**WorldGraph**. The directed graph of bindings and edges. It has a start anchor called NOW and uses breadth‑first search (BFS) to find routes from NOW to a goal predicate.

**Drive**. A motive with a scalar level (e.g., hunger, fatigue, warmth). The controller exposes **ephemeral drive flags** via `Drives.flags()` (strings like `drive:hunger_high`) used only inside policy triggers; they are **not written** into WorldGraph. If you want a persisted/plannable drive condition, create a tag explicitly as **`pred:drive:*`** (plannable) or **`cue:drive:*`** (trigger-only).

**Policy**. A small routine with `trigger()` and `execute()`. The Action Center scans policies in priority order, picks the first that triggers, and executes it once. Execution typically creates a new binding and connects it to whatever was most recent.

**Provenance**. A policy stamps its name into the `meta` of any binding it creates. This makes behavior audit trails easy to read.

Design decision (formerly ADR-0002): We use drives + policies instead of a heavy rule engine. Behavior for a newborn unfolds well as short triggered routines (“stand up if you are not already standing,” “seek nipple if hungry”). Guards inside `trigger()` prevent refiring when a state is already true.



***Q&A to help you learn this section***

Q: Binding vs. Predicate vs. Anchor—what’s the difference?   
A: A **predicate** is a token (`pred:…`), a **binding** is the node that carries it (plus meta/engrams), an **anchor** (e.g., NOW) is a special binding used as a planning start.

Q: Where do I see who created a node?   
A: In `meta.policy`—policies stamp their names when they create bindings.

Q: What are drive flags?   
A: Derived flags like `drive:hunger_high` that make policy triggers straightforward.

Q: Can I inspect an engram from the UI?   
A: Yes—use the binding inspection flow to see engram pointers and meta.



###### Opening screen (banner) explained

    A Warm Welcome to the CCA8 Mammalian Brain Simulation
    (cca8_run.py v0.7.11)
    
    Entry point program being run: C:\Users\howar\workspace\cca8_run.py
    OS: win32 (run system-dependent utilities for more detailed system/simulation info)
    (for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)
    
    Embodiment:  HAL (hardware abstraction layer) setting: off (runs without consideration of the robotic embodiment)
    Embodiment:  body_type-version_number-serial_number (i.e., robotic embodiment): none specified
    
    The simulation of the cognitive architecture can be adjusted to add or take away
      various features, allowing exploration of different evolutionary-like configurations.
    
      1. Mountain Goat-like brain simulation
      2. Chimpanzee-like brain simulation
      3. Human-like brain simulation
      4. Human-like one-agent multiple-brains simulation
      5. Human-like one-brain simulation × multiple-agents society
      6. Human-like one-agent multiple-brains simulation with combinatorial planning
      7. Super-Human-like machine simulation
    
    Pending additional intro material here....
    Please make a choice [1-7]:

What each part means:

* Version and path: printed by the runner, the version comes from `__version__` in the runner. The path helps confirm which file you launched.

* OS/flags line: a reminder that you can run `--help` or the non-interactive flags such as `--about`, `--plan`, `--preflight`.

* Embodiment (HAL/body): shows whether the hardware abstraction layer is enabled and which body profile (if any) was provided. The current build runs fine with HAL off.

* Profile menu: seven presets that configure or demonstrate different cognitive configurations (documented below). Selection is handled by `choose_profile`, which records your choice in the runtime context and proceeds with the session.

* * *

##### Profiles (1–7): overview and implementation notes

This section documents what each profile intends to represent and how the current runner implements it. Items 2–7 are demonstration stubs that explain the idea, print a short trace, and then fall back to the Mountain Goat profile so today’s simulation continues unchanged.

1. Mountain Goat-like brain simulation  
   Baseline profile focused on a neonate mountain goat. Defaults: sigma=0.015, jump=0.2, winners_k=2. A boot step ensures a stand intent early in the episode. Use this profile for all current demos and for reading the code.

2. Chimpanzee-like brain simulation  
   Narrative only. Prints an explanation of enhanced feedback pathways and combinatorial language relative to the goat, then falls back to the Mountain Goat defaults. This is a placeholder for a richer causal model.

3. Human-like brain simulation  
   Narrative only. Prints an explanation of further-enhanced feedback pathways, causal and analogical reasoning, then falls back to the Mountain Goat defaults.

4. Human-like one-agent multiple-brains simulation  
   Implements a dry-run “multi-brains” scaffold inside one agent. The runner forks five sandbox WorldGraphs (deep copies of the live world for now), each proposes a next action with a confidence and rationale, and a voting rule selects the winner (most popular, ties broken by average and maximum confidence). No changes are committed to the live world, it is a read-only demonstration of the mechanism. Future work would merge only new nodes/edges from the winning sandbox and re-id them to avoid collisions.

5. Human-like one-brain × multiple-agents society  
   Implements a dry-run “society” scaffold. The runner creates three independent agents, each with its own WorldGraph and Drives, runs one action-center tick per agent, and demonstrates a simple inter-agent message as a cue (e.g., A1 bleats, A2 receives a sound cue). No snapshots are written, this is a safe, print-only demo. In a full build, you would iterate over agents each tick and exchange messages via a queue or shared mailbox.

6. Human-like one-agent multiple-brains with combinatorial planning  
   Implements a dry-run combinatorial planner. Five “brains” each run many von Neumann processors (configurable, the current stub uses 256 per brain) to explore short candidate plans, score them with a simple utility (sum of action rewards minus a per-step cost), report the per-brain best and average score, and then select a champion brain. In a real system only the first action of the winning plan would be committed to the live world after a safety check, the stub prints the commit rule but does not modify state.

7. Super-Human-like machine simulation  
   Implements a dry-run meta-controller. Three proposal sources (symbolic search, neural value, program synthesis) each provide an action and a utility, the meta-controller picks the winner by score with a fixed tie-break preference. The printout illustrates how a higher-level controller could arbitrate between heterogeneous planners. No state is modified.
* 

* * *

**The WorldGraph in detail**

**Nodes (Bindings):**

A binding carries:

* `tags`: a list of strings. One is always a predicate like `pred:stand` or `pred:nurse`. Optional tags include anchors (`anchor:NOW`) or cues (`cue:scent:milk`).
* `engrams`: optional pointers to richer content, e.g., `{"column01": {"id": "...", "act": 1.0}}`.
* `meta`: provenance and light context (policy name that created it, timestamps, etc.).

Bindings live in an index by id (`b1`, `b2`, …). The id is what edges point to.



**Edges (Links):**

Edges live in a simple adjacency list: `src_id -> [{ "to": dst_id, "label": "then", "meta": {...}}, ...]`.

Design decision (ADR-0001 folded in): We keep edges small and directed, multiple distinct edges between the same nodes are allowed if their labels differ (e.g., “then”, “causes”), dedup is left to the caller and the UI can warn on duplication.



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
  You can consider richer domain labels but keep them short and consistent so paths remain readable.
  **Action-like predicates.** When it improves readability or you want an intermediate state, you may also record an action-like predicate such as `pred:action:push_up`. The project’s lexicon permits several `action:*` tokens **under the `pred` family**. Planner behavior is unchanged (planning is over structure), and the house style still favors **edge labels** for actions.

##### Consistency invariants (quick checklist)

* Every binding has a unique `id` (`bN`), and **anchors** (e.g., `NOW`) map to real binding ids.

* Edges are **directed**, the adjacency lives on the **source** binding’s `edges[]`.

* A binding without edges is a valid **sink**.

* The first `pred:*` tag is used as the default UI label, if absent, the `id` is shown.

* Snapshots must restore `latest`, anchor ids, and advance the internal `bN` counter beyond any loaded ids.

##### Scale & performance notes

For development scale (up to hundreds of thousands of bindings), the dict-of-lists adjacency plus a `deque` frontier is fast and transparent. If the graph grows toward tens of millions of edges, swap the backend (e.g., CSR or a KV store) behind the same interface without changing runner semantics or user-facing behavior.

**Families recap.** WorldGraph stores only `pred:*`, `cue:*`, and `anchor:*`. The controller may compute `drive:*` **flags** for triggers, but they are never written into the graph unless you explicitly add `pred:drive:*` or `cue:drive:*`.





***Q&A to help you learn this section***

Q: How are edges stored?   
A: On the source binding in an adjacency list: each edge is `{to, label, meta}`.

Q: Do we dedupe edges?   
A: The design allows multiple edges, the UI warns if you add an identical labeled edge so you can skip duplicates.

Q: What labels should I use?   
A: `"then"` for episode flow,  you can add others like `approach`, `search`, `latch`, `suckle` to clarify intent.

Q: How does NOW behave?   
A: It’s a named binding used as the plan start and orientation point in the runner and visualizations.

Q: Why a deque?   
A: O(1) `popleft()` for BFS frontiers (lists would be O(n) for `pop(0)`).



**Drives, Policies, and the Action Center:**

The controller tracks simple drives (hunger, fatigue, warmth). Policies consume those signals and look for tags in the WorldGraph or context to decide whether to act. The Action Center asks policies in a fixed order “are you ready? ” and executes the first one that returns true.

Example (stand up):

* Trigger: standing is not already true, body is not severely fatigued.
* Execute: create a `pred:stand` binding, connect from LATEST (or NOW) with label `initiate_stand`, then follow‑on edges `then` into chronological progression.

Design decision (ADR-0002 folded in): Policies are intentionally small and readable. We avoid global planning for every step to keep the code explainable and the UI responsive. Guards in `trigger()` prevent repeated firing (e.g., don’t stand up twice if standing exists).

Design decision (ADR-0008 folded in): If a drive source cannot publish tag predicates for some reason, the system should continue running, policies degrade gracefully by relying on tags already in the graph.



***Q&A to help you learn this section***
Q: How is an action chosen each tick?   
A: The Action Center scans policies in a fixed order and runs the first whose `trigger()` returns True given current drives/tags.

Q: What prevents re-firing the same action?   
A: Guards in `trigger()` (e.g., StandUp checks that standing isn’t already true).

Q: What does a policy return?   
A: A small status dict (policy name, ok/fail/noop, reward, notes) and it stamps provenance on any binding it creates.

Q: What if drive predicates aren’t available?   
A: Policies degrade gracefully by relying on existing graph tags, the system keeps running.





**Persistence (snapshots):**

A session snapshot is a JSON file that contains: the world graph (bindings + edges + internal counters), drives, minimal skill telemetry, and small context items. Saving is atomic, loading restores indices and advances the id counter so new bindings don’t collide with old ids.

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
A: JSON keeps sessions portable and debuggable, binary would be smaller but opaque.





**Runner, menus, and CLI:**

You can explore the graph via an interactive menu. Relevant items:

* Display snapshot (prints bindings, edges, drives, optionally exports an interactive graph).
* Add predicate (creates a node with a `pred:*` tag, you can attach it to NOW or LATEST to auto‑link chronology).
* Connect two bindings (adds a directed edge, the UI warns if the same labeled edge already exists).
* Plan from NOW to a predicate (prints ids and a pretty path).

Design decision (ADR-0004 folded in): The runner offers a quick‑exit `--plan <token>` flag when you only need to compute a plan once and exit. The menu shows a short “drives” view because drives are central to policy triggers.

Design decision (ADR-0007 folded in): Attachment semantics are explicit and lowercase: `attach="now"`, `attach="latest"`, or `"none"`. This removes ambiguity when auto‑wiring the newest binding into the episode chain.

***Q&A to help you learn this section***

Q: What are the most useful menu items while learning?   
A: Display snapshot, Add predicate, Connect two bindings, Plan from NOW, and the interactive graph export.

Q: Is there a quick way to visualize the graph?   
A: Yes—export an interactive HTML graph from the menu, labels can show `id`, `first_pred`, or both.

Q: Why does the menu warn about duplicate edges?   
A: To avoid clutter when auto-attach already created the same `(src, label, dst)` relation.

Q: Can I skip the menu and just plan?   
A: Use `--plan pred:<token>` from the CLI for a one-shot plan.



## Logging & Unit Tests

###### Logging (minimal, already enabled)

The runner initializes logging once at startup:

Version:1.0StartHTML:0000000105EndHTML:0000040966StartFragment:0000038726EndFragment:0000040926<style></style>

The runner initializes logging once at startup:

- Writes to **`cca8_run.log`** (UTF-8) and also echoes tothe console.

- One INFO line per run (version, Python, platform).

- You can expand logging later by sprinkling`logging.info(...)` / `warning(...)` where useful.

**Change level or file:**

Edit `cca8_run.py` in `main(...)` where`logging.basicConfig(...)` is called.

**Tail the log while you run (Windows PowerShell):**

Get-Content .\cca8_run.log -Wait

Unit tests (pytest)

We keep tests under tests/.

Preflight runs pytest first (so failures stop you early).

Stdout from tests is captured by default; enable prints byrunning pytest with -s (see below).

Run preflight (will run tests first):

Copy code

python cca8_run.py --preflight

Run tests directly (show prints):

Copy code

pytest -q -s

Included starter tests:

tests/test_smoke.py — basic sanity (asserts True).

tests/test_boot_prime_stand.py — seeds stand near NOW andasserts a path NOW → pred:stand exists.



---

## Executive Overview

CCA8 aims to simulate early mammalian cognition with a **small symbolic episode index** (the *WorldGraph*) coordinating **rich engrams** (perceptual/temporal content) in a column provider. Symbols are used for **fast indexing & planning**, not as a full knowledge store.

**Core mental model:**

- **Predicate** — a symbolic fact token (e.g., `state:posture_standing`). Atomic.  
- **Binding** — a node instance that *carries* one or more tags, including `pred:<token>`, plus `meta` and optional `engrams`.  
- **Edge** — a directed link between bindings with a label (often `"then"`) representing **weak, episode-level causality** (“in this run, this led to that”).  
- **WorldGraph** — the directed graph composed of these bindings and edges, supports **BFS planning**.  
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

* `14` Autonomic tick once or twice, then `D` Show drives (aim for `drive:hunger_high`).

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

Q: Why keep the symbolic graph small?  A: For fast indexing/planning, heavy content lives in engrams.

Q: Which primitives form “standing”?  A: action:push_up, action:extend_legs, state:posture_standing.

Q: Where is provenance stored?  A: binding.meta.policy = "policy:<name>".
Q: What’s the planner algorithm?  A: BFS from NOW to the first pred:<token> match.



***Q&A to help you learn the above sections:***

Q: What’s the key separation in CCA8?  A: A compact symbolic episode index** (WorldGraph) for fast lookup/plan, and rich engrams** outside the graph for heavyweight content.

Q: Are edges logical implications?  A: No—edges encode weak, episode-level causality** (“then”), good for action and recall without heavy inference.

Q: Why not store everything in the graph? A: Keeping symbols small avoids brittleness and keeps planning fast, the heavy 95% lives in engrams referenced by bindings.

Q: How does this help planning? A: BFS over a sparse adjacency list gives shortest-hop paths quickly, the graph is shaped for that.

---

## Theory Primer

- **Weak causality:** Mammalian episodes often encode **soft** chains (“this happened, then that”), sufficient for immediate action without formal causal inference. In CCA8, edges labeled `"then"` capture this episode flow.
- **Two-store economy:** Keep the **symbolic graph small** (~5%): tags & edges for **recall and planning**. Keep the **heavy content** (~95%) in engrams (features, traces, sensory payloads). This avoids the brittleness of “all knowledge in a graph.”
- **From pre-causal to causal:** The symbolic skeleton is compatible with later, stronger causal reasoning layered above (e.g., annotating edges with conditions, failure modes, or learned utilities).
  
  

***Q&A to help you learn this section***

Q: Define “weak causality.” A: Soft episode links (“then”) without asserting logical necessity.

Q: Why engrams vs symbols?  A: Symbols = fast index, engrams = heavy content → avoids brittle all-graph designs.

Q: Can we add stronger causal reasoning later?  A: Yes, layered above (edge annotations, utilities).

---

Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)
-------------------------------------------------------------------------------------

This section standardizes how we name and store information in the WorldGraph so planning stays simple, policies remain readable, and snapshots are easy to inspect.

### Why we say “binding” (not just node)

A **binding** is a small “episode card” that _binds_ together:

* lightweight **symbols** (tags: predicates, cues, anchors),

* pointers to **engrams** (rich memory stored outside the graph),

* and **provenance/meta** (who/when/why).

“Binding” emphasizes that we’re recording a coherent moment with attached facts and references, not just a graph vertex.

### What a binding contains

* **id** — `b<number>`; referenced by edges.

* **tags: list[str]** — the symbolic labels for this moment (see families below).

* **engrams: dict** _(optional)_ — pointers to rich content (e.g., `{ "column01": {"id": "...", "act": 1.0} }`).

* **meta: dict** _(optional)_ — provenance & light context (e.g., `{"policy": "policy:stand_up", "t": 123.4}`).

* **edges: list[{"to": id, "label": str, "meta": dict}]** _(optional)_ — directed links from this binding (adjacency list).

### Tag families (use exactly these)

Keep families distinct so humans (and the planner) never have to guess.

1. **Predicates — states/goals/events you might plan _to_**
   
   * **Prefix:** `pred:`
   
   * **Purpose:** targets for planning and state description.
   
   * **Examples:**  
     `pred:born`, `pred:posture:standing`, `pred:locomotion:running`,  
     `pred:mom:close`, `pred:nipple:found`, `pred:nipple:latched`, `pred:milk:drinking`,  
     `pred:event:fall_detected`, `pred:goal:safe_standing`.

> The planner looks for `pred:*`. The **first** `pred:*` (if present) is used as the human label in pretty paths/exports.

2. **Cues — evidence/context you _notice_, not goals**
   
   * **Prefix:** `cue:`
   
   * **Purpose:** sensory/context hints for policy `trigger()` logic.
   
   * **Examples:**  
     `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:silhouette:mom`, `cue:terrain:rocky`, `cue:tilt:left`.

> We **do not** plan to cues; they’re conditions that help decide which policy fires.

3. **Anchors — orientation markers**
   
   * **Prefix:** `anchor:` (e.g., `anchor:NOW`).
   
   * Also recorded in the engine’s `anchors` map, e.g., `{"NOW": "b1"}`.
   
   * A binding can be _only_ an anchor (no `pred:*`) — that’s fine.
   
   * 

4. **Drive-derived tags — pred:drive:* or cue:drive:***  
   **Only three stored families:** `pred:*`, `cue:*`, and `anchor:*`. Any bare `drive:*` you see is a **controller flag** (ephemeral) and is not stored in the graph.
   We standardize as:
   
   * **Project default:** use **`pred:drive:*`** for drive conditions that matter to planning (e.g., `pred:drive:hunger_high`).
   
   * **Optional alternative (if you prefer purely as conditions):** use **`cue:drive:*`** when the drive threshold is only a trigger and never a plan target.
   
   * **Do not** use bare `drive:*` in tags; prefer one of the two forms above.

### Actions = edge labels (transitions)

* The **edge** from `src → dst` bears the action name in its `label`.  
  Examples: `then`, `search`, `latch`, `suckle`, `approach`, `recover_fall`, `run`, `stabilize`.

* Put **quantities** about the action (e.g., meters, duration, success) in **`edge.meta`**, not in tags:
  `{ "to": "b101", "label": "run", "meta": {"meters": 8.5, "duration_s": 3.2, "created_by": "policy:locomote"} }`

* **Planner behavior today:** edge labels are **readability metadata**; BFS follows structure (not names). Labels may later inform costs/filters.

### Provenance & engrams

* **Provenance:**
  
  * Binding creator: `binding.meta["policy"] = "policy:<name>"`
  
  * Edge creator: `edge.meta["created_by"] = "policy:<name>"`

* **Engrams:**
  
  * Only pointers live on the binding: `binding.engrams["column01"] = {"id": "...", "act": 1.0}`
  
  * The large payloads live outside WorldGraph (resolved via column provider).

### Naming style (predicates & cues)

* Use **lowercase, colon-separated** segments: `pred:locomotion:running`.

* Prefer **2–3 segments** for clarity; avoid very deep chains:
  
  * `pred:mom:location:north_forest` (ok)
  
  * `pred:location:mom:north_forest` (also ok)  
    Choose one pattern and stay consistent within a domain.

* If you might search by a broader class later, consider adding a second umbrella tag (e.g., `pred:location:mom:northish`) when useful.

### Invariants checklist

* Every binding has a unique **id** (`bN`).

* **Edges are directed**; stored on the **source** binding’s `edges[]`. A binding without edges is a valid **sink**.

* **Anchors** (e.g., NOW) exist and point to real binding ids (they may also carry `anchor:*` tags).

* The **first `pred:*`** (if present) is used as the node label in UIs; fallback is the `id`.

* Snapshots restore `latest`, anchors, and advance the id counter past loaded ids.

### Vocabulary starter table

| Family     | Examples                                                                                                                                                           | Purpose                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `pred:`    | `pred:born`, `pred:posture:standing`, `pred:nipple:latched`, `pred:milk:drinking`, `pred:event:fall_detected`, `pred:goal:safe_standing`, `pred:drive:hunger_high` | planner targets; human labels        |
| `cue:`     | `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:silhouette:mom`, `cue:terrain:rocky`, `cue:tilt:left`                                                                | policy triggers; not planner goals   |
| `anchor:`  | `anchor:NOW`, `anchor:HERE`                                                                                                                                        | orientation; also in `anchors` map   |
| Edge label | `then`, `search`, `latch`, `suckle`, `approach`, `recover_fall`, `run`                                                                                             | action/transition; metrics in `meta` |

### Do / Don’t

* Use **one** predicate prefix: `pred:*` for states/goals/events (and drives, per project default above).

* Keep **cues** separate (`cue:*`), used by policies (not planner goals).

* Put creator/time/notes in **`meta`**; put action measurements in **`edge.meta`**.

* Allow anchor-only bindings (e.g., `anchor:NOW`).

* Don’t mix `state:*` and `pred:*` (pick `pred:*`).

* Don’t encode rich data in tags; use **engrams** for large payloads.

#### Q&A

**Q: Can a binding exist with only an anchor and no predicate?**  
A: Yes. Anchors (e.g., `anchor:NOW`) are bindings and don’t require a `pred:*`.

**Q: Can a binding exist with only a cue and no predicate?**  
A: Yes. It’s valid for a cue-only moment; just remember you **can’t plan to a cue**.

**Q: How do I record that “running happened”?**  
A: Put it on the **edge label** (e.g., `--run-->`) and any measurements in `edge.meta`. If you also want a plannable “running” state, add `pred:locomotion:running` as the destination binding label.

**Q: Do we allow duplicate edges?**  
A: The structure allows them; the UI warns on exact duplicates of `(src, label, dst)` so you can skip unintended repeats.

**Q: Which tag shows up as the node’s label?**  
A: The **first `pred:*`** tag; otherwise we fall back to the binding id.



* * *

Here’s a drop-in section for your README. I recommend placing it **immediately after “Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)” and before “Data schemas (for contributors)”**, and adding it to the Table of Contents as:

* `Restricted Lexicon (Developmental Vocabulary)`

* * *

Restricted Lexicon (Developmental Vocabulary)
---------------------------------------------

Early mammals don’t start life with an unlimited conceptual vocabulary. Following the spirit of **Spelke’s core knowledge** (a constrained, structured set of early abilities), CCA8 introduces a **restricted lexicon** for tags at early developmental stages and then **unlocks** a broader vocabulary as the agent “matures.” The goal is to keep symbols clean, avoid tag drift, and make early planning/search tractable and biologically plausible.

### Why we constrain early vocabulary

* **Developmental realism.** Neonates have a small, structured set of capacities (posture, proximity, feeding milestones, a few salient cues). The lexicon mirrors this and scales up later.

* **Software hygiene.** Constraining tags prevents ad-hoc token variations (e.g., `pred:standing`, `pred:posture_standing`, `pred:posture:standing`) from creeping in.

* **Search simplicity.** A smaller, consistent tag set makes paths/states easier to debug and keeps the fast index coherent.

* * *

### How it works (user view)

* **Stages.** The world tracks a developmental **stage** (`"neonate"`, `"infant"`, `"juvenile"`, `"adult"`). Stages are **cumulative**: later stages include all earlier tokens.

* **Automatic stage setting.** The runner derives the stage from `ctx.age_days` (toy rule: `<= 3.0 → neonate`, otherwise infant). This happens right after profile selection and after each autonomic tick (so the stage follows age).

* **Enforcement policy.** Creation-time checks use one of:
  
  * `"allow"` — accept any tag silently.
  
  * `"warn"` (default) — accept out-of-lexicon or legacy tags but print a short warning.
  
  * `"strict"` — reject out-of-lexicon tags with an error.

* **Legacy tokens.** A small **legacy map** accepts older forms (e.g., `state:posture_standing`) while **suggesting** the canonical form (`posture:standing`). This keeps old snapshots workable while you migrate.

**Everyday behavior you’ll notice:**

* When you **add** a predicate/cue in early life, it is checked against the stage vocabulary. In `"warn"` mode you’ll see a one-line hint if the token is off-lexicon (still accepted). In `"strict"` mode you’ll get a clear error.

* Planning, pretty-printing, autosave, etc., are unchanged; the lexicon guards **creation**, not reading.

* * *

### How to adjust the vocabulary

* **Add tokens to a stage.** Edit the stage sets in `TagLexicon.BASE[...]` (inside `cca8_world_graph.py`). New tokens added under `"infant"` (or higher) automatically become available after the agent “grows” into that stage.

* **Rename/normalize tokens.** Put old → new mappings in `TagLexicon.LEGACY_MAP`. Old tags are still accepted; a warning suggests the canonical form until you finish migration.

* **Change stage thresholds.** Update `WorldGraph.set_stage_from_ctx(ctx)` (e.g., change the age rule or read a profile flag).

* **Adjust enforcement.** Call `world.set_tag_policy("allow"|"warn"|"strict")`. During development you can start with `"warn"`, switch to `"strict"` when the vocabulary stabilizes.

* * *

### Technical notes (what’s under the hood)

* **`TagLexicon` (in `cca8_world_graph.py`)**
  
  * `STAGE_ORDER = ("neonate","infant","juvenile","adult")` — later stages include earlier tokens.
  
  * `BASE[stage][family]` — preferred tokens per **family** (`pred`, `cue`, `anchor`) and **stage**.
  
  * `LEGACY_MAP` — accepts legacy tokens (e.g., `state:posture_standing`) and suggests the canonical form (`posture:standing`).
  
  * Methods:
    
    * `is_allowed(family, token, stage)` — “Is this token ok at this stage?”
    
    * `preferred_of(token)` — returns canonical name if token is legacy.

* **`WorldGraph` integration**
  
  * Initialization wires the lexicon and defaults the stage to `"neonate"` and policy to `"warn"`.
  
  * Stage helpers:
    
    * `set_stage(stage)` — explicitly set stage.
    
    * `set_stage_from_ctx(ctx)` — derive from `ctx.age_days` (runner calls this after profile selection and after each autonomic tick).
    
    * `set_tag_policy("allow"|"warn"|"strict")` — choose enforcement.
  
  * Enforcement hook:
    
    * `add_predicate(...)` and `add_cue(...)` normalize input (`pred:`/`cue:` prefixes), then call a private `_enforce_tag(...)`. In `"warn"` it logs once and allows; in `"strict"` it raises `ValueError`.

* **Preflight coverage (no warning noise).** Preflight exercises attach semantics, action metrics, and BFS with temporary worlds set to `"allow"` (so runs are quiet), and separately verifies `"strict"` on an intentionally illegal token. You’ll still see a clean PASS wall.

* * *

### What’s currently in the neonate vocabulary (starter set)

* **`pred:` posture/proximity/feeding**
  
  * `posture:standing`, `posture:fallen`
  
  * `proximity:mom:close`, `proximity:mom:far`
  
  * `nipple:found`, `nipple:latched`, `milk:drinking`
  
  * `seeking_mom`
  
  * “action-like” states we currently model as predicates: `action:push_up`, `action:extend_legs`, `action:orient_to_mom`
  
  * (Optional) `drive:hunger_high` if you intend to **plan to** a drive threshold

* **`cue:` sensory/context**
  
  * `vision:silhouette:mom`, `scent:milk`, `sound:bleat:mom`
  
  * `vestibular:fall`, `touch:flank_on_ground`, `balance:lost`
  
  * (Optional) `drive:hunger_high` if used only as a **trigger**

* **`anchor:`** `NOW`, `HERE`

You can expand `"infant"` and later stages as you add tasks (e.g., navigation landmarks, social signals).

* * *

### Quick usage examples

* **Set the stage automatically (runner):**
  
      world.set_stage_from_ctx(ctx)     # after profile selection and after autonomic tick
      world.set_tag_policy("warn")      # start permissive; flip to "strict" when stable

* **Add a canonical predicate (neonate-ok):**
  
      world.add_predicate("posture:standing", attach="latest")

* **Add a cue (neonate-ok):**
  
      world.add_cue("vision:silhouette:mom", attach="now")

* **Accept an old snapshot silently (warn today, migrate later):**
  
      # legacy 'state:posture_standing' is accepted; warning suggests 'posture:standing'
  
  

* * *

### FAQ (restricted lexicon)

**Does this break old runs?**  
No. Legacy tokens are accepted; in `"warn"` you’ll see a one-line hint suggesting the canonical form. Switch to `"strict"` after you migrate.

**Will planning fail because of the lexicon?**  
No. The lexicon checks **creation** time. Planner behavior (BFS over existing tags) is unchanged.

**Can I silence warnings during automated checks?**  
Yes. Use temporary worlds with `set_tag_policy("allow")` inside tests/preflight. The codebase already does this for its synthetic preflight tokens.

**How do I add a new domain (e.g., landmarks)?**  
Add tokens under the appropriate stage in `TagLexicon.BASE` (and `LEGACY_MAP` if you’re renaming), then adjust your policies to emit/check the new tokens.



* * *

Signal Bridge (WorldGraph ↔ Engrams)
------------------------------------

Early animals do not decide purely in symbols; spatial/visual structure in perception strongly shapes behavior. In CCA8, **WorldGraph** is the fast symbolic index (states, cues, anchors, transitions), while **columns/engrams** hold richer scene-like data (vectors, features, metadata). The **signal bridge** connects the two without committing to heavy perception yet:

* **Emit** a lightweight scene/cue into the column (creates an **engram** and returns its id).

* **Attach** the engram id back to the current binding in **`binding.engrams`** (pointer only).

* **Fetch** the engram later for inspection or analytics.

This lets you keep planning/search **simple and fast** while still recording a **traceable link** to the perception that motivated a step.

* * *

### What the bridge does now (and near-term path)

**Implemented now (lightweight, safe):**

* Create a binding (`pred:*` or `cue:*`) and **assert** a tiny engram record in the column memory.

* Store only a **pointer** on the binding:
  
      "engrams": {
        "column01": { "id": "<engram_id>", "act": 1.0, "meta": {…optional…} }
      }

* Retrieve the full column record by id for debugging/analytics.

**Soon (drop-in extensions, no format change):**

* Search **similar** engrams (nearest neighbors) to bias which policy fires.

* Enrich payloads (e.g., multi-modal features) while keeping the binding pointer small.

* Summaries in UI/HTML (e.g., show engram ids or small stats in tooltips).

* * *

### How to use it (menu)

From the runner:

1. **Capture scene → emit cue/predicate with tiny engram** (menu **24**):
   
   * Choose **channel** (`vision/scent/sound/touch`), **token** (e.g., `silhouette:mom`), **family** (`cue` or `pred`), **attach** (`now/latest/none`), and an optional vector (e.g., `0.1, 0.2, 0.3`).
   
   * The runner prints the created binding id and the attached **engram id**.
   
   * “Display snapshot” lists **engrams=[column01]** on that binding; “Inspect binding details” shows the pointer JSON.
   
   * Pyvis HTML shows the node; hover for tags/meta. (Labels fall back to **cue** when no `pred:*` is present.)

2. **Resolve engrams on a binding** (existing menu): enter a binding id (e.g., `b9`) to dump its `engrams` map.

Tip: Attach mode matters for episode wiring—`now` will add `NOW → new` (label `then`) and update LATEST; `latest` attaches from the previous LATEST; `none` creates a floating binding (valid sink).

* * *

### Technical details (what lives where)

**On the binding (WorldGraph):**

* `tags` — symbols (`pred:*`, `cue:*`, `anchor:*`)

* `edges` — transitions (edge `label` is the action; measurements in `edge.meta`)

* **`engrams`** — pointer(s) only:
  
      {
        "column01": {
          "id": "<engram_id>",
          "act": 1.0,
          "meta": { "...optional..." }
        }
      }
  
  

**In the column (engram store):**

* A small record keyed by `engram_id`, typically containing a **payload** and/or metadata.

* For “scene” captures we create a tiny numeric payload (vector) and optional descriptors (links/attrs).

* Heavy data stays **out** of WorldGraph; you only carry the id.

**Bridge API (inside `WorldGraph`):**

* `attach_engram(bid, column="column01", engram_id, act=1.0, extra_meta=None)`  
  Attach an existing engram pointer to a binding.

* `get_engram(column="column01", engram_id)`  
  Fetch the column record by id (read-only).

* `emit_pred_with_engram(token, payload=None, name=None, column="column01", attach="now", links=None, attrs=None, meta=None) -> (bid, engram_id)`  
  Create a **predicate** binding and assert an engram in one call; attach the pointer.

* `emit_cue_with_engram(cue_token, payload=None, name=None, column="column01", attach="now", links=None, attrs=None, meta=None) -> (bid, engram_id)`  
  Same as above for a **cue** binding.

* `capture_scene(channel, token, vector, attach="now", family="cue", name=None, links=None, attrs=None) -> (bid, engram_id)`  
  Convenience wrapper: builds a tiny scene payload (vector) and calls the appropriate emit function.
  
  * **family**: `cue` (default) or `pred`
  
  * **attach**: `now/latest/none`

**Column functions (internal):**

* `cca8_column.mem.assert_fact(name, payload, fact_meta) -> engram_id`

* `cca8_column.mem.get(engram_id) -> dict`

**Features helpers (optional):**

* `cca8_features.TensorPayload`, `cca8_features.FactMeta` — typed wrappers for payload and metadata; the bridge gracefully falls back to plain dicts if these are unavailable.

* * *

### Example workflows

**A. Cue + scene pointer (vision silhouette, neonate)**
    menu 24 → channel=vision, token=silhouette:mom, family=cue, attach=now

* Creates `bX: [cue:vision:silhouette:mom]`

* Adds `NOW --then--> bX`

* Attaches `engrams["column01"].id = <engram_id>`

* (Optional) a policy may react (e.g., orient or follow)

**B. Predicate + scene pointer (if plannable state)**
    menu 24 → family=pred, token=location:mom:north_forest, attach=latest

* Creates a `pred:*` node (ensure the token is allowed by the restricted lexicon for the current stage)

* Records an engram id for later inspection; planning can now **target** the predicate token.

* * *

### Notes & guardrails

* The **restricted lexicon** still applies at creation time. In neonates, `cue:vision:silhouette:mom` is allowed; off-lexicon tokens print a warn (or raise in `strict` mode).

* Keep payloads **small** (vectors, light descriptors). Use the column to store/compute heavier structures; the binding only needs the pointer.

* Planning/search is **unchanged**: BFS uses tags/edges; the bridge does not slow down the fast index.

* Provenance remains visible: bindings created by a policy stamp `binding.meta["policy"]`; engrams created via the bridge store their **id** in the binding pointer and a record in the column memory.
  
  
  
  

#### Q&A — Signal Bridge (WorldGraph ↔ Engrams)

**Q: Why store only a pointer on the binding instead of the full scene?**  
A: To keep the **fast index** small and predictable. Bindings carry lightweight symbols for planning; the **heavy payloads** (tensors, features, frames) live in the column. A pointer preserves traceability without slowing graph operations.

**Q: Does the bridge change how planning works today?**  
A: No. Planning is still **BFS over bindings/edges**. The bridge adds provenance to perception (via pointers) but does not alter search or path cost.

**Q: When should I emit a `cue:*` vs a `pred:*` with an engram?**  
A: Use **`cue:*`** when the scene is **evidence** for policy triggers (not a goal). Use **`pred:*`** when the scene defines a **state you may plan to** (e.g., `pred:location:mom:north_forest`).

**Q: How do I see that a binding has an engram attached?**  
A: In **Display snapshot**, you’ll see `engrams=[column01]` on that binding; in **Inspect binding details** you’ll see the pointer JSON, e.g.  
`"column01": {"id": "<engram_id>", "act": 1.0, "meta": {...}}`.

**Q: How do I retrieve the actual engram record?**  
A: The bridge provides `get_engram(engram_id=...)`. The column returns the full record (payload + descriptors) so you can inspect data shape, kind, links, etc.

**Q: Can a binding point to more than one engram?**  
A: Yes. The `engrams` map is **column-name → pointer**. You can attach multiple columns (e.g., `column01`, `column_vision`, `column_audio`) to the same binding.

**Q: What does `act` (activation) in the pointer represent?**  
A: A lightweight scalar you can use as a confidence/strength hint. It does not affect planning; it’s there for downstream analytics or heuristics.

**Q: What happens if the column entry is missing or cannot be found?**  
A: The binding remains valid (it only stores a pointer). `get_engram(...)` will raise an error; you can handle it to report a broken pointer and continue.

**Q: How is this used from the menu today?**  
A: Use **menu 24** (“Capture scene → emit cue/predicate with tiny engram”). It creates a cue/predicate, asserts an engram in the column, and attaches the pointer—everything in one step.

**Q: How do I attach an existing engram id to a binding?**  
A: Call `attach_engram(bid, column="column01", engram_id=...)`. This is useful when a policy or external tool computed an engram beforehand.

**Q: Does the restricted lexicon still apply when using the bridge?**  
A: Yes. The **creation-time** check still enforces stage-appropriate tokens (`neonate/infant/...`). Use `cue:*` tokens that are allowed at the current stage, or switch to `strict` mode to catch mistakes early.

**Q: How will similarity search or value estimates plug in later?**  
A: The pointer makes it easy: a future call (e.g., `search_similar(engram_id)`) can fetch nearest neighbors in the column and return candidate bindings or hints for policy arbitration—without disrupting WorldGraph’s structure.

**Q: Can I show engram details in the HTML visualization?**  
A: Tooltips already display tags/meta; you can extend them to include **engram keys** or a short id preview if you’d like (cosmetic change in the exporter).

**Q: Any guidance on payload size?**  
A: Keep payloads **small** (tiny vectors, short descriptors). The bridge is meant for quick linking; large arrays should stay in the column (and be summarized when displayed).

**Q: What’s the minimal recommended pattern when adding perception today?**  
A: (1) Emit a `cue:*` that captures the gist (e.g., `cue:vision:silhouette:mom`), (2) attach a tiny scene vector through the bridge, (3) let policies read the cue and stamp provenance; planning remains structure-first.

* * *



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

1. Action Center computes active **drive flags**.  
2. Scans **policies** in order, first `trigger()` that returns True **fires**.  
3. `execute()` appends a **small chain** of predicates + edges to the WorldGraph, stamps `meta.policy`, returns a status dict, and updates the skill ledger.  
4. Planner (on demand) runs BFS from **NOW** to a target `pred:<token>`.  

---

## Action Selection: Drives, Policies, Action Center

- **Policies** are small classes with:
  
  - `trigger(world, drives) -> bool`  
  - `execute(world, ctx, drives) -> {"policy", "status", "reward", "notes"}`

- **Ordered list** `PRIMITIVES = [StandUp(), SeekNipple(), FollowMom(), ExploreCheck(), Rest(), ...]`.  
   Updated: `PRIMITIVES = [StandUp(), SeekNipple(), Rest(), FollowMom(), ExploreCheck(), ...]`  
  ( code now evaluates **Rest before FollowMom**.)

- **Action Center** runs the **first** policy whose `trigger` is True.  

- **StandUp guard:** `StandUp.trigger()` checks for an existing `pred:state:posture_standing` to avoid “re-standing” every tick.

**Status dict convention:**  
`{"policy": "policy:<name>" | None, "status": "ok|fail|noop|error", "reward": float, "notes": str}`



##### Policy ordering & fairness

Policies are evaluated in a fixed order to keep behavior explainable. If two policies could fire on the same tick, the one earlier in the list wins that tick, the other will get a chance later if its trigger remains true. For fairness in long runs, you can:

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
  Both yield shortest paths in unweighted graphs, stop-on-pop tends to produce cleaner logs because the pop order matches the BFS layers.

##### Frontier semantics (one line mental model)

The frontier is the **FIFO queue of discovered-but-not-expanded nodes**. A node is marked “discovered” at **enqueue time**, never enqueue a discovered node again. This invariant prevents cycles from causing duplicates.

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

### Planner: BFS vs Dijkstra (weighted edges)

**What’s available**

- **Default = BFS** (fewest edges/hops).

- **Dijkstra** (optional) computes the **lowest total edge weight**; uses the same API and return type as BFS (`WorldGraph.plan_to_predicate(...)` returns a list of binding ids).
  In the real world, pathways from node to node are not at the same advantage or cost, and we end up using weighted edges past the neonatal state very quickly.

**Edge weights**

- Each directed edge can carry metadata; cost is read in this priority:
  `weight` → `cost` → `distance` → `duration_s` → **1.0** (fallback).
- If you don’t set any weights, Dijkstra and BFS usually produce the same path.

**Switching planners**

- **Interactive**: menu item **25) Planner strategy (toggle BFS ↔ Dijkstra)** (if your runner exposes it).

- **Environment**:
  
  - Windows (cmd):  
    `set CCA8_PLANNER=dijkstra && python cca8_run.py --plan goal:whatever`
  - macOS/Linux (bash/zsh):  
    `CCA8_PLANNER=dijkstra python3 cca8_run.py --plan goal:whatever`

- **In code**:
  
  ```python
  world.set_planner("dijkstra")    # or "bfs"
  current = world.get_planner()
  ```

## Persistence: Autosave/Load

- Snapshot file (JSON) includes:
  
  ```jsonc
  {"saved_at": "...", "world": {...}, "drives": {...}, "skills": {...}}
  ```

- **Autosave:** `--autosave session.json` writes after each completed action (atomic replace). Overwrites prior file if same name.

- **Load:** `--load session.json` restores world/drives/skills, id counter advances to avoid `bNN` collisions.

- **Fresh start:** Use a new filename, delete/rename old file, or load a non-existent file (runner continues with a fresh session and starts saving after first action).

##### Atomic writes & recovery

Snapshots are written via **atomic replace**: write to a temp file in the same directory and rename over the old snapshot. If a crash occurs mid-write, the old file remains intact. On load:

1. Parse JSON safely, if it fails, print a clear error with the path and keep the process alive so the user can save to a new file.

2. Validate minimal invariants (`anchors`, `latest`, `bN` shape). If any are missing, reconstruct conservative defaults and continue (prefer a live session to a hard fail).

##### Versioning the shape

Include a small `{"version": "0.7.x"}` under `world`. If you add fields later, bump this string and keep best-effort compatibility in `from_dict()`—log a one-liner describing any defaulted fields so users know what changed.



***Q&A to help you learn this section***

Q: What does autosave write?  A: {saved_at, world, drives, skills}.

Q: How do we avoid id collisions after load?  A: from_dict() advances the internal bNN counter.

Q: Missing --load file?  A: Continue fresh, file created on first autosave.
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

Menu → **11** → channel `vision`, cue `mom:close` → creates `cue:vision:mom:close` (depending on your input normalization).
Note: menu **11** adds a **cue** not a pred.

### Show drives (raw + tags)

Menu → **D** → prints numeric drives and active **drive flags** (`drive:*`, ephemeral)



##### Export an interactive graph with readable labels

From the main menu choose **22) Export interactive graph (Pyvis HTML)**, then:

* **Node label mode** → `id+first_pred` (shows both `bN` and the first predicate).

* **Edge labels** → `Y` for small graphs, `n` for big graphs to reduce clutter.

* **Physics** → `Y` unless the graph is very large.  
  Open the saved HTML in your browser and hover nodes/edges for tooltips, the NOW anchor is highlighted to orient you.

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



Note: only numeric levels are persisted. **Drive flags** (`drive:*`) are ephemeral controller signals and are not stored in the snapshot. If you need persisted drive state, write `pred:drive:*` (or `cue:drive:*`) explicitly.

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

* `tags` is a list of strings, at least one tag for a “stateful” node should be a `pred:*` token (e.g., `pred:stand`).

* `meta.policy` records provenance (which policy created the node), `meta` can hold timestamps or light context.

* `engrams` holds **pointers** to rich content (stored outside the WorldGraph).

### Edge (directed link)

Edges are stored **on the source binding** in its `edges[]` list, forming a classic adjacency list.
    { "to": "b43", "label": "then", "meta": {} }

**Conventions (edge):**

* `to` is the destination binding id.

* `label` is a short relation name. Use `"then"` for episode flow, feel free to add domain labels (e.g., `approach`, `search`, `latch`, `suckle`) when helpful.

* Multiple edges between the same pair are allowed if labels differ, the UI warns when you attempt to add an identical `(src, label, dst)` edge.

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

* **Labels & pretty print:** when displaying paths or graphs, the first `pred:*` tag is used as a human label if present, otherwise the id is shown.
  
  

#### Why edges live on the source binding (design rationale)

Storing edges on the source binding gives:

* **O(1) neighbor iteration** for BFS (no global lookups needed).

* **Locality of reasoning:** everything needed to “expand” a node is on that node.

* **Simple persistence:** the snapshot is a direct dump of each binding’s edges.  
  The trade-off is that reverse lookups (who points _to_ `bK`?) require scanning or a small auxiliary index, in practice we only need forward edges for planning.
  
  

***Q&A to help you learn this section***

Q: What’s inside a Binding?  A: id, tags, edges[], meta, engrams.

Q: How are edges stored?  A: On the source binding as {"to", "label", "meta"}.

Q: One drive:* flag example?  A: drive:hunger_high (hunger > 0.6).
(This is an ephemeral controller flag; for persisted use, write `pred:drive:hunger_high`.)

Q: A skill stat besides n?  A: succ, q, or last_reward.

Q: Where do edges live relative to nodes?  A: On the source binding, inside its `edges[]` list. That’s the adjacency list the planner traverses.

Q: Are duplicate edges allowed? A: The structure allows them, but the UI warns when an identical `(src, label, dst)` already exists so you can skip duplicates.

Q: Which tag shows as the node label in UIs? A: The first `pred:*` tag if present, otherwise the binding id.

Q: How does the loader avoid `bNN` collisions after a load? A: It advances `next_id` past the highest numeric suffix seen in `bindings`.

Q: Do I need to add an edge for a terminal node? A: No. A binding with an empty (or missing) `edges` list is a valid sink.

Q: What makes a predicate “atomic”?A: It’s a single namespaced token (`pred:…`) carried by a binding, we don’t decompose it further inside the graph.

Q: One concrete example of provenance?A: `meta.policy = "policy:stand_up"` on the standing binding created by the StandUp policy.

Q: What is the “skill ledger”?A: Lightweight per-policy stats (counts, success, running q, last reward) to support analytics or future RL.

* * *

Tutorial on WorldGraph, Bindings, Edges, Tags and Concepts
----------------------------------------------------------

This tutorial introduces the mental model behind WorldGraph and shows how to encode experience in a way that stays simple for planning, clear for humans, and easy to maintain. It complements the “Tagging Standard” and “WorldGraph in detail” sections by walking through the why and how with concrete, domain-flavored examples.

### 1) Mental model at a glance

WorldGraph is a compact, symbolic **episode index**. Each “moment” is captured as a small record (a **binding**) that carries tags and optional pointers to richer memory (**engrams**). **Edges** connect moments to show how one led to another. Planning is graph search over those edges from a temporal **anchor** called **NOW** toward a goal predicate.

A readable example path:
    born --then--> wobble --stabilize--> posture:standing --suckle--> milk:drinking

Here the words on the nodes are **predicates** (states), and the words on the arrows are **actions** (edge labels). The generic label `then` just means “and then this happened.”

* * *

### 2) Why “bindings” and not just “nodes”?

A binding is more than a vertex. It **binds** together:

* lightweight symbols (**tags**) that describe the moment (predicates you can plan to, cues you noticed, and anchors),

* **engrams** that point to richer content stored outside WorldGraph (e.g., a column or feature store),

* **provenance** in **meta** (who/when/why this binding was created),

* and outgoing **edges** that encode how we moved forward.

“Binding” emphasizes that this is an episode card—a snapshot you can read and understand—rather than an abstract graph point.

* * *

### 3) What a binding contains (shape and invariants)

Every binding is identified by an id like `b42`. Conceptually it looks like:
    id: "b42"
    tags: [ ... ]                  # strings; families are pred:*, cue:*, anchor:*
    engrams: { ... }               # pointers to rich memory outside WorldGraph
    meta: { ... }                  # provenance and light notes (e.g., policy that created it)
    edges: [                       # directed adjacency (stored on the source)
      { "to": "b43", "label": "then", "meta": { "created_by": "policy:..." } },
      ...
    ]

Invariants that keep the graph healthy:

* ids are unique (`bN`);

* edges are directed and live on the **source** binding (adjacency list);

* a binding with no edges is a valid **sink**;

* the **first** `pred:*` tag (if present) is used as the node label in pretty paths/exports; fallback is the id;

* the engine keeps a small `anchors` map, e.g., `{"NOW": "b1"}`.

* * *

### 4) Tags: predicates, cues, anchors (and drive thresholds)

Use exactly these families (see the Tagging Standard for full details):

* **pred:** states/goals/events you may plan to  
  Examples: `pred:posture:standing`, `pred:nipple:latched`, `pred:milk:drinking`, `pred:event:fall_detected`, `pred:goal:safe_standing`.

* **cue:** evidence or context you noticed (conditions for policy triggers; not planning targets)  
  Examples: `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:terrain:rocky`, `cue:tilt:left`.

* **anchor:** orientation markers (e.g., `anchor:NOW`, `anchor:HERE`)  
  The anchors map is authoritative (`anchors["NOW"]=...`); the tag is recommended for readability.

* **Drive thresholds:** pick one convention and be consistent  
  Default in this project: `pred:drive:hunger_high` if the condition is plannable;  
  Alternative: `cue:drive:hunger_high` if it is strictly a trigger for policies.

Style tips:

* keep tokens lowercase and colon-separated (`pred:locomotion:running`);

* keep depth to two or three segments when possible (`pred:mom:close` is usually better than a long chain);

* if you might search by a broader class later, you can add a second umbrella tag (e.g., `pred:location:mom:northish`) alongside a specific one.

* * *

### 5) Edges: actions and transition metadata

* The **edge label** is the action name (plain string): `then`, `search`, `latch`, `suckle`, `approach`, `recover_fall`, `run`, `stabilize`, etc.

* **Quantities** about the action (e.g., distance, duration, success) belong in **`edge.meta`**, not in tags. For example:
  
      { "to": "b101", "label": "run",
        "meta": {"meters": 12.0, "duration_s": 5.0, "speed_mps": 2.4, "created_by": "policy:locomote"} }

* The planner today **ignores labels for correctness** (it follows structure), so labels serve readability and analytics. They can later inform costs (Dijkstra/A*) or filters (“avoid recover_fall”).

* The runner warns if you try to add an **exact duplicate** `(src, label, dst)` edge.

* * *

### 6) Anchors and orientation (NOW, HERE, and housekeeping)

* **NOW** is the temporal anchor used by the runner and planner as the default starting point. The **map** `anchors["NOW"]=...` is the source of truth; the tag `anchor:NOW` on the binding is for human-friendly display.

* It is valid for a binding to be **anchor-only** (no predicate or cue). It is also valid for a binding to combine an anchor with predicates and/or cues.

* You can “move” NOW by updating the anchors map. A helper like `set_now(bid, tag=True, clean_previous=True)` re-points the map, adds `anchor:NOW` to the new binding and removes it from the previous one (so you don’t end up with two bindings tagged as NOW).

* Optional anchors (used if helpful): `HERE` (spatial rather than temporal), `SESSION_START`, `CHECKPOINT_*`. Only NOW has semantics in the current runner.

* * *

### 7) Planning (how goals are recognized; why BFS works well here)

* Planning starts from the binding id referenced by **NOW**.

* The algorithm is classic **Breadth-First Search** with **visited-on-enqueue** (don’t enqueue a node twice) and **stop-on-pop** (the first time you pop a goal, you have a shortest-hop path).

* The **goal test** is: “do this binding’s tags contain the exact token `pred:<token>`?” If yes, reconstruct the path via the parent map and return it.

* Because edges are unweighted, BFS is the right tool and guarantees fewest edges. If you later introduce costs, switch to Dijkstra/A*; labels and/or context can determine edge costs.

Practical effect: when you type `pred:milk:drinking` as your goal, the planner will stop when it pops the first binding whose tags include that token, and return the shortest-hop path from NOW.

* * *

### 8) Adding new states and wiring them (attach semantics)

When you add a new predicate, you can choose how to **attach** it:

* `attach="latest"`: add a `then` edge from the current LATEST to the new binding, then update LATEST to the new binding.

* `attach="now"`: add a `then` edge from NOW to the new binding, then update LATEST to the new binding.

* `attach="none"`: create the binding with no auto-edge; LATEST still updates to the new binding.

Nuances:

* If NOW == LATEST, `attach="now"` and `attach="latest"` behave the same.

* Auto-attachments help you build an episode spine quickly; you can name the transition (e.g., `search`, `latch`) instead of using the generic `then` when helpful.

* * *

### 9) Style choices for state: snapshot vs delta

Two workable styles exist; pick one and stay consistent.

* **Snapshot-of-state (recommended):** each binding is a full current state. Carry stable invariants forward (e.g., still standing, still close), and **replace** transient milestones (e.g., drop `pred:nipple:found` once `pred:nipple:latched` is true).  
  Pros: every binding is self-describing; planning and debugging are easier.

* **Delta/minimal:** each binding adds only what changed (e.g., add `found`, later add `latched`) and omits repeated invariants.  
  Pros: fewer tags; cons: harder to interpret a single node without its history.

* * *

### 10) Worked examples (no code, just structure)

#### 10.1 Smell of milk (policy trigger, not a plan target)

* Current binding tags add: `cue:scent:milk`.

* Rationale: cues are evidence for policies. Policies may then consider seeking mom or searching for nipple depending on other context. We do not plan to `cue:*`.

#### 10.2 Running with measurements (action on the edge)

* Source binding: `pred:posture:standing`, `pred:proximity:mom:far`.

* Destination binding: `pred:posture:standing`, `pred:proximity:mom:close`.

* Transition: `--run-->` with `edge.meta = {meters: 12.0, duration_s: 5.0, speed_mps: 2.4, created_by: ...}`.

* Optional: if “running” is a state you sometimes plan to, insert an intermediate `pred:locomotion:running` node; otherwise keep it on the edge.

#### 10.3 Nipple found → latched (milestone to state)

* From standing/far to “found”:
  
  * Add binding `pred:nipple:found`, `pred:posture:standing`, `pred:proximity:mom:close`.
  
  * Edge: `--search-->` from the previous binding.

* From “found” to “latched”:
  
  * Add binding `pred:nipple:latched`, keep posture/proximity as appropriate.
  
  * Edge: `--latch-->` from the “found” binding.

* Style note: on the “latched” binding, you generally don’t need to keep `pred:nipple:found` unless you explicitly want milestone redundancy.

#### 10.4 Fall and recovery (two transitions)

* Standing → Fallen: edge `--fall-->`, destination tags `pred:posture:fallen`.

* Fallen → Recovered standing: edge `--stand_up-->` (or `recover_fall`), destination tags `pred:posture:standing`.

* If you record timing, use a standard key like `duration_s` in `edge.meta` (e.g., time to stand again).

#### 10.5 Hunger high as a trigger (not a goal)

* Add `cue:drive:hunger_high` to the current binding.

* Rationale: a trigger for policies to act (seek mom, search, etc.). If you ever want to plan to that condition instead, emit `pred:drive:hunger_high`—but avoid using both forms at the same time.

* * *

### 11) Isolated bindings and anchors (and when they’re useful)

* It’s valid to create **isolated anchors** (e.g., NOW with no edges yet). Planning will fail until wiring exists; that’s expected during construction.

* It’s valid to create **isolated bindings** with cues or predicates and wire them later (e.g., a received message as a cue).

* Avoid long-lived **tagless** bindings: they’re hard to interpret. If you must create a placeholder, give it a minimal tag (`pred:event:placeholder` or `cue:import:pending`) or a clear meta note.

* Reusing an old binding to “return to the same state” collapses time; generally prefer a fresh binding, even if the tags match, so the episode remains chronological.

* * *

### 12) Inspecting and explaining the graph

* **Pretty paths:** the runner prints both a path of ids and a readable line like  
  `b3[born] --then--> b4[wobble] --stabilize--> b5[posture:standing] --suckle--> b6[milk:drinking]`.  
  Place the tag you want to show first in the binding’s tag list.

* **Interactive HTML (Pyvis):** export an HTML graph from the menu; choose label mode `id+first_pred` while developing so you see both id and the first predicate. NOW is highlighted as a box.

* **Action summaries:** summarize action labels across the graph and (optionally) aggregate simple metrics like `duration_s` or `meters` to check data quality and get a quick feel for what happened.

* * *

### 13) Common pitfalls and quick fixes

* **“No path found”**: verify the exact goal token (`pred:...`), check that edges form a forward chain from NOW, watch for reversed edges (`B→A` when you meant `A→B`).

* **Duplicate edges**: the UI warns on exact duplicate `(src,label,dst)`; accept different labels (`then` vs `search`) if intentional.

* **Tagless bindings**: add at least one predicate, cue, or anchor so snapshots and exports stay readable.

* **Two NOW tags**: if you move the anchor, remove `anchor:NOW` from the previous binding (the helper can do this).

* * *

### 14) Quick reference (cheat sheet)

* Use `pred:*` for states/goals/events (and, by project default, plannable drive thresholds).

* Use `cue:*` for evidence/conditions that policies react to; you do not plan to cues.

* Use `anchor:*` for orientation markers; the anchors map is authoritative.

* Edge labels are actions; keep measurements in `edge.meta`.

* Prefer the **snapshot-of-state** style; drop stale milestones and carry stable invariants.

* NOW is the default start for planning; LATEST updates when you add a new binding.

* It’s okay to build the episode spine with `then` labels; add named actions where it improves clarity.

* * *

### 15) Short FAQ

**Q: Can a binding be only an anchor?**  
Yes. `anchor:NOW` alone is valid; you can combine anchors with predicates/cues when helpful.

**Q: Can a binding be only a cue?**  
Yes. Useful for a “noticed” moment you may wire later. You cannot plan to a cue.

**Q: How do I record that “running happened” with distance/time?**  
Label the edge `run` and put numbers in `edge.meta` (e.g., `meters`, `duration_s`, `speed_mps`). If you also want a plannable state, add `pred:locomotion:running`.

**Q: Do edge labels change planning outcomes today?**  
No. They’re readability/analytics metadata. Planning follows structure. Later you can map labels to costs and use Dijkstra/A*.

**Q: Should I reuse an earlier binding when I return to the same state?**  
Prefer a new binding (e.g., `standing` again) to preserve chronology. Reusing the old one collapses time.

**Q: Where are policies and learning kept?**  
Policies live in the controller, not in WorldGraph. Provenance is stamped into `meta`. Learning hooks (skill ledger, edge costs) can be layered without changing the graph format.



* * *

# Tutorial on WorldGraph Technical Features

This tutorial teaches you how to **build, inspect, and reason about the WorldGraph**—the symbolic fast index that sits at the heart of CCA8. It’s written for developers new to the codebase.

***Note: Code changes will occur over time,  but the main ideas below should remain stable with the project***

* * *

### 1. Purpose of `cca8_world_graph.py`

`cca8_world_graph.py` implements the **symbolic episode index**:

* **Bindings** = nodes (episode cards) that hold tags, meta, and optional engram pointers.

* **Edges** = directed links (`src → dst`) with labels like `"then"`, `"search"`, `"suckle"`.

* **Anchors** = named bindings (e.g., `NOW`) used as temporal reference points.

* **Planner** = BFS (or Dijkstra) search from `NOW` to the first `pred:<token>` goal.

The file also enforces a **restricted developmental lexicon** (`TagLexicon`) and provides `to_dict()` / `from_dict()` for JSON persistence.

* * *

### 2. Key Classes and What They Do

| Class            | Purpose                                                                                                                 |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **`Edge`**       | A `TypedDict` describing one outgoing link: `{"to": str, "label": str, "meta": dict}`                                   |
| **`Binding`**    | A `dataclass(slots=True)` representing one node in the episode graph. Fields: `id`, `tags`, `edges`, `meta`, `engrams`. |
| **`TagLexicon`** | Defines allowed tokens by developmental stage (neonate→adult). Enforces `allow/warn/strict` policy.                     |
| **`WorldGraph`** | The main engine: manages all bindings, edges, anchors, planning, persistence, and lexicon enforcement.                  |

* * *

### 3. Simplifying the Type Hints

You’ll often see:
    self.allowed: dict[str, dict[str, set[str]]] = {}

Read this **inside-out**:

> mapping of `<stage>` → `<family>` → `<set of tokens>`

Example:
    {
      "neonate": {
         "pred": {"posture:standing", "milk:drinking"},
         "cue":  {"vision:silhouette:mom"},
         "anchor": {"NOW"}
      }
    }

Use this mental model whenever you meet deeply nested hints.

* * *

### 4. Creating Bindings (Nodes)

| Tag type                      | Method                                              | Example                                       |
| ----------------------------- | --------------------------------------------------- | --------------------------------------------- |
| **Anchor**                    | `ensure_anchor("NOW")`                              | creates or returns the NOW binding            |
| **Predicate**                 | `add_predicate("posture:standing", attach="now")`   | auto-links from NOW                           |
| **Cue**                       | `add_cue("vision:silhouette:mom", attach="latest")` | links from latest predicate                   |
| **Tagless (not recommended)** | `add_binding(set())`                                | creates an unlabeled node; skip in normal use |

Each new predicate or cue updates the internal pointer `_latest_binding_id`.

* * *

### 5. Automatic vs Manual Linking

| Method                      | Effect                                 |
| --------------------------- | -------------------------------------- |
| `attach="now"`              | Adds edge `NOW → new` (`label="then"`) |
| `attach="latest"`           | Adds edge `<previous latest> → new`    |
| `attach="none"`             | Creates unlinked node                  |
| `add_edge(src, dst, label)` | Manual link (e.g., `"stand"`)          |

**Example:**
    g = WorldGraph()
    now = g.ensure_anchor("NOW")
    a = g.add_predicate("posture:fallen", attach="none")
    b = g.add_predicate("posture:standing", attach="none")
    g.add_edge(a, b, label="stand")
    print(g.plan_pretty(a, "posture:standing"))
    # → b3[posture:fallen] --stand--> b4[posture:standing]

* * *

### 6. The Lexicon (Tag Enforcement)

The lexicon constrains vocabulary per developmental stage.
    g.set_stage("neonate")
    g.set_tag_policy("warn")  # allow, warn (default), or strict

* In `warn` mode, out-of-lexicon tokens print a one-line warning.

* In `strict` mode, they raise `ValueError`.

* Later stages include all earlier tokens.

**Quick test:**
    g.add_predicate("posture:jumping", attach="latest")
    # WARN [tags] pred:posture:jumping not allowed at stage=neonate (allowing)

* * *

### 7. Planning

The planner searches from a start node (usually NOW) to the first binding whose tags include `pred:<token>`.
    path = g.plan_to_predicate(now, "posture:standing")
    print(path)                     # ['b1','b2']
    print(g.plan_pretty(now, "posture:standing"))
    # b1(NOW) --then--> b2[posture:standing]

Under the hood:

* BFS → unweighted (fewest edges)

* Dijkstra → weighted (`meta["weight"]`, `cost`, `distance`, or `duration_s`)

Switch planners:
    g.set_planner("dijkstra")
    print(g.get_planner())  # 'dijkstra'

* * *

### 8. Exercises (with solutions)

**Exercise 1 – Manual edge**
    a = g.add_predicate("posture:fallen", attach="none")
    b = g.add_predicate("posture:standing", attach="none")
    g.add_edge(a, b, "stand")
    print(g.plan_pretty(a, "posture:standing"))

✅ _Output:_ `b3[posture:fallen] --stand--> b4[posture:standing]`

* * *

**Exercise 2 – Auto chain**
    g = WorldGraph()
    g.ensure_anchor("NOW")
    g.add_predicate("posture:standing", attach="now")
    g.add_predicate("posture:jumping", attach="latest")
    print(g.plan_pretty("b1", "posture:jumping"))

✅ _Output:_ `b1(NOW) --then--> b2[posture:standing] --then--> b3[posture:jumping]`

* * *

**Exercise 3 – Lexicon policy test**
    g.set_stage("neonate")
    g.set_tag_policy("strict")
    try:
        g.add_predicate("posture:jumping", attach="latest")
    except ValueError as e:
        print("Caught:", e)

✅ _Output:_ `Caught: [tags] pred:posture:jumping not allowed at stage=neonate`

* * *

### 9. Engrams (Pointers to Rich Memory)

Bindings can reference “heavy” sensory or temporal data via a small pointer:
    g.attach_engram("b2", column="column01", engram_id="engr_123", act=0.9)
    eng = g.get_engram("b2", column="column01")

Planner ignores engrams; they’re for analytics or linking perception.

* * *

### 10. Invariants & Best Practices

| Invariant                                      | Why it matters                          |
| ---------------------------------------------- | --------------------------------------- |
| Every binding has a unique id (`bN`).          | Keeps planning stable.                  |
| Edges are stored on the **source** binding.    | Local adjacency = O(1) neighbor lookup. |
| Anchors map names (`NOW`) to real ids.         | Planning start points.                  |
| `latest` tracks the most recent predicate/cue. | Auto-attach works correctly.            |
| The first `pred:*` tag is used as label.       | Keeps graph readable.                   |

* * *

### 11. Quick Reference Summary

| Concept              | Code / Description                                    |
| -------------------- | ----------------------------------------------------- |
| **Create world**     | `g = WorldGraph()`                                    |
| **Add anchor**       | `now = g.ensure_anchor("NOW")`                        |
| **Add predicate**    | `g.add_predicate("posture:standing", attach="now")`   |
| **Add cue**          | `g.add_cue("vision:silhouette:mom", attach="latest")` |
| **Manual edge**      | `g.add_edge(src, dst, "search")`                      |
| **Plan**             | `g.plan_pretty(now, "pred:milk:drinking")`            |
| **Save**             | `snap = g.to_dict()`                                  |
| **Load**             | `g2 = WorldGraph.from_dict(snap)`                     |
| **Check invariants** | `g.check_invariants()`                                |
| **Export HTML**      | `g.to_pyvis_html()`                                   |

* * *

### 12. Common Pitfalls

| Symptom           | Likely cause                                | Fix                                     |
| ----------------- | ------------------------------------------- | --------------------------------------- |
| `"No path"`       | predicate not created or disconnected       | check edges and direction               |
| duplicate edges   | created manually _and_ by attach            | remove one or ignore warning            |
| multiple NOW tags | forgot `clean_previous=True` in `set_now()` | use helper to tidy                      |
| lexicon error     | `strict` mode, off-vocab token              | switch to `warn` or add token to `BASE` |

* * *

### 13. Minimal Code Snippet

    from cca8_world_graph import WorldGraph
    
    g = WorldGraph()
    g.set_tag_policy("allow")
    
    now = g.ensure_anchor("NOW")
    g.add_predicate("posture:standing", attach="now")
    g.add_predicate("posture:jumping", attach="latest")
    
    print(g.plan_pretty(now, "posture:jumping"))
    # NOW --then--> standing --then--> jumping

* * *

Core instance attributes and methods for WorldGraph Module
================================

******Note: Code changes will occur over time, but the main ideas below should remain stable with the project***



* `_bindings: dict[str, Binding]` — all nodes by id (e.g., `"b7" → Binding(...)`).

* `_anchors: dict[str, str]` — anchor name → binding id (e.g., `"NOW" → "b1"`).

* `_latest_binding_id: str | None` — most recently created predicate/cue binding.

* `_id_counter: itertools.count` — id generator for `"b<N>"`.

* `_lexicon: TagLexicon` — stage/family vocab + legacy map.

* `_stage: str` — `"neonate" | "infant" | "juvenile" | "adult"`.

* `_tag_policy: str` — `"allow" | "warn" | "strict"`.

* `_plan_strategy: str` — `"bfs" | "dijkstra"`.

(Module constants you’ll see used: `_ATTACH_OPTIONS = {"now","latest","none"}`.)
Public API (call these)
=======================

| Method                    | Parameters (types)                                                                          | Returns                                                                                             | Purpose                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `__init__`                | `()`                                                                                        | `None`                                                                                              | Initialize empty world; set counters, lexicon, defaults.                         |
| `set_stage`               | `(stage: str)`                                                                              | `None`                                                                                              | Set developmental stage for lexicon checks.                                      |
| `set_stage_from_ctx`      | `(ctx)`                                                                                     | `None`                                                                                              | Derive stage from `ctx.age_days` (toy thresholds).                               |
| `set_tag_policy`          | `(policy: str)`                                                                             | `None`                                                                                              | Lexicon enforcement: allow/warn/strict.                                          |
| `set_planner`             | `(strategy: str = "bfs")`                                                                   | `None`                                                                                              | Choose `"bfs"` or `"dijkstra"`.                                                  |
| `get_planner`             | `()`                                                                                        | `str`                                                                                               | Current planner strategy.                                                        |
| `ensure_anchor`           | `(name: str)`                                                                               | `str` (binding id)                                                                                  | Ensure anchor exists (e.g., `"NOW"`), return its id; tags node `anchor:<NAME>`.  |
| `set_now`                 | `(bid: str, *, tag: bool = True, clean_previous: bool = True)`                              | `str                                                                                                | None`                                                                            |
| `add_binding`             | `(tags: set[str], *, meta: dict                                                             | None = None, engrams: dict                                                                          | None = None)`                                                                    |
| `add_predicate`           | `(token: str, *, attach: str                                                                | None = None, meta: dict                                                                             | None = None, engrams: dict                                                       |
| `add_cue`                 | `(token: str, *, attach: str                                                                | None = None, meta: dict                                                                             | None = None, engrams: dict                                                       |
| `attach_engram`           | `(bid: str, *, column: str = "column01", engram_id: str, act: float = 1.0, extra_meta: dict | None = None)`                                                                                       | `None`                                                                           |
| `get_engram`              | `(bid: str, *, column: str = "column01")`                                                   | `dict                                                                                               | None`                                                                            |
| `add_edge`                | `(src_id: str, dst_id: str, label: str, meta: dict                                          | None = None, *, allow_self_loop: bool = False)`                                                     | `None`                                                                           |
| `delete_edge`             | `(src_id: str, dst_id: str, label: str                                                      | None = None)`                                                                                       | `int`                                                                            |
| `plan_to_predicate`       | `(src_id: str, token: str)`                                                                 | `list[str]                                                                                          | None`                                                                            |
| `plan_pretty`             | `(src_id: str, token: str, **kwargs)`                                                       | `str`                                                                                               | Convenience: plan then pretty-print (or `"(no path)"`).                          |
| `pretty_path`             | `(ids: list[str]                                                                            | None, *, node_mode: str = "id+pred", show_edge_labels: bool = True, annotate_anchors: bool = True)` | `str`                                                                            |
| `list_actions`            | `(*, include_then: bool = True)`                                                            | `list[str]`                                                                                         | All distinct edge labels (optionally excluding `"then"`).                        |
| `action_counts`           | `(*, include_then: bool = True)`                                                            | `dict[str, int]`                                                                                    | Count of edges per label.                                                        |
| `edges_with_action`       | `(label: str)`                                                                              | `list[tuple[str, str]]`                                                                             | (Src, dst) pairs whose edge label matches.                                       |
| `action_metrics`          | `(label: str, *, numeric_keys: tuple[str, ...] = ("meters","duration_s","speed_mps"))`      | `dict`                                                                                              | Simple metrics from `edge.meta` for a given label.                               |
| `action_summary_text`     | `(label: str                                                                                | None = None)`                                                                                       | `str`                                                                            |
| `to_pyvis_html`           | `(*, physics: bool = True, node_mode: str = "id+pred")`                                     | `str` (HTML)                                                                                        | Quick visualization export.                                                      |
| `to_dict`                 | `()`                                                                                        | `dict`                                                                                              | Snapshot of the episode (bindings, anchors, latest).                             |
| `from_dict` (classmethod) | `(data: dict)`                                                                              | `WorldGraph`                                                                                        | Rehydrate; advances id-counter above max existing `"b<N>"`.                      |
| `check_invariants`        | `(*, raise_on_error: bool = True)`                                                          | `list[str]`                                                                                         | Validate: NOW exists & tagged, latest exists, all edges point to existing nodes. |

Internal helpers (private by convention)
========================================

| Helper                        | Parameters                                   | Purpose                                                                                      |
| ----------------------------- | -------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `_init_lexicon`               | `()`                                         | Create `TagLexicon`, set default stage/policy.                                               |
| `_enforce_tag`                | `(family: str, token_local: str) -> str`     | Apply lexicon policy (allow/warn/strict); return stored token-local form (no family prefix). |
| `_next_id`                    | `() -> str`                                  | Generate `"b<N>"` from internal counter.                                                     |
| `_edge_cost`                  | `(e: Edge) -> float`                         | Weight: `meta['weight'] → 'cost' → 'distance' → 'duration_s' → 1.0`.                         |
| `_plan_to_predicate_dijkstra` | `(src_id: str, target_tag: str) -> list[str] | None`                                                                                        |
| `_iter_edges`                 | `()`                                         | Yield `(src, dst, edge_dict)` for valid edges.                                               |
| `_first_pred_of`              | `(bid: str) -> str                           | None`                                                                                        |
| `_anchor_name_of`             | `(bid: str) -> str                           | None`                                                                                        |
| `_edge_label`                 | `(src: str, dst: str) -> str                 | None`                                                                                        |

* * *

`Edge` (TypedDict)
------------------

* Shape: `{"to": str, "label": str, "meta": dict}`

* Purpose: stored on the **source** `Binding` to represent a directed edge and its label/metrics.

* Example:
    e: Edge = {"to": "b7", "label": "stand", "meta": {"duration_s": 2.5}}

`Binding` (dataclass, `slots=True`)
-----------------------------------

Fields:

* `id: str` — e.g., `"b42"`.

* `tags: set[str]` — e.g., `{"pred:posture:standing"}` or `{"anchor:NOW"}`.

* `edges: list[Edge]` — outgoing edges.

* `meta: dict` — provenance/context.

* `engrams: dict` — small pointers into column memory.

Helpers:
    b_dict = b.to_dict()
    b2 = Binding.from_dict(b_dict)
`TagLexicon`

------------

* Class attrs (constants):  
  `STAGE_ORDER = ("neonate","infant","juvenile","adult")`  
  `BASE: dict[stage][family] -> set[str]` (allowed tokens per stage & family)  
  `LEGACY_MAP: dict[str, str]` (legacy → preferred)

* Instance:
  
  * `self.allowed: dict[str, dict[str, set[str]]]` (cumulative per stage)
  
  * Methods:
    
    * `is_allowed(family, token, stage) -> bool`
    
    * `preferred_of(token) -> str | None`
    
    * `normalize_family_and_token(family, raw) -> (family, local_token)`
      
      * E.g., `("pred", "pred:state:posture_standing") -> ("pred", "state:posture_standing")`

Cheat-sheet: `WorldGraph` core state
====================================

* `_bindings: dict[str, Binding]`

* `_anchors: dict[str, str]` (e.g., `"NOW" -> "b1"`)

* `_latest_binding_id: str | None`

* `_id_counter: itertools.count` (`"b<N>"` ids)

* `_lexicon: TagLexicon`

* `_stage: str` (`"neonate"` …)

* `_tag_policy: str` (`"allow"|"warn"|"strict"`)

* `_plan_strategy: str` (`"bfs"|"dijkstra"`)

Cheat-sheet: `WorldGraph` public API
====================================

Lifecycle & config

* `WorldGraph()` — empty graph, stage=`neonate`, policy=`warn`, planner from `CCA8_PLANNER` env (default `bfs`).

* `set_stage(stage: str)` / `set_stage_from_ctx(ctx)`

* `set_tag_policy(policy: str)` — `"allow"|"warn"|"strict"`

* `set_planner(strategy: str = "bfs")` / `get_planner() -> str`

Anchors & orientation

* `ensure_anchor(name: str) -> str` — create/get anchor binding (tags it `anchor:<NAME>`).

* `set_now(bid: str, *, tag=True, clean_previous=True)` — repoint the NOW anchor; tidy tags.

Nodes

* `add_predicate(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Creates `pred:<token>` node; updates `latest`.
  
  * `attach="now"|"latest"|"none"` → auto-edge (NOW→new) or (latest→new) or none.

* `add_cue(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Same semantics; creates `cue:<token>`; updates `latest`.

* `add_binding(tags: set[str], *, meta=None, engrams=None) -> str`
  
  * Low-level constructor (prefer the helpers above).

Edges & actions

* `add_edge(src_id: str, dst_id: str, label: str, meta: dict|None = None, *, allow_self_loop=False) -> None`

* `delete_edge(src_id: str, dst_id: str, label: str|None = None) -> int` (returns removed count)

Planning & display

* `plan_to_predicate(src_id: str, token: str) -> list[str]|None`
  
  * Uses `bfs` (default) or `dijkstra` depending on `get_planner()`.

* `pretty_path(ids: list[str]|None, *, node_mode="id+pred", show_edge_labels=True, annotate_anchors=True) -> str`

* `plan_pretty(src_id: str, token: str, **kwargs) -> str` — convenience: plan + pretty.

Actions / metrics

* `list_actions(*, include_then=True) -> list[str]`

* `action_counts(*, include_then=True) -> dict[str, int]`

* `edges_with_action(label: str) -> list[tuple[str, str]]`

* `action_metrics(label: str, *, numeric_keys=("meters","duration_s","speed_mps")) -> dict`

* `action_summary_text(label: str|None = None) -> str`

Persistence / checks / viz

* `to_dict() -> dict`

* `from_dict(data: dict) -> WorldGraph` (class method; advances id counter above max `"b<N>"`)

* `check_invariants(*, raise_on_error: bool = True) -> list[str]`

* `to_pyvis_html(*, physics: bool = True, node_mode: str = "id+pred") -> str`

Minimal usage crib (copy/paste friendly)
========================================

0) Start a world

----------------

    from cca8_world_graph import WorldGraph
    g = WorldGraph()
    g.set_tag_policy("allow")  # keep lexicon quiet while learning
    now = g.ensure_anchor("NOW")

1) Add predicates / cues (with auto-edges)

------------------------------------------

    b1 = g.add_predicate("posture:standing", attach="now")     # NOW -> b1
    b2 = g.add_cue("vision:silhouette:mom", attach="latest")   # b1 -> b2
    print(g.plan_pretty(now, "posture:standing"))              # NOW -> b1

2) Manual action edges

----------------------

    fallen = g.add_predicate("posture:fallen", attach="none")
    stand  = g.add_predicate("posture:standing", attach="none")
    g.add_edge(fallen, stand, label="stand", meta={"duration_s": 3.2})
    print(g.plan_pretty(fallen, "posture:standing"))  # fallen --stand--> standing

3) Auto-chain timeline with `attach="latest"`

---------------------------------------------

    a = g.add_predicate("state:alert", attach="latest")
    b = g.add_predicate("seeking_mom", attach="latest")
    c = g.add_predicate("nipple:found", attach="latest")
    print(g.plan_pretty(now, "nipple:found"))  # NOW -> ... -> c

4) Planner choice (BFS vs Dijkstra)

-----------------------------------

    print(g.get_planner())   # 'bfs'
    g.set_planner("dijkstra")
    print(g.get_planner())   # 'dijkstra'

5) Action inspection

--------------------

    print(g.list_actions())               # ['stand', 'then', ...]
    print(g.action_counts())              # {'stand': 1, 'then': 4, ...}
    print(g.action_metrics("stand"))      # aggregates edge.meta for 'stand'
    print(g.action_summary_text())        # readable summary of actions

6) Persistence (save / load)

----------------------------

    snap = g.to_dict()
    # ... write to JSON if you like ...
    g2 = WorldGraph.from_dict(snap)       # id counter advanced above max b<N>

7) Sanity checks

----------------

    issues = g.check_invariants(raise_on_error=False)
    print(issues)  # [] when all good

8) Pretty printing options

--------------------------

    path = g.plan_to_predicate(now, "seeking_mom")
    print(g.pretty_path(path, node_mode="id+pred", show_edge_labels=True))
    # variants: node_mode='id' or 'pred'; annotate_anchors=True/False

9) Engram bridge (lightweight pointer)

--------------------------------------

    bid = g.add_predicate("state:alert", attach="latest")
    g.attach_engram(bid, column="column01", engram_id="engr_123", act=0.9, extra_meta={"note": "demo"})
    print(g.get_engram(bid, column="column01"))



* * *

Tutorial on Breadth-First Search (BFS) Used by the CCA8 Fast Index
------------------------------------------------------------------

This tutorial explains the exact BFS discipline the CCA8 planner uses over the WorldGraph’s adjacency list. It is written to be followed with pencil-and-paper; no code is required.

BFS is deliberately simple: a queue, a parent map, and two rules (visited-on-enqueue, stop-on-pop). In CCA8 this simplicity pays off—planning remains predictable and fast, and the returned paths are immediately readable against the episode structure.

### What BFS is doing for CCA8

* **Goal:** find a **shortest-hop** path (fewest edges) from a start binding (by default, the **NOW** anchor) to any binding whose tags contain the requested **`pred:<token>`**.

* **Why BFS:** WorldGraph edges are **unweighted**. BFS guarantees the first time you pop a node (remove it from the left of the queue) you have reached it by a shortest number of edges.

* **Data you maintain while running BFS:**
  
  * **Frontier** — a **FIFO queue** (think `deque`) of nodes discovered but not yet expanded.
  
  * **Expanded** — the set of nodes already popped/processed.
  
  * **Parent** — a discovery map `{child: parent}` that doubles as the **visited** set.

**Rules used here (and by CCA8):**  
**Visited-on-enqueue** (never enqueue a node that already appears in `parent`) and **Stop-on-pop** (return as soon as the goal node is popped).

* * *

### Worked example (hand simulation)

**Adjacency (directed; neighbor order matters):**

* S → [A, B]

* A → [C, D]

* B → [D, E]

* C → [G]

* D → [E, A] _(cycle back to A)_

* E → [G]

* G → []

**Start:** S  **Goal:** G

We will record the **three buckets** at each step:

* `frontier = [...]`

* `expanded = {…}`

* `parent = {child: parent, ...}`

#### Initial state

`frontier = [S] expanded = {} parent   = {S: None}`

#### Step 1 — pop S, enqueue S’s neighbors

Neighbors in order: A, B.

`frontier = [A, B] expanded = {S} parent   = {S: None, A: S, B: S}`

#### Step 2 — pop A, enqueue A’s neighbors

Neighbors: C, D.

`frontier = [B, C, D] expanded = {S, A} parent   = {S: None, A: S, B: S, C: A, D: A}`

#### Step 3 — pop B, enqueue B’s neighbors

Neighbors: D, E.  
D is already in `parent` (visited-on-enqueue), so **skip D**; enqueue only E.

`frontier = [C, D, E] expanded = {S, A, B} parent   = {S: None, A: S, B: S, C: A, D: A, E: B}`

#### Step 4 — pop C, enqueue C’s neighbors

Neighbor: G (the goal). Enqueue it.

`frontier = [D, E, G] expanded = {S, A, B, C} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

#### Step 5 — pop D, enqueue D’s neighbors

Neighbors: E, A. Both already discovered; **skip**.

`frontier = [E, G] expanded = {S, A, B, C, D} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

#### Step 6 — pop E, enqueue E’s neighbors

Neighbor: G (already discovered); **skip**.

`frontier = [G] expanded = {S, A, B, C, D, E} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

#### Step 7 — pop G (goal)

We are using **stop-on-pop**: the moment G is popped, we stop.

**Final buckets:**

`frontier = [] expanded = {S, A, B, C, D, E, G} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

> Note: With **visited-on-enqueue**, you never actually hold duplicate entries like `[G, E, G]` in the frontier. The second `G` would have been skipped at discovery.

* * *

### Reconstructing the shortest path

Use the **parent** map to walk backward from the goal to the start, then reverse:

* `G ← C ← A ← S` → reverse → **`S → A → C → G`**

**Path length (edges):** 3.

There is also an equally short route **`S → B → E → G`**. BFS returns the first shortest path it pops; **neighbor order** determines which one appears.

* * *

### Distances and BFS layers

Compute distances (in edges) from `S` by layer:

* `dist(S) = 0`

* `dist(A) = 1`, `dist(B) = 1`

* `dist(C) = 2`, `dist(D) = 2`, `dist(E) = 2`

* `dist(G) = 3`

Layers (by distance):

* **L0:** {S}

* **L1:** {A, B}

* **L2:** {C, D, E}

* **L3:** {G}

**Why BFS guarantees shortest paths:** the frontier (a queue) ensures you completely explore **Lk** before touching **Lk+1**. When a node at **Lk+1** is first popped, there cannot exist a path with fewer than `k+1` edges to it that you haven’t already discovered.

* * *

### Neighbor order and tie-paths

If you swap the order at S to `[B, A]`, you will still find a shortest path of length 3, but the **pop order** and the **returned path** may differ (e.g., via `B → E → G`). BFS correctness doesn’t change; only the specific shortest path chosen among equals may change.

* * *

### Cycles and correctness

The edge `D → A` introduces a cycle. **Visited-on-enqueue** prevents re-enqueuing already discovered nodes, so BFS never loops. This is the standard cycle-safety discipline.

* * *

### Stop-on-pop vs. Stop-on-discovery

Both conventions produce correct shortest paths in an unweighted graph:

* **Stop-on-pop** (used here): simpler logs; the pop order matches layers.

* **Stop-on-discovery**: returns as soon as the goal is enqueued; also correct but may be slightly less intuitive when you read queue traces.

CCA8 uses **stop-on-pop**.

* * *

### How this maps to CCA8 planning

* **Start node:** the binding id referenced by the **NOW** anchor.

* **Goal test:** “do the tags of this popped binding contain the exact token `pred:<token>`?”

* **Path reconstruction:** backtrack with `parent` to NOW, then reverse.

* **Frontier implementation:** a `deque` for O(1) `popleft()`; never re-enqueue a node once it appears in `parent`.

**Practical example:** To plan toward milk drinking, set NOW as your start and request the goal token `pred:milk:drinking`. The first binding popped that carries this tag ends the search; the reconstructed path is a shortest-hop route from NOW.

* * *

### Common pitfalls (and quick fixes)

* **Duplicate frontier entries:** violated visited-on-enqueue. Always check `if v not in parent` before enqueue.

* **“No path found”:** verify the exact goal token (`pred:...`), confirm edges form a forward chain from NOW, and watch for reversed links (`B→A` instead of `A→B`).

* **Neighbor order surprises:** BFS may return a different (but equally short) path when neighbor orders change; that’s expected.

* **Assuming labels matter:** BFS follows **structure**, not action labels. Labels are for readability and (later) analytics/costs.

* * *

### Self-check (one minute)

1. In the given adjacency, what is the **pop order** under stop-on-pop?  
   **Answer:** `S, A, B, C, D, E, G`.

2. What are the **three buckets** immediately after popping `G`?  
   **Answer:**  
   `frontier = []`  
   `expanded = {S, A, B, C, D, E, G}`  
   `parent = {S:None, A:S, B:S, C:A, D:A, E:B, G:C}`

3. Give a **shortest path** and its **length**.  
   **Answer:** `S → A → C → G` (3 edges) — `S → B → E → G` is also 3.

4. Distances from S?  
   **Answer:** `S:0, A:1, B:1, C:2, D:2, E:2, G:3`.

* * *

Here’s a drop-in **cheat-sheet for `cca8_run.py` (Runner)** you can paste into your README. It’s concise, task-oriented, and mirrors how you actually use the runner day to day.

* * *

Tutorial on Main (Runner) Module Technical Features
==================================

What it is: the interactive & CLI entry point for CCA8.  It is run first and prints the banner, selects a profile, wires a `WorldGraph`, exposes preflight checks, autosave/load, and a full-screen menu to inspect/plan/act. 

Why is this tutorial after the one on WorldGraph, i.e., rather than being the first tutorial to start with?  It is because you really need to know the concepts such as binding, predicate, edge, and so on, and how they are coded and stored in the instance of the WorldGraph, before looking at the overall functioning of the program, which is what this module does.

***Note: Code changes will occur over time, but the main ideas below should remain stable with the project***

#### Public surface (importables)

Exports (see `__all__`):  
`main`, `interactive_loop`, `run_preflight_full`, `snapshot_text`, `export_snapshot`, `world_delete_edge`, `boot_prime_stand`, `save_session`, `versions_dict`, `versions_text`, `choose_contextual_base`, `compute_foa`, `candidate_anchors`, `Ctx`, `__version__`.

### Runtime context (`Ctx`)

Dataclass carried between engine and CLI:  
`sigma: float`, `jump: float`, `age_days: float`, `ticks: int`, `profile: str`, `winners_k: Optional[int]`, `hal: Optional[Any]`, `body: str`.

* * *

CLI quick reference
-------------------

    # About / versions
    python cca8_run.py --about          # list component versions & paths
    python cca8_run.py --version        # runner version only
    
    # Start interactive (fresh) with autosave
    python cca8_run.py --autosave session.json
    
    # Resume from a snapshot (and keep autosaving)
    python cca8_run.py --load session.json --autosave session.json
    
    # One-shot plan (non-interactive)
    python cca8_run.py --load session.json --plan pred:milk:drinking
    
    # Full preflight (runs pytest + checks) and exit
    python cca8_run.py --preflight

Flags you’ll actually use: `--about`, `--version`, `--load`, `--autosave`, `--plan`, `--preflight`, `--no-intro`, `--no-boot-prime`, `--profile {goat,chimp,human,super}`, `--hal`, `--body`.

* * *

Interactive menu: the 10 you’ll press most
------------------------------------------

* **1 World stats** — counts, NOW/LATEST, loaded policies.

* **2 Show last 5** — quickest way to grab fresh ids.

* **3 Add predicate** — auto-attach to `LATEST` (uses `WorldGraph.add_predicate`).

* **4 Connect two** — `(src, dst, relation)` with duplicate edge guard.

* **5 Plan from NOW** — pretty path + raw ids.

* **11 Add sensory cue** — adds `cue:*` and nudges controller once.

* **12 Instinct step** — Action Center tick with pre/post “why” text.

* **16 Export snapshot** — writes `world_snapshot.txt`.

* **22 Pyvis export** — interactive HTML graph (label mode, edge labels, physics).

* **25 Planner toggle** — BFS ↔ Dijkstra (weights read from `edge.meta`).

Tip: word aliases work (e.g., type “plan”, “graph”, “save”). The runner maps them to menu numbers.

* * *

Autosave / Load
---------------

* **Autosave** rewrites the JSON atomically after each action.

* **Load** restores `world/drives/skills` and **advances** internal id counter to avoid `bN` collisions.

* **Reset current autosave**: press `R` in the menu (with `--autosave` active).

* * *

Preflight (what it actually checks)
-----------------------------------

* Runs **pytest** (optionally with coverage).

* Imports core modules & symbols, prints versions.

* Fresh-world invariants (NOW exists & tagged, edges well-formed).

* Accessory files (e.g., `README.md`, image) present.

* Pyvis availability (optional).

* Planner probes, **attach semantics**, **cue normalization**, **action metrics**, **BFS shortest-hop** sanity.

* **Lexicon strictness** (reject illegal tokens at neonate).

* **Engram bridge**: capture→pointer attached→column record retrievable.

* * *

Handy engine helpers (the runner gives you)
-------------------------------------------

* **`world_delete_edge(world, src, dst, rel)`** — robust edge deletion (per-binding or global lists; tolerates legacy keys). Used by the menu delete flow.

* **`boot_prime_stand(world, ctx)`** — at birth, seed or connect a `stand` intent near NOW (idempotent).

* **FOA & base selection** — `compute_foa`, `candidate_anchors`, `choose_contextual_base` (light scaffolding used in the instinct printouts).

* * *

HAL (embodiment) stub
---------------------

`HAL` class carries `body` and exposes stubbed actuators/sensors (`push_up`, `extend_legs`, `orient_to_mom`, etc.). Gate with `--hal` / `--body`. Nothing hardware-critical runs yet.

* * *

Minimal usage crib (copy/paste)
-------------------------------

### A) One-shot CLI flow

    # Fresh session with autosave
    python cca8_run.py --autosave session.json
    
    # Add predicates / cues from the menu, then plan:
    # 5 → "state:posture_standing"   # pretty path prints
    
    # Export an interactive graph
    # 22 → choose label mode 'id+first_pred', edge labels Y, physics Y

### B) Resume + one-shot plan

    python cca8_run.py --load session.json --plan pred:milk:drinking

### C) Preflight before a demo

    python cca8_run.py --preflight

Look for “PASS” lines (pytest, invariants, attach semantics, BFS, engram bridge).

* * *

Troubleshooting quickies
------------------------

* **“No path found”** → check exact `pred:<token>`, ensure forward chain from NOW, watch for reversed edges.

* **Duplicate edge warning** → auto-attach plus manual connect; keep one.

* **Two NOW tags** → use `set_now(..., clean_previous=True)` (menu already tidies).

* **Strict lexicon errors** → switch to `warn` while developing or extend `TagLexicon.BASE`.

* * *

##### ****Note: Code changes will occur over time, but the main ideas below should remain stable with the project*** `



# cca8_run.py` — Call Flow & Usage Cheat-Sheet

What `main()` does (call flow)
------------------------------

    main(argv)
     ├─ configure logging
     ├─ parse CLI flags (about/version/load/autosave/plan/preflight/etc.)
     ├─ if --about: print component versions and exit
     ├─ if --preflight: run_preflight_full(args) and exit
     └─ interactive_loop(args)  ← primary entry for the TUI

Typical entry points:
    # About / versions
    python cca8_run.py --about
    python cca8_run.py --version
    # Fresh session with autosave
    python cca8_run.py --autosave session.json
    # Resume + keep autosaving
    python cca8_run.py --load session.json --autosave session.json
    # One-shot plan and exit
    python cca8_run.py --load session.json --plan pred:milk:drinking
    # Full preflight and exit
    python cca8_run.py --preflight

* * *

What `interactive_loop(args)` sets up (at start)
------------------------------------------------

    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives
    
    world = WorldGraph()            # empty world
    drives = Drives()               # controller drives (hunger/fatigue/warmth)
    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)  # runtime context
    
    # optional: load snapshot if --load path is provided
    # menu loop: add predicates/cues, connect edges, plan, export, etc.

Menu highlights you’ll actually use during demos:

* **World stats**, **Show last 5**, **Inspect binding**, **Add predicate**, **Connect two**, **Plan from NOW**, **Add sensory cue**, **Instinct step**, **Export snapshot**, **Pyvis export**, **Planner toggle (BFS↔Dijkstra)**.

* * *

Public surface (functions you can import)
-----------------------------------------

### Session & world utilities

    from cca8_run import snapshot_text, export_snapshot, save_session, world_delete_edge
    
    # 1) Human-readable snapshot (same text as menu item)
    print(snapshot_text(world, drives, ctx, policy_rt))
    
    # 2) Export a compact world snapshot to disk (bindings + edges)
    export_snapshot(world, drives, ctx, policy_rt,
                    path_txt="world_snapshot.txt",
                    _path_dot=None)  # DOT is optional elsewhere
    
    # 3) Save a full session (JSON): world + drives + skills
    save_session("session.json", world, drives)
    
    # 4) Robust edge deletion (handles legacy edge keys)
    removed = world_delete_edge(world, src="b3", dst="b4", rel="then")
    print("removed", removed)

### Preflight & versions

    from cca8_run import run_preflight_full, versions_dict, versions_text
    
    # One-shot preflight (pytest + invariants + planner/cue/attach probes)
    exit_code = run_preflight_full(args_namespace)
    
    # Versions as dict or pretty text
    print(versions_dict())
    print(versions_text())

### Planning helpers (skeletons for future control logic)

    from cca8_run import choose_contextual_base, compute_foa, candidate_anchors
    
    base_id = choose_contextual_base(world, ctx, targets={"pred:milk:drinking"})
    foa_ids = compute_foa(world, ctx, max_hops=2)     # Focus of Attention window
    cands   = candidate_anchors(world, ctx)           # e.g., NOW, HERE, …

### Bootstrapping newborn intent

    from cca8_run import boot_prime_stand
    boot_prime_stand(world, ctx)  # ensure NOW can reach a 'stand' intent at birth

* * *

Core classes defined in `cca8_run.py`
-------------------------------------

### `Ctx` — runtime context (mutable; passed around runner/controller)

    from cca8_run import Ctx
    
    ctx = Ctx(
        sigma=0.015,             # exploration jitter (UI demos)
        jump=0.2,                # epsilon exploration for policies
        age_days=0.0,            # developmental clock (drives → stage)
        ticks=0,                 # autonomic ticks
        profile="goat",          # selected profile label
        winners_k=None,          # used by multi-brain stubs
        hal=None,                # HAL instance if enabled
        body=""                  # body profile (if any)
    )

Fields (shape):  
`sigma: float`, `jump: float`, `age_days: float`, `ticks: int`, `profile: str`, `winners_k: Optional[int]`, `hal: Optional[Any]`, `body: str`

* * *

### `HAL` — hardware abstraction layer (stub)

    from cca8_run import HAL
    hal = HAL(body="hapty")     # stub embodiment
    
    # actuator stubs (no-ops today)
    hal.push_up()
    hal.extend_legs()
    hal.orient_to_mom()
    
    # sensor stubs (return booleans in demos)
    if hal.sense_vision_mom():
        print("seeing mom")

Methods:

* `push_up()`, `extend_legs()`, `orient_to_mom()`

* `sense_vision_mom()`, `sense_vestibular_fall()`

> Enable via CLI: `--hal --body hapty` (the runner prints a HAL status line).

* * *

### `PolicyRuntime` — gate filtering & single-step controller wrapper

    from cca8_run import PolicyRuntime
    from cca8_controller import CATALOG_GATES, Drives
    
    pr = PolicyRuntime(CATALOG_GATES)
    pr.refresh_loaded(ctx)                     # dev-gating by age/profile
    print("loaded:", pr.list_loaded_names())   # which gates are live?
    
    # Evaluate controllers once (respect ordering & safety priority)
    result = pr.consider_and_maybe_fire(world, Drives(), ctx)
    print(result)   # {'policy': 'policy:stand_up', 'status': 'ok', ...} or 'no_match'

Methods:

* `refresh_loaded(ctx)`

* `list_loaded_names() -> list[str]`

* `consider_and_maybe_fire(world, drives, ctx, tie_break=...) -> dict | 'no_match'`

> The runner’s **Instinct step** menu item uses this mechanism and prints a one-line status.

* * *

Putting it together (tiny end-to-end snippets)
----------------------------------------------

### 1) Minimal programmatic session (no TUI)

    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives
    from cca8_run import Ctx, save_session, versions_text
    
    world = WorldGraph()
    drives = Drives()
    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)
    
    now = world.ensure_anchor("NOW")
    b1  = world.add_predicate("posture:standing", attach="now")
    b2  = world.add_predicate("seeking_mom", attach="latest")
    
    print(versions_text())
    print(world.plan_pretty(now, "seeking_mom"))  # NOW -> b1 -> b2
    
    save_session("session.json", world, drives)

### 2) Delete a mistaken edge and autosave

    from cca8_run import world_delete_edge, save_session
    
    removed = world_delete_edge(world, src=b1, dst=b2, rel="then")
    if removed:
        print("fixed:", removed, "edge(s)"); save_session("session.json", world, drives)

### 3) Toggle planner strategy (code, not menu)

    print(world.get_planner())    # 'bfs'
    world.set_planner("dijkstra")
    print(world.get_planner())    # 'dijkstra'

* * *

What to scan in the code (orientation map)
------------------------------------------

* **`main()`**: argparse flags, about/preflight branches, calls `interactive_loop(args)`.

* **`interactive_loop()`**: world/drives/ctx construction, optional `--load`, then the **menu loop** (aliases + grouped items).  
  Look for blocks labeled: Add predicate, Add cue, Connect two, Plan, Instinct step, Export snapshot, Pyvis export, Planner toggle.

* **Exports (`__all__`)** you can import:  
  `main`, `interactive_loop`, `run_preflight_full`, `snapshot_text`, `export_snapshot`, `world_delete_edge`, `boot_prime_stand`, `save_session`, `versions_dict`, `versions_text`, `choose_contextual_base`, `compute_foa`, `candidate_anchors`, `__version__`, `Ctx`.

* * *

****Note: Code changes will occur over time, but the main ideas below should remain stable with the project*** `



# Tutorial on Controller Module Technical Features



## cca8_controller.py : Usage & Mental Model (Part 1)

**What this module does.**  
It owns the **drives** (hunger/fatigue/warmth), the **policies** (a.k.a. primitives) that decide one step at a time, and the **Action Center** loop that picks the first policy whose `trigger(...)` is true and runs it.

**Key ideas:**

* **Drives → ephemeral `drive:*` tags.** `Drives.flags()` returns strings like `drive:hunger_high`. These are **not** written into the graph; they’re only used inside policy `trigger(...)` logic.

* **Policies (primitives).** Each policy has two methods:
  
  * `trigger(world, drives) -> bool`
  
  * `execute(world, ctx, drives) -> dict`  
    `execute` appends a _small chain_ of predicates/edges to the **WorldGraph** and returns a standard status dict (policy, status, reward, notes).

* **Action Center.** Scans `PRIMITIVES` in order; runs the first policy whose `trigger(...)` returns `True`. Safety exception: if the agent is **fallen**, `StandUp` is run immediately.

* **Provenance & skill ledger.** Policies stamp `binding.meta["policy"]` (and edge `meta["created_by"]`) and update a small in-memory **SKILLS** ledger (n, succ, q, last_reward).

### One-minute quickstart (copy/paste)

    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives, action_center_step
    
    g = WorldGraph()
    now = g.ensure_anchor("NOW")
    
    # Neonate: hungry enough to act; fatigue moderate
    dr = Drives(hunger=0.9, fatigue=0.2, warmth=0.6)
    print("drive flags:", dr.predicates())   # e.g., ['drive:hunger_high']
    
    # One Action Center tick
    status = action_center_step(g, ctx=None, drives=dr)
    print(status)                            # {'policy': 'policy:stand_up', 'status': 'ok', ...}
    print(g.plan_pretty(now, "posture:standing"))

**Status dict contract (always):**
    {
      "policy": "policy:<name>" | None,
      "status": "ok" | "fail" | "noop" | "error",
      "reward": float,
      "notes": str
    }

**Drive thresholds (from `Drives` docstring):**

* `hunger > 0.6 → 'drive:hunger_high'`

* `fatigue > 0.7 → 'drive:fatigue_high'`

* `warmth < 0.3 → 'drive:cold'`

**Planner note.** Policies create/chain **predicates** with directed edges; planning remains BFS (or Dijkstra, if selected) on the episode graph you built in `cca8_world_graph.py`.

* * *

## `cca8_controller.py` — API & Internals (Part 2)

Core data & module-level symbols
--------------------------------

* **`PRIMITIVES: list[Primitive]`** — ordered repertoire scanned by the Action Center (default order):  
  `StandUp()`, `SeekNipple()`, `FollowMom()`, `ExploreCheck()`, `Rest()`.

* **`SKILLS: dict[str, SkillStat]`** — in-memory per-policy stats (n, succ, q, last_reward).

Classes
-------

### `Drives`

Agent internal state + conversion to ephemeral drive flags.

* **Attributes:**  
  `hunger: float`, `fatigue: float`, `warmth: float`

* **Methods:**  
  `predicates() -> list[str]` ⮕ returns `drive:*` tags by threshold  
  `to_dict() -> dict` / `from_dict(d) -> Drives`

### `SkillStat`

Tiny running stats structure for the skill ledger.  
Fields: `n`, `succ`, `q`, `last_reward`.

### `Primitive` (base class)

Policy interface + standardized return helpers.

* `name: str = "policy:unknown"`

* `trigger(world, drives) -> bool`

* `execute(world, ctx, drives) -> dict`

* Helpers (update SKILLS + return dict):
  
  * `_success(reward: float, notes: str) -> dict`
  
  * `_fail(notes: str, reward: float = 0.0) -> dict`

### Concrete policies (default set)

#### `StandUp(Primitive)`

* **Trigger:** true if **fallen**, or if **hunger high** and **not upright yet**.  
  Accepts legacy & canonical posture tags (`state:posture_standing` / `posture:standing`).

* **Execute:** append a tiny chain  
  `action:push_up → action:extend_legs → state:posture_standing`  
  Add `"then"` edges, stamp provenance, return reward `+1.0`.

#### `SeekNipple(Primitive)`

* **Trigger:** **hungry**, **upright**, **not fallen**, **not already seeking**.

* **Execute:** `action:orient_to_mom → seeking_mom` with a `"then"` edge; reward `+0.5`.

#### `FollowMom(Primitive)`

* **Trigger:** permissive default (returns `True`).

* **Execute:** `action:look_around → state:alert`; reward `+0.1`.

#### `ExploreCheck(Primitive)`

* **Trigger:** currently `False` (stub for periodic checks).

* **Execute:** returns `_success("checked")` (no graph mutation).

#### `Rest(Primitive)`

* **Trigger:** `fatigue > 0.8`.

* **Execute:** reduces `fatigue`, adds `state:resting` (attached to NOW), reward `+0.2`.

Functions (helpers & Action Center)
-----------------------------------

* **`update_skill(name, reward, ok=True, alpha=0.3) -> None`**  
  Get-or-create a `SkillStat`, bump counts, **exponential-avg** into `q`, set `last_reward`.

* **`skills_to_dict() -> dict` / `skills_from_dict(d: dict) -> None`**  
  Serialize/rehydrate the in-memory SKILLS ledger.

* **`skill_readout() -> str`**  
  Human-readable one-liner per policy: `n, succ, rate, q, last`.

* **`_any_tag(world, full_tag: str) -> bool`**  
  `True` if any binding carries the exact tag (used by triggers).

* **`_has(world, token: str) -> bool`**  
  Convenience: token like `"posture:fallen"` → checks for `pred:posture:fallen` anywhere.

* **`_any_cue_present(world) -> bool`**  
  `True` if any `cue:*` tag is present in the world (loose sensor check).

* **`_run(policy, world, ctx, drives) -> dict`**  
  Wrapper: call `execute`, update SKILLS; catch and report policy errors.

* **`action_center_step(world, ctx, drives: Drives) -> dict`**  
  **Contract:** scan `PRIMITIVES`; run the first whose `trigger(...)` returns `True`.  
  **Safety short-circuit:** if fallen, immediately run `StandUp`.  
  **Side-effects:** appends bindings/edges, may adjust drives, updates SKILLS.  
  **Returns:** a status dict (`ok`/`fail`/`noop`/`error`).

* * *

Minimal usage crib (controller-focused)
---------------------------------------

    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives, action_center_step, skill_readout
    
    g = WorldGraph()
    now = g.ensure_anchor("NOW")
    
    # 1) Hungry neonate → StandUp likely fires
    dr = Drives(hunger=0.95, fatigue=0.2, warmth=0.6)
    print(action_center_step(g, ctx=None, drives=dr))
    print(g.plan_pretty(now, "posture:standing"))
    
    # 2) Fatigued agent → Rest fires next
    dr.fatigue = 0.9
    print(action_center_step(g, ctx=None, drives=dr))
    
    # 3) Ledger peek
    print(skill_readout())

**Style guidance:** keep **drive tags ephemeral (which is why they are called flags)** (policy triggers). If we want drive states visible to planning/paths, add **`pred:drive:*`** nodes (plannable) or **`cue:drive:*`** (trigger-only) deliberately in your controller logic.

* * *

Tutorial on Temporal Module Technical Features
----------------------------------------------

This tutorial explains how **`cca8_temporal.py`** gives CCA8 a lightweight notion of time that complements wall-clock timestamps. It covers the **why**, the **math**, and the **wiring** added to the runner and controller.

### 1) Why a temporal vector if we already have timestamps?

Wall-clock (ISO-8601) stamps are excellent for **provenance** and audit trails, but clumsy for two tasks we care about:

* **Episode segmentation.** “Did a new episode start?” Rule-of-thumb gap detectors (e.g., “>5 s”) are brittle when sim speed varies.

* **Time-aware similarity.** “Fetch things that happened around the same time as X.” Pure timestamps don’t give a smooth, unitless notion of “nearby.”

The Temporal module adds a **unit-norm context vector** that **drifts** a little each tick and **jumps** at boundaries. With unit vectors, **cosine = dot product**, so “near in time” becomes a cheap dot-product check—no units, no parsing, no NumPy.

> Design note: WorldGraph remains **atemporal** (except anchors like `NOW`). Time semantics live in `meta` and in this module/runner, not inside graph mechanics. Policies continue to stamp `created_at` directly.

* * *

### 2) What the TemporalContext is

`TemporalContext` maintains a **D-dimensional unit vector** (default 128-D) representing “now.” Two operations evolve it:

* `step()` – add tiny Gaussian noise (σ = `sigma`) to each component, then **re-normalize** to length 1 (a gentle **drift**).

* `boundary()` – add larger Gaussian noise (σ = `jump`), then re-normalize (a **jump** for episode cuts).  
  Because the vector is always unit-norm, comparing two time points is just a dot product. 1.0 ≈ very close; ~0.0 ≈ far/orthogonal.

**Quick mental model.** Think of time as a path on a high-dimensional unit sphere: smooth motion with occasional bigger hops at important moments. “Meaning” emerges only by **comparison** (dot products), not from individual components.

* * *

### 3) Math refresher (why cosine is cheap here)

For vectors u,v:  
cosθ=∥u∥∥v∥u⋅v​. If ∥u∥=∥v∥=1, then cosθ=u⋅v.  
Same direction → 1.0; orthogonal → 0.0; opposite → −1.0. We re-normalize after every drift/jump, so comparisons are just `sum(a*b for a,b in zip(u,v))`.

* * *

### 4) How we use it in CCA8 (current wiring)

At this point in time, we've wired the soft clock in the **Runner** and added tiny provenance in the **Controller**:

* **Runner creates & advances the soft clock**
  
  * On session start: `ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump)`; seed `ctx.tvec_last_boundary = ctx.temporal.vector()`.
  
  * Every **Instinct step** and **Autonomic tick**: call `ctx.temporal.step()` once (drift).
  
  * On a **successful write** (graph grew): call `ctx.temporal.boundary()` and update `tvec_last_boundary` (one boundary per write).
  
  * (Optional) **thresholded segmentation:** if `dot(now, last_boundary) < τ` (e.g., 0.90), force a boundary.
  
  * Snapshots show a compact **TEMPORAL** block: `(dim, sigma, jump)`, `cos_to_last_boundary`, and a short hash.

* **Controller stamps temporal provenance**
  
  * Policies keep stamping `meta["created_at"]` (ISO-8601, seconds precision).
  
  * We also add `meta["ticks"]` and a compact **time fingerprint** `meta["tvec64"]` (sign-bit hash of the temporal vector at write time).
  
  * Result: each binding has both **wall-clock** and **soft-clock** context.

A concise summary of this wiring is also recorded in the code comments you added on Nov 1, 2025.

* * *

### 5) What the vector “looks like” (and doesn’t)

* It’s a plain Python **list[float]** of length `dim`, re-normalized each change; no NumPy dependency.

* Components are **standard-normal samples** at init, then small/noisy updates—**components have no human meaning** by themselves.

* We **never** read it dimension-by-dimension; we **only compare whole vectors** (cosine/dot).

* * *

### 6) Typical workflows

**A) Segmentation by threshold**  
Keep `v* = last_boundary`. Each tick:

`cos_now = sum(a*b for a,b in zip(ctx.temporal.vector(), v_star)) if cos_now < 0.90:    v_star = ctx.temporal.boundary()`

* Small `sigma` → slow decay; rare auto cuts.

* Larger `jump` → deeper cosine dip on boundary.

* Tune τ per profile (goat vs chimp vs human).

**B) Time-aware retrieval**  
Store `meta["tvec64"]` (or the full vector during development). Later, “near this time” queries become nearest-neighbors by dot product (or Hamming distance on the sign bits).

**C) Provenance & analytics**  
Bindings now carry `created_at` (ISO-8601), `ticks`, and `tvec64`. You can correlate actions with recency and segment chapters post-hoc.

* * *

### 7) Parameters that can be tuned

* `dim` (64–128 typical): higher dims → smoother geometry, less variance in dot products.

* `sigma` (drift): how fast “time” moves when nothing big happens.

* `jump` (boundary): how distinct chapters feel (bigger jump → lower cosine after boundary).

* `τ` (threshold): when to auto-cut based on similarity to the last boundary.

* * *

### 8) Minimal API (developer crib)

`from cca8_temporal import TemporalContextt = TemporalContext(dim=128, sigma=0.02, jump=0.25)v0 = t.vector()       # defensive copy (unit-norm) v1 = t.step()         # drift (small change) v2 = t.boundary()     # jump  (larger change)  def dot(a,b): return sum(x*y for x,y in zip(a,b)) print(dot(v0, v1))    # ~0.995–0.999… print(dot(v0, v2))    # noticeably smaller (e.g., 0.7–0.95 depending on jump)`

Under the hood: `_normalize(vals)` returns a unit-norm copy and guards zero-norm with `1.0`.

* * *

### 9) Invariants & guardrails

* Always re-normalize after drift/boundary so cosine=dot remains valid.

* TemporalContext **does not** stamp `created_at`; that remains a policy/controller responsibility.

* The soft clock is **run-relative** (not meant for cross-run alignment unless you fix a random seed).

* Pure-Python O(d) per tick; no heavy deps.

* * *

### 10) Quick demo in the Runner (what to expect)

1. `12` Instinct step → if the controller writes, you’ll see  
   `[temporal] boundary after write (cos reset to ~1.000)` and `cos_to_last_boundary: 1.000` in the snapshot.

2. `15` Autonomic tick × N → `cos_to_last_boundary` decays gently (drift only).

3. If you enabled the τ-cut, a boundary triggers automatically once cosine drops below τ (you’ll see a console note).

4. Saved JSON shows `meta.created_at`, `meta.ticks`, and `meta.tvec64` on new bindings.

* * *

Tutorial on Features Module Technical Features
==============================================

This section explains what **`cca8_features.py`** provides, why it exists, and how to use it day-to-day. It complements the Signal Bridge (WorldGraph ↔ Engrams) by defining **what an engram payload looks like**, a **concrete dense-tensor payload**, and a **lightweight descriptor** you can search/filter without touching big data.

**Why this design?** The WorldGraph stays an **episode index** (≈5% of data) while columns hold the rich 95%. The bridge preserves traceability without slowing planning.

* * *

### 1) What this module is

A small, dependency-free toolkit for **engram payloads**:

* **`FeaturePayload`** — a _Protocol_ (typing interface) describing the **shape** a payload must have (attributes + methods).

* **`TensorPayload`** — a concrete, bytes-serializable dense vector/tensor (float32 body).

* **`FactMeta`** — a compact descriptor for column records (name/links/attrs) with optional **time linkage** to the runner.

This keeps WorldGraph lean (only an **engram pointer** lives on a binding) while Columns store the heavy content.

* * *

### 2) Public API (what to import)

    from cca8_features import FeaturePayload, TensorPayload, FactMeta
    # optional helper (if you exposed it): time_attrs_from_ctx

* `FeaturePayload` is an **interface** (Protocol). You don’t instantiate it; any class with the required attributes/methods _conforms_.

* `TensorPayload` and `FactMeta` are concrete dataclasses you use directly.

* * *

### 3) `FeaturePayload` (Protocol) — the interface

**Purpose.** Define the minimal **contract** any engram payload must satisfy so Columns and bridges don’t depend on one concrete class.

**Attributes**

* `kind: str` – human/use-case label (e.g., `"embedding"`, `"scene"`).

* `fmt: str` – storage/format hint (e.g., `"tensor/list-f32"`).

* `shape: tuple[int, ...]` – tensor-like shape; use `()` for scalars.

**Methods**

* `to_bytes() -> bytes` — portable serialization.

* `from_bytes(cls, data: bytes) -> FeaturePayload` — decode a payload produced by `to_bytes`.

* `meta() -> dict` — JSON-safe descriptor (`{"kind","fmt","shape","len"}`) for logs/UI without decoding bytes.

> Protocols are **typing interfaces** (non-instantiable). Your concrete classes (like `TensorPayload`) implement the contract.

* * *

### 4) `TensorPayload` — a compact dense tensor (float32)

**What it carries**

* `data: list[float]` — numeric values (treated as **float32** on disk).

* `shape: tuple[int, ...]` — e.g., `(768,)` for an embedding.

* `kind="embedding"`, `fmt="tensor/list-f32"` — defaults you can override.

**Why it’s light**  
Uses only the standard library:

* Header encoded with `struct` (**little-endian, versioned**).

* Body written as contiguous **float32** with `array('f')`.

**Binary layout**
    MAGIC(5) | VER(u32) | NDIMS(u32) | DIMS[NDIMS](u32 …) | DATA(float32 …)

**Key methods**

* `to_bytes()` — builds header via `struct.pack("<5sII…")` then appends `array('f', data).tobytes()`.

* `from_bytes(...)` — validates MAGIC/version, parses dims with `struct.unpack_from`, rebuilds data via `array('f').frombytes(...)`.

* `meta()` — returns `{"kind","fmt","shape","len"}` without touching the body.

_Invariant hints_ (good practice you may already enforce):

* `len(data) == product(shape)`

* `array('f').itemsize == 4`

* * *

### 5) `FactMeta` — lightweight descriptor (with optional time linkage)

**Fields**

* `name: str` — concise, queryable label (e.g., `vision:silhouette:mom`, `scene`).

* `links: list[str] | None` — cross-refs (typically **WorldGraph binding ids** this engram relates to).

* `attrs: dict[str, Any] | None` — freeform descriptors you’ll filter/sort by (e.g., `{"model":"clip-vit-b32","sensor":"camera0"}`).

**Nice helpers**

* `as_dict()` — JSON-safe view with defaults applied.

* `with_time(ctx)` — merges runner time keys into `attrs` when available:
  
  * `ticks` — runner’s tick counter.
  
  * `tvec64` — 64-bit sign-bit hash of the temporal vector (TemporalContext fingerprint).

**Why mirror time here?**  
Bindings already carry graph-side provenance (`created_at`, `ticks`, `tvec64`). Mirroring `{"ticks","tvec64"}` into Column engrams lets you **correlate** engrams with graph events _without_ opening payload bytes.

* * *

### 6) Where it fits in CCA8 (end-to-end picture)

* **WorldGraph** stores _pointers_ to engrams on a binding:  
  `binding.engrams["column01"] = {"id": "<engram_id>", "act": 1.0}`

* **ColumnMemory** stores the **record** `{id, name, payload, meta}` where:
  
  * `payload` is a **FeaturePayload** (e.g., `TensorPayload`),
  
  * `meta` is a **FactMeta** (often with `ticks`/`tvec64` in `attrs`).

* **Signal bridge** (menu **24** “Capture scene”) wraps a small vector into a `TensorPayload`, asserts it as an engram, attaches the pointer to the new binding, and—if you pass `attrs=time_attrs_from_ctx(ctx)`—**mirrors time** into the column record automatically.

* * *

### 7) Minimal usage cribs

**A) Programmatic (Column direct)**
    from cca8_column import mem
    from cca8_features import TensorPayload, FactMeta
    vec = [0.1, 0.2, 0.3]
    payload = TensorPayload(data=vec, shape=(len(vec),))
    meta = FactMeta(name="vision:silhouette:mom", links=[latest_bid]).with_time(ctx)
    engram_id = mem.assert_fact("vision:silhouette:mom", payload, meta)
    world.attach_engram(latest_bid, column="column01", engram_id=engram_id, act=1.0)

**B) Via WorldGraph bridge (menu 24 path)**
    from cca8_features import time_attrs_from_ctx  # if exported
    attrs = time_attrs_from_ctx(ctx)  # {'ticks': ..., 'tvec64': ...} or {}
    bid, engram_id = world.capture_scene("vision", "silhouette:mom",
                                         vector=vec, attach="now",
                                         family="cue", attrs=attrs)

**C) Inspect an engram**
    rec = world.get_engram(engram_id=engram_id)
    print(rec["meta"])   # should include {'ticks': N, 'tvec64': '...'} if mirrored

* * *

### 8) Invariants & guardrails (quick checklist)

* `TensorPayload.to_bytes()/from_bytes()`:
  
  * MAGIC/VER must match; shapes parsed from little-endian u32s.
  
  * Body length matches `product(shape) * 4` bytes (float32).

* `FactMeta` is **JSON-safe** (`as_dict()` gives lists/dicts; tuples serialize as lists).

* Time linkage:
  
  * **Graph side**: bindings carry `created_at` (ISO-8601), `ticks`, `tvec64`.
  
  * **Column side**: `FactMeta.attrs` may carry `ticks`/`tvec64` (optional, by your choice).

* Bridge keeps **WorldGraph fast**: engrams stay outside; bindings carry only pointers.

* * *

### 9) Why no NumPy?

This module focuses on **schema + portability**, not numeric ops. `struct` + `array('f')` give a compact, stable on-disk format and fast IO with **zero heavy deps**. If/when you need vector math, you can opt-in elsewhere without changing the engram format.

* * *

### 10) Quick test ideas (already partly covered)

* `TensorPayload` round-trip bytes → equal `data/shape`, correct `meta()`.

* `FactMeta.with_time(ctx)` merges `{"ticks","tvec64"}` when available; a missing `ctx` field yields no keys.

* World bridge: `capture_scene(..., attrs=time_attrs_from_ctx(ctx))` → `get_engram(...)[ "meta"]["attrs"]` contains mirrored time.

* * *



### **11) What’s new (Nov 2025)**

* Runner’s **Capture scene** (menu **24**) now mirrors temporal context into each engram via `time_attrs_from_ctx(ctx)`: `ticks`, `tvec64`, **`epoch`**, and **`epoch_vhash64`**. This makes engrams time-aware without touching payload bytes.

* Two new runner tools: **27) Inspect engram by id** (also accepts a **binding id** and resolves its pointer) and **28) List all engrams** (id, source binding, time attrs, payload summary).

* Snapshot and probe make event boundaries explicit (`boundary_no`, `last_boundary_vhash64` in CTX; probe shows cosine/Hamming status). (Context; see Runner TEMPORAL section.)

#### The bridge (WorldGraph ↔ Column)

1. **Emit**: Runner **24) Capture scene** asks for channel/token/family (cue|pred), attach policy (now/latest/none), and a small vector. It creates a binding and asserts a column engram, then attaches a pointer:

`"engrams": { "column01": { "id": "<engram_id>", "act": 1.0 } }`

The Column record stores `{id, name, payload, meta}`, where `meta.attrs` carries `ticks`, `tvec64`, **epoch**, **epoch_vhash64**.

2. **Attach**: Only the **pointer** (column name → id) sits on the binding; the heavy payload stays in the Column. Planning remains purely over tags/edges.

3. **Inspect**:
* **Display snapshot** shows which bindings have engrams: `engrams=[column01]`.

* **Inspect binding details** prints the full pointer JSON (including the engram id).

* **27) Inspect engram by id** prints the Column record (meta + payload summary). If you type a **binding id** (e.g., `b11`) it resolves its engram automatically.

* **28) List all engrams** enumerates all attached engrams with time attrs.

#### Minimal API surface (dev view)

* **Column store** (`cca8_column.py`):  
  `ColumnMemory.assert_fact(name, payload, meta) -> engram_id`  
  `ColumnMemory.get(engram_id) -> dict`  
  (Default singleton `mem = ColumnMemory(name="column01")` used by the bridge.)

* **Runner bridge** (`cca8_run.py`):  
  `world.capture_scene(channel, token, vector, attach, family, attrs=...) -> (bid, engram_id)`  
  plus menu **24**, **27**, **28** wrappers so you don’t have to write code to use it.

#### Quick tutorial (CLI)

1. **24) Capture scene** → use `vision / silhouette:mom / cue / now / 0.1 0.2 0.3`  
   Runner prints both the **binding id** and the **engram id**, and echoes the time attrs mirrored into the engram.

2. **3) Inspect binding** → paste the binding id. You’ll see `Engrams: {"column01": {"id":"…"}}`.

3. **27) Inspect engram by id** → paste the engram id **or** just type the binding id; it resolves for you.

4. **28) List all engrams** → browse all engrams with their source binding and time attrs.
   
   



### Tutorial on Column Module Technical Features

This section explains **`cca8_column.py`** — the in-memory engram store (“Column”) that holds **rich payloads** outside the WorldGraph. Bindings keep **only pointers** to these engrams, preserving a fast, compact episode index while still giving you traceability to perceptual/feature data.

_Why this module exists._ WorldGraph stays small and plannable; columns carry the heavyweight 95% (vectors, features, descriptors). The runner’s bridge writes the minimum pointer on the binding so planning/search remain unchanged. 
The Column keeps heavy memory **out of the graph** without losing traceability: bindings stay fast and small; engrams in Column carry the payloads + time fingerprints you can inspect and query. The Runner menus make this workflow usable without writing code, albeit for small examples.

* * *

#### 1) Mental model

* **Binding (WorldGraph)** → carries tags + **engrams pointer(s)** like  
  `{"column01": {"id": "<engram_id>", "act": 1.0}}`

* **Column (this module)** → keyed by `engram_id`, stores the **record**:  
  `{ "id", "name", "payload", "meta", "v" }`

* **Payload** → usually a `TensorPayload` (float32 vector) or a small dict with `meta()` describing `{"kind","fmt","shape","len"}`.

* **Time linkage** → runner mirrors temporal context into the engram’s `meta.attrs`: `ticks`, `tvec64`, **`epoch`**, **`epoch_vhash64`** (hash of the last event boundary).

* * *

#### 2) Public API (what you can call)

`from cca8_column import mem as column_mem  # default singleton column ("column01")  # Core engram_id = column_mem.assert_fact(name: str, payload, meta: FactMeta|dict) -> str record    = column_mem.get(engram_id: str) -> dict  # Convenience helpers (present in current build) ok        = column_mem.exists(engram_id: str) -> bool record_or_none = column_mem.try_get(engram_id: str) -> dict|None removed   = column_mem.delete(engram_id: str) -> bool ids       = column_mem.list_ids(limit: int|None = None) -> list[str]matches   = column_mem.find(name_contains: str|None = None,                            epoch: int|None = None,                            has_attr: str|None = None,                            limit: int|None = None) -> list[dict]n         = column_mem.count() -> int`

**Record shape (typical):**

`{   "id": "<engram_id>",   "name": "scene:vision:silhouette:mom",   "payload": TensorPayload(...),     // or a small dict with shape/kind   "meta": {     "name": "...", "links": ["b3"], "attrs": {       "ticks": 5, "tvec64": "…", "epoch": 2, "epoch_vhash64": "…",       "column": "column01"     },     "created_at": "YYYY-MM-DDThh:mm:ss"   },   "v": "1" }`

* * *

#### 3) How time gets into Column records (bridge)

From the Runner (menu **24 Capture scene**), we pass `attrs=time_attrs_from_ctx(ctx)`, which copies **`ticks`**, **`tvec64`**, **`epoch`**, **`epoch_vhash64`** into `meta.attrs` of the Column record at **assert time**. With the current Runner, capture does a **pre-capture event boundary**, so the engram’s `epoch` reflects the **new** boundary you just created.

CLI menus that help you see this:

* **24** Capture → prints binding id + engram id + mirrored time attrs.

* **27** Inspect engram by id (also accepts a binding id; it resolves the pointer).

* **28** List all engrams (id, source binding, time attrs, payload summary).

* **29** Search engrams (by name substring / epoch).

* **30** Delete engram (accepts binding id or engram id; also **prunes all binding pointers** to that id).

* **31** Attach existing engram to a binding (demonstrates many-to-one pointers).

* * *

#### 4) Minimal usage cribs

**A) Programmatic (direct Column write + pointer attach)**

`from cca8_column import mem from cca8_features import TensorPayload, FactMeta, time_attrs_from_ctxvec = [0.1, 0.2, 0.3]payload = TensorPayload(data=vec, shape=(len(vec),))meta = FactMeta(name="scene:vision:silhouette:mom",                links=[latest_bid],                attrs=time_attrs_from_ctx(ctx))  # ticks, tvec64, epoch, epoch_vhash64  eid = mem.assert_fact("scene:vision:silhouette:mom", payload, meta)world.attach_engram(latest_bid, column="column01", engram_id=eid, act=1.0)`

**B) Via the Runner bridge (one step)**

`bid, eid = world.capture_scene(    channel="vision", token="silhouette:mom",    vector=[0.1, 0.2, 0.3], attach="now", family="cue",    attrs=time_attrs_from_ctx(ctx)  # mirrors temporal attrs )`

**C) Lookup & inspect**

`rec = world.get_engram(engram_id=eid) print(rec["meta"]["attrs"])   # -> ticks/tvec64/epoch/epoch_vhash64/column print(rec["payload"].meta())  # -> {'kind','fmt','shape','len'}`

* * *

#### 5) Invariants & guardrails

* **WorldGraph only stores pointers.** Don’t stuff large blobs in bindings; keep payloads in Column.

* **Provenance & time are split:** bindings stamp `created_at`, `ticks`, `tvec64`, `epoch`; engrams mirror time in `meta.attrs`.

* **Pointer pruning:** deleting an engram from Column should prune any binding pointers to it (Runner menu **30**) to prevent dangling references.

* **Volatility:** the default in-memory Column is session-local. Pointers aren’t persisted across restarts unless you add a persistence layer for Column (future work).

* **Payload discipline:** keep payloads **small** (vectors, short descriptors). Summarize in UIs; use `.meta()` (shape/kind/len) instead of decoding bytes.

* * *

#### 6) CLI walkthrough (fast demo)

1. **24** capture `vision / silhouette:mom / cue / now / 0.1 0.2 0.3`  
   → logs binding id + engram id + mirrored time; shows a short pointer line like  
   `[bridge] attached pointer: b3.engrams["column01"] = <EID>`

2. **3** inspect binding `b3`  
   → see `Engrams: {"column01": {"id": "<EID>", "act": 1.0}}`

3. **27** inspect `b3` (or paste `<EID>`)  
   → see full Column record; `meta.attrs.epoch` matches the boundary you just took

4. **28** list  
   → rows like `EID=<…> src=b3 ticks=… epoch=… payload(shape=(3,), dtype=scene)`

5. **29** search  
   → filter by `silhouette` and/or `epoch`

6. **30** delete `b3`  
   → “Deleted. Pruned 1 pointer(s).” Now **27** on `b3` shows “No engrams on binding b3.”

* * *

#### 7) Test ideas (unit tests you can add/extend)

* **Round-trip & meta:** `assert_fact → get` preserves `id/name/payload`, `meta.attrs["epoch"]` present when provided.

* **CRUD:** `exists/try_get/delete/list_ids/count` behave as advertised.

* **Find:** substring match on `name`, epoch filter, `has_attr` key present.

* **Pointer pruning:** after delete, runner scan finds **0** pointers to the removed id.

* * *

#### 8) Roadmap (non-breaking extensions)

* Optional persistence for Column (e.g., JSONL/SQLite sidecar).

* Nearest-neighbor queries on payloads (similarity search) to bias policy arbitration.

* Multi-column pointers per binding (vision/audio/touch) with light aggregation in UIs.

* * *



# Planner contract (for maintainers)

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
A: Keep it stable, if fields change, bump a version field and handle compatibility in `from_dict()`.

Q: Does loading mutate counters?   
A: Yes—counters advance so newly created bindings get fresh ids.

Q: What else does the runner persist beyond the world?   
A: Drives and small controller telemetry to aid debugging.





* * *

## Traceability (requirements to code)

---------------------------------------------------------------

A traceability‑lite table maps major requirements to the modules and functions that satisfy them. Keep this short and keep it close to code names so a maintainer can jump straight into the right file. Examples:

* REQ‑PLAN‑01: BFS finds a shortest path in edges.Satisfied by `WorldGraph.plan_to_predicate` (BFS), `pretty_path` (display).

* REQ‑POL‑02: Policies run in priority order with small guards.Satisfied by `cca8_controller.ActionCenter`, policy `trigger()` guards, and provenance in `meta`.

* REQ‑PERS‑03: Loading a snapshot advances the id counter.Satisfied by `WorldGraph.from_dict`.

You can expand this list as the codebase grows.
Note -- Currently paused. To revisit as the codebase grows and requirements stabilize.



***Q&A to help you learn this section***

Q: How do I keep requirements and code in sync?   
A: Add a short REQ row and tag the relevant functions/classes with the REQ id in comments.

Q: Where should new ADRs go now that decisions are in-line?   
A: Summarize in the section where the topic appears and, if large, put the full ADR under `docs/adr/` with a link.

Q: What belongs in a REQ vs. ADR?   
A: REQ = behavior the system must provide, ADR = why a design choice was made among alternatives. 

* * *

## Roadmap

* Enrich engrams and column providers, add minimal perception‑to‑predicate pipelines.
* Add “landmarks” and heuristics for long‑distance plans (A* when we add weights).
* Optional database or CSR backend if the graph grows beyond memory.
* Exporters: NetworkX/GraphML for interoperability, continue shipping the Pyvis HTML for quick, zero‑install visualization.

***Q&A to help you learn this section***

Pending as codebase grows and features stabilize

* * *

### 

## Debugging Tips (traceback, pdb, VS Code)

- **traceback:** In `except Exception:` add `traceback.print_exc()` to print a full stack. Use when a loader/snapshot fails.  
- **pdb:** Drop `breakpoint()` in code or run `python -m pdb cca8_run.py --load ...`. Commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p`/`pp` (print), `b` (breakpoint), `where`.  
- **VS Code debugger:** Create `.vscode/launch.json` with args, set breakpoints in the gutter, F5 to start. Great for multi-file stepping.
* Tracebacks: the runner keeps exceptions readable, copy the stack into an issue if you see unexpected behavior.
* `pdb`: insert `import pdb, pdb.set_trace()` where needed to inspect bindings and edges.
* VS Code: run `cca8_run.py` with the debugger and place breakpoints in `plan_to_predicate()` or policy `trigger()`/`execute()`.
  
  

A common pitfall is duplicate edges when both auto‑attach and a manual connect create the same relation. The UI warns when you try to add a duplicate, you can also inspect the `edges` list on a binding directly in the debugger.

#### Playbook: “No path found”

1. **Verify the predicate exists** (snapshot shows a binding with that `pred:*`).

2. **Check connectivity** (ensure there’s a forward chain of edges from NOW to that binding).

3. **Look for reversed edges** (common error: added `B→A` instead of `A→B`).

4. **Confirm the goal token** (exact `pred:<token>` string, avoid typos/extra spaces).

5. **Inspect layers** (use the interactive graph, the missing hop will be visually obvious).

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
- **Loading says file not found** — We continue with a fresh session, the file will be created on your first autosave event.
  
  

***Q&A to help you learn this section***

Q: Why “No path found …” on a new session?  A: You planned before adding the predicate, run one instinct tick.

Q: Why duplicate “standing” nodes?  A: Old controller, update to guarded StandUp.trigger().

Q: How to keep an old snapshot?  A: Autosave to a new filename.
Q: Is load failure fatal?  A: No, runner continues with a fresh session.

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
- **Action Center** — ordered scan of policies, runs first match per tick.  
- **Drives** — homeostatic variables (hunger/fatigue/warmth) that generate drive flags for triggers.  
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
Scalar homeostatic variables (0–1): `hunger`, `warmth`, `fatigue`. When crossing thresholds, the runner emits drive flags like `drive:hunger_high`.

**Search knobs**

* `k`: branch cap during expansion (smaller = decisive, larger = broader).

* `sigma`: small Gaussian jitter to break ties/avoid stagnation.

* `jump`: ε-exploration probability to occasionally take a random plausible move.

**Cues & ticks**

* **Sensory cue** adds transient evidence (vision/smell/sound/touch).

* **Autonomic tick** updates drives (e.g., hunger rises) and can emit drive flags.

**Instinct step**  
One step chosen by the controller using policies + drives + cues. You can accept/reject proposals.

**Planning**  
BFS-style search from the `NOW` anchor to any binding carrying a target predicate (`pred:<name>`), traversing directed edges.



***Q&A to help you learn this section***

Q: Binding vs Predicate?  A: Binding = node container, Predicate = symbolic fact carried by the binding.

Q: Edge label semantics today?  A: "then" = weak episode causality.

Q: Engram?  A: Pointer to heavy content (outside the graph).

Q: Provenance?  A: meta.policy records which policy created the node.

---

# Session Notes (Living Log)





* * *



# References





## 

### 

[Navigation Map-Based Artificial Intelligence](https://www.mdpi.com/2673-2688/3/2/26)

[Frontiers | The emergence of enhanced intelligence in a brain-inspired cognitive architecture](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1367712/full)

#### 

# Work in Progress

--

--
