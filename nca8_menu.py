#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimental terminal menu for the isolated new CCA8 runtime.

The module is imported lazily only after the user explicitly chooses NCA8 from
Main Menu #1. It receives and returns only ``Nca8SessionV1``; the legacy world,
drives, Ctx, PolicyRuntime, WorkingMap, WorldGraph, and autosave path never
cross this composition boundary.
"""

from __future__ import annotations

import cca8_cli
from nca8_runtime import Nca8SessionV1
from nca8_trace import render_flow_trace_lines_v1
from nca8_hierarchy_demo import run_hierarchy_review_menu_v1
from nca8_righting_demo import run_righting_preview_review_v1
from nca8_sensorimotor_demo import run_sensorimotor_review_menu_v1

__version__ = "0.10.0"
__all__ = ["run_nca8_experimental_menu_v1", "__version__"]


_INTRODUCTION_V1 = """Current checkpoint: A0 / retained Gate A.
Accepted Architecture v10.1 and Planning v18 govern new work.
Options 1-5 retain Gate A; option 6 reviews P18-H4 supplied-target motor control.
H4 is not yet integrated Righting or a new default cognitive runtime.
Option 7 runs the H5 relational Righting preview without installing targets or moving a body.
Option 8 runs the separate H6-A integrated hierarchy with finite targets and actual local movement.
H6-B qualification and P16-1G task outcomes remain open.
Planning v16 P16-1R-B separates internal handoff and cycle closure from the
external world step and returning-input admission. Gate-A decisions are unchanged.

This demonstration runs a short sequence of NCA8 cognitive cycles for the
newborn goat's StandUp task. A fixed maximum number of cycles prevents the
demonstration from running indefinitely.

A developmentally seeded POSTURE-SUPPORT NavMap already exists when a session
is created. Current body and physical-support evidence updates that NavMap's
present NM configuration. The durable innate NavMap itself is not rewritten
by every new observation.

If physical support is inadequate, Attention can make the current
POSTURE-SUPPORT configuration the focal working representation, the WNM.
Navigation can then select the StandUp Instinctive Primitive (IP), and a
Projected NavMap (PNM) is created to represent what that operation expects
to happen.

Most NavMaps represent relationships in an allocentric-compatible form.
BodyMap converts the task-relevant NavMap relationship into a body-relative
representation -- i.e., converts an allocentric NavMap mapping into an
egocentric BodyMap mapping. Gate A uses a simple task-to-body scaffold here,
not a complete geometric coordinate transformation.

For this Gate-A StandUp task, BodyMap looks at its current representation
of the goat's body -- including posture, physical support, and body-ground
contact -- and checks whether a STAND_UP command is appropriate. The rule is
simple: a goat currently observed as fallen with inadequate physical support
may attempt to stand. Missing or out-of-date body evidence cannot permit it.

If BodyMap permits the action, the cognitive runtime commits the STAND_UP
request and hands it to the internal lower-action boundary. After the internal
cognitive cycle closes, the outer runner sends the accepted request to the
simulated environment. The Authorized Action Envelope records body permission;
the separate handoff receipt controls one-time consumption. Neither proves
execution success. Later sensory evidence can be matched back to the attempt.

The next or a later sensory input -- i.e., later body evidence -- determines
whether that StandUp attempt succeeded or failed. The STAND_UP command itself
never proves that the goat actually stood up.

This Gate-A demonstration uses only the NCA8 cognitive modules. The legacy CCA8
controller does not choose, replace, or rescue the NCA8 action. The
Sequential/Error Correcting (SEC) Module, WorldIndex, and durable learning
or plasticity are not yet active in this demonstration."""

_STATUS_KEY_V1 = """Session / isolated
  One self-contained NCA8 working instance. It owns its changeable cognitive
  state separately from legacy CCA8 and other independently created NCA8 sessions.

Generation
  Starts at 1 when a new session is created. Resetting that same session advances
  this number. Option 5 creates another fresh session, starting at generation 1.

