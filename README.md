# CCA8  — Project Documentation -- Compendium (README.md)

*If you are new to CCA8: read 1-minute + 5-minute summary, try the 5-step demo, then jump to ‘The WorldGraph in detail’ and ‘Action Selection’.*

*The Tutorials below (see Table of Contents) are designed to teach you the practical aspects of the CCA8 as well as some of the theory behind it.*

Questions?  Send me an email: hschneidermd@alum.mit.edu



# **1-minute summary**

The CCA8 Project is the simulation of the brain of a mountain goat through the lifecycle with hooks for different robotic embodiments. 

Scaffolding in place (partially operational) for simulation of a chimpanzee-like brain, human-like brain, human-like brain with five brains operating in parallel in the same agent, human-like brain with multiple agents interacting, human-like brain with five brains operating in parallel with combinatorial planning ability.

This single document is the canonical “compendium” for the Causal Cognitive Architecture 8 (CCA8). It serves as: README, user guide, architecture notes, design decisions, and maintainer reference.

**Repo:** `https://github.com/howard8888/workspace`
**Entry point:** `>python cca8_run.py`  

*The program will run on most computers, although different sets of features (as well as embodiments, of course) will be available.*



<img title="Mountain Goat Calf" src="calf_goat.jpg" alt="loading-ag-2696" style="zoom:200%;">

*Adult Mountain Goat with recently born Calf (walking within minutes
of birth, and by one week can climb most places its mother can)*



**CCA8** Simulation of a mountain goat through the lifecycle 
**CCA8b** Simulation of a mountain goat-like brain with 5 brains within the same agent
**CCA8c** Simulation of multiple agents with goat-like brains able to interact
**CCA8d** Simulation of a mountain goat-like brain with 5 brains within the same agent with combinatorial planning
**CCA9** Simulation of a chimpanzee through the lifecycle
**CCA10** Simulation of a human through the lifecycle

*See **References** Section for published peer reviewed articles on the **CCA7** and earlier versions*



***Notes:***

-Versions of Python that will work with code:  check docstring of cca8_run.py or requirements.txt
   *(at time of writing, tested on Windows 11 Pro with Python 3.11.4)*

-Dependencies required:  check docstring of cca8_run.py or requirements.txt
     -*-> Software should be able to run on most systems without any issues (GPU and LLM API requirements, if used, are very fail-safe)*

-Windows: *>python cca8_run.py*   will also usually work, depending on Python setup; it will ignore the shebang line
(*>cca8_run.py* may work if Windows file associations set up for the Python version)

-Mac, Linux:  *>python3 cca8_run.py*

-Virtual environment Venv (*must activate*) (Windows, Mac or Linux):  *>python cca8_run.py*

-Graphical User Interface (GUI): Due to ongoing software development, the CCA8 Simulation is Command-Line Interface (CLI) only.  (Tkinter Windows GUI-based cca8_run.pyw module is available but not supported at this time.)

-Robotics real-world environment: You need to run the Python environment version of cca8_run.py as shown above, and specify the robotics embodiment as shown above. (Ensure that the correct hardware abstraction layer (HAL) exists and is installed for the robotics equipment version you are using.)



# **5-minute summary**



## Executive Overview

CCA8 aims to simulate early mammalian cognition with a **small symbolic episode index** (the *WorldGraph*) coordinating **rich engrams** (perceptual/temporal content) in a column provider. Symbols are used for **fast indexing & planning**, not as a full knowledge store.

**Core model:**

- **Binding** — a node instance that *carries* one or more tags, including `pred:<token>`, plus `meta` and optional `engrams`; bindings can hold predicates pred:<tag>, actions action:<tag>, anchors, cues

- **Edge** — a directed link between bindings with a label (often `"then"`) representing **weak, episode-level causality** (“this led to that”).  

- **WorldGraph** — the directed graph composed of these bindings and edges, supports **BFS planning**.  

- **Policy (primitive)** — an instinctive behavior with `dev_gate(ctx)` + `trigger(world, drives, ctx)` + `execute(world, ctx, drives)`. Each tick, CCA8 forms a candidate set (dev_gate + trigger + safety filters) and selects ONE winner: drive-urgency “deficit” score → non-drive priority → (if RL enabled: epsilon exploration / learned q tie-break) → stable policy order.

- **Provenance** — when a policy creates a new binding, its name is stamped into `binding.meta["policy"]`.  

- **Autosave/Load** — a JSON snapshot persists (world, drives, skills) with `saved_at`, written via atomic replace.
  *--> See Tutorial Sections below for more information*
  
  

## Newborn Mountain Goat: stand → mom → nipple → drink (5-step demo)

Here is a concrete example of a short episode you can build by hand or through the menu.
*(Note: Software may change in the future. If exact menu selections are not available, please choose similar items. Nov, 2025.)*

1) Start or resume

`python cca8_run.py --autosave session.json`

Pick **Profile 1: Mountain Goat** when prompted.

2) Note binding IDs you’ll need

**Show last 5 bindings**  anytime to grab the newest IDs you create.

3) (Optional) Prime drives and cues
* Select 'Autonomic tick' once or twice, then `D` Show drives (aim for `drive:hunger_high`).

* Select Add sensory cue a few times:
  
  * `vision` → `silhouette:mom`
  
  * `smell` → `milk:scent`
  
  * `sound` → `bleat:mom`
4) Create milestones (add predicates), then wire edges

**A. Stand first**

1. Add predicate → `stand` → note ID, e.g., `b2`.

2. Connect two bindings:
   
   * Source: `<NOW_id>` (e.g., `b0`)
   
   * Destination: `<stand_id>` (e.g., `b2`)
   
   * Relation: `stand_up`

**B. Approach mom**

1. Add predicate → `mom:close` → note ID, e.g., `b3`.

2. Connect:
   
   * Destination: `<mom_id>` (e.g., `b3`)
   
   * Relation: `approach`

**C. Find nipple**

* Source: `<stand_id>` (e.g., `b2`)
1. Add predicate → `nipple:found` → ID `b4`.

2. Connect `b3 → b4` with relation `search`.

**D. Latch**

1. Add predicate → `nipple:latched` → ID `b5`.

2. Connect `b4 → b5` with relation `latch`.

**E. Drink**

1. Add predicate → `milk:drinking` → ID `b6`.

2. Connect `b5 → b6` with relation `suckle`.
5) Verify with planning
* Plan from NOW → `<predicate>`

* Target: `milk:drinking`

* Expect a path like: NOW (b0) → stand (b2) → mom:close (b3) → nipple:found (b4) → nipple:latched (b5) → milk:drinking (b6)

----------------------------



**Useful Command-line Quickstarts:**

Start a new simulation: *>python cca8_run.py*

Start a new simulation and autosave it:  *>python cca8_run.py --autosave mysession.json*

Resume a previous simulation and autosave it to the same file:
         *>python cca8_run.py  --load mysession.json --autosave mysession.json*

Resume a previous simulation and autosave it to a new file:
         *>python cca8_run.py  --load mysession.json --autosave newfile.json*

