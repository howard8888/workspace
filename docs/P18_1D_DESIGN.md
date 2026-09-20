# P18-0 / P18-1D: hierarchical Righting entry and implementation design

Date: 19 September 2026.
Scientific authority: accepted CCA8 Architecture v10.1.
Implementation authority: Planning v18, explicitly adopted in the current request.
Entry HEAD: e93c1192fe4095346b0c2c828606254bfac6055f (main).

## Current checkpoint: H2 committed; H3 requested

Howard supplied a clean checkout at 2c7994b2e6b9bafd19837cdcac603194506d2a5f,
with main/origin/main equal, and explicitly requested P18-H3. The preceding local
H2 wall and manual inspections passed. The H1 registry correction is already in
that H2 commit; it must not be reapplied. The original historical design/status
sections below are preserved. New section 11 records H3's bounded implementation
choices; docs/P18_H3_REVIEW.md describes the delivered candidate and its limits.

## Historical checkpoint: H1 committed; H2 requested

The issue-time review wording below is historical. Howard subsequently reported
all local H1 checks green, supplied the passing manual output, and committed/pushed
H1 as 1fc768a0c415fc5086e8aa27698ed88b17535059. His next explicit request authorizes
preparation of P18-H2 together with the omitted component-registry correction.
The original H1 commit is preserved; no commit is amended or replayed.

The registry corrections described below are applied in that forward H2 update,
not retroactively claimed to have been in the original H1 commit. The H2 provider
now uses the shared motor messages. See P18_H2_REVIEW.md for its implementation,
small API/timing refinements, tests and remaining local acceptance requirements.

## 1. Authority and exact source

Howard supplied an empty Windows git status, main/origin/main at e93c119, and
workspace(20260919-152940).zip. A separate extraction confirms the full HEAD above,
a clean tree, and the same recorded remote-tracking reference. No live remote was
queried. The archive SHA-256 is
3dbbe7b38eb94d435cf7c5a8722420ce86cac20927d75f5ab809d1615a5dd257.
It is byte-identical to the archive inspected for Planning v18 despite its later name.

P18-0 authority/source reconciliation is complete. Earlier accepted P16-0, 1R and 1E
work stays complete at its original scope. Earlier user-reported local validation is
not described as freshly run here. A fresh extraction test on Python 3.13.5 returned
1,661 passed and two failures at the existing unavailable Pyvis dependency; this is
not a green full local wall. The repository's Python 3.13/mypy configuration is kept.

The user explicitly requested preparation of the next software update, not merely
adoption of the document. This record supplies the concrete design for that review
candidate. Technical recommendation: GO for P18-H1 only. A separate user review of
these detailed API/physical-profile choices has not yet occurred: review this record
before applying the candidate patch. No user design approval, local H1 acceptance,
H2 implementation authority or A99 closure is invented by this record.

## 2. Scope and examined interfaces

Planning v18 sections 14, 16, 17, 24-29, 36.4-36.5, 38.2, 59 and 61.2 govern this
slice. Architecture v10.1 sections 31.6-31.7, 85, 88.1, 89.5-89.6 and 129.16-129.18
supply its functional constraints. The inspected source seams are:

- nca8_body: populated BodyTaskTargetV1, AuthorizedActionEnvelopeV1 and
  LowerActionRequestV1, plus Nca8BodyRuntimeV1.authorize_application.
- nca8_primitives: TaskActionV1, PrimitiveApplicationV1 and StandUpIPV1.
- nca8_contracts: CircuitTimingV1, CyclePhase and CycleCommitmentV1.
- nca8_handoff: Nca8InternalHandoffV1 and consume-before-external-effect semantics.
- nca8_adapters: environment_token_for_task_action_v1 and detached input admission.
- nca8_runtime: the separated cognitive runtime and external episode runner.
- cca8_support_world: advance_support_world_v1 and support_observation_packet_v1.

None of these implementations was changed in the original H1 commit. Their old
None, policy:stand_up, posture_support_v1, event_cycle and receipt meanings stay
intact. The forward H2 correction lists both H1 production modules in the diagnostic
component registry; the H2 motor provider is an explicit separate mode.

Only immutable contracts and pure validation/projection helpers are implemented.
There is no installed executor, motor/body provider, Righting transform, learner,
new clock, mutation of a cognitive source, new WNM, or live authorization path.

## 3. Concrete H1 module/API decision

cca8_motor_contracts.py is a neutral standard-library-only boundary, shared by the
future physical provider and NCA8. It contains MotorStreamRefV1, MotorCommandV1 and
MotorFeedbackV1. The world receives only the command, never a task, target or PNM.

