# P16-1R-B — Internal handoff, external execution and input admission

## 1. Delivery and entry checkpoint

**Scope:** P16-1R-B only, under Planning v16 §28 and §36.1 (pages 24–25 and 33–34).
This is the functional counterpart of the accepted P16-1R-A explanation change.
It does not implement P16-1E-B/C, persistent Righting, new body physics, Emotion,
learning, general asynchronous execution or default-runtime promotion.

**Entry commit:** `6ef4fd9f25568eb098139582b4b74c323c5da193` — `updates to cog cycle`.
The supplied archive has clean `main`; its recorded `origin/main` resolves to the
same commit. No network fetch or live remote inspection was performed. Howard
reported green local validation and preflight after the parent-menu v09.3 wording
correction. That correction and the committed P16-1R-A work are preserved.

Source archive: `workspace(20260914-003654).zip`.
SHA-256: `053d8fb36ac3796c23f6fe964e2ea7a27faec66ee0f95e60c09d017b01cf6216`.

Planning source: `CCA8_Project_Planning_v16(2).docx`.
SHA-256: `042acfbf93aa27c840240e70d59ecc4c973414eb6c1b70ba6f5ee3ca273ea5c3`.

The original extraction stayed clean. Changes and tests used a separate clone.
Architecture, Planner, To-Do documents, the uploaded archive and Howard's local
checkout were not modified by this preparation. Planner v16's historical dirty
snapshot description is intentionally left alone, as requested.

**Delivery status:** review candidate, not a certified complete local GO.
Container tests support the results below, but pylint/mypy could not run and two
pre-existing missing-Pyvis failures prevent a green container full-suite/preflight
result. Local validation and a short success/adverse trace review remain required.

## 2. What now happens

```text
INSIDE THE CORE
    current input -> A/B/C -> D -> PNM and protected BodyMap checks
    E: immutable permitted commitment
    E: accept one internal handoff request (not a world call)
    F: existing zero-durable-learning slot
    scheduler maintenance
    record internal cognitive-cycle closure
    release the accepted receipt for outer consumption

OUTSIDE THE CLOSED CORE
    consume the ready receipt once
    call the private external world once (None also advances time)
    record returned world-step metadata
    admit/detach the returned observation once
    buffer it for the next eligible cognitive cycle
```

The core no longer accepts an action-producing `phase_e_hook`. A concrete bounded
handoff service replaces it. The outer runner, not the cognitive core, performs
world evolution. Returning reward/done remain external reporting/control values;
raw `EnvObservation` never becomes a cognitive-owner input. Existing positive
whitelisting and the optional read-only support-observation schema remain intact.

This is a serialized simulator protocol, not a model in which a real body must
wait for a global brain clock. Real asynchronous actuation and confirmed hardware
stopping remain outside this slice. The protected-stop seam below explicitly
reports that it has not confirmed a physical actuator stop.

## 3. Failure contract and bounded state transitions

The new service owns one immutable receipt at a time, not a general queue. Its
current snapshot is replaced on each transition. Old snapshots remain history
and cannot authorize another use. Receipt object identity plus owner generation
reject copied, foreign, cross-session and stale-reset receipts, even where their
printed generation/action identifiers happen to coincide.

| Situation | Handoff / execution result | Input and continuation policy |
|---|---|---|
| Normal E acceptance | `accepted`; execution `not_attempted` | F and internal closure must finish first. |
| Successful internal close | `ready`; still `not_attempted` | Outer runner may consume this exact receipt. |
| Outer consumption | `consumed` before returning the permitted task or None | The receipt cannot become ready again. |
| World call is about to start | Execution is conservatively `unknown` | An exception does not authorize a retry. |
| World call returns normally | Execution `returned`, not proof of bodily success | Separate admission and buffering follow. |
| Disabled handoff boundary | `refused`; no world call | Stop and require reset; no substitute action. |
| F, scheduler or close/report failure after acceptance | Unconsumed request `cancelled`; no world call | Retain commitment, revoke live body permission and mark only that known-unexecuted claim not applied. |
| Exception during possible world execution | Receipt remains consumed; execution `unknown` | Revoke future permission, clear pending input, require reset; do not call the world again automatically. |
| World returns, but input is lost/malformed or admission/reporting fails | Execution remains `returned` | No fabricated fresh input and no retry of the physical request; stop until reset. |
| Duplicate/copy/stale receipt use | Rejected before another side effect | No replay of the original movement or null time step. |
| Protected stop before the world call | Revoke further permission; unconsumed receipt can be cancelled | Withhold the world step and require reset. |
| Protected stop after possible/returned execution | Preserve original commitment and execution status | Revoke further permission, not past motion; `physical_stop_confirmed=False`. |