(Note: the order of --load and --autosave doesn't matter )

Version info (all components): *>python cca8_run.py --about*

Runner (main program) Version only: *>python cca8_run.py --version*

Preflight self-testing (four parts):   *>python cca8_run.py --preflight*

Use with robotic embodiment: *>python cca8_run.py --hal --body myrobot*



**CCA8 Python Major Modules:**

cca8_run.py (informal name: "Runner module" or "Main module")

cca8_world_graph.py (informal name: "WorldGraph module")

cca8_column.py  (informal name: "Column module")

cca8_controller.py  (informal name: "Controller module")

cca8_features.py  (informal name: "Features module")

cca8_temporal.py (informal name: "Temporal module")

cca8_env.py (informal name: "Environment module")

cca8_test_worlds.py (informal name: "Test Worlds module")





### Q&A to help you learn the big picture

Q: What is the core split in CCA8’s memory representation?
A: A small symbolic WorldGraph (~5%) used for fast indexing and planning, and rich engrams (~95%) stored in Columns. The graph knows “what led to what”; the engrams hold heavy perceptual/temporal content.

Q: In the 5-step newborn demo, what does the planner actually search over?
A: It runs BFS from the NOW anchor over directed edges and looks for any binding whose tags contain the target pred:<token> (e.g., pred:milk:drinking). It doesn’t care about engram payloads; only tags and edges matter for planning.

Q: Why is StandUp the first primitive in the newborn goat’s repertoire?
A: Because standing up is a precondition for almost everything else in the newborn vignette (orienting to mom, seeking the nipple, moving to shelter). It’s both ethologically plausible and structurally convenient: it creates the first meaningful S–A–S pattern (fallen → actions → standing) in the WorldGraph.

Q: Where is provenance recorded in step 5 (drink)?
A: On each binding created by a policy, e.g.
binding.meta["policy"] = "policy:seek_nipple" or "policy:suckle". This lets you reconstruct “which policy wrote this node” when reading graphs or debugging.

Q: Why did you decide to keep control flow (policies) outside the graph instead of encoding everything as rules in the graph?
A: To keep the system readable, testable, and flexible. Small, handwritten policies are easy to reason about and modify; the graph records what actually happened (episodes), not entire control logic. This follows the “index vs representation” and “program + data” split, rather than trying to cram cognition into a single giant graph.

Q: Which primitives form “standing”?  
A: `action:push_up`, `action:extend_legs`, and the predicate `pred:posture:standing` (based on the `posture:standing` tag).

Q: What’s the planner algorithm?  
A: BFS from NOW to the first pred:<token> match.

Q: What’s the key separation in CCA8?  
A: A compact symbolic episode index** (WorldGraph) for fast lookup/plan, and rich engrams** outside the graph for heavyweight content.

Q: Are edges logical implications?  
A: No—edges encode weak, episode-level causality** (“then”), good for action and recall without heavy inference.

Q: Why not store everything in the graph? 
A: Keeping symbols small avoids brittleness and keeps planning fast, the heavy 95% lives in engrams referenced by bindings.

Q: How does this help planning? 
A: BFS over a sparse adjacency list gives shortest-hop paths quickly, the graph is shaped for that.

---



# Table of Contents

**Introduction to the Causal Cognitive Architecture 8 (CCA8)**

- [Executive Overview](#executive-overview)
- [Opening screen (banner) explained](#opening-screen-banner-explained)
- [Profiles (1–7): overview and implementation notes](#profiles-17-overview-and-implementation-notes)
- [The WorldGraph in detail](#the-worldgraph-in-detail)
- [Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)](#tagging-standard-bindings-predicates-cues-anchors-actions-provenance--engrams)
- [Restricted Lexicon (Developmental Vocabulary)](#restricted-lexicon-developmental-vocabulary)
- [Signal Bridge (WorldGraph ↔ Engrams)](#signal-bridge-worldgraph--engrams)
- [Architecture](#architecture)
  - [Modules (lean overview)](#modules-lean-overview)
  - [Timekeeping in CCA8 (five measures)](#timekeeping-in-cca8-five-measures)
  - [Data flow (a controller step)](#data-flow-a-controller-step)
- [Action Selection: Drives, Policies, Action Center](#action-selection-drives-policies-action-center)
- [Planner Contract](#planner-contract)
- [Planner: BFS vs Dijkstra (weighted edges)](#planner-bfs-vs-dijkstra-weighted-edges)
- [Persistence: Autosave/Load](#persistence-autosaveload)
- [Runner, menus, and CLI](#runner-menus-and-cli)
- [Logging & Unit Tests](#logging--unit-tests)
- [Preflight (four-part self-test)](#preflight-four-part-self-test)
- [CCA8 as a Robotic Cognitive Operating System (RCOS)](#cca8-as-a-robotic-cognitive-operating-system-rcos)
- [Hardware Abstraction Layer (HAL)](#hardware-abstraction-layer-hal)
- [Hardware preflight lane (status stub)](#hardware-preflight-lane-status-stub)
- [How-To Guides](#how-to-guides)
- [Data schemas (for contributors)](#data-schemas-for-contributors)
- [Traceability (requirements to code)](#traceability-requirements-to-code)
- [Roadmap](#roadmap)
- [Debugging Tips (traceback, pdb, VS Code)](#debugging-tips-traceback-pdb-vs-code)
- [FAQ / Pitfalls](#faq--pitfalls)
- [Intro Glossary](#intro-glossary)

**Tutorials and technical deep dives**

- [Tutorial on WorldGraph, Bindings, Edges, Tags and Concepts](#tutorial-on-worldgraph-bindings-edges-tags-and-concepts)
- [Binding and Edge Representation](#binding-and-edge-representation)
- [Anchors, LATEST, and Base-Aware Writes](#anchors-latest-and-base-aware-writes)
- [Tutorial on Drives](#tutorial-on-drives)
- [Tutorial on WorldGraph Technical Features](#tutorial-on-worldgraph-technical-features)
- [Tutorial on Breadth-First Search (BFS) Used by the CCA8 Fast Index](#tutorial-on-breadth-first-search-bfs-used-by-the-cca8-fast-index)
- [Tutorial on BodyMap](#tutorial-on-bodymap)
- [Tutorial on Main (Runner) Module Technical Features](#tutorial-on-main-runner-module-technical-features)
- [Tutorial on Controller Module Technical Features](#tutorial-on-controller-module-technical-features)
- [Tutorial on Reinforcement Learning in the CCA8](#tutorial-on-reinforcement-learning-in-the-cca8)
- [Tutorial on Temporal Module Technical Features](#tutorial-on-temporal-module-technical-features)
- [Tutorial on Features Module Technical Features](#tutorial-on-features-module-technical-features)
- [Tutorial on Column Module Technical Features](#tutorial-on-column-module-technical-features)
- [Tutorial on Approach to Simulation of the Environment](#tutorial-on-approach-to-simulation-of-the-environment)
- [Tutorial on Environment Module Technical Features](#tutorial-on-environment-module-technical-features)
- [Planner contract (for maintainers)](#planner-contract-for-maintainers)
- [Persistence contract](#persistence-contract)

**References and Notes**

- [References](#references)
- [Developer and Maintainer Notes](#developer-and-maintainer-notes)
  
  
  
  

# INTRODUCTION TO THE CAUSAL COGNITIVE ARCHITECTURE 8 (CCA8)

# Opening screen (banner) explained

**Opening screen:**

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
Please make a choice [1-7]:*



**What each part means:**

* Version and path: printed by the runner, the version comes from `__version__` in the runner. The path helps confirm which file you launched.

* OS/flags line: a reminder that you can run `--help` or the non-interactive flags such as `--about`, `--plan`, `--preflight`.

* Embodiment (HAL/body): shows whether the hardware abstraction layer is enabled and which body profile (if any) was provided. The current build runs fine with HAL off.

* Profile menu: seven presets that configure or demonstrate different cognitive configurations (documented below). Selection is handled by `choose_profile`, which records your choice in the runtime context and proceeds with the session.
  
  

### Q&A to help you learn this section

Q: Why does the banner show a full filesystem path to cca8_run.py?
A: To make it obvious which file you actually launched (and from where). This avoids confusion if you have multiple checkouts or stale copies; you can confirm you’re running the expected entry point.

Q: What is the practical use of the OS/flags line (win32, --help, etc.)?
A: It reminds you that (1) you’re on a particular platform (Windows/macOS/Linux), which may affect file paths and HAL support, and (2) you can always run --help, --about, or --preflight from the CLI instead of entering the menu.

Q: What does “HAL (hardware abstraction layer) setting: off” actually mean?
A: It means the simulation is currently running headless: policies and WorldGraph are active, but no physical robot or real sensors are connected. When HAL is ON with a body profile, controller outputs can be forwarded to hardware via the HAL.









# Profiles (1–7): overview and implementation notes

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

### Q&A to help you learn this section

Q: Which profile should I use for real experiments right now?
A: Use Profile 1 (mountain goat). At the time of this writing, it's the profile that is fully wired to drives, policies, the newborn storyboard environment, and the runner. The others are narrative/dry-run stubs that fall back to Profile 1.

Q: Do the multi-brain / multi-agent profiles modify the live WorldGraph today?
A: No. At present, they typically operate on sandbox copies of the world (or separate worlds) and print results, but they do not commit changes back to the live WorldGraph. That keeps the core goat simulation deterministic and easy to reason about.

Q: What is the practical difference between “human-like” and “super-human-like” profiles today?
A: At the time of writing, the difference is mainly in the story and trace they print: the “super-human-like” profile demonstrates a dry-run meta-controller that arbitrates between heterogeneous proposal sources. Neither profile currently runs a distinct, fully human-level cognitive architecture; they are scaffolds for future work.

Q: How do profiles interact with the rest of the code?
A: Each profile sets initial parameters in Ctx (sigma, jump, profile label), may run a stub/demo, and then hands control back to the same runner loop. The WorldGraph, controller, and environment interfaces remain the same; only initial configuration and demonstration traces change.





# The WorldGraph in detail

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
   
   

**Indexing & goal resolution (how the planner finds a match)**

The planner checks each popped node’s tags for a goal predicate (`pred:<token>`). Implementations may also keep a tiny tag→binding index to accelerate goal detection on large runs. Either way, a match is defined as “any binding whose `tags` contains the requested goal token.” If multiple candidates exist, BFS guarantees the first one popped is on a shortest-hop path from the start. This makes planning both predictable and easy to reason about in logs and demos.

**Edge-label conventions (house style)**



* Operationally, **all edges mean “then”**: “this binding tended to be followed by that binding in this episode”.

* The **default label** is `"then"`. You may use **short domain labels** as human-facing aliases when helpful, but the engine treats them as “then”:
  
  * `approach`: locomote toward a target (`standing → mom:close`).
  * `search`: information-seeking (`mom:close → nipple:found`).
  * `latch`: discrete contact (`nipple:found → nipple:latched`).
  * `suckle`: sustained feeding (`nipple:latched → milk:drinking`).
  
  Think of these as `"then (approach)"`, `"then (search)"` etc.

* **Actions themselves live as `action:*` bindings** in the graph (e.g., `action:push_up`, `action:extend_legs`). Policies create small **predicate–action–predicate** chains by connecting predicate states and action bindings with `then` edges.
  
  

**Consistency invariants (quick checklist)**

* Every binding has a unique `id` (`bN`), and **anchors** (e.g., `NOW`) map to real binding ids.

* Edges are **directed**, the adjacency lives on the **source** binding’s `edges[]`.

* A binding without edges is a valid **sink**.

* The first `pred:*` tag is used as the default UI label, if absent, the `id` is shown.

* Snapshots must restore `latest`, anchor ids, and advance the internal `bN` counter beyond any loaded ids.

**Scale & performance notes**

For development scale (up to hundreds of thousands of bindings), the dict-of-lists adjacency plus a `deque` frontier is fast and transparent. If the graph grows toward tens of millions of edges, swap the backend (e.g., CSR or a KV store) behind the same interface without changing runner semantics or user-facing behavior..

**Families recap.** WorldGraph stores only `pred:*`, `action:*`, `cue:*`, and `anchor:*`. The controller may compute `drive:*` **flags** for triggers, but they are never written into the graph unless you explicitly add `pred:drive:*` or `cue:drive:*`.



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

The controller tracks simple drives (hunger, fatigue, warmth). Policies consume those signals and look for tags in the WorldGraph or context to decide whether to act. 

The Action Center evaluates all policies that pass dev gating, forms a triggered candidate set, and selects ONE winner. By default (non-RL), winner = highest drive-urgency “deficit” → non-drive priority → stable policy order. With RL enabled, epsilon may choose a random candidate (exploration); otherwise exploitation chooses within the near-best deficit band (rl_delta) and breaks ties by non-drive → learned value q → stable policy order.


Example (stand up):

Example (stand up):

* Trigger: `posture:fallen` is near NOW and the body is not severely fatigued.
* Execute: emit an `action:push_up` binding and an `action:extend_legs` binding, then a `pred:posture:standing` binding, linked in a short chain from NOW/LATEST with `then` edges.
  
  

***Q&A to help you learn this section***
Q: How is an action chosen each tick?   
A: Policies are first filtered by dev_gate + safety overrides, then triggers are evaluated to form a candidate set. The winner is chosen by: deficit (drive urgency) → non_drive priority → (RL: q tie-break inside the near-best deficit band; non-RL: stable order). In RL mode, epsilon can also pick a random candidate (exploration).

Q: What prevents re-firing the same action?   
A: Guards in `trigger()` (e.g., StandUp checks that standing isn’t already true).

Q: What does a policy return?   
A: A small status dict (policy name, ok/fail/noop, reward, notes) and it stamps provenance on any binding it creates.

Q: What if drive predicates aren’t available?   
A: Policies degrade gracefully by relying on existing graph tags, the system keeps running.





### Gating versus Triggering versus Executing

How do policies work in the CCA8 architecture?

You should think of how policies work in terms of three states (which actually map very cleanly to what CCA8 is doing in code):

1. **Gating**

   * “Is this policy even allowed in the candidate set right now?”
   * Includes:

     * `dev_gate(ctx)` (e.g., neonatal-only policies)
     * safety overrides (e.g., “if fallen, only allow StandUp/RecoverFall”)
   * Everything that fails here is **out** before we even look at drives or world.

2. **Triggering**

   * For the policies that passed gating:
     “Given world + drives + BodyMap, does this policy *want* to fire now?”
   * Implemented by each policy’s `trigger(world, drives, ctx)`.
   * If `trigger(...)` is `True` → the policy is **triggered** and joins the **candidate list** for this tick.

3. **Executing**

   * Among all **triggered** policies, pick one to actually run.
   * This is where we define “best”:

     * drive deficit scores (hunger vs fatigue, etc.),
     * maybe a preferred action,
     * tie-breaking / ordering.
   * The winner gets:

     * logged as `[executed] policy:...`,
     * its primitive run in the Action Center,
     * its name fed into `env.step(action=...)` next tick.

So in short:

 **Allowed → Triggered → Executed**
 (gating → triggering → winner)



***Q&A to help you learn this section***

Q: What is a “policy” in CCA8?
A: A policy is a named behaviour like policy:stand_up, policy:seek_nipple, policy:follow_mom, or policy:rest. Each policy has:

a gate (dev + safety),

a trigger function,

and a primitive that actually runs when the policy is selected to execute.

Q: What does “gating” really do?
A: Gating answers: “Is this policy even allowed to be considered right now?”
Examples:

dev_gate(ctx) filters out policies that don’t apply to the current profile (e.g., neonatal-only).

The safety override may say “if BodyMap says fallen, only allow StandUp/RecoverFall.”
If a policy fails gating, its trigger is never even called that tick.

Q: How is “triggering” different from “gating”?
A: Gating is a coarse include/exclude filter. Triggering is a context check for policies that survived the gate:

Gating: “Am I even allowed in the candidate set?”

Triggering: “Given world + drives + BodyMap, do I want to fire now?”

Triggering is implemented by trigger(world, drives, ctx). If this returns True, the policy is marked as triggered and joins the candidate list.

Q: Can a policy pass gating but fail to trigger?
A: Yes. For example, policy:rest might:

Pass gating (dev + safety say it is allowed), but

Fail trigger if fatigue is below FATIGUE_HIGH or zone is unsafe.

In that case, Rest is “allowed in principle” but does not join the triggered candidate set for that tick.

Q: Can multiple policies trigger in the same tick?
A: Yes. For example, both SeekNipple and Rest can be triggered if hunger and fatigue are both high and zone is safe. In that case, they both enter the candidate list and the execution stage must pick a winner.

Q: How do we choose which triggered policy actually executes?
A: Execution is handled by the Action Center / PolicyRuntime:

It takes the triggered policies,

Computes some notion of “best” (e.g., drive deficit scores, preferred action, ordering),

Chooses a single winner for this tick.

That winner:

is logged as [executed] policy:...,

runs its primitive,

and its name becomes the action string for env.step(...) in the next environment tick.

Q: Where does the safety override fit into this picture?
A: Safety is implemented as an extra gating layer:

First, we collect policies that pass dev_gate(ctx) and trigger True.

Then, if _fallen_near_now(...) says “fallen”, we filter that list down to a small safety set (e.g., {StandUp, RecoverFall}).

Only after that do we pick the “best” policy to execute.

So safety never directly executes a policy; it restricts which policies are even allowed to compete.

Q: How does this relate to what I see in the env-loop logs?
A: Roughly:

[gate:rest] ... lines show triggering and gating conditions (fatigue, zone, BodyMap freshness, etc.).

[env→controller] policy:... shows what the gate catalog and safety layer proposed for this tick.

[executed] policy:... (in the controller logs) shows which policy actually executed.

env.step(action='policy:...') uses that executed policy name to advance the storyboard and world geometry on the next environment tick.

In other words, the logs are just different windows onto the three phases you summarized as:

Allowed → Triggered → Executed
(gating → triggering → winner)




### Persistence (snapshots):

A session snapshot is a JSON file that contains: the world graph (bindings + edges + internal counters), drives, minimal skill telemetry, and small context items. Saving is atomic, loading restores indices and advances the id counter so new bindings don’t collide with old ids.

Design decision: We use human‑readable JSON for portability and easy field debugging. A binary format would be smaller but harder to inspect. The JSON structure is stable enough to be versioned if we add fields later.

Design decision: A runner‑level “Reset” is preferable to ad‑hoc deletes when starting a clean demo—this guarantees counters and anchors are consistent.


***Q&A to help you learn this section***

Q: What exactly is persisted?   
A: Bindings, edges, anchors, id counters, drives, and simple skill telemetry, plus `saved_at`.

Q: Are saves safe against partial writes?   
A: Yes—snapshots are written via atomic replace.

Q: After load, why don’t my new nodes collide with old ids?   
A: The loader restores and **advances** the internal id counter.

Q: Binary vs JSON?   
A: JSON keeps sessions portable and debuggable, binary would be smaller but opaque.






## Memory systems in CCA8: BodyMap, WorkingMap, WorldGraph, and Engrams

CCA8 uses several small “maps” as well the large WorldGraph map for its memory store. The key idea is to separate:

- **what must be correct right now** (for action selection),
- **what we want to keep as a detailed trace** (for debugging / later consolidation),
- **what we want to keep long-term** (for planning and inspection),
- **and where heavy data lives** (engrams).

### 1) BodyMap (ctx.body_world): “what I believe right now”
BodyMap is a tiny, structured register for body + near-world state (e.g. in the case of the goat calf, its posture, mom distance, nipple state, shelter/cliff distances).

- Updated **every environment step** from EnvObservation.
- Used **BodyMap-first** for policy gating (e.g., don’t execute RecoverFall when posture is already standing).
- Can become “stale” if it hasn’t been updated recently; in that case, some gates fall back to WorldGraph.

Think of BodyMap as the “fast, always-on” body schema.

### 2) WorkingMap (ctx.working_world): short-term “write everything” trace
WorkingMap is a separate WorldGraph instance intended to log the raw tick-by-tick stream.

- It is deliberately **high bandwidth** and may contain repeated predicates/actions.
- It is capped by `working_max_bindings` so long runs don’t explode memory.
- It exists so we can keep a rich local trace **without forcing long-term memory** to store every redundant node.

WorkingMap is a good place for future consolidation rules:
“write everything to WorkingMap → copy/consolidate selected structure into WorldGraph”.

### 3) WorldGraph (long-term): symbolic episode index for planning + inspection
WorldGraph is the long-term symbolic episode index.

It contains:
- **actions and expected outcomes** written by policies (episodic “attempts”),
- and **selected summaries of environment state** (predicates/cues) that are useful for reasoning and planning.

#### Long-term EnvObservation → WorldGraph injection (“snapshot” vs “changes”)
When the environment produces discrete predicates (posture, proximity, hazards, etc.), we can choose how aggressively to log them in the long-term WorldGraph:

- `mode = snapshot`  
  Write every observed `pred:*` each tick (dense, easy to read, can spam repeated facts).

- `mode = changes`  
  Treat many env predicates as **state slots** (e.g., `posture`, `proximity:mom`, `hazard:cliff`) and write a new `pred:*` binding only when the slot changes.  
  This prevents “rewriting the same fact 4000×” while preserving transitions like fallen→standing→fallen.

Optional flexibility knobs:
- `reassert_steps` — re-emit unchanged slots periodically (so stable facts can be “re-observed” occasionally).
- `keyframe_on_stage_change` — force a snapshot-like refresh when the environment’s scenario stage changes (birth→struggle→first_stand…).

### 4) WorldGraph memory_mode: episodic vs semantic
WorldGraph also has an internal memory mode:

- **episodic**: every add creates a new binding (timeline-first).
- **semantic (experimental)**: identical pred/cue tags may be consolidated to a canonical binding (clutter reduction).

Important caution: semantic consolidation can make stale facts “look true forever” if code treats “tag exists anywhere” as “true now”.
The safe trajectory is:
- use **BodyMap / WorkingMap** for “current tick truth”,
- use **WorldGraph** for long-term structure and episodes.

### 5) Engrams (Column memory): heavy payloads live outside the graph
WorldGraph bindings are small. Rich content (vectors, sensory payloads, scene descriptors) is stored as **engrams** in Column memory.
Bindings can carry lightweight pointers to these engrams so you can keep the symbolic index compact while still retaining rich data.







### Mammalian / Human memory systems and their CCA8 equivalents (conceptual map)

This table is a *conceptual mapping*, not a claim of exact neuroanatomical equivalence. It is intended to help readers orient themselves: “if I know the human memory taxonomy, where does that live in CCA8?”

| Mammalian / human memory system | What it does (brain-side) | CCA8 equivalent (architecture / simulation) |
|---|---|---|
| **Sensory memory** (iconic / echoic / haptic) | Very short-lived sensory traces (sub-second to a few seconds) in primary sensory cortex pipelines | **HybridEnvironment → EnvObservation** as the “incoming perceptual stream” (raw_sensors + predicates + cues). Optionally, capture as **engrams** if you want persistence. The intent is that this stream is transient and can be configured for different time windows. |
| **Short-term memory** | Passive short holding buffer (~15–30s; classic “7±2” item framing) | **WorkingMap** as a short-term high-bandwidth trace (bounded by max_bindings) plus **BodyMap** as a tiny register. (CCA8 does not yet enforce strict capacity; instead it provides pruning knobs.) |
| **Working memory (overall)** | Short-term + active processing (“workspace”) | **WorkingMap + PolicyRuntime/Action Center + FOA/base mechanisms**. WorkingMap holds the local trace; PolicyRuntime/Action Center selects what to do next; FOA/base are the “what is currently relevant?” scaffolds. |
| • Central executive (WM component) | Attention control, selection, coordination | **PolicyRuntime / Action Center** (gating → triggering → executing) plus FOA selection. |
| • Phonological loop (WM component) | Verbal/auditory rehearsal system | Not a focus in the goat profile; future “human-like” profiles would likely map this to **column/engram payloads** + rehearsal-like controller loops. |
| • Visuospatial sketchpad (WM component) | Spatial/visual manipulation (“mind’s eye”) | **BodyMap + environment geometry** (near-space posture/mom/shelter/cliff) and (future) richer **engrams** for spatial scenes. |
| • Episodic buffer (WM component) | Integrates across WM subsystems and links to LTM | A future “bridge” layer: **WorkingMap → consolidation into WorldGraph/Columns** (partially scaffolded today; details still evolving). |
| **Long-term memory: episodic (explicit/declarative)** | Personal event memory; hippocampal indexing and retrieval | **WorldGraph** as the episode index + methods that reconstruct trajectories (bindings/edges with provenance). (CCA8 episodic details remain a design focus and will evolve.) |
| **Long-term memory: semantic (explicit/declarative)** | General knowledge/facts consolidated in cortex (semantic hub concepts) | **WorldGraph** as the symbolic index; optionally `memory_mode="semantic"` (experimental). Longer-term, “semantic engrams” belong in **Columns**, with WorldGraph as the pointer/index layer. |
| **Procedural memory (implicit/non-declarative)** | Skills/habits; basal ganglia + cerebellum involvement | **Controller policies/primitives** and their learned parameters (e.g., skill ledger / q values). This is “how to do things,” not “facts about the world.” |
| **Priming / classical conditioning (implicit)** | Learned associations (cue → response), often emotion/autonomic linked | **Autonomic + drive/threshold cues + learned primitives**: rising-edge interoceptive cues (`cue:drive:*`), valence tags, and policy selection shaping. (CCA8 currently expresses this via autonomic tick + cue/policy machinery; richer conditioning is future work.) |

Notes:
- Sensory memory: iconic/echoic/haptic timescales and cortical associations are listed in the companion document; CCA8 treats these as the **incoming observation stream** and can store them longer/shorter as needed.
- Working memory components and their cognitive roles are listed in the companion document; in CCA8 they map naturally onto “what is currently in focus” + the action selection machinery + short-term traces.
- Episodic vs semantic vs procedural vs priming/conditioning are listed in the companion document; CCA8’s current equivalents are WorldGraph for episodic/semantic indexing and Controller policies/autonomic machinery for procedural/conditioning-style behavior shaping.





## WorkingMap (Working Memory Graph)

CCA8 now maintains a **WorkingMap**, a short‑term “write everything” graph intended to hold the *full episodic trace* of what is happening tick‑by‑tick.

### Why a WorkingMap?

WorldGraph can become cluttered quickly when we log repeated predicates (e.g., posture, distances, cues) every tick. Biologically, this mirrors a common separation:

- **working / short‑term memory**: high‑bandwidth, constantly updated, may be pruned
- **long‑term memory**: lower bandwidth, consolidated, less redundant

WorkingMap lets us record the detailed stream without forcing long‑term memory to store every redundant node.

### Implementation

- `ctx.working_world` is a **separate** `WorldGraph` instance (WorkingMap).
- Environment observations are mirrored into WorkingMap on each tick (when enabled).
- WorkingMap is capped by `ctx.working_max_bindings` to prevent unlimited growth.
- WorkingMap is intended to become the source graph for consolidation policies later:
  “write everything to WorkingMap → copy/consolidate selected information into WorldGraph”.




### Runner controls

- **Menu #**: Control Panel (RL + memory knobs)
  - Toggle WorkingMap mirroring + verbosity + size cap
  - Set WorldGraph `memory_mode` (episodic vs semantic)
  - Configure long-term env observation injection (changes vs snapshot, reassert_steps, keyframes, verbose reuse)

- **Menu #**: WorkingMap snapshot
  - Print the last N bindings from WorkingMap
  - Optionally clear WorkingMap







### Menu Menu Selection — Control Panel (RL policy selection + memory knobs)

This menu selection is the main “knobs and buttons” control panel for CCA8 experiments. It lets you control:

how policies are selected (deterministic vs RL-assisted),

whether EnvObservation is written to WorkingMap, WorldGraph, or both,

how aggressively long-term environment observations are deduplicated,

and (Phase VII) whether the system logs long-term actions as “motor program runs” rather than decision ticks.

**Mental model (what these knobs are really controlling)**

At runtime, it helps to keep three graphs in mind:

BodyMap (ctx.body_world)
A tiny, safety-critical “what I believe right now” register (posture, mom distance, nipple state, shelter/cliff). Used for gating, safety, and tie-break logic.

WorkingMap (ctx.working_world)
A short-term raw trace scratchpad (dense, tick-level). It is pruned by working_max_bindings and is intended to hold detail that we do not want to commit to long-term memory.

WorldGraph (world)
The durable long-term episode index that persists (autosave/save session). It holds a sparse symbolic record for planning/inspection.

EnvObservation injection follows this fixed pipeline:

EnvObservation → BodyMap update (always) → WorkingMap mirror (if enabled) → WorldGraph injection (if enabled)

So WorkingMap is normally a mirror, not a redirect: if WorkingMap and long-term env obs are both enabled, EnvObservation is written to both (WorkingMap every tick, WorldGraph according to its long-term injection settings).

**Presets (long-term env obs)**

Presets are shortcuts that set only the “Long-term EnvObservation → WorldGraph injection” knobs.

bio
mode=changes, keyframes on, reassert_steps=25
Rationale: sparse long-term growth, but periodically re-assert stable state slots to mimic re-observation.

sparse
mode=changes, keyframes on, reassert_steps=0
Rationale: minimal long-term growth (write only on slot change + keyframes).

debug
mode=snapshot, verbose on
Rationale: maximal visibility (writes every env predicate each tick; will be noisy).

**RL policy selection knobs (epsilon-greedy among triggered candidates)**

These knobs only matter when more than one policy is eligible/triggered and we must choose a single winner.

rl_enabled (bool)

OFF: deterministic heuristic selection (deficit → non-drive priority → stable order).

ON: epsilon-greedy selection:

explore (probability epsilon): choose a random policy from the triggered candidate set.

exploit (probability 1 - epsilon): choose by deficit and tie-break logic (see rl_delta below).

rl_epsilon (float in [0.0, 1.0] or None)

Exploration probability.

0.0 means 0% explore (always exploit).

0.10 means 10% explore.

Values are clamped to [0.0, 1.0].

Important: if rl_epsilon is None, the “effective epsilon” falls back to ctx.jump.
This is a convenience reuse of the existing jump knob (originally meant for TemporalContext boundaries), and it means RL can still explore even if epsilon prints as None.

If you want RL enabled but no randomness, explicitly set:

rl_enabled = on

rl_epsilon = 0.0

rl_delta (float, >= 0.0)

Defines the “near-best deficit band” inside the exploit branch:

Compute best_deficit = max(deficit(policy)) over triggered candidates.

Define near_best as those policies where (best_deficit - deficit(policy)) <= rl_delta.

Meaning:

rl_delta = 0.0: learning/tie-breaks only matter on exact deficit ties (most conservative).

larger rl_delta: more policies qualify as “near-best” and learning can influence more choices.

Within the near-best band, the system breaks ties by:

non-drive priority (explicit tie-break logic),

learned value estimate q (skill ledger),

then stable order as the final deterministic fallback.

**WorkingMap (short-term raw trace)**

working_enabled (bool)

ON: mirror every EnvObservation into WorkingMap (dense per-tick trace).

OFF: WorkingMap exists but receives no new env predicates/cues.

Note: WorkingMap mirroring does not automatically disable long-term injection; if long-term env obs is still enabled, EnvObservation will be written to both.

working_verbose (bool)

ON: prints per-tick [env→working] ... lines for env injection into WorkingMap.

working_max_bindings (int)

Caps WorkingMap size; pruning deletes older non-anchor bindings to prevent unlimited growth.

**Phase VII memory pipeline (experimental)**

These knobs are used to move toward a WorkingMap-first pipeline and “motor program runs, not decision ticks”.

phase7_working_first (bool)

If ON, the controller executes policy writes into WorkingMap rather than into the long-term WorldGraph. This helps keep WorldGraph sparse while WorkingMap remains dense.

This is currently most relevant to the closed-loop environment run (menu 37).

phase7_run_compress (bool)

If ON, long-term WorldGraph records policy actions as compressed “runs” rather than per-tick action spam.

High-level behavior:

If the same policy repeats across consecutive env steps, do not create a new long-term action binding each tick.

Instead, extend one run record (run_len++) and update the run’s end-state pointer.

Split/close the run on boundary signatures (e.g., stage/posture/nipple/zone changes) or when policy changes.

Net effect:

Long-term WorldGraph becomes: keyframe state → run(action) → keyframe state → …

In the menu implementation, enabling run_compress typically turns working_first on automatically (because run compression makes the most sense when dense tick-level detail is kept in WorkingMap).

phase7_run_verbose (bool)

If ON, prints run-compression debug lines such as: start / extend / close run.

phase7_move_longterm_now_to_env (bool)

Controls anchor semantics for long-term NOW in mode=changes.

OFF: NOW only moves when new long-term predicate bindings are written (or at keyframes).

ON: long-term NOW is actively moved to the current environment “state binding” each step (useful for NOW-relative debugging when changes-mode suppresses writes).

**WorldGraph memory_mode (long-term storage strategy)**
episodic (default)

Every add_predicate(...) / add_cue(...) creates a fresh binding.
This preserves a literal “event log” timeline (new node per occurrence), which is easiest for ordering and debugging.

semantic (experimental)

Identical pred/cue tokens are consolidated (reused) to reduce clutter.
This reduces node explosion but changes temporal semantics: repeated occurrences can collapse onto one node. Use with caution if you rely on “the chain itself” as a literal time axis.

**Long-term EnvObservation → WorldGraph injection**
longterm_obs_enabled (bool)

ON: env predicates/cues are written to WorldGraph (subject to mode settings).

OFF: env predicates/cues are not written to WorldGraph (BodyMap still updates; WorkingMap still mirrors if enabled).

longterm_obs_mode (changes vs snapshot)

snapshot: write every observed env predicate each tick (dense, old behavior).

changes: treat env predicates as “state slots” (posture, proximity:mom, hazard:cliff, …) and write only when a slot changes.

In changes mode, the system deduplicates per slot using a slot cache:

first time a slot is seen → emit (“first”)

slot value changes → emit (“changed”)

unchanged → skip (unless reasserted)

longterm_obs_reassert_steps (int)

In changes mode: re-emit unchanged slots periodically after N controller steps (re-observation).

longterm_obs_keyframe_on_stage_change (bool)

Only meaningful in changes mode.

If ON: when scenario_stage changes (birth → struggle → first_stand …), clear the slot cache so the current state is written again as a keyframe (even if some values are unchanged). This is why you see a KEYFRAME log line and then a “rewrite” of stable predicates at stage boundaries.

longterm_obs_keyframe_log (bool)

If ON: print a one-line KEYFRAME message when a keyframe boundary clears the slot cache (helpful for debugging long-term representation).

longterm_obs_verbose (bool)

In changes mode: print verbose reuse lines when slots are unchanged (can be noisy).

**Clear actions (manual resets without env.reset)**
Clear WorkingMap now?

Clears WorkingMap (fresh short-term trace window without resetting the environment).

Clear long-term slot cache now?

Clears the long-term slot cache so the next env observation is treated as “first” for each slot (manual keyframe).

**Practical starter configs**

Minimal long-term growth (recommended default for closed-loop runs)

preset: sparse

RL: off

WorkingMap: on

WorldGraph memory_mode: episodic

Phase VII: off

Debug “why didn’t this write?”

preset: debug

WorkingMap verbose: on (briefly)

Phase VII experiment (WorkingMap-first + long-term runs)

WorkingMap: on

Phase VII: working_first=on, run_compress=on, run_verbose=on briefly

long-term env obs: changes + keyframes, reassert=0

WorldGraph: episodic (for now)

---







## WorldGraph memory modes: episodic vs semantic

WorldGraph supports two storage modes for predicates/cues:

### Episodic mode (default)

- Each `add_predicate(...)` / `add_cue(...)` creates a **new** binding.
- Best when you want a rich timeline and do not mind redundancy.

### Semantic mode (consolidated, experimental)

- Identical `pred:` / `cue:` tags are consolidated to a **single** canonical binding.
- Reduces repeated nodes in long‑term graphs and can improve readability.

**Important note:** If policy code treats “tag exists anywhere in WorldGraph” as meaning “true right now”, semantic mode can make stale facts appear permanently true. The safe trajectory is:

- use **WorkingMap / BodyMap** as the source of “current tick” state,
- use **WorldGraph (semantic)** as consolidated long‑term structure.

(Note at time of this writing: CCA8 is being developed in that direction; semantic mode is optin and intended for experimentation.)










# Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)

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
     `pred:born`, `pred:posture:fallen`, `pred:posture:standing`,  
     `pred:mom:close`, `pred:nipple:found`, `pred:nipple:latched`, `pred:milk:drinking`,  
     `pred:event:fall_detected`, `pred:goal:safe_standing`,  
     `pred:drive:hunger_high` (if you want a plannable drive condition).
   
   > The planner looks for `pred:*`. The **first** `pred:*` (if present) is used as the human label in pretty paths/exports.

2. **Cues — evidence/context you _notice_, not goals**
   
   * **Prefix:** `cue:`
   * **Purpose:** sensory/context hints for policy `trigger()` logic.
   * **Examples:**  
     `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:vision:silhouette:mom`,  
     `cue:terrain:rocky`, `cue:vestibular:fall`, `cue:touch:flank_on_ground`,  
     `cue:drive:hunger_high` (if used only as a trigger).
   
   > We **do not** plan to cues; they’re conditions that help decide which policy fires.

3. **Anchors — orientation markers**
   
   * **Prefix:** `anchor:` (e.g., `anchor:NOW`).
   * Also recorded in the engine’s `anchors` map, e.g., `{"NOW": "b1"}`.
   * A binding can be only an anchor (no `pred:*`) — that’s fine.

4. **Actions — motor / behavioral steps**
   
   * **Prefix:** `action:`
   * **Purpose:** explicit action/motor steps in **state–action–state** chains.
   * **Examples:**  
     `action:push_up`, `action:extend_legs`, `action:orient_to_mom`,  
     `action:bleat_twice`, `action:look_around`.
   
   > Actions are **bindings**, not edge types. Policies create `action:*` bindings and connect them between predicate states with `then` edges.

5. **Drive flags (controller-only)**
   
   * The controller computes ephemeral flags like `drive:hunger_high`, `drive:fatigue_high`, `drive:cold` from numeric levels.
   * These bare `drive:*` strings are **not** stored in the WorldGraph.
   * If you want a persisted/plannable drive condition, use `pred:drive:*` (pred) or `cue:drive:*` (trigger).

### Actions = bindings; edge labels are “then” (with optional history)

* **Actions are their own bindings**: they carry `action:*` tags inside the same WorldGraph as predicates/cues/anchors.
  Typical pattern for `policy:stand_up`:
  
  ```text
  (state)  pred:posture:fallen
     │
     ├─then→  (action) action:push_up
     │
     ├─then→  (action) action:extend_legs
     │
     └─then→  (state)  pred:posture:standing
  
  ```

* Edges are **conceptually all “then”** (episode flow). The `label` field is kept mainly for readability and history. The default label is `"then"`.

* If you prefer, you can still use **domain labels** as _synonyms_ for “then” (e.g., `"approach"`, `"search"`, `"latch"`, `"suckle"`) when it helps humans read the path. The engine treats them as “then” for planning.

* Put **quantities** about the transition (meters, duration, success, etc.) in **`edge.meta`**, not in tags:

{
"to": "b101",
  "label": "then",        // or "search" as a human-facing alias
  "meta": {
    "meters":  8.5,
    "duration_s": 3.2,
    "created_by": "policy:seek_nipple"
  }
}



The planner today is **structure-first**: it follows edges, ignores labels for correctness, and looks only at node tags to detect goals. Later, labels/meta can inform **costs** (Dijkstra/A*) or filters (“avoid transitions marked as recover_fall”).



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



```markdown
| Family     | Examples                                                                                                                                                           | Purpose                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `pred:`    | `pred:born`, `pred:posture:standing`, `pred:nipple:latched`, `pred:milk:drinking`, `pred:event:fall_detected`, `pred:goal:safe_standing`, `pred:drive:hunger_high` | planner targets; human labels        |
| `cue:`     | `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:vision:silhouette:mom`, `cue:terrain:rocky`, `cue:vestibular:fall`                                                  | policy triggers; not planner goals   |
| `anchor:`  | `anchor:NOW`, `anchor:HERE`                                                                                                                                        | orientation; also in `anchors` map   |
| `action:`  | `action:push_up`, `action:extend_legs`, `action:orient_to_mom`, `action:bleat_twice`                                                                              | explicit motor / behavioral steps    |
| Edge label | `then` (default), and optional human aliases like `"approach"`, `"search"`, `"latch"`, `"suckle"`                                                                  | episode flow; semantics = “then”     |
```



### Do / Don’t

* Use **one** predicate prefix: `pred:*` for states/goals/events (and drives, per project default above).

* Keep **cues** separate (`cue:*`), used by policies (not planner goals).

* Put creator/time/notes in **`meta`**; put action measurements in **`edge.meta`**.

* Allow anchor-only bindings (e.g., `anchor:NOW`).

* Don’t invent ad-hoc families like `state:*`; stick to the four canonical families: `pred:*`, `action:*`, `cue:*`, `anchor:*`.

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







# Restricted Lexicon (Developmental Vocabulary)

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



# Architecture

## Modules (lean overview)

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





* * *

## Timekeeping in CCA8 (five measures)

CCA8 uses four orthogonal time measures. They serve different purposes and are intentionally decoupled.

**1) Controller steps** — one Action Center decision/execution loop (aka “instinct step”).  
*Purpose:* cognition/behavior pacing (not wall-clock).  
*Source:* a loop in the runner that evaluates policies once and may write to the WorldGraph. When that write occurs, we mark a **temporal boundary (epoch++)**. :contentReference[oaicite:0]{index=0}

With regards to its effects on timekeeping, **when a Controller Step occurs**:
i) **controller_steps**: ++ once per controller step  
ii) **temporal drift**: ++ (one soft-clock drift) per controller step  
iii) **autonomic ticks**: no change  
iv) **developmental age**: no change  
v) **cognitive cycles**: ++ if there is a write to the graph (nb. need to change in the future)
                               Cognitive cycles are currenlty counted only in Instinct Step (productive writes) (to change in future)

With regards to terminology and operations that affect controller steps:
**“Action Center”** = the engine (`PolicyRuntime`).
**“Controller step”** = one invocation of that engine.
**“Instinct step”** = diagnostics + **one controller step**.
**“Autonomic tick”** = physiology + **one controller step**.
**“Simulate fall”** = inject fallen + **one controller step** (no drift) (but no cognitive cycle increment)

**2) Temporal drift** — the *soft clock* (unit vector) that drifts a bit each step and jumps at boundaries.  
*Purpose:* similarity + episode segmentation that’s unitless and cheap (cosine of current vs last-boundary vector).  
*Drift call:* `ctx.temporal.step()`; *Boundary call:* `ctx.temporal.boundary()`; vectors are re-normalized every time. See module notes on drift vs boundary. :contentReference[oaicite:1]{index=1}  
*Runner usage:* we drift once per instinct step and once per autonomic tick in the current build; boundary is taken when an instinct step actually writes new facts. :contentReference[oaicite:2]{index=2}

**3) Autonomic ticks** — a fixed-rate heartbeat (physiology/IO), independent of controller latency.  
*Purpose:* hardware/robotics cadence; advancing drives; dev-age.  
*Source variable:* `ctx.ticks` (int).  
*Where incremented today:* the **Autonomic Tick** menu path increments `ticks`, nudges drives, and performs a drift; it can also trigger a thresholded boundary. :contentReference[oaicite:3]{index=3} :contentReference[oaicite:4]{index=4}

**4) Developmental age (days)** — a coarse developmental measure used for stage gating.  
*Source variable:* `ctx.age_days` (float), advanced along with autonomic ticks; used by `world.set_stage_from_ctx(ctx)`. :contentReference[oaicite:5]{index=5}

**5) Cognitive cycles** — a derived counter for end-to-end loops that **produced an output**  
(sense → decide → act that resulted in a write).

*Purpose:* progress gating & timeouts (e.g., “if no success in N cycles, switch strategy”), analytics.

*Source variable:* `ctx.cog_cycles` (int).  
*Runner rule (current build):* increment when an Instinct step **returns `status=="ok"` and the graph grew** (bindings_after > bindings_before).  
*Contrast with controller steps:* a controller **step** runs every time you invoke the Action Center once; a **cognitive cycle** only increments on steps that actually produced an output/write.

*Recommended invariants:* `cog_cycles ≤ controller_steps`; epochs increment only on boundary jumps (writes or τ-cuts), never decrement.

### Event boundaries & epochs

When the controller **actually writes** (graph grew), we take a **boundary jump** and increment `ctx.boundary_no` (epoch). We also update a short fingerprint of the boundary vector (`ctx.boundary_vhash64`) for snapshot readability. :contentReference[oaicite:6]{index=6}  
A thresholded segmentation (“τ-cut”) can also force a boundary when `cos_to_last_boundary` falls below τ (default shown in code). :contentReference[oaicite:7]{index=7}

### Source fields & helpers at a glance

- **autonomic ticks:** `ctx.ticks` (runner increments) :contentReference[oaicite:8]{index=8}  
- **developmental age:** `ctx.age_days` (runner increments) & `world.set_stage_from_ctx(ctx)` :contentReference[oaicite:9]{index=9}  
- **temporal drift:** `ctx.temporal.step()`; **boundary:** `ctx.temporal.boundary()`; **epoch:** `ctx.boundary_no++` :contentReference[oaicite:10]{index=10}  
- **soft-clock fingerprints:** current `ctx.tvec64()`; last boundary `ctx.boundary_vhash64`; cosine via `ctx.cos_to_last_boundary()` (shown in snapshot/probe UIs). :contentReference[oaicite:11]{index=11}

### Recommended invariants

- Controller-driven mode (today): each instinct **controller step** performs one **temporal drift**; boundary (epoch++) only on a real write. :contentReference[oaicite:12]{index=12}  
- Autonomic-driven mode (future HAL): **drift** belongs to the heartbeat; controller step reads time but does not drift.  
- Epochs never decrement; `cos_to_last_boundary` resets ≈1.000 on boundary. :contentReference[oaicite:13]{index=13} 
  
  

## Data flow (a controller step)

1. Action Center computes active **drive flags**.  
2. Evaluates dev gates + triggers to form a candidate set; selects ONE winner by deficit → non_drive → (RL: q tie-break / epsilon explore) → stable order. 
3. `execute()` appends a **small chain** of predicates + edges to the WorldGraph, stamps `meta.policy`, returns a status dict, and updates the skill ledger.  
4. Planner (on demand) runs BFS from **NOW** to a target `pred:<token>`.  

### Q&A to help you learn this section

Q: What’s the difference between controller_steps and cog_cycles?
A: controller_steps counts every invocation of the Action Center (each time we ask “what should I do?”). cog_cycles only increments when a controller step actually produced a write to the WorldGraph in the Instinct step. So cog_cycles ≤ controller_steps by design.

Q: When do we increment ticks (autonomic ticks) versus controller_steps?
A: ticks increment only in the Autonomic Tick path (heartbeat: physiology, drive updates, time-based age). controller_steps increment whenever a controller step runs (Instinct step, Autonomic tick, simulate fall, env-loop, etc.). They are orthogonal measures.

Q: What is the semantic difference between age_days and ticks?
A: age_days is a coarse developmental clock (used to set lexicon stage and developmental gates), while ticks is a fine-grained physiological heartbeat counter. Typically age_days advances in proportion to ticks but on a much slower scale.

Q: What does a “temporal boundary” (epoch++) represent?
A: A boundary is taken when a controller step writes new facts (or when a thresholded τ-cut triggers). It’s a way of saying “a new episode chapter started here” in the soft-clock vector space. We then jump the temporal vector, increment boundary_no (epoch), and reset cos_to_last_boundary to ~1.0.

Q: Why do we maintain both wall-clock created_at timestamps and a soft temporal vector?
A: Wall-clock is great for logs and cross-run inspection, but awkward for unitless similarity and segmentation. The soft temporal vector gives a cheap, unitless notion of “near in time” (via cosine) and supports operations like “time-aware similarity” and “episode segmentation” without relying on wall-clock units.

---





# Action Selection: Drives, Policies, Action Center

- **Policies** are small classes with:
  
  - `trigger(world, drives) -> bool`  
  - `execute(world, ctx, drives) -> {"policy", "status", "reward", "notes"}`

- **Ordered list** `PRIMITIVES = [StandUp(), SeekNipple(), FollowMom(), ExploreCheck(), Rest(), ...]`.  
   Updated: `PRIMITIVES = [StandUp(), SeekNipple(), Rest(), FollowMom(), ExploreCheck(), ...]`  
  ( code now evaluates **Rest before FollowMom**.)

- **Action Center / PolicyRuntime** selects ONE policy per tick:
  - build candidates = dev_gate passes AND trigger(...) is True (plus safety filtering),
  - winner = highest deficit → non_drive → (RL: q tie-break inside near-best band; non-RL: stable order),
  - RL adds epsilon-greedy exploration: epsilon chooses a random candidate; otherwise we exploit the winner logic above.


- **StandUp guard:** `StandUp.trigger()` checks for an existing `pred:posture:standing` to avoid “re-standing” every tick.

**Status dict convention:**  
`{"policy": "policy:<name>" | None, "status": "ok|fail|noop|error", "reward": float, "notes": str}`



## Policy ordering & fairness

Policies are evaluated in a fixed order mainly as a deterministic final tie-break (and for readability), but most decisions are made by deficit/non_drive scoring (and, in RL mode, by q within the near-best band).


## Designing good `trigger()` guards

Good triggers are **narrow and testable**:

* Test for **absence** of the goal state (`not standing yet`).

* Include **drive thresholds** when appropriate (`hunger_high`).

* Prefer **explicit tags** or **anchors** over ad-hoc string checks.  
  This makes behavior auditable: anyone can read a binding’s tags/drives and understand why a policy did or did not fire.

## Example sketch: SeekNipple

* **Trigger:** `drive:hunger_high` and no `pred:nipple:latched`.

* **Execute:** add `pred:nipple:found`, connect from the current state with `search`, optionally emit a cue tag (`cue:scent:milk`) when present.

* **Provenance:** stamp `meta.policy = "policy:seek_nipple"` on any new binding.

Q&A to help you learn this section

Q: Two methods every policy must have?  A: trigger, execute.

Q: What prevents “re-standing”?  A: Guard in `StandUp.trigger()` that checks for `pred:posture:standing`.

Q: What does a policy return?  A: A status dict (policy, status, reward, notes).

Q: What does the skill ledger track?  A: Counts, success rate, running q, last reward.

---

# Planner Contract

- **Goal:** Find a path from anchor **NOW** to the **first** binding carrying `pred:<token>`.
- **Algorithm:** **BFS** (O(|V|+|E|)) over edges.  
- **Returns:** List of binding ids (`["b1", "b9", "b12", ...]`) or `None` if not found.
- **When paths don’t exist:** Either you haven’t created the predicate yet (e.g., no instinct tick) or it’s disconnected.
  
  

## Stop conditions & correctness

Two equivalent conventions exist:

* **Stop-on-pop (default):** return when a goal binding is **popped** from the frontier.

* **Stop-on-discovery:** return as soon as a goal binding is **enqueued**.  
  Both yield shortest paths in unweighted graphs, stop-on-pop tends to produce cleaner logs because the pop order matches the BFS layers.

## Frontier semantics (one line mental model)

The frontier is the **FIFO queue of discovered-but-not-expanded nodes**. A node is marked “discovered” at **enqueue time**, never enqueue a discovered node again. This invariant prevents cycles from causing duplicates.

## Path presentation

For humans, show both ids and predicates:  
`b3[born] --then--> b4[wobble] --then--> b5[stand] --then--> b6[nurse]`.  
For programs, keep returning the id list (stable, parseable, compact).



***Q&A to help you learn this section***

Q: Where does planning start?  A: Anchor NOW.

Q: How is the goal detected?  A: First binding whose tags contain pred:<token>.

Q: Complexity?  A: O(|V|+|E|) BFS.
Q: Why might a path be missing?  A: Predicate not created yet or the graph is disconnected.

---

# Planner: BFS vs Dijkstra (weighted edges)

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

# Persistence: Autosave/Load

- Snapshot file (JSON) includes:
  
  ```jsonc
  {"saved_at": "...", "world": {...}, "drives": {...}, "skills": {...}}
  ```

- **Autosave:** `--autosave session.json` writes after each completed action (atomic replace). Overwrites prior file if same name.

- **Load:** `--load session.json` restores world/drives/skills, id counter advances to avoid `bNN` collisions.

- **Fresh start:** Use a new filename, delete/rename old file, or load a non-existent file (runner continues with a fresh session and starts saving after first action).

**Atomic writes & recovery**

Snapshots are written via **atomic replace**: write to a temp file in the same directory and rename over the old snapshot. If a crash occurs mid-write, the old file remains intact. On load:

1. Parse JSON safely, if it fails, print a clear error with the path and keep the process alive so the user can save to a new file.

2. Validate minimal invariants (`anchors`, `latest`, `bN` shape). If any are missing, reconstruct conservative defaults and continue (prefer a live session to a hard fail).

**Versioning the shape**

Include a small `{"version": "0.7.x"}` under `world`. If you add fields later, bump this string and keep best-effort compatibility in `from_dict()`—log a one-liner describing any defaulted fields so users know what changed.





### Q&A to help you learn this section

Q: When do I actually need Dijkstra instead of BFS?
A: Use BFS when all edges are effectively equal-cost (e.g., neonatal episodes where each “then” step is similar). Use Dijkstra when you’ve started annotating edges with meaningful costs (distance, duration, risk, etc.) and you care about lowest total cost, not just fewest hops.

Q: How does Dijkstra know what cost to use for an edge?
A: It checks edge.meta in priority order: weight → cost → distance → duration_s → 1.0. If none are present, it falls back to 1.0, which makes Dijkstra behave like BFS.

Q: If all my edges have weight=1.0, will BFS and Dijkstra give different paths?
A: No. With equal weights, Dijkstra and BFS usually produce the same set of shortest paths (up to tie-breaking). Dijkstra is only useful once some edges have lower/higher costs than others.

Q: How can I check which planner is currently active?
A: Call world.get_planner() in code or use the Planner strategy (toggle BFS ↔ Dijkstra) menu item. The menu prints the current strategy before planning so you can see whether you’re on BFS or Dijkstra.

Q: Does switching planner change how WorldGraph stores edges?
A: No. Edges are stored the same way (adjacency list on the source binding). Only the search algorithm that walks those edges changes (BFS vs Dijkstra).

Q: What does autosave write? 
 A: {saved_at, world, drives, skills}.

Q: How do we avoid id collisions after load?  
A: from_dict() advances the internal bNN counter.

Q: Missing --load file?  
A: Continue fresh, file created on first autosave.

Q: Why atomic replace on save?  
A: Prevents partial/corrupt snapshots.







# Runner, menus, and CLI

You can explore the graph via an interactive menu. The most useful items while learning are:

* The **“Snapshot”** entry  
  Prints bindings, edges, drives, CTX, TEMPORAL, and policy telemetry. Shows NOW/LATEST, event boundary (epoch), soft-clock cosine, and which policies are eligible at the current developmental stage. This is your “state of the world and controller” dashboard.

* The **“Drives & drive tags”** entry  
  Shows numeric drives (`hunger`, `fatigue`, `warmth`) and the derived **drive flags** (`drive:*`) that policies use in `trigger()`. These flags are ephemeral, not written into the graph unless you explicitly create `pred:drive:*` or `cue:drive:*` tags.

* The **“Input [sensory] cue”** entry  
  Writes a `cue:<channel>:<token>` binding (e.g., `cue:vision:silhouette:mom`) and runs one controller step so you can see how policies respond to evidence. This is the “Sense → Process → Act” entry point.

* The **“Instinct step (Action Center)”** entry  
  Runs the policy runtime once, with explanatory pre/post text. If a policy fires, you get a small chain of bindings/edges (e.g., the standing chain) and a status dict (`policy, status, reward, notes`).

* The **“Inspect binding details”** entry  
  Given a binding id (or `ALL`), shows:
  
  - tags (families: `pred:*`, `cue:*`, `anchor:*`),
  - `meta` as JSON,
  - a short **Provenance:** summary (`meta.policy/created_by/boot/ticks/epoch`),
  - attached engrams (slot → short id + act + OK/dangling),
  - both **outgoing and incoming** edges and a degree line (`out=N in=M`).
    Use this to audit where a node came from and how it is connected.

* The **“List predicates”** entry  
  Groups all `pred:*` tokens and shows which bindings carry each token. You can optionally filter by substring (e.g., `rest` or `posture`) to reduce clutter. This is a good way to see which planner targets exist.

* The **“Add predicate”** entry  
  Prompts for a token (e.g., `posture:standing`, without the `pred:` prefix) and an attach mode (`now/latest/none` – default `latest`). It:
          creates a new binding tagged `pred:<token>`,

        optionally auto-links it from NOW/LATEST with a `"then"` edge,

        stamps provenance (`meta.added_by="user"`, `meta.created_by="menu:add_predicate"`, `meta.created_at=ISO-8601`).
It’s your primary way to “teach” the graph new states by hand.

* The **“Connect bindings”** entry  
  Adds a directed edge `src --label--> dst` (default label `then`), with a simple duplicate guard that skips an exact `(src, label, dst)` edge if it already exists. Edges created here carry `meta.created_by="menu:connect"` and a timestamp. Use this to wire episodes with meaningful labels such as `approach`, `search`, `latch`, `suckle`.

* The **“Delete Edge”** entry  
  Interactive helper for removing edges. It handles different legacy edge layouts and prints how many edges were removed between `src` and `dst` (with an optional label filter). This is the safest way to repair a mistaken link without editing JSON by hand.

* * The **“Plan to predicate”** entry  
    Asks for a target predicate token (e.g., `posture:standing`) and:
  - prints the **current planner strategy** (`BFS` or `DIJKSTRA`),
  - calls `WorldGraph.plan_to_predicate` from the NOW anchor,
  - prints both the raw id path and a **pretty path** (`b3[posture:standing] --then--> b4[milk:drinking] ...`).
    With all edges weight=1, BFS and Dijkstra produce the same paths; once you assign weights, Dijkstra uses `edge.meta['weight'/'cost'/'distance'/'duration_s']` as the cost.

* The **“Export and display interactive graph”** entry  
  Writes a Pyvis HTML file for the current graph, with options for label mode (`id`, `first_pred`, or `id+first_pred`), edge label display, and physics. Open the HTML in your browser to hover nodes/edges and orient yourself visually.

* The **“Save session”** entry  
  Manual one-shot snapshot to a JSON file you specify. It writes the same shape as autosave (`saved_at`, `world`, `drives`, `skills`) via atomic replace. It does **not** change your `--autosave` setting and is ideal for named checkpoints (e.g., `session_after_first_hours.json`).

* The **“Load session”** entry  
  Loads a prior JSON snapshot (world, drives, skills) and replaces the current in-memory state. It never overwrites the file on load. After loading, the I/O banner explains whether autosave is ON/OFF and where the next autosaves will go.

* The **“Reset current saved session”** entry  
  Available only when you started with `--autosave <path>`. After an explicit confirmation (`DELETE` in uppercase), it:
  
  - deletes the autosave file at that path,
  - re-initializes a fresh WorldGraph, Drives, and skill ledger in memory,
  - keeps `--autosave` pointing at the same path.  
    From the simulation’s point of view you are now in essentially the same state as a fresh run with `--autosave` set; the **next** action that triggers autosave will create a new snapshot at that path.

Design decision (folded in): The runner offers a quick-exit `--plan <token>` flag when you only need to compute a plan once and exit. In interactive mode, the menu shows a small drives panel because drives are central to policy triggers.

Design decision (folded in): Attachment semantics are explicit and lowercase: `attach="now"`, `attach="latest"`, or `"none"`. This removes ambiguity when auto-wiring the newest binding into the episode chain.



## Environment loop and episode configuration

Two runner menu selection entries work together to make the newborn-goat simulation easier to explore:

- **Run N environment steps (closed-loop timeline)**  
  Runs a short loop between the **HybridEnvironment** and the **Action Center**:

  1. If needed, calls `env.reset()` to start a newborn-goat episode.
  2. On each step, calls `env.step(action=ctx.env_last_action, ctx=ctx)`, where `ctx.env_last_action` is the name of the last executed policy (e.g., `policy:stand_up`, `policy:seek_nipple`, `policy:follow_mom`).
  3. Injects `EnvObservation` into the main WorldGraph and updates BodyMap from the predicates.
  4. Runs one controller step to select and execute a policy, logging it as `[executed] policy:...`, and stores its name back into `ctx.env_last_action` for the next environment tick.

  The log for each step includes:

  - an `[env]` line (stage, posture, mom/nipple, last action),
  - `[env→world]` lines (what predicates/cues were written),
  - `[env→controller]` lines (which policy fired and why),
  - a compact `[env-loop] summary ...` line, plus:
    - `explain posture: ...` — why posture stayed fallen/standing/latched/resting,
    - `explain nipple: ...` — how nipple moved hidden → reachable → latched,
    - `explain zone: ...` — why geometry is currently classified as unknown / unsafe_cliff_near / safe.

  Together, these lines turn the closed-loop run into a readable text storyboard (“fell, stood, followed mom off the cliff, moved into shelter, latched, rested”).

- **Configure episode starting state (drives + age_days)**  
  Allows you to adjust the **internal starting conditions** without editing code:

  - `drives.hunger` (0.0–1.0)
  - `drives.fatigue` (0.0–1.0)
  - `drives.warmth` (0.0–1.0)
  - `ctx.age_days` (≥ 0.0)

  The runner:

  1. Prints current values.
  2. Prompts for new values (blank = keep current), clamping drives to `[0.0, 1.0]` and age to `≥ 0.0`.
  3. Writes them back into the live `drives` and `ctx` objects.
  4. Prints an updated summary line.

  This is the main way to explore different behavioural regimes:

  - **Hungry, not tired** → expect `SeekNipple` to dominate once geometry is safe.
  - **Very tired, moderately hungry** → `Rest` competes strongly once the kid is in shelter.
  - **Low drives** → permissive `FollowMom` behaviour dominates, moving geometry without strong drive pressure.

After configuring drives and age with menu 40, you can immediately run menu 37 to see how those initial conditions change the closed-loop story.


***Q&A to help you learn this section***

Q: What are the most useful menu items while learning?   
A: Display snapshot, Add predicate, Connect two bindings, Plan from NOW, and the interactive graph export.

Q: Is there a quick way to visualize the graph?   
A: Yes—export an interactive HTML graph from the menu, labels can show `id`, `first_pred`, or both.

Q: Why does the menu warn about duplicate edges?   
A: To avoid clutter when auto-attach already created the same `(src, label, dst)` relation.

Q: Can I skip the menu and just plan?   
A: Use `--plan pred:<token>` from the CLI for a one-shot plan.



# Logging & Unit Tests



## Logging (minimal, already enabled)

The runner initializes logging once at startup:

- Writes to **`cca8_run.log`** (UTF-8) and also echoes to the console.
- One INFO line per run (runner version, Python, platform).
- You can expand logging later by sprinkling `logging.info(...)` / `warning(...)` where useful.

**Change level or file:**

Edit `cca8_run.py` in `main(...)` where `logging.basicConfig(...)` is called.

## Tail the log while you run (Windows PowerShell):

Get-Content .\cca8_run.log -Wait



## Unit tests (pytest)

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

- `tests/test_smoke.py` — basic reasonableness (asserts True).
- `tests/test_boot_prime_stand.py` — seeds stand near NOW and asserts a path NOW → pred:stand exists.
- `tests/test_inspect_binding_details.py` — uses a small demo world and asserts that inspect-binding reports edge degrees as expected by the “Inspect binding details” menu.
- `tests/test_phase_vi_c_spatial.py` — checks that the newborn-goat environment’s **spatial movement and safety gating** behave as described: `follow_mom` moves the kid off the cliff and into shelter, and the Rest gate respects BodyMap’s safety zone (vetoes rest near the cliff, allows rest when shelter is near and the cliff is far).


The demo world for these tests is built via `cca8_test_worlds.build_demo_world_for_inspect()`, which creates a tiny, deterministic WorldGraph (anchors NOW/HERE, stand/fallen/cue_mom/rest predicates, and a single engram pointer) that you can also use interactively via `--demo-world`.
Unit tests (pytest)



## Preflight (four-part self-test)

Run all checks and exit:

`> python cca8_run.py --preflight`

**What runs**

1) **Unit tests (pytest + coverage).**  
   Prints a normal pytest summary. Coverage is percent of **executable** lines
   (comments/docstrings ignored). Ordinary code—including `print(...)` /
   `input(...)`—counts toward coverage. Target ≥30%.  
   *Note: console vs footer may differ by ~1% due to reporter rounding.*  

2) **Scenario checks (whole-flow).**  
   Deterministic probes that catch issues unit tests miss:
   
   - Core imports & symbols present; version printouts
   - Fresh-world invariants and NOW anchor
   - `set_now` tag housekeeping (old NOW tag removed, new NOW tagged)
   - Accessory files exist (e.g., README, images)
   - Optional PyVis availability
   - Planner probes (BFS/Dijkstra toggle), attach semantics (now/latest)
   - Cue normalization, action metrics aggregation
   - Lexicon strictness (neonate stage rejects off-vocab), engram bridge
   - Action helpers summary is printable

3) **Robotics hardware preflight (stub).**  
   Reports HAL/body flag status. Example line:  
   `[preflight hardware] PASS  - NO-TEST: HAL=OFF (no embodiment); body=0.0.0 : none specified — pending integration`
   Note: Pending integration of HALs.

4) **System-functionality fitness (stub).**  
   Placeholder for end-to-end task demos (will exercise cognitive + HAL paths).
   Note: Pending integration of HALS.

**Footer format & exit code**

The last line gives a compact verdict and returns a process exit code:

[preflight] RESULT: PASS | tests=118/118 | coverage=33% (≥30) |  
probes=41/41 | hardware_checks=0 | system_fitness_assessments=0 | elapsed=00:02

- `PASS/FAIL` reflects both pytest and probe results.  
- `probes` counts scenario checks (part 2).  
- `hardware_checks` / `system_fitness_assessments` are **0** until those lanes are implemented.

**Artifacts**

- JUnit XML: `.coverage/junit.xml`  
- Coverage XML: `.coverage/coverage.xml` (console prints a human summary)

**Tip:** a lightweight *startup* check can be toggled with
`CCA8_PREFLIGHT=off` (disables the “lite” banner probe at launch).



### Q&A to help you learn this section

Q: What does --preflight actually guarantee when it says PASS?
A: It guarantees that:

all unit tests passed,

basic WorldGraph invariants hold (anchors valid, ids consistent),

planner/attach/cue/engram probes behaved as expected,

and the hardware and system-fitness lanes didn’t report critical issues.
It’s not a proof of correctness, but it’s a strong “everything basic is wired up” signal.

Q: Why is coverage only ~30% and not 100%?
A: CCA8 is an evolving research codebase. The goal is to keep coverage high enough (≥30%) to catch regressions in the core engine, not to exhaustively test every UI/menu branch yet. As the code stabilizes, more tests can be added around new features.

Q: If a probe fails but pytest is green, what should I suspect?
A: Probe failures usually mean a behavioral contract was broken (e.g., NOW not tagged, attach semantics changed, lexicon enforcement drifted). Unit tests check small pieces; probes check whole-flow assumptions. Treat probe failures as “something important in the pipeline changed.”

Q: Can I skip preflight for quick ad-hoc runs?
A: Yes. Preflight only runs when you explicitly pass --preflight. Normal cca8_run.py runs don’t automatically run tests. There is also a lightweight startup check you can disable with CCA8_PREFLIGHT=off if needed.

Q: Where do the preflight artifacts go, and why do I care?
A: JUnit XML and coverage XML are written under .coverage/. They’re useful for CI integration, trend tracking (coverage drifting up/down), and investigating test failures without re-running everything interactively.







# CCA8 as a Robotic Cognitive Operating System (RCOS)

## Overview

**CCA8 can be considered in two ways:**

As a **developmental cognitive architecture inspired by early mammalian brains.**

As the **kernel of a Robotic Cognitive Operating System (RCOS)** – a layer that manages embodiment, behavior, and cognition on top of low‑level robot firmware, real‑time OSes, and middleware such as ROS 2.

Traditional operating systems (OS/360, Unix, Windows, Linux) sit between hardware and applications, providing stable abstractions: processes, files, memory, I/O. In robotics today, we typically have:

microcontroller firmware and drivers

a general‑purpose OS (Linux, RTOS)

robotics middleware (e.g., ROS 2) for messaging, topics, services

What is usually missing is an operating system for behavior and cognition – something that:

unifies goals, drives, skills, memory, and action selection

treats the robot’s world as an explicit structure (not just ad‑hoc node graphs and callbacks)

exposes a consistent “app platform” so users can install and compose new behaviors on their embodiment

CCA8 aims to fill this role.

### Position in the stack

You can think of CCA8 as sitting above the hardware and middleware in roughly this shape:

+-------------------------------------------------------------+
|   **User behavior packs / tasks / curricula ("apps") **     
+-------------------------------------------------------------+
|   **CCA8 RCOS kernel**                                      
|   - WorldGraph (episodic world model)                       
|   - ColumnMemory (engrams, traces)                          
|   - Drives & homeostasis                                    
|   - Policies (primitive skills) & Action Center             
|   - Temporal scaffolding (ticks, episodes, age)             
+-------------------------------------------------------------+
|   **Robot HAL / middleware**                                
|   - ROS 2, PetitCat-style minimal OS, simulators            
|   - sense() / act() / status() surfaces                     
+-------------------------------------------------------------+
|   **Hardware & low-level OS**                               
|   - motors, joints, sensors, microcontrollers, RTOS/Linux   
+-------------------------------------------------------------+

In this view:

A **HAL or ROS 2 stack plays a role analogous to a BIOS + device drivers in a PC**: it knows how to talk to motors, joints, cameras, etc.

**CCA8 is the cognitive OS**: it knows about episodes, goals, drives, skills, policies, and worlds.

**User-defined skills, policies, and task scripts** are the equivalent of applications.

Small platforms like the PetitCat robot can sit under CCA8 just as well as richer ROS 2 platforms. As long as there is a HAL that implements the expected surfaces, the same CCA8 brain can drive different embodiments.

#### What the user gets: an “app platform” for behavior

From a user’s point of view, CCA8 as an RCOS should eventually feel a bit like “Windows for your robot”:

you configure the body and environment,

you install or write behaviors (“apps”),

you specify goals and constraints,

and the RCOS manages the ongoing lifecycle of perception, memory, and action.

Concretely, CCA8 exposes (or is intended to expose) a few stable surfaces.

**1. Embodiment and HAL configuration**

The user (or integrator) plugs a robot into CCA8 by supplying a HAL adapter:

sense() → returns structured observations which can be turned into cues/engram payloads

act(intent) → takes a small set of action tags / parameters (e.g., action:step_forward, action:look_around) and translates them into motors, joint trajectories, or ROS 2 messages

status() → reports health, battery, fault states, etc., which can be reflected as predicates in the WorldGraph

CCA8 does not care whether act(intent) ends up calling ROS 2, a PetitCat‑style mini OS, or direct serial commands. That complexity stays below the RCOS boundary.

**2. Drives, goals, and profiles**

On top of the embodiment, the user configures the internal “needs” and goals:

numeric drives (hunger, fatigue, warmth, safety, etc.) with thresholds

profiles (e.g., “newborn mountain goat”, “explorer bot”) that set default drive parameters, exploration policies, and curricula

optional task‑level goals (e.g., “stay upright”, “follow mom”, “inspect room”, “return to dock”) that guide what “success” means over episodes

Drives are exposed to the controller as tags like drive:hunger_high, which policies can trigger on. This is where “what the robot should care about” gets declared.

**3. Skills and policies as “apps”**

The primary way users extend CCA8 is by installing or authoring policies and skills.

At the lowest level, a primitive policy is just a small behavior object with two methods:

trigger(world, drives) → should this skill run now?

execute(world, drives, ctx) → append a small chain of bindings/edges to the WorldGraph, optionally call the HAL, update drives, and return a status dict.

Policies are registered with the Action Center, which acts as the scheduler:

it inspects the current world + drives

it chooses which policy fires next (safety policies first, then homeostatic needs, then fallbacks)

it tracks provenance and learning signals (skill ledger, rewards)

From a user’s point of view, each policy is a bit like an installed application:

It has a name and version (policy:seek_nipple, policy:avoid_edge).

It declares preconditions (what states/drives it needs).

It leaves a trace in the world (provenance tags, binding chains) for later analysis or learning.

Higher-level skills can be built as small libraries of policies plus helper functions, packaged as Python modules or “behavior packs” that CCA8 discovers and loads.

**4. Task scripts and curricula**

On top of skills, the user writes task scripts that set up experimental or operational episodes. For example:

choose a profile and embodiment (e.g., goat vs. PetitCat)

load a particular world template or terrain

enable a set of skills/policies (e.g., StandUp, FollowMom, AvoidEdge, ExploreRoom)

define stopping conditions and logging preferences

This can be done via:

Python entry points (e.g., cca8_run.py with arguments), and

eventually, configuration files (e.g., YAML/JSON manifests) that describe “what brain, what body, what skills, what goals”.

The intent is that non‑specialist users should be able to say, in effect:

“Here is my robot body, here are the behaviors I want available, and here is what I want it to try to do.”

and let the CCA8 RCOS handle the ongoing cycle of perception → world update → drive update → action selection → embodiment.

**5. Introspection and debugging surfaces**

Like a conventional OS exposes tools such as ps, logs, and debuggers, the CCA8 RCOS exposes (or will expose) introspection surfaces:

WorldGraph views: what bindings and edges are currently active, where “NOW” is, what predicates are true

Skill ledger: per‑policy statistics (counts, rewards, success/fail history)

Drive traces: how internal needs evolved over time and which policies responded

Embodiment traces: what actions were actually sent through the HAL and with what results

These let the user treat behaviors as first‑class, inspectable objects rather than opaque ROS node graphs.

PetitCat and other small embodiments

For small robots such as PetitCat, CCA8’s RCOS view is especially useful:

a minimal robot “OS” handles low‑level timing, motor control, and safety (PetitCat‑like firmware / micro‑OS),

a thin HAL adapter translates between CCA8’s action tags and the robot’s specific capabilities,

the same CCA8 brain can then be reused across simulation and physical hardware, or across different small bodies.

In that sense, CCA8 is not just a simulator of a mountain goat calf, but a general-purpose Robotic Cognitive Operating System designed to be ported to many embodiments while giving users a consistent way to “install” behaviors and tell their robot what they want it to do.













# Hardware Abstraction Layer (HAL)

A Hardware Abstraction Layer (HAL) separates *what* the cognitive system wants to do from *how* a specific robot makes it happen. In robotics, a HAL normalizes diverse sensors (camera, IMU, microphones, joint encoders) and actuators (motors, servos, grippers) behind a stable interface: perception enters the stack as time-stamped, unit-annotated measurements; actions leave as parameterized commands with feedback and safety guarantees. This indirection lets the same policy or planner run on simulation today and a very different platform tomorrow (e.g., a wheeled rover vs. a quadruped), without rewriting cognition. A good HAL also handles low-level concerns—synchronization, rate limiting, watchdogs/estops, and health reporting—so higher layers reason in task space, not device idiosyncrasies.

In practice, a HAL defines a few consistent surfaces: **sense()** for bulk sensor pulls or event callbacks, **act(command, params)** for goals in actuator space, and **status()** for state, limits, and faults. It owns the mapping from device coordinates to canonical frames, applies calibration/units, enforces safety envelopes, and returns structured acknowledgements (accepted/Executing/Done/Error) with timestamps. With this contract, cognition can compose behaviors from predicates and policies, while the HAL translates to hardware-specific drivers and transport.



## CCA8 and future HAL integration

The importance of embodiment in the generation and development to cognition is acknowledged. Embodiment shapes cognition—sensorimotor contingencies, action affordances, latency, noise, and body-centric frames all co-determine how an agent learns and reasons. CCA8’s HAL deliberately _abstracts_ embodiment during core development to decouple variables: it gives us reproducible experiments, deterministic tests, and portability across platforms without rewriting cognition. This isn’t a denial of embodiment; it’s a seam. We mitigate “embodiment debt” by (1) keeping time, units, frames, limits, and latencies explicit in the HAL manifest; (2) expressing actions as **intents** (e.g., move/gaze/manipulate) rather than device torques; (3) mirroring real timing into engrams (`ticks`, `tvec64`, `epoch`) so learning remains time-aware; and (4) swapping in realistic adapters (noise/latency/domain-randomization) when moving from headless runs to hardware. In short, HAL postpones _implementation details_ of a body while preserving the _constraints_ that matter, so embodiment can be reintroduced precisely—at the right layer—without entangling the cognitive core.

While the importance of embodiment to cognition is acknowledged, the CCA8 architecture is structured to drop in a HAL without disturbing cognition. The **Runner** already distinguishes the cognitive context (policies, temporal clock, world graph) from embodiment details; by default HAL is **OFF** and the system runs “headless.” The seams are intentional: (1) **perception bridge** — features/engrams can be filled from HAL sensor streams with time linkage (`ticks`, `tvec64`, `epoch`); (2) **action bridge** — controller **primitives/policies** can emit normalized action intents (e.g., `move_base(dx,dy,theta)`, `gaze(target)`, `manip(grasp=open/close)`), which a HAL adapter maps to device commands; (3) **timing** — the cognitive **TemporalContext** stays procedural and device-agnostic, while the HAL can expose a wall-clock/rt clock when needed.

When a HAL is enabled, CCA8 will load an *embodiment manifest* (sensors, frames, capabilities, limits), bind HAL streams to the **Features** module (creating engrams with temporal fingerprints), and route controller outputs to **act()** with safety interlocks (dead-man, estop, limit checks). This keeps the **WorldGraph** an episodic index (lightweight, device-neutral), lets **policies** remain portable, and confines hardware specialization to HAL adapters. The same simulation you run today can, with a manifest and a driver pack, target different robots with minimal code changes—exactly the portability a HAL is meant to provide.



### Q&A to help you learn this section

Q: Why is HAL kept separate from the cognitive architecture?
A: To keep cognition portable and testable. The same WorldGraph/controller stack should run:

in a pure simulation,

on different robots,

or in hybrid sim+sensor regimes
without rewriting core cognitive logic. HAL localizes sensor/actuator quirks and safety constraints to one layer.

Q: What changes in CCA8 when HAL is turned ON?
A: Cognition (WorldGraph, controller, TemporalContext) stays the same. The difference is that:

perception features/engrams can be fed from real sensors via the HAL, and

policy actions can be turned into device commands (act()) with safety envelopes (limits, estops, etc.).

Q: Does HAL know about predicates and policies?
A: No. HAL deals in sensor streams and action intents (move/gaze/manipulate). Policies and predicates remain in CCA8. The runner/bridge is responsible for mapping action:* / policy decisions into HAL act(...) calls.

Q: How does HAL help with sim-to-real transfer?
A: It defines a stable contract:

sense() → returns normalized, time-stamped sensor data,

act(intent, params) → executes primitive actions in actuator space,

status() → reports health/limits/faults.
By adhering to this contract in both sim and real deployments, you can reuse cognitive code and gradually swap simulators for real hardware.







# Hardware preflight lane (status stub)

When you run `--preflight`, CCA8 reports HAL/body flags in a dedicated lane.
This is a **status stub**—no hardware I/O yet.

Example:
`[preflight hardware] PASS  - NO-TEST: HAL=ON (...); body=0.1.1 hapty — pending integration`

Enable it via CLI:
`> python cca8_run.py --hal --body hapty`

Future checks will cover: transport handshake (USB/serial/network), sensor
enumeration, actuator enable/disable, estop/limits, and simple round-trip
commands (with timestamps and unit checks).

<img title="Goat Embodiment" src="./robot_goat.jpg" alt="robot_goat" style="zoom:25%;" data-align="center">

### Q&A to help you learn this section

Q: What does it mean when hardware preflight prints “NO-TEST: HAL=OFF … pending integration”?
A: It means the hardware lane ran, but there were no active hardware checks to perform:

HAL is off, or

no body profile is configured.
It’s a reminder that the HAL lane is wired but not yet doing real transport/sensor tests.

Q: How do I enable the hardware lane for future robots?
A: Start the runner with --hal --body <name>, e.g.:
python cca8_run.py --hal --body hapty.
Once real HAL implementations exist, preflight will use that configuration to check connectivity, sensors, estops, etc.

Q: Will hardware failures make --preflight return non-zero exit codes?
A: Yes, once implemented. The intention is that:

any serious hardware connectivity/safety issue

should cause the hardware preflight lane to FAIL
and thus make the overall --preflight exit code non-zero so CI or scripts can react.

Q: Does HAL preflight change anything in the cognitive state?
A: No. It should only probe transport, sensors, actuators and log health. WorldGraph, drives, and policies should remain unaffected by hardware preflight.

Q: How should I read the “hardware_checks=0” field in the preflight footer today?
A: Literally: there are currently zero implemented hardware checks. It’s a placeholder count that will increase as real HAL checks (sensor enumeration, estop status, etc.) are added.







# How-To Guides

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
cca8_run.py --load session.json --plan pred:posture:standing
```

### Add a sensory cue

Menu → **11** → channel `vision`, cue `mom:close` → creates `cue:vision:mom:close` (depending on your input normalization).
Note: menu **11** adds a **cue** not a pred.

### Show drives (raw + tags)

In the menu, choose **“Drives & drive tags”** (you can also type `drives` or `d` at the prompt).  
This prints numeric drives and active **drive flags** (`drive:*`, ephemeral). These flags are computed by the controller (`Drives.flags()` / `Drives.predicates()`) and used in policy `trigger()` logic; they are **not persisted** in the WorldGraph unless you explicitly create `pred:drive:*` or `cue:drive:*` tags.



### Start with a preloaded demo world (for graph/menu testing)

Sometimes you want a small, deterministic graph to test the graph menus without building everything via instincts first.

cca8_run.py --demo-world



This:

* Seeds a tiny WorldGraph with 6 bindings and 7 edges (anchors `NOW`/`HERE`, a `stand` predicate, a `fallen` state, a cue-like `vision:silhouette:mom`, and a `state:resting` node with provenance and an engram pointer).

* Prints a short banner such as:
  `[demo_world] Preloaded demo world (NOW=b1, bindings=6)`
  at startup.

* Lets you immediately use:
  
  * the **“Snapshot”** entry to see the pre-wired edges and tags,
  
  * the **“Inspect binding details”** entry (e.g., on the “resting” node) to inspect tags/meta/provenance/engrams and incoming/outgoing edges,
  
  * the **“List predicates”**, **“Connect bindings” / “Delete Edge”**, and **“Plan to predicate”** entries, all against the same stable mini-world.

The same demo builder is used by `tests/test_inspect_binding_details.py` via `cca8_test_worlds.build_demo_world_for_inspect()`, so interactive experiments and unit tests share the same graph shape.



### Export an interactive graph with readable labels

From the main menu choose **Export and display interactive graph (Pyvis HTML)**, then:

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

# Data schemas (for contributors)

This section documents the canonical in-memory shapes and their JSON snapshot equivalents. The goal is that a maintainer can read the structures, eyeball a saved session, and reconstruct what happened without digging into code.

## World snapshot (top level)

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

## Binding (node)

Bindings are the atomic “episode cards” in the graph.
    {
      "id": "b42",
      "tags": [
        "pred:posture_standing",
        "cue:vision:silhouette:mom"
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

## Anchors

Anchors are just bindings with special meaning, referenced in `world.anchors`. Many anchor bindings also carry a tag like `anchor:NOW` for visibility in UIs. Planning typically starts from the `NOW` anchor.

## Drives (controller)

    { "hunger": 0.70, "fatigue": 0.20, "warmth": 0.60 }

The controller may derive helper tags (e.g., `drive:hunger_high`) for policy triggers. If those tags aren’t available, policies should degrade gracefully by using graph state alone.

## Skill ledger (per policy)

A lightweight, per-policy roll-up to support introspection and future learning hooks:
    "policy:stand_up": { "n": 3, "succ": 3, "q": 0.58, "last_reward": 1.0 }

Field meanings are intentionally minimal: total runs `n`, number succeeded `succ`, an optional running quality estimate `q`, and the last reward.

## Contracts & loader behavior

* **Serialization:** `WorldGraph.to_dict()` emits `version`, `next_id`, `latest`, `anchors`, and `bindings`.

* **Deserialization:** `WorldGraph.from_dict()` restores the structures and **advances** the internal id counter beyond any loaded ids.

* **Sinks:** a binding without `edges` is a valid sink.

* **Labels & pretty print:** when displaying paths or graphs, the first `pred:*` tag is used as a human label if present, otherwise the id is shown.
  
  

## Why edges live on the source binding (design rationale)

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







# Traceability (requirements to code)

---------------------------------------------------------------

A traceability lite table maps major requirements to the modules and functions that satisfy them. Keep this short and keep
 it close to code names so a maintainer can jump straight into the right file. Examples:

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







# Roadmap

* Enrich engrams and column providers, add minimal perception‑to‑predicate pipelines.
* Add “landmarks” and heuristics for long‑distance plans (A* when we add weights).
* Optional database or CSR backend if the graph grows beyond memory.
* Exporters: NetworkX/GraphML for interoperability, continue shipping the Pyvis HTML for quick, zero‑install visualization.

***Q&A to help you learn this section***

Pending as codebase grows and features stabilize









## Debugging Tips (traceback, pdb, VS Code)

- **traceback:** In `except Exception:` add `traceback.print_exc()` to print a full stack. Use when a loader/snapshot fails.  
- **pdb:** Drop `breakpoint()` in code or run `python -m pdb cca8_run.py --load ...`. Commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p`/`pp` (print), `b` (breakpoint), `where`.  
- **VS Code debugger:** Create `.vscode/launch.json` with args, set breakpoints in the gutter, F5 to start. Great for multi-file stepping.
* Tracebacks: the runner keeps exceptions readable, copy the stack into an issue if you see unexpected behavior.
* `pdb`: insert `import pdb, pdb.set_trace()` where needed to inspect bindings and edges.
* VS Code: run `cca8_run.py` with the debugger and place breakpoints in `plan_to_predicate()` or policy `trigger()`/`execute()`.
  
  

A common pitfall is duplicate edges when both auto‑attach and a manual connect create the same relation. The UI warns when you try to add a duplicate, you can also inspect the `edges` list on a binding directly in the debugger.

### Playbook: “No path found”

1. **Verify the predicate exists** (snapshot shows a binding with that `pred:*`).

2. **Check connectivity** (ensure there’s a forward chain of edges from NOW to that binding).

3. **Look for reversed edges** (common error: added `B→A` instead of `A→B`).

4. **Confirm the goal token** (exact `pred:<token>` string, avoid typos/extra spaces).

5. **Inspect layers** (use the interactive graph, the missing hop will be visually obvious).

### Playbook: “Repeated standing”

1. Confirm `StandUp.trigger()` checks for an existing standing predicate.

2. Verify policy order (another policy shouldn’t insert a second standing node as a side effect).

3. Grep recent bindings for `meta.policy` to see who created duplicates.
   
   

***Q&A to help you learn this section***

Q: Quick way to print a stack?  A: traceback.print_exc() in except.

Q: Start debugger from CLI?  A: python -m pdb cca8_run.py --load ....

Q: Persistent breakpoint in code?  A: breakpoint() (Python 3.7+).

Q: IDE workflow?  A: VS Code launch config + gutter breakpoints.

---



# FAQ / Pitfalls

- **“No path found to state:posture_standing”** — You planned before creating the state. Run one instinct step (menu **12**) first or `--load` a session that already has it.
- **Repeated “standing” nodes** — Tightened `StandUp.trigger()` prevents refiring when a standing binding exists. If you see repeats, ensure you’re on the updated controller.
- **Autosave overwrote my old run** — Use a new filename for autosave (e.g., `--autosave session_YYYYMMDD.json`) or keep read-only load + new autosave path.
- **Loading says file not found** — We continue with a fresh session, the file will be created on your first autosave event.
  
  

***Q&A to help you learn this section***

Q: Why “No path found …” on a new session?  A: You planned before adding the predicate, run one instinct step.

Q: Why duplicate “standing” nodes?  A: Old controller, update to guarded StandUp.trigger().

Q: How to keep an old snapshot?  A: Autosave to a new filename.
Q: Is load failure fatal?  A: No, runner continues with a fresh session.







## Intro Glossary

- **Predicate** — symbolic fact token (atomic).  
- **Binding** — node that carries predicate tag(s) and holds meta/engrams/edges.  
- **Edge** — directed relation labeled `"then"`, encoding episode flow.  
- **WorldGraph** — the episode index graph.  
- **Policy** — primitive behavior with `trigger` + `execute`.  
- **Action Center** — ordered scan of policies, runs first match per controller step  
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





# TUTORIALS AND TECHNICAL DEEP DIVES

# Tutorial on WorldGraph, Bindings, Edges, Tags and Concepts

This tutorial introduces the mental model behind **WorldGraph** and shows how to encode experience in a way that is:

- simple for **planning** (BFS / Dijkstra),
- clear for **humans** (bindings are little episode cards),
- and consistent with the **four binding kinds**: anchors, predicates, cues, and actions.

It complements the “WorldGraph in detail” and “Tagging Standard” sections by walking through the *why* and *how* with newborn-goat flavored examples.

---

## 1) Mental model at a glance

WorldGraph is a **compact, symbolic episode index**. Each “moment” is captured as a small record (a **binding**) that carries tags and optional pointers to richer memory (**engrams**). **Edges** connect moments to show how one led to another. Planning is graph search from a temporal **anchor** (usually `NOW`) toward a **goal predicate**.

A readable example path:

born --then--> wobble --then--> posture:standing --then--> nipple:latched --then--> milk:drinking
In CCA8:

the things on the nodes are tags (predicates, cues, anchors, actions),

the things on the arrows are edge labels (often just "then").

We now treat actions primarily as action:* nodes, not as special edge labels.

## 2) Why “bindings” and not just “nodes”?



A binding is more than a bare vertex. It binds together:

lightweight symbols (tags: pred:*, action:*, cue:*, anchor:*),

pointers to engrams (rich memory outside the graph),

and provenance/meta (who created it, when, why),

plus outgoing edges that capture “what happened next”.

Think of each binding as a tiny episode card:

“At this moment, the kid was posture:fallen, we saw vision:silhouette:mom, and the StandUp policy fired.”

That’s why we call it a “binding”: it’s a coherent, inspectable snapshot.

## 3) What a binding contains (shape)

   Every binding has a unique id like b42. Conceptually it looks like:

jsonc
Copy code
{
  "id": "b42",
  "tags": [
    "pred:posture:standing",
    "cue:vision:silhouette:mom"
  ],
  "edges": [
    { "to": "b43", "label": "then", "meta": {"created_by": "policy:seek_nipple"} }
  ],
  "meta": {
    "policy": "policy:stand_up",
    "created_at": "2025-11-27T10:09:56",
    "ticks": 5,
    "tvec64": "..."
  },
  "engrams": {
    "column01": { "id": "<engram_id>", "act": 1.0 }
  }
}
Invariants that keep the graph healthy:

Ids are unique (bN).

Edges are directed and live on the source binding (edges[] list).

A binding with no edges is a valid sink.

The first pred:* tag (if present) is used as the node label in pretty paths/exports; fallback is the id.

The engine keeps an anchors map (e.g. {"NOW": "b5", "NOW_ORIGIN": "b1"}); the corresponding anchor:* tags are for human readability.

## 4) Tag families (pred, cue, anchor, action)

   We use exactly four families of tags in the WorldGraph:

Predicates — what is true about body/world

Prefix: pred:

Examples:

pred:posture:fallen, pred:posture:standing, pred:resting

pred:mom:close, pred:nipple:latched, pred:milk:drinking

pred:seeking_mom

Purpose: planner goals and state descriptions.

Cues — evidence, not goals

Prefix: cue:

Examples:

cue:vision:silhouette:mom

cue:scent:milk

cue:drive:hunger_high

Purpose: policy triggers and FOA seeds. We do not plan to cues.

Anchors — orientation markers

Prefix: anchor:

Examples:

anchor:NOW – current focus of attention / local time,

anchor:NOW_ORIGIN – starting point of this episode.

The anchors map is authoritative (anchors["NOW"] = "b5"); tags make them visible in UIs.

Actions — motor / behavioral steps

Prefix: action:

Examples:

action:push_up

action:extend_legs

action:orient_to_mom

Purpose: explicit action nodes between predicate states.

You can think of:

pred:* = nouns/adjectives: what is (posture, proximity, feeding state),

action:* = verbs: what the goat actually did,

cue:* = sensory hints,

anchor:* = index pegs.



## 5) Edges: “then” glue + optional labels

Edges are directed links between bindings:

jsonc
Copy code
{ "to": "b4", "label": "then", "meta": {"created_by": "policy:stand_up"} }
Design:

Semantics: every edge is conceptually “then” — “this binding tended to be followed by that binding in this episode.”

Label: defaults to "then"; you may use domain labels like "approach", "search", "latch", "suckle" as human-facing aliases ("then (approach)").

Meta: numeric/action metrics belong in edge.meta:

{"meters": 8.5, "duration_s": 3.2, "created_by": "policy:seek_nipple"}.

Algorithms (planner, FOA) treat edges as structure-first:

They look at which nodes are connected, not the exact label string.

Labels can later inform costs (Dijkstra) or filters (“avoid edges marked recover_fall”), but are not required for correctness.

## 6) Anchors: NOW and NOW_ORIGIN

   We use two important anchors in the neonate:

anchor:NOW_ORIGIN

Set once at the start of the episode (birth).

Never moves; a natural starting point for “whole story” plans.

anchor:NOW

Follows the latest stable predicate state (e.g., posture:standing, seeking_mom, resting).

Moved by the runner after successful policy executions.

Common uses:

Planning from NOW: “Given where I am, how do I reach X?”

Planning from NOW_ORIGIN: “What path did I take from birth to X?”

Resetting NOW in experiments (e.g. set NOW=b3 temporarily to explore a local neighborhood).

## 7) S–A–S in practice: a StandUp example

   Consider the simplified StandUp episode:

Start: goat is fallen near NOW_ORIGIN.

StandUp fires:

action:push_up

action:extend_legs

End: goat is standing; NOW moves to this new binding.

WorldGraph after one StandUp:

text
Copy code
b1: [anchor:NOW_ORIGIN]
b2: [pred:posture:fallen]
b3: [action:push_up]
b4: [action:extend_legs]
b5: [anchor:NOW, pred:posture:standing]
Edges:

text
Copy code
b1 --then--> b2    # NOW_ORIGIN → fallen
b1 --then--> b3    # NOW_ORIGIN → push_up
b3 --then--> b4    # push_up → extend_legs
b4 --then--> b5    # extend_legs → standing (NOW)
From a map perspective, the S–A–S segment is:

text
Copy code
[pred:posture:fallen] 
   → [action:push_up] → [action:extend_legs] 
   → [pred:posture:standing]
The standalone b1 anchor plus b2 predicate both represent the “fallen” situation; the actions attach off NOW and lead to a new predicate where NOW is finally placed.

## 8) Snapshot-style vs delta-style bindings

   Two encoding styles exist; CCA8 uses a snapshot-of-state style by default:

Snapshot-of-state (recommended):

Each predicate binding carries the current body/world facts (posture, proximity, feeding state, etc.).

Stable invariants (e.g., posture:standing) are repeated for a while, only changed when the fact changes.

Transient milestones (nipple:found) are often dropped once a stable state (nipple:latched) is reached.

Delta/minimal (not used today):

Each binding only adds what changed (“found”, then “latched”) without repeating posture/proximity.

Fewer tags per node, but harder to interpret a single binding in isolation.

The snapshot style keeps planning and debugging simple: each pred:* binding is a self-contained “what is true now” card.

## 9) Building small paths by hand (menu intuition)

Using the runner menus, you can manually build paths that match the tutorial diagrams:

Add predicate (3)

e.g., posture:standing, nipple:latched, milk:drinking.

Connect two bindings (4)

e.g., b2 --latch--> b3.

A typical hand-built path:

text
Copy code
NOW(b1) --then--> b2[pred:posture:standing] --latch--> b3[pred:nipple:latched] --suckle--> b4[pred:milk:drinking]
The planner (Plan to predicate menu) will then find this path when you ask for milk:drinking as the goal.

## 10) Common pitfalls and tips

    “No path found”:
    Check that:

You spelled the goal token exactly (pred:posture:standing vs pred:posture_standing),

There is a forward chain of edges from NOW (or your chosen start) to the target binding,

Edges are not reversed (B→A when you meant A→B).

Too many actions on edges:
It’s tempting to encode everything as labels (--stand_up-->). Prefer to:

make actions into action:* bindings (action:push_up), and

use edge labels mainly as annotations ("then", "latch", "search").

Tagless nodes:
Bindings with no tags are hard to interpret. Give each meaningful binding at least one pred:*, cue:*, or anchor:* tag.

11) Quick reference cheat sheet (WorldGraph concepts)
    Binding: id + tags (pred/cue/anchor/action) + edges[] + meta + engrams.

Edge: {"to": dst_id, "label": "then", "meta": {...}}; stored on source binding.

Anchors: NOW, NOW_ORIGIN, HERE → map names to binding ids.

Families: pred:*, action:*, cue:*, anchor:*.

Planner goal: any binding whose tags include pred:<token>.

Snapshot vs delta: we use snapshot-of-state by default.

Source of truth for NOW/NOW_ORIGIN: world.anchors (tags are for readability).

With this picture in mind, the later tutorials (“WorldGraph Technical Features”, “Controller”, “Environment”) should feel much more natural: they’re all just elaborations of this same map—bindings and edges, tagged with four families, driven by policies and the environment.



### Q&A to help you learn this section

Q: What’s the difference between a “binding” and a generic graph node?
A: A binding is a rich node: it carries tags (pred/cue/action/anchor), optional engram pointers, provenance (meta), and outgoing edges. It’s closer to an “episode card” than a bare vertex — it describes what was true, what happened next, and how to get to richer memory.

Q: Why do we separate pred:*, cue:*, action:*, and anchor:* families?
A: To keep semantics clear and algorithms simple. Predicates are facts/states, cues are evidence, actions are behavioral steps, and anchors are orientation points. This separation lets policies and the planner read tags without guessing what a string means.

Q: Why do we treat actions as nodes (action:*) instead of edge labels?
A: Because in the “everything is a map” view, actions are events in time, not just labels on edges. Recording them as nodes makes it easy to attach engrams, provenance, and additional structure (timing, cost) to actions, and to traverse state–action–state chains uniformly.

Q: What does “snapshot-of-state” style mean here?
A: It means each pred-binding is intended to be a self-contained state card (“what is true now”: posture, proximity, feeding state, etc.). We may repeat posture:standing across several bindings as the episode unfolds rather than only storing deltas. That makes planning and debugging much easier.

Q: How does the planner know which label to show for a binding?
A: The first pred:* tag (if present) is used as the node’s human label in pretty paths and exports. If there is no pred:* tag, we fall back to the binding id (bN).





# Binding and Edge Representation

Note: Nov 2025 -- In other part of this README, you may still see the simpler “actions-as-edge-labels” pattern that has been deprecated at this time. This section describes a richer ontology (and one that better reflects the mammalian brain) where actions become explicit `action:*` bindings and edges are conceptually just “then”. 



## Motivation

CCA8 is intended to model a **mammalian‑style cognitive architecture**, not just a symbolic planner. The core hypothesis behind the project is that:

> Mammalian cortex is built from repeated **spatial / navigation maps** (cortical minicolumns), evolutionarily related to the hippocampal–entorhinal system.  
> A “brain” is therefore a vast collection of overlapping maps, with hippocampal structures acting as higher‑level maps tying local maps together.

At the implementation level, CCA8 has two main representational layers:

* A **representation layer** (Columns / engrams / payloads) – analogous to distributed neural ensembles and local maps.

* An **index / map layer** (WorldGraph bindings and edges) – analogous to hippocampal / MTL maps over states, actions and episodes.
  
  

This is based on Schneider's work, e.g., [Frontiers | The emergence of enhanced intelligence in a brain-inspired cognitive architecture](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1367712/full) , 

 [Navigation Map-Based Artificial Intelligence](https://www.mdpi.com/2673-2688/3/2/26)   . In the CCA8 we formalize a bit more and adopt more of the common terminology of the standard symbolic predicate and subsymbolic representation layer toolboxes. 

](https://www.youtube.com/watch?v=Ld7I5EFpSYI&t=213s)

The focus of this section is to nail down a **clean, consistent ontology** (i.e., formal specification of a conceptualization) for:

* what a **binding** represents,

* what an **edge** represents,

* and how we represent **actions** and **state changes**,

in a way that:

1. Is neuro‑plausible relative to hippocampal/engram work, cognitive map theory, and the evolutionary minicolumn hypothesis our model uses;

2. Is simple and consistent enough to scale (billions of bindings over long simulations);

3. Gives the codebase a clean, minimal set of patterns that policies, FOA, planning and RL can rely on.

* * *

## Neuroscience context (very briefly)

Modern memory and navigation neuroscience gives us a few constraints and inspirations:

* **Engrams**: memories are stored in **sparse ensembles of neurons** (“engram cells”) whose activity and connectivity change during learning and can later be reactivated to express the memory.

* **Cognitive maps**: the hippocampus and related areas implement **map‑like representations** of space and, more broadly, structured task/concept spaces. Place cells, grid cells, and related populations support flexible navigation and episodic memory.

* **Index vs representation layers**: The “Tensor Brain” model and related work argue for a distinction between:
  
  * a **representation layer** (distributed activations in sensory and associative cortex), and
  
  * an **index layer** that holds discrete symbols for entities, predicates, and episodic instances, with tensor‑like links between the two.

CCA8 instantiates a similar distinction:

* Columns / engrams = **representation layer** (what the “cortical minicolumns” are doing).

* WorldGraph = **index/map layer** (what hippocampal‑like structures are doing).

In that picture, **bindings** and **edges** are not neurons; they are **index‑layer nodes and links** that point into and organize the representation layer.

* * *

## Binding ontology in CCA8: four binding “kinds”

We standardize on four conceptual kinds of bindings:

1. **Anchor bindings**

2. **Predicate bindings**

3. **Cue bindings**

4. **Action bindings**

In the implementation, a binding is still just a node with a set of tags, meta, and edges. The “kind” is given by the leading tag family:

* `anchor:*`

* `pred:*`

* `cue:*`

* `action:*`

Bindings may carry multiple tags, but there is typically **one dominant “kind”** that determines how algorithms treat them.

## Anchor bindings (`anchor:*`)

Anchor bindings are special, sparse nodes that **orient** the graph and FOA:

* `anchor:NOW` – the current “moment” or temporal focus.

* `anchor:HERE` – current spatial focus (if/when we add spatial anchors).

* `anchor:EPISODE_ROOT` – optional roots for episodes or scenarios.

These are not states or actions; they are **reference points** for:

* FOA seeding (start expansion from NOW/HERE),

* temporal / episode segmentation,

* navigation over the graph (“where am I in this story?”).

In practice, we want:

* **one `anchor:NOW` binding pointing to the latest stable state** (see below),

* and a small number of other anchors as needed.

## Predicate bindings (`pred:*`)

Predicate bindings represent **semantic / state facts** about the agent and world:

* Body / posture:
  
  * `pred:posture:fallen`
  
  * `pred:posture:standing`
  
  * `pred:posture:resting`

* Proximity / relations:
  
  * `pred:mom:close`
  
  * `pred:nipple:latched`
  
  * `pred:milk:drinking`

* Drives and internal conditions (optionally mirrored):
  
  * `pred:drive:hunger_high`
  
  * `pred:drive:fatigue_high`

We deliberately prefer simple, brain‑like labels such as `pred:posture:standing` rather than more computer‑science‑ish `pred:state:posture:standing`. The extra “state” sub‑namespace may be useful for a formal ontology, but your modeling intuition (and probably the biological reality) is that the brain is concerned with **what is happening** (“standing”, “falling”, “predator near”), not with an abstract “state:” wrapper. The _meaning_ of “this is a state” is in how the predicate is _used_ – by policies, FOA, planner, etc. – not in the literal string.

Semantically:

* **Predicate nodes** are the “noun / adjective world”: what is true about the body or environment at a particular moment.

## Cue bindings (`cue:*`)

Cue bindings are **pseudo‑nodes** for incoming sensory information in a form accessible to the maps:

* `cue:vision:silhouette:mom`

* `cue:vestibular:tilt`

* `cue:somatosensory:pressure:flank`

* `cue:drive:cold_skin`

These are **short‑lived, input‑facing** representations: they reflect what just hit the senses, not necessarily what the agent believes or remembers.

The typical flow:

* Sensors (or HybridEnvironment) produce `EnvObservation` → WorldGraph gets **cue bindings** attached near NOW.

* Policies read cues + predicates + drives to decide what to do.

* Later, “stable” interpretations of cues (e.g., `mom:close`, `nipple:found`) become **predicate bindings**.

So:

* **Cue nodes** = “what just came in”.

* **Predicate nodes** = “what the agent believes / treats as facts”.

## Action bindings (`action:*`)

Action bindings represent **motor / behavioral steps**:

* Micro‑actions:
  
  * `action:push_up`
  
  * `action:extend_legs`
  
  * `action:bleat_twice`
  
  * `action:orient_to_mom`

* Macro‑actions / policies (optional):
  
  * `action:stand_up` (if we want a macro node)
  
  * `action:suckle`

These bindings live **in the same graph** as predicates and anchors. They are created when policies execute, and they show up in episode traces as the “verb” nodes between “noun” states.

Each action binding typically carries meta such as:

* `meta["policy"] = "policy:stand_up"` (which policy created it),

* temporal stamps (`ticks`, `epoch`, `tvec64`, etc.),

* optional links to motor commands sent to a robot or environment.

Semantically:

**Action nodes** are the “verb world”: what the agent _did_ at that point along the path.



## Edges as generic “then” links

Edges in WorldGraph are **directed links between bindings**. In the early code and docs, we used edge labels both for:

* temporal/causal transitions (`then`, `fall`, `recovered_to`),

* and structural relations (`initiate_stand`, spatial relations, etc.).

To bring this closer to the “everything is a node on a map” picture and simplify algorithms, we standardize as follows:

1. **Default edge semantics**:
   
   * All episode / transition edges are **conceptually “then”**:
     
     * “this binding came after / was derived from that binding in this story.”
   
   * Implementation may store the label as `"then"` (or leave label blank and treat it as `then`).

2. **Edge labels are optional history annotations**:
   
   * We may keep a `label` field for readability and logging:
     
     * e.g. `fall`, `recovered_to`, `on`, `under`.
   
   * But algorithms (FOA, planner, policies) primarily treat these edges as **generic transitions**.
   
   * Special labels are only introduced when we have a **clear algorithmic reason** to treat those transitions differently.

3. **Semantics move to node tags and meta**:
   
   * “What happened” is determined by the **sequence of node types** (predicate, action, cue) and their tags, not by fancy edge labels.
   
   * Edges are the **glue**; nodes carry the semantics.

This matches your intuition that in the brain:

* temporal sequence, causal flow, “pointer” relationships and even spatial adjacency are all different _uses_ of the same underlying connectivity, not different “edge types” at the synapse level.

----

### Theory primer:

- **Weak causality:** Mammalian episodes often encode **soft** chains (“this happened, then that”), sufficient for immediate action without formal causal inference. In CCA8, edges labeled `"then"` capture this episode flow.
- **Two-store economy:** Keep the **symbolic graph small** (~5%): tags & edges for **recall and planning**. Keep the **heavy content** (~95%) in engrams (features, traces, sensory payloads). This avoids the brittleness of “all knowledge in a graph.”
- **From pre-causal to causal:** The symbolic skeleton is compatible with later, stronger causal reasoning layered above (e.g., annotating edges with conditions, failure modes, or learned utilities).

----



***Q&A to help you learn this section***

Q: Define “weak causality.” A: Soft episode links (“then”) without asserting logical necessity.

Q: Why engrams vs symbols?  A: Symbols = fast index, engrams = heavy content → avoids brittle all-graph designs.

Q: Can we add stronger causal reasoning later?  A: Yes, layered above (edge annotations, utilities).



## State–Action–State patterns: `policy:stand_up` as a worked example



When a policy executes, it leaves behind a simple **state–action–state** pattern in the graph.

Consider `policy:stand_up`.

## Pre‑condition

Before the policy fires, we want:

* An anchor:
  
      b_now: [anchor:NOW]

* A predicate representing current posture:
  
      b_fallen: [pred:posture:fallen, ...]

* A link so NOW’s FOA can “see” that state:
  
      b_now --then--> b_fallen
  
  

In context, there may also be:

* `pred:drive:hunger_high`,

* cues like `cue:vestibular:tilt`,

which all live in the FOA neighborhood of `b_now`.

The dev gate for `policy:stand_up` looks at that **local map**:

* posture fallen,

* age in neonatal range,

* drives not too extreme.

If satisfied, the controller chooses `policy:stand_up`.

## Execution: graph write

When `policy:stand_up` executes, it writes a short chain:
    (anchor)    b_now
                 |
                 v (then)
    (state)     b_fallen : [pred:posture:fallen]
                 |
                 v (then)
    (action)    b_act1  : [action:push_up]
                 |
                 v (then)
    (action)    b_act2  : [action:extend_legs]
                 |
                 v (then)
    (state)     b_stand : [pred:posture:standing, ...]

Implementation details:

* `b_act1` and `b_act2` are **action bindings** with:
  
  * `tags = {"action:push_up"}` and `{"action:extend_legs"}` respectively,
  
  * meta `{"policy": "policy:stand_up", "created_by": "policy:stand_up", ...}`.

* `b_stand` is a **predicate binding** with:
  
  * `tags` including `pred:posture:standing`,
  
  * meta `{"policy": "policy:stand_up", ...}`.

Every edge is:
    source --then--> target

and may optionally record a label like `"then"` in its field for clarity.

## NOW and temporal anchoring

After the stand sequence completes, we want `NOW` to **track the latest stable state**. Conceptually:

* `anchor:NOW` should ultimately refer to `b_stand` (“right now, the goat is standing”).

Implementation options:

* Update an existing `anchor:NOW` binding to point (via a `then` or internal field) to `b_stand`, or

* Create a fresh `anchor:NOW` binding `b_now2` with a `then` path from `b_fallen` → `b_act1` → `b_act2` → `b_stand` → `b_now2`.

For navigation and FOA, the key invariant is:

> **From `anchor:NOW`, FOA can quickly reach the binding(s) that encode current posture, proximity, drives, etc.**

If we later add a `NOW_origin` or episode roots, they can be separate anchors; but for basic behavior we keep: **NOW points to the latest state**.

## Cues and drives in context

During this whole process:

* **Cue bindings** near NOW (e.g., `cue:vestibular:tilt`, `cue:somatosensory:pressure`) provide the sensory evidence that posture is fallen.

* **Drives** live in a separate `Drives` object but can be mirrored as predicates (e.g., `pred:drive:hunger_high`) if needed.

* Dev gates and policies read:
  
  * `pred:posture:fallen`,
  
  * cues,
  
  * drives,  
    to decide when to fire.

So the role split is:

* **Bindings / edges**: “what the episode looked like” (states, actions, transitions).

* **Drives / context / policies**: “why we decided to do that”.

* * *

## How actions are invoked and stored



Critically:

* **Actions are invoked by policies**, not by edges.

* **Edges do not “tell the system what to do”**; they are records of what was done.

Control flow:

1. **FOA**:
   
   * starts from `anchor:NOW` and nearby bindings (predicates, cues),
   
   * builds a small subgraph (few hops) in focus.

2. **Policy gating**:
   
   * sees patterns like “`pred:posture:fallen` near NOW + neonatal age + hunger”,
   
   * selects `policy:stand_up`.

3. **Policy execution**:
   
   * calls motor controllers / environment (actuation),
   
   * writes **action bindings** (`action:*`) and final **predicate bindings** (new state) into WorldGraph, connected by `then`.

4. **Graph as trace**:
   
   * Later, FOA, planner, and RL see a stored **state–action–state** path they can learn from or re‑use.

This keeps the **architecture clean**:

* Policies are the “spinal cord / motor programs”.

* WorldGraph is the “notebook” where stories of state/action/state are written down.

* * *

## Relationship to engrams and columns

In the full CCA8 picture:

* Each binding may have **engram pointers** into column stores (representation layer):
  
  * a posture binding might have an engram for the proprioceptive/visual pattern of “standing”.
  
  * a cue binding might have an engram for a particular visual snapshot (“silhouette:mom”).
  
  * an action binding might have a motor‑related engram representing a learned action pattern (“push_up”).

WorldGraph then plays the hippocampal role:

* It links these local engrams into **episodic and semantic maps**, in line with engram and cognitive map theories.

This is exactly the **index / representation layer** story:

* Index layer (bindings + edges): discrete nodes for **anchors, predicates, cues, actions**, organized into a map.

* Representation layer (columns/engrams): distributed neural‑style representations, pointed to by bindings.

Your “cortical minicolumns are spatial maps” hypothesis fits here by treating each column as a local map over its feature space, with WorldGraph indexing and sequencing them at a higher level.

* * *

## Implications for the CCA8 codebase



Adopting this scheme implies several concrete steps.

1. **Standardize binding types**:
   
   * Ensure that:
     
     * anchors carry `anchor:*` tags,
     
     * semantic facts carry `pred:*` tags (e.g., `pred:posture:standing`),
     
     * cues carry `cue:*` tags,
     
     * actions carry `action:*` tags.
   
   * We can keep legacy tags like `pred:state:posture_standing` temporarily for compatibility, but the **canonical name** should be `pred:posture:standing`.

2. **Refactor edge usage**:
   
   * Default edge label is conceptually `then`.
   
   * Extra labels like `fall`, `recovered_to` can be kept as optional annotations, but algorithms should mostly rely on:
     
     * graph structure,
     
     * node tags/meta.

3. **Refactor policies to write S–A–S chains**:
   
   * `policy:stand_up`, `policy:recover_fall`, `policy:seek_nipple`, `policy:suckle`, etc., should:
     
     * create action bindings `action:*`,
     
     * connect them between predicate states with `then` edges,
     
     * update `anchor:NOW` so FOA can see the new state.

4. **FOA and planning**:
   
   * FOA should treat all four binding types as nodes in the **same map**, but may:
     
     * weight anchors and predicates more strongly,
     
     * treat action nodes as transitory steps.
   
   * Planner should search over state–action–state trajectories to reach target predicates (e.g., `pred:nipple:latched`, `pred:milk:drinking`).

5. **Documentation alignment**:
   
   * Docstrings in `cca8_world_graph.py`, `cca8_controller.py`, `cca8_run.py`, `cca8_env.py` should be updated to:
     
     * describe bindings as “anchor / predicate / cue / action” nodes,
     
     * describe edges as “then” transitions,
     
     * clarify that **actions are nodes**, not edges.

6. **README / design docs**:
   
   * README sections on WorldGraph and policies should be updated to reflect this white‑paper view, so future readers see:
     
     * a **unified map story**,
     
     * a clear binding ontology,
     
     * and a clean separation between control (policies) and trace (WorldGraph).

* * *

## Summary

The central design decisions are:

* **Four binding kinds**:
  
  * `anchor:*` – special nodes for NOW/HERE/origins.
  
  * `pred:*` – semantic/state facts.
  
  * `cue:*` – sensory/input postings.
  
  * `action:*` – motor/behavioral steps.

* **Edges as generic “then”**:
  
  * Edges are primarily temporal/relational glue.
  
  * Labels are optional annotations, not the main source of semantics.

* **Actions as nodes, not edges**:
  
  * Policies invoke actions.
  
  * WorldGraph stores those actions as `action:*` bindings in state–action–state chains.

* **WorldGraph as hippocampal / index map**:
  
  * It ties Columns/engrams (representation layer) into a coherent cognitive map over episodes and semantics.

This architecture:

* aligns well with hippocampal / engram / cognitive‑map evidence,

* matches your “minicolumns are spatial maps” hypothesis (everything is a node on a map),

* gives us a clean base for later language work (nouns ↔ predicates, verbs ↔ actions, temporal connectives ↔ `then`),

* and simplifies the code: fewer relation types, clearer patterns, easier refactoring.

Once we’re both happy with this conceptual foundation, the next step is to:

1. Implement this state–action–state pattern concretely for a few key policies (e.g., `stand_up`),

2. propagate the pattern into the environment simulation,

3. and then bring all docs (docstrings + README) into alignment with this binding/edge ontology. 
   
   
   
   
   
   
   
   
   
   

# Anchors, LATEST, and Base-Aware Writes



## Anchors, LATEST, and Base-Aware Writes (NOW, base_suggestion)

This section explains how the CCA8 runner uses **anchors**, the **LATEST** pointer, and the new **base-aware write** logic to keep episodes tidy and meaningful when adding new bindings.

The goal is that when you say “hang this new fact off the current situation,” the system knows *where* in the WorldGraph that is — not just “whatever node happened to be written last.”

### Anchors vs. LATEST: mental model

The WorldGraph keeps two distinct orientation mechanisms: **anchors** and a **LATEST** pointer.

* **Anchors** are bindings tagged `anchor:<NAME>` and tracked in `world._anchors` (e.g., `"NOW" → "b5"`).
  
  * `anchor:NOW` – the current **situation** or **temporal orientation**: where planning and FOA usually start.
  * `anchor:NOW_ORIGIN` – the **episode root**, pinned once on a fresh world (birth) and left alone later.
  * `anchor:HERE` – reserved for **spatial orientation** (“where the body is in space”); currently a stub.

* **LATEST** is *not* a binding tag; it’s an internal pointer `world._latest_binding_id` that always refers to the **most recently created binding**, regardless of whether it is a predicate, cue, or action.

At any moment:

* **NOW** answers: “Where am *I* in this story?”
* **LATEST** answers: “What was the last node I wrote?”

They often coincide right after a policy runs, but they are allowed (and expected) to diverge. For example, after a StandUp:

```text
b1: [anchor:NOW_ORIGIN]  →  episode root  
b2: [pred:posture:fallen]  
b3: [action:push_up]  
b4: [action:extend_legs]  
b5: [anchor:NOW, pred:posture:standing]
```

NOW and LATEST are both `b5` immediately after the StandUp policy executes. If you then add a cue:

```text
b6: [cue:vision:my_cue:mom]    # attached from NOW → b5 --then--> b6
```

* `NOW` remains `b5` (standing posture).
* `LATEST` becomes `b6` (the cue).

This separation is intentional: NOW reflects the **current state**, while LATEST simply tracks the last binding created (which might be a transient cue or helper node).

### Attach semantics: `attach="now"` vs. `"latest"` vs `"none"`

All node-creation helpers in `WorldGraph` accept an `attach=` parameter:

* `attach="now"`
  
  * Create a new binding and add an edge `NOW --then--> new`.
  * Update `LATEST = new`.

* `attach="latest"`
  
  * Create a new binding and add an edge `LATEST --then--> new`.
  * Update `LATEST = new`.

* `attach="none"` / `None`
  
  * Create a new binding **without** any auto-edge.
  * Still updates `LATEST = new`.

In other words:

* `attach="now"` → “attach from the **NOW anchor**.”
* `attach="latest"` → “attach from the **last node written**.”
* `attach="none"` → “create a floating node; I’ll wire it manually.”

### Why we needed “base” and base_suggestion

In simple demos, `attach="latest"` is good enough. But once you start mixing predicates, cues, actions, and scene captures, “latest” can drift to a node that is *not* the right semantic parent.

Example:

1. Instinct step runs **StandUp** → NOW and LATEST both at `b5` (`pred:posture:standing`).

2. You add a cue (`attach="now"`):
   
   * `b5 --then--> b6` (`cue:vision:my_cue:mom`)
   * `LATEST = b6`, NOW still `b5`.

3. You add a new predicate or scene **with `attach="latest"`**.

**Without** base-aware logic:

* The new binding would hang off `b6` (the cue) simply because that’s LATEST, even though semantically it belongs with the standing posture node `b5`.

To fix this, the runner now computes a **write base** each step — a suggested parent node for new writes that reflects the *current situation*, not just the last node touched.

### Base and base_suggestion

A **base** is “where should this new binding be linked so the episode stays tidy and meaningful?”

`choose_contextual_base(world, ctx, targets=[...])` computes a **base_suggestion** as a small dict:

```python
{"base": "NEAREST_PRED", "pred": "posture:standing", "bid": "b5"}
```

or falls back to:

```python
{"base": "HERE", "bid": "?"}      # HERE stub, unresolved
{"base": "NOW", "bid": "b_now"}   # if HERE and NEAREST_PRED aren’t available
```

In words:

* **`base["base"]`** – the *strategy* we used:
  
  * `"NEAREST_PRED"` – nearest binding (by BFS) around NOW carrying the target predicate (e.g., `posture:standing`, `stand`).
  * `"HERE"` – a spatial anchor (stubbed for now).
  * `"NOW"` – fallback to the NOW anchor.

* **`base["bid"]`** – the concrete binding id we suggest as the parent (e.g., `b5`).

* **`base["pred"]`** – the matching predicate token for diagnostics (e.g., `"posture:standing"`).

This base_suggestion answers:

> “Given the current situation (NOW + FOA), which binding is the best parent for new nodes this step?”

### Base-aware attach logic in the Runner

Some runner menus — notably **Add Predicate** and **Capture Scene** — now incorporate **base-aware logic** when you request `attach="latest"`.

The pattern is:

1. Compute a base suggestion:
   
   ```python
   base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
   ```

2. Decide an effective attach mode:
   
   ```python
   effective_attach = _maybe_anchor_attach("latest", base)
   ```
   
   * If `base["base"] == "NEAREST_PRED"` and you asked for `"latest"`, we return `"none"`.
   * Otherwise, we leave attach unchanged.

3. Create the new binding with `attach=effective_attach`.
   
   * If `effective_attach == "none"`, the node is created **unattached** (no auto edge from LATEST).

4. If we used a NEAREST_PRED base and suppressed auto-attach, we explicitly anchor the new node under the base:
   
   ```python
   _attach_via_base(world, base, new_bid, rel="then", meta={...})
   # adds base['bid'] --then--> new_bid
   ```

In logs you’ll see:

```text
[base] write-base suggestion for this add_predicate: NEAREST_PRED(pred=posture:standing) -> b5
[base] base-aware attach: new binding will be created unattached, then linked from the suggested NEAREST_PRED base instead of plain 'LATEST'.
Added binding b9 with pred:vision:silhouette:mom (attach=none)
[base] attached b9 under base b5 via then (NEAREST_PRED(pred=posture:standing) -> b5)
```

and in the mini-snapshot:

```text
b5: [anchor:NOW, pred:posture:standing]
    edges: then:b6, then:b7, then:b9
b6: [cue:vision:my_cue:mom]
    edges: (none)
b7: [action:orient_to_mom] -> b8
b8: [pred:seeking_mom]
    edges: (none)
b9: [pred:vision:silhouette:mom]
    edges: (none)
```

Here:

* LATEST before the add was `b8` (`seeking_mom`).
* `attach="latest"` *would* have made `b8 --then--> b9`.
* Base-aware logic instead anchored `b9` under `b5` (standing/NOW), which is semantically cleaner.

### Where base-aware logic is used today

Base-aware writes currently apply to:

* **Add Predicate** menu (manual predicates):
  
  * When you choose `attach="latest"` (the default), the new `pred:*` is anchored under:
    
    * the nearest `posture:standing` / `stand` near NOW (if available),
    * otherwise behaves like a normal `attach="latest"`.

* **Capture Scene → tiny engram** menu:
  
  * When you choose `attach="latest"`, the new scene binding (cue or pred) is created unattached and then anchored under the same NEAREST_PRED base, so scene engrams cluster under the appropriate posture node (e.g., “scenes while standing”).

Attach modes are still fully under your control:

* If you explicitly pick `attach="now"` or `"none"`, base-aware logic only prints a small “[base] write-base suggestion skipped…” note and respects your choice.

### Summary cheat-sheet

* **NOW_ORIGIN**
  
  * Episode root anchor; pinned once at startup, rarely used directly by policies.

* **NOW**
  
  * Semantic “current situation” anchor; planning and FOA start here.
  * Moved by the runner after significant events (e.g., StandUp).

* **HERE**
  
  * Reserved for future spatial anchoring (“where the body is in space”).

* **LATEST**
  
  * Internal pointer to the last binding created; used by raw `attach="latest"` semantics.

* **base**
  
  * A suggested parent binding (`{"base": strategy, "bid": "bN", "pred": "…"}`) computed near NOW.

* **base_suggestion / choose_contextual_base(...)**
  
  * Given NOW + FOA and target predicates, returns a base dict; NEAREST_PRED is the typical case for posture.

* **Base-aware logic**
  
  * For `attach="latest"` in certain menus, `_maybe_anchor_attach(...)` and `_attach_via_base(...)` cooperate to:
    
    * suppress naive auto-linking from LATEST,
    * explicitly anchor the new binding under the semantically meaningful base node near NOW.

The result is that this keeps the WorldGraph’s episode structure both **readable for the human reader** and **usable for planning**, even as cues and other small bindings proliferate around the current situation.



## Quick Q&A: Anchors, LATEST, and Base-Aware Writes

**Q1. What’s the difference between `NOW` and `LATEST`?**
**A.** `NOW` is an **anchor binding** (tagged `anchor:NOW`) that represents the *current situation* in the episode — planning and FOA start here. `LATEST` is just an **internal pointer** to the last binding created (`_latest_binding_id`). They often coincide right after a big event, but they can diverge: `NOW` stays on the meaningful situation node, while `LATEST` chases every new binding (including transient cues).

---

**Q2. What is `NOW_ORIGIN` used for?**
**A.** `NOW_ORIGIN` is an anchor marking the **episode root** — the binding where `NOW` started on a fresh world. It’s a stable “start” marker. The runner doesn’t change it during normal operation; it’s mostly there for orientation and future algorithms that need a canonical start.

---

**Q3. What happens when I use `attach="now"` vs `attach="latest"`?**
**A.**

* `attach="now"`:
  Creates a new binding and adds `NOW --then--> new`. The NOW anchor is the parent.
* `attach="latest"`:
  Creates a new binding and adds `LATEST --then--> new`. The last-created binding is the parent.

Both modes update `LATEST = new`. Base-aware logic may intercept `"latest"` in some menus (see below), but `"now"` always attaches from the NOW anchor.

---

**Q4. What do we mean by a “base” or `base_suggestion`?**
**A.** A **base** is the binding the system thinks is the **best parent** for new writes *this step*. `base_suggestion` is a small dict like:

```python
{"base": "NEAREST_PRED", "pred": "posture:standing", "bid": "b5"}
```

It means:

> “Starting from NOW, the nearest binding with `pred:posture:standing` is `b5`; that’s the node we should probably hang new facts under.”

If no such predicate is found, the strategy can fall back to HERE or NOW.

---

**Q5. Is a base the same thing as `NOW`?**
**A.** No. `NOW` is the **starting point** for search. A base is the **chosen parent** within the neighborhood around NOW. In many simple cases NOW *is* the best base (e.g., NOW is the standing node), but in general:

* `NOW` = “where we are in the episode.”
* `base` = “which node under/around here should own this new fact.”

---

**Q6. What problem does base-aware logic solve for `attach="latest"`?**
**A.** Without base-aware logic, `attach="latest"` blindly attaches new bindings from `_latest_binding_id`. If the last thing you wrote was a cue or a helper node, new predicates/scenes hang under that, even though they semantically belong under a posture or state node.

Base-aware logic:

1. Computes a base near NOW (e.g., nearest `posture:standing`).

2. If you requested `attach="latest"` and the base is `NEAREST_PRED`, it:
   
   * creates the new node with `attach="none"`,
   * then explicitly adds `base_bid --then--> new`.

So the new binding is anchored under the **meaningful state** (e.g., “standing at b5”) instead of some random “last node” (e.g., a cue at b6).

---

**Q7. Does base-aware logic affect `attach="now"` or `attach="none"`?**
**A.** No. If you explicitly choose `attach="now"` or `"none"`:

* The runner prints a small note that it has a base suggestion but “skips” it because the attach mode was user-specified.

* The write behaves exactly as before:
  
  * `"now"` attaches from the NOW anchor,
  * `"none"` creates a floating node (you can wire it manually).

Base-aware write behavior only kicks in when **you choose `attach="latest"`** in certain menus.

---

**Q8. Which menus currently use base-aware logic?**
**A.** Today:

* **Add Predicate** – default `attach="latest"` uses a NEAREST_PRED base near NOW (standing/stand) and anchors the new predicate under that node.
* **Capture Scene** – default `attach="latest"` creates the scene binding unattached and anchors it under the NEAREST_PRED base (e.g., “scene while standing”).

More menus (and maybe env injection) can be upgraded to use the same pattern in future phases.









# Tutorial on Drives

   drive:* as the notation for internal flags, but by design they are:

   **ephemeral controller-only flags** — _not_ stored as pred:* in the WorldGraph.

   There are three layers to this:

   **a) Drives →drive:* flags**

   In Drives.flags() we turn raw numbers into **ephemeral flags**:

   defflags(self) -> List[str]:

       tags: List[str] = []

       if self.hunger > HUNGER_HIGH:

           tags.append("drive:hunger_high")

       if self.fatigue > FATIGUE_HIGH:

           tags.append("drive:fatigue_high")

       if self.warmth < WARMTH_COLD:

           tags.append("drive:cold")

       return tags

   These drive:flags live **inside the Drives object**,

* are recomputed on each controller step / autonomic tick,

* are used by policies in trigger(...) and deficit scoring.
  They are **not** automatically written to the WorldGraph.
  The controller docstring saysthis explicitly:
  “Drives: numeric homeostaticvalues (hunger, fatigue, warmth) → derive 'drive:_' flags (ephemeral tagsthat are not written to worldgraph)”  
  “Controller-only flags (never written as pred:_): drive:* — ephemeral …”
  **b)Runner-level helper** **_drive_tags(...)**
  In cca8_run.py, _drive_tags(drives) is a robust helper that:

* Preferentially uses drives.flags() (new API),

* Falls back to drives.predicates() (legacy),

* Or derives flags directly from hunger/fatigue/warmth if needed:
  def_drive_tags(drives) -> list[str]:
      ...
      # Prefer the new API
      if hasattr(drives, "flags"):
          tags = list(drives.flags())
          return [t for t in tags ifisinstance(t, str)]
      ...
      # Last-resort derived flags
      tags = []
      if drives.hunger > 0.6:tags.append("drive:hunger_high")
      if drives.fatigue > 0.7:tags.append("drive:fatigue_high")
      if drives.warmth < 0.3:tags.append("drive:cold")
      return tags
  These are still **internalflags**; at this point nothing is in the graph yet.
  **c) How/whendo drive flags touch the WorldGraph?**
  Two ways:
1. **As cues** (our house style):_emit_interoceptive_cues converts _rising-edge_ drive flags into cue:drive:* bindings:
   2.  started =flags_now - flags_prev  # e.g.{"drive:hunger_high"}
   3.  for f insorted(started):
   4.      world.add_cue(f, attach=attach,
   5.                    meta={"created_by":"autonomic", "ticks": ctx.ticks})
   6.      # → creates binding with tag"cue:drive:hunger_high"
   7.  ctx.last_drive_flags= flags_now
   8.  returnstarted
   So ifhunger crosses HUNGER_HIGH on an autonomic tick, you get a binding like:
   b6:[cue:drive:hunger_high]
   That’s **evidence**,not a goal.

2. **As predicates (rare, explicit)**:  
   If we ever want a **plannable drive condition**, we explicitly use pred:drive:* (or cue:drive:* as evidence). The docstring hints at this:
   “…controller-only flags … never written as pred:* …  
   e.g., plannable drive condition → pred:drive:hunger_high, or evidence → cue:drive:hunger_high”
   But bydefault, **we do not auto-write** **pred:drive:***; you’d only see that if you deliberately created it (e.g., for a demo).
   So the mental model:
   drive: = **ephemeral flags** on Drives (used by triggers/deficit scoring, not persisted).
   cue:drive: = **WorldGraph evidence** when drive thresholds _start_ (rising edge).
   pred:drive: = **explicit planner goals** (only if we choose to add them).

**TL;DR:**

* drive:* are still ephemeral controller flags; we use cue:drive:* and pred:drive:* only when we explicitly want them in WorldGraph.
  
  

### Q&A to help you learn this section

Q: Are drive:* flags stored in the WorldGraph by default?
A: No. drive:* flags (e.g. drive:hunger_high, drive:fatigue_high, drive:cold) are ephemeral controller signals computed from numeric drives (hunger, fatigue, warmth) each tick. They live in the Drives object and are used by policy triggers and deficit scoring; they are not written as pred:* unless you explicitly create pred:drive:* or cue:drive:*.

Q: When do drive flags become visible as WorldGraph tags?
A: Only in two cases: (1) the autonomic path deliberately emits interoceptive cues (e.g. cue:drive:hunger_high on a rising edge via _emit_interoceptive_cues), or (2) you explicitly choose to represent a plannable drive condition as pred:drive:*. By default, drive flags stay out of the graph.

Q: Why distinguish drive:* from pred:drive:* and cue:drive:*?
A: drive:* flags are internal controller facts (“how hungry/fatigued/cold I am”) used by triggers. pred:drive:* would be a persisted fact you might plan toward, and cue:drive:* is evidence (“I just sensed cold skin”). Keeping these separate avoids cluttering the graph while still allowing you to model drive states explicitly when needed.

Q: How do policies actually see the drive state?
A: Policies call drives.flags() (or the runner helper _drive_tags(drives)) to get a list of drive:* flags. They then test for the presence/absence of these flags in trigger(...) and possibly in deficit scoring, without touching the WorldGraph.

Q: If I want the agent to plan around hunger, what should I do?
A: Decide whether you want hunger to be a goal or just evidence. Use pred:drive:hunger_high if you want planners to explicitly seek alleviation conditions; use cue:drive:hunger_high if it should only modulate which policies fire (e.g., SeekNipple) without becoming a planner target.









# Tutorial on WorldGraph Technical Features

This tutorial teaches you how to **build, inspect, and reason about the WorldGraph**—the symbolic fast index that sits at the heart of CCA8. It’s written for developers new to the codebase.



The module implements:

- **Bindings** — nodes that carry tags, meta, optional engram pointers, and outgoing edges.
- **Edges** — directed `"then"` links between bindings with optional human-readable labels.
- **Anchors** — named bindings like NOW and NOW_ORIGIN.
- **TagLexicon** — a restricted, stage-aware vocabulary for tags.
- **Planner** — BFS (or Dijkstra) from a start binding to a `pred:<token>` goal.
- **Persistence** — `to_dict()` / `from_dict()` for snapshots.
  
  

**Note: Code changes will occur over time,  but the main ideas below should remain stable with the project**



## 0. Snapshot header: where the numbers come from

The **snapshot** shown in the Runner (menu: “Display snapshot”) pulls values directly from `WorldGraph`, `Drives`, and `Ctx`. It’s useful to know where they come from:

- **NOW=b5** → `_anchor_id(world, "NOW")` (usually `world._anchors["NOW"]`)

- **NOW_ORIGIN=b1** → `_anchor_id(world, "NOW_ORIGIN")`

- **LATEST=b9** → `world._latest_binding_id` (most recently created binding)

- **NOW_LATEST=b9** → alias for `LATEST` for convenience

- **CTX fields**:
  
  - `age_days` → `ctx.age_days`
  - `ticks` → `ctx.ticks`
  - `profile` → `ctx.profile`
  - `winners_k` → `ctx.winners_k`
  - `vhash64(now)` → `ctx.tvec64()` (temporal vector fingerprint)
  - `epoch` → `ctx.boundary_no`
  - `epoch_vhash64` → `ctx.boundary_vhash64`

- **TEMPORAL**:
  
  - `dim` → `ctx.temporal.dim`
  - `sigma` → `ctx.temporal.sigma`
  - `jump`  → `ctx.temporal.jump`
  - `cos_to_last_boundary` → `ctx.cos_to_last_boundary()`

- **DRIVES**:
  
  - `hunger`, `fatigue`, `warmth` → `drives.hunger/fatigue/warmth`

- **POLICIES telemetry**:
  
  - `n`, `succ`, `rate`, `q`, `last` → from the “skill ledger” per policy (updated when `execute()` returns).

- **BINDINGS / EDGES**:
  
  - BINDINGS: iterate `world._bindings` in id order and print `tags`.
  - EDGES: scan each binding’s outgoing `edges` and print `src --label--> dst` (duplicates collapsed with `×N`).

This is mostly convenience wiring around the core WorldGraph API.

---

## 1. What `cca8_world_graph.py` is for

At a high level, `cca8_world_graph.py` implements:

- A small **episode graph** (`WorldGraph`) where each binding is a time-slice,
- **Edges** (`src → dst`) with labels (often `"then"`),
- **Anchors** (NOW, NOW_ORIGIN, …) for orientation,
- A **restricted lexicon** (`TagLexicon`) to keep tags clean,
- **Planning** (BFS / Dijkstra) over that graph,
- **Persistence** (JSON-friendly snapshots).

The design is intentionally minimal: the graph is an **index**, not a full knowledge base. Heavy content lives in engrams; the graph just tells you what led to what.

---

## 2. Core classes

| Class        | Purpose                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| `Binding`    | A node (episode card) with `id`, `tags`, `edges`, `meta`, `engrams`.                                         |
| `Edge`       | A small dict describing a directed link: `{"to": dst_id, "label": str, "meta": dict}`.                       |
| `TagLexicon` | Defines allowed tokens per **stage** and **family**; enforces allow/warn/strict policy.                      |
| `WorldGraph` | Manages all bindings, edges, anchors, lexicon enforcement, planning, persistence, and simple action metrics. |

Bindings and edges make up the graph; the lexicon and planner are the disciplines that keep it usable.

---

## 3. Binding internals (shape and families)

A `Binding` is a `@dataclass(slots=True)` with:

```python
@dataclass(slots=True)
class Binding:
    id: str
    tags: set[str]
    edges: list[Edge]
    meta: dict
    engrams: dict
```

**Families** of tags we use:

* `pred:*` — predicates (facts/states), e.g. `pred:posture:standing`, `pred:nipple:latched`.

* `action:*` — actions (verbs), e.g. `action:push_up`, `action:extend_legs`.

* `cue:*` — cues/evidence, e.g. `cue:vision:silhouette:mom`, `cue:drive:hunger_high`.

* `anchor:*` — anchors, e.g. `anchor:NOW`, `anchor:NOW_ORIGIN`.

_Invariants:_

* Each binding has a unique `id` (`"b1"`, `"b2"`, …).

* Edges live in `binding.edges` on the **source** node.

* A binding with no tags is allowed but discouraged for long-term use (harder to interpret).

* The **first `pred:*` tag**, if present, is used as the default label in pretty paths and exports.

* * *

## 4. Creating bindings (anchors, predicates, cues, actions)

The public API for node creation is:

`world = WorldGraph()world.set_tag_policy("allow")  # or "warn"/"strict" now = world.ensure_anchor("NOW")`

**Anchors**

`now = world.ensure_anchor("NOW")    # returns binding id for NOW`

* If NOW exists → returns its id.

* If not → creates a binding with `tags={"anchor:NOW"}` and records it in `world._anchors`.

**Predicates**

`b1 = world.add_predicate("posture:standing", attach="now") # writes pred:posture:standing; NOW -> b1 if attach="now"`

**Cues**

`c1 = world.add_cue("vision:silhouette:mom", attach="latest") # writes cue:vision:silhouette:mom; LATEST -> c1 if attach="latest"`



**Actions**

`a1 = world.add_action("push_up", attach="now")a2 = world.add_action("extend_legs", attach="latest") # writes action:push_up, action:extend_legs; NOW -> a1 -> a2`

All three of `add_predicate`, `add_cue`, `add_action` accept:

* `attach="now"` — auto-edge `NOW --then--> new`.

* `attach="latest"` — auto-edge `LATEST --then--> new`.

* `attach=None` or `"none"` — no auto-edge; just create the binding and update `LATEST`.

`world._latest_binding_id` is updated to the new binding each time.



## 5. Edges and attach semantics

Edges are stored **on the source binding**:

`e = {"to": dst_id, "label": "then", "meta": {...}}binding.edges.append(e)`

The `add_edge(...)` helper is:

`world.add_edge(src_id, dst_id, label="then", meta=None)`

Attach helpers (`attach="now"/"latest"`) just call `add_edge(...)` under the hood with `label="then"`.

**Conventions:**

* **Semantics**: every edge is conceptually `"then"` — “this binding was followed by that one.”

* **Labels**: you may use labels like `"approach"`, `"search"`, `"latch"`, `"suckle"` as **human-facing aliases**. The planner does not rely on them for correctness.

* **Metrics**: any numeric properties (distance, duration, speed, cost) belong in `edge.meta`, not in the tag name.
  
  

## 6. Lexicon: restricted vocabulary and enforcement

`TagLexicon` enforces a small, stage-aware vocabulary:

* `STAGE_ORDER = ("neonate", "juvenile", "adult")` (example).

* `BASE[stage][family]` lists allowed tokens for each family/stage.

* `LEGACY_MAP` is now empty (we’ve removed `state:*` and `pred:action:*`).

`WorldGraph` wires this up:

`world.set_stage("neonate")world.set_tag_policy("warn")   # "allow" | "warn" (default) | "strict"`

When you call `add_predicate/add_cue/add_action`, the graph:

1. Normalizes family + token (e.g. `"pred", "posture:standing"`),

2. Uses `_enforce_tag(family, token_local)` to:
   
   * **allow** silently in `"allow"` mode,
   
   * **warn** (one-line log) and accept in `"warn"` mode,
   
   * **raise ValueError** in `"strict"` mode for off-lexicon tokens.

This protects you from accidental tag drift (e.g. `posture_standing` vs `posture:standing`) and keeps the early neonate vocabulary small and meaningful.



## 7. Anchors and NOW/NOW_ORIGIN behavior

Anchors are managed via:

`bid = world.ensure_anchor("NOW")`

The runner also uses:

* `world.set_now(bid, tag=True, clean_previous=True)`  
  to move NOW when a policy completes (so NOW always points to the latest stable predicate state),

* an `ensure_now_origin(world)` helper that sets `NOW_ORIGIN` once per episode.

Snapshot header shows:

`NOW=b5  LATEST=b9NOW_ORIGIN=b1NOW_LATEST=b9`

* **NOW** — the main planning start.

* **NOW_ORIGIN** — the root of this episode (birth).

* **LATEST** / **NOW_LATEST** — the most recently created binding id.
  
  

## 8. Planning: BFS / Dijkstra over `pred:*` tags

The planner entrypoint is:

`path = world.plan_to_predicate(src_id=now, token="posture:standing")`

* **Goal test**: “Does this binding’s tags contain `pred:posture:standing`?”

* **Algorithm**: BFS (default) or Dijkstra (if you call `set_planner("dijkstra")`).

* **Return**: `list[str]` of binding ids (`["b1","b3","b4","b5"]`) or `None` if the goal can’t be reached.

The Runner’s menu wraps this and prints:

* `Path (ids): b1 -> b3 -> b4 -> b5`

* A pretty path (with first `pred:*` tag per node).

* A **typed path** and **reverse typed path** that show `[binding_id:label]` pairs (anchor, actions, predicates).

Because edges are unweighted by default, BFS gives a shortest-hop path. If you later add costs in `edge.meta` (e.g. `weight`, `cost`, `duration_s`), Dijkstra uses those values.



## 9. Engrams: pointers, not payloads

Bindings can carry **pointers** to external memory (columns):

`binding.engrams = {    "column01": {"id": "<engram_id>", "act": 1.0, "meta": {...}}}`

WorldGraph provides helpers (`attach_engram`, `get_engram`) but does not know what’s inside the engram payload. Heavy data is kept outside the graph for speed and simplicity.

Planner ignores engrams entirely; they matter only for analysis or for advanced perception hooks.



## 10. Reasonableness checks and invariants

`WorldGraph.check_invariants()` can be used to validate:

* Every binding id is unique.

* All edges’ `to` fields point to existing bindings.

* Anchors in `world._anchors` point to valid bindings.

* `latest` (if not `None`) points to a valid binding.

* Optional: NOW has the `anchor:NOW` tag if `tag=True` was used in `set_now`.

The Runner uses various preflight probes to assert attach semantics, planner behavior, and lexicon enforcement are all working as intended.



## 11. Minimal code crib (for quick experiments)

`from cca8_world_graph import WorldGraph  # 1. Create world and anchors g = WorldGraph()g.set_tag_policy("allow")      # be permissive while experimenting now = g.ensure_anchor("NOW")  # 2. Build a tiny S–A–S episode: fallen → stand_up → standing fallen = g.add_predicate("posture:fallen", attach="now")a1 = g.add_action("push_up", attach="now")a2 = g.add_action("extend_legs", attach="latest")standing = g.add_predicate("posture:standing", attach="latest")  # 3. Plan and pretty-print path = g.plan_to_predicate(now, "posture:standing") print("Path:", path) print(g.plan_pretty(now, "posture:standing"))`

Typical output:

`Path: ['b1','b3','b4','b5']b1(NOW_ORIGIN) --then--> b3[action:push_up] --then--> b4[action:extend_legs] --then--> b5[posture:standing](NOW)`

From here you can add cues, attach engrams, export to Pyvis HTML, and exercise the rest of the WorldGraph features with confidence.



## Core instance attributes and methods for WorldGraph Module

**Note: Code changes will occur over time, but the main ideas below should remain stable with the project**

These are the main internal fields of a `WorldGraph` instance:

- `_bindings: dict[str, Binding]`  
  All bindings by id (e.g. `"b7" → Binding(...)`).

- `_anchors: dict[str, str]`  
  Anchor name → binding id (e.g. `"NOW" → "b5"`, `"NOW_ORIGIN" → "b1"`).

- `_latest_binding_id: str | None`  
  Id of the **most recently created binding**, regardless of family (`pred`, `action`, `cue`, or `anchor`).

- `_id_counter: itertools.count`  
  Generator for `"b<N>"` ids (`b1`, `b2`, …).

- `_lexicon: TagLexicon`  
  Restricted vocabulary for tags, per stage & family (`pred`, `action`, `cue`, `anchor`).

- `_stage: str`  
  Current developmental stage (e.g. `"neonate"`, `"juvenile"`, `"adult"`).

- `_tag_policy: str`  
  Lexicon enforcement policy: `"allow"`, `"warn"` (default), or `"strict"`.

- `_plan_strategy: str`  
  Planner choice: `"bfs"` (unweighted shortest-hop) or `"dijkstra"` (weighted edges).

Module-level constant:

- `_ATTACH_OPTIONS: set[str] = {"now", "latest", "none"}`  
  Valid values for `attach=` in `add_predicate`, `add_cue`, and `add_action`.

## Selected public methods (overview)

This is a **quick overview** of the most important methods. The “Cheat-sheet: `WorldGraph` public API” section below contains a more detailed list.

| Method                  | Purpose                                                                           |
| ----------------------- | --------------------------------------------------------------------------------- |
| `ensure_anchor`         | Create/get an anchor binding and tag it `anchor:<NAME>`.                          |
| `set_now`               | Repoint the `NOW` anchor to a binding id; optionally clean old tags.              |
| `add_predicate`         | Create a `pred:<token>` binding; optionally auto-attach from `NOW`/`LATEST`.      |
| `add_cue`               | Create a `cue:<token>` binding; optionally auto-attach from `NOW`/`LATEST`.       |
| `add_action`            | Create an `action:<token>` binding; optionally auto-attach from `NOW`/`LATEST`.   |
| `add_edge`              | Add a directed edge `src --label--> dst` (label often `"then"`).                  |
| `delete_edge`           | Remove one or more edges between `src` and `dst` (with optional label).           |
| `plan_to_predicate`     | BFS/Dijkstra from a starting id to the first binding with `pred:<token>`.         |
| `pretty_path`           | Format a list of ids into a human-readable path (ids + first `pred:*`).           |
| `plan_pretty`           | Convenience: run `plan_to_predicate` and pretty-print the result.                 |
| `to_dict` / `from_dict` | Snapshot/restore bindings, anchors, and id counters.                              |
| `check_invariants`      | Validate basic graph invariants (anchors valid, edges point to real nodes, etc.). |
|                         |                                                                                   |



## Cheat-sheet: `WorldGraph` public API

**Lifecycle & config**

* `WorldGraph()` — empty graph, stage=`neonate`, policy=`warn`, planner from `CCA8_PLANNER` env (default `bfs`).

* `set_stage(stage: str)` / `set_stage_from_ctx(ctx)`

* `set_tag_policy(policy: str)` — `"allow"|"warn"|"strict"`

* `set_planner(strategy: str = "bfs")` / `get_planner() -> str`

**Anchors & orientation**

* `ensure_anchor(name: str) -> str` — create/get anchor binding (tags it `anchor:<NAME>`).

* `set_now(bid: str, *, tag=True, clean_previous=True)` — repoint the NOW anchor; tidy tags.
  
  

**Nodes**

* `add_predicate(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Creates `pred:<token>` node; updates `latest`.
  
  * `attach="now"|"latest"|"none"` → auto-edge (NOW→new) or (latest→new) or none.

* `add_cue(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Same semantics; creates `cue:<token>`; updates `latest`.

* `add_action(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Creates an `action:<token>` node; updates `latest`.
  
  * `attach="now"|"latest"|"none"` → auto-edge (NOW→new) or (latest→new) or none.

* `add_binding(tags: set[str], *, meta=None, engrams=None) -> str`
  
  * Low-level constructor (prefer the helpers above).
    
    
    
    

## Internal helpers (private by convention)

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



**`Edge` (TypedDict)**

* Shape: `{"to": str, "label": str, "meta": dict}`

* Purpose: stored on the **source** `Binding` to represent a directed edge and its label/metrics.

* Example:
    e: Edge = {"to": "b7", "label": "stand", "meta": {"duration_s": 2.5}}

**`Binding` (dataclass, `slots=True`)**

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
      
      * E.g., `("pred", "pred:posture_standing") -> ("pred", "posture_standing")`

## Cheat-sheet: `WorldGraph` core state

* `_bindings: dict[str, Binding]`

* `_anchors: dict[str, str]` (e.g., `"NOW" -> "b1"`)

* `_latest_binding_id: str | None`

* `_id_counter: itertools.count` (`"b<N>"` ids)

* `_lexicon: TagLexicon`

* `_stage: str` (`"neonate"` …)

* `_tag_policy: str` (`"allow"|"warn"|"strict"`)

* `_plan_strategy: str` (`"bfs"|"dijkstra"`)

## Cheat-sheet: `WorldGraph` public API

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

* `add_action(token: str, *, attach: str|None = None, meta=None, engrams=None) -> str`
  
  * Creates an `action:<token>` node; updates `latest`.
  
  * `attach="now"|"latest"|"none"` → auto-edge (NOW→new) or (latest→new) or none.

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

## Minimal usage crib

### 0) Start a world

    from cca8_world_graph import WorldGraph
    g = WorldGraph()
    g.set_tag_policy("allow")  # keep lexicon quiet while learning
    now = g.ensure_anchor("NOW")

### 1) Add predicates / cues (with auto-edges)

    b1 = g.add_predicate("posture:standing", attach="now")     # NOW -> b1
    b2 = g.add_cue("vision:silhouette:mom", attach="latest")   # b1 -> b2
    print(g.plan_pretty(now, "posture:standing"))              # NOW -> b1

### 2) Manual action edges

    fallen = g.add_predicate("posture:fallen", attach="none")
    stand  = g.add_predicate("posture:standing", attach="none")
    g.add_edge(fallen, stand, label="stand", meta={"duration_s": 3.2})
    print(g.plan_pretty(fallen, "posture:standing"))  # fallen --stand--> standing

### 3) Auto-chain timeline with `attach="latest"`

    a = g.add_predicate("alert", attach="latest")
    b = g.add_predicate("seeking_mom", attach="latest")
    c = g.add_predicate("nipple:found", attach="latest")
    print(g.plan_pretty(now, "nipple:found"))  # NOW -> ... -> c

### 4) Planner choice (BFS vs Dijkstra)

    print(g.get_planner())   # 'bfs'
    g.set_planner("dijkstra")
    print(g.get_planner())   # 'dijkstra'

### 5) Action inspection

    print(g.list_actions())               # ['stand', 'then', ...]
    print(g.action_counts())              # {'stand': 1, 'then': 4, ...}
    print(g.action_metrics("stand"))      # aggregates edge.meta for 'stand'
    print(g.action_summary_text())        # readable summary of actions

### 6) Persistence (save / load)

    snap = g.to_dict()
    # ... write to JSON if you like ...
    g2 = WorldGraph.from_dict(snap)       # id counter advanced above max b<N>

### 7) Reasonableness checks

    issues = g.check_invariants(raise_on_error=False)
    print(issues)  # [] when all good

### 8) Pretty printing options

    path = g.plan_to_predicate(now, "seeking_mom")
    print(g.pretty_path(path, node_mode="id+pred", show_edge_labels=True))
    # variants: node_mode='id' or 'pred'; annotate_anchors=True/False

### 9) Engram bridge (lightweight pointer)

    bid = g.add_predicate("alert", attach="latest")
    g.attach_engram(bid, column="column01", engram_id="engr_123", act=0.9, extra_meta={"note": "demo"})
    print(g.get_engram(bid, column="column01"))



# Tutorial on Breadth-First Search (BFS) Used by the CCA8 Fast Index

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

## Worked example (hand simulation)

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

### Initial state

`frontier = [S] expanded = {} parent   = {S: None}`

### Step 1 — pop S, enqueue S’s neighbors

Neighbors in order: A, B.

`frontier = [A, B] expanded = {S} parent   = {S: None, A: S, B: S}`

### Step 2 — pop A, enqueue A’s neighbors

Neighbors: C, D.

`frontier = [B, C, D] expanded = {S, A} parent   = {S: None, A: S, B: S, C: A, D: A}`

### Step 3 — pop B, enqueue B’s neighbors

Neighbors: D, E.  
D is already in `parent` (visited-on-enqueue), so **skip D**; enqueue only E.

`frontier = [C, D, E] expanded = {S, A, B} parent   = {S: None, A: S, B: S, C: A, D: A, E: B}`

### Step 4 — pop C, enqueue C’s neighbors

Neighbor: G (the goal). Enqueue it.

`frontier = [D, E, G] expanded = {S, A, B, C} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

### Step 5 — pop D, enqueue D’s neighbors

Neighbors: E, A. Both already discovered; **skip**.

`frontier = [E, G] expanded = {S, A, B, C, D} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

### Step 6 — pop E, enqueue E’s neighbors

Neighbor: G (already discovered); **skip**.

`frontier = [G] expanded = {S, A, B, C, D, E} parent   = {S: None, A: S, B: S, C: A, D: A, E: B, G: C}`

### Step 7 — pop G (goal)

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
   
   
   
   
   
   
   
   

# Tutorial on BodyMap



## Overview: BodyMap in the Architecture: Body + Peripersonal Near Space

**CCA8 keeps two main maps:**

**WorldGraph** – the episode index: “what happened over time” (states, actions, cues, weak causality).

**BodyMap** – a tiny, always-on map of the agent’s own body plus the immediate near world.

BodyMap is implemented as a separate WorldGraph instance (ctx.body_world) with a small, fixed set of slots (ctx.body_ids):

root – the body as a whole (anchor:BODY_ROOT).

posture – overall posture (pred:posture:fallen, pred:posture:standing, pred:resting).

mom – mom’s distance relative to the body (pred:proximity:mom:far / pred:proximity:mom:close).

nipple – nipple / latch state (pred:nipple:hidden, pred:nipple:found, pred:nipple:latched, plus pred:milk:drinking when feeding).
(at the time of writing, the software emulates a newborn goat and thus this is an important part of its world; the fixed set of slots will expand and change with software development and of course, development of the goat)

Edges form a tiny body-centred scene graph:

BODY_ROOT --body_state-->     POSTURE
BODY_ROOT --body_relation-->  MOM
MOM       --body_part-->      NIPPLE

### Conceptually:

BodyMap is the body schema + peripersonal near space.
It represents “how my body is configured right now, and where crucial things are relative to me” (mom, nipple, later shelter/cliff), not the full world.

WorldGraph is the story of the world over time.
It accumulates all posture/feeding events, actions, cues, and transitions as an episode index for planning and inspection.

The environment pipeline keeps the separation clean:

HybridEnvironment maintains EnvState (God’s-eye world state) and produces EnvObservation.

The runner:

injects EnvObservation.predicates / .cues into the main WorldGraph as pred:* / cue:*, and

mirrors discrete posture / mom-distance / nipple predicates into BodyMap via update_body_world_from_obs(ctx, env_obs).

The controller then treats BodyMap as the authoritative, body-centred register for gating:

body_posture(ctx) → "standing" | "fallen" | "resting" | None

body_mom_distance(ctx) → "near" | "far" | None

body_nipple_state(ctx) → "latched" | "found" | "hidden" | None

Policies read BodyMap first, and fall back to the episode graph only when BodyMap is stale or missing. For example:

StandUp uses BodyMap posture to decide whether to stand and when to stop retrying.

SeekNipple uses BodyMap posture, nipple state, and (when available) mom distance (“don’t seek nipple if mom is clearly far”).

In short:

**WorldGraph** = compact symbolic episode index over time.

**BodyMap** = compact, body-centred near-space map (posture + mom + nipple, later shelter/cliff) reflecting “right now”.

The detailed structure and update rules for BodyMap are described below.



## BodyMap: Tiny Body + Near-World Register

The newborn goat doesn’t just have a world graph – it has a sense of its own body and the immediate world around it. In the current CCA8 build, this is captured by a small, separate graph called the BodyMap.

BodyMap is implemented as a second WorldGraph instance (ctx.body_world) with a handful of fixed nodes (ctx.body_ids) that act like a structured register:

**root** – the body as a whole (anchor:BODY_ROOT).

**posture** – overall posture (pred:posture:fallen / pred:posture:standing / pred:resting).

**mom** – mom’s distance relative to the body (pred:proximity:mom:far / pred:proximity:mom:close).

**nipple** – nipple / latch state (pred:nipple:hidden / pred:nipple:found / pred:nipple:latched, plus pred:milk:drinking when latched and feeding).

Edges encode a tiny body-centered scene graph:

BODY_ROOT --body_state-->     POSTURE
BODY_ROOT --body_relation-->  MOM
MOM       --body_part-->      NIPPLE

This is enough to express the core neonatal situation:
“I am fallen or standing; mom is far/near; nipple is hidden/found/latched.”



## How BodyMap is created and updated

Initialization (Runner)

At runner startup, interactive_loop(...) calls a helper:

ctx.body_world, ctx.body_ids = init_body_world()

init_body_world():

creates a new WorldGraph() for the BodyMap,

seeds four bindings: root, posture, mom, nipple,

tags them with the default neonatal state:

posture: pred:posture:fallen

mom: pred:proximity:mom:far

nipple: pred:nipple:hidden

These are body-side defaults before any environment step runs.

Update from EnvObservation

Every time the environment produces a new observation (via HybridEnvironment.step(...)), the runner calls:

inject_obs_into_world(world, ctx, env_obs)
update_body_world_from_obs(ctx, env_obs)

update_body_world_from_obs(...) mirrors discrete predicates from EnvObservation.predicates into the BodyMap slots:

If posture:standing appears in env_obs.predicates, BodyMap’s posture node’s tags are rewritten to include pred:posture:standing (and drop old posture tags).

If posture:fallen appears, it becomes pred:posture:fallen.

If resting appears, BodyMap marks pred:resting.

proximity:mom:close / proximity:mom:far update the mom slot.

nipple:found / nipple:latched / milk:drinking update the nipple slot accordingly (with pred:milk:drinking added when latched+feeding).

So on every env step we have:

EnvState  →  PerceptionAdapter  →  EnvObservation
                     │
                     ├─→ main WorldGraph (pred:* / cue:*)
                     └─→ BodyMap (posture / mom / nipple slots)

Snapshot output includes a compact BODYMAP panel:

BODYMAP (body + near-world):
  (**different map than the larger WorldGraph**)
  (same binding ids e.g., 'b1','b2', etc. but different map)
  root   : b1: [anchor:BODY_ROOT]
  posture: b2: [pred:posture:fallen]
  mom    : b3: [pred:proximity:mom:far]
  nipple : b4: [pred:nipple:hidden]

Note: binding ids (b1, b2, …) in BodyMap are separate from the main WorldGraph; each graph instance has its own bN space.

Reading BodyMap like a register (controller helpers)

To make BodyMap feel like simple fields, the controller exposes three helpers:

body_posture(ctx)       -> "fallen" | "standing" | "resting" | None
body_mom_distance(ctx)  -> "far"    | "near"     | None
body_nipple_state(ctx)  -> "hidden" | "found"    | "latched" | None

Internally they:

look up ctx.body_world and ctx.body_ids["posture" / "mom" / "nipple"],

read tags on those bindings,

return a simple string label so policies don’t need to know anything about the BodyMap’s internal structure.

The runner also prints a small BodyMap summary on each environment step:

[body] posture='fallen' mom_distance='far' nipple_state='hidden'

This line comes directly from body_posture, body_mom_distance, body_nipple_state and is a quick check that BodyMap is tracking the environment.

## How policies use BodyMap

BodyMap is the preferred source of body state for gating policies:

StandUp gate (BodyMap-first):

bp = body_posture(ctx)
if bp is not None:
    fallen   = (bp == "fallen")
    standing = (bp == "standing")
else:
    fallen   = has_pred_near_now(world, "posture:fallen")
    standing = has_pred_near_now(world, "posture:standing")

stand_intent = has_pred_near_now(world, "stand")
trigger = fallen or (stand_intent and not standing)

So when BodyMap posture flips from "fallen" to "standing", the StandUp gate naturally stops firing (except for the separate safety override, which will be updated in a future phase to also consult BodyMap).

SeekNipple gate (BodyMap posture + nipple state):

hunger = drives.hunger
bp = body_posture(ctx)
ns = body_nipple_state(ctx)

 **roughly:**
trigger = (
    hunger > HUNGER_HIGH
    and bp == "standing"
    and ns != "latched"
    and not has_pred_near_now(world, "seeking_mom")
)

Once BodyMap’s nipple slot reaches "latched" and milk:drinking is present, body_nipple_state(ctx) == "latched" and SeekNipple stops firing — a simple but realistic “don’t keep seeking when you’re already latched and drinking” rule.

This pattern will extend naturally to future BodyMap fields (e.g., a “balance” or “contact” slot, or limb-specific posture) without forcing policies to change their call sites.



## Role of BodyMap vs main WorldGraph

WorldGraph: big, episode-level map over what happened (states, actions, cues, transitions). It accumulates all the posture:fallen and posture:standing bindings over time and is used for planning and discrepancy diagnostics.

BodyMap: tiny, always-on body-centered map for what is true of my body right now (plus very small near-world: mom, nipple). It is updated from the latest EnvObservation, independent of how messy the episode graph has become.

You can think of it as:

WorldGraph = “story of my life”
BodyMap = “how my body is configured right now (and where mom/nipple are relative to me)”

Later phases will expand BodyMap and add a PeripersonalMap, but this v1 gives us a proper place for sensor-fused body state while keeping the main WorldGraph small and semantic.



### Q&A – BodyMap (Body + Near-World)

Q: Why use a separate WorldGraph for BodyMap instead of just tags in Ctx?

A: Two reasons: (1) Conceptual honesty — BodyMap really is a tiny map, not just a flat struct, and we want that structure available when we’re ready to grow it (e.g., split posture into limbs, add contact nodes). (2) Uniform tools — by using WorldGraph again, we can reuse invariants, snapshot logic, and future graph tools (FOA, queries) without inventing a new mini-DSL.

Q: Do BodyMap binding ids collide with the main WorldGraph ids?

A: No. Each WorldGraph instance has its own bN counter. b3 in BodyMap is not the same as b3 in the main world. Snapshot clearly separates them: BODYMAP shows ctx.body_world, the BINDINGS/EDGES sections show the main world.

Q: What is the relationship between BodyMap and EnvObservation?

A: BodyMap is updated directly from EnvObservation.predicates via update_body_world_from_obs(ctx, env_obs). So at each env step, BodyMap mirrors the latest sensed posture/mom/nipple state. It is a per-step state estimate, not a long-term history; history lives in the main WorldGraph.

Q: Which policies read BodyMap today?

A: The StandUp and SeekNipple gates (via body_posture(ctx) and body_nipple_state(ctx)) prefer BodyMap when it’s available and only fall back to scanning the main WorldGraph when BodyMap is missing. This makes basic posture and latch decisions depend on the body schema, which is closer to how real animals (and robots with a state estimator) behave.

Q: Does BodyMap affect planning or just gating?

A: Today it affects policy gating and diagnostics, not planning: BFS/Dijkstra still operate over the main WorldGraph. In the future, we may add small queries over BodyMap (e.g., “which body parts are in contact?”) and integrate that into path selection or spatial reasoning, but the fast episode planner remains graph over the main world.



## BodyMap slots for shelter and cliff (safety-aware near-space)

In addition to posture, mom-distance, and nipple state, BodyMap at this time of writing tracks two
extra near-world slots that matter for survival:

- **shelter** – distance to a safe resting niche
  (`pred:proximity:shelter:far` / `pred:proximity:shelter:near`).

- **cliff** – proximity of a dangerous drop
  (`pred:hazard:cliff:far` / `pred:hazard:cliff:near`).

**The BodyMap graph is extended accordingly:**

BODY_ROOT --body_state-->     POSTURE
BODY_ROOT --body_relation-->  MOM
BODY_ROOT --body_relation-->  SHELTER
BODY_ROOT --body_danger-->    CLIFF
MOM       --body_part-->      NIPPLE

These slots are kept deliberately simple at the newborn stage:

shelter_distance is “far” early in the story and becomes “near”
when the kid has moved into a sheltered resting position near mom.

cliff_distance is “near” during early struggle/first-stand (exposed
terrain) and “far” once the kid is in a safer sheltered niche.

The Environment module (EnvState + FsmBackend + PerceptionAdapter) drives
these slots:

EnvState.shelter_distance / cliff_distance are updated as part of
the newborn storyboard (birth → struggle → first_stand → first_latch → rest).

PerceptionAdapter.observe(...) emits proximity:shelter:* and
hazard:cliff:* predicates.

update_body_world_from_obs(ctx, env_obs) mirrors those predicates into the
BodyMap shelter and cliff nodes (just like posture/mom/nipple).

Controller helpers make these easy to read:

body_shelter_distance(ctx) -> "near" | "far" | None

body_cliff_distance(ctx) -> "near" | "far" | None

**These helpers are used in gates and policies when deciding whether it is safe**
**to rest or which actions are appropriate in the current geometry.**

---------

### Terminology Explanation: Environment Geometry

When this README talks about the **geometry** of the environment, it is not referring to school-style angles and triangles. Instead, “environment geometry” means the **spatial configuration of the scene**: where, for example, the kid, mom, shelter, and cliff are, and how they are related (near, far, under shelter, near a drop, etc.).

In CCA8 there are three closely related layers that together define this geometry:

1. **EnvState (God’s-eye world)**  
   The Environment module keeps a canonical `EnvState` with fields such as `kid_posture`, `mom_distance`, `nipple_state`, `kid_position`, `mom_position`, and high-level `scenario_stage` (birth → struggle → first_stand → first_latch → rest). This is the environment’s own notion of “where everything is and what is happening right now.” :contentReference[oaicite:0]{index=0}  

2. **BodyMap (body-centred near space)**  
   BodyMap is a tiny, separate WorldGraph that tracks the **geometry as experienced by the body**: posture (fallen/standing/resting), mom’s proximity (far/near/touching), nipple state (hidden/found/latched/milk:drinking), and safety-relevant slots for shelter and cliff (shelter near/far, cliff near/far). From BodyMap you can ask, “Is it safe to lie down here?” or “Is mom close enough to seek the nipple?” without scanning the full episode history.  

3. **WorldGraph spatial overlay (episode-level geometry)**  
   The main WorldGraph stores **episodic traces** of geometry using predicates and a small scene-graph overlay. For example, when the kid is resting safely, the runner writes edges like  
   `NOW --near--> b_mom_close` and `NOW --near--> b_shelter_near`,  
   where the target bindings carry tags such as `pred:proximity:mom:close` and `pred:proximity:shelter:near`. These edges say, “in this episode moment, SELF (NOW) is near mom and near shelter,” and can be inspected later via the snapshot, Pyvis export, or the spatial scene demo menu.

---------

Hazard-aware Rest: “don’t lie down at the cliff edge”

Resting is now BodyMap-aware in a simple but important way:

When fatigue is high, policy:rest may be considered by the Action Center.

Before it actually changes anything, Rest.execute(...) consults BodyMap:

cliff   = body_cliff_distance(ctx)
shelter = body_shelter_distance(ctx)
if cliff == "near" and shelter != "near":
    return self._fail("unsafe to rest (cliff near, shelter not near)")

In that case, Rest fails fast:

no change to drives (fatigue is not reduced),

no pred:resting binding is written.

Only when BodyMap says the geometry is safe:

shelter_distance == "near" and

cliff_distance == "far"

does Rest.execute(...) succeed, reduce fatigue, and assert a resting state.

This matches the ethological intuition:

The kid may attempt to rest near a drop, but the architecture refuses
to actually lie down until it is in a sheltered, safer position.

Spatial overlay on the WorldGraph: NOW-near edges

BodyMap is the live, body-centred map. The main WorldGraph now carries a
tiny scene-graph overlay derived from BodyMap and the environment:

At resting times, the runner inspects the current EnvObservation:

if it contains resting,

plus proximity:mom:close and/or proximity:shelter:near,

it writes small spatial edges out of the NOW anchor:

NOW --near--> b_mom_close
NOW --near--> b_shelter_near

The destination bindings already carry their own tags:

pred:proximity:mom:close

pred:proximity:shelter:near

and any other metadata (e.g., temporal context, provenance).

**The result is a very small spatial layer in the main episode graph:**

The edge label vocabulary is kept minimal: near only (with inside and
supports stubbed in code for future use).

Nodes still carry all semantics via their tags; the near edges just say
“SELF (NOW) is currently near this mom-near / shelter-near node.”

**In snapshot output, you will see entries like:**

b1 --near--> b183
b183: [pred:proximity:mom:close]

b1 --near--> b184
b184: [pred:proximity:shelter:near]

interpreted as:

“At this resting moment, NOW (SELF) is near mom and near shelter.”

Spatial queries and menu demos

To make this spatial structure easy to inspect, the runner provides a couple
of small query helpers and a menu demo.

Helpers (in cca8_run.py):

neighbors_near_self(world) -> list[str]

Returns all binding ids reachable via NOW --near--> *. Useful when you
want to know “what is SELF currently near?” without scrolling the whole
edge list.

resting_scenes_in_shelter(world) -> dict[str, Any]

Returns a summary dict like:

{
    "rest_near_now": True/False,              # is any 'resting' near NOW?
    "shelter_near_now": True/False,           # is NOW near shelter-near bindings?
    "shelter_bids": [...],                    # the shelter-near binding ids
    "hazard_cliff_far_near_now": True/False,  # is any 'hazard:cliff:far' near NOW?
}

This is a convenience wrapper for the “resting in shelter, cliff far”
situation.

Menu 39 – Spatial scene demo

The runner adds a small TUI demo:

“Spatial scene demo (NOW-near + resting-in-shelter?)” (menu 39).

It prints:

all NOW-near neighbors, showing their tags:

NOW-near neighbors:
  b183: [pred:proximity:mom:close]
  b184: [pred:proximity:shelter:near]
  ...

a one-line summary of the resting-in-shelter pattern:

Resting-in-shelter scene summary (around NOW):
  rest_near_now:             True
  shelter_near_now:          True
  hazard_cliff_far_near_now: True
  shelter_bids (NOW --near--> ...):
    b184: [pred:proximity:shelter:near]
    ...

**Together with the BODYMAP summary line and the BodyMap Inspect menu, this
gives a compact, readable picture of:**

current posture,

near-space geometry (mom / shelter / cliff),

and where, in the episode graph, REST is happening (or being refused) as a
function of that geometry.





## Valence in the CCA8

### What is valence? Why is it important in advantageous behavior?

In CCA8, **valence** is a simple notion:

> how good or bad a configuration feels to the agent, in a way that can guide
> future approach/avoid decisions.

It is not just a one-off reward at a single time step, but a small, symbolic
marker that says:

- “being in *this kind of situation* tends to be good for me”, or
- “being in *this kind of situation* tends to be bad for me”.

In biological brains, valence is closely tied to:

- **Body state** (hunger relief, warmth, pain).
- **Near-space geometry** (safe shelter vs exposed cliff).
- **Social relations** (comfort near mom vs separation).

CCA8 deliberately mirrors this by letting valence sit **on top of the same
spatial maps** that drive behaviour:

- BodyMap tells the agent how its body is configured and what is nearby
  (posture, mom distance, shelter, cliff).
- The main WorldGraph records episodes with posture / proximity / hazard facts.
- Spatial edges (like `NOW --near--> mom_near` and `NOW --near--> shelter_near`)
  mark which nodes are currently near SELF.

Valence connects directly to these:

- We do **not** treat “like/hate” as a separate channel or a mysterious
  scalar floating around; instead we attach valence to **specific bindings**
  in the WorldGraph (and, later, potentially to BodyMap configurations).
- That way, the system is able to learn regularities like:
  - “When I am near mom and latched I tend to like this configuration.”
  - “When I am resting in shelter with the cliff far away this is usually safe
     and desirable.”

This matters pragmatically because:

- Planning and policy selection can be biased toward **liked regions of the
  world graph** (states and trajectories that were tagged as good), and away
  from strongly disliked regions.
- Spatial queries and the scene-graph overlay can be extended to ask not only
  “what am I near?” but also “what am I near that I historically like?”

The current Phase V implementation stops at **representing** a tiny amount of
valence; using it for learning and policy bias is left to a future, more
explicit RL/learning phase.



### How is valence implemented in the CCA8?

Valence in CCA8 is implemented as a small, explicit predicate vocabulary
plus a couple of helpers and a minimal newborn wiring.

**1. Valence tokens in the lexicon**

The tag lexicon (`TagLexicon.BASE`) defines two canonical valence predicates:

- `valence:like`
- `valence:hate`

These live in the **predicate** family (`pred:valence:like`, `pred:valence:hate`)
and are available starting at the **neonate** stage. That means any stage
(neonate → juvenile → adult) can attach simple “like/hate” markers to its
episodes without fighting the tag policy.

**2. Node-level valence tags**

Valence is represented as an extra tag on **specific bindings** in the
WorldGraph. A typical example after the Phase V work is:

b143: [pred:proximity:mom:close, pred:valence:like]
This says:

“Binding b143 represents a state where mom is close, and the agent tags
this configuration as liked.”

Crucially:

Valence is attached to a relational configuration, not a mysterious
global “mom is always good” or “cliff is always bad”.

The same object (e.g., cliffs) could later be tagged positively in other
contexts (e.g., a safe refuge from predators). The representation does not
hard-code “hate cliff”.

3. Minimal newborn wiring: ‘like mom’

In the current newborn goat scenario, we make one small but concrete choice:

When an EnvObservation simultaneously reports:

nipple:latched, and

proximity:mom:close

The runner identifies the binding created for proximity:mom:close in that
step, and adds:

text
Copy code
pred:valence:like
to its tags.

This is implemented as a tiny helper in the runner:

It uses the token_to_bid map from inject_obs_into_world(...) to find
the mom-near binding for that observation.

It adds pred:valence:like to that binding’s tag set.

Over time, the WorldGraph accumulates a series of bindings like:

text
Copy code
b103: [pred:proximity:mom:close, pred:valence:like]
b113: [pred:proximity:mom:close, pred:valence:like]
b123: [pred:proximity:mom:close, pred:valence:like]
...
These are precisely those moments when the kid was near mom and nursing.
They are then connected to NOW via NOW --near--> * edges at resting times,
so spatial queries like “what is NOW near?” will often list mom-close-liked
bindings in safe resting configurations.

4. Future extensions: valence nodes and strengths (stubs)

The controller also provides a stub helper:

add_valence_binding(world, ctx, polarity, *, target=None, strength=1.0)

which, when used, will create a separate valence binding carrying:

pred:valence:like or pred:valence:hate,

plus meta fields:

python
Copy code
{
    "valence_polarity":  "like" or "hate",
    "valence_target":    "mom" / "cliff" / "shelter" / "research:direction_A" / ...,
    "valence_strength":  float,
    ...
}
The current newborn implementation does not use this helper yet; it is
provided as a structured way to represent more abstract or longer-lasting
valence in future phases (e.g., research strategies, complex environments),
without scattering ad-hoc meta fields through the code.

5. Where valence will plug in later

In the present Phase V work, valence is entirely representational:

No gate or planner reads pred:valence:like or pred:valence:hate yet.

No edge weights or policy scores are adjusted based on valence.

This is intentional: Phase V focuses on getting the wiring and structure
right (BodyMap, spatial overlay, safety logic, valence tags). In a future
learning/RL phase, these valence predicates can be used to:

bias planning toward “liked” trajectories in the WorldGraph,

modulate policy selection (e.g., prefer actions that preserve mom-close-liked
configurations),

and serve as a structured target for RL-style value functions that are
grounded in the same spatial/episodic maps the rest of CCA8 uses.

**In summary:**

Valence in CCA8 is a small, explicit symbolic layer sitting on top of the
same spatial and episodic machinery as posture, shelter, and cliffs. Today
it records “like mom when close and feeding”; tomorrow it can help the
agent decide where to go and what to do.





### Q&A – BodyMap Safety, Spatial Overlay, and Scene Graph

**Q: Why put shelter and cliff into BodyMap instead of a separate PeripersonalMap?**  

**A: BodyMap already mixes body and very-near world (posture, mom distance, nipple state).**

 Adding `shelter` and `cliff` slots simply makes that explicit: BodyMap is a **body-centred near-space map**. If we created a separate PeripersonalMap, we would have to keep two sources of truth for “is shelter near me?” and “is cliff near me?”, which is error-prone. With the current design:

- BodyMap owns posture + mom + nipple + shelter + cliff.
- Policies ask **one authority** (`body_*` helpers) for this information.
- The main WorldGraph stores **episodes over time**, not a second near-space map.

This keeps the architecture simple: **WorldGraph = story over time; BodyMap = body + immediate near world.**

---

**Q: What exactly happens when Rest is blocked near a cliff?**  

**A:*When fatigue is high, the controller may select `policy:rest` based on drives. However, `Rest.execute(...)` now checks BodyMap:**

cliff   = body_cliff_distance(ctx)
shelter = body_shelter_distance(ctx)
if cliff == "near" and shelter != "near":
    return self._fail("unsafe to rest (cliff near, shelter not near)")

In this situation:

Rest returns fail (status "fail", reward 0.0).

Fatigue is not reduced.

No pred:resting predicate is written.

So the goat may “try” to rest, but the architecture refuses to actually lie down at the edge. Once BodyMap says shelter=near and cliff=far, Rest is allowed to succeed and assert a resting state.

**Q: How do the NOW-near edges relate to BodyMap? Aren’t they redundant?**

**A: BodyMap is a live register (one posture/mom/shelter/cliff configuration at a time).**

The NOW --near--> * edges are a thin episodic overlay written into the main WorldGraph at important moments (currently at resting times):

BodyMap says: “right now, mom is near, shelter is near, cliff is far.”

The runner writes: NOW --near--> b_mom_close and NOW --near--> b_shelter_near into the WorldGraph.

Those bindings (b_mom_close, b_shelter_near) already carry their own tags, including provenance and temporal fingerprint.

This lets you later inspect or analyze where resting happened in the episode graph (e.g., “rest near mom and shelter”) without re-running the environment or looking at BodyMap snapshots.

**Q: Do spatial near edges change planning behavior today?**

**A: No. Today, spatial edges are purely descriptive:**

They don’t affect BFS/Dijkstra correctness.

They’re not used as weights or filters yet.

They exist so humans (and future algorithms) can see and query simple scene-graph structure.

In the future, the same near label could be mapped to costs or constraints (e.g., prefer paths through near shelter states, avoid risky near cliff states), but Phase V keeps planning semantics unchanged. The edges are a no-regrets addition: useful for inspection now, available for planning later.

**Q: How do I see what NOW is near in a running simulation?**

**A: Use the Spatial scene demo (menu 39):**

It calls neighbors_near_self(world) and prints all NOW --near--> * neighbors with their tags, e.g.:

NOW-near neighbors:
  b183: [pred:proximity:mom:close, pred:valence:like]
  b184: [pred:proximity:shelter:near]

It also calls resting_scenes_in_shelter(world) and prints:

Resting-in-shelter scene summary (around NOW):
  rest_near_now:             True
  shelter_near_now:          True
  hazard_cliff_far_near_now: True
  shelter_bids (NOW --near--> ...):
    b184: [pred:proximity:shelter:near]

This is the quickest way to answer “what is SELF currently near?” and “are we in a resting-in-shelter, cliff-far scene?” without manually scanning the whole snapshot.

**Q: How does all this relate to planning and learning later on?**

**A: At the time of writing, the implementation's spatial and safety features are designed as structural hooks:**

BodyMap adds shelter/cliff slots so policies can make safety-aware choices (e.g., blocking Rest at the cliff).

The scene-graph overlay (NOW --near--> *) records where key events happened.

Spatial queries (neighbors_near_self, resting_scenes_in_shelter) make it easy to inspect and measure these structures.

In future phases (RL/learning), this same structure can be used to:

Weight or filter planner edges (e.g., prefer “liked” or “safe” near-space configurations).

Build simple value functions over states with spatial + safety context.

Study how often successful paths pass through “resting in shelter, cliff far” configurations versus riskier ones.















# Tutorial on Main (Runner) Module Technical Features

What it is: the interactive & CLI entry point for CCA8.  It is run first and prints the banner, selects a profile, wires a `WorldGraph`, exposes preflight checks, autosave/load, and a full-screen menu to inspect/plan/act. 

Why is this tutorial after the one on WorldGraph, i.e., rather than being the first tutorial to start with?  It is because you really need to know the concepts such as binding, predicate, edge, and so on, and how they are coded and stored in the instance of the WorldGraph, before looking at the overall functioning of the program, which is what this module does.

***Note: Code changes will occur over time, but the main ideas below should remain stable with the project***

## Public surface (importables)

Exports (see `__all__`):  
`main`, `interactive_loop`, `run_preflight_full`, `snapshot_text`, `export_snapshot`, `world_delete_edge`, `boot_prime_stand`, `save_session`, `versions_dict`, `versions_text`, `choose_contextual_base`, `compute_foa`, `candidate_anchors`, `Ctx`, `__version__`.

### Runtime context (`Ctx`)

Dataclass carried between engine and CLI:  
`sigma: float`, `jump: float`, `age_days: float`, `ticks: int`, `profile: str`, `winners_k: Optional[int]`, `hal: Optional[Any]`, `body: str`.

* * *

CLI quick reference
-------------------

    ### About / versions
    python cca8_run.py --about          # list component versions & paths
    python cca8_run.py --version        # runner version only
    
    ### Start interactive (fresh) with autosave
    python cca8_run.py --autosave session.json
    
    ### Resume from a snapshot (and keep autosaving)
    python cca8_run.py --load session.json --autosave session.json
    
    ### One-shot plan (non-interactive)
    python cca8_run.py --load session.json --plan pred:milk:drinking
    
    ### Full preflight (runs pytest + checks) and exit
    python cca8_run.py --preflight
    
    ### Start with a small preloaded demo world (for graph/menu testing)
    python cca8_run.py --demo-world
    
    Flags you’ll actually use: `--about`, `--version`, `--load`, `--autosave`, `--plan`, `--preflight`, `--no-intro`, `--no-boot-prime`, `--profile {goat,chimp,human,super}`, `--hal`, `--body`, `--demo-world`.

Interactive menu: the 10 you’ll press most
------------------------------------------

* **1 World stats** — counts, NOW/LATEST, loaded policies.

* **2 Show last 5** — quickest way to grab fresh ids.

* **3 Add predicate** — auto-attach to `LATEST` (uses `WorldGraph.add_predicate`).

* **4 Connect two** — `(src, dst, relation)` with duplicate edge guard.

* **5 Plan from NOW** — pretty path + raw ids.

* **11 Add sensory cue** — adds `cue:*` and nudges controller once.

* **12 Instinct step** — Action Center --one controller step with pre/post “why” text.

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

* Planner probes, **attach semantics**, **cue normalization**, **action metrics**, **BFS shortest-hop** reasonableness.

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

## Minimal usage crib (copy/paste)

### A) One-shot CLI flow

    # Fresh session with autosave
    python cca8_run.py --autosave session.json
    
    # Add predicates / cues from the menu, then plan:
    # 5 → "posture_standing"   # pretty path prints
    
    # Export an interactive graph
    # 22 → choose label mode 'id+first_pred', edge labels Y, physics Y

### B) Resume + one-shot plan

    python cca8_run.py --load session.json --plan pred:milk:drinking

### C) Preflight before a demo

    python cca8_run.py --preflight

Look for “PASS” lines (pytest, invariants, attach semantics, BFS, engram bridge).



**Troubleshooting quickies**

* **“No path found”** → check exact `pred:<token>`, ensure forward chain from NOW, watch for reversed edges.

* **Duplicate edge warning** → auto-attach plus manual connect; keep one.

* **Two NOW tags** → use `set_now(..., clean_previous=True)` (menu already tidies).

* **Strict lexicon errors** → switch to `warn` while developing or extend `TagLexicon.BASE`.

* * *

**Note: Code changes will occur over time, but the main ideas below should remain stable with the project**



## cca8_run.py — Call Flow & Usage Cheat-Sheet

**What `main()` does (call flow)**
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



**What `interactive_loop(args)` sets up (at start)**
    from cca8_world_graph import WorldGraph
    from cca8_controller import Drives
    world = WorldGraph()            # empty world
    drives = Drives()               # controller drives (hunger/fatigue/warmth)
    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)  # runtime context

    optional: load snapshot if --load path is provided
    menu loop: add predicates/cues, connect edges, plan, export, etc.

Menu highlights you’ll actually use during demos:

* **World stats**, **Show last 5**, **Inspect binding**, **Add predicate**, **Connect two**, **Plan from NOW**, **Add sensory cue**, **Instinct step**, **Export snapshot**, **Pyvis export**, **Planner toggle (BFS↔Dijkstra)**.
  
  

## Public surface (functions you can import)

### Session & world utilities

    from cca8_run import snapshot_text, export_snapshot, save_session, world_delete_edge
    
    1) Human-readable snapshot (same text as menu item)
    print(snapshot_text(world, drives, ctx, policy_rt))
    
    2) Export a compact world snapshot to disk (bindings + edges)
    export_snapshot(world, drives, ctx, policy_rt,
                    path_txt="world_snapshot.txt",
                    _path_dot=None)  # DOT is optional elsewhere
    
    3) Save a full session (JSON): world + drives + skills
    save_session("session.json", world, drives)
    
    4) Robust edge deletion (handles legacy edge keys)
    removed = world_delete_edge(world, src="b3", dst="b4", rel="then")
    print("removed", removed)

### Preflight & versions

    from cca8_run import run_preflight_full, versions_dict, versions_text
    
    One-shot preflight (pytest + invariants + planner/cue/attach probes)
    exit_code = run_preflight_full(args_namespace)
    
    Versions as dict or pretty text
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



## Core classes defined in `cca8_run.py`

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

**Methods:**

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

**Methods:**

* `refresh_loaded(ctx)`

* `list_loaded_names() -> list[str]`

* `consider_and_maybe_fire(world, drives, ctx, tie_break=...) -> dict | 'no_match'`

> The runner’s **Instinct step** menu item uses this mechanism and prints a one-line status.

* * *

**Putting it together (tiny end-to-end snippets)**

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

**What to scan in the code (orientation map)**
------------------------------------------

* **`main()`**: argparse flags, about/preflight branches, calls `interactive_loop(args)`.

* **`interactive_loop()`**: world/drives/ctx construction, optional `--load`, then the **menu loop** (aliases + grouped items).  
  Look for blocks labeled: Add predicate, Add cue, Connect two, Plan, Instinct step, Export snapshot, Pyvis export, Planner toggle.

* **Exports (`__all__`)** you can import:  
  `main`, `interactive_loop`, `run_preflight_full`, `snapshot_text`, `export_snapshot`, `world_delete_edge`, `boot_prime_stand`, `save_session`, `versions_dict`, `versions_text`, `choose_contextual_base`, `compute_foa`, `candidate_anchors`, `__version__`, `Ctx`.
  
  
  
  
  
  

# Tutorial on Controller Module Technical Features

This tutorial explains how the **Controller module** (`cca8_controller.py`) works, how it uses drives, policies, and the Action Center, and how it writes **predicate–action–predicate (S–A–S)** chains into the WorldGraph as the goat “thinks and acts.”

The Controller is where the **“what should I do next?”** logic lives. It sits between:

- the **WorldGraph** (what the agent believes/has experienced),
- the **Drives** (hunger, fatigue, warmth, etc.),
- the **TemporalContext** (soft clock, ticks/epochs),
- and, eventually, the **HAL** (robot or simulated body).

Its job is to:

1. Read the current situation (predicates/cues near `NOW` + drives),
2. Decide which **policy** (primitive behavior) should fire,
3. Execute that policy, which:
   - updates drives,
   - writes new **action** and **predicate** bindings into the WorldGraph,
   - and returns a small result to the Runner / Action Center.

The Controller does *not* try to be a full planner; it provides a small set of hand-written “reflexive” policies (e.g., StandUp, SeekNipple, Rest) that form the core of the newborn’s first repertoire.
**Note: Code changes will occur over time, but the main ideas below should remain stable with the project*** `

---

## 1. Drives and Drive Flags

The controller maintains a small `Drives` object:

python
@dataclass
class Drives:
    hunger:  float = 0.7
    fatigue: float = 0.2
    warmth:  float = 0.6
    def flags(self) -> list[str]:
        ...

The numeric levels (hunger, fatigue, warmth) are the underlying homeostatic state. From these, the controller derives ephemeral flags:

drive:hunger_high

drive:fatigue_high

drive:cold

These drive:* flags are:

controller-only: they are not stored as pred:* in the WorldGraph,

used in trigger(...) logic for policies (e.g., “if drive:hunger_high then consider SeekNipple”),

occasionally mirrored into the graph as cues (cue:drive:hunger_high) when we want the world model to “remember” that a drive was high at a particular moment.

So:

drive:* = internal, ephemeral.

cue:drive:* = optional evidence in the WorldGraph.

pred:drive:* = only if we explicitly want a drive threshold to be a planner goal (rare in the newborn stage).



## 2. Binding Families and S–A–S in the Controller

The Controller writes into the WorldGraph using four families of tags:

* `pred:*` – **predicates** (what is true of the body/world right now), e.g.:
  
  * `pred:posture:fallen`
  
  * `pred:posture:standing`
  
  * `pred:resting`
  
  * `pred:seeking_mom`
  
  * `pred:nipple:latched`, `pred:milk:drinking`

* `action:*` – **action bindings** (what the agent is doing / has just done), e.g.:
  
  * `action:push_up`
  
  * `action:extend_legs`
  
  * `action:orient_to_mom`
  
  * `action:look_around`

* `cue:*` – **sensory or interoceptive cues**, e.g.:
  
  * `cue:vision:silhouette:mom`
  
  * `cue:scent:milk`
  
  * `cue:drive:hunger_high`

* `anchor:*` – **special orientation nodes**, e.g.:
  
  * `anchor:NOW` – current focus of attention / local state,
  
  * `anchor:NOW_ORIGIN` – the binding where NOW started this episode.

Each policy execution writes a short **predicate–action–predicate** chain into the graph:

`[pred:posture:fallen]  --then-->  [action:push_up]  --then-->  [action:extend_legs]  --then-->  [pred:posture:standing]`

We refer to these as **S–A–S segments** (State–Action–State), but in the implementation the “state” is always represented by one or more **predicates** (e.g., `pred:posture:fallen`, `pred:posture:standing`), not a separate `state:*` family.

* * *


## 3. Gating versus Triggering versus Executing

This sub-section gives a mini-tutorial, i.e., an overview, on how policies work in the CCA8 architecture.

You should think of how policies work in terms of three states (which actually map very cleanly to what CCA8 is doing in code):

1. **Gating**

   * “Is this policy even allowed in the candidate set right now?”
   * Includes:

     * `dev_gate(ctx)` (e.g., neonatal-only policies)
     * safety overrides (e.g., “if fallen, only allow StandUp/RecoverFall”)
   * Everything that fails here is **out** before we even look at drives or world.

2. **Triggering**

   * For the policies that passed gating:
     “Given world + drives + BodyMap, does this policy *want* to fire now?”
   * Implemented by each policy’s `trigger(world, drives, ctx)`.
   * If `trigger(...)` is `True` → the policy is **triggered** and joins the **candidate list** for this tick.

3. **Executing**

   * Among all **triggered** policies, pick one to actually run.
   * This is where we define “best”:

     * drive deficit scores (hunger vs fatigue, etc.),
     * maybe a preferred action,
     * tie-breaking / ordering.
   * The winner gets:

     * logged as `[executed] policy:...`,
     * its primitive run in the Action Center,
     * its name fed into `env.step(action=...)` next tick.

So in short:

 **Allowed → Triggered → Executed**
 (gating → triggering → winner)



***Q&A to help you learn this section***

Q: What is a “policy” in CCA8?
A: A policy is a named behaviour like policy:stand_up, policy:seek_nipple, policy:follow_mom, or policy:rest. Each policy has:

a gate (dev + safety),

a trigger function,

and a primitive that actually runs when the policy is selected to execute.

Q: What does “gating” really do?
A: Gating answers: “Is this policy even allowed to be considered right now?”
Examples:

dev_gate(ctx) filters out policies that don’t apply to the current profile (e.g., neonatal-only).

The safety override may say “if BodyMap says fallen, only allow StandUp/RecoverFall.”
If a policy fails gating, its trigger is never even called that tick.

Q: How is “triggering” different from “gating”?
A: Gating is a coarse include/exclude filter. Triggering is a context check for policies that survived the gate:

Gating: “Am I even allowed in the candidate set?”

Triggering: “Given world + drives + BodyMap, do I want to fire now?”

Triggering is implemented by trigger(world, drives, ctx). If this returns True, the policy is marked as triggered and joins the candidate list.

Q: Can a policy pass gating but fail to trigger?
A: Yes. For example, policy:rest might:

Pass gating (dev + safety say it is allowed), but

Fail trigger if fatigue is below FATIGUE_HIGH or zone is unsafe.

In that case, Rest is “allowed in principle” but does not join the triggered candidate set for that tick.

Q: Can multiple policies trigger in the same tick?
A: Yes. For example, both SeekNipple and Rest can be triggered if hunger and fatigue are both high and zone is safe. In that case, they both enter the candidate list and the execution stage must pick a winner.

Q: How do we choose which triggered policy actually executes?
A: Execution is handled by the Action Center / PolicyRuntime:

It takes the triggered policies,

Computes some notion of “best” (e.g., drive deficit scores, preferred action, ordering),

Chooses a single winner for this tick.

That winner:

is logged as [executed] policy:...,

runs its primitive,

and its name becomes the action string for env.step(...) in the next environment tick.

Q: Where does the safety override fit into this picture?
A: Safety is implemented as an extra gating layer:

First, we collect policies that pass dev_gate(ctx) and trigger True.

Then, if _fallen_near_now(...) says “fallen”, we filter that list down to a small safety set (e.g., {StandUp, RecoverFall}).

Only after that do we pick the “best” policy to execute.

So safety never directly executes a policy; it restricts which policies are even allowed to compete.

Q: How does this relate to what I see in the env-loop logs?
A: Roughly:

[gate:rest] ... lines show triggering and gating conditions (fatigue, zone, BodyMap freshness, etc.).

[env→controller] policy:... shows what the gate catalog and safety layer proposed for this tick.

[executed] policy:... (in the controller logs) shows which policy actually executed.

env.step(action='policy:...') uses that executed policy name to advance the storyboard and world geometry on the next environment tick.

In other words, the logs are just different windows onto the three phases you summarized as:

Allowed → Triggered → Executed
(gating → triggering → winner)


* * *

## 4. Policies and the Action Center

Each primitive behavior is represented by a small **policy class** in `cca8_controller.py`:

* `StandUp` – stand if fallen and not overly fatigued.

* `SeekNipple` – orient toward mom and start seeking the nipple when upright and hungry.

* `Rest` – reduce fatigue when very tired.

* (plus a few others like `ExploreCheck` or recovery policies).

Each policy has two key methods:

* `trigger(world, drives)` → `bool`  
  Decide whether the policy _wants_ to fire given the current world predicates/cues and drives.

* `execute(world, ctx, drives)` → `{ "policy": ..., "status": ..., "reward": ..., "binding": ... }`  
  Actually perform the action: update drives, write bindings/edges, and return a small summary to the Action Center.

The **Action Center** (inside `cca8_controller.action_center_step`) orchestrates one “controller step”:

1. For each policy `P`:
   
   * Check `P.trigger(world, drives)`.
   
   * If true, compute a **score** using a small “deficit” function based on drives (e.g. hunger, fatigue).

2. Pick the policy with the best score.

3. Call `P.execute(world, ctx, drives)`.

4. Return a small payload (so the Runner can log what happened and move `NOW` to the last predicate written).

This keeps the controller logic simple and explainable: a handful of hand-authored primitives plus a light “who should go next?” scheduler.

* * *

## 5. Example: StandUp (fallen → standing)

**Goal:** If the newborn goat is fallen and not too fatigued, stand it up.

**Trigger:** roughly:

* `posture:fallen` is near `NOW`, and

* fatigue is below a threshold.

In code, this is checked by a combination of:

* a **safety override** in the runner (`action_center_step`) that fires StandUp when `posture:fallen` is near NOW, and

* a `StandUp.trigger(world, drives)` check that ensures we aren’t already standing.

**Execution:** `StandUp.execute(world, ctx, drives)` writes:

`# (simplified) _add_action(world, ACTION_PUSH_UP,     attach="now",    meta=meta)    # action:push_up _add_action(world, ACTION_EXTEND_LEGS, attach="latest", meta=meta)    # action:extend_legs c = _add_pred(world, STATE_POSTURE_STANDING, attach="latest", meta=meta)  # pred:posture:standing`

Structurally, after one StandUp execution, the graph looks like:

`b1: [anchor:NOW_ORIGIN]b2: [pred:posture:fallen]b3: [action:push_up]b4: [action:extend_legs]b5: [anchor:NOW, pred:posture:standing]`

Edges:

`b1 --then--> b2b1 --then--> b3b3 --then--> b4b4 --then--> b5`

So the S–A–S segment is:

`[pred:posture:fallen]  (near NOW_ORIGIN)    → [action:push_up] → [action:extend_legs] → [pred:posture:standing]  (NOW)`

After execution:

* `ctx.controller_steps` is incremented,

* NOW is moved to `b5` (the new standing state),

* Drives are slightly adjusted (e.g., small fatigue cost, small reward credit).

* * *

## 6. Example: SeekNipple (standing & hungry → seeking mom)

**Goal:** When upright and hungry, start seeking mom’s nipple.

**Trigger:** roughly:

* `posture:standing` near NOW,

* hunger is above a threshold,

* **not** already seeking (`seeking_mom` not near NOW),

* **not** fallen (safety override).

**Execution:** `SeekNipple.execute(world, ctx, drives)` writes:

`meta = _policy_meta(ctx, self.name)_add_action(world, ACTION_ORIENT_TO_MOM, attach="now",    meta=meta)       # action:orient_to_mom b = _add_pred(world, STATE_SEEKING_MOM,  attach="latest", meta=meta)       # pred:seeking_mom return self._success(reward=0.5, notes="seeking mom", binding=b)`

Structurally, after a StandUp followed by SeekNipple, you might see:

`b1: [anchor:NOW_ORIGIN]b2: [pred:posture:fallen]b3: [action:push_up]b4: [action:extend_legs]b5: [pred:posture:standing]b6: [cue:drive:hunger_high]b7: [action:orient_to_mom]b8: [anchor:NOW, pred:seeking_mom]`

Edges:

`b1 --then--> b2, b3b3 --then--> b4b4 --then--> b5b5 --then--> b6, b7b7 --then--> b8`

Typed path from `NOW_ORIGIN` to `seeking_mom`:

`[anchor:NOW_ORIGIN] -> [action:push_up] -> [action:extend_legs]                     -> [posture:standing] -> [action:orient_to_mom] -> [seeking_mom]`

Reverse typed path:

`[seeking_mom] -> [action:orient_to_mom] -> [posture:standing]               -> [action:extend_legs] -> [action:push_up] -> [anchor:NOW_ORIGIN]`

Again, that’s a sequence of **predicate–action–predicate** segments.

* * *

## 7. Example: Rest (fatigued → resting)

**Goal:** When the goat is very fatigued, let it rest and reduce fatigue.

**Trigger:** roughly:

* `drive:fatigue_high` flag is present (derived from `drives.fatigue`),

* and no more urgent safety override is active.

**Execution:** `Rest.execute(world, ctx, drives)`:

* Decreases `drives.fatigue` by a fixed amount (e.g. −0.2, clamped at 0),

* Writes a `pred:resting` binding attached near NOW (or latest) to capture that the goat entered a resting state.

The S–A–S shape is simpler here:

`[pred:posture:standing]  →  [pred:resting]`

(Future versions can insert explicit `action:*` nodes for lying down; for now we keep the newborn rest primitive very simple.)

* * *

## 8. Interplay with NOW, NOW_ORIGIN, and LATEST

The controller and runner cooperate to keep the anchors meaningful:

* `NOW_ORIGIN` is set once per episode (birth / start of scenario). It never moves.

* `NOW` is moved by the Action Center after each successful policy execution to follow the **latest stable predicate** (e.g., `posture:standing`, `seeking_mom`, `resting`).

* `LATEST` (internal) is just the most recently created binding id, regardless of type.

This leads to a natural interpretation:

* Local planning: **from NOW** (“what do I do next?”),

* Global episode summaries: **from NOW_ORIGIN** (“what was the whole story from birth to here?”),

* Reverse reasoning: the **reverse typed path** from a predicate back to NOW_ORIGIN shows one of the many ways the agent arrived at its current state.

* * *

## 9. Q&A to help consolidate

**Q: Where are actions stored — in edges or nodes?**  
A: In **nodes**. Each action is a binding tagged `action:*` (e.g., `action:push_up`) with `then` edges linking it to predicates. Edge labels are mostly human-facing aliases (often just `"then"`).

**Q: What happened to `state:*` and `pred:action:*`?**  
A: We no longer use those as first-class families. Conceptual “states” are represented by `pred:*` bindings (e.g., `pred:posture:standing`, `pred:resting`, `pred:seeking_mom`), and actions by `action:*` bindings. Older snapshots may still contain `pred:action:*` or `pred:state:*` tags, but new code does not write them.

**Q: How does StandUp avoid firing repeatedly?**  
A: Its trigger (and the safety override in the runner) check for `pred:posture:standing` near NOW and skip if already standing.

**Q: How does SeekNipple avoid firing when the kid is already seeking?**  
A: The gate includes `not has_pred_near_now("seeking_mom")`, so once a `seeking_mom` predicate is near NOW, the policy will not re-trigger.

**Q: How does this tie into planning?**  
A: The planner is a BFS/Dijkstra over the WorldGraph. Given a start binding (NOW or NOW_ORIGIN) and a target predicate token (e.g., `posture:standing`, `milk:drinking`), it finds a path of bindings `[b_start, …, b_goal]`. The Runner then prints both a **typed path** and a **reverse typed path**, so you can see the S–A–S structure.

**More Q&A:**

Q: Are drive:* flags stored in the WorldGraph by default?
A: No. drive:* flags (e.g. drive:hunger_high, drive:fatigue_high, drive:cold) are ephemeral controller signals computed from numeric drives (hunger, fatigue, warmth) each tick. They live in the Drives object and are used by policy triggers and deficit scoring; they are not written as pred:* unless you explicitly create pred:drive:* or cue:drive:*.

Q: When do drive flags become visible as WorldGraph tags?
A: Only in two cases: (1) the autonomic path deliberately emits interoceptive cues (e.g. cue:drive:hunger_high on a rising edge via _emit_interoceptive_cues), or (2) you explicitly choose to represent a plannable drive condition as pred:drive:*. By default, drive flags stay out of the graph.

Q: Why distinguish drive:* from pred:drive:* and cue:drive:*?
A: drive:* flags are internal controller facts (“how hungry/fatigued/cold I am”) used by triggers. pred:drive:* would be a persisted fact you might plan toward, and cue:drive:* is evidence (“I just sensed cold skin”). Keeping these separate avoids cluttering the graph while still allowing you to model drive states explicitly when needed.

Q: How do policies actually see the drive state?
A: Policies call drives.flags() (or the runner helper _drive_tags(drives)) to get a list of drive:* flags. They then test for the presence/absence of these flags in trigger(...) and possibly in deficit scoring, without touching the WorldGraph.

Q: If I want the agent to plan around hunger, what should I do?
A: Decide whether you want hunger to be a goal or just evidence. Use pred:drive:hunger_high if you want planners to explicitly seek alleviation conditions; use cue:drive:hunger_high if it should only modulate which policies fire (e.g., SeekNipple) without becoming a planner target.






# Tutorial on Reinforcement Learning in the CCA8



The CCA8 is designed so that learning can be introduced **incrementally** without rewriting the core architecture. The first learning target is **policy selection** (which primitive to execute under which conditions), rather than “learning the maps” (WorldGraph / BodyMap) themselves. This matches both the current code structure and a plausible evolutionary sequence: first learn *which actions work in which contexts*, then later refine richer navigation/map circuits.

CCA8 begins with **transparent, inspectable reinforcement learning** rather than opaque gradient-heavy training loops. That does not mean CCA8 will never use gradient descent (e.g., for perception modules or external neural components); it means that, for the core newborn-goat controller, we start with RL mechanisms that are easy to audit in logs, tests, and snapshots.

The RL integration points are intentionally small and clean:

### 1) MdpBackend: reward and termination as a separate concern

Reward and episode termination are handled by an **MdpBackend** whose job is to **evaluate** transitions, not to change world state. It reads `(prev_state, action, curr_state)` and returns `(reward, done, mdp_info)`. This keeps the task definition (what counts as “good” or “complete”) separate from the environment dynamics (how the world evolves).

### 2) HybridEnvironment: a stable RL-style seam

`HybridEnvironment` is the environment-side orchestrator and the stable boundary between “world” and “brain.” It exposes a Gym-like interface:

- `reset(...) -> (EnvObservation, info)`
- `step(action, ctx) -> (EnvObservation, reward, done, info)`

In early development, the environment dynamics are primarily scripted (FSM/storyboard), but the interface already supports reward/done so RL experiments can be layered in without disturbing WorldGraph, BodyMap, or the Action Center API.

### 3) Skill ledger: learning over policies first

CCA8 already maintains a lightweight per-policy telemetry structure (the **skill ledger**) that tracks how often each policy runs and how well it tends to do. When reward is enabled via `MdpBackend`, each executed policy can update its `SkillStat` (e.g., running value estimate `q`, success counts, last reward).

This yields a simple, biologically natural learning loop:

1. World + drives + BodyMap gate/trigger a small set of candidate policies.
2. The Action Center selects and executes one policy.
3. The environment evaluates the transition and emits `reward` / `done`.
4. The skill ledger updates the statistics for the executed policy.
5. Over time, these learned estimates can be used (initially as a **tie-breaker**) to prefer policies that historically produce better outcomes in similar contexts.

The key design principle is that learning should **not** bypass safety gates or replace the controller’s interpretability. Early RL in CCA8 is meant to be a small, auditable improvement to “which policy wins,” while the underlying maps remain readable and stable.


## Policy choice with and without RL (rl_enabled / rl_epsilon)

CCA8 policies operate in three conceptual stages:

1) gating  
A fast filter: dev gates (e.g., neonatal-only) and safety overrides (e.g., if the body is fallen, restrict to recovery/stand policies).

2) triggering  
For policies that pass gating: each policy’s `trigger(world, drives, ctx)` decides whether it is active this tick.

3) executing  
If multiple policies triggered, choose one “best” policy to execute.

Reinforcement learning (RL) in CCA8 currently modifies only the executing stage. Gating, triggering, and safety logic remain unchanged.

**(At the time of this writing. This will change with development.)**



### No RL (rl_enabled = False)

If multiple policies are triggered, CCA8 selects the winner by:

1) highest drive-urgency “deficit” score (amount above threshold; max(0, drive - HIGH_THRESHOLD))
2) if tied, highest non_drive_priority (Phase VI-D: explicit posture/safety tie-breaks)
3) if still tied, stable policy order (deterministic)


The skill ledger is still updated for telemetry, but it does not affect selection.


### RL enabled (rl_enabled = True)

RL introduces epsilon-greedy exploration when multiple policies are triggered:

- Let epsilon be the exploration rate:
  - epsilon = `rl_epsilon` if set
  - otherwise epsilon falls back to `ctx.jump`

Selection rule:

- With probability epsilon: choose a random triggered policy (exploration).
- With probability (1 - epsilon): exploit:
  1) compute deficit scores and define a near-best band using rl_delta:
         (best_deficit - deficit(policy)) <= rl_delta
  2) within the near-best band, prefer higher non_drive_priority
  3) if still tied, prefer higher SkillStat.q (EMA of observed rewards)
  4) if still tied, prefer slightly higher deficit
  5) if still tied, stable policy order

`SkillStat.q` is a learned value estimate for each policy: an exponential moving average of observed rewards for that policy. It is not the success rate (success rate is tracked for inspection, but q is the value estimate).


### Why CCA8 starts RL here

CCA8 introduces learning in the smallest, most inspectable place: choosing among already-triggered policies. This is a conservative design:

- It is biologically plausible as an “early” learning mechanism (reward-modulated action selection).
- It keeps safety interpretable: RL never bypasses safety gating.
- It is easy to debug: the learned values (n/succ/q/last) are visible in snapshot output and can be correlated with behavior.


### Soft tie-break learning: rl_delta (when q is allowed to matter)

When RL is enabled, CCA8 still uses drive deficit as the primary notion of urgency, but it adds a conservative mechanism that lets the learned value estimate `SkillStat.q` influence choices in *ambiguous* situations.

Definitions (executing stage only; gating/triggering/safety are unchanged):

- Each triggered policy receives a `deficit(policy)` score (domain heuristic; hunger/fatigue urgency).
- Let `best_deficit = max(deficit(policy))` over the triggered set.
- Define a “near-best band” using `rl_delta`:

  Any policy with `(best_deficit - deficit(policy)) <= rl_delta` is considered near-best.

Selection logic in exploit mode (i.e., not exploring):

- If the near-best band has exactly one candidate → choose it (deficit clearly dominates).

- If the near-best band has multiple candidates → choose among that band by:
  1) highest non_drive_priority
  2) if tied, highest SkillStat.q (learned value; EMA reward)
  3) if tied, slightly higher deficit
  4) if still tied, stable policy order


rl_delta effect (important):

- `rl_delta = 0.0`  
  `q` is only used when deficits are exactly tied (most conservative behavior).

- `rl_delta` small (e.g., 0.02)  
  `q` is used only in “near ties” (learning nudges choices only when urgency is very close).

- `rl_delta` large  
  Many policies fall into the near-best band, so `q` can influence most choices among triggered policies (approaches “q-driven” within the candidate set, while still respecting gating/triggering/safety).

This is a conservative compromise between:
- “q only breaks exact ties” (too inert when scores are real-valued/noisy), and
- “blend q into every score” (can amplify noisy/mis-specified rewards).



### Interactive controls for RL (runner menu 41)

The Runner provides an interactive control panel:

- `rl_enabled`  
  Turns the RL logic on/off. When off, selection uses deficit + stable order only. :contentReference[oaicite:1]{index=1}

- `rl_epsilon` (exploration rate, 0..1)  
  When RL is enabled and multiple policies are triggered:
  - with probability epsilon → choose a random triggered policy (exploration),
  - otherwise → exploit using deficit and (when applicable) the q-based soft tie-break. :contentReference[oaicite:2]{index=2}

  If `rl_epsilon` is `None`, epsilon falls back to `ctx.jump` (so you can reuse the existing “jump” knob as a quick exploration control).

- `rl_delta` (soft tie-break band, >=0)  
  Controls how often learned value `q` is consulted during exploitation:
  - 0.0 = q only on exact ties
  - larger = q used more often (near ties)

Menu 41 prints the current values, allows toggling RL, and prompts for new epsilon and delta values. :contentReference[oaicite:3]{index=3}



### Skill ledger and the Skills HUD (how to read learning)

CCA8 maintains a tiny per-policy skill ledger and prints a compact Skills HUD after closed-loop environment runs.

Per-policy fields:

- `n`  
  Number of times the policy executed.

- `succ` and `rate = succ / n`  
  Success bookkeeping. (At this stage many policies count as “ok” most of the time; this becomes more informative as explicit failures are modeled.)

- `last`  
  The reward value received the last time the policy executed.

- `q` (learned value estimate)  
  Exponential moving average (EMA) of observed rewards for this policy:

  `q_new = (1 - alpha) * q_old + alpha * reward`

  where alpha is a smoothing factor (currently ~0.3). `q` is not the success rate; it is the running value estimate used for RL tie-breaking within the near-best band.

The Skills HUD also reports RL settings and the observed explore/exploit counts for the current run (these counts increment only when RL selection is actually active).



### Seeing when q influenced a choice in the env-loop trace (menu 37)

During menu 37 (closed-loop environment run), the trace may include a line like:

`[rl-pick] chosen via q-soft-tiebreak: ...`

This line is printed only when:
- RL is enabled,
- the system is exploiting (not in the epsilon-random exploration branch),
- and the near-best band contains more than one candidate (meaning q was consulted to decide the winner).

Note: safety gating still has priority. For example, in a “fallen” situation, the safety layer can still force StandUp/RecoverFall regardless of q; the `[rl-pick]` line indicates how the gate runtime ranked candidates, not a bypass of safety logic.










# Tutorial on Temporal Module Technical Features

This tutorial explains how **`cca8_temporal.py`** gives CCA8 a lightweight notion of time that complements wall-clock timestamps. It covers the **why**, the **math**, and the **wiring** added to the runner and controller.

## 1) Why a temporal vector if we already have timestamps?

Wall-clock (ISO-8601) stamps are excellent for **provenance** and audit trails, but clumsy for two tasks we care about:

* **Episode segmentation.** “Did a new episode start?” Rule-of-thumb gap detectors (e.g., “>5 s”) are brittle when sim speed varies.

* **Time-aware similarity.** “Fetch things that happened around the same time as X.” Pure timestamps don’t give a smooth, unitless notion of “nearby.”

The Temporal module adds a **unit-norm context vector** that **drifts** a little each tick and **jumps** at boundaries. With unit vectors, **cosine = dot product**, so “near in time” becomes a cheap dot-product check—no units, no parsing, no NumPy.

> Design note: WorldGraph remains **atemporal** (except anchors like `NOW`). Time semantics live in `meta` and in this module/runner, not inside graph mechanics. Policies continue to stamp `created_at` directly.

* * *

## 2) What the TemporalContext is

`TemporalContext` maintains a **D-dimensional unit vector** (default 128-D) representing “now.” Two operations evolve it:

* `step()` – add tiny Gaussian noise (σ = `sigma`) to each component, then **re-normalize** to length 1 (a gentle **drift**).

* `boundary()` – add larger Gaussian noise (σ = `jump`), then re-normalize (a **jump** for episode cuts).  
  Because the vector is always unit-norm, comparing two time points is just a dot product. 1.0 ≈ very close; ~0.0 ≈ far/orthogonal.

**Quick mental model.** Think of time as a path on a high-dimensional unit sphere: smooth motion with occasional bigger hops at important moments. “Meaning” emerges only by **comparison** (dot products), not from individual components.



## 3) Math refresher (why cosine is cheap here)

For vectors u,v:  
cosθ=∥u∥∥v∥u⋅v​. If ∥u∥=∥v∥=1, then cosθ=u⋅v.  
Same direction → 1.0; orthogonal → 0.0; opposite → −1.0. We re-normalize after every drift/jump, so comparisons are just `sum(a*b for a,b in zip(u,v))`.



## 4) How we use it in CCA8 (current wiring)

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

## 5) What the vector “looks like” (and doesn’t)

* It’s a plain Python **list[float]** of length `dim`, re-normalized each change; no NumPy dependency.

* Components are **standard-normal samples** at init, then small/noisy updates—**components have no human meaning** by themselves.

* We **never** read it dimension-by-dimension; we **only compare whole vectors** (cosine/dot).
  
  

## 6) Typical workflows

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



## 7) Parameters that can be tuned

* `dim` (64–128 typical): higher dims → smoother geometry, less variance in dot products.

* `sigma` (drift): how fast “time” moves when nothing big happens.

* `jump` (boundary): how distinct chapters feel (bigger jump → lower cosine after boundary).

* `τ` (threshold): when to auto-cut based on similarity to the last boundary.
  
  

## 8) Minimal API (developer crib)

`from cca8_temporal import TemporalContextt = TemporalContext(dim=128, sigma=0.02, jump=0.25)v0 = t.vector()       # defensive copy (unit-norm) v1 = t.step()         # drift (small change) v2 = t.boundary()     # jump  (larger change)  def dot(a,b): return sum(x*y for x,y in zip(a,b)) print(dot(v0, v1))    # ~0.995–0.999… print(dot(v0, v2))    # noticeably smaller (e.g., 0.7–0.95 depending on jump)`

Under the hood: `_normalize(vals)` returns a unit-norm copy and guards zero-norm with `1.0`.



## 9) Invariants & guardrails

* Always re-normalize after drift/boundary so cosine=dot remains valid.

* TemporalContext **does not** stamp `created_at`; that remains a policy/controller responsibility.

* The soft clock is **run-relative** (not meant for cross-run alignment unless you fix a random seed).

* Pure-Python O(d) per tick; no heavy deps.
  
  

## 10) Quick demo in the Runner (what to expect)

1. `12` Instinct step → if the controller writes, you’ll see  
   `[temporal] boundary after write (cos reset to ~1.000)` and `cos_to_last_boundary: 1.000` in the snapshot.

2. `15` Autonomic tick × N → `cos_to_last_boundary` decays gently (drift only).

3. If you enabled the τ-cut, a boundary triggers automatically once cosine drops below τ (you’ll see a console note).

4. Saved JSON shows `meta.created_at`, `meta.ticks`, and `meta.tvec64` on new bindings.
   
   

### Q&A to help you learn this section

Q: Why do we need a TemporalContext vector if we already have created_at timestamps?
A: ISO-8601 timestamps are great for logs and cross-run audit, but awkward for segmentation and similarity (“find things near this episode in time”). The TemporalContext is a procedural soft clock: a 128-D unit vector that drifts (small Gaussian noise per tick) and jumps (larger noise at boundaries). Cosine between two vectors gives a cheap, unitless “near in time vs far in time” measure without unit conversions or wall-clock parsing.

Q: What do sigma and jump control?
A: sigma controls drift noise added in each step() – how fast the soft clock wanders within an epoch. jump controls boundary noise added in boundary() – how far the vector moves when an event boundary is taken. Larger jump → more separation between episodes; larger sigma → faster within-episode decorrelation.

Q: How does the runner actually use TemporalContext today?
A: The runner:

calls ctx.temporal.step() for each controller/autonomic tick (soft drift),

calls ctx.temporal.boundary() when a controller step writes new facts (event boundary),

caches the boundary vector and its hash in ctx.tvec_last_boundary / ctx.boundary_vhash64,

exposes ctx.tvec64() and ctx.cos_to_last_boundary() so snapshots and engrams can carry time fingerprints.

Q: What do tvec64 and epoch_vhash64 represent?
A: tvec64 is a 64-bit sign-bit hash of the current TemporalContext vector (bit i encodes whether coordinate i is ≥0). epoch_vhash64 (and boundary_vhash64) is the same hash captured at the last boundary. Taken together, they let you:

compare “now” vs last boundary in a compact way,

annotate engrams/snapshots with a short, human-readable temporal fingerprint.

Q: Can TemporalContext be used across different runs as an absolute timeline?
A: No. It’s deliberately a relative, per-run construct. The vector is initialized from random noise and is only meaningful within a single run: high cosine ⇒ close in time in that run. Across runs, you should treat TemporalContext as local, not globally aligned.







# Tutorial on Features Module Technical Features

This section explains what **`cca8_features.py`** provides, why it exists, and how to use it day-to-day. It complements the Signal Bridge (WorldGraph ↔ Engrams) by defining **what an engram payload looks like**, a **concrete dense-tensor payload**, and a **lightweight descriptor** you can search/filter without touching big data.

**Why this design?** The WorldGraph stays an **episode index** (≈5% of data) while columns hold the rich 95%. The bridge preserves traceability without slowing planning.



## 1) What this module is

A small, dependency-free toolkit for **engram payloads**:

* **`FeaturePayload`** — a _Protocol_ (typing interface) describing the **shape** a payload must have (attributes + methods).

* **`TensorPayload`** — a concrete, bytes-serializable dense vector/tensor (float32 body).

* **`FactMeta`** — a compact descriptor for column records (name/links/attrs) with optional **time linkage** to the runner.

This keeps WorldGraph lean (only an **engram pointer** lives on a binding) while Columns store the heavy content.



## 2) Public API (what to import)

    from cca8_features import FeaturePayload, TensorPayload, FactMeta
    # optional helper (if you exposed it): time_attrs_from_ctx

* `FeaturePayload` is an **interface** (Protocol). You don’t instantiate it; any class with the required attributes/methods _conforms_.

* `TensorPayload` and `FactMeta` are concrete dataclasses you use directly.
  
  

## 3) `FeaturePayload` (Protocol) — the interface

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



## 4) `TensorPayload` — a compact dense tensor (float32)

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
  
  

## 5) `FactMeta` — lightweight descriptor (with optional time linkage)

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



## 6) Where it fits in CCA8 (end-to-end picture)

* **WorldGraph** stores _pointers_ to engrams on a binding:  
  `binding.engrams["column01"] = {"id": "<engram_id>", "act": 1.0}`

* **ColumnMemory** stores the **record** `{id, name, payload, meta}` where:
  
  * `payload` is a **FeaturePayload** (e.g., `TensorPayload`),
  
  * `meta` is a **FactMeta** (often with `ticks`/`tvec64` in `attrs`).

* **Signal bridge** (menu **24** “Capture scene”) wraps a small vector into a `TensorPayload`, asserts it as an engram, attaches the pointer to the new binding, and—if you pass `attrs=time_attrs_from_ctx(ctx)`—**mirrors time** into the column record automatically.
  
  

## 7) Minimal usage cribs

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



## 8) Invariants & guardrails (quick checklist)

* `TensorPayload.to_bytes()/from_bytes()`:
  
  * MAGIC/VER must match; shapes parsed from little-endian u32s.
  
  * Body length matches `product(shape) * 4` bytes (float32).

* `FactMeta` is **JSON-safe** (`as_dict()` gives lists/dicts; tuples serialize as lists).

* Time linkage:
  
  * **Graph side**: bindings carry `created_at` (ISO-8601), `ticks`, `tvec64`.
  
  * **Column side**: `FactMeta.attrs` may carry `ticks`/`tvec64` (optional, by your choice).

* Bridge keeps **WorldGraph fast**: engrams stay outside; bindings carry only pointers.
  
  

## 9) Why no NumPy?

This module focuses on **schema + portability**, not numeric ops. `struct` + `array('f')` give a compact, stable on-disk format and fast IO with **zero heavy deps**. If/when you need vector math, you can opt-in elsewhere without changing the engram format.



## 10) Quick test ideas (already partly covered)

* `TensorPayload` round-trip bytes → equal `data/shape`, correct `meta()`.

* `FactMeta.with_time(ctx)` merges `{"ticks","tvec64"}` when available; a missing `ctx` field yields no keys.

* World bridge: `capture_scene(..., attrs=time_attrs_from_ctx(ctx))` → `get_engram(...)[ "meta"]["attrs"]` contains mirrored time.
  
  

## 11) What’s new (Nov 2025)

* Runner’s **Capture scene** (menu **24**) now mirrors temporal context into each engram via `time_attrs_from_ctx(ctx)`: `ticks`, `tvec64`, **`epoch`**, and **`epoch_vhash64`**. This makes engrams time-aware without touching payload bytes.

* Two new runner tools: **27) Inspect engram by id** (also accepts a **binding id** and resolves its pointer) and **28) List all engrams** (id, source binding, time attrs, payload summary).

* Snapshot and probe make event boundaries explicit (`boundary_no`, `last_boundary_vhash64` in CTX; probe shows cosine/Hamming status). (Context; see Runner TEMPORAL section.)

## The bridge (WorldGraph ↔ Column)

1. **Emit**: Runner **24) Capture scene** asks for channel/token/family (cue|pred), attach policy (now/latest/none), and a small vector. It creates a binding and asserts a column engram, then attaches a pointer:

`"engrams": { "column01": { "id": "<engram_id>", "act": 1.0 } }`

The Column record stores `{id, name, payload, meta}`, where `meta.attrs` carries `ticks`, `tvec64`, **epoch**, **epoch_vhash64**.

2. **Attach**: Only the **pointer** (column name → id) sits on the binding; the heavy payload stays in the Column. Planning remains purely over tags/edges.

3. **Inspect**:
* **Display snapshot** shows which bindings have engrams: `engrams=[column01]`.

* **Inspect binding details** prints the full pointer JSON (including the engram id).

* **27) Inspect engram by id** prints the Column record (meta + payload summary). If you type a **binding id** (e.g., `b11`) it resolves its engram automatically.

* **28) List all engrams** enumerates all attached engrams with time attrs.

### Minimal API surface (dev view)

* **Column store** (`cca8_column.py`):  
  `ColumnMemory.assert_fact(name, payload, meta) -> engram_id`  
  `ColumnMemory.get(engram_id) -> dict`  
  (Default singleton `mem = ColumnMemory(name="column01")` used by the bridge.)

* **Runner bridge** (`cca8_run.py`):  
  `world.capture_scene(channel, token, vector, attach, family, attrs=...) -> (bid, engram_id)`  
  plus menu **24**, **27**, **28** wrappers so you don’t have to write code to use it.

### Quick tutorial (CLI)

1. **24) Capture scene** → use `vision / silhouette:mom / cue / now / 0.1 0.2 0.3`  
   Runner prints both the **binding id** and the **engram id**, and echoes the time attrs mirrored into the engram.

2. **3) Inspect binding** → paste the binding id. You’ll see `Engrams: {"column01": {"id":"…"}}`.

3. **27) Inspect engram by id** → paste the engram id **or** just type the binding id; it resolves for you.

4. **28) List all engrams** → browse all engrams with their source binding and time attrs.

### Q&A to help you learn this section

Q: What is FeaturePayload and why is it a Protocol rather than a base class?
A: FeaturePayload is a typing Protocol that describes the shape a payload must have (attributes kind, fmt, shape and methods to_bytes(), from_bytes(), meta()). It’s not meant to be instantiated; instead, any class that implements this interface (like TensorPayload) can be used as a payload. This keeps the column/bridge decoupled from a single concrete type.

Q: What problem does TensorPayload solve?
A: TensorPayload is a small, dependency-free way to package dense float tensors (often 1-D embeddings) for engrams. It supports:

compact binary serialization (to_bytes()),

reconstruction (from_bytes()),

and a lightweight meta() description (kind, fmt, shape, len).
This lets you store vectors in column memory, move them around, and describe them to UIs without pulling in NumPy.

Q: What does FactMeta represent and why must it be JSON-safe?
A: FactMeta is a compact descriptor for an engram: it gives a name (e.g., "vision:silhouette:mom"), optional links (binding ids or other engram ids), and free-form attrs (all JSON-safe). The Column stores {id, name, payload, meta} and the WorldGraph only needs the engram id. JSON-safety ensures we can put FactMeta.as_dict() directly into snapshots or logs without serialization issues.

Q: How does time_attrs_from_ctx relate to TemporalContext?
A: time_attrs_from_ctx(ctx) builds a tiny dict like {"ticks": ..., "tvec64": "...", "epoch": ..., "epoch_vhash64": "..."} by reading the runner’s Ctx. This is used to stamp engrams with temporal context at creation time, so later you can correlate engrams with episode boundaries and soft-clock similarity without decoding heavy payloads.

Q: Do I have to use TensorPayload and FactMeta or can I provide my own payloads?
A: You can provide any payload that satisfies the FeaturePayload protocol, and you can construct FactMeta (or equivalent) however you like as long as it’s JSON-safe. TensorPayload + FactMeta are just convenient, well-documented defaults that work nicely with the signal bridge and tests.



### Q&A to help you learn this section

Q: What exactly is stored inside ColumnMemory?
A: ColumnMemory is a simple in-RAM engram store. Each call to assert_fact(name, payload, meta) creates a record:

{
  "id": engram_id,
  "name": name,
  "payload": payload,   # often a TensorPayload
  "meta": meta_dict,    # includes attrs
  "v": "1"
}

and keeps it in _store[engram_id]. The WorldGraph only keeps the engram_id on bindings; the Column holds the heavy data.

Q: What does FactMeta.attrs["column"] represent?
A: When you assert a fact, ColumnMemory.assert_fact(...) ensures there is an attrs dict and sets attrs["column"] = self.name (e.g., "column01"). This lets you track which column owns an engram and is useful if you later add multiple columns (vision, audio, etc.).

Q: How do I safely fetch an engram without crashing?
A: Use try_get(engram_id) to get a record or None (never raises), or exists(engram_id) to check presence. get(engram_id) is stricter and will raise if the id is missing. For UI/tools, try_get is usually the safest choice.

Q: What is find(...) used for?
A: find(name_contains=..., epoch=..., has_attr=..., limit=...) gives you a lightweight query over the in-memory store. It’s handy for debugging and analytics, e.g., “show me all engrams whose name contains silhouette and epoch==2,” without needing a full database.

Q: Does ColumnMemory persist engrams across runs?
A: Not yet. ColumnMemory lives in RAM only. Engram ids and pointers are serialized via WorldGraph snapshots, but the column payloads themselves are currently in-memory. A future persistence layer could dump column contents to disk if needed; for now this keeps the system simple and fast for development runs.





# Tutorial on Column Module Technical Features

This section explains **`cca8_column.py`** — the in-memory engram store (“Column”) that holds **rich payloads** outside the WorldGraph. Bindings keep **only pointers** to these engrams, preserving a fast, compact episode index while still giving you traceability to perceptual/feature data.

**Why this module exists.**
_ WorldGraph stays small and plannable; columns carry the heavyweight 95% (vectors, features, descriptors). The runner’s bridge writes the minimum pointer on the binding so planning/search remain unchanged. 
The Column keeps heavy memory **out of the graph** without losing traceability: bindings stay fast and small; engrams in Column carry the payloads + time fingerprints you can inspect and query. The Runner menus make this workflow usable without writing code, albeit for small examples.



## 1) Mental model

* **Binding (WorldGraph)** → carries tags + **engrams pointer(s)** like  
  `{"column01": {"id": "<engram_id>", "act": 1.0}}`

* **Column (this module)** → keyed by `engram_id`, stores the **record**:  
  `{ "id", "name", "payload", "meta", "v" }`

* **Payload** → usually a `TensorPayload` (float32 vector) or a small dict with `meta()` describing `{"kind","fmt","shape","len"}`.

* **Time linkage** → runner mirrors temporal context into the engram’s `meta.attrs`: `ticks`, `tvec64`, **`epoch`**, **`epoch_vhash64`** (hash of the last event boundary).
  
  

## 2) Public API (what you can call)

from cca8_column import mem as column_mem

default singleton column ("column01")

Core engram_id = column_mem.assert_fact(name: str, payload, meta: FactMeta|dict) -> str record    = column_mem.get(engram_id: str) -> dict

Convenience helpers (present in current build) ok = column_mem.exists(engram_id: str) -> bool record_or_none = column_mem.try_get(engram_id: str)
    -> dict|None removed   = column_mem.delete(engram_id: str) 
    -> bool ids       = column_mem.list_ids(limit: int|None = None) -> list[str]matches = column_mem.find(name_contains: str|None =

    None,   epoch: int|None = None,  has_attr: str|None = None,   limit: int|None = None) -> list[dict]n = column_mem.count() -> int`

**Record shape (typical):**

`{   "id": "<engram_id>",   "name": "scene:vision:silhouette:mom",   "payload": TensorPayload(...),     // or a small dict with shape/kind   "meta":
 {     "name": "...", "links": ["b3"], "attrs": {       "ticks": 5, "tvec64": "…", "epoch": 2, "epoch_vhash64": "…",       "column": "column01"     },
  "created_at": "YYYY-MM-DDThh:mm:ss"   },   "v": "1" }`



## 3) How time gets into Column records (bridge)

From the Runner (menu **24 Capture scene**), we pass `attrs=time_attrs_from_ctx(ctx)`, which copies **`ticks`**, **`tvec64`**, **`epoch`**, **`epoch_vhash64`** into `meta.attrs` of the Column record at **assert time**. With the current Runner, capture does a **pre-capture event boundary**, so the engram’s `epoch` reflects the **new** boundary you just created.

CLI menus that help you see this:

* **24** Capture → prints binding id + engram id + mirrored time attrs.

* **27** Inspect engram by id (also accepts a binding id; it resolves the pointer).

* **28** List all engrams (id, source binding, time attrs, payload summary).

* **29** Search engrams (by name substring / epoch).

* **30** Delete engram (accepts binding id or engram id; also **prunes all binding pointers** to that id).

* **31** Attach existing engram to a binding (demonstrates many-to-one pointers).
  
  

## 4) Minimal usage cribs

**A) Programmatic (direct Column write + pointer attach)**

`from cca8_column import mem from cca8_features import TensorPayload, FactMeta, time_attrs_from_ctxvec = [0.1, 0.2, 0.3]payload = TensorPayload(data=vec, shape=(len(vec),))meta = FactMeta(name="scene:vision:silhouette:mom",                links=[latest_bid],                attrs=time_attrs_from_ctx(ctx))  # ticks, tvec64, epoch, epoch_vhash64  eid = mem.assert_fact("scene:vision:silhouette:mom", payload, meta)world.attach_engram(latest_bid, column="column01", engram_id=eid, act=1.0)`

**B) Via the Runner bridge (one step)**

`bid, eid = world.capture_scene(    channel="vision", token="silhouette:mom",    vector=[0.1, 0.2, 0.3], attach="now", family="cue",    attrs=time_attrs_from_ctx(ctx)  # mirrors temporal attrs )`

**C) Lookup & inspect**

`rec = world.get_engram(engram_id=eid) print(rec["meta"]["attrs"])   # -> ticks/tvec64/epoch/epoch_vhash64/column print(rec["payload"].meta())  # -> {'kind','fmt','shape','len'}`



## 5) Invariants & guardrails

* **WorldGraph only stores pointers.** Don’t stuff large blobs in bindings; keep payloads in Column.

* **Provenance & time are split:** bindings stamp `created_at`, `ticks`, `tvec64`, `epoch`; engrams mirror time in `meta.attrs`.

* **Pointer pruning:** deleting an engram from Column should prune any binding pointers to it (Runner menu **30**) to prevent dangling references.

* **Volatility:** the default in-memory Column is session-local. Pointers aren’t persisted across restarts unless you add a persistence layer for Column (future work).

* **Payload discipline:** keep payloads **small** (vectors, short descriptors). Summarize in UIs; use `.meta()` (shape/kind/len) instead of decoding bytes.
  
  

## 6) CLI walkthrough (fast demo)

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
   
   

## 7) Test ideas (unit tests you can add/extend)

* **Round-trip & meta:** `assert_fact → get` preserves `id/name/payload`, `meta.attrs["epoch"]` present when provided.

* **CRUD:** `exists/try_get/delete/list_ids/count` behave as advertised.

* **Find:** substring match on `name`, epoch filter, `has_attr` key present.

* **Pointer pruning:** after delete, runner scan finds **0** pointers to the removed id.
  
  

## 8) Roadmap (non-breaking extensions)

* Optional persistence for Column (e.g., JSONL/SQLite sidecar).

* Nearest-neighbor queries on payloads (similarity search) to bias policy arbitration.

* Multi-column pointers per binding (vision/audio/touch) with light aggregation in UIs.
  
  
  
  
  
  

# Tutorial on Approach to Simulation of the Environment



* * *

**1 Introduction**

Embodied AI and cognitive robotics require agents that can perceive, act, and learn in environments whosecomplexity often far exceeds what can be modeled analytically. Simulation hastherefore become a central tool in robotics and embodied AI, enabling safe,scalable experimentation before deployment in the real world. In parallel,reinforcement learning (RL) communities have converged on standardizedenvironment interfaces (e.g., Gym/Gymnasium) that present agents withobservations, actions, and rewards, abstracting away simulator details.

At the same time, cognitive architectures and semantic world models emphasize internal knowledgerepresentations—often graph-based—that support reasoning, planning, andepisodic memory. Examples include knowledge-graph world models in robotics andframeworks such as KnowRob, which integrate symbolic knowledge with perceptionand planning. More recently, large language models (LLMs) have been used assimulators and world models, generating agent behavior and environmentaldynamics in agent-based simulations.

As noted above, the CCA8architecture is a columnar, graph-centric cognitive system intended to controlembodied agents (e.g., a newborn goat, and later a robot). Internally, itmaintains a **WorldGraph** reflecting its beliefs and memories about theenvironment. However, for the near future, CCA8 must operate in simulatedenvironments. The long-term goal is to transition to partial and eventuallyfull real-world sensing via a physical robot. This raises a design question:

**How can we design a simulationsystem that starts as a tiny finite-state-scripted world and eventuallyincorporates physics simulation, RL-style reward modeling, LLM-driven events,and real sensor streams—without repeatedly rewriting the agent–environmentinterface?**

In this section we imagine a hybrid environment architecture that addresses this question. The core idea isto fix a stable, agent-facing observation interface and a canonical environmentstate representation, and to treat different simulators (FSM, physics, LLM,etc.) as composable backends that update this state. The architecture isdesigned explicitly to:

1. Start with a purely finite-state machine (FSM) “storyboard” environment for a newborn-goat scenario.
2. Grow to incorporate physics/robotics simulators and RL-style MDP reward models.
3. Support LLM-driven environment components where appropriate.
4. Eventually plug in real-world robot sensors (and hybrid sim+sensor regimes) without changing CCA8’s core code.

* * *

**2 Backgroundand Related Work**

**2.1 Environment representations and world models in robotics**

Robots require internalrepresentations of their environment to plan and act. Traditional robotics hasemployed metric maps (e.g., occupancy grids, point clouds) for localization andnavigation. More recent work emphasizes **semantic world models**, whereobjects, rooms, and relations are explicitly represented in a knowledge base orgraph.

KnowRob is a prominent example,KnowRob, or Knowledge Processing for Robots, is a knowledge processing system thatcombines knowledge representation and reasoning methods with techniques foracquiring the knowledge and grounding the knowledge in a physical system.KnowRob has been developed at the University of Bremen, Germany. KnowRob providesa knowledge processing system where robot experience, environment structure,and task knowledge are encoded in a shared knowledge base, enabling symbolicreasoning about objects, actions, and their preconditions and effects. Otherwork proposes multi-layer environment models that link sensor-levelobservations to semantic knowledge graphs, explicitly bridging betweenlow-level data and high-level concepts.

The CCA8 **WorldGraph** is conceptually aligned with these semantic/episodic knowledge graphs: itrepresents objects, agents, events, and relations as graph nodes and edges.However, in our design, WorldGraph is strictly an **internal construct** ofthe agent. The external environment is represented separately in **EnvState**,and only filtered, agent-relevant information is projected into WorldGraph.

**2.2 Simulation in robotics and sim-to-real pipelines**

Simulation is widely used totest controllers, generate training data, and de-risk robotic deployments.Physics-based simulators model rigid-body dynamics, sensors, and interactionswith objects and humans, enabling control algorithms to be developed beforereal-world trials. Newer systems aim to create high-fidelity “digital twins” ofreal environments using 3D reconstruction and neural rendering, which can beused to train policies that transfer back to the physical world via sim-to-realpipelines.

Hybrid approaches combineanalytical dynamics for parts of the scene with learned models for robotdynamics, providing more realistic simulators while keeping some structureexplicit. Our proposed architecture is compatible with such simulators: a **PhysicsBackend** can wrap any of these engines.

**2.3 Reinforcement learning environment APIs**

In RL, environment design isoften standardized through APIs. Gym and its successor Gymnasium  (formerly OpenAI Gym which is an open sourcePython library for reinforcement learning) define an interface where an agentinteracts with an environment via methods such as reset() and step(action), receiving observations, rewards, and terminationsignals. This interface has enabled broad interoperability acrossdomains—games, control tasks, and robotics—and is widely adopted in RL researchand practice.

Our **HybridEnvironment** deliberately mirrors this style: it exposes a stable reset/step interface returning **EnvObservation**, areward, and metadata. However, rather than binding tightly to a singlesimulator, it orchestrates multiple backends (FSM, physics, LLM, robot sensors)to update a shared EnvState.

**2.4 LLM-based simulators and world models**

Large language models areincreasingly used as components of simulation frameworks, both for agentpolicies and for environment dynamics. At the time of this writing, i.e.,November 2025, s urveys of LLM-empowered agent-based modeling emphasize theiruse in generating realistic agent behaviors, interactions, and narratives.Other work explores LLMs as text-based world simulators, assessing how wellmodels can track object properties and state transitions over time.

There is also growing interestin “world models” that go beyond next-token prediction, maintaining internalstate and predictive dynamics to support planning and control. Our architecturetreats LLMs as **one backend among several**—primarily for high-level eventgeneration, scenario randomization, and narrative augmentation—rather than asthe sole environment model.

**2.5 Hybrid synthetic and real data**

To improve generalization andsim-to-real robustness, many systems combine synthetic and real data. Hybriddatasets blend simulated and real examples, leveraging the scalability ofsynthetic data and the fidelity of real-world samples. Robotics work similarlycombines simulated training with real-world fine-tuning, sometimes in iterative“real-to-sim-to-real” loops.

Our design aims to support thishybrid regime at the environment level: **RobotBackend** provides realsensor observations, while FSM and PhysicsBackends fill in unobserved orhypothetical aspects, all feeding into the same EnvObservation interface.

* * *

**3 Proposed Hybrid Environment Architecture for CCA8**

**3.1 Design goals**

The architecture is driven bythe following goals:

1. **Stable agent–environment interface**: CCA8 should interact with the environment through a single, stable interface that remains valid as we move from pure simulation to real-world sensors.
2. **Multiple fidelity levels**: Support tiny finite-state “storyboards,” physics-based simulations, RL-style reward modeling, and LLM-driven components in a composable manner.
3. **Separation of concerns**: Cleanly separate (a) the external environment, (b) the agent’s internal world model (WorldGraph), and (c) environment simulators or sensor backends.
4. **Hybrid sim+sensor support**: Allow partial simulation and partial real sensing in the same environment episode, with clear precedence rules.
5. **Cognitive realism**: Ensure that the agent never directly accesses the “God’s-eye” environment state; it only sees observations derived from that state.

**3.2 Core terminology**

We introduce key terms that willbe used consistently in CCA8 development.

* **Agent**  
  The embodied system controlled by CCA8 (e.g., a simulated newborn goat or a robot).

* **WorldGraph**  
  CCA8’s internal, graph-structured world model representing objects, agents, events, and relations as nodes and edges. This is an **internal belief and memory structure**, not the environment itself.

* **Environment**  
  The external world in which the agent exists. In this work, the environment may be simulated (FSM, physics), partially simulated plus real sensors, or fully real.

* **EnvState** (environment state)  
  A canonical data structure maintained by the environment that encodes the **ground-truth state** of the world from a “God’s-eye” perspective. For the newborn-goat scenario, EnvState contains fields such as the kid’s posture, positions of kid and mother, nipple visibility, fatigue, and time since birth.

* **EnvObservation**  
  The agent-facing observation structure produced by the environment on each step. EnvObservation includes:

* raw_sensors: Optional numeric/tensor channels (e.g., depth images, proprioceptive signals).

* predicates: Discrete, symbolic facts suitable for insertion into WorldGraph.

* cues: Tokens that route into CCA8’s feature/column subsystems.

* env_meta: Lightweight metadata (e.g., episode identifiers, uncertainty estimates).

* **HybridEnvironment**  
  The orchestrator object that implements the RL-style interface:

·       EnvObservation, info = reset(seed, config)

·       EnvObservation, reward, done, info =step(action, ctx)

HybridEnvironmentowns EnvState and coordinates multiple backends to update it.

* **Backend**  
  A module that contributes to updating EnvState or evaluating transitions. We define several types:

* FsmBackend: Finite-state machine or scripted environment.

* PhysicsBackend: Physics or robotics simulator backend.

* MdpBackend: Reward and termination evaluator (MDP/POMDP).

* LlmBackend: LLM-driven event and parameter generator.

* RobotBackend: Interface to real sensors (and possibly actuators) for physical robots.

* **PerceptionAdapter**  
  The component that converts EnvState into EnvObservation, including symbolic predicates and cues.

These definitions are chosen sothat CCA8 code refers only to HybridEnvironment, EnvObservation, and its ownWorldGraph; EnvState and backends are strictly environment-side.



## Environment Geometry

When we talk about the **geometry** of the environment, it is not referring to school-style angles and triangles. Instead, “environment geometry” means the **spatial configuration of the scene**: where, for example in the early stages of the Mountain Goat, the kid, mom, shelter, and cliff are, and how they are related (near, far, under shelter, near a drop, etc.).

In CCA8 there are three closely related layers that together define this geometry:

1. **EnvState (God’s-eye world)**  
   The Environment module keeps a canonical `EnvState` with fields such as `kid_posture`, `mom_distance`, `nipple_state`, `kid_position`, `mom_position`, and high-level `scenario_stage` (birth → struggle → first_stand → first_latch → rest). This is the environment’s own notion of “where everything is and what is happening right now.” :contentReference[oaicite:0]{index=0}  

2. **BodyMap (body-centred near space)**  
   BodyMap is a tiny, separate WorldGraph that tracks the **geometry as experienced by the body**: posture (fallen/standing/resting), mom’s proximity (far/near/touching), nipple state (hidden/found/latched/milk:drinking), and safety-relevant slots for shelter and cliff (shelter near/far, cliff near/far). From BodyMap you can ask, “Is it safe to lie down here?” or “Is mom close enough to seek the nipple?” without scanning the full episode history.  

3. **WorldGraph spatial overlay (episode-level geometry)**  
   The main WorldGraph stores **episodic traces** of geometry using predicates and a small scene-graph overlay. For example, when the kid is resting safely, the runner writes edges like  
   `NOW --near--> b_mom_close` and `NOW --near--> b_shelter_near`,  
   where the target bindings carry tags such as `pred:proximity:mom:close` and `pred:proximity:shelter:near`. These edges say, “in this episode moment, SELF (NOW) is near mom and near shelter,” and can be inspected later via the snapshot, Pyvis export, or the spatial scene demo menu.
   
   

### Passive storyboard vs. active geometry

Early in development the geometry can be driven **purely by the storyboard**:

- The `FsmBackend` advances `EnvState` through a fixed script (birth → struggle → first stand → latch → rest).
- PerceptionAdapter turns that `EnvState` into `EnvObservation`, which is injected into WorldGraph and mirrored into BodyMap.
- Geometry changes because the **environment script** says “mom moves closer,” “shelter becomes available,” and so on.

As we move toward a more complete system, the goat’s **own actions** begin to change geometry:

- Policies such as `StandUp`, `SeekNipple`, or a future `SeekShelter` fire in response to drives and BodyMap state.
- Their chosen actions are fed back into `HybridEnvironment.step(action, ctx)`, where backends are allowed to update positions, distances, and stages based on what the agent did.
- BodyMap and the WorldGraph spatial overlay then reflect geometry that has changed **because of the agent’s behavior**, not just because time passed in a storyboard.

In this sense, when we say:

> “the goat’s actions change the storyboard geometry”

we mean that the same underlying structures—`EnvState`, BodyMap, and the WorldGraph spatial overlay—are being updated so that:

- the kid moves from exposed, cliff-near terrain into a sheltered, cliff-far niche,
- the spatial relations (`near mom`, `near shelter`, `cliff far`) flip as a **consequence of policies firing**, and
- planning and inspection later can see that these safer configurations were **reached by the agent’s own actions**, not by a scripted teleport.

Environment geometry, then, is simply the **current spatial layout of the scene** plus its episode-level trace: who is where relative to whom, which regions are safe vs. dangerous, and how that configuration evolves over time as the environment and the agent interact.


### Example: Follow-mom movement across terrain

In the newborn goat storyboard, one of the simplest examples of “actions changing geometry” is the **follow-mom behaviour**.

At the environment level we keep a coarse spatial ladder in `EnvState`:

- `position`: `"cliff_edge"`, `"open_field"`, or `"shelter_area"`
- `zone`: a safety classification derived from `position` and distances (`"unsafe"`, `"neutral"`, `"safe"`)

The **storyboard + FollowMom policy** cooperate to move the kid along this ladder:

1. Early in the story, once the kid is standing, geometry is still exposed:

   - `position = "cliff_edge"`
   - `cliff_distance = "near"`
   - `shelter_distance = "far"`
   - BodyMap’s zone ≈ “near a drop, no shelter” (unsafe for resting)

2. When the controller selects `policy:follow_mom` and the environment applies it in this stage:

   - First hop:  
     `cliff_edge → open_field`  
     `cliff_distance` flips to `"far"` while `shelter_distance` stays `"far"`.  
     Geometry is now “neutral ground” (no nearby cliff, no nearby shelter).

   - Second hop:  
     `open_field → shelter_area`  
     `shelter_distance` becomes `"near"`, `cliff_distance` remains `"far"`.  
     Geometry is now a sheltered niche near mom, suitable for resting and feeding.

BodyMap mirrors these changes into posture / mom-distance / shelter / cliff slots and recomputes its own zone (`unsafe_cliff_near` vs `safe`). The main WorldGraph records the **episode trace** of these transitions, so a diagnostic snapshot clearly shows that the kid did not magically teleport into safety; it walked off the edge, then into shelter, under its own `follow_mom` behaviour.




### Understanding these terms:

**1. Is EnvState the ground-truth state of the world?**

**Yes, that’s exactly how we’re treating it.**

* **EnvState ≈ “God’s-eye reality”** _as far as the environment module is concerned_.
* In pure simulation, EnvState _is_ the simulator’s canonical state (kid posture, positions, mom distance, nipple state, etc.).
* In a robot setting, EnvState is our maintained best estimate of reality, updated from sensors—but conceptually, we still treat it as “the environment’s ground truth,” not the agent’s belief.

CCA8 never reads EnvState directly.

### 2. Do portions of EnvState stream into theagent as sensory streams?

**Yes, with two caveats: partial and possiblynoisy.**

·       Oneach tick, the environment takes EnvState and runs it through a **PerceptionAdapter** to produce an **EnvObservation**.

·       Thatadapter:

o   selects _which_ bits ofEnvState are observable,

o   mayadd noise / quantization / occlusion,

o   convertsthem into:

§  `raw_sensors` (e.g. distances, images,proprioception),

§  `predicates` (symbolic facts),

§  `cues` (tokens for Columns/features).

So: **EnvObservation is the “sensory/perceptual packet” derived from EnvState**, not a direct dump of EnvState.

### 3. Is EnvObservation the sensory stream, orthe agent’s internal perception/storage?

Shortanswer:

·       **EnvObservation= the sensory/perceptual** _**input**_ **the agent receives** _**thistick**_**.**

·       **WorldGraph(and engrams/columns) = the agent’s** _**internal perception + storage**_**.**

More precisely:

·       EnvObservation is like:

o   Theset of spikes coming in from the senses,

o   plusperhaps some very early preprocessing (e.g. “already segmented into objects”).

·       It is **not** persistent storage; it’s a _transientmessage_ for this step.

·       CCA8 then:

o   readsEnvObservation,

o   writescorresponding nodes/edges into **WorldGraph**,

o   updatesColumns / engrams, etc.

o   Thatstored, structured stuff _is_ the agent’s internal perception/interpretation.

So you can picture the pipeline as threedistinct layers:
    Reality / EnvState         (world as it is, "God's-eye")
              ↓
    PerceptionAdapter
              ↓
    EnvObservation             (what hits CCA8 this tick: sensors + symbolic cues)
              ↓
    CCA8 (WorldGraph, Columns)
              ↓
    Internal model / memory    (agent’s ongoing interpretation & storage)

**EnvState = world;EnvObservation = what the agent “sees” now; WorldGraph = what the agent “thinksand remembers” about the world.**

* * *

i. The hard boundary in code
----------------------------

There is **one clear architectural seam**:
    [Environment side]                 |            [Agent (CCA8) side]
    -----------------------------------+----------------------------------------
    HybridEnvironment.step(...)        | CCA8.ingest_observation(...)
    produces: EnvObservation, reward   | consumes: EnvObservation
                                       | updates: WorldGraph, Columns, etc.

So:

·       **Everythingthat happens** _**before**_ `**EnvObservation**` **exists** is “environment-side”.

·       **Everythingthat happens** _**after**_ **CCA8 receives** `**EnvObservation**` is “agent-side” (WorldGraph, Columns, FOA, planning, etc.).

`EnvObservation` itself isthe **message on the wire** between the two sides.

* * *

ii. Three layers of “world” – quick review
------------------------------------------

Let’s name the three levels explicitly:

1.     **EnvState** — reality (as the environment subsystem believes it)

2.     **EnvObservation** — what hits the agent this tick

3.     **WorldGraph/ Columns / Engrams** — what the agent thinks and remembers

Visually:
    Reality / EnvState                 (world as it is; God’s-eye)
              │
              │  PerceptionAdapter (env-side)
              ▼
    EnvObservation                     (what the agent receives *this tick*)
              │
              │  CCA8.ingest_observation(...)
              ▼
    WorldGraph + Columns               (agent’s internal, persistent model)

So to your question:

EnvObservation is this sensory stream or the mapped storage?

**It’s the sensory/perceptual stream.**  
**The storage / interpretation lives in WorldGraph & friends.**

* * *

iii. What exactly lives in EnvObservation?
------------------------------------------

This is where the boundary can feel fuzzy, because EnvObservation cancontain both low-level and high-level stuff.

I’d define it like this:
    @dataclass
    class EnvObservation:
        raw_sensors: dict[str, Any]    # e.g. depth image, IMU, distances...
        predicates: list[Predicate]    # symbolic facts (posture, near, etc.)
        cues: list[str]                # tokens that hint Columns/features
        env_meta: dict[str, Any]       # episode id, uncertainties, etc.

Conceptually:

·       `raw_sensors`:

o   Direct-ish sensor outputs (orsimulated equivalents).

o   E.g. “here’s a 64×64 depth map”,“here’s a vector of joint angles”.

·       `predicates`:

o   Already somewhat _interpreted_ facts like `posture(kid,fallen)`, `near(mom,kid)`.

o   These are still **observation-level**, because they are not yet writteninto memory or stitched into a timeline.

·       `cues`:

o   Lightweight tokens that say “pleasewake up this feature/column” (e.g. `"visual_mom_silhouette"`).

All of that is still **“incoming data”**. When CCA8 turns those predicates andcues into nodes/edges with attach semantics and folds them into its internalFOA / Columns / engrams, that’s where it becomes **internal perception + memory**.

* * *

iv. Where does “perception” live: env vsagent?
----------------------------------------------

There’s a design choice here,and we can support a few regimes without breaking the boundary:

### Variant A – EnvObservation is mostly raw

·       Environmentgives you:

o   `raw_sensors` (depth maps, IMU, etc.)

o   maybe very minimal predicates.

·       CCA8is responsible for:

o   detecting mom, inferring posture,quantizing distances, etc.

·       Thisis maximally “cognitively pure”: **almost all interpretation is in the agent**.

### Variant B – EnvObservation is partlypre-digested

·       Environment(or a “pre-perception” stack) runs object detectors, pose estimators, etc.

·       EnvObservationincludes predicates like:

o   `object(mom)`, `posture(kid,fallen)`, `near(mom,kid)`.

·       CCA8still:

o   decides what to store,

o   where to attach in time,

o   how to relate these to its existingWorldGraph.

This is more practical earlyon (we don’t have to build our own vision stack inside CCA8), and it’s what weimplicitly assumed in the paper.

### Variant C – Hybrid

·       Somechannels are raw (e.g. proprioception).

·       Someare pre-tokenized (e.g. “mom silhouette detected”).

·       CCA8can refine / override predicates over time.

**Architecturally**, all three variants look the same:the only thing we promise is:

“Whatever mixture you choose,it will be wrapped in `EnvObservation` before CCA8 sees it.”

So we don’t have to decide _now_ whether a YOLO detector lives “inside CCA8” or “insidethe Environment”. From the architecture’s point of view, it’s just _more work done before EnvObservation isconstructed_.

* * *

v. Small 1-tick Example
-----------------------

Let’s walk a single tickend-to-end:

### v.1 EnvState (God’s-eye)

    kid_posture      = fallen
    
    kid_position     = (0.0, 0.0)
    
    mom_position     = (0.7, 0.0)
    
    nipple_state     = hidden
    
    time_since_birth = 45 seconds

### v.2 PerceptionAdapter (env-side) →EnvObservation

From this, the environmentconstructs:
    raw_sensors:
      distance_to_mom = 0.7
      imu_accel       = [some vector indicating lying down]
    predicates:
      posture(kid, fallen)
      near(mom, kid)        # because distance_to_mom < threshold_near
    cues:
      ["visual_mom_silhouette", "body_low_posture"]
    env_meta:
      {"time": 45.0}

This full structure is **EnvObservation**. The environment then calls:
    obs, reward, done, info = env.step(action, ctx)

and hands `obs` to CCA8.

### v.3 CCA8.ingest_observation (agent-side)

CCA8 does something like:

·       Foreach `predicate`:

o   Turn into a node/edge in WorldGraph,with `attach="now"` or `attach="latest"`, respecting our attach semantics.

·       Foreach `cue`:

o   Wake up or update relevant Columns /features.

·       Possiblyderive _further_ internal predicates (e.g.“risk_of_hypothermia ↑” based on repeated low posture + temperature).

Now we’ve crossed theboundary: we’re no longer talking about **observation**,but about **internalbelief and memory**.

If at some later tick theenvironment stops reporting mom (e.g. occlusion), WorldGraph might stillpreserve the last seen mom location, FOA might keep it active briefly, etc.That divergence between **current observation** and **internalremembered model** is exactly why we keep EnvObservation and WorldGraph conceptually distinct.

* * *

** HybridEnvironment “control” the environment?**

Yes — HybridEnvironment is the central hub on the _environment_ side.
But the _overall_ organization comes from two things together:

1.     HybridEnvironment (hub + scheduler of backends), and

2.     A “Scenario / Task config” that tells it _what kind_ of world to run(newborn goat, later robot, etc.).

On the **environment side**:

·       It **owns EnvState** (the canonical world state).

·       Itknows which backends are enabled: FsmBackend, PhysicsBackend, LlmBackend,MdpBackend, RobotBackend.

·       Onevery `step(action, ctx)` it:

1.     Takescurrent `EnvState_t`.

2.     Askseach backend for its contribution:

§  FSM:“Any discrete stage updates?”

§  Physics:“Integrate dynamics for dt?”

§  Robot:“New sensor readings?”

§  LLM:“Any exogenous events?”

3.     Mergestheir deltas according to field-ownership rules.

4.     CallsPerceptionAdapter to produce `EnvObservation`.

5.     CallsMdpBackend to compute reward/done if needed.

6.     Returns `(EnvObservation, reward, done, info)` to CCA8.

So yes, HybridEnvironment is the **controlling hub** _for world updates_. All environment-side logicultimately runs under its coordination.

What it does **not** control:

·       Itdoesn’t decide the agent’s actions—that’s CCA8.

·       Itdoesn’t write into WorldGraph; it only emits EnvObservation.

Global control loop looks like:
    loop:
        action = CCA8.choose_action(last_observation, ctx)
        observation, reward, done, info = HybridEnvironment.step(action, ctx)
        CCA8.ingest_observation(observation, reward, done, info)

So:

·       **HybridEnvironmentcontrols the world.**

·       **CCA8controls the agent.**

·       Atop-level driver script (like your `cca8_run.py`)controls the _overall simulation loop_.



**What gives the “overall organization” of the simulation?**

There are two layers of“organization”:

### 2.1 Environment-side organization: Scenario / Task

Here we have a **Scenario or Task config** thattells HybridEnvironment:

·       whichbackends to enable (`use_fsm`, `use_physics`, `use_robot`, `use_llm`, `use_mdp`),

·       initialconditions for EnvState (e.g., kid fallen, mom at distance X),

·       parameters(time constants, thresholds, noise levels),

·       possiblyhigh-level script (e.g., stages: birth → struggle → first-stand → latch →rest).

This scenario config is what makes one episode “newborn goat first hour” vs“different goat in snow” vs “robot in lab”.

Typically:

·       **FsmBackend** encodes the macro **story structure**:

o   scenario stages (birth, struggle, latch, rest),

o   when certain scripted events are allowed tohappen.

·       **PhysicsBackend/ RobotBackend** handle concrete movement and sensor realismwithin that structure.

·       **MdpBackend** defines what counts as “success” and how reward is computed.

So the _organization of the environment’sbehavior over time_ is mostly:

Scenario config + FsmBackend logic, all orchestrated by HybridEnvironment.

### 2.2 System-wide organization: the main loop

At the full-system level, the “director” is simply the main loop:

1.     Call `HybridEnvironment.reset(...)` with a chosen scenario.

2.     Foreach tick:

o   Ask CCA8 for an action.

o   Pass that action to HybridEnvironment.

o   Feed the resulting EnvObservation back intoCCA8.

That’s where you decide:

·       How long episodes last,

·       Whether you run one goat or many,

·       Whether you run in real time or faster-than-real-time, etc.



**Why we want HybridEnvironment as the hub (and not, say, FsmBackendalone)**



Reasons to centralize around HybridEnvironment:

·       **Singleowner of EnvState**  
No backend is allowed to maintain its own hidden “canonical” world; they alltalk through EnvState, which HybridEnvironment owns. That prevents divergence.

·       **Cleancomposition of backends**  
Only HybridEnvironment knows how to:

o   call backends in the right order,

o   merge their proposed deltas,

o   respect ownership rules (e.g., RobotBackendoverrides Physics for positions).

·       **Stableagent interface**  
From CCA8’s point of view, there is just one environment object with `reset/step` and `EnvObservation`.HybridEnvironment ensures that never changes even when you add or swapbackends.

·       **Scenario-levelorganization lives “above” individual backends**  
A scenario might:

o   select which backends to use

o   initialize their configs

o   set the starting EnvState  
but HybridEnvironment is the runtime hub that executes that scenario.



**HybridEnvironment Summary**



**HybridEnvironment owns EnvState, therefore is this thecontrolling hub?**

Yes.  
HybridEnvironment is the **controlling hub on the environment side**:it’s the central authority that holds EnvState and coordinates all the backendsthat change it.

**What gives overall organization of the environment simulation?**

·       Onthe **world side**:  
Scenario + FsmBackend (and configs for other backends), all executed throughHybridEnvironment.

·       Onthe **full system side**:  
The main simulation loop (in your driver code) that alternates:

o   CCA8 choosing actions,

o   HybridEnvironment updating the world andreturning observations.

Essentially:

·       **HybridEnvironment** = the laws and bookkeeping of that universe.

·       **Backends(FSM/physics/LLM/robot/MDP)** = the physical + narrativesubsystems inside that universe.

·       **Scenarioconfig** = which universe you’re running right now.

·       **CCA8** = the mind of the goat that lives inside it.



**Big-picture: what is a “backend” here?**

In our design, a **backend** is:

A _modular subsystem_ that knows how to update **someaspect** of the environment’s ground-truth state (**EnvState**),or how to evaluate it (reward/termination), under the control of **HybridEnvironment**.

So:

·       HybridEnvironment= the **conductor**.

·       Backends= the **section players** (strings,percussion, brass…) that each handle a specific part of the music.

HybridEnvironment doesn’t “know physics” or “know the script” or “talk tothe robot” itself.  

Instead, it delegates those responsibilities to backends, then merges theircontributions.

**Backends exist to solve four problems:**

### Separation of concerns

We don’t want one giant “god class” that:

·       runsthe storyboard,

·       simulatesphysics,

·       computesreward,

·       talksto real sensors,

·       callsan LLM, etc.

That would quickly become unmanageable.

Backends let us say:

·       “Thispiece of code is responsible _only_ for high-level scriptlogic.”

·       “Thispiece is _only_ responsible for continuous dynamics.”

·       “Thisone _only_ reads sensors from a robot.”

Each is focused, testable, and swappable.

### Composableenvironment fidelity

We want to be able to say things like:

·       _Rightnow_: “Use only the FSM backend — just a tiny storyboard.”

·       _Later_:“Turn on FSM + Physics.”

·       _Evenlater_: “Turn on Robot + MDP, FSM just for high-level stage logic.”

·       Andmaybe: “Occasionally consult an LLM backend for rare exogenous events.”

Backends are the knobs we turn **on/off** or **combine** as the project matures, _without_ changing CCA8’s interface.



### Stable interface to CCA8

From CCA8’s perspective:

·       Thereis **one** environment object.

·       Itspeaks `reset()` / `step()` and returns **EnvObservation**.

All the mess of:

·       “Isthis step driven by a script or a simulator?”

·       “Isposture real IMU or fake physics?”

·       “Isthis reward from an RL task or just logging?”

is hidden behind the backend layer.

Backends are how we **evolve the world** overmonths/years without ever asking CCA8 to change how it talks to the world.



### Straight path to robots

Finally, the backends give us a clean path from:

·       “Everythingis simulated” →

·       “Someparts are sensors, some parts are still simulated” →

·       “Everythingphysical is from the robot; only unobservable bits are simulated.”

That progression is just:

·       graduallyhanding ownership of EnvState fields from **PhysicsBackend** to **RobotBackend**,

·       maybekeeping FSM around to define high-level stages,

·       andletting MdpBackend compute reward if we ever train RL policies.

Because these roles are cleanly separated into backends, we don’t have totear the environment apart when we finally plug in a real robot.

**Backends are the plug-in “sub-engines” of the world**:each handles one slice of reality (script, physics, reward, LLM events, or realsensors), while HybridEnvironment coordinates them and presents a single, cleanEnvObservation stream to CCA8.



**9. Big picture: what is PerceptionAdapter _for_?**



**High level:**

PerceptionAdapter is the environment’s “sensory interface” tothe agent.

It looks at **EnvState** (God’s‑eyeworld) and decides:

·       _what_ the agent is allowed to sense,

·       _how_ that information is encoded, 

and then packages it into **EnvObservation**, whichCCA8 receives.

So if backends answer the question:

“Given the world right now and the action, how does the world _change_?”

PerceptionAdapter answers:

“Given the world right now, what does the agent _see/feel/hear_ this tick?”

Key points:

·       Itlives on the **environment side** (beforethe agent boundary).

·       Itdoes **not** store memory and does **not** update WorldGraph.

·       Itcan be as simple as “hand the agent a few booleans” or as rich as “full RGBDimages + symbolic detections”.

·       Itsoutput, `EnvObservation`,is the only thing CCA8 sees of the world.

You can think of it as the environment’s _“sensor andearly-vision cortex”_ bundled together, up to the point where wehand off to CCA8.



**Why do we have a PerceptionAdapter?**

Three main reasons:

### Control what’s observable

EnvState may contain a lot of stuff:

·       exactpositions, hidden variables, internal counters, etc.

The agent should not see all of that:

·       insim, for realism (no omniscience),

·       withrobots, because sensors are limited and noisy.

PerceptionAdapter is the **gatekeeper**:

·       chooseswhich parts of EnvState are observable at all,

·       andin what _form_ (raw numbers vs symbols vs cues).

* * *

### Decouple observation formatfrom environment internals

We want to be able to change the environment internals without breakingCCA8:

·       maybewe switch from a 1D “distance_to_mom” to full 3D positions,

·       orfrom a toy posture flag to a detailed physics body pose.

If PerceptionAdapter is the only place that knows how to turn EnvState intoEnvObservation, then:

·       wecan refactor EnvState structure,

·       orswap out backends,

·       andjust update PerceptionAdapter,

·       whileCCA8 continues to consume the same EnvObservation schema.

So the adapter is a **stability layer**: it hidesthe messy details of EnvState and presents a stable “sensor API” to the brain.

* * *

### Make perception itself modular and upgradable

Early on, PerceptionAdapter can be:

·       completelyhand‑coded:

o   “if distance < 1.0 → emit `near(mom,kid)` predicate”,

o   “if kid_posture == fallen → emit `posture(kid,fallen)`”.

Later, we may want:

·       realdetectors / learned perception:

o   run a vision model on a depth image,

o   detect mom’s silhouette,

o   infer posture from an IMU trace.

If all of that lives inside PerceptionAdapter (or submodules under it), wecan:

·       upgradeperception over time,

·       mixsimulated signals and real sensor processing,

·       withouttouching HybridEnvironment or the CCA8 side.



**So, what _is_ PerceptionAdapter, concretely?**



Conceptually:
    EnvState  --[PerceptionAdapter]-->  EnvObservation  --(crosses boundary)-->  CCA8

Inputs:

·       Current `EnvState` (and optionallysome short observation history).

·       Possiblyraw sensor measurements from RobotBackend.

Outputs: a fully populated `EnvObservation`,something like:
    EnvObservation:
        raw_sensors: dict[str, Any]   # numeric/tensor channels (e.g. images, distances, IMU)
        predicates:  list[Predicate]  # symbolic facts, ready to be written into WorldGraph
        cues:        list[str]        # tokens for Columns/features ("visual_mom", "cold_skin")
        env_meta:    dict[str, Any]   # extras: time, uncertainties, episode id, etc.

What it _does_ in between:

·       **Select**:choose which pieces of EnvState matter for the agent right now.

·       **Transform**:

o   Raw → numeric features (“distance_to_mom = 0.7m”).

o   Numeric → symbolic (“near(mom,kid)” vs“far(mom,kid)”).

o   Continuous posture → discrete label (`fallen`, `standing`, `latched`).

·       **Degrade/ mask** for realism:

o   add noise,

o   simulate occlusion,

o   drop some variables entirely.

·       **Summarize**:

o   compress rich internal state into a fewpredicates/cues that are cognitively meaningful.

It does **not**:

·       addtemporal structure (that’s CCA8 attaching things in WorldGraph),

·       manageFOA or memory,

·       makedecisions about actions.



## Example in the newborn-goat world

Say EnvState this tick is:
    kid_posture      = fallen
    kid_position     = (0.0, 0.0)
    mom_position     = (0.7, 0.1)
    nipple_state     = hidden
    kid_temperature  = 0.45
    time_since_birth = 120 seconds

PerceptionAdapter might produce:
    raw_sensors:
      distance_to_mom = 0.71
      skin_temp       = 0.45
    predicates:
      posture(kid, fallen)
      near(mom, kid)           # because distance_to_mom < threshold_near
    cues:
      ["visual_mom_silhouette", "body_low_posture"]
    env_meta:
      {"time": 120.0, "distance_uncertainty": 0.05}

Then:

·       EnvObservationis handed to CCA8.

·       CCA8:

o   writes `posture(kid,fallen)` and `near(mom,kid)` intoWorldGraph with attach semantics,

o   wakes up any Columns that listen to `visual_mom_silhouette` or `body_low_posture`,

o   updates its internal beliefs and decides on thenext action.

PerceptionAdapter never sees WorldGraph; it only knows aboutEnvState→EnvObservation.

* * *

## Relationship to backends

Quick contrast:

·       **Backends**:  
“Given EnvState and an action, how does the _world itself_ evolve?”  
(script, physics, sensors, LLM events, reward…)

·       **PerceptionAdapter**:  
“Given EnvState _after those updates_, whatdoes the _agent_ get to see right now, and how is it encoded?”

Backends = **world dynamics & evaluation**.  
PerceptionAdapter = **world → sensors**.

Recap:

EnvState = environment’s canonical world,  
HybridEnvironment = coordinator/owner of EnvState + RL-style API,  
Backends = sub-engines that update/evaluate EnvState,  
PerceptionAdapter = EnvState → EnvObservation (what the agent senses).



**Agent–environmentinterface**

We adopt a Gymnasium-likeinterface for HybridEnvironment:

EnvObservation,info = HybridEnvironment.reset(seed, config)

EnvObservation,reward, done, info = HybridEnvironment.step(action, ctx)

* actionA structured representation of what the controller decided at this tick (e.g., high-level primitive such as "StandUp" or low-level motor commands in the future).
* ctx  
  The CCA8 context object, including temporal information; this allows environment dynamics to depend on agent-internal timing if desired.
* reward and done  
  Optional RL-style signals computed by MdpBackend. CCA8 can ignore them when operating in purely cognitive mode but they are available for RL experiments.

The **key invariant** is thatthis interface, and the structure of EnvObservation, remain stable as wereplace or augment backends. For CCA8, nothing changes whether the environmentis a tiny FSM, a high-end physics simulator, a robot, or some combination.

**EnvState:canonical environment state**

EnvState is a structuredrepresentation of “what is really going on.” For the newborn goat, examplefields might include:

* Discrete state:

* kid_posture ∈ {fallen, standing, latched, resting}

* mom_distance ∈ {far, near, touching}

* nipple_state ∈ {hidden, visible, reachable, latched}

* scenario_stage ∈ {birth, struggle, first_stand, first_latch, rest, ...}

* Continuous state:

* kid_position ∈ ℝ² or ℝ³

* mom_position ∈ ℝ² or ℝ³

* kid_fatigue ∈ [0, 1]

* kid_temperature ∈ [0, 1]

* time_since_birth (ticks or seconds)

* Optional additional fields:

* weather_state

* terrain_slope

* flags for exogenous events (e.g., presence of other animals).

EnvState is **not visible** to CCA8. It is manipulated only by the environment backends and consumed by thePerceptionAdapter.

**Back-endmodules**

**FsmBackend(finite-state/scripted environment)**

The FsmBackend encodes **discrete,high-level dynamics** of the environment. It is responsible for scriptedstorylines and simple branching logic.

API sketch:

FsmBackend.reset(env_state,config) -> env_state'

FsmBackend.propose_update(env_state,action) -> delta_state, events

For the newborn-goat scenario,FsmBackend would:

* Transition kid_posture from fallen to standing when a StandUp action succeeds.
* Move mom_distance from far to near as part of a scripted timeline, possibly modulated by how long the kid has been struggling.
* Update nipple_state to reachable after certain conditions are met.

In early phases, FsmBackend isthe **only** backend that changes EnvState; physics and sensors are absent.Over time, its role becomes more high-level and complementary to physics androbot backends.

**PhysicsBackend(physics/robotics simulator)**

PhysicsBackend is responsiblefor **continuous-time dynamics** and geometry:

PhysicsBackend.reset(env_state,config) -> env_state'

PhysicsBackend.step_dynamics(env_state,action, dt) -> env_state'

It updates fields such aspositions, velocities, and possibly low-level body configurations. Initially,this backend may be a simple kinematic model (e.g., 1D distance between kid andmom). Later, it can wrap a full physics simulator or a neural dynamics model.

PhysicsBackend must honordiscrete invariants set by FsmBackend (e.g., ensuring that kid_posture= standing translates to an upright pose).Conversely, FSM logic may consult physics-derived values (e.g., whether the kidhas actually closed the distance to the mother).

**MdpBackend(reward and termination)**

MdpBackend encodes the **taskdefinition** in RL terms:

MdpBackend.reset(env_state,config) -> mdp_state

MdpBackend.evaluate(env_state,action, env_state_next) -> reward, done, mdp_info

It never changes EnvState; itevaluates transitions to compute:

* Reward signals (e.g., positive reward for standing up within a time window, latching successfully, or staying warm).
* Termination flags (e.g., episode ends when the goat has latched and rested for a minimum duration).

This allows the same environmentto be used both for RL research and for cognitive experiments, withoutconflating environment dynamics with task evaluation.

**LlmBackend(LLM-driven environment)**

LlmBackend introduces **high-levelstochastic events** and scenario variation, rather than core physics:

LlmBackend.reset(env_state,config) -> env_state', narrative

LlmBackend.propose_exogenous(env_state,action, history) -> delta_state, narrative

Example uses include:

* Randomizing scenario parameters at reset (initial mom distance, weather, presence of obstacles).
* Introducing rare exogenous events during an episode (e.g., sudden cold wind lowering kid_temperature, appearance of another goat).
* Generating natural-language narratives or annotations for debugging.

Critically, LlmBackend is **not** responsible for per-tick physics updates. This avoids making core dynamicsopaque or non-deterministic, preserving testability and reproducibility whilestill leveraging LLMs where they are strongest.

**RobotBackend(real sensors)**

RobotBackend provides a bridgeto physical embodiments:

RobotBackend.reset(env_state,config) -> env_state'

RobotBackend.read_sensors(env_state,ctx) -> sensor_measurements

It:

* Reads real sensors (IMUs, cameras, encoders, temperature sensors, etc.).
* Updates or annotates EnvState fields that correspond to measurable quantities (e.g., posture, positions, temperature).
* Optionally outputs raw sensor tensors that are passed through EnvObservation.

In a **partial simulation /partial sensor** regime, RobotBackend owns some fields (e.g., kid posturefrom IMU), while others remain simulated (e.g., unobserved aspects of theenvironment). EnvState merging rules determine how these contributions arecombined each step.

** Fieldownership and merging**

Because multiple backends canpropose updates to EnvState, we define **field-level ownership** andprecedence. For example:

* kid_posture: owned by RobotBackend when available; otherwise, FsmBackend.
* kid_position, mom_position: owned by RobotBackend (via localization) or PhysicsBackend in pure sim.
* scenario_stage: owned by FsmBackend.
* weather_state: owned by LlmBackend or a dedicated environment module.

On each step, HybridEnvironment:

1. Starts from EnvState_t.
2. Applies FsmBackend updates for discrete fields it owns.
3. Applies PhysicsBackend dynamics for continuous fields it owns (subject to discrete constraints).
4. Applies RobotBackend sensor updates, overwriting fields it owns.
5. Applies LlmBackend exogenous updates for its fields.

This ensures that addingbackends does not introduce uncontrolled conflicts and that real sensorinformation takes precedence where appropriate.

** PerceptionAdapter:EnvState → EnvObservation → WorldGraph**

The PerceptionAdapter translatesEnvState into EnvObservation, and, indirectly, into WorldGraph updates. It:

* Converts physical quantities into **symbolic predicates**, e.g.:

* near(mom, kid) when distance below a threshold.

* posture(kid, fallen) when kid_posture = fallen.

* under(mom, kid) based on relative pose.

* Emits **cues** that route into CCA8’s feature and column subsystems.

* Passes through raw numeric sensor channels where needed (e.g., distances, images, proprioception).

* Optionally attaches **uncertainty meta-data**, especially when values are inferred from noisy sensors.

Because PerceptionAdapterdepends only on EnvState, it is agnostic to which backends produced that state.Upgrading from FSM-only to physics + sensors requires no changes on the CCA8side; only EnvState evolution and perception mapping become richer.



** Comparisonto existing RL and robotics frameworks**

The proposed architecture isdeliberately compatible with RL environment standards such as Gymnasium.HybridEnvironment’s reset/step interface and use of an observation structure plusreward align with these conventions, facilitating the use of RL algorithms ifdesired.

However, our design differs intwo key respects:

1. **Explicit internal world model separation**: CCA8 maintains its own WorldGraph, separate from EnvState, reflecting an agent-centric perspective similar to knowledge-based frameworks like KnowRob.
2. **Multi-backend orchestration**: Whereas typical RL environments are backed by a single simulator, our HybridEnvironment combines FSM, physics, LLM, and real sensor backends, giving a clearer path from toy simulations to real robotics.

The architecture also resonateswith work on multi-layer environment representations that connect low-levelsensory data to high-level semantic knowledge graphs, but we maintain a strictagent–environment boundary and treat the agent’s world model as separate fromthe “God’s-eye” environment state.

** Benefitsfor CCA8 and similar architectures**

For CCA8, the design offersseveral advantages:

* **Architectural stability over time**  
  CCA8’s interaction with the world is fixed in terms of EnvObservation and actions. As we move from a simple newborn-goat storyboard to real robot control, the internal environment implementation can change extensively without affecting CCA8’s core code.
* **Gradual fidelity increase**  
  Development can start with a minimal FsmBackend for a deterministic, interpretable newborn scenario, then incorporate PhysicsBackend, MdpBackend, and RobotBackend in stages.
* **Support for hybrid sim + real sensing**  
  By defining field ownership and merge rules, we can cleanly combine partial real sensors with simulated aspects. This is particularly useful during incremental robot bring-up and for “shadow mode” evaluation where a simulated environment runs alongside a physical system.
* **Cognitive plausibility and analysis**  
  Because CCA8 never sees EnvState directly, but only EnvObservation-derived predicates and cues, we can study how its internal WorldGraph evolves in response to sensor-like inputs. This aligns with conceptualizations of world models as internal, compressed, and simulatable representations distinct from external reality.

** Role ofLLMs and limitations**

LLM-based environments and worldmodels are powerful but raise concerns around determinism, grounding, andhidden assumptions. By confining LlmBackend primarily to high-level, exogenousevents and scenario generation, we:

* Preserve a well-specified core dynamics model (FSM + physics + sensors).
* Retain the ability to do reproducible experiments by disabling LlmBackend or constraining its use.
* Still benefit from LLM capabilities in scenario design, parameter sampling, and narrative explanation.
  
  
  
  
  
  

# Tutorial on Environment Module Technical Features

> Note: Code will evolve over time, but the core ideas in this section should remain stable for the project. (Nov 2025 – HS)

## 1. Purpose and mental model

The **Environment module** (`cca8_env.py`) is the *world side* of CCA8. It simulates the **external environment** the agent lives in (ground, 3D space, time, mom goat, weather), while the main CCA8 modules simulate the **brain + body** (WorldGraph, controller, columns, features, temporal context). 

The key separation is:

* **EnvState** – “God’s-eye” world state as the environment subsystem believes it.
* **EnvObservation** – the sensory/perceptual packet the world sends to the agent each tick.
* **WorldGraph / Columns / Engrams** – the agent’s internal beliefs and memories. 

CCA8 never reads `EnvState` directly. It only sees `EnvObservation` and then decides what to write into the WorldGraph and Columns.

---

## 2. Public API (what you import)

From `cca8_env.py` you typically import: 

```python
from cca8_env import (
    EnvState,
    EnvObservation,
    EnvConfig,
    FsmBackend,
    PerceptionAdapter,
    HybridEnvironment,
)
```

* **EnvState** – canonical environment state (posture, mom distance, nipple state, positions, fatigue, temperature, time_since_birth, step_index).
* **EnvObservation** – one-tick observation packet (`raw_sensors`, `predicates`, `cues`, `env_meta`).
* **EnvConfig** – scenario/config knobs (`scenario_name`, `dt`, which backends are enabled). 
* **FsmBackend** – finite-state / scripted backend implementing the newborn-goat storyboard over `EnvState`.
* **PerceptionAdapter** – converts `EnvState → EnvObservation` (sensor interface).
* **HybridEnvironment** – orchestrator that owns `EnvState`, calls backends, and exposes a Gym-like `reset`/`step` API.

---

## 3. EnvState and EnvObservation

### 3.1 EnvState — canonical world state

`EnvState` is a `@dataclass` representing the **ground-truth environment state** for the newborn-goat vignette:

* **Discrete:**
  
  * `kid_posture ∈ {"fallen", "standing", "latched", "resting"}`
  * `mom_distance ∈ {"far", "near", "touching"}`
  * `nipple_state ∈ {"hidden", "visible", "reachable", "latched"}`
  * `scenario_stage ∈ {"birth", "struggle", "first_stand", "first_latch", "rest"}`

* **Continuous-ish:**
  
  * `kid_position: tuple[float, float]`
  * `mom_position: tuple[float, float]`
  * `kid_fatigue: float` (0..1)
  * `kid_temperature: float` (0..1)
  * `time_since_birth: float` (seconds or ticks, as long as consistent)

* **Bookkeeping:**
  
  * `step_index: int` – environment steps in this episode.

Only `HybridEnvironment` and backends mutate `EnvState`; CCA8 never touches it directly.

---

### 3.2 EnvObservation — one-tick sensory/perceptual packet

`EnvObservation` is what crosses the agent–environment boundary each tick:

```python
@dataclass
class EnvObservation:
    raw_sensors: dict[str, Any]
    predicates: list[str]
    cues: list[str]
    env_meta: dict[str, Any]
```

* **`raw_sensors`** – numeric/tensor channels (e.g., `distance_to_mom`, `kid_temperature`).
* **`predicates`** – discrete tokens suitable for WorldGraph (e.g., `posture:fallen`, `proximity:mom:close`, `nipple:latched`, `milk:drinking`).
* **`cues`** – cue tokens for features/columns (e.g., `vision:silhouette:mom`, `drive:cold_skin`).
* **`env_meta`** – small metadata (e.g., `{"time_since_birth": ..., "scenario_stage": ...}`).

These are **observations**, not beliefs. WorldGraph and Columns are where CCA8 turns them into internal state and memory.

---

## 4. HybridEnvironment — orchestrator and RL-style seam

`HybridEnvironment` is the **central hub** on the environment side. It owns `EnvState` and presents a Gym-like API:

```python
env = HybridEnvironment(config=EnvConfig())
obs, info = env.reset(seed=None, config=None)
obs, reward, done, info = env.step(action, ctx)
```

**Reset**

* Create a fresh `EnvState`.
* Call `FsmBackend.reset(env_state, config)` to set initial posture, mom distance, nipple state, stage, fatigue, temperature, positions.
* Call `PerceptionAdapter.observe(env_state)` to build the first `EnvObservation`.
* Return `(obs, info)` to the caller.

**Step**

* Increment `episode_steps` and copy that into `EnvState.step_index`.
* Advance `time_since_birth` by `config.dt`. 
* Call `FsmBackend.step(env_state, action, ctx)` to update the discrete storyboard (birth → struggle → first_stand → first_latch → rest).
* (Future) call physics/robot/LLM/MDP backends in a defined order.
* For now, set `reward = 0.0`, `done = False` (RL slots are owned by a future `MdpBackend`). 
* Call `PerceptionAdapter.observe(env_state)` again to produce the new `EnvObservation`.
* Return `(obs, reward, done, info)`.

From CCA8’s point of view, **HybridEnvironment *is* “the environment”**: there is one object that speaks `reset`/`step` and hands back observations, reward, and done.

---

## 5. FsmBackend — newborn-goat storyboard

`FsmBackend` is the first concrete backend. It implements a tiny **hand-scripted storyboard** over `EnvState` for the newborn goat’s first minutes:

* **Stages**
  
  * `"birth"` → `"struggle"` → `"first_stand"` → `"first_latch"` → `"rest"`.

* **Time thresholds** (in environment steps) drive the default progression:
  
  * `_BIRTH_TO_STRUGGLE = 3`
  * `_STRUGGLE_MOM_NEAR = 5`
  * `_AUTO_STAND_UP = 8`
  * `_AUTO_NIPPLE_REACHABLE = 11`
  * `_AUTO_LATCH = 13`
  * `_AUTO_REST = 16`

* **Within each stage**, `step(env_state, action, ctx)`:
  
  * Sets `kid_posture`, `mom_distance`, `nipple_state`, and `scenario_stage` according to the storyboard.
  * Treats actions like `"policy:stand_up"` and `"policy:seek_nipple"` as **accelerators** (e.g., standing earlier than the auto threshold, nipple reachable/latching earlier once seeking).
  * Applies small drifts to `kid_fatigue` and `kid_temperature` to give PerceptionAdapter interesting signals.

FsmBackend **never** writes to the WorldGraph; it only updates `EnvState`.

---

## 6. PerceptionAdapter — world → EnvObservation

`PerceptionAdapter` is the environment’s **sensor interface**. It answers:

> “Given this EnvState, what does the agent get to sense this tick, and how is it encoded?”

In `observe(env_state)` it:

* Computes `distance_to_mom` and other scalar channels, stores them in `raw_sensors`.

* Maps posture:
  
  * `"fallen"` → `posture:fallen`
  * `"standing"` or `"latched"` → `posture:standing`
  * `"resting"` → `resting` (today; could later add `posture:resting`).

* Maps mom distance:
  
  * `"near"` / `"touching"` → `proximity:mom:close`
  * `"far"` → `proximity:mom:far`.

* Maps nipple state:
  
  * `"visible"` / `"reachable"` → `nipple:found`
  * `"latched"` → `nipple:latched` + `milk:drinking`.

* Emits simple **cues**:
  
  * mom near/touching → `vision:silhouette:mom`
  * low temperature → `drive:cold_skin`.

* Populates `env_meta` with `time_since_birth` and `scenario_stage`.

PerceptionAdapter knows nothing about WorldGraph or policies; it just turns `EnvState` into `EnvObservation`.

---

## 7. Runner handshake and Menu Selection Envr't Step (HybridEnvironment-->WorldGraph demo) closed-loop demo

The **Runner module** (`cca8_run.py`) owns the *full* simulation loop (menu, WorldGraph, controller, drives, `Ctx`). The environment module plugs in as one component of that loop. 

### 7.1 Where HybridEnvironment is created

In `interactive_loop(args)`, after `world`, `drives`, and `ctx` are created and the temporal soft clock is initialized, the runner instantiates the environment:

```python
world = cca8_world_graph.WorldGraph()
drives = Drives()
ctx = Ctx(...)
ctx.temporal = TemporalContext(...)
...
env = HybridEnvironment()
```

So `env` and `ctx` sit side-by-side in the main loop.

---

### 7.2 Menu Selection — “Environment step (HybridEnvironment → WorldGraph demo)”

This Menu Selection is a **one-step closed-loop demo** that ties together HybridEnvironment, WorldGraph, the controller, and timekeeping. 

When you choose this menu selection, the runner:

1. **Prints a guide**
   Explains the meaning of `[env]`, `[env→world]`, and `[env→controller]` lines:
   
   * `[env]` – summary of what the environment just did (reset vs step, stage, posture, mom distance, nipple state, action).
   * `[env→world]` – how `EnvObservation` was injected into the WorldGraph as `pred:*` and `cue:*`.
   * `[env→controller]` – which policy the controller fired in response (if any); a policy like `policy:stand_up` then writes its own S–A–S chain (actions and a standing predicate). 

2. **Advances internal time (soft clock + controller_steps)**
   
   * `ctx.controller_steps += 1`.
   * If `ctx.temporal` exists, it calls `ctx.temporal.step()` once (soft temporal drift).
   * Autonomic ticks (`ctx.ticks`) and `age_days` are **not** changed by this menu selection; they belong to the autonomic tick menu. 

3. **Environment evolution**
   
   * **First call** – if `ctx.env_episode_started` is `False`:
     
     ```python
     env_obs, env_info = env.reset()
     ctx.env_episode_started = True
     ctx.env_last_action = None
     print(f"[env] Reset newborn_goat scenario: episode_index={...} scenario={...}")
     ``` :contentReference[oaicite:35]{index=35}  
     
     This starts a fresh newborn-goat episode at the `"birth"` stage with `kid_posture="fallen"`, `mom_distance="far"`, `nipple_state="hidden"`.   
     
     ```
   
   * **Subsequent calls** – feed the last fired policy back into the environment:
     
     ```python
     action_for_env = ctx.env_last_action   # e.g., "policy:stand_up" or None
     env_obs, _reward, _done, env_info = env.step(action=action_for_env, ctx=ctx)
     ctx.env_last_action = None
     st = env.state
     print(f"[env] step={env_info['step_index']} stage={st.scenario_stage} "
           f"posture={st.kid_posture} mom_distance={st.mom_distance} "
           f"nipple_state={st.nipple_state} action={action_for_env!r}")
     ```
     
     This is where `FsmBackend` can treat `policy:stand_up` or `policy:seek_nipple` as early hints and accelerate the storyboard.

4. **Environment → WorldGraph (observation injection)**
   For each predicate in `env_obs.predicates`:
   
   ```python
   bid = world.add_predicate(
       token,
       attach=attach,  # first "now", then "latest"
       meta={"created_by": "env_step", "source": "HybridEnvironment"},
   )
   print(f"[env→world] pred:{token} → {bid} (attach={attach})")
   attach = "latest"
   ``` :contentReference[oaicite:39]{index=39}  
   
   For each cue in `env_obs.cues`:
   
   ```python
   bid_c = world.add_cue(
       cue_token,
       attach=attach_c,  # first "now", then "latest"
       meta={"created_by": "env_step", "source": "HybridEnvironment"},
   )
   print(f"[env→world] cue:{cue_token} → {bid_c} (attach={attach_c})")
   attach_c = "latest"
   ``` :contentReference[oaicite:40]{index=40}  
   
   This stamps the environment’s current view (posture, proximity, nipple state, visual cue) into the WorldGraph as ordinary `pred:*` and `cue:*` bindings, tagged with `source="HybridEnvironment"` for provenance.
   
   ```

5. **WorldGraph → Controller → Env (action feedback)**
   After injection, the runner gives the controller one decision step:
   
   ```python
   POLICY_RT.refresh_loaded(ctx)
   fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
   if fired != "no_match":
       print(f"[env→controller] {fired}")
       # extract "policy:..." from the first token of the summary string
       ctx.env_last_action = first_token_if_policy(fired)
   else:
       ctx.env_last_action = None
   ``` :contentReference[oaicite:41]{index=41}  
   
   The next time you choose this menu selection, `ctx.env_last_action` is passed into `env.step(...)` as `action`, allowing `FsmBackend` to react (e.g., treat `policy:stand_up` as standing earlier during `"struggle"`).   
   
   ```

6. **Discrepancy diagnostics (posture expectation vs observation)**
   The mini-snapshot printed after this menu selection includes a **diagnostic line** when the latest environment posture and the latest **policy-expected** posture disagree.
   Internally, the runner:
   
   * Finds the newest env-driven `pred:posture:*` (with `meta["source"] == "HybridEnvironment"`).
   
   * Finds the newest policy-written `pred:posture:*` (with `meta["policy"]` set, e.g., by `policy:stand_up`). 
   
   * If they differ (e.g., env says `fallen` but the last StandUp invocation wrote `standing`), it prints:
     
     ```text
     [discrepancy] env posture='fallen' at b18 vs policy-expected posture='standing'
                  from policy:stand_up at b22
     [discrepancy] -often the motor system will attempt an action, but it does not actually occur-
     ```
   
   * It also keeps a short **discrepancy history** (last ~50 entries) in `ctx.posture_discrepancy_history` and prints it under:
     
     ```text
     [discrepancy history] recent posture discrepancies (most recent last):
       [discrepancy] ...
     ``` :contentReference[oaicite:44]{index=44}  
     ```
   
   These lines are **display-only diagnostics**; they do not create additional bindings. They are meant to mirror a robotics / physiology intuition:
   
   > *The motor system may “intend” standing, but sensors still report a fallen posture until the environment actually transitions.*

Putting it all together, this menu selection implements a minimal closed loop:

```text
world dynamics (HybridEnvironment/FsmBackend)
  → EnvObservation (predicates + cues)
  → WorldGraph update + one controller step
  → policy name (e.g., "policy:stand_up")
  → fed back into HybridEnvironment.step(...) on the next call of this menu selection
```

---

## 8. Debugging and tests

* Running `python cca8_env.py` exercises the **environment module alone** via a small debug driver under `if __name__ == "__main__":`. It prints a tabular trace of `step_index`, `scenario_stage`, `kid_posture`, `mom_distance`, `nipple_state`, `kid_temperature`, `kid_fatigue`, and the predicates PerceptionAdapter generated at each step. 

* `tests/test_cca8_env.py` covers: 
  
  * storyboard progression over multiple `env.step(action=None, ctx=None)` calls (key milestones at steps 0, 3, 5, 8, 11, 13, 16);
  * PerceptionAdapter outputs (`predicates`, `cues`, `raw_sensors`, `env_meta`) for a constructed `EnvState`.

These tests make it easy to verify that changes to the storyboard or perception mapping do what you expect before you wire them through the full CCA8 loop.



### Q&A to help you learn this section

Q: What’s the difference between EnvState and EnvObservation?
A: EnvState is the environment’s canonical ground-truth state (God’s-eye view), maintained by HybridEnvironment and its backends. EnvObservation is the sensory/perceptual packet the agent receives each tick (derived from EnvState by PerceptionAdapter). CCA8 never reads EnvState directly; it only sees EnvObservation.

Q: How does HybridEnvironment relate to WorldGraph?
A: HybridEnvironment lives on the environment side and knows nothing about WorldGraph. It owns EnvState, runs reset/step, and produces EnvObservation + reward/done/info. WorldGraph is purely agent-side; it ingests EnvObservation and maintains the agent’s internal beliefs/memories.

Q: What does FsmBackend actually do in the newborn-goat vignette?
A: It implements a small, hand-scripted storyboard over EnvState: stages birth → struggle → first_stand → first_latch → rest, time thresholds for automatic transitions, and optional acceleration when certain policies fire (e.g., treating "policy:stand_up" as an early stand trigger during struggle).

Q: What is the role of PerceptionAdapter?
A: PerceptionAdapter is the environment’s sensor interface. Given EnvState, it produces EnvObservation by:

filling raw_sensors (e.g., distances, temperatures),

mapping state into symbolic predicates (posture, proximity, nipple state),

emitting cues (e.g., vision:silhouette:mom, drive:cold_skin), and

including small env_meta. It does not update WorldGraph or the agent; it just describes what the agent gets to sense this tick.

Q: How does Menu “Environment step (HybridEnvironment → WorldGraph demo)” use all this?
A: That menu item runs a single closed-loop tick:

HybridEnvironment evolves EnvState via reset or step(action, ctx).

PerceptionAdapter produces EnvObservation.

The runner injects predicates/cues into the WorldGraph.

The controller runs one policy step and records which policy executed.

The chosen policy name is fed back as the next action into HybridEnvironment on the following env-step.

It’s a minimal “world ↔ brain” loop for inspection and debugging.



---







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









# Persistence contract

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





# REFERENCES AND NOTES

# References



Schneider, H., Navigation Map-Based Artificial Intelligence -- [Navigation Map-Based Artificial Intelligence](https://www.mdpi.com/2673-2688/3/2/26)

Schneider, H., The Emergence of Enhanced Intelligence in a Brain-Inspired Cognitive Architecture -- [Frontiers | The emergence of enhanced intelligence in a brain-inspired cognitive architecture](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1367712/full)



Tresp, V. et al., Tensor Brain -- [[2109.13392] The Tensor Brain: A Unified Theory of Perception, Memory and Semantic Decoding](https://arxiv.org/abs/2109.13392)









# Developer and Maintainer Notes



## Development Phases

This section summarizes how the CCA8 codebase has been evolving. It is mainly for future maintainers and contributors.

**Phase I – Core kernel and newborn goat skeleton**  

- Stand up `cca8_run.py` (runner), `cca8_world_graph.py` (WorldGraph), `cca8_controller.py` (drives + policies), `cca8_column.py` (engrams), and `cca8_temporal.py` (timekeeping).  
- Implement a minimal newborn mountain-goat profile: bindings/edges, drives, primitive policies, autosave/load, and the CLI runner.

**Phase II – Testing, preflight, and documentation spine**  

- Add the pytest suite, coverage reporting, and the four-part `--preflight` self-test (unit tests + whole-flow probes).  
- Grow this README into the main “compendium” for CCA8: overview, architecture, tutorials, contracts, and glossary.

**Phase III – Representation and tagging cleanup**  

- Standardize tag families (`pred:*`, `action:*`, `cue:*`, `anchor:*`) and introduce the stage-aware restricted lexicon.  
- Move to explicit `action:*` bindings and state–action–state (S–A–S) chains; deprecate legacy `state:*` and `pred:action:*` patterns.  
- Clarify NOW / NOW_ORIGIN / LATEST semantics and tighten provenance/meta fields on bindings and edges.

**Phase IV – Timekeeping, environment, and BodyMap**  

- Introduce the TemporalContext “soft clock” and the five time measures (controller steps, temporal drift, autonomic ticks, developmental age, cognitive cycles).  
- Implement the newborn-goat storyboard environment: `EnvState`, `EnvObservation`, `FsmBackend`, `PerceptionAdapter`, and `HybridEnvironment`.  
- Add BodyMap as a small body-centred graph (posture, mom distance, nipple/nursing state, shelter/cliff) with controller helpers.

**Phase V – RCOS framing and operator tools (current)**  

- Present CCA8 as a Robotic Cognitive Operating System (RCOS) kernel and stabilize the runner / CLI experience.  
- Extend preflight probes, snapshot/inspect views, BodyMap panels, and spatial “NOW-near” overlays to make internal state easy to audit.  
- Polish logging, menu wording, and documentation so new users can reproduce the newborn-goat demo and understand how the system fits together.
  
  

## Future Development Phases

**Future phases** will extend spatial reasoning, multi-brain / multi-agent profiles,
learning, and Theory-of-Mind modules on top of this base. (At the time of writing,
November 2025 these are still design-stage.)


### Future Phase  – Two-Stream Processing (Ventral “what” / Dorsal “where/how”) + Binding Hub (design-stage)

Evidence suggests the dorsal/ventral “two-stream” split is a conserved motif across vertebrate lineages, and is not
a primate-only quirk. In other words: for a goat-like agent, a dorsal **action/spatial** stream and a ventral
**identity/recognition** stream are likely part of the baseline architecture, not an optional “human upgrade”.

**Design intent for CCA8:** keep “what” and “where” representations separate through at least one tier, then
introduce an explicit *binding* mechanism (a heteromodal “hub”) that can combine them when the task truly
requires it. This keeps integrated identity+location queries *explicit* (and therefore measurable), and preserves a
workspace for symbolic relations instead of pre-binding everything into one structure.

#### Mapping to existing CCA8 concepts

- **Dorsal / “where-how”** (fast, body-centred, action-guiding):
  - BodyMap (`ctx.body_world`) already functions like a tiny dorsal register (posture, mom distance, nipple state,
    shelter/cliff safety slots).
  - The “NOW-near” scene-graph overlays (spatial neighbors) are also dorsal-leaning.

- **Ventral / “what”** (slower, feature-rich, invariant identity):
  - A future *FeatureMap / ObjectMap* should hold object identity representations and richer perceptual engrams.
  - This can live as a separate WorldGraph-like structure or as a dedicated engram store (column) indexed by stable
    object IDs.

- **Binding hub / heteromodal workspace**:
  - A future binder should explicitly link a ventral identity token to a dorsal location / affordance context.
  - In CCA terms, this can be represented as either:
    - a dedicated binding record (cross-index table), and/or
    - a small “binding episode” node in the main WorldGraph whose role is to *relate* the two streams.

#### Operational rule of thumb (simulation + engineering)

1. **Default: don’t collapse streams early.**
   - Policies that require fast action should read mostly dorsal state (BodyMap + near-world).
   - Perceptual learning and semantic enrichment should write mostly ventral state (FeatureMap/ObjectMap).

2. **Make binding an operator, not an accidental side effect.**
   - Add an explicit API (future) such as:
     - `bind(what_id, where_id, *, t, confidence, source="...")`
   - Treat each bind as a first-class event (loggable, inspectable, testable).

3. **Exploit parallelism.**
   - Dorsal and ventral updates should be able to run concurrently (ideally separate OS processes).
   - This is aligned with the existing multi-brain scaffolding: “parallelism note: farm processors to separate OS
     processes” (see cca8_run.py narrative scaffolds).

4. **Instrument query mix.**
   - Track how often the agent needs integrated “what+where” binding versus stream-local queries.
   - This will let us validate whether the simulation is operating in a “two-stream-beneficial” regime, and where to
     spend optimization effort (binder vs caches).

#### Concrete future work items

- Add `ctx.ventral_world` (or `ctx.feature_world`) alongside BodyMap, with a minimal vocabulary for object IDs and
  feature tags.
- Add a `cca8_binding.py` (or similar) module that defines:
  - a binding record schema, plus
  - simple binding/unbinding operations, plus
  - debug printouts (so we can see the workspace forming).
- Add a micro-benchmark / probe in `--preflight` that:
  - creates N objects with (what, where),
  - runs a controlled mix of what-only / where-only / integrated queries,
  - reports the measured ratios and timing (for regression tracking).
