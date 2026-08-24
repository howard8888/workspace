#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive Cognitive Storage Oscilloscope and system-inspector menu.

Purpose
-------
This module owns the terminal-control surface for Main Menu #2. The underlying
DP00-DP18 collectors and renderers remain in :mod:`cca8_cognitive_scope`, while
synthetic ``EnvObservation`` construction and sandbox execution remain in
:mod:`cca8_cognitive_injection`.

The separation keeps three concerns distinct:

- ``cca8_cognitive_scope`` samples and renders diagnostic signals;
- ``cca8_cognitive_injection`` runs the bounded disposable test cycle;
- this module asks the technician what to inspect and routes that request.

Authority boundary
------------------
The ordinary oscilloscope remains read-only and external to goat cognition.
The DP01 injector remains source-stamped, sandbox-only, and unable to mutate
the live WorldGraph, operative WNM, environment, drives, or retained trace.

The runner supplies a small callback bundle for compatibility-facing actions.
That keeps this module independent of :mod:`cca8_run` and preserves historical
runner monkeypatch seams used by tests and downstream tools.
"""

from __future__ import annotations

# Interactive diagnostic boundaries should report errors without terminating
# the live CCA8 session.
# pylint: disable=broad-exception-caught
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=duplicate-code

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
import sys
from typing import Any
import webbrowser

import cca8_cli
import cca8_cognitive_injection
import cca8_cognitive_scope
import cca8_reporting
from cca8_column import mem as column_mem
from cca8_controller import skill_readout

__version__ = "0.2.1"

__all__ = [
    "CognitiveScopeMenuRuntimeV1",
    "cognitive_scope_injection_flow_v1",
    "cognitive_scope_live_snapshot_v1",
    "cognitive_scope_menu_v1",
    "cognitive_scope_prompt_port_detail_v1",
    "cognitive_scope_show_compact_snapshot_v1",
    "open_worldgraph_pyvis_flow_v1",
    "show_architecture_status_v1",
    "show_drives_v1",
    "show_recent_bindings_v1",
    "show_skill_telemetry_v1",
    "show_timekeeping_status_v1",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class CognitiveScopeMenuRuntimeV1:  # pylint: disable=too-few-public-methods
    """Runner-visible callbacks used by the interactive inspector.

    The callbacks are intentionally high-level. They preserve the runner's
    historical private helper names while allowing the complete menu loop to
    live outside the composition root. Each callback is resolved when the menu
    opens, so tests that monkeypatch a runner helper continue to observe the
    expected behavior.
    """

    show_architecture_status: Callable[[Any, Any, Any], None]
    show_recent_bindings: Callable[..., None]
    show_drives: Callable[[Any], None]
    show_timekeeping_status: Callable[[Any, Any], None]
    show_skill_telemetry: Callable[[Any], None]
    open_worldgraph_pyvis: Callable[[Any], None]
    run_injection_flow: Callable[[Any], None]
    build_live_snapshot: Callable[[Any, Any, Any, Any, Any], dict[str, Any]]
    show_compact_snapshot: Callable[[Mapping[str, Any]], None]
    legacy_snapshot_text: Callable[..., str]



def open_worldgraph_pyvis_flow_v1(world: Any) -> None:
    """Generate and optionally open an interactive WorldGraph HTML view.

    This is the single terminal controller for both the current Oscilloscope
    visualization panel and the hidden historical direct-menu compatibility
    route. Presentation options remain here so ``cca8_run`` does not carry a
    second Pyvis interaction flow.
    """
    print()
    print("INTERACTIVE WORLDGRAPH HTML")
    print("=" * 78)
    print("Node labels can show ids, first predicates, or both.")
    print("Edge-label text is useful on small graphs and can be hidden on larger graphs.")
    print("Physics uses a force-directed layout and is usually best left enabled.")
    print()

    label_mode = cca8_cli.read_menu_input_v1(
        "Node label mode [id / first_pred / id+first_pred] (default: id+first_pred): "
    )
    if label_mode is None:
        return
    label_mode = label_mode.lower()
    if label_mode not in {"id", "first_pred", "id+first_pred"}:
        label_mode = "id+first_pred"

    edge_choice = cca8_cli.read_menu_input_v1("Show edge labels on links? [Y/n]: ")
    if edge_choice is None:
        return
    show_edge_labels = edge_choice.lower() not in {"n", "no", "0"}

    physics_choice = cca8_cli.read_menu_input_v1("Enable physics (force-directed layout)? [Y/n]: ")
    if physics_choice is None:
        return
    physics = physics_choice.lower() not in {"n", "no", "0"}

    default_path = "world_graph.html"
    path_choice = cca8_cli.read_menu_input_v1(f"Save HTML to (default: {default_path}): ")
    if path_choice is None:
        return
    path = path_choice or default_path

    try:
        out = world.to_pyvis_html(
            path_html=path,
            label_mode=label_mode,
            show_edge_labels=show_edge_labels,
            physics=physics,
        )
        print(f"Interactive graph written to: {out}")

        open_now = cca8_cli.read_menu_input_v1("Open in your default browser now? [y/N]: ")
        if open_now is None or open_now.lower() not in ("y", "yes"):
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(out)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{out}"')
            else:
                webbrowser.open(f"file://{out}")
            print("(opened in your browser)")
        except Exception as exc:
            print(f"[warn] Could not open automatically: {exc}")
    except Exception as exc:
        print(f"[warn] Could not generate Pyvis HTML: {exc}")
        print("       Tip: install with  pip install pyvis")


def show_architecture_status_v1(world: Any, ctx: Any, policy_rt: Any) -> None:
    """Display the coherent WNM/Columns/WorldGraph architecture panel."""
    print()
    print(cca8_reporting.architecture_status_text_v1(world, ctx, column_mem, policy_rt))
    print()


def show_recent_bindings_v1(world: Any, *, limit: int = 5) -> None:
    """Display a bounded WorldGraph tail as one inspector view."""
    print()
    print("WORLDGRAPH RECENT BINDINGS")
    print("=" * 78)
    print(
        "This is a sparse episode/index tail, not the operative WNM or an assertion that every historical tag is true now."
    )
    print()
    print(cca8_reporting.recent_bindings_text(world, limit=limit))


def show_drives_v1(drives: Any) -> None:
    """Display current compact biological-control values and derived flags."""
    print()
    print("DRIVES / INTERNAL CONTROL STATE")
    print("=" * 78)
    print("Numeric drives are legitimate compact control state; derived drive:* flags are not a second world model.")
    print()
    print(cca8_reporting.drives_and_tags_text(drives))


def show_timekeeping_status_v1(env: Any, ctx: Any) -> None:
    """Display all explicit CCA8 time domains as one read-only panel."""
    print()
    print(cca8_reporting.timekeeping_status_text_v1(ctx, env))
    print()


def show_skill_telemetry_v1(ctx: Any) -> None:
    """Display current primitive execution and learning telemetry."""
    print()
    print("PRIMITIVE SKILL TELEMETRY")
    print("=" * 78)
    print("Execution counts, success telemetry, rewards, and q estimates describe primitive history; they do not grant truth.")
    print()
    print(cca8_reporting.skills_hud_text(ctx, top_n=20))
    print("\nFull ledger:")
    print(skill_readout())


def cognitive_scope_live_snapshot_v1(
    env: Any,
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
) -> dict[str, Any]:
    """Build one current-state scope view without retaining it in history."""
    state = getattr(env, "state", None)
    output_env_step = getattr(state, "step_index", None)
    dispatched = getattr(state, "last_applied_action", None)
    selected = getattr(ctx, "env_last_action", None)
    pending_observation = getattr(ctx, "env_pending_observation", None)
    prior_external_state = getattr(ctx, "env_pending_previous_state", None)
    dispatch_succeeded = pending_observation is not None

    if dispatch_succeeded and prior_external_state is not None:
        external_state = prior_external_state
        input_env_step = getattr(prior_external_state, "step_index", None)
    else:
        external_state = state
        input_env_step = output_env_step

    return cca8_cognitive_scope.build_cognitive_scope_snapshot_v1(
        ctx,
        env=env,
        env_obs=None,
        world=world,
        drives=drives,
        policy_rt=policy_rt,
        selected_policy=selected if isinstance(selected, str) else None,
        action_applied=dispatched if isinstance(dispatched, str) else None,
        env_step=input_env_step if isinstance(input_env_step, int) else None,
        external_state=external_state,
        dispatch_succeeded=dispatch_succeeded,
        output_env_step=output_env_step if isinstance(output_env_step, int) else None,
        capture_kind="manual_live",
        snapshot_no=None,
    )


def cognitive_scope_prompt_port_detail_v1(snapshot: Mapping[str, Any]) -> None:
    """Offer repeated drill-down into one stored DP signal at a time."""
    while True:
        try:
            raw = input("Inspect diagnostic point [DP00-DP18 | Enter = return]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw == "":
            return

        port_id = cca8_cognitive_scope.cognitive_scope_normalize_port_id_v1(raw)
        if port_id is None:
            print("Please enter DP00-DP18, or the equivalent number 0-18.")
            continue
        print()
        print("\n".join(cca8_cognitive_scope.render_cognitive_scope_port_detail_lines_v1(snapshot, port_id)))
        print()


def cognitive_scope_show_compact_snapshot_v1(snapshot: Mapping[str, Any]) -> None:
    """Display the front panel and then offer repeated one-port drill-downs."""
    print("\n".join(cca8_cognitive_scope.render_cognitive_scope_compact_snapshot_lines_v1(snapshot)))
    cognitive_scope_prompt_port_detail_v1(snapshot)


def cognitive_scope_injection_flow_v1(
    ctx: Any,
    injection_runtime: cca8_cognitive_injection.CognitiveInjectionRuntimeV1,
    *,
    show_compact_snapshot: Callable[[Mapping[str, Any]], None] | None = None,
) -> None:
    """Run one preset synthetic ``EnvObservation`` in a disposable sandbox."""
    print()
    print("CCA8 SYNTHETIC ENVOBSERVATION INJECTION -- SANDBOX ONLY")
    print("=" * 78)
    print("This first controller injects at DP01 only. It never receives the live session's world, WNM, drives, or environment.")
    print("Shared skill telemetry and Column memory are restored before the diagnostic result is returned.")
    print()

    presets = cca8_cognitive_injection.cognitive_injection_preset_rows_v1()
    print("A preset is a ready-made synthetic EnvObservation test signal.")
    print("To run a preset, type the NUMBER shown at the left and press Enter.")
    print("For example, type 1 and press Enter to run preset 1.")
    print("Each number represents the synthetic test situation described beside it.")
    print()

    for index, row in enumerate(presets, start=1):
        print(f"  {index}) {row['label']}")
        print(f"     Synthetic situation: {row['label']}")
        print(f"     Expected downstream path: {row['expected_path']}")

    valid_choices = "1" if len(presets) == 1 else f"1-{len(presets)}"
    print()
    print(f"Available preset number(s): {valid_choices}")
    print("Press Enter without typing a number to cancel.")

    try:
        choice = input(f"Enter injection preset number [{valid_choices} | Enter = cancel]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice == "":
        return

    try:
        selected_index = int(choice) - 1
        if selected_index < 0:
            raise IndexError
        selected_preset = presets[selected_index]
    except (TypeError, ValueError, IndexError):
        print(f"Please choose 1-{len(presets)} or press Enter to cancel.")
        return

    next_no = int(getattr(ctx, "cognitive_scope_injection_no_v1", 0) or 0) + 1
    injection_id = f"INJ{next_no:04d}"
    result = cca8_cognitive_injection.run_envobservation_injection_sandbox_v1(
        injection_runtime,
        injection_id=injection_id,
        preset_id=selected_preset["preset_id"],
    )
    result["live_diagnostic_record_updated"] = True
    ctx.cognitive_scope_injection_no_v1 = next_no
    ctx.cognitive_scope_last_injection_v1 = result

    print()
    print("\n".join(cca8_cognitive_injection.render_cognitive_injection_result_lines_v1(result)))
    snapshot = result.get("snapshot")
    if isinstance(snapshot, Mapping) and snapshot:
        display_snapshot = show_compact_snapshot or cognitive_scope_show_compact_snapshot_v1
        display_snapshot(snapshot)

    try:
        show_transcript = input("Show the full disposable sandbox cycle transcript? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if show_transcript in ("y", "yes"):
        print()
        print("\n".join(cca8_cognitive_injection.render_cognitive_injection_transcript_lines_v1(result)))
        print()


def _scope_trace_menu_v1(
    env: Any,
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    *,
    runtime: CognitiveScopeMenuRuntimeV1,
) -> None:
    """Display retained/live DP00-DP18 trace operations."""
    while True:
        print()
        print("COGNITIVE SIGNAL PATH / RETAINED CYCLES")
        print("=" * 78)
        print("  1) Display latest retained compact signal path + optional DP drill-down")
        print("  2) List retained snapshot index")
        print("  3) Display retained compact signal path by snapshot number + optional DP drill-down")
        print("  4) Display current live compact state + optional DP drill-down")
        print("  5) Display latest full raw all-port snapshot")
        print("  [Enter] Return to the Oscilloscope front panel")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "1":
            snapshot = cca8_cognitive_scope.cognitive_scope_latest_snapshot_v1(ctx)
            if snapshot is None:
                print("\nNo cognitive-cycle snapshot has been retained yet; showing current live state instead.\n")
                snapshot = runtime.build_live_snapshot(env, world, drives, ctx, policy_rt)
            runtime.show_compact_snapshot(snapshot)
            continue
        if choice == "2":
            print("\n".join(cca8_cognitive_scope.render_cognitive_scope_trace_index_lines_v1(ctx, limit=30)))
            continue
        if choice == "3":
            try:
                raw = input("Snapshot number: ").strip()
                snapshot_no = int(raw)
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            except ValueError:
                print("Please enter an integer snapshot number.")
                continue
            snapshot = cca8_cognitive_scope.cognitive_scope_find_snapshot_v1(ctx, snapshot_no)
            if snapshot is None:
                print(f"Snapshot {snapshot_no} is not retained in the current bounded trace.")
                continue
            runtime.show_compact_snapshot(snapshot)
            continue
        if choice == "4":
            snapshot = runtime.build_live_snapshot(env, world, drives, ctx, policy_rt)
            runtime.show_compact_snapshot(snapshot)
            continue
        if choice == "5":
            snapshot = cca8_cognitive_scope.cognitive_scope_latest_snapshot_v1(ctx)
            if snapshot is None:
                print("\nNo retained snapshot exists; showing the current live raw view instead.\n")
                snapshot = runtime.build_live_snapshot(env, world, drives, ctx, policy_rt)
            print("\n".join(cca8_cognitive_scope.render_cognitive_scope_snapshot_lines_v1(snapshot)))
            continue
        print("Please choose 1-5 or press Enter to return.")


def _scope_current_state_menu_v1(
    env: Any,
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    *,
    runtime: CognitiveScopeMenuRuntimeV1,
) -> str | None:
    """Display current cognition/control views or return a legacy read-only handler."""
    while True:
        print()
        print("CURRENT COGNITION & CONTROL STATE")
        print("=" * 78)
        print("  1) Operative WNM / ready set and architecture status")
        print("  2) Protected BodyMap")
        print("  3) WorkingMap / MapSurface / SurfaceGrid")
        print("  4) Spatial scene relations around NOW")
        print("  5) Drives / internal control state")
        print("  6) Explicit timekeeping / ordering")
        print("  7) Primitive skill telemetry")
        print("  [Enter] Return to the Oscilloscope front panel")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            runtime.show_architecture_status(world, ctx, policy_rt)
            continue
        if choice == "2":
            return "38"
        if choice == "3":
            return "43"
        if choice == "4":
            return "39"
        if choice == "5":
            runtime.show_drives(drives)
            continue
        if choice == "6":
            runtime.show_timekeeping_status(env, ctx)
            continue
        if choice == "7":
            runtime.show_skill_telemetry(ctx)
            continue
        print("Please choose 1-7 or press Enter to return.")


def _scope_memory_stores_menu_v1(
    world: Any,
    ctx: Any,
    policy_rt: Any,
    *,
    runtime: CognitiveScopeMenuRuntimeV1,
) -> str | None:
    """Display memory/index views or return a historical read-only handler."""
    while True:
        print()
        print("MEMORY STORES & WORLDGRAPH STATE -- READ ONLY")
        print("=" * 78)
        print("  1) Architecture / memory status")
        print("  2) Recent WorldGraph bindings")
        print("  3) Inspect one WorldGraph binding")
        print("  4) List WorldGraph predicates")
        print("  5) Resolve engram pointers on a binding")
        print("  6) Inspect one engram")
        print("  7) List all engrams")
        print("  8) Search engrams")
        print("  9) WorkingMap / MapSurface snapshot")
        print(" 10) List recent MapSurface engrams")
        print(" 11) Rank the best MapSurface candidate without loading it")
        print("  [Enter] Return to the Oscilloscope front panel")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            runtime.show_architecture_status(world, ctx, policy_rt)
            continue
        if choice == "2":
            runtime.show_recent_bindings(world, limit=5)
            continue
        routes = {
            "3": "10",
            "4": "2",
            "5": "6",
            "6": "27",
            "7": "28",
            "8": "29",
            "9": "43",
            "10": "45",
            "11": "46",
        }
        routed = routes.get(choice)
        if routed is not None:
            return routed
        print("Please choose 1-11 or press Enter to return.")


def _scope_visualization_menu_v1(
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    *,
    runtime: CognitiveScopeMenuRuntimeV1,
) -> str | None:
    """Display diagnostic reports/visualization or return the text-export handler."""
    while True:
        print()
        print("VISUALIZATIONS & DIAGNOSTIC EXPORTS")
        print("=" * 78)
        print("  1) Legacy detailed Snapshot")
        print("  2) Generate / display interactive WorldGraph HTML")
        print("  3) Export a diagnostic text snapshot")
        print("  [Enter] Return to the Oscilloscope front panel")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            print()
            print("LEGACY DETAILED SNAPSHOT -- retained temporarily for compatibility")
            print(runtime.legacy_snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt))
            continue
        if choice == "2":
            runtime.open_worldgraph_pyvis(world)
            continue
        if choice == "3":
            return "16"
        print("Please choose 1-3 or press Enter to return.")


def _scope_trace_controls_menu_v1(ctx: Any) -> str | None:
    """Clear retained scope records or return the existing display-toggle handler."""
    while True:
        print()
        print("TRACE & DISPLAY CONTROLS")
        print("=" * 78)
        print("  1) Clear retained oscilloscope snapshots")
        print("  2) Toggle mini-snapshot after ordinary menu operations")
        print("  [Enter] Return to the Oscilloscope front panel")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            confirm = cca8_cli.read_menu_input_v1("Clear retained diagnostic snapshots? [y/N]: ")
            if isinstance(confirm, str) and confirm.lower() in ("y", "yes"):
                removed = cca8_cognitive_scope.cognitive_scope_clear_v1(ctx)
                print(f"Cleared {removed} retained diagnostic snapshot(s).")
            else:
                print("Trace unchanged.")
            continue
        if choice == "2":
            return "36"
        print("Please choose 1-2 or press Enter to return.")


def cognitive_scope_menu_v1(
    env: Any,
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    *,
    runtime: CognitiveScopeMenuRuntimeV1,
) -> str | None:
    """Run Main Menu #2 and return an optional established read-only handler.

    The front panel keeps the complete inspector conceptually unified while
    grouping its many functions by technician intent. Views already owned by
    the runner are returned as historical handler keys rather than duplicated.
    """
    while True:
        trace = cca8_cognitive_scope.cognitive_scope_trace_summary_v1(ctx)
        print()
        print("=" * 78)
        print("CCA8 COGNITIVE STORAGE OSCILLOSCOPE / SYSTEM INSPECTOR")
        print("=" * 78)
        print(
            f"Retained cognitive-cycle snapshots: {trace.get('retained_count')}/{trace.get('capacity')}  "
            f"total captured this session: {trace.get('total_capture_count')}"
        )
        print("DP00 is external simulation truth; DP01-DP18 are eighteen CCA8 service points.")
        print("The ordinary scope trace and store views are read-only diagnostic instrumentation.")
        print("The source-stamped DP01 injector remains confined to a disposable sandbox.\n")
        print("  1) Signal Path / Retained Cognitive Cycles")
        print("  2) Current Cognition & Control State")
        print("  3) Memory Stores & WorldGraph State")
        print("  4) Visualizations & Diagnostic Exports")
        print("  5) Sandbox Signal Injection")
        print("  6) Trace & Display Controls")
        print("  [Enter] Return to Main Menu")

        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return None
        if choice == "1":
            _scope_trace_menu_v1(env, world, drives, ctx, policy_rt, runtime=runtime)
            continue
        if choice == "2":
            routed = _scope_current_state_menu_v1(env, world, drives, ctx, policy_rt, runtime=runtime)
            if routed is not None:
                return routed
            continue
        if choice == "3":
            routed = _scope_memory_stores_menu_v1(world, ctx, policy_rt, runtime=runtime)
            if routed is not None:
                return routed
            continue
        if choice == "4":
            routed = _scope_visualization_menu_v1(world, drives, ctx, policy_rt, runtime=runtime)
            if routed is not None:
                return routed
            continue
        if choice == "5":
            runtime.run_injection_flow(ctx)
            continue
        if choice == "6":
            routed = _scope_trace_controls_menu_v1(ctx)
            if routed is not None:
                return routed
            continue
        print("Please choose 1-6 or press Enter to return.")
