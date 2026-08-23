# -*- coding: utf-8 -*-
# pylint: disable=duplicate-code
#   while there may be some (tiny) amount of duplicated code, it is not worth refactoring it into a common module, increases complexity

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
- explanations can be expanded cumulatively as additional terminal output is documented.

The first use case is Main Menu #1 option 1, which runs one closed-loop
cognitive cycle using the same engine as option 2, but with extra tutorial
text.
"""

from __future__ import annotations


__version__ = "0.2.1"
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
      -> task-level output dispatched before the cognitive cycle closes
      -> resulting later observation buffered for the next cognitive cycle

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
    1) [env] identifies the current observation entering this cognitive cycle.
    2) [env→working] shows current observations entering the WorkingMap / MapSurface.
    3) [env→world] shows what was written to the long-term WorldGraph.
    4) [surfacegrid] shows the current local spatial surface, if it changed.
    5) [env→controller] shows which policy won the action-selection step.
    6) [controller→env] shows that cycle's task-level output crossing the lower-controller boundary.
    7) [cycle] lines summarize the same cycle in compact diagnostic form.
""".strip()


def menu37_teaching_after_observation_v1() -> str:
    """Return a teaching note printed after observation injection."""
    return """
[teach] Observation injection checkpoint:
  Near the start of this cognitive cycle, the environment produced an EnvObservation.

  That observation has now updated several memory systems:
    - BodyMap: the fast current-state body schema.
    - WorkingMap / MapSurface: the short-term scene/entity workspace.
    - WorldGraph: the long-term symbolic episode index.

  The WorkingMap is allowed to be high-bandwidth and current.
  The WorldGraph is more selective; repeated unchanged facts may be skipped and we may not
     create more nodes and/or tags to avoid clutter.
""".strip()


def menu37_teaching_after_controller_v1() -> str:
    """Return a teaching note printed after policy selection/execution."""
    return """
[teach] Controller checkpoint:
  The controller has selected and internally executed one primitive, and its
  task-level output has now crossed the environment / lower-controller boundary.

  Important timing detail:
    The output belongs to THIS cognitive cycle.
    Its sensory consequences normally become evidence for a LATER cognitive cycle.

  For example:
    If CognitiveCycle_n selects policy:stand_up, that action is dispatched during
    CognitiveCycle_n. The environment transition returns Observation_(n+1), which
    is buffered and not cognitively processed until CognitiveCycle_(n+1).

  This is why the current cycle can still report an observed posture of fallen
  while also emitting an expected posture of standing. The standing expectation
  is tested only when later sensory evidence enters through the normal input path.
""".strip()


def menu37_teaching_after_run_v1() -> str:
    """Return a final teaching note printed after a verbose closed-loop run."""
    return """
[teach] End of verbose cognitive-cycle run.

[teach] Useful follow-up inspections:
  Menu 38 shows the BodyMap summary.
  Menu 43 shows the WorkingMap / MapSurface snapshot.
  Main Menu #2 opens the Cognitive Storage Oscilloscope / System Inspector;
  option 7 shows recent WorldGraph bindings and option 10 shows the legacy
  detailed Snapshot.
  cycle_log.jsonl stores the machine-readable version of the same cycle trace.
""".strip()