The canonical sensor schema is body_motor_feedback_v1. It carries a stream and
reset generation, positive sample identity, nonnegative event and availability ticks,
gravity_surface_planar_v1 frame, signed tilt in degrees, normalized aggregate
extension, optional Boolean support contact, normalized useful loading and
normalized destabilization. Missing scalar channels are None, never invented zero.
An absent whole report is not a no-contact report. Strict decoding rejects unknown
keys, wrong units/frame/schema, Boolean numerics and nonfinite/out-of-range values.

The command schema is body_motor_command_v1. It carries stream/generation, command
number, issue tick and two normalized signed drives in [-1, 1]. It is one interval's
command, not a continuing task. A future provider checks the expected stream/tick
and previous command number before applying it. H1 supplies that pure check, not
a live command queue or exactly-once actuator guarantee.

nca8_sensorimotor_contracts.py contains TargetOriginV1, BodyRelativeTargetV1,
CommittedBodyTargetV1, FocalMotorEvidenceV1 and LocalTargetReportV1, plus the two
SensorimotorTargetKindV1 values, LocalTargetDispositionV1 and TargetDirectiveV1.
Targets retain task/application/envelope identity and the immutable sensed body
basis. A committed-target description additionally has execution identity and a
finite issue/expiry interval. Descriptive records and their JSON exports cannot
install a target, reconstruct a receipt, grant live permission or select a task.

Each type has a concrete consumer in H2 (command/feedback), H3 (body target), H4
(committed target/local report/directive), or H6 (detached focal evidence). The two
production modules are listed in the host diagnostic component registry, but H1 adds
no new runtime actor and no behavioral primitive.

## 4. Target semantics and bounds

Two supplied-target families are fixed for the first experiment:

- ORIENTATION_ADJUST: signed change from the measured planar tilt; endpoint in
  [-90, 90] degrees. Nominal request: up to 12 degrees, tolerance 1 degree,
  commanded rate limit 60 degrees per simulation second, maximum permitted
  excursion 18 degrees from the immutable starting basis.
- SUPPORT_EXTENSION: signed change from the measured aggregate extension;
  endpoint in [0, 1]. Nominal request: up to 0.20, tolerance 0.01, rate limit
  1.0 normalized unit per simulation second, permitted excursion at most 0.25.

Targets may use smaller bounds. H1 permits explicit finite variants within the
physical-coordinate ranges and maximum motor rates (90 degrees/s and 1 unit/s),
so a wrong-but-feasible target remains testable. A target with an out-of-range
endpoint, excessive request displacement or invalid tolerance is rejected rather
than clipped into a different request. Nominal values are engineering assumptions.

An offset is always added to the saved basis, never to a later body sample. Thus
+30 degrees with offset -12 targets +18; later sensing +25 still means target +18,
not +13. The mirrored -30/+12 case targets -18. The new signed measurement is not
manufactured from the old undirected v1 angle.

The lease is [committed_tick, expires_at_tick), at most eight ticks. At expiry,
no fresh pursuit is permitted. At most two anomalous corrections are allowed;
ordinary error tracking is not a counted retry. No new target/output implicitly
renews a lease. Two resources can coexist only inside an explicitly common envelope;
actual occupancy and installation ownership remain H4, not a Boolean on a record.

## 5. Proposed H2 physical profile, frozen for review before implementation

The first physical state is signed tilt theta in [-90, 90] degrees and aggregate
extension e in [0, 1]. Upright is theta=0. One external support surface has normalized
required reach h=0.25 and a presence flag. These are evaluator/provider parameters;
cognition sees sensed consequences, not the forcing label or h as a task solution.

Let c=cos(theta in radians). Support reach is e*c. Contact exists only when the
surface is present and reach >= h. Useful loading is zero without contact;
otherwise L=clip((reach-h)/(1-h), 0, 1). These simple aggregate geometry choices do
not identify a leg, a muscle or a contact polygon.

For each dt=0.05 interval, using the previous physical loading L:

    e_next = clip(e + dt * extension_drive, 0, 1)
    angular_rate = 90 * orientation_drive
                   + 12 * sin(theta) * (1-L) + external_angular_rate
    theta_next = clip(theta + dt * angular_rate, -90, 90)

Recompute contact and L from the new geometry. The proposed destabilization readout
is clip(abs(sin(theta_next))*(1-L_next) + abs(angular_rate)/180, 0, 1).
All trigonometric arguments use radians after conversion from the represented degrees.
Surface absence, actuator blocking/motor-off, and externally applied angular forcing
are independent adverse conditions. Provider action saturation and external forcing
are not equivalent to a controller choosing another target. Zero drive does not stop
gravity; aggregate extension is retained by the nominal actuator rather than
silently restoring support. The provider never reads Righting, target achievement,
PNM, a stage counter or task-completion thresholds.

