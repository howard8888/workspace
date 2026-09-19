# P18-H2: command-driven body simulator and the H1 component-report correction

Date: 19 September 2026.
Scientific authority: accepted Architecture v10.1.
Implementation authority: adopted Planning v18, especially sections 17, 28, 38.3 and 61.2.
Entry: 1fc768a0c415fc5086e8aa27698ed88b17535059, clean main.
Status: software review candidate; local validation and manual GO remain required.

## Source and scope

The supplied workspace(20260919-165311).zip and fresh Windows terminal identify
committed/pushed P18-H1 at 1fc768a. A separate extraction agrees on the full HEAD,
clean tree and recorded origin/main. No live GitHub request, user commit amendment,
revert, dependency change or alteration of the supplied archive is performed.

The prior H1 mypy fix is already committed. The previously offered standalone
component-registry patch is NOT a prerequisite: its correction is included here.
Both shared H1 modules belong to the project and now appear in the normal report.
The count changes from 61 to 63; registered behavioral primitives remain 8.

This implements H2 only. Fixed commands make a small physical body move and
produce time-qualified sensing. No BodyMap target selection, target-following SMP,
feedback correction, Righting transformation, task PNM, learning or default-mode
promotion is added. Those remain H3, H4, H5/H6 and the later learning programme.

## Ordinary Python modules and public methods

The simulator is added to the existing cca8_support_world.py. Three small frozen
dataclasses describe physical starting coordinates, a physical-time perturbation
and fixed experiment settings. MotorWorldV1 is the stateful simulator; there is
no abstract base class, protocol hierarchy, general event bus or new dependency.
It reuses the existing MotorCommandV1 and MotorFeedbackV1 definitions unchanged.

HybridEnvironment in cca8_env.py provides:

    reset_motor(stream_id=..., profile=None) -> MotorFeedbackV1
    step_motor(command=None) -> tuple[MotorFeedbackV1, ...]
    observe_motor() -> MotorFeedbackV1
    motor_body -> MotorBodyStateV1              [external inspection only]
    motor_elapsed_seconds -> float             [physical time]

Motor mode is explicitly selected by reset_motor, not by changing normal startup
or silently reusing an old scenario. The existing EnvConfig, normal reset/step,
FSM and v1 support equations retain their original meanings. Normal reset ends
motor mode; motor reset increments its generation and discards all old deliveries.
Normal step/observe/state access in motor mode is rejected: the old storyboard
fields do not describe this body. Conversely, a motor command cannot advance an
ordinary scenario. Invalid mode/command/profile requests fail before side effects.

step_motor returns only newly delivered reports. It can return an empty tuple while
the body has moved. That is not a no-contact measurement. observe_motor returns the
latest delivered event without a new acquisition; after delay/dropout it is older
than the physical body. Agent-side H3/H4 readers must check its time and identity.

## Physical equations and declared approximations

The numerical laws from committed docs/P18_1D_DESIGN.md are retained:

    theta: signed tilt from upright, -90 through +90 degrees
    e: aggregate support-extension coordinate, 0 through 1
    h: normalized required surface reach, nominal 0.25
    reach = e * cos(theta)
    contact = surface_present and reach >= h
    loading = clip((reach - h) / (1 - h), 0, 1), or zero without contact

    e_next = clip(e + dt * extension_drive, 0, 1)
    angular_rate = 90 * orientation_drive
                   + 12 * sin(theta) * (1 - loading)
                   + external_angular_rate
    theta_next = clip(theta + dt * angular_rate, -90, 90)

Recompute contact/loading from the new coordinates. The destabilization readout is:

    clip(abs(sin(theta_next)) * (1 - loading_next) + abs(angular_rate) / 180, 0, 1)

Trigonometric calls convert degrees to radians. This last readout deliberately
uses the specified pre-saturation angular-rate proxy; it is not a measured joint
velocity, validated instability probability or task-success score. Full drive is
90 degrees/s or 1 extension unit/s; external forcing/passive drift are separate.
A missing surface changes loading before the interval's drift calculation.

Nominal tilt +30, e=0.40, drives -0.5/+0.5 and dt=0.05 give, after one interval:

    tilt            +28.01143593539449 degrees
    extension         0.425
    useful loading    0.16695052702710544
    destabilization   0.6121914026076246

These are computed body/sensor values, not copied target answers. Extension can
reach 0.60 while contact remains False and useful loading is zero. The simulator
contains no standing flag, local achievement result, task-completion threshold,
Righting token, automatic recovery trajectory or feedback-based choice of drive.

