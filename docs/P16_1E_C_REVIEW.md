# P16-1E-C review: local support trends, bounded continuity and current-source WNM refresh

**Status:** source review candidate, not yet a local GO or an A99 gate.
**Date:** 14 September 2026.
**Scope:** Planning v16 §§21–22 and §37, building on accepted P16-1R-B and P16-1E-B.
**Entry:** `47bbd5937c0ed2815ed65d7946069915edd077d9`, `more cog cycle updates`.

## 1. Exact source basis and preservation

The supplied `workspace(20260914-040151).zip` was extracted separately, including its Git history.
HEAD, main and recorded origin/main resolved to the entry SHA above. The original extraction had an empty
`git status --porcelain`. No fetch was made; recorded origin/main is not an independent live-remote check.
The archive SHA256 is `4ddcad73faeb282d35e3cbb39d8594d5426628f7e2f7f58210ea3018ea22b049`.

A separate clone was edited and tested. The uploaded ZIP and extracted production source remain unchanged.
Tests produced ordinary ignored artifacts in their own extraction. The original source was rechecked clean.

Before source edits, eight six-cycle conditions were captured in the new fixture
`tests/fixtures/nca8_support_dynamics_baseline.json`:
ordinary Gate A, Attention disabled, Navigation disabled, body-handoff veto, Gate A with only the old support
consumer enabled, physical recovery, physical disturbance, and the recovery-world no-action control.
The fixture records result, next-input, measured-configuration, canonical-trace and durable-map hashes.
It was not generated from two runs of the changed implementation.

The new path is independently opt-in. No prior fixture, world model, packet schema, BodyMap action rule,
primitive, prediction evaluator, boundary handoff implementation or scheduler is rewritten. The earlier text
corrections are preserved. The Architecture, Planner and To-Do documents are unchanged.

## 2. What this slice makes real

1E-B supplied measurements from an external action-responsive support surrogate. This slice adds a real
CCA-side representation of local change, followed by a read-only refresh of the same selected source's WNM:

```text
already admitted support observation
    -> existing body-sensory Phase-C application / SupportConfigurationV1
    -> source-owned finite differences and bounded continuity
    -> Attention selects or maintains its existing source
    -> Navigation refreshes a measured section in the same WNM

primitive applicability and application
    <- restricted A0 argument view WITHOUT the new measured section
```

`nca8_support_dynamics.py` is a cohesive helper called by the existing body-sensory owner. It is not an
additional brain PART, general memory manager, SEC learner or source selector.

The dynamics snapshot is actual source/working content, not a computation performed by the renderer.
The source and copied WNM snapshots are immutable. The WNM includes the source reference, current input
disposition, applicable reference sample, previous sample where comparable, event age, profile, rates and
directions. An earlier saved WNM remains unchanged when the current one is refreshed.

The same durable `posture_support@r1` remains in place. Source, owner, revision and applied cycle must match
the chosen WNM. No new durable map or revision is created by taking a sample or calculating a difference.
After Attention releases the source, the source owner continues processing its observations without making
a second WNM. Returning focus uses newer eligible source content, not a cached old WNM.

### Deliberate action-authority boundary

`support_dynamics_enabled=True` requires `support_observation_enabled=True`; both default false.
The optional `WorkingNavMapStateV1.support_dynamics` section does not enter `working_relations`.
Navigation creates a short-lived argument view without that section for both primitive queries and `apply()`.
It retains only one selected/current WNM; this restricted argument view is not another selected or stored focus.

A test primitive explicitly attempts to read the field and sees `None` at both call boundaries.
BodyMap and prediction continue to receive their unchanged coarse inputs. Attention ranks the unchanged
source nominations. No measured trend chooses, cancels, recalibrates or improves an action in 1E-C.

This is a staging boundary, not a biological claim that a mature primitive should ignore useful working
relations. P16-1F will separately specify how richer Righting may use the new source information.

## 3. Named temporal profile

The new **CCA-side** profile is `support_trend_v1`, distinct from the unchanged **world-side**
`support_dynamics_v1`. Profile parameters are explicit in serialized source/WNM snapshots.
The session currently uses the fixed default profile; the helper permits bounded parameter variants for tests.

