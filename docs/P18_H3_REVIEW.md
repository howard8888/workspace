# P18-H3: BodyMap target formation and capability binding

Date: 19 September 2026.
Scientific authority: accepted Architecture v10.1.
Implementation authority: adopted Planning v18, especially sections 27, 38.4 and 61.2.
Source baseline: 2c7994b2e6b9bafd19837cdcac603194506d2a5f, main.
Delivery status: implementation candidate; local validation/manual GO remains required.

## Entry and scope

Howard supplied a clean Windows checkout with main and origin/main at 2c7994b,
"Add command-driven motor body provider (P18-H2)", and requested H3. A separate
extraction of workspace(20260919-194531).zip confirms that full HEAD, a clean tree
and the same recorded remote-tracking reference. No live remote was queried.
Archive SHA-256:
15d302ef3df194143685c7fecc16c358d005d2a8338ca97e4b3ee3c4b17c8cda.

H2's local validation was supplied in the preceding conversation: 1932 passing
unit tests, clean final Pylint/mypy, full preflight and both manual inspections.
That is attributed local evidence, not a fresh check of this H3 candidate. The
new extraction's baseline full pytest separately returned 1930 passed and the
two existing missing-Pyvis export failures. No dependency/configuration was changed.

H3 implements the BodyMap calculation and its bounded target interface. It does
not select Righting, choose a route, run a feedback controller, issue a motor
command, change the physical provider or update a cortical source. Task
requirements and capability declarations are supplied explicitly by the review
harness. H4 will execute the resulting targets; H5/H6 will supply requirements
through the actual selected Righting operation and integrate the hierarchy.

## Ordinary Python module placement

The existing nca8_body.py owns an optional BodyTargetMapperV1 helper, implemented
in the new cohesive nca8_body_targets.py. Keeping the arithmetic, evidence checks
and two-resource bookkeeping here avoids doubling the old coarse BodyMap file.
These are ordinary Python functions, dataclasses and a small stateful class, not
a generic event framework, new cognitive part or separate body-control executive.

Nca8BodyRuntimeV1.configure_motor_targets explicitly constructs the helper.
The normal A0 runtime never calls it. The read-only motor_targets property is None
until configured. Reconfiguration is rejected rather than silently discarding
requests; a new owning BodyMap and stream generation are used at reset. Existing
BodyMap action-handoff ablation also disables H3 target formation.

Versions:

    nca8_body.py           0.3.0 -> 0.4.0
    nca8_body_targets.py   new, 0.1.0
    cca8_run.py            0.30.12 -> 0.30.13

The new production module is in the component inventory. --about now lists 64
components and 8 registered behavioral primitives. This updates the H1 inventory
assertion and the explicit NCA8 import manifest. Only the neutral motor-message
module is newly permitted for BodyMap and its helper; no legacy cognition import
is allowed. H1 messages, H2 physics, normal menus and all other NCA8 production
modules are unchanged.

## The actual transformation

BodyMovementRequestV1 contains a supplied task/application/envelope origin,
optional desired signed orientation and aggregate extension, and an at-most-eight-
tick lease. The orientation is relative to the existing gravity/surface reference;
it is not a body-relative offset, a posture predicate or a motor drive. Extension
is the declared aggregate actuator coordinate, not desired useful loading.

For each requested and available axis, BodyMap performs:

    bounded_goal = requested coordinate restricted to the capability range
    travel_budget = maximum_rate * tick_seconds * lease_ticks
    step_bound = min(capability.maximum_step, travel_budget)
    offset = bounded_goal - current measured coordinate, limited to step_bound
    endpoint = original measured coordinate + offset

The original request is retained, so a limited endpoint is not reported as full
satisfaction of the task requirement. One new target can make only a partial
contribution. If the available travel budget cannot even leave the target tolerance
while the goal remains outside it, the axis is withheld instead of proposing a
pointless already-achieved increment. A goal already within tolerance can describe
a set-point; it does not grant indefinite holding authority.

Nominal example, same supplied requirement for both bodies:

    requested: tilt toward 0 degrees; extension toward 0.60
    body A: +30 degrees, extension 0.40 -> offset -12, endpoint +18; extension +0.20
    body B: -30 degrees, extension 0.40 -> offset +12, endpoint -18; extension +0.20