Calculated one-interval illustration (not an implemented H2 experiment): initial
+30 degrees, e=0.40, surface present, drives -0.5/+0.5 gives approximately
+28.0114 degrees, e=0.425, L=0.166951, destabilization=0.612191. Remove the surface
and sensed contact/loading differ even though extension still changes. A successful
extension target without a surface is not successful Righting.

These equations are a proposed functional surrogate, not goat biomechanics. H2 must
validate nominal competence, passive behavior, mirrored forcing, independent drive
channels, saturation, contact absence and no-task-label dependency before acceptance.
A numerical refinement must be recorded and reviewed rather than hidden in H2 code.

## 6. One timebase and two feedback consumers

Integer tick k names boundary time k*0.05 simulation seconds. A command issued at k
applies only over [k, k+1). Sensing after that interval names physical event k+1.
The nominal delayed report becomes available at k+2 (one sensor-delay tick after
its event). H1 permits declared nonnegative availability delays; H2 enforces the
chosen profile. A reset acquisition may be available at its event time. No record
increments a clock or rewrites CyclePhase, CircuitTimingV1 or event_cycle.

At a local update, the future executor may use the newest eligible report within its
explicit age limit. Re-reading a still-usable cached report is not a new observation
or another confirmation. A scheduled but not-yet-due report is not evidence. During
startup or dropout with no usable report, issue no new drive. Retain diagnostics for
at most two ticks, then stop/expire as appropriate. Feedback validity and expected
local consequences remain different objects.

An H1 FocalMotorEvidenceV1 is a frozen, detached diagnostic projection of an admitted
sensor record with a focal cycle and cutoff. It rejects availability after the cutoff
and preserves the original physical sample identity. It neither admits itself to the
old runtime nor replaces POSTURE-SUPPORT. H6 must select the correct due record and
avoid counting local and focal use as independent physical acquisitions.

Nominal focal spacing is four ticks. Fixed-horizon controls use 1/4/8 ticks between
focal calls, with unchanged dt, perturbation schedule and physical duration. There
are at most four routine local samples per target, four significant-event latches,
sixteen staged deliveries, 80 lower ticks/4 seconds for the Righting qualification,
and 20 focal opportunities. These runtime bounds are future consumer obligations;
H1 contains no history, queue or trial runner pretending to enforce them.

## 7. Target directives, first attempts and dispositions

NO_NEW_TASK_OUTPUT does not cancel, renew or create a target. A valid previously
installed target may continue only until its original expiry. INSTALL_TARGET,
REPLACE_TARGET and CANCEL_TARGET are distinct future owner operations. Neutral
motor output is not physical safety. Changing the target must have its own revision
and authorization; none of these enum values by itself performs the operation.

A fresh single body sample can support a conservative feasible target where signed
pose, extension, capability and required contact evidence suffice. Missing rates do
not become zeros. H5 will not require a previous failed attempt to permit a newborn
first attempt. Missing essential body evidence withholds the affected request.

Local reports distinguish pending, active, partial, achieved, blocked, unavailable,
cancelled, interrupted, expired and unresolved. ACHIEVED requires an available
matching measurement inside the supplied target tolerance; it has no task-success
meaning. Late feedback can describe an earlier physical event but cannot reactivate
an expired pursuit or make old evidence current. H6 minimum task results are running,
supported candidate, interrupted, expired or unresolved; complete corresponding
progress/dwell and routed interpretation remain P16-1G. Three distinct supported
task samples must span at least eight ticks for the planned dwell test.

## 8. Nominal and adverse hierarchy timelines

Nominal, prospective integration (H5/H6, not executed at H1): the eligible source
contains observed signed tilt +30 and extension 0.40 with sensed contact. Righting
organizes partial support development; a sparse PNM projects improvement, while a
separate task requirement reaches BodyMap. BodyMap proposes offsets -12 and +0.20
from that actual body basis. The authorized executor receives targets +18 and 0.60,
not a standing flag. After installation it issues bounded drives; sensed physical
consequences become locally available after the declared delay. A later focal
summary retains those original event IDs and updates the same source. Task outcome
still requires activity-relative evidence and dwell.

Adverse: the external harness removes the support surface at a fixed physical tick.
A subsequently available report says contact=False and loading=0. Local extension
can nevertheless be achieved. The current target/expectation comparison can stop or
narrow pursuit, and preserve a bounded significant event for later source relevance.
It cannot fabricate contact, rewrite the earlier PNM, select a new task or fall back
to legacy stand-up. If the report is absent instead, the result is unknown and the
finite missing-feedback rule applies, not the no-contact interpretation.

## 9. Predeclared tests and controls