| Parameter | Default | Meaning |
|---|---:|---|
| Angle deadband | 1.0 | Degrees per represented event-cycle. |
| Loading deadband | 0.02 | Normalized loading units per represented event-cycle. |
| Destabilization deadband | 0.02 | Normalized destabilization units per represented event-cycle. |
| Maximum pair interval | 2 | Compare consecutive accepted reference samples only within this event interval. |
| Continuity age limit | 2 | Hold an old reference at event ages one and two, never indefinitely. |

A rate is `(new_value - old_value) / (new_event - old_event)`. Sample identity and event time must both increase.
Polling count, availability time, the number of attempted StandUps, a posture label and a future pending packet
cannot substitute for the measured event interval. A new current sample separated by too large a gap starts
a new baseline with unknown rates. The default pair interval permits one missing intervening event.

An absolute rate at or below its deadband is `approximately_stable`; otherwise its direction is `increasing`
or `decreasing`. A 1e-12 floating-point comparison tolerance handles numerical equality at a deadband.
The raw finite difference is still retained: the deadband does not zero or modify the measurement.

These directions do not mean task progress, desirable change, safe support or success. For example,
approximately constant angle at zero degrees is still a fallen body. The same supported activity may not
require being upright. Activity-relative judgments and supported dwell belong to later 1F/1G.

Contact remains the existing optional Boolean. Its pairwise description can be `appeared`, `disappeared`,
`unchanged` or `unknown`; no contact fraction or contact-velocity quantity is invented.

## 4. Missing, stale, invalid and contradictory input

The existing support consumer keeps its original admission and ordering semantics. The new helper consumes
that result rather than revalidating the wire in a parallel adapter.

| Applied result / condition | New source treatment |
|---|---|
| First current nonconflicting sample | Current reference; no previous sample and no rate. |
| Later current comparable sample | Current reference plus previous reference; finite difference for each quantity present in both. |
| Partial current sample | Only its present quantities are current. Missing fields are not backfilled from older observations. |
| Missing, duplicate, delayed or all-missing optional input | May hold the last valid reference within the fixed age limit; no new pair/rate. |
| Expired continuity | Clear the usable reference; show insufficient evidence; the next fresh sample is a new baseline. |
| Invalid, future, out-of-order or conflicting result | Break usable history; do not use the rejected sample as a trend endpoint. |
| Unsupported changed frame | Existing adapter rejects it; the new helper breaks history. No new frame is silently introduced. |
| Changed source revision | Do not compare across sources/revisions; any new current sample begins a baseline. |
| Ambiguous coarse posture, or clear changed posture while the measured reference is not current | Invalidate held content rather than retaining a contradictory precise body reference. |

The immutable output distinguishes **the actual applied configuration** from **a usable reference**.
A delayed/rejected sample may remain visible in the applied configuration without becoming current working
geometry. Holding preserves the old reference's event time and ages it; it does not advance the existing
`last_supported_event_cycle`. That field is historical sensory support, not proof of stable mechanical support.

Rates are unknown during held-input cycles, rather than repeated old rates presented as newly measured.
This implementation does not extrapolate geometry or keep an independently aged cache for every quantity.
The next fresh partial sample remains partial. Reading or rendering the snapshot does not age, update or
revive it; one later Phase-C application does that work.

A missing **complete outer observation** remains the accepted 1R-B reset-required transport failure.
Only missing/invalid **optional support data within an otherwise usable observation** is handled here.
There is no silent replay of the preceding complete observation after transport failure.

## 5. Trace and review behavior

New events are emitted only when the new flag is enabled:

| Channel | Phase | Meaning |
|---|---|---|
| `support_dynamics` | C1, stored `UPDATE_OUTCOMES` | The existing body-sensory owner produced the actual source-local snapshot. |
| `wnm_support` | D, stored `FOCAL_COMMITMENT` | Navigation copied that eligible selected-source snapshot into the same WNM. |

Each record respects the existing sixteen-detail bound. The C record contains input disposition and reason;
the WNM record instead contains working identity and refresh cycle. Original support-observation and WNM
events remain. Known new events receive source/working explanations; unknown messages remain unclassified.
The renderer reads recorded values only and does not construct missing predecessors or calculate trends.

