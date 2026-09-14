# P16-1E-B — Action-responsive physical support evidence

**Status: review candidate; not a certified full local GO.**

## 1. Source checkpoint and bounded scope

This patch continues Howard's committed P16-1R-B implementation, including its real internal-handoff / external-world / input-admission separation. It implements **P16-1E-B only**, plus the two presentation corrections explicitly deferred into this update. It does not amend the already committed 1R-B source history.

| Source | Exact basis |
|---|---|
| Supplied archive | `workspace(20260914-022545).zip` |
| Archive SHA-256 | `390304f2662a91e662dece1c5131184dde5a489f8af785781053b2b66d3132f2` |
| Entry HEAD | `6df155db28d75c8be53a93e1a2dd3b69d8e6eb03` — `cog cycle improvements` |
| Branch and recorded references | `main`, `origin/main`, and `origin/HEAD` resolve to the entry commit in the archive; no network fetch |
| Working tree | Clean in the supplied extraction; source edits made only in a separate candidate clone |
| Planning basis | Planning v16 §§17, 21, 28, 37, 59 and 63; Architecture v09.9 remains its scientific basis |
| Planner source | `CCA8_Project_Planning_v16(2).docx`, SHA-256 `042acfbf93aa27c840240e70d59ecc4c973414eb6c1b70ba6f5ee3ca273ea5c3` |
| User entry evidence | Howard reported all tests green for 1R-B, supplied its successful terminal trace, and committed it as `6df155d` |

The already implemented `posture_support_v1` schema and read-only consumer are reused. P16-1E-C trajectory/continuity/current-source refresh, P16-1F activity-relative persistent Righting, P16-1G outcome routing, and subsequent durable learning remain separate slices. The historical baseline wording in Planning v16 is intentionally left alone at Howard's request.

## 2. What this patch changes

| File | Change |
|---|---|
| **New** `cca8_support_world.py` — 0.1.0 | Small standard-library-only physical surrogate, immutable body/profile, pure state transition and sensor packet |
| `cca8_env.py` — 0.7.0 | Two opt-in support scenarios and physical-provider integration into the existing `HybridEnvironment` |
| `cca8_run.py` — 0.30.10 | Register the real external provider in `--about`; host version only otherwise |
| `nca8_adapters.py` — 0.4.1 | Update the scaffold ledger's source/maturity description; no whitelist or parsing change |
| `nca8_menu.py` — 0.7.5 | Clarify commitment, internal acceptance, later outer execution and the distinction between envelope and receipt |
| `nca8_trace.py` — 0.8.1 | Current separated-protocol Phase E says **COMMIT AND HAND OFF**; historical traces retain their dispatch heading |
| **New** `scripts/run_nca8_support_evidence.py` — 0.1.0 | Bounded review command using actual isolated NCA8 sessions; no action script or simulator-state reads |
| **New** `tests/test_nca8_support_provider.py` | 94 provider, integration, isolation, regression, timing, error and presentation test cases |
| **New** `tests/fixtures/nca8_support_provider_baseline.json` | Five NCA8 and three legacy-world fingerprints captured before editing the entry source |
| `README.md` | Current provider scope, review commands, unchanged defaults and explicit limitations |
| **New** `docs/P16_1E_B_REVIEW.md` | This implementation, validation, application and rollback record |

There are **11 patch files: six existing files modified and five new files**. No existing test, canonical fixture, import manifest, dependency, lint/type configuration, Architecture document, Planner or To-Do document is changed.

The cognitive algorithms in `nca8_runtime`, `nca8_sensory`, `nca8_maps`, `nca8_executive`, `nca8_primitives`, `nca8_prediction`, `nca8_body`, `nca8_scheduler` and `nca8_handoff` are unchanged. There remain thirteen flat `nca8_*` files. The new provider is world-side `cca8_support_world`, not another cognitive part or a replacement environment framework.

## 3. Physical profile and observable meaning

The scenarios are `posture_support_recovery_v1` and `posture_support_disturbed_v1`. Both initialize the same physical body: **10 degrees, 0.45 useful loading, 0.40 destabilization**. The first has external disturbance 0; the second 0.85. Both use `support_dynamics_v1`. The profile is a deterministic engineering surrogate, not measured or validated goat biomechanics.

| Quantity | Declared interpretation |
|---|---|
| Body-ground angle | Undirected body-axis angle, 0 horizontal to 90 upright, in degrees |
| Useful loading | Modeled fraction of body weight usefully supported by limbs, 0–1; touching is not full loading |
| Destabilization | Unwanted sliding/collapse speed normalized to the profile's reference maximum, 0–1; not prediction error or confidence |
| Lateral contact | Boolean side-contact approximation, true when angle is at most 20 degrees; not a contact-area fraction |
| External disturbance | Bounded surface forcing, 0–1; an experiment parameter, not a cognitive difficulty or success label |
| Integration interval | `0 < dt <= 1` seconds; default 1; invalid intervals fail before world-state/counter mutation |