An arbitrary supplied tilt goal of +45 from +30 instead gives a +12 adjustment
and +42 endpoint. The mapper does not secretly prefer upright. A smaller four-
degree orientation capability gives +26 rather than +18. These are controlled
mapping results, not biological calibration or proof of learned BodyMap geometry.

The capability-range comparisons use an explicit absolute 1e-12 allowance for
floating-point subtraction at endpoints. This prevents valid bounded requests
from being rejected by one-ULP cancellation error. It is not a movement-success
tolerance and does not relax the H1 sensor or physical-coordinate schema.

## Capability binding and evidence requirements

BodyAxisCapabilityV1 declares one family, an identifier, coordinate range,
maximum new-target step, permitted pursuit excursion, rate and tolerance.
nominal_body_capabilities_v1 returns the fixed H1 design values for explicitly
supplied fixtures:

    orientation: step 12 degrees; excursion 18; rate 60 degrees/s; tolerance 1
    extension:   step 0.20; excursion 0.25; rate 1 unit/s; tolerance 0.01

One family binds to one supplied capability. Duplicate families/identifiers are
rejected; omission makes only that capability unavailable. Ordering the tuple
differently changes no decision. Capability IDs do not claim that an H4 executor
has been implemented or registered. They are not task-IP selection or a test of
large-repertoire candidate access.

The new H3 mapping profile requires available signed tilt, current contact=True
and positive measured useful loading before proposing an orientation change.
There is no newly invented scalar loading threshold or stability classifier.
Contact=False with positive loading is explicitly inconsistent for that mapping.
Missing contact/load and valid no loaded support have different refusal reasons.

Extension requires its own current measured coordinate and capability but does not
require already-established contact: developing extension is a possible attempt
to acquire support. It cannot claim contact or useful loading afterward. Missing
tilt or contradictory support therefore need not suppress an independent extension
proposal. A measured coordinate outside the offered capability's operating range
is withheld, rather than claiming a feasible mapping from unsupported conditions.

These are conservative initial mapping conditions, not a proof that every proposed
movement is dynamically safe or will reach its endpoint. H4 must enforce current
feedback/protection during pursuit. H5 owns Righting's task-dependent contribution;
H3 cannot obtain private support geometry, disturbance labels or a complete task
solution from the H2 provider. The initial extension requirement is supplied at the
chosen aggregate coordinate scale; inverse mapping from richer load/limb relations
has not been invented here.

## Protected local body view and evidence timing

The helper accepts only canonical MotorFeedbackV1 or explicit None. It reads no
environment object, private physical state, coarse posture label or PNM.
MotorFeedbackV1.from_dict remains the existing strict external-packet decoder.

One current immutable acquisition is retained with its actual sample identity,
event tick and availability tick. Default admissible age is at most two ticks
from acquisition, not from the latest read. A repeated identical sample is a
reread and does not refresh time. A newer partial sample does not backfill missing
channels from the previous sample. Explicit None makes the current view unavailable;
the last record remains only for bounded-size ordering and diagnostic inspection.

A strictly older sample/event pair is ignored for current-state replacement.
Conflicting identity reuse, inconsistent event ordering, future availability and
wrong stream/generation raise before mutation. Such an exception is a rejected
input operation, not permission for a future motor driver to continue blindly.
The H4 driver must handle input faults and currentness before emitting a drive.

H3 has no access to the focal WNM or its source. Tests retain an earlier
FocalMotorEvidenceV1 while the local body receives a newer sample; the old focal
basis and original target endpoint remain unchanged. A new proposal can use the
newer body basis, but it does not mutate a previously reserved target.

## Proposals, reservations, cancellation and refinement

propose() stores one pending proposal but occupies no resource. Each requested
axis has exactly one bound target or explicit refusal. A new proposal replaces
only the preceding unreserved proposal. reserve() requires the mapper's current
original proposal and still-valid body basis. Exported, reconstructed, superseded,
foreign or previously reserved proposals cannot be replayed into reservations.

reserve() is body-side bookkeeping for an explicitly supplied execution fixture,
not acceptance of a cognitive handoff or installation of a motor executor. The
future H4/H6 integration must still validate actual task/envelope/receipt ownership
and authorize physical execution. A matching string or copied descriptive record
is not a physical permission. No live robot can be controlled by this H3 helper.