Environment run
  A run of the simulated environment, beginning with an environment reset.
  This is simulator bookkeeping, not a cognitive episode or an episodic-memory
  boundary. This demonstration recreates the environment when the NCA8 session
  is reset, so its environment-run counter starts at 1 again.

Seed
  The number used for reproducible runs. The same starting state, seed, sensory
  inputs, and logical timing should produce the same results.

Cognitive cycles completed / pending observation
  A cycle processes available input, updates representations, chooses an action
  or NO_ACTION, accepts its handoff, and closes. The outer driver then advances
  the world and admits the next observation. Pending input is not evidence
  already used; a failed boundary can leave no pending observation.

Attention / last Attention decision
  Attention chooses the NM configuration to focus on, not the primitive action.
  Its last decision can be to switch, maintain, or release that focus.

WNM -- Working Navigation Map
  The one source-linked focal working representation used for the current task.
  There is no WNM when Attention has selected no source configuration.

Navigation / selected primitive
  Navigation maintains the WNM and selects the task-level primitive to apply.
  This checkpoint uses the StandUp Instinctive Primitive (IP); Learned Primitives
  (LPs) are not yet implemented in this NCA8 demonstration.

PNM -- Projected NavMap
  Represents what the selected operation expects to happen. It is a prediction,
  not an observation showing that the expected result has already happened.

Body-to-environment action handoff
  BodyMap converts the task-relevant allocentric NavMap mapping into an egocentric
  BodyMap mapping. Gate A uses a simple scaffold for this conversion. It then
  checks its current body representation before permitting a STAND_UP command.
  Disabling this handoff blocks the task action, but NO_ACTION still advances
  the simulated environment.

Read-only support measurements
  The P15-1E-A inspection option. When enabled, supplied support measurements can
  be inspected without changing action selection. The menu does not turn it on.

Durable innate POSTURE-SUPPORT NavMap
  The developmentally seeded organization for body and physical-support relations.
  The suffix @r1 means durable revision 1. New observations update its current
  NM configuration without creating a new durable revision each time.

Current posture / physical support
  What the current POSTURE-SUPPORT NM configuration represents about the body.
  Before the first cognitive cycle, no body observation has yet been processed.

Last StandUp prediction outcome
  Whether later body evidence confirmed or contradicted an earlier StandUp
  expectation. It is not a success claim made by issuing the action command.

Trace entries retained
  How many explanatory entries are still held, followed by the maximum capacity.
  One cognitive cycle produces several entries. When the capacity is exceeded,
  the oldest entries are discarded and the newest ones are retained."""

_RESET_EXPLANATION_V1 = """This creates a fresh working NCA8 demo session, or resets the current one.

"Isolated" means that this NCA8 demo session owns its own changeable cognitive
state. It does not share or alter the cognitive state of the legacy CCA8
session or of another independently created NCA8 demo session.

Resetting the session:
  - replaces its changeable NCA8 state and clears its previous trace;
  - advances the generation number of that same NCA8 session;
  - starts a fresh simulated environment run;
  - initializes the developmentally seeded POSTURE-SUPPORT NavMap; and
  - prepares Observation_1 as the next sensory input to be processed.

A newly created session starts at generation 1. The environment is recreated
on reset, so its environment-run counter also starts at 1 again.
This reset is not a new cognitive episode or an episodic-memory boundary."""

_CYCLE_EXPLANATION_V1 = """This advances the current isolated NCA8 session by exactly one cognitive cycle.

One cognitive cycle:
  1. takes the next waiting sensory observation;
  2. updates the NCA8 representations that are allowed to use that observation;
  3. lets Attention choose the focal NM configuration;
  4. lets Navigation select a task-level primitive when appropriate;
  5. creates a PNM when an action is expected;
  6. lets BodyMap map and check the proposed body action;
  7. commits and accepts the permitted action, or NO_ACTION, internally;
  8. completes Phase F, scheduler housekeeping and internal cycle closure;
  9. advances the external simulated world once through the outer driver; and
 10. admits and buffers the resulting observation for the next cognitive cycle.

Only one cognitive cycle is run. The session is then left in its new state so
you can inspect it or run another cycle manually.

