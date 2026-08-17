# CCA8  — Project Documentation -- Compendium (README.md)



Questions?  Send me an email: hschneidermd [at] alum [dot] mit [dot] edu

NOTE: This README is large; if GitHub truncates the preview at the 512 KiB render limit, open the file directly to view the full document.


Software was developed in a Windows environment but should run with minimal changes in a macOS or Linux environment.
Requires Python 3.11
Please contact hschneidermd [at] alum [dot] mit [dot] edu for inquiries about additional software modules, related
 materials, or ongoing development.

Architecture and migration authority: `CCA8_Project_Planning_v11.pdf`. The local source tree, tests, and traces remain authoritative for what actually runs.


# Executive Overview

## **TL;DR == Run code**

Requirements:
- Python 3.11
- All root-level `cca8_*.py` production modules in the same repository directory
- Optional: unit-test files in the `tests/` directory (used by `--preflight`)
- Python standard-library modules are included with a normal Python installation
- Optional/development dependencies are listed in `requirements.txt`
- OpenAI access is optional; core CCA8 execution and preflight do not require an API account

Use `python cca8_run.py --about` to display the canonical component registry, module versions, and source paths for the exact checkout being run.

Recommended fresh Windows setup (in terminal):

>py -m pip install -r requirements.txt

>python cca8_run.py --preflight

>python cca8_run.py




## **TL;DR == One-minute summary**

● **Simulates a mammalian brain**

*The CCA8 project simulates a mammalian brain inspired by a mountain goat across its lifecycle, used as a testbed for a navigation map-based theory of mammalian brain evolution and function. It aims to: (1) model the goat-level map substrate from which later architectures may explore human capacities such as full causal reasoning, full analogical reasoning, and partially compositional language; (2) offer a candidate mechanistic account of mammalian cognition; and (3) explore in-model evolution and mechanisms of psychotic and autistic disorders in later human-like architectures (no clinical claims). CCA8 itself remains goat-level; later profiles are developmental roadmaps or scaffolds rather than implemented human cognition.*


● **Robotic Cognitive Operating System (RCOS)**

*The CCA8 project also creates a flexible kernel of a Robotic Cognitive Operating System (RCOS):*
 - Agent behavior layer
 - CCA8 RCOS kernel <--
 - Robot middleware layer (e.g., ROS 2)
 - Hardware Abstraction Layer (HAL)
 - Low-Level OS / firmware (e.g., Linux, an RTOS, or a PetitCat-style minimal middleware/OS)
 - Hardware Layer
 
*CCA8 as RCOS = a cognitive supervisory runtime that organizes goals, memory, world models, and recovery around embodied controllers, rather than pretending that high-level intelligence alone solves robotics*



## **TL;DR == Theoretical framing**

CCA8 tests a **Map Primacy** hypothesis: ordinary mammalian cognition is organized primarily through Navigation Maps, not through a
large collection of independent symbolic state variables. Compact predicates, scores, and states remain useful, but they should normally
be physiological/control signals, derived readouts of a named map revision, or software bookkeeping. They should not quietly become a
second world model.

The principal cognitive product is one accepted root **Working Navigation Map (WNM)** with explicitly linked submaps at appropriate
scales and reference frames. The root may link to body/posture, maternal, nipple, terrain, hazard, shelter, object, and route maps. A linked
submap can become the focus of attention without becoming a second equally authoritative reality.

A CCA8 Navigation Map is a bounded, addressable, spatially organized and relationally linked representation of some part of the goat's
body, environment, object world, action possibilities, or learned experience. It preserves geometry, topology, boundaries, containment,
direction, distance, connectivity, motion, uncertainty, provenance, and relation to SELF. Graph operations are useful within and among
maps, but a NavMap is not merely a generic graph because frame, scale, geometry, modality, and spatial embedding are first-class.

Long-term memory participates in constructing each WNM. **WorldGraph** is the sparse indexing and retrieval structure that helps answer
"where should I look?" **Columns** hold the rich stored Local NavMaps, prototypes, trajectories, transformations, and episodes that answer
"what is stored there?" Retrieved content remains a prior or candidate until it is aligned, compared with reliable current evidence, and
explicitly accepted.

CCA8 is a newborn-goat architecture. It uses a CCA2/CCA3-like mammalian substrate: spatial and temporal binding, one current map,
long-term map matching, primitives operating on maps, strong embodied prediction, and rich pre-causal behavior. It does **not** normally
include CCA4-style analogical transformation-transfer, sustained recursive internal causal processing, or a separate language
architecture. Human-readable labels in terminal output are names for developers, not evidence that the goat internally speaks English.

CCA8 is **quasi-predictive-coding-like** because expected maps are compared with evidence maps and structured residuals guide revision,
attention, learning, and protection. It is **quasi-active-inference-like** because the goat acts both to satisfy drives and to obtain better
evidence. It is not presently a formal variational free-energy or expected-free-energy policy-selection system.

The robotics interpretation is parallel. CCA8/RCOS selects and supervises map-grounded intents; lower HAL, ROS 2, vendor, VLA, firmware,
and motor-control systems implement the detailed movement. World models and LLMs may propose or rehearse, but they cannot directly
write observed evidence, the accepted WNM, protected memory, or actuators. Whether the NavMap paradigm improves neuroscience
explanation, robotics, agentic AI, or LLM synergy remains an experimental question rather than an established claim.


## **TL;DR == Current runnable NavMap predictive path**
**THIS SECTION IS UPDATED PERIODICALLY**

The current runner contains a visible, read-only NavMap predictive-processing path. It is deliberately a diagnostic path first: it does not
yet drive ordinary policy selection, replace the live WorkingMap, become WorldGraph truth, or write accepted NavMaps into Columns.

The present signal path is:

    EnvObservation
        -> evidence NavMap

    previous scene_body map + selected primitive / context
        -> expected-current NavMap

    expected-current NavMap <-> evidence NavMap
        -> structured predictive residual

    evidence-first comparison
        -> accepted-current NavMap diagnostic

    previous map + action + current map
        -> action-conditioned transition
        -> policy-outcome sample / policy-outcome index

    all probes
        -> NavMap Oscilloscope

Current design rules:

- Expected and retrieved maps are priors, not observations.
- Direct evidence remains authoritative in the current diagnostic comparison.
- The accepted-current diagnostic currently copies the evidence payload while recording confirmation, adjustment, context-shift, or
  context-break labels.
- Reliable conflicting evidence is recorded rather than overwritten by expectation.
- `working_navmap_surface_v1` is a non-writing bridge surface. It is not policy authority, WorldGraph truth, or Column-write authority.

**Current implementation versus target architecture**

- **Current implementation:** authority remains distributed across BodyMap, observation-driven WorkingMap/MapSurface, SurfaceGrid and
  NavSummary, WorldGraph history, retrieval hints, drives, policy bridges, and the controller. The accepted-current NavMap is a shadow.
- **Target architecture:** one accepted root WNM becomes the principal current world representation. MapSurface, SurfaceGrid,
  NavSummary, predicates, and most BodyMap-facing values become named projections or synchronized readouts of a specific WNM
  revision, while BodyMap retains a fast independent safety path.
- **Migration rule:** legacy and WNM-derived paths run in shadow/compare/dual-run before any authority is promoted. The README must not
  describe future authority as though it already controls the goat.

**Authoritative August 2026 baseline**

- Git commit: `71ab4dc` (`Refactor policy runtime out of runner`)
- Python: 3.11.4
- Runner: `cca8_run.py` v0.9.7
- Pylint on the runner: 10.00/10
- Mypy on the runner: no issues
- Preflight: PASS
- Unit tests: 505/505
- Coverage: 46%
- Architecture probes: 80/80
- Hardware/robotics host checks: 5/5
- System fitness: 1 pass, 0 warnings, 0 failures

The NavMap Oscilloscope marker in terminal output is:

    (~~) [navmap-scope] ...

It should be interpreted as high-impedance instrumentation over the current path, not as evidence that the target WNM authority migration
is complete.


## **TL;DR == Five-minute summary**

● **What CCA8 is**

CCA8 is a simulation of a brain inspired by a mountain goat across its lifecycle. It is a testbed for the hypothesis that mammalian cognition
is organized around Navigation Maps and one continuously reconstructed Working Navigation Map rather than around a large symbolic
state table.

The current software is not yet a complete implementation of that hypothesis. It already contains many of the required parts, but Phase 0
showed that behavior is still controlled by a committee of BodyMap, WorkingMap, NavSummary, WorldGraph, hints, drives, prediction
histories, and policy logic while the accepted-current NavMap remains diagnostic. The development programme therefore reorganizes
existing authority gradually instead of performing a wholesale rewrite.

● **Scientific and evolutionary hypothesis**

The working evolutionary hypothesis is that spatially organized sensorimotor representations are extremely ancient; the vertebrate
lineage elaborated topographic sensory, body, motor, heading, boundary, and environmental maps; the common amniote possessed an
active integrated world/navigation map; and mammalian neocortex supplied a vastly richer distributed library of maps that medial-pallial/
hippocampal-like systems could index and retrieve.

In the modern CCA8 decomposition:

    Columns
        = rich long-term map library

    WorldGraph
        = sparse indexing, episode, and retrieval structure

    accepted root WNM
        = one current authorized map assembled from evidence, memory, context, and prediction

The historical CCA paper numbers are not a phylogenetic ladder. CCA8 uses mechanisms wherever they are biologically appropriate. For
the goat this means spatial and temporal binding, memory matching, one current map, primitives acting on maps, and weak/pre-causal
behavior. CCA4 analogical feedback, sustained recursive causal processing, and compositional language are deferred.

● **What makes a NavMap different from a state table**

A compact record such as `posture=fallen`, `mom_distance=far`, and `cliff_near=true` is useful for implementation. The architectural
question is whether those values are derived from a richer map or have silently replaced it. The NavMap should preserve the relationships
among SELF, body, terrain, objects, motion, uncertainty, affordances, and memory. A policy can derive a distance or boolean from the map
without making that scalar the goat's complete cognition.

● **The intended goat loop**

    sensory evidence + temporal binding + bounded long-term retrieval
        -> modality and scene candidates
        -> one accepted root WNM with linked submaps
        -> derived readouts and map-native primitive queries
        -> bounded action intent
        -> lower automatic motor implementation
        -> new evidence
        -> map comparison, revision, and selective learning

The goat can be highly capable through map matching, retrieval, short expected transformations, attention, Probe, and embodied action
without becoming a small human.

● **Quasi-predictive coding and quasi-active inference**

CCA8 predicts expected current or successor maps and compares them with evidence maps. Structured residuals guide map revision,
attention, retrieval, protection, and learning. The goat also acts to change its situation and sometimes to gather information. These are
predictive-coding-like and active-inference-like functions, but CCA8 is not presently a formal free-energy-minimization or EFE-selection
implementation.

● **RCOS and the motor boundary**

CCA8 also serves as the kernel of a Robotic Cognitive Operating System:

- Agent behavior layer
- CCA8 RCOS cognitive-supervisory kernel
- Robot middleware, skill providers, or ROS 2
- Hardware Abstraction Layer
- Low-level OS / firmware
- Hardware

CCA8 chooses and supervises interpretable intents. Lower systems handle force control, balance, trajectories, actuator timing, slip,
contact, and other automatic motor implementation. CCA8 receives the temporal products needed for cognition: progress, completion,
contact, motion, rate, error, and safety.

The governing rule remains:

    World models rehearse.
    LLM / VLA proposes.
    CCA8 validates against the accepted map and protected constraints.
    HAL executes.
    Reality corrects.
    CCA8 records provenance.

● **Experimental status**

The NavMap theory may provide a flexible brain-like system, a useful RCOS/agentic architecture, or meaningful synergy with LLMs. It may
also provide little advantage over state-first, graph-first, or other systems. The project therefore aims first to implement the hypothesis
faithfully and then compare map-first and state-first architectures, operator ablations, memory designs, surprise mechanisms, and LLM
integration under controlled experiments.

● **Documentation role**

This README is the canonical project compendium: user guide, architecture explanation, implementation-status record, technical tutorial,
and maintainer reference. Planning v11 is the current architecture and migration authority; the local source tree and tests remain the
authority for what actually executes.

**Repo:** `https://github.com/howard8888/workspace`  
**Entry point:** `python cca8_run.py`


### CCA8 Versions


- CCA8 Simulation of a mountain goat through the lifecycle
- CCA8_Bringup  Robotic Cognitive Operating System with CCA8 controlling PetitCat or ROS 2-based hardware
- CCA8b Simulation of a mountain goat-like brain with 5 brains within the same agent
- CCA8c Simulation of multiple agents with goat-like brains able to interact
- CCA8d Simulation of a mountain goat-like brain with 5 brains within the same agent with combinatorial planning
- CCA9 Simulation of a chimpanzee through the lifecycle
- CCA10 Simulation of a human through the lifecycle
- CCA11 One coherent superhuman mind with governed cognitive plurality
- CCA12 Governed pod of complete CCA11 cognitive architectures
- CCAx_Bringup  Robotic Cognitive Operating System with CCAx version controlling supported hardware


***Notes:***

- **Requirements / dependencies:** see `requirements.txt` (and the docstring at the top of `cca8_run.py`, if present).
- **Most portable way to run:** `python cca8_run.py`  
  *(On some macOS/Linux installs, use `python3 cca8_run.py` if `python` points to Python 2.)*
- **CLI flags, autosave/load workflow, and menu guide:** see **Runner, menus, and CLI** later in this README.
- **GUI:** the supported runner is CLI/TUI only at the time of writing (a Tkinter `.pyw` may exist but is not maintained).
- **Robotics / embodiment:** still launch via `cca8_run.py`; enable HAL with flags when supported (see the HAL section below).
    (The CCA8 ecosystem may not include all the required files for robotics control. Use the CCA8_Bringup package version to ensure
     that all the necessary files are present to control a PetitCat or ROS 2-based robotics platform.)






# Table of Contents

**Introduction to the Causal Cognitive Architecture 8 (CCA8)**