H1: strict type/range/Boolean checks; fixed anchors; JSON detachment; event/availability
ordering; wrong stream/generation/revision rejection; local achievement versus support;
no source/world/RNG mutation; unchanged actor startup and old fixtures. The H2
correction lists the two new production modules. Neutral messages may now be
imported by the physical provider without constructing a new actor.
H2: independent fixed commands and passive/motor-off/no-surface controls.
H3: mirrored bodies, constrained increments, wrong targets and missing capability.
H4: fixed-target execution, angular perturbation of +6 degrees at a fixed tick,
local residual thresholds 5 degrees/0.04 extension, feedback delay/dropout, two-attempt
limit, target expiry and duplicate installation rejection. The local command-conditioned
expectation must have a consumer in residual protection; removing that route must
change the corresponding residual/escalation result, not merely a printed field.
H6: Righting-off preserves sensors and lower capability; mapping-off/wrong-target
preserves the executor; SMP/motor-off preserves the task; feedback and local-prediction
ablations preserve the same plant; PNM-route ablation tests prospective evaluation,
not an unsupported claim that no movement can occur without PNM.

Record target error, contact/loading, maximum tilt/destabilization, cancellation and
expiry reasons, command/update counts, elapsed time and task/evidence correspondence.
No successful curve alone establishes prediction, learning, biological uniqueness or
A99. The intended ordering remains H1 -> H2 -> H3 -> H4 -> H5 -> H6-A -> H6-B -> 1G.


## 10. H2 implementation refinements, 19 September 2026

The numerical physical laws and nominal values in section 5 are unchanged.
MotorWorldV1 is an ordinary class added to cca8_support_world.py; the existing v1
functions are retained. HybridEnvironment.reset_motor/step_motor/observe_motor
select the new experiment explicitly, without changing normal reset/step or
posture_support_v1. No new general simulator, interface layer or event bus is added.

The profile fixes dt for the instance. Nominal dt remains 0.05 seconds; explicitly
selected 0 < dt <= 0.05 variants support resolution tests without hidden substeps.
A maximum of sixteen sorted nonoverlapping physical intervals supplies external
angular forcing, surface removal and/or whole-acquisition dropout. Surface removal
applies at the beginning of the named interval, so the previous geometry's loading
is recomputed under that physical surface condition before gravity is integrated.

Commands at k act during [k,k+1); acquisition is at k+1 and nominal availability
at k+2, exactly as section 6 specifies. Constant delay may explicitly be 0-16 ticks.
A reset reading is immediately available. The provider returns only due records;
observe_motor rereads the latest delivered record without new time or identity.
At most sixteen future readings remain staged between updates. A dropped acquisition
does not erase earlier in-flight evidence; explicit channel loss produces None.

Unavailable motors suppress only their commanded drive. Gravity and external
forcing remain, and neutral extension is retained by the stated actuator model.
The destabilization formula uses the declared pre-saturation angular-rate proxy,
not an invented measured velocity. These limitations remain explicit in H2.
The phase demonstrates physical response to supplied drives, not target following,
Righting, learning, or the complete prediction-action hierarchy.


## 11. H3 implementation decisions, 19 September 2026

The physical equations, H1 messages, eight-tick maximum lease and nominal target
parameters remain unchanged. BodyMap owns an opt-in helper implemented in the
normal Python module nca8_body_targets.py. It maps supplied absolute planar
orientation/aggregate-extension requirements by subtracting the current measured
coordinate and limiting the result to the capability range, maximum step and
nominal rate/time budget. This is a partial target, not a full task solution.

Orientation requires available tilt, contact=True and positive measured loading.
Contradictory contact/loading or missing support withholds that axis. Extension
can still be proposed from its own available coordinate without prior contact;
no contact or load is fabricated. The default local freshness bound is two ticks
from acquisition. A new partial sample does not backfill its missing channels,
and a duplicate cannot refresh its event time. This mapping profile is an H3
engineering choice, not a biological threshold or full dynamic-safety guarantee.

One supplied capability binds to each family; an absent family is withheld. At
most two BodyMap-side reservations share one task/application/envelope/execution.
Proposals do not reserve resources and reservations do not install an executor.
H4/H6 still check the real handoff and current feedback before movement. No new
autonomous selector or generic event/resource framework is added.

Local refinement keeps the original anchor and expiry and stays within the original
endpoint tolerance band and capability/excursion bounds. That band cannot ratchet.
A changed endpoint receives a new revision at a distinct later local tick; no-op
refinement renews nothing. Cancellation releases only the named axis. Queries
exclude an expired lease even before explicit expiry housekeeping. Diagnostic
records cannot restore a target. These are tested H3 interface behaviors, not
implemented H4 execution or learned BodyMap calibration.

The new module is registered, yielding 64 components with the existing eight
behavioral primitives. All prior NCA8 production modules except the small BodyMap
ownership addition remain unchanged. The H3 review uses supplied task/sensor
fixtures, issues no motor commands, and needs its own local validation/manual GO.