`EnvelopeStatusV1.CANCELLED` describes withdrawal of continuing permission. After
possible execution it must not be read as proof that nothing moved. Known
nonexecution can close the matching PNM as NOT_APPLIED. Unknown or returned
execution does not become either success or an invented predictive failure.
A failed later cycle cannot mark the previous cycle's executed prediction not
applied simply because it is still the last stored commitment.

The runner removes its old pending input before starting a pass. Any failure after
processing begins leaves no reusable pending packet and latches reset-required.
An expected next observation number is displayed separately from actual packet
availability. A second public step after failure raises before another world call.
Reset creates a fresh session generation; it is not an automatic retry or a claim
that physical history has been undone.

The bridge separately protects its pending raw result and admission receipt:
no outstanding-result overwrite, repeated admission, reentrant world/reset call,
or failed-reset reuse. A malformed *whole* observation stops the boundary.
Rejection of an invalid optional `posture_support_v1` payload retains the existing
read-only seam's behavior; it is not silently upgraded to a new behavioral policy.

The exactly-once claim is deliberately narrow: at most one issued world/time
advance per valid runner request in this process, with no automatic reissue after
uncertainty. It is not a network-delivery or actuator-level guarantee. After a
process crash there is no new persistent replay protocol.

## 4. Production changes and API compatibility

| File | Version | Bounded change |
|---|---|---|
| `nca8_handoff.py` | 0.1.0, new | Typed immutable dispatch/receipt and single-slot internal acceptance, release, consumption and cancellation. A boundary service, not a new brain module. |
| `nca8_adapters.py` | 0.4.0 | Separate `advance_task_action()` from `admit_observation()`; preserve private combined outer compatibility helper. |
| `nca8_body.py` | 0.3.0 | Revoke the current named action permission without changing historical commitments or body evidence. |
| `nca8_runtime.py` | 0.6.0 | Remove world callback, close core first, consume externally, admit/buffer later; bounded failure/protection state. |
| `nca8_trace.py` | 0.8.0 | Explain actual handoff/world/input events and distinguish current protocol from saved historical callback traces. |
| `nca8_menu.py` | 0.7.4 | Describe actual order and show stopped/input-availability status without changing menu routing. |
| `cca8_run.py` | 0.30.9 | Version and component-registry entry only; component report now lists 59 entries. |

`Nca8PhaseEDispatchV1` moves to the cohesive handoff file and is re-exported from
`nca8_runtime` under its original name. Its fields and diagnostic dictionary are
retained. `Nca8CognitiveRuntimeCycleV1` additionally returns a ready handoff receipt.
A caller using the low-level core must explicitly consume or cancel that receipt
before another core pass. Core-only tests can consume without simulating a world,
but that disposal is not physical-execution evidence. Use the session/runner API
for ordinary closed-loop operation and failure handling.

The successful public `Nca8CognitiveCycleResultV1.as_dict()` remains unchanged in
meaning. Normal session/menu run and reset methods remain available. Session status
adds input availability, reset-required, execution and handoff fields. Attempting
to access `pending_observation` when no packet exists now raises rather than
returning stale evidence. `phase_e_hook` is intentionally removed: preserving that
world-producing callback would defeat the requested separation.