At most one current request exists per orientation/extension resource. The two
can coexist only under the same task/application/envelope and execution. Another
task is refused, not ranked or selected. A busy orientation axis can coexist with
a new compatible extension proposal without replacing its old target. This is the
minimal H3 resource rule, not completion of general multi-task PTD-022 arbitration.

validate_reservation() checks that the exact current owner-held record and lease
are still valid; retained or reconstructed copies cannot restore a request.
H4 must additionally check timely local sensing and protection before actuation.

cancel() releases only the named current resource. It does not erase a physical
effect or declare an executed failure. expire() retires due reservations; a
read-only reservations(at_tick=...) call already excludes expired leases even
before housekeeping runs. No output/reread/proposal implicitly renews an existing
lease. No current-body query advances the physical world or its clock.

refine() is deliberately narrow. It uses current admissible body evidence, keeps
the original body basis, excursion/rate/tolerance/correction bounds and expiry,
and permits only an endpoint inside the ORIGINAL endpoint tolerance band. That
band never moves with successive revisions. The new endpoint must also fit the
capability range and remaining nominal rate/time budget. Current body position
outside the original excursion requires refusal, not an expanded envelope.

A real refinement increments the revision and requires a later local tick; at most
one revision occurs per such tick. The original committed tick still denotes the
lease origin. updated_tick denotes the latest reservation change: while reserved
it is the revision event; a terminal record instead names cancellation or expiry.
A later revision cannot be backdated to the original commitment. No-op refinement
does not create a revision or renew time. These changes do not consume the future
SMP anomalous-correction counter or constitute learned calibration.

## Public entry points

    body = Nca8BodyRuntimeV1()
    mapper = body.configure_motor_targets(feedback.stream, nominal_body_capabilities_v1())
    mapper.update_feedback(feedback, at_tick=0)
    proposal = mapper.propose(
        BodyMovementRequestV1(origin, desired_tilt_degrees=0.0, desired_extension=0.60),
        at_tick=0,
    )

The separate reserve/refine/cancel/expire methods are exercised as nonexecuting
fixtures in this slice. No default runtime or menu calls them. New interface records
are BodyAxisCapabilityV1, BodyMovementRequestV1, BodyTargetBindingV1,
BodyTargetProposalV1 and BodyTargetReservationV1. Existing H1 target/message types
are reused rather than copied into a second schema.

## Tests and inspection

The new tests/test_nca8_body_targets.py collects 136 tests. Coverage includes:
mirrored pose and arbitrary goals; bounded extension; capability ordering/absence;
range, rate and lease narrowing; selective missing/contradictory evidence;
actual H2 reset/measurement consumption without mapper-driven movement; old
anchor and focal-snapshot preservation; currentness, duplicate and older arrivals;
resource ownership; proposal replay rejection; cancellation, expiry, fixed-band
refinement and revision time; reset/ablation isolation; unchanged A0 results;
frozen records/finite exports; malformed values/counters; and bounded long runs.
A seeded 400-case capability-range test covers floating-point endpoint arithmetic.
Task-origin label parity is a fixture test, not proof of acquired LP learning.

The permanent command-line review is:

    python scripts/review_nca8_body_targets.py

Its ten blocks show actual BodyMap calculations from supplied requirements and
sensor fixtures. Initial readings come from H2 resets; changed later readings
are labelled supplied fixtures. It issues zero motor commands. Both previous
H1/H2 review programs remain byte-identical and available.

## Validation and acceptance boundary

The accompanying VALIDATION.txt records exact extraction checks. Pylint/mypy are
unavailable in this review environment and must be checked locally. Missing Pyvis
causes two existing baseline/full-suite failures here; no test is skipped, weakened
or rewritten to hide that dependency. The complete 24-file local lint/type scope
and expected counts are in APPLY_AND_VALIDATE.txt.

This delivery is not local H3 GO, H4 feedback control, integrated Righting, learned
BodyMap calibration, A99 closure or default promotion. After the local wall and
manual review pass, commit H3 separately. The next planned slice is P18-H4:
deterministic target execution with rapid local feedback and its controls.