- [Executive Overview](#executive-overview)
- [TL;DR == 15-minute summary](#tldr--15-minute-summary)
- [Opening screen (banner) explained](#opening-screen-banner-explained)
- [Profiles (1–9): overview and implementation notes](#profiles-19-overview-and-implementation-notes)
- [NavMap Primacy and the CCA8 architecture hypothesis](#navmap-primacy-and-the-cca8-architecture-hypothesis)
- [Introduction to the Memory Pipeline](#introduction-to-the-memory-pipeline)
- [CCA8 as a Robotic Cognitive Operating System (RCOS)](#cca8-as-a-robotic-cognitive-operating-system-rcos)
- [RCOS implementation status and roadmap](#rcos-implementation-status-and-roadmap)
- [Hardware Abstraction Layer (HAL)](#hardware-abstraction-layer-hal)
- [Hardware preflight lane (host-readiness checks; device I/O pending)](#hardware-preflight-lane-host-readiness-checks-device-io-pending)
- [FAQ / Pitfalls](#faq--pitfalls)
- [Intro Glossary](#intro-glossary)



**Instructive Tutorial**
- [Instructive Tutorial](#instructive-tutorial)



**Detailed Tutorials and Technical Deep Dives**

- [Predictive Coding, Active Inference, Enactive Inference, and CCA8](#predictive-coding-active-inference-enactive-inference-and-cca8)
- [Tutorial on WorldGraph, Bindings, Edges, Tags and Concepts](#tutorial-on-worldgraph-bindings-edges-tags-and-concepts)
- [The WorldGraph in detail](#the-worldgraph-in-detail)
- [Tagging Standard (bindings, predicates, cues, anchors, actions, provenance & engrams)](#tagging-standard-bindings-predicates-cues-anchors-actions-provenance--engrams)
- [Restricted Lexicon (Developmental Vocabulary)](#restricted-lexicon-developmental-vocabulary)
- [Signal Bridge (WorldGraph ↔ Engrams)](#signal-bridge-worldgraph--engrams)
- [Architecture](#architecture)
- [Action Selection: Drives, Policies, Action Center](#action-selection-drives-policies-action-center)
- [Planner Contract](#planner-contract)
- [Planner: BFS vs Dijkstra (weighted edges)](#planner-bfs-vs-dijkstra-weighted-edges)
- [Persistence: Autosave/Load](#persistence-autosaveload)
- [Runner, menus, and CLI](#runner-menus-and-cli)
- [Menu 48: OpenAI / LLM setup, smoke test, state-summary demo, and advanced request knobs](#menu-48-openai--llm-setup-smoke-test-state-summary-demo-and-advanced-request-knobs)
- [Experiments](#experiments)
- [Menu 49: Experiments / Benchmarks](#menu-49-experiments--benchmarks)
- [Experiment protocol: conditions A–E](#experiment-protocol-conditions-ae)
- [Current benchmark suite](#current-benchmark-suite)
- [Experiment outputs and JSONL records](#experiment-outputs-and-jsonl-records)
- [Preflight (four-part self-test)](#preflight-four-part-self-test)
- [Logging](#logging)
- [WorkingMap Layer Contracts](#workingmap-layer-contracts)
- [Design principle: multi-scale navigation is first-class](#design-principle-multi-scale-navigation-is-first-class)
- [Tutorial on Timekeeping](#tutorial-on-timekeeping)
- [Tutorial on Cognitive Cycles](#tutorial-on-cognitive-cycles)
- [Tutorial on NavPatch: MapSurface patches and matching](#tutorial-on-navpatch-mapsurface-patches-and-matching)
- [Prediction error and predictive coding](#prediction-error-and-predictive-coding)
- [Tutorial on WorkingMap](#tutorial-on-workingmap)
- [Memory systems in CCA8](#memory-systems-in-cca8)
- [Binding and Edge Representation](#binding-and-edge-representation)
- [Anchors, LATEST, and Base-Aware Writes](#anchors-latest-and-base-aware-writes)
- [Data schemas (for contributors)](#data-schemas-for-contributors)
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
- [Traceability (requirements to code)](#traceability-requirements-to-code)
- [Debugging Tips (traceback, pdb, VS Code)](#debugging-tips-traceback-pdb-vs-code)

**References and Notes**

- [References](#references)
- [Developer and Maintainer Notes](#developer-and-maintainer-notes)







# **TL;DR == 15-minute summary**


**Goal (what you should accomplish in ~15 minutes)**

In ~15 minutes, you should be able to:

- start the newborn mountain-goat simulation,
- run a short closed-loop episode (environment ↔ controller) using **menu 37**,
- recognize **keyframes**, the **WM⇄Column memory pipeline** (store/retrieve/apply), and **prediction error v0** in the terminal,
- and optionally flip one knob (**partial observability**) to see priors start to matter.

This is intentionally optimized for “I ran it and saw it work” rather than deep theory.



### 0) Start the program (1–2 minutes)


**If you copied all files from GitHub to your local directory the code should readily run:**

*>python cca8_run.py*



nb- Optional: If you want to specifically specify a fresh session and the autosave file:

*>python cca8_run.py --autosave session.json*


nb- Optional: If you want to resume a prior session:

*>python cca8_run.py --load session.json --autosave session.json*


nb- Optional: If you want an optional confidence check that all code is operating properly (this will also include
checks for supported hardware embodiments if you are using this project for a robotics project): 

*>python cca8_run.py --preflight*  



     
**You will now see a welcome screen, and a small menu allowing you to choose simulation of**
**agents ranging from a Mountain Goat-like brain through CCA11 and CCA12 superhuman research profiles.**


**Choose Profile 1: Mountain Goat**

You will now see the Main Menu.








### 1) Run a closed-loop newborn-goat episode (5–7 minutes)


**From the main menu:**

For a slow, annotated first pass, select:

- **menu 35**: Run 1 Cognitive Cycle, verbose teaching mode

This is the best first NavMap Oscilloscope demo. It shows one closed-loop environment → evidence map → expected map → residual → accepted map signal path, with `[teach]` notes beside the live output.

For a compact multi-cycle run, select:

- **menu 37**: Run n Cognitive Cycles, compact timeline

This is the best multi-cycle run. It shows compact environment/controller/skills output plus mini-snapshot NavMap Oscilloscope lines.

Enter N = 20 (or N = 25).

**What you should see over a short run:**

The Mountain Goat calf starts as fallen on the ground, then StandUp tries to produce standing.

Mom proximity and nipple availability change by storyboard + action feedback from the agent.

The trace becomes a readable story (“fell → stood → followed mom → found nipple → latched → rested”), even in early builds.



### 2) How to quickly read the terminal output (2–3 minutes to understand key outputs)



**Two counters you will see (different meanings)**

cognitive_cycle=1/N ... (agent loop counter for this run)

env_step=0,1,2,... (environment step index since reset; 0-indexed)

**Lines to look for (these are the “heartbeats”)**

Environment truth (storyboard state):

[env] ... stage=... posture=... mom=... nipple=...

Keyframes (episode boundaries) (for example):

[env→world] KEYFRAME: periodic(step=20, period=10)

[wm<->col] store: ...

[wm<->col] retrieve: ...

[wm<->col] apply: ...

**Predictive coding / mismatch signal:**

[pred_err] v0 err={'posture': 0|1} pred_posture=... obs_posture=... from=policy:...

0 means “prediction matched observation”

1 means “prediction mismatched observation”

v0 is intentionally minimal (posture only)

**Per-cycle summary (fast sanity line):**

[env-loop] summary ... env_step=... stage=... env_posture=... bm_posture=... last_policy=... zone=...



### How to Read the Cognitive Cycle and its Summary (optional: 30-60 minutes)

During **menu 35** and **menu 37** closed-loop runs, each cognitive cycle ends with a short **footer block** intended for fast human scanning.
Menu 35 adds explanatory `[teach]` blocks for one slow annotated cycle; menu 37 runs the compact multi-cycle timeline.
This footer is intentionally pragmatic and is **under constant development** as Phase IX evolves; treat it as a reading aid,
not a stable API.

You will see lines with the prefix:

- `[cycle] IN`  — “important inputs” for this cycle: env_step, stage, posture, mom/nipple, zone, drives, and the action that
  the environment applied on this tick (the action was chosen on the prior cycle).
- `[cycle] WM`  — **WorkingMap** summary:
  - `surfaceΔ` lists coarse slot changes (posture / proximity / hazard / nipple) derived from EnvState truth.
  - `scratch` reports which policy executed and how many bindings it wrote (typically into **WM_SCRATCH** when execute_on=WM).
- `[cycle] WG`  — **WorldGraph** long-term injection summary: how many `pred:*` and `cue:*` bindings were written this tick
  (in `changes` mode, this may be `preds+0` when slots are unchanged).
- `[cycle] COL` — **WM⇄Column** keyframe pipeline summary (store / retrieve / apply). If no keyframe-triggered memory ops ran,
  the footer will say so explicitly.
- `[cycle] ACT` — action recap: executed policy name, reward if present in logs, and the **next** action string that will be
  fed back to `env.step(...)` on the next cycle.

As the system matures (HAL/robotics, richer perception, more WorkingMap semantics), the exact fields may change — the guiding
principle is constant: **show the smallest digest that lets you visually confirm the architecture is behaving as intended**.





### 2b) Terminal tag legend (prefixes) + closed-loop terminology (optional: 30-60 minutes)

CCA8 prints many lines with a `[tag]` prefix. These tags are a stable “legend” that lets you skim runs quickly.

**Core env-loop tags**
- **[env-loop]**: one **closed-loop cognitive cycle** driver iteration (env update → internal updates → policy select/execute).
- **[env]**: environment-side events and “truth now” (storyboard stage, posture, mom/nipple state, etc.).
- **[env→working]**: EnvObservation projected into **WorkingMap.MapSurface** (entity/slot updates).
- **[env→world]**: EnvObservation written into the **WorldGraph** (long-term episode index).
- **[wm<->col]**: WorkingMap ⇄ Column keyframe pipeline:
- **store** writes a MapSurface snapshot engram + a lightweight pointer binding; **retrieve** ranks past snapshots
  by context (stage/zone/signature) while excluding the just-stored one; **apply** injects priors (merge/seed) into WorkingMap.
- **[pred_err]**: prediction error v0 (expected vs observed posture); used for retrieval gating and for action shaping
  (a small negative reward shaping update is applied after mismatch streaks).
- **[gate:<policy>]**: a specific gate/trigger’s diagnostic readout (drives, BodyMap stale, zone classification, etc.).
- **[pick]**: which policy won this cycle and why (deficits / non-drive tie-break / RL note if enabled).
- **[executed]**: the chosen policy executed (its internal success/reward signal; confirmation is via NEXT cycle’s observation).
- **[maps]**: which map was used to **select** vs **execute** (e.g., `selection_on=WG execute_on=WM`).
- **[obs-mask]**: partial observability masking (token drops), when enabled.

**Important terminology (to avoid “step” ambiguity)**
- **Cognitive cycle (closed-loop)**: EnvObservation arrives → maps update → policy select/execute → action fed back to env.  
  (Printed as “Cognitive Cycle i/N” in menu 37.):contentReference[oaicite:3]{index=3}
- **env_step / step_index**: the environment’s internal counter since env.reset() (0-indexed).:contentReference[oaicite:4]{index=4}
- **controller step**: one Action Center invocation (“what should I do now?”). In menu 37, we do one controller step per cognitive cycle.
- **avPatch**: a lightweight recognition layer on top of MapSurface

**Environment simulator vs “world model” (AI literature note)**
In modern AI literature, a “world model” usually means an agent’s **internal predictive model** (often learned) that supports action-conditioned prediction.
In CCA8, **HybridEnvironment** is the external **simulated world** (ground truth generator), not the agent’s learned world model.

CCA8’s internal “world model-ish” content is distributed across:

- BodyMap (fast “belief now” safety registers),
- WorkingMap.MapSurface (entity/slot belief table; semantic index),
- *(Phase X)* WorkingMap.SurfaceGrid (policy-facing topology; composed each tick from NavPatches),
- WorkingMap.Scratch / WorkingMap.Creative (predicted postconditions + counterfactual candidates),
- WorldGraph (long-term episode index + pointer scaffold),
- Columns/Engrams (heavy payloads: MapEngrams, NavPatch prototypes, and future perceptual feature engrams).

Phase X adds an explicit, inspectable lookahead hook (**WM1**): given the current SurfaceGrid (+ MapSurface context) and a candidate action/policy, produce a small **OutcomeSketch** (risk/progress/uncertainty) without mutating “truth”.




### 3) Optional experiment: partial observability (optional: 10 minutes)



**Optional: If you want to see that priors matter, enable observation masking:**

Go to menu 40: Configure episode starting state (drives + age_days)

Set:

obs_mask_prob = 0.20 (leave drives as-is for now)

(Optional, for reproducible experiments) Also set:

obs_mask_seed = 123

- If obs_mask_seed is set (an int), masking is reproducible across runs.
- If obs_mask_seed is None/off, masking uses the global RNG (still random).)


Run menu 37 again for N = 20.

What you should notice:

Occasional lines like:

[obs-mask] config mode=seeded seed=123 step_ref=... p=0.20 protected=3
[obs-mask] dropped preds=... cues=... p=0.20 ...

On masked cycles, the WorkingMap update will be missing some facts.

Keyframe retrieval becomes more meaningful (you may see more non-trivial merge/apply summaries).

Tip: set obs_mask_prob back to 0.00 for “fully observed baseline” runs.




### 3b) Optional experiment: contextual map switching (optional: 10 minutes)

If you want to see the **WorkingMap ⇄ Column** memory pipeline in a controlled context-switch task, use the dedicated
goat-foraging evaluation harness:

- go to **menu 42**: *Configure goat_foraging_04 contextual map-switch evaluation*
- then run **menu 37** for `N = 20` (or `N = 50` if you want a longer trace)

What to look for:

- the first context milestones seed two stored MapSurface snapshots (one **hawk**, one **fox**),
- later alternating milestones trigger **retrieve** + **apply** in merge mode,
- and the footer will summarize these events with `[cycle] COL` / `[cycle] MS` lines.

This is the quickest way to confirm that contextual retrieval is happening on cues rather than only on coarse geometry.




### 4) Quick ways to confirm you “used the system” (2 minutes)



**After a menu 37 run:**

Display snapshot / world stats (to see NOW/LATEST, counts, drives, CTX timekeeping).

Plan from NOW to a target predicate (e.g., milk:drinking) to confirm the episode index is searchable.

Export interactive graph (HTML) if you want a visual of the episode skeleton.


### Quick NavMap Oscilloscope test

The NavMap Oscilloscope is the easiest way to see whether the new predictive NavMap path is doing anything real.

It is read-only instrumentation. It does not change policy selection, WorldGraph, Column memory, BodyMap, WorkingMap, or skill values. It reads existing diagnostic registers and formats them as one signal path.

Run:

 
python cca8_run.py
Choose:
Profile 1: Mountain Goat-like brain simulation
Then at the Main Menu:
3

Expected before any environment cycle:
(~~) NAVMAP OSCILLOSCOPE:
  status=idle probes=all_off
Then run one verbose closed-loop cognitive cycle:
35

Expected first-cycle pattern:
(~~) [navmap-scope] acceptance=evidence_only residuals=0 shift=False break=False ...
This means CCA8 has evidence from the first EnvObservation, but no previous map/action prior yet.
Run a second verbose cycle:
35

Expected second-cycle pattern:
(~~) [navmap-scope] acceptance=adjusted_by_evidence residuals=... shift=... break=... action=policy:...
This means CCA8 now has a previous map and a selected primitive/action context, so it can compare:
expected current map
vs
observed evidence map
Then inspect the full snapshot again:
3

Look for:
(~~) NAVMAP OSCILLOSCOPE:
  1 evidence
  
  2 expected
  
  3 residual
  
  4 accepted
  
  5 transition
  
  6 outcome
  
  
The six probes mean:

1 evidence   = EnvObservation-derived NavMap

2 expected   = prior from previous map/context/selected primitive

3 residual   = slot-level mismatch between expected and evidence maps

4 accepted   = accepted-current diagnostic map; evidence remains authoritative

5 transition = previous map + action + current map

6 outcome    = policy-outcome sample and indexed learning surface

Menu 35 is best for teaching because it prints explanatory text. Menu 37 is best for watching several compact cycles run in sequence.

---




**Where to learn more (after the first run)**

Once you’ve seen one closed-loop episode run successfully, take a look at other sections in this documentation:


“Memory Systems in CCA8” (overview of BodyMap / WorkingMap / WorldGraph / Columns)

“Tutorial on Cognitive Cycles” (keyframes vs ordinary cycles; pipeline ordering invariant)

“Tutorial on Timekeeping” (controller_steps vs cog_cycles vs epochs)

“Prediction error and predictive coding” (how v0 is implemented; planned upgrades)




---



# INTRODUCTION TO THE CAUSAL COGNITIVE ARCHITECTURE 8 (CCA8)

# Opening screen (banner) explained


**Opening screen (current runner example):**

A Warm Welcome to the CCA8 Mammalian Brain Simulation
(cca8_run.py v0.9.x; the exact patch version will match the build you launched)

Entry point program being run: C:\Users\howar\workspace\cca8_run.py
OS: win32 (see system-dependent utilities for more detailed system/simulation info)
(for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)

Embodiment:  HAL (hardware abstraction layer) setting: OFF (runs without consideration of the robotic embodiment)
Embodiment:  body_type|version_number|serial_number (i.e., robotic embodiment): 0.0.0 : none specified

The simulation of the cognitive architecture can be adjusted to add or take away
various features, allowing exploration of different evolutionary-like configurations.

1. Mountain Goat-like brain simulation
2. Chimpanzee-like brain simulation
3. Human-like brain simulation
4. Human-like one-agent multiple-brains simulation
5. Human-like one-brain simulation × multiple-agents society
6. Human-like one-agent multiple-brains simulation with combinatorial planning
7. Super-Human-like machine simulation
8. CCA11: one coherent superhuman mind with governed cognitive plurality
9. CCA12: governed pod of complete CCA11 cognitive architectures
T. Tutorial (more information) on using and maintaining this program, references

Please make a choice [1–9 or T | Enter = Mountain Goat]:*



**What each part means:**

* Version and path: printed by the runner, the version comes from `__version__` in the runner. The path helps confirm which file you launched.

* OS/flags line: a reminder that you can run `--help` or the non-interactive flags such as `--about`, `--plan`, `--preflight`.

* Embodiment (HAL/body): shows whether the hardware abstraction layer is enabled and which body profile (if any) was provided. The current build runs fine with HAL off.

* Profile menu: nine presets that configure, demonstrate, or document different cognitive configurations (described below). Selection is handled by `choose_profile`, which records the resulting operational profile in the runtime context and proceeds with the session. Profiles 8 and 9 print future architectural research designs and then return to the Mountain Goat runtime.
  
  

### Q&A to help you learn this section

Q: Why does the banner show a full filesystem path to cca8_run.py?
A: To make it obvious which file you actually launched (and from where). This avoids confusion if you have multiple checkouts or stale copies; you can confirm you’re running the expected entry point.

Q: What is the practical use of the OS/flags line (win32, --help, etc.)?
A: It reminds you that (1) you’re on a particular platform (Windows/macOS/Linux), which may affect file paths and HAL support, and (2) you can always run --help, --about, or --preflight from the CLI instead of entering the menu.

Q: What does “HAL (hardware abstraction layer) setting: off” actually mean?
A: It means the simulation is currently running headless: policies and WorldGraph are active, but no physical robot or real sensors are connected. When HAL is ON with a body profile, controller outputs can be forwarded to hardware via the HAL.









# Profiles (1–9): overview and implementation notes

This section documents what each profile intends to represent and how the current profile subsystem implements it. `cca8_profiles.py` owns profile selection, narratives, and bounded dry-run demonstrations; `cca8_run.py` retains startup orchestration and compatibility wrappers. Longer explanatory help and the new-user tour live in `cca8_guidance.py`. Items 2–9 remain narrative or bounded dry-run research scaffolds. After their explanation or demonstration, they return to the Mountain Goat profile so today’s executable simulation continues unchanged.

1. Mountain Goat-like brain simulation  
   Baseline profile focused on a neonate mountain goat. Defaults: sigma=0.015, jump=0.2, winners_k=2. A boot step ensures a stand intent early in the episode. Use this profile for all current demos and for reading the code.

2. Chimpanzee-like brain simulation  
   Narrative only. Describes a later primate-like architecture with richer social and relational maps, short recursive map operations, limited hidden-cause/counterfactual fragments, and stronger secondary processing than the goat. It does not imply human compositional language. The current runner then falls back to Mountain Goat defaults.

3. Human-like brain simulation  
   Narrative only. Describes a later architecture with sustained recursive causal map operations, full analogical transformation, alternate hypotheses, and compositional language, then falls back to the Mountain Goat defaults.

4. Human-like one-agent multiple-brains simulation  
   Implements a dry-run “multi-brains” scaffold inside one agent. `cca8_profiles.py` forks five sandbox WorldGraphs (deep copies of the live world for now), each proposes a next action with a confidence and rationale, and a voting rule selects the winner (most popular, ties broken by average and maximum confidence). No changes are committed to the live world, it is a read-only demonstration of the mechanism. Future work would merge only new nodes/edges from the winning sandbox and re-id them to avoid collisions.

5. Human-like one-brain × multiple-agents society  
   Implements a dry-run “society” scaffold. `cca8_profiles.py` creates three independent agents, each with its own WorldGraph and Drives, runs one action-center tick per agent, and demonstrates a simple inter-agent message as a cue (e.g., A1 bleats, A2 receives a sound cue). No snapshots are written, this is a safe, print-only demo. In a full build, you would iterate over agents each tick and exchange messages via a queue or shared mailbox.

6. Human-like one-agent multiple-brains with combinatorial planning  
   Implements a dry-run combinatorial planner. Five “brains” each run many von Neumann processors (configurable, the current stub uses 256 per brain) to explore short candidate plans, score them with a simple utility (sum of action rewards minus a per-step cost), report the per-brain best and average score, and then select a champion brain. In a real system only the first action of the winning plan would be committed to the live world after a safety check, the stub prints the commit rule but does not modify state.

7. Super-Human-like machine simulation  
   Implements an early dry-run meta-controller. Three proposal sources (symbolic search, neural value, program synthesis) each provide an action and a utility, the meta-controller picks the winner by score with a fixed tie-break preference. The printout illustrates how a higher-level controller could arbitrate between heterogeneous planners. No state is modified. This remains a small mechanism demonstration rather than the complete architecture proposed for CCA11.

8. CCA11: one coherent superhuman mind with governed cognitive plurality

   Prints a detailed future-architecture narrative and then returns to Profile 1. CCA11 is intended to be one persistent self with one human-authorized mission, one committed Accepted Working Navigation Map for present external control, one governed memory system, and one controlled action path. Within that coherent agent, several heterogeneous cognitive processes may work in parallel or on separate branch-local maps.

   Candidate processes include NavMap prediction, causal intervention reasoning, analogical reasoning, symbolic planning, probabilistic forecasting, episodic retrieval, semantic or LLM-based reasoning, scientific hypothesis generation, skeptical/red-team analysis, safety checking, and metacognitive resource allocation. These processes submit structured proposals rather than directly rewriting accepted state.

   A future proposal record should preserve the proposing process, input-map revision, evidence and provenance, assumptions, predicted outcomes, counterevidence, support type, calibration information when probability is claimed, recommended action or probe, reversibility, safety implications, authority implications, and unresolved objections.

   **Plural thought does not imply plural executive authority.** Observed evidence, the committed current map, persistent memory, protected goals, human authority, and actuators remain protected surfaces. A separate acceptance/commitment mechanism may reject a proposal, preserve it as an unresolved alternative, request a probe, escalate it for human review, provisionally commit it, revise accepted state, or authorize external action.

   **Agreement is not the stopping rule.** Several processes may agree because they share evidence, models, training data, assumptions, or copied conclusions. CCA11 should evaluate evidence quality, provenance, reasoning-path dependence, predictive performance, calibration, causal tests, reversibility, safety, and the expected value of more information. It must retain `UNKNOWN`, abstention, and reject-all outcomes when the available proposals are inadequate.

   **Relationship to Minsky's Society of Mind.** CCA11 accepts Minsky's core pluralist insight that no single cognitive method is adequate for every problem. Minsky's technical agents are generally subpersonal mechanisms whose organization produces one mind. CCA11 may contain much larger cognitive processes, but it adds explicit executable contracts for proposal provenance, protected accepted-map authority, governed memory commitment, unresolved dissent, and controlled external action. A useful description is **a constitutional society of cognitive processes inside one coherent mind**. “Constitutional” means that explicit rules govern state, memory, goals, authority, and action; it does not imply equal voting rights among modules.

   **Relationship to Goertzel's cognitive synergy, OpenCog, and Hyperon.** Cognitive synergy asks how heterogeneous processes can help one another when one process becomes stuck. CCA11 accepts that principle. It adds a second question: **what authority does the resulting proposal possess?** A shared substrate or orchestration mechanism may enable processes to exchange work, but CCA11 additionally distinguishes observed, expected, inferred, retrieved, imagined, and accepted content and governs which proposal may alter the committed map or control action. HyperClaw-like orchestration could be one routing layer, but it would not by itself supply the complete CCA11 state-authority contract.

   Several current runner profiles are precursors. Profile 4 demonstrates parallel sandbox brains. Profile 6 demonstrates parallel combinatorial search. Profile 7 demonstrates heterogeneous proposal arbitration. CCA11 would integrate these ideas while replacing simple fork-and-vote behavior with specialized reasoning roles, explicit disagreement, metacognitive recruitment, evidence-based adjudication, governed commitment, and one controlled external-action path.

   The concise architectural statement is:

       CCA11
           = one coherent self
           + many cognitive methods
           + several branch-local workspaces
           + explicit provenance
           + one governed commitment structure
           + one controlled external-action path

9. CCA12: governed pod of complete CCA11 cognitive architectures

   Prints a detailed federated-architecture narrative and then returns to Profile 1. CCA12 groups several complete CCA11 minds. Each pod member may have its own identity, Accepted Working Navigation Map, sensory viewpoint or embodiment, episodic history, learned transformations, attention, uncertainty, internal cognitive council, and delegated local goals.

   The central distinction is:

       CCA11 = one self with many cognitive methods
       CCA12 = many CCA11 selves operating under one governed mission

   The purpose of a pod is not merely to multiply copies. A useful pod can perform parallel hypothesis search, independent replication, multi-horizon planning, distributed perception, domain specialization, adversarial checking, fault tolerance, and independent confirmation before consequential action. Ten identical agents using the same model, prompts, memories, data, and assumptions may simply reproduce one correlated error ten times.

   **Mission Charter.** A CCA12 pod requires an explicit charter defining the legitimate mission, human authorities, protected goals, prohibited actions, delegation boundaries, resource and privacy limits, required confirmations, escalation conditions, emergency-stop authority, membership rules, and the procedure for changing the charter. No ordinary pod member may rewrite it unilaterally.

   **Local minds and shared pod state.** Each member retains its local accepted map and broader cognitive state. Shared information is published through provenance-preserving observations, map fragments, hypotheses, plans, predictions, counterarguments, experimental results, resource commitments, action proposals, and authority decisions. A Pod Blackboard or Assertion Ledger should distinguish a published assertion, independent confirmation, provisional pod commitment, accepted mission state, and authorized external action. A statement on the blackboard is not automatically true.

   **Controlled independence.** Members should often produce an initial analysis before seeing other conclusions. The ledger should record shared models, data, code, memories, and assumptions so that apparent agreement is not mistaken for independent confirmation. After the first pass, members may critique, replicate, test, or synthesize one another's work.

   **Adjudication.** CCA12 should not use simple majority vote as its universal rule. Sensor claims may be weighted by provenance and reliability. Specialized questions may use demonstrated competence. Important factual claims may require replication. Uncertain explanations may require adversarial comparison. Safety-critical actions may require an explicit Guardian authorization or two independent keys. Out-of-charter decisions require human escalation. The pod must be able to preserve several viable alternatives, declare insufficient evidence, request another observation, abstain, or reject all represented hypotheses.

   **Action authority.** A pod sharing one embodiment should normally have one governed action gateway. For multiple embodiments, explicit action leases define which member may control which body or resource, the permitted actions, mission/geographic/time limits, expiration, revocation, collision rules, and emergency-stop behavior.

   **Distributed-system risks.** CCA12 must address correlated error, groupthink, stale shared context, poisoned messages, authority capture, race conditions, duplicated actions, resource contention, deadlock, communication loss, member failure, compromised members, and drift between local maps and shared mission state. Scaling unresolved architecture problems can amplify error rather than intelligence.

   **Relationship to Minsky and Goertzel.** CCA12 is a society of complete minds, unlike Minsky's usual society of subpersonal agents. Cognitive synergy may occur both within each CCA11 and across the pod, but inter-agent communication should not erase agent boundaries. A shared OpenCog/Hyperon-like substrate may support cooperation, while CCA12 adds a Mission Charter, provenance-preserving federation, explicit delegation, fault isolation, and governed external-action rights.

   The concise architectural statement is:

       CCA12
           = many complete CCA11 selves
           + one governed mission
           + one Mission Charter
           + one provenance-preserving pod ledger
           + controlled delegation
           + governed external-action rights

### Q&A to help you learn this section

Q: Which profile should I use for real experiments right now?
A: Use Profile 1 (mountain goat). At the time of this writing, it's the profile that is fully wired to drives, policies, the newborn storyboard environment, and the runner. The others are narrative/dry-run stubs that fall back to Profile 1.

Q: Do the multi-brain / multi-agent profiles modify the live WorldGraph today?
A: No. At present, they typically operate on sandbox copies of the world (or separate worlds) and print results, but they do not commit changes back to the live WorldGraph. That keeps the core goat simulation deterministic and easy to reason about.

Q: What is the practical difference between “human-like” and “super-human-like” profiles today?
A: At the time of writing, the difference is mainly in the story and trace they print. Profile 7 demonstrates a small dry-run meta-controller. Profiles 8 and 9 preserve more complete architectural roadmaps for later CCA11 and CCA12 development. None of these choices currently runs a distinct human-level or superhuman cognitive architecture; all return to the Mountain Goat runtime after the explanation or dry run.

Q: Why keep both CCA11 and CCA12?
A: They address different scaling problems. CCA11 asks how one coherent mind can recruit many cognitive methods without losing accepted-map, goal, or action authority. CCA12 asks how several complete CCA11 minds can cooperate without losing mission coherence, provenance, delegation boundaries, or safe action control. Internal governance should be solved before federation amplifies the architecture.

Q: Is CCA11 just Minsky's Society of Mind?
A: It shares Minsky's insight that intelligence can emerge from organized specialists rather than one universal procedure. CCA11 adds a NavMap-centered software contract: typed proposals, protected evidence, a committed accepted map, explicit provenance, unresolved dissent, and governed memory/action commitment. The intended implementation is therefore a particular constitutional and auditable society of processes, not merely a restatement of the general theory.

Q: Is CCA11 just Goertzel-style cognitive synergy or HyperClaw?
A: It overlaps strongly with cognitive synergy because heterogeneous processes should help one another overcome bottlenecks. The additional CCA question is which result is allowed to become accepted present state or control action. Orchestration can route work; CCA11 also requires source authority, map authority, commitment rules, and a protected action gateway.

Q: How do profiles interact with the rest of the code?
A: `cca8_profiles.py` selects the profile, sets initial parameters in Ctx (sigma, jump, profile label), and may run a bounded stub/demo. It then returns configuration to the same high-level runner loop. The WorldGraph, controller, and environment interfaces remain the same; only initial configuration and demonstration traces change.










# NavMap Primacy and the CCA8 architecture hypothesis

This section states the architecture that CCA8 is intended to test. It is integrated into the README as the governing paradigm rather than
as a chronological project update.

## Scientific status and source precedence

Three sources answer different questions:

| Source | Question answered |
|---|---|
| Current local source code, tests, and traces | What does CCA8 actually do today? |
| Published CCA papers | What navigation-map architecture is the project trying to instantiate? |
| Planning v11 | How should the present implementation build and test the distributed Column/NavMap kernel, then migrate safely toward map-first authority? |

The NavMap paradigm is an experimental scientific hypothesis. The purpose is not to protect it from failure. The purpose is to build it
faithfully enough that success, failure, or partial success teaches us something about mammalian cognition, robotics, and artificial
intelligence.

## Evolutionary and developmental scope

The paper sequence CCA0–CCA7 records the historical development of Howard Schneider's ideas; it is not a literal phylogenetic ladder.
For CCA8, mechanisms are selected according to biological and developmental plausibility.

The working evolutionary hypothesis is:

| Evolutionary level | Proposed map capability | CCA8 interpretation |
|---|---|---|
| Early mobile bilaterian | Primitive spatially organized sensorimotor representations for orientation, approach, avoidance, and locomotion | Deep precursor; not claimed to be a vertebrate-style WNM |
| Early vertebrate | Topographic sensory, body, motor, heading, and self-motion organization | Map machinery older than tetrapods |
| Fish and early tetrapod | Place learning, boundaries, heading, spatial memory, and useful temporal prediction | Rich map cognition before amniotes |
| Common amniote | An active integrated world/navigation map used with memory, goals, and action selection | Proposed WNM precursor |
| Mammal | Six-layered neocortex supplies a very large distributed library of specialized maps; hippocampal-like machinery indexes and retrieves them | Core CCA evolutionary hypothesis |
| Goat | A richly reconstructed WNM, extensive learned map library, strong embodiment and pre-causal behavior | CCA8 target; no requirement for human recursive cognition |

CCA8 is therefore not "CCA3 implemented literally" and not "CCA2 plus a goat skin." It uses a CCA2/CCA3-like mammalian substrate:
spatial binding, temporal binding, Local and multisensory maps, one current WNM, long-term matching/retrieval, primitives operating on
maps, and ordinary prediction/action loops. It excludes normal CCA4 transformation-transfer analogy, sustained recursive causal
processing, and a separate language architecture.

## Map Primacy and state discipline

**Map Primacy Principle:** the Navigation Map is the primary cognitive representation of the goat's world. A compact state is legitimate
when it is one of the following:

1. a genuine compact biological or control state, such as hunger, energy, arousal, developmental stage, or motor-controller status;
2. a derived readout of a named map revision, such as fallen, Mom-near, cliff-near, path-available, or nipple-reachable;
3. implementation bookkeeping, such as a flag, counter, seed, cache version, or history limit.

A compact state should not quietly become an independent symbolic world model.

The central diagnostic question is:

    Does this value help the software read a map?

    or

    Has this value quietly replaced the map?

The current software necessarily uses predicates, dictionaries, enums, and scalar summaries. The theory-level claim is not that Python
must stop using states; it is that the cognitively meaningful structure should remain recoverable from maps and provenance.

## What exactly is a CCA8 Navigation Map?

A **CCA8 Navigation Map** is a bounded, addressable, spatially organized and relationally linked representation of some portion of the
goat's body, environment, object world, action possibilities, or learned experience, at a declared scale and reference frame. Its locations
or regions may contain feature bundles, entity membership, temporal-change information, affordances or procedure references, and links
to other Navigation Maps. Every contribution retains its source, quality, and status. A NavMap may be incomplete, ambiguous, or partly
unknown. It becomes current cognitive reality only through explicit acceptance as the WNM.

A NavMap preserves more than a bag of facts:

- geometry and spatial embedding;
- topology, adjacency, connectivity, boundaries, and containment;
- direction, distance, orientation, and relation to SELF;
- entities, regions, objects, and provisional identities;
- multimodal features and source quality;
- motion, rate, trajectory, persistence, and expected continuation;
- affordances and links to primitive maps;
- links to parent, child, close-up, contextual, episodic, and prototype maps;
- observed, expected, inferred, retrieved, imagined, historical, rejected, and unknown status.

Graph theory is useful for reachability, neighborhoods, connected components, paths, cycles, and structural matching. A NavMap is not
merely a generic graph because frame, scale, geometry, modality, region extent, and spatial embedding remain first-class.

### Distributed Column and decoded map content

Planning v11 treats one conceptual cortical Column/minicolumn as a distributed local map-processing and storage unit. A Column can
represent many places, objects, regions, geometries, and relationships through internal population activity. CCA8 does not yet model the
neurons, recurrent weights, or low-level learning rule inside that Column. Instead, the first `NavMapV2` kernel exposes the decoded
relational-spatial content needed by the architecture while remaining neutral about whether the later local backend is explicit-record,
ANN-like, sparse, attractor-like, or hippocampal-like.

The fundamental NavMap is therefore **not** a 6×6 or 100×100 array of cortical storage cells. A 6×6 diagram may remain useful for papers,
teaching, and terminal inspection, but it is only a renderer of continuous geometry. Rendering the same map at a different resolution must
not change its identity, relationships, matching, transformations, or cognitive result. The existing raster-like `SurfaceGrid` remains a
useful later policy-facing projection; it is not the underlying Column/NavMap.

A useful theory-level decomposition is:

| Component | Meaning |
|---|---|
| Identity and lifecycle | map id, schema, revision, parent revision, status, ownership, creation/acceptance time, lifetime |
| Frame and scale | reference frame, viewpoint, origin, orientation, scale, extent, alignment transforms, relation to SELF or parent |
| Spatial substrate | represented places/regions, continuous coordinates, geometry, topology, surfaces, boundaries, occupancy, and unknown areas |
| Entities | segmentation, role and identity, persistence, containment, merge/split, occlusion history |
| Features | multimodal feature bundles, body relations, terrain properties, affordances, quality, missingness |
| Temporal features | direction, rate, trajectory, approach/recession, persistence, contact duration, time-to-hazard |
| Action references | possible actions, primitive links, preconditions, and expected local transformations |
| Links | parent/child maps, close-ups, memories, prototypes, primitive maps, successors, contexts, episodes |
| Provenance and authority | observed/expected/retrieved/inferred/imagined/appraised/historical source, support, conflict, uncertainty |

This is a conceptual decomposition, not a demand that one Python dataclass contain exactly nine fields.

## The CCA8 NavMap family

| Map role | Purpose |
|---|---|
| Modality evidence map | Current visual, auditory, olfactory, tactile, vestibular, proprioceptive, or interoceptive evidence with frame, quality, time, missingness, and provenance |
| Stored Local NavMap / prototype | Same-modality learned pattern used to recognize incomplete or noisy evidence |
| NavPatch | Bounded attended fragment representing an entity, terrain motif, contact pattern, hazard, landmark, goal, or scene region |
| Multisensory scene/object candidate | Aligned composition of compatible Local maps and patches while retaining support, conflict, missingness, and candidate status |
| Accepted WNM | One current authorized root map, with linked submaps, representing the goat's best present interpretation |
| Expected current/successor map | Short prediction from prior WNM, action, transition, context, and motion; explicitly unconfirmed |
| Episodic/prototype map | Durable scene, object, trajectory, before-action-after pattern, success/failure, or generalized family stored in Columns |
| Primitive/transformation map | Specialized map describing trigger patterns, queries, operations, action intent, expected transformation, completion, failure, and links |

The WNM is primarily a **role and authority status**. It is the map revision granted accepted-current authority. Acceptance authorizes
current use; it does not relabel retrieved or expected content as observed and does not automatically consolidate the map long-term.

## One accepted root WNM with linked submaps

One accepted scene does not require one enormous flat object. The preferred architecture is one accepted root WNM that contains or links
the active whole-scene context, with bounded submaps at different scales and frames.

    Accepted root WNM
        SELF
        MOM
        local terrain
        cliff region
        shelter direction

            links to:

        SELF body/posture close-up
        maternal-body close-up
        nipple-mouth relation map
        cliff-edge geometry map
        broader route/context map

Attention may activate a linked submap without creating a second equally authoritative world. The parent scene remains protected and can
be restored through an explicit stack or context link. Candidate, expected, retrieved, imagined, rejected, and historical maps remain in
protected layers.

## Long-term memory participates in WNM construction

The WNM is not built from sensory evidence alone and then sent to memory afterward. Current evidence queries memory for useful map
structure:

    partial modality evidence maps
        -> WorldGraph query, context, and episode neighborhood
        -> bounded Column candidate maps
        -> align and compare
        -> retrieve useful prior structure
        -> combine with reliable present evidence
        -> candidate scene maps
        -> one accepted root WNM or UNKNOWN

WorldGraph approximately answers **where should I look?** Columns answer **what rich map content is stored there?** Retrieval does not
confer truth. Memory may organize perception and fill gaps, but reliable incompatible evidence defeats the prior. A best poor candidate is
not accepted merely because it is the best represented candidate.

## Protected source and authority classes

| Class | Meaning |
|---|---|
| OBSERVED / EVIDENCE | Direct current sensor-derived support with source quality, time, frame, transforms, and missingness |
| EXPECTED | Predicted current or successor content generated from WNM, action, transition, context, or prior |
| CANDIDATE | Provisional interpretation competing for acceptance |
| ACCEPTED | Authorized current use in the one root WNM; original source classes remain recoverable |
| INFERRED | Derived relation or feature supported by operators but not directly observed |
| RETRIEVED | Long-term memory activated for comparison or guidance |
| IMAGINED | Creative or counterfactual proposal; bounded and non-authoritative |
| APPRAISED | Control interpretation such as surprise or threat relevance |
| HISTORICAL | Past accepted/evidence/transaction content |
| REJECTED | Candidate declined with reason |
| UNKNOWN | No candidate or field is adequately supported |

**Provenance invariant:** no operator converts EXPECTED, RETRIEVED, INFERRED, IMAGINED, APPRAISED, or HISTORICAL
content into OBSERVED. Acceptance preserves source and derivation.

## NavMap operator vocabulary

Elementary map operations are called **NavMap operators** to distinguish them from behavioral primitives such as StandUp or FollowMom.
Every operator should declare inputs, accepted source classes, frame requirements, output schema, purity or side effects, deterministic
ordering, bounds, failure/UNKNOWN behavior, and tests.

| Operator family | Contract |
|---|---|
| select / focus / zoom / follow-link | Choose a region or entity; activate close-up or parent map while protecting context |
| align / reframe / rotate / translate / rescale | Put maps into a comparable frame and return the explicit transformation used |
| segment / merge / split / track | Create and maintain provisional or persistent entities and regions with lineage and occlusion provenance |
| bind / compose | Combine compatible modality maps and patches into a candidate while retaining source and conflict |
| query relation / trace path | Ask adjacency, containment, distance, direction, contact, reachability, safe path, neighborhood, or boundary questions |
| retrieve candidates | Query WorldGraph and activate a bounded set of Column maps without conferring authority |
| match / rank | Return correspondences, transform, coverage, residual basis, score, margin, missingness, novelty, and ambiguity |
| compare / structured residual | Preserve map-local differences among regions, entities, relations, features, sources, and trends |
| propose revision | KEEP, REVISE, CREATE, UNKNOWN, or REJECT-ALL under explicit evidence and authority rules |
| apply revision | Create a versioned child map through an authorized proposal; no arbitrary setter on accepted WNM |
| accept root | Choose at most one candidate root WNM or explicit UNKNOWN |
| predict successor / apply primitive transform | Produce a short expected map from accepted map plus primitive/action/local transition |
| project | Derive MapSurface, SurfaceGrid, NavSummary, predicates, or BodyMap-facing values from a named revision |
| consolidate / index | Store selected rich maps in Columns and sparse episode/pointer links in WorldGraph after acceptance/outcome evaluation |
| expire / prune | Bound candidates, Scratch, histories, caches, and working representations while preserving protected current/safety records |

Matching must return structure, not only a scalar score. A useful match reports correspondences, alignment assumptions, matched and
mismatched regions, missing and novel material, coverage by modality, source quality, rank, margin, ambiguity, and retrieval provenance.
A scalar residual may summarize a structured mismatch, but it must link back to the comparison that gave it meaning.

## Primitive maps and the motor abstraction boundary

An instinctive or learned primitive is a map-based procedure. Its cognitive content can be represented as a specialized primitive map plus
a simple readable Python execution class. A primitive may describe:

- the map pattern and relations it can operate on;
- drive, developmental, and arousal modulation;
- map queries and operators;
- an action intent;
- an expected local map transformation;
- completion, failure, and UNKNOWN patterns;
- safety, hold, interruption, and recovery rules;
- links to lower motor routines, successor primitives, and supporting episodes.

For example, FollowMom conceptually locates SELF and the maternal entity, examines relative geometry and maternal motion, inspects
intervening terrain and hazard topology, chooses a safe reachable direction, emits a bounded intent, and predicts a modest change in the
SELF–MOM relationship. The implementation may calculate distance classes and booleans, but the primitive should not be architecturally
reduced to a condition forest over independent state variables.

Detailed motor implementation remains below CCA8. Fish, goats, humans, and robots execute movement through fast sensorimotor systems.
CCA8 chooses and supervises intents such as StandUp, FollowMom, Retreat, Rest, or Probe. Lower controllers handle balance, force,
trajectories, slip, actuator timing, and muscle-equivalent control. CCA8 receives motion direction, rate, progress, contact, completion,
error, and safety products that can be bound onto the map.

## Current implementation versus target authority

Current CCA8 already contains most of the required components, but not yet the target authority structure.

    Current tendency:

    EnvObservation
        -> BodyMap
        -> observation-driven MapSurface / SurfaceGrid / WorkingMap
        -> NavMap diagnostic shadows
        -> WorldGraph writes
        -> mixed-source policy arbitration
        -> controller primitive

    Target tendency:

    minimally interpreted modality evidence
        -> evidence and Local NavMaps
        -> segmentation / NavPatches / candidate scenes
        -> bounded Column and WorldGraph retrieval
        -> one accepted root WNM with linked submaps
        -> derived MapSurface / SurfaceGrid / NavSummary / predicates / BodyMap-facing values
        -> map-native primitive transaction and expected transformation
        -> lower motor intent
        -> new evidence, structured residual, revision, and selective consolidation

The migration is staged. New records begin as inventory, shadow, compare, or advisory paths. Behavioral authority is promoted one domain
at a time only after deterministic traces, differential tests, safety checks, and compatibility tests demonstrate that the change is
understood.


# Introduction to the Memory Pipeline

This section is the front door to CCA8 memory. It distinguishes the **current implementation** from the **target Map-Primacy
architecture**, explains how long-term memory helps construct the WNM, and states which structures are authoritative, derived, protected,
or merely diagnostic.

## Current implementation versus target map authority

**Current implementation at commit `71ab4dc`:**

- `cca8_run.py` coordinates the closed-loop order and installs runtime hooks.
- `cca8_observation_runtime.py` receives `EnvObservation`, applies masking, updates BodyMap, runs Sequential/Error support, builds or
  updates MapSurface and SurfaceGrid-related structures, invokes NavPatch matching, records selected keyframes and WorldGraph writes,
  and calls the NavMap diagnostic bridge.
- BodyMap, WorkingMap/MapSurface, SurfaceGrid/NavSummary, WorldGraph history, retrieval hints, drives, and policy bridges can affect
  action.
- `ctx.navmap_last_accepted_current_v1` and `working_navmap_surface_v1` remain diagnostic shadows rather than canonical WNM
  authority.

**Target architecture:**

- modality-specific evidence maps and stored Local NavMaps participate in perception;
- WorldGraph retrieves a bounded set of rich Column maps;
- aligned evidence, prior maps, temporal features, and previous context form candidate scenes;
- one accepted root WNM becomes the principal current world representation;
- MapSurface, SurfaceGrid, NavSummary, predicates, and most BodyMap-facing values are derived from or synchronized with a named WNM
  revision;
- primitives query and transform maps, then send bounded intents below the motor abstraction boundary;
- accepted maps, transformations, outcomes, and important episodes are selectively consolidated.

This target is a development programme, not a claim about current runtime behavior.

## Environment boundary: evidence, not belief

The environment owns `EnvState`, the simulator's hidden truth. The agent never treats that object as cognition. `EnvObservation` is the
packet crossing the boundary into the agent. It is currently semantically rich and therefore already performs some interpretation that a
future biological pathway should perform inside CCA8.

The long-term sensory direction is:

    raw or shaped modality signal
        -> modality evidence NavMap
        -> stored Local NavMap match / revision / creation
        -> temporal binding and segmentation
        -> NavPatch and scene candidates
        -> accepted root WNM

`EnvObservation` remains a practical adapter while that pathway is introduced gradually.

## Current and target cognitive-cycle ordering

The current loop is approximately:

    environment reset / step
        -> feedback for the previous prediction
        -> observation masking
        -> BodyMap update
        -> Sequential/Error support
        -> SurfaceGrid / MapSurface / NavPatch / WorkingMap updates
        -> preserved second BodyMap update
        -> NavMap evidence/expected/accepted diagnostics
        -> keyframe and selected WorldGraph / Column work
        -> retrieval and map-switch hooks
        -> PolicyRuntime arbitration
        -> controller primitive execution
        -> next prediction and reporting

The target map-first loop is:

    modality evidence
        -> Local NavMap matching
        -> temporal binding, segmentation, and NavPatches
        -> bounded WorldGraph-indexed Column retrieval
        -> alignment and multisensory candidate composition
        -> expected current/successor map
        -> structured comparison
        -> one accepted root WNM or UNKNOWN
        -> WNM-derived projections and compact readouts
        -> map-native primitive transaction
        -> lower motor intent
        -> progress and new evidence
        -> confirmation/revision/surprise resolution
        -> selective consolidation

Ordering matters. Policy selection should not read stale projections. Retrieval should not masquerade as observation. Expected outcomes
should not be written as confirmed facts. Long-term consolidation should follow acceptance and outcome evaluation in the target
architecture.

## Memory and representation roles

| Component | Current role | Target role / authority |
|---|---|---|
| `EnvObservation` | One-tick semantically interpreted evidence packet | Evidence adapter only; never final belief |
| Modality evidence NavMaps | Mostly future, with compact diagnostic precursors | Current bottom-up evidence by modality, frame, quality, time, and missingness |
| Stored Local NavMaps | Partial through prototypes/candidates | Same-modality learned maps used for recognition and revision |
| BodyMap | Fast, active posture/near-space gating and safety register | Retains independent fast safety path; ordinarily synchronized with WNM body relations |
| WorkingMap | Active workspace/container | Owns accepted root WNM, linked submaps, protected layers, projections, Scratch, Creative, and bounded histories |
| Accepted WNM | Diagnostic shadow today | One authorized current root map; principal world representation |
| MapSurface | Observation-driven policy-facing semantic scene today | Derived sparse entity/relation projection of a named accepted WNM revision |
| SurfaceGrid | Active local topology and NavSummary support | Derived traversability/hazard/goal/unknown projection of accepted WNM/submaps |
| Scratch | Action chains, ambiguity records, comparisons, transient traces | Protected workspace for transactions, residuals, local transformations, and bounded surprise episodes |
| Creative | Bounded candidate outcomes and scaffolding | Protected imagined/counterfactual maps; never direct belief or actuator authority |
| Columns | Heavy payload/engram store | Rich durable map library: Local/multisensory maps, prototypes, trajectories, transformations, and episodes |
| WorldGraph | Sparse episode graph, planning/indexing, pointers, selected historical predicates | Sparse index and retrieval/navigation structure; not current truth |
| Predictions/residuals | Active diagnostics and some feedback/keyframe influence | Map-linked expectations and structured comparisons; not the cognitive product |
| Policies/controller | Mixed-source selection and Python primitive execution | Primitive maps/query contracts plus readable Python safety/execution substrate |

## WorkingMap, WNM, and protected layers

WorkingMap is the **container**. It is not itself the WNM. The target WorkingMap owns:

- one accepted root WNM and its bounded revision history;
- linked body, terrain, maternal, hazard, object, route, and close-up submaps;
- evidence maps and candidate scenes;
- expected maps and transactions;
- retrieved memory maps;
- Scratch comparisons and surprise episodes;
- Creative proposals;
- derived MapSurface, SurfaceGrid, NavSummary, predicates, and BodyMap-facing readouts.

Only one root WNM has accepted-current authority. A focused linked submap can be active without becoming another reality.

## BodyMap contract

BodyMap is the important exception to a pure single-source rule. A biological animal or robot needs a rapid embodied protection path for
posture, balance, contact, falling, immediate near-body danger, and controller status. BodyMap can therefore retain independent fast safety
authority.

The ordinary relationship should still be explicit:

    accepted WNM body/near-space relations
        <-> BodyMap synchronization and discrepancy check

    fast body feedback
        -> immediate BodyMap protection
        -> WNM/transaction revision at cognitive cadence

A BodyMap value such as `fallen` is a compact control readout. It should not expand into an independent full world model.

## MapSurface, SurfaceGrid, NavSummary, and predicates

These views remain valuable because they make the system efficient and inspectable.

- **MapSurface** exposes stable entity handles, selected attributes, and relations.
- **SurfaceGrid** exposes local terrain, occupancy, hazard, goal, corridor, and conservative UNKNOWN structure.
- **NavSummary** supplies small policy-facing topology and focus summaries.
- **Predicates/tags** support indexing, compatibility gates, displays, planning, serialization, and experiment metrics.

In the target architecture, every behaviorally authoritative view should answer:

    From which WNM revision was this value derived?
    By which projection/operator?
    How fresh is it?
    What is its uncertainty and source authority?

During migration, legacy and WNM-derived versions run side by side and differences are recorded before promotion.

## Columns and WorldGraph: one long-term memory system with two layers

WorldGraph and Columns cooperate but carry different content.

    WorldGraph
        -> sparse episodes, actions, keyframes, anchors, retrieval links, content addresses, and Column pointers

    Columns
        -> rich maps, prototypes, sensory feature bundles, trajectories, transformations, and episode payloads

WorldGraph tells the architecture **where to look**. Columns hold **what it wants to inspect**. Neither becomes present belief without
activation, alignment, comparison, and acceptance.

## Retrieval contract

The target retrieval path is:

    partial current map + context + task/drive relevance
        -> bounded WorldGraph query
        -> Column candidate maps
        -> explicit alignment and matching
        -> protected RETRIEVED layer
        -> candidate scene composition
        -> acceptance or rejection

Retrieved maps may fill gaps, suggest identities, supply trajectories, or prime attention. They may not overwrite reliable incompatible
evidence or become accepted merely because they are the best available poor match.

The current snapshot merge/replace pipeline remains useful scaffolding and an experimental comparison surface. Merge is conservative;
replace is a strong-prior/debug mode and must not be mistaken for the final acceptance contract.

## Prediction and primitive transactions

Prediction is an update law over maps, not a detached memory store.

    accepted WNM + selected primitive + local transition + motion
        -> expected current/successor map

    expected map <-> new evidence map
        -> structured residual

A scalar error is useful for display and thresholds, but the cognitively useful object identifies which region, entity, relation, feature,
frame, or source failed to match.

A future primitive transaction links:

- accepted map before action;
- trigger and safety evidence;
- intent;
- expected local map transformation;
- progress and fast body feedback;
- completion, failure, interruption, or UNKNOWN;
- accepted map after action;
- provenance and learning eligibility.

The Python policy/controller remains a readable safety and execution substrate while these map-native contracts mature.

## Drives, valence, and compact biological states

Drives such as hunger, fatigue, warmth, arousal, or safety pressure are legitimate compact control states. They do not need to be forced
into a spatial map merely to satisfy Map Primacy. Their cognitive effect, however, should be map-relevant:

    hunger
        -> raises value of maternal/nipple/milk maps and related primitive patterns

    fatigue
        -> raises value of safe-rest maps and suppresses unsafe rest

    threat/body instability
        -> raises salience, caution, protective gating, and interruption readiness

Valence should attach to map regions, routes, relationships, actions, and outcomes where possible rather than remaining only an opaque
global scalar.

## Keyframes, consolidation, and memory boundaries

CCA8 does not need to store a heavy map every tick. Keyframes and consolidation decisions preserve important structure while keeping
WorldGraph sparse.

Current triggers include stage changes, zone changes, periodic boundaries, milestones, prediction discrepancies, and experiment-specific
captures. The target consolidation decision follows accepted-map and outcome processing and may store:

- accepted scene or linked submap;
- novel or refined prototype;
- before-action-after transformation;
- successful or failed trajectory;
- surprise/resolution episode;
- high-value, safety-critical, or developmental milestone.

The rich payload goes to Columns. WorldGraph receives a sparse pointer/index/action/keyframe record after a successful and explicitly
reasoned consolidation operation.

## Reading current logs without confusing implementation and target

When reading Menu 35, Menu 37, snapshots, or JSONL:

- `[env]` and `EnvObservation` show evidence supplied by the simulator/adapter.
- BodyMap shows the current fast gating/safety register.
- MapSurface and SurfaceGrid show current active working views, not yet WNM-derived projections.
- `(~~) [navmap-scope]` shows the diagnostic evidence/expected/residual/accepted/transition/outcome path.
- `[wm<->col]` shows current snapshot store/retrieve/apply behavior.
- `[gate:*]`, `[pick]`, and `[executed]` show current mixed-source policy authority.
- WorldGraph and Column writes show current long-term side effects; they are not proof of target consolidation order.

## Recommended deeper reading

- **NavMap Primacy and the CCA8 architecture hypothesis**
- **WorkingMap Layer Contracts**
- **Predictive Coding, Active Inference, Enactive Inference, and CCA8**
- **Tutorial on NavPatch**
- **Tutorial on WorkingMap**
- **Memory systems in CCA8**
- **Tutorial on Cognitive Cycles**
- **The WorldGraph in detail**


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



**Why the RCOS Matters**


Recent humanoid-robotics discussion suggests that the remaining barrier to general-purpose robots is not only high-level planning or language-guided action, but robust embodied interaction with the physical world. Modern systems have improved through reinforcement learning, better compliant actuators, and vision-language-action pipelines, yet they still struggle with the “small stuff” of real-world dexterity: contact, force, slip, resistance, inertia, and delicate manipulation. 

In that sense, a robotic cognitive operating system should not be viewed as a single end-to-end controller, but as the supervisory layer that coordinates world modeling, goals, memory, task selection, skill execution, safety, and recovery while delegating fast low-level force-sensitive control to specialized subsystems. 

This fits the CCA8 direction well: CCA8 can serve as the interpretable runtime that manages context, maps, affordances, episodic traces, and replanning, while lower layers handle tactile sensing, compliance, contact regulation, and micro-adjustment. 

The RCOS is an integration architecture: not “LLM + motors,” but a structured system that unifies cognition with embodied control.

### How CCA8 RCOS deals with the real world

The real world is not just a larger simulation. It is slow, noisy, expensive, partially observable, physically risky, and not perfectly repeatable. A robot may encounter shadows, sensor noise, slip, friction changes, unexpected contact, latency, battery limits, actuator faults, object deformation, and human interruption. Therefore, the CCA8 RCOS should not pretend that a high-level planner, an LLM, a VLA, or a learned world model can directly control the body without a supervisory layer.

CCA8's role is to manage the boundary between imagined futures and real consequences.

In this design, a learned world model is useful because it can rehearse possible futures before the robot acts. It may generate action-conditioned rollouts such as:

- "If I move forward, I may hit the obstacle."
- "If I push this object, it may move or fall."
- "If the floor is slippery, this path may be unsafe."
- "If lighting changes, the same object may still be present."

However, a world-model rollout is not truth. It is a proposal about what might happen. Current sensor/HAL evidence has protected source authority; the target accepted root WNM is the authorized current interpretation; BodyMap retains a rapid independent safety path. In the present implementation, authority remains distributed across BodyMap, WorkingMap, and policy-facing summaries while the WNM path is still diagnostic.

The intended RCOS discipline is:

    World models rehearse.
    LLM / VLA proposes.
    CCA8 validates.
    HAL executes.
    Reality corrects.
    CCA8 records provenance.

This gives CCA8 a practical answer to the sim-to-real problem. CCA8 does not eliminate the sim-to-real gap by internally solving all physics. Instead, it manages the gap by supervising how simulated or learned predictions are used.

The key operating rules are:

1. **Present-state authority**  
   Real observations override imagined rollouts. If a simulator or world model predicts a clear path but the current HAL sensor packet indicates an obstacle, contact fault, unstable posture, or unsafe zone, CCA8 treats the present observation as authoritative.

2. **Bounded action vocabulary**  
   CCA8 should issue bounded, interpretable commands such as `recover_fall`, `walk_forward`, `turn_left`, `inspect`, `return_to_dock`, `recharge`, or `stop`, rather than raw actuator torques. Low-level motor control remains the responsibility of the HAL, ROS 2, vendor SDK, VLA skill provider, or robot controller.

3. **World-model rollouts as candidate futures**  
   A world model may generate possible future states for candidate actions. These rollouts belong conceptually in WorkingMap.Scratch / WorkingMap.Creative or in a future WM1 / OutcomeSketch interface. They should be small, inspectable, uncertainty-aware summaries, not unbounded generated fantasies.

4. **Safety-gated validation**  
   Before action, CCA8 validates candidate commands against BodyMap, WorkingMap.MapSurface, SurfaceGrid, task goals, battery/fatigue state, hazard flags, uncertainty, and prior episode memory. If uncertainty is high, the correct action may be to stop, probe, zoom perception, ask for help, or choose a safer reversible action.

5. **HAL execution with feedback**  
   The HAL executes only the approved command and returns structured feedback: accepted, executing, done, blocked, failed, faulted, or emergency-stopped. This keeps hardware-specific execution below the RCOS boundary while preserving a clean cognitive contract.

6. **Reality-correction loop**  
   After each action, the next HAL / EnvObservation packet updates BodyMap and WorkingMap. CCA8 compares the observed result with the predicted postcondition. Prediction error is not a failure of the architecture; it is the learning signal that tells the RCOS when to update memory, revise policy confidence, retrieve a different prior, or mark a world model as unreliable in that context.

7. **Memory and provenance**  
   Every important real-world action should leave a trace: observation, body state, candidate policies, selected command, predicted outcome, HAL acknowledgement, observed outcome, prediction error, and safety notes. WorldGraph remains the thin symbolic index, while Columns / Engrams hold heavier scene, map, or sensor payloads.

In short, the CCA8 RCOS does not try to replace physics engines, robot foundation models, ROS 2, or hardware controllers. It organizes them. The scientific claim is not that CCA8 can simulate the whole physical world internally. The claim is that a memory-bearing, safety-gated, auditable cognitive layer can make better use of simulators, world models, LLMs, VLAs, and HALs by deciding when to trust them, when to constrain them, when to ignore them, and how to learn from the difference between prediction and reality.




### NavMap-centered RCOS and the motor abstraction boundary

CCA8 as RCOS is not intended to become an end-to-end motor controller. Its central cognitive object is the accepted root WNM and its
linked submaps. The RCOS should decide what the current situation is, which bounded intent is appropriate, what outcome is expected,
when uncertainty requires Probe or caution, and how failure changes the map and memory.

Detailed movement remains below the cognitive boundary:

    accepted WNM + drives + protected constraints
        -> primitive transaction and bounded intent
        -> ROS 2 / HAL / vendor controller / VLA skill provider
        -> automatic balance, force, trajectory, contact, and actuator control
        -> progress, completion, slip, contact, error, and safety feedback
        -> WNM and transaction revision

The same division applies biologically: the goat does not symbolically calculate hoof trajectories. Cerebellar-like and lower sensorimotor
systems perform automatic implementation. CCA8 models the temporal products relevant to cognition—motion, rate, expected continuation,
progress, and error—without attempting to reproduce the lower motor controller.

An LLM or learned world model is optional and subordinate. It may propose a candidate interpretation, primitive, or rollout, but it cannot
directly write OBSERVED evidence, the accepted WNM, protected goals, long-term memory, or actuators. Later experiments should test
whether an LLM plus NavMap architecture yields capabilities beyond a conventional wrapper; the README does not assume that result.


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






## RCOS implementation status and roadmap

### Overview

The CCA8 RCOS is intended to sit **above** ROS 2, vendor middleware, or a custom HAL, not to replace them.

In other words, the intended stack is:

- user task / application layer
- **CCA8 RCOS cognitive layer**
- ROS 2, vendor SDK, or custom HAL
- low-level OS / firmware
- hardware

This is an important design choice. The CCA8 RCOS is **not** trying to become:

- another ROS 2,
- another robot motion-planning middleware,
- another large language model chat product,
- or another end-to-end motor policy.

Instead, it is intended to become a **cognitive supervisory layer** that supplies:

- task persistence over long horizons,
- body-state awareness,
- working memory,
- episodic memory,
- policy gating,
- safety vetoes,
- bounded LLM / VLA arbitration,
- recovery after setbacks,
- and full provenance / replay of why actions were selected.

A useful one-line summary is:

> The CCA8 RCOS is meant to be the robot’s cognitive operating layer, while ROS 2 / HAL / vendor control stacks remain the execution substrate.

---

### Current implementation: Stage 1 RCOS sandbox

At the time of writing, the first concrete RCOS implementation is now present as a **Stage 1 simulated robotics sandbox**.

The new module is:

- `cca8_rcos.py`

Its purpose is deliberately narrow and foundational:

1. define a stable embodied command vocabulary,
2. simulate a small robot/goat world that responds to those commands,
3. expose a HAL-like seam,
4. and provide deterministic observations, metrics, and summaries that can later be connected to the main CCA8 controller.

This Stage 1 work does **not** yet let the main CCA8 Action Center control the robot sandbox directly. That is the next stage. Stage 1 exists to prove the RCOS seam cleanly before controller integration.

---

### What the new RCOS code does

The Stage 1 module currently provides two main pieces:

#### 1. `SimRobotGoatEnv`

A deterministic simulated robot/goat task world.

The default mission is:

    recover -> inspect target -> return to dock -> recharge -> rest

The simulated robot starts:

- fallen,
- at the dock,
- with a target marker elsewhere in the map,
- and with a hazard band that blocks the trivial straight-line path.

So even the first RCOS sandbox already includes:

- posture recovery,
- locomotion,
- hazard avoidance,
- goal-directed inspection,
- return-home behavior,
- recharge,
- and final rest.

This is intentionally more meaningful than a one-step “stand up once” demo.

#### 2. `SimRobotGoatHAL`

A very small HAL-like wrapper over the sandbox environment.

It exposes the seam that later robotics work should preserve:

- `reset(...)`
- `sense()`
- `act(command)`
- `status()`
- `emergency_stop()`

That means the current sandbox already behaves like a tiny embodiment layer, even though it is still purely simulated.

### Stage 1 command vocabulary

The current RCOS command set is intentionally small and inspectable:

- `stand`
- `recover_fall`
- `turn_left`
- `turn_right`
- `walk_forward`
- `inspect`
- `avoid_hazard`
- `return_to_dock`
- `recharge`
- `rest`
- `stop`

This vocabulary is important because it creates a clean contract between:

- future CCA8 policy selection,
- future LLM / adviser ranking,
- future VLA or skill-provider execution,
- and future real robot HAL adapters.

The RCOS should make decisions in terms of bounded, interpretable actions like these, not in terms of low-level motor torques.

### Stage 1 state, observations, and metrics

The SimRobotGoat sandbox keeps explicit robot state such as:

- position,
- heading,
- posture,
- battery,
- fatigue,
- mission progress,
- falls,
- safety violations,
- repeated-action loop count,
- and mission completion state.

It emits observations in the same broad style already used elsewhere in CCA8:

- `raw_sensors`
- `predicates`
- `cues`
- `env_meta`

This means the sandbox is already aligned with the rest of the architecture’s observation vocabulary.

The current episode summary includes:

- success / failure,
- done reason,
- steps,
- milestone vector,
- milestone score,
- falls,
- safety violations,
- repeated-action loop count,
- final battery / fatigue,
- target inspected?,
- returned to dock?,
- and final posture.

This gives the RCOS work an immediate experimental footing rather than being only a user-interface demo.

### Menu 50: interactive RCOS sandbox

The runner now exposes the Stage 1 sandbox through:

- **Menu 50: SimRobotGoat RCOS sandbox**

This menu is intentionally thin. It does not implement robot logic itself. It simply wraps the RCOS module so the user can:

- reset the episode,
- view the ASCII map,
- inspect current status / summary,
- inspect the current observation,
- step one Stage 1 command,
- and trigger HAL emergency stop.

This keeps the main runner lightweight while all RCOS simulation logic remains centralized in `cca8_rcos.py`.

One important implementation principle is:

> The RCOS sandbox is isolated from the main CCA8 simulation state.

In practical terms, you can enter Menu 50, test the robot sandbox, then return to the main menu without mutating the ordinary CCA8 WorldGraph / controller timeline. That isolation is deliberate and useful.

### Why this Stage 1 work matters

The Stage 1 sandbox is not meant to be impressive because it is large. It is meant to be useful because it is clean.

Before the main CCA8 controller or any real robot hardware is connected, we need to prove a minimal outer loop:

    command -> world update -> observation -> metrics -> summary

That gives us:

- deterministic debugging,
- unit-testable behavior,
- a portable HAL seam,
- a place to design RCOS metrics,
- and a simulation target for the next development stages.

In other words, Stage 1 is the first concrete proof that the RCOS direction is software, not just architecture drawings.

### Design stance of the RCOS

The current RCOS direction can be summarized in five rules.

#### 1. Do not reinvent ROS 2

CCA8 should sit above ROS 2, vendor SDKs, or a custom HAL. Those layers already solve transport, device interfaces, and many execution details.

#### 2. Keep the cognitive layer authoritative

The RCOS should decide:

- what the task is,
- what the agent currently believes,
- what is safe,
- which candidate policy should run,
- when memory should be retrieved,
- and how to explain the episode afterward.

#### 3. Keep action vocabulary bounded

Commands should stay interpretable and safety-checkable. Early RCOS work should use high-level commands like:

- walk forward,
- turn left,
- inspect,
- return to dock,
- and recover fall,

not raw actuator-level control.

#### 4. Treat LLMs and VLAs as bounded modules, not masters

Future LLM or VLA integration should be subordinate to the RCOS, not the other way around.

The intended rule is:

    LLM / VLA proposes.
    CCA8 validates.
    HAL executes.
    CCA8 records provenance.

#### 5. Preserve replay and auditability

Every important RCOS action should ultimately be explainable in terms of:

- observation,
- body state,
- working memory,
- episodic retrieval,
- candidate policies,
- selected policy,
- command sent,
- and observed outcome.

That is one of the most important ways in which the CCA8 RCOS differs from generic agent shells.

### Planned staged development

The intended RCOS development path is now:

#### Stage 1 — SimRobotGoat sandbox (implemented)

- deterministic simulated robot/goat world,
- HAL-like wrapper,
- command vocabulary,
- mission scoring,
- runner menu access,
- and unit tests.

#### Stage 2 — CCA8 controller drives SimRobotGoat

Connect the existing CCA8 controller / policy machinery to the RCOS sandbox so that:

- `EnvObservation` from SimRobotGoat updates CCA8 memory,
- CCA8 selects one bounded policy,
- that policy maps to one Stage 1 command,
- and the command is sent back into the simulated HAL.

This is the first true “CCA8 as RCOS controller” step.

#### Stage 3 — long-horizon RCOS benchmark

Strengthen the sandbox into a benchmark that includes:

- partial observability,
- setbacks,
- fall recovery,
- hazard avoidance,
- battery pressure,
- delayed completion,
- and recovery after interruption.

The important result to demonstrate is not just “the robot can do a task once,” but:

- it can maintain the task over time,
- remember what matters,
- recover from failure,
- and remain interpretable.

#### Stage 4 — bounded LLM adviser

Add a GPT-style adviser only at bounded ambiguity points.

The intended interface is not free-form robot control. Instead, the RCOS should send a small structured packet such as:

- current body state,
- task context,
- risk flags,
- memory summary,
- and candidate policies,

and receive back:

- recommended policy,
- ranking,
- rationale,
- confidence,
- and risk flags.

CCA8 remains authoritative.

#### Stage 5 — VLA / skill-provider integration

The RCOS should eventually be able to use a VLA or other embodied skill provider as a bounded module.

The intended decomposition is:

- CCA8 RCOS = memory, persistence, safety, policy gating, recovery, explanation
- LLM / reasoning model = high-level interpretation or bounded adviser
- VLA / motor skill provider = execution of specific embodied skills
- HAL / ROS 2 / vendor SDK = physical execution substrate

That means CCA8 should not try to outcompete robot foundation models directly. Instead, it should provide the cognitive operating layer above them.

#### Stage 6 — real hardware HAL adapters

After the simulated loop is stable, the same RCOS contract can be implemented for real embodiments, for example:

- a PetitCat-style mobile platform,
- a ROS 2 robot,
- a quadruped platform,
- or another supported body.

The important discipline is that the physical adapter should preserve the same high-level contract:

- `sense`
- `act`
- `status`
- `emergency_stop`

so that the RCOS stays portable.

### SimRobotGoat as the first benchmark embodiment

The choice of **SimRobotGoat** is intentional.

It preserves continuity with the existing newborn-goat cognitive architecture while still letting the project move toward robotics. In practical terms, it is “robot enough” to design an RCOS against, while remaining close to the original developmental theory.

The first benchmark embodiment therefore asks the right kind of question:

> Can a brain-inspired, memory-bearing cognitive layer keep a simple embodied agent working over a longer horizon than a reflex-only or script-only control stack?

That is much closer to the eventual robotics goal than simply adding more one-step menu actions.

### Research direction: what would make the RCOS scientifically interesting?

The scientific contribution is not:

- “CCA8 can call an API,”
- “CCA8 can drive a toy robot,”
- or “CCA8 has another menu.”

The scientifically interesting question is:

> Can a developmental, brain-inspired, auditable cognitive operating layer improve long-horizon embodied autonomy by adding memory, safety-gated control, recovery, and explainable policy selection above robot middleware and bounded model-based skill providers?

That research direction becomes stronger when the RCOS can demonstrate:

- task persistence,
- episodic readback,
- body-state-aware action gating,
- recovery after interruption,
- safe behavior under uncertainty,
- and replayable provenance.

This is the real RCOS target.







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







# Hardware preflight lane (host-readiness checks; device I/O pending)

When you run `--preflight`, Part 3 reports the configured HAL/body flags and performs five host-readiness checks that are useful for simulation and future robotics work:

1. CPU enumeration (`os.cpu_count()`)
2. monotonic high-resolution timer behavior (`perf_counter`)
3. temporary-file write capability
4. installed RAM against `CCA8_MIN_RAM_GB` (default 4 GiB)
5. free disk space against `CCA8_MIN_DISK_GB` (default 1 GiB)

A typical footer reports `hardware_robotics_checks = 5/5`. These are real host checks, but they are **not yet robot-device transport checks**. USB/serial/network handshakes, sensor enumeration, actuator enablement, estop/limit verification, and command round trips remain future HAL-adapter work.

The runner still prints the selected HAL/body configuration. You can supply future-facing configuration with:

`python cca8_run.py --hal --body hapty`

<img title="Goat Embodiment" src="docs/images/robot_goat.jpg"  alt="robot_goat" style="zoom:25%;" data-align="center">

### Q&A to help you learn this section

Q: Does `hardware_robotics_checks = 5/5` mean a physical robot was tested?
A: No. It means the host computer passed the CPU, timer, temporary-file, RAM, and disk checks. Physical transport, sensors, actuators, and estop paths are not yet exercised by this lane.

Q: How do I enable the hardware configuration fields for a future robot?
A: Start the runner with `--hal --body <name>`, for example `python cca8_run.py --hal --body hapty`. Until a matching HAL adapter is implemented, this identifies the intended embodiment but does not create a device connection.

Q: Will a failed host-readiness check make `--preflight` return a non-zero exit code?
A: Yes. Part 3 failures count as preflight failures. Future serious transport or safety failures should follow the same rule once device checks are implemented.

Q: Does the hardware lane change cognitive state?
A: No. It performs read-only host checks and reports configuration. WorldGraph, drives, WorkingMap, and policies should remain unaffected.






# FAQ / Pitfalls

- **“No path found to `pred:posture:standing`”** — You planned before creating the predicate (or before NOW is connected forward to it). Run one instinct step (menu **9**) first, add the predicate manually, or `--load` a session that already contains it. *(If you see `state:posture_standing`, that’s a legacy token; canonical is `pred:posture:standing`.)*
- **Repeated “standing” nodes** — Tightened `StandUp.trigger()` prevents refiring when a standing binding exists. If you see repeats, ensure you’re on the updated controller.
- **Autosave overwrote my old run** — Use a new filename for autosave (e.g., `--autosave session_YYYYMMDD.json`) or keep read-only load + new autosave path.
- **Loading says file not found** — We continue with a fresh session, the file will be created on your first autosave event.
  
  

***Q&A to help you learn this section***

Q: Why “No path found …” on a new session?  A: You planned before adding the predicate, run one instinct step.

Q: Why duplicate “standing” nodes?  A: Old controller, update to guarded StandUp.trigger().

Q: How to keep an old snapshot?  A: Autosave to a new filename.
Q: Is load failure fatal?  A: No, runner continues with a fresh session.







# Intro Glossary

This glossary distinguishes **current runtime objects** from **target architecture roles**. A familiar name does not by itself prove that the
object is authoritative.

## High-frequency terms

- **HybridEnvironment** — external simulated world and truth generator.
- **EnvState** — environment-side hidden truth; never the agent's belief.
- **EnvObservation** — one-tick evidence packet crossing into the agent; currently semantically rich.
- **Closed-loop cognitive cycle** — observe, update internal representations, select/execute one policy, send action to the environment,
  receive the next observation.
- **Ctx** — shared runtime contract containing counters, flags, handles, histories, and cross-cycle registers. It is not a cognitive theory.
- **Navigation Map / NavMap** — bounded spatially organized and relationally linked representation with frame, scale, features, entities,
  temporal information, links, provenance, and authority status.
- **Map Primacy** — doctrine that the map is the principal world representation; compact states are controls, derived readouts, or
  bookkeeping unless explicitly justified otherwise.
- **WorkingMap** — workspace/container. In the target architecture it owns the accepted root WNM, linked submaps, candidates, protected
  evidence/expected/retrieved layers, Scratch, Creative, projections, and bounded histories.
- **Working Navigation Map (WNM)** — the one map revision granted accepted-current root authority. It is a role/status, not necessarily a
  completely separate physical map schema.
- **Root WNM** — accepted whole-scene context linking SELF, attended entities, terrain, goals, hazards, and active submaps.
- **Linked submap** — body, maternal, nipple, terrain, hazard, object, route, or close-up map at its own frame/scale, linked to the accepted
  root without becoming a second reality.
- **Evidence NavMap** — current modality or adapter-derived evidence with source, quality, frame, time, missingness, and transforms.
- **Local NavMap** — stored or newly created same-modality map matched and revised from evidence.
- **NavPatch** — bounded attended map fragment for an entity, terrain motif, contact pattern, hazard, landmark, goal, or scene region.
- **MapSurface** — currently an observation-driven policy-facing semantic scene; target role is a derived entity/relation projection of a
  named accepted WNM revision.
- **SurfaceGrid** — local traversability/topology/hazard/goal/UNKNOWN view; target role is a derived WNM/submap projection.
- **NavSummary** — compact topology/focus readout for efficient policy access; not the WNM.
- **BodyMap** — fast body and near-space safety/gating register. It remains an independent rapid protection path while ordinarily
  corresponding to WNM body relations.
- **Scratch** — protected transient workspace for action chains, comparisons, ambiguity, transactions, local transformations, and bounded
  surprise episodes.
- **Creative** — protected imagined/counterfactual candidates. Creative content is not observed, accepted, or executable without an
  explicit authority operation.
- **WorldGraph** — sparse episode, action, keyframe, retrieval, and pointer index. It tells the system where to look; it is not the complete
  world model or current truth.
- **Columns / Engrams** — rich durable payload store for maps, prototypes, trajectories, transformations, and episodes. A Python Column
  is a computational storage unit inspired by cortical minicolumns, not necessarily a one-to-one biological minicolumn.
- **Binding** — WorldGraph episode/index node containing tags, metadata, edges, and optional Column pointers.
- **Keyframe** — boundary at which selected map or episode content may be stored, indexed, retrieved, or compared.
- **Prediction / expected map** — unconfirmed current or successor map generated from prior WNM, primitive, context, transition, or motion.
- **Structured residual** — map-linked comparison showing which regions, entities, relations, features, frames, or sources differ. A scalar
  error is only a summary.
- **NavMap operator** — elementary map operation such as align, segment, compose, query, retrieve, match, compare, revise, accept,
  project, consolidate, or prune.
- **Primitive** — instinctive or learned map-based procedure that queries a WNM, emits a bounded intent, and predicts a local
  transformation; Python classes remain the safe execution substrate.
- **Primitive transaction** — explicit record joining accepted-before map, trigger/safety evidence, intent, expected transformation,
  progress, outcome, accepted-after map, and provenance.
- **Probe** — epistemic primitive that seeks information about a named uncertainty under bounded cost and safety constraints.
- **Quasi-predictive coding** — expected maps are compared with evidence maps and residuals guide map revision; not a claim of formal
  cortical predictive-coding mathematics.
- **Quasi-active inference** — actions satisfy drives or reduce uncertainty in a closed perception/action loop; not validated formal
  variational free-energy or EFE policy selection.
- **RCOS** — Robotic Cognitive Operating System: cognitive supervisory layer above HAL/middleware/skill providers and below task/apps.

## Source and authority classes

- **OBSERVED / EVIDENCE** — current sensor-derived support.
- **EXPECTED** — predicted current or successor content.
- **CANDIDATE** — provisional interpretation.
- **ACCEPTED** — authorized current use in the one root WNM; source remains recoverable.
- **INFERRED** — operator-derived, not directly observed.
- **RETRIEVED** — activated long-term memory.
- **IMAGINED** — Creative/counterfactual proposal.
- **APPRAISED** — control interpretation such as surprise or threat relevance.
- **HISTORICAL** — past accepted/evidence/transaction content.
- **REJECTED** — declined candidate with reason.
- **UNKNOWN** — no candidate or field is adequately supported.

No operator may convert EXPECTED, RETRIEVED, INFERRED, IMAGINED, APPRAISED, or HISTORICAL content into
OBSERVED.

## Current versus target shorthand

| Question | Current implementation | Target architecture |
|---|---|---|
| What controls immediate policy? | BodyMap, WorkingMap/MapSurface, SurfaceGrid/NavSummary, WorldGraph history, hints, drives, and policy bridges | WNM queries and named projections plus drives/protected safety; BodyMap retains rapid veto |
| What is accepted-current NavMap? | Evidence-first diagnostic shadow | One canonical root WNM revision |
| What is MapSurface? | Active observation-driven semantic workspace | Derived entity/relation projection of accepted WNM |
| What is SurfaceGrid? | Active policy-facing topology scaffold | Derived conservative topology projection of WNM/submaps |
| What does retrieval do? | Snapshot/patch/context mechanisms can influence WorkingMap and hints | Activates protected map candidates that must be aligned, compared, and accepted |
| Where is long-term content? | WorldGraph plus Column engrams | WorldGraph sparse index plus Columns rich map library |

## Counters and runtime terms

- **env_step / step_index** — environment counter since reset.
- **controller_steps** — number of Action Center invocations.
- **cog_cycles** — closed-loop/productive cycle counter under current runner semantics.
- **ticks / age_days / boundary_no / TemporalContext** — physiology/development/episode timing aids; not substitutes for map-bound motion.
- **NOW / NOW_ORIGIN / LATEST** — WorldGraph orientation and write pointers; not the accepted WNM.
- **Attach modes** — `now`, `latest`, or `none` determine how a new WorldGraph binding is connected.

## Reading rule

When a compact variable appears, ask whether it is:

1. a genuine physiological/control state;
2. a derived readout from a named map revision;
3. software bookkeeping;
4. or an accidental competing world model.

That question is the practical safeguard against turning CCA8 into a predicate-first or NETL-like architecture while retaining NavMap
names.


# INSTRUCTIVE TUTORIAL

This tutorial explains the CCA8 architecture as a map-centered system while remaining honest about the current implementation. The
current goat already runs closed-loop and contains many map, memory, prediction, policy, and RCOS components. The major research task
is to reorganize authority so those parts behave as one WNM-centered mammalian architecture rather than as a committee of states and
parallel structures.

## 1. Begin with the environment boundary

The simulator owns `EnvState`, its hidden truth. CCA8 receives only `EnvObservation`. The current observation packet already contains
interpreted concepts such as posture, maternal distance, nipple state, shelter, hazard, and stage. This is useful development scaffolding,
but the target architecture moves more sensory shaping, Local NavMap matching, temporal binding, segmentation, and entity formation
inside CCA8.

    external world / HAL
        -> evidence packet or modality signals
        -> internal maps

The first rule is therefore:

> Evidence supplied by the environment is not automatically the agent's accepted belief.

## 2. The map-first theory

The CCA hypothesis is not that every piece of software must be a NavMap. It is that the animal's world cognition is primarily map-shaped.

A state-first implementation might say:

    posture = fallen
    mom_distance = far
    cliff_near = true

A map-first architecture represents SELF, body orientation and contact, Mom, terrain, the cliff region, motion, uncertainty, and their
relationships. It may then derive the three compact values for efficient gating.

The distinction is architectural:

    map pattern
        -> compact readout
        -> primitive query or safety gate

not:

    independent compact states
        -> condition forest
        -> map retained only for display

Drives, arousal, developmental stage, controller status, counters, and flags can remain compact states because they are not competing
world models.

## 3. What a NavMap carries

A useful NavMap may include:

- identity, schema, revision, parent revision, and lifetime;
- a declared frame, viewpoint, scale, orientation, and extent;
- cells, regions, geometry, topology, surfaces, boundaries, and unknown areas;
- entities, provisional roles/identities, continuity, occlusion, merge, and split history;
- visual, auditory, tactile, vestibular, proprioceptive, olfactory, interoceptive, and derived features;
- motion direction, rate, trajectory, persistence, contact duration, and expected continuation;
- affordances and links to primitive maps;
- links to close-ups, parent scenes, prototypes, episodes, successors, and contexts;
- source, quality, support, conflict, uncertainty, and authority status.

Graph algorithms help with adjacency and paths, but the map also retains geometry, scale, frames, and spatial embedding.

## 4. The NavMap family

CCA8 needs a family of compatible map roles rather than one giant class:

1. modality evidence maps;
2. stored Local NavMaps and prototypes;
3. NavPatches for attended entities, terrain, hazards, contacts, landmarks, goals, or scene motifs;
4. multisensory scene/object candidates;
5. one accepted root WNM with linked submaps;
6. expected current or successor maps;
7. episodic and generalized maps in Columns;
8. primitive/transformation maps.

The WNM is the one map revision with accepted-current authority. Other maps can be active as evidence, candidates, retrievals,
expectations, or focused submaps without becoming equally authoritative realities.

## 5. How long-term memory builds the present map

Columns and WorldGraph are not merely archives used after perception.

    current partial evidence
        -> WorldGraph identifies a bounded memory neighborhood
        -> Columns provide rich candidate maps
        -> align and compare
        -> use suitable stored structure as a prior
        -> preserve reliable current evidence
        -> compose candidate scenes
        -> accept one root WNM or UNKNOWN

WorldGraph is the sparse index. Columns are the rich distributed map library. Retrieval is not truth.

## 6. One root WNM and linked submaps

The accepted root WNM can represent the whole active situation while linking maps at other scales:

    root scene
        -> SELF body/posture map
        -> maternal body map
        -> nipple/mouth close-up
        -> local terrain and cliff geometry
        -> shelter/route context

Attention can activate a close-up and later return to the parent. The architecture remains one coherent current world rather than a set of
contradictory scenes competing for actuators.

## 7. Current runtime memory layers

The current implementation contains:

| Layer | What it does today | Target relationship |
|---|---|---|
| BodyMap | Fast active gating and safety | Rapid safety path synchronized with WNM body relations |
| MapSurface | Observation-driven semantic entity/slot workspace | Derived entity/relation projection |
| SurfaceGrid/NavSummary | Active local topology and compact policy support | Derived WNM/submap topology projection |
| Scratch | Action chains, ambiguity, transient records | Transactions, residuals, bounded map operations and surprise episodes |
| Creative | Candidate outcomes | Protected imagined maps, never direct truth |
| WorldGraph | Sparse long-term episode/index/planning graph | Sparse retrieval and episode index, not current truth |
| Columns | Heavy snapshot, patch, and engram payloads | Rich durable map library |
| NavMap runtime | Evidence/expected/residual/accepted/transition/outcome diagnostics | Bridge toward canonical WNM and map-native learning |

The current runtime is useful precisely because these structures already work. The migration changes their authority one relation at a time.

## 8. Map operators

Behavioral primitives such as StandUp call elementary NavMap operators:

- focus and zoom;
- align and reframe;
- segment and track;
- bind and compose;
- query relationships and paths;
- retrieve candidates;
- match and rank;
- compare and produce structured residuals;
- propose and apply versioned revisions;
- accept one root or UNKNOWN;
- predict a short successor;
- project compact views;
- consolidate and index;
- expire and prune.

The operator output should preserve enough structure to explain the result. Matching should not return only `0.83`; it should identify the
correspondence, transform, coverage, mismatches, missing regions, novelty, source quality, rank, margin, and ambiguity.

## 9. Primitives operate on maps

A current Python policy often reads BodyMap, MapSurface, NavSummary, graph history, hints, and drives. The target primitive instead begins
from WNM queries plus protected compact controls.

StandUp conceptually reads SELF posture/contact geometry, emits a `STAND` intent below the motor boundary, and creates an expected
successor map in which SELF is upright and supported. The next evidence map confirms, revises, fails, or leaves the transformation
UNKNOWN.

### Current StandUp authority: Phase 3D

New `Ctx` sessions now use `navmap_standup_authority_mode="default"`. Actionable maintained SELF-ground geometry is therefore the
normal cognitive source for the StandUp trigger and expected successor. The migration remains bounded and reversible:

- `default` uses the maintained NavMap/WNM when support is fresh or aging;
- `guarded` preserves the Phase 3C feature-flagged experiment;
- `legacy` restores the historical BodyMap/PolicyRuntime gate for comparison and rollback;
- stale, invalidated, missing, ambiguous, or transform-incomplete map content falls back to the complete legacy gate;
- fresh BodyMap `fallen` remains a protected rapid safety override;
- PolicyRuntime and the existing Python behavioral primitive still execute StandUp;
- BodyMap and legacy StandUp code are retained rather than retired.

The compatibility field `navmap_standup_guarded_enabled` remains temporarily available: `None` uses the canonical mode, `True` forces
`guarded`, and `False` forces `legacy`.

FollowMom locates SELF and the maternal entity, checks relative motion and intervening terrain, chooses a safe reachable direction, emits
a bounded intent, and predicts a modest change in the SELF–MOM relation.

Probe names an uncertainty target and predicts what additional observation should reduce it.

The implementation may still calculate booleans, classes, and distances. Those are queries over a map rather than the whole cognition.

## 10. Motor implementation is below CCA8

CCA8 does not symbolically calculate hoof trajectories, balance corrections, force control, or muscle recruitment. Biological or robotic
lower controllers implement the movement. CCA8 receives time-stamped progress, contact, slip, completion, failure, and safety products.
Temporal/cerebellar-like processing converts changing sequences into map features such as approaching, falling, rising, accelerating,
contact duration, and time-to-hazard.

This is also the RCOS boundary: the cognitive layer selects and supervises intent; HAL/ROS/vendor/VLA/firmware systems perform detailed
execution.

## 11. Prediction and active perception

CCA8 is quasi-predictive-coding-like:

    accepted WNM + primitive + motion/local transition
        -> expected successor map

    expected successor <-> new evidence
        -> structured residual
        -> map revision, attention, learning, protection, or surprise appraisal

CCA8 is quasi-active-inference-like because action changes the world and sometimes seeks information. FollowMom changes spatial
relations; StandUp changes body-terrain relations; Probe changes sampling or viewpoint.

The system is not presently a formal variational free-energy or validated EFE policy-selection architecture.

## 12. Surprise is bounded goat processing

Most cycles should be rapid:

    predict -> observe -> compare -> revise WNM -> act

When reliable, persistent, important evidence violates the current map or expected transformation, CCA8 may spend one or a few extra
passes:

- focus a mismatch;
- resample the same modality;
- sample one additional modality;
- retrieve a very small candidate set;
- zoom once;
- Probe once;
- hold or interrupt when safe;
- retreat, protect, recover, or preserve UNKNOWN.

CCA8 does not normally replace external evidence with internally transformed maps for many recursive cycles. CCA4 analogy and human
causal deliberation belong to later architectures.

## 13. Current cognitive cycle versus target cycle

Current:

    EnvObservation
        -> BodyMap and observation-driven working structures
        -> NavMap diagnostic shadows
        -> keyframe/graph/Column side effects
        -> mixed-source policy selection
        -> controller primitive
        -> next observation

Target:

    modality evidence
        -> Local maps, temporal binding, segmentation, patches
        -> bounded long-term retrieval
        -> candidate scene maps
        -> one accepted root WNM
        -> derived views
        -> map-native primitive transaction
        -> lower motor intent
        -> progress and new evidence
        -> structured comparison, revision, and selective memory

## 14. How to read the current terminal

- Menu 35 shows one annotated closed-loop cycle.
- Menu 37 shows a compact multi-cycle story.
- `[env]` shows simulator-side truth and events.
- BodyMap lines show fast current gating information.
- MapSurface/SurfaceGrid lines show present working scaffolds.
- `(~~) [navmap-scope]` shows the diagnostic map comparison path.
- `[wm<->col]` shows snapshot storage/retrieval/apply behavior.
- `[gate:*]`, `[pick]`, and `[executed]` show current policy authority.

Do not infer target architecture from a terminal label. The source code, tests, and deterministic traces decide what currently has authority.

## 15. The experimental obligation

The first task is to build a coherent map-first goat. Later experiments should ask whether map-first control improves flexibility,
partial-observability recovery, transfer, safety, interpretability, learning, and LLM synergy relative to state-first or graph-first alternatives.
A negative result would be scientifically useful if the implementation faithfully represents the hypothesis.


# DETAILED TUTORIALS AND TECHNICAL DEEP DIVES


NOTE: This README.md file exceeds the 512K GitHub rendering limit. Therefore, some topics
    are not accessible by scrolling, but via the Table of Contents which will link you
    to another similar README.md file.


# Predictive Coding, Active Inference, Enactive Inference, and CCA8

CCA8 is related to predictive coding, active inference, and enactive robotics, but it begins from a different architectural commitment:
**the useful cognitive product is an updated map**.

## Map-centered predictive processing

Predictive coding is often summarized as prediction, residual error, and belief update. CCA8 asks what the belief update is made of. Its
answer is a Navigation Map or an accepted WNM revision.

    previous accepted WNM + selected primitive + motion/context
        -> expected current or successor map

    current sensory evidence
        -> evidence map

    expected map <-> evidence map
        -> structured residual

    residual + source reliability + persistence + body/safety relevance
        -> revise, keep, create, preserve UNKNOWN, focus, Probe, protect, or learn

Prediction error is a signal attached to a specific comparison. It is not the central cognitive object and cannot become an independent
policy command.

## Quasi-predictive coding

CCA8 resembles predictive coding because:

- previous maps and stored experience generate expectations;
- current evidence is compared with those expectations;
- mismatch changes the accepted map, attention, retrieval, or learning;
- top-down context can help interpret missing or ambiguous evidence;
- reliable incompatible evidence defeats the prior.

CCA8 does not claim that the entire system minimizes one prediction-error scalar or reproduces cortical predictive-coding microcircuits.
The objective is a useful embodied map, not error minimization for its own sake.

## Quasi-active inference

CCA8 resembles active inference because perception and action form a closed loop. The goat acts to satisfy drives and sometimes to gain
information.

    hunger + accepted maternal map
        -> SeekNipple / FollowMom intent
        -> changed SELF-MOM-nipple relations
        -> new evidence

    ambiguous patch
        -> Probe or focused sampling
        -> evidence expected to reduce uncertainty
        -> revised WNM or preserved UNKNOWN

CCA8 does not presently maintain a validated variational generative model, minimize variational free energy, or select policies through
formal expected free energy. EFE-like scoring remains diagnostic unless a later controlled experiment justifies promotion.

## Enactive interpretation

Enactive approaches emphasize action-outcome interaction. CCA8 agrees that cognition develops through interaction, but represents the
interaction as a transformation among maps:

    accepted before-map + primitive
        -> expected successor map

    actual next evidence
        -> observed after-map

    expected successor <-> observed after-map
        -> structured residual and outcome record

Thus CCA8 can be described as **NavMap-centered enactive predictive control**.

## Context is a prior, not a hallucination engine

Context may narrow candidates, support continuity, or fill missing regions when evidence is weak. It may not overwrite strong direct or
safety-relevant evidence.

    expected nursing context
        + weak missing visual evidence
        -> maternal candidate may remain plausible

    expected nursing context
        + reliable predator/hazard evidence
        -> context break, map revision, and protection

Retrieved, imagined, and expected maps preserve their source class. Acceptance authorizes current use but does not relabel them as
observed.

## Long-term memory is inside the predictive loop

The predictive loop is not only WNM-to-sensory comparison. Current evidence retrieves and tests stored maps:

    partial evidence
        -> WorldGraph index query
        -> bounded Column map candidates
        -> align, match, and compare
        -> useful prior structure
        -> candidate scene
        -> one accepted root WNM or UNKNOWN

The current WNM then influences what is expected and which memory neighborhood is useful during the next cycle.

## Map-bound temporal prediction

CCA8 does not need to store every moment as a disconnected snapshot. Sequential/Error and cerebellar-like products should bind change
onto map regions and entities:

- Mom approaching or receding;
- SELF falling, rising, or slipping;
- an edge expanding in the visual field;
- contact beginning, persisting, or ending;
- expected continuation and time-to-hazard.

Lower motor systems compute and execute fast dynamics. CCA8 uses their temporal products to update maps and primitive transactions.

## Structured residuals rather than scalar error alone

A useful residual can say:

- SELF was expected upright but remains lateral to the ground;
- Mom was expected near-left but current evidence places her far-right;
- a predicted safe route is blocked in one region;
- nipple contact was expected but tactile evidence is missing;
- a new moving region appeared near the cliff.

A scalar count or magnitude may summarize the mismatch, but the linked structural record is what supports attention, learning,
explanation, and safe action.

## Controlled map maintenance, not mindless minimization

Intelligent map maintenance can:

- keep a map when evidence fits;
- revise a map when moderate reliable differences appear;
- create a new candidate when all stored maps fit poorly;
- preserve ambiguity when candidates remain close;
- retain UNKNOWN when evidence is inadequate;
- Probe when a safe action can resolve uncertainty;
- reject a familiar prior when current evidence is incompatible.

A system that only restores familiar priors or minimizes immediate mismatch may become rigid, avoid novelty, or stabilize the wrong map.

## Goat-level expectation versus human counterfactual reasoning

CCA8 may predict short local transformations:

    fallen + StandUp
        -> expect upright supported SELF

    Mom far + FollowMom
        -> expect a modest improvement in relative geometry

    ambiguous patch + Probe
        -> expect a reduction in uncertainty

This is not sustained human counterfactual simulation. CCA8 does not normally suppress current evidence for many cycles while
recursively manipulating internally generated maps. Full causal reasoning, CCA4 transformation-transfer analogy, and compositional
language are deferred.

## Surprise as a processing-mode change

Residual magnitude alone is not surprise. CCA8 appraises source reliability, persistence, cross-modal support, body/safety relevance,
transition explainability, action state, reversibility, and cost of error.

    routine:
        predict -> observe -> compare -> revise WNM -> act

    bounded surprise:
        structured residual
            -> appraisal
            -> focus / resample / one extra modality / small retrieval / zoom / one Probe / protect
            -> accept / revise / preserve UNKNOWN / retreat / recover
            -> named resolution and mandatory exit

This is a bounded goat-level allocation of additional resources, not a full human System 2.

## Psychosis and later human architecture

The CCA research programme hypothesizes that stronger recursive map generation and reprocessing can support human causal reasoning,
analogy, imagination, and language while also creating failure modes in which internally generated or retrieved maps acquire inappropriate
authority. CCA8 is deliberately the stable goat-level substrate before those mechanisms are added.

This is an architectural research hypothesis, not a clinical claim. CCA8 should first demonstrate one coherent accepted WNM and strict
provenance among observed, expected, retrieved, inferred, and imagined content.

## RCOS and LLM implications

For robotics, a world model or LLM can propose an expected map, interpretation, or action. CCA8/RCOS validates that proposal against
current evidence, the accepted WNM, BodyMap safety, mission constraints, and provenance before issuing a bounded intent.

    world model rehearses
    LLM / VLA proposes
    CCA8 validates
    HAL executes
    reality corrects
    CCA8 records map-linked outcome

Whether this architecture provides more than an agentic wrapper is an experiment, not an assumption.

## Current implementation status

The runner currently provides:

- `scene_body` evidence NavMap payloads;
- expected-current augmentation from prior map/context/selected primitive;
- expected-versus-evidence comparison and residuals;
- evidence-first accepted-current diagnostic records;
- action-conditioned transitions and policy-outcome indexing;
- an Oscilloscope view of evidence, expected, residual, accepted, transition, and outcome;
- active but separate prediction-feedback histories and mismatch effects.

The accepted-current record is not yet the canonical root WNM. Policies still read a mixture of BodyMap, WorkingMap/MapSurface,
SurfaceGrid/NavSummary, WorldGraph history, retrieval hints, drives, and experiment bridges. The implementation programme therefore
promotes map authority gradually through shadow, compare, guarded, and default stages.

## One-line summary

> CCA8 treats cognition as embodied, enactive, predictive **map maintenance**: evidence and memory construct an accepted WNM,
> primitives predict and attempt local map transformations, reality supplies the next evidence, and structured residuals revise maps and
> learning.


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









# The WorldGraph in detail

> **Architecture status:** this section documents the current sparse symbolic episode/index implementation. WorldGraph is not the
> accepted WNM and should not be interpreted as the goat's complete present world model. In the target architecture it indexes and
> retrieves rich Column maps that participate in WNM construction.

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






**NavPatch: patch-level recognition on MapSurface**

**NavPatch**, a lightweight recognition layer on top of MapSurface: each cycle we extract observed patches (e.g., scene/mom/shelter/cliff), match them against stored prototypes (top-K + confidence), optionally bias matching with priors *only under ambiguity*, and record prediction error when evidence disagrees. The main deliverable is traceability: runs become easy to debug and evaluate via the human-readable `terminal.txt` and the machine-parsable per-cycle `cycle_log.jsonl`. See the deep dive: [Phase X — NavPatch](#phase-x--navpatch).





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
  
   
  (state)  pred:posture:fallen
     │
     ├─then→  (action) action:push_up
     │
     ├─then→  (action) action:extend_legs
     │
     └─then→  (state)  pred:posture:standing
  
   

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



 markdown
| Family     | Examples                                                                                                                                                           | Purpose                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `pred:`    | `pred:born`, `pred:posture:standing`, `pred:nipple:latched`, `pred:milk:drinking`, `pred:event:fall_detected`, `pred:goal:safe_standing`, `pred:drive:hunger_high` | planner targets; human labels        |
| `cue:`     | `cue:scent:milk`, `cue:sound:bleat:mom`, `cue:vision:silhouette:mom`, `cue:terrain:rocky`, `cue:vestibular:fall`                                                  | policy triggers; not planner goals   |
| `anchor:`  | `anchor:NOW`, `anchor:HERE`                                                                                                                                        | orientation; also in `anchors` map   |
| `action:`  | `action:push_up`, `action:extend_legs`, `action:orient_to_mom`, `action:bleat_twice`                                                                              | explicit motor / behavioral steps    |
| Edge label | `then` (default), and optional human aliases like `"approach"`, `"search"`, `"latch"`, `"suckle"`                                                                  | episode flow; semantics = “then”     |
 



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


From the runner (current grouped menu):

1. **Capture scene → emit cue/predicate with tiny engram** (menu **13**):

   
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
    menu 13 → channel=vision, token=silhouette:mom, family=cue, attach=now

* Creates `bX: [cue:vision:silhouette:mom]`

* Adds `NOW --then--> bX`

* Attaches `engrams["column01"].id = <engram_id>`

* (Optional) a policy may react (e.g., orient or follow)

**B. Predicate + scene pointer (if plannable state)**
    menu 13 → family=pred, token=location:mom:north_forest, attach=latest

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

## Architectural direction

CCA8 is migrating from distributed state-first control toward one accepted root WNM with linked submaps. The current source tree is
modular enough to support that work, but module ownership does not by itself establish cognitive authority.

The intended dependency direction is:

    environment / HAL evidence
        -> observation and map-processing owners
        -> WorkingMap-owned accepted WNM and projections
        -> PolicyRuntime supervision
        -> controller primitive execution
        -> environment / HAL

`cca8_run.py` remains the executable composition root and compatibility facade. Extracted runtime modules must not import the runner.
The runner constructs the session, installs hook bundles, coordinates cycle order, hosts menus, wires persistence and experiments, and
preserves historical imports and monkeypatch seams.

## Modules and current ownership

The canonical component list used by `versions_dict()`, `versions_text()`, and `python cca8_run.py --about` is
`_CCA8_COMPONENT_REGISTRY` in `cca8_run.py`.

| Module | Current responsibility and architecture status |
|---|---|
| `cca8_run.py` | Entry point, session construction, high-level cycle orchestration, menu dispatch, persistence wiring, callback installation, and compatibility facade |
| `cca8_context.py` | `Ctx`, experiment configuration, counters, flags, handles, histories, and cross-cycle registers; useful mutable contract but a high-risk hidden-authority surface |
| `cca8_env.py` | `EnvState`, `EnvObservation`, storyboard dynamics, `PerceptionAdapter`, and reset/step boundary; supplies interpreted evidence, not agent belief |
| `cca8_observation_runtime.py` | Masking, BodyMap updates, Sequential/Error handoffs, current legacy MapSurface/SurfaceGrid/NavPatch injection, keyframes, sparse graph writes, and cycle records |
| `cca8_navmap.py` | Pure versioned NavMap payloads, matching, residual, learning proposal, update, transition, and outcome operators; substrate rather than runtime authority |
| `cca8_navmap_runtime.py` | Ctx-local evidence, expected-current, accepted-current shadow, WNM-surface bridge, transitions, outcome index, scope, histories, and Oscilloscope integration |
| `cca8_predictive.py` | Pending expectations, expected-slot augmentation, next-observation comparison, bounded histories, feedback, and rendering; map-linked signal rather than cognitive product |
| `cca8_working_memory.py` | WorkingMap, MapSurface, SurfaceGrid, NavSummary, NavPatch orchestration, salience, Scratch, Creative, retrieval, map switching, zoom, and Probe; target owner of root WNM/protected layers or its stable owned record module |
| `cca8_policy_runtime.py` | High-level gates, newborn bridges, safety filtering, arbitration, RL/LLM tie-breaking, EFE diagnostics, Probe, Scratch provenance, Creative scoring; current mixed-source policy authority |
| `cca8_controller.py` | Drives, primitive classes, lower Action Center execution, BodyMap readers, and skill ledger; lower cognitive/motor abstraction boundary |
| `cca8_reporting.py` | Snapshots, WorkingMap/entity displays, temporal/cycle HUDs, transcript support, and diagnostic rendering; current posture-discrepancy mutation remains documented until explicitly moved |
| `cca8_navpatch.py` | NavPatch and SurfaceGrid schemas, composition, matching support, and fragment helpers |
| `cca8_world_graph.py` | Sparse episode/retrieval/index graph, bindings, anchors, BFS/Dijkstra, persistence, and Column pointers; not complete world model or current truth |
| `cca8_column.py` | Heavy durable engram/map payload store; no direct acceptance authority |
| `cca8_features.py` | Typed feature payloads, fact metadata, and temporal linkage |
| `cca8_temporal.py` | Soft procedural clock, drift/boundary operations, and temporal similarity; not a substitute for motion bound onto maps |
| `cca8_cli.py` | CLI parsing and presentation support |
| `cca8_profiles.py` | Profile selection, developmental narratives, defaults, and bounded demonstrations |
| `cca8_guidance.py` | User-facing explanations and tutorial support |
| `cca8_teaching.py` | Verbose cycle annotations used by Menu 35 |
| `cca8_preflight.py` | Test, architecture-probe, host/hardware-readiness, and system-fitness validation wall |
| `cca8_experiments.py` | Experiment definitions, stressors, conditions, scoring, statistics, JSON/JSONL output, and Menu 49 |
| `cca8_openai.py` | Optional bounded OpenAI adviser and structured request/response support |
| `cca8_rcos.py` | SimRobotGoat/RCOS mission-state, command vocabulary, supervision, and HAL-like sandbox seam |
| `cca8_rcos_experiments.py` | RCOS long-horizon experiments, perturbations, repeats, and ablations |
| `cca8_state_integrity.py` | Long-horizon state-integrity metrics, guards, and repair research support |
| `cca8_test_fixtures.py` | Deterministic fixtures for tests, preflight, and demonstrations |

Publication and validation adjuncts remain part of the authoritative repository and should not be casually modified during core architecture
work. Run `python cca8_run.py --about` for the exact component versions and source paths in the checkout being executed.

## Authority versus ownership

A module can own a record without that record controlling behavior. At the current baseline:

- BodyMap, WorkingMap/MapSurface, SurfaceGrid/NavSummary, WorldGraph history, retrieval hints, drives, and policy bridges can affect
  action.
- accepted-current NavMap and `working_navmap_surface_v1` are diagnostic shadows.
- EFE calculation is diagnostic; `efe_selection_enabled` appears dormant.
- reporting is not yet guaranteed side-effect free.
- the preserved second BodyMap update appears redundant but remains unchanged until trace confirmation.

The staged migration changes one authority relation at a time while preserving working behavior, safety, tests, publications, and
compatibility seams.

## Architecture Q&A

**Which module is the composition root?**  
`cca8_run.py`.

**Which module owns the pure NavMap schemas and operators?**  
`cca8_navmap.py`.

**Which module owns current diagnostic NavMap runtime integration?**  
`cca8_navmap_runtime.py`.

**Which module owns WorkingMap and the future root-WNM workspace contract?**  
`cca8_working_memory.py`, or a small stable record module owned by it if later justified.

**Which modules supervise and execute policies?**  
`cca8_policy_runtime.py` supervises/gates/arbitrates; `cca8_controller.py` retains lower primitive execution and the motor abstraction seam.

**Where do rich maps live long-term?**  
Columns. WorldGraph stores sparse indexes, episodes, and pointers.

**How do I verify the actual checkout?**  
Run `python cca8_run.py --about` and the full preflight wall.


# Action Selection: Drives, Policies, Action Center

## Current implementation

Current CCA8 policies are readable Python classes with gates, triggers, and execute methods. `cca8_policy_runtime.py` forms and filters the
candidate set, applies safety and newborn bridges, supports optional RL/LLM tie-breaking, and selects one winner. `cca8_controller.py`
executes the selected primitive and maintains Drives and the skill ledger.

The current policy interface reads a mixture of:

- BodyMap;
- WorkingMap/MapSurface;
- SurfaceGrid/NavSummary;
- WorldGraph history and retrieval hints;
- Drives and developmental context;
- selected experiment and repair bridges.

This mixed-source control is the current implementation, not the target final architecture.

## Target map-native primitive contract

A CCA8 primitive should increasingly operate on the accepted WNM or named projections derived from it. The primitive's cognitive content
can be represented as a specialized map plus a simple Python execution class.

A primitive specifies:

- trigger map pattern and required entities/relations;
- drive, developmental, and arousal modulation;
- map queries and operators;
- safety constraints and interruption rules;
- bounded action intent;
- expected local map transformation;
- completion, failure, and UNKNOWN evidence patterns;
- supporting episodes, outcome reliability, and learned exceptions.

The implementation may still derive efficient booleans or distances. Those values should retain provenance to the source WNM revision.

## Allowed -> triggered -> executed

1. **Gating** — is the primitive allowed under developmental, safety, mission, and transaction constraints?
2. **Triggering** — does the current WNM pattern, compact drive state, and protected context make the primitive applicable?
3. **Execution** — which triggered primitive wins, and what bounded intent is sent below the motor boundary?

Safety remains prior to ordinary scoring. BodyMap retains a rapid protective veto even after WNM-derived policy access is promoted.

## Example: StandUp

Current implementation may use compact posture fields and policy guards. The target cognitive interpretation is:

    accepted WNM before:
        SELF body axis lateral to ground
        broad lateral contact
        head low
        legs not normally load-bearing

    StandUp primitive:
        query body/contact map
        emit STAND intent
        create expected successor map

    new evidence:
        confirm upright support, revise, fail, or remain UNKNOWN

The lower controller performs the detailed motor skill. CCA8 does not symbolically control every hoof or joint.

## Example: SeekNipple / FollowMom

SeekNipple and FollowMom should query SELF, maternal identity/role, relative geometry, motion, contact, terrain, hazard, and uncertainty.
A compact `mom_distance=far` value can accelerate the query, but it should not replace the maternal and terrain maps.

## Selection and learning

Current selection uses drive deficit, non-drive priority, stable ordering, optional RL values, and bounded adviser support. Future map-native
selection may add map-match quality, transition reliability, expected information gain, transaction state, and structured surprise—but raw
residual magnitude must never directly choose a policy.

A primitive returns a status record and stamps provenance. Future transactions should explicitly connect accepted-before map, intent,
expected transformation, progress, observed outcome, accepted-after map, and learning eligibility.


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

- **Interactive:** use the *Planner strategy* menu toggle (BFS ↔ Dijkstra). *(Menu numbers may drift as the runner grows.)*

- **Environment variable:** set `CCA8_PLANNER=dijkstra` before launch to force Dijkstra by default:
  - Windows (cmd): `set CCA8_PLANNER=dijkstra`
  - Windows (PowerShell): `$env:CCA8_PLANNER="dijkstra"`
  - macOS/Linux (bash/zsh): `export CCA8_PLANNER=dijkstra`

  Then run the runner normally; planning calls will use Dijkstra (see **Runner, menus, and CLI** for launch examples).

- **In code**:

   python
  world.set_planner("dijkstra")    # or "bfs"
  current = world.get_planner()
   


# Persistence: Autosave/Load

- Snapshot file (JSON) includes:
  
   jsonc
  {"saved_at": "...", "world": {...}, "drives": {...}, "skills": {...}}
   

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

`cca8_run.py` is the interactive “world runner” for the CCA8 simulation. By default it:

1) prints a banner and some system info,  
2) prompts you to pick a developmental **profile** (goat/chimp/human/super),  
3) starts an interactive menu loop where you can inspect the **WorldGraph**, inject cues/predicates, run the **Action Center** (policies), and (optionally) step the **HybridEnvironment**.

---

## Quick start (interactive)

Most people should start here:

 bash
python cca8_run.py
 

See all supported command-line flags:

 bash
python cca8_run.py --help
 

Notes:
- On Windows, you may also be able to run `cca8_run.py` directly if `.py` is associated with Python.
- On macOS/Linux you can run `./cca8_run.py` if it’s marked executable, but `python cca8_run.py` is the most portable.

---

## Command-line flags (argparse)

These are the most useful flags while learning / debugging:

- `--about`  
  Prints the runner plus every component in the canonical registry, including each module version and source path. This is the preferred component report for bug reports and checkout verification.

- `--version`  
  Prints just the runner version.

- `--no-intro`  
  Skips the banner (useful for tight debug loops).

- `--profile {goat,chimp,human,super}`  
  Picks a profile without prompting.

- `--load <file>.json`  
  Loads a previously saved session snapshot (WorldGraph + drives + skill stats).

- `--autosave <file>.json`  
  Writes a snapshot **after each action** (great for “resume exactly here” workflows).

- `--save <file>.json`  
  Writes a snapshot **on clean exit** (useful when you don’t want frequent overwrites).

- `--plan <PRED>`  
  Runs a one-shot plan (NOW → goal predicate) and exits. Example:
   bash
  python cca8_run.py --load session.json --plan pred:posture:standing
   

- `--demo-world`  
  Starts with a small preloaded demo WorldGraph (great for menu testing and graph inspection).

- `--preflight`  
  Runs the full self-test suite and exits (see **Preflight (four-part self-test)** below).

- `--no-boot-prime`  
  Disables the default boot “prime” intent (e.g., the calf/goat stand intent).

- `--hal` and `--body <profile>`  
  Enables the HAL (embodiment) stub and selects a body profile (future-facing; may be partial).

---

## Session workflow: load / autosave / save

CCA8 uses **JSON snapshots** as the lowest-friction persistence format.

### Resume + keep autosaving (recommended during experiments)

 bash
python cca8_run.py --load session.json --autosave session.json
 

### Start fresh but keep an old snapshot (branch your run)

 bash
python cca8_run.py --load session.json --autosave session_NEXT.json
 

### Save only on exit (no autosave)

 bash
python cca8_run.py --load session.json --save session_end.json
 

Operational notes:
- Autosave uses **atomic replace** (write `*.tmp`, then rename) to reduce partial/corrupt snapshots.
- If you forget `--load`, CCA8 starts a fresh session; the first autosave will create the file.
- If you have autosave set, you can usually “reset” from the UI and keep a clean resume point
  (some menus also support an `R` shortcut).

---

## Menu highlights (recommended learning path)

Menu numbering may drift as new items are added; the **names** below are the stable guideposts.

Start with these:

* **Snapshot**  
  Prints bindings, edges, drives, CTX, TEMPORAL, and policy telemetry. Shows NOW/LATEST, event boundary (epoch), soft-clock cosine, and which policies are eligible at the current developmental stage. This is your “state of the world + controller” dashboard.

* **Drives & drive tags**  
  Shows numeric drives (`hunger`, `fatigue`, `warmth`) and the derived **drive flags** (`drive:*`) that policies use in `trigger()`. These flags are ephemeral and are not written into the graph unless you explicitly create `pred:drive:*` or `cue:drive:*` tags.

* **Input [sensory] cue**  
  Writes a `cue:<channel>:<token>` binding (for example `cue:vision:silhouette:mom`) and runs one controller step so you can see how policies respond to evidence. This is the most direct “Sense → Process → Act” entry point.

* **Instinct step (Action Center)**  
  Runs the policy runtime once, with explanatory pre/post text. If a policy fires, you’ll usually see a small chain of bindings/edges plus a compact status dict (`policy`, `status`, `reward`, `notes`).

Once you’re comfortable, these become very useful:

* **Run 1 Cognitive Cycle — verbose teaching mode**  
  Menu 35 runs one closed-loop cognitive cycle using the same engine as menu 37, but adds `[teach]` notes beside the live output.
  This is the best entry point when learning or debugging the cognitive-cycle sequence slowly.

* **Run n Cognitive Cycles — compact timeline**  
  Menu 37 runs multiple closed-loop cognitive cycles in compact form. It is useful for “does this stabilize?” tests and for
  generating `cycle_log.jsonl` traces.


* **Export and display interactive graph (Pyvis HTML)**  
  Generates a clickable HTML visualization. Use it when the Snapshot output becomes too dense.

* **Inspect binding details**  
  Given a binding id (or `ALL`), shows:
  - tags (`pred:*`, `cue:*`, `anchor:*`, etc.)
  - `meta` as JSON
  - a short **Provenance** summary (`meta.policy/created_by/boot/ticks/epoch`)
  - attached engrams (slot → id/summary)
  - incoming/outgoing edges and degrees

Planning and surgery tools (when you start editing graphs by hand):

* **LLM API setup + first demo (Menu 48)**  
  Configure the OpenAI API key and default model, run a live smoke test, inspect the outgoing CCA8 state-summary JSON, and experiment with a small set of request-level LLM knobs.


* **Plan to predicate**  
  Runs the planner from NOW to a target predicate and prints a readable path.

* **Connect bindings / Delete edge**  
  Lets you manually edit the graph (helpful for controlled experiments, but watch for duplicates).
  
* **Lines of Python code LOC by directory**  
  Menu 33 reports Python line counts by top-level directory. It prints:
  - `physical_LOC`: all lines in `.py` files, including comments, docstrings, menu text, teaching text, and blanks
  - `nonblank_LOC`: all nonblank lines
  - `code_like_LOC`: nonblank lines minus full-line comments, while still counting docstrings and multiline strings

  This is intended as a human-readable project-size report rather than formal SLOC.

---


# Menu 48: OpenAI / LLM setup, smoke test, state-summary demo, and advanced request knobs

Menu **48** is the current entry point for OpenAI / LLM work inside the runner.

It keeps the first bridge deliberately simple and readable:

- configure the API key,
- choose the default model,
- run a tiny live smoke test,
- run a first **CCA8 -> LLM** state-summary demo,
- and (optionally) adjust a small set of **advanced request knobs** that are useful for later experiments.

The current Menu 48 screen presents:

1. Configure / update `OPENAI_API_KEY`
2. Configure / update default OpenAI model
3. Run OpenAI SDK / API smoke test
4. Show install/help text
5. Run first CCA8 -> LLM state-summary demo
6. Advanced request settings
7. Run the evaluation harness (batch comparison + JSONL logging)

This keeps all of the current LLM-facing setup in one place rather than scattering it across multiple menus.



### Smoke test

The smoke test is the quickest way to verify that the LLM interface is wired correctly in the current Python environment.

It checks:

1. whether the `openai` Python package imports,
2. whether `OPENAI_API_KEY` is present,
3. which model CCA8 will use,
4. and whether a real API call succeeds.

If everything is configured correctly, CCA8 sends a tiny request and expects a tiny fixed reply. This is intentionally minimal: it is not a cognitive demo, only a “plumbing works” test.

### Optional integration and preflight policy

OpenAI access is not required to run the core CCA8 simulation, deterministic tests, WorkingMap pipeline, RCOS sandbox, or ordinary cognitive cycles. During full preflight, the live LLM smoke test is visible in Part 4:

- a successful configured call is reported as `PASS`;
- a missing SDK, missing key, rejected key, unavailable model, connection problem, or unexpected reply is reported as `WARN`;
- an OpenAI warning does not make the overall core preflight fail.

The low-level LLM probe still preserves precise `pass` / `skip` / `fail` diagnostics for focused tests and callers. The non-blocking policy applies only when the result is aggregated into the full CCA8 preflight.

### First CCA8 -> LLM state-summary demo

The first CCA8 -> LLM demo is intentionally **read-only**.

It does **not** write anything back into CCA8. Instead, it takes a very small runtime summary from the current CCA8 state, sends that summary to the model, and asks the model for a **structured interpretation** in a fixed JSON shape.

This keeps the first bridge:

- conservative,
- inspectable,
- easy to debug,
- and easy for a human reader to understand from terminal output.

At present, the demo asks the model to return exactly these conceptual fields:

- `scene_label`
- `current_task`
- `risk_flags`
- `advice`
- `confidence`

The terminal then prints the parsed result in a **human-friendly** display format rather than echoing raw JSON back to the user.



### Outgoing CCA8 state summary (what is sent to the model)

The current demo sends a compact JSON object whose purpose is to summarize the **current runtime state**, not to dump the entire architecture.

The outgoing state summary currently includes:

- `schema` — version tag for the outgoing summary format
- `profile` — current simulation profile (for example, Mountain Goat)
- `age_days`
- `controller_steps`
- `cog_cycles`
- `autonomic_ticks`
- `timekeeping` — one compact human-readable summary line
- `body` — small BodyMap-style readout such as posture, mother distance, nipple state, zone, and BodyMap staleness
- `drives` — numeric drives such as hunger, fatigue, and warmth
- `graph` — small WorldGraph summary such as NOW id, latest id, node count, and edge count
- `working_map` — a compact WorkingMap status summary
- `navsummary` — current nav-summary cache (if present)
- `recent_bindings` — a short tail of recent bindings and tags

This is intentionally a **small state packet** rather than a full memory export. The goal is to let the model interpret the current situation cheaply and transparently.



### How the model is instructed

The demo prompt tells the model that it is reading a **tiny CCA8 runtime snapshot** and that it must be conservative.

In particular, the current prompt tells the model to:

- use only the supplied JSON summary,
- avoid inventing hidden sensors, hidden goals, or hidden world state,
- and return only a JSON object matching the required schema.

This is important because the model is **not** directly connected to the live CCA8 internals. It only sees the prompt text plus the outgoing summary JSON. The LLM therefore behaves like an outside interpreter of a small state packet, not like a hidden controller with privileged access.



### Advanced request settings (future tuning knobs)

Menu 48 now also includes a small **advanced request settings** submenu.

These are **request-level** LLM knobs, not CCA8 architectural knobs. In other words, they tune how the OpenAI request is sent, but they do not change the underlying CCA8 memory structures, drives, policies, or map logic.

The current submenu supports:

1. **temperature**
2. **top_p**
3. **max_output_tokens**
4. **reasoning_effort**
5. **clear all advanced settings back to defaults**

These settings are intentionally limited to a small set that already maps cleanly onto the current request path used by both the smoke test and the CCA8 demo.

Current environment variable names used by Menu 48:

- `CCA8_OPENAI_TEMPERATURE`
- `CCA8_OPENAI_TOP_P`
- `CCA8_OPENAI_MAX_OUTPUT_TOKENS`
- `CCA8_OPENAI_REASONING_EFFORT`

On Windows, the menu loads these values into the **current process** and also saves them for future `cmd.exe` sessions, so experimental settings can persist without editing source code.



### Why these knobs were added

The first demo is already understandable without any extra tuning. However, future serious work on the **CCA8 <-> LLM** interface will likely need some request-level experimentation.

Examples:

- making output more stable vs. more variable,
- capping token usage,
- trying different reasoning-effort levels,
- or quickly testing how the same CCA8 state is interpreted under different request settings.

By putting these controls into Menu 48 now, later experiments can be run from the interface rather than by hand-editing Python code.



### What to expect when changing advanced settings

The advanced settings affect the **request**, not the underlying CCA8 state summary.

So if you keep the same CCA8 state but raise, for example, `temperature`, you should expect the **shape** of the reply to remain stable (same required fields), while the **wording, emphasis, and exact interpretation details** may vary.

This is useful for experimentation:

- low-variation settings are better when you want more repeatable interpretations,
- high-variation settings are useful when you want to stress-test the interface and see how robust the structured interpretation remains.

In practical testing, raising `temperature` and adjusting `top_p` made the CCA8 demo replies vary more while still remaining structurally valid and recognizable as interpretations of the same small state summary.



### Practical reading guide for Menu 48 terminal output

When reading the terminal output, it helps to separate four different things:

1. **Menu/UI text from CCA8**
   - e.g., the `Selection: OpenAI / LLM API setup...` blocks

2. **Smoke test narration**
   - friendly text explaining what is being checked

3. **Outgoing CCA8 summary**
   - the JSON state packet generated by CCA8 and sent to the model

4. **Structured LLM reply**
   - a parsed, human-friendly display of the model’s reply fields

This separation makes Menu 48 easier to debug:
first confirm the setup, then confirm the outgoing state summary, then inspect the model’s returned interpretation.



### Q&A

**Q: Does Menu 48 let the LLM control CCA8?**  
A: Not in the current demo. The first bridge is read-only and returns an interpretation only.

**Q: Is the model seeing all of CCA8?**  
A: No. It sees only the prompt plus the compact outgoing JSON summary.

**Q: Why not just print raw JSON from the reply?**  
A: The reply is parsed as JSON, but then displayed in a more human-friendly form because that is easier to read during interactive use.

**Q: Why keep the outgoing summary so small?**  
A: So the first bridge stays cheap, understandable, and easy to inspect. It is meant to demonstrate the interface cleanly before richer CCA8 <-> LLM coupling is attempted.

**Q: Why are the advanced settings in the menu already, if the demo itself is simple?**  
A: Because future work will likely need experimentation with request-level LLM behavior, and it is more convenient to expose a few useful knobs once than to repeatedly edit code during later experiments.





## Quick CLI + menu recipes

### One-shot planning (no menu)

 bash
python cca8_run.py --load session.json --plan pred:posture:standing
 

### Start with a preloaded demo world (for graph/menu testing)

 bash
python cca8_run.py --demo-world
 

### Add a sensory cue (interactive)

Use the menu entry that prompts for channel + cue token (it creates a `cue:*` tag, not a `pred:*` tag).

Tip: if you expected a *predicate* but created a *cue*, check the tag prefix in Snapshot (`cue:` vs `pred:`).

---

### Q&A to help you learn this section

Q: Can I skip the menu and just plan?  
A: Yes — use `--plan pred:<token>` for a one-shot plan and exit.

Q: I’m getting “No path found”. Where do I start?  
A: First confirm your goal token is exact (e.g., `pred:posture:standing`), then Snapshot the graph and verify there is a forward edge chain from NOW to a binding that contains that predicate.

Q: Is there a “known good” graph for debugging menus?  
A: Yes — `--demo-world` seeds a small deterministic graph that is also used by some unit tests, so interactive experiments and tests share the same baseline.




# Experiments



CCA8 contains a dedicated experiment harness for controlled benchmark runs. The purpose of this harness is not merely to “run the goat many times,” but to compare memory-governance and control conditions against frozen benchmark definitions using a stable action vocabulary, repeatable seeds, machine-readable JSONL records, and repeat-level statistics.

The experiment harness is intentionally additive. Ordinary interactive CCA8 simulation behavior is unchanged unless the experiment menu is explicitly used. Experiment episodes are executed in isolated sandbox runtimes so that benchmark execution does not mutate the user’s live interactive session.

The current experimental focus is **long-horizon state integrity**: whether the architecture can maintain the correct relationship among current evidence, prior memory, task stage, goals, and selected actions over an extended closed-loop trajectory.


## Experimental status of the NavMap paradigm

The current benchmark suite primarily tests **current-runtime memory governance, task continuity, retrieval behavior, and RCOS-shaped
long-horizon control**. It does not yet constitute a direct test of the full Map-Primacy architecture because the canonical root WNM is not
yet behaviorally authoritative.

After the WNM migration stabilizes, the experiment programme should compare:

| Experiment family | Main question |
|---|---|
| Map-first versus state-first control | Does WNM-centered policy access improve flexibility, transfer, partial-observability recovery, or interpretability? |
| Root-WNM authority ablation | What changes when MapSurface/BodyMap/WorldGraph continue to act independently instead of being derived or synchronized? |
| NavMap operator ablation | Which benefits depend on alignment, structured matching, linked submaps, structured residuals, or versioned revision? |
| Memory architecture | Do WorldGraph-indexed Column maps improve WNM construction compared with direct state retrieval or no retrieval? |
| Temporal binding | Does binding motion/rate onto maps improve prediction and action over snapshot-only representation? |
| Surprise processing | Does bounded focus/resampling/Probe improve safety and uncertainty resolution without importing human recursion? |
| Primitive representation | Do map-native trigger/transform contracts outperform or clarify condition forests over compact states? |
| LLM synergy | Does an LLM plus NavMap authority/provenance outperform an LLM wrapper or CCA8 alone? |
| Neuroscience hypothesis | Which observed successes and failures support, refine, or weaken the proposed evolutionary map architecture? |

Negative or null results are informative. The project should not redefine success after the fact or protect NavMap primacy from comparison.
Current metric names such as `state_integrity_score` remain compatibility/research terms; they do not imply that the target cognitive
architecture is a state-vector system.


## Menu 49: Experiments / Benchmarks

Menu 49 is the entry point for experiment work.

It currently supports:

* protocol inspection and reset,
* benchmark and condition selection,
* seed-list and run-budget configuration,
* observation-mask probability,
* newborn stress-profile configuration,
* JSONL output-path preparation,
* example cycle and episode records,
* isolated single-episode benchmark runs,
* A/B/C condition batches,
* repeated A/B/C random-seed runs with repeat-level statistics,
* optional A/E hybrid-adviser runs,
* and preliminary RCOS robotic long-horizon experiments.

Useful submenu entries include:

* **17** — run one prepared experiment episode in an isolated sandbox
* **18** — run an A/B/C batch over the current seed list
* **19** — run 20 random-seed A/B/C repeat blocks and print repeat-level statistics
* **20** — run an A/E batch over the current seed list
* **21** — run 20 random-seed A/E repeat blocks
* **30** — set the newborn stress profile
* **31** — set the newborn blackout length

The RCOS robotic entries in Menu 49 are preliminary simulation benchmarks for later robotics work. They are useful for testing RCOS/HAL task sequencing, perturbations, and ablations, but they are separate from the native newborn A/B/C memory-governance benchmark.


## Experiment protocol: conditions A–E

The experiment protocol defines five comparison conditions.

### A) Full CCA8 with guarded merge retrieval

Reference condition. Stored prior state may be retrieved and conservatively merged into the current WorkingMap / MapSurface. Retrieved memory can fill missing information or provide a prior, but it should not overwrite fresh current evidence or active safety/task constraints.

### B) CCA8 without episodic readback

Storage remains available, but automatic episodic readback is disabled. This condition tests whether storing prior state is sufficient when stored state is not functionally reintroduced into ongoing control.

### C) CCA8 with replace-mode prior injection

Episodic retrieval is enabled, but retrieved MapSurface priors are applied in replace mode rather than conservative merge mode. This condition tests the risk of giving prior memory too much authority over current state.

### D) LLM-only controller baseline

Reserved future condition. The intended baseline is an LLM controller choosing from the same bounded action vocabulary using only agent-visible state summaries. This condition is not part of the reported CCA8 native A/B/C benchmark runs.

### E) Hybrid CCA8 + LLM adviser

Optional experimental condition. CCA8 remains the authoritative controller, while an LLM adviser may rank or recommend among bounded candidate policies when the candidate set is ambiguous. The adviser is subordinate to CCA8 and is not used as an unconstrained controller.

The native CCA8 A/B/C benchmark runs do not use external LLM processing, API calls, or a language-model controller. Conditions D and E are reserved or optional LLM-related comparison conditions.

## Current benchmark suite

The harness currently defines two main CCA8 benchmarks.

### 1) `goat04_context`

This is the contextual map-switch benchmark built around the `goat_foraging_04` evaluation world.

Its purpose is mechanistic:

* partial observability,
* sparse fox / hawk contextual switching,
* retrieval of the appropriate prior map,
* contamination control,
* and stabilization after a context switch.

Representative metrics include:

* `context_switch_accuracy`
* `false_retrieval_count`
* `cue_leakage_violations`
* `oracle_action_accuracy`
* `oracle_retrieval_precision`
* `internal_retrieval_event_ratio`
* `stabilization_latency`
* `cumulative_prediction_error`

This benchmark is useful for testing whether retrieved context changes downstream control.

### 2) `newborn_long_horizon`

This is the Long-Horizon State-Integrity Benchmark.

Its purpose is behavioral and state-governance oriented: can the system preserve coherent state while progressing through an ordered newborn survival sequence under partial observability and structured stress?

The milestone ladder is:

1. `stood_up`
2. `reached_mom`
3. `found_nipple`
4. `latched_nipple`
5. `milk_drinking`
6. `rested`

Representative task-completion metrics include:

* `success`
* `milestone_vector`
* `milestone_steps`
* `milestone_score`
* `time_to_rested`
* `time_to_rested_or_max_cycles`
* `recovery_latency`
* `cycles_to_end`
* `cumulative_prediction_error`

The newborn benchmark also records long-horizon state-integrity metrics through `cca8_state_integrity.py`.

## Newborn stress profiles

The newborn benchmark supports the following stress profiles:

### `baseline`

Ordinary partial observability only. The observation-mask probability still applies, so this is not a fully observable control. It is the partially observable baseline without structured route-loss perturbation.

### `blackout_short`

A short structured blackout after selected milestone events. It removes selected local relation and feeding-state tokens for a small number of cycles.

### `blackout_long`

A longer version of the structured blackout stressor.

### `route_loss`

The main memory-critical stress profile for the `newborn_long_horizon` benchmark. During route-loss periods, the agent retains body/proprioceptive information, but external route and task-continuity evidence is removed from the visible observation packet. This includes mother/nipple/shelter/hazard relation fields, route/navigation cues, selected raw-sensor fields, and local navigation surfaces.

Route loss is designed to make memory useful but potentially dangerous. A no-readback agent may fail because it cannot recover route/task continuity. A replace-mode agent may preserve outward progress while allowing old state to overwrite current state. A guarded-merge agent should use prior state as support while preserving current-state authority.

## State-integrity metrics

The module `cca8_state_integrity.py` provides read-only post-processing for newborn long-horizon cycle records. It does not change the controller, environment, memory system, or action-selection behavior.

The state-integrity summary includes:

* `state_integrity_score`
* `wrong_stage_action_count`
* `repeated_action_loop_count_lhsi`
* `cumulative_prediction_error_lhsi`
* `retrieval_event_count`
* `retrieval_ok_count`
* `retrieval_non_noop_count`
* `retrieval_merge_noop_count`
* `retrieval_replace_count`
* `current_state_overwrite_proxy_count`
* `stale_memory_intrusion_proxy_count`
* `retrieval_action_dissociation_proxy_count`
* `retrieval_followup_basis_count`
* `provenance_complete_cycle_rate`

Important interpretation note: metrics with `_proxy` in the name are conservative proxy measures derived from available cycle records. They are not yet full slot-level pre/post audits. Component metrics should be inspected alongside the composite `state_integrity_score`.

## Experiment outputs and provenance files

The experiment harness can write machine-readable artifacts to a configurable output directory, usually `testvalues`.

Common per-run artifacts include:

* `<run_id>__cycle.jsonl`
* `<run_id>__episode.jsonl`

Repeated-run analysis can also write:

* `<run_id>__episode_rows.jsonl`
* `<run_id>__repeat_rows.jsonl`
* `<run_id>__stats.json`

The repeated-run bundle is the preferred provenance artifact for analysis tables, regression checks, and release notes because it preserves:

* episode-level rows,
* repeat-level condition summaries,
* repeat metric rows,
* descriptive statistics,
* and paired comparisons against Condition A.

## Example repeated-run protocol

The following configuration is a useful reproducible stress-test configuration for the `newborn_long_horizon` benchmark:

* benchmark: `newborn_long_horizon`
* conditions: `A`, `B`, `C`
* stress profiles: `baseline` and `route_loss`
* observation-mask probability: `0.50`
* maximum cycles: `60`
* repeat blocks: `20`
* seeds per repeat: `5`
* episodes per seed: `1`
* episodes per condition per stress profile: `100`
* total episodes across baseline and route-loss profiles: `600`
* external LLM calls for native A/B/C runs: `0`

A practical way to run this workflow from Menu 49 is:

1. Set benchmark id to `newborn_long_horizon`.
2. Set condition ids to `A B C`.
3. Set observation-mask probability to `0.50`.
4. Set max cycles to `60`.
5. Set episodes per seed to `1`.
6. Set stress profile to `baseline`.
7. Run submenu 19 and save the repeated analysis bundle.
8. Set stress profile to `route_loss`.
9. Run submenu 19 again and save the repeated analysis bundle.

This protocol can be used to compare ordinary partial observability against structured route-loss stress. The route-loss profile is expected to be more memory-critical than the baseline profile, but numerical results should always be regenerated from saved JSONL/statistics artifacts rather than treated as hard-coded behavior.


## Source-file map for the experiment subsystem

### `cca8_experiments.py`

This module owns the complete experiment subsystem: frozen condition and benchmark definitions, newborn observation stressors, protocol normalization, JSON/JSONL preparation, isolated sandbox execution, optional LLM-adviser support, benchmark scoring, repeated-run statistics, result rendering, and the interactive Menu 49 flow.

Important concepts include:

* `ExperimentConditionDef`
* `ExperimentBenchmarkDef`
* `ExperimentRuntime`
* `ExperimentMenuOperations`
* `experiment_condition_catalog_v1`
* `experiment_benchmark_catalog_v1`
* `NEWBORN_STRESS_PROFILES_V1`
* `apply_newborn_experiment_stress_v1`
* `experiment_run_one_episode_v1`
* `experiment_run_condition_batch_v1`
* `experiment_run_repeated_random_abc_v1`
* `_experiment_write_repeated_result_bundle_v1`

### `cca8_context.py`

Owns `ExperimentProtocolConfig` and the runtime fields used to carry protocol choices, logging state, experiment labels, and cross-cycle configuration.

### `cca8_run.py`

The runner no longer owns experiment algorithms. It preserves historical experiment names through aliases and narrow wrappers, constructs the current `ExperimentRuntime` / `ExperimentMenuOperations` callback bridges, and connects Menu 49 to the live runner environment.

### `cca8_openai.py`

Owns the optional OpenAI request, response, state-summary, error-normalization, and usage helpers supplied to the experiment runtime for bounded adviser conditions. Native A/B/C benchmark runs do not require OpenAI.

### `cca8_working_memory.py`

Owns the MapSurface storage/retrieval, contextual switching, and retrieved-state hint operations exercised by memory-governance experiment conditions.

### `cca8_state_integrity.py`

Read-only post-processing for newborn long-horizon state-integrity metrics. This module analyzes saved cycle records and returns JSON-safe summaries without altering runtime behavior.

### `cca8_rcos_experiments.py`

Preliminary RCOS robotic long-horizon experiment helpers. These use the SimRobotGoat HAL seam and bounded command vocabulary to test robot-shaped task sequencing, perturbations, repeats, and RCOS/no-RCOS ablations in simulation.

### `cca8_teaching.py`

Teaching text helpers used by the verbose Menu 35 cognitive-cycle mode. They are separate from experiment execution but help explain the same closed-loop runtime.

### `cca8_world_graph.py` and `cca8_column.py`

WorldGraph remains the thin symbolic episode index and pointer scaffold. Column memory remains the heavy immutable payload store used by MapSurface snapshot/retrieval and other engram-backed experiment paths.

## Current limitations

The experiment harness is a research tool, not a finished general benchmark suite.

Current limitations include:

1. The newborn benchmark is intentionally small and controlled. It tests one proposed prerequisite for long-horizon agency, not general intelligence or real-world autonomy by itself.
2. The route-loss stressor is artificial and designed to isolate memory-governance behavior.
3. Proxy metrics are conservative and depend on available cycle records.
4. The LLM-only Condition D is reserved for future work.
5. The optional hybrid LLM adviser Condition E is not part of the native CCA8 A/B/C benchmark configuration.
6. The RCOS robotic experiment helpers are preliminary software benchmarks and do not yet demonstrate full CCA8 Action Center control of physical hardware.

These limitations are useful boundaries. They keep the README honest and prevent readers from overinterpreting the experimental code.






# WorkingMap Layer Contracts

WorkingMap is the active **workspace/container**. It is not itself the WNM and should not be described as one undifferentiated memory
store.

## Target ownership structure

WorkingMap should own or explicitly reference:

- one accepted root WNM and its bounded revision history;
- linked body, terrain, maternal, nipple, hazard, object, route, and close-up submaps;
- modality evidence maps and scene candidates;
- protected EXPECTED and RETRIEVED maps;
- Scratch comparisons, primitive transactions, residuals, and bounded surprise episodes;
- Creative imagined/counterfactual candidates;
- derived MapSurface, SurfaceGrid, NavSummary, predicates, and BodyMap-facing readouts;
- projection caches tied to source WNM revision and configuration.

Only one root map has accepted-current authority. A linked submap may be active in focus without becoming a second reality.

## Current implementation checkpoint

`cca8_working_memory.py` currently owns WorkingMap construction, MapSurface entities/relations, NavPatch storage/matching/ambiguity,
SurfaceGrid composition, NavSummary, salience, Scratch, Creative, zoom, Probe, retrieval, contextual switching, and live observation
projection.

At commit `71ab4dc`, MapSurface and SurfaceGrid are still built primarily from interpreted observation before the accepted-current NavMap
shadow is computed. Some WorkingMap and NavSummary content affects policy. The canonical root WNM has not yet been promoted.

## Layer contracts

### Accepted root WNM — target canonical current map

**Purpose:** one authorized map of the present embodied situation.

**Contains or links:** SELF, attended entities, body/world relations, geometry/topology, motion, uncertainty, evidence provenance,
expected/transaction links, active focus, unresolved ambiguity, and linked submaps.

**Lifecycle:** versioned revisions; at most one accepted root; UNKNOWN allowed; arbitrary mutation prohibited.

**Authority:** representational authority first in shadow/compare, then controlled behavioral authority after projection and safety parity.

### Evidence and candidate layers

**Purpose:** retain current modality evidence and competing scene interpretations without prematurely choosing one.

**Invariant:** ranking is not acceptance. Best-poor candidates may be rejected. Frame and scale alignment must be explicit.

### MapSurface — current active scaffold, target WNM projection

**Current purpose:** compact entity/slot semantic scene updated from observation and retrieval.

**Target purpose:** deterministic sparse entity/relation projection of a named accepted WNM revision.

**Allowed content:** stable handles, selected attributes, relations, source revision, freshness, unresolved status, thin links.

**Not allowed:** unbounded topology, long reasoning chains, or imagined futures.

### SurfaceGrid — target topological projection

**Purpose:** one local action-facing topology view for traversability, occupancy, hazards, goals, corridors, SELF position, and UNKNOWN.

**Target source:** accepted WNM and active linked terrain/hazard submaps.

**Conflict rules:** hazard does not disappear because a goal overlaps it; UNKNOWN remains conservative; source revision is recorded.

**Lifecycle:** recompute or cache by accepted revision/configuration; stale grids must not be labelled current.

### NavSummary and predicates — compact derived readouts

**Purpose:** efficient gates, compatibility, indexing, logging, and displays.

**Requirement:** behaviorally authoritative values identify source WNM revision, derivation, freshness, and uncertainty where relevant.

### Scratch — protected transient map workspace

**Purpose:** comparisons, structured residuals, primitive transactions, expected transformations, ambiguity, local map operations, Probe
records, and bounded surprise episodes.

**Lifecycle:** explicitly owned, bounded, and pruned. Nothing becomes long-term or accepted without an authority operation.

### Creative — protected imagined candidates

**Purpose:** bounded counterfactual or candidate maps for later architectures and selected CCA8 lookahead hooks.

**Invariant:** Creative cannot write OBSERVED evidence, accepted WNM, long-term memory, or actuators directly.

CCA8 should use Creative sparingly. Large multibranch counterfactual planning is outside the goat boundary.

### Retrieved layer

**Purpose:** hold Column/WorldGraph maps activated for comparison and guidance.

**Invariant:** RETRIEVED remains RETRIEVED even if accepted content later incorporates part of it; source and derivation remain
recoverable.

### BodyMap seam

BodyMap is not a WorkingMap layer, but WorkingMap/WNM must expose its relationship to body and near-space safety. Fast body feedback
may update BodyMap sooner than the cognitive scene cycle. Disagreement between BodyMap and WNM-derived body readouts is exposed
and resolved conservatively.

## Derived-view discipline

The target direction is:

    accepted WNM revision
        -> MapSurface
        -> SurfaceGrid
        -> NavSummary / predicates / BodyMap-facing proposals
        -> policy accessors

During migration:

    legacy projection + WNM-derived projection
        -> differential record
        -> categorize each difference
        -> preserve legacy authority until understood

## Minimal candidate/outcome record

A bounded candidate may carry:

- seed WNM revision;
- active submap/focus;
- proposed primitive or operator sequence;
- expected successor map or compact outcome sketch;
- risk, progress, uncertainty, and reversibility;
- score with declared semantics;
- provenance, version, parameters, and random seed.

A candidate score never confers belief or action authority by itself.

## WorkingMap invariant

> Rich moment-to-moment cognition belongs in map structures and protected layers inside WorkingMap. WorldGraph remains sparse;
> Columns remain rich and durable; compact state variables remain controls or projections rather than an accidental second cognition.


# Design principle: multi-scale navigation is first-class

CCA8 treats scale, viewpoint, focus, and map switching as explicit operations rather than accidental side effects of one monolithic
representation.

## Root WNM plus linked submaps

The accepted root WNM maintains the coherent whole-scene context. It can link to:

- body/posture and near-space maps;
- maternal-body and nipple/mouth close-ups;
- terrain, ledge, foothold, cliff, and hazard maps;
- object and landmark maps;
- broader route or episode-context maps.

A linked submap has its own frame, origin, orientation, scale, extent, quality, and parent/overlap links. Activating it changes attention, not
reality count.

## Zooming

Zooming is a deliberate operator that:

1. selects a focus region, entity, or relation;
2. follows or creates a linked submap at a more useful scale;
3. records the parent/child transform and overlap;
4. protects the root scene/context;
5. performs bounded processing;
6. projects any stable result back to the appropriate parent revision.

Zoom down when local control, uncertainty, contact, hazard, or mismatch requires detail. Zoom up when the local ambiguity is resolved and
scene-level action can resume.

## Map switching

Map switching activates a different stored map hypothesis, prototype, or episode context for comparison. It is more than recall but less
than acceptance.

    current evidence and WNM context
        -> WorldGraph retrieval neighborhood
        -> bounded Column maps
        -> align and compare
        -> activate candidate in RETRIEVED layer
        -> recompose candidate scene
        -> accept, reject, preserve ambiguity, or create a new map

A retrieved map never becomes present truth solely because it reduced a scalar error. Reliable current evidence and provenance remain
protected.

## Current implementation

Current NavPatch prototypes, instances, patch matching, SurfaceGrid composition, zoom/Probe bookkeeping, MapSurface snapshots, and
contextual retrieval are practical scaffolds for this direction. They currently operate before a canonical accepted root WNM is
behaviorally authoritative.

## Traceability

Each zoom or switch should eventually record:

- source/root WNM revision;
- active submap and frame/scale transform;
- candidate maps and retrieval provenance;
- matching correspondences, scores, margins, and structured residuals;
- accepted/rejected/UNKNOWN decision;
- projection changes;
- policy or safety effect;
- cost and processing budget consumed.


# Tutorial on Timekeeping


## Timekeeping in CCA8 (five measures)

CCA8 uses five orthogonal time measures. They serve different purposes and are intentionally decoupled.


**1) Controller steps** — one Action Center decision/execution loop (aka “instinct step”).  
*Purpose:* cognition/behavior pacing (not wall-clock).  
*Source:* a loop in the runner that evaluates policies once and may write to the WorldGraph. When that write occurs, we mark a **temporal boundary (epoch++)**. :contentReference[oaicite:0]{index=0}

With regards to its effects on timekeeping, **when a Controller Step occurs**:
i) **controller_steps**: ++ every Action Center evaluation
ii) **temporal drift**: ++ (one soft-clock drift) per controller step  
iii) **autonomic ticks**: no change  
iv) **developmental age**: no change  
v) **cognitive cycles**: no direct change (they are incremented only on closed-loop env↔controller iterations; see item 5 below)
                            
                             
With regards to terminology and operations that affect controller steps:
**“Action Center”** = the engine (`PolicyRuntime`).
**“Controller step”** = one invocation of that engine
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


**5) Cognitive cycles** — a derived counter for “meaningful sense→decide→act” iterations

In CCA8, the most canonical “cognitive cycle” is the **closed-loop env↔controller iteration** used by menu 37:
EnvObservation → internal update (BodyMap/WorkingMap/WorldGraph as configured) → policy select/execute → action feedback to env.:contentReference[oaicite:8]{index=8}

*Source variable:* `ctx.cog_cycles` (int).

*Where incremented today (current runner behavior):*
- **Env-loop (menu 37; menu 35 alias)**: increments once per closed-loop iteration (ordinary or keyframe).
- **Controller-only “Instinct step” path:** currently increments **only when the controller wrote new bindings** (i.e., a real state/action update occurred).  
  (This is a temporary “meaningful write = cycle” definition while we continue to harden the explicit sense→process→act loop.)

*Contrast with controller steps:* `controller_steps` counts every Action Center invocation; in menu 37 runs they typically advance together (1 controller step per closed-loop cycle). Outside the env-loop, `controller_steps` may advance without `cog_cycles` (e.g., no-op decisions), and `cog_cycles` may increment only on a successful write.

*Recommended invariant:* `cog_cycles ≤ controller_steps`.


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

Q: When do we increment ticks (autonomic ticks) versus controller_steps?
A: ticks increment only in the Autonomic Tick path (heartbeat: physiology, drive updates, time-based age). controller_steps increment whenever a controller step runs (Instinct step, Autonomic tick, simulate fall, env-loop, etc.). They are orthogonal measures.

Q: What is the semantic difference between age_days and ticks?
A: age_days is a coarse developmental clock (used to set lexicon stage and developmental gates), while ticks is a fine-grained physiological heartbeat counter. Typically age_days advances in proportion to ticks but on a much slower scale.

Q: What does a “temporal boundary” (epoch++) represent?
A: A boundary is taken when a controller step writes new facts (or when a thresholded τ-cut triggers). It’s a way of saying “a new episode chapter started here” in the soft-clock vector space. We then jump the temporal vector, increment boundary_no (epoch), and reset cos_to_last_boundary to ~1.0.

Q: Why do we maintain both wall-clock created_at timestamps and a soft temporal vector?
A: Wall-clock is great for logs and cross-run inspection, but awkward for unitless similarity and segmentation. The soft temporal vector gives a cheap, unitless notion of “near in time” (via cosine) and supports operations like “time-aware similarity” and “episode segmentation” without relying on wall-clock units.

---








# Tutorial on Cognitive Cycles

> **Architecture status:** the detailed sequence below describes the current executable cycle. The target map-first cycle inserts Local
> NavMap matching, bounded Column/WorldGraph retrieval, candidate-scene composition, root-WNM acceptance, and WNM-derived
> projections before map-native primitive selection.




## A. Dataflow chart: where information goes each step

This tutorial focuses on **timing**: what must happen before what in a closed-loop run.

For the canonical “what lives where / what runs when” memory-pipeline description (Phase VII + Phase X), see:
- **Tutorial on WorkingMap → Phase VII → “Memory pipeline (plain-English): how CCA8 remembers”**
- **Tutorial on WorkingMap → Phase X → “where SurfaceGrid + NavPatches fit into the loop”**

A minimal orientation sketch:

 
EnvState (hidden truth)
  → EnvObservation
  → BodyMap update
  → SeqErr update (temporal deltas + prediction error stub; diagnostic only)
  → WorkingMap.MapSurface update
  → (keyframes only) store / retrieve / apply priors (wm<->col)   # may modify MapSurface
  → (Phase X) compose WorkingMap.SurfaceGrid (derived)
  → Action selection + policy execution
  → env.step(action)
  → next EnvObservation
 

---

### The CCA8 cognitive cycle (closed-loop env↔controller iteration)

In the CCA8, a cognitive cycle is one iteration of the closed-loop interaction between:
(1) the environment producing an observation, and
(2) the agent updating its internal maps, selecting a policy, and executing that policy,
followed by feeding the selected action back to the environment.

Terminology note:
- cognitive_cycle is the agent’s “sense → decide → act” iteration (often printed as 1/5, 2/5, … in menu 37).
- env_step (or step_index) is the environment’s internal 0-indexed counter since the last reset.

**Cognitive cycle** = every closed-loop iteration:
EnvObservation → update internal maps (BodyMap + WorkingMap.MapSurface, then (Phase X) compose SurfaceGrid) → select policy → execute policy (Scratch S–A–S chain) → act

**Keyframe cycle** = a cognitive cycle where the “keyframe flag” is true, meaning we additionally run the WM ⇄ Column engram pipeline at the boundary:
(keyframe) store snapshot → (keyframe) optional retrieve + apply priors
inserted between MapSurface update and policy selection (and before any derived SurfaceGrid composition used by policies).

Note: 
Each cognitive cycle ends by selecting/executing an action that changes the env, then the system immediately starts the next cognitive cycle when the env produces the next EnvObservation.

Whether the next cycle is a keyframe is decided fresh each cycle based on the keyframe triggers (stage/zone boundary, forced snapshot, periodic keyframe, etc.)

Note:
Predictions/hypotheses exist, are compared to the next observation, and produce a mismatch signal (v0 “prediction error vector” plan is already aligned with this).

An optional internal reprocessing loop exists as a reserved capability, where intermediate results can be fed back into the next cycle’s “input stream” (or internal buffer) instead of (or in addition to) relying purely on fresh external observation. This is the CCA8 analog to the “feed WNM back to association modules” idea in the published work on the CCA.

In reprocessing mode, the architecture may temporarily down-weight or ignore fresh external observation (attention diverted) and instead iterate on an internal buffer; when external observation is present, EnvObservation remains the authority for ‘truth-now’.

Note: The controller_steps counts every invocation of the Action Center (each time we ask “what should I do?”).
cog_cycles counts closed-loop env↔controller iterations (EnvObservation → update → select/execute → action feedback).
In menu 37 runs (and menu 35, which is now an alias that runs one closed-loop step), controller_steps and cog_cycles advance together.
Outside the env-loop, controller_steps may advance without cog_cycles (e.g., Instinct Step, Autonomic Tick).



**At a high level, each cognitive cycle proceeds as follows:**
(Keyframe-only steps are explicitly marked.)

0) Prior cycle ends; this cycle begins
   - The previous cycle selected/executed an action (or no-op), which the environment applied.
   - The environment now produces the next EnvObservation, beginning the next cognitive cycle.
   - Whether this cycle is a keyframe is decided fresh each cycle (env_reset, stage/zone transitions, forced keyframes, etc.).

1) Environment produces an observation (EnvObservation)
   - HybridEnvironment generates an EnvObservation (predicates/cues + info) based on the current storyboard/world state.
   - If actual robotic embodiment (i.e., non-simulation) then this will be actual, albeit pre-processed, sensory input values.
   - This observation is the only authoritative source for “what is true now” in the agent’s belief state.

2) BodyMap update (fast gating cache)
   - BodyMap mirrors action-critical scalar/slot values (e.g., posture, mom_distance, nipple_state, derived safety zone, staleness).
   - Gates consult BodyMap for fast O(1) checks (e.g., unsafe_cliff_near) without graph traversal.

3) WorkingMap update: MapSurface (current belief state table)
   - EnvObservation facts are written into WorkingMap.MapSurface using semantic addressing:
     (entity_id, slot-family) → current value
   - MapSurface overwrites within a slot-family (one current value per channel); it is optimized for “what do I believe right now?”

4) WorldGraph observation logging (optional; per configuration)
   - The long-term WorldGraph may receive an observation commit (append-style), subject to long-term injection settings:
     snapshot vs changes, ctx.longterm_obs_reassert_steps, and related verbosity knobs.
   - This is distinct from the WM⇄Column keyframe pipeline: WorldGraph logging can occur on ordinary cycles as well.

5) (KEYFRAME) WM ⇄ Column boundary pipeline (conditional; ordering invariant)
   - If this cycle is a keyframe, run the boundary pipeline BETWEEN MapSurface update and SurfaceGrid composition / policy selection:

   5a) Store (consolidation): MapSurface → Column engram
       - Store a MapSurface snapshot as an engram in Column memory.
       - Write/refresh a lightweight pointer/index node in WorldGraph for later retrieval.

   5b) Optional guarded auto-retrieve + apply (priors): Column → WorkingMap
       - Optionally retrieve prior MapSurface snapshot(s) and apply them to WorkingMap:
         - replace mode: rebuild MapSurface from the snapshot
         - seed/merge mode: seed predicate priors only; do NOT inject cue:* tags into live belief (no cue leakage)
       - Exclude the engram just stored on this same keyframe (no trivial self-retrieval).

   5c) Temporal boundary bookkeeping (if enabled)
       - TemporalContext is stepped each cycle and may take a boundary jump at keyframes.

5d) (Phase X) SurfaceGrid composition (derived; policy-facing topology)
   - If Phase X is enabled, compose **WorkingMap.SurfaceGrid** from the currently active NavPatch *instances* (and the prototype payloads they reference).
   - Do this **after** any retrieve+apply step that may have modified MapSurface, so policies see a grid consistent with current belief.

6) Policy selection (the decision step)
   - The Action Center evaluates candidate policies:
     - trigger conditions (is it relevant now?)
     - gate conditions (is it allowed now?)
   - Policies are scored (deficit scores, non-drive scores, and optional RL tie-breaks).
   - The best policy is chosen for this cognitive cycle.

7) Policy execution (procedural trace + predicted postcondition)
   - The chosen policy is executed on the designated execution map (often WorkingMap).
   - Execution writes a Scratch chain representing a State–Action–State (S–A–S) trace:
       action:* → action:* → … → pred:* (postcondition/outcome hypothesis)
   - The final pred:* node in Scratch represents the expected post-state (a hypothesis), not the confirmed world state.
   - Confirmation/refutation occurs on the next cognitive cycle when the next EnvObservation arrives.

8) (FUTURE, KEYFRAME OPTIONAL) Consolidation/reconsolidation write-back slot (copy-on-write)
   - After policy selection + execution, a keyframe may optionally run a write-back hook that:
     - writes new engrams (copy-on-write) and/or patch records (schema/world-model learning), and
     - updates WorldGraph pointer bindings for future retrieval,
     WITHOUT changing the belief state that was already used for action selection in this same cycle.
   - This slot is reserved for future learning/consolidation work (reconsolidation) and is intentionally not required for v0.

9) Action feedback to the environment (completes this cycle)
   - The chosen policy name/action token is passed to HybridEnvironment.step(action=...),
     which advances the storyboard and produces the next observation (beginning the next cognitive cycle).
     
10) REPEAT -- START A NEW CYCLE
   - The next cycle may be an ordinary cognitive cycle or a keyframe cycle, depending on whether the keyframe trigger fires.


Reading the logs:
- env_* fields reflect the environment/storyboard truth for that cycle.
- bm_* fields reflect the agent’s current belief cache after observation injection.
- expected_* fields reflect policy postconditions written into Scratch (hypotheses) and are intended for prediction-error computation on subsequent cycles.



### WM ⇄ Column engram pipeline (store / retrieve / apply priors)

The WM ⇄ Column (“wm<->col”) pipeline is the **keyframe-only** consolidation + priors mechanism:
it stores boundary snapshots into long-term memory and can auto-retrieve priors to seed/merge belief.

The **canonical** description lives in **Tutorial on WorkingMap (Phase VII + Phase X)**, especially:

- **Keyframes and “boundaries”: when we store a MapSurface snapshot**
- **WorkingMap <-> Column (wm<->col): what is stored and what “merge” reconstitutes**

High-level steps at a boundary:

1) **Store**: MapSurface snapshot → Column engram, plus a thin pointer/index binding in WorldGraph  
2) **(Optional) Retrieve**: select candidate prior snapshots (and later: patch prototypes)  
3) **Apply**: seed/merge priors into WorkingMap without overwriting currently observed slot-families  

Ordering invariant for a keyframe cycle:

> observe → update BodyMap/MapSurface → (store/retrieve/apply priors) → policy selection + execution

# Tutorial on NavPatch: MapSurface patches and matching

> **Architecture status:** NavPatch is an active and important scaffold. Current patches are often already interpreted and are composed
> before a canonical accepted root WNM exists. The target architecture links patch prototypes and instances to evidence maps, candidate
> scenes, explicit frames/scales, and the accepted WNM revision.

NavPatch is the Phase X layer that treats parts of perception as matchable, reusable “patch prototypes”.

Design goals:
- improve generalization across local geometric motifs (terrain/hazards/affordances),
- keep WorldGraph thin (symbols + pointers) while Columns hold heavier patch payloads,
- keep decisions traceable (top-K matches, priors applied, error/uncertainty, margins).


---



## 1) What problem NavPatch solves

MapSurface is a compact “what is here now” sketch. It is excellent for action selection and gating,
but it needs a mechanism to:
- recognize recurring local motifs (e.g., “cliff edge”, “shelter alcove”, “mom silhouette”),
- decide when a motif is ambiguous vs confident,
- and record why a match was chosen (for debugging and later learning).

NavPatch supplies that recognition loop and makes it visible in logs.

---

## 2) Relationship to WorkingMap.MapSurface

MapSurface holds a small, inspectable “scene sketch” of entities and slot-families.

NavPatch is the optional patch layer that:
- extracts local “patch” observations each tick (EnvObservation.nav_patches),
- matches them to stored prototypes (Column navpatch_v1 engrams),
- and attaches patch_refs back onto MapSurface entities (keeping MapSurface light).

(See “WorkingMap Layer Contracts” for the MapSurface/Scratch/Creative split and invariants.)


### 2.1 Tutorial: how NavPatch becomes a rendered SurfaceGrid

This subsection answers a practical question:

**How do we get from patch matching to the actual body-centered grid that the policy can read?**

A useful way to think about it is:

- **NavPatch matching** answers:  
  *“What stored local terrain/map prototypes best explain the evidence I have right now?”*

- **SurfaceGrid rendering/composition** answers:  
  *“Given the currently active patch instances, what local topology should the agent treat as present right now?”*

They are closely related, but they are not the same thing.

---

#### Abstract pipeline

At a high level, one cognitive cycle does the following:

1. **Observe the local scene**
   - The agent receives an `EnvObservation`.
   - Some of that observation can be interpreted as **patch evidence**:
     local terrain fragments, hazard structure, traversability hints, partial geometric motifs, etc.

2. **Match observed evidence against stored NavPatch prototypes**
   - Each observed patch is compared against stored **NavPatch prototypes** in Columns.
   - The result is a **ranked top-K list** plus a decision:
     - `commit`
     - `ambiguous`
     - `unknown`

3. **Create/update NavPatch instances in working memory**
   - A **prototype** is the long-term reusable template.
   - An **instance** is that prototype bound to the current situation:
     “this patch, here-and-now, in this pose/role/context.”
   - These instances are working-memory objects, not long-term records.

4. **Compose one SurfaceGrid for the current cycle**
   - The currently active patch instances are overlaid/stiched into a single body-centered grid.
   - Conflict resolution is deterministic (for example, hazard should dominate traversable when both compete for the same cell).
   - The result is a single **SurfaceGrid** that policies can inspect directly.

5. **Derive cheap summary predicates back into MapSurface**
   - From the grid, the system may derive a few cheap facts such as:
     - `hazard:near`
     - `terrain:traversable_near`
     - `goal:dir`
   - These are useful because many policies should not need to scan the full grid just to ask a simple gating question.

6. **Keep uncertainty explicit**
   - If matching is ambiguous, the architecture should not hallucinate certainty.
   - Ambiguity belongs in **WM.Scratch** (and can trigger zoom/probe behavior).
   - SurfaceGrid can still be composed conservatively so the agent behaves safely even before ambiguity resolves.

---

#### Concrete mountain-goat-calf example

Imagine the newborn calf is:

- fallen,
- near a cliff edge,
- mother is still far away,
- shelter is far away.

The current observation may contain evidence that the local terrain looks like a dangerous boundary.

##### Step A — what is observed

The system receives evidence such as:

- `posture:fallen`
- `proximity:mom:far`
- `proximity:shelter:far`
- `hazard:cliff:near`

and possibly local patch/grid evidence suggesting:

- a sharp drop-off ahead-right,
- low traversability near the edge,
- safer cells slightly left/back.

##### Step B — NavPatch matching

Suppose the stored prototype library contains:

- **Patch A** = “cliff-edge ledge”
- **Patch B** = “rock ridge / raised boundary”

The current evidence is compared to both.

Possible outcome:

- Patch A score = 0.81
- Patch B score = 0.79

That is not a clean winner, so the match result is:

- top-K = `[A, B, ...]`
- decision = **ambiguous**

##### Step C — what becomes active in working memory

Working memory now has:

- the current **MapSurface** scene sketch (`self`, `mom`, `cliff`, `shelter`, etc.),
- one or more active **NavPatch instances** referring to prototype A / B,
- a **Scratch ambiguity record** saying that the cliff-related match is ambiguous.

##### Step D — SurfaceGrid composition

Even though the system is not certain which prototype is correct, it still needs to act safely.

So the SurfaceGrid for this cycle can be composed conservatively:

- if either plausible patch implies a hazardous boundary in forward-right cells,
  those cells should remain hazardous in the composed grid.

In other words:

- ambiguity in identity does **not** imply permissiveness in action.

The rendered grid might therefore still show:

- dangerous cells near the forward-right edge,
- safer cells toward the left/back,
- no false claim that the exact terrain identity is known.

##### Step E — policy use

Now a policy does **not** need to inspect hidden prototype details.

It can read one composed SurfaceGrid and simple MapSurface summaries such as:

- `hazard:near = True`

That is enough to support behavior such as:

- do not step forward-right,
- prefer a safer direction,
- or trigger a probe/inspect action to gather better evidence.

---

#### Important distinction: prototype vs instance vs grid

These three things should stay mentally separate:

- **NavPatch prototype**  
  long-term memory template stored in Columns

- **NavPatch instance**  
  working-memory use of that template in the current scene

- **SurfaceGrid**  
  the single composed local grid produced from the active instances for this cycle

So:

> prototypes are stored, instances are active, and SurfaceGrid is rendered/composed.

---

#### Lifecycle rule: does SurfaceGrid persist?

SurfaceGrid is best understood as a **derived working-memory view**, not a long-term record.

- It is the grid the agent uses **for the current cycle**.
- On the next cycle, it may be:
  - recomposed from updated patch instances, or
  - reused from cache if nothing relevant changed.

That means it has a short “half-life”:

- **stable within the cycle**
- **replaceable on the next cycle**

Long-term memory should usually store:

- **MapSurface snapshots**
- **patch references**
- **patch prototypes**

not full SurfaceGrid dumps every tick.

---

#### Why this separation is useful

This architecture gives us several advantages:

- **MapSurface stays compact**
  - a scene sketch of entities + slot-families

- **SurfaceGrid stays action-facing**
  - a local “where can I move?” view

- **WorldGraph stays thin**
  - episode index + pointers

- **Columns stay heavy**
  - actual patch prototypes / map payloads

This preserves the core principle:

> **WorldGraph tells you where to look; Columns hold what you actually want to look at.**

---

### Q&A to help you learn this section

**Q: Is a NavPatch the same thing as the rendered SurfaceGrid?**  
**A:** No. A NavPatch is a reusable local map fragment or prototype match. SurfaceGrid is the single composed grid built from the active patch instances for the current cycle.

**Q: What does “match” mean in NavPatch matching?**  
**A:** It means comparing the current **derived evidence** (tokens, local patch/grid features, coarse geometry) against stored prototype features and producing a ranked top-K result.

**Q: If the match is ambiguous, should the agent still build a SurfaceGrid?**  
**A:** Yes. In fact that is when SurfaceGrid is especially useful. The grid should be composed conservatively so the agent remains safe even before the ambiguity is resolved.

**Q: Does policy read the hidden patches directly?**  
**A:** Preferably no. Policy should read:
1. one composed SurfaceGrid, and
2. a few derived MapSurface facts.  
This keeps policy code simple and inspectable.

**Q: Where does ambiguity live?**  
**A:** In **WM.Scratch**, not in MapSurface. MapSurface should remain the compact “belief-now” sketch, while ambiguity bookkeeping stays explicit in the reasoning workspace.

**Q: Is SurfaceGrid long-term memory?**  
**A:** Usually no. SurfaceGrid is a derived, short-lived working-memory view. Long-term memory should store prototypes, pointers, and selected keyframe-like summaries instead.

**Q: Does SeqErr build NavPatches or SurfaceGrid?**  
**A:** No. SeqErr is a separate temporal/error layer. It tracks change over time (`raw_delta`, prediction error, slot changes). Later it may influence attention/probe decisions, but it is not the patch renderer itself.

**Q: Should SurfaceGrid be rebuilt every cycle?**  
**A:** Semantically, yes: there is one current SurfaceGrid per cycle. Mechanically, you may reuse a cached grid if nothing relevant changed.






---

## 3) Data model (conceptual)

A NavPatch is a small, JSON-safe dict. The core fields are intended to be stable enough that we can:
- hash them into a deterministic signature (sig) for de-dup and retrieval scoring,
- store them as Column engrams (navpatch_v1),
- and reference them from MapSurface snapshots (wm_mapsurface_v1) via patch_refs.

### 3.1 Minimal navpatch_v1 shape

Typical fields (v1-ish):
- v: schema/version string or int (evolution hook)
- sig / sig16: stable signature of the canonical “core” (excludes volatile timing fields)
- local_id: local identifier within the current observation tick (optional)
- entity_id: MapSurface entity id this patch is attached to (optional)
- role: coarse role label (scene/mom/shelter/cliff/terrain/goal, …)
- frame: coordinate frame label (self_local / allocentric_stub, …)
- extent: patch bounds in that frame (meters or normalized units)
- tags: small, discrete features (e.g., ["hazard:cliff", "traversable", "stable_footing"])

Optional trace hook (added by matching, not required in incoming obs):
- match: {commit, margin, best, top_k, priors_sig16, decision_note}

### 3.2 Patch references (patch_refs)

Storage strategy (recommended): Option B — store patches as separate navpatch_v1 engrams;
MapSurface stores only references:

- MapSurface entity record carries meta.wm.patch_refs = [<navpatch_eid>, ...]
- wm_mapsurface_v1 snapshots store patch_refs per entity (not full patch geometry)
- WorldGraph stays thin: pointer bindings index episode snapshots (and later: patch_sig summaries)

This preserves the principle: WorldGraph thin, Columns heavy.

---

## 4) Predictive matching loop (baseline v1)

Baseline matching loop:
1) extract observed patches from EnvObservation.nav_patches,
2) retrieve candidate prototypes from Column (by signature similarity / tags),
3) compute similarity + a simple prediction error (diff) measure,
4) record top-K candidates + decision margin,
5) decide: reuse an existing prototype, or mark unknown/create a new prototype.

### 4.1 Priors bundle + error-dominance guardrail (predictive coding)

Recognition is not purely bottom-up:
- a lightweight priors bundle can bias matching when evidence is ambiguous (v1 = hazard bias),
- but if prediction error is high, priors must not “force” a match.

Guardrail:
- if raw error > err_guard ⇒ classify as unknown/new, regardless of prior bias.

### 4.2 Precision weighting (tags vs extent) (v1)

We treat evidence as a small set of channels and weight each channel by a precision/reliability term.

v1 implementation uses two channels:
- tags similarity (semantic features)
- extent similarity (coarse geometry)

We compute a weighted error:
- err_weighted = w_tags * err_tags + w_extent * err_extent
and derive a score from it (e.g., score = 1 - err_weighted).

Interpretation:
- low precision (noisy evidence) ⇒ priors matter more and ambiguity is more likely,
- high precision ⇒ evidence dominates and overrides prior bias.

### 4.3 Commit semantics (Phase 2.2c hook)

Each patch match emits a commit classification:
- commit: confident reuse (or exact match)
- ambiguous: best candidate is above accept threshold but margin vs runner-up is small
- unknown: error too high or below accept threshold (do not hallucinate certainty)

These signals are currently logged (terminal + JSONL). Next slice: persist ambiguous hypotheses into Scratch and use them in control.

---

## 5) Storage + de-dup (Column navpatch_v1)

- Each stored patch gets a deterministic signature (sig / sig16) derived from its canonical core.
- Per-run de-dup prevents “store the same patch 100 times in a row”:
  - if sig already stored in this run, reuse the existing navpatch eid.
- MapSurface stores patch_refs (ids) so wm_mapsurface snapshots stay compact.

---

## 6) Traceability (terminal + JSONL)

Human-readable:
- terminal logs show per-cycle patch counts and match summaries (what was seen, what matched, what changed).
- MapSurface table can show a patches column + a footer summary (counts + sig16).

Machine-readable:
- cycle_log.jsonl emits one record per cycle including:
  - observed patches (nav_patches),
  - navpatch_matches (top-K and chosen + commit/margin),
  - navpatch_priors (bundle/signature + precision weights),
  - policy_fired, drives,
  - (optional) diagnostic EFE scoring fields.

This JSONL trace is the evaluation substrate and regression artifact for Phase X.

---

## 7) Diagnostic EFE policy scoring stub (optional)

We include a trace-only Expected Free Energy (EFE) scoring hook (Friston / Active Inference compatibility).

v0 decomposition (per candidate policy π):
- risk(π): expected hazard cost (falls, predator cues, energy/time loss)
- ambiguity(π): expected remaining uncertainty (e.g., fraction of ambiguous patches)
- preference(π): expected drive improvement

Total (minimized):
- G(π) = w_risk*risk + w_amb*ambiguity - w_pref*preference

Important: this is diagnostic only right now (selection unchanged). Future integration (OFF by default):
use EFE total as a tie-break among already-triggered policies, never bypassing safety gates.

---

## 8) Roadmap hooks (next slices)

Immediate next steps (v5.5 priority order):
1) Persist top-K hypotheses into WorkingMap.Scratch when commit != "commit", and add a cautious probe/vantage policy hook.
2) Patch-aware WorldGraph indexing: pointer nodes carry small patch_sig/tag summaries for patch-driven retrieval.
3) Evaluation scaffolding (goat_foraging_*):
   - goat_foraging_01: multiple paths to bushes with at least one hazard (choose safe path).
   - goat_foraging_02: ambiguous terrain at distance (priors bias recognition; high error yields unknown).
   - goat_foraging_03: out-of-distribution hazard (prediction error triggers caution/exploration).

NavPatch-specific ablations (for later):
- EPI only (baseline)
- NavPatch perception only (no episodic retrieval)
- NavPatch + EPI (full)
- NavPatch but no patch memory (patches transient only)
- priors OFF vs priors ON
- precision schedules vs uniform precision
- EFE scoring stub on/off (w_amb>0 vs w_amb=0)






# Prediction error and predictive coding

> **Architecture status:** this section documents current runner mechanisms. The governing theory is described in the earlier
> map-centered predictive-processing section: residuals remain attached to map comparisons, and the accepted WNM—not the scalar
> error—is the intended cognitive product.


## Predictive coding (high-level intuition)

- Many theories of cortical computation treat perception as a constant negotiation between:
  (a) top-down predictions (what I expect to be true next), and
  (b) bottom-up evidence (what the sensors actually delivered).
- The useful signal is the mismatch (prediction error). It can:
  - gate attention and retrieval (“do I need priors?”),
  - drive consolidation / reconsolidation decisions (“should I store a corrected map?”),
  - shape action selection (avoid repeating policies that consistently fail to produce their predicted postcondition).

- Phase VIII (implemented): prediction error v0 is now used as a conservative control signal to gate keyframe auto-retrieve
  (i.e., mismatch can trigger priors). It is not yet used to change policy scoring; it currently affects whether priors are fetched.
  
- Phase X (NavPatch): prediction error becomes patch-level (tags vs extent), is precision-weighted, and emits
  commit/ambiguous/unknown signals + margins for traceability. We also add an optional diagnostic EFE scoring stub
  (risk/ambiguity/preference/total) in the JSONL trace; selection remains unchanged unless explicitly enabled.


## CCA8 implementation overview

- In CCA8, predicted outcomes are written as hypotheses, not truth:
  - WorkingMap.Scratch stores a short S–A–S chain whose final pred:abcd node is the postcondition hypothesis.
  - EnvObservation remains the authority for “truth-now” when it is present.
- We compute prediction error by comparing a prior cycle’s hypothesis to the next cycle’s observation.

Prediction error is best understood as an **update law over maps**, not as a separate memory system. The prediction itself belongs in WorkingMap.Scratch or WorkingMap.Creative. The comparison happens when the next observation arrives. The result can update confidence, salience, value, retrieval priority, and consolidation priority, but the prediction should not be committed to long-term WorldGraph as a fact unless later observation confirms it.

### Prediction error v0 (minimal signal; posture only)

- v0 is version 0
- v0 stores one predicted postcondition component:
  - predicted next posture (standing vs fallen), attributed to the policy that produced it.
- On the next cognitive cycle, we compare:
  - pred_posture (from the last cycle’s Scratch postcondition) vs
  - obs_posture (from the new EnvObservation / env state report).
- The resulting error vector is a tiny dict with binary components:
  - 0 means match
  - 1 means mismatch

Log line format (example):

[pred_err] v0 err={'posture': 1} pred_posture=standing obs_posture=fallen from=policy:stand_up


**Action shaping ("extinction pressure”)**

When the same policy repeatedly predicts a posture postcondition and the next EnvObservation contradicts it,
CCA8 applies a small **negative shaping reward** to that policy’s skill ledger value (`SkillStat.q`).

- The penalty is applied only after a short mismatch streak (>=2) to avoid punishing the normal “first mismatch after reset”
  where the environment has not yet consumed the last action.
- This creates a biologically-inspired “stop repeating actions that do not work” pressure without requiring a full RL backend.

You may see an additional line during menu 37 runs:

[pred_err] shaping: policy=policy:stand_up reward=-0.15 (streak=2) q=+0.42

This shaping affects RL tie-break behavior (`q`) and also feeds the discrepancy-history used by some non-drive tie-breaks.


### Sequential/error v1 (SeqErr stub: temporal deltas on the sensory stream)

CCA8 also has a diagnostic-first “sequential / error” unit (CCA7 cerebellum-inspired) that tracks how observations change across a short window.

- Implemented in `cca8_run.py` as `seqerr_update_from_obs(ctx, env_obs)`; it runs every env-loop tick (called from `inject_obs_into_world(...)`).
- Inputs:
  - `EnvObservation.raw_sensors` (numeric channels only)
  - `EnvObservation.predicates` (discrete slot tokens)
- Outputs (stored on ctx):
  - `ctx.seqerr_last`: JSON-safe bundle including `raw_delta`, `raw_err` (constant-velocity extrapolation error when ≥3 frames),
    `slot_changes`, `slot_stability`, and a small attention suggestion.
  - `ctx.seqerr_history`: ring buffer of recent frames (size = `ctx.seqerr_window`, default 4).
- Default behavior: does not affect policy selection.
- Optional attention seam (OFF): if `ctx.seqerr_attention_enabled=True`, large errors can set `ctx.seqerr_attention_request`
  (a suggestion string), which future perception code may use to request higher-fidelity channels.
- Debugging: set `ctx.seqerr_verbose=True` to print short lines when discrete slots flip.




## Partial observability knob



Motivation
- Real sensory systems are incomplete and noisy.
- To make priors and retrieval behavior meaningful in CCA8, we need the agent to sometimes *not* receive some facts that are present in the environment.
- The goal of this knob is experimental:
  - create missing facts so seed/merge priors can visibly fill gaps,
  - create prediction mismatches so error signals become informative,
  - without changing the underlying EnvState truth in the simulator.

Knobs (runtime context)

- Masked-step drop counts are recorded in env_meta and used by the retrieval guard as a missingness signal.

- ctx.obs_mask_prob is a probability in [0.0..1.0].
  - When > 0, a fraction of EnvObservation predicates/cues are dropped before they are written into memory systems.
  - Default is 0.0 (fully observed), preserving baseline behavior.

- ctx.obs_mask_seed controls reproducibility:
  - None/off: stochastic masking (uses the global RNG).
  - int: reproducible masking (uses a deterministic per-step RNG derived from the base seed and the step index).
  - Purpose: make “which tokens were dropped at step k” reproducible across runs for experiments and debugging.

- ctx.obs_mask_verbose controls printing:
  - True: prints one config line when masking config changes, and per-step drop lines when anything is dropped.
  - False: masking still occurs, but logs are suppressed.

Implementation note:
- Masking happens in the runner before BodyMap and WorkingMap are updated, so it directly affects “belief-now” and policy selection (not just long-term logging).

Log lines

When masking is enabled (obs_mask_prob > 0), the runner prints a one-time configuration line (or whenever the config changes):

[obs-mask] config mode=seeded seed=123 step_ref=4 p=0.20 protected=3

When masking actually drops anything on a given step, the runner prints a per-step summary:

[obs-mask] mode=seeded seed_eff=... step_ref=4 dropped preds=1/4 cues=0/0 p=0.20

Interpretation:

mode=seeded means a deterministic per-step RNG is being used (reproducible).

mode=global means masking draws from the global RNG (stochastic).

step_ref is the environment step_index when available (otherwise a runner fallback).

seed_eff is the derived per-step seed used for that specific step in seeded mode (printed for traceability).




# Tutorial on WorkingMap

WorkingMap is the workspace in which CCA8 maintains current maps, alternatives, predictions, retrievals, and temporary operations. The
central correction carried forward in Planning v11 is that WorkingMap is **not itself the cognitive world model**. The target world model is one
accepted root WNM inside the workspace, with linked submaps and protected source layers.

## Current implementation

The current WorkingMap pipeline is implemented primarily in `cca8_working_memory.py` and includes:

- MapSurface entities, slot families, relations, and snapshot serialization;
- NavPatch prototypes/instances, matching, top-K ambiguity, priors, precision-like weights, and SurfaceGrid composition;
- NavSummary and grid-derived compact readouts;
- Scratch action chains and ambiguity records;
- Creative candidate outcomes;
- salience, focus, zoom, Probe, retrieval, merge/replace loading, and contextual map switching;
- live `EnvObservation` projection.

These mechanisms are behaviorally relevant today. The accepted-current NavMap path is still a downstream diagnostic shadow.

## Target WorkingMap organization

    WorkingMap
        accepted root WNM
            linked body / maternal / terrain / hazard / object / route submaps

        protected evidence maps
        candidate scene maps
        expected maps
        retrieved maps
        rejected / historical references

        Scratch
            alignments
            comparisons
            structured residuals
            primitive transactions
            bounded surprise episodes

        Creative
            bounded imagined candidates

        projections
            MapSurface
            SurfaceGrid
            NavSummary
            predicates
            BodyMap-facing proposals

Only the root WNM has accepted-current authority.

## How a WNM should be constructed

1. Receive modality evidence with frame, quality, time, latency, and missingness.
2. Match it against stored Local NavMaps.
3. Bind temporal change and segment NavPatches/entities.
4. Query WorldGraph for a bounded memory neighborhood.
5. Load rich candidate maps from Columns.
6. Align current evidence, stored maps, previous WNM context, and relevant submaps.
7. Compose scene candidates while retaining conflict and provenance.
8. Compare expected, candidate, and evidence maps.
9. Accept one root WNM or explicit UNKNOWN.
10. Derive working views and policy accessors from that revision.

## Current MapSurface snapshot pipeline

Current keyframe storage serializes a `wm_mapsurface_v1` payload into Columns and creates a thin WorldGraph pointer/index binding. The
payload may include stable entities, slot-family values, selected relations, patch references, context metadata, and a deterministic
signature used for deduplication.

This is useful long-term-memory scaffolding. It should not be interpreted as the final definition of a stored WNM because current
MapSurface is an observation-driven projection rather than the canonical accepted map.

## Store, retrieve, and apply

**Store**

- serialize current MapSurface;
- assert the payload in Column memory;
- create a sparse WorldGraph pointer/index record;
- skip duplicate content under current signature rules unless explicitly forced.

**Retrieve**

- rank eligible snapshots or prototypes using stage, zone, context, salience, signatures, recency, and other descriptors;
- exclude the just-stored item when appropriate;
- return candidate references without mutating current belief.

**Apply**

- merge mode conservatively fills missing structure and keeps prior cues out of current-evidence tags;
- replace mode rebuilds MapSurface from the prior and is a strong-prior/debug/research condition;
- target architecture instead loads retrieved maps into a protected layer, aligns/compares them, and accepts only through an explicit map
  authority operation.

## NavPatch and SurfaceGrid

NavPatch makes local map reuse concrete:

- prototypes live in Columns;
- current instances live in WorkingMap with pose, evidence, quality, and prototype references;
- instances compose a current SurfaceGrid;
- ambiguity may create Scratch records, focus changes, zoom, or Probe eligibility.

In the target architecture, patches and grid projections are linked to the accepted WNM revision. A patch match does not by itself confer
entity identity or scene acceptance.

## MapSurface and SurfaceGrid are complementary projections

MapSurface answers approximately:

    Which entities and selected relations should be exposed for efficient current use?

SurfaceGrid answers approximately:

    What local topology, traversability, hazard, goal, corridor, occupancy, and UNKNOWN structure matters for action?

Neither should become a second world model independent of the accepted WNM.

## Scratch and primitive transactions

Scratch should eventually hold the map-native action record:

    accepted before-map
        + trigger/safety evidence
        + primitive intent
        + expected local transformation
        + progress and fast feedback
        + observed outcome
        + accepted after-map

Current action chains and predicted postconditions are useful precursors. Scratch ownership, lifetime, bounds, and cleanup must remain
explicit.

## Creative and goat-level limits

Creative can hold isolated candidate outcomes or bounded map variants. It cannot directly rewrite the root WNM or actuators. CCA8 should
not turn Creative into a large human-style planner. One or a few candidates may support Probe, safety, or short local choice; sustained
counterfactual branches belong to later architectures.

## BodyMap relationship

BodyMap currently supplies fast policy gating. The target relationship is conservative synchronization:

    fast body feedback
        -> BodyMap safety

    accepted WNM body relations
        -> BodyMap-facing projection

    disagreement
        -> explicit discrepancy and conservative resolution

BodyMap may veto dangerous action even when a slower map projection is stale or uncertain.

## Keyframes and consolidation

Current keyframes include stage/zone transitions, milestones, periodic events, prediction discrepancies, and experiment controls. The
future consolidation service should run after accepted-map and outcome processing and decide whether to store:

- a scene or submap;
- a prototype;
- a transformation or trajectory;
- a success/failure episode;
- a surprise/resolution episode;
- a developmentally or safety-important milestone.

WorldGraph receives sparse indexes and pointers; Columns receive the rich map payload.

## Current menu tools

Menu numbers may change; use the displayed runner menu as authority.

- Menu 35: one verbose closed-loop cycle and Oscilloscope teaching output.
- Menu 37: compact multi-cycle run.
- Menu 38: inspect BodyMap.
- Menu 42: configure contextual map-switch evaluation.
- Menu 43: inspect WorkingMap/MapSurface payload.
- Menu 44: store MapSurface snapshot.
- Menu 45: list recent MapSurface engrams.
- Menu 46: rank a stored MapSurface candidate.
- Menu 47: load a stored MapSurface into WorkingMap.

## Debugging order

For current-runtime problems, inspect:

    EnvObservation
        -> BodyMap
        -> MapSurface
        -> NavPatch / SurfaceGrid / NavSummary
        -> NavMap diagnostic comparison
        -> retrieval/keyframe records
        -> policy candidates and selected primitive
        -> WorldGraph / Column side effects

For target-architecture work, also verify the source WNM revision and protected authority class of every derived value.


# Memory systems in CCA8

CCA8 memory is a coordinated map ecology rather than one store. The structures differ in authority, lifetime, scale, update rule, and
computational purpose.

## One-line roles

| Component | Question answered |
|---|---|
| Modality evidence map | What did this sensory channel support now, in which frame, with what quality and missingness? |
| Local NavMap / prototype | Which stored same-modality pattern best organizes the evidence? |
| NavPatch | Which bounded entity, terrain, hazard, contact, landmark, goal, or scene fragment is active? |
| Accepted root WNM | What map is authorized as the goat's current embodied interpretation? |
| Linked submap | Which bounded close-up or alternate scale is currently relevant under the accepted root? |
| BodyMap | What rapid body/near-space safety information must be available now? |
| MapSurface | Which stable entity/relation handles should be projected for efficient use? |
| SurfaceGrid | What local topology, traversability, hazard, goal, and UNKNOWN structure matters? |
| Scratch | What comparison, transaction, ambiguity, expected transformation, or surprise episode is temporarily active? |
| Creative | Which bounded imagined candidates are being considered without authority? |
| WorldGraph | Where should memory retrieval, episode traversal, or sparse planning look? |
| Columns | What rich maps, prototypes, trajectories, transformations, and episode payloads are stored there? |

## Current authority status

At the current baseline, BodyMap and observation-driven WorkingMap structures are active policy sources. WorldGraph history, retrieval
hints, drives, and policy bridges also influence action. The accepted-current NavMap remains diagnostic. Therefore the architecture must
be described in two layers:

- **current runtime contract**, which must remain accurate for developers and tests;
- **target Map-Primacy contract**, which guides staged authority migration.

## Short-term and long-term memory

**WorkingMap** holds current and protected working structures. **Columns** hold durable rich content. **WorldGraph** holds sparse
indexes, episodes, actions, keyframes, content addresses, and pointers.

    WorkingMap
        -> current evidence, candidates, accepted WNM, projections, Scratch, Creative

    Columns
        -> rich durable maps and transformations

    WorldGraph
        -> sparse retrieval and episode navigation

The old phrase "WorldGraph thin, Columns heavy" remains useful, with one addition: WorkingMap should become WNM-centered rather than
MapSurface/state-centered.

## The accepted WNM is not long-term memory

The WNM is the current operational map. It may be based partly on retrieved long-term content, but it is not automatically consolidated.
A new accepted revision may be transient, incomplete, or later rejected. Long-term storage requires an explicit consolidation decision.

## Sensory memory and Local NavMaps

Future sensory processing should retain separate channel provenance:

    visual evidence map
    auditory evidence map
    olfactory evidence map
    tactile evidence map
    vestibular evidence map
    proprioceptive evidence map
    interoceptive evidence map

Each channel can match stored Local NavMaps, bind short temporal change, and contribute to segmented NavPatches or entities. Cross-modal
binding occurs after frames, features, quality, and missingness are known.

## BodyMap

BodyMap is deliberately small and fast. Current fields include posture, maternal distance, nipple state, shelter/cliff relationships, zone,
freshness, and related gating values. It remains behaviorally active today.

Target discipline:

- preserve immediate safety and fast body feedback;
- synchronize ordinary body/near-space readouts with accepted WNM relations;
- expose disagreement and stale/UNKNOWN values;
- prevent BodyMap from expanding into an independent symbolic world model.

## MapSurface

Current MapSurface uses stable entity ids and overwrite-by-slot semantics. This makes the live scene easy to inspect and update. It is
valuable, but its compact slot families can lose geometry, uncertainty, trend, scale, and provenance if treated as the complete cognition.

Target MapSurface becomes a deterministic projection containing stable handles, selected attributes and relations, source WNM revision,
freshness, and unresolved status.

## SurfaceGrid and NavPatch

SurfaceGrid is the local topology view. NavPatch prototypes are reusable stored fragments; instances are current aligned matches. Current
matching, ambiguity, priors, precision-like weights, composition, and NavSummary are active scaffolds.

Target rules:

- patches preserve frame, scale, pose, extent, source, and prototype/instance distinction;
- matching returns correspondence and structured residual, not score alone;
- hazard and UNKNOWN remain conservative during composition;
- the grid records the accepted WNM revision and active submap configuration from which it was derived.

## Scratch

Scratch should hold transient cognitive work rather than long-term truth:

- action chains and primitive transactions;
- expected transformations;
- alignments and comparisons;
- structured residuals;
- ambiguity and Probe records;
- bounded surprise episodes;
- local revision proposals and rejected alternatives.

Scratch records are explicitly owned, bounded, and pruned. Promotion to accepted or long-term memory requires a separate operation.

## Creative

Creative stores bounded imagined or counterfactual candidates. It is non-authoritative. The goat may use tiny lookahead or candidate
comparison, but extensive multibranch planning and recursive internal map processing belong to CCA9/CCA10.

## WorldGraph

WorldGraph is a sparse graph of bindings, edges, anchors, actions, keyframes, provenance, and Column pointers. It supports BFS/Dijkstra,
inspection, and bounded retrieval/planning. It does not need to mirror every WNM feature every cycle.

Current predicates and cue tags remain useful for compatibility and experiments. They should increasingly be understood as indexes,
historical records, or derived readouts rather than as the goat's full current world representation.

## Columns and engrams

Columns hold rich payloads outside the sparse graph:

- stored Local and multisensory NavMaps;
- NavPatch prototypes;
- scene and object maps;
- body/terrain/maternal maps at multiple scales;
- sensory features and trajectories;
- primitive maps and learned local transformations;
- before-action-after episodes;
- success, failure, surprise, and resolution records;
- generalized families with support and exceptions.

The current in-memory Column implementation is a scaffold. A Python Column need not correspond numerically one-to-one with a
biological cortical minicolumn.

## Retrieval

Retrieval is a controlled map operation:

1. derive a query from current evidence, WNM context, drive/task relevance, and WorldGraph neighborhood;
2. retrieve a bounded set of Column maps;
3. align them to current frames and scales;
4. compare them with current evidence;
5. preserve candidates in RETRIEVED/CANDIDATE layers;
6. accept one root, create a new map, or retain UNKNOWN.

Current snapshot merge/replace behavior is valuable for experiments but should not be confused with the final authority operation.

## Prediction, transitions, and procedural memory

Procedural memory is map-like at the cognitive level:

    before-map pattern
        + primitive
        -> expected successor-map family

The learned content can include trigger pattern, intent, expected transform, progress signature, outcome reliability, costs, safety
constraints, supporting episodes, exceptions, and developmental stage.

Low-level motor memory remains below CCA8 in the controller/HAL/firmware/skill-provider layer.

## Drives and valence

Drives are legitimate compact biological control states. Their effects should be expressed through map value and primitive competition:

- hunger increases relevance of maternal/nipple/milk maps;
- fatigue increases relevance of safe-rest maps;
- danger increases hazard salience and protective urgency;
- successful contact or feeding changes value attached to map relations and routes.

## Temporal memory

TemporalContext provides recency and boundary scaffolding. It is not motion itself. Motion, approach rate, contact duration, rise/slip,
trajectory, and time-to-hazard should be bound to map regions/entities using Sequential/Error and fast feedback products.

## Keyframes and consolidation

A keyframe marks a potential memory boundary; it does not force every current structure into long-term memory. A target consolidation
decision records why content deserves storage and where it belongs.

Possible reasons:

- developmental milestone;
- body transition or safety-critical outcome;
- novel map or recurring prototype;
- useful or failed transformation;
- context boundary;
- significant surprise and resolution;
- experiment/publication capture under an explicit protocol.

Columns receive the rich payload. WorldGraph receives sparse pointers and episode/action links.

## Persistence and provenance

Persisted/external records require versioned schemas and round-trip tests. Every map-derived or memory-derived record should preserve:

- source map and revision;
- frame and transform;
- evidence or retrieval provenance;
- creation and acceptance times;
- authority class;
- quality/uncertainty semantics;
- parent/child links;
- operator and software version;
- experiment configuration and random streams when relevant.

## Debugging memory

Current debugging order:

    evidence packet
        -> BodyMap
        -> MapSurface
        -> NavPatch / SurfaceGrid / NavSummary
        -> NavMap expected/evidence/accepted diagnostics
        -> Scratch / Creative
        -> retrieval / keyframe
        -> policy
        -> WorldGraph / Column writes

Target debugging adds:

    root WNM revision
        -> active linked submap
        -> source/authority classes
        -> projection revision
        -> primitive transaction
        -> structured residual and resolution

## One-sentence summary

> CCA8 memory is a coordinated family of map representations, protected workspaces, fast controls, sparse indexes, and rich durable
> payloads whose central purpose is to construct, use, test, revise, and selectively remember one accepted root WNM.


# Binding and Edge Representation

> **Architecture status:** bindings and edges are the current WorldGraph episode/index vocabulary. They remain useful for history,
> retrieval, planning, provenance, and compatibility, but they are not intended to replace the spatially embedded accepted WNM.

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


## Anchor NOW movement: attach="now" vs WorldGraph.set_now()

Two distinct ideas often get conflated:

### 1) attach="now"
Creating a new binding with `attach="now"`:
- adds an edge `NOW --then--> new_binding`
- updates `LATEST = new_binding`
- **does not** re-point the NOW anchor itself

So NOW remains a stable anchor binding unless explicitly moved.

### 2) WorldGraph.set_now(...)
`world.set_now(bid)` **re-points the anchor**:
- updates the anchors map so NOW points to a different binding id
- updates anchor tags (removes `anchor:NOW` from the previous binding, adds it to the new one)

In closed-loop runs, NOW may be moved explicitly at keyframes (or continuously in a debugging mode) so that
“plan from NOW” reflects the current state binding even when long-term env writes are deduplicated.



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

 
b1: [anchor:NOW_ORIGIN]  →  episode root  
b2: [pred:posture:fallen]  
b3: [action:push_up]  
b4: [action:extend_legs]  
b5: [anchor:NOW, pred:posture:standing]
 

NOW and LATEST are both `b5` immediately after the StandUp policy executes. If you then add a cue:

 
b6: [cue:vision:my_cue:mom]    # attached from NOW → b5 --then--> b6
 

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

 python
{"base": "NEAREST_PRED", "pred": "posture:standing", "bid": "b5"}
 

or falls back to:

 python
{"base": "HERE", "bid": "?"}      # HERE stub, unresolved
{"base": "NOW", "bid": "b_now"}   # if HERE and NEAREST_PRED aren’t available
 

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
   
    python
   base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
    

2. Decide an effective attach mode:
   
    python
   effective_attach = _maybe_anchor_attach("latest", base)
    
   
   * If `base["base"] == "NEAREST_PRED"` and you asked for `"latest"`, we return `"none"`.
   * Otherwise, we leave attach unchanged.

3. Create the new binding with `attach=effective_attach`.
   
   * If `effective_attach == "none"`, the node is created **unattached** (no auto edge from LATEST).

4. If we used a NEAREST_PRED base and suppressed auto-attach, we explicitly anchor the new node under the base:
   
    python
   _attach_via_base(world, base, new_bid, rel="then", meta={...})
   # adds base['bid'] --then--> new_bid
    

In logs you’ll see:

 
[base] write-base suggestion for this add_predicate: NEAREST_PRED(pred=posture:standing) -> b5
[base] base-aware attach: new binding will be created unattached, then linked from the suggested NEAREST_PRED base instead of plain 'LATEST'.
Added binding b9 with pred:vision:silhouette:mom (attach=none)
[base] attached b9 under base b5 via then (NEAREST_PRED(pred=posture:standing) -> b5)
 

and in the mini-snapshot:

 
b5: [anchor:NOW, pred:posture:standing]
    edges: then:b6, then:b7, then:b9
b6: [cue:vision:my_cue:mom]
    edges: (none)
b7: [action:orient_to_mom] -> b8
b8: [pred:seeking_mom]
    edges: (none)
b9: [pred:vision:silhouette:mom]
    edges: (none)
 

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

 python
{"base": "NEAREST_PRED", "pred": "posture:standing", "bid": "b5"}
 

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







# Data schemas (for contributors)

This section documents the **canonical in-memory shapes** and their **JSON snapshot equivalents**. The goal is that a maintainer can:

- read the structures,
- eyeball a saved session,
- and reconstruct “what happened” without digging through the full codebase.

CCA8 intentionally uses **plain JSON/JSONL** rather than Python-specific formats for portability and human inspectability.

---

## Session snapshot (top level)

A saved session is a single JSON object (written by `--autosave`, `--save`, and “Manual Save Session”):

 json
{
  "saved_at": "2025-10-16T12:34:56",
  "app_version": "cca8_run/0.7.11",
  "platform": "Windows-10-10.0.22631-SP0",
  "world": { "...WorldGraph..." },
  "drives": { "...drive levels..." },
  "skills": { "...policy telemetry..." }
}
 

Notes:
- `saved_at` is local time (runner clock) at write time.
- `app_version` and `platform` are informational and help debug “works on my machine” issues.

---

## WorldGraph snapshot (`world`)

The `world` object is a compact episode index: bindings + edges + anchors.

Typical fields:

 json
{
  "version": "0.7.x",
  "next_id": 7,
  "latest": "b6",
  "anchors": { "NOW": "b1", "HERE": "b1" },
  "bindings": {
    "b1": { "...binding..." },
    "b2": { "...binding..." }
  }
}
 

**Invariants (world):**
- `next_id` is the next numeric suffix to allocate (`b{next_id}`), advanced on load to avoid collisions.
- `latest` is the most recently created binding id (used for some default attachments).
- `anchors` maps named anchors (e.g., `NOW`, `HERE`) to binding ids.
- `bindings` is a dict `{binding_id -> binding_object}`.

---

## Binding (node)

Bindings are the atomic “episode cards” in the WorldGraph.

Minimal shape:

 json
{
  "id": "b42",
  "tags": [
    "pred:posture:standing",
    "cue:vision:silhouette:mom",
    "anchor:NOW"
  ],
  "meta": {
    "policy": "policy:stand_up",
    "ticks": 12,
    "epoch": 3
  },
  "edges": [
    { "to": "b43", "label": "then", "meta": {} }
  ],
  "engrams": {
    "episodic:image": "e17",
    "wm:surfacegrid": "e18"
  }
}
 

**Conventions / invariants (binding):**
- `id` is a string of the form `b<num>`, unique within the world.
- `tags` is a list of compact string tokens (see Tagging Standard).  
  A “stateful” binding should usually include at least one `pred:*` tag.
- `meta` holds light provenance + timestamps (policy name, boot flags, tick counters, epoch, etc.).  
  This should remain JSON-serializable (dict/str/int/float/bool/lists), no custom objects.
- `edges` is an adjacency list stored on the **source** binding (directed edges).
- `engrams` holds **pointers** to rich content stored outside the WorldGraph.  
  The graph stays small and fast; the engram store can grow.

---

## Edge (directed link)

Edges are stored **on the source binding** in its `edges[]` list:

 json
{ "to": "b43", "label": "then", "meta": {} }
 

**Conventions:**
- `to` is the destination binding id.
- `label` is a short relation name. Use `"then"` for episode flow; add domain labels when helpful (e.g., `approach`, `search`, `latch`).
- Multiple edges between the same pair are allowed if labels differ. The UI may warn when you attempt to add an identical `(src, label, dst)` edge.

---

## Drives snapshot (`drives`)

Drives are persisted as numeric levels (usually normalized floats):

 json
{ "hunger": 0.70, "fatigue": 0.20, "warmth": 0.60 }
 

Important:
- Only numeric levels are persisted.
- **Drive flags** (`drive:*`) are ephemeral controller signals derived each step and are not stored in the snapshot.
  If you want persisted drive state in the WorldGraph, explicitly write `pred:drive:*` (or `cue:drive:*`) tags.

---

## Skills / policy telemetry snapshot (`skills`)

`skills` is a lightweight policy ledger (counts + running value estimates), keyed by policy name:

 json
{
  "policy:stand_up": { "n": 3, "succ": 3, "q": 0.58, "last_reward": 1.0 }
}
 

Field intent (typical):
- `n`: number of times the policy was attempted
- `succ`: number of “success” outcomes (as defined by that policy)
- `q`: running value estimate / quality score (implementation-dependent)
- `last_reward`: last scalar reward recorded for that policy

---

## Policy structure (in code)

Policies are *not* serialized directly, but it helps contributors to know the runtime contract:

A policy typically has:
- a stable **name** (`policy:*`) used in provenance + skill telemetry,
- a `trigger(...) -> bool` (or score) that checks whether the policy is eligible in the current context,
- an `execute(...)` (or `act(...)`) that:
  - may write bindings/edges/tags into the WorldGraph,
  - returns a compact result bundle (status, reward, notes),
  - updates policy telemetry (skills) via the controller.

Design goal: policies should be small, inspectable, and composable — most “memory” should live in the WorldGraph + engrams rather than hidden inside policy code.

---

## Environment observation schema (agent-facing)

The environment is *ground truth* (`EnvState`), but the agent only receives **observations** (`EnvObservation`) via the PerceptionAdapter.

A typical observation packet contains:
- `predicates: list[str]` — symbolic state (posture, proximity, etc.)
- `cues: list[str]` — sensory “evidence” tokens
- `raw_sensors: dict[str, float|int|str]` — optional continuous sensors
- `env_meta: dict` — stage / zone / other debug metadata

Keeping this packet small and explicit is deliberate: it makes the perception → memory boundary auditable.



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

> **Architecture status:** WorldGraph is a sparse episode/retrieval index and pointer scaffold. It is not the accepted current world map.
> Rich map content belongs in Columns; current belief requires activation, alignment, comparison, and WNM acceptance.

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

 python
@dataclass(slots=True)
class Binding:
    id: str
    tags: set[str]
    edges: list[Edge]
    meta: dict
    engrams: dict
 

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

> **Architecture status:** BodyMap is currently an active and trusted policy-gating register. The target architecture preserves its rapid
> safety authority while synchronizing ordinary body/near-space readouts with the accepted WNM and exposing disagreements explicitly.



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

These are body-side defaults before any Cognitive Cycle runs.

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

The runner also prints a small BodyMap summary on each Cognitive Cycle:

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



## Zone (BodyMap spatial classification) — what it is used for

CCA8 uses a coarse **zone** label derived from BodyMap near-space slots:

- `proximity:shelter:{near|far}`
- `hazard:cliff:{near|far}`

Current classification (intentionally minimal):
- **unsafe_cliff_near**: cliff is near AND shelter is not near
- **safe**: shelter is near AND cliff is not near
- **unknown**: any other combination (including missing data)

Zone is used as a **gating signal**, not as a long-term semantic fact:
- example: `policy:rest` is vetoed in `unsafe_cliff_near` even if fatigue is high
- example: `policy:follow_mom` receives a positive “escape cliff” preference in `unsafe_cliff_near`

This keeps safety decisions fast: policies can consult BodyMap instead of scanning the long-term episodic chain.




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

> **July 2026 modularization note:** `cca8_run.py` remains the composition root and compatibility facade, so many historical names are still importable from it. Their implementations may now live in `cca8_context.py`, `cca8_cli.py`, `cca8_preflight.py`, `cca8_experiments.py`, `cca8_openai.py`, `cca8_working_memory.py`, `cca8_profiles.py`, or `cca8_guidance.py`. Use the Architecture module-ownership table and `python cca8_run.py --about` when physical source ownership matters.

## Public surface (importables)
Exports (see `__all__`):  
`main`, `interactive_loop`, `run_preflight_full`, `snapshot_text`, `export_snapshot`, `world_delete_edge`, `boot_prime_stand`, `save_session`, `versions_dict`, `versions_text`, `choose_contextual_base`, `compute_foa`, `candidate_anchors`, `Ctx`, `HAL`, `PolicyRuntime`, `__version__`.


### Runtime context (`Ctx`)

Dataclass carried between engine and CLI:  
`sigma: float`, `jump: float`, `age_days: float`, `ticks: int`, `profile: str`, `winners_k: Optional[int]`, `hal: Optional[Any]`, `body: str`.

---

### Where the user-facing run guide lives

This tutorial is intentionally **code-facing**.

For the canonical “how to run CCA8” instructions (CLI flags, autosave/load workflow, preflight, and menu highlights), see:

- **Runner, menus, and CLI**
- **Persistence: Autosave/Load**
- **Preflight (four-part self-test)**

---

## cca8_run.py — Call Flow (internal wiring)

**High-level call flow**

 
main(argv)
 ├─ configure logging (+ optional terminal tee)
 ├─ parse CLI flags into an argparse Namespace
 ├─ optional: print versions / exit (--about, --version)
 ├─ optional: run preflight probes / exit (--preflight)
 ├─ optional: run one-shot planning / exit (--plan ...)
 └─ interactive_loop(args)  ← primary TUI entry
 

**What `interactive_loop(args)` sets up**

- Instantiates: `WorldGraph`, `Drives`, `Ctx`, `PolicyRuntime`, and (optionally) `HAL`.
- Optionally loads a session snapshot (`--load`) and/or seeds a deterministic demo world (`--demo-world`).
- Optionally runs a boot “prime” step (profile-dependent; can be disabled with `--no-boot-prime`).
- Enters the TUI menu loop which dispatches to helpers like `snapshot_text(...)`, `export_snapshot(...)`,
  planner calls, manual graph edits, and environment-loop demos.


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

> **Architecture status:** this section documents current Python policy and controller behavior. The target adds map-native primitive
> patterns, WNM queries, expected transformations, and transactions while retaining the readable Python controller as the safety and
> execution substrate.

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

1. `9` Instinct step → if the controller writes, you’ll see  
   `[temporal] boundary after write (cos reset to ~1.000)` and `cos_to_last_boundary: 1.000` in the snapshot.

2. `10` Autonomic tick × N → `cos_to_last_boundary` decays gently (drift only).

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

* **Signal bridge** (menu **13** “Capture scene”) wraps a small vector into a `TensorPayload`, asserts it as an engram, attaches the pointer to the new binding, and—if you pass `attrs=time_attrs_from_ctx(ctx)`—**mirrors time** into the column record automatically.
  
  

## 7) Minimal usage cribs

**A) Programmatic (Column direct)**
    from cca8_column import mem
    from cca8_features import TensorPayload, FactMeta
    vec = [0.1, 0.2, 0.3]
    payload = TensorPayload(data=vec, shape=(len(vec),))
    meta = FactMeta(name="vision:silhouette:mom", links=[latest_bid]).with_time(ctx)
    engram_id = mem.assert_fact("vision:silhouette:mom", payload, meta)
    world.attach_engram(latest_bid, column="column01", engram_id=engram_id, act=1.0)

**B) Via WorldGraph bridge (menu 13 path)**
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
  


## The bridge (WorldGraph ↔ Column)

1. **Emit**: Runner **13) Capture scene** asks for channel/token/family (cue|pred), attach policy (now/latest/none), and a small vector. It creates a binding and asserts a column engram, then attaches a pointer:

`"engrams": { "column01": { "id": "<engram_id>", "act": 1.0 } }`

The Column record stores `{id, name, payload, meta}`, where `meta.attrs` carries `ticks`, `tvec64`, **epoch**, **epoch_vhash64**.

2. **Attach**: Only the **pointer** (column name → id) sits on the binding; the heavy payload stays in the Column. Planning remains purely over tags/edges.

3. **Inspect**:
* **Display snapshot** shows which bindings have engrams: `engrams=[column01]`.

* **Inspect binding details** prints the full pointer JSON (including the engram id).

* **15) Inspect engram by id** prints the Column record (meta + payload summary). If you type a **binding id** (e.g., `b11`) it resolves its engram automatically.

* **16) List all engrams** enumerates all attached engrams with time attrs.


### Minimal API surface (dev view)

* **Column store** (`cca8_column.py`):  
  `ColumnMemory.assert_fact(name, payload, meta) -> engram_id`  
  `ColumnMemory.get(engram_id) -> dict`  
  (Default singleton `mem = ColumnMemory(name="column01")` used by the bridge.)

* **Runner bridge** (`cca8_run.py`):  
  `world.capture_scene(channel, token, vector, attach, family, attrs=...) -> (bid, engram_id)`  
  plus menu **13**, **15**, **16** wrappers so you don’t have to write code to use it.
  

### Quick tutorial (CLI)

1. **13) Capture scene** → use `vision / silhouette:mom / cue / now / 0.1 0.2 0.3`  
   Runner prints both the **binding id** and the **engram id**, and echoes the time attrs mirrored into the engram.

2. **20) Inspect binding details** → paste the binding id. You’ll see the engram pointer under `binding.engrams["column01"]`.

3. **15) Inspect engram by id** → paste the engram id **or** just type the binding id; it resolves the pointer for you.

4. **16) List all engrams** → browse all engrams with their source binding and time attrs.



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


From the Runner (menu **13 Capture scene**), we pass `attrs=time_attrs_from_ctx(ctx)`, which copies **`ticks`**, **`tvec64`**, **`epoch`**, **`epoch_vhash64`** into `meta.attrs` of the Column record at **assert time**. With the current Runner, capture does a **pre-capture event boundary**, so the engram’s `epoch` reflects the **new** boundary you just created.


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

This is more practical earlyon (we don’t have to build our own vision stack inside CCA8), and it’s what weimplicitly assumed in the associated work on the architecture.

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

 python
from cca8_env import (
    EnvState,
    EnvObservation,
    EnvConfig,
    FsmBackend,
    PerceptionAdapter,
    HybridEnvironment,
)
 

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
  
  * `step_index: int` – Cognitive Cycles in this episode.

Only `HybridEnvironment` and backends mutate `EnvState`; CCA8 never touches it directly.

---

### 3.2 EnvObservation — one-tick sensory/perceptual packet

`EnvObservation` is what crosses the agent–environment boundary each tick:

 python
@dataclass
class EnvObservation:
    raw_sensors: dict[str, Any]
    predicates: list[str]
    cues: list[str]
    env_meta: dict[str, Any]
 

* **`raw_sensors`** – numeric/tensor channels (e.g., `distance_to_mom`, `kid_temperature`).
* **`predicates`** – discrete tokens suitable for WorldGraph (e.g., `posture:fallen`, `proximity:mom:close`, `nipple:latched`, `milk:drinking`).
* **`cues`** – cue tokens for features/columns (e.g., `vision:silhouette:mom`, `drive:cold_skin`).
* **`env_meta`** – small metadata (e.g., `{"time_since_birth": ..., "scenario_stage": ...}`).

These are **observations**, not beliefs. WorldGraph and Columns are where CCA8 turns them into internal state and memory.

---

## 4. HybridEnvironment — orchestrator and RL-style seam

`HybridEnvironment` is the **central hub** on the environment side. It owns `EnvState` and presents a Gym-like API:

 python
env = HybridEnvironment(config=EnvConfig())
obs, info = env.reset(seed=None, config=None)
obs, reward, done, info = env.step(action, ctx)
 

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

* **Time thresholds** (in Cognitive Cycles) drive the default progression:
  
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

* (Phase X) Emits stub **nav_patches** (optional): a small list of patch dicts (role/tags/extent)
  for NavPatch matching and MapSurface patch_refs.
  
  
PerceptionAdapter knows nothing about WorldGraph or policies; it just turns `EnvState` into `EnvObservation`.

---

## 7. Runner handshake and Menu Selection Envr't Step (HybridEnvironment-->WorldGraph demo) closed-loop demo

The **Runner module** (`cca8_run.py`) owns the *full* simulation loop (menu, WorldGraph, controller, drives, `Ctx`). The environment module plugs in as one component of that loop. 

### 7.1 Where HybridEnvironment is created

In `interactive_loop(args)`, after `world`, `drives`, and `ctx` are created and the temporal soft clock is initialized, the runner instantiates the environment:

 python
world = cca8_world_graph.WorldGraph()
drives = Drives()
ctx = Ctx(...)
ctx.temporal = TemporalContext(...)
...
env = HybridEnvironment()
 

So `env` and `ctx` sit side-by-side in the main loop.

---

### 7.2 Menu Selection — “Cognitive Cycle (HybridEnvironment → WorldGraph demo)”

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
     
      python
     env_obs, env_info = env.reset()
     ctx.env_episode_started = True
     ctx.env_last_action = None
     print(f"[env] Reset newborn_goat scenario: episode_index={...} scenario={...}")
       :contentReference[oaicite:35]{index=35}  
     
     This starts a fresh newborn-goat episode at the `"birth"` stage with `kid_posture="fallen"`, `mom_distance="far"`, `nipple_state="hidden"`.   
     
      
   
   * **Subsequent calls** – feed the last fired policy back into the environment:
     
      python
     action_for_env = ctx.env_last_action   # e.g., "policy:stand_up" or None
     env_obs, _reward, _done, env_info = env.step(action=action_for_env, ctx=ctx)
     ctx.env_last_action = None
     st = env.state
     print(f"[env] step={env_info['step_index']} stage={st.scenario_stage} "
           f"posture={st.kid_posture} mom_distance={st.mom_distance} "
           f"nipple_state={st.nipple_state} action={action_for_env!r}")
      
     
     This is where `FsmBackend` can treat `policy:stand_up` or `policy:seek_nipple` as early hints and accelerate the storyboard.

4. **Environment → WorldGraph (observation injection)**
   For each predicate in `env_obs.predicates`:
   
    python
   bid = world.add_predicate(
       token,
       attach=attach,  # first "now", then "latest"
       meta={"created_by": "env_step", "source": "HybridEnvironment"},
   )
   print(f"[env→world] pred:{token} → {bid} (attach={attach})")
   attach = "latest"
     :contentReference[oaicite:39]{index=39}  
   
   For each cue in `env_obs.cues`:
   
    python
   bid_c = world.add_cue(
       cue_token,
       attach=attach_c,  # first "now", then "latest"
       meta={"created_by": "env_step", "source": "HybridEnvironment"},
   )
   print(f"[env→world] cue:{cue_token} → {bid_c} (attach={attach_c})")
   attach_c = "latest"
     :contentReference[oaicite:40]{index=40}  
   
   This stamps the environment’s current view (posture, proximity, nipple state, visual cue) into the WorldGraph as ordinary `pred:*` and `cue:*` bindings, tagged with `source="HybridEnvironment"` for provenance.
   
    

5. **WorldGraph → Controller → Env (action feedback)**
   After injection, the runner gives the controller one decision step:
   
    python
   POLICY_RT.refresh_loaded(ctx)
   fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
   if fired != "no_match":
       print(f"[env→controller] {fired}")
       # extract "policy:..." from the first token of the summary string
       ctx.env_last_action = first_token_if_policy(fired)
   else:
       ctx.env_last_action = None
     :contentReference[oaicite:41]{index=41}  
   
   The next time you choose this menu selection, `ctx.env_last_action` is passed into `env.step(...)` as `action`, allowing `FsmBackend` to react (e.g., treat `policy:stand_up` as standing earlier during `"struggle"`).   
   
    

6. **Discrepancy diagnostics (posture expectation vs observation)**
   The mini-snapshot printed after this menu selection includes a **diagnostic line** when the latest environment posture and the latest **policy-expected** posture disagree.
   Internally, the runner:
   
   * Finds the newest env-driven `pred:posture:*` (with `meta["source"] == "HybridEnvironment"`).
   
   * Finds the newest policy-written `pred:posture:*` (with `meta["policy"]` set, e.g., by `policy:stand_up`). 
   
   * If they differ (e.g., env says `fallen` but the last StandUp invocation wrote `standing`), it prints:
     
      
     [discrepancy] env posture='fallen' at b18 vs policy-expected posture='standing'
                  from policy:stand_up at b22
     [discrepancy] -often the motor system will attempt an action, but it does not actually occur-
      
   
   * It also keeps a short **discrepancy history** (last ~50 entries) in `ctx.posture_discrepancy_history` and prints it under:
     
      
     [discrepancy history] recent posture discrepancies (most recent last):
       [discrepancy] ...
       :contentReference[oaicite:44]{index=44}  
      
   
   These lines are **display-only diagnostics**; they do not create additional bindings. They are meant to mirror a robotics / physiology intuition:
   
   > *The motor system may “intend” standing, but sensors still report a fallen posture until the environment actually transitions.*

Putting it all together, this menu selection implements a minimal closed loop:

 
world dynamics (HybridEnvironment/FsmBackend)
  → EnvObservation (predicates + cues)
  → WorldGraph update + one controller step
  → policy name (e.g., "policy:stand_up")
  → fed back into HybridEnvironment.step(...) on the next call of this menu selection
 

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

Q: How does Menu “Cognitive Cycle (HybridEnvironment → WorldGraph demo)” use all this?
A: That menu item runs a single closed-loop tick:

HybridEnvironment evolves EnvState via reset or step(action, ctx).

PerceptionAdapter produces EnvObservation.

The runner injects predicates/cues into the WorldGraph.

The controller runs one policy step and records which policy executed.

The chosen policy name is fed back as the next action into HybridEnvironment on the following env-step.

It’s a minimal “world ↔ brain” loop for inspection and debugging.



---



# Preflight (four-part self-test)

Run all checks and exit:

    python cca8_run.py --preflight

Preflight is the fast way to answer: “Is this checkout internally consistent, are the deterministic tests green, and is the host ready to run the current CCA8 software?”

---

## What runs

1. **Unit tests and coverage.**
   Preflight runs the repository’s `tests/` directory with pytest. If `pytest-cov` is available, it also writes coverage artifacts and reports executable-line coverage. The authoritative August 2026 baseline contains 505 passing tests; the exact count is expected to grow.

2. **Scenario and architecture probes.**
   Deterministic whole-flow checks cover imports and key symbols, version reporting, WorldGraph invariants, NOW/LATEST behavior, attach semantics, planner behavior, lexicon enforcement, engram round trips, environment/controller integration, WorkingMap/MapSurface paths, and other contracts that can be missed by isolated unit tests.

3. **Hardware/robotics host-readiness checks.**
   Part 3 reports HAL/body configuration and checks CPU enumeration, monotonic high-resolution timing, temporary-file writing, installed RAM, and free disk space. These are real host checks; physical USB/serial/network transport, sensors, actuators, and estop paths remain future HAL-adapter checks.

4. **System-fitness assessment.**
   Part 4 currently runs a tiny live OpenAI/LLM smoke test when the optional integration is available. A successful call is reported as `PASS`. Missing or unusable OpenAI configuration is reported as `WARN` and does **not** fail the core CCA8 preflight.

---

## Running pytest directly

For a fast deterministic run without coverage:

    python -m pytest -q --no-cov

For a focused file:

    python -m pytest -q --no-cov tests\test_runner_component_registry.py

The repository-root working directory matters because tests import root-level CCA8 modules and read project configuration such as `pytest.ini` and `mypy.ini`.

---

## Footer format and exit code

The current footer uses explicit Part 1–4 denominators:

    [preflight] RESULT: PASS | PART 1: unit_tests=<passed>/<total> | coverage=<pct>% (≥30) | PART 2: probes=<passed>/<total> |
    [preflight] PART 3: hardware_robotics_checks = <passed>/<total> | PART 4: system_fitness_assessments = <pass> pass, <warning> warning(s), <fail> fail, <skip> skipped, <total> total |
    [preflight] elapsed_time (mm:ss) =<mm:ss>

The process returns zero only when all required unit-test, architecture-probe, and host/hardware checks pass and Part 4 has no blocking failures. Optional OpenAI warnings are visible but non-blocking.

---

## Artifacts

- JUnit XML: `.coverage/junit.xml`
- Coverage XML: `.coverage/coverage.xml`
- Coverage data: `.coverage/.coverage.preflight` when coverage is enabled

A lightweight startup check can be disabled with `CCA8_PREFLIGHT=off`; this affects only the startup-lite notice, not an explicit `--preflight` run.

---

## Troubleshooting

- If pytest is green but a Part 2 probe fails, suspect an architectural contract regression: import ownership, NOW tagging, attach semantics, public WorldGraph boundaries, compatibility aliases, or a whole-flow behavior that unit tests did not isolate.
- If Part 3 fails, inspect the reported CPU/timer/temp-file/RAM/disk item and the configurable thresholds `CCA8_MIN_RAM_GB` and `CCA8_MIN_DISK_GB`.
- If Part 4 reports an OpenAI warning, core CCA8 remains usable. Configure Menu 48 only when you intend to use live OpenAI features.
- Run preflight from the repository root so it can find `tests/`, project configuration, README assets, and all root-level modules.


# Logging



## Trace streams

CCA8 intentionally produces **three complementary trace streams**, plus optional state snapshots:

1) **`cca8_run.log`** — structured Python logging (best for warnings/errors and developer breadcrumbs).
2) **`terminal.txt`** — a verbatim terminal transcript (best for human “story” review and sharing runs).
3) **`cycle_log.jsonl`** — a per-cycle machine-parsable trace (best for analysis, plots, and regression tests).

In addition, `--autosave <file>.json` produces **state checkpoints** (not an execution trace).



### 1) `cca8_run.log` (structured Python logging)


What it is:
- Configured in `cca8_run.py` `main(...)` via `logging.basicConfig(...)`.
- Writes to **`cca8_run.log`** (UTF-8) and also echoes to the console.
- Intended for: exceptions/tracebacks, “this should never happen” conditions, and low-noise breadcrumbs.

How to change it:
- Edit `main(...)` in `cca8_run.py` where `logging.basicConfig(...)` is called (log level, filename, etc.).

Tail the log while you run (Windows PowerShell):
- `Get-Content .\cca8_run.log -Wait`



### 2) `terminal.txt` (terminal transcript)


What it is:
- A tee-style transcript of everything printed to stdout (and optionally stderr).
- Installed in `cca8_run.py` `main(...)` via `install_terminal_tee("terminal.txt", append=True, also_stderr=True)`.

Why it exists:
- It’s the easiest artifact to skim for “does the run tell a coherent story?”
- It’s also easy to share (no screenshots needed).

Operational notes:
- It appends by default. Delete the file (or change `append=False`) when you want a clean run transcript.
- If you want to disable it entirely, comment out the `install_terminal_tee(...)` call in `main(...)`.



### 3) `cycle_log.jsonl` (per-cycle JSONL trace)


What it is:
- One JSON object per closed-loop environment step (JSONL = JSON Lines).
- Designed for downstream parsing/plotting and for regression-style comparisons.

Where it is configured:
- In the interactive runner (`interactive_loop(...)`) via:
  - `ctx.cycle_json_enabled` (on/off)
  - `ctx.cycle_json_path` (file path; if None, file writing is disabled)
  - `ctx.cycle_json_max_records` (ring buffer size for `ctx.cycle_json_records`)

Operational notes:
- JSONL is append-only. Delete/rotate `cycle_log.jsonl` between experiments if you want clean traces.
- If you set `ctx.cycle_json_path = None`, the runner still keeps an in-memory ring buffer
  (`ctx.cycle_json_records`) up to `ctx.cycle_json_max_records` entries.

Record schema (v0; evolves over time):
- v: record schema/version (if present)
- episode_index / cycle_idx (or controller_steps) + env_meta (stage/zone/time, etc.)
- obs: predicates, cues, and (optional) nav_patches (Phase X)
- navpatch_matches: top-K candidates + chosen + commit/margin (Phase X)
- navpatch_priors: priors bundle + precision weights (Phase X)
- policy_fired / action_selected + drives (and other small scalars)
- (optional) efe_scores: per-policy (risk, ambiguity, preference, total) diagnostic bundle
- (optional) memory_ops summary: stored/deduped engram ids, pointer bids, etc.


### 4) Autosave snapshots (state checkpoints, not a log)


What it is:
- `--autosave session.json` overwrites a single snapshot file after completed actions.
- It is intended for “resume from here”, not for “analyze every step”.

Related menu features:
- Manual Save Session writes the same snapshot format as autosave.
- Reset (with autosave set) deletes the autosave file and reinitializes state.


### 5) Other debug artifacts


- Interactive **HTML graph export** (menu) provides a visual snapshot of the WorldGraph.
- `--preflight` prints to the console and also logs details to `cca8_run.log`.




### JSON (why we use it heavily)


CCA8 uses JSON (and JSONL) as a “lowest-friction” structured data representation across the project.

Why JSON works well for CCA8:

- It is supported by the Python standard library (`json`) with no extra dependencies.
- It is language-agnostic: the same artifacts are easy to read from Python, JS, Go, Rust, etc.
- It is diff-friendly and inspectable in plain text editors (great for debugging and code review).
- It fits our needs for:
  - autosave session snapshots (portable state checkpoints),
  - per-cycle traces (`cycle_log.jsonl`) for analysis/regression,
  - metadata dictionaries on nodes/edges/engrams (exportable without custom serializers).

Why JSONL (JSON Lines) is used for traces:

- One record per line enables streaming + append-only logging.
- You can process huge runs without loading the full file into memory.
- A partially-written file is still usable (everything up to the last complete line parses).

We intentionally avoid Python-specific formats (e.g., pickle) for saved artifacts because portability and inspectability matter more than raw speed at the time of writing.  However, Python's Pickle is a binary-format and can be many times faster than using JSON, so it may be used in some areas of future versions of the CCA8 where data structures have grown exponentially. Note that Python Pickle is not language-agnostic and is a binary format more difficult for human inspection.



### Tiny “same data” examples across common formats

Example case: one closed-loop step summary with an env step, a fired policy, a zone, and two predicates.

Consider the representation in different popular formats:



JSON (JavaScript Object Notation)(object):

{"env_step": 5, "policy_fired": "policy:stand_up", "zone": "unsafe_cliff_near",
 "predicates": ["posture:standing", "hazard:cliff:near"]}


JSONL/ NDJSON  (one JSON object per line):

{"env_step":5,"policy_fired":"policy:stand_up","zone":"unsafe_cliff_near","predicates":["posture:standing","hazard:cliff:near"]}



TOML (Tom's Obvious Minimal Language) (useful for settings, similar to INI file syntax):

env_step = 5
policy_fired = "policy:stand_up"
zone = "unsafe_cliff_near"
predicates = ["posture:standing", "hazard:cliff:near"]



INI (initialization format; legacy Windows/system settings; no native lists):

[status]
env_step = 5
policy_fired = policy:stand_up
zone = unsafe_cliff_near
predicates = posture:standing; hazard:cliff:near



TOON (Token-Oriented Object Notation) (useful to save tokens for usage with LLMs):

env_step: 5
policy_fired: policy:stand_up
zone: unsafe_cliff_near
predicates[2]: posture:standing,hazard:cliff:near



YAML (YAML Ain't Markup Language/ Yet Another Markup Language) (human-friendly, indentation-significant):

env_step: 5
policy_fired: policy:stand_up
zone: unsafe_cliff_near
predicates: [posture:standing, hazard:cliff:near]


XML (eXtensible Markup Language) (tag-based, verbose but explicit and hierarchical):

<step env_step="5" policy_fired="policy:stand_up" zone="unsafe_cliff_near">
  <pred>posture:standing</pred><pred>hazard:cliff:near</pred>
</step>



OR another possible way of expressing in XML:


<status>
  <env_step>5</env_step>
  <policy_fired>policy:stand_up</policy_fired>
  <zone>unsafe_cliff_near</zone>
  <predicates>
    <item>posture:standing</item>
    <item>hazard:cliff:near</item>
  </predicates>
</status>




CSV (Comma-Separated Values) (text-based, flat structure, can inspect in spreadsheets):

env_step,policy_fired,zone,predicates
5,policy:stand_up,unsafe_cliff_near,"posture:standing;hazard:cliff:near"



PICKLE (not an acroynym but refers to preserving objects) (Python-specific binary serialization, .pkl file):


e.g., write the same example case as a Pickle file:

import pickle
obj = {
    "env_step": 5,
    "policy_fired": "policy:stand_up",
    "zone": "unsafe_cliff_near",
    "predicates": ["posture:standing", "hazard:cliff:near"] }
with open("step.pkl", "wb") as f:
    pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


e.g., write the same example as a Pickle in-memory structre and then display as Base64 text:

import base64
import pickle
obj = {
    "env_step": 5,
    "policy_fired": "policy:stand_up",
    "zone": "unsafe_cliff_near",
    "predicates": ["posture:standing", "hazard:cliff:near"]}
b = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
print(base64.b64encode(b).decode("ascii"))

Base-64 output:
gAWVhgAAAAAAAAB9lCiMCGVudl9zdGVwlEsFjAxwb2xpY3lfZmlyZWSUjA9wb2xpY3k6c3RhbmRfdXCUjAR6b25llIwRdW5zYWZlX2NsaWZmX25lYXKUjApwcmVkaWNhdGVzlF2UKIwQcG9zdHVyZTpzdGFuZGluZ5SMEWhhemFyZDpjbGlmZjpuZWFylGV1Lg==


Not considered in initial software development of the CCA8 but might be considered in aspects of future implementations:

Protobuf (Protocol Buffers) (Google-developed format; faster and smaller than JSON):

-actually need pre-defined schema
- smaller and faster than JSON but may not be smaller or faster than Pickle
-however, more of a transferable format than Pickle



Msgpack (MessagePack) (binary-like JSON essentially):

-not faster or smaller than Pickle but much better for sharing data with others




Parquet (Apache; instead of storing rows in CSV this stores as columns):

-industry standard for Apache Spark and data science
-less usueful for non-tabular data with arbitrary nested state graphs




HDF5 (Hierarchical Data Format) (useful for billions of entries):

- useful for very large numeric arrays/ tensors with chunking and compression
- as the CCA8 scales in data generation size, to avoid the need to re-write future versions
        of the CCA8 into Rust or C++ code, can combine Python with
        HDF5 data format and use Python high-level vectorized libraries that have C/C++
        or CUDA cores -- get near-native performance while still retaining the Python 'glue code'
        (with the option of coding custom some low-level algorithms in C/CUDA where needed)
- JSON slowest < Pickle and MessagePack fast < HDF5 ultrafast speeds
- also much lower memory usage since lazy loading
- can also be the smallest file size since supports GZIP or LZF compression at the 'chunk' level
- can attach metadata directly to the data in this format


import h5py
import numpy as np
with h5py.File("data.h5", "w") as f:
    f.attrs["env_step"] = 5
    f.attrs["policy_fired"] = "policy:stand_up"
    predicates = np.array(["posture:standing", "hazard:cliff:near"], dtype='S')
    f.create_dataset("predicates", data=predicates)
with h5py.File("data.h5", "r") as f:
    print(f.attrs["env_step"])



# Traceability (requirements to code)

CCA8 is evolving quickly, so traceability has to be **lightweight** to stay alive.

The goal of this section is *not* heavyweight compliance — it’s to help a maintainer answer:

- “Where in the code is requirement X implemented?”
- “If I change this behavior, what else should I re-test?”


---

## Traceability-lite table

Keep requirement IDs short and stable. A simple convention that works well:

- `REQ-<SUBSYS>-<NNN>` for requirements / behavioral contracts  
- `ADR-<NNN>` for “why we chose this design” decisions (put the full writeup under `docs/adr/` if it grows)

Example mapping (expand as the codebase grows):

| Requirement | What it means (short) | Where it lives (examples) |
|---|---|---|
| REQ-PLAN-01 | Planner finds a path NOW → goal predicate | `WorldGraph.plan_to_predicate(...)`, planner helpers, pretty-path display |
| REQ-WG-01 | WorldGraph anchors are valid and NOW is consistent | WorldGraph anchor/tag utilities; preflight probes validating NOW/LATEST invariants |
| REQ-PERS-01 | Snapshot load/save is atomic and id-safe | snapshot load/save helpers; `WorldGraph.from_dict(...)` advances `next_id` safely |
| REQ-POL-01 | Policies are gated + run in priority order | `ActionCenter` policy ordering + `trigger()` guards + provenance in `meta` |
| REQ-OBS-01 | Agent never reads EnvState directly (only EnvObservation) | `HybridEnvironment` + `PerceptionAdapter` boundary; runner wiring |
| REQ-TRACE-01 | Runs produce human + machine traces | `terminal.txt`, `cca8_run.log`, `cycle_log.jsonl` pipeline (see Logging) |

Guidelines:
- Put the REQ id in a short comment near the relevant function/class (easy to grep).
- When a behavioral contract changes, update:
  1) the REQ row here, and  
  2) at least one **probe** or **unit test** that asserts the new behavior.

Note: This is intentionally “lite”. If requirements are in flux, it’s better to keep this small than to let it rot.

---

## Debugging Tips (traceback, pdb, VS Code)

### Fast triage checklist (before opening a debugger)

1) **Reproduce from a snapshot**  
   If you can, run from a minimal `--load` file and avoid “fresh randomness”.

