# P16-1R-A: domain-aware trace — implementation candidate

Date: 13 September 2026
Scientific target: Architecture v09.9
Planning scope: Planning v16 §§28, 35, 36.1, 59 and 66; Appendix G.3
Status: review candidate; local P16-0 and P16-1R-A GO are not certified by this report.

## 1. Entry and authority

Howard requested the next source update under Planning v16 and supplied a clean `main` checkout at
`7dae1dc3cb4aba8f29b5f33fbe638d05af175006` (`trace text improvements`). The archive's recorded
`origin/main` matches that SHA. No network fetch or live-remote verification was performed.

The supplied archive is `workspace(20260913-230438).zip`; its SHA-256 is:

```text
a8c84517a61c5e848b466603311fa113e28282efe48f042a31a550005bbd75fc
```

The earlier Planner snapshot was dirty at `448183b`. Its four changed trace/menu/test files and three
untracked trace tests are now committed in the new checkpoint. They were preserved, not replaced with
an older patch. The existing read-only P15-1E-A support-observation seam also remains in place.

The work here is a separately extracted, display-only candidate. The container's missing dependencies
prevent a complete P16-0 GO. Do not treat preparation of this candidate as a waiver: establish the full
authoritative local baseline before applying it, and pass the post-change wall before accepting it.
No user working directory, remote branch, Word document, dependency file or validation configuration
was modified by preparing the patch.

## 2. Exact change boundary

| Path | Change |
|---|---|
| `nca8_trace.py` | Version 0.6.0 to 0.7.0. Add private presentation-only domain/target-note helpers; correct bridge/buffer and F wording; show original messages in technical explanations. |
| `nca8_menu.py` | Version 0.7.2 to 0.7.3. Update scientific-target and trace-help text. No menu routing or execution changes. |
| `tests/test_nca8_trace_domains.py` | New 37-case domain, truncation, provenance and noninterference tests. |
| `tests/fixtures/nca8_trace_domains_baseline.json` | Frozen fingerprints from clean pre-patch source, not generated from the implementation under test. |
| `tests/test_nca8_menu_routing.py` | Update two expected target-version strings; retain existing behavior assertions. |
| `README.md` | Correct the top-level planning reference and document this bounded display change. |
| `docs/P16_1R_A_REVIEW.md` | This preservation, validation and application record. |

Exact edits to the existing renderer are in `_explain_firewall_v1`, `_explain_scheduler_v1`,
`_explain_dispatch_v1`, `_flow_input_step_v1`, `_flow_action_step_v1`, `_flow_finish_step_v1`,
`_flow_technical_v1`, `_flow_cycle_heading_v1`, `_flow_render_cycle_v1`, and
`render_flow_trace_lines_v1`, plus their relevant display constants/docstrings. The two added helpers
are `_flow_domain_v1` and `_flow_target_note_v1`; neither is a new public API or runtime mechanism.
The Git patch supplies exact insertion/replacement locations.

No change is made to `nca8_runtime.py`, `nca8_adapters.py`, the scheduler, maps, BodyMap, primitives,
Attention/Navigation selection, prediction evaluation, support schema, environment or legacy default.
No new production module, dependency, phase enum, trace field, learned state or callback is introduced.
The existing compact renderer and canonical serialization are unchanged. No formatter was run and no
lint/type suppression was added.

## 3. What the explanation now says

`DOMAIN` is independent of the existing PART / REPRESENTATION / SERVICE categories and an integrity
check's purpose. A sensory service can implement cognitive work while a scheduler service is runtime
infrastructure. A recorded cycle/phase is a grouping label, not proof that everything in it belongs
inside cognition. Unknown messages stay unclassified even when their channel or phase looks familiar.

The ordinary A0 first-cycle tail remains **#20, #21, #22, #23, #24, #25**, in that order:

| Record | Explanation |
|---|---|
| #20 | Cognitive coordination commits the permitted action. |
| #21 | Mixed boundary report: the synchronous bridge has already advanced the external world and adapted the returned observation. |
| #22 | Internal learning placeholder reports zero durable updates. This is not a new learner. |
| #23 | Internal runtime scheduler maintains pending, latched and expired results. Those counts are not learning or episodic-memory counts. |
| #24 | Input-boundary service buffers the already-adapted observation. It does not filter or step the world again. |
| #25 | Runtime bookkeeping reports closure without interpreting the next observation. |