For effort `u=1` only when the world receives `policy:stand_up`, and `u=0` for `None`, one step computes:

```text
L_next = clip(L + dt * (0.60 * u * (1 - L) - (0.10 + disturbance) * L))
S_target = clip(0.45 * (1 - L_next) + disturbance)
S_next = clip(S + dt * 0.50 * (S_target - S))
angle_next = clip(angle + dt * (
    35 * u * L_next * (1 - disturbance)
    - 18 * S_next * (1 - L_next)
    - 45 * disturbance
), 0, 90)
```

`clip` saturates the model's physical ranges; it does not repair invalid input. The constants describe a simple recruitment, unloading, sliding-relaxation and lifting surrogate. They are not mammalian constants. Null output supplies no lifting drive. The sliding variable can initially decay under passive settling; it is not forced to increase on every null step. Disturbed loading can show a damped oscillation, not universal monotonic failure.

The transition receives only physical body, received action, profile and interval. It cannot read WNM, PNM, NavMap identity, a cognitive success verdict, scenario stage, milestones, attempt counters or cognitive context. Repeated commands can yield different measurements because the body changed, not because an attempt counter unlocked a prewritten outcome. Unsupported action tokens are rejected, not silently reinterpreted as null.

The support scenarios bypass the old newborn FSM as a body updater. Ordinary scenarios retain their existing behavior. An optional `EnvConfig.support_profile` override is valid only for a named support scenario and takes effect at reset. It permits controlled initial-condition and disturbance tests without adding another cognitive configuration API. A misspelled reserved `posture_support_*` name fails instead of selecting an unrelated storyboard. No joint simulator, automatic lower learner, milestone script, new reward or completion oracle is introduced.

### Important A0 limitation

The old posture token is derived **from** physical orientation: angle at least 75 degrees reports `standing`; lower angles report `fallen` in the coarse compatibility vocabulary. The measurements are never manufactured **from** that token.

This orientation label is not an activity-relative support or dwell verdict. A0 still maps `standing` to its old coarse `stable` representation and can stop issuing StandUp while loading later decays. That remains a known scaffold, not a claim that the new measured register now governs safety or recovery. P16-1E-C and 1F/1G must separately qualify richer evidence and behavioral use. The disturbed case is deliberately still fallen so it exposes distinct loading/sliding without borrowing a changed posture label as the explanation.

## 4. Packet, timing, ownership and failure contracts

`PerceptionAdapter` samples the immutable physical body into the existing `raw_sensors["posture_support_v1"]` location. Its keys are exactly:

```text
schema, sample_id, event_cycle, frame_id,
body_ground_angle_degrees, useful_loading, destabilization, lateral_contact
```

The schema and frame remain `posture_support_v1` and `body_ground_v1`. No scenario, profile, PNM, map-owner, action-answer, desired support or task-success fields enter the packet. Profile provenance appears in external reset/step `info`, not a newly whitelisted cognitive field.

Under this declared serialized harness, world reset step 0 maps to sample/event 1; world step n maps to sample/event n+1. A repeated `observe()` at the same step returns the same identity and values. Numerical measurements do not depend on that counter. World reset restarts the stream, while NCA8 separately resets its owning consumer and generation. Different-rate or longer-lived streams require a later clock-domain contract; this patch does not pretend that all sensory sampling is one biological clock.

The causal path remains:

```text
eligible Observation_n -> existing owner-side Phase C
     -> coarse A0 decision -> commitment -> internal handoff
     -> zero-learning F -> housekeeping -> internal close
     -> outer receipt consumed once -> physical provider advances once
     -> input admission/detachment -> Observation_(n+1) pending
```

The original `support_observation_enabled=False` default is unchanged. The review script explicitly enables it. A current `SupportConfigurationV1` is a separate read-only companion with `behavioral_authority=False`. It does not add measured values to the WNM, change Attention or Navigation, calibrate an IP, or revise the durable source. Turning its consumer off leaves the same actions and next observations in each new physical scenario.

All four measurements are available in the deterministic provider. Existing missing/partial/invalid/future/duplicate/out-of-order/conflict handling is exercised by explicit transport fault injection, not by a hidden random sensor model. Re-reading a cached sample cannot create fresh support. New body snapshots leave old snapshots intact; each session owns its world. Stream overflow is rejected before another world step.

