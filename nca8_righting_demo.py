#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finite H5 review fixtures shared by the menu and command-line inspection.

All measurements here are explicitly replay/synthetic inputs, not a physical run
or successful recovery. The runner supplies activity and observations, never a
body target or the winning task. Actual source maintenance, Attention, Navigation,
Righting/PNM and BodyMap mapping run through Nca8RightingPreviewSessionV1. No H2
world or H4 executor is constructed and the caller's A0 session is not touched.
"""

from __future__ import annotations

from dataclasses import dataclass

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_contracts import CircuitValidityV1
from nca8_executive import AttentionBidV1
from nca8_maps import DurableNavMapRefV1, NavMapStateV1, Nca8ContactStateV1, Nca8PostureStateV1, Nca8SupportStateV1
from nca8_righting import RightingActivityV1, RightingApplicationV1, RightingContextV1
from nca8_runtime import Nca8RightingPreviewSessionV1, RightingPreviewResultV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, SensorimotorTargetKindV1

__version__ = "0.1.1"
__all__ = [
    "RightingPreviewExampleV1", "competing_preview_bid_v1", "run_righting_preview_examples_v1",
    "render_righting_preview_v1", "run_righting_preview_review_v1", "__version__",
]


@dataclass(frozen=True, slots=True)
class RightingPreviewExampleV1:
    """An externally labelled review result; its label never enters cognition."""

    name: str
    result: RightingPreviewResultV1


def competing_preview_bid_v1(cycle_id: int, *, persistence_rank: int = 10) -> AttentionBidV1:
    """Supply one controlled second source, not a second WNM or real domain claim.

    Its ordinary need and activation equal the support bid. Only the specified
    persistence component competes with the source-owned continuation influence.
    The source has its own identity and carries no support/motor observation.
    """
    source = NavMapStateV1(
        "fixture:competing_source:current", DurableNavMapRefV1("fixture_competing_source", 1), "fixture_source_owner",
        Nca8PostureStateV1.UNKNOWN, Nca8SupportStateV1.UNKNOWN, Nca8ContactStateV1.UNKNOWN,
        (), ("fixture:other_source_context",), 1.0, False, cycle_id, cycle_id, cycle_id, None,
        CircuitValidityV1.VALID, 1, 0, 0,
    )
    return AttentionBidV1(
        f"fixture_bid:{cycle_id}", "fixture:competing_source", source, "fixture_source_owner", cycle_id,
        0, 20, 0, 0, persistence_rank, 20, ("controlled_competing_source",), False, "fixture:competing_source",
    )


def _reading(
    stream: MotorStreamRefV1, tick: int = 0, *, tilt: float | None = 30.0,
    extension: float | None = 0.4, contact: bool | None = True, loading: float | None = 0.5,
    instability: float | None = 0.3,
) -> MotorFeedbackV1:
    """Make a labelled synthetic acquisition; IDs/timing follow the H1 sensor schema."""
    return MotorFeedbackV1(stream, tick + 1, tick, tick if tick == 0 else tick + 1, tilt, extension, contact, loading, instability)


def run_righting_preview_examples_v1() -> tuple[RightingPreviewExampleV1, ...]:
    """Run finite positive/adverse source and task previews, without motor dispatch.

    The matched trajectory pair ends with identical current measurements but
    different supported histories. The influence pair holds sensing and all
    non-context priority components fixed. Every example owns an isolated session;
    the explicit continuity and budget cases reuse only their own task/source.
    """
    examples: list[RightingPreviewExampleV1] = []
    stream = MotorStreamRefV1("h5:preview_fixture", 1)
    initial = _reading(stream)
    first = Nca8RightingPreviewSessionV1(stream)
    examples.append(RightingPreviewExampleV1("FIRST SAMPLE / UNKNOWN RATES", first.preview(initial, cutoff_tick=0)))
    for name, old_tilt, old_load, old_instability in (
        ("SAME CURRENT POSE / IMPROVING SUPPORT", 34.0, 0.4, 0.4),
        ("SAME CURRENT POSE / DETERIORATING SUPPORT", 26.0, 0.6, 0.2),
    ):
        session = Nca8RightingPreviewSessionV1(stream)
        session.preview(_reading(stream, tilt=old_tilt, loading=old_load, instability=old_instability), cutoff_tick=0)
        examples.append(RightingPreviewExampleV1(name, session.preview(_reading(stream, 3), cutoff_tick=4)))
    rest = Nca8RightingPreviewSessionV1(stream, context=RightingContextV1("activity:rest", RightingActivityV1.REST))
    examples.append(RightingPreviewExampleV1(
        "REQUESTED REST / CURRENT SAFE-REST FIXTURE", rest.preview(_reading(stream, tilt=80.0, loading=0.03, instability=0.05), cutoff_tick=0),
    ))
    crouch = Nca8RightingPreviewSessionV1(stream, context=RightingContextV1("activity:crouch", RightingActivityV1.CROUCH))
    examples.append(RightingPreviewExampleV1(
        "SUPPORTED CROUCH / NO FORCED UPRIGHT REQUEST", crouch.preview(_reading(stream, instability=0.1), cutoff_tick=0),
    ))
    for name, reading in (
        ("UNKNOWN TILT / LIMITED EXTENSION STILL POSSIBLE", _reading(stream, tilt=None)),
        ("NO CONTACT / DO NOT PREDICT A KNOWN SURFACE", _reading(stream, contact=False, loading=0.0)),
    ):
        session = Nca8RightingPreviewSessionV1(stream)
        examples.append(RightingPreviewExampleV1(name, session.preview(reading, cutoff_tick=0)))
    capability = tuple(item for item in nominal_body_capabilities_v1() if item.kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    session = Nca8RightingPreviewSessionV1(stream, capabilities=capability)
    examples.append(RightingPreviewExampleV1("ORIENTATION CAPABILITY UNAVAILABLE", session.preview(initial, cutoff_tick=0)))
    for enabled in (True, False):
        session = Nca8RightingPreviewSessionV1(stream, influence_enabled=enabled)
        session.preview(initial, cutoff_tick=0)
        result = session.preview(initial, cutoff_tick=1, competing_bids=(competing_preview_bid_v1(2),))
        examples.append(RightingPreviewExampleV1(f"FIXED EVIDENCE / CONTINUATION INFLUENCE {'ON' if enabled else 'OFF'}", result))
    session = Nca8RightingPreviewSessionV1(stream)
    old = session.preview(initial, cutoff_tick=0)
    old_export = old.as_dict()
    result = session.preview(
        _reading(stream, 3, tilt=80.0, loading=0.03, instability=0.05), cutoff_tick=4,
        context=RightingContextV1("activity:new_rest_request", RightingActivityV1.REST),
    )
    assert old.as_dict() == old_export
    examples.append(RightingPreviewExampleV1("CONTEXT CHANGE / OLD CRITERION AND PREVIEW RETAINED", result))
    session = Nca8RightingPreviewSessionV1(stream)
    session.preview(initial, cutoff_tick=0)
    examples.append(RightingPreviewExampleV1("MISSING CURRENT INPUT / NO INVENTED SUPPORT", session.preview(None, cutoff_tick=4)))
    session = Nca8RightingPreviewSessionV1(stream)
    session.preview(initial, cutoff_tick=0)
    result = session.preview(_reading(stream, 79), cutoff_tick=80)
    examples.append(RightingPreviewExampleV1("PHYSICAL TASK BUDGET / NO SILENT RESTART", result))
    return tuple(examples)


def _quantity(value: float | None) -> str:
    """Use unknown rather than a numeric zero for absent relations/rates."""
    return "unknown" if value is None else f"{value:+.4f}"


def render_righting_preview_v1(example: RightingPreviewExampleV1) -> str:
    """Render retained results without updating a source, task, PNM or body."""
    result = example.result
    facet = result.source.motor_support
    if facet is None:
        raise ValueError("H5 inspection requires the enhanced source facet")
    feedback = facet.feedback
    selected = result.attention.selected_source_state
    lines = [
        example.name, "-" * 76,
        f"  focal opportunity={result.cycle_id}; physical cutoff={result.cutoff_tick}; status={result.source_status}",
        f"  source={result.source.source_map_ref.map_id}@r{result.source.source_map_ref.revision}; current evidence={facet.current}",
    ]
    if feedback is not None:
        lines.append(
            f"  observed tilt={_quantity(feedback.body_tilt_degrees)}; load={_quantity(feedback.useful_loading)}; "
            f"destabilization={_quantity(feedback.destabilization)}; contact={feedback.support_contact}"
        )
        lines.append(f"  original sensor sample={feedback.sample_id}; event={feedback.event_tick}; available={feedback.available_tick}")
    tilt_rate, load_rate, instability_rate = facet.rates
    lines.extend([
        f"  rates / second: |tilt|={_quantity(tilt_rate)}; load={_quantity(load_rate)}; instability={_quantity(instability_rate)}",
        f"  owner persistence rank={result.persistence_rank}; Attention={result.attention.disposition.value}; "
        f"selected source={selected.source_map_ref.map_id if selected is not None else '(none)'}",
        f"  Navigation selected={result.navigation.selected_primitive_id or '(none)'}",
    ])
    if result.task is not None:
        lines.append(
            f"  task={result.task.task_id}; applications={result.task.applications}; status={result.task.status}; "
            f"original activity={result.task.context.activity.value}"
        )
    application = result.navigation.application
    if isinstance(application, RightingApplicationV1):
        request, preview = application.contribution, application.projection
        lines.extend([
            f"  contribution={application.strategy}; desired tilt={_quantity(request.desired_tilt_degrees)}; "
            f"desired extension={_quantity(request.desired_extension)}",
            f"  PNM PREVIEW: tilt={_quantity(preview.predicted_tilt)}; extension={_quantity(preview.predicted_extension)}; "
            f"load={_quantity(preview.predicted_loading)}; instability={_quantity(preview.predicted_destabilization)}",
            f"  prospective contact={preview.expected_contact}; observation horizon={facet.cutoff_tick + 1}.."
            f"{facet.cutoff_tick + preview.horizon_ticks}; unexecuted, conditional reference model",
        ])
    if result.proposal is not None:
        for binding in result.proposal.bindings:
            target = binding.target
            if not isinstance(target, BodyRelativeTargetV1):
                raise TypeError("this retained review expects a scalar support target")
            lines.append(f"  BodyMap {target.kind.value}: offset={target.offset:+.4f}; anchored endpoint={target.endpoint:+.4f}")
        for kind, reason in result.proposal.withheld:
            lines.append(f"  BodyMap {kind.value}: WITHHELD ({reason})")
    lines.append("  installed targets=0; motor commands=0; physical steps=0; durable updates=0; task success not established")
    return "\n".join(lines)


def run_righting_preview_review_v1() -> None:
    """Print the same finite preview review from the CLI or existing NCA8 menu."""
    print("P18-H5 RIGHTING PREVIEW -- REPLAYED SENSING, REAL TASK CALCULATION, NO MOVEMENT")
    print("Profile: righting_preview_v1; criteria and linear predictions are fixed engineering assumptions.")
    for index, example in enumerate(run_righting_preview_examples_v1(), 1):
        print(f"\n{index}) {render_righting_preview_v1(example)}")
    print("\nRIGHTING PREVIEW CHECKS COMPLETE -- H6 integration and 1G outcomes remain open.")