These numbers identify the familiar example, not the implementation's classification rules. A veto
adds a NOT_APPLIED event and changes later numbers; the domain logic follows recognized events instead.

The explanation is grounded in the unchanged source path:

```text
Nca8EpisodeRunnerV1.run_cycle
  Phase-E callback
    Nca8EnvironmentBridgeV1.apply_task_action
      translate permitted task
      advance private external environment
      adapt_env_observation_v1 on returned observation
    emit dispatch report
  Nca8CognitiveRuntimeV1 finishes F and scheduler housekeeping
  runner assigns already-adapted packet as pending
  emit buffering record
  emit closure record
```

The initial reset bridge also adapts before the initial buffering report. These are explicitly labeled
SOURCE CONTRACT explanations. They do not fabricate observed substep timestamps or reconstruct
missing diagnostic records.

An unnumbered schematic marked **PLANNED TARGET ORDER - NOT EXECUTED (P16-1R-B)** precedes the
recorded flow. It describes future internal handoff/F/closure, then outer world/input processing in the
serialized driver, while noting possible overlap in a real embodiment. It does not create #21a/#21b,
reorder historical records or claim that this candidate implements the refactor.

Architecture sources: §§8.9, 89, 97, 139.9–139.10, 147–150.9. This is explanatory maintenance, not
biological validation or implementation of the planned Emotion and local-learning capabilities.

## 4. Evidence from this container

Interpreter: Python 3.13.5, preserving the repository's configured 3.13 development line. No claim of
Python 3.11 execution or Howard's installed patch version is made.

| Check | Clean baseline | Candidate |
|---|---|---|
| Explicit `tests/test_nca8_*.py` selection | 306 passed | 343 passed |
| New domain test file | Not present | 37 passed |
| Planner CMD selection `tests -k nca8` | Not used for the baseline count | 344 passed; 1,048 deselected |
| Full coverage-free pytest | 1,353 passed; 2 failed | 1,390 passed; 2 failed |
| Gate A, default API reset | 6 cycles; 5 actions; standing/stable; later success | Identical summary and canonical bytes; 146 records |
| Component report | 58 registered host components | 58; updated menu/trace versions only |
| Preflight software probes | 101/101 | 101/101 |
| Preflight hardware checks | 5/5 in this container, HAL off | 5/5 in this container, HAL off |
| Pylint and mypy | Unavailable | Unavailable; invocation fails before analysis |
| Python compilation / patch whitespace | Baseline retained | Passed |

Both full-suite failures are the same missing optional-package dependency in this container:

```text
tests/test_world_graph_pyvis_export.py::test_to_pyvis_html_writes_file
tests/test_world_graph_pyvis_physics_true.py::test_to_pyvis_html_physics_true
RuntimeError: Pyvis not installed
```

They were not skipped, patched out or treated as acceptable local failures. Attempted isolated tooling
installation was blocked by DNS/network access; repository requirements were not changed. The candidate's
full preflight completed and returned exit code 1, with unit tests 1390/1392, probes 101/101 and hardware
checks 5/5. The optional OpenAI smoke emitted a warning because no API key was present. Coverage was
disabled under the existing default policy. The earlier baseline preflight emitted its complete summary
but its surrounding tool invocation timed out; it is not used as proof of a normal baseline process exit.

Consequently, **the full validation wall is not green here**. These results establish a bounded
before/after comparison, not the local P16-0 or P16-1R-A acceptance certificate.

The single patch was applied with `--whitespace=error-all` to a separate clean local checkout of
`7dae1dc`. All seven file contents matched the tested candidate. The Planner's `tests -k nca8`
selection passed there (344 passed, 1,048 deselected), and checked reversal restored an empty
working-tree status. The extra selected test is outside the explicit `test_nca8_*.py` file set;
the two selection counts are not interchangeable. These are patch reproducibility checks, not a
substitute for missing pylint/mypy or the authoritative local validation wall.

### Noninterference controls

The frozen fixture was captured from clean `7dae1dc` before any production edit. Five six-cycle cases
use seed 19: standard, Attention-off, Navigation-off, body-handoff-veto, and read-only-support enabled.
Tests compare full result hashes, canonical-event hashes, pending-observation hashes and final status,
while invoking both explanatory and flow renderers between cycles. Do not regenerate these references
to conceal a later behavioral change; a deliberately changed profile requires explicit fixture review.

