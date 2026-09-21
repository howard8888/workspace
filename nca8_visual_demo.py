#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu/CLI visual-source and frame-transform fixtures, explicitly without motion.

The existing H5 preview composition supplies the genuine POSTURE-SUPPORT owner,
Attention, Navigation/WNM, Righting and BodyMap helper. A separate visual owner
publishes its own candidate to that same selector. The supplied visual approach
requirement is mapped only when vision is the selected source. No visual task IP,
MOM ANM, physical provider, handoff, target installation or learner is introduced.
These are finite source/transform fixtures, not full A-F cycles or world runs.
"""
from __future__ import annotations

from dataclasses import dataclass

import cca8_cli
from cca8_env import EnvObservation
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_adapters import adapt_env_observation_v1, admit_visual_surface_v1
from nca8_body_targets import PlanarBodyObservationV1, VisualApproachRequestV1, VisualBodyPreviewV1
from nca8_runtime import Nca8RightingPreviewSessionV1, RightingPreviewResultV1
from nca8_sensorimotor_contracts import TargetOriginV1
from nca8_visual import VisualNavMapStateV1, VisualObservationV1, VisualSourceV1

__version__ = "0.1.0"
__all__ = ["VISUAL_PREVIEW_CASES_V1", "VisualPreviewRecordV1", "VisualPreviewRunV1", "run_visual_preview_v1",
           "render_visual_preview_v1", "run_visual_preview_menu_v1", "__version__"]

VISUAL_PREVIEW_CASES_V1 = (
    "heading_0", "heading_90", "rotated_coordinates", "translated_coordinates",
    "recognition_off", "spatial_off", "both_off", "missing_vision", "missing_heading",
    "missing_body_position", "frame_mismatch", "target_unlocalized", "mapping_off",
    "support_priority", "nonfocal_refresh", "gap_recovery", "stale_body",
)


@dataclass(frozen=True, slots=True)
class VisualPreviewRecordV1:
    """One real shared-selector result and optional non-actuating visual mapping."""

    visual: VisualNavMapStateV1
    calculation: RightingPreviewResultV1
    mapping: VisualBodyPreviewV1 | None

    def as_dict(self) -> dict[str, object]:
        """Export actual source/selection and fixture mapping without recomputation."""
        return {"visual": self.visual.as_dict(), "calculation": self.calculation.as_dict(),
                "visual_mapping": None if self.mapping is None else self.mapping.as_dict()}


@dataclass(frozen=True, slots=True)
class VisualPreviewRunV1:
    """Finite diagnostic records, not a second live source or saved cognition."""

    case: str
    records: tuple[VisualPreviewRecordV1, ...]
    owner_counts: tuple[tuple[str, int], ...]
    durable_unchanged: bool
    bound_violations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """State explicitly what this source/frame preview does not implement."""
        return {"case": self.case, "profile": "visual_frame_preview_v1", "evidence_kind": "supplied_sensor_and_task_fixtures",
                "records": [item.as_dict() for item in self.records], "owner_counts": dict(self.owner_counts),
                "durable_unchanged": self.durable_unchanged, "bound_violations": list(self.bound_violations),
                "physical_steps": 0, "motor_commands": 0, "target_installations": 0, "durable_learning_updates": 0,
                "visual_task_selected": False, "visual_task_pnm_created": False,
                "remaining_2a": "translation capability, physical consumer and integrated qualification"}


def _visual_fixture(
    stream: MotorStreamRefV1, *, tick: int, frame: str, target: NavPointV1 | None, position: NavPointV1 | None,
) -> VisualObservationV1:
    """Enter fixtures through the real existing whitelist plus the new typed reader."""
    event = max(0, tick - 1)
    item: dict[str, object] = {"entity": "region_1", "kind": "object"}
    if target is not None:
        item.update(target.as_dict())
    raw = EnvObservation(
        raw_sensors={}, predicates=[], cues=[], nav_patches=[], env_meta={"step_index": event},
        surface_grid={"schema": "surface_grid_v1", "frame": frame,
                      "anchor": {} if position is None else {"entity": "self", **position.as_dict()},
                      "objects": [item], "landmarks": []},
    )
    result = admit_visual_surface_v1(adapt_env_observation_v1(raw), stream=stream, sample_id=event + 1,
                                    event_tick=event, available_tick=tick)
    if result is None:
        raise RuntimeError("valid explicit visual fixture disappeared during admission")
    return result


def run_visual_preview_v1(case: str = "heading_0") -> VisualPreviewRunV1:
    """Run one finite shared-source experiment without selecting a visual task.

    Geometry/recognition are independently suppressed at the owner. The same
    fixed target is used for heading controls. Coordinate re-expression rotates
    or translates all corresponding scene/body coordinates, not the body alone.
    Support-priority and nonfocal-refresh use real H5 source nomination, not a
    hard-coded competing winner. All simulated body readings are supplied here;
    no physical time is advanced and no result establishes locomotor success.
    """
    if not isinstance(case, str) or case not in VISUAL_PREVIEW_CASES_V1:
        raise ValueError("unknown visual preview case")
    stream = MotorStreamRefV1("visual_preview", 1)
    visual = VisualSourceV1(stream, recognition_enabled=case not in {"recognition_off", "both_off"},
                            spatial_enabled=case not in {"spatial_off", "both_off"})
    session = Nca8RightingPreviewSessionV1(stream, visual_preview_enabled=True)
    if case == "mapping_off":
        # Use the ordinary BodyMap ablation at construction, not a changed sensor.
        from nca8_body import Nca8BodyRuntimeV1  # pylint: disable=import-outside-toplevel
        session.body = Nca8BodyRuntimeV1(action_handoff_enabled=False)
        session.mapper = session.body.configure_motor_targets(stream, (), visual_preview_enabled=True)
    initial_durable = visual.durable_map.as_dict(), session.maps.durable_map().as_dict()
    ticks = (0, 4, 8) if case == "nonfocal_refresh" else (0, 4, 8, 12) if case == "gap_recovery" else (0, 4) if case == "stale_body" else (0,)
    records: list[VisualPreviewRecordV1] = []
    old_visual: VisualObservationV1 | None = None
    old_body: PlanarBodyObservationV1 | None = None
    for cycle, tick in enumerate(ticks, 1):
        frame = "scene_xy:lab"
        heading = 90.0 if case in {"heading_90", "rotated_coordinates"} else 0.0
        body_position = NavPointV1(0, 0)
        target = NavPointV1(2 + (cycle - 1 if case == "nonfocal_refresh" else 0), 1)
        if case == "rotated_coordinates":
            frame, target = "scene_xy:rotated", NavPointV1(-1, 2)
        elif case == "translated_coordinates":
            frame, body_position, target = "scene_xy:translated", NavPointV1(10, -3), NavPointV1(12, -2)
        acquisition = _visual_fixture(stream, tick=tick, frame=frame,
                                      target=None if case == "target_unlocalized" else target, position=body_position)
        supplied_visual: VisualObservationV1 | None = acquisition
        if case == "missing_vision" or (case == "gap_recovery" and cycle == 2):
            supplied_visual = None
        if case == "gap_recovery" and cycle == 3:
            supplied_visual = old_visual
        source = visual.update(supplied_visual, cycle_id=cycle, cutoff_tick=tick)
        if cycle == 1:
            old_visual = acquisition
        pose = PlanarBodyObservationV1(
            stream, max(0, tick - 1) + 1, max(0, tick - 1), tick,
            "scene_xy:other" if case == "frame_mismatch" else frame,
            None if case == "missing_body_position" else body_position,
            None if case == "missing_heading" else heading,
        )
        if case == "stale_body" and cycle > 1:
            pose = old_body if old_body is not None else pose
        session.mapper.observe_planar_body(pose, at_tick=tick)
        old_body = pose
        unsafe = case == "support_priority" or (case == "nonfocal_refresh" and cycle < 3)
        feedback = MotorFeedbackV1(stream, max(0, tick - 1) + 1, max(0, tick - 1), tick,
                                   30.0 if unsafe else 5.0, 0.4 if unsafe else 1.0, True,
                                   0.1 if unsafe else 0.95, 0.5 if unsafe else 0.05)
        candidate = visual.candidate()
        bids = () if candidate is None else (session.attention.build_bid(candidate, cycle_id=cycle),)
        calculation = session.preview(feedback, cutoff_tick=tick, competing_bids=bids)
        mapping: VisualBodyPreviewV1 | None = None
        working = calculation.navigation.wnm
        if working is not None and isinstance(working.primary_source_state, VisualNavMapStateV1):
            origin = TargetOriginV1(stream, "fixture:visual_approach", f"fixture:application:{cycle}", f"fixture:envelope:{cycle}")
            request = VisualApproachRequestV1(origin, source.source_map_ref, "region_1")
            mapping = session.mapper.preview_visual_approach(request, working.primary_source_state, at_tick=tick)
        records.append(VisualPreviewRecordV1(source, calculation, mapping))
    counts = {**visual.retained_counts(), **session.mapper.retained_counts()}
    violations = tuple(name for name, limit in (("durable_maps", 1), ("acquisitions", 1), ("current_configurations", 1),
                                                ("retained_detections", 8), ("recognition_contributions", 8),
                                                ("guidance_contributions", 8), ("planar_body_records", 1), ("body_reserved_records", 0))
                       if counts[name] > limit)
    unchanged = initial_durable == (visual.durable_map.as_dict(), session.maps.durable_map().as_dict())
    return VisualPreviewRunV1(case, tuple(records), tuple(sorted(counts.items())), unchanged, violations)


def render_visual_preview_v1(run: VisualPreviewRunV1, *, detail: bool = False) -> str:
    """Render retained fields only; display cannot advance or recompute the trial."""
    if not isinstance(run, VisualPreviewRunV1) or not isinstance(detail, bool):
        raise TypeError("rendering requires a completed run and Boolean detail")
    lines = [f"P16-2A-A VISUAL SOURCE / BODY-FRAME PREVIEW | {run.case}",
             "Supplied sensor/task fixtures. No visual task IP, locomotor executor, or world steps."]
    for record in run.records:
        source, calculation, mapping = record.visual, record.calculation, record.mapping
        selected = calculation.attention.selected_source_state
        source_name = "none" if selected is None else selected.source_map_ref.map_id
        lines.append(f"  opportunity={source.applied_cycle} cutoff={source.cutoff_tick}: visual={source.input_status}; "
                     f"recognition={len(source.recognition)} guidance={len(source.guidance)}; "
                     f"Attention={calculation.attention.disposition.value} {source_name}")
        if mapping is None:
            lines.append("    visual mapping not run: visual source did not obtain the focal role")
        else:
            lines.append(f"    BodyMap={mapping.status}")
            target, step = mapping.body_relative_target, mapping.body_step
            if target is not None and step is not None:
                lines.append(f"    target forward={target.x:+.6f} m, left={target.y:+.6f} m; "
                             f"bounded step=({step.x:+.6f}, {step.y:+.6f}) m")
                if mapping.hypothetical_self is not None:
                    lines.append(f"    hypothetical SELF=({mapping.hypothetical_self.x:+.6f}, {mapping.hypothetical_self.y:+.6f}); "
                                 "NOT current evidence or an executed PNM")
        if detail:
            lines.append(f"    original visual sample/event/available={source.sample_id}/{source.event_tick}/{source.available_tick}; "
                         f"frame={source.frame_id}; units=metres")
            for recognition in source.recognition:
                lines.append(
                    f"    recognition {recognition.region_id}: {recognition.descriptor} (provider category scaffold)"
                )
            for guidance in source.guidance:
                lines.append(f"    located {guidance.region_id}: {guidance.position.as_dict()}; SELF relation="
                             f"{None if guidance.relative_to_self is None else guidance.relative_to_self.as_dict()}")
            if mapping is not None and mapping.body is not None:
                lines.append(f"    independent body heading={mapping.body.heading_degrees}; "
                             f"body event/available={mapping.body.event_tick}/{mapping.body.available_tick}")
    lines.append(f"  durable unchanged={run.durable_unchanged}; bounds={list(run.bound_violations)}; "
                 "physical steps=0; installations=0; durable updates=0")
    lines.append("  P16-2A remains open: translation consumer, real displacement/contact and integrated qualification are not implemented here.")
    return "\n".join(lines)


def run_visual_preview_menu_v1() -> None:
    """Launch the shared finite fixtures without touching an existing A0 session."""
    choices = {"1": VISUAL_PREVIEW_CASES_V1, "2": ("heading_0", "heading_90", "rotated_coordinates", "translated_coordinates"),
               "3": ("heading_0", "recognition_off", "spatial_off", "both_off"),
               "4": ("missing_vision", "missing_heading", "frame_mismatch", "target_unlocalized", "stale_body"),
               "5": ("support_priority", "nonfocal_refresh"), "6": ("gap_recovery",), "7": ("heading_0",)}
    while True:
        print("\nP16-2A-A -- VISUAL SOURCE / NON-ACTUATING BODY-FRAME REVIEW")
        print("  1) All fixed profiles\n  2) Body heading versus coordinate re-expression\n"
              "  3) Recognition/guidance independently disabled\n  4) Missing, stale and incompatible geometry\n"
              "  5) Real support competition and nonfocal visual refresh\n  6) Gap / old duplicate / fresh reacquisition\n"
              "  7) Detailed nominal frame calculation\n  [Enter] Return to NCA8 menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        cases = choices.get(choice)
        if cases is None:
            print("Choose 1-7 or press Enter to return.")
            continue
        for case in cases:
            print(render_visual_preview_v1(run_visual_preview_v1(case), detail=choice == "7"))