With the same starting state, sensory inputs, seed, and logical timing, this
NCA8 implementation is designed to produce the same result again."""

_TRACE_EXPLANATION_V1 = """This shows the saved trace as narrated text and a cycle-by-cycle flowchart.
Read each cycle's boxes from top to bottom. Numbered explanations and technical
details follow that cycle's diagram, in the same record order.

Parts-first diagrams name CCA8 components and show INPUT, DO and OUTPUT.
Representations have bracketed outlines; software services and temporary
scaffolds have dashed outlines. Python implementation details are below the
main diagram. Arrows between boxes show record order, not signal wiring;
follow the named input source and output destination for the data path.

Phase C is shown as C1 (apply input and update current representations) followed by C2 (resolve
earlier-operation outcomes using the updated evidence). These are display
subsections of the existing Phase C, not additional scheduler phases.
Unnumbered context notes explain the source code; they are not trace events.

It shows session setup and the cognitive-cycle entries that are still retained
since the session was created or reset.

After option 3, it shows the retained entries from all the cycles you have run
in that session, not just the last cycle. After option 5, it shows the retained
entries from the fresh Gate-A StandUp demonstration.

The numbered flowchart shows retained execution, not a proposed architecture.
DOMAIN labels distinguish cognition, runtime infrastructure, the lower-action
boundary, the external body/world and the input boundary. A cycle/phase heading
only groups recorded labels; it does not make the simulator part of cognition.
The internal cycle now ends after handoff, Phase F and scheduler housekeeping.
Separate outer records show the world step, input admission and buffering.
The world call really occurs after internal closure; this is not a display-only
reordering. Input admission filters once; later buffering does not filter again.

An unnumbered reference schematic is not an additional set of trace events.
Older saved traces keep their historical combined-boundary explanation.
Missing records and unknown events stay visible; no missing steps are invented.

A fixed entry limit prevents the trace from growing indefinitely. Oldest entries
are discarded when the limit is exceeded, so a long session may no longer show
its setup or earliest cycles. One cycle produces several trace entries.

Showing the trace is read-only. It does not run another cognitive cycle,
change the NCA8 session, or influence any cognitive decision."""

_GATE_A_EXPLANATION_V1 = """This creates a fresh isolated NCA8 session and automatically runs successive
cognitive cycles until the Gate-A StandUp demonstration succeeds or reaches
its fixed maximum number of cycles.

