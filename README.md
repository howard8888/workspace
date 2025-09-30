# CCA8 — Mammalian Brain Simulation
**Column‑Primary Facts, Graph Index** (ADR‑001/002)

> CCA8 models a cortex‑first memory architecture: **columns own declarative engrams** (facts/scenes), while a global **world graph** keeps the **episode timeline** (bindings + edges + anchors) and **indexes** those engrams for planning and recall.

---

## Contents (modules)
```
.
├─ run_world_intro.py        # Entry point with INTRODUCTION, profiles, and interactive menu
├─ run_world_patched.py      # Minimal entry point (no intro/profile flow)
├─ world_graph_patched.py    # Episode timeline + index (bindings, edges, predicates, engram pointers)
├─ column01_patched.py       # A single cortical column's memory + provider (engram store)
├─ cca8_features.py          # Typed engram payloads (FeaturePayload protocol, TensorPayload, FactMeta)
└─ temporal_context.py       # 128‑D temporal context (unit vector with drift and boundary jumps)
```

**Recommended entry point:** `run_world_intro.py`

- Menu option **0** re‑shows the INTRODUCTION and lets you pick an **evolutionary profile** (Mountain Goat, Chimpanzee, Human, Super‑Human).
- Profiles adjust temporal drift/jump and a `winners_k` hint for sparse ensemble winners.
- A **HAL** (embodiment) toggle exists as a **stub** only.

---

## Key concepts (quick glossary)

- **Binding** – a single **episode snapshot** in the world graph. Carries small `meta` (incl. a temporal context vector) and optional **engrams** pointers.
- **Edge** – a directed **transition** between bindings with a free‑text `label`.
- **Anchor** – a named binding that acts as a fixed reference; e.g., `NOW`.
- **Predicate tag** – a label of the form `pred:<name>` attached to a binding for planning/queries.
- **Engram pointer** – a reference from a binding to one or more column memories, e.g.:
  ```json
  { "column01": { "id": "<engram_id>", "act": 0.82 } }
  ```
- **ColumnMemory** – a per‑column RAM store for declarative **payloads** (typed objects like tensors/graphs) + tiny human‑readable `meta`.
- **TemporalContext (128‑D)** – unit‑norm vector that **drifts** each tick and **jumps** at event boundaries; stored in each binding’s `meta`.

**Invariants**
- **Append‑only** episode model: past bindings are never mutated; new states are appended.
- Predicates are **tags**, not payloads. The payload lives in columns; the graph **indexes** them.

---

## Quickstart

### Requirements
- Python **3.11+**
- No third‑party dependencies (stdlib only).

### Run (interactive)
```bash
python run_world_intro.py
```
Flags:
- `--no-intro` (skip the INTRODUCTION screen)
- `--about`, `-V/--version`
- `--period CHILDHOOD`, `--year 1974` (coarse tags saved on new bindings)
- `--hal`, `--body HSFSD` (HAL/embodiment stub)

### Minimal runner
```bash
python run_world_patched.py
```

---

## Typical workflow (interactive menu)

1) **Add predicate**  
   Creates a column engram and a new predicate‑tagged binding.  
   - **Attach = now** → add edge `NOW -> new_binding`  
   - **Attach = latest** → edge `latest -> new_binding`  
   - **Attach = none** → no edge initially

   Binding `meta` includes the current **TemporalContext** vector (and optional `period/year/profile`).

2) **Connect bindings**  
   Manually add edges to represent transitions or relations.

3) **Plan from NOW → predicate**  
   Breadth‑first search over edges to find a path to a binding with `pred:<name>`.

4) **Resolve engrams**  
   For a given binding, dereference its engram pointers via registered column providers (e.g., `column01.mem`) to retrieve the **payload + meta**.

---

## Architecture overview

```
Columns (cortex, declarative engrams)        World Graph (episode + index)
┌───────────────────────────────┐            ┌────────────────────────────────────────┐
│ column01_patched.ColumnMemory │◄──────────►│ bindings (snapshots, meta{context,...})│
│  engram: payload + tiny meta  │   pointer  │ edges (transitions)                    │
└───────────────────────────────┘            │ tags: "pred:<name>", anchors ("NOW")   │
                                             │ engrams:{column->id/act}               │
                                             └────────────────────────────────────────┘
                                                       ↑ deref via provider registry
```

- Columns store **payloads** (typed objects, e.g., `TensorPayload`).
- The graph stores **when/what** happened and **how** states connect, plus **pointers** back to column engrams.
- An optional future **Indexer** (hippocampus‑like) will bind item/place/context for rapid reinstatement.

---

## Evolutionary profiles (defaults)

| Profile        | Context drift (σ) | Boundary jump | `winners_k` |
|----------------|-------------------|---------------|-------------|
| Mountain Goat  | 0.015             | 0.20          | 2           |
| Chimpanzee     | 0.020             | 0.25          | 3           |
| Human          | 0.020             | 0.25          | 3           |
| Super‑Human    | 0.015             | 0.20          | 4           |

*(Edit in `run_world_intro.py` → `apply_evo_profile`.)*

---

## Developer notes

- **Typed payloads, not JSON.**  
  Engram content implements `FeaturePayload` (see `cca8_features.py`).  
  Start with `TensorPayload`; add sparse/graph payloads later without changing callers.

- **Provider registry.**  
  `world_graph_patched.WorldGraph.register_column_provider("column01", column01_patched.mem)`  
  lets the graph **resolve** pointers via `resolve_fact(binding_id, name)`.

- **Temporal context.**  
  `TemporalContext(dim=128)` supplies the vector stored in `meta["context"]`.  
  Use `.step()` per tick; `.boundary()` on event boundaries.

- **Append‑only** episode store.  
  All new information is recorded as **new bindings + edges**; existing ones are not rewritten.

---

## Roadmap (near‑term)
- **Indexer stub** (hippocampus‑like): fast binding and cue‑based reinstatement.
- **Persistence**: write‑ahead log for graph; per‑column snapshots (e.g., `.npy`/Zarr/Arrow).
- **Multi‑column**: add more columns and record multiple engrams per binding.
- **Action selection**: basal‑ganglia‑like near‑WTA for motor decisions.
- **Headless CLI**: subcommands for non‑interactive scripts/tests.

---

## Architecture Decision Records
- **ADR‑001**: Memory Architecture & Timeline (columns hold declarative payloads; world graph is episode/index).  
- **ADR‑002**: Column payloads (typed FeaturePayload) and 128‑D TemporalContext defaults; sparse ensemble winners.

*(Store ADRs in `docs/adr/` or keep them in your ChatGPT project canvas and mirror here when finalized.)*

---

## License
© 2025 Howard Schneider. All rights reserved (placeholder).  
Adjust license terms as needed.