`stop_for_protection(reason=...)` is an explicit lower-boundary stop seam, not an
automatic hazard detector, a new task selector, or a detailed motor controller.
No general Ready/offloading/resource system is introduced.

Unchanged production includes `nca8_contracts.py`, `nca8_executive.py`, `nca8_maps.py`,
`nca8_prediction.py`, `nca8_primitives.py`, `nca8_scheduler.py`, `nca8_sensory.py`,
`cca8_env.py` and `cca8_cli.py`. The source-linked WNM, coarse A0 StandUp policy,
PNM endpoint comparison, existing support schema/default-disabled read-only status,
legacy default/isolation, dependency files and validation configuration are retained.

## 5. Trace changes and regression evidence

The first standard Gate-A tail now contains actual records in this order:

| Record | Meaning |
|---|---|
| #20 | Commit Action_1:STAND_UP. |
| #21 | Internal handoff accepted during E; no world advance yet. |
| #22 | Existing Phase-F zero-durable-learning report. |
| #23 | Scheduler maintenance. |
| #24 | Internal CognitiveCycle_1 closure. |
| #25 | Outer external world call returned after one advance. |
| #26 | Observation_2 admitted/detached at the input boundary. |
| #27 | Observation_2 buffered for CognitiveCycle_2. |

Gate A still takes **6 cognitive cycles and 5 StandUp commands**, finishing with
later standing/stable evidence and success for `application:stand_up:5`. Cycle 6
commits NO_ACTION, advances the world with None and buffers Observation_7. This is
not a sixth StandUp command. The fresh menu demonstration remains generation 1;
the API's default extra reset still produces its separately documented generation.

The new trace contains **158 events rather than 146**: two additional real boundary
records per cycle. Record numbering changes honestly; no synthetic #21a/#21b is
inserted into an old trace. New boundary events identify `p16_1r_b_v1`. The canonical
JSON serializer remains, but reordered and added events deliberately change its
bytes. The separate unnumbered reference-order note is explanatory, not an event.

Three complementary controls are retained:

- `tests/fixtures/nca8_trace_domains_baseline.json` remains byte-for-byte unchanged.
  Five six-cycle seed-19 cases retain their original public cycle-result and next
  observation fingerprints: standard, Attention off, Navigation off, body veto,
  and support-read-only. Original status values remain except trace count; new
  status fields are explicitly checked separately.
- `tests/fixtures/nca8_gate_a_pre_1r_b.json` records the actual 146-event pre-patch
  Gate A captured from the clean 6ef4fd9 source. Historical renderer tests keep
  their old mixed-boundary assertions against that fixture.
- `tests/fixtures/nca8_boundary_protocol_v1.json` independently versions the five
  new canonical trace fingerprints and expanded status. It does not replace the
  original behavioral baseline with fingerprints of modified behavior.

Existing timing/trace tests were updated where they asserted the old callback order
or record count. Their new assertions test handoff before F and close before world,
not merely the presence of a word. Historical callback-rendering coverage remains
in addition to new live-protocol tests. Import-firewall scope adds the new file
without permitting it any legacy cognitive dependency.

Actual manual evidence was generated from the candidate, not invented diagrams:
`CCA8_P16_1R_B_Trace_Examples.txt` contains the success summary and first-cycle tail,
a null cycle, and a controlled unknown-execution case. In that fault test the world
call occurs and an OSError is then raised to simulate loss of its response. The
session reports unknown execution, no pending input, preserved commitment and
reset-required. A second step is rejected; the world-call counter remains one.
The file labels the fault as an injected transport test, not spontaneous goat behavior.

A full host-menu smoke also ran through Watch -> NCA8 -> fresh Gate A -> guided
trace -> return -> quit. It reported 6/5/158 and completed normally. No lengthy
record-by-record review is required here; the agreed deeper review remains after
1E-C, before 1F.

## 6. Validation performed in the separate container

Interpreter: Python 3.13.5. No interpreter or repository dependency migration.