Blocked/unavailable motors suppress their respective commanded drive only.
Gravity and external forcing remain; blocked orientation drive does not pin the
body in space. With neutral extension drive the aggregate actuator retains its
coordinate. That declared holding competence does not imply useful support.
Saturation clamps the physical coordinates, never an invalid input or a target.

## Time, sensing and bounded storage

The profile fixes dt for the whole instance. Default 0.05 seconds and explicitly
selected 0 < dt <= 0.05 variants are supported; there is no hidden subdivision.
Tick k identifies boundary time k*dt. A command at k applies to [k,k+1). The
post-step measurement is event k+1, sample k+2; nominal delivery is at k+2.
The reset acquisition is sample 1 at event/availability 0.

An explicitly selected constant sensor delay may be 0-16 ticks. At most sixteen
future deliveries are stored between calls, and only due records are returned.
The simulator retains the latest delivered reading for read-only observation.
It stores no full movement history, NavMap snapshots, PNM or cognitive memory.
Local/task lifetimes are not implemented by this physical provider.

At most sixteen sorted, nonoverlapping MotorWorldPerturbationV1 intervals can
supply angular forcing, surface removal and/or whole-acquisition dropout. Their
start/stop ticks identify physical integration intervals, not task/command counts.
The manual disturbance applies +120 degrees/s during [2,3), adding six degrees
over the nominal 0.05-second interval. Commands are identical in the comparison.
There is no feedback correction in H2; the effect is observed, not corrected.

Dropout removes only acquisitions during the named intervals; already acquired
readings in transit can still arrive. Sample numbers therefore show gaps after
dropout. A separate unavailable_channels tuple masks specified channels with None.
Valid contact=False, missing channel=None, and no newly delivered report are three
different conditions. Invalid external packets remain rejected by the H1 decoders.
The simulator itself never intentionally fabricates malformed sensor packets.

Command IDs must increase within the correct stream/generation and match the
current interval. Gaps are allowed; duplicates/reversed IDs and wrong time fail.
All new state and deliveries are computed and validated before local replacement.
In this synchronous in-memory provider, rejected inputs/calculation failures leave
state/time unchanged. This is not an exactly-once hardware-delivery guarantee.

The review helper caps every fixed run at 80 intervals. The provider itself is not
an overall Righting budget manager; task/target horizons are still later work.
Reset invalidates old command generations and discards pending readings. Separate
world instances share no mutable state or random generator.

## Registry, versions and retained source

    cca8_run.py             0.30.11 -> 0.30.12
    cca8_env.py             0.7.0   -> 0.8.0
    cca8_support_world.py   0.1.0   -> 0.2.0

The two H1 message/target modules remain version 0.1.0 and their code is unchanged.
Both now appear in the component inventory. Since the simulator extends existing
modules, the total is 63, not 64. No new behavioral primitive is registered.
The H1 commit and its historical review evidence remain intact; its documentation
now records the subsequent local acceptance and the forward registry correction.

The retained support-provider import test permits exactly one additional neutral
module, cca8_motor_contracts. New tests check that it does not import cognition.
The H1 startup test still rejects eager NCA8 imports; it no longer incorrectly
forbids the physical module from importing shared motor-message definitions.
No import-firewall allowance for NCA8 cognition is broadened. Old v1 fixture files,
public packet keys, binary actions, source dynamics and A0 traces are unchanged.

## Tests and manual inspection

The new tests/test_nca8_motor_world.py collects 114 tests covering independent
sign/magnitude response, frozen equations, passive motion, mirror symmetry,
contact/loading, support absence, blocked drives, physical saturation, physical-time
forcing, command-number independence, sensing delay/dropout/channel loss, finite
storage, exact replay, read-only observation, RNG and instance isolation, invalid
inputs/time/generation, reset/mode switching, and the shared environment path.
The manual program is also executed twice for deterministic output in the tests.

Run from the repository root:

    python scripts/review_nca8_motor_world.py

Its nine blocks show real physical response to preset commands, not a Righting
success banner. It is a permanent review program. The H1 review helper remains
unchanged. H4's later menu workflow can call shared functions; no new menu entry
is needed for this interim physical-only experiment.

## Validation and acceptance

See the accompanying APPLY_AND_VALIDATE.txt and VALIDATION.txt for exact commands,
results, tool availability and expected local counts. The current source candidate
must pass the local pytest/Pylint/mypy/preflight wall and this physical inspection
before H2 GO. A review-host missing dependency is not permission to skip its tests.

After local H2 acceptance, commit this as one forward update. P18-H3 is next:
BodyMap computes body-relative targets from current evidence. H4 then consumes
those targets with local feedback control. This physical provider does neither.