Separate tests inspect live public source/durable-map, BodyMap, commitment, pending prediction and
outcome-history snapshots before and after rendering, including while a prediction is pending. Menu
option 4 also preserves status, pending input and canonical events. Existing flow/C1/C2/parts-first
and menu tests remain active.

Manual text inspection covered the successful #20–#25 tail, the body-veto/NO_ACTION trace, and the
truncated buffer/closure tail. The latter shows missing context rather than synthesizing dispatch.
Width checks cover 60, 96 and 140 columns. Known original messages and detail values remain available;
unknown events retain raw evidence even when ordinary technical details are disabled.

A SHA-256 audit checked all 260 pre-existing Python files: only the two presentation modules and the
two-string menu test changed. All other existing Python file bytes were identical to the entry snapshot.

## 5. Windows CMD: validate the clean baseline

Use the same interpreter/environment used for the repository's normal checks. Save the patch as
`%USERPROFILE%\Downloads\CCA8_P16_1R_A_trace_domains.patch`.

Run this baseline block **before applying the patch**. Stop on a failed check; do not skip a failing
test to match this container. Confirm the intended clean SHA before proceeding.

```bat
cd /d C:\Users\howar\workspace
git status -s
git rev-parse HEAD
git branch --show-current
git rev-parse refs/remotes/origin/main
python --version
python -m pip --version
python cca8_run.py --about
python -m pytest --no-cov -q tests -k nca8
python -m pylint nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py
python -m mypy nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py
python -m pytest --no-cov -q
python cca8_run.py --preflight
git diff --check
```

Expected entry SHA: `7dae1dc3cb4aba8f29b5f33fbe638d05af175006`. Empty `git status -s` is the
intended baseline. No fetch, pull, reset, clean, interpreter migration or package installation is
part of this patch. The `-k nca8` command is the Planner's convenient CMD-compatible selection;
record its actual count rather than assume it always equals an explicit file-glob selection.

## 6. Apply and validate

Only after the authoritative baseline passes:

```bat
git apply --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1R_A_trace_domains.patch" && git apply --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1R_A_trace_domains.patch"
git diff --check
git diff --stat
git status -s
python -m py_compile nca8_trace.py nca8_menu.py tests\test_nca8_trace_domains.py
python -m pytest --no-cov -q tests\test_nca8_trace_domains.py
```

Then repeat the baseline's focused/full pytest, twelve-module pylint/mypy, component report and
preflight commands against the candidate. No early slice acceptance or P16-1R-B work follows from
`git apply --check` alone. Ordinary `git diff --stat` omits untracked additions; use `git status -s`
and the seven-file manifest above until those files are staged.

For manual review, run `python cca8_run.py`, enter the NCA8 experimental submenu, select **5** for
a fresh Gate-A run, then **4** for the guided trace. Check domain labels on the actual #20–#25 tail,
the already-adapted wording at #24, zero learning at #22, and the separate planned schematic.
Opening option 4 repeatedly must not add cycles or change pending input.

After all checks and manual review pass, the bounded commit can be recorded with explicit paths:

```bat
git add -- README.md nca8_trace.py nca8_menu.py tests/test_nca8_menu_routing.py tests/test_nca8_trace_domains.py tests/fixtures/nca8_trace_domains_baseline.json docs/P16_1R_A_REVIEW.md
git diff --cached --check
git diff --cached --stat
git commit -m "P16-1R-A: distinguish trace domains without changing A0 behavior"
```

Do not commit a failing candidate. No push is performed by these commands. Record local counts,
manual outcome, accepted SHA and GO/NO-GO separately; this dated report describes the delivered
candidate, not an acceptance result that has already occurred.

## 7. Rollback and next scope

Before committing or making subsequent edits, reverse this candidate with:

```bat
git apply --reverse --check "%USERPROFILE%\Downloads\CCA8_P16_1R_A_trace_domains.patch" && git apply --reverse "%USERPROFILE%\Downloads\CCA8_P16_1R_A_trace_domains.patch"
git status -s
```

Reversal is safe only when its check passes and these files have not accumulated work that must be
retained. After a committed accepted change, use a separately reviewed revert of that specific commit,
not a destructive reset or `git clean`.

The next functional slice remains **P16-1R-B**, after accepted 1R-A and a fresh baseline. It will change
the actual callback/handoff/world/input order with explicit once-only and failure-state tests. This
candidate neither includes that change nor authorizes the later learning/Emotion programme.