| Check | Baseline 6ef4fd9 | Final candidate |
|---|---|---|
| New boundary test file | Not present | 63 passed |
| `pytest --no-cov -q tests -k nca8` | 344 passed; 1,048 deselected | 407 passed; 1,048 deselected |
| Full pytest | 1,390 passed; 2 failed | 1,453 passed; 2 failed |
| Gate A | 6 cycles; 5 commands; 146 events | 6 cycles; 5 commands; 158 events |
| Compile changed/new source and boundary tests | — | Passed |
| `--about` | Existing registered components | Passed; 59 entries |
| Preflight software probes | — | 101/101 |
| Preflight hardware checks | — | 5/5 in this container, HAL off |
| Full preflight | — | **FAIL**, unit tests 1,453/1,455 |
| Pylint / mypy | Unavailable | Could not execute: modules unavailable |
| Patch whitespace check | Clean baseline | Passed |

Both full-suite failures are unchanged missing-Pyvis failures:
`tests/test_world_graph_pyvis_export.py::test_to_pyvis_html_writes_file` and
`tests/test_world_graph_pyvis_physics_true.py::test_to_pyvis_html_physics_true`.
Preflight fails on those same unit tests. Its optional external-model smoke reports
no API key; that warning is separate from the two failures. Package installation
could not resolve PyPI because DNS was unavailable. No tests were skipped, no
validation limits weakened and no new suppressions introduced to hide a failure.

The 63 new cases cover real order/core isolation, single consumption, null and
veto paths, refusal, F/scheduler/logging failures, wrong action/PNM/body links,
foreign/copied/stale receipts, missing/malformed input, admission failure,
uncertain execution, protected stop before and after possible execution, reset,
reentrancy, KeyboardInterrupt/SystemExit cleanup, small diagnostic capacities,
partial/historical rendering and stopped-menu reporting. Controlled boundary
failure uses test injection, not new runtime action-selection policy.

Patch packaging was checked on a fresh separate 6ef4fd9 checkout: strict apply
check and application, exact comparison of all delivered files with the tested
candidate, the new boundary tests and focused NCA8 selection, then reverse-check
and reversal restoring a clean checkout. No commit was made in Howard's repository.

## 7. Delivered file manifest

- `README.md`
- `cca8_run.py`
- `docs/P16_1R_B_REVIEW.md`
- `nca8_adapters.py`
- `nca8_body.py`
- `nca8_handoff.py`
- `nca8_menu.py`
- `nca8_runtime.py`
- `nca8_trace.py`
- `tests/fixtures/nca8_boundary_protocol_v1.json`
- `tests/fixtures/nca8_gate_a_pre_1r_b.json`
- `tests/test_nca8_boundary_separation.py`
- `tests/test_nca8_import_firewall.py`
- `tests/test_nca8_logical_availability.py`
- `tests/test_nca8_menu_routing.py`
- `tests/test_nca8_null_cycle.py`
- `tests/test_nca8_prediction_order.py`
- `tests/test_nca8_session_isolation.py`
- `tests/test_nca8_support_observation.py`
- `tests/test_nca8_trace_c1c2.py`
- `tests/test_nca8_trace_domains.py`
- `tests/test_nca8_trace_flow.py`
- `tests/test_nca8_trace_parts_first.py`

The patch contains 23 paths: seven production files (one new), eleven existing
test files, one new test file, two new fixtures, README and this review record.
The previous `docs/P16_1R_A_REVIEW.md` and original semantic baseline fixture remain
unchanged. Generated render images, incidental caches, test logs and the source
archive are not added to Git by this patch.

## 8. Windows CMD application

Save `CCA8_P16_1R_B_boundary_separation.patch` in Downloads. Confirm the unchanged
starting checkout; stop if HEAD or local changes differ unexpectedly:

```bat
cd /d C:\Users\howar\workspace
git status -s
git rev-parse HEAD
```

Expected HEAD is `6ef4fd9f25568eb098139582b4b74c323c5da193`; status should be empty.
The first command below checks only; the second applies only if that check passes:

```bat
git apply --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1R_B_boundary_separation.patch" && git apply --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1R_B_boundary_separation.patch"
git diff --check
git diff --stat
git status -s --untracked-files=all
```

