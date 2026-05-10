# -*- coding: utf-8 -*-
"""
CCA8 teaching text helpers.

Purpose
-------
Keep longer terminal explanations out of ``cca8_run.py`` while still letting
selected menu flows print human-readable teaching notes beside the live output.

This module is deliberately simple:
- no CCA8 imports,
- no side effects,
- all functions return strings,
- explanations can be expanded cumulatively as we discuss more terminal output.

The first use case is Menu 35, which runs one closed-loop cognitive cycle using
the same engine as Menu 37, but with extra tutorial text.
"""

from __future__ import annotations


__version__ = "0.1.0"
__all__ = [
    "menu37_teaching_intro_v1",
    "menu37_teaching_cycle_header_v1",
    "menu37_teaching_after_observation_v1",
    "menu37_teaching_after_controller_v1",
    "menu37_teaching_after_run_v1",
    "__version__",
]


def menu37_teaching_intro_v1() -> str:
    """Return the introductory teaching block for verbose closed-loop runs."""
    return """
[teach] Verbose cognitive-cycle mode is ON.

[teach] Big picture:
  A closed-loop cognitive cycle is one pass through:

      environment truth
      -> EnvObservation
      -> BodyMap / WorkingMap / WorldGraph
      -> policy selection
      -> policy execution
      -> next action stored for the following environment step

[teach] Memory layers:
  EnvState is the environment-side truth. The agent does not directly read it.
  EnvObservation is the one-tick perceptual packet sent from the environment to CCA8.
  BodyMap is the fast current body / near-world belief used by policy gates.
  WorkingMap is the short-term workspace. It includes MapSurface, Scratch, and Creative layers.
  WorldGraph is the long-term symbolic episode index.
  Column memory stores heavier payloads, such as map snapshots, vectors, and NavPatch data.

[teach] Anchors:
  Anchors are stable names for important graph nodes.
  The binding id can change or be hard to remember, but the anchor name stays meaningful.

  In the WorkingMap:
    WM_ROOT is the current working scene root.
    WM_SELF is the agent/self entity node.
    WM_SCRATCH stores temporary policy/action hypotheses.
    WM_CREATIVE stores imagined or candidate future items.
    WM_ENT_MOM, WM_ENT_SHELTER, and WM_ENT_CLIFF identify entity nodes.

[teach] Important distinction:
  A node such as w6 is not merely 'the posture:fallen node'.
  It is usually the SELF entity node, carrying current predicates such as pred:posture:fallen.
""".strip()


def menu37_teaching_cycle_header_v1(cycle_index: int, total_cycles: int) -> str:
    """Return a short teaching note printed at the start of each verbose cycle."""
    return f"""
[teach] Reading this cycle:
  This is cognitive cycle {cycle_index}/{total_cycles}.

  Watch the output in this order:
    1) [env] tells you whether the environment reset or stepped forward.
    2) [env→working] shows current observations entering the WorkingMap / MapSurface.
    3) [env→world] shows what was written to the long-term WorldGraph.
    4) [surfacegrid] shows the current local spatial surface, if it changed.
    5) [env→controller] shows which policy won the action-selection step.
    6) [cycle] lines summarize the same cycle in compact diagnostic form.
""".strip()


def menu37_teaching_after_observation_v1() -> str:
    """Return a teaching note printed after observation injection."""
    return """
[teach] Observation injection checkpoint:
  At this point the environment has produced an EnvObservation.

  The same observation can update several memory systems:
    - BodyMap: the fast current-state body schema.
    - WorkingMap / MapSurface: the short-term scene/entity workspace.
    - WorldGraph: the long-term symbolic episode index.

  The WorkingMap is allowed to be high-bandwidth and current.
  The WorldGraph is more selective; repeated unchanged facts may be skipped to avoid clutter.
""".strip()


def menu37_teaching_after_controller_v1() -> str:
    """Return a teaching note printed after policy selection/execution."""
    return """
[teach] Controller checkpoint:
  The controller has now selected and executed one policy.

  Important timing detail:
    The selected policy affects the NEXT environment step.

  For example:
    If this cycle executes policy:stand_up, the environment only gets that action
    when the next cycle calls env.step(action='policy:stand_up').

  This is why the terminal may show an expected posture of standing while the
  environment still reports fallen during the same cycle. That mismatch becomes
  prediction-error evidence on the following cycle.
""".strip()


def menu37_teaching_after_run_v1() -> str:
    """Return a final teaching note printed after a verbose closed-loop run."""
    return """
[teach] End of verbose cognitive-cycle run.

[teach] Useful follow-up inspections:
  Menu 38 shows the BodyMap summary.
  Menu 43 shows the WorkingMap / MapSurface snapshot.
  Menu 3 shows the long-term WorldGraph snapshot.
  cycle_log.jsonl stores the machine-readable version of the same cycle trace.
""".strip()