The ordinary interactive menu still uses default A0 and does not silently enable either optional support flag.
It retains the six-cycle, five-StandUp, 158-record Gate A. Its new status line appears only for an explicitly
provided session with dynamics enabled. Existing menu routing and fresh-session semantics are unchanged.

The existing review script defaults to the accepted 1E-B provider-only behavior. Add `--dynamics` for this slice.
Its source/WNM lines are printed between the processed input and the next pending observation.
Sample n+1 returned by the current world step remains unavailable to the calculation for sample n.

With the fixed six-cycle review profiles:
- Recovery: three StandUp commands then three null outputs; **163** records with dynamics, versus **154** without.
- Disturbed: six StandUp commands; **180** records with dynamics, versus **168** without.
- Navigation-disabled control: six null outputs; **152** records with dynamics, versus **140** without.

Recovery has fewer added WNM records because standing causes A0 to release the only focal source after cycle 3.
The source continues measuring the subsequent loading decrease even when no WNM is selected.
Record counts are evidence of these specific runs, not fixed cognitive-capacity requirements.

## 6. Source locations / file scope

The patch contains **15 files: ten modified tracked files and five new files**.

| File | Version / exact integration location |
|---|---|
| `nca8_support_dynamics.py` — NEW | v0.1.0; profile, immutable `SupportDynamicsV1`, and owner-local `SupportDynamicsTrackerV1`. |
| `nca8_sensory.py` | v0.3.0; constructor flag, `support_dynamics` property, `_apply_support_observation` invokes helper after existing disposition. |
| `nca8_executive.py` | v0.2.0; optional WNM section and serialization, `NavigationRuntimeV1.update_wnm` refresh/copy, `commit` restricted primitive view. |
| `nca8_runtime.py` | v0.7.0; session flag validation/reset, source property, C1 report, D refresh/report. No change to handoff/world ordering. |
| `nca8_maps.py` | v0.2.1; documentation/version only, clarifying the read-only companion's new permitted working use. |
| `nca8_trace.py` | v0.9.0; two event explanation/flow builders and C1/D component grouping. |
| `nca8_menu.py` | v0.7.6; conditional read-only-dynamics status line only. |
| `cca8_run.py` | v0.30.11; actual helper registration and version only. |
| `scripts/run_nca8_support_evidence.py` | v0.2.0; `--dynamics`, actual source/WNM inspection, separate `--continuity-demo` owner-input control. |
| `tests/test_nca8_import_firewall.py` | Add the actual helper to the explicit module manifest; do not relax import permissions. |
| `tests/test_nca8_support_dynamics.py` — NEW | Local profile, evidence/pair/continuity/error/reset/immutability tests. |
| `tests/test_nca8_support_wnm_refresh.py` — NEW | Actual working refresh, noninterference, ablations, diagnostic isolation and review-script tests. |
| `tests/fixtures/nca8_support_dynamics_baseline.json` — NEW | Eight conditions captured from entry source before editing. |
| `README.md` | Current 1E-C description; retain the 1E-B and earlier histories under predecessor headings. |
| `docs/P16_1E_C_REVIEW.md` — NEW | This implementation, validation and local acceptance record. |

No new dependency, formatter, test exclusion, weakened check or broad source rename is introduced.
There are now fourteen flat NCA8 files, not fourteen biological PARTS. No world-side production file is changed.

## 7. Tests and evidence

### Automated distinctions

The 114 new tests cover finite/range/type validation, positive event intervals, sample identity, inclusive
deadbands, signed rates, Boolean contact, missing/duplicate/empty/delayed/partial input, expiry, invalid-frame
and NaN/Inf rejection, conflict/future/out-of-order invalidation, source revision, session reset and bounded history.

Working tests establish actual source-to-WNM refresh, matching owner/time/revision, unchanged older snapshots,
clearing old content, source updates during focal release, return using current content, absent/unselected facets,
and a primitive that attempts to read the new section at both applicability and application.

Eight pre-edit conditions are compared exactly with the new path disabled. Enabled-path comparisons remove
only the new WNM section and the two named added trace channels, resequencing the retained old events.
No old message, detail, action, prediction, body input, admitted observation or durable field is normalized away.

Diagnostic calls and a five-entry ring buffer are compared with a 256-entry buffer over eight cycles.
Outputs, pending inputs and source/working snapshots agree. No source history depends on trace retention.
The tests also preserve learning's zero-update status and existing Attention/Navigation/body-veto ablations.