P16-1R-B's stop/reset contract is retained. A test lets a real physical step occur and then loses its result: execution is recorded unknown, pending input is withheld, and a second call cannot issue another lift. No automatic retry, stale-input substitution, callback task selection or legacy rescue is added.

## 5. Actual review examples

At the same initial body and `dt=1`, the first returned measurements are:

| Condition | Received token | Angle (degrees) | Useful loading | Destabilization | Coarse posture |
|---|---|---:|---:|---:|---|
| Initial reset | None yet | 10.000000 | 0.450000 | 0.400000 | fallen |
| Recovery | `policy:stand_up` | 34.486589 | 0.735000 | 0.259625 | fallen |
| Disturbed | `policy:stand_up` | 0.000000 | 0.352500 | 0.700000 | fallen |
| No-action control | `None` | 6.424199 | 0.405000 | 0.333875 | fallen |

Thus the same command and coarse posture can accompany opposite loading/sliding changes. A human can compare the samples, but CCA8 does not yet compute a trajectory estimate in this slice.

The six-cycle review script produces three independently reset cases. Recovery issues three StandUp requests followed by three null outputs; sustained disturbance issues six StandUp requests; the explicitly Navigation-disabled control issues six null outputs. These are **observed results of the runtime**, not an action list supplied to it. The script prints processed input and next pending input separately and stops at its declared bound without processing the final pending sample.

The ordinary menu Gate A is unchanged: **six cycles, five StandUp commands, final standing/stable, 158 records**. The provider experiment is separate from that benchmark. Its trace lengths need not match the original Gate A because it includes the optional support-consumer records and different physical observations.

## 6. Validation evidence and remaining limits

Checks used Python 3.13.5 in a separate Linux container. They are not a replacement for Howard's Windows validation or evidence that the proposed source slice has been locally accepted.

| Check | Before patch | Candidate |
|---|---:|---:|
| New provider test file | Absent | **94 passed** |
| `pytest --no-cov -q tests -k nca8` | **407 passed**, 1,048 deselected | **501 passed**, 1,048 deselected |
| Full `pytest --no-cov -q` | **1,453 passed; 2 failed** | **1,547 passed; 2 failed** |
| Ordinary Gate A | 6 cycles / 5 commands / 158 records | Same; original canonical bytes retained |
| Five original NCA8 fingerprints | Captured from entry source | All result, next-input and canonical hashes match |
| Three legacy-world observation fingerprints | Captured from entry source | All match |
| New review command | Absent | Recovery / disturbed / no-action complete |
| Interactive host → fresh Gate A → trace → quit | Entry behavior retained | Completed; both wording changes visible |
| `--about` | Existing registry | 60 components, including the actual external provider |
| Preflight software probes | Not separately rerun here on entry | **101/101 passed** |
| Preflight hardware checks | Not separately rerun here on entry | **5/5 passed** in this container |
| Full candidate preflight | — | **FAIL**: 1,547/1,549 unit tests; same two missing-Pyvis failures |
| Compilation / patch whitespace | — | Passed |
| Pylint / mypy | Unavailable in this container | Could not run; local validation required |

The two failures are unchanged dependency failures:

```text
tests/test_world_graph_pyvis_export.py::test_to_pyvis_html_writes_file
tests/test_world_graph_pyvis_physics_true.py::test_to_pyvis_html_physics_true
```

Both fail because Pyvis is not installed. Attempts to install the missing tools did not succeed; this review does not attribute a more specific cause than the observed installation failure. No check was skipped or weakened. Preflight also reports the existing optional missing-API-key warning, which is not the cause of its unit-test failure. No live external service or physical robot was tested.

The packaging check uses a second clean clone of the same entry commit: strict patch application, byte-for-byte comparison of all 11 delivered files, rerun of the 94 new tests and 501-test NCA8 selection, strict reversal, and clean-tree confirmation. These checks supplement, not replace, the local wall.

The pre-edit fixture is independent of the candidate. It covers default operation, Attention disabled, Navigation disabled, body handoff vetoed and the optional read-only consumer enabled on the old world. The captured legacy streams cover ordinary newborn, hard newborn and goat-foraging worlds. This is evidence for those declared cases, not every possible simulator configuration.

## 7. Apply in Windows CMD

Save `CCA8_P16_1E_B_support_evidence.patch` in Downloads. Preserve any newer local work and stop if HEAD or status differs from the intended entry. Do not reapply the previous 1R-B patch.

```bat
cd /d C:\Users\howar\workspace
git status -s
git rev-parse HEAD
```

Expected HEAD is `6df155db28d75c8be53a93e1a2dd3b69d8e6eb03`; status should be empty. The user-reported prior green wall is entry evidence. Repeat it before applying if source, interpreter or dependencies have changed.

