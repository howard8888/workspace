# P18-H1 review: target, command, feedback, time and authority contracts

Date: 19 September 2026.
Status: tested source review candidate; local validation and acceptance remain pending.
Entry: e93c1192fe4095346b0c2c828606254bfac6055f, clean main.
Authority: accepted Architecture v10.1 and newly adopted Planning v18.
Design record: docs/P18_1D_DESIGN.md. Review its detailed choices before applying H1;
a separate user GO for that detailed record is not claimed by this delivery.

## What this update implements

Two new, small contract modules supply the typed boundary needed by later body,
BodyMap and sensorimotor work. They contain frozen records, strict parsers,
detached diagnostic exports and pure correspondence/time checks. No new actor is
constructed by normal CCA8 or NCA8 startup. No motor command is dispatched.

- cca8_motor_contracts.py: standard-library-only command and feedback interface.
  It has no task, WNM, PNM, policy, simulator or legacy-cognition import.
- nca8_sensorimotor_contracts.py: proposed/committed target descriptions, fixed
  body anchors, finite lease, two target families, local dispositions and a
  detached focal view of the same physical observation.
- scripts/review_nca8_motor_contracts.py: finite positive/adverse contract fixtures,
  not a physical demonstration. Keep this versioned development helper.
- tests/test_nca8_hierarchical_motor_contracts.py: 155 collected tests, including
  parameterized boundary cases and the manual program's deterministic output.
- tests/test_nca8_import_firewall.py: exactly the new NCA8 contract module and
  its one neutral import are added to the existing explicit manifest.

Both new modules begin at version 0.1.0. Existing component versions are unchanged.
The host registry remains 61 components / 8 registered behavioral primitives;
those are host counts, not an implemented SMP inventory.

## Important distinctions demonstrated

A target based on tilt +30 with offset -12 keeps endpoint +18 when a later sensor
reading becomes +25. The target does not slide to +13 by applying the offset again.
The mirrored fixture has the opposite sign. These are supplied fixtures, not an
implemented BodyMap mapping.

MotorCommandV1 has only two signed normalized drives plus stream/number/time.
It cannot carry a standing target, Righting label or task prediction. A provider
must later enforce its own command watermark and physical time; pure validation
is not an exactly-once delivery service.

A sensed extension of 0.60 can satisfy its supplied target while support_contact
is False and useful_loading is zero. LocalTargetReportV1 therefore never establishes
task success or action causation. ACHIEVED cannot be constructed with absent target
measurements or a coordinate outside tolerance.

Availability is distinct from event time. The focal projection rejects a future
report and preserves the original acquisition identity; it neither creates a new
sensor event nor becomes WNM. Dict exports are detached from all immutable records.

Leases are half-open, at most eight ticks. Wrong stream/generation/execution/envelope/
target revision is rejected by the pure context check. No-new-task-output neither
renews nor cancels a target. Actual installation, state transitions, freshness,
resource occupancy, correction counting and physical stopping are H4 obligations,
not secretly implemented by a dataclass.

An old sample identity cannot be changed to claim a new measured achievement.
Delayed evidence may report achievement observed by the lease endpoint, but cannot
make an expired target current again. There is no live-permission deserializer.

## Deliberate exclusions and preservation

No existing runtime, BodyMap, primitive, handoff, scheduler, adapter, source,
world provider, README, component registry, interpreter configuration or dependency
file is edited. The old posture_support_v1 schema, binary policy:stand_up/None
provider, A0 fixtures and independent legacy runtime are unchanged.

H1 does not implement the proposed physical equations, finite physical driver,
BodyMap transform, target executor, local predictor, Righting IP/PNM changes,
learning, probability, multi-task arbitration or default promotion. It does not
create a NavMap revision for each sample. Runtime bounded buffers are future H4/H6
work; H1 has no history, queue or RNG.

## Validation actually performed in the review environment

Python 3.13.5; pytest 9.0.2. Existing mypy target 3.13 retained.

    Unmodified baseline full pytest:       1,661 passed; 2 failed (missing Pyvis)
    New H1 test module:                      155 passed
    H1 plus existing import firewall:        164 passed
    Complete focused NCA8 selection:         770 passed; 1,048 deselected
    Full candidate pytest:                 1,816 passed; 2 failed (missing Pyvis)
    Candidate preflight unit lane:         1,816 / 1,818
    Candidate preflight architecture probes: 101 / 101
    Candidate preflight hardware checks:       5 / 5 (review host only)
    Candidate preflight optional LLM check: warning: unconfigured integration
    Candidate preflight overall:            FAIL, not a green certificate
    Compile and Python-3.11 grammar checks:  PASS; not Python-3.11 execution proof
    About / contract fixture:               PASS

The same two failures occurred before and after the patch:

    tests/test_world_graph_pyvis_export.py::test_to_pyvis_html_writes_file
    tests/test_world_graph_pyvis_physics_true.py::test_to_pyvis_html_physics_true

Both stop at ModuleNotFoundError for Pyvis. No test is removed, skipped or weakened.
Pylint and mypy are unavailable in this environment; their commands returned
No module named pylint / mypy. An isolated tooling download could not reach its
package index; no package was installed and no project dependency was changed.
The local Windows pylint, mypy and complete preflight wall remain mandatory.

## Manual inspection

From the repository root:

    python scripts/review_nca8_motor_contracts.py

The eight blocks show fixed anchors; target/command/sensor separation; local
achievement without support; missing versus no-contact evidence; future-data
refusal and same-event focal projection; expiry and wrong-generation/revision
refusals; malformed packets/duplicate commands; and absence of runtime effects.
Every observed value is explicitly a fixture. There is no claim that a goat moved.

## Acceptance and next work

Review the P18-1D record first. Apply only to the declared clean source (or a separately
reconciled overlay), then run the supplied full local validation wall and inspection.
Do not mark H1 GO or commit based solely on this extraction's partial wall.

After local GO, commit this bounded contract slice. The next implementation is
P18-H2, the additive command-driven physical provider, under the reviewed numerical
profile. H3 BodyMap, H4 execution/feedback, H5 Righting preview and H6 integration
remain separate patches. A99 also still requires P16-1G.