### Container checks, not a local certificate

Review environment: Python 3.13.5, pytest 9.0.2. Preserve the repository's Python 3.13 development line.
No separate Python 3.11 run was performed.

| Check | Result |
|---|---|
| Untouched source focused NCA8 baseline | 501 passed, 1,048 deselected. |
| Untouched source full pytest, repeated in original extraction | 1,547 passed; 2 missing-Pyvis failures. |
| New tests | 114 passed. |
| Candidate focused NCA8 selection | 615 passed, 1,048 deselected. |
| Candidate full pytest | 1,661 passed; the same two missing-Pyvis failures. |
| Compilation | All listed NCA8/changed host/script files and both new tests compile. |
| Interactive host / fresh Gate A / trace / quit | Completed; six cycles, five StandUps, 158 retained records. |
| New physical review runs | Recovery, disturbed and no-action complete with the counts in §5. |
| New synthetic continuity control | Actual owner path shows age 1/2 retention, expiry, bad-frame reset and fresh baseline. |
| Preflight software probes | 101/101 passed. |
| Preflight hardware checks | 5/5 passed in this container. |
| Preflight overall | FAIL: unit tests 1,661/1,663; coverage disabled. |
| Optional external-model smoke | One warning: API key absent, unchanged optional integration boundary. |
| Pylint / mypy | Unavailable; each command exits with `No module named ...`. |
| Whitespace / packaged patch | Strict application, file equivalence and reversal are verified separately before delivery. |

The unchanged failing tests are:
`tests/test_world_graph_pyvis_export.py::test_to_pyvis_html_writes_file` and
`tests/test_world_graph_pyvis_physics_true.py::test_to_pyvis_html_physics_true`.
Both stop at the missing Pyvis dependency. An attempted tool/dependency installation was unsuccessful.
These failures are not waived for Howard's local validation. No unobserved local pytest/lint/type/preflight GO is claimed.

The packaged patch was applied strictly to a separate clean clone of the same entry commit. All 15 resulting
files matched the tested candidate byte-for-byte. The 114 new tests and the 615-test NCA8 selection passed
again in that applied clone. Strict reversal restored an empty working status; the final documentation-only
evidence update was then repackaged and the file/application/reversal check repeated. This packaging check
does not replace the full candidate suite or the local wall.

## 8. Windows CMD application and validation

Keep the downloaded patch in Downloads as `CCA8_P16_1E_C_support_dynamics.patch`.
First confirm that no intervening source work is mixed into the entry:

```bat
cd /d C:\Users\howar\workspace
git status -s
git rev-parse HEAD
```

Expected empty status and HEAD `47bbd5937c0ed2815ed65d7946069915edd077d9`.
Capture a fresh local baseline when needed; Howard reported the previous committed slice green.
Do not discard intervening work or force application onto an unexplained checkout.

```bat
git apply --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_C_support_dynamics.patch" && git apply --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_C_support_dynamics.patch"
git diff --check
git diff --stat
git status -s --untracked-files=all
```

The first `git apply` checks; the second applies only if the check succeeds. Neither commits.
Before staging, ordinary `git diff --stat` lists ten modified tracked files; the five new files appear in status.

Run each command and inspect any failure before proceeding to a commit:

```bat
python --version
python -m pip --version
python -m py_compile nca8_support_dynamics.py nca8_sensory.py nca8_executive.py nca8_runtime.py nca8_maps.py nca8_menu.py nca8_trace.py cca8_run.py scripts\run_nca8_support_evidence.py tests\test_nca8_support_dynamics.py tests\test_nca8_support_wnm_refresh.py

python -m pytest --no-cov -q tests\test_nca8_support_dynamics.py tests\test_nca8_support_wnm_refresh.py
python -m pytest --no-cov -q tests -k nca8

python -m pylint nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_support_dynamics.py nca8_trace.py ^
 cca8_run.py scripts\run_nca8_support_evidence.py

python -m mypy nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_support_dynamics.py nca8_trace.py ^
 cca8_run.py scripts\run_nca8_support_evidence.py

python -m pytest --no-cov -q
python cca8_run.py --about
python cca8_run.py --preflight
git diff --check
```