2) **Check the Snapshot menu output first**  
   Confirm NOW/LATEST, anchor tags, and that the goal predicate actually exists somewhere in the graph.

3) **Use the right artifact for the right question**
   - `terminal.txt`: “What story happened?” (best first skim)
   - `cca8_run.log`: warnings/errors/tracebacks (developer breadcrumbs)
   - `cycle_log.jsonl`: machine-parseable per-cycle record (best for regressions)
   - autosave snapshots: “resume exactly here” checkpoints

### Debugger basics

- **traceback:** in `except Exception:` add `traceback.print_exc()` to print a full stack (useful when a loader/snapshot fails).
- **pdb:** drop `breakpoint()` in code or run:
   bash
  python -m pdb cca8_run.py --load session.json --no-intro
   
  Handy commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p`/`pp` (print), `b` (breakpoint), `where`.
- **VS Code debugger:** create `.vscode/launch.json` with args, set breakpoints, press F5. Great for multi-file stepping (planner ↔ controller ↔ env).

Common breakpoint targets:
- planner: `plan_to_predicate(...)`
- controller: `ActionCenter.step(...)` (or equivalent)
- policies: `trigger()` and `execute()/act()`
- snapshot I/O: load/save functions if JSON structure changes

### Playbook: “No path found”

1. **Verify the predicate exists** (Snapshot shows a binding with that `pred:*`).
2. **Check connectivity** (ensure there’s a forward chain of edges from NOW to that binding).
3. **Look for reversed edges** (common error: you added `B→A` instead of `A→B`).
4. **Confirm the goal token** (exact `pred:<token>` string; avoid typos/extra spaces).
5. **Inspect layers** (the interactive graph export usually makes the missing hop obvious).

### Playbook: “Duplicate edges / graph clutter”

A common pitfall is duplicate edges when both auto‑attach and a manual connect create the same relation.

- The UI warns when you try to add an identical `(src, label, dst)` edge.
- In a debugger, inspect the `edges[]` list on a binding directly and remove duplicates carefully
  (or edit a snapshot JSON and reload).

### Playbook: “Policy keeps repeating an action”

1. Confirm the policy’s `trigger()` checks for an already-satisfied predicate (e.g., don’t “stand up” if already `pred:posture:standing`).
2. Verify policy order (a higher-priority policy shouldn’t accidentally insert the same predicate as a side effect).
3. Inspect recent bindings’ `meta.policy` to see which policy created duplicates.

---

### Q&A to help you learn this section

Q: Quick way to print a stack?  
A: `traceback.print_exc()` inside an exception handler.

Q: Start the debugger from the CLI?  
A: `python -m pdb cca8_run.py --load ...`

Q: Persistent breakpoint in code?  
A: `breakpoint()` (Python 3.7+).

Q: What’s the best “bug report bundle”?  
A: A minimal snapshot (`--load` file), plus `terminal.txt` and the relevant excerpt from `cca8_run.log`. If it’s a regression across runs, include the `cycle_log.jsonl` slice.



# REFERENCES AND NOTES

# References



Schneider, H., Navigation Map-Based Artificial Intelligence -- [Navigation Map-Based Artificial Intelligence](https://www.mdpi.com/2673-2688/3/2/26)

Schneider, H., The Emergence of Enhanced Intelligence in a Brain-Inspired Cognitive Architecture -- [Frontiers | The emergence of enhanced intelligence in a brain-inspired cognitive architecture](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2024.1367712/full)

Minsky, M. (1986), *The Society of Mind*. Simon & Schuster.

Goertzel, B. (2017), Cognitive Synergy between General Intelligence Components -- [[1703.04361] Cognitive Synergy between General Intelligence Components](https://arxiv.org/abs/1703.04361)


Tresp, V. et al., Tensor Brain -- [[2109.13392] The Tensor Brain: A Unified Theory of Perception, Memory and Semantic Decoding](https://arxiv.org/abs/2109.13392)






# Developer and Maintainer Notes

----