`git diff --stat` initially lists the 18 modified tracked files. The five new paths
appear separately as untracked until staged. No second patch or manual source
insertion is required.

## 9. Required local validation and brief manual review

Use the same interpreter/environment that passed the entry wall. Stop and inspect
a failing command instead of proceeding to a commit. Include the new handoff file
and modified host runner in lint/type scope:

```bat
python --version
python -m py_compile nca8_handoff.py nca8_adapters.py nca8_body.py nca8_runtime.py nca8_trace.py nca8_menu.py cca8_run.py
python -m pytest --no-cov -q tests\test_nca8_boundary_separation.py
python -m pytest --no-cov -q tests -k nca8

python -m pylint nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py cca8_run.py

python -m mypy nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py cca8_run.py

python -m pytest --no-cov -q
python cca8_run.py --about
python cca8_run.py --preflight
git diff --check
```

Then run `python cca8_run.py`, enter Watch -> NCA8, select 5 and then 4. Confirm
6 cycles, 5 StandUp commands, final standing/stable, and the #20–#27 order above.
The diagram should distinguish internal close from external-world return and
input admission. The last cycle should be a null output, not another StandUp.
Review the adverse/null examples alongside the passing fault tests; these are
quick boundary checks, not another several-hour conceptual walkthrough.

Acceptance requires the complete local wall plus this limited manual review.
Container Pyvis failures do not excuse corresponding failures locally. A green
pytest run alone does not certify pylint, mypy, preflight or hardware behavior.
Record the actual results and accepted commit in the coding checkpoint.

## 10. Commit and rollback

Only after local validation and manual acceptance, stage exactly the delivered
paths rather than all workspace changes:

```bat
git add -- README.md cca8_run.py docs/P16_1R_B_REVIEW.md ^
 nca8_adapters.py nca8_body.py nca8_handoff.py ^
 nca8_menu.py nca8_runtime.py nca8_trace.py ^
 tests/fixtures/nca8_boundary_protocol_v1.json tests/fixtures/nca8_gate_a_pre_1r_b.json tests/test_nca8_boundary_separation.py ^
 tests/test_nca8_import_firewall.py tests/test_nca8_logical_availability.py tests/test_nca8_menu_routing.py ^
 tests/test_nca8_null_cycle.py tests/test_nca8_prediction_order.py tests/test_nca8_session_isolation.py ^
 tests/test_nca8_support_observation.py tests/test_nca8_trace_c1c2.py tests/test_nca8_trace_domains.py ^
 tests/test_nca8_trace_flow.py tests/test_nca8_trace_parts_first.py
git diff --cached --check
git diff --cached --stat
git status -s --untracked-files=all
```

Inspect that staged scope before committing:

```bat
git commit -m "P16-1R-B separate cognitive handoff from world execution"
git status -s
git log --oneline -3
```

Do not commit incidental logs or other unrelated changes. Sharing the new commit
SHA and a fresh archive establishes the entry to P16-1E-B; do not apply a new slice
to this older 6ef4fd9 baseline once 1R-B has been committed.

For an uncommitted, **unstaged** patch whose delivered files have not acquired
further changes, reverse-check and reverse it:

```bat
git apply --reverse --check "%USERPROFILE%\Downloads\CCA8_P16_1R_B_boundary_separation.patch" && git apply --reverse "%USERPROFILE%\Downloads\CCA8_P16_1R_B_boundary_separation.patch"
git status -s --untracked-files=all
```

If the patch is staged, or later work touches these files, stop and inspect rather
than force reversal. After a dedicated commit, use a reviewed `git revert` of its
actual SHA rather than destructive reset/clean. Source rollback cannot reverse
an already executed body/world action. Preserve any unknown-execution history.

**Next slice only after accepted 1R-B:** P16-1E-B, the small action-responsive
support-evidence provider. Existing P15-1E-A is retained, not rebuilt. No A99 or
learning gate is claimed complete by this boundary change.