It replaces the session previously displayed in this menu, including its trace.
Existing session settings are kept. A new session starts at generation 1.
Use option 3 instead to advance the existing session by just one cycle.
After the demonstration, option 4 shows the retained explanatory trace."""


def _print_panel_v1(title: str, explanation: str) -> None:
    """Print display-only heading and explanation without consulting cognition.

    This helper never creates a session, advances the environment, or writes to
    the trace. The menu still owns the existing create/reset/step/run choices.
    """
    print()
    print(title)
    print(cca8_cli.MENU_RESPONSE_DIVIDER)
    print(explanation)
    print()


def _print_status_v1(session: Nca8SessionV1 | None, *, include_key: bool = True) -> None:
    """Explain the existing read-only status fields without changing their values.

    The displayed environment-run number is the existing environment counter,
    not a new cognitive-episode counter. Internal field names remain unchanged.
    Creation/reset confirmations omit the longer term key; option 1 includes it.
    An absent session is reported without constructing a session just to inspect it.
    """
    _print_panel_v1(
        "NCA8 ISOLATED SESSION STATUS",
        "This screen shows the current state of the experimental NCA8 session.\n"
        "The NCA8 session is separate from the legacy CCA8 cognitive runtime.",
    )
    if session is None:
        print("No NCA8 session has been created yet.")
        print("Option 2 creates one. Options 3 and 5 also create one when needed.")
    else:
        status = session.status()
        config = session.config
        print(f"Session generation: {status.lifecycle_generation}")
        print(f"Environment run: {status.environment_episode_index}")
        print(f"Reproducibility seed: {status.seed}")
        print(f"Cognitive cycles completed: {status.cognitive_cycles}")
        if status.pending_input_available:
            print(f"Next sensory input waiting to be processed: Observation_{status.pending_observation_number}")
        else:
            print(f"No next sensory input is available (expected Observation_{status.pending_observation_number}).")
        print(f"Internal handoff: {status.handoff_disposition or '(none yet)'}; receipt: {status.handoff_receipt_id or '(none)'}")
        print(f"Latest external execution: {status.execution_status} (not a task-success verdict)")
        print(f"Reset required before further cycles: {'yes' if status.reset_required else 'no'}")
        print()
        print(f"Attention: {'enabled' if config.attention_enabled else 'disabled'}")
        print(f"Navigation: {'enabled' if config.navigation_enabled else 'disabled'}")
        print(f"Body-to-environment action handoff: {'enabled' if config.body_action_handoff_enabled else 'disabled'}")
        print(f"Read-only support measurements: {'enabled' if config.support_observation_enabled else 'disabled'}")
        if config.support_dynamics_enabled:
            print("Read-only source dynamics / WNM facet: enabled (no action authority)")
        print()
        print(f"Durable innate POSTURE-SUPPORT NavMap: posture_support@r{status.posture_support_map_revision}")
        print(f"Current posture: {status.current_posture or '(not yet processed)'}")
        print(f"Current physical support: {status.current_support or '(not yet processed)'}")
        print(f"Last Attention decision: {status.attention_disposition or '(none yet)'}")
        print(f"Current WNM: {status.wnm_id or '(none)'}")
        print(f"Selected primitive: {status.selected_primitive_id or '(none)'}")
        print(f"Current PNM: {status.current_pnm_id or '(none)'}")
        print(f"Last StandUp prediction outcome: {status.last_prediction_outcome or '(none yet)'}")
        print(f"Trace entries retained: {status.trace_retained} / {status.trace_capacity}")
    if include_key:
        _print_panel_v1("TERM KEY", _STATUS_KEY_V1)


def _ensure_session_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1:
    """Return the existing session or lazily construct one isolated session."""
    if session is not None:
        return session
    print("[nca8:session] Creating a fresh isolated NCA8 session.")
    return Nca8SessionV1()


def _print_cycle_result_v1(session: Nca8SessionV1) -> None:
    """Run and print one compact causal Gate-A-capable cycle."""
    result = session.run_cognitive_cycle()
    print(
        "[nca8:cycle] "
        f"cognitive_cycle={result.cycle_id} "
        f"input=Observation_{result.observation_number} "
        f"output=Action_{result.action_number}:{result.output} "
        f"next_input=Observation_{result.next_observation_number}"
    )
    print(
        "[nca8:focal] "
        f"attention={result.attention_selection.disposition.value} "
        f"source_state={result.wnm.primary_source_state.state_id if result.wnm is not None else '(none)'} "
        f"wnm={result.wnm.working_id if result.wnm is not None else '(none)'} "
        f"primitive={result.navigation.selected_primitive_id or '(none)'}"
    )
    body_authorization = (
        str(result.body_handoff.authorized)
        if result.body_handoff is not None
        else "not-required"
    )
    print(
        "[nca8:prospective] "
        f"pnm={result.pnm.pnm_id if result.pnm is not None else '(none)'} "
        f"task_action={result.task_action or '(none)'} "
        f"body_authorization={body_authorization} "
        f"env_action={result.environment_action!r}"
    )
    for outcome in result.prediction_outcomes:
        print(
            "[nca8:outcome] "
            f"application={outcome.application_id} status={outcome.status.value} "
            f"evidence_cycle={outcome.evidence_sampled_cycle}"
        )


def _fresh_gate_a_session_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1:
    """Create one brand-new Gate-A session whose first lifecycle generation is one.

    Menu option 5 promises a fresh demonstration rather than an additional reset
    of whichever session happened to be retained from earlier menu activity. The
    retained session's immutable configuration is preserved when one exists, but
    none of its mutable episode state is reused. A newly constructed session has
    already performed its one required initialization reset, so the caller must
    use ``run_gate_a(reset_first=False)`` to avoid a misleading second generation.
    """
    print("[nca8:session] Creating a fresh isolated NCA8 session.")
    config = session.config if session is not None else None
    return Nca8SessionV1(config)


def run_nca8_experimental_menu_v1(session: Nca8SessionV1 | None) -> Nca8SessionV1 | None:
    """Run the explanatory NCA8 submenu without changing cognitive behavior.

    Merely opening the menu does not construct a session. Runtime exceptions are
    caught here and cannot mutate the separately owned legacy CCA8 runtime. The
    established Main Menu, not this submenu, owns the one common return pause.
    """
    while True:
        print()
        print("NCA8 -- EXPERIMENTAL RUNTIME / HIERARCHICAL MOTOR REVIEW")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print(_INTRODUCTION_V1)
        print()
        print("  1) Show session status for the current isolated NCA8 session")
        print("  2) Create or reset the current isolated NCA8 session")
        print("  3) Advance the current NCA8 session by exactly one cognitive cycle")
        print("  4) Show the explanatory trace for the current NCA8 session (text + flowchart)")
        print("  5) Start fresh and automatically run the complete Gate-A StandUp demonstration")
        print("  6) Review supplied-target movement and fast local feedback (P18-H4)")
        print("  7) Review relational Righting and sparse PNM preview (P18-H5; no movement)")
        print("  8) Review integrated Righting and persistent motor execution (P18-H6-A)")
        print("  [Enter] Return to Main Menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return session
        try:
            if choice == "1":
                _print_status_v1(session)
                continue
            if choice == "2":
                _print_panel_v1("CREATE / RESET ISOLATED NCA8 SESSION", _RESET_EXPLANATION_V1)
                if session is None:
                    session = Nca8SessionV1()
                    print("[nca8:session] Fresh isolated NCA8 session created.")
                else:
                    status = session.reset()
                    print(f"[nca8:session] NCA8 session reset. Session generation: {status.lifecycle_generation}")
                _print_status_v1(session, include_key=False)
                continue
            if choice == "3":
                _print_panel_v1("RUN ONE NCA8 COGNITIVE CYCLE", _CYCLE_EXPLANATION_V1)
                session = _ensure_session_v1(session)
                _print_cycle_result_v1(session)
                continue
            if choice == "4":
                _print_panel_v1("EXPLANATORY TRACE FOR THE CURRENT NCA8 SESSION", _TRACE_EXPLANATION_V1)
                if session is None:
                    print("No NCA8 session has been created, so there is no trace to show.")
                    continue
                status = session.status()
                print(f"Trace entries retained: {status.trace_retained} / {status.trace_capacity}")
                lines = render_flow_trace_lines_v1(session.trace_snapshot())
                print("\n".join(lines) if lines else "[nca8:trace] empty")
                continue
            if choice == "5":
                _print_panel_v1("FRESH GATE-A STANDUP DEMONSTRATION", _GATE_A_EXPLANATION_V1)
                session = _fresh_gate_a_session_v1(session)
                print(f"Maximum cognitive cycles for this demonstration: {session.config.gate_a_max_cycles}")
                summary = session.run_gate_a(reset_first=False)
                print(
                    "[nca8:gate-a] "
                    f"standing={summary.achieved_standing} cycles={summary.cycles_run} "
                    f"stand_up_actions={summary.stand_up_actions} "
                    f"final_posture={summary.final_posture} final_support={summary.final_support} "
                    f"outcome={summary.last_outcome_status}"
                )
                print(f"[nca8:gate-a] reason={summary.reason}")
                continue
            if choice == "6":
                run_sensorimotor_review_menu_v1()
                continue
            if choice == "7":
                run_righting_preview_review_v1()
                continue
            if choice == "8":
                run_hierarchy_review_menu_v1()
                continue
            print("Please choose 1, 2, 3, 4, 5, 6, 7, or 8; or press Enter to return.")
        except Exception as exc:  # pragma: no cover - defensive interactive boundary
            print(f"[nca8:error] {type(exc).__name__}: {exc}")
            if session is not None and session.status().reset_required:
                print("[nca8:stopped] No automatic retry or stale input. Inspect option 4; use option 2 to reset explicitly.")