The caret is CMD continuation; do not append spaces after it. Include the newly added helper in lint/type scope.
Also use the repository's broader prescribed scope where applicable. Do not reduce that scope because the
container lacked a tool. Ordinary pytest remains coverage-free; preflight retains its existing coverage policy.

## 9. Manual review and GO/NO-GO

```bat
python scripts\run_nca8_support_evidence.py --dynamics
python scripts\run_nca8_support_evidence.py --continuity-demo
python scripts\run_nca8_support_evidence.py --dynamics --case recovery --cycles 2 --trace
python scripts\run_nca8_support_evidence.py --dynamics --case disturbed --cycles 2 --trace
```

The first command runs three independent physical cases. The second runs only synthetic owner-input control,
not a fourth physical benchmark. Omit `--dynamics` to reproduce the accepted provider-only view.
The supplied `CCA8_P16_1E_C_Trace_Examples.txt` contains captured output, not a proposed future flowchart.

For recovery Cycle 2, the processed sample gives approximately +24.486589 degrees/event, +0.285 loading/event
and -0.140375 destabilization/event. Both coarse pose and the selected action remain A0. The WNM references
sample 2 while sample 3 is still pending. In disturbance, the corresponding differences are -10, -0.0975 and
+0.3. Later nearly flat angle at zero does not mean stability; no aggregate progress verdict is produced.

In the synthetic case, sample 1 is held at ages one and two with all rates unknown, then expires at cycle 4.
After the frame error at cycle 6, sample 7 starts a baseline without a rate; sample 8 produces a legitimate pair.
A WNM test separately covers the corresponding hold/expiry behavior in the actual cognitive path.

Run the ordinary interactive Gate A and trace once as well:
`python cca8_run.py`, Watch Cognition Run → NCA8 → option 5 → option 4.
It must still report six cycles, five StandUp commands and 158 retained events.

GO requires the complete local wall, actual source/working refresh, correct input timing, honest adverse-input
handling, unchanged A0/default behavior and Howard's review. NO-GO on invented freshness, stale copied WNM,
trend-driven action changes, durable revision growth, unknown data becoming zero or diagnostic feedback.

After local GO, commit this bounded slice independently. The agreed next step is the deeper conceptual trace
review at the end of 1E-C, before P16-1F. This delivery does not authorize that behavioral slice automatically,
complete A99, demonstrate realistic goat mechanics or add any learner.

## 10. Commit, without sweeping unrelated files into the slice

First inspect status and ensure the index has no unrelated staged work. Stage only these paths:

```bat
git add -- README.md cca8_run.py nca8_executive.py nca8_maps.py nca8_menu.py nca8_runtime.py ^
 nca8_sensory.py nca8_support_dynamics.py nca8_trace.py scripts/run_nca8_support_evidence.py ^
 tests/test_nca8_import_firewall.py tests/test_nca8_support_dynamics.py tests/test_nca8_support_wnm_refresh.py ^
 tests/fixtures/nca8_support_dynamics_baseline.json docs/P16_1E_C_REVIEW.md
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Expect exactly the 15 paths above. Stop on any unexpected file or failing check. After the tests and manual GO:

```bat
git commit -m "P16-1E-C: read-only support trends and source-linked WNM refresh"
git status -s
git log --oneline -3
```

Record the new SHA and local command/count evidence. No push is performed by this patch.

## 11. Rollback

Before a commit, and only while these files still exactly contain this patch, reversal can restore the entry.
If these paths were staged, first unstage these exact paths with `git restore --staged -- <the paths in §10>`;
that changes the index, not the working files. Do not use a destructive reset/clean or a wildcard checkout.

```bat
git apply --reverse --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_C_support_dynamics.patch" && git apply --reverse --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_C_support_dynamics.patch"
git status -s
```

A reverse-check failure means stop and reconcile intervening edits; do not force it.
After committing, prefer reverting the specifically recorded 1E-C commit in a clean working tree.
Use `git revert --no-edit HEAD` only when HEAD is still that exact 1E-C commit, verified from the log;
otherwise select its recorded SHA deliberately. Rerun the appropriate restored baseline checks.

Turning off `support_dynamics_enabled` is also a supported in-process comparison configuration, not an
automatic rescue after failure. Neither a code rollback nor a flag change rewinds already executed world motion.