```bat
git apply --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_B_support_evidence.patch" && git apply --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_B_support_evidence.patch"
git diff --check
git diff --stat
git status -s --untracked-files=all
```

The first `git apply` checks only. The second applies only when the first succeeds. Neither stages nor commits. Ordinary `git diff --stat` initially shows the six modified tracked files; `git status` also shows the five additions.

## 8. Validate and perform the short manual review

Run each command and inspect a failure before continuing to acceptance. The new world module, changed shared environment and review script are included in lint/type scope, not just the thirteen NCA8 files.

```bat
python --version
python -m py_compile cca8_support_world.py cca8_env.py nca8_adapters.py nca8_menu.py nca8_trace.py cca8_run.py scripts\run_nca8_support_evidence.py tests\test_nca8_support_provider.py
python -m pytest --no-cov -q tests\test_nca8_support_provider.py
python -m pytest --no-cov -q tests -k nca8

python -m pylint nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py ^
 cca8_env.py cca8_support_world.py cca8_run.py scripts\run_nca8_support_evidence.py

python -m mypy nca8_adapters.py nca8_body.py ^
 nca8_contracts.py nca8_executive.py nca8_handoff.py nca8_maps.py ^
 nca8_menu.py nca8_prediction.py nca8_primitives.py ^
 nca8_runtime.py nca8_scheduler.py nca8_sensory.py nca8_trace.py ^
 cca8_env.py cca8_support_world.py cca8_run.py scripts\run_nca8_support_evidence.py

python -m pytest --no-cov -q
python cca8_run.py --about
python cca8_run.py --preflight
git diff --check
```

For the new evidence, run:

```bat
python scripts\run_nca8_support_evidence.py
python scripts\run_nca8_support_evidence.py --case recovery --cycles 2 --trace
python scripts\run_nca8_support_evidence.py --case disturbed --cycles 2 --trace
```

The first command is the compact three-case review; it is not a pytest command. Confirm common initial measurements, different physical consequences, read-only status, and processed-input versus next-pending labels. The separate `CCA8_P16_1E_B_Trace_Examples.txt` contains generated compact output and selected actual saved events. Selection there omits intermediate records deliberately; full `--trace` remains available.

Also run `python cca8_run.py`, enter the NCA8 menu, choose 5 then 4, and verify the unchanged 6/5/158 Gate-A result and the two corrected texts. There is no new menu choice or automatic activation of support physics in this slice. The script avoids altering the existing interactive session and supplies a small executable inspection route before later enhanced-menu work.

**GO requires** the local full wall, the brief success/adverse/null review, unchanged old Gate A, and no unplanned files. A provider-only GO does not close 1E-C, 1F, 1G or A99. This review's missing tools/dependencies are not permission to waive a failing local check.

## 9. Commit and rollback

After local GO, stage only the declared files. Inspect the staged list before committing; do not include transient terminal logs, caches or archive/render artifacts.

```bat
git add -- README.md cca8_env.py cca8_run.py cca8_support_world.py ^
 nca8_adapters.py nca8_menu.py nca8_trace.py ^
 scripts/run_nca8_support_evidence.py tests/test_nca8_support_provider.py ^
 tests/fixtures/nca8_support_provider_baseline.json docs/P16_1E_B_REVIEW.md
git diff --cached --check
git diff --cached --stat
git status -s
```

After verifying those 11 files:

```bat
git commit -m "P16-1E-B add action-responsive support evidence"
git status -s
git log --oneline -3
```

No push is performed automatically. Record the resulting SHA and actual local validation counts; do not invent a commit SHA from the candidate extraction.

Before committing, and **only while the patch files have no subsequent edits and are not staged**, checked reversal is:

```bat
git apply -R --check --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_B_support_evidence.patch" && git apply -R --whitespace=error-all "%USERPROFILE%\Downloads\CCA8_P16_1E_B_support_evidence.patch"
git status -s --untracked-files=all
```

If files have been staged or edited afterward, stop and reconcile them instead of forcing reversal. After a commit, use a separately reviewed `git revert` of that specific slice commit. No destructive reset, clean or checkout is required. Code rollback cannot undo an already executed external physical action.

## 10. Next bounded work

After this slice is accepted and committed, **P16-1E-C** can build local trajectory and bounded continuity from distinct compatible observations and refresh source-linked working content. It must reject false freshness, compare actual event intervals and keep current evidence separate from durable organization. It should not gain trajectory-sensitive action authority before the planned 1F/1G gates.

The agreed deeper conceptual trace review remains after 1E-C and before persistent activity-relative Righting. The present update provides a real action-responsive source for that work; it does not pretend to have already implemented it.
